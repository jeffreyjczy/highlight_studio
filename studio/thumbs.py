"""Thumbnails for merged videos: frames from make_thumbnail.py, chosen by Claude.

Text-free, stylised thumbnails (HUD cropped away, punchy colour, glow, zoom blur), plus a
creative YouTube title idea. Files next to the merged video <name>.mp4:
  <name>.thumb.jpg          the thumbnail that is used (card, YouTube upload)
  <name>.thumb-clean.jpg    style: one frame, cleaned up
  <name>.thumb-mirror.jpg   style: the weapon side mirrored (dual-wield look)
  <name>.thumb.json         {pick, layout, title, why, by}
The frame candidates live in %LOCALAPPDATA%\\HighlightStudio\\thumbs-work\\<name>.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from common import CLAUDE, DATA, NO_WINDOW, PIPE

WORK = DATA / "thumbs-work"
# make_thumbnail.py needs Pillow, which is installed in the app's .venv (not the system Python)
PYTHON = str(Path(sys.executable).with_name("python.exe"))
LAYOUTS = ("clean", "mirror")

PROMPT = """You are making a YouTube thumbnail and title for a gaming highlight video.

Read the image sheet.jpg in the current folder. It shows {n} numbered candidate frames (yellow number,
top-left of each tile). candidates.json has each frame's clip title and kill count.

Video: {game}, {length} long, {kills} kills in total, {clips} clips. Clip titles: {titles}

The thumbnail has NO text. The app crops the HUD away (minimap, kill feed, health, ammo), boosts the
colour, adds glow and a zoom blur at the edges, like popular "satisfying clips" channels. Two styles:
- "clean": the frame itself, cropped to the middle-right (keeps the weapon).
- "mirror": the right half of the frame mirrored onto the left, so the weapon appears on both sides
  (a dual-wield look). Only good when the weapon is big on the lower right and the middle of the frame
  is open (a corridor or a doorway), not when an enemy or a wall sits in the middle.

Pick the frame that looks most striking WITHOUT any text: a colourful weapon skin big in view, an enemy
clearly visible or a kill effect, bright, sharp, good depth, nothing blocking the view (no menus,
scoreboard, death screen or smoke wall). Avoid frames with HUD icons in the middle area that the crop
would keep, such as a big skull kill icon or a "SPIKE CARRIER KILLED" banner. Then choose the style that
suits it best.

Also write a creative YouTube title (at most 70 characters) in the style of big gaming channels:
curiosity, mood or a promise, not a plain description. Honest to the video, no emoji, no hashtags,
never match or round numbers. Only name a weapon, skin, agent or map if you are sure from the frames. Examples: "{mins} Minutes of Satisfying {game} Clips",
"This Vandal Should Be Illegal", "When Every Shot Just Lands", "My Aim Was Possessed Tonight",
"The Cleanest Ace I've Ever Hit".

Do not change any files. Reply with only this JSON, nothing else:
{{"pick": <number>, "layout": "clean" or "mirror", "title": "<title>", "why": "<one short sentence>"}}"""


def paths(merged):
    m = Path(merged)
    return {"use": m.with_suffix(".thumb.jpg"), "clean": m.with_suffix(".thumb-clean.jpg"),
            "mirror": m.with_suffix(".thumb-mirror.jpg"), "meta": m.with_suffix(".thumb.json"),
            "work": WORK / m.stem}


def files(merged):
    """Every thumbnail file of a merged video (for deleting it together with the video)."""
    p = paths(merged)
    old = [Path(merged).with_suffix(e) for e in (".thumb-hero.jpg", ".thumb-badge.jpg")]
    return [p["use"], p["clean"], p["mirror"], p["meta"]] + old


def _env():
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    return env


def _length(merged):
    try:
        return float(json.loads(Path(merged).with_suffix(".json").read_text(encoding="utf-8")).get("length") or 0)
    except (OSError, ValueError):
        return 0.0


def candidates(merged, log):
    p = paths(merged)
    if p["work"].exists():
        shutil.rmtree(p["work"], ignore_errors=True)
    r = subprocess.run([PYTHON, str(PIPE / "make_thumbnail.py"), "candidates", str(merged), str(p["work"])],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    log(r.stdout + r.stderr)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout).strip()[-400:] or "couldn't grab frames")
    info = json.loads((p["work"] / "candidates.json").read_text(encoding="utf-8"))
    info["length"] = _length(merged)
    return info


def _mins(sec):
    return max(1, round(sec / 60))


def fallback(info):
    """No Claude: best-scored frame, clean style, a stock title."""
    game = info.get("game") or "Gameplay"
    length = info.get("length") or 0
    title = f"{_mins(length)} Minutes of Satisfying {game} Clips" if length >= 90 else f"Satisfying {game} Moments"
    return {"pick": info["candidates"][0]["n"], "layout": "clean", "title": title,
            "why": "Highest-scored frame (no Claude)", "by": "script"}


def ask_claude(info, work, log, proc_cb=None):
    length = info.get("length") or 0
    prompt = PROMPT.format(n=len(info["candidates"]), game=info["game"] or "Gameplay", kills=info["total_kills"],
                           clips=len(info["titles"]), titles="; ".join(info["titles"])[:600],
                           length=f"{int(length // 60)}:{int(length % 60):02d}", mins=_mins(length))
    cmd = [CLAUDE, "-p", "--model", "sonnet", "--allowedTools", "Read", "--output-format", "json"]
    p = subprocess.Popen(cmd, cwd=str(work), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         env=_env(), creationflags=NO_WINDOW, text=True, encoding="utf-8", errors="replace")
    if proc_cb:
        proc_cb(p)
    out, err = p.communicate(prompt, timeout=300)
    log(out[-4000:] + err[-1000:])
    if p.returncode:
        raise RuntimeError("Claude didn't answer")
    res = json.loads(out).get("result", "")
    m = re.search(r"\{.*\}", res, re.S)
    if not m:
        raise RuntimeError("Claude's answer had no JSON")
    pick = json.loads(m.group(0))
    if pick.get("pick") not in {c["n"] for c in info["candidates"]}:
        raise RuntimeError(f"Claude picked a frame that doesn't exist ({pick.get('pick')})")
    pick["layout"] = pick.get("layout") if pick.get("layout") in LAYOUTS else "clean"
    pick["title"] = re.sub(r"[<>#]", "", str(pick.get("title", "")))[:100].strip()
    pick["by"] = "claude"
    return pick


def render(merged, choice, log=lambda s: None):
    """Render both styles from the saved candidates and make the chosen one the thumbnail."""
    p = paths(merged)
    for layout in LAYOUTS:
        r = subprocess.run([PYTHON, str(PIPE / "make_thumbnail.py"), "render", str(p["work"]),
                            "--pick", str(choice["pick"]), "--layout", layout, "--out", str(p[layout])],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
        log(r.stdout + r.stderr)
        if r.returncode:
            raise RuntimeError((r.stderr or r.stdout).strip()[-400:])
    if choice.get("layout") not in LAYOUTS:
        choice["layout"] = "clean"
    shutil.copyfile(p[choice["layout"]], p["use"])
    p["meta"].write_text(json.dumps(choice, indent=1, ensure_ascii=False), encoding="utf-8")
    return choice


def choose_layout(merged, layout):
    p = paths(merged)
    meta = json.loads(p["meta"].read_text(encoding="utf-8"))
    if layout not in LAYOUTS or not p[layout].exists():
        raise ValueError("unknown style")
    shutil.copyfile(p[layout], p["use"])
    meta["layout"] = layout
    p["meta"].write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    return meta


def set_title(merged, title):
    p = paths(merged)
    meta = json.loads(p["meta"].read_text(encoding="utf-8"))
    meta["title"] = re.sub(r"[<>]", "", title or "")[:100].strip()
    p["meta"].write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")


def info(merged):
    p = paths(merged)
    if not p["meta"].exists() or not p["use"].exists():
        return None
    try:
        meta = json.loads(p["meta"].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if meta.get("layout") not in LAYOUTS or not p[meta["layout"]].exists():
        meta["old"] = True  # made by the earlier text styles: offer to make a new one
    meta["can_edit"] = (p["work"] / "candidates.json").exists()
    return meta
