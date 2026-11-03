#!/usr/bin/env python3
"""Check that everything the skill needs is installed. Prints the exact fix for anything missing."""
import shutil, sys
from common import find_model

ok = True


def line(name, good, fix=""):
    global ok
    print(("  OK       " if good else "  MISSING  ") + name + ("" if good else f"   ->  {fix}"))
    ok = ok and good


print("youtube-clipper setup check")
line("ffmpeg", bool(shutil.which("ffmpeg")), "brew install ffmpeg")
line("yt-dlp (only needed for links)", bool(shutil.which("yt-dlp")), "brew install yt-dlp   (or: pipx install yt-dlp)")
line("whisper-cli (transcription)", bool(shutil.which("whisper-cli")), "brew install whisper-cpp")
m = find_model()
line("a whisper model" + (f" ({m.name})" if m else ""), bool(m), "python3 scripts/transcribe.py --download-model small   (English: small.en)")
try:
    import PIL  # noqa
    line("Pillow (captions)", True)
except ImportError:
    line("Pillow (captions)", False, "python3 -m pip install --user pillow")
print("\nAll set." if ok else "\nInstall what is marked MISSING, then run this again.")
sys.exit(0 if ok else 1)
