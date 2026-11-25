"""Highlight pipeline ledger: tracks which recordings have been worked on.

The ledger is the single source of truth for "already processed" and is the ONLY
thing allowed to delete original recordings. Deletion is restricted to recordings
that this pipeline finished (status "done"), whose file is unchanged since it was
processed, that are not open by any program, and whose highlights folder exists.
New footage is never in that state, so it can never be deleted.

Usage (python ledger.py <command> ...):
  scan [--json]                       Show every recording and its status
  claim <recording>                   Mark a finished, new recording as "processing"
  complete <recording> <clips_dir>    Mark as "done" (clips_dir must hold clips.json)
  fail <recording> <reason>           Mark as "failed" (can be retried with reset)
  reset <recording>                   Forget a recording so it is treated as new
  cleanup-plan [--json]               List originals that are safe to delete
  cleanup --confirm <recording>...    Delete those originals (re-checked first)
  cleanup --confirm --all             Delete every original in the cleanup plan
  trash --confirm <file>...           Move files to the Recycle Bin (Highlight Studio's Delete);
                                      originals in the ledger become "original_deleted"
"""
import ctypes
from ctypes import wintypes
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Env overrides exist only for testing against dummy folders.
RECORDINGS_ROOT = Path(os.environ.get("HL_RECORDINGS_ROOT", r"E:\Recordings"))
HIGHLIGHTS_ROOT = Path(os.environ.get("HL_HIGHLIGHTS_ROOT", r"E:\Highlights"))
LEDGER_PATH = HIGHLIGHTS_ROOT / "_ledger.json"
VIDEO_EXTS = {".mp4", ".mkv", ".mov"}
MIN_SIZE_BYTES = 100 * 1024 * 1024   # smaller files are accidental start/stop clips
SETTLE_SECONDS = 120                 # unchanged this long = recording finished
STALE_PROCESSING_HOURS = 6


# ---------- helpers ----------

def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def key_of(path):
    return str(Path(path).resolve()).lower()


def fingerprint(path):
    st = Path(path).stat()
    return {"size": st.st_size, "mtime": int(st.st_mtime)}


def is_locked(path):
    """True if another program (e.g. the recorder) has the file open."""
    GENERIC_READ, OPEN_EXISTING, SHARE_NONE = 0x80000000, 3, 0
    INVALID = ctypes.c_void_p(-1).value
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = ctypes.c_void_p
    h = k32.CreateFileW(str(path), GENERIC_READ, SHARE_NONE, None, OPEN_EXISTING, 0, None)
    if h == INVALID:
        return ctypes.get_last_error() in (32, 33)  # sharing / lock violation
    k32.CloseHandle(ctypes.c_void_p(h))
    return False


class _SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]


def recycle(path):
    """Move one file to the Recycle Bin. Returns True if the file is gone afterwards.

    FOF_WANTNUKEWARNING makes Windows ask first if a file is too big for the Recycle Bin
    and would be deleted permanently instead."""
    FO_DELETE, FOF_SILENT, FOF_NOCONFIRMATION, FOF_ALLOWUNDO, FOF_NOERRORUI, FOF_WANTNUKEWARNING = \
        3, 0x4, 0x10, 0x40, 0x400, 0x4000
    p = str(Path(path).resolve())
    op = _SHFILEOPSTRUCTW(None, FO_DELETE, p + "\0", None,
                          FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI | FOF_WANTNUKEWARNING,
                          False, None, None)
    ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    return not Path(p).exists()


def trash_files(paths):
    """Recycle files; originals known to the ledger are marked original_deleted.

    Refuses recordings that are being processed or still open (being recorded).
    Returns [{path, ok, reason, size}]."""
    ledger = load()
    results = []
    for raw in paths:
        p = Path(raw)
        if not p.exists():
            results.append({"path": str(p), "ok": False, "reason": "not found", "size": 0})
            continue
        size = p.stat().st_size
        e = ledger["recordings"].get(key_of(p))
        if e and e["status"] == "processing":
            results.append({"path": str(p), "ok": False, "reason": "being processed", "size": size})
            continue
        if p.suffix.lower() in VIDEO_EXTS and is_locked(p):
            results.append({"path": str(p), "ok": False, "reason": "open in another program", "size": size})
            continue
        if not recycle(p):
            results.append({"path": str(p), "ok": False, "reason": "Windows did not move it", "size": size})
            continue
        if e:
            e.update(status="original_deleted", deleted_at=now_iso(), deleted_via="recycle bin")
            save(ledger)
        results.append({"path": str(p), "ok": True, "reason": "", "size": size})
    return results


def load():
    if LEDGER_PATH.exists():
        return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    return {"version": 1, "recordings": {}}


def save(ledger):
    HIGHLIGHTS_ROOT.mkdir(parents=True, exist_ok=True)
    tmp = LEDGER_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, LEDGER_PATH)


def iter_recordings():
    if not RECORDINGS_ROOT.exists():
        return
    for p in sorted(RECORDINGS_ROOT.rglob("*")):
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS:
            yield p


def classify(path, entry):
    """Return the status of a recording on disk, combining disk state and ledger."""
    fp = fingerprint(path)
    if entry:
        status = entry["status"]
        if status == "original_deleted":
            status = "done"  # restored from the Recycle Bin: still has its highlights
        if status in ("processing", "done") and entry.get("fingerprint") != fp:
            return "changed"  # file differs from what was processed: never auto-delete
        if status == "processing":
            started = datetime.fromisoformat(entry["claimed_at"])
            if (datetime.now() - started).total_seconds() > STALE_PROCESSING_HOURS * 3600:
                return "stale"
        return status
    if fp["size"] < MIN_SIZE_BYTES:
        return "too_small"
    if time.time() - fp["mtime"] < SETTLE_SECONDS or is_locked(path):
        return "recording"
    return "new"


def cleanup_candidates(ledger):
    out = []
    for key, e in ledger["recordings"].items():
        if e["status"] != "done":
            continue
        src = Path(e["path"])
        reasons = []
        if not src.exists():
            reasons.append("original already gone")
        else:
            if fingerprint(src) != e["fingerprint"]:
                reasons.append("file changed since processing")
            if is_locked(src):
                reasons.append("file is open in another program")
        clips_dir = Path(e.get("clips_dir", ""))
        if not (clips_dir / "clips.json").exists():
            reasons.append("highlights folder / clips.json missing")
        out.append({"key": key, "path": str(src), "game": e.get("game"),
                    "size_gb": round(e["fingerprint"]["size"] / 1e9, 2),
                    "clips_dir": str(clips_dir), "clip_count": e.get("clip_count"),
                    "safe": not reasons, "blocked_because": reasons})
    return out


def need(args, n, usage):
    if len(args) < n:
        sys.exit(f"usage: ledger.py {usage}")


# ---------- commands ----------

def cmd_scan(args):
    ledger = load()
    rows = []
    for p in iter_recordings():
        e = ledger["recordings"].get(key_of(p))
        st = p.stat()
        rows.append({"path": str(p), "game": p.parent.name, "status": classify(p, e),
                     "size_gb": round(st.st_size / 1e9, 2),
                     "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="minutes")})
    if "--json" in args:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return
    for r in rows:
        print(f"{r['status']:<10} {r['size_gb']:>7.2f} GB  {r['modified']}  {r['path']}")
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("\n" + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))


def cmd_claim(args):
    need(args, 1, "claim <recording>")
    p = Path(args[0]).resolve()
    if not p.exists():
        sys.exit(f"ERROR: not found: {p}")
    ledger = load()
    status = classify(p, ledger["recordings"].get(key_of(p)))
    if status != "new":
        sys.exit(f"ERROR: cannot claim, status is '{status}' (only 'new' can be claimed)")
    ledger["recordings"][key_of(p)] = {
        "path": str(p), "game": p.parent.name, "status": "processing",
        "fingerprint": fingerprint(p), "claimed_at": now_iso()}
    save(ledger)
    print(f"claimed: {p}")


def cmd_complete(args):
    need(args, 2, "complete <recording> <clips_dir>")
    p, clips_dir = Path(args[0]).resolve(), Path(args[1]).resolve()
    ledger = load()
    e = ledger["recordings"].get(key_of(p))
    if not e or e["status"] != "processing":
        sys.exit("ERROR: recording is not in 'processing' state")
    if fingerprint(p) != e["fingerprint"]:
        sys.exit("ERROR: recording changed while processing; not marking done")
    manifest = clips_dir / "clips.json"
    if not manifest.exists():
        sys.exit(f"ERROR: {manifest} missing")
    clips = json.loads(manifest.read_text(encoding="utf-8")).get("clips", [])
    e.update(status="done", completed_at=now_iso(), clips_dir=str(clips_dir), clip_count=len(clips))
    save(ledger)
    print(f"done: {p} ({len(clips)} clips -> {clips_dir})")


def cmd_fail(args):
    need(args, 2, "fail <recording> <reason>")
    p = Path(args[0]).resolve()
    ledger = load()
    e = ledger["recordings"].get(key_of(p))
    if not e:
        sys.exit("ERROR: recording not in ledger")
    e.update(status="failed", failed_at=now_iso(), reason=" ".join(args[1:]))
    save(ledger)
    print(f"failed: {p}")


def cmd_reset(args):
    need(args, 1, "reset <recording>")
    ledger = load()
    if ledger["recordings"].pop(key_of(args[0]), None) is None:
        sys.exit("ERROR: recording not in ledger")
    save(ledger)
    print(f"reset: {args[0]}")


def cmd_cleanup_plan(args):
    cands = cleanup_candidates(load())
    if "--json" in args:
        print(json.dumps(cands, indent=2, ensure_ascii=False))
        return
    safe = [c for c in cands if c["safe"]]
    for c in safe:
        print(f"SAFE     {c['size_gb']:>7.2f} GB  {c['clip_count']} clips  {c['path']}")
    for c in cands:
        if not c["safe"] and "original already gone" not in c["blocked_because"]:
            print(f"BLOCKED  {c['size_gb']:>7.2f} GB  {c['path']}  ({'; '.join(c['blocked_because'])})")
    print(f"\n{len(safe)} original(s) safe to delete, "
          f"{sum(c['size_gb'] for c in safe):.2f} GB would be freed.")


def cmd_cleanup(args):
    if "--confirm" not in args:
        sys.exit("ERROR: cleanup deletes files; pass --confirm (run cleanup-plan first)")
    targets = [a for a in args if not a.startswith("--")]
    ledger = load()
    safe = {c["key"]: c for c in cleanup_candidates(ledger) if c["safe"]}
    if "--all" in args:
        keys = list(safe)
    else:
        if not targets:
            sys.exit("ERROR: name the recordings to delete, or pass --all")
        keys = [key_of(t) for t in targets]
    freed = 0.0
    for k in keys:
        if k not in safe:
            print(f"REFUSED  {k}  (not a finished, unchanged, closed recording with highlights)")
            continue
        path = Path(safe[k]["path"])
        os.remove(path)
        e = ledger["recordings"][k]
        e.update(status="original_deleted", deleted_at=now_iso())
        save(ledger)
        freed += safe[k]["size_gb"]
        print(f"DELETED  {path}")
    print(f"\nfreed {freed:.2f} GB")


def cmd_trash(args):
    if "--confirm" not in args:
        sys.exit("ERROR: trash moves files to the Recycle Bin; pass --confirm")
    targets = [a for a in args if not a.startswith("--")]
    if not targets:
        sys.exit("ERROR: name the files to move to the Recycle Bin")
    freed = 0
    for r in trash_files(targets):
        print(f"{'RECYCLED' if r['ok'] else 'REFUSED '}  {r['path']}" + ("" if r["ok"] else f"  ({r['reason']})"))
        freed += r["size"] if r["ok"] else 0
    print(f"\n{freed / 1e9:.2f} GB moved to the Recycle Bin (freed when it is emptied)")


COMMANDS = {"scan": cmd_scan, "claim": cmd_claim, "complete": cmd_complete,
            "fail": cmd_fail, "reset": cmd_reset,
            "cleanup-plan": cmd_cleanup_plan, "cleanup": cmd_cleanup, "trash": cmd_trash}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    COMMANDS[sys.argv[1]](sys.argv[2:])
