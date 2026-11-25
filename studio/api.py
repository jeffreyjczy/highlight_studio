"""Methods the UI calls through pywebview (window.pywebview.api.*). Each returns plain JSON data."""
import json
import os
import random
import re
import subprocess
import threading
import time
from pathlib import Path

import library
import music
from common import (CLAUDE, DATA, HIGHLIGHTS_ROOT, NO_WINDOW, PIPE, PYTHON, RECORDINGS_ROOT, SETTINGS,
                    is_inside, ledger, merged_root, music_root, run, save_settings)
from jobs import Jobs
from media_server import TOKEN


def _safe_name(s):
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", s or "").strip().rstrip(".")
    return (s or "Merged video")[:80]


class Api:
    def __init__(self, port):
        self._port = port
        self._window = None
        self._added = []  # music that the Downloads watcher brought in, for UI toasts
        self._jobs = Jobs()
        self._watcher = music.Watcher(lambda a: self._added.append(a))

    def _bind(self, window):
        self._window = window

    # ------------------------------------------------------------ basics
    def init(self):
        cred = Path.home() / ".claude" / ".credentials.json"
        return {"port": self._port, "token": TOKEN, "settings": SETTINGS, "disk": library.disk_usage(),
                "claude": {"path": CLAUDE, "found": Path(CLAUDE).exists(), "signed_in": cred.exists()},
                "roots": {"recordings": str(RECORDINGS_ROOT), "highlights": str(HIGHLIGHTS_ROOT),
                          "merged": str(merged_root()), "music": str(music_root())}}

    def disk(self):
        return library.disk_usage()

    def footage(self):
        return library.scan_footage()

    def shorts(self):
        sets = library.scan_shorts()
        used = {}
        for m in library.scan_merged():
            for c in m["clips"]:
                used[str(c).lower()] = used.get(str(c).lower(), 0) + 1
        for s in sets:
            for c in s["clips"]:
                c["used"] = used.get(c["path"].lower(), 0)
        return sets

    def merged(self):
        return library.scan_merged()

    def playbooks(self):
        return library.playbooks()

    def reveal_playbook(self, file):
        p = Path(file)
        if p.parent.resolve() == (PIPE / "games").resolve() and p.exists():
            subprocess.Popen(["explorer", "/select,", str(p)], creationflags=NO_WINDOW)

    def set_fullscreen(self, on):
        """Real full screen for the video viewer: hides the window's title bar and its close button."""
        on = bool(on)
        if self._window and on != getattr(self, "_fs", False):
            self._window.toggle_fullscreen()
            self._fs = on
        return on

    def settings_set(self, patch):
        for k, v in (patch or {}).items():
            if k in ("merged_root", "music_root", "jobs_at_once", "valorant_model", "watch_downloads",
                     "theme", "last_page", "merge", "window"):
                SETTINGS[k] = v
        save_settings(SETTINGS)
        return SETTINGS

    def pick_folder(self, key):
        import webview
        if key not in ("merged_root", "music_root"):
            return None
        r = self._window.create_file_dialog(webview.FileDialog.FOLDER, directory=SETTINGS.get(key, ""))
        if r:
            self.settings_set({key: r[0]})
            return r[0]
        return None

    def reveal(self, path):
        p = Path(path)
        if is_inside(p) and p.exists():
            subprocess.Popen(["explorer", "/select,", str(p)], creationflags=NO_WINDOW)

    def open_folder(self, key):
        p = {"recordings": RECORDINGS_ROOT, "highlights": HIGHLIGHTS_ROOT, "merged": merged_root(),
             "music": music_root(), "logs": DATA / "logs"}.get(key)
        if p:
            p.mkdir(parents=True, exist_ok=True)
            os.startfile(str(p))

    def open_url(self, url):
        if str(url).startswith(("https://ncs.io/", "https://studio.youtube.com/", "https://www.youtube.com/",
                                "https://youtu.be/", "https://console.cloud.google.com/")):
            music.open_url(url)

    # ------------------------------------------------------------ YouTube
    def yt_status(self):
        import youtube
        return youtube.status()

    def yt_choose_client(self):
        import webview
        import youtube
        r = self._window.create_file_dialog(webview.FileDialog.OPEN, file_types=("Google OAuth client (*.json)",))
        if not r:
            return {"ok": False, "error": ""}
        try:
            youtube.set_client(r[0])
            return {"ok": True}
        except youtube.YTError as e:
            return {"ok": False, "error": str(e)}

    def yt_sign_in(self):
        import youtube
        try:
            return {"ok": True, **youtube.sign_in()}
        except youtube.YTError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            return {"ok": False, "error": f"Sign-in didn't finish ({type(e).__name__}: {e})"}

    def yt_sign_out(self):
        import youtube
        youtube.sign_out()
        return True

    def yt_upload(self, form):
        p = Path(form.get("path", ""))
        if not is_inside(p, [merged_root()]) or not p.exists():
            return {"ok": False, "error": "Only videos in the Merged folder can be uploaded."}
        title = (form.get("title") or "").strip()
        if not title:
            return {"ok": False, "error": "Add a title."}
        if any(ch in title for ch in "<>"):
            return {"ok": False, "error": "YouTube titles can't contain < or >."}
        tags = [t.strip().lstrip("#") for t in re.split(r"[,\n]", form.get("tags") or "") if t.strip().lstrip("#")]
        if len(",".join(tags)) > 500:
            return {"ok": False, "error": "Tags are over YouTube's 500-character limit."}
        meta = {"title": title, "description": (form.get("description") or "").replace("<", "‹").replace(">", "›"),
                "tags": tags, "privacy": form.get("privacy", "private"), "publish_at": form.get("publish_at") or "",
                "made_for_kids": bool(form.get("made_for_kids")), "notify": bool(form.get("notify", True))}
        if meta["privacy"] not in ("private", "unlisted", "public"):
            meta["privacy"] = "private"
        import youtube
        st = youtube.status()
        if not st["signed_in"]:
            return {"ok": False, "error": st["error"] or "Not signed in to YouTube. Sign in in Settings → YouTube."}
        return {"ok": True, "id": self._jobs.add_upload(p, meta)}

    # ------------------------------------------------------------ jobs
    def jobs(self):
        added, self._added = self._added, []
        return {"jobs": self._jobs.snapshot(), "watch": self._watcher.status(), "music_added": added}

    def make_highlights(self, paths):
        n = 0
        for p in paths:
            pp = Path(p)
            if is_inside(pp, [RECORDINGS_ROOT]) and pp.exists():
                if self._jobs.add_highlight(str(pp), pp.parent.name):
                    n += 1
        return n

    def cancel_job(self, jid):
        return self._jobs.cancel(jid)

    def clear_jobs(self):
        self._jobs.clear_finished()

    def running_jobs(self):
        return sum(1 for j in self._jobs.snapshot() if j["state"] in ("queued", "running"))

    def stop_all(self):
        for j in self._jobs.snapshot():
            if j["state"] in ("queued", "running"):
                self._jobs.cancel(j["id"])

    # ------------------------------------------------------------ delete (Recycle Bin)
    def trash(self, kind, paths):
        results = []
        if kind == "footage":
            ok_paths = [p for p in paths if is_inside(p, [RECORDINGS_ROOT])]
            results = ledger.trash_files(ok_paths)
        elif kind in ("shorts", "merged"):
            root = HIGHLIGHTS_ROOT if kind == "shorts" else merged_root()
            side = ".txt" if kind == "shorts" else ".json"
            for p in paths:
                p = Path(p)
                if not is_inside(p, [root]) or p.suffix.lower() != ".mp4":
                    results.append({"path": str(p), "ok": False, "reason": "outside its folder", "size": 0})
                    continue
                size = p.stat().st_size if p.exists() else 0
                ok = ledger.recycle(p) if p.exists() else False
                if ok and p.with_suffix(side).exists():
                    ledger.recycle(p.with_suffix(side))
                results.append({"path": str(p), "ok": ok, "reason": "" if ok else "Windows did not move it",
                                "size": size})
        elif kind == "music":
            results = music.delete_tracks(paths)
        return results

    # ------------------------------------------------------------ merge
    def _merge_args(self, o, out, plan_json=None):
        clips = [c for c in o.get("clips", []) if is_inside(c, [HIGHLIGHTS_ROOT]) and Path(c).exists()]
        if len(clips) < 2:
            raise ValueError("Add at least 2 shorts to the queue.")
        args = [str(out), *clips, "--order", "given", "--format", o.get("fmt", "short"),
                "--style", o.get("style", "punchy")]
        if o.get("hq"):
            args.append("--hq")
        # sound mix presets (merge_highlights.py defaults = "balanced": game first, music ducks under it)
        mix = {"music": ["--music-volume", "-4", "--game-volume", "0.45", "--no-duck"],
               "musiconly": ["--music-volume", "-2", "--game-volume", "0", "--no-duck"],
               "balanced": []}.get(o.get("mix", "music"), [])
        args += mix
        track = self._pick_music(o.get("music", "any"))
        if track:
            args += ["--music", track]
        if plan_json:
            args += ["--dry-run", "--plan-json", str(plan_json), "--seed", "7"]
        return args, clips, track

    def _pick_music(self, choice):
        tracks = [t for t in music.list_tracks() if t["credit_state"] != "missing"]
        if choice and choice != "any":
            t = next((t for t in tracks if t["path"] == choice), None)
            if not t:
                raise ValueError("That track needs a credit line first (Music page).")
            return t["path"]
        if not tracks:
            raise ValueError("Add at least one track with a credit line on the Music page first.")
        return random.choice(tracks)["path"]

    def merge(self, o):
        try:
            name = _safe_name(o.get("name"))
            out = merged_root() / f"{name}.mp4"
            args, clips, track = self._merge_args(o, out)
            merged_root().mkdir(parents=True, exist_ok=True)
            jid = self._jobs.add_merge(out, clips, args, name, track)
            return {"ok": True, "id": jid}
        except ValueError as e:
            return {"ok": False, "error": str(e)}

    def preview(self, o):
        try:
            plan = DATA / "tmp" / f"plan-{int(time.time() * 1000)}.json"
            args, clips, track = self._merge_args(o, DATA / "tmp" / "preview.mp4", plan)
            r = run([PYTHON, str(PIPE / "merge_highlights.py"), *args], timeout=600, cwd=str(PIPE))
            if not plan.exists():
                return {"ok": False, "error": (r.stdout + r.stderr).strip()[-600:] or "Preview failed"}
            data = json.loads(plan.read_text(encoding="utf-8"))
            plan.unlink(missing_ok=True)
            data["ok"] = True
            data["log"] = [l for l in r.stdout.splitlines() if l.strip().startswith("over ")]
            return data
        except ValueError as e:
            return {"ok": False, "error": str(e)}

    # ------------------------------------------------------------ music
    def music_list(self):
        return music.list_tracks()

    def music_save(self, file, title, artist, source, credit, no_credit):
        music.save_credit(file, title, artist, source, credit, no_credit)
        return True

    def music_import(self):
        import webview
        r = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=True,
                                            file_types=("Music files (*.mp3;*.m4a;*.aac;*.wav;*.flac;*.ogg;*.opus)",))
        return music.import_files(r or [])

    def ncs_search(self, q):
        try:
            return {"ok": True, "items": music.ncs_search(q)}
        except Exception as e:
            return {"ok": False, "error": f"Couldn't reach ncs.io ({type(e).__name__}). Check the internet connection."}

    def ncs_track(self, slug):
        try:
            return {"ok": True, **music.ncs_track(slug)}
        except Exception as e:
            return {"ok": False, "error": f"Couldn't load the track page ({type(e).__name__})."}

    def ncs_get(self, item):
        info = self.ncs_track(item["slug"])
        credit = info.get("credit") if info.get("ok") else ""
        if not credit:
            credit = f"Song: {item['artist']} - {item['title']}\nMusic provided by NoCopyrightSounds\n" \
                     f"Free Download/Stream: https://ncs.io/{item['slug']}"
        self._watcher.expect_ncs({"slug": item["slug"], "title": item["title"], "artist": item["artist"],
                                  "credit": credit, "url": f"https://ncs.io/{item['slug']}"})
        music.open_url(f"https://ncs.io/{item['slug']}")
        return True

    def open_ytal(self):
        self._watcher.expect_ytal()
        music.open_url("https://studio.youtube.com/channel/UC/music")
        return True

    def check_link(self, url):
        try:
            return {"ok": True, **music.check_link(url)}
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            return {"ok": False, "error": f"Couldn't read that page ({type(e).__name__})."}
