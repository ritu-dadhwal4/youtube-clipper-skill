---
name: youtube-clipper
description: Turn a long YouTube video or podcast (a link or a video file) into ready-to-post vertical short clips with word-by-word captions, then open a page on the user's computer to preview, trim and download them. Use when the user wants to clip a long video, find the best moments of a podcast or interview, make Shorts/Reels/TikToks from a long video, or says "youtube clipper", "clip this video", "make clips from this link".
---

# YouTube clipper

Plain words: you give Claude one long video. Claude reads what was said, picks the moments that work on their own, cuts each into a 9:16 clip with captions, and opens a page where you preview, trim and download them.

Everything runs on the user's own computer. Claude cannot watch video, so it picks moments by **reading the transcript**; it never claims to have "watched" the video.

Scripts live in `<skill>/scripts/` (run with `python3`). Working folder per video: `~/Documents/YouTube Clips/<video-name>/`.

## Before you start (say this once, in one line)

"Clip only videos you own, have permission to use, or that sit inside a paid clipping programme where the creator invites clippers. Re-uploading someone's video without that can get your channel demonetised or struck."

Do not lecture beyond that.

## Step 0 - Check the setup (first run only)

`python3 scripts/setup_check.py`. For each MISSING item, run the fix it prints (ask before installing). The whisper model is a large download (small.en ≈ 470 MB): tell the user the size before downloading.

## Step 1 - Ask once

One AskUserQuestion call, only for what the user did not already say:

1. **How many clips?** 5 / 10 (Recommended) / 15. A 1-hour video holds about 8-15 good moments; beyond ~12 quality drops.
2. **Language spoken** - English (Recommended if it is) / Hindi or Hinglish / other (auto-detect).
3. **Layout** - "Whole frame over a blurred background" (Recommended; keeps both speakers in view) / "Fill the screen" (tighter, loses the sides).

## Step 2 - Fetch

`python3 scripts/fetch.py "<link or file>"` → prints the working folder. Long videos download slowly; say so and keep going when it finishes. If yt-dlp is blocked or the link is private/age-restricted, ask the user for the video file instead; never look for workarounds.

## Step 3 - Transcribe

**For a YouTube link, try YouTube's own captions first** (instant, no download, and much better than whisper for Hindi/Hinglish): `yt-dlp --list-subs "<link>"` shows what exists; then `python3 scripts/transcribe.py <folder> --youtube-captions en` (or `hi-orig`, the original-language track). The captions are auto-generated, so spelling can be off; the time of every word is real.

**No captions, or a file instead of a link: whisper.** `python3 scripts/transcribe.py <folder> --lang en` (or `hi`, or `auto`; non-English needs the multilingual model, `--download-model small`). Takes roughly 5-10 min per hour of video; tell the user it is running and that they can step away. Whisper's small multilingual model is weak on Hindi/Hinglish (repeats and garbles); say so, and prefer YouTube captions or the medium model (`--download-model medium`, about 1.5 GB, slower).

## Step 4 - Pick the moments (this is the part only Claude does)

Read `<folder>/transcript.txt` (lines look like `[00:12:31] sentence`). Read it in pieces of about 400 lines; after each piece write down candidate moments, then rank them all at the end. A 3-hour video is fine; just keep the running candidate list.

A good clip:
- **Starts with a hook** in the first sentence: a claim, a question, a surprising number, a conflict, a story opening. Never starts mid-thought ("and so that's why…", "as I said before").
- **Makes sense with no context.** Someone who never saw the rest must follow it.
- **Ends when the thought ends** - on the punchline, the answer or the lesson. Never mid-sentence.
- **Is 30-60 seconds** (hard limits 20 s and 90 s).
- Contains one idea: advice, a story with a turn, a number that surprises, a strong opinion, a funny exchange.

Rules: spread picks across the whole video (no two overlapping, no more than 3 from one 10-minute stretch unless they are clearly the best); skip intros, sponsor reads and housekeeping; score each 1-10 honestly (7+ only if you would post it); if fewer than the requested number are good, return fewer and say so.

Write `<folder>/clips.json`, best first:

```json
[{"id": "c1", "title": "≤60 chars, curiosity not clickbait", "hook": "the first spoken line",
  "start": 754.2, "end": 801.0, "score": 9, "reason": "one sentence: why this works",
  "post": "Caption to post, 1-2 lines + 3-5 hashtags", "layout": "blur"}]
```
`start`/`end` are seconds from the transcript timestamps (read the exact word times from `words.json` when you need precision). Rendering snaps the cut to word edges.

## Step 5 - Render

`python3 scripts/render.py <folder>` - about 5-10 s per clip. Captions are drawn word by word (white, the spoken word in yellow) with Pillow, so nothing besides ffmpeg is needed.

## Step 6 - Open the page

`python3 scripts/picker.py <folder>` (runs in the background; opens http://127.0.0.1:8765). Tell the user: preview each clip, nudge start/end with +/- and press **Re-render**, switch layout, edit the title and caption, untick **Keep** to drop one, download single clips or the zip. Stop the page with Ctrl+C when done.

## Step 7 - Report

Say how many clips, the best three with their titles and scores, anything dropped and why, and that the clips were chosen from the transcript only (Claude did not see the video; the user should watch before posting). If the user wants different clips, change `clips.json` and re-run render; do not re-transcribe.

## Rules

- Never promise views or income. Clips are a starting point; results depend on the account, the topic and consistency.
- Do not add music, logos or faces from other sources. Do not edit what a person says (no cutting words out to change the meaning).
- Keep each video's files inside its own working folder. Never delete the source video unless asked.
- Mute any preview you open yourself; never press play with sound.
