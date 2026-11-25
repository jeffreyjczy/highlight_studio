"""Reads recordings, shorts and merged videos from disk; ffprobe metadata and thumbnail caches."""
import hashlib
import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from common import DATA, FFMPEG, FFPROBE, HIGHLIGHTS_ROOT, ledger, merged_root, run

VIDEO_EXTS = {".mp4", ".mkv", ".mov"}
_probe_lock = threading.Lock()
_PROBE_FILE = DATA / "probe_cache.json"
try:
    _probe = json.loads(_PROBE_FILE.read_text(encoding="utf-8"))
except (OSError, ValueError):
    _probe = {}
_probe_dirty = False
_thumb_gate = threading.Semaphore(3)  # at most 3 ffmpeg thumbnail decodes at once


def file_id(path):
    return hashlib.sha1(str(path).lower().encode("utf-8")).hexdigest()[:12]


def _stamp(p):
    st = p.stat()
    return f"{st.st_size}:{int(st.st_mtime)}"


def probe(path):
    """{dur, w, h, fps, audio} for a media file, cached by size+mtime."""
    global _probe_dirty
    p = Path(path)
    key, stamp = str(p).lower(), _stamp(p)
    with _probe_lock:
        hit = _probe.get(key)
        if hit and hit.get("stamp") == stamp:
            return hit
    info = {"stamp": stamp, "dur": 0.0, "w": 0, "h": 0, "fps": 0, "audio": 0}
    r = run([FFPROBE, "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,avg_frame_rate",
             "-of", "json", str(p)], timeout=60)
    try:
        d = json.loads(r.stdout or "{}")
        info["dur"] = float(d.get("format", {}).get("duration") or 0)
        for s in d.get("streams", []):
            if s.get("codec_type") == "video" and not info["w"]:
                info["w"], info["h"] = s.get("width", 0), s.get("height", 0)
                num, _, den = (s.get("avg_frame_rate") or "0/1").partition("/")
                info["fps"] = round(float(num) / float(den or 1)) if float(den or 1) else 0
            elif s.get("codec_type") == "audio":
                info["audio"] += 1
    except (ValueError, ZeroDivisionError):
        pass
    with _probe_lock:
        _probe[key] = info
        _probe_dirty = True
    return info


def save_probe_cache():
    global _probe_dirty
    with _probe_lock:
        if not _probe_dirty:
            return
        tmp = _PROBE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(_probe), encoding="utf-8")
        os.replace(tmp, _PROBE_FILE)
        _probe_dirty = False


def res_label(info):
    w, h = info.get("w") or 0, info.get("h") or 0
    if not h:
        return ""
    short = min(w, h)
    return f"{short}p{info.get('fps') or ''}"


def thumb(path, frac=0.1, width=480, index=None):
    """Path to a cached JPEG frame. index (0-7) gives the hover-scrub frames."""
    p = Path(path)
    key = hashlib.sha1(f"{str(p).lower()}|{_stamp(p)}|{frac if index is None else 'i' + str(index)}|{width}"
                       .encode("utf-8")).hexdigest()
    out = DATA / "thumbs" / f"{key}.jpg"
    if out.exists():
        return out
    dur = probe(p)["dur"] or 1
    t = dur * ((index + 0.5) / 8 if index is not None else frac)
    t = max(0.0, min(t, dur - 0.5))
    tmp = out.with_suffix(".part.jpg")
    with _thumb_gate:
        if out.exists():
            return out
        run([FFMPEG, "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(p), "-frames:v", "1",
             "-vf", f"scale={width}:-2", "-q:v", "5", str(tmp)], timeout=60)
        if tmp.exists():
            os.replace(tmp, out)
    return out if out.exists() else None


# ---------------------------------------------------------------- footage
def scan_footage():
    led = ledger.load()
    rows = []
    paths = list(ledger.iter_recordings())
    with ThreadPoolExecutor(6) as ex:
        infos = list(ex.map(lambda p: probe(p), paths))
    for p, info in zip(paths, infos):
        e = led["recordings"].get(ledger.key_of(p))
        try:
            status = ledger.classify(p, e)
            st = p.stat()
        except OSError:
            continue
        rows.append({
            "id": file_id(p), "path": str(p), "file": p.name, "game": p.parent.name, "status": status,
            "size": st.st_size, "ts": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="minutes"),
            "recorded": recorded_at(p.name) or datetime.fromtimestamp(st.st_mtime).isoformat(timespec="minutes"),
            "dur": info["dur"], "res": res_label(info), "w": info["w"], "h": info["h"], "fps": info["fps"],
            "audio": info["audio"],
            "clips": (e or {}).get("clip_count"), "clips_dir": (e or {}).get("clips_dir"),
            "reason": (e or {}).get("reason"), "completed_at": (e or {}).get("completed_at"),
            "failed_at": (e or {}).get("failed_at"),
        })
    save_probe_cache()
    return rows


_NV = re.compile(r"(\d{4})\.(\d{2})\.(\d{2}) - (\d{2})\.(\d{2})")
_AMD = re.compile(r"(\d{4})\.(\d{2})\.(\d{2})-(\d{2})\.(\d{2})")


def recorded_at(name):
    m = _NV.search(name) or _AMD.search(name)
    if not m:
        return None
    y, mo, d, h, mi = m.groups()
    return f"{y}-{mo}-{d}T{h}:{mi}"


# ---------------------------------------------------------------- shorts
_SECTION = re.compile(r"^(TITLE|DESCRIPTION|HASHTAGS|STORY|HOOK IDEA)[^:\n]*:\s*$", re.M)


def parse_txt(path):
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except OSError:
        return {}
    out, parts = {}, _SECTION.split(text)
    for i in range(1, len(parts) - 1, 2):
        out[parts[i].lower()] = parts[i + 1].strip()
    return out


def _clip_sets():
    """Every folder under E:\\Highlights that holds .mp4 shorts."""
    if not HIGHLIGHTS_ROOT.exists():
        return []
    sets = {}
    for f in HIGHLIGHTS_ROOT.rglob("*.mp4"):
        sets.setdefault(f.parent, []).append(f)
    return sorted(sets.items(), key=lambda kv: str(kv[0]).lower())


def scan_shorts():
    led = ledger.load()
    by_dir = {}
    for e in led["recordings"].values():
        if e.get("clips_dir"):
            by_dir[str(Path(e["clips_dir"])).lower()] = e
    sets = []
    all_sets = _clip_sets()
    with ThreadPoolExecutor(8) as ex:  # warm the probe cache in parallel
        list(ex.map(probe, [f for _, files in all_sets for f in files]))
    for folder, files in all_sets:
        rel = folder.relative_to(HIGHLIGHTS_ROOT).parts
        game = rel[0] if len(rel) > 1 else "Other"
        label = " / ".join(rel[1:]) if len(rel) > 1 else rel[0]
        meta, data = {}, {}
        mj = folder / "clips.json"
        if mj.exists():
            try:
                data = json.loads(mj.read_text(encoding="utf-8-sig"))
                meta = {c.get("file"): c for c in data.get("clips", [])}
            except (OSError, ValueError):
                pass
        e = by_dir.get(str(folder).lower())
        clips = []
        for f in sorted(files, key=lambda x: x.name.lower()):
            m = meta.get(f.name, {})
            txt = parse_txt(f.with_suffix(".txt"))
            yt = m.get("youtube") or {}
            num = re.match(r"(\d+)\s*-\s*(.*)$", f.stem)
            title = yt.get("title") or txt.get("title") or m.get("title") or (num.group(2) if num else f.stem)
            tags = yt.get("hashtags")
            tags = " ".join(tags) if isinstance(tags, list) else (tags or txt.get("hashtags") or "")
            info = probe(f)
            score = m.get("score")
            if isinstance(score, (int, float)) and score <= 10:  # older runs scored 0-10
                score = round(score * 10)
            clips.append({
                "id": file_id(f), "path": str(f), "file": f.name, "n": int(num.group(1)) if num else None,
                "name": num.group(2) if num else f.stem, "title": title, "score": score,
                "parts": m.get("score_parts"), "hook": m.get("hook") or txt.get("hook idea") or "",
                "story": m.get("story") or txt.get("story") or m.get("why") or "",
                "desc": yt.get("description") or txt.get("description") or "", "tags": tags,
                "len": m.get("length") or info["dur"], "type": m.get("type"),
                "size": f.stat().st_size,
            })
        sets.append({"id": file_id(folder), "path": str(folder), "game": game, "label": label,
                     "processed_at": data.get("processed_at"), "source": data.get("source") or (e or {}).get("path"),
                     "current": bool(e), "clips": clips})
    save_probe_cache()
    return sets


# ---------------------------------------------------------------- merged
def scan_merged():
    root = merged_root()
    out = []
    if not root.exists():
        return out
    for f in sorted(root.glob("*.mp4"), key=lambda x: -x.stat().st_mtime):
        side = {}
        sj = f.with_suffix(".json")
        if sj.exists():
            try:
                side = json.loads(sj.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
        info = probe(f)
        st = f.stat()
        out.append({
            "id": file_id(f), "path": str(f), "name": f.stem, "size": st.st_size,
            "ts": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="minutes"),
            "len": side.get("length") or info["dur"], "w": info["w"], "h": info["h"],
            "fmt": "short" if info["h"] > info["w"] else "long",
            "music": side.get("music"), "style": side.get("style"), "bpm": side.get("bpm"),
            "clips": [c.get("file") for c in side.get("clips", [])],
        })
    save_probe_cache()
    return out


def playbooks():
    """Game playbooks rendered to HTML (read-only viewer; they're edited with Claude outside the app)."""
    from markdown_it import MarkdownIt
    from common import PIPE, RECORDINGS_ROOT
    md = MarkdownIt("commonmark", {"html": False}).enable("table")
    gdir = PIPE / "games"
    files = sorted(gdir.glob("*.md"), key=lambda f: (f.stem.startswith("_"), f.stem.lower()))
    own = {f.stem.lower() for f in files if not f.stem.startswith("_")}
    folders = sorted({p.name for p in RECORDINGS_ROOT.iterdir() if p.is_dir()} |
                     {p.name for p in HIGHLIGHTS_ROOT.iterdir() if p.is_dir()}) if RECORDINGS_ROOT.exists() else []
    out = []
    for f in files:
        text = f.read_text(encoding="utf-8-sig")
        default = f.stem.startswith("_")
        used_by = [g for g in folders if g.lower() not in own] if default else [f.stem]
        out.append({
            "id": f.stem, "game": "Other games" if default else f.stem, "default": default, "file": str(f),
            "updated": datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="minutes"),
            "used_by": used_by, "html": md.render(text),
        })
    return out


def disk_usage():
    import shutil
    try:
        u = shutil.disk_usage(str(HIGHLIGHTS_ROOT.anchor or "E:\\"))
        return {"drive": HIGHLIGHTS_ROOT.drive or "E:", "free": u.free, "total": u.total}
    except OSError:
        return {"drive": "E:", "free": 0, "total": 0}
