"""Word-by-word captions drawn with Pillow (works on any ffmpeg, no libass needed)."""
import hashlib, html, os, shutil, subprocess, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, features
from common import YELLOW

CHROME = [os.environ.get("CHROME_PATH", ""), "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
          "/Applications/Chromium.app/Contents/MacOS/Chromium", "google-chrome", "chromium", "chrome"]

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


def _chrome():
    for c in CHROME:
        if c and (Path(c).exists() or shutil.which(c)):
            return c
    return None


def _latin(texts):
    return all(ord(c) < 0x250 for t in texts for c in t)


def draw_chrome(jobs, chrome, per_shot=40):
    """Draw caption pictures with Chrome's text engine. Pillow cannot shape Hindi (Devanagari) without libraqm,
    and Chrome can. One headless screenshot holds up to `per_shot` stacked pictures."""
    for i in range(0, len(jobs), per_shot):
        batch = jobs[i:i + per_shot]
        rows = "".join('<div class="s"><div class="r">' + "".join(
            f'<span{" class=a" if k == act else ""}>{html.escape(t.upper())}</span>' for k, t in enumerate(texts)) + "</div></div>"
            for _, texts, act in batch)
        page = f"""<!doctype html><meta charset="utf-8"><style>
html,body{{margin:0;background:transparent}}
.s{{width:{W}px;height:{H}px;display:flex;align-items:center;justify-content:center;overflow:hidden}}
.r{{display:inline-flex;gap:.28em;white-space:nowrap;font-family:"Arial Black","Kohinoor Devanagari","Devanagari Sangam MN",sans-serif;font-weight:900;font-size:92px;color:#fff}}
.r span{{-webkit-text-stroke:18px #000;paint-order:stroke fill}}.r .a{{color:rgb({YELLOW[0]},{YELLOW[1]},{YELLOW[2]})}}
</style>{rows}<script>document.querySelectorAll('.r').forEach(r=>{{let s=92;while(r.getBoundingClientRect().width>{W - 100}&&s>48){{s-=4;r.style.fontSize=s+'px'}}}})</script>"""
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "p.html").write_text(page, encoding="utf-8")
            shot = Path(t) / "shot.png"
            subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--default-background-color=00000000",
                            f"--user-data-dir={t}/profile", f"--window-size={W},{H * len(batch)}", "--virtual-time-budget=4000",
                            f"--screenshot={shot}", f"file://{t}/p.html"], capture_output=True, timeout=180)
            if not shot.exists():
                raise RuntimeError("Chrome could not draw the captions")
            sheet = Image.open(shot).convert("RGBA")
            for k, (path, _, _) in enumerate(batch):
                sheet.crop((0, k * H, W, (k + 1) * H)).save(path)


def draw_all(jobs):
    """jobs = [(png path, [words], active index)]. Uses Pillow for Latin text, Chrome for Hindi etc."""
    jobs = [j for j in jobs if not Path(j[0]).exists()]
    wide = [j for j in jobs if not _latin(j[1])]
    chrome = _chrome() if wide and not features.check("raqm") else None
    if wide and not features.check("raqm") and not chrome:
        print("WARNING: this text needs Chrome (or Pillow with libraqm) to draw correctly; vowel marks may be misplaced.")
    if chrome and wide:
        draw_chrome(wide, chrome)
    for path, texts, act in jobs:
        if not Path(path).exists():
            draw_state(texts, act, path)


def build_track(words, clip_start, clip_end, folder):
    """Return the path of an ffconcat file that plays one PNG per spoken word over the clip's length."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    dur = clip_end - clip_start
    blank = folder / "blank.png"
    Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(blank)
    rel = [{"w": w["w"], "s": max(0, w["s"] - clip_start), "e": min(dur, w["e"] - clip_start)}
           for w in words if w["e"] > clip_start and w["s"] < clip_end]
    segs, t, to_draw = [], 0.0, []
    for ch in chunks(rel):
        for i, w in enumerate(ch):
            s = max(w["s"], t)
            end = ch[i + 1]["s"] if i + 1 < len(ch) else min(w["e"] + 0.15, dur)
            end = max(end, s + 0.05)
            if s > t + 0.01:
                segs.append((blank, s - t))
            key = hashlib.md5((" ".join(x["w"] for x in ch) + str(i)).encode()).hexdigest()[:12]
            png = folder / f"{key}.png"
            to_draw.append((png, [x["w"] for x in ch], i))
            segs.append((png, end - s))
            t = end
    if dur > t:
        segs.append((blank, dur - t))
    draw_all(to_draw)
    lines = ["ffconcat version 1.0"]
    for p, d in segs:
        lines += [f"file '{p}'", f"duration {d:.3f}"]
    lines.append(f"file '{segs[-1][0]}'")
    track = folder / "captions.ffconcat"
    track.write_text("\n".join(lines))
    return track
