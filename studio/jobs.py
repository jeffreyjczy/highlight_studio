"""Job queue: highlight runs (one `claude -p --agent highlight-maker` process per recording)
and merges (merge_highlights.py). Runs in background threads; the UI polls snapshot()."""
import json
import os
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path

from common import CLAUDE, DATA, NO_WINDOW, PIPE, PYTHON, SETTINGS, ledger

AGENT_TOOLS = "PowerShell,Bash,Read,Write,Edit,Glob,Grep"  # the highlight-maker's own tool list
HL_STEPS = ["Claim", "Probe", "Analyze", "Plan clips", "Render", "Check", "Finish"]
MERGE_STEPS = ["Read clips", "Beat-sync", "Plan cuts", "Encode", "Finish"]
LOGIN_HINT = "Claude Code isn't logged in. Open a terminal, run `claude`, log in, then try again."


def _child_env():
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)  # always use the logged-in Claude account, never API billing
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _hl_step(tool, inp, cur):
    """Map an agent tool call to a PROCEDURE.md step (only ever moves forward)."""
    text = json.dumps(inp, ensure_ascii=False).lower() if isinstance(inp, dict) else str(inp).lower()
    rules = [(6, ("ledger.py complete",)), (4, ("render_clip.py",)),
             (3, ("valorant_plan.py", "plan.json", "timeline.json")),
             (2, ("astats", "transcribe.py", "sheets.py", "valorant_killfeed.py", "ebur128", "silencedetect")),
             (1, ("ffprobe",)), (0, ("ledger.py scan", "ledger.py claim"))]
    for step, keys in rules:
        if any(k in text for k in keys):
            return max(cur, step)
    if cur >= 4 and tool == "Read" and re.search(r"\.(jpg|png)", text):
        return max(cur, 5)
    return cur


def _activity(tool, inp):
    if not isinstance(inp, dict):
        return tool
    if tool in ("Bash", "PowerShell"):
        cmd = (inp.get("description") or inp.get("command") or "").strip().splitlines()
        return (cmd[0] if cmd else tool)[:110]
    if tool in ("Read", "Write", "Edit"):
        return f"{tool} {Path(inp.get('file_path', '')).name}"
    return tool


class Jobs:
    def __init__(self, on_change=None):
        self.jobs = []
        self.lock = threading.RLock()
        self.procs = {}
        self.on_change = on_change or (lambda: None)
        threading.Thread(target=self._scheduler, daemon=True).start()

    # ------------------------------------------------------------ public
    def snapshot(self):
        with self.lock:
            now = time.time()
            out = []
            for j in self.jobs:
                d = {k: v for k, v in j.items() if not k.startswith("_")}
                d["elapsed"] = (j.get("ended") or now) - j["started"] if j.get("started") else 0
                out.append(d)
            return out

    def add_highlight(self, rec_path, game):
        model = SETTINGS.get("valorant_model", "sonnet") if game.lower() == "valorant" else None
        with self.lock:
            if any(j["kind"] == "highlight" and j["path"].lower() == rec_path.lower()
                   and j["state"] in ("queued", "running") for j in self.jobs):
                return None
            j = self._new("highlight", path=rec_path, game=game, model=model or "default",
                          title=Path(rec_path).stem, steps=HL_STEPS)
            self.jobs.insert(0, j)
        return j["id"]

    def add_merge(self, out, clips, args, name, music):
        with self.lock:
            j = self._new("merge", path=str(out), title=name, steps=MERGE_STEPS, clips=clips, music=music)
            j["_args"] = args
            self.jobs.insert(0, j)
        return j["id"]

    def cancel(self, jid):
        with self.lock:
            j = self._find(jid)
            if not j:
                return False
            if j["state"] == "queued":
                j.update(state="cancelled", ended=time.time(), error="Cancelled before it started")
                return True
            if j["state"] != "running":
                return False
            j["_cancel"] = True
            p = self.procs.get(jid)
        if p:
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True, creationflags=NO_WINDOW)
        return True

    def clear_finished(self):
        with self.lock:
            self.jobs = [j for j in self.jobs if j["state"] in ("queued", "running")]

    # ------------------------------------------------------------ internals
    def _new(self, kind, **kw):
        return {"id": uuid.uuid4().hex[:10], "kind": kind, "state": "queued", "step": 0, "activity": "Waiting",
                "started": None, "ended": None, "report": "", "error": "", "usage": None, **kw}

    def _find(self, jid):
        return next((j for j in self.jobs if j["id"] == jid), None)

    def _scheduler(self):
        while True:
            time.sleep(0.5)
            with self.lock:
                limit = max(1, int(SETTINGS.get("jobs_at_once", 1)))
                hl_running = sum(1 for x in self.jobs if x["kind"] == "highlight" and x["state"] == "running")
                merge_running = any(x["kind"] == "merge" and x["state"] == "running" for x in self.jobs)
                # highlight runs obey the limit; one merge (no Claude involved) can run beside them
                nxt = next((x for x in reversed(self.jobs) if x["state"] == "queued" and
                            ((x["kind"] == "highlight" and hl_running < limit) or
                             (x["kind"] == "merge" and not merge_running))), None)
                if not nxt:
                    continue
                nxt.update(state="running", started=time.time(), activity="Starting")
            target = self._run_highlight if nxt["kind"] == "highlight" else self._run_merge
            threading.Thread(target=self._guard, args=(target, nxt), daemon=True).start()

    def _guard(self, fn, j):
        try:
            fn(j)
        except Exception as e:  # never leave a job stuck in "running"
            with self.lock:
                j.update(state="failed", error=f"{type(e).__name__}: {e}", ended=time.time())
        self.on_change()

    def _finish(self, j, state, **kw):
        with self.lock:
            j.update(state=state, ended=time.time(), **kw)
            self.procs.pop(j["id"], None)

    # ------------------------------------------------------------ highlight
    def _run_highlight(self, j):
        rec = Path(j["path"])
        led = ledger.load()
        e = led["recordings"].get(ledger.key_of(rec))
        status = ledger.classify(rec, e) if rec.exists() else "missing"
        if status in ("failed", "stale"):
            led["recordings"].pop(ledger.key_of(rec), None)  # same as `ledger.py reset`
            ledger.save(led)
            status = "new"
        if status != "new":
            return self._finish(j, "failed", error=f"Can't start: the recording's status is '{status}'.")

        prompt = (f"Make highlights from this recording:\n{rec}\n\n"
                  "This run was started by the user from Highlight Studio. Process only this one recording. "
                  "Do not run cleanup or trash, and do not delete anything. "
                  "Finish with the report described in PROCEDURE.md.")
        cmd = [CLAUDE, "-p", "--agent", "highlight-maker", "--allowedTools", AGENT_TOOLS,
               "--output-format", "stream-json", "--verbose"]
        if j["model"] != "default":
            cmd += ["--model", j["model"]]
        log = DATA / "logs" / f"{time.strftime('%Y%m%d-%H%M%S')}-{j['id']}.jsonl"
        j["log"] = str(log)
        p = subprocess.Popen(cmd, cwd=str(PIPE), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, env=_child_env(), creationflags=NO_WINDOW,
                             text=True, encoding="utf-8", errors="replace", bufsize=1)
        with self.lock:
            self.procs[j["id"]] = p
        p.stdin.write(prompt)
        p.stdin.close()
        result, last_text, raw_tail = None, "", []
        with open(log, "w", encoding="utf-8") as lf:
            for line in p.stdout:
                lf.write(line)
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    raw_tail = (raw_tail + [line])[-20:]
                    continue
                t = ev.get("type")
                if t == "system" and ev.get("subtype") == "init":
                    with self.lock:
                        j["model_used"] = ev.get("model")
                        j["activity"] = "Reading PROCEDURE.md"
                elif t == "assistant":
                    for c in (ev.get("message") or {}).get("content") or []:
                        if c.get("type") == "tool_use":
                            with self.lock:
                                j["step"] = _hl_step(c.get("name"), c.get("input"), j["step"])
                                j["activity"] = _activity(c.get("name"), c.get("input"))
                        elif c.get("type") == "text" and c.get("text", "").strip():
                            last_text = c["text"].strip()
                elif t == "result":
                    result = ev
        p.wait()
        cancelled = j.get("_cancel")
        text = (result or {}).get("result") or last_text
        usage = None
        if result:
            u = result.get("usage") or {}
            usage = {"duration_s": round((result.get("duration_ms") or 0) / 1000),
                     "turns": result.get("num_turns"),
                     "tokens": sum(int(u.get(k) or 0) for k in ("input_tokens", "output_tokens",
                                                                 "cache_creation_input_tokens", "cache_read_input_tokens")),
                     "output_tokens": u.get("output_tokens")}
        # the ledger is the truth about how it ended
        led = ledger.load()
        e = led["recordings"].get(ledger.key_of(rec)) or {}
        if e.get("status") == "processing":
            reason = "Cancelled from Highlight Studio" if cancelled else "Agent stopped before finishing"
            e.update(status="failed", failed_at=ledger.now_iso(), reason=reason)
            ledger.save(led)
        e_status = e.get("status")
        blob = (text or "") + " " + " ".join(raw_tail)
        if cancelled:
            return self._finish(j, "cancelled", report=text, usage=usage, error="Cancelled")
        if e_status == "done":
            return self._finish(j, "done", step=len(HL_STEPS) - 1, report=text, usage=usage,
                                clips=e.get("clip_count"), clips_dir=e.get("clips_dir"))
        err = LOGIN_HINT if re.search(r"log ?in|/login|authenticat|invalid api key|oauth", blob, re.I) and \
            not result else (e.get("reason") or (text[-400:] if text else "") or " ".join(raw_tail)[-400:]
                             or f"claude exited with code {p.returncode}")
        self._finish(j, "failed", report=text, usage=usage, error=err)

    # ------------------------------------------------------------ merge
    def _run_merge(self, j):
        cmd = [PYTHON, "-u", str(PIPE / "merge_highlights.py")] + j["_args"]
        log = DATA / "logs" / f"{time.strftime('%Y%m%d-%H%M%S')}-{j['id']}-merge.log"
        j["log"] = str(log)
        p = subprocess.Popen(cmd, cwd=str(PIPE), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             env=_child_env(), creationflags=NO_WINDOW, text=True, encoding="utf-8",
                             errors="replace", bufsize=1)
        with self.lock:
            self.procs[j["id"]] = p
        out_path, tail = None, []
        with open(log, "w", encoding="utf-8") as lf:
            for line in p.stdout:
                lf.write(line)
                s = line.strip()
                tail = (tail + [s])[-30:]
                with self.lock:
                    if re.search(r"actions, \d+ deaths", s):
                        j["step"], j["activity"] = max(j["step"], 0), s.split(":")[0]
                    elif s.startswith("music:"):
                        j["step"], j["activity"] = max(j["step"], 1), s
                    elif s.startswith("plan ("):
                        j["step"], j["activity"] = 3, "Encoding with the GPU (h264_amf)"
                    elif s.startswith("over "):
                        j["activity"] = s
                    m = re.match(r"merged \d+ clips -> (.+?)\s+planned", s)
                    if m:
                        out_path = m.group(1)
        p.wait()
        if j.get("_cancel"):
            return self._finish(j, "cancelled", error="Cancelled")
        if p.returncode == 0 and out_path:
            return self._finish(j, "done", step=len(MERGE_STEPS) - 1, out=out_path,
                                report=next((t for t in reversed(tail) if t.startswith("merged")), ""))
        self._finish(j, "failed", error="\n".join(t for t in tail if t)[-600:] or f"exit code {p.returncode}")
