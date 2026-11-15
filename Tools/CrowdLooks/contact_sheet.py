"""Contact sheet from audit captures: python contact_sheet.py <folder> <out.png> [prefix] [cols] [verdicts.json]

Each tile is the face close-up above the body shot, captioned with the look name and (optionally) its verdict.
"""
import glob
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

folder, out = sys.argv[1], sys.argv[2]
prefix = sys.argv[3] if len(sys.argv) > 3 else ''
cols = int(sys.argv[4]) if len(sys.argv) > 4 else 6
verdicts = json.load(open(sys.argv[5])) if len(sys.argv) > 5 else {}

faces = sorted(glob.glob(os.path.join(folder, prefix + '*_face.png')))
TW, FH, BH, CAP = 300, 300, 450, 54
try:
    font = ImageFont.truetype('arial.ttf', 15)
    small = ImageFont.truetype('arial.ttf', 13)
except Exception:
    font = small = ImageFont.load_default()
rows = (len(faces) + cols - 1) // cols
sheet = Image.new('RGB', (cols * TW, rows * (FH + BH + CAP)), (24, 24, 28))
d = ImageDraw.Draw(sheet)
COLORS = {'complete': (90, 200, 110), 'ok': (90, 200, 110)}
for i, fp in enumerate(faces):
    x, y = (i % cols) * TW, (i // cols) * (FH + BH + CAP)
    stem = os.path.basename(fp)[:-len('_face.png')]
    sheet.paste(Image.open(fp).convert('RGB').resize((TW, FH)), (x, y))
    bp = fp.replace('_face.png', '_body.png')
    if os.path.exists(bp):
        b = Image.open(bp).convert('RGB')
        b = b.resize((int(b.width * BH / b.height), BH))
        sheet.paste(b, (x + (TW - b.width) // 2, y + FH))
    name = stem.split('_', 2)[-1] if stem.count('_') >= 2 else stem
    v = verdicts.get(stem) or verdicts.get(name) or ''
    d.text((x + 6, y + FH + BH + 4), name[:36], fill=(235, 235, 235), font=font)
    if v:
        col = COLORS.get(v.split(':')[0].strip().lower(), (235, 110, 90))
        d.text((x + 6, y + FH + BH + 24), v[:44], fill=col, font=small)
sheet.save(out)
print(out, len(faces))
