#!/usr/bin/env python3
"""Step 2: word-level transcript with timestamps.

usage: transcribe.py DIR [--lang en|hi|auto] [--model PATH]
       transcribe.py --download-model small|small.en|medium|medium.en|base|base.en
Writes DIR/words.json  [{"w","s","e"}...]  and DIR/transcript.txt  ("[HH:MM:SS] sentence" lines for reading).
"""
import argparse, json, sys, tempfile, urllib.request
from pathlib import Path
from common import run, need, save, fmt, find_model, MODEL_DIRS

ap = argparse.ArgumentParser()
ap.add_argument("dir", nargs="?")
ap.add_argument("--lang", default="en")
ap.add_argument("--model")
ap.add_argument("--prompt", help="a sentence in the spoken style, e.g. Hinglish in Roman letters, to steer the spelling")
ap.add_argument("--download-model")
a = ap.parse_args()

if a.download_model:
    name = f"ggml-{a.download_model}.bin"
    dest = MODEL_DIRS[0]
    dest.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {name} from huggingface.co/ggerganov/whisper.cpp ...")
    urllib.request.urlretrieve(f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{name}", dest / name)
    print(f"Saved {dest / name}")
    sys.exit(0)

if not a.dir:
    ap.error("give the working folder")
d = Path(a.dir)
need("whisper-cli", "brew install whisper-cpp")
if a.model:
    model = Path(a.model)
elif a.lang == "en":
    model = find_model()
else:  # non-English needs a multilingual model (no ".en" in the name)
    model = find_model("ggml-small.bin") or find_model("ggml-medium.bin") or find_model("ggml-base.bin")
if not model:
    sys.exit("No suitable whisper model. Run: python3 scripts/transcribe.py --download-model " +
             ("small.en" if a.lang == "en" else "small"))
if a.lang != "en" and ".en" in model.name:
    sys.exit(f"{model.name} is English-only. For --lang {a.lang} download a multilingual model: --download-model small")

print(f"Transcribing with {model.name} (language: {a.lang}) ...")
with tempfile.TemporaryDirectory() as t:
    base = Path(t) / "out"
    run(["whisper-cli", "-m", str(model), "-f", str(d / "audio.wav"), "-l", a.lang, "-ml", "1", "-sow",
         "-oj", "-of", str(base), "-np"] + (["--prompt", a.prompt] if a.prompt else []))
    raw = json.loads(Path(str(base) + ".json").read_text())

words = []
for seg in raw["transcription"]:
    w = seg["text"].strip()
    if not w or (w.startswith("[") and w.endswith("]")) or (w.startswith("(") and w.endswith(")")):
        continue  # [MUSIC], (laughs) ...
    s, e = seg["offsets"]["from"] / 1000, seg["offsets"]["to"] / 1000
    if words and not w[0].isalnum() and w[0] not in "\"'(" and len(w) <= 2 and words[-1]["e"] >= s - 0.05:
        words[-1]["w"] += w  # stray punctuation token joins the word before it
        words[-1]["e"] = max(words[-1]["e"], e)
        continue
    words.append({"w": w, "s": round(s, 2), "e": round(max(e, s + 0.05), 2)})
save(d / "words.json", words)

lines, cur, start = [], [], None
for i, x in enumerate(words):
    if start is None:
        start = x["s"]
    cur.append(x["w"])
    nxt_gap = (words[i + 1]["s"] - x["e"]) if i + 1 < len(words) else 9
    if x["w"][-1] in ".?!" or nxt_gap > 0.8 or len(cur) >= 28:
        lines.append(f"[{fmt(start)}] {' '.join(cur)}")
        cur, start = [], None
if cur:
    lines.append(f"[{fmt(start)}] {' '.join(cur)}")
(d / "transcript.txt").write_text("\n".join(lines))
print(f"DONE {len(words)} words, {len(lines)} lines -> {d / 'transcript.txt'}")
