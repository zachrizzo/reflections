"""Quick shaded previews of a garment on the captured source body (no Unreal, no Blender).

  python preview.py <garment npz with P and F (or P0/P)> <capture folder> <out.png> [title] [--before]
Crossing triangles are painted magenta. Views: front, back, back from above, side.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contact
from meshops import read_surface

SKIN, UNDER, CLOTH = (214, 160, 120), (120, 124, 118), (196, 96, 48)
VIEWS = [(0, 5, "front"), (180, 10, "back"), (180, 55, "back, from above"), (90, 5, "side")]


def samples(P, F, px, colors, light):
    a, b, c = P[F].transpose(1, 0, 2)
    n = np.cross(b - a, c - a)
    area = .5 * np.linalg.norm(n, axis=1)
    n /= np.maximum(2 * area, 1e-12)[:, None]
    k = np.clip(np.ceil(area / (px * px) * 2.2).astype(int), 1, 400)
    idx = np.repeat(np.arange(len(F)), k)
    r = np.random.default_rng(0).random((len(idx), 2))
    s = np.sqrt(r[:, 0])
    pts = a[idx] * (1 - s)[:, None] + b[idx] * (s * (1 - r[:, 1]))[:, None] + c[idx] * (s * r[:, 1])[:, None]
    shade = .35 + .65 * np.abs(n @ light)
    col = (np.asarray(colors, float) if np.ndim(colors) == 2 else np.tile(np.asarray(colors, float), (len(F), 1))) * shade[:, None]
    return pts, col[idx]


def render(parts, az, el, center, half, px=.11, bg=(236, 238, 242)):
    a, e = np.radians(az), np.radians(el)
    fwd = np.array([np.sin(a) * np.cos(e), np.cos(a) * np.cos(e), np.sin(e)])
    right = np.cross([0, 0, 1.], fwd); right /= np.linalg.norm(right)
    up = np.cross(fwd, right)
    right = -right
    light = fwd * .8 + up * .5 + right * .3
    light /= np.linalg.norm(light)
    W, H = int(2 * half[0] / px), int(2 * half[1] / px)
    pts, cols = zip(*[samples(P, F, px, col, light) for P, F, col in parts])
    p = np.vstack(pts) - center
    c = np.vstack(cols)
    x = ((p @ right + half[0]) / px).astype(int)
    y = ((half[1] - p @ up) / px).astype(int)
    d = p @ fwd
    ok = (x >= 0) & (x < W) & (y >= 0) & (y < H)
    x, y, d, c = x[ok], y[ok], d[ok], c[ok]
    o = np.argsort(d)
    img = np.empty((H, W, 3)); img[:] = bg
    img[y[o], x[o]] = c[o]
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def sheet(P, F, capture, title, under="bottom", color=CLOTH):
    body, bf = read_surface(capture / "standing_body.bin")
    face, ff = read_surface(capture / "standing_face.bin")
    skin = np.vstack((body, face)); sf = np.vstack((bf, ff + len(body)))
    lo, hi = P.min(0) - 26, P.max(0) + 30
    near = sf[np.all((skin[sf] >= lo) & (skin[sf] <= hi), axis=(1, 2))]
    crossing, _ = contact.crossing_triangles(skin, sf, P, F)
    col = np.tile(np.array(color, float), (len(F), 1))
    col[crossing] = (255, 0, 200)
    parts = [(skin, near, SKIN), (P, F, col)]
    if under and (capture / f"standing_{under}.bin").exists():
        up, uf = read_surface(capture / f"standing_{under}.bin")
        parts.insert(1, (up, uf[np.all(up[uf] >= lo, axis=(1, 2))], UNDER))
    center = (P.min(0) + P.max(0)) / 2
    half = (max(34., np.ptp(P[:, 0]) / 2 + 10), max(36., np.ptp(P[:, 2]) / 2 + 12))
    images = [render(parts, az, el, center, half) for az, el, _ in VIEWS]
    out = Image.new("RGB", (sum(i.width for i in images), images[0].height + 54), (255, 255, 255))
    draw = ImageDraw.Draw(out)
    draw.text((8, 6), f"{title}: {len(crossing)} garment triangles cross skin (magenta)", fill=(0, 0, 0))
    x = 0
    for im, (_, _, label) in zip(images, VIEWS):
        out.paste(im, (x, 54)); draw.text((x + 8, 30), label, fill=(40, 40, 40)); x += im.width
    return out, len(crossing)


if __name__ == "__main__":
    data = np.load(sys.argv[1])
    key = "P0" if "--before" in sys.argv and "P0" in data else "P"
    title = sys.argv[4] if len(sys.argv) > 4 and not sys.argv[4].startswith("--") else Path(sys.argv[1]).stem
    image, count = sheet(data[key], data["F"], Path(sys.argv[2]), title, under=None if "--no-under" in sys.argv else "bottom")
    image.save(sys.argv[3])
    print("crossing triangles", count)
