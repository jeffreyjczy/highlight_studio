"""Render highlight clips from a recording: one clip from a spec, or every clip in a plan.

Clips keep the recording's own resolution, frame rate and full horizontal frame:
no cropping, no vertical layout, no text. Formatting for Shorts (vertical) or a long
highlight video is done later by merge_highlights.py.

Video is CUT WITHOUT RE-ENCODING (stream copy): the clip has exactly the recording's
quality and codec (AV1), and rendering takes about a second. Each segment starts on the
keyframe at or before its planned start (recordings have one every 0.5-1 s), so a clip
can start up to 1 s early. A segment whose keyframe would reach back into the previous
segment (back-to-back or nearly touching) is cut together with it as one continuous run,
so no footage plays twice. The actual starts are written back (clips.json / printed).
Only the audio is re-encoded: game audio, plus the mic track if given, through a limiter
so loud moments don't clip.
Clips with a "hold" (freeze frame) segment can't be stream-copied: they are encoded to
h264 at a high bitrate (about 30 Mb/s at 1080p60) instead.

Usage:
  python render_clip.py <spec.json>                       one clip
  python render_clip.py <plan.json> [--check-dir DIR]     every clip in a plan
                        [--redo 03,07]                    re-render these numbers in place

spec.json (one clip):
{
  "source": "E:\\\\Recordings\\\\Game\\\\file.mp4",
  "out": "E:\\\\Highlights\\\\Game\\\\file\\\\01 - Title.mp4",
  "segments": [ {"start": 490.0, "end": 500.0, "label": "first kill"},
                {"start": 865.5, "end": 867.5, "label": "end screen", "layout": "center", "hold": 3} ],
  // "hold": N freezes the segment's last frame for N extra seconds (forces h264)
  // "layout" is NOT applied here: it is a framing hint (crop | blur | center) that the
  //   merger uses when it makes a vertical Short. Keep it in clips.json.
  "youtube": {"title": "...", "description": "...", "hashtags": ["..."], "story": "...", "hook": "..."},
                           // optional: written next to the video as "<name>.txt"
  "mic_track": 1           // audio track index of the mic to mix in, or null
}

plan.json (a whole recording): the clips.json fields plus "out_dir" and "mic_track":
{
  "source": "...", "game": "Valorant", "playbook": "games/Valorant.md",
  "out_dir": "E:\\\\Highlights\\\\Valorant\\\\<recording name>", "mic_track": 1,
  "timeline": [...],
  "clips": [{"title": "Reyna Double Kill on Haven", "type": "moment", "score": 63,
             "score_parts": {...}, "hook": "...", "story": "...", "youtube": {...},
             "segments": [...], "events": [...], "why": "..."}]
}
Clips are numbered by score (01 = best) and named "NN - <title>.mp4". Clips with
"skip": true are left out. Writes <out_dir>/clips.json (refuses to replace an existing
one unless --redo is used), and with --check-dir, check_NN.jpg images showing the first,
middle and last frame of 6 clips each, to verify the cuts cheaply.

Every clip is checked after rendering: codec, the source's exact resolution and frame
rate, an audio track, and the planned length. Problems are printed as FAILED and the
exit code is 1.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

BIN = Path(r"C:\Users\jeffr\AppData\Local\Microsoft\WinGet\Packages"
           r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.1-full_build\bin")
FFMPEG, FFPROBE = str(BIN / "ffmpeg.exe"), str(BIN / "ffprobe.exe")
FONT = "C\\:/Windows/Fonts/arialbd.ttf"


# ---------------------------------------------------------------- probing
def probe_video(src):
    r = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=codec_name,width,height,r_frame_rate:format=start_time",
                        "-of", "json", str(src)], capture_output=True, text=True, check=True)
    d = json.loads(r.stdout)
    s = d["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return {"codec": s["codec_name"], "w": int(s["width"]), "h": int(s["height"]),
            "fps": float(num) / float(den), "start_time": float(d["format"].get("start_time", 0) or 0)}


def probe_out(path):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries",
                        "stream=codec_type,codec_name,width,height,r_frame_rate:format=duration",
                        "-of", "json", str(path)], capture_output=True, text=True)
    if r.returncode:
        return None
    d = json.loads(r.stdout)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
    a = any(s["codec_type"] == "audio" for s in d["streams"])
    if not v:
        return None
    num, den = v["r_frame_rate"].split("/")
    return {"codec": v["codec_name"], "w": int(v["width"]), "h": int(v["height"]),
            "fps": float(num) / float(den), "audio": a, "duration": float(d["format"]["duration"])}


def keyframe_at_or_before(src, t, start_time=0.0):
    """Time of the last keyframe at or before t (file position, seconds)."""
    for back in (3, 12, 60):
        lo = max(0.0, t - back)
        # packet flags (K = keyframe) need no decoding, so this is quick
        r = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "packet=pts_time,flags", "-of", "csv=p=0",
                            "-read_intervals", f"{lo:.3f}%{t + 0.05:.3f}", str(src)],
                           capture_output=True, text=True)
        ks = []
        for line in r.stdout.splitlines():
            parts = line.strip().split(",")
            if len(parts) >= 2 and "K" in parts[1] and parts[0] not in ("", "N/A"):
                ks.append(float(parts[0]) - start_time)
        ks = [k for k in ks if k <= t + 0.001]
        if ks:
            return round(max(ks), 3)
    return round(t, 3)


# ---------------------------------------------------------------- rendering
def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"ffmpeg failed:\n{r.stderr[-2000:]}")


def audio_filter(mic, hold=0.0):
    pad = f",apad=pad_dur={hold}" if hold else ""
    lim = "alimiter=limit=0.95:level=false:latency=true"
    if mic is not None:
        return f"[0:a:0][0:a:{mic}]amix=inputs=2:normalize=0,{lim},aresample=48000{pad}[aout]"
    return f"[0:a:0]{lim},aresample=48000{pad}[aout]"


def write_youtube_txt(out, yt):
    """Sidecar text file with the title/description/hashtags, ready to copy."""
    tags = " ".join(t if t.startswith("#") else f"#{t}" for t in yt.get("hashtags", []))
    body = (f"TITLE:\n{yt.get('title', '')}\n\nDESCRIPTION:\n{yt.get('description', '')}\n\n"
            f"HASHTAGS:\n{tags}\n")
    if yt.get("story"):
        body += f"\nSTORY:\n{yt['story']}\n"
    if yt.get("hook"):
        body += f"\nHOOK IDEA (not shown in the video):\n{yt['hook']}\n"
    out.with_suffix(".txt").write_text(body, encoding="utf-8")


def render(src, out, segs, mic, info):
    """Render one clip. Returns (segments as actually cut, mode)."""
    for s in segs:
        if float(s["end"]) <= float(s["start"]):
            raise ValueError(f"bad segment {s}")
    copy = not any(float(s.get("hold", 0)) for s in segs)
    actual = []
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="clip_", dir=Path.home()))
    try:
        parts = []
        if copy:
            # A stream-copied piece must start on a keyframe, i.e. up to 1 s before its planned
            # start. When that would reach back into the previous piece (back-to-back segments,
            # like the planner's "multi-kill feed" tail, or gaps shorter than the keyframe
            # spacing), the footage would play twice. Such segments are cut as one continuous run
            # instead; the segment list keeps them separate (layout hints) but back to back.
            runs = []
            for s in segs:
                a = dict(s)
                k = keyframe_at_or_before(src, float(s["start"]), info["start_time"])
                if runs and k < runs[-1]["end"] - 0.001:
                    a["start"] = actual[-1]["end"]          # continues the previous piece
                    runs[-1]["end"] = max(runs[-1]["end"], float(s["end"]))
                else:
                    a["start"] = k
                    runs.append({"start": k, "end": float(s["end"])})
                actual.append(a)
            for i, r in enumerate(runs):
                part = tmp / f"part_{i:02d}.mp4"
                # seek just past the keyframe so the demuxer lands exactly on it
                run([FFMPEG, "-v", "error", "-y", "-ss", f"{r['start'] + 0.001:.3f}", "-i", str(src),
                     "-t", f"{r['end'] - r['start']:.3f}",
                     "-filter_complex", audio_filter(mic), "-map", "0:v:0", "-map", "[aout]",
                     "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ac", "2",
                     "-avoid_negative_ts", "make_zero", str(part)])
                parts.append(part)
        else:  # re-encoded (a "hold" freeze frame somewhere): frame-exact cuts, no keyframe snapping
            fps = round(info["fps"])
            mbps = min(80, max(20, round(30 * (info["w"] * info["h"]) / (1920 * 1080) * max(1.0, fps / 60))))
            for i, s in enumerate(segs):
                part = tmp / f"part_{i:02d}.mp4"
                hold = float(s.get("hold", 0))
                vhold = f",tpad=stop_mode=clone:stop_duration={hold}" if hold else ""
                vf = f"[0:v]setsar=1{vhold},fps={fps},format=yuv420p[v];"
                run([FFMPEG, "-v", "error", "-y", "-ss", str(s["start"]),
                     "-t", str(float(s["end"]) - float(s["start"])), "-i", str(src),
                     "-filter_complex", vf + audio_filter(mic, hold), "-map", "[v]", "-map", "[aout]",
                     "-c:v", "h264_amf", "-quality", "quality", "-b:v", f"{mbps}M",
                     "-c:a", "aac", "-b:a", "192k", "-ac", "2", str(part)])
                parts.append(part)
                actual.append(dict(s))
        listfile = tmp / "list.txt"
        listfile.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
        run([FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0",
             "-i", str(listfile), "-c", "copy", "-movflags", "+faststart", str(out)])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return actual, ("copy" if copy else "h264")


def verify(out, segs, info, mode):
    """Problems with a rendered clip, as a list of strings (empty = OK)."""
    p = probe_out(out)
    if not p:
        return ["can't read the output"]
    probs = []
    want_codec = info["codec"] if mode == "copy" else "h264"
    if p["codec"] != want_codec:
        probs.append(f"codec {p['codec']}, expected {want_codec}")
    if (p["w"], p["h"]) != (info["w"], info["h"]):
        probs.append(f"size {p['w']}x{p['h']}, source is {info['w']}x{info['h']}")
    if abs(p["fps"] - info["fps"]) > 0.5:
        probs.append(f"{p['fps']:.2f} fps, source is {info['fps']:.2f}")
    if not p["audio"]:
        probs.append("no audio")
    planned = sum(float(s["end"]) - float(s["start"]) + float(s.get("hold", 0)) for s in segs)
    if abs(p["duration"] - planned) > 0.25 + 0.05 * len(segs):
        probs.append(f"length {p['duration']:.2f}s, planned {planned:.2f}s")
    return probs


# ---------------------------------------------------------------- check images
def check_images(rows, folder):
    """rows: [(label, clip path, duration)]. 6 clips per image, first/middle/last frame."""
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("check_*.jpg"):
        old.unlink()
    tmp = Path(tempfile.mkdtemp(prefix="check_", dir=Path.home()))
    made = []
    try:
        tiles = []
        for n, (label, path, dur) in enumerate(rows):
            for j, t in enumerate((0.15, dur / 2, max(0.0, dur - 0.25))):
                safe = re.sub(r"[^A-Za-z0-9 .\-]", "", label)[:40]
                txt = f"{safe}  {t:.1f}s" if j == 0 else f"{t:.1f}s"
                tile = tmp / f"t_{n:03d}_{j}.png"
                subprocess.run([FFMPEG, "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(path),
                                "-frames:v", "1", "-vf",
                                f"scale=320:180,drawtext=fontfile='{FONT}':text='{txt}':x=3:y=3:"
                                "fontsize=13:fontcolor=yellow:box=1:boxcolor=black@0.7", str(tile)],
                               capture_output=True)
                if not tile.exists():   # keep the grid aligned even if a frame fails
                    subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i",
                                    "color=c=red:s=320x180", "-frames:v", "1", str(tile)],
                                   capture_output=True)
                tiles.append(tile)
        per = 18                         # 6 clips x 3 frames
        for i in range(0, len(tiles), per):
            chunk = tiles[i:i + per]
            lst = tmp / f"l_{i}.txt"
            lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in chunk), encoding="utf-8")
            rows_n = (len(chunk) + 2) // 3
            out = folder / f"check_{i // per + 1:02d}.jpg"
            subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                            "-vf", f"tile=3x{rows_n}:padding=2", "-frames:v", "1", "-q:v", "4", str(out)],
                           capture_output=True)
            made.append(out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return made


# ---------------------------------------------------------------- plan mode
def safe_title(t):
    t = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", t).strip().rstrip(".")
    return t[:60].rstrip() or "Clip"


def free_path(p):
    n, cand = 2, p
    while cand.exists():
        cand = p.with_name(f"{p.stem} ({n}){p.suffix}")
        n += 1
    return cand


def run_plan(plan_path, check_dir, redo):
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8-sig"))
    src, out_dir = plan["source"], Path(plan["out_dir"])
    mic = plan.get("mic_track")
    info = probe_video(src)
    manifest = out_dir / "clips.json"
    clips = [c for c in plan["clips"] if not c.get("skip")]
    # number by score, best first; ties in timeline order
    clips.sort(key=lambda c: (-c.get("score", 0), min(float(s["start"]) for s in c["segments"])))
    done = {}
    if redo:
        if not manifest.exists():
            sys.exit("--redo needs an existing clips.json")
        done = {c["file"]: c for c in json.loads(manifest.read_text(encoding="utf-8")).get("clips", [])}
    elif manifest.exists():
        sys.exit(f"{manifest} already exists: use a new folder, or --redo NN to re-render clips")
    out_dir.mkdir(parents=True, exist_ok=True)

    entries, failed, checks = [], [], []
    for n, c in enumerate(clips, 1):
        name = f"{n:02d} - {safe_title(c['title'])}.mp4"
        if redo and f"{n:02d}" not in redo:
            if name in done:
                entries.append(done[name])
            continue
        # a clip rendered earlier in this same run may be replaced (--redo); never others
        out = out_dir / name if redo else free_path(out_dir / name)
        try:
            actual, mode = render(src, out, c["segments"], mic, info)
        except Exception as e:          # keep going: report every failure at the end
            failed.append(f"{name}: {e}")
            print(f"FAILED {name}: {e}")
            continue
        probs = verify(out, actual, info, mode)
        p = probe_out(out)
        dur = p["duration"] if p else 0.0
        if probs:
            failed.append(f"{out.name}: {'; '.join(probs)}")
            print(f"FAILED {out.name}: {'; '.join(probs)}")
        else:
            print(f"ok  {out.name}  {dur:.1f}s  {mode}  {len(actual)} segment(s)")
        yt = dict(c.get("youtube", {}))
        yt.setdefault("title", c["title"])
        yt["story"], yt["hook"] = c.get("story", ""), c.get("hook", "")
        write_youtube_txt(out, yt)
        e = {k: v for k, v in c.items() if k not in ("title", "skip")}
        e["file"], e["segments"], e["length"], e["encoding"] = out.name, actual, round(dur, 2), mode
        entries.append(e)
        checks.append((out.stem, out, dur or 1.0))

    meta = {k: v for k, v in plan.items() if k not in ("clips", "out_dir", "mic_track")}
    meta["processed_at"] = datetime.now().isoformat(timespec="seconds")
    meta["clips"] = entries
    manifest.write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\n{len(entries)} clip(s) in {out_dir}, clips.json written")
    if check_dir and checks:
        imgs = check_images(checks, Path(check_dir))
        print("check images: " + ", ".join(str(p) for p in imgs))
    if failed:
        print(f"\n{len(failed)} FAILED:\n  " + "\n  ".join(failed))
        return 1
    return 0


def run_spec(spec_path):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8-sig"))
    src, out = spec["source"], Path(spec["out"])
    if not spec.get("segments"):
        sys.exit("no segments")
    info = probe_video(src)
    actual, mode = render(src, out, spec["segments"], spec.get("mic_track"), info)
    if spec.get("youtube"):
        write_youtube_txt(out, spec["youtube"])
    probs = verify(out, actual, info, mode)
    p = probe_out(out)
    planned = sum(float(s["end"]) - float(s["start"]) + float(s.get("hold", 0)) for s in actual)
    print(f"rendered {out} : {info['w']}x{info['h']} {round(info['fps'])} fps, {mode}, "
          f"{len(actual)} segments, planned {planned:.1f}s, actual {p['duration'] if p else 0:.1f}s")
    print("segments as cut (copy these into clips.json): " + json.dumps(actual, ensure_ascii=False))
    if probs:
        print("FAILED: " + "; ".join(probs))
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("json")
    ap.add_argument("--check-dir")
    ap.add_argument("--redo", help="plan mode: comma-separated clip numbers to re-render in place")
    a = ap.parse_args()
    data = json.loads(Path(a.json).read_text(encoding="utf-8-sig"))
    if "clips" in data:
        redo = {f"{int(x):02d}" for x in a.redo.split(",")} if a.redo else None
        return run_plan(a.json, a.check_dir, redo)
    return run_spec(a.json)


if __name__ == "__main__":
    sys.exit(main())
