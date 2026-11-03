"""Shared helpers for the youtube-clipper scripts."""
import json, os, shutil, subprocess, sys
from pathlib import Path

HOME = Path.home()
MODEL_DIRS = [HOME / ".youtube-clipper" / "models", HOME / ".cache" / "hyperframes" / "whisper" / "models",
              HOME / ".cache" / "whisper", Path("/opt/homebrew/share/whisper-cpp/models")]
YELLOW = (254, 213, 12)


def run(cmd, **kw):
    """Run a command, stop with a clear message if it fails."""
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.exit(f"Command failed: {' '.join(map(str, cmd))}\n{r.stderr[-1500:]}")
    return r


def need(binary, how):
    path = shutil.which(binary)
    if not path:
        sys.exit(f"'{binary}' is not installed. Install it with:  {how}")
    return path


def load(path, default=None):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else default


def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False))


def fmt(t):
    t = int(t)
    return f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


def find_model(name=None):
    names = [name] if name else ["ggml-small.en.bin", "ggml-small.bin", "ggml-medium.en.bin", "ggml-medium.bin",
                                 "ggml-base.en.bin", "ggml-base.bin"]
    for d in MODEL_DIRS:
        for n in names:
            if (d / n).exists() and (d / n).stat().st_size > 10_000_000:
                return d / n
    return None
