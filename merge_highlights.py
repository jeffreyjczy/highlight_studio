"""Merge highlight shorts into one compilation, edited like a montage.

Usage:
  python merge_highlights.py <out.mp4> --folder <highlights folder> --music <file or folder> [options]
  python merge_highlights.py <out.mp4> <clip1.mp4> <clip2.mp4> ... [options]

What it does by itself (each part can be switched off):
  * Smart order   - with scores (clips.json): the 2nd-best clip opens as the hook, the best
                    clip closes as the finale, the rest play in the order they happened.
  * Tight cuts    - finds the action in every clip (kills from clips.json "events", the
                    Valorant kill detector, or loudness peaks) and trims dead time before
                    and after it.
  * Beat sync     - detects the music's tempo and beats, starts the music on a downbeat
                    (skipping a quiet intro), and moves every cut onto a beat (downbeats
                    preferred). The video ends on a beat.
  * Transitions   - picked per cut: fade to black after a death, a white flash into the
                    finale, and a varied set of quick motion transitions elsewhere, each
                    half a beat long.
  * Kill punch    - a short zoom punch and a light flash on every kill/action moment.
  * Sound         - music ducks under gameplay (shots and voice stay clear), fades in and
                    out; the whole mix is normalised to -14 LUFS. Fade in from and out to black.

Formats (the clips themselves are horizontal, full resolution):
  --format short        vertical 1080x1920 for YouTube Shorts / TikTok (default), max 180 s.
                        Each segment is framed by its clips.json "layout" hint:
                        crop (zoom on the action, default) | blur (whole frame) | center
  --format long         horizontal video, --size WxH (default 1920x1080), no length cap
  --hq                  1440p output: Shorts 1440x2560, long 2560x1440 (bitrate scaled up).
                        YouTube gives 1440p+ uploads a better encode; worth an A/B test.

Options:
  --folder DIR          use every short in DIR (clips.json gives scores, order and times)
  --order smart|time|score|given   (default: smart if scores exist, else given)
  --music PATH          music file, or a folder to pick one from at random
  --music-start S       start the music at S seconds (default: auto, first strong downbeat)
  --seed N              fixes random choices (music pick, transitions)
  --style punchy|clean  punchy (default): varied transitions, kill punch;
                        clean: plain crossfades, no punch or flash
  --transition NAME     use this one xfade transition for every cut
  --no-trim | --no-sync | --no-punch | --no-flash | --no-duck
  --lead S / --tail S   seconds kept before the first / after the last action (3.0 / 1.8)
  --max-length S        drop the lowest-scored clips until the video fits (e.g. 180 for Shorts)
  --music-volume DB     music level before ducking (default -12)
  --game-volume X       gameplay audio gain (default 1.0; 0 = music only)
  --lufs N              loudness target (default -14)
  --dry-run             print the edit plan without rendering

Output: <out.mp4> and <out>.json (the edit plan: clips, in/out points, transitions,
beats, action times). Existing files are never overwritten: " (2)" is added instead.
Inputs are only read.
"""
import argparse
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
BIN = Path(r"C:\Users\jeffr\AppData\Local\Microsoft\WinGet\Packages"
           r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.1-full_build\bin")
FFMPEG, FFPROBE = str(BIN / "ffmpeg.exe"), str(BIN / "ffprobe.exe")
MUSIC_EXT = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus"}
SHORTS_MAX = 180.0
MOTION = ["smoothleft", "smoothup", "zoomin", "circleopen", "smoothright", "slideleft",
          "radial", "hlslice", "smoothdown", "circlecrop"]


# ---------------------------------------------------------------- probing / audio
def probe(path, size=False):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries",
                        "format=duration:stream=codec_type,width,height",
                        "-of", "json", str(path)], capture_output=True, text=True, check=True)
    d = json.loads(r.stdout)
    st = d.get("streams", [])
    dur, aud = float(d["format"]["duration"]), any(x["codec_type"] == "audio" for x in st)
    if not size:
        return dur, aud
    v = next((x for x in st if x["codec_type"] == "video"), {})
    return dur, aud, int(v.get("width", 1920)), int(v.get("height", 1080))


# Vertical framing for horizontal clips (Shorts). Picked per segment from the clip's
# "layout" hint in clips.json: crop = zoom on the centre for action (default),
# blur = whole frame for wide UI, center = strong zoom on result/stat screens.
# Each fills 1080x1920 with a blurred copy of the frame behind it.
FG = {"crop": "crop=ih*4/5:ih", "blur": "null", "center": "crop=iw*0.48:ih*0.75:iw*0.26:ih*0.2"}


def vertical(inp, out, layout, tag, W=1080, H=1920):
    fg = FG.get(layout, FG["crop"])
    bw, bh = W // 4, H // 4
    return (f"[{inp}]split[{tag}a][{tag}b];"
            f"[{tag}a]scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},"
            f"boxblur=10:2,scale={W}:{H},setsar=1[{tag}bg];"
            f"[{tag}b]{fg},scale={W}:-2,setsar=1[{tag}fg];"
            f"[{tag}bg][{tag}fg]overlay=0:(H-h)/2[{out}]")


def layout_spans(it):
    """[(clip_t0, clip_t1, layout)] from the clip's segments."""
    meta = it.get("meta") or {}
    segs = meta.get("segments") or []
    spans, pos = [], 0.0
    for sg in segs:
        ln = sg["end"] - sg["start"] + float(sg.get("hold", 0))
        spans.append((pos, pos + ln, sg.get("layout") or "crop"))
        pos += ln
    return spans or [(0.0, it["dur"], "crop")]


def decode_mono(path, sr, start=0.0, dur=None):
    cmd = [FFMPEG, "-v", "error"]
    if start:
        cmd += ["-ss", str(start)]
    if dur:
        cmd += ["-t", str(dur)]
    cmd += ["-i", str(path), "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


# ---------------------------------------------------------------- beat tracking
def analyse_music(path):
    """Tempo, beat times, downbeat phase and a sensible start point.

    Onset strength = positive spectral flux of a log-magnitude STFT. Tempo comes from
    the onset autocorrelation (70-180 BPM, biased towards ~120), beat phase from the
    grid offset that collects the most onset energy, and each beat is then nudged to
    the strongest onset within +-35 ms.
    """
    sr, hop, nfft = 22050, 512, 2048
    y = decode_mono(path, sr)
    if len(y) < sr * 5:
        return None
    nfr = 1 + (len(y) - nfft) // hop
    idx = np.arange(nfft)[None, :] + hop * np.arange(nfr)[:, None]
    win = np.hanning(nfft).astype(np.float32)
    onset = np.empty(nfr, np.float32)
    rms = np.empty(nfr, np.float32)
    prev = None
    for s in range(0, nfr, 2048):            # chunked to keep memory small
        fr = y[idx[s:s + 2048]] * win
        mag = np.log1p(10 * np.abs(np.fft.rfft(fr, axis=1)))
        if prev is not None:
            mag_prev = np.vstack([prev[None, :], mag[:-1]])
        else:
            mag_prev = np.vstack([mag[:1], mag[:-1]])
        onset[s:s + len(fr)] = np.maximum(0, mag - mag_prev).sum(axis=1)
        rms[s:s + len(fr)] = np.sqrt((fr ** 2).mean(axis=1))
        prev = mag[-1]
    fps = sr / hop
    o = onset - np.convolve(onset, np.ones(16) / 16, mode="same")   # remove slow trend
    o = np.maximum(o, 0)
    ac = np.correlate(o, o, mode="full")[len(o) - 1:]
    lags = np.arange(int(fps * 60 / 180), int(fps * 60 / 70) + 1)
    bpms = 60 * fps / lags
    weight = np.exp(-0.5 * (np.log2(bpms / 120) / 0.6) ** 2)
    best = lags[np.argmax(ac[lags] * weight)]
    # parabolic refinement of the period
    a, b, c = ac[best - 1], ac[best], ac[best + 1]
    period = best + 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else best
    # phase
    phases = np.arange(0, period, 0.5)
    scores = [o[np.round(np.arange(p, len(o) - 1, period)).astype(int)].sum() for p in phases]
    phase = phases[int(np.argmax(scores))]
    grid = np.arange(phase, len(o) - 1, period)
    beats = []
    for g in grid:
        lo, hi = max(0, int(g) - 1), min(len(o), int(g) + 2)
        beats.append(lo + int(np.argmax(o[lo:hi])))
    beats = np.array(beats) / fps
    # downbeat: the beat-in-4 position with the most onset energy
    bi = np.round(beats * fps).astype(int).clip(0, len(o) - 1)
    down = int(np.argmax([o[bi[k::4]].sum() for k in range(4)]))
    # start: first downbeat where the track is reasonably loud (skip quiet intros)
    loud = np.percentile(rms, 75)
    start = 0.0
    for k in range(down, len(beats), 4):
        f = int(beats[k] * fps)
        if rms[f:f + int(fps * 2)].mean() >= 0.5 * loud:
            start = float(beats[k])
            break
    return {"bpm": float(60 * fps / period), "period": float(period / fps), "beats": beats.tolist(),
            "downbeat_index": down, "start": start, "length": len(y) / sr}


def beat_grid(m, music_start, total_needed):
    """Beats (and which are downbeats) in OUTPUT time, music starting at output 0.
    If the music loops, the grid repeats with the loop."""
    beats = np.array(m["beats"])
    loop_len = m["length"] - music_start
    out, downs = [], []
    k0 = int(np.argmin(np.abs(beats - music_start)))
    rep = 0
    while True:
        base = rep * loop_len
        for k in range(k0, len(beats)):
            t = beats[k] - music_start + base
            if t < -0.01:
                continue
            if t > total_needed + 8:
                return np.array(out), np.array(downs, bool)
            out.append(t)
            downs.append((k - m["downbeat_index"]) % 4 == 0)
        rep += 1
        if rep > 50:
            return np.array(out), np.array(downs, bool)


# ---------------------------------------------------------------- clips and actions
def sibling_meta(clip):
    """A clip passed by path still gets its clips.json entry (scores, segments, events, layout)."""
    meta = clip.parent / "clips.json"
    if not meta.exists():
        return None, None
    try:
        data = json.loads(meta.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None, None
    for c in data.get("clips", []):
        if c.get("file") == clip.name and ("segments" in c or "score" in c):
            return c, data
    return None, None


def load_items(a):
    items = []
    for c in a.clips:
        f = Path(c)
        meta, data = sibling_meta(f)
        items.append({"file": f, "meta": meta, "source": (data or {}).get("source"),
                      "game": (data or {}).get("game")})
    if a.folder:
        folder = Path(a.folder)
        meta = folder / "clips.json"
        if meta.exists():
            data = json.loads(meta.read_text(encoding="utf-8-sig"))
            for c in data.get("clips", []):
                f = folder / c["file"]
                if f.exists():
                    items.append({"file": f, "meta": c, "source": data.get("source"),
                                  "game": data.get("game")})
        else:
            items += [{"file": f, "meta": None} for f in sorted(folder.glob("*.mp4"))]
    return items


def clip_time_map(meta):
    """Source time -> clip time, from the clip's segments (joined with hard cuts)."""
    segs = meta.get("segments") or []
    spans, pos = [], 0.0
    for s in segs:
        spans.append((s["start"], s["end"], pos))
        pos += s["end"] - s["start"] + float(s.get("hold", 0))
    def f(t):
        for s0, s1, p in spans:
            if s0 - 0.01 <= t <= s1 + 0.01:
                return p + (t - s0)
        return None
    return f


def actions_from_events(it):
    meta = it.get("meta") or {}
    ev = meta.get("events")
    if not ev:
        return None
    f = clip_time_map(meta)
    acts = [f(e["t"]) for e in ev if e.get("type") in ("kill", "action")]
    deaths = [f(e["t"]) for e in ev if e.get("type") == "death"]
    return [t for t in acts if t is not None], [t for t in deaths if t is not None]


def actions_from_valorant(it, tmp):
    meta, src = it.get("meta") or {}, it.get("source")
    if not (meta.get("segments") and src and Path(src).exists()
            and "valorant" in (it.get("game") or "").lower()):
        return None
    f = clip_time_map(meta)
    acts, deaths = [], []
    for i, s in enumerate(meta["segments"]):
        out = Path(tmp) / f"kf_{id(it)}_{i}.json"
        r = subprocess.run([sys.executable, str(HERE / "valorant_killfeed.py"), src, str(out),
                            "--start", str(max(0, s["start"] - 1)), "--end", str(s["end"] + 0.6)],
                           capture_output=True, text=True)
        if r.returncode or not out.exists():
            return None
        d = json.loads(out.read_text(encoding="utf-8"))
        # Entries already on screen when the scan starts are older kills (e.g. a
        # full-frame end segment still shows the whole round's feed): skip them.
        # A feed entry shows up to 0.5 s after the kill.
        scan0 = max(0, s["start"] - 1) + 0.3
        for key, dst in (("kills", acts), ("deaths", deaths)):
            for k in d[key]:
                if k["t"] <= scan0 and s["start"] > 1:
                    continue
                t = k["t"] - 0.3
                if s["start"] <= t <= s["end"] and all(abs(t - x[1]) > 0.4 for x in dst if x[0] == i):
                    dst.append((i, t))
    acts = [f(t) for _, t in acts]
    deaths = [f(t) for _, t in deaths]
    acts = sorted({round(t, 2) for t in acts if t is not None})
    deaths = sorted({round(t, 2) for t in deaths if t is not None})
    return acts, deaths


def actions_from_audio(path, dur):
    """Loudness peaks: the clip's loudest moments well above its median (shots, kills)."""
    sr = 8000
    y = decode_mono(path, sr)
    w = sr // 20
    n = len(y) // w
    if n < 10:
        return [], []
    db = 20 * np.log10(np.sqrt((y[:n * w].reshape(n, w) ** 2).mean(axis=1)) + 1e-6)
    thr = max(np.median(db) + 12, db.max() - 8)
    peaks = []
    for i in np.argsort(-db):
        if db[i] < thr or len(peaks) >= 4:
            break
        t = i / 20
        if all(abs(t - p) > 1.5 for p in peaks):
            peaks.append(t)
    return sorted(peaks), []


# ---------------------------------------------------------------- planning
def smart_order(items):
    scored = [it for it in items if it.get("meta") and it["meta"].get("score") is not None]
    if len(scored) < len(items) or len(items) < 3:
        return items
    def when(it):
        segs = it["meta"].get("segments") or [{"start": 0}]
        return min(s["start"] for s in segs)
    by_score = sorted(items, key=lambda it: -it["meta"]["score"])
    finale, opener = by_score[0], by_score[1]
    middle = sorted([it for it in items if it is not finale and it is not opener], key=when)
    return [opener] + middle + [finale]


def plan(items, a, grid):
    """In/out points, start times and transitions, cuts snapped to beats."""
    rnd = random.Random(a.seed)
    beats, downs = grid if grid is not None else (np.array([]), np.array([], bool))
    period = float(np.median(np.diff(beats))) if len(beats) > 2 else 0.5
    base_fade = 0.35 if a.style == "clean" else float(np.clip(period / 2, 0.25, 0.5))
    pool = MOTION[:]
    rnd.shuffle(pool)
    n = len(items)
    for it in items:
        acts = it["actions"]
        lo_act = min(acts) if acts else None
        hi_act = max(acts + it["deaths"]) if acts or it["deaths"] else None
        it["in"] = 0.0
        it["out_nat"] = it["dur"]
        if a.trim and lo_act is not None:
            it["in"] = max(0.0, lo_act - a.lead)
            it["out_nat"] = min(it["dur"], hi_act + a.tail)
        it["out_min"] = max(it["in"] + 2.0, (hi_act + 0.6) if hi_act is not None else it["in"] + 2.0)
        it["out_min"] = min(it["out_min"], it["dur"])
    # The finale plays to its own end (its payoff, e.g. a WON banner, is often last);
    # the video's end may only move a little earlier to land on a beat.
    last = items[-1]
    last["out_nat"] = last["dur"]
    last["out_min"] = max(last["out_min"], last["dur"] - 0.6)

    # transitions
    for k in range(1, n):
        prev = items[k - 1]
        died = bool(prev["deaths"]) and max(prev["deaths"]) >= max(prev["actions"] or [0])
        if a.transition:
            tr, fd = a.transition, base_fade
        elif a.style == "clean":
            tr, fd = "fade", base_fade
        elif died:
            tr, fd = "fadeblack", float(np.clip(period, 0.4, 0.7))
        elif k == n - 1 and n > 2:
            tr, fd = "fadewhite", float(np.clip(period * 0.75, 0.3, 0.6))
        else:
            tr, fd = pool[(k - 1) % len(pool)], base_fade
        items[k]["transition"], items[k]["fade"] = tr, fd
    items[0]["transition"], items[0]["fade"] = None, 0.0

    # timeline: clip k starts at S_k; the cut (middle of the transition) is at B_k
    S = 0.0
    for k, it in enumerate(items):
        it["start"] = S
        nxt = items[k + 1] if k + 1 < n else None
        f = nxt["fade"] if nxt else 0.0
        nat_cut = S + (it["out_nat"] - it["in"]) - f / 2
        out = it["out_nat"]
        snapped = None
        if a.sync and len(beats):
            best = None
            for b, d in zip(beats, downs):
                if abs(b - nat_cut) > 1.6:
                    continue
                e = it["in"] + (b + f / 2 - S)
                if not (it["out_min"] <= e <= it["dur"] - 0.02):
                    continue
                cost = abs(b - nat_cut) - (0.5 if d else 0)
                if best is None or cost < best[0]:
                    best = (cost, b, e)
            if best:
                snapped, out = best[1], best[2]
        it["out"] = out
        it["cut_on_beat"] = snapped
        it["length"] = it["out"] - it["in"]
        S = S + it["length"] - f
    total = items[-1]["start"] + items[-1]["length"]
    return total


# ---------------------------------------------------------------- rendering
def build_graph(items, a, music_idx, music_info, total):
    W, H = a.W, a.H
    f = []
    for i, it in enumerate(items):
        norm = f"setsar=1,fps=60,format=yuv420p,settb=AVTB[v{i}]"
        if a.format == "long" or it["h"] > it["w"]:
            # long video: fit into W x H; already-vertical clips (old shorts): fit as is
            f.append(f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
                     f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,{norm}")
        else:
            spans = [(max(0.0, t0 - it["in"]), min(it["length"], t1 - it["in"]), lay)
                     for t0, t1, lay in layout_spans(it) if t1 > it["in"] and t0 < it["in"] + it["length"]]
            if len({lay for _, _, lay in spans}) <= 1:
                f.append(vertical(f"{i}:v", f"l{i}", spans[0][2] if spans else "crop", f"c{i}", W, H))
            else:
                # different framing per segment: split by time, frame each, join back
                n = len(spans)
                f.append(f"[{i}:v]split={n}" + "".join(f"[s{i}_{j}]" for j in range(n)))
                for j, (t0, t1, lay) in enumerate(spans):
                    f.append(f"[s{i}_{j}]trim=start={t0:.3f}:end={t1:.3f},setpts=PTS-STARTPTS[t{i}_{j}]")
                    f.append(vertical(f"t{i}_{j}", f"p{i}_{j}", lay, f"c{i}_{j}", W, H))
                f.append("".join(f"[p{i}_{j}]" for j in range(n)) + f"concat=n={n}:v=1:a=0[l{i}]")
            f.append(f"[l{i}]{norm}")
        if it["has_audio"]:
            f.append(f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                     f"apad,atrim=0:{it['length']:.3f}[a{i}]")
        else:
            f.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{it['length']:.3f}[a{i}]")
    v, au, length = "v0", "a0", items[0]["length"]
    for i in range(1, len(items)):
        it = items[i]
        off = length - it["fade"]
        f.append(f"[{v}][v{i}]xfade=transition={it['transition']}:duration={it['fade']:.3f}:offset={off:.3f}[vx{i}]")
        f.append(f"[{au}][a{i}]acrossfade=d={it['fade']:.3f}:c1=tri:c2=tri[ax{i}]")
        v, au = f"vx{i}", f"ax{i}"
        length = off + it["length"]

    # action moments in output time
    moments = sorted(it["start"] + (t - it["in"]) for it in items for t in it["actions"]
                     if it["in"] <= t <= it["out"])
    vchain = f"[{v}]"
    post = []
    if a.punch and moments and a.style != "clean":
        # zoompan keeps the frame size fixed (a per-frame scale makes later filters reinit)
        terms = "+".join(f"0.09*exp(-9*(it-{m:.3f}))*between(it,{m:.3f},{m + 0.6:.3f})" for m in moments)
        post.append(f"zoompan=z='1+{terms}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={W}x{H}:fps=60")
    if a.flash and moments and a.style != "clean":
        en1 = "+".join(f"between(t,{m:.3f},{m + 0.05:.3f})" for m in moments)
        en2 = "+".join(f"between(t,{m + 0.05:.3f},{m + 0.13:.3f})" for m in moments)
        post.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=white@0.35:t=fill:enable='{en1}'")
        post.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=white@0.15:t=fill:enable='{en2}'")
    post.append(f"fade=t=in:st=0:d=0.4,fade=t=out:st={max(0, total - 1.0):.3f}:d=1.0,format=yuv420p")
    f.append(vchain + ",".join(post) + "[vout]")

    f.append(f"[{au}]volume={a.game_volume}[game]")
    if music_idx is None:
        f.append(f"[game]afade=t=in:d=0.3,afade=t=out:st={max(0, total - 1.0):.3f}:d=1.0,"
                 f"loudnorm=I={a.lufs}:TP=-1.5:LRA=11,aresample=48000[aout]")
    else:
        ms = music_info["start"]
        loop_samples = int((music_info["length"] - ms) * 48000)
        f.append(f"[{music_idx}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                 f"atrim=start={ms:.3f},asetpts=N/SR/TB,aloop=loop=-1:size={loop_samples},"
                 f"atrim=0:{total:.3f},asetpts=N/SR/TB,volume={a.music_volume}dB,"
                 f"afade=t=in:d=0.5,afade=t=out:st={max(0, total - 2.0):.3f}:d=2.0[mus]")
        if a.duck and a.game_volume > 0:
            f.append("[game]asplit[g1][g2]")
            f.append("[mus][g2]sidechaincompress=threshold=0.035:ratio=6:attack=10:release=300:makeup=1[mduck]")
            f.append("[g1][mduck]amix=inputs=2:normalize=0:duration=longest[mix]")
        else:
            f.append("[game][mus]amix=inputs=2:normalize=0:duration=longest[mix]")
        f.append(f"[mix]atrim=0:{total:.3f},loudnorm=I={a.lufs}:TP=-1.5:LRA=11,aresample=48000[aout]")
    return ";".join(f), moments


def free_name(out):
    out, n = Path(out), 2
    cand = out
    while cand.exists() or cand.with_suffix(".json").exists():
        cand = out.with_name(f"{out.stem} ({n}){out.suffix}")
        n += 1
    return cand


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("clips", nargs="*")
    ap.add_argument("--folder")
    ap.add_argument("--order", choices=["smart", "time", "score", "given"])
    ap.add_argument("--music")
    ap.add_argument("--music-start", type=float)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--format", choices=["short", "long"], default="short")
    ap.add_argument("--size", help="long format output size (default 1920x1080, 2560x1440 with --hq)")
    ap.add_argument("--hq", action="store_true",
                    help="1440p output (Shorts 1440x2560, long 2560x1440): YouTube gives 1440p+ "
                         "uploads a higher-quality encode")
    ap.add_argument("--style", choices=["punchy", "clean"], default="punchy")
    ap.add_argument("--transition")
    ap.add_argument("--no-trim", dest="trim", action="store_false")
    ap.add_argument("--no-sync", dest="sync", action="store_false")
    ap.add_argument("--no-punch", dest="punch", action="store_false")
    ap.add_argument("--no-flash", dest="flash", action="store_false")
    ap.add_argument("--no-duck", dest="duck", action="store_false")
    ap.add_argument("--lead", type=float, default=3.0)
    ap.add_argument("--tail", type=float, default=1.8)
    ap.add_argument("--max-length", type=float)
    ap.add_argument("--music-volume", type=float, default=-12.0)
    ap.add_argument("--game-volume", type=float, default=1.0)
    ap.add_argument("--lufs", type=float, default=-14.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--plan-json", help="with --dry-run: also write the edit plan as JSON to this file")
    a = ap.parse_args()

    if a.format == "short":
        a.W, a.H = (1440, 2560) if a.hq else (1080, 1920)
        if a.max_length is None:
            a.max_length = SHORTS_MAX
    else:
        a.W, a.H = (int(x) for x in (a.size or ("2560x1440" if a.hq else "1920x1080")).lower().split("x"))
    # 12 Mb/s at 1080p, scaled with the pixel count (about 21 Mb/s at 1440p)
    a.mbps = max(12, round(12 * a.W * a.H / (1920 * 1080)))
    items = load_items(a)
    if len(items) < 2:
        sys.exit("need at least 2 clips")
    tmp = tempfile.mkdtemp(prefix="merge_")
    for it in items:
        if not it["file"].exists():
            sys.exit(f"missing clip: {it['file']}")
        it["dur"], it["has_audio"], it["w"], it["h"] = probe(it["file"], size=True)
        found, how = None, None
        for fn, name in ((lambda: actions_from_events(it), "events"),
                         (lambda: actions_from_valorant(it, tmp), "valorant kill feed"),
                         (lambda: actions_from_audio(it["file"], it["dur"]) if it["has_audio"] else ([], []),
                          "loudness peaks")):
            found = fn()
            if found is not None and (found[0] or found[1] or name == "loudness peaks"):
                how = name
                break
        it["actions"], it["deaths"], it["actions_from"] = found[0], found[1], how
        print(f"  {it['file'].name}: {len(it['actions'])} actions, {len(it['deaths'])} deaths ({how})")

    order = a.order or ("smart" if all(it.get("meta") and it["meta"].get("score") is not None
                                       for it in items) else "given")
    if order == "smart":
        items = smart_order(items)
    elif order == "score":
        items.sort(key=lambda it: -(it.get("meta") or {}).get("score", 0))
    elif order == "time":
        items.sort(key=lambda it: min(s["start"] for s in (it.get("meta") or {}).get("segments", [{"start": 0}])))

    music = None
    if a.music:
        p = Path(a.music)
        tracks = [p] if p.is_file() else sorted(x for x in p.rglob("*") if x.suffix.lower() in MUSIC_EXT)
        if not tracks:
            sys.exit(f"no music in {p}")
        music = random.Random(a.seed).choice(tracks)
    minfo = analyse_music(music) if music else None
    if minfo and a.music_start is not None:
        minfo["start"] = a.music_start
    if minfo:
        print(f"  music: {music.name}  {minfo['bpm']:.1f} BPM, starts at {minfo['start']:.2f}s")

    while True:
        rough = sum(it["dur"] for it in items) + 10
        grid = beat_grid(minfo, minfo["start"], rough) if (minfo and a.sync) else None
        total = plan(items, a, grid)
        if not a.max_length or total <= a.max_length or len(items) <= 2:
            break
        drop = min((it for it in items[1:-1]) if len(items) > 2 else items,
                   key=lambda it: (it.get("meta") or {}).get("score", 0))
        print(f"  over {a.max_length:.0f}s ({total:.1f}s): dropping {drop['file'].name}")
        items.remove(drop)

    print(f"\nplan ({total:.1f}s):")
    for it in items:
        tr = f"{it['transition']} {it['fade']:.2f}s" if it["transition"] else "fade in"
        beat = f" cut on beat {it['cut_on_beat']:.2f}" if it.get("cut_on_beat") is not None else ""
        print(f"  {it['start']:6.2f}s  [{tr}]  {it['file'].name}  in {it['in']:.2f} out {it['out']:.2f}{beat}")
    if a.dry_run:
        if a.plan_json:
            Path(a.plan_json).write_text(json.dumps({
                "length": round(total, 2), "order": order, "music": str(music) if music else None,
                "bpm": round(minfo["bpm"], 1) if minfo else None,
                "clips": [{"file": str(it["file"]), "starts_at": round(it["start"], 2), "in": round(it["in"], 2),
                           "out": round(it["out"], 2), "transition_in": it["transition"],
                           "actions_from": it["actions_from"]} for it in items]},
                indent=1, ensure_ascii=False), encoding="utf-8")
        return

    cmd = [FFMPEG, "-v", "error", "-y"]
    for it in items:
        cmd += ["-ss", f"{it['in']:.3f}", "-t", f"{it['length']:.3f}", "-i", str(it["file"])]
    midx = None
    if music:
        midx = len(items)
        cmd += ["-i", str(music)]
    fc, moments = build_graph(items, a, midx, minfo, total)
    out = free_name(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fcfile = Path(tmp) / "graph.txt"
    fcfile.write_text(fc, encoding="utf-8")
    # "-/filter_complex <file>" reads the graph from a file (ffmpeg 7+; graphs get long)
    cmd += ["-/filter_complex", str(fcfile), "-map", "[vout]", "-map", "[aout]",
            "-t", f"{total:.3f}", "-c:v", "h264_amf", "-quality", "quality", "-b:v", f"{a.mbps}M",
            "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-movflags", "+faststart", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"ffmpeg failed:\n{r.stderr[-3000:]}")

    actual, _ = probe(out)
    side = {"out": str(out), "length": round(actual, 2), "style": a.style, "order": order,
            "music": str(music) if music else None,
            "bpm": round(minfo["bpm"], 1) if minfo else None,
            "music_start": round(minfo["start"], 2) if minfo else None,
            "action_moments": [round(m, 2) for m in moments],
            "clips": [{"file": str(it["file"]), "starts_at": round(it["start"], 2),
                       "in": round(it["in"], 2), "out": round(it["out"], 2),
                       "transition_in": it["transition"], "fade": round(it["fade"], 2),
                       "cut_on_beat": it.get("cut_on_beat") is not None,
                       "actions": [round(t, 2) for t in it["actions"]], "actions_from": it["actions_from"],
                       "score": (it.get("meta") or {}).get("score")} for it in items]}
    out.with_suffix(".json").write_text(json.dumps(side, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nmerged {len(items)} clips -> {out}  planned {total:.1f}s, actual {actual:.1f}s")
    if a.format == "short" and actual > SHORTS_MAX:
        print(f"note: {actual:.0f}s is over the {SHORTS_MAX:.0f}s Shorts limit (use --max-length 180)")


if __name__ == "__main__":
    main()
