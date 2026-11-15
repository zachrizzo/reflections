"""Before/after contact sheet: ArtDirection/MockCity/Screenshots/<tag>.png (box city, 16:08) vs shots_city/<tag>.png
(city kit). Copies the after shots to Screenshots/CityKit/ and writes Screenshots/CityKit/00_before_after.png."""
import os
import shutil
from PIL import Image, ImageDraw, ImageFont

PROJ = r'C:\Users\zachc\Documents\Unreal Projects\reflections\ArtDirection\MockCity\Screenshots'
SP = os.path.dirname(os.path.abspath(__file__))
AFTER = os.path.join(SP, 'shots_city')
OUT = os.path.join(PROJ, 'CityKit')
os.makedirs(OUT, exist_ok=True)
TAGS = ['m01_gilt_start', 'm02_gilt_lantern_row', 'm03_gilt_bell_square', 'm07_gilt_lantern_gate',
        'm04_pew_weighhouse_corner', 'm05_pew_weighhouse_stair', 'm12_pew_coal_lane',
        'm11_frost_bone_market', 'm10_frost_crown_arena', 'f01_frost_north_street', 'f02_frost_bell_square']
TW, TH = 640, 360
try:
    font = ImageFont.truetype('arial.ttf', 22)
except OSError:
    font = ImageFont.load_default()
rows = []
for tag in TAGS:
    a = os.path.join(AFTER, tag + '.png')
    if not os.path.exists(a):
        continue
    shutil.copy(a, os.path.join(OUT, tag + '.png'))
    b = os.path.join(PROJ, tag + '.png')
    rows.append((tag, b if os.path.exists(b) else None, a))
sheet = Image.new('RGB', (TW * 2 + 30, len(rows) * (TH + 40) + 50), (24, 24, 26))
d = ImageDraw.Draw(sheet)
d.text((10, 12), 'BEFORE: box city (16:08)', fill=(230, 230, 230), font=font)
d.text((TW + 20, 12), 'AFTER: Codex city kit', fill=(230, 230, 230), font=font)
for i, (tag, b, a) in enumerate(rows):
    y = 50 + i * (TH + 40)
    d.text((10, y), tag, fill=(200, 200, 200), font=font)
    for j, path in enumerate((b, a)):
        x = 10 + j * (TW + 10)
        if path:
            im = Image.open(path).convert('RGB')
            im.thumbnail((TW, TH))
            sheet.paste(im, (x, y + 28))
        else:
            d.text((x + 20, y + 150), '(no before shot: new angle)', fill=(150, 150, 150), font=font)
sheet.save(os.path.join(OUT, '00_before_after.png'))
print('pairs', len(rows), '->', os.path.join(OUT, '00_before_after.png'))
