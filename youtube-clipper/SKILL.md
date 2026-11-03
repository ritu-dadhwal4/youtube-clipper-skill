---
name: youtube-clipper
description: Turn a long YouTube video or podcast (a link or a video file) into ready-to-post vertical short clips with word-by-word captions, then open a page on the user's computer to preview, trim and download them. Use when the user wants to clip a long video, find the best moments of a podcast or interview, make Shorts/Reels/TikToks from a long video, or says "youtube clipper", "clip this video", "make clips from this link".
---

# YouTube clipper

Plain words: you give Claude one long video. Claude reads what was said, picks the moments that work on their own, cuts each into a 9:16 clip with captions, and opens a page where you preview, trim and download them.

Everything runs on the user's own computer. Claude cannot watch video, so it picks moments by **reading the transcript**; it never claims to have "watched" the video.

Scripts live in `<skill>/scripts/` (run with `python3`). Working folder per video: `~/Documents/YouTube Clips/<video-name>/`.

## Before you start (say this once, and do not soften it)

"Never post a clip of someone else's video without the creator's clear consent, and always tag and credit them. Clip only videos you own, videos whose creator has said yes in writing, or videos inside a paid clipping programme where the creator invites clippers. Do not use anyone's work without their agreement."

If the user says they do not have consent, do not continue with that video; offer to clip a video they own instead. Do not lecture beyond this.

## Step 0 - Check the setup (first run only)

`python3 scripts/setup_check.py`. For each MISSING item, run the fix it prints (ask before installing). The whisper model is a large download (small.en ≈ 470 MB): tell the user the size before downloading.

## Step 1 - Ask (two short rounds, both mandatory)

Round 1, one AskUserQuestion call. Always ask the layout and the caption language, even if the user said little; skip only what they already told you:

1. **How many clips?** 5 / 10 (Recommended) / 15. A 1-hour video holds about 8-15 good moments; beyond ~12 quality drops.
2. **Layout** (put the best fit first):
   - **Fill the screen** (Recommended for a single speaker): the video fills the screen and follows the speaker's face. Optional zoom.
   - **Card with hook on top**: a headline above, the video in a tall rounded card, on a colour background.
   - **Whole frame on a colour**: the full frame in the middle, on a colour background. Best when the video shows slides or graphics.
   - **Whole frame on blur**: the full frame over a blurred copy. Safest, but the most generic.
3. **Captions** (this is the only place the language is chosen, so ask it every time): Spoken words as said, word by word with the spoken word in yellow (Recommended) / English / Hinglish (Hindi in Roman letters) / No captions. You write the English or Hinglish lines yourself in Step 4; they show a line at a time. The clip page can switch between what exists but cannot make new languages.
4. **Hook headline on the clips?** Yes, in English / Yes, in the spoken language / Yes, in Hinglish / No. The card layout always has one, so for it skip the "No" and still ask the language.

Round 2, only what the answers need (one AskUserQuestion call):
- **Background colour** for Card or Whole frame on a colour: Yellow #FED50C (Recommended) / Black / White / Navy / or the user types their own colour code under Other.
- **Language spoken** if you do not already know it, and for a link, whether to use YouTube's captions (Step 3).

**The hook question in Step 4 is mandatory and cannot be skipped** whenever a hook headline is on: do not render a Card or hooked clip without a hook the user has approved.

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
[{"id": "c1", "title": "≤60 chars, curiosity not clickbait", "first_line": "the first spoken line (a note for you, never shown on the clip)",
  "start": 754.2, "end": 801.0, "score": 9, "reason": "one sentence: why this works",
  "post": "Caption to post, 1-2 lines + 3-5 hashtags, ending with a credit line: Source: <channel name> (read it from meta.json)",
  "layout": "fill", "zoom": 1.0, "bg": "#FED50C", "captions": "original",
  "hook": "", "hook_options": [], "caption_sets": {}}]
```
`start`/`end` are seconds from the transcript timestamps (read the exact word times from `words.json` when you need precision). Rendering snaps the cut to word edges.

`layout` is `fill`, `card`, `brand` or `blur` (the user's round-1 answer). `bg` only matters for `card` and `brand`. Leave `xpos`/`ypos` out: the render follows the speaker's face on its own.

**Hook headline (when on, and always for `card`).** Write 3 options per clip in the language the user chose in round 1, each at most 8 words: a claim, a question or a number that makes someone stop scrolling, true to what the clip says, no false promises. Show the user every clip with its options and ask which to use per clip (one AskUserQuestion call, up to 4 clips each; for more clips list them in text and let the user answer in one message). They may pick one, write their own, or pick none for a layout that does not need it. Put the approved text in `hook` and keep the options in `hook_options` (the clip page offers them as one-tap suggestions). Layouts other than `card` show the hook for the first 4.5 seconds; `card` shows it throughout.

**Captions.** `"captions": "original"` draws the spoken words. `"none"` draws nothing. For the English or Hinglish choice, translate or transliterate each clip into short lines (at most 5 words or 28 characters), with start and end in source seconds taken from `words.json`, and store them as `"caption_sets": {"English": [{"s": 754.2, "e": 757.0, "t": "..."}]}` with `"captions": "set:English"`. Also keep the spoken words available (`captions` can be switched back to `original` on the clip page). Keep the meaning exact; never invent or soften what was said.

## Step 5 - Render

`python3 scripts/render.py <folder>` - about 5-10 s per clip. Latin captions are drawn with Pillow; Hindi (and any non-Latin text) and hook headlines are drawn with Chrome, because Pillow cannot shape Devanagari. Face-following needs `opencv-python-headless` (`python3 -m pip install --user "opencv-python-headless<5"`); without it the crop stays centred.

## Step 6 - Open the page

`python3 scripts/picker.py <folder>` (runs in the background; opens http://127.0.0.1:8765). Tell the user: the page opens on a grid of all clips (tick Keep, hover to preview); **Edit** opens one clip with the video on the left and the options on the right: nudge start/end with +/-, press **Re-render**, switch layout, zoom, colour, hook headline (tap one of the ideas you wrote, or type your own) and captions (the languages you prepared, spoken words or none). The language is chosen once, when the skill starts, and the page does not translate. Untick **Keep** to drop a clip; download single clips or the zip. Stop the page with Ctrl+C when done.

## Step 7 - Report

Say how many clips, the best three with their titles and scores, anything dropped and why, and that the clips were chosen from the transcript only (Claude did not see the video; the user should watch before posting). If the user wants different clips, change `clips.json` and re-run render; do not re-transcribe.

## Rules

- Every post caption you write ends with `Source: <creator or channel name>`, and you remind the user to tag the creator when they post. Never write a caption that suggests the clip is the user's own work.
- Never promise views or income. Clips are a starting point; results depend on the account, the topic and consistency.
- Do not add music, logos or faces from other sources. Do not edit what a person says (no cutting words out to change the meaning).
- Keep each video's files inside its own working folder. Never delete the source video unless asked.
- Mute any preview you open yourself; never press play with sound.
