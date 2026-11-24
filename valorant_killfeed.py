"""Find the user's own kills and deaths in a Valorant recording from the kill feed.

Valorant writes the local player as "Me" in the kill feed (top right), with a gold
outline. Teammates, including the one you spectate after dying, appear under their
own names, so a "Me" entry is proof that the play is the user's.

  - "Me" on the LEFT of an entry (killer side)  -> the user got a kill
  - "Me" on the RIGHT of an entry (victim side) -> the user died

Only keyframes are decoded (Valorant recordings have one every 0.5 s and a kill
feed entry stays up for several seconds), so a 1h40m recording takes 2-3 minutes.

Usage:
  python valorant_killfeed.py <recording> <out.json> [--start s] [--end s] [--debug-dir dir]

Output JSON:
  {"kills": [{"t": 244.1, "row_y": 112}], "deaths": [{"t": 255.6}],
   "clusters": [{"start": 240.1, "end": 252.6, "kills": 2, "died_at": 255.6}]}
Times are the first keyframe where the entry is visible (the kill happened 0-0.5 s
before). Clusters group kills less than 30 s apart in one life (a death ends a cluster).

Validated on "Valorant 2026.08.01 - 16.15.54.03": 49 kills / 43 deaths, exactly the
K and D on the three end-of-match scoreboards, no false positives.
Assumes the default HUD scale and kill feed position (top right).
"""
import argparse
import json
import re
import subprocess
import sys
import threading
from pathlib import Path

import cv2
import numpy as np

BIN = Path(r"C:\Users\jeffr\AppData\Local\Microsoft\WinGet\Packages"
           r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.1-full_build\bin")

# Kill feed region in 1920x1080 coordinates (frames are scaled to 1920 wide first).
X0, Y0, W, H = 1200, 88, 710, 330
# "Me" in white text, cut from real footage (1080p HUD scale).
ME = np.array([[int(c == "#") for c in r] for r in [
    "##.....##.........",
    "##.....##.........",
    "###...###....###..",
    "#.#..####...#...##",
    "#.##.#..#..##....#",
    "#..###..#..#######",
    "#..###..#..##.....",
    "#...#...#...#.....",
    "#.......#...#####.",
]], dtype=np.uint8) * 255
# The victim's name ends just left of their portrait at about x=1850. "Me" with its
# left edge left of this line is on the killer side.
KILLER_SIDE_MAX_X = 1740
MATCH_MIN = 0.80        # real "Me" entries score 0.84-0.93; HUD/map noise stays below 0.78
GOLD_MIN = 150          # gold outline pixels around a real "Me" entry: 300-650; noise: mostly < 100
CLUSTER_GAP = 30.0
# Soft template (blurred, padded) so 1 px rendering/compression differences still match.
ME_SOFT = cv2.copyMakeBorder(cv2.GaussianBlur(ME.astype(np.float32), (3, 3), 0),
                             2, 2, 2, 2, cv2.BORDER_CONSTANT, value=0)


def white_mask(bgr):
    g = bgr.min(axis=2).astype(np.float32)
    return cv2.GaussianBlur(np.clip((g - 140) / 80, 0, 1) * 255, (3, 3), 0)


def gold_near(bgr, x, y):
    """Count gold outline pixels in the entry band around a "Me" hit (feed-local coords)."""
    y0, y1 = max(0, y - 16), min(bgr.shape[0], y + 26)
    x0, x1 = max(0, x - 110), min(bgr.shape[1], x + 140)
    b = bgr[y0:y1, x0:x1].astype(int)
    B, G, R = b[..., 0], b[..., 1], b[..., 2]
    return int(((R > 190) & (G > 185) & (B < 160) & (np.abs(R - G) < 35)).sum())


def find_me(bgr):
    m = white_mask(bgr)
    res = cv2.matchTemplate(m, ME_SOFT, cv2.TM_CCOEFF_NORMED)
    hits = []
    while True:
        _, v, _, (x, y) = cv2.minMaxLoc(res)
        if v < MATCH_MIN:
            break
        hits.append((x, y, float(v)))
        res[max(0, y - 12):y + 12, max(0, x - 20):x + 20] = -1
    return hits


def frames(src, start, end, ow=1920):
    """Yield (time, bgr crop) for every keyframe."""
    times = []
    cmd = [str(BIN / "ffmpeg.exe"), "-hide_banner", "-skip_frame", "nokey"]
    if start:
        cmd += ["-ss", str(start)]
    if end:
        cmd += ["-to", str(end)]
    cmd += ["-copyts", "-i", src, "-an",
            "-vf", f"scale={ow}:-2,crop={W}:{H}:{X0}:{Y0},showinfo",
            "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def read_err():
        for line in p.stderr:
            mt = re.search(rb"pts_time:([0-9.]+)", line)
            if mt:
                times.append(float(mt.group(1)))
    th = threading.Thread(target=read_err, daemon=True)
    th.start()
    size = W * H * 3
    i = 0
    while True:
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        while len(times) <= i and th.is_alive():
            th.join(0.01)
        t = times[i] if i < len(times) else (times[-1] + 0.5 if times else i * 0.5)
        yield t, np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        i += 1
    p.wait()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--end", type=float)
    ap.add_argument("--debug-dir")
    a = ap.parse_args()
    dbg = Path(a.debug_dir) if a.debug_dir else None
    if dbg:
        dbg.mkdir(parents=True, exist_ok=True)

    kills, deaths = [], []
    active = []   # entries on screen: {"kind", "x", "y", "last"}
    for t, img in frames(a.src, a.start, a.end):
        hits = []
        for x, y, v in find_me(img):
            if gold_near(img, x, y) < GOLD_MIN:     # "Me" inside someone's name, or noise
                continue
            hits.append(("kill" if X0 + x <= KILLER_SIDE_MAX_X else "death", x, y))
        # Entries keep their x and only ever move up (older rows expire above them), so a
        # hit continues an entry with the same kind and x at the same or a higher row.
        # A keyframe or two can miss an entry, so entries live 1.6 s without being seen.
        active = [e for e in active if t - e["last"] <= 1.6]
        used = set()
        new = []
        for kind, x, y in sorted(hits, key=lambda h: h[2]):
            cands = [i for i, e in enumerate(active) if i not in used and e["kind"] == kind
                     and abs(e["x"] - x) <= 4 and y <= e["y"] + 6]
            if cands:
                i = min(cands, key=lambda i: active[i]["y"] - y)   # nearest row at/below
                used.add(i)
                active[i].update(y=y, last=t)
            else:
                new.append({"kind": kind, "x": x, "y": y, "last": t})
        for e in new:
            active.append(e)
            used.add(len(active) - 1)
            (kills if e["kind"] == "kill" else deaths).append({"t": round(t, 2), "row_y": int(Y0 + e["y"])})
        if dbg and new:
            tag = "".join("K" if e["kind"] == "kill" else "D" for e in new)
            cv2.imwrite(str(dbg / f"{t:08.1f}_{tag}.png"), img)

    # One cluster = the user's kills in one life (one round). A death always ends a
    # cluster (after it the user is spectating), and so does a gap over CLUSTER_GAP.
    clusters = []
    # On a tie (kill and death on the same keyframe, i.e. a trade) the kill goes first,
    # so the death still ends that cluster.
    events = sorted([(k["t"], 0, "k") for k in kills] + [(d["t"], 1, "d") for d in deaths])
    open_c = None
    for t, _, kind in events:
        if kind == "d":
            if open_c and t - open_c["end"] <= CLUSTER_GAP:
                open_c["died_at"] = t
            open_c = None
            continue
        if open_c and t - open_c["end"] <= CLUSTER_GAP:
            open_c["end"] = t
            open_c["kills"] += 1
            open_c["kill_times"].append(t)
        else:
            open_c = {"start": t, "end": t, "kills": 1, "kill_times": [t], "died_at": None}
            clusters.append(open_c)

    Path(a.out).write_text(json.dumps({"kills": kills, "deaths": deaths, "clusters": clusters},
                                      indent=1), encoding="utf-8")
    print(f"{len(kills)} kills, {len(deaths)} deaths, {len(clusters)} clusters")
    for c in clusters:
        print(f"  {c['start']:7.1f}-{c['end']:7.1f}s  kills={c['kills']}  died_at={c['died_at']}")


if __name__ == "__main__":
    sys.exit(main())
