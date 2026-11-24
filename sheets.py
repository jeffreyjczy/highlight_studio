"""Make timestamped contact sheets (grids of frames) from a recording.

Used to split a long session into matches/raids cheaply: one sheet image shows
many moments at once, each labelled with its time in the recording.

Usage:
  python sheets.py <recording> <out_dir> [--every 10] [--start 0] [--end <s>] [--cols 4] [--rows 4] [--width 320]

Writes out_dir/sheet_001.jpg, ... Each tile is labelled H:MM:SS (time in the recording),
read left to right, then top to bottom.
"""
import argparse
import subprocess
import sys
from pathlib import Path

BIN = Path(r"C:\Users\jeffr\AppData\Local\Microsoft\WinGet\Packages"
           r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.1-full_build\bin")
FONT = "C\\:/Windows/Fonts/arialbd.ttf"


def duration(src):
    out = subprocess.run([str(BIN / "ffprobe.exe"), "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", src], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out_dir")
    ap.add_argument("--every", type=float, default=10)
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--end", type=float)
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--rows", type=int, default=4)
    ap.add_argument("--width", type=int, default=320)
    a = ap.parse_args()

    end = a.end if a.end is not None else duration(a.src)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("sheet_*.jpg"):
        old.unlink()
    # Decode keyframes only (-skip_frame nokey): ~50x faster than decoding every
    # frame. The label shows each tile's real time, accurate to the keyframe spacing.
    label = (f"drawtext=fontfile='{FONT}':text='%{{pts\\:hms\\:{a.start}}}':"
             "x=4:y=4:fontsize=20:fontcolor=yellow:box=1:boxcolor=black@0.7:boxborderw=3")
    vf = f"fps=1/{a.every},scale={a.width}:-2,{label},tile={a.cols}x{a.rows}:padding=2"
    cmd = [str(BIN / "ffmpeg.exe"), "-v", "error", "-y", "-skip_frame", "nokey",
           "-ss", str(a.start), "-t", str(end - a.start),
           "-i", a.src, "-an", "-vf", vf, "-fps_mode", "passthrough", "-q:v", "4",
           str(out / "sheet_%03d.jpg")]
    r = subprocess.run(cmd)
    if r.returncode:
        sys.exit(r.returncode)
    sheets = sorted(out.glob("sheet_*.jpg"))
    per = a.cols * a.rows
    for i, s in enumerate(sheets):
        t0 = a.start + i * per * a.every
        print(f"{s.name}: {t0:.0f}s - {min(end, t0 + per * a.every):.0f}s")


if __name__ == "__main__":
    main()
