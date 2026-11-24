"""Turn valorant_killfeed.py output into a render plan (plan.json for render_clip.py).

Applies the Valorant playbook's cut rules to every kill the detector found, so cuts and
scores are the same every run. Claude only adds what needs eyes: map and agent names
(from one sheet per match), the scoreboard cross-check, and a look at the titles.

Usage:
  python valorant_plan.py <recording> <kills.json> <plan.json>
         [--match "1=Breeze/Viper" --match "2=Sunset/Reyna" ...] [--out-dir DIR]

Without --match, titles say "in Match N" instead of agent and map. The script prints the
matches with the time windows where agent select and the end-of-match scoreboard are,
so they can be checked with one contact sheet each.

Cut rules (from games/Valorant.md):
  - one clip per life with kills; kills more than 10 s apart become separate segments
    (hard cuts), waiting in between dropped; never starts before the round goes live
  - start 4 s before the first kill (5.5 s for a clip with a single kill), 3 s before
    later segments; segments at least 4 s long
  - end 2 s after the last kill; if the user dies within 5 s of it, end just after the
    detected death (0.4 s with 0.5 s keyframes, 0.1 s with 1 s keyframes: spectating
    follows about 1 s after a death); if a round-end banner comes within 5 s while the
    user is alive, the kill won the round: end 1.5 s after the banner
  - 3+ kills: the last 2.5 s get "layout": "blur" (the merger shows the whole kill feed)
  - kills after the user's death in that round (utility) are skipped: the view is
    spectating by then
Scores: hook/action/payoff from the kill count and outcome (see score()), calibrated to
the scores given by hand on earlier recordings.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BIN = Path(r"C:\Users\jeffr\AppData\Local\Microsoft\WinGet\Packages"
           r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.1-full_build\bin")

JOIN_GAP = 10.0       # kills closer than this share a segment
LEAD_SINGLE, LEAD_FIRST, LEAD_LATER = 5.5, 4.0, 3.0
TAIL, DEATH_NEAR = 2.0, 5.0
WIN_NEAR, WIN_TAIL = 5.0, 1.5
MIN_SEG, BLUR_TAIL = 4.0, 2.5
WORD = {1: "Kill", 2: "Double Kill", 3: "Triple Kill", 4: "Quadra Kill", 5: "ACE"}


def audio_tracks(src):
    r = subprocess.run([str(BIN / "ffprobe.exe"), "-v", "error", "-select_streams", "a",
                        "-show_entries", "stream=index", "-of", "csv=p=0", src],
                       capture_output=True, text=True)
    return len([x for x in r.stdout.split() if x.strip()])


def score(n, died, won_after):
    hook = {1: 5, 2: 6}.get(n, 7)
    action = {1: 3, 2: 6, 3: 8, 4: 9}.get(n, 10)
    if n == 1 and won_after:
        action = 5                                    # a kill that wins the round
    if died:
        payoff = 4 if n == 1 else 5
    elif won_after:
        payoff = 8
    else:
        payoff = 6 if n == 1 else 7
    return round((hook + action + payoff) * 10 / 3), {"hook": hook, "action": action, "payoff": payoff}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("kills")
    ap.add_argument("out")
    ap.add_argument("--match", action="append", default=[], help='"N=Map/Agent"')
    ap.add_argument("--out-dir")
    a = ap.parse_args()

    d = json.loads(Path(a.kills).read_text(encoding="utf-8"))
    settings = json.loads((HERE / "settings.json").read_text(encoding="utf-8"))
    always = settings.get("always_hashtags", ["#gaming"])
    rounds = {r["index"]: r for r in d.get("rounds", [])}
    # The view switches to spectating about 1 s after a death, and the detector sees the
    # death up to one keyframe interval late: end early enough to never show spectating.
    kf = float(d.get("keyframe_interval", 0.5))
    death_tail = max(0.1, 0.9 - kf)
    matches = {m["index"]: m for m in d.get("matches", [])}
    info = {}
    for m in a.match:
        k, v = m.split("=", 1)
        mp, _, ag = v.partition("/")
        info[int(k)] = {"map": mp.strip() or None, "agent": ag.strip() or None}

    deaths_by_round = {}
    for x in d["deaths"]:
        deaths_by_round.setdefault(x["round"], x["t"])

    # merge clusters of the same life: same round, no death between (the detector also
    # splits a life after a 30 s gap)
    clusters = []
    for c in d["clusters"]:
        prev = clusters[-1] if clusters else None
        if (prev and c["round"] is not None and prev["round"] == c["round"]
                and prev["died_at"] is None):
            prev["kill_times"] += c["kill_times"]
            prev["kills"] += c["kills"]
            prev["end"], prev["died_at"] = c["end"], c["died_at"]
        else:
            clusters.append(json.loads(json.dumps(c)))

    clips, skipped, title_count = [], [], {}
    for c in clusters:
        r = rounds.get(c["round"]) or {}
        death = deaths_by_round.get(c["round"])
        kts = sorted(c["kill_times"])
        after = [t for t in kts if death is not None and t > death + 0.01]
        kts = [t for t in kts if t not in after]
        for t in after:
            skipped.append({"t": t, "why": "kill after the user's death this round (utility): view is spectating"})
        if not kts:
            continue
        n = len(kts)
        died = c["died_at"] is not None and c["died_at"] - kts[-1] <= DEATH_NEAR
        # A round-end banner right after the user's kill, with the user alive, means that
        # kill ended the round, so it was won. This also covers CLUTCH/ACE-type banners,
        # whose result the detector leaves unknown.
        won_after = (not died and r.get("result") != "lost" and r.get("end") is not None
                     and 0 <= r["end"] - kts[-1] <= WIN_NEAR)
        live = r.get("start", 0.0) or 0.0

        groups = [[kts[0]]]
        for t in kts[1:]:
            (groups[-1].append(t) if t - groups[-1][-1] <= JOIN_GAP else groups.append([t]))
        segs = []
        for gi, g in enumerate(groups):
            lead = LEAD_SINGLE if n == 1 else (LEAD_FIRST if gi == 0 else LEAD_LATER)
            s, e = g[0] - lead, g[-1] + TAIL
            if gi == len(groups) - 1:
                if died:
                    e = c["died_at"] + death_tail
                elif won_after:
                    e = r["end"] + WIN_TAIL
            s = max(s, live, segs[-1]["end"] if segs else 0.0)
            if e - s < MIN_SEG:
                s = max(e - MIN_SEG, live, segs[-1]["end"] if segs else 0.0)
            if segs and s - segs[-1]["end"] < 3.0:      # nearly touching: one segment
                segs[-1]["end"] = round(e, 2)
                segs[-1]["label"] += f" + {len(g)} kill(s)"
                continue
            segs.append({"start": round(s, 2), "end": round(e, 2),
                         "label": f"{len(g)} kill(s)" + (" + death" if died and gi == len(groups) - 1 else "")})
        if n >= 3 and segs[-1]["end"] - segs[-1]["start"] >= BLUR_TAIL + 3.5:
            last = segs[-1]
            cut = round(last["end"] - BLUR_TAIL, 2)
            segs[-1] = {"start": last["start"], "end": cut, "label": last["label"]}
            segs.append({"start": cut, "end": last["end"], "label": "multi-kill feed", "layout": "blur"})

        mi = r.get("match")
        mm = info.get(mi, {})
        agent, mp = mm.get("agent"), mm.get("map")
        rnd_in_match = sum(1 for x in rounds.values() if x.get("match") == mi and x["index"] <= c["round"]) \
            if c["round"] else None
        word = WORD.get(n, "ACE")
        if n == 1:
            base = "Round-Winning Kill" if won_after else ("Kill Before Going Down" if died else "Clean Kill")
        else:
            base = word + (" Then Death" if died else "") + (" Round Win" if won_after else "")
        where = f"on {mp}" if mp else (f"in Match {mi}" if mi else "")
        title = " ".join(x for x in (agent, base, where) if x)
        title_count[title] = title_count.get(title, 0) + 1
        if title_count[title] > 1:
            title = f"{title} {title_count[title]}"
        sc, parts = score(n, died, won_after)
        if n == 1:
            hook = "THE ROUND-WINNING KILL" if won_after else ("ONE KILL / THEN DOWN" if died else "ONE CLEAN KILL")
        else:
            hook = f"{word.upper()} / " + ("WINS THE ROUND" if won_after else ("THEN GOES DOWN" if died else "ONE ROUND"))
        who = f"Playing {agent}" if agent else "In this round"
        story = (f"{who}{' on ' + mp if mp else ''}, the user gets {n} kill{'s' if n > 1 else ''}"
                 f"{' in round ' + str(rnd_in_match) if rnd_in_match else ''}"
                 f"{', then goes down' if died else ''}{' and the round is won' if won_after else ''}.")
        tags = ["#valorant"] + [t for t in always if t != "#valorant"]
        tags += [f"#{x.lower().replace(' ', '')}" for x in (agent, mp) if x]
        events = [{"t": round(t - 0.3, 2), "type": "kill"} for t in kts]
        if died:
            events.append({"t": round(c["died_at"] - 0.3, 2), "type": "death"})
        clips.append({
            "title": title, "type": "moment", "score": sc, "score_parts": parts,
            "hook": hook, "story": story,
            "youtube": {"title": f"{title} | Valorant"[:70],
                        "description": f"{word if n > 1 else 'A kill'}{' as ' + agent if agent else ''}"
                                       f"{' on ' + mp if mp else ''} in a Valorant match.",
                        "hashtags": tags[:6]},
            "segments": segs, "events": events,
            "why": f"Detector: {n} kill(s), {'died' if died else 'survived'}"
                   f"{', round won' if won_after else ''}; match {mi}, round {rnd_in_match}.",
            "match": mi, "round": c["round"],
        })

    timeline = []
    for m in matches.values():
        mm = info.get(m["index"], {})
        label = f"match {m['index']}" + (f" ({mm.get('map')}, {mm.get('agent')})" if mm else "")
        timeline.append({"phase": label, "start": m["start"], "end": m["end"],
                         "result": m["result"], "rounds_won_lost": f"{m['won']}-{m['lost']}",
                         "detector_kd": f"{m['kills']}/{m['deaths']}"})
    stem = Path(a.src).stem
    plan = {"source": a.src, "game": "Valorant", "playbook": "games/Valorant.md",
            "out_dir": a.out_dir or str(Path(r"E:\Highlights\Valorant") / stem),
            "mic_track": 1 if audio_tracks(a.src) >= 2 else None,
            "timeline": timeline, "skipped_kills": skipped, "clips": clips}
    Path(a.out).write_text(json.dumps(plan, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"{len(clips)} clips, {sum(len(c['events']) - (1 if c['events'][-1]['type'] == 'death' else 0) for c in clips)} kills"
          f" in clips, {len(skipped)} skipped; mic track: {plan['mic_track']}; out_dir: {plan['out_dir']}")
    for m in matches.values():
        rs = [r for r in d["rounds"] if r.get("match") == m["index"]]
        first_buy = rs[0]["buy_start"] if rs else m["start"]
        end = f"{m['end']:.0f}s" if m["end"] is not None else "? (recording ends or match left)"
        unk = m.get("unknown", m["rounds"] - m["won"] - m["lost"])
        print(f"match {m['index']}: {m['start']:.0f}s-{end} {m['result'] or 'no result'}"
              f", rounds won-lost {m['won']}-{m['lost']}" + (f" (+{unk} unknown)" if unk else "")
              + f", detector K/D {m['kills']}/{m['deaths']}")
        if m["index"] not in info:
            if first_buy < 30:
                print("   recording starts in this match: agent select isn't recorded; read the agent"
                      " from the ability icons / first sheet, or leave it unnamed")
            else:
                print(f"   agent select / map card: sheet --start {max(0, first_buy - 150):.0f}"
                      f" --end {first_buy:.0f} --every 10")
        if m["end"] and m["result"]:
            print(f"   end screens (MVP card, scoreboard): sheet --start {m['end']:.0f} --end {m['end'] + 48:.0f} --every 3")
    for c in sorted(clips, key=lambda c: -c["score"]):
        ln = sum(s["end"] - s["start"] for s in c["segments"])
        print(f"  {c['score']:3d}  {ln:5.1f}s  {len(c['segments'])} seg  {c['title']}")
    for s in skipped:
        print(f"  skipped kill at {s['t']}: {s['why']}")


if __name__ == "__main__":
    sys.exit(main())
