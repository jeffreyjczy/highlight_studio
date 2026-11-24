"""Render one highlight clip from one or more segments of a recording.

Clips keep the recording's own resolution, frame rate and full horizontal frame:
no cropping, no vertical layout, no text. Formatting for Shorts (vertical) or a long
highlight video is done later by merge_highlights.py.

Usage:
  python render_clip.py <spec.json>

spec.json:
{
  "source": "E:\\\\Recordings\\\\Game\\\\file.mp4",
  "out": "E:\\\\Highlights\\\\Game\\\\file\\\\01 - Title.mp4",
  "segments": [ {"start": 490.0, "end": 500.0, "label": "first kill"},
                {"start": 865.5, "end": 867.5, "label": "end screen", "layout": "center", "hold": 3} ],
  // "hold": N freezes the segment's last frame for N extra seconds
  // "layout" is NOT applied here: it is a framing hint (crop | blur | center) that the
  //   merger uses when it makes a vertical Short. Keep it in clips.json.
  "youtube": {"title": "...", "description": "...", "hashtags": ["..."]},
                           // optional: written next to the video as "<name>.txt"
  "mic_track": 1           // audio track index of the mic to mix in, or null
}

Each segment is cut and encoded the same way into a temp folder, then the parts are
joined without re-encoding (hard cuts between segments).
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BIN = Path(r"C:\Users\jeffr\AppData\Local\Microsoft\WinGet\Packages"
           r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.1-full_build\bin")


def probe_video(src):
    r = subprocess.run([str(BIN / "ffprobe.exe"), "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height,r_frame_rate", "-of", "json", src],
                       capture_output=True, text=True, check=True)
    s = json.loads(r.stdout)["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return int(s["width"]), int(s["height"]), float(num) / float(den)


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


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"ffmpeg failed:\n{r.stderr[-2000:]}")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    src, out = spec["source"], Path(spec["out"])
    segs = spec["segments"]
    mic = spec.get("mic_track")
    if not segs:
        sys.exit("no segments")
    for s in segs:
        if s["end"] <= s["start"]:
            sys.exit(f"bad segment {s}")

    w, h, fps = probe_video(src)
    fps_out = round(fps)
    # Bitrate scaled from 12 Mb/s at 1080p60 (h264 needs more for 1440p / 120 fps).
    mbps = min(45, max(10, round(12 * (w * h) / (1920 * 1080) * max(1.0, fps_out / 60))))

    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="clip_", dir=Path.home()))
    try:
        parts = []
        for i, s in enumerate(segs):
            part = tmp / f"part_{i:02d}.mp4"
            hold = float(s.get("hold", 0))
            vhold = f",tpad=stop_mode=clone:stop_duration={hold}" if hold else ""
            vfilter = f"[0:v]setsar=1{vhold},fps={fps_out},format=yuv420p[v]"
            ahold = f",apad=pad_dur={hold}" if hold else ""
            afilter = ((f";[0:a:0][0:a:{mic}]amix=inputs=2:normalize=0,aresample=48000{ahold}[aout]")
                       if mic is not None else f";[0:a:0]aresample=48000{ahold}[aout]")
            run([str(BIN / "ffmpeg.exe"), "-v", "error", "-y", "-ss", str(s["start"]),
                 "-t", str(s["end"] - s["start"]), "-i", src,
                 "-filter_complex", vfilter + afilter, "-map", "[v]", "-map", "[aout]",
                 "-c:v", "h264_amf", "-quality", "quality", "-b:v", f"{mbps}M",
                 "-c:a", "aac", "-b:a", "192k", "-ac", "2", str(part)])
            parts.append(part)
        listfile = tmp / "list.txt"
        listfile.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
        run([str(BIN / "ffmpeg.exe"), "-v", "error", "-y", "-f", "concat", "-safe", "0",
             "-i", str(listfile), "-c", "copy", "-movflags", "+faststart", str(out)])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if spec.get("youtube"):
        write_youtube_txt(out, spec["youtube"])

    probe = subprocess.run([str(BIN / "ffprobe.exe"), "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", str(out)], capture_output=True, text=True)
    total = sum(s["end"] - s["start"] + float(s.get("hold", 0)) for s in segs)
    print(f"rendered {out} : {w}x{h} {fps_out} fps {mbps} Mb/s, {len(segs)} segments, "
          f"planned {total:.1f}s, actual {float(probe.stdout):.1f}s")


if __name__ == "__main__":
    main()
