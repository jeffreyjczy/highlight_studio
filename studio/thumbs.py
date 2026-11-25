"""Thumbnails for merged videos: frames from make_thumbnail.py, chosen by Claude.

Files next to the merged video <name>.mp4:
  <name>.thumb.jpg         the thumbnail that is used (card, YouTube upload)
  <name>.thumb-hero.jpg    layout: hero frame + headline
  <name>.thumb-badge.jpg   layout: hero frame + kill badge
  <name>.thumb.json        {pick, headline, badge, layout, why, by}
The frame candidates live in %LOCALAPPDATA%\\HighlightStudio\\thumbs-work\\<name>.
"""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import sys

from common import CLAUDE, DATA, NO_WINDOW, PIPE

WORK = DATA / "thumbs-work"
# make_thumbnail.py needs Pillow, which is installed in the app's .venv (not the system Python)
PYTHON = str(Path(sys.executable).with_name("python.exe"))
KILL_WORDS = {2: "DOUBLE KILL", 3: "TRIPLE KILL", 4: "QUADRA KILL", 5: "ACE"}

PROMPT = """You are choosing a YouTube thumbnail for a gaming highlight video.

Read the image sheet.jpg in the current folder. It shows {n} numbered candidate frames (yellow number,
top-left of each tile). Details of each candidate are in candidates.json: the clip title, how many kills
that clip has, the game.

Video: {game} highlights, {kills} kills in total. Clip titles: {titles}

Pick the frame that makes the most exciting thumbnail: an enemy or a kill clearly visible (kill feed
showing "Me", a muzzle flash, an enemy in the crosshair), sharp, bright, not blocked by a menu, map,
scoreboard or death screen. Then write:
- headline: 2 to 4 punchy words, at most 22 characters, no emoji, no hashtags, no clickbait lies.
  Use what really happens and what a viewer understands: the feat plus the map, agent or weapon if you
  can see it (e.g. "*ACE* ON BIND", "*QUADRA* KILL ON ASCENT", "1V3 *CLUTCH*", "*ACE* WITH A SHERIFF").
  Never use match or round numbers ("MATCH 2" means nothing to a viewer). Wrap the one most important
  word in *asterisks*; it is drawn in the game's colour.
- badge: the biggest feat in at most 12 characters, e.g. "ACE", "QUADRA KILL", "1V3", "{kills} KILLS".

Do not change any files. Reply with only this JSON, nothing else:
{{"pick": <number>, "headline": "<text>", "badge": "<text>", "why": "<one short sentence>"}}"""


def paths(merged):
    m = Path(merged)
    return {"use": m.with_suffix(".thumb.jpg"), "hero": m.with_suffix(".thumb-hero.jpg"),
            "badge": m.with_suffix(".thumb-badge.jpg"), "meta": m.with_suffix(".thumb.json"),
            "work": WORK / m.stem}


def _env():
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    return env


def candidates(merged, log):
    p = paths(merged)
    if p["work"].exists():
        shutil.rmtree(p["work"], ignore_errors=True)
    r = subprocess.run([PYTHON, str(PIPE / "make_thumbnail.py"), "candidates", str(merged), str(p["work"])],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    log(r.stdout + r.stderr)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout).strip()[-400:] or "couldn't grab frames")
    return json.loads((p["work"] / "candidates.json").read_text(encoding="utf-8"))


def fallback(info):
    """No Claude: best-scored frame, headline from the best clip's title."""
    best = info["candidates"][0]
    top = max(info["candidates"], key=lambda c: c["kills_in_clip"])
    badge = KILL_WORDS.get(min(top["kills_in_clip"], 5)) or (f"{info['total_kills']} KILLS" if info["total_kills"] else "")
    head = re.sub(r"\s*\(.*?\)", "", top["title"]).upper()[:22] or f"{info['game']} HIGHLIGHTS".upper()
    return {"pick": best["n"], "headline": head, "badge": badge, "why": "Highest-scored frame (no Claude)", "by": "script"}


def ask_claude(info, work, log, proc_cb=None):
    prompt = PROMPT.format(n=len(info["candidates"]), game=info["game"] or "Gameplay", kills=info["total_kills"],
                           titles="; ".join(info["titles"])[:600])
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
    ns = {c["n"] for c in info["candidates"]}
    if pick.get("pick") not in ns:
        raise RuntimeError(f"Claude picked a frame that doesn't exist ({pick.get('pick')})")
    pick["headline"] = str(pick.get("headline", ""))[:28]
    pick["badge"] = str(pick.get("badge", ""))[:14]
    pick["by"] = "claude"
    return pick


def render(merged, choice, log=lambda s: None):
    """Render both layouts from the saved candidates and make the chosen layout the thumbnail."""
    p = paths(merged)
    for layout in ("hero", "badge"):
        r = subprocess.run([PYTHON, str(PIPE / "make_thumbnail.py"), "render", str(p["work"]),
                            "--pick", str(choice["pick"]), "--headline", choice.get("headline", ""),
                            "--badge", choice.get("badge", ""), "--layout", layout, "--out", str(p[layout])],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
        log(r.stdout + r.stderr)
        if r.returncode:
            raise RuntimeError((r.stderr or r.stdout).strip()[-400:])
    choice.setdefault("layout", "hero")
    shutil.copyfile(p[choice["layout"]], p["use"])
    p["meta"].write_text(json.dumps(choice, indent=1, ensure_ascii=False), encoding="utf-8")
    return choice


def choose_layout(merged, layout):
    p = paths(merged)
    meta = json.loads(p["meta"].read_text(encoding="utf-8"))
    if layout not in ("hero", "badge") or not p[layout].exists():
        raise ValueError("unknown layout")
    shutil.copyfile(p[layout], p["use"])
    meta["layout"] = layout
    p["meta"].write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    return meta


def info(merged):
    p = paths(merged)
    if not p["meta"].exists() or not p["use"].exists():
        return None
    try:
        meta = json.loads(p["meta"].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    meta["can_edit"] = (p["work"] / "candidates.json").exists()
    meta["candidates"] = len(json.loads((p["work"] / "candidates.json").read_text(encoding="utf-8"))["candidates"]) \
        if meta["can_edit"] else 0
    return meta
