"""Lives places for Medieval London, worked out from the town's saved layout (no hand placing, no editor).

    python Tools/Lives/derive_places.py [streets.json]

Input: fable-streets' street data for the saved town, Saved/MedievalLondon_Narrow_streets.json: street and alley
centre lines (each with a 2.5 m walk strip), the market square, every house box, every stall [x, y, yaw], the lantern
mouths. Output: Content/Crowd/Spots/MedievalLondon_Lives.json, read by Lives at the start of play
(UReflectionsLivesSubsystem::LoadPlaceFile):

  pools.home    a door point just out from each house's street-facing wall (the face nearest a street centre line)
  pools.work    a vendor's standing point behind each stall's counter (its side away from the street)
  pools.gather  round the market well and the square's cistern, beside the lantern mouths, at street corners
  places        named places that should not stay where the story markers heaped them (none needed yet)

Every point keeps the 2.5 m centre strip of every street and alley clear (orchestrator rule, plus 40 cm for a body)
and stays out of houses, stalls, crates and casks. A place no marker answers (a generated townsperson's Home_gen_*,
Work_*, Haunt_*, a missing story home) takes the nearest free door or stall to that person. Crowd-react's street
scenes keep 2.5 m from these points. Also writes Saved/Lives/places_MedievalLondon.png (top-down check, needs Pillow).
"""

import json
import math
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
STREETS = PROJECT / 'Saved' / 'MedievalLondon_Narrow_streets.json'
OUT = PROJECT / 'Content' / 'Crowd' / 'Spots' / 'MedievalLondon_Lives.json'
PICTURE = PROJECT / 'Saved' / 'Lives' / 'places_MedievalLondon.png'
STALL_BOUNDS = ((-68.8, -120.0), (76.3, 120.0))   # SM_GL1450_MarketStall local XY bounds (FableStreets_measure_before.json)
WELL = (-3100.0, 780.0)                             # Tools/CityPCG/place_medieval_london_well.py CENTER
CISTERN = (400.0, 800.0)                            # story places Fountain / Square_Cistern
DOOR_OUT_CM = 120.0
VENDOR_BACK_CM = 90.0
MARGIN_CM = 40.0                                    # a body's width beside the strip


def seg_dist(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else STREETS
    s = json.loads(src.read_text(encoding='utf-8-sig'))
    strip = float(s.get('walk_strip_half_width', 125.0))
    lines = [st['centre'] for st in s['east_west_streets']] + [al['centre'] for al in s['cross_alleys']]
    segments = [(line[i], line[i + 1]) for line in lines for i in range(len(line) - 1)]

    def street_dist(p):
        return min(seg_dist(p, a, b) for a, b in segments)

    houses = [tuple(b) for b in s['house_boxes']]
    (lx, ly), (hx, hy) = STALL_BOUNDS
    stalls = []
    for x, y, yaw in s['stalls']:
        a = math.radians(yaw)
        c, sn = math.cos(a), math.sin(a)
        pts = [(x + c * px - sn * py, y + sn * px + c * py) for px in (lx, hx) for py in (ly, hy)]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        stalls.append(((min(xs), min(ys), max(xs), max(ys)), (x, y)))
    goods = [(x - 45, y - 45, x + 45, y + 45) for x, y in s.get('crates', []) + s.get('casks', [])]
    stall_boxes = [b for b, _ in stalls]

    def inside(p, boxes, pad):
        return any(b[0] - pad <= p[0] <= b[2] + pad and b[1] - pad <= p[1] <= b[3] + pad for b in boxes)

    def ok(p):
        return (street_dist(p) >= strip + MARGIN_CM and not inside(p, houses, 25.0) and not inside(p, stall_boxes, 25.0)
                and not inside(p, goods, 15.0) and abs(p[0]) < 24000 and abs(p[1]) < 24000)

    def toward_street(box):
        """Each face's midpoint and outward direction, nearest-to-a-street first (only faces that look at one)."""
        cx, cy = (box[0] + box[2]) * .5, (box[1] + box[3]) * .5
        faces = [((cx, box[1]), (0, -1)), ((cx, box[3]), (0, 1)), ((box[0], cy), (-1, 0)), ((box[2], cy), (1, 0))]
        scored = []
        for (fx, fy), (dx, dy) in faces:
            d0 = street_dist((fx, fy))
            d1 = street_dist((fx + dx * 300, fy + dy * 300))
            if d1 < d0:                                   # stepping out of this face goes toward a street
                scored.append((d0, (fx, fy), (dx, dy)))
        return sorted(scored)

    homes, skipped = [], {'home': 0, 'work': 0, 'gather': 0}
    for box in houses:
        placed = False
        for d0, (fx, fy), (dx, dy) in toward_street(box)[:2]:
            out = min(DOOR_OUT_CM, max(30.0, d0 - strip - MARGIN_CM))
            p = (fx + dx * out, fy + dy * out)
            if ok(p):
                homes.append({'x': round(p[0], 1), 'y': round(p[1], 1), 'z': 0.0, 'kind': 'door', 'radius': 150})
                placed = True
                break
        skipped['home'] += 0 if placed else 1

    work = []
    for box, (x, y) in stalls:
        faces = toward_street(box)
        if not faces:
            skipped['work'] += 1
            continue
        _, _, (dx, dy) = faces[0]
        half = ((box[2] - box[0]) * .5) if dx else ((box[3] - box[1]) * .5)
        cands = [(x - dx * (half + VENDOR_BACK_CM), y - dy * (half + VENDOR_BACK_CM))]           # behind the counter
        for gap in (80.0, 140.0, 200.0):                                                           # else beside it
            cands += [(box[2] + gap, y), (box[0] - gap, y)] if dy else [(x, box[3] + gap), (x, box[1] - gap)]
        cands.append((x + dx * (half + 60.0), y + dy * (half + 60.0)))                             # last, at its front
        p = next((c for c in cands if ok(c)), None)
        if p:
            mx, my = s['market_square']['x'], s['market_square']['y']
            work.append({'x': round(p[0], 1), 'y': round(p[1], 1), 'z': 0.0, 'kind': 'stall', 'stall_x': x, 'stall_y': y,
                         'market': mx[0] <= x <= mx[1] and my[0] <= y <= my[1], 'radius': 120})
        else:
            skipped['work'] += 1

    gather, cands = [], []
    for (cx, cy), kind, r in ((WELL, 'well', 330.0), (CISTERN, 'cistern', 330.0)):
        for i in range(6):
            a = math.radians(30 + 60 * i)
            cands.append(((cx + r * math.cos(a), cy + r * math.sin(a)), kind, 220))
    for mx, my in s.get('lantern_mouths', []):
        for ox, oy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            off = strip + MARGIN_CM + 60
            cands.append(((mx + ox * off, my + oy * 120), 'lantern', 220))
    for al in s['cross_alleys']:
        ax = al['centre'][0][0]
        for st in s['east_west_streets']:
            line = st['centre']
            ly_ = min(line, key=lambda q: abs(q[0] - ax))[1]
            off = strip + MARGIN_CM + 90
            for ox in (-1, 1):
                for oy in (-1, 1):
                    cands.append(((ax + ox * off, ly_ + oy * off), 'corner', 260))
    for p, kind, r in cands:
        if ok(p):
            gather.append({'x': round(p[0], 1), 'y': round(p[1], 1), 'z': 0.0, 'kind': kind, 'radius': r})
        else:
            skipped['gather'] += 1

    data = {
        'map': 'MedievalLondon',
        'note': ('Lives places from Tools/Lives/derive_places.py out of %s. Street and alley 2.5 m centre strips kept clear; '
                 'crowd street scenes keep 2.5 m from these points.' % src.name),
        'places': [],
        'pools': {'home': homes, 'work': work, 'gather': gather},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1), encoding='utf-8')
    summary = {'source': src.name, 'status': s.get('status'), 'houses': len(houses), 'stalls': len(stalls), 'homes': len(homes),
               'work': len(work), 'gather': len(gather), 'skipped': skipped, 'out': str(OUT)}
    try:
        picture(segments, strip, houses, stall_boxes, homes, work, gather)
        summary['picture'] = str(PICTURE)
    except Exception as e:  # Pillow missing is fine
        summary['picture'] = repr(e)
    print(json.dumps(summary, indent=1))


def picture(segments, strip, houses, stalls, homes, work, gather):
    from PIL import Image, ImageDraw
    size, half = 2400, 24500.0
    img = Image.new('RGB', (size, size), (235, 232, 225))
    d = ImageDraw.Draw(img)

    def px(x, y):
        return ((x + half) / (2 * half) * size, (half - y) / (2 * half) * size)

    for a, b in segments:
        d.line([px(*a), px(*b)], fill=(205, 195, 175), width=max(1, round(2 * strip / (2 * half) * size)))
    for b in houses:
        d.rectangle([px(b[0], b[3]), px(b[2], b[1])], outline=(90, 90, 90), fill=(170, 160, 150))
    for b in stalls:
        d.rectangle([px(b[0], b[3]), px(b[2], b[1])], fill=(150, 60, 40))
    for pool, col in ((homes, (40, 90, 200)), (work, (210, 120, 0)), (gather, (30, 150, 60))):
        for p in pool:
            x, y = px(p['x'], p['y'])
            d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=col)
    PICTURE.parent.mkdir(parents=True, exist_ok=True)
    img.save(PICTURE)


if __name__ == '__main__':
    main()
