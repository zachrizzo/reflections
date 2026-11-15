"""Two-angle check of the soldiers' hand grip, from author_melee_kimodo.py's grip_check output.

python draw_grip_sheet.py <grip.json> <out.png>
For each hand: a side view looking down the handle (along x palm), where the fingers should wrap the 3 cm circle, and a
palm view (along x across), where the four fingers should fold over the handle and the thumb close across them. Grey is
the reference (open) hand, orange the grip, blue the handle.
"""
import json
import sys

from PIL import Image, ImageDraw, ImageFont

COLOURS = {'index': (255, 170, 90), 'middle': (255, 200, 120), 'ring': (240, 150, 80), 'pinky': (220, 130, 70),
           'thumb': (120, 220, 255)}


def font(size, bold=False):
    for name in (('segoeuib.ttf' if bold else 'segoeui.ttf'), 'arial.ttf', 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def panel(d, x0, y0, size, hand, axes, title, scale=22.0):
    """axes: indices into (along, across, palm) for the panel's right and up directions."""
    d.rectangle([x0, y0, x0 + size, y0 + size], fill=(14, 16, 22))
    d.text((x0 + 10, y0 + 8), title, fill=(235, 235, 235), font=font(17, True))
    cx, cy = x0 + size * 0.45, y0 + size * 0.55
    to_px = lambda p: (cx + p[axes[0]] * scale, cy - p[axes[1]] * scale)
    # 1 cm grid ticks
    for k in range(-6, 7):
        d.line([to_px([k if i == axes[0] else 0 for i in range(3)]), to_px([k if i == axes[0] else 0.25 for i in range(3)])],
               fill=(60, 64, 76))
    h = hand['handle_centre']
    r = hand['radius'] * scale
    hx, hy = to_px(h)
    if 1 not in axes:  # side view: the handle is a circle
        d.ellipse([hx - r, hy - r, hx + r, hy + r], outline=(90, 160, 255), width=3)
    else:  # palm view: the handle is a band across the hand
        other = axes[1] if axes[0] == 1 else axes[0]
        a = [0, 0, 0]
        a[other] = h[other] - hand['radius']
        b = [0, 0, 0]
        b[other] = h[other] + hand['radius']
        for p, q in ((a, b),):
            pa, pb = list(p), list(q)
            pa[1], pb[1] = -5.0, 5.0
            ax_, ay_ = to_px(pa)
            bx_, by_ = to_px(pb)
            d.rectangle([min(ax_, bx_), min(ay_, by_), max(ax_, bx_), max(ay_, by_)], outline=(90, 160, 255), width=2)
    wx, wy = to_px(hand['wrist'])
    d.ellipse([wx - 5, wy - 5, wx + 5, wy + 5], fill=(200, 200, 200))
    for finger, pts in hand['ref'].items():
        d.line([to_px(hand['wrist'])] + [to_px(p) for p in pts], fill=(90, 90, 100), width=2)
    for finger, pts in hand['grip'].items():
        d.line([to_px(hand['wrist'])] + [to_px(p) for p in pts], fill=COLOURS[finger], width=4, joint='curve')
        tx, ty = to_px(pts[-1])
        d.ellipse([tx - 4, ty - 4, tx + 4, ty + 4], fill=COLOURS[finger])


def main(src, dst):
    data = json.load(open(src))
    hands = data['draw']
    size, pad = 520, 8
    img = Image.new('RGB', (2 * size + 3 * pad, len(hands) * (size + pad) + pad + 70), (22, 22, 26))
    d = ImageDraw.Draw(img)
    fingers = data['fingers']
    summary = '  '.join('%s wrap %d deg, skin gap %.1f to %.1f cm' % (k, v['wrap_deg'], v['min_skin_gap_cm'], v['max_skin_gap_cm'])
                        for k, v in fingers.items() if isinstance(v, dict) and 'wrap_deg' in v and k.endswith('_r'))
    d.text((pad, 8), 'Grip check: %.0f cm handle (blue). Grey = open reference hand, orange = grip, blue line = thumb.'
           % data['handle_diameter_cm'], fill=(240, 240, 240), font=font(18, True))
    d.text((pad, 36), summary, fill=(200, 200, 200), font=font(14))
    for r, (side, hand) in enumerate(sorted(hands.items())):
        y = 70 + pad + r * (size + pad)
        name = 'Left' if side == 'l' else 'Right'
        panel(d, pad, y, size, hand, (0, 2), '%s hand: side view, looking down the handle' % name)
        panel(d, 2 * pad + size, y, size, hand, (1, 0), '%s hand: palm view' % name)
    img.save(dst, optimize=True)
    print(dst, img.size)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
