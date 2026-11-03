#!/usr/bin/env python3
"""Step 1: get the long video into a working folder.

usage: fetch.py <youtube link | video file> [--out DIR]
Creates DIR/source.mp4, DIR/audio.wav (16 kHz mono for transcription) and DIR/meta.json.
"""
import argparse, re, shutil
from pathlib import Path
from common import run, need, save, HOME

ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("--out")
a = ap.parse_args()
need("ffmpeg", "brew install ffmpeg")
JS = ["--js-runtimes", "node"] if shutil.which("node") else []  # newer yt-dlp wants a JavaScript runtime for YouTube

meta = {"source": a.src, "title": Path(a.src).stem, "channel": ""}
if re.match(r"https?://", a.src):
    need("yt-dlp", "brew install yt-dlp")
    info = run(["yt-dlp", *JS, "--no-playlist", "--print", "%(id)s|%(title)s|%(channel)s|%(duration)s", a.src]).stdout.strip().split("|")
    vid, meta["title"], meta["channel"], dur = info[0], info[1], info[2], info[3]
    meta["id"], meta["duration"] = vid, float(dur or 0)
    out = Path(a.out or HOME / "Documents" / "YouTube Clips" / re.sub(r"[^\w\- ]+", "", meta["title"]).strip()[:60].replace(" ", "-"))
    out.mkdir(parents=True, exist_ok=True)
    if not (out / "source.mp4").exists():
        print("Downloading (this is the slow part for long videos)...")
        run(["yt-dlp", *JS, "--no-playlist", "-f", "bv*[height<=1080]+ba/b[height<=1080]/b", "--merge-output-format", "mp4",
             "-o", str(out / "source.%(ext)s"), a.src])
else:
    src = Path(a.src).expanduser()
    if not src.exists():
        raise SystemExit(f"File not found: {src}")
    out = Path(a.out or HOME / "Documents" / "YouTube Clips" / src.stem.replace(" ", "-"))
    out.mkdir(parents=True, exist_ok=True)
    if not (out / "source.mp4").exists():
        shutil.copy(src, out / "source.mp4")

if not (out / "audio.wav").exists():
    run(["ffmpeg", "-y", "-i", str(out / "source.mp4"), "-vn", "-ac", "1", "-ar", "16000", str(out / "audio.wav")])
probe = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
             "-of", "default=nw=1", str(out / "source.mp4")]).stdout
for l in probe.split():
    k, v = l.split("=")
    meta["duration" if k == "duration" else k] = float(v) if k == "duration" else int(v)
save(out / "meta.json", meta)
print(f"READY {out}\n{meta['title']} - {meta['duration'] / 60:.0f} min, {meta.get('width')}x{meta.get('height')}")
