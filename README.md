# YouTube Clipper — a Claude skill

Give Claude one long video (a YouTube link or a file). It reads what was said, picks the best moments, cuts them into **vertical 9:16 clips with word-by-word captions**, and opens a page on your computer where you **preview, trim and download** them.

- Works on podcasts and interviews up to about 3 hours.
- A 1-hour video usually gives **8–15 good clips** (default: 10). Quality drops after that.
- Clips are 30–60 seconds, start on a hook and end on a finished thought.
- Everything runs on your own computer. Nothing is uploaded anywhere.

> Claude cannot watch video. It chooses moments by reading the transcript, so watch each clip before you post it.

## Install

You need [Claude Code](https://claude.com/claude-code), Python 3 and [Homebrew](https://brew.sh) (Mac).

```bash
git clone https://github.com/ritu-dadhwal4/youtube-clipper-skill.git
```

```bash
mkdir -p ~/.claude/skills && cp -r youtube-clipper-skill/youtube-clipper ~/.claude/skills/
```

```bash
brew install ffmpeg yt-dlp whisper-cpp && python3 -m pip install --user pillow
```

The first run also downloads a speech model (about 470 MB). Claude asks before it does.

## Use

In Claude Code, type:

```
/youtube-clipper
```

then paste the video link. Claude asks how many clips, which language and which layout, and does the rest.

## Hindi and Hinglish

For a YouTube link, the skill uses YouTube's own captions first (fast, and far better than a small speech model for Hindi). Hindi captions are drawn with Google Chrome, which must be installed, because Python's Pillow cannot shape Devanagari without extra libraries. YouTube's auto-captions sometimes drop or misspell numbers, so check any clip that quotes figures.

## Not on a Mac?

Linux: install ffmpeg, yt-dlp and whisper.cpp with your package manager (the `whisper-cli` command must work). Windows: use WSL. The captions use Arial fonts from macOS; on Linux, edit the two font paths at the top of `scripts/captions.py`.

## Use it responsibly

Clip videos you own, have permission to use, or that are part of a paid clipping programme where the creator invites clippers. Re-uploading someone else's video without that can get your channel demonetised or struck. No tool can promise views or income.

## What is inside

| File | Does |
|---|---|
| `SKILL.md` | The instructions Claude follows |
| `scripts/setup_check.py` | Checks what is installed |
| `scripts/fetch.py` | Downloads the video (yt-dlp) |
| `scripts/transcribe.py` | Word-by-word transcript (whisper.cpp) |
| `scripts/render.py` | Cuts, crops to 9:16, adds captions (ffmpeg + Pillow) |
| `scripts/picker.py` | The preview page on your computer |

## License

MIT
