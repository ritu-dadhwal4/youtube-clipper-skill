"""Find where the speaker's face is, so a 'fill the screen' crop can follow it."""
import statistics, tempfile
from pathlib import Path
from common import run

FPS = 2          # face samples per second
DEADZONE = 0.07  # the crop only moves once the face is this far (fraction of frame width) from the middle of the crop


def track_face(source, start, end):
    """Return {"x": [[t, x], ...], "y": y} with x, y as fractions of the frame (0..1) and t in seconds from the clip
    start, one keyframe a second. The crop stays still while the speaker sits roughly in place and glides when they
    move. Returns None if no face is found or OpenCV is not installed."""
    try:
        import cv2
    except ImportError:
        return None
    dur = end - start
    with tempfile.TemporaryDirectory() as t:
        run(["ffmpeg", "-y", "-ss", str(start), "-t", f"{dur:.2f}", "-i", str(source), "-vf", f"fps={FPS},scale=640:-2",
             "-q:v", "4", f"{t}/f%04d.jpg"])
        casc = [cv2.CascadeClassifier(cv2.data.haarcascades + n) for n in
                ("haarcascade_frontalface_default.xml", "haarcascade_frontalface_alt2.xml")]
        pts = []
        for f in sorted(Path(t).glob("f*.jpg")):
            img = cv2.imread(str(f))
            if img is None:
                pts.append(None)
                continue
            h, w = img.shape[:2]
            gray = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
            faces = []
            for c in casc:
                faces = c.detectMultiScale(gray, 1.1, 5, minSize=(int(w * 0.05), int(w * 0.05)))
                if len(faces):
                    break
            if len(faces):
                x, y, fw, fh = max(faces, key=lambda r: r[2] * r[3])
                pts.append((float((x + fw / 2) / w), float((y + fh / 2) / h)))
            else:
                pts.append(None)
    seen = [p for p in pts if p]
    if len(seen) < 2:
        return None
    # fill gaps with the last known position, then smooth with a 2-second median
    xs, last = [], seen[0]
    for p in pts:
        last = p or last
        xs.append(last[0])
    sm = [statistics.median(xs[max(0, i - FPS):i + FPS + 1]) for i in range(len(xs))]
    # camera: stays put until the face drifts out of the dead zone, then moves to it
    cam, cams = sm[0], []
    for v in sm:
        if abs(v - cam) > DEADZONE:
            cam = v
        cams.append(cam)
    key = [[0.0, round(cams[0], 3)]]
    for s in range(1, int(dur) + 1):
        key.append([float(s), round(cams[min(len(cams) - 1, s * FPS)], 3)])
    return {"x": key, "y": round(statistics.median(p[1] for p in seen), 3)}


def x_expr(keys):
    """ffmpeg expression for x at time t: the first value plus one linear ramp per change, no nesting."""
    terms = [f"({b - a:.4f})*clip((t-{t1:.2f})/{t2 - t1:.2f},0,1)" for (t1, a), (t2, b) in zip(keys, keys[1:]) if abs(b - a) > 1e-3]
    return f"({keys[0][1]:.4f}" + "".join("+" + t for t in terms) + ")"
