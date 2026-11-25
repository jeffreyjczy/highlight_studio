"""Music library (files + music.json with credits), NCS catalogue search, link check, Downloads watcher.

Downloads from ncs.io are always made by the user in their browser: ncs.io's robots.txt
disallows /api/download/ for automated clients, so the app never requests it. The app only
reads public pages (search, track page for the credit text) and plays the preview stream."""
import html
import json
import os
import re
import shutil
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

import library
from common import downloads_dir, ledger, music_root, SETTINGS

AUDIO_EXTS = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus"}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HighlightStudio/1.0"
_lock = threading.RLock()


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


# ---------------------------------------------------------------- library
def _meta_file():
    return music_root() / "music.json"


def _load_meta():
    try:
        return json.loads(_meta_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": 1, "tracks": {}}


def _save_meta(meta):
    root = music_root()
    root.mkdir(parents=True, exist_ok=True)
    tmp = _meta_file().with_suffix(".tmp")
    tmp.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, _meta_file())


def _guess(stem):
    s = re.sub(r"\s*[\[(](?:NCS Release|Official.*?|Audio)[\])]\s*", "", stem, flags=re.I).strip()
    if " - " in s:
        a, t = s.split(" - ", 1)
        return t.strip(), a.strip()
    return s, ""


def credit_state(m):
    if m.get("no_credit"):
        return "none"
    return "ready" if (m.get("credit") or "").strip() else "missing"


def list_tracks():
    root = music_root()
    with _lock:
        meta = _load_meta()
        files = sorted(f for f in root.glob("*") if f.is_file() and f.suffix.lower() in AUDIO_EXTS) if root.exists() else []
        changed = False
        out = []
        for f in files:
            m = meta["tracks"].get(f.name)
            if m is None:
                title, artist = _guess(f.stem)
                m = meta["tracks"][f.name] = {"title": title, "artist": artist, "source": "Imported file",
                                              "source_url": "", "credit": "", "no_credit": False,
                                              "added": datetime.now().isoformat(timespec="minutes")}
                changed = True
            info = library.probe(f)
            out.append({"id": library.file_id(f), "path": str(f), "file": f.name, "len": info["dur"],
                        "credit_state": credit_state(m), **m})
        if changed:
            _save_meta(meta)
    library.save_probe_cache()
    return out


def save_credit(file, title, artist, source, credit, no_credit, source_url=None):
    with _lock:
        meta = _load_meta()
        m = meta["tracks"].setdefault(file, {})
        m.update(title=title, artist=artist, source=source, credit=credit.strip(), no_credit=bool(no_credit))
        if source_url is not None:
            m["source_url"] = source_url
        _save_meta(meta)


def delete_tracks(paths):
    results = []
    with _lock:
        meta = _load_meta()
        for p in paths:
            p = Path(p)
            if p.parent.resolve() != music_root().resolve():
                results.append({"path": str(p), "ok": False, "reason": "not in the music folder"})
                continue
            ok = ledger.recycle(p) if p.exists() else False
            if ok:
                meta["tracks"].pop(p.name, None)
            results.append({"path": str(p), "ok": ok, "reason": "" if ok else "Windows did not move it"})
        _save_meta(meta)
    return results


def _free_target(name):
    root = music_root()
    root.mkdir(parents=True, exist_ok=True)
    dst, n = root / name, 2
    while dst.exists():
        dst = root / f"{Path(name).stem} ({n}){Path(name).suffix}"
        n += 1
    return dst


def import_files(paths, source="Imported file", info=None):
    """Copy (from anywhere) or move (from Downloads) audio files into the library."""
    added = []
    dl = downloads_dir().resolve()
    for p in paths:
        p = Path(p)
        if not p.is_file() or p.suffix.lower() not in AUDIO_EXTS:
            continue
        dst = _free_target(p.name)
        if p.parent.resolve() == dl:
            shutil.move(str(p), dst)
        else:
            shutil.copy2(p, dst)
        title, artist = _guess(dst.stem)
        m = {"title": title, "artist": artist, "source": source, "source_url": "", "credit": "",
             "no_credit": False, "added": datetime.now().isoformat(timespec="minutes")}
        if info:
            m.update({k: v for k, v in info.items() if v is not None})
        with _lock:
            meta = _load_meta()
            meta["tracks"][dst.name] = m
            _save_meta(meta)
        added.append({"file": dst.name, "title": m["title"], "credit_state": credit_state(m)})
    return added


# ---------------------------------------------------------------- NCS
_ncs_cache = {}


def _txt(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def ncs_search(q=""):
    url = "https://ncs.io/music-search?" + urllib.parse.urlencode({"q": q or ""})
    page = _get(url)
    rows = re.findall(r'<div class="lrow" data-sid="[^"]+".*?(?=<div class="lrow" data-sid=|</main>|$)', page, re.S)
    out, seen = [], set()
    for r in rows:
        t = re.search(r'class="t" href="/([A-Za-z0-9_\-]+)">(.*?)</a>', r)
        if not t or t.group(1) in seen:
            continue
        seen.add(t.group(1))
        artists = [_txt(a) for a in re.findall(r'href="/artist/[^"]+">(.*?)</a>', r)]
        g = re.search(r'class="gc"[^>]*>(.*?)</span><i>(.*?)</i>', r)
        ln = re.search(r'class="lrow-len">([^<]+)', r)
        cov = re.search(r'<img src="([^"]+)"', r)
        cover = ""
        if cov:
            src = html.unescape(cov.group(1))
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(src).query)
            cover = qs.get("url", [src])[0]
            if cover.startswith("/"):
                cover = "https://ncs.io" + cover
        out.append({"slug": t.group(1), "title": _txt(t.group(2)), "artists": artists,
                    "artist": ", ".join(artists), "genre": _txt(g.group(1)) if g else "",
                    "mood": _txt(g.group(2)) if g else "", "len": _txt(ln.group(1)) if ln else "", "cover": cover})
    return out


def ncs_track(slug):
    """Credit text and preview stream for one track (from its public page)."""
    if slug in _ncs_cache:
        return _ncs_cache[slug]
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", slug):
        raise ValueError("bad track id")
    page = _get(f"https://ncs.io/{slug}")
    credit = ""
    for m in re.findall(r"<code[^>]*>(.*?)</code>", page, re.S):
        if "Music provided by" in m or "NoCopyrightSounds" in m:
            credit = _txt(re.sub(r"<br\s*/?>", "\n", m))
            break
    prev = re.search(r"https?://audio\.ncs\.io/" + re.escape(slug) + r"/[A-Za-z0-9_\-]+\.(?:mp3|m4a)", page) \
        or re.search(r"audio\.ncs\.io/" + re.escape(slug) + r"/[A-Za-z0-9_\-]+\.(?:mp3|m4a)", page)
    preview = prev.group(0) if prev else ""
    if preview and not preview.startswith("http"):
        preview = "https://" + preview
    title = re.search(r"<title>(.*?)</title>", page, re.S)
    res = {"slug": slug, "credit": credit, "preview": preview, "url": f"https://ncs.io/{slug}",
           "page_title": _txt(title.group(1)) if title else ""}
    _ncs_cache[slug] = res
    return res


# ---------------------------------------------------------------- link check
def check_link(url):
    u = urllib.parse.urlparse(url.strip())
    host = (u.netloc or "").lower()
    vid = None
    if host.endswith("youtu.be"):
        vid = u.path.strip("/").split("/")[0]
    elif "youtube.com" in host:
        vid = urllib.parse.parse_qs(u.query).get("v", [None])[0]
        if not vid and u.path.startswith(("/shorts/", "/live/")):
            vid = u.path.split("/")[2]
    if not vid or not re.fullmatch(r"[A-Za-z0-9_\-]{6,20}", vid):
        raise ValueError("Paste a YouTube video link (youtube.com/watch?v=… or youtu.be/…).")
    page = _get(f"https://www.youtube.com/watch?v={vid}&hl=en")

    def jstr(key):
        m = re.search(r'"' + key + r'":"((?:[^"\\]|\\.)*)"', page)
        return json.loads('"' + m.group(1) + '"') if m else ""
    title, channel, desc = jstr("title"), jstr("ownerChannelName") or jstr("author"), jstr("shortDescription")
    found = None
    for line in [title] + desc.splitlines():
        line = line.strip()
        m = re.match(r"(?:song|track|music)\s*[:\-–]\s*(.+?)\s+[-–]\s+(.+?)(?:\s*\[(.+?)\])?\s*$", line, re.I) \
            or re.match(r"(.+?)\s+[-–]\s+(.+?)\s*\[((?:NCS|Monstercat|[^\]]*) Release)\]", line, re.I)
        if m:
            found = {"artist": m.group(1).strip(), "track": m.group(2).strip(), "label": (m.group(3) or "").strip()}
            break
    slug = re.search(r"(?:https?://)?(?:www\.)?ncs\.io/(?!artist/|playlist/)([A-Za-z0-9_]+)", desc)
    links = re.findall(r"https?://[^\s)]+", desc)[:8]
    is_ncs = bool(slug) or bool(found and "ncs" in found["label"].lower()) or "NoCopyrightSounds" in desc
    return {"title": title, "channel": channel, "found": found, "ncs_slug": slug.group(1) if slug else None,
            "is_ncs": is_ncs, "links": links, "excerpt": desc[:700]}


# ---------------------------------------------------------------- Downloads watcher
class Watcher:
    """Moves music that arrives in Downloads into the library, but only after the user chose
    'Get track' (NCS) or 'Open Audio Library', so unrelated downloads are left alone."""

    def __init__(self, on_added):
        self.on_added = on_added
        self.pending = []          # [{slug, title, artist, credit, url, since}]
        self.ytal_until = 0.0
        self.seen = {}
        self._snap()
        threading.Thread(target=self._loop, daemon=True).start()

    def _snap(self):
        d = downloads_dir()
        self.seen = {f.name: f.stat().st_size for f in d.glob("*") if f.is_file()} if d.exists() else {}

    def expect_ncs(self, track):
        if not self.active():
            self._snap()
        self.pending.append({**track, "since": time.time()})

    def expect_ytal(self, minutes=30):
        if not self.active():
            self._snap()
        self.ytal_until = time.time() + minutes * 60

    def active(self):
        now = time.time()
        self.pending = [p for p in self.pending if now - p["since"] < 30 * 60]
        return bool(self.pending) or now < self.ytal_until

    def status(self):
        return {"waiting": [p["slug"] for p in self.pending], "ytal": time.time() < self.ytal_until}

    def _loop(self):
        sizes = {}
        while True:
            time.sleep(2)
            if not SETTINGS.get("watch_downloads", True) or not self.active():
                sizes.clear()
                continue
            d = downloads_dir()
            try:
                files = [f for f in d.glob("*") if f.is_file() and f.suffix.lower() in AUDIO_EXTS]
            except OSError:
                continue
            for f in files:
                try:
                    sz = f.stat().st_size
                except OSError:
                    continue
                if self.seen.get(f.name) == sz:
                    continue
                if sizes.get(f.name) != sz:  # still growing: check again next round
                    sizes[f.name] = sz
                    continue
                self.seen[f.name] = sz
                sizes.pop(f.name, None)
                self._take(f)

    def _take(self, f):
        norm = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())
        match = next((p for p in self.pending if norm(p["title"]) and norm(p["title"]) in norm(f.stem)), None)
        if not match and len(self.pending) == 1 and time.time() >= self.ytal_until:
            match = self.pending[0]
        try:
            if match:
                self.pending.remove(match)
                info = {"title": match["title"], "artist": match["artist"], "source": "NCS",
                        "source_url": match.get("url", ""), "credit": match.get("credit", "")}
                added = import_files([f], "NCS", info)
            elif time.time() < self.ytal_until:
                added = import_files([f], "YouTube Audio Library")
            else:
                return
        except OSError:
            return
        for a in added:
            self.on_added(a)


def open_url(url):
    webbrowser.open(url)
