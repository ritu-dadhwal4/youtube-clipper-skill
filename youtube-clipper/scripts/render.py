#!/usr/bin/env python3
"""Step 4: cut the chosen moments into finished 1080x1920 clips with captions.

usage: render.py DIR [--only c1,c3] [--no-captions]
Reads DIR/clips.json (the list Claude wrote), DIR/words.json and DIR/source.mp4.
Writes DIR/clips/<id>.mp4 + <id>.jpg and puts the final start/end back into clips.json.

Layouts (per clip, "layout"):  blur = whole frame in the middle over a blurred copy (default; keeps both speakers)
                               crop = fills the screen; "xpos" 0..1 picks which part of the frame stays (0.5 = centre)
"""
import argparse
from pathlib import Path
from common import run, need, load, save
from captions import build_track

CAP_Y = 1360  # top of the caption strip (the strip is 300 px tall)


def snap(words, start, end):
    """Move the cut to real word edges so no word is chopped in half."""
    ws = [w for w in words if w["e"] > start - 0.4 and w["s"] < end + 0.4]
    if ws:
        first = next((w for w in ws if w["s"] >= start - 0.25), ws[0])
        last = [w for w in ws if w["e"] <= end + 0.25][-1] if any(w["e"] <= end + 0.25 for w in ws) else ws[-1]
        start, end = max(0, first["s"] - 0.12), last["e"] + 0.3
    return round(start, 2), round(end, 2)


def render(d, c, words, meta, captions=True):
    out = d / "clips"
    out.mkdir(exist_ok=True)
    c["start"], c["end"] = snap(words, float(c["start"]), float(c["end"]))
    dur = c["end"] - c["start"]
    layout, xpos = c.get("layout", "blur"), float(c.get("xpos", 0.5))
    vertical = meta.get("height", 0) > meta.get("width", 1)
    if layout == "crop" or vertical:
        base = f"[0:v]scale=-2:1920,crop=1080:1920:(iw-1080)*{xpos}:0[base]"
    else:
        base = ("[0:v]split=2[a][b];[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,gblur=sigma=6,"
                "scale=1080:1920,eq=brightness=-0.15[bg];[b]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[base]")
    cmd = ["ffmpeg", "-y", "-ss", str(c["start"]), "-t", f"{dur:.2f}", "-i", str(d / "source.mp4")]
    if captions and words:
        track = build_track(words, c["start"], c["end"], d / "work" / c["id"])
        cmd += ["-f", "concat", "-safe", "0", "-i", str(track)]
        fc = f"{base};[1:v]fps=30,format=rgba[cap];[base][cap]overlay=0:{CAP_Y}:shortest=1,format=yuv420p[v]"
    else:
        fc = f"{base};[base]format=yuv420p[v]"
    cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "0:a:0", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000",
            "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", "-t", f"{dur:.2f}", str(out / f"{c['id']}.mp4")]
    run(cmd)
    run(["ffmpeg", "-y", "-ss", "1.5", "-i", str(out / f"{c['id']}.mp4"), "-frames:v", "1", "-q:v", "3", str(out / f"{c['id']}.jpg")])
    return c


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--only")
    ap.add_argument("--no-captions", action="store_true")
    a = ap.parse_args()
    need("ffmpeg", "brew install ffmpeg")
    d = Path(a.dir)
    clips, words, meta = load(d / "clips.json"), load(d / "words.json", []), load(d / "meta.json", {})
    only = set(a.only.split(",")) if a.only else None
    for i, c in enumerate(clips, 1):
        if only and c["id"] not in only:
            continue
        print(f"[{i}/{len(clips)}] {c['id']}  {c.get('title', '')}", flush=True)
        render(d, c, words, meta, not a.no_captions)
        save(d / "clips.json", clips)
    print(f"DONE {d / 'clips'}")
