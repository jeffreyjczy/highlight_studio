"""Highlight Studio: desktop app for the highlight pipeline. Start with .venv\\Scripts\\pythonw.exe studio\\main.py"""
import ctypes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import webview  # noqa: E402

import media_server  # noqa: E402
from api import Api  # noqa: E402
from common import DATA, SETTINGS, STUDIO, save_settings  # noqa: E402

TITLE = "Highlight Studio"


def single_instance():
    """Only one copy may run (two would schedule jobs on the same ledger). A second launch
    brings the open window to the front instead."""
    k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
    k32.CreateMutexW(None, False, "Local\\HighlightStudioSingleInstance")
    if k32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        hwnd = u32.FindWindowW(None, TITLE)
        if hwnd:
            u32.ShowWindow(hwnd, 9)  # SW_RESTORE
            u32.SetForegroundWindow(hwnd)
        sys.exit(0)


def main():
    single_instance()
    try:  # own taskbar group, so the pinned/desktop shortcut and the window share an icon
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("HighlightStudio.App")
    except Exception:
        pass
    port = media_server.start()
    api = Api(port)
    win_cfg = SETTINGS.get("window") or {}
    # --open page[:tab] starts on a given page (e.g. --open music:ncs)
    start = sys.argv[sys.argv.index("--open") + 1] if "--open" in sys.argv[:-1] else ""
    window = webview.create_window(
        TITLE, f"http://127.0.0.1:{port}/" + (f"#open={start}" if start else ""), js_api=api,
        width=win_cfg.get("w", 1440), height=win_cfg.get("h", 900), min_size=(980, 640),
        background_color="#202020", text_select=True)
    api._bind(window)

    def on_shown():
        ico = STUDIO / "studio.ico"
        if ico.exists():
            try:
                from System import Action  # pythonnet (WinForms backend)
                from System.Drawing import Icon
                form = window.native
                form.Invoke(Action(lambda: setattr(form, "Icon", Icon(str(ico)))))
            except Exception as e:
                (DATA / "logs" / "icon_error.txt").write_text(repr(e), encoding="utf-8")

    def on_resized(w, h):
        SETTINGS["window"] = {"w": w, "h": h}

    def on_closing():
        if api.running_jobs():
            ok = window.create_confirmation_dialog(
                "Jobs are still running",
                "Closing Highlight Studio stops them. A stopped highlight run is marked failed and can be retried. Close anyway?")
            if not ok:
                return False
            api.stop_all()
        save_settings(SETTINGS)
        return True

    window.events.shown += on_shown
    window.events.resized += on_resized
    window.events.closing += on_closing
    webview.start(gui="edgechromium", private_mode=False, storage_path=str(DATA / "webview"))


if __name__ == "__main__":
    main()
