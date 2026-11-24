# Playbook: Valorant

5v5 tactical shooter. A session has several **matches** (competitive: first to 13
rounds). Each round, the user either survives or dies and then **spectates a teammate**
until the round ends. Built from "Valorant 2026.08.01 - 16.15.54.03" (Ascent, Sunset,
Summit); detector and planner tuned on "Valorant 2026.06.20 - 17.58.06.02".

## User rules
1. **Every kill the user gets is in a short.** Single kills too, not just multi-kills.
   One short per fight (one life in one round). Don't skip a kill because it looks
   ordinary. The only exception is a kill with nothing visible on screen, e.g. hidden
   behind a full-screen menu; list it as rejected with the reason.
2. **Only the user's own plays.** Never use footage from while the user is dead and
   spectating, even if a teammate gets an ACE or CLUTCH.

## Flow (replaces PROCEDURE steps 4-9)

Scripts do the finding, cutting and scoring. Your job is the parts that need eyes: map and
agent names, the scoreboard cross-check, checking the detections, and the titles.
**No Whisper transcript, no loudness pass and no overview sheets** for Valorant: the
detector's kill list decides every clip, so they never change the result.

1. **Detector** (about 3-4 min for a 2-hour recording):
   ```
   python valorant_killfeed.py "<src>" "<work>\kills.json" --debug-dir "<work>\killfeed"
   ```
   One pass finds:
   - the user's **kills and deaths** from the kill feed: Valorant writes the local player
     as **"Me"** with a **gold outline**. "Me" on the left of an entry = a kill, on the
     right = the user died. A spectated teammate appears under their own name, so a "Me"
     entry proves the play is the user's. A second death in the same round is dropped
     (the user can only die once per round).
   - **rounds**: buy phase from "PRESS [B] TO BUY" (also under MATCH POINT / OVERTIME
     banners), the round result from WON / LOST.
   - **matches**: VICTORY / DEFEAT, with rounds won/lost and the detector's K/D per match.
   It prints the matches and the clusters (kills per life).
2. **Check the detections:** view `<work>\killfeed\killfeed_NN.jpg`. Each is 24 kill feed
   strips, labelled with the time and K (kill) or D (death). Confirm each strip shows a
   gold-outlined "Me" on the right side. Report any false detection (and set `"skip": true`
   on that clip in step 5, with the reason in `why`).
3. **Plan, first pass** (no names yet):
   ```
   python valorant_plan.py "<src>" "<work>\kills.json" "<work>\plan.json"
   ```
   It prints, per match, the time windows to check:
   - **agent select / map card** (before the first round): `sheets.py ... --start A --end B --every 10`,
     one sheet. Agent select shows the agent's name in large text and the map top left.
     If several agent selects appear (a dodge or requeue), the last one before the match counts.
     The big name is whatever is **hovered**, not necessarily locked in: confirm with the
     loading screen or the in-game ability icons / death camera (on 06.20, agent select
     showed CLOVE but the user played Reyna).
     If the recording starts mid-match, say so and leave that match unnamed.
   - **end screens** (after VICTORY/DEFEAT): `sheets.py ... --start A --end B --every 3`,
     one sheet: the MVP card (5 agents with K/D/A) and the scoreboard (the user's row is
     highlighted yellow/gold). If the game went straight to the lobby, there's no
     scoreboard: say so.
4. **Cross-check:** the scoreboard's K and D must match the detector's count for that
   match. If they don't, find the missing kills with `--every 1` sheets around deaths and
   fights, and report the difference. (Tested: exact match on 3 matches of 08.01 and
   match 1 of 06.20.)
5. **Plan, final pass** with the names, e.g.:
   ```
   python valorant_plan.py "<src>" "<work>\kills.json" "<work>\plan.json" --match "1=Breeze/Viper" --match "2=Sunset/Reyna"
   ```
   Read the printed clip list. Edit `plan.json` only where it needs judgement: a better
   title or hook (only claim what's in the clip), a `"skip": true` with a reason, a
   CLUTCH you confirmed is the user's (see below).
6. **Render and verify**: PROCEDURE step 8 (`render_clip.py "<work>\plan.json" --check-dir
   "<work>\checks"`) and step 9 (view the check images). Clips that end on a death must
   end on the user's own death camera (red tint, own body), never on a teammate's view.

## How the planner cuts (valorant_plan.py)
- One clip per life with kills. Kills more than 10 s apart become separate segments
  (hard cuts), waiting dropped. A clip never starts before the round goes live.
- Start 4 s before the first kill (5.5 s for a single-kill clip, so it reaches about 8 s),
  3 s before later segments. Segments are at least 4 s.
- End 2 s after the last kill. If the user dies within 5 s of it, end just after the
  detected death (spectating follows about 1 s after a death). If a round-end banner
  appears within 5 s while the user is alive, the user's kill ended the round, so it was
  won: end 1.5 s after the banner.
- 3+ kills: the last 2.5 s get `"layout": "blur"`, so a vertical Short shows the whole
  kill feed.
- A kill after the user's death in the same round (utility) is skipped, because the view
  is spectating: it is listed as a skipped kill. Report it.
- Scores: hook / action / payoff from the kill count and outcome, calibrated to earlier
  hand scores: single kill 47, single kill then death 40, round-winning kill 60, double
  63 (57 if the user dies), triple 73 (77 if it wins the round), more for 4K / ACE.
  Adjust by hand only for something the script can't see (low HP, a crazy flick).

## Recognising the phases (for the sheets you do look at)

| Phase | What it looks like |
|---|---|
| Agent select | Agent grid, the chosen agent's name in large text (e.g. "REYNA"), map name top left, "LOCK IN" |
| Loading | Big map name card ("BREEZE", "LOTUS") with "COMPETITIVE". **The same card also shows at the end of a match**, after the end screens |
| Buy phase | Top banner "BUY PHASE", or "MATCH POINT" / "OVERTIME" / "OVERTIME - MATCH POINT", always with "PRESS [B] TO BUY" under it; timer counts down from 0:30 |
| **Live round** | First-person view. Top centre: round timer and score, with ally portraits (teal) left and enemy portraits (red) right. Bottom: HP, abilities (C Q E X) and ammo. Kill feed top right |
| User kill | Kill feed entry **"Me [weapon] Victim"** with a gold outline. Also a skull-in-ring kill banner just above the ability bar |
| User death | Kill feed entry **"Killer [weapon] Me"**, a red-tinted death camera on the user's own agent, then a **COMBAT REPORT** panel on the right |
| **Spectating (exclude)** | Bottom left: teammate portrait and name with **"< SWITCH PLAYER >"**. The combat report often stays open |
| Round end | "WON" (teal box) or "LOST" (red box) at the top. Sometimes **CLUTCH, ACE, FLAWLESS or THRIFTY** instead: CLUTCH is shown to **both teams**, so these banners don't tell who won (the detector leaves those rounds' result unknown) and **don't prove a user play** |
| Match end | Big "VICTORY" (teal) or "DEFEAT" (red) with the final score, the MVP card (5 agents with ACS and K/D/A), the scoreboard if opened, the rank screen, then the map card |

## Titles and hooks
- Claim only kills the detector found in that short's time range.
- Use the multi-kill words: "Double Kill", "Triple Kill", "Quadra Kill" and "ACE" (only for 5 by the user).
- Never use an ACE, CLUTCH or FLAWLESS banner in a title unless it's the user's,
  confirmed by the "Me" kill count. A CLUTCH banner is the user's only if it shows "Me"
  under it (check a full-resolution crop of the banner).
- The kill feed usually shows **player names**, not agent names, so don't name victims.
- Hashtags: `#valorant` plus the always_hashtags from settings.json (the planner adds the
  agent and map too).

## No match recaps
Don't make recaps for now.

## Notes from earlier runs
- The skull multi-kill counter (II, III) often hasn't appeared yet on the keyframe the
  detector reads, so don't use it to group kills; the detector's rounds do that.
- Many matches go straight from VICTORY/DEFEAT to the lobby without the scoreboard; the
  cross-check then isn't possible. The user can press Tab at the end of a match.
- Recordings can end with desktop footage (Steam etc.) or include an abandoned match
  (a loading card with no rounds after it). The detector simply finds no rounds there.

## Report
Per match: map, agent, result and score, and the user's K/D from the scoreboard next to
the detector's count. Rounds with an unknown result (CLUTCH/ACE banners). Then all
shorts, and any kill without a short, with the reason.
