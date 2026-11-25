"""YouTube thumbnail for a merged video, built from real frames of the clips it uses.

  python make_thumbnail.py candidates <merged.mp4> <workdir>
      Grabs frames just before each kill/action in the source clips (the shot; no kill banner or skull yet),
      scores them (sharpness, exposure, colour), keeps the best 12 and writes
      <workdir>/candidates.json and <workdir>/sheet.jpg (numbered contact sheet for review).

  python make_thumbnail.py render <workdir> --pick N [--headline TEXT] [--badge TEXT]
                                  [--layout hero|badge] --out <file.jpg>
      Renders a 1280x720 JPEG (under 2 MB, YouTube's limit) from candidate N.
        clean  one frame, HUD cropped away, punchy colour, glow, zoom blur (no text)
        mirror the weapon side mirrored onto the left: a dual-wield look (no text)
        hero   one graded frame and a big outlined headline
        badge  the same frame with a large kill badge ("QUADRA KILL") and a smaller headline

Inputs are only read. Needs Pillow and numpy.
"""
import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    from merge_highlights import FFMPEG
except Exception:  # pragma: no cover
    FFMPEG = "ffmpeg"

W, H = 1280, 720
FONT_DIR = Path(r"C:\Windows\Fonts")
HEAD_FONT = next((FONT_DIR / f for f in ("impact.ttf", "seguibl.ttf", "arialbd.ttf") if (FONT_DIR / f).exists()), None)
ACCENT = {"valorant": (255, 70, 85), "counter-strike 2": (255, 166, 0), "arena breakout infinite": (255, 204, 0)}
KILL_WORDS = {2: "DOUBLE KILL", 3: "TRIPLE KILL", 4: "QUADRA KILL", 5: "ACE"}
NO_WINDOW = 0x08000000


def accent_for(game):
    return ACCENT.get((game or "").lower(), (80, 200, 255))


# ---------------------------------------------------------------- candidates
def grab(src, t, out):
    subprocess.run([FFMPEG, "-v", "error", "-y", "-ss", f"{max(0, t):.3f}", "-i", str(src), "-frames:v", "1",
                    "-q:v", "2", str(out)], capture_output=True, creationflags=NO_WINDOW if sys.platform == "win32" else 0)
    return out.exists()


def score(img):
    g = np.asarray(img.convert("L").resize((480, 270)), dtype=np.float32)
    lap = g[1:-1, 1:-1] * 4 - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
    sharp = min(1.0, float(lap.var()) / 900.0)
    mean = float(g.mean()) / 255
    expo = 1.0 - min(1.0, abs(mean - 0.45) / 0.35)          # neither black nor blown out
    hsv = np.asarray(img.convert("HSV").resize((240, 135)), dtype=np.float32)
    colour = min(1.0, float(hsv[..., 1].mean()) / 140.0)
    dark = float((g < 25).mean())                            # death screens / menus are mostly dark
    return round(0.5 * sharp + 0.3 * expo + 0.2 * colour - 0.5 * max(0, dark - 0.4), 4)


def clip_game(path):
    parts = Path(path).parts
    try:
        return parts[[p.lower() for p in parts].index("highlights") + 1]
    except ValueError:
        return Path(path).parent.parent.name


def clip_title(path):
    m = re.match(r"\d+\s*-\s*(.*?)(\s*\(\d+m\d+s\))?$", Path(path).stem)
    return m.group(1) if m else Path(path).stem


def candidates(merged, work):
    work.mkdir(parents=True, exist_ok=True)
    plan = json.loads(Path(merged).with_suffix(".json").read_text(encoding="utf-8"))
    jobs = []
    for ci, c in enumerate(plan.get("clips", [])):
        src = Path(c["file"])
        if not src.exists():
            continue
        acts = [t for t in c.get("actions", []) if c["in"] <= t <= c["out"]]
        times = [(t + d, k) for k, t in enumerate(acts) for d in (-0.45, -0.25, -0.08)] or \
                [(c["in"] + (c["out"] - c["in"]) * f, None) for f in (0.3, 0.5, 0.7)]
        jobs += [(ci, src, t, k, len(acts)) for t, k in times]

    def one(job):
        ci, src, t, k, n = job
        f = work / f"c{ci:02d}_{t:08.2f}.jpg"
        if not grab(src, t, f):
            return None
        with Image.open(f) as im:
            sc = score(im)
        return {"file": str(f), "clip": str(src), "clip_index": ci, "time": round(t, 2), "action": k,
                "score": sc, "kills_in_clip": n, "title": clip_title(src), "game": clip_game(src)}

    with ThreadPoolExecutor(6) as ex:  # frame grabs from AV1 sources are slow one by one
        cands = [c for c in ex.map(one, jobs) if c]
    # best frame per action first, then fill up to 12
    best = {}
    for c in sorted(cands, key=lambda x: -x["score"]):
        best.setdefault((c["clip_index"], c["action"]), c)
    picks = sorted(best.values(), key=lambda x: -x["score"])[:12]
    if len(picks) < 12:
        picks += [c for c in sorted(cands, key=lambda x: -x["score"]) if c not in picks][:12 - len(picks)]
    for i, c in enumerate(picks, 1):
        c["n"] = i
    sheet(picks, work / "sheet.jpg")
    total = sum(len([t for t in c.get("actions", []) if c["in"] <= t <= c["out"]]) for c in plan.get("clips", []))
    info = {"merged": str(merged), "game": picks[0]["game"] if picks else "", "total_kills": total,
            "titles": [clip_title(c["file"]) for c in plan.get("clips", [])], "candidates": picks}
    (work / "candidates.json").write_text(json.dumps(info, indent=1, ensure_ascii=False), encoding="utf-8")
    return info


def font(size):
    return ImageFont.truetype(str(HEAD_FONT), size) if HEAD_FONT else ImageFont.load_default(size)


def sheet(picks, out):
    tw, th, cols = 480, 270, 4
    rows = max(1, (len(picks) + cols - 1) // cols)
    sh = Image.new("RGB", (cols * tw, rows * th), (20, 20, 20))
    d = ImageDraw.Draw(sh)
    for i, c in enumerate(picks):
        with Image.open(c["file"]) as im:
            sh.paste(ImageOps.fit(im.convert("RGB"), (tw, th)), ((i % cols) * tw, (i // cols) * th))
        x, y = (i % cols) * tw, (i // cols) * th
        d.rectangle([x, y, x + 64, y + 52], fill=(0, 0, 0))
        d.text((x + 10, y + 4), str(c["n"]), font=font(42), fill=(255, 255, 0))
    sh.save(out, quality=85)


# ---------------------------------------------------------------- render
def grade(img):
    img = ImageEnhance.Contrast(img).enhance(1.18)
    img = ImageEnhance.Color(img).enhance(1.3)
    img = ImageEnhance.Sharpness(img).enhance(1.3)
    # vignette: darken the edges so text and the centre pop
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).ellipse([-W * 0.15, -H * 0.25, W * 1.15, H * 1.25], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(120))
    dark = ImageEnhance.Brightness(img).enhance(0.45)
    return Image.composite(img, dark, mask)


def fit_text(d, text, max_w, start, min_size=40):
    size = start
    while size > min_size:
        f = font(size)
        if d.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return font(min_size)


def outlined(d, xy, text, f, fill, stroke=(0, 0, 0), sw=None, anchor="ls"):
    sw = sw or max(4, f.size // 14)
    # soft drop shadow, then the outlined text
    d.text((xy[0] + sw, xy[1] + sw), text, font=f, fill=(0, 0, 0), stroke_width=sw, stroke_fill=(0, 0, 0), anchor=anchor)
    d.text(xy, text, font=f, fill=fill, stroke_width=sw, stroke_fill=stroke, anchor=anchor)


def headline_block(base, text, acc, max_w, start, bottom):
    """Up to two lines, bottom-left. Words written as *WORD* get the game's accent colour
    (default: the last word)."""
    d = ImageDraw.Draw(base)
    raw = (text or "").upper().split()
    if not raw:
        return
    words = [w.strip("*") for w in raw]
    hot = {i for i, w in enumerate(raw) if w.startswith("*") or w.endswith("*")} or {len(raw) - 1}
    idx = list(range(len(words)))
    lines = [idx]
    if d.textlength(" ".join(words), font=font(start)) > max_w and len(words) > 1:
        cut = max(1, len(words) // 2)
        lines = [idx[:cut], idx[cut:]]
    f = min((fit_text(d, " ".join(words[i] for i in ln), max_w, start) for ln in lines), key=lambda x: x.size)
    y = bottom - (len(lines) - 1) * int(f.size * 0.95)
    space = d.textlength(" ", font=f)
    for ln in lines:
        x = 48
        for i in ln:
            outlined(d, (x, y), words[i], f, acc if i in hot else (255, 255, 255))
            x += d.textlength(words[i], font=f) + space
        y += int(f.size * 0.95)


def badge(base, text, acc):
    d0 = ImageDraw.Draw(base)
    f = fit_text(d0, text.upper(), 520, 120, 50)
    tw = int(d0.textlength(text.upper(), font=f))
    pad = 34
    b = Image.new("RGBA", (tw + pad * 2, f.size + pad * 2), (0, 0, 0, 0))
    bd = ImageDraw.Draw(b)
    bd.rounded_rectangle([0, 0, b.width - 1, b.height - 1], radius=22, fill=acc + (255,), outline=(255, 255, 255, 255), width=6)
    bd.text((b.width // 2, b.height // 2 + 4), text.upper(), font=f, fill=(255, 255, 255), anchor="mm",
            stroke_width=max(3, f.size // 18), stroke_fill=(0, 0, 0))
    b = b.rotate(-5, expand=True, resample=Image.BICUBIC)
    shadow = Image.new("RGBA", b.size, (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 160), mask=b.split()[3])
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    x, y = 28, 24  # top left, over the minimap: the kill feed (top right) stays visible
    base.alpha_composite(shadow, (x + 8, y + 12))
    base.alpha_composite(b, (x, y))


# ---------------------------------------------------------------- text-free styles
# HUD-free crop boxes (fractions of the source frame). FPS HUDs sit at the edges: minimap top-left,
# kill feed top-right, health/abilities bottom-centre, ammo bottom-right. The weapon is lower right.
CLEAN_BOX = (0.23, 0.15, 0.95, 0.87)      # 72% of the frame, right (weapon), below the banner, above notices
MIRROR_BOX = (0.50, 0.16, 0.85, 0.86)     # right half of a 70% crop, below the top banner: mirrored


def stylise(img, strength=1.0):
    """Punchy colour, bloom on the highlights, zoom blur towards the edges (centre stays sharp)."""
    img = ImageEnhance.Color(img).enhance(1.0 + 0.45 * strength)
    img = ImageEnhance.Contrast(img).enhance(1.0 + 0.14 * strength)
    img = ImageEnhance.Sharpness(img).enhance(1.4)
    # bloom: blurred bright parts, screen-blended back
    bright = img.point(lambda v: max(0, v - 150) * 2.4).filter(ImageFilter.GaussianBlur(22))
    a, b = np.asarray(img, dtype=np.float32), np.asarray(bright, dtype=np.float32)
    img = Image.fromarray(np.clip(255 - (255 - a) * (255 - b * 0.55 * strength) / 255, 0, 255).astype(np.uint8))
    # zoom blur: average of slightly scaled copies, masked so only the edges smear (speed feel)
    acc_ = np.zeros((H, W, 3), dtype=np.float32)
    steps = 8
    for i in range(steps):
        s = 1.0 + 0.075 * i / (steps - 1)
        z = img.resize((int(W * s), int(H * s)), Image.BILINEAR)
        x0, y0 = (z.width - W) // 2, (z.height - H) // 2
        acc_ += np.asarray(z.crop((x0, y0, x0 + W, y0 + H)), dtype=np.float32)
    zoom = Image.fromarray((acc_ / steps).astype(np.uint8))
    mask = Image.new("L", (W, H), 255)
    ImageDraw.Draw(mask).ellipse([W * 0.14, H * 0.10, W * 0.86, H * 0.98], fill=0)
    mask = mask.filter(ImageFilter.GaussianBlur(110))
    img = Image.composite(zoom, img, mask)
    # soft vignette
    v = Image.new("L", (W, H), 0)
    ImageDraw.Draw(v).ellipse([-W * 0.2, -H * 0.3, W * 1.2, H * 1.3], fill=255)
    v = v.filter(ImageFilter.GaussianBlur(140))
    return Image.composite(img, ImageEnhance.Brightness(img).enhance(0.6), v)


def crop_box(frame, box):
    fw, fh = frame.size
    return frame.crop((int(box[0] * fw), int(box[1] * fh), int(box[2] * fw), int(box[3] * fh)))


def styled(frame, layout):
    if layout == "mirror":
        half = crop_box(frame, MIRROR_BOX).resize((W // 2, H), Image.LANCZOS)
        img = Image.new("RGB", (W, H))
        img.paste(ImageOps.mirror(half), (0, 0))
        img.paste(half, (W // 2, 0))  # the seam is the frame's own centre line, so it is continuous
        return stylise(img)
    return stylise(crop_box(frame, CLEAN_BOX).resize((W, H), Image.LANCZOS))


def render(work, pick, headline, badge_text, layout, out):
    info = json.loads((work / "candidates.json").read_text(encoding="utf-8"))
    c = next((x for x in info["candidates"] if x["n"] == pick), info["candidates"][0])
    acc = accent_for(c["game"])
    with Image.open(c["file"]) as im:
        frame = im.convert("RGB")
    if layout in ("clean", "mirror"):
        return save_jpg(styled(frame, layout), out)
    # slight zoom on the centre (the crosshair is where the action is)
    frame = ImageOps.fit(frame, (int(W * 1.08), int(H * 1.08)), centering=(0.5, 0.48)).crop(
        (int(W * 0.04), int(H * 0.04), int(W * 0.04) + W, int(H * 0.04) + H))
    base = grade(frame).convert("RGBA")
    # bottom gradient for the headline
    grad = Image.new("L", (1, H), 0)
    for y in range(H):
        grad.putpixel((0, y), int(max(0, (y - H * 0.45) / (H * 0.55)) ** 1.6 * 210))
    black = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    base = Image.composite(black, base, grad.resize((W, H)))
    if layout == "badge" and badge_text:
        badge(base, badge_text, acc)
        headline_block(base, headline, acc, W - 96, 110, H - 48)
    else:
        headline_block(base, headline, acc, W - 96, 170, H - 52)
    return save_jpg(base.convert("RGB"), out)


def save_jpg(img, out):
    out = Path(out)
    for q in (92, 85, 75, 65):  # YouTube's limit is 2 MB
        img.save(out, quality=q, optimize=True)
        if out.stat().st_size < 1_900_000:
            break
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("candidates")
    a.add_argument("merged")
    a.add_argument("work")
    r = sub.add_parser("render")
    r.add_argument("work")
    r.add_argument("--pick", type=int, default=1)
    r.add_argument("--headline", default="")
    r.add_argument("--badge", default="")
    r.add_argument("--layout", choices=["clean", "mirror", "hero", "badge"], default="clean")
    r.add_argument("--out", required=True)
    args = ap.parse_args()
    if args.cmd == "candidates":
        info = candidates(Path(args.merged), Path(args.work))
        print(f"{len(info['candidates'])} candidates, sheet: {Path(args.work) / 'sheet.jpg'}")
    else:
        print(render(Path(args.work), args.pick, args.headline, args.badge, args.layout, args.out))


if __name__ == "__main__":
    main()
