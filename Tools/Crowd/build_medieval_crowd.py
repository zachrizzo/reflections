"""MedievalLondon crowd data, generated from the town's own layout (offline, NumPy + PIL; no editor).

Writes Content/Crowd/Spots/MedievalLondon.json with
  - "routes": a walking graph along the clear centre of every street (the town's east-west streets, the curved
    main street, the cross streets) plus loops round the market square and the well. Ring walkers follow it
    (ReflectionsCrowdStrollSubsystem route mode), keeping a little to the left of the centre line, so they stay
    inside the 2.5 m strip the town keeps clear of houses, stalls, crates and casks;
  - "spots": street scenes for ReflectionsCrowdSpotSubsystem, placed from the layout: a vendor behind (or beside)
    every market stall and customers in front of it, chats round the well, in the market square and at cross-street
    corners, and people leaning or smoking at house fronts. Nothing is placed by hand.

Source of the layout (first that exists, or --measure PATH / --layout):
  Saved/FableStreets_measure_after.json, Saved/FableStreets_measure_before.json  (instances read from the saved
  map: {"ism": {mesh: [[x, y, z, yaw, sx, sy, sz], ...]}, "bounds": {mesh: [min, max]}, "actors": [...]}),
  else --layout: Tools/CityPCG/build_medieval_london_map.py layout() with those bounds.
Also writes Saved/CrowdReactions/MedievalLondon_crowd_plan.png (+ _market.png) for review.

Usage (repository root):  python Tools/Crowd/build_medieval_crowd.py [--measure PATH | --layout] [--dry-run]
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools' / 'CityPCG'))
import build_medieval_london_map as town  # noqa: E402

OUT = ROOT / 'Content' / 'Crowd' / 'Spots' / 'MedievalLondon.json'
PLAN = ROOT / 'Saved' / 'CrowdReactions' / 'MedievalLondon_crowd_plan.png'

WALKER = 45.0          # walker capsule radius + margin: route centres keep this far from any obstacle (cm)
STEP = 300.0           # route node spacing along a street (cm)
OFFSET = 35.0          # walkers keep this far left of the route centre line (cm)
SPOT_CLEAR_OF_ROUTE = 110.0   # standing people keep this far from a route centre line (cm)
EDGE = 23300.0         # streets are sampled up to the town wall
FLOOR_Z = 3.0
STALL_VENDORS = False  # npc-lives' named vendors work the stalls (--stall-vendors puts generic ones back)
PIN_EVERY = 3          # one spot in three of each kind spawns its own occupants (0: all borrow passing walkers)

MESH_KEYS = {path.split('/')[-1]: key for key, path in town.ASSETS.items()}
HOUSE_KEYS = set(town.HOUSES)
OBSTACLE_KEYS = HOUSE_KEYS | {'wall', 'gate', 'stall', 'crates', 'cask'}


# ---------------------------------------------------------------------------------------------- layout input
def load_instances(args):
    """{key: [(x, y, yaw, sx, sy)]}, bounds {key: (low, high)}, story points [(x, y, name)], well (x, y, r)."""
    candidates = [Path(args.measure)] if args.measure else [ROOT / 'Saved' / 'FableStreets_measure_after.json',
                                                            ROOT / 'Saved' / 'FableStreets_measure_before.json']
    measure = next((p for p in candidates if p.exists()), None)
    if measure is None:
        raise SystemExit('No layout measurement found (Saved/FableStreets_measure_*.json); pass --measure PATH.')
    data = json.loads(measure.read_text(encoding='utf-8-sig'))
    bounds = {MESH_KEYS[m]: (tuple(b[0]), tuple(b[1])) for m, b in data['bounds'].items() if m in MESH_KEYS}
    source = str(measure.relative_to(ROOT))
    if args.layout:
        groups = town.layout(bounds)
        inst = {k: [(p[0][0], p[0][1], p[1], p[2][0], p[2][1]) for p in rows] for k, rows in groups.items()}
        source = 'Tools/CityPCG/build_medieval_london_map.py layout() with bounds from ' + source
    else:
        inst = {}
        for mesh, rows in data['ism'].items():
            if mesh in MESH_KEYS:
                inst.setdefault(MESH_KEYS[mesh], []).extend((r[0], r[1], r[3], r[4], r[5]) for r in rows)
    story, well = [], None
    for a in data.get('actors', []):
        name, cls, x, y = a[0], a[1], a[2], a[3]
        if cls in ('ReflectionsStoryMarker', 'PlayerStart'):
            story.append((x, y, name))
        if 'Well masonry collision' in name:
            well = (x, y, 100.0 * max(a[6], a[7]))
    if not story:
        story = [(x, y, n) for x, y, n in town.town_story_points()]
    if well is None:
        well = (-3100.0, 780.0, 110.0)
    return inst, bounds, story, well, source


NARROW = ROOT / 'Saved' / 'MedievalLondon_Narrow_streets.json'


def load_narrow(path, measure_path):
    """fable-streets' narrowed town (Saved/MedievalLondon_Narrow_streets.json, UE cm): street and alley centre lines
    with a clear 2.5 m strip, stalls [x, y, yaw], crates/casks [x, y], house boxes, lantern posts on alley mouths,
    the market square. Walls, gates, story markers and the well come from the earlier map measurement."""
    d = json.loads(path.read_text(encoding='utf-8-sig'))
    m = json.loads(measure_path.read_text(encoding='utf-8-sig'))
    bounds = {MESH_KEYS[k]: (tuple(b[0]), tuple(b[1])) for k, b in m['bounds'].items() if k in MESH_KEYS}
    boxes = {'merchants': [tuple(b) for b in d['house_boxes']]}
    stalls = []
    for x, y, yaw in d.get('stalls', []):
        box = instance_box(bounds, 'stall', x, y, yaw, 1.0, 1.0)
        boxes.setdefault('stall', []).append(box)
        stalls.append(box)
    for key, half in (('crates', 60.0), ('casks', 50.0)):
        for p in d.get(key, []):
            boxes.setdefault('crates' if key == 'crates' else 'cask', []).append((p[0] - half, p[1] - half, p[0] + half, p[1] + half))
    for x, y in d.get('lantern_mouths', []):
        boxes.setdefault('wall', []).append((x - 80.0, y - 80.0, x + 80.0, y + 80.0))
    for mesh, rows in m['ism'].items():
        key = MESH_KEYS.get(mesh)
        if key in ('wall', 'gate'):
            boxes.setdefault(key, []).extend(instance_box(bounds, key, r[0], r[1], r[3], r[4], r[5]) for r in rows)
    story, well = [], (-3100.0, 780.0, 110.0)
    for a in m.get('actors', []):
        if a[1] in ('ReflectionsStoryMarker', 'PlayerStart'): story.append((a[2], a[3], a[0]))
        if 'Well masonry collision' in a[0]: well = (a[2], a[3], 100.0 * max(a[6], a[7]))
    streets = [s['centre'] for s in d.get('east_west_streets', [])] + [s['centre'] for s in d.get('cross_alleys', [])]
    market = d.get('market_square')
    return boxes, stalls, story, well, str(path.relative_to(ROOT)) + ' (' + d.get('status', '') + ')', streets, market


def instance_box(bounds, key, x, y, yaw, sx, sy):
    (lx0, ly0, _), (lx1, ly1, _) = bounds[key]
    a = math.radians(yaw)
    c, s = math.cos(a), math.sin(a)
    xs, ys = [], []
    for lx in (lx0 * sx, lx1 * sx):
        for ly in (ly0 * sy, ly1 * sy):
            xs.append(x + c * lx - s * ly)
            ys.append(y + s * lx + c * ly)
    return min(xs), min(ys), max(xs), max(ys)


# ---------------------------------------------------------------------------------------------- geometry
class Obstacles:
    def __init__(self, boxes):
        self.b = np.asarray(boxes, dtype=np.float64).reshape(-1, 4)

    def blocked(self, pts, r):
        """pts (N,2): True where a disc of radius r round the point touches any box."""
        pts = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
        out = np.zeros(len(pts), dtype=bool)
        for i in range(0, len(pts), 256):
            p = pts[i:i + 256, None, :]
            dx = np.maximum(np.maximum(self.b[None, :, 0] - p[..., 0], p[..., 0] - self.b[None, :, 2]), 0.0)
            dy = np.maximum(np.maximum(self.b[None, :, 1] - p[..., 1], p[..., 1] - self.b[None, :, 3]), 0.0)
            out[i:i + 256] = ((dx * dx + dy * dy) < r * r).any(axis=1)
        return out

    def segment_clear(self, a, b, r):
        n = max(2, int(math.dist(a, b) / 25.0) + 1)
        t = np.linspace(0.0, 1.0, n)[:, None]
        return not self.blocked(np.asarray(a) * (1 - t) + np.asarray(b) * t, r).any()

    def free_interval(self, fixed, axis, centre, reach, r):
        """Along the other axis at coordinate `fixed`: the free span (for a disc of radius r) nearest `centre`."""
        b = self.b
        if axis == 'x':   # fixed x, search along y
            near = (b[:, 0] - r <= fixed) & (b[:, 2] + r >= fixed)
            spans = b[near][:, [1, 3]]
        else:             # fixed y, search along x
            near = (b[:, 1] - r <= fixed) & (b[:, 3] + r >= fixed)
            spans = b[near][:, [0, 2]]
        lo, hi = centre - reach, centre + reach
        spans = spans[(spans[:, 1] + r > lo) & (spans[:, 0] - r < hi)]
        spans = np.sort(np.stack([spans[:, 0] - r, spans[:, 1] + r], axis=1), axis=0) if len(spans) else spans
        free, cur = [], lo
        for s0, s1 in sorted(map(tuple, spans)):
            if s0 > cur: free.append((cur, min(s0, hi)))
            cur = max(cur, s1)
            if cur >= hi: break
        if cur < hi: free.append((cur, hi))
        free = [f for f in free if f[1] - f[0] >= 20.0]
        if not free: return None
        return min(free, key=lambda f: 0.0 if f[0] <= centre <= f[1] else min(abs(f[0] - centre), abs(f[1] - centre)))


# ---------------------------------------------------------------------------------------------- routes
class Graph:
    def __init__(self):
        self.nodes, self.edges = [], set()

    def add(self, p):
        self.nodes.append((float(p[0]), float(p[1])))
        return len(self.nodes) - 1

    def link(self, a, b):
        if a != b: self.edges.add((min(a, b), max(a, b)))


def street_polyline(obs, axis, fixed_of, nominal, lo, hi):
    """Clear centre points of one street. axis 'x': an east-west street sampled along x (centre in y)."""
    pts = []
    s = lo
    while s <= hi:
        c0 = nominal(s)
        span = obs.free_interval(s, axis, c0, 700.0, WALKER)
        if span is None or span[1] - span[0] < 2 * OFFSET:
            pts.append(None)
        else:
            # Narrow street: its middle. Open ground (a square, a crossing): stay on the street's own line.
            mid = 0.5 * (span[0] + span[1]) if span[1] - span[0] < 500.0 else min(max(c0, span[0] + 150.0), span[1] - 150.0)
            pts.append((s, mid) if axis == 'x' else (mid, s))
        s += STEP
    return pts


def centre_polyline(obs, centre):
    """A given street centre line (fable-streets' clear strip), resampled every STEP. A point that something stands on
    (a lantern post on an alley mouth) moves sideways to the nearest free spot within 2 m, else breaks the line."""
    c = np.asarray(centre, dtype=np.float64)
    seg = np.hypot(*(c[1:] - c[:-1]).T)
    total = float(seg.sum())
    out, base, normal, shifts = [], [], [], []
    for s in np.arange(0.0, total + 1.0, STEP):
        k = int(np.searchsorted(np.cumsum(seg), s, side='right'))
        k = min(k, len(seg) - 1)
        s0 = float(np.cumsum(seg)[k] - seg[k])
        t = (s - s0) / max(seg[k], 1e-6)
        p = c[k] + (c[k + 1] - c[k]) * min(max(t, 0.0), 1.0)
        d = (c[k + 1] - c[k]) / max(seg[k], 1e-6)
        n = np.array([-d[1], d[0]])
        best, used = None, 0.0
        # Off the line, a slightly tighter squeeze is fine (a walker passing a lantern post in a 3.5 m alley).
        for shift in [0.0] + [s * sign for s in range(10, 201, 10) for sign in (1.0, -1.0)]:
            q = p + n * shift
            if not obs.blocked([q], WALKER if shift == 0.0 else WALKER - 8.0)[0]:
                best, used = (float(q[0]), float(q[1])), shift
                break
        out.append(best); base.append(p); normal.append(n); shifts.append(used)
    # Step round an obstacle in a straight run: where a segment next to a moved point is blocked, move the
    # neighbour by the same amount too.
    for _ in range(4):
        changed = False
        for i in range(len(out) - 1):
            a, b = out[i], out[i + 1]
            if a is None or b is None or obs.segment_clear(a, b, WALKER - 8.0): continue
            if shifts[i] == 0.0 and shifts[i + 1] == 0.0:
                # Both points are free but the line between them runs through something: move both aside.
                for s in [v * sign for v in range(10, 201, 10) for sign in (1.0, -1.0)]:
                    qa, qb = base[i] + normal[i] * s, base[i + 1] + normal[i + 1] * s
                    if not obs.blocked([qa, qb], WALKER - 8.0).any() and obs.segment_clear(qa, qb, WALKER - 8.0):
                        out[i], out[i + 1] = (float(qa[0]), float(qa[1])), (float(qb[0]), float(qb[1]))
                        shifts[i] = shifts[i + 1] = s
                        changed = True
                        break
                continue
            for j, k in ((i + 1, i), (i, i + 1)):
                if shifts[k] != 0.0 and shifts[j] != shifts[k]:
                    q = base[j] + normal[j] * shifts[k]
                    if not obs.blocked([q], WALKER - 8.0)[0]:
                        out[j], shifts[j], changed = (float(q[0]), float(q[1])), shifts[k], True
                        break
        if not changed: break
    return out


def build_routes(obs, well, streets=None, market=None):
    g = Graph()
    lines = []
    if streets:
        # fable-streets' centre lines: every street and alley keeps a clear 2.5 m strip round its line.
        for k, centre in enumerate(streets):
            lines.append(('street %d' % k, centre_polyline(obs, centre)))
    else:
        # East-west streets (one is the curved main street), then the cross streets, from the free space.
        for lane in town.STREET_AXES:
            nominal = town.main_street_center if lane == 0 else (lambda x, lane=lane: lane + 95.0 * math.sin(x / 8800.0))
            lines.append(('ew %d' % lane, street_polyline(obs, 'x', None, nominal, -EDGE, EDGE)))
        for road in town.CROSS_STREETS:
            lines.append(('ns %d' % road, street_polyline(obs, 'y', None, lambda y, road=road: road, -EDGE, EDGE)))
    # The market square: walking rows between its stall rows, and a ring round the well.
    if market:
        x0, x1 = market['x']
        ys = sorted(set([0.0] + [float(v) for v in market.get('stall_rows_y', [])] + [float(market['y'][0]), float(market['y'][1])]))
        rows_y = [0.5 * (a + b) for a, b in zip(ys, ys[1:]) if abs(0.5 * (a + b)) > 300.0]
    else:
        x0, x1, rows_y = -4400.0, 4400.0, [-1700.0, 1700.0]
    for y in rows_y:
        row = []
        for x in np.arange(x0 + 300.0, x1 - 299.0, STEP):
            p = (float(x), y)
            row.append(p if not obs.blocked([p], WALKER)[0] else None)
        lines.append(('market %d' % y, row))
    wx, wy, wr = well
    ring = [(wx + (wr + 170.0) * math.cos(a), wy + (wr + 170.0) * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 13)[:-1]]
    ring = [p if not obs.blocked([p], WALKER)[0] else None for p in ring]
    lines.append(('well ring', ring + ring[:1]))

    owner = []
    for name, pts in lines:
        prev = None
        for p in pts:
            if p is None:
                prev = None
                continue
            i = g.add(p)
            owner.append(name)
            if prev is not None and obs.segment_clear(g.nodes[prev], p, WALKER - 8.0):
                g.link(prev, i)
            prev = i
    # Junctions: where two lines meet, one link between their mutually nearest nodes (no fans of diagonals).
    pts = np.asarray(g.nodes)
    own = np.asarray(owner)
    nearest = {}
    for i in range(len(pts)):
        d = np.hypot(pts[:, 0] - pts[i, 0], pts[:, 1] - pts[i, 1])
        close = np.nonzero((d < 420.0) & (own != own[i]))[0]
        for line in set(own[close]):
            js = close[own[close] == line]
            nearest[(i, line)] = int(js[np.argmin(d[js])])
    for (i, line), j in nearest.items():
        if j > i and nearest.get((j, own[i])) == i and obs.segment_clear(g.nodes[i], g.nodes[j], WALKER):
            g.link(i, j)
    # Keep only nodes that are linked, and the largest connected part (stray bits behind a gate are not streets).
    adj = {i: set() for i in range(len(g.nodes))}
    for a, b in g.edges:
        adj[a].add(b); adj[b].add(a)
    seen, best = set(), []
    for i in adj:
        if i in seen or not adj[i]: continue
        comp, stack = [], [i]
        seen.add(i)
        while stack:
            k = stack.pop(); comp.append(k)
            for m in adj[k]:
                if m not in seen: seen.add(m); stack.append(m)
        if len(comp) > len(best): best = comp
    keep = sorted(best)
    remap = {old: new for new, old in enumerate(keep)}
    nodes = [g.nodes[i] for i in keep]
    edges = sorted((remap[a], remap[b]) for a, b in g.edges if a in remap and b in remap)
    return nodes, edges


def route_distance(nodes, edges, pts):
    """Distance (cm) from each point to the nearest route centre line."""
    n = np.asarray(nodes)
    e = np.asarray(edges)
    a, b = n[e[:, 0]], n[e[:, 1]]
    ab = b - a
    L2 = np.maximum((ab ** 2).sum(axis=1), 1e-6)
    out = []
    for p in np.asarray(pts, dtype=np.float64).reshape(-1, 2):
        t = np.clip(((p - a) * ab).sum(axis=1) / L2, 0.0, 1.0)
        q = a + ab * t[:, None]
        out.append(float(np.min(np.hypot(q[:, 0] - p[0], q[:, 1] - p[1]))))
    return np.asarray(out)


# ---------------------------------------------------------------------------------------------- spots
def load_lives_points():
    """npc-lives' MedievalLondon places (homes' door points, working vendors behind stalls, the gathering place):
    Content/Crowd/Spots/MedievalLondon_Lives.json, a list or {"points"|"spots": [...]} of {x, y, kind[, radius]}.
    Street scenes keep 2.5 m (+ the point's radius) clear of them; a stall customer may face a Lives vendor."""
    path = OUT.with_name('MedievalLondon_Lives.json')
    if not path.exists(): return [], None
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if isinstance(data, list):
        rows = data
    else:
        rows = list(data.get('points') or []) + list(data.get('spots') or []) + list(data.get('places') or [])
        for pool in (data.get('pools') or {}).values():
            if isinstance(pool, list): rows.extend(pool)
    pts = []
    for r in rows:
        try: pts.append((float(r['x']), float(r['y']), str(r.get('kind', '')), float(r.get('radius', r.get('radius_cm', 0.0)) or 0.0)))
        except (KeyError, TypeError, ValueError): continue
    return pts, str(path.relative_to(ROOT))


LIVES_CLEARANCE = 250.0


def build_spots(stalls, obs, nodes, edges, story, well, lives=()):
    spots = []
    taken = []

    def far_from_story(p, d=260.0):
        return all(math.hypot(p[0] - x, p[1] - y) > d for x, y, _ in story)

    def far_from_lives(p, kind):
        for x, y, k, r in lives:
            kl = k.lower()
            # A customer at a stall faces the Lives vendor across the counter: that pairing is the point.
            if kind == 'window' and kl in ('vendor', 'stall', 'work'): continue
            # The agreed rule: 2.5 m from each point. A gathering place (well, corner, cistern, lantern) covers an
            # area, so its radius counts too; a door or a stall is a standing point. Radii under 20 are metres.
            rr = (r * 100.0 if 0.0 < r < 20.0 else r) if kl not in ('door', 'stall', 'vendor', 'work') else 0.0
            if math.hypot(p[0] - x, p[1] - y) < LIVES_CLEARANCE + rr: return False
        return True

    def far_from_spots(p, d):
        return all(math.hypot(p[0] - q[0], p[1] - q[1]) > d for q in taken)

    made = {}

    def add(name, kind, p, yaw, slots, place, pinned=None, search_m=None, spacing=350.0, clear=SPOT_CLEAR_OF_ROUTE, room=40.0):
        if obs.blocked([p], room)[0] or not far_from_story(p) or not far_from_spots(p, spacing) or not far_from_lives(p, kind):
            return False
        if route_distance(nodes, edges, [p])[0] < clear:
            return False
        # Density: about one spot in PIN_EVERY of each kind spawns its own people (pairs chatting, a shopper,
        # someone leaning in a doorway), so the street is full without taking walkers off it. The rest borrow
        # passing walkers. Pinned shoppers come alone; the spot subsystem caps pinned people (Crowd.Spots.MaxPinned).
        n_kind = made.get(kind, 0)
        made[kind] = n_kind + 1
        if pinned is None:
            pinned = PIN_EVERY > 0 and n_kind % PIN_EVERY == 0
            if pinned and kind == 'window': slots = 1
            if pinned and kind == 'chat': slots = 2
        row = {'name': name, 'kind': kind, 'slots': slots, 'x': round(p[0], 1), 'y': round(p[1], 1), 'z': 0.0,
               'yaw': round(yaw % 360.0, 1), 'place': place, 'pinned': pinned}
        if search_m: row['search_m'] = search_m
        spots.append(row)
        taken.append(p)
        return True

    def toward_route(p):
        """Unit vector from p to the nearest route point."""
        n = np.asarray(nodes); e = np.asarray(edges)
        a, b = n[e[:, 0]], n[e[:, 1]]
        ab = b - a
        t = np.clip(((np.asarray(p) - a) * ab).sum(axis=1) / np.maximum((ab ** 2).sum(axis=1), 1e-6), 0.0, 1.0)
        q = a + ab * t[:, None]
        k = int(np.argmin(np.hypot(q[:, 0] - p[0], q[:, 1] - p[1])))
        v = q[k] - np.asarray(p)
        d = float(np.hypot(*v))
        return (v / d) if d > 1e-3 else np.array([1.0, 0.0]), d

    def yaw_of(v):
        return math.degrees(math.atan2(v[1], v[0]))

    # 1. Stalls: customers in front (every other stall when a street is lined with them). The vendor behind the
    #    counter is npc-lives' (a named NPC at work), so no vendor spot here unless --stall-vendors.
    for i, box in enumerate(stalls):
        c = ((box[0] + box[2]) * 0.5, (box[1] + box[3]) * 0.5)
        # Long rows of stalls: customers at about every other one, on both sides (by position, not list order).
        if len(stalls) > 40 and int(math.floor((c[0] + c[1]) / 450.0)) % 2: continue
        to_street, dist = toward_route(c)
        if dist > 1500.0: continue
        half_depth = abs(to_street[0]) * (box[2] - box[0]) * 0.5 + abs(to_street[1]) * (box[3] - box[1]) * 0.5
        side = np.array([-to_street[1], to_street[0]])
        half_width = abs(side[0]) * (box[2] - box[0]) * 0.5 + abs(side[1]) * (box[3] - box[1]) * 0.5
        market = abs(c[0]) < 4700 and abs(c[1]) < 3800
        place = 'market'
        front = np.asarray(c) + to_street * (half_depth + 45.0)
        add('stall%02d_customers' % i, 'window', tuple(front), yaw_of(-to_street), 2, place, clear=80.0, room=20.0, spacing=150.0)
        if not STALL_VENDORS: continue
        for cand in (np.asarray(c) - to_street * (half_depth + 50.0),
                     np.asarray(c) + side * (half_width + 55.0), np.asarray(c) - side * (half_width + 55.0)):
            if add('stall%02d_vendor' % i, 'vendor', tuple(cand), yaw_of(to_street), 1, place, pinned=True, spacing=120.0, clear=95.0, room=30.0):
                break
        _ = market

    # 2. The well: a chat ring beside it.
    wx, wy, wr = well
    for k, a in enumerate(np.linspace(0, 2 * math.pi, 9)[:-1]):
        p = (wx + (wr + 330.0) * math.cos(a), wy + (wr + 330.0) * math.sin(a))
        if add('well_chat', 'chat', p, yaw_of((wx - p[0], wy - p[1])), 3, 'market', clear=150.0, room=110.0):
            break

    # 3. The market square: chats and a smoker on open ground off the walking rows.
    market_kinds = [('chat', 3), ('chat', 2), ('smoke', 1), ('chat', 3), ('chat', 2), ('lean', 1)]
    grid = [(float(x), float(y)) for x in np.arange(-4300, 4301, 150) for y in np.arange(-3300, 3301, 150)]
    rng = np.random.default_rng(1450)
    rng.shuffle(grid)
    k = 0
    for p in grid:
        if k >= len(market_kinds): break
        kind, slots = market_kinds[k]
        if add('market_%s_%d' % (kind, k), kind, p, float(rng.uniform(0, 360)), slots, 'market',
               clear=170.0, room=110.0 if kind == 'chat' else 45.0, spacing=600.0):
            k += 1

    # 4. House fronts along every street: leaners, smokers and doorstep chats facing the street.
    n = np.asarray(nodes)
    order = ['lean', 'smoke', 'lean', 'chat']
    count = 0
    for i, (a, b) in enumerate(edges):
        if i % 7: continue   # about one try per 20 m of route
        pa, pb = n[a], n[b]
        d = pb - pa
        L = float(np.hypot(*d))
        if L < 1.0: continue
        d /= L
        mid = (pa + pb) * 0.5
        for sgn in (1.0, -1.0):
            out = np.array([-d[1], d[0]]) * sgn
            # Walk out from the street to the first house front within 5 m.
            wall = None
            for r in np.arange(60.0, 520.0, 20.0):
                if obs.blocked([tuple(mid + out * r)], 1.0)[0]:
                    wall = r
                    break
            if wall is None: continue
            kind = order[count % len(order)]
            # The leaner's own search puts it 40 cm off the wall; a doorstep chat needs a bit more room.
            p = tuple(mid + out * (wall - (70.0 if kind != 'chat' else 110.0)))
            place = 'market' if abs(p[0]) < 4700 and abs(p[1]) < 3800 else 'street'
            if add('front_%s_%d' % (kind, count), kind, p, yaw_of(-out) if kind == 'chat' else yaw_of(d * sgn),
                   2 if kind == 'chat' else 1, place, spacing=1800.0, room=30.0 if kind != 'chat' else 70.0):
                count += 1

    # 5. Cross-street corners: two neighbours talking at every other crossing, a smoker at the rest.
    for ri, road in enumerate(town.CROSS_STREETS):
        for li, lane in enumerate(town.STREET_AXES):
            kind, slots = (('chat', 2) if (ri + li) % 2 == 0 else ('smoke', 1))
            for dx in (-1, 1):
                for dy in (-1, 1):
                    p = (road + dx * 330.0, lane + dy * 330.0)
                    if add('corner_%s_%d_%d' % (kind, road, lane), kind, p, yaw_of((-dx, -dy)), slots, 'street',
                           clear=150.0, room=80.0 if kind == 'chat' else 45.0, spacing=700.0):
                        break
                else:
                    continue
                break
    return spots


# ---------------------------------------------------------------------------------------------- picture
def draw_plan(path, boxes_by_key, nodes, edges, spots, story, crop=None, scale=None):
    from PIL import Image, ImageDraw
    x0, y0, x1, y1 = crop or (-24500.0, -24500.0, 24500.0, 24500.0)
    W = 1400
    s = W / (x1 - x0)
    H = int((y1 - y0) * s)
    img = Image.new('RGB', (W, H), (236, 232, 222))
    dr = ImageDraw.Draw(img)

    def P(x, y):  # north (+y) up
        return ((x - x0) * s, (y1 - y) * s)

    colours = {'merchants': (120, 110, 100), 'workshop': (140, 128, 112), 'compound': (100, 92, 84), 'wall': (60, 60, 60),
               'gate': (40, 40, 40), 'stall': (214, 140, 50), 'crates': (150, 100, 60), 'cask': (130, 80, 50)}
    for key, boxes in boxes_by_key.items():
        for b in boxes:
            (ax, ay), (bx, by) = P(b[0], b[3]), P(b[2], b[1])
            dr.rectangle([ax, ay, bx, by], fill=colours.get(key, (100, 100, 100)))
    for a, b in edges:
        dr.line([P(*nodes[a]), P(*nodes[b])], fill=(40, 110, 220), width=2 if crop else 1)
    kc = {'chat': (220, 40, 60), 'window': (40, 170, 80), 'vendor': (240, 200, 0), 'lean': (150, 60, 200),
          'smoke': (90, 90, 90), 'bench': (0, 160, 160)}
    r = 6 if crop else 3
    for sp in spots:
        cx, cy = P(sp['x'], sp['y'])
        dr.ellipse([cx - r, cy - r, cx + r, cy + r], fill=kc.get(sp['kind'], (0, 0, 0)), outline=(0, 0, 0))
    for x, y, _ in story:
        cx, cy = P(x, y)
        dr.rectangle([cx - 2, cy - 2, cx + 2, cy + 2], fill=(255, 0, 255))
    img.save(path)


# ---------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--narrow', help="fable-streets' narrowed-town JSON (default Saved/MedievalLondon_Narrow_streets.json, preferred when present)")
    ap.add_argument('--measure', help='a FableStreets-style measurement JSON of the saved map')
    ap.add_argument('--layout', action='store_true', help="use the town script's layout() instead of the measured instances")
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--stall-vendors', action='store_true', help='generic pinned vendors at the stalls (without npc-lives)')
    args = ap.parse_args()
    global STALL_VENDORS
    STALL_VENDORS = args.stall_vendors

    lives, lives_source = load_lives_points()
    streets = market = None
    narrow = Path(args.narrow) if args.narrow else NARROW
    if not args.measure and not args.layout and narrow.exists():
        boxes_by_key, stalls, story, well, source, streets, market = load_narrow(narrow, ROOT / 'Saved' / 'FableStreets_measure_before.json')
    else:
        inst, bounds, story, well, source = load_instances(args)
        boxes_by_key = {}
        for key, rows in inst.items():
            if key in OBSTACLE_KEYS:
                boxes_by_key[key] = [instance_box(bounds, key, *row) for row in rows]
        stalls = boxes_by_key.get('stall', [])
    boxes = [b for kb in boxes_by_key.values() for b in kb]
    wx, wy, wr = well
    boxes.append((wx - wr, wy - wr, wx + wr, wy + wr))
    obs = Obstacles(boxes)

    nodes, edges = build_routes(obs, well, streets, market)
    spots = build_spots(stalls, obs, nodes, edges, story, well, lives)

    # Checks: every route edge clear of every obstacle; every spot off the walking band and not inside anything.
    bad_edges = sum(1 for a, b in edges if not obs.segment_clear(nodes[a], nodes[b], WALKER - 10.0))
    length_m = sum(math.dist(nodes[a], nodes[b]) for a, b in edges) / 100.0
    kinds = {}
    for sp in spots: kinds[sp['kind']] = kinds.get(sp['kind'], 0) + 1
    stats = {'source': source, 'route_nodes': len(nodes), 'route_edges': len(edges), 'route_km': round(length_m / 1000.0, 2),
             'edges_touching_obstacles': bad_edges, 'spots': len(spots), 'by_kind': kinds,
             'pinned': sum(1 for sp in spots if sp['pinned']), 'obstacles': len(boxes),
             'lives_points_kept_clear': len(lives), 'lives_source': lives_source}
    out = {
        'map': 'MedievalLondon',
        'note': ('Generated by Tools/Crowd/build_medieval_crowd.py from the town layout (%s); do not edit by hand. '
                 'routes: walking graph along the clear street centres (ReflectionsCrowdStrollSubsystem route mode; '
                 'walkers keep offset_cm left of the line). spots: street scenes (ReflectionsCrowdSpotSubsystem), '
                 'x/y in UE cm.') % source,
        'stats': stats,
        'routes': {'offset_cm': OFFSET, 'nodes': [[round(x, 1), round(y, 1), FLOOR_Z] for x, y in nodes],
                   'edges': [list(e) for e in edges]},
        'spots': spots,
    }
    print(json.dumps(stats, indent=1))
    if args.dry_run: return
    OUT.write_text(json.dumps(out, indent=1), encoding='utf-8')
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    draw_plan(PLAN, boxes_by_key, nodes, edges, spots, story)
    draw_plan(PLAN.with_name(PLAN.stem + '_market.png'), boxes_by_key, nodes, edges, spots, story,
              crop=(-6000.0, -4500.0, 6000.0, 4500.0))
    draw_plan(PLAN.with_name(PLAN.stem + '_gate.png'), boxes_by_key, nodes, edges, spots, story,
              crop=(-24300.0, -3000.0, -16300.0, 3000.0))
    print('wrote', OUT.relative_to(ROOT), 'and', PLAN.relative_to(ROOT))


if __name__ == '__main__':
    main()
