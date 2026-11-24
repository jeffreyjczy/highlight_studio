# Playbook: Valorant

5v5 tactical shooter. A session has several **matches** (competitive: first to 13
rounds). Each round, the user either survives or dies and then **spectates a teammate**
until the round ends. Built from "Valorant 2026.08.01 - 16.15.54.03" (Ascent, Sunset,
Summit).

## User rules
1. **Every kill the user gets is in a short.** Single kills too, not just multi-kills.
   One short per fight (one life in one round). Don't skip a kill because it looks
   ordinary. The only exception is a kill with nothing visible on screen, e.g. hidden
   behind a full-screen menu; list it as rejected with the reason.
2. **Only the user's own plays.** Never use footage from while the user is dead and
   spectating, even if a teammate gets an ACE or CLUTCH.

## Step 1: run the kill detector (mandatory, before choosing clips)

```
python valorant_killfeed.py "<src>" "<work>\kills.json" --debug-dir "<work>\killfeed"
```

The detector takes about 1 minute for a 1h40m recording. It reads the kill feed and
finds every entry where Valorant writes the user as **"Me"**. Valorant always shows
the local player as "Me" with a **gold outline** in the kill feed. A teammate you're
spectating is shown by their own name, so a "Me" entry proves the play is the user's.
- "Me" on the **left** of an entry (killer) = a kill. On the **right** (victim) = the user died.
- `kills.json` → `clusters`: the user's kills grouped per life, with `kill_times` and
  `died_at` (null = survived the round).
- `--debug-dir` saves a kill feed crop for every new detection. View them quickly to
  confirm them and read the victims' agent names for titles.

**The detector's kill list is the source of truth.** Audio peaks, the transcript and
banners are only for choosing cut points and judging how exciting a fight is.

**Cross-check with the scoreboard:** after each match, the scoreboard row highlighted
in **yellow/gold** is the user's. The MVP card and scoreboard show K / D / A. The
detector's kill and death counts for that match must match the K and D. If they don't,
find the missing kills with denser sheets (`--every 1`) around deaths and fights, and
report the difference. On the test recording they matched exactly: 16/14, 14/18 and
19/11.

**Merging clusters:** the detector splits kills more than 30 s apart. If two clusters
are in the **same round** with no "Me" death between them (no "BUY PHASE" or
WON/LOST banner between them on a sheet), make them one short, with the waiting
between them trimmed out using segments.

## Recognising the phases (from contact sheets)

| Phase | What it looks like |
|---|---|
| Agent select / loading | Agent grid, then a big map name card ("ASCENT", "SUNSET", "SUMMIT") with "COMPETITIVE" |
| Buy phase | "BUY PHASE" at the top, buy menu, round timer counting down from 0:30 |
| **Live round** | First-person view. Top centre: round timer and score, with ally portraits (teal) left and enemy portraits (red) right. Bottom: HP, abilities (C Q E X) and ammo. Kill feed top right |
| User kill | Kill feed entry **"Me [weapon] Victim"** with a gold outline. Also a skull-in-ring kill banner just above the ability bar, with a **multi-kill counter** (II, III, IV, V) next to the "Me" entry for kills 2 to 5 in a round |
| User death | Kill feed entry **"Killer [weapon] Me"**. Then a **COMBAT REPORT** panel on the right ("KILLED BY <AGENT>", damage dealt and taken) |
| **Spectating (exclude)** | Bottom left: teammate portrait and name with **"< SWITCH PLAYER >"**. The combat report often stays open on the right. ACE, CLUTCH and FLAWLESS banners also show while spectating, so **they don't prove a user play** |
| Round end | "WON" or "LOST" banner at the top, then a brief ALLIES n / n ENEMIES card |
| Match end | "VICTORY" or "DEFEAT" with the final score, the map card, the MVP card (5 agents with ACS and K/D/A), the rank screen, then the scoreboard |

## Shorts

### Moment clip (one per fight): about 8–45 s
- **Start:** 3–5 s before the first kill (the kill time minus 0.5 s, since the feed entry
  appears up to 0.5 s after the kill). Start earlier, up to 8 s before, if the user is
  visibly peeking, spotting or trading shots first.
- **End:** 2 s after the last kill. If the user dies in the same fight (`died_at` within
  about 5 s of the last kill), end **0.7 s** after the detector's death time: the view can
  switch to spectating about 1 s after it. **Never** include the spectating that follows.
- **Single kills:** start 5–6 s before the kill, so the short reaches about 8 s.
- If the round is won right after the last kill (WON banner within about 5 s), it's fine to end
  on the banner.
- Several kills spread over one life: one short with multiple segments (hard cuts),
  dropping walking and waiting in between. Keep each segment at least 4 s.
- Clips are horizontal, full-frame, at the source resolution. Vertical framing hint for the
  merger: leave `layout` out (= `crop`) for gameplay; set `"layout": "blur"` on a segment
  where the kill feed or a multi-kill banner is the point (e.g. the last 2–3 s of a 3K+ round).

### No match recaps
Don't make recaps for now.

## Ranking and scoring
Ace (5K) → 4K → 3K → clutch (user is last alive and wins the round, with kills) →
2K → a kill that wins the round → a single kill, then death → a single kill. A low-HP
kill or a kill that wins the round makes any short better.

Score as in PROCEDURE.md. As a guide for `action`: 5K 10, 4K 9, 3K 8, 2K 6, a kill that
wins the round 5, a single kill 3–4. A single kill followed by a death usually scores
30–45. That's fine: it still gets made (user rule 1).

## Titles and hooks
- Claim only kills the detector found in that short's time range. Name the victims'
  agents (from the kill feed crops) when it helps, e.g. "Pistol Double Kill: Omen and Sova".
- Use the multi-kill words: "Double Kill", "Triple Kill", "Quadra Kill" and "ACE" (only for 5 by the user).
- Never use an ACE, CLUTCH or FLAWLESS banner in a title unless it's the user's,
  confirmed by the "Me" kill count.
- Hashtags: `#valorant` plus the always_hashtags from settings.json.

## clips.json events
For every short, put each detector kill and death inside it in `events` as source times: `{"t": <kill time - 0.3>, "type": "kill"}` (the feed entry appears up to 0.5 s after the kill), and the same with `"type": "death"`. The compilation merger uses them.

## CLUTCH banners
A CLUTCH banner is the user's only if it shows "Me" under it (check a full-resolution frame).

## Report
Per match: map, result and score, and the user's K/D/A from the scoreboard next to the
detector's count. Then all shorts, and any kill without a short, with the reason.
