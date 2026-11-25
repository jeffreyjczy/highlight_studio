"""Shared paths, settings and small helpers for Highlight Studio."""
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

STUDIO = Path(__file__).resolve().parent
PIPE = STUDIO.parent
sys.path.insert(0, str(PIPE))
import ledger  # noqa: E402  (pipeline module: scan state, classify, recycle)

RECORDINGS_ROOT = ledger.RECORDINGS_ROOT
HIGHLIGHTS_ROOT = ledger.HIGHLIGHTS_ROOT
DATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "HighlightStudio"
for sub in ("thumbs", "logs", "tmp"):
    (DATA / sub).mkdir(parents=True, exist_ok=True)

_FF_DIR = Path(r"C:\Users\jeffr\AppData\Local\Microsoft\WinGet\Packages"
               r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.1-full_build\bin")
FFMPEG = shutil.which("ffmpeg") or str(_FF_DIR / "ffmpeg.exe")
FFPROBE = shutil.which("ffprobe") or str(_FF_DIR / "ffprobe.exe")
# Pipeline scripts run with the system Python (numpy etc.), like PROCEDURE.md says.
PYTHON = shutil.which("python") or r"C:\Users\jeffr\AppData\Local\Programs\Python\Python313\python.exe"
CLAUDE = shutil.which("claude") or str(Path.home() / ".local" / "bin" / "claude.exe")

NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW: no console flashes from pythonw

DEFAULTS = {
    "merged_root": r"E:\Merged",
    "music_root": r"E:\Music\Highlights",
    "jobs_at_once": 1,
    "valorant_model": "sonnet",
    "watch_downloads": True,
    "theme": "system",
    "rec_hotkey": "Ctrl+Shift+E",
    "last_page": "footage",
    "merge": {"fmt": "short", "hq": True, "style": "punchy", "music": "any"},
}
_lock = threading.Lock()
_SETTINGS_FILE = DATA / "settings.json"


def load_settings():
    s = json.loads(json.dumps(DEFAULTS))
    try:
        s.update(json.loads(_SETTINGS_FILE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return s


def save_settings(s):
    with _lock:
        tmp = _SETTINGS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, _SETTINGS_FILE)


SETTINGS = load_settings()


def merged_root():
    return Path(SETTINGS["merged_root"])


def music_root():
    return Path(SETTINGS["music_root"])


def allowed_roots():
    return [RECORDINGS_ROOT, HIGHLIGHTS_ROOT, merged_root(), music_root()]


def is_inside(path, roots=None):
    try:
        p = Path(path).resolve()
    except OSError:
        return False
    for r in roots or allowed_roots():
        try:
            p.relative_to(Path(r).resolve())
            return True
        except ValueError:
            continue
    return False


def run(cmd, timeout=None, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, creationflags=NO_WINDOW, **kw)


def downloads_dir():
    """The user's Downloads folder (Known Folder, so a moved folder is found too)."""
    try:
        import ctypes
        from ctypes import wintypes
        import uuid

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                        ("Data4", wintypes.BYTE * 8)]
        u = uuid.UUID("{374DE290-123F-4565-9164-39C4925E467B}")
        g = GUID(u.fields[0], u.fields[1], u.fields[2], (wintypes.BYTE * 8).from_buffer_copy(u.bytes[8:]))
        out = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(out)) == 0:
            p = Path(out.value)
            ctypes.windll.ole32.CoTaskMemFree(out)
            return p
    except Exception:
        pass
    return Path.home() / "Downloads"
