"""Tiles the aim-hold comparison captures into one labelled image per situation (run with the system Python + Pillow).

python tile_aim_compare.py <shots dir> <prefix> [<prefix> ...]
Expects <prefix>_<front|side>_<old|new>.png and writes <prefix>_compare.png: columns old | new, rows front | side.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont


def font(size):
    for name in ('segoeuib.ttf', 'arialbd.ttf', 'DejaVuSans-Bold.ttf'):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def tile(folder, prefix):
    cells = [[Image.open(os.path.join(folder, '%s_%s_%s.png' % (prefix, view, tag))).convert('RGB') for tag in ('old', 'new')]
             for view in ('front', 'side')]
    w, h = cells[0][0].size
    pad, head, side = 12, 64, 120
    out = Image.new('RGB', (side + 2 * w + 3 * pad, head + 2 * h + 3 * pad), (24, 24, 28))
    d = ImageDraw.Draw(out)
    big, small = font(34), font(26)
    for c, label in enumerate(('Old: original aim hold (now _V1)', 'New: aim hold V2 (live)')):
        d.text((side + pad + c * (w + pad) + 10, 14), label, fill=(235, 235, 235) if c else (235, 150, 140), font=big)
    for r, label in enumerate(('Front', 'Side\n(right)')):
        d.multiline_text((12, head + pad + r * (h + pad) + h // 2 - 30), label, fill=(220, 220, 220), font=small)
        for c in range(2):
            out.paste(cells[r][c], (side + pad + c * (w + pad), head + pad + r * (h + pad)))
    path = os.path.join(folder, prefix + '_compare.png')
    out.save(path, optimize=True)
    return path


if __name__ == '__main__':
    for p in sys.argv[2:]:
        print(tile(sys.argv[1], p))
