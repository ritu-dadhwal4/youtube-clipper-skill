"""Word-by-word captions drawn with Pillow (works on any ffmpeg, no libass needed)."""
import hashlib
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from common import YELLOW

W, H = 1080, 300
LATIN = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
WIDE = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"


def _font(text, size):
    path = LATIN if all(ord(c) < 0x250 for c in text) else WIDE
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def chunks(words, max_words=3, max_chars=22, gap=0.55):
    out, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_words or sum(len(x["w"]) + 1 for x in cur) + len(w["w"]) > max_chars
                    or w["s"] - cur[-1]["e"] > gap or cur[-1]["w"][-1] in ".?!"):
            out.append(cur)
            cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return out


def draw_state(texts, active, path, upper=True):
    texts = [t.upper() if upper else t for t in texts]
    size = 92
    while True:
        font = _font("".join(texts), size)
        widths = [font.getlength(t) for t in texts]
        space = font.getlength(" ")
        total = sum(widths) + space * (len(texts) - 1)
        if total <= W - 100 or size <= 48:
            break
        size -= 4
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = (W - total) / 2
    for i, t in enumerate(texts):
        d.text((x, H / 2), t, font=font, anchor="lm", fill=YELLOW + (255,) if i == active else (255, 255, 255, 255),
               stroke_width=9, stroke_fill=(0, 0, 0, 255))
        x += widths[i] + space
    img.save(path)


def build_track(words, clip_start, clip_end, folder):
    """Return the path of an ffconcat file that plays one PNG per spoken word over the clip's length."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    dur = clip_end - clip_start
    blank = folder / "blank.png"
    Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(blank)
    rel = [{"w": w["w"], "s": max(0, w["s"] - clip_start), "e": min(dur, w["e"] - clip_start)}
           for w in words if w["e"] > clip_start and w["s"] < clip_end]
    segs, t = [], 0.0
    for ch in chunks(rel):
        for i, w in enumerate(ch):
            s = max(w["s"], t)
            end = ch[i + 1]["s"] if i + 1 < len(ch) else min(w["e"] + 0.15, dur)
            end = max(end, s + 0.05)
            if s > t + 0.01:
                segs.append((blank, s - t))
            key = hashlib.md5((" ".join(x["w"] for x in ch) + str(i)).encode()).hexdigest()[:12]
            png = folder / f"{key}.png"
            if not png.exists():
                draw_state([x["w"] for x in ch], i, png)
            segs.append((png, end - s))
            t = end
    if dur > t:
        segs.append((blank, dur - t))
    lines = ["ffconcat version 1.0"]
    for p, d in segs:
        lines += [f"file '{p}'", f"duration {d:.3f}"]
    lines.append(f"file '{segs[-1][0]}'")
    track = folder / "captions.ffconcat"
    track.write_text("\n".join(lines))
    return track
