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
import recorder
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
        self._rec = recorder.Recorder()
        # a merge stopped by closing the app leaves "<name>.mp4.part": nothing is running now
        try:
            for f in merged_root().glob("*.mp4.part"):
                f.unlink()
        except OSError:
            pass

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
                     "theme", "last_page", "merge", "window", "rec_hotkey"):
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
        if form.get("thumbnail"):
            import thumbs
            t = thumbs.paths(p)["use"]
            meta["thumbnail"] = str(t) if t.exists() else ""
        import youtube
        st = youtube.status()
        if not st["signed_in"]:
            return {"ok": False, "error": st["error"] or "Not signed in to YouTube. Sign in in Settings → YouTube."}
        return {"ok": True, "id": self._jobs.add_upload(p, meta)}

    # ------------------------------------------------------------ jobs
    def jobs(self):
        added, self._added = self._added, []
        return {"jobs": self._jobs.snapshot(), "watch": self._watcher.status(), "music_added": added,
                "rec": self._rec.status()}

    # ------------------------------------------------------------ recording (AMD Adrenalin hotkey)
    def rec_toggle(self):
        return self._rec.toggle()

    def rec_status(self):
        return self._rec.status()

    def rec_info(self):
        return self._rec.info()

    # ------------------------------------------------------------ rerun a processed recording
    def _old_shorts(self, rec):
        r"""Folders under E:\Highlights that hold this recording's shorts: the ledger's clips
        folder and E:\Highlights\<game>\<recording name> (earlier reruns sit inside it as v2...)."""
        led = ledger.load()
        e = led["recordings"].get(ledger.key_of(rec)) or {}
        found = []
        cands = [Path(e["clips_dir"])] if e.get("clips_dir") else []
        cands += [d for d in HIGHLIGHTS_ROOT.glob(f"*/{rec.stem}") if d.is_dir()]
        for d in cands:
            if not d.exists() or not is_inside(d, [HIGHLIGHTS_ROOT]) or d.resolve() == HIGHLIGHTS_ROOT.resolve():
                continue
            if any(d.resolve() == f.resolve() or f.resolve() in d.resolve().parents for f in found):
                continue  # already covered by a parent folder
            found = [f for f in found if d.resolve() not in f.resolve().parents] + [d]
        return found

    # ------------------------------------------------------------ thumbnails
    def thumb_make(self, path):
        p = Path(path)
        if not (is_inside(p, [merged_root()]) and p.exists()):
            return {"ok": False, "error": "That merged video isn't in the Merged folder."}
        if not p.with_suffix(".json").exists():
            return {"ok": False, "error": "This video has no edit plan (.json), so its clips are unknown."}
        jid = self._jobs.add_thumb(str(p), p.stem)
        return {"ok": bool(jid), "error": "" if jid else "A thumbnail for this video is already being made."}

    def thumb_candidates(self, path):
        import thumbs
        w = thumbs.paths(path)["work"] / "candidates.json"
        try:
            return json.loads(w.read_text(encoding="utf-8"))["candidates"]
        except (OSError, ValueError, KeyError):
            return []

    def thumb_edit(self, path, choice):
        """Re-render locally (no Claude) with another frame, headline or badge."""
        import thumbs
        p = Path(path)
        if not is_inside(p, [merged_root()]):
            return {"ok": False, "error": "Not a merged video."}
        old = thumbs.info(p) or {}
        choice = choice or {}
        if set(choice) <= {"title"} and not old.get("old"):  # only the title changed: no re-render
            thumbs.set_title(p, choice.get("title", ""))
            return {"ok": True}
        new = {**{k: old.get(k) for k in ("pick", "layout", "title", "why")}, **choice, "by": "you"}
        try:
            thumbs.render(p, new)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True}

    def thumb_layout(self, path, layout):
        import thumbs
        try:
            thumbs.choose_layout(path, layout)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def rerun_info(self, path):
        rec = Path(path)
        if not (is_inside(rec, [RECORDINGS_ROOT]) and rec.exists()):
            return {"ok": False, "error": "The recording isn't in the recordings folder any more."}
        folders = self._old_shorts(rec)
        shorts = [f for d in folders for f in d.rglob("*.mp4")]
        lower = {str(f).lower() for f in shorts}
        merged = [m["name"] for m in library.scan_merged() if any(str(c).lower() in lower for c in m["clips"])]
        return {"ok": True, "folders": [str(d) for d in folders], "shorts": len(shorts),
                "size": sum(f.stat().st_size for f in shorts), "merged": merged}

    def rerun_highlights(self, path):
        rec = Path(path)
        info = self.rerun_info(path)
        if not info["ok"]:
            return info
        led = ledger.load()
        key = ledger.key_of(rec)
        status = ledger.classify(rec, led["recordings"].get(key))
        if status in ("processing", "recording"):
            return {"ok": False, "error": f"Can't rerun while the recording is {status}."}
        if any(j["kind"] == "highlight" and j["path"].lower() == str(rec).lower() and j["state"] in ("queued", "running")
               for j in self._jobs.snapshot()):
            return {"ok": False, "error": "A highlight run for this recording is already queued."}
        for d in info["folders"]:
            if not ledger.recycle(d):
                return {"ok": False, "error": f"Couldn't move {d} to the Recycle Bin. Is a file in it open?"}
        led = ledger.load()
        led["recordings"].pop(key, None)  # same as `ledger.py reset`: treated as new
        ledger.save(led)
        if not self._jobs.add_highlight(str(rec), rec.parent.name):
            return {"ok": False, "error": "The old shorts were removed, but the run couldn't be queued. Use Make highlights."}
        return {"ok": True, "removed": info["shorts"]}

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
        if not self._jobs.wait_idle(15):  # cleanup didn't finish: free the recordings directly
            for j in self._jobs.snapshot():
                if j["state"] == "running" and j["kind"] == "highlight":
                    self._jobs._release(j["path"], "Stopped because Highlight Studio was closed")
        self._jobs._save()

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
                if ok and kind == "merged":  # its thumbnail files go with it
                    import thumbs
                    for f in thumbs.files(p):
                        if f.exists():
                            ledger.recycle(f)
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
        # sound mix presets. The music level is set relative to the gameplay's measured
        # loudness (merge_highlights.py --music-level), because NCS tracks are mastered very
        # differently (one measured -3.6 LUFS vs ~-13 for clips). mvol 100% = as loud as
        # the game, 50% = half the amplitude (-6 dB).
        import math
        rel = str(round(20 * math.log10(max(5, min(200, float(o.get("mvol") or 50))) / 100), 1))
        mix = {"music": ["--music-level", rel, "--game-volume", "1.0", "--no-duck"],
               "musiconly": ["--music-volume", "-2", "--game-volume", "0", "--no-duck"],
               "balanced": ["--music-level", rel]}.get(o.get("mix", "music"), [])
        args += mix
        # overall loudness of the finished video. 100% = -14 LUFS (YouTube's reference level),
        # 50% = half the amplitude = -20 LUFS. YouTube turns loud uploads down but never turns
        # quiet ones up, so a quieter master also plays quieter there.
        ovol = max(25, min(100, float(o.get("ovol") or 50)))
        args += ["--lufs", str(round(-14 + 20 * math.log10(ovol / 100), 1))]
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

    def ncs_cancel(self, slug):
        self._watcher.cancel(slug)
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
