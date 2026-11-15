"""Compares ground brightness 5 s after casting with the baseline capture taken before casting (same camera).

Usage: python compare_ground_glow.py Saved/SpellCombatTest/ground_<tag> [more dirs...]
For each case it tiles the ground band of the frame (below the horizon, above the HUD) into 10 x 4 tiles and reports
the mean luminance change per tile (0-255 scale). A light left on the ground shows up as several tiles brightened by
10+; a walking NPC usually moves one or two tiles either way. These numbers are evidence to read with the images.
"""
import json
import sys
from pathlib import Path

from PIL import Image


def luminance_tiles(path, cols=10, rows=4):
    im = Image.open(path).convert('RGB')
    w, h = im.size
    top, bottom = int(h * 0.36), int(h * 0.82)
    out = []
    for r in range(rows):
        for c in range(cols):
            box = (int(w * c / cols), top + int((bottom - top) * r / rows),
                   int(w * (c + 1) / cols), top + int((bottom - top) * (r + 1) / rows))
            px = list(im.crop(box).resize((16, 16)).getdata())
            out.append(sum(0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2] for p in px) / len(px))
    return out


def compare(folder):
    folder = Path(folder)
    report = json.loads((folder / 'report.json').read_text())
    result = {}
    for case, data in report.get('cases', {}).items():
        caps = data.get('captures', {})
        base, after = caps.get('baseline'), caps.get('after5s')
        if not base or not after:
            result[case] = 'missing capture'
            continue
        deltas = [round(a - b, 1) for a, b in zip(luminance_tiles(after), luminance_tiles(base))]
        result[case] = {'max_brighten': max(deltas), 'tiles_brightened_10plus': sum(d >= 10 for d in deltas),
                        'mean_delta': round(sum(deltas) / len(deltas), 2)}
    return {'tag': report.get('tag'), 'result': report.get('result'), 'failures': report.get('failures'), 'glow': result}


if __name__ == '__main__':
    for arg in sys.argv[1:]:
        print(json.dumps(compare(arg), indent=1))
