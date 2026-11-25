"""Start/stop AMD Adrenalin recording by pressing its record hotkey, and read the
recording state from the recordings folder.

Adrenalin has no API, so the app presses the same hotkey the user would. Whether a
recording is running is read from disk: Adrenalin keeps the file it records into
locked (LastWriteTime is no use - Windows updates it late for open files), and the
file's creation time is when the recording started.
"""
import ctypes
import subprocess
import threading
import time
import winreg
from ctypes import wintypes
from pathlib import Path

from common import NO_WINDOW, RECORDINGS_ROOT, SETTINGS, ledger

RECENT = 24 * 3600     # only files created in the last day can be the live recording
GROW_WINDOW = 12.0     # a recording file grows every second; still this long = not recording
HANDSHAKE = 8.0        # seconds to wait for Adrenalin to start/stop after the key press

# ---------------------------------------------------------------- hotkey
_MODS = {"ctrl": 0x11, "control": 0x11, "shift": 0x10, "alt": 0x12, "win": 0x5B}
KEYEVENTF_KEYUP = 0x0002


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", _KEYBDINPUT), ("pad", ctypes.c_byte * 32)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def parse_hotkey(text):
    """'Ctrl+Shift+E' -> ([0x11, 0x10], 0x45). Raises ValueError if it can't be pressed."""
    parts = [p.strip().lower() for p in (text or "").split("+") if p.strip()]
    if not parts:
        raise ValueError("no hotkey set")
    mods, key = [], None
    for p in parts:
        if p in _MODS:
            mods.append(_MODS[p])
        elif len(p) == 1 and p.isalnum():
            key = ord(p.upper())
        elif p.startswith("f") and p[1:].isdigit() and 1 <= int(p[1:]) <= 24:
            key = 0x70 + int(p[1:]) - 1
        else:
            raise ValueError(f"unknown key '{p}'")
    if key is None:
        raise ValueError("the hotkey needs a letter, number or F-key")
    return mods, key


def press(text):
    mods, key = parse_hotkey(text)
    seq = [(vk, 0) for vk in mods] + [(key, 0), (key, KEYEVENTF_KEYUP)] + [(vk, KEYEVENTF_KEYUP) for vk in reversed(mods)]
    for vk, flags in seq:
        inp = _INPUT(type=1)  # INPUT_KEYBOARD
        inp.ki = _KEYBDINPUT(vk, 0, flags, 0, 0)
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))
        time.sleep(0.03)


# ---------------------------------------------------------------- Adrenalin
_run_cache = [0.0, False]


def adrenalin_running():
    if time.time() - _run_cache[0] < 10:
        return _run_cache[1]
    try:
        out = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True,
                             creationflags=NO_WINDOW, timeout=10).stdout.lower()
        ok = "radeonsoftware.exe" in out or "amdrsserv.exe" in out
    except Exception:
        ok = True  # can't tell: don't block the button
    _run_cache[:] = [time.time(), ok]
    return ok


def output_dir():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\AMD\DVR") as k:
            return winreg.QueryValueEx(k, "CaptureFileOutput")[0]
    except OSError:
        return None


# ---------------------------------------------------------------- state
class Recorder:
    def __init__(self):
        self._lock = threading.Lock()
        self._cache = (0.0, None)
        self._sizes = {}  # path -> (size, when it last changed)
        self._phase, self._phase_at, self._error = "", 0.0, ""

    def _scan(self):
        """The live recording: a recent file that Adrenalin keeps open AND that is still
        growing. (Adrenalin sometimes keeps a finished file open for hours, so a lock
        alone isn't proof.) The size is read through a handle, because the directory
        entry's size also lags for open files."""
        now, live, seen = time.time(), None, {}
        for p in ledger.iter_recordings():
            try:
                st = p.stat()
            except OSError:
                continue
            if now - st.st_ctime > RECENT or not ledger.is_locked(p):
                continue
            try:
                with open(p, "rb") as f:
                    size = f.seek(0, 2)
            except OSError:
                continue
            key = str(p)
            prev = self._sizes.get(key)
            changed = prev[1] if prev and prev[0] == size else now
            if prev is None and now - st.st_ctime > 30:
                # first look at an older open file (e.g. the app was just reopened mid-recording):
                # check right away whether it is still growing instead of waiting for the next poll
                time.sleep(1.5)
                try:
                    with open(p, "rb") as f:
                        changed = now if f.seek(0, 2) != size else 0.0
                except OSError:
                    changed = 0.0
            seen[key] = (size, changed)
            if now - changed <= GROW_WINDOW and (live is None or st.st_ctime > live[1].st_ctime):
                live = (p, st, size)
        self._sizes = seen
        if not live:
            return None
        p, st, size = live
        game = p.parent.name if p.parent != RECORDINGS_ROOT else p.stem
        return {"path": str(p), "game": game, "started_at": st.st_ctime, "size": size}

    def status(self):
        with self._lock:
            t, live = self._cache
            if time.time() - t > 1.0:
                live = self._scan()
                self._cache = (time.time(), live)
            # finish the start/stop handshake
            if self._phase in ("starting", "stopping"):
                done = (self._phase == "starting" and live and live["started_at"] >= self._phase_at - 5) or \
                       (self._phase == "stopping" and not live)
                if done:
                    self._phase = ""
                elif time.time() - self._phase_at > HANDSHAKE:
                    self._error = ("Adrenalin didn't start recording. Is it running, and does the hotkey match "
                                   "Adrenalin's Record video hotkey?") if self._phase == "starting" else \
                                  "Adrenalin didn't stop recording. Check the hotkey, or stop it in Adrenalin."
                    self._phase, self._phase_at = "failed", time.time()
            elif self._phase == "failed" and time.time() - self._phase_at > 15:
                self._phase, self._error = "", ""
            return {"recording": bool(live), **(live or {}), "phase": self._phase, "error": self._error,
                    "hotkey": SETTINGS.get("rec_hotkey", "Ctrl+Shift+E")}

    def toggle(self):
        hk = SETTINGS.get("rec_hotkey", "Ctrl+Shift+E")
        try:
            parse_hotkey(hk)
        except ValueError as e:
            return {"ok": False, "error": f"The record hotkey isn't valid ({e}). Set it in Settings."}
        if not adrenalin_running():
            return {"ok": False, "error": "AMD Adrenalin isn't running. Open AMD Software, then try again."}
        with self._lock:
            self._cache = (0.0, self._cache[1])  # re-check right away
        recording = self.status()["recording"]
        press(hk)
        with self._lock:
            self._phase, self._phase_at, self._error = ("stopping" if recording else "starting"), time.time(), ""
            self._cache = (0.0, self._cache[1])
        return {"ok": True, "phase": self._phase}

    def info(self):
        out = output_dir()
        return {"adrenalin": adrenalin_running(), "output": out,
                "output_ok": out is None or Path(out).resolve() == RECORDINGS_ROOT.resolve(),
                "recordings": str(RECORDINGS_ROOT), "hotkey": SETTINGS.get("rec_hotkey", "Ctrl+Shift+E")}
