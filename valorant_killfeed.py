"""Find the user's kills and deaths, and the rounds and matches, in a Valorant recording.

One pass over the recording's keyframes reads three regions of the screen:

Kill feed (top right). Valorant writes the local player as "Me", with a gold outline.
Teammates, including the one you spectate after dying, appear under their own names,
so a "Me" entry proves the play is the user's.
  - "Me" on the LEFT of an entry (killer side)  -> the user got a kill
  - "Me" on the RIGHT of an entry (victim side) -> the user died

Round banner (top centre):
  - "PRESS [B] TO BUY" under the buy-phase banner (BUY PHASE, MATCH POINT, OVERTIME...)
    -> buy phase; the round goes live when it disappears
  - WON / LOST -> round result. Other round-end banners (CLUTCH, ACE, FLAWLESS,
    THRIFTY...) end the round with an unknown result: CLUTCH is shown to both teams.
Screen centre: VICTORY / DEFEAT -> end of a match.

Only keyframes are decoded (NVIDIA recordings have one every 0.5 s, AMD Adrenalin
recordings one every 1 s; a kill feed entry stays up for several seconds), so a 2-hour
recording takes about 3 minutes.

Usage:
  python valorant_killfeed.py <recording> <out.json> [--start s] [--end s] [--debug-dir dir]

Output JSON:
  "kills":    [{"t": 244.1, "row_y": 112, "round": 3}]
  "deaths":   [{"t": 255.6, "round": 3}]      (at most one per round)
  "clusters": [{"start", "end", "kills", "kill_times", "died_at", "round"}]
              the user's kills in one life: a death ends a cluster, and so does a new
              round or a gap over 30 s
  "rounds":   [{"index", "match", "buy_start", "start", "end", "result"}]
              start = round goes live, end = round-end banner, result won | lost | null
              (null = a CLUTCH/ACE-type banner, or no banner seen)
  "matches":  [{"index", "start", "end", "result", "rounds", "won", "lost", "unknown",
                "kills", "deaths"}]
              result victory | defeat | null (recording ends or the match was left)
Kill and death times are the first keyframe where the entry is visible (the kill happened
up to one keyframe interval before).

--debug-dir writes killfeed_NN.jpg: a strip of the kill feed for every detection, 24 per
image, labelled with its time and K (kill) or D (death). View these instead of full frames.

Validated on "Valorant 2026.08.01 - 16.15.54.03": 49 kills / 43 deaths, exactly the
K and D on the three end-of-match scoreboards, no false positives.
Assumes the default HUD scale and positions. Templates: templates/valorant/*.png.
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

HERE = Path(__file__).resolve().parent
BIN = Path(r"C:\Users\jeffr\AppData\Local\Microsoft\WinGet\Packages"
           r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.1-full_build\bin")
TPL_DIR = HERE / "templates" / "valorant"

# Regions in 1920x1080 coordinates (frames are scaled to 1920 wide first).
X0, Y0, W, H = 1200, 88, 710, 330          # kill feed
BX, BY, BW, BH = 720, 120, 480, 180         # round banner band (top centre)
CX, CY, CW, CH = 560, 360, 800, 360         # screen centre, scanned at half size
CW2, CH2 = CW // 2, CH // 2
FRAME_H = H + BH + CH2                      # the three regions stacked, W wide

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

# Phase templates (binary masks) and the score each needs. Tuned on
# "Valorant 2026.06.20 - 17.58.06.02" (see the git history for the measurements).
PHASE_MIN = {"buy": 0.60, "won": 0.70, "lost": 0.70, "victory": 0.55, "defeat": 0.55}
BANNER_TEXT_MIN = 1500  # white pixels in the banner's text area = some round banner is up


def load_tpl(name):
    t = cv2.imread(str(TPL_DIR / f"{name}.png"), cv2.IMREAD_GRAYSCALE)
    if t is None:
        sys.exit(f"missing template {TPL_DIR / name}.png")
    return cv2.GaussianBlur(t.astype(np.float32), (3, 3), 0)


def white_mask(bgr, thr=140):
    g = bgr.min(axis=2).astype(np.float32)
    return cv2.GaussianBlur(np.clip((g - thr) / 80, 0, 1) * 255, (3, 3), 0)


def hard_white(bgr, thr):
    return (bgr.min(axis=2) > thr).astype(np.float32) * 255


def colour_mask(bgr):
    mx, mn = bgr.max(axis=2).astype(np.int16), bgr.min(axis=2).astype(np.int16)
    return ((mx > 150) & (mx - mn > 90)).astype(np.float32) * 255


def best(img, tpl):
    if img.shape[0] < tpl.shape[0] or img.shape[1] < tpl.shape[1]:
        return 0.0
    return float(cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED).max())


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


def frames(src, start, end, step=1):
    """Yield (time, kill feed, banner band, centre at half size) for every keyframe.
    step > 1 keeps only every step-th keyframe (to test wider keyframe spacing)."""
    times = []
    cmd = [str(BIN / "ffmpeg.exe"), "-hide_banner", "-skip_frame", "nokey"]
    if start:
        cmd += ["-ss", str(start)]
    if end:
        cmd += ["-to", str(end)]
    fc = (f"[0:v]scale=1920:1080,split=3[a][b][c];"
          f"[a]crop={W}:{H}:{X0}:{Y0}[k];"
          f"[b]crop={BW}:{BH}:{BX}:{BY},pad={W}:{BH}[bd];"
          f"[c]crop={CW}:{CH}:{CX}:{CY},scale={CW2}:{CH2},pad={W}:{CH2}[ce];"
          f"[k][bd][ce]vstack=3,showinfo[out]")
    cmd += ["-copyts", "-i", src, "-an", "-filter_complex", fc, "-map", "[out]",
            "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def read_err():
        for line in p.stderr:
            mt = re.search(rb"pts_time:([0-9.]+)", line)
            if mt:
                times.append(float(mt.group(1)))
    th = threading.Thread(target=read_err, daemon=True)
    th.start()
    size = W * FRAME_H * 3
    i = 0
    while True:
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        while len(times) <= i and th.is_alive():
            th.join(0.01)
        t = times[i] if i < len(times) else (times[-1] + 0.5 if times else i * 0.5)
        i += 1
        if (i - 1) % step:
            continue
        f = np.frombuffer(buf, np.uint8).reshape(FRAME_H, W, 3)
        yield t, f[:H], f[H:H + BH, :BW], f[H + BH:, :CW2]
    p.wait()


def runs(points, gap):
    """Group sorted times into [first, last] runs; a new run starts after a gap > gap."""
    out = []
    for t in points:
        if out and t - out[-1][1] <= gap:
            out[-1][1] = t
        else:
            out.append([t, t])
    return out


class Strips:
    """Kill feed strips for every detection, 24 per image (cheap to view)."""
    PER = 24

    def __init__(self, folder):
        self.dir, self.rows, self.n = folder, [], 0

    def add(self, img, y, t, tag):
        y0, y1 = max(0, y - 14), min(img.shape[0], y + 30)
        s = np.zeros((44, W, 3), np.uint8)
        s[:y1 - y0] = img[y0:y1]
        lab = np.zeros((44, 130, 3), np.uint8)
        cv2.putText(lab, f"{t:7.1f} {tag}", (4, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (0, 255, 255) if tag == "K" else (80, 80, 255), 2)
        self.rows.append(np.hstack([lab, s]))
        if len(self.rows) == self.PER:
            self.flush()

    def flush(self):
        if self.rows:
            self.n += 1
            cv2.imwrite(str(self.dir / f"killfeed_{self.n:02d}.jpg"), np.vstack(self.rows),
                        [cv2.IMWRITE_JPEG_QUALITY, 85])
            self.rows = []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--end", type=float)
    ap.add_argument("--debug-dir")
    ap.add_argument("--features", help="write every keyframe's phase scores here (for tuning)")
    ap.add_argument("--keyframe-step", type=int, default=1, help=argparse.SUPPRESS)
    a = ap.parse_args()
    dbg = None
    if a.debug_dir:
        Path(a.debug_dir).mkdir(parents=True, exist_ok=True)
        for old in Path(a.debug_dir).glob("killfeed_*.jpg"):
            old.unlink()
        dbg = Strips(Path(a.debug_dir))

    tpl = {k: load_tpl(k) for k in PHASE_MIN}
    kills, deaths, feats = [], [], []
    phase_hits = {k: [] for k in PHASE_MIN}
    banner_text = []
    active = []   # entries on screen: {"kind", "x", "y", "last"}
    prev_t, gaps = None, []
    expire = 1.6
    for t, img, band, centre in frames(a.src, a.start, a.end, a.keyframe_step):
        # Keyframe spacing decides how long an unseen entry stays "on screen": an entry
        # can be missed on a keyframe or two, but must not be re-counted as a new kill.
        if prev_t is not None:
            gaps.append(t - prev_t)
            if len(gaps) == 40:
                kf = float(np.median(gaps))
                expire = max(1.6, 2.5 * kf)
        prev_t = t

        # ---- phases
        bw = hard_white(band, 215)
        sc = {"buy": best(hard_white(band, 190), tpl["buy"]),
              "won": best(bw, tpl["won"]), "lost": best(bw, tpl["lost"])}
        cm = colour_mask(centre)
        sc["victory"], sc["defeat"] = best(cm, tpl["victory"]), best(cm, tpl["defeat"])
        txt = int((bw[30:120, 140:340] > 0).sum())
        for k, v in sc.items():
            if v >= PHASE_MIN[k]:
                phase_hits[k].append(t)
        if (txt >= BANNER_TEXT_MIN and sc["buy"] < PHASE_MIN["buy"]
                and sc["won"] < PHASE_MIN["won"] and sc["lost"] < PHASE_MIN["lost"]):
            banner_text.append(t)          # some other round-end banner (CLUTCH, ACE...)
        if a.features:
            feats.append({"t": round(t, 2), **{k: round(v, 3) for k, v in sc.items()}, "txt": txt})

        # ---- kill feed
        hits = []
        for x, y, v in find_me(img):
            if gold_near(img, x, y) < GOLD_MIN:     # "Me" inside someone's name, or noise
                continue
            hits.append(("kill" if X0 + x <= KILLER_SIDE_MAX_X else "death", x, y))
        # Entries keep their x and only ever move up (older rows expire above them), so a
        # hit continues an entry with the same kind and x at the same or a higher row.
        active = [e for e in active if t - e["last"] <= expire]
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
            if dbg:
                dbg.add(img, e["y"], t, "K" if e["kind"] == "kill" else "D")
    if dbg:
        dbg.flush()
    kf = float(np.median(gaps)) if gaps else 0.5

    # ---- rounds and matches
    buys = runs(phase_hits["buy"], 15.0)            # one run per buy phase
    ends = sorted([(r[0], "won") for r in runs(phase_hits["won"], 3.0)] +
                  [(r[0], "lost") for r in runs(phase_hits["lost"], 3.0)] +
                  [(r[0], "other") for r in runs(banner_text, 3.0) if r[1] - r[0] >= kf])
    mends = sorted([(r[0], "victory") for r in runs(phase_hits["victory"], 5.0)] +
                   [(r[0], "defeat") for r in runs(phase_hits["defeat"], 5.0)])
    # a VICTORY and a DEFEAT run close together is one screen: keep the first
    mends = [m for i, m in enumerate(mends) if i == 0 or m[0] - mends[i - 1][0] > 30]
    rounds = []
    for i, (b0, b1) in enumerate(buys):
        live = b1 + kf
        nxt = buys[i + 1][0] if i + 1 < len(buys) else float("inf")
        r = {"index": i + 1, "buy_start": round(b0, 2), "start": round(live, 2),
             "end": None, "result": None}
        for t, kind in ends:                         # the first banner after going live
            if live <= t < nxt:
                if kind == "other" and any(live <= t2 < nxt and k2 != "other" for t2, k2 in ends):
                    continue
                # CLUTCH, ACE etc. are shown to both teams: the result stays unknown
                r["end"], r["result"] = round(t, 2), None if kind == "other" else kind
                break
        rounds.append(r)
    matches, m_idx, cur = [], 1, []
    pending = list(mends)

    def close(result, t_end):
        nonlocal m_idx, cur
        if cur:
            matches.append({"index": m_idx, "start": cur[0]["start"], "end": t_end,
                            "result": result, "rounds": len(cur)})
            m_idx += 1
        cur = []

    for r in rounds:
        while pending and pending[0][0] < r["buy_start"]:
            t_end, res = pending.pop(0)
            close(res, round(t_end, 2))
        if cur and r["buy_start"] - (cur[-1]["end"] or cur[-1]["start"]) > 360:
            close(None, cur[-1]["end"])              # long gap: a match was left or cut
        cur.append(r)
        r["match"] = m_idx
    while pending:
        t_end, res = pending.pop(0)
        close(res, round(t_end, 2))
    close(None, cur[-1]["end"] if cur else None)

    def round_of(t):
        for r in reversed(rounds):
            if r["buy_start"] <= t:
                return r["index"]
        return None

    for k in kills:
        k["round"] = round_of(k["t"])
    # The user can only die once per round. A second "Me" death in the same round (or
    # within 20 s without rounds) is the same entry seen again.
    kept = []
    for d in deaths:
        d["round"] = round_of(d["t"])
        if kept and ((d["round"] is not None and d["round"] == kept[-1]["round"]) or
                     (d["round"] is None and d["t"] - kept[-1]["t"] < 20)):
            continue
        kept.append(d)
    dropped = len(deaths) - len(kept)
    deaths = kept
    for m in matches:
        ids = {r["index"] for r in rounds if r.get("match") == m["index"]}
        m["won"] = sum(1 for r in rounds if r["index"] in ids and r["result"] == "won")
        m["lost"] = sum(1 for r in rounds if r["index"] in ids and r["result"] == "lost")
        m["unknown"] = m["rounds"] - m["won"] - m["lost"]
        m["kills"] = sum(1 for k in kills if k["round"] in ids)
        m["deaths"] = sum(1 for d in deaths if d["round"] in ids)

    # One cluster = the user's kills in one life. A death always ends a cluster (after it
    # the user is spectating), and so do a new round and a gap over CLUSTER_GAP.
    clusters = []
    # On a tie (kill and death on the same keyframe, i.e. a trade) the kill goes first,
    # so the death still ends that cluster.
    events = sorted([(k["t"], 0, "k", k["round"]) for k in kills] +
                    [(d["t"], 1, "d", d["round"]) for d in deaths],
                    key=lambda e: (e[0], e[1]))
    open_c = None
    for t, _, kind, rnd in events:
        same = open_c and t - open_c["end"] <= CLUSTER_GAP and open_c["round"] == rnd
        if kind == "d":
            if same:
                open_c["died_at"] = t
            open_c = None
            continue
        if same:
            open_c["end"] = t
            open_c["kills"] += 1
            open_c["kill_times"].append(t)
        else:
            open_c = {"start": t, "end": t, "kills": 1, "kill_times": [t], "died_at": None,
                      "round": rnd}
            clusters.append(open_c)

    result = {"source": a.src, "keyframe_interval": round(kf, 3),
              "kills": kills, "deaths": deaths, "clusters": clusters,
              "rounds": rounds, "matches": matches}
    Path(a.out).write_text(json.dumps(result, indent=1), encoding="utf-8")
    if a.features:
        Path(a.features).write_text(json.dumps(feats), encoding="utf-8")
    print(f"{len(kills)} kills, {len(deaths)} deaths ({dropped} duplicate deaths dropped), "
          f"{len(clusters)} clusters, {len(rounds)} rounds, {len(matches)} matches, "
          f"keyframes every {kf:.2f} s")
    for m in matches:
        end = f"{m['end']:.0f}s" if m["end"] is not None else "?"
        print(f"  match {m['index']}: {m['start']:.0f}s-{end}  {m['result'] or 'no result'}"
              f"  rounds {m['rounds']} (won {m['won']}, lost {m['lost']}, unknown {m['unknown']})"
              f"  K {m['kills']}  D {m['deaths']}")
    for c in clusters:
        print(f"  {c['start']:7.1f}-{c['end']:7.1f}s  round {c['round']}  kills={c['kills']}  died_at={c['died_at']}")


if __name__ == "__main__":
    sys.exit(main())
