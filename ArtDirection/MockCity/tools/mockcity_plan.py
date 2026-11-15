"""Draws the mock Lanthorne plan (top view) from the same layout code the level builder uses, without Unreal.

python mockcity_plan.py <out.png> [markers_dir]
markers_dir holds Saved/MockCity_markers_<Side>.json from a build (optional): their markers are drawn too.
"""
import json
import os
import sys
import types

# A stub 'unreal' so mockcity_build imports without the editor; its bottom block then does nothing.
stub = types.ModuleType('unreal')


class _Any:
    def __getattr__(self, name):
        return _Any()

    def __call__(self, *a, **k):
        return _Any()


for n in ('EditorAssetLibrary', 'ReflectionsWorldLibrary', 'ReflectionsWorld', 'ReflectionsMarkerSide'):
    setattr(stub, n, _Any())
stub.AssetToolsHelpers = _Any()
stub.load_asset = lambda *a, **k: None
stub.Paths = types.SimpleNamespace(project_dir=lambda: '', project_saved_dir=lambda: '')
stub.EditorLevelLibrary = types.SimpleNamespace(get_game_world=lambda: object())
stub.__getattr__ = lambda name: _Any()
sys.modules['unreal'] = stub
sys.argv_saved = list(sys.argv)
ARGS = []
here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, 'mockcity_build.py'), encoding='utf-8').read()
g = {'__name__': 'mockcity_build', 'ARGS': ['none']}
exec(compile(src, 'mockcity_build.py', 'exec'), g)

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

S = 4.0          # px per metre
PAD = 90
W = int(2 * 190 * S + 2 * PAD)


def px(x, y):
    return PAD + (x + 175.0) * S, PAD + (175.0 - y) * S


class Recorder:
    name = 'Giltside'

    def __init__(self):
        self.rects = []
        self.lamps = []
        self.lamp_index = 0

    def box(self, x0, x1, y0, y1, z0, z1, mat, label=None, **kw):
        self.rects.append((x0, x1, y0, y1, z1, mat, label or '', kw.get('visible', True)))

    def cbox(self, c, s, mat, label=None, **kw):
        self.box(c[0] - s[0] / 2, c[0] + s[0] / 2, c[1] - s[1] / 2, c[1] + s[1] / 2, c[2] - s[2] / 2, c[2] + s[2] / 2, mat, label, **kw)

    def mesh(self, mesh, c, s, mat, label=None, **kw):
        self.cbox(c, s, mat, label, **kw)

    def prop(self, *a, **k):
        return None

    def light(self, *a, **k):
        return None

    def lamp(self, x, y, label, lit=None):
        self.lamps.append((x, y))

    def spawn(self, *a, **k):
        return _Any()


rec = Recorder()
g['build_common'](rec)
g['build_tower'](rec)
places = {k: v for k, v in g['PLACES'].items() if not k.startswith('_')}

img = Image.new('RGB', (W, W), (24, 40, 58))
d = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype('arial.ttf', 15)
    small = ImageFont.truetype('arial.ttf', 11)
    big = ImageFont.truetype('arialbd.ttf', 22)
except OSError:
    font = small = big = ImageFont.load_default()
FILL = {'Ground': (92, 86, 78), 'Street': (60, 58, 56), 'Wall': (170, 132, 92), 'WallAlt': (150, 112, 80),
        'Trim': (200, 190, 170), 'Water': (24, 40, 58), 'Tower': (230, 190, 90), 'Stall': (180, 70, 40),
        'Canvas': (200, 160, 90), 'Metal': (40, 40, 40), 'Door': (30, 20, 15), 'Rail': (25, 25, 25)}
order = ['Water', 'Ground', 'Street', 'Trim', 'Wall', 'WallAlt', 'Tower', 'Stall', 'Canvas', 'Metal', 'Door', 'Rail']
for mat in order:
    for (x0, x1, y0, y1, z1, m, label, vis) in rec.rects:
        if m != mat or not vis or label.startswith('Water'):
            continue
        a = px(x0, y1)
        b = px(x1, y0)
        if b[0] - a[0] < 1 or b[1] - a[1] < 1:
            continue
        col = FILL.get(m, (120, 120, 120))
        if label.startswith('Bldg_') and not label.endswith('Cornice'):
            shade = int(min(1.0, z1 / 16.0) * 40)
            col = (col[0] - shade, col[1] - shade, col[2] - shade)
        if label.endswith('Cornice'):
            continue
        d.rectangle([a, b], fill=col)
for (x, y) in rec.lamps:
    cx, cy = px(x, y)
    d.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=(255, 200, 90))

# Grid ticks every 50 m.
for v in range(-150, 151, 50):
    x, _ = px(v, 0)
    _, y = px(0, v)
    d.text((x - 10, PAD - 40), '%d' % v, fill=(200, 200, 200), font=small)
    d.text((PAD - 50, y - 6), '%d' % v, fill=(200, 200, 200), font=small)
d.text((PAD, 10), 'Mock Lanthorne: plan (metres, local to each side; +X right, +Y up)', fill=(255, 255, 255), font=big)

LABELS = {
    'TowerPlaza': 'Tower plaza (Gilt / Frost Tower)', 'BellSquare': 'Bell Square / Weigh-House Corner / Cistern',
    'WeighHouseRoof': 'Weigh-House (Pew tower)', 'Lamplight': 'Lamplight / Long Shelter', 'ArchiveSteps': 'Archive Steps / Ice Stairs',
    'LanternRow': 'Lantern Row / Bone Market', 'LanternGate': 'Lantern Gate / Frozen Gate', 'DrifterCamp': "Drifters' camp",
    'CanalRift': 'Canal rift post', 'FishSteps': 'Fish Steps', 'CoalLaneStop': 'Coal Lane tram stop', 'HesterDoorstep': "Hester's doorstep",
    'CoalLaneLaundry': 'Laundry', 'WickStreet': 'Wick St infirmary', 'MusterYard': 'Muster yard', 'Shed': "Sorrel's shed",
    'BarracksWest': 'Barracks (Gilt)', 'BarracksEast': 'Watch barracks', 'IceWall': 'Ice Wall (north quay)', 'GateBridge': 'Gate bridge',
    'BellLane': 'Bell Lane', 'Furnace': 'Furnace', 'VaneAtelier': 'Vane atelier',
}
for key, text in LABELS.items():
    if key not in places:
        continue
    x, y = places[key][0], places[key][1]
    cx, cy = px(x, y)
    d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], outline=(255, 255, 255), width=2)
    d.text((cx + 8, cy - 8), text, fill=(255, 255, 255), font=font, stroke_width=2, stroke_fill=(0, 0, 0))

if len(sys.argv) > 2:
    colors = {'Pewterside': (150, 160, 175), 'Giltside': (255, 170, 60), 'Frostside': (150, 210, 255)}
    for i, side in enumerate(('Pewterside', 'Giltside', 'Frostside')):
        f = os.path.join(sys.argv[2], 'MockCity_markers_%s.json' % side)
        if not os.path.exists(f):
            continue
        mk = json.load(open(f))['markers']
        for name, (x, y, z, yaw, tags) in mk.items():
            cx, cy = px(x, y)
            o = (i - 1) * 3
            d.rectangle([cx - 2 + o, cy - 2, cx + 2 + o, cy + 2], fill=colors[side])
        d.rectangle([PAD + i * 260, W - 40, PAD + i * 260 + 14, W - 26], fill=colors[side])
        d.text((PAD + i * 260 + 20, W - 44), '%s markers (%d)' % (side, len(mk)), fill=(255, 255, 255), font=font)
img.save(sys.argv[1])
print('saved', sys.argv[1], len(rec.rects), 'rects', len(rec.lamps), 'lamps')
