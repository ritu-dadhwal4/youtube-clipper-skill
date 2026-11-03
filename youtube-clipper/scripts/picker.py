#!/usr/bin/env python3
"""Step 5: open the clip page in your browser (runs only on your computer).

usage: picker.py DIR [--port 8765] [--no-open]
Shows every finished clip as a card: preview, score, why it was picked, a trim nudge, a layout switch,
caption text to copy, a Keep tick and a download button. 'Re-render' rebuilds one clip after you nudge it.
"""
import argparse, io, json, re, shutil, subprocess, threading, webbrowser, zipfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from common import load, save
from render import render

PAGE = Path(__file__).with_name("picker.html")


def ask_claude(prompt):
    """One-shot question to the user's own Claude Code (`claude -p`), used for translations and hook ideas."""
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("Claude Code's 'claude' command was not found, so the page cannot translate. Ask Claude in your chat instead.")
    for model in ("sonnet", None):
        cmd = [exe, "-p"] + (["--model", model] if model else [])
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=180)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
    raise RuntimeError("Claude did not answer: " + (r.stderr or "")[-200:])


def json_list(text):
    m = re.search(r"\[.*\]", text, re.S)
    return json.loads(m.group(0)) if m else []


def caption_lines(words, start, end, max_words=6):
    """The clip's spoken words grouped into short caption lines with their times (source seconds)."""
    ws = [w for w in words if w["s"] >= start - 0.05 and w["s"] < end]
    lines, cur = [], []
    for i, w in enumerate(ws):
        cur.append(w)
        gap = (ws[i + 1]["s"] - w["e"]) if i + 1 < len(ws) else 9
        if len(cur) >= max_words or w["w"][-1] in ".?!\u0964" or gap > 0.5:
            lines.append({"s": cur[0]["s"], "e": cur[-1]["e"], "orig": " ".join(x["w"] for x in cur)})
            cur = []
    if cur:
        lines.append({"s": cur[0]["s"], "e": cur[-1]["e"], "orig": " ".join(x["w"] for x in cur)})
    merged = []   # a one-word line reads badly as a caption: fold it into its neighbour
    for l in lines:
        if merged and len(l["orig"].split()) < 2:
            merged[-1]["e"], merged[-1]["orig"] = l["e"], merged[-1]["orig"] + " " + l["orig"]
        else:
            merged.append(l)
    return merged


LANG_NOTE = {"English": "English", "Hindi": "Hindi in Devanagari script", "Hinglish": "Hinglish: Hindi written in Roman letters, the way people text it"}


def translate_clip(d, c, lang):
    lines = caption_lines(load(d / "words.json", []), c["start"], c["end"])
    numbered = "\n".join(f"{i + 1}. {l['orig']}" for i, l in enumerate(lines))
    out = json_list(ask_claude(
        f"These are numbered caption lines from a short video clip, in the original spoken language. Rewrite every line in {LANG_NOTE[lang]}.\n"
        "Rules: keep each line's meaning exactly (no added or dropped ideas, no softening); keep names, brands and numbers; "
        "keep each line short, at most 6 words or 32 characters where the meaning allows; one output line per input line, same order.\n"
        f"Reply with ONLY a JSON array of exactly {len(lines)} strings, nothing else.\n\n{numbered}"))
    if len(out) != len(lines):
        raise RuntimeError(f"Claude returned {len(out)} lines for {len(lines)}; try again.")
    return [{"s": l["s"], "e": l["e"], "t": str(t)} for l, t in zip(lines, out)]


def hooks_for(d, c, lang):
    text = " ".join(l["orig"] for l in caption_lines(load(d / "words.json", []), c["start"], c["end"]))
    where = "the same language as the clip is spoken in" if lang == "Original" else LANG_NOTE[lang]
    return [str(x) for x in json_list(ask_claude(
        f"Write 3 hook headlines for a short vertical video clip, in {where}. Each at most 8 words, made to make someone stop scrolling: "
        "a claim, a question or a number. They must be true to what is said in the clip; no false promises. "
        f"Reply with ONLY a JSON array of 3 strings.\n\nClip transcript:\n{text}"))][:3]


def make_handler(d):
    lock = threading.Lock()

    class H(SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(d), **k)

        def log_message(self, *a):
            pass

        def _send(self, body, ctype="application/json", code=200, extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self.path = self.path.split("?")[0]   # ignore ?v=2 style cache-busters
            if self.path in ("/", "/index.html"):
                return self._send(PAGE.read_bytes(), "text/html; charset=utf-8")
            if self.path.startswith("/assets/"):
                f = Path(__file__).with_name("assets") / Path(self.path).name
                return self._send(f.read_bytes(), "font/woff2") if f.exists() else self._send(b"", code=404)
            if self.path == "/api/state":
                return self._send(json.dumps({"meta": load(d / "meta.json", {}), "clips": load(d / "clips.json", [])}).encode())
            if self.path == "/api/zip":
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w") as z:
                    for c in load(d / "clips.json", []):
                        if c.get("keep", True) and (d / "clips" / f"{c['id']}.mp4").exists():
                            name = "".join(ch for ch in c.get("title", c["id"]) if ch.isalnum() or ch in " -_")[:50].strip() or c["id"]
                            z.write(d / "clips" / f"{c['id']}.mp4", f"{c['id']} {name}.mp4")
                return self._send(buf.getvalue(), "application/zip", extra={"Content-Disposition": 'attachment; filename="clips.zip"'})
            return super().do_GET()

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if self.path in ("/api/translate", "/api/hooks"):
                clip = next((x for x in load(d / "clips.json", []) if x["id"] == body.get("id")), None)
                if not clip:
                    return self._send(b'{"error":"unknown clip"}', code=404)
                clip["start"], clip["end"] = float(body.get("start", clip["start"])), float(body.get("end", clip["end"]))
                try:
                    result = translate_clip(d, clip, body["lang"]) if self.path == "/api/translate" else hooks_for(d, clip, body["lang"])
                except Exception as e:  # shown to the user in the page
                    return self._send(json.dumps({"error": str(e)}).encode(), code=500)
                with lock:
                    clips = load(d / "clips.json", [])
                    c = next(x for x in clips if x["id"] == body["id"])
                    if self.path == "/api/translate":
                        c.setdefault("caption_sets", {})[body["lang"]] = result
                    else:
                        c.setdefault("hook_options_by_lang", {})[body["lang"]] = result
                    save(d / "clips.json", clips)
                return self._send(json.dumps(result).encode())
            with lock:
                clips = load(d / "clips.json", [])
                c = next((x for x in clips if x["id"] == body.get("id")), None)
                if not c:
                    return self._send(b'{"error":"unknown clip"}', code=404)
                for k in ("title", "post", "keep", "layout", "zoom", "bg", "hook", "captions"):
                    if k in body:
                        c[k] = body[k]
                if self.path == "/api/rerender":
                    c["start"], c["end"] = float(body["start"]), float(body["end"])
                    c.pop("xpos", None)
                    c.pop("ypos", None)  # follow the face again
                    render(d, c, load(d / "words.json", []), load(d / "meta.json", {}))
                    c["v"] = c.get("v", 0) + 1
                save(d / "clips.json", clips)
            return self._send(json.dumps(c).encode())

    return H


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()
    d = Path(a.dir).resolve()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(d))
    url = f"http://127.0.0.1:{a.port}/"
    print(f"Clip page: {url}   (press Ctrl+C to stop)", flush=True)
    if not a.no_open:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
