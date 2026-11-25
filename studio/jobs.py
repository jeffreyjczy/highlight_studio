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

HISTORY = DATA / "jobs.json"   # finished jobs are kept here so they show again after a restart
HISTORY_MAX = 100

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
        self._load()
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
        self._save()
        return j["id"]

    def add_merge(self, out, clips, args, name, music):
        with self.lock:
            j = self._new("merge", path=str(out), title=name, steps=MERGE_STEPS, clips=clips, music=music)
            j["_args"] = args
            self.jobs.insert(0, j)
        self._save()
        return j["id"]

    def add_upload(self, path, meta):
        with self.lock:
            j = self._new("upload", path=str(path), title=meta["title"], steps=["Upload", "Finish"], meta=meta,
                          progress=0.0, privacy=meta.get("privacy"))
            self.jobs.insert(0, j)
        self._save()
        return j["id"]

    def cancel(self, jid):
        with self.lock:
            j = self._find(jid)
            if not j:
                return False
            if j["state"] == "queued":
                j.update(state="cancelled", ended=time.time(), error="Cancelled before it started")
                self._save()
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
        self._save()

    # ------------------------------------------------------------ history (survives closing the app)
    def _load(self):
        try:
            saved = json.loads(HISTORY.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for j in saved:
            if j.get("state") in ("queued", "running"):  # the app was closed while it ran
                j.update(state="failed" if j["state"] == "running" else "cancelled",
                         ended=j.get("ended") or j.get("started") or time.time(),
                         error=j.get("error") or "Stopped because the app was closed")
            self.jobs.append(j)

    def _save(self):
        with self.lock:
            keep = [{k: v for k, v in j.items() if not k.startswith("_")} for j in self.jobs]
            done = [j for j in keep if j["state"] not in ("queued", "running")][:HISTORY_MAX]
            keep = [j for j in keep if j["state"] in ("queued", "running")] + done
        try:
            tmp = HISTORY.with_suffix(".tmp")
            tmp.write_text(json.dumps(keep, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, HISTORY)
        except OSError:
            pass

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
                busy = {x["kind"] for x in self.jobs if x["state"] == "running"}
                # highlight runs obey the limit; one merge and one upload can run beside them
                nxt = next((x for x in reversed(self.jobs) if x["state"] == "queued" and
                            ((x["kind"] == "highlight" and hl_running < limit) or
                             (x["kind"] in ("merge", "upload") and x["kind"] not in busy))), None)
                if not nxt:
                    continue
                nxt.update(state="running", started=time.time(), activity="Starting")
            self._save()
            target = {"highlight": self._run_highlight, "merge": self._run_merge, "upload": self._run_upload}[nxt["kind"]]
            threading.Thread(target=self._guard, args=(target, nxt), daemon=True).start()

    def _guard(self, fn, j):
        try:
            fn(j)
        except Exception as e:  # never leave a job stuck in "running"
            with self.lock:
                j.update(state="failed", error=f"{type(e).__name__}: {e}", ended=time.time())
        self._save()
        self.on_change()

    def _finish(self, j, state, **kw):
        with self.lock:
            j.update(state=state, ended=time.time(), **kw)
            self.procs.pop(j["id"], None)
        self._save()

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

    # ------------------------------------------------------------ YouTube upload
    def _run_upload(self, j):
        import youtube
        src = Path(j["path"])
        if not src.exists():
            return self._finish(j, "failed", error="The merged video no longer exists.")
        with self.lock:
            j["activity"] = "Uploading to YouTube"

        def progress(f):
            with self.lock:
                j["progress"] = round(f, 4)
                j["activity"] = f"Uploading to YouTube, {f * 100:.0f}% of {src.stat().st_size / 1048576:.0f} MB"
        try:
            res = youtube.upload(src, j["meta"], progress, lambda: bool(j.get("_cancel")))
        except youtube.YTError as e:
            if j.get("_cancel"):
                return self._finish(j, "cancelled", error="Cancelled. Nothing was published.")
            return self._finish(j, "failed", error=str(e))
        record = src.with_suffix(".youtube.json")
        history = []
        if record.exists():
            try:
                old = json.loads(record.read_text(encoding="utf-8"))
                history = old if isinstance(old, list) else [old]
            except (OSError, ValueError):
                pass
        record.write_text(json.dumps(history + [res], indent=1, ensure_ascii=False), encoding="utf-8")
        forced = res["privacy_requested"] in ("public", "unlisted") and res["privacy"] == "private"
        self._finish(j, "done", step=1, progress=1.0, out=res["url"], studio=res["studio"], yt=res, forced_private=forced,
                     report=("YouTube kept this video Private (new API apps can only upload privately until Google "
                             "reviews them). Open it in YouTube Studio to make it public.") if forced else
                     f"Uploaded as {res['privacy_requested']}: {res['url']}")

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
