#!/usr/bin/env python3
"""Step 5: cut the chosen moments into finished 1080x1920 clips.

usage: render.py DIR [--only c1,c3]
Reads DIR/clips.json (the list Claude wrote), DIR/words.json and DIR/source.mp4.
Writes DIR/clips/<id>.mp4 + <id>.jpg and puts the final start/end back into clips.json.

Per-clip options in clips.json (all optional):
  layout   fill  = fills the screen, centred on the speaker's face (default)
           blur  = whole frame in the middle over a blurred copy of itself
           brand = whole frame in the middle over a solid colour
           card  = hook text on top, the video in a tall rounded card, over a solid colour
  zoom     1.0-1.6, how far to zoom in for fill and card (default 1.0)
  xpos,ypos  pin the crop to one spot, 0-1. Leave out to follow the speaker's face automatically
  bg       background colour for brand and card, e.g. "#FED50C" (default)
  hook     headline text. Always shown in card; in the other layouts it shows for the first 4.5 seconds
  captions "original" (the spoken words, default) | "none" | "set:<name>" (lines from caption_sets[name])
"""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw
from common import run, need, load, save
from captions import build_track, build_line_track, hook_png
from face import track_face, x_expr

CAP_Y = 1360                      # top of the 300 px caption strip
CARD_W, CARD_H, CARD_X, CARD_Y = 900, 1150, 90, 520
HOOK_SECONDS = 4.5


def snap(words, start, end):
    """Move the cut to real word edges so no word is chopped in half."""
    ws = [w for w in words if w["e"] > start - 0.4 and w["s"] < end + 0.4]
    if ws:
        first = next((w for w in ws if w["s"] >= start - 0.25), ws[0])
        last = [w for w in ws if w["e"] <= end + 0.25][-1] if any(w["e"] <= end + 0.25 for w in ws) else ws[-1]
        start, end = max(0, first["s"] - 0.12), last["e"] + 0.3
    return round(start, 2), round(end, 2)


def hex_rgb(h):
    h = (h or "#FED50C").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (254, 213, 12)


def is_light(rgb):
    return (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) > 150


def fillcrop(w, h, zoom, fx, fy):
    """Scale the source to cover w x h (times zoom), then crop w x h around the face. fx is a number or an
    expression of time t (a moving face); fy a number."""
    return (f"scale={int(w * zoom)}:{int(h * zoom)}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h}:'min(max(iw*{fx}-{w / 2},0),iw-{w})':'min(max(ih*{fy}-{h * 0.38:.0f},0),ih-{h})'")


def render(d, c, words, meta, quiet=False):
    out, work = d / "clips", d / "work" / c["id"]
    out.mkdir(exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    c["start"], c["end"] = snap(words, float(c["start"]), float(c["end"]))
    dur = c["end"] - c["start"]
    layout = c.get("layout", "fill")
    if layout == "crop":      # old name
        layout = "fill"
    if meta.get("height", 0) > meta.get("width", 1) and layout in ("blur", "brand"):
        layout = "fill"       # already vertical: nothing to letterbox
    zoom = min(1.6, max(1.0, float(c.get("zoom", 1.0))))
    fx, fy = c.get("xpos"), c.get("ypos")
    if layout in ("fill", "card") and (fx is None or fy is None):
        # no position chosen: follow the face (saved in the clip so a re-render does not search again)
        if not c.get("track") or c.get("track_for") != [c["start"], c["end"]]:
            c["track"], c["track_for"] = track_face(d / "source.mp4", c["start"], c["end"]), [c["start"], c["end"]]
            if not quiet:
                print("    face:", "followed" if c["track"] else "not found, centring")
        tr = c.get("track")
        fx_val = x_expr(tr["x"]) if tr else 0.5
        fy = tr["y"] if tr else 0.4
    else:
        fx_val, fy = (0.5 if fx is None else float(fx)), (0.4 if fy is None else float(fy))
    c["layout"] = layout

    bg = hex_rgb(c.get("bg"))
    hook = (c.get("hook") or "").strip()
    cmd = ["ffmpeg", "-y", "-ss", str(c["start"]), "-t", f"{dur:.2f}", "-i", str(d / "source.mp4")]
    n, parts = 1, []

    def add(args):
        nonlocal n
        cmd.extend(args)
        n += 1
        return n - 1

    bgcol = f"0x{bg[0]:02x}{bg[1]:02x}{bg[2]:02x}"
    if layout == "blur":
        parts.append("[0:v]split=2[a][b];[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,gblur=sigma=6,"
                     "scale=1080:1920,eq=brightness=-0.15[bg];[b]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[base]")
    elif layout == "brand":
        i = add(["-f", "lavfi", "-t", f"{dur:.2f}", "-i", f"color=c={bgcol}:s=1080x1920:r=30"])
        parts.append(f"[0:v]scale=1080:-2[fg];[{i}:v][fg]overlay=(W-w)/2:(H-h)/2[base]")
    elif layout == "card":
        i = add(["-f", "lavfi", "-t", f"{dur:.2f}", "-i", f"color=c={bgcol}:s=1080x1920:r=30"])
        mask = Image.new("L", (CARD_W, CARD_H), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, CARD_W - 1, CARD_H - 1), radius=48, fill=255)
        mask.save(work / "card-mask.png")
        m = add(["-loop", "1", "-framerate", "30", "-t", f"{dur:.2f}", "-i", str(work / "card-mask.png")])
        parts.append(f"[0:v]{fillcrop(CARD_W, CARD_H, zoom, fx_val, fy)},format=yuva420p[cv];[{m}:v]format=gray[m];"
                     f"[cv][m]alphamerge[card];[{i}:v][card]overlay={CARD_X}:{CARD_Y}[base]")
    else:  # fill
        parts.append(f"[0:v]{fillcrop(1080, 1920, zoom, fx_val, fy)}[base]")
    last = "base"

    if hook or layout == "card":
        text = hook or "Your hook here"
        light_bg = layout in ("brand", "card") and is_light(bg)
        on_card = layout == "card"
        fg = "#17150f" if (on_card and light_bg) else "#ffffff"
        height, y = (380, 110) if on_card else (330, 140)
        hook_png(text, work / "hook.png", fg=fg, outline=not on_card, h=height)
        h = add(["-loop", "1", "-framerate", "30", "-t", f"{dur:.2f}", "-i", str(work / "hook.png")])
        en = "" if on_card else f":enable='lt(t,{HOOK_SECONDS})'"
        parts.append(f"[{h}:v]format=rgba[hk];[{last}][hk]overlay=0:{y}{en}[hooked]")
        last = "hooked"

    mode = c.get("captions", "original")
    track = None
    if mode == "original" and words:
        track = build_track(words, c["start"], c["end"], work)
    elif mode.startswith("set:"):
        lines = (c.get("caption_sets") or {}).get(mode[4:])
        if lines:
            track = build_line_track(lines, c["start"], c["end"], work)
    if track:
        k = add(["-f", "concat", "-safe", "0", "-i", str(track)])
        parts.append(f"[{k}:v]fps=30,format=rgba[cap];[{last}][cap]overlay=0:{CAP_Y}:shortest=1,format=yuv420p[v]")
    else:
        parts.append(f"[{last}]format=yuv420p[v]")

    cmd += ["-filter_complex", ";".join(parts), "-map", "[v]", "-map", "0:a:0", "-af",
            "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000", "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{dur:.2f}", str(out / f"{c['id']}.mp4")]
    run(cmd)
    run(["ffmpeg", "-y", "-ss", "1.5", "-i", str(out / f"{c['id']}.mp4"), "-frames:v", "1", "-q:v", "3", str(out / f"{c['id']}.jpg")])
    return c


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--only")
    a = ap.parse_args()
    need("ffmpeg", "brew install ffmpeg")
    d = Path(a.dir)
    clips, words, meta = load(d / "clips.json"), load(d / "words.json", []), load(d / "meta.json", {})
    only = set(a.only.split(",")) if a.only else None
    for i, c in enumerate(clips, 1):
        if only and c["id"] not in only:
            continue
        print(f"[{i}/{len(clips)}] {c['id']}  {c.get('title', '')}", flush=True)
        render(d, c, words, meta)
        save(d / "clips.json", clips)
    print(f"DONE {d / 'clips'}")
