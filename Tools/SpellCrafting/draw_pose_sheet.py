"""Stick-figure contact sheet from exported bone positions (poses.json from author_conversion_kimodo / the editor).

python draw_pose_sheet.py <poses.json> <out.png>
Each row is a clip, each column a time; 3/4 orthographic view (azimuth 40, elevation 20) of the UEFN mannequin in
component space, ground line at z=0, with a short tick showing which way the face points.
"""
import json
import math
import sys

from PIL import Image, ImageDraw, ImageFont

CHAINS = [
    ['pelvis', 'spine_01', 'spine_02', 'spine_03', 'spine_04', 'spine_05', 'neck_01', 'neck_02', 'head'],
    ['spine_05', 'clavicle_l', 'upperarm_l', 'lowerarm_l', 'hand_l'],
    ['spine_05', 'clavicle_r', 'upperarm_r', 'lowerarm_r', 'hand_r'],
    ['pelvis', 'thigh_l', 'calf_l', 'foot_l', 'ball_l'],
    ['pelvis', 'thigh_r', 'calf_r', 'foot_r', 'ball_r'],
]
AZ, EL = math.radians(40), math.radians(20)


def project(p):
    x, y, z = p
    u = x * math.cos(AZ) + y * math.sin(AZ)
    depth = -x * math.sin(AZ) + y * math.cos(AZ)
    v = z * math.cos(EL) - depth * math.sin(EL)
    return u, v


def font(size, bold=False):
    for name in (('segoeuib.ttf' if bold else 'segoeui.ttf'), 'arial.ttf', 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def main(src, dst):
    data = json.load(open(src))
    cell, label_w, head_h = 300, 210, 30
    cols = max(len(v) for v in data.values())
    img = Image.new('RGB', (label_w + cols * (cell + 6), head_h + len(data) * (cell + 6)), (22, 22, 26))
    d = ImageDraw.Draw(img)
    big, small = font(20, True), font(16)
    for r, (name, frames) in enumerate(data.items()):
        y0 = head_h + r * (cell + 6)
        d.text((10, y0 + cell // 2 - 12), name.replace('_', ' '), fill=(230, 230, 230), font=big)
        # One scale per row so motion between columns is comparable.
        pts = [project(p) for f in frames for p in f['pos'].values()]
        umin, umax = min(p[0] for p in pts), max(p[0] for p in pts)
        vmin, vmax = min(min(p[1] for p in pts), project((0, 0, 0))[1]), max(p[1] for p in pts)
        scale = (cell - 40) / max(umax - umin, vmax - vmin, 1.0)
        for c, f in enumerate(frames):
            x0 = label_w + c * (cell + 6)
            d.rectangle([x0, y0, x0 + cell, y0 + cell], fill=(14, 16, 22))

            def to_px(p):
                u, v = project(p)
                return (x0 + 20 + (u - umin) * scale + (cell - 40 - (umax - umin) * scale) / 2,
                        y0 + cell - 20 - (v - vmin) * scale)
            ground = [to_px((gx, gy, 0)) for gx, gy in ((-150, -150), (150, -150), (150, 150), (-150, 150))]
            d.polygon(ground, outline=(60, 64, 76))
            for chain in CHAINS:
                d.line([to_px(f['pos'][b]) for b in chain], fill=(255, 170, 90), width=4, joint='curve')
            hx, hy = to_px(f['pos']['head'])
            d.ellipse([hx - 9, hy - 9, hx + 9, hy + 9], outline=(255, 210, 160), width=3)
            face_tip = [f['pos']['head'][i] + f['face'][i] * 22 for i in range(3)]
            d.line([(hx, hy), to_px(face_tip)], fill=(120, 220, 255), width=3)
            d.text((x0 + 8, y0 + 6), '%.2f s' % f['t'], fill=(255, 255, 255), font=small)
    img.save(dst, optimize=True)
    print(dst, img.size)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
