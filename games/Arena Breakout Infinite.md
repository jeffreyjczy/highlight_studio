# Playbook: Arena Breakout Infinite

Extraction shooter. A session contains several **raids**, with lobby time in between.
Each raid ends in **extraction** (success) or **death** (failure).

## Recognising the phases (from contact sheets)

| Phase | What it looks like |
|---|---|
| Lobby | Dark menu UI with tabs along the bottom (Storage, Missions, Contracts, Market...). Stash grids, market price lists, loadout, the "Return to Team" / ready screen, event banners |
| Queue / loading / deploy | Matchmaking, loading screens, the start-of-raid gear screen |
| **In raid** | First-person view with HUD: body-status silhouette bottom-left, compass strip top-centre, weapon/ammo bottom-right. Scope view = black circle vignette |
| In-raid looting | Inventory screen *during* a raid: character model left, item grids, "Last Value" at top right. Many short looting screens means one raid with lots of looting |
| Taking damage / low HP | Red edges around the screen. **Not to be confused with the extraction alarm**: when an extract is activated ("Extraction Point Alarm" banner top-right), the whole area glows red. That's lighting, not damage |
| Death | Sudden cut away from first-person, "Operation Failed" / KIA screens, then spectating a teammate (spectate card with names) |
| Extraction | "Hold position" countdown at an extract point, then the **end screen** (below) |
| **End screen (success)** | Confirmed by the user. Large **"OPERATION SUCCESS"** text over a dimmed game view, with mode, map and raid time above it (e.g. "Tactical Ops · TV Station · Lockdown Zone · 00:06:24"). Below it: "Perfect Raid" (sometimes), **Loot Value** (e.g. 375,335), **Total Eliminations**, **Operators Elim'd**, and a "Results" button. **It fades in over about 0.5 s and is fully readable for only about 1 s**, then the screen goes black for loading. Find its exact second with a 1 s zoom sheet (`--every 1`) |
| End screen (failure) | "OPERATION FAILED" / KIA, then spectating |

Use the end screen's numbers in titles and your report. **Operators Elim'd = player kills, which is the number that matters.** Total Eliminations includes AI/NPC kills; don't feature it in hooks or titles.

## What counts (user rule)
**Only operator (player) kills matter. NPC/AI eliminations don't count.**
- A fight is short-worthy only if it involves **operators**: you kill one or more, or you fight several and lose after a real fight.
- Fights against NPCs only (scavs, guards, bosses' AI) are **not** shorts, and don't count toward "kills" in hooks or titles.
- To tell them apart: there's usually **no kill feed or kill notification** for operator kills. The reliable proof is the **"Operators Eliminated" counter in the in-raid inventory header** (top right, next to "Last Value"). Compare it on inventory screens before and after a fight. Players also move and fight like players (gear, flanking, return fire). A body with no counter change is an NPC.
- If you're unsure whether a kill was an operator, don't claim it in the hook or title.

Kill signals:
- The "operators eliminated" counter in the HUD/summary going up = a **player (PMC) kill**.
- A body plus a blood hit with no counter change is most likely an **AI enemy (scav)**.

## What makes a short (two types, both allowed)

### A. Moment short (most common): 15–60 s
Any fight worth watching, **win or lose**:
- **Best:** a 1vN fight with multiple player kills, even if you die at the end. A 1v4 with 3 kills and then a death is a great clip.
- Good: an operator kill after a real exchange of fire, a close-range surprise fight against an operator, a clutch heal-and-fight-back against operators.
- Not a short: fights against NPCs only, however many.
- Cut: start 3–5 s before the first shot or the spotting moment. End 2–3 s after the last kill. If you die, end on the death, including the first 1–2 s of the death screen. Fights inside one clip can be trimmed together (cut out long waiting between kills) with multiple segments.

### B. Raid recap short: 30–90 s (max 120 s)
Only for a raid that **extracted successfully** with **at least one operator kill** or a big Loot Value. Tell the raid as a story:
1. Deploy / first look at the map (2–3 s)
2. Each operator fight, trimmed tight (5–15 s each). Leave out NPC fights, or keep them to 1–2 s at most if needed for the story.
3. Best loot moments: an inventory screen showing a valuable item being picked up (2–4 s each, layout hint `blur`)
4. Reaching the extract and the end of the countdown (2–3 s)
5. **End screen with the Loot Value. Always end on it.** Use a segment of about 1.5–2 s covering the end screen, with the layout hint `"layout": "center"` (for vertical Shorts the merger zooms in so the numbers are readable on a phone) and `"hold": 3` (freezes its last frame for 3 s). Make sure the segment ends before the screen turns black.

Moment shorts from a raid that extracted can also end on the end screen (1.5 s + `"hold": 2`) when the fight is near the end of the raid.

A raid can produce **both** a recap and separate moment shorts for its best fights.

### Skip
- Lobby, stash, market, queue, loading.
- Raids with no fight and nothing notable looted.
- Instant deaths with no fight back.
- Long scope holds with no visible payoff.
- Spectating teammates.

## Ranking (when there's more than you can use)
1v2+ operator multi-kill or clutch → single operator kill after a real fight → extraction recap (with operator kills and/or a high Loot Value) → losing a real fight against several operators. NPC-only action is never ranked.

## Other notes
- Mic commentary is Thai. Strong reactions near a fight make it better, but don't pick a clip from the transcript alone.
- Avoid scoreboard/spectate cards showing other players' names where you can.
- Clips are horizontal, full-frame, at the source resolution. Layout hints for the merger's vertical Shorts: none (= `crop`) for gameplay, `blur` for inventory screens (wide UI), `center` for the end screen.
- Example short title using the end screen: "2 Operators Down, 375K Loot Extracted". Use Operators Elim'd, never Total Eliminations.
- Fights sheets (PROCEDURE step 5, `--fights`): NPC fights and looting are loud too, so many windows are scav fights or inventory screens after a fight. Use them to spot fights, then check operator kills with the "Operators Eliminated" counter as above. Tested on "Arena Breakout Infinite 2026.07.05 - 21.03.25.01" (84 min): 70 windows, 21 fights sheets + 11 overview sheets.
