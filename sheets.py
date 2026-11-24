"""Make timestamped contact sheets (grids of frames) from a recording.

Used to split a long session into matches/raids cheaply: one sheet image shows
many moments at once, each labelled with its time in the recording.

Usage:
  python sheets.py <recording> <out_dir> [--every 10] [--start 0] [--end <s>] [--cols 4] [--rows 4] [--width 320]
  python sheets.py <recording> <out_dir> --fights <rms_a0.txt> [--every 4] [--fight-db 15] [--fight-pct 95]

Writes out_dir/sheet_001.jpg, ... Each tile is labelled H:MM:SS (time in the recording),
read left to right, then top to bottom.

--fights: frames only around sudden loud moments (gunfire, explosions, shouting), found in
the per-second loudness file made by the PROCEDURE's astats command. A second counts as a
spike when it is at least --fight-db dB above the median of the minute around it AND among
the loudest (100 - --fight-pct)% of the recording. Each spike gets a window from 6 s before
to 4 s after it; windows closer than 4 s merge. Frames every --every s (default 4) inside
the windows, so sheets may jump in time: always read the tile labels. Pair it with a sparse
overview (--every 30) of the whole recording for phases (lobby, loading, raid start/end).
On an 84 min Arena Breakout recording this was 30 sheets in total, the same as the old
10 s overview, with fights covered 2.5x more densely.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

BIN = Path(r"C:\Users\jeffr\AppData\Local\Microsoft\WinGet\Packages"
           r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.1-full_build\bin")
FONT = "C\\:/Windows/Fonts/arialbd.ttf"


def duration(src):
    out = subprocess.run([str(BIN / "ffprobe.exe"), "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", src], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def fight_windows(rms_file, db, pct, pre=6.0, post=4.0, merge=4.0):
    txt = Path(rms_file).read_text(encoding="utf-8", errors="replace")
    t = np.array([float(x) for x in re.findall(r"pts_time:([0-9.]+)", txt)])
    v = np.array([float(x) if re.match(r"^-?[0-9.]+$", x) else -120.0
                  for x in re.findall(r"RMS_level=(\S+)", txt)])
    n = min(len(t), len(v))
    t, v = t[:n], v[:n]
    if not n:
        sys.exit(f"no loudness values in {rms_file}")
    base = np.array([np.median(v[max(0, i - 30):i + 31]) for i in range(n)])
    hot = t[(v - base >= db) & (v >= np.percentile(v, pct))]
    wins = []
    for x in hot:
        if wins and x - pre - wins[-1][1] <= merge:
            wins[-1][1] = x + post
        else:
            wins.append([max(0.0, x - pre), x + post])
    return wins


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out_dir")
    ap.add_argument("--every", type=float)
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--end", type=float)
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--rows", type=int, default=4)
    ap.add_argument("--width", type=int, default=320)
    ap.add_argument("--fights", metavar="RMS_FILE")
    ap.add_argument("--fight-db", type=float, default=15)
    ap.add_argument("--fight-pct", type=float, default=95)
    a = ap.parse_args()
    every = a.every or (4.0 if a.fights else 10.0)

    end = a.end if a.end is not None else duration(a.src)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("sheet_*.jpg"):
        old.unlink()
    # Decode keyframes only (-skip_frame nokey): ~50x faster than decoding every
    # frame. The label shows each tile's real time, accurate to the keyframe spacing.
    if a.fights:
        wins = [w for w in fight_windows(a.fights, a.fight_db, a.fight_pct)
                if w[1] > a.start and w[0] < end]
        if not wins:
            print("no fight windows found")
            return
        # one pass over the whole file; keep a frame every `every` s inside any window
        inside = "+".join(f"between(t,{w0:.2f},{w1:.2f})" for w0, w1 in wins)
        sel = f"select='({inside})*(isnan(prev_selected_t)+gte(t-prev_selected_t,{every - 0.1:.2f}))'"
        label = (f"drawtext=fontfile='{FONT}':text='%{{pts\\:hms}}':"
                 "x=4:y=4:fontsize=20:fontcolor=yellow:box=1:boxcolor=black@0.7:boxborderw=3")
        vf = f"{sel},scale={a.width}:-2,{label},tile={a.cols}x{a.rows}:padding=2"
        cmd = [str(BIN / "ffmpeg.exe"), "-v", "error", "-y", "-skip_frame", "nokey",
               "-i", a.src, "-an", "-vf", vf, "-fps_mode", "passthrough", "-q:v", "4",
               str(out / "sheet_%03d.jpg")]
        r = subprocess.run(cmd)
        if r.returncode:
            sys.exit(r.returncode)
        cov = sum(w1 - w0 for w0, w1 in wins)
        print(f"{len(wins)} fight windows, {cov:.0f} s ({cov / end * 100:.0f}% of the recording), "
              f"{len(list(out.glob('sheet_*.jpg')))} sheets, a frame every {every:g} s inside them")
        print("windows: " + ", ".join(f"{w0:.0f}-{w1:.0f}" for w0, w1 in wins))
        return

    label = (f"drawtext=fontfile='{FONT}':text='%{{pts\\:hms\\:{a.start}}}':"
             "x=4:y=4:fontsize=20:fontcolor=yellow:box=1:boxcolor=black@0.7:boxborderw=3")
    vf = f"fps=1/{every},scale={a.width}:-2,{label},tile={a.cols}x{a.rows}:padding=2"
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
        t0 = a.start + i * per * every
        print(f"{s.name}: {t0:.0f}s - {min(end, t0 + per * every):.0f}s")


if __name__ == "__main__":
    main()
