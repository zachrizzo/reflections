"""Builds ArtDirection/Cinematics/ContactSheet_<Name>.png from the PIE frames test_cutscenes_pie.py captured.
usage: python Tools/Cinematics/make_contact_sheet.py <Name> [<Name> ...]"""
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
ROOT = PROJECT / 'Saved' / 'CinematicsTest'
SHEETS = PROJECT / 'ArtDirection' / 'Cinematics'
LENGTHS = {'Intro': 48.0, 'BurningEyes': 36.0, 'FirstPage': 28.5, 'GiltTower': 35.5, 'MirrorWhole': 29.5, 'Ending': 46.0}


def sheet(name):
    from PIL import Image, ImageDraw, ImageFont
    folder = ROOT / name
    frames = sorted(folder.glob('frame_*.png'))
    if not frames:
        return 'no frames for %s' % name
    images = [Image.open(f).convert('RGB') for f in frames]
    w = 800
    h = int(images[0].height * w / images[0].width)
    cols = 2 if len(images) <= 4 else (3 if len(images) <= 6 else 4)
    rows = (len(images) + cols - 1) // cols
    pad, title = 12, 64
    canvas = Image.new('RGB', (cols * w + (cols + 1) * pad, rows * (h + pad) + pad + title), (12, 12, 18))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype('arial.ttf', 30)
        small = ImageFont.truetype('arial.ttf', 18)
    except Exception:
        font = small = ImageFont.load_default()
    report = {}
    try:
        report = json.loads((folder / 'report.json').read_text())
    except Exception:
        pass
    draw.text((pad, 16), 'Reflections - cutscene "%s"  (%s, PIE %s)' % (name, report.get('map', '').rsplit('/', 1)[-1].split('.')[0],
                                                                         report.get('started', '')), fill=(237, 227, 204), font=font)
    length = LENGTHS.get(name, 30.0)
    for i, im in enumerate(images):
        x = pad + (i % cols) * (w + pad)
        y = title + pad + (i // cols) * (h + pad)
        canvas.paste(im.resize((w, h)), (x, y))
        draw.text((x + 8, y + 6), '%.1f s' % (length * (i + 0.5) / 8.0), fill=(242, 184, 71), font=small)
    path = SHEETS / ('ContactSheet_%s.png' % name)
    canvas.save(path)
    return str(path)



if __name__ == '__main__':
    for n in sys.argv[1:]:
        print(sheet(n))
