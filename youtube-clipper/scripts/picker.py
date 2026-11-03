#!/usr/bin/env python3
"""Step 5: open the clip page in your browser (runs only on your computer).

usage: picker.py DIR [--port 8765] [--no-open]
Shows every finished clip as a card: preview, score, why it was picked, a trim nudge, a layout switch,
caption text to copy, a Keep tick and a download button. 'Re-render' rebuilds one clip after you nudge it.
"""
import argparse, io, json, threading, webbrowser, zipfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from common import load, save
from render import render

PAGE = Path(__file__).with_name("picker.html")


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
            if self.path in ("/", "/index.html"):
                return self._send(PAGE.read_bytes(), "text/html; charset=utf-8")
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
