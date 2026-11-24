"""Render clean orthographic tailor-form silhouette guides of the source body (Barnaby) in A-pose.

  python body_silhouette.py [source_body_folder] [out_folder]

Writes Barnaby_Top_Template.png and Barnaby_Bottom_Template.png (1024x1024, clean flat orthographic
silhouette with no face or hands/feet, cropped cleanly to the garment region). Used as a proportion
and pose guide for image generation so generated garments match Barnaby's exact A-pose (shoulder
width, arm angle, sleeve length, waist, crotch rise, leg length) before image-to-3D even runs.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from meshops import read_surface


def render_silhouette(body_p, body_f, joints, kind, out_path, size=1024):
    # Project body triangles orthogonally onto front plane (-X right, +Z up) and rasterize cleanly via PIL polygon fill
    if kind == "top":
        z_hi = float(joints["neck_01"][2]) + 10.0
        z_lo = float(joints["pelvis"][2]) - 18.0
        half_w = max(abs(float(joints["hand_l"][0])), abs(float(joints["hand_r"][0]))) + 16.0
        # Trim above neck_01, below pelvis-12, and past wrists so silhouette matches exact top-garment coverage
        wr_l, el_l = joints["hand_l"], joints["lowerarm_l"]
        wr_r, el_r = joints["hand_r"], joints["lowerarm_r"]
        u_l = (wr_l - el_l) / np.linalg.norm(wr_l - el_l)
        u_r = (wr_r - el_r) / np.linalg.norm(wr_r - el_r)
        cen = body_p[body_f].mean(1)
        keep = ((cen[:, 2] <= float(joints["neck_01"][2]) - 0.5)
                & (cen[:, 2] >= float(joints["pelvis"][2]) - 10.0)
                & (((cen - wr_l) @ u_l) <= 1.5)
                & (((cen - wr_r) @ u_r) <= 1.5))
    elif kind == "cloak":
        z_hi = float(joints["neck_01"][2]) + 10.0
        calf_z = min(float(joints["calf_l"][2]), float(joints["calf_r"][2]))
        z_lo = calf_z - 4.0
        half_w = 56.0
        cen = body_p[body_f].mean(1)
        sh_x = max(abs(float(joints["upperarm_l"][0])), abs(float(joints["upperarm_r"][0]))) + 6.5
        keep = ((cen[:, 2] <= float(joints["neck_01"][2]) - 0.5)
                & (cen[:, 2] >= calf_z + 10.0)
                & (np.abs(cen[:, 0]) <= sh_x))
    else:
        z_hi = float(joints["pelvis"][2]) + 20.0
        z_lo = max(0.0, min(float(joints["foot_l"][2]), float(joints["foot_r"][2])) - 10.0)
        half_w = 50.0
        cen = body_p[body_f].mean(1)
        foot_z = min(float(joints["foot_l"][2]), float(joints["foot_r"][2])) + 3.0
        keep = ((cen[:, 2] <= float(joints["pelvis"][2]) + 11.0)
                & (cen[:, 2] >= foot_z)
                & (np.abs(cen[:, 0]) < 28.0))

    z_mid = 0.5 * (z_hi + z_lo)
    half = max(half_w, 0.5 * (z_hi - z_lo) + 4.0)
    px = (2.0 * half) / size

    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    tris = body_p[body_f[keep]]
    sx = ((-tris[:, :, 0]) + half) / px
    sy = (half - (tris[:, :, 2] - z_mid)) / px
    for i in range(len(tris)):
        draw.polygon([(float(sx[i, 0]), float(sy[i, 0])),
                      (float(sx[i, 1]), float(sy[i, 1])),
                      (float(sx[i, 2]), float(sy[i, 2]))], fill=255)
    # Slight smooth closing + ease expansion so silhouette shows the tailored garment outline
    ease_cm = 2.6 if kind == "cloak" else 1.4
    ease_px = max(2, int(round(ease_cm / px)))
    arr = np.asarray(mask) > 127
    if kind == "cloak":
        # Smooth draped cape silhouette from shoulder span down to hem (fills arm notches and thigh gap)
        ys = np.flatnonzero(arr.any(axis=1))
        if len(ys):
            y_top, y_bot = int(ys[0]), int(ys[-1])
            half_span = np.zeros(size, float)
            for y in range(y_top, y_bot + 1):
                xs = np.flatnonzero(arr[y])
                if len(xs):
                    half_span[y] = max(abs(xs[0] - size * 0.5), abs(xs[-1] - size * 0.5))
            # Monotonically non-decreasing from shoulders downward with gentle 5 cm cape flare toward hem
            y_sh = y_top + int(0.16 * (y_bot - y_top))
            max_w = half_span[y_top:y_sh + 1].max()
            for y in range(y_sh, y_bot + 1):
                t = (y - y_sh) / max(y_bot - y_sh, 1)
                target = max_w + (5.5 / px) * t
                half_span[y] = max(half_span[y], target)
            for y in range(y_top, y_bot + 1):
                hw = int(round(half_span[y]))
                if hw > 0:
                    x0 = max(0, int(size * 0.5 - hw))
                    x1 = min(size, int(size * 0.5 + hw))
                    arr[y, x0:x1] = True
    arr = ndimage.binary_closing(arr, iterations=2)
    dil = ndimage.binary_dilation(arr, iterations=ease_px)
    edge = dil & ~ndimage.binary_erosion(dil, iterations=2)

    bg = np.full((size, size, 3), [245, 243, 238], dtype=np.uint8)
    bg[dil] = [212, 214, 218]
    bg[edge] = [140, 144, 152]
    Image.fromarray(bg, "RGB").save(out_path)
    return out_path


def main():
    root = HERE.parents[2]
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "Saved/ClothingFit/SourceBody/Barnaby"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else src
    out.mkdir(parents=True, exist_ok=True)
    body_p, body_f = read_surface(src / "standing_body.bin")
    jdata = json.loads((src / "joints_local.json").read_text())
    joints = {k: np.asarray(v, float) for k, v in jdata.get("joints", jdata).items()}
    for kind in ("top", "bottom", "cloak"):
        target = out / f"Barnaby_{kind.capitalize()}_Template.png"
        render_silhouette(body_p, body_f, joints, kind, target)
        print("WROTE", target)


if __name__ == "__main__":
    main()
