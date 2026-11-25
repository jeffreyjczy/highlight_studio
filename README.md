# highlight_studio

A personal pipeline that turns gameplay recordings into highlight shorts, merges them into music-synced videos, and uploads them to YouTube, with a Windows desktop app (**Highlight Studio**) on top.

## How it works
1. **Recordings** (NVIDIA or AMD Adrenalin, AV1) land in `E:\Recordings\<Game>\`.
2. A **Claude Code agent** (`highlight-maker`) follows [`PROCEDURE.md`](PROCEDURE.md) and the game's playbook in [`games/`](games/) to find the best moments. It uses the helper scripts below and writes lossless clips plus `clips.json` to `E:\Highlights\<Game>\<recording>\`.
3. **`merge_highlights.py`** edits chosen clips into a montage. The montage has beat-synced cuts, tight trims around kills, transitions, and a sound mix. It comes out as a vertical Short or a long horizontal video.
4. **Highlight Studio** does all of the above from one window.

## Highlight Studio (`studio/`)
A pywebview (Edge WebView2) app with a Python backend and a plain HTML/CSS/JS UI.

| Page | What it does |
|---|---|
| Footage | Recordings grouped by game, with thumbnails, hover scrub, details, Make highlights (one `claude -p --agent highlight-maker` run per recording) and Delete (Recycle Bin) |
| Shorts | Clips grouped by game and recording, a player, the YouTube text, and a drag-to-order merge queue with cut preview and sound mix presets |
| Merged | Merged videos, a YouTube description builder and **Upload to YouTube** (official Data API, private by default) |
| Music | Library with credit lines, NCS search and preview (downloads are done by the user in the browser), a link checker and import |
| Settings | Claude account status, game playbook viewer, YouTube connection, folders and theme |

Claude runs use the account signed in to the Claude Code CLI. No API key is used.

## Scripts
| File | Purpose |
|---|---|
| `ledger.py` | The source of truth for what's processed, and the only path to delete or recycle originals |
| `sheets.py` | Contact sheets of keyframes (overview or around fights) |
| `transcribe.py` | Mic transcript (faster-whisper, CPU) |
| `render_clip.py` | Lossless clip cutting from a plan, with check images |
| `valorant_killfeed.py`, `valorant_plan.py` | Scripted Valorant kill, round and match detection, and clip planning |
| `merge_highlights.py` | Montage editor (Shorts or long) |

## Setup (Windows)
- Python 3.13 and ffmpeg (on PATH, or the WinGet path set in the scripts).
- [Claude Code](https://claude.com/claude-code), signed in, with the `highlight-maker` agent in `~/.claude/agents/`.
- App environment: `python -m venv .venv`, then `.venv\Scripts\pip install -r studio/requirements.txt` (plus `faster-whisper` for `transcribe.py`).
- Desktop shortcut: `powershell -File studio\install_shortcut.ps1`.
- YouTube upload: create your own Google Cloud OAuth client of type "Desktop app". The in-app guide at Settings → YouTube → Set up walks through it.

## Privacy
No credentials are stored in this repository. The YouTube sign-in token and OAuth client file live only in `%LOCALAPPDATA%\HighlightStudio\youtube\` on the user's PC. [`docs/`](docs/) holds the app's home page and privacy policy for the Google consent screen, served by GitHub Pages at https://jeffreyjczy.github.io/highlight_studio/.
