"""Generate the standalone 500 m Medieval London map through the Unreal MCP.

Run in the editor's async Python tool with this directory on sys.path, the map
open outside Play, and Saved/PIE_LOCK.json held by one of LEASE_OWNERS:
`await run()` builds a new town; `await repack()` re-applies a revised layout to
the saved one. The street widths are the constants under "Street widths" below.
layout() also runs without Unreal when given the mesh bounds, for plotting.
"""

import asyncio
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import random
import time

from apply_facade_pcg import cell_transform, configure_spawner, make_point, populate_point_mesh_graph

MAP = '/Game/GrayLondon/Maps/MedievalLondon'
ROOT = '/Game/GrayLondon/MedievalOpening'
GRAPH_DIR = f'{ROOT}/Graphs'
GRAPH_NAME = 'PCG_MedievalLondon_Town'
HOUSES = {
    key: f'{ROOT}/WholeBuildings/WestMarkLane/SM_GLMedieval_MarkLane{suffix}'
    for key, suffix in [('merchants', 'MerchantsHouses'), ('workshop', 'Workshop'),
                        ('compound', 'TradingCompound')]
}
PROPS = {
    key: f'{ROOT}/MarketDressing/SM_GL1450_{suffix}/StaticMeshes/SM_GL1450_{suffix}'
    for key, suffix in [('gate', 'WatchGate'), ('wall', 'WatchPalisadeWing'),
                        ('stall', 'MarketStall'), ('crates', 'CratesAndBasket'),
                        ('cask', 'CaskAndSack')]
}
PAVING = f'{ROOT}/Ground/SM_GL1450_OpeningGround/StaticMeshes/SM_GL1450_OpeningGround'
ASSETS = {**HOUSES, **PROPS, 'paving': PAVING}
SOLID = {*HOUSES, 'wall'}
CROSS_STREETS = (-18300, -10900, -3700, 3600, 11300, 18900)
STREET_AXES = (-19400, -12400, -6200, 0, 6400, 12200, 19300)
# The bend of the main street is pinned to these two X values (the first market
# edges), so story markers and lanterns keep their place beside the street.
CURVE_X = (-4680, 4650)

# --- Street widths, wall to wall. Edit these to re-tune the town. -----------
# Each pair is the range of the distance from a street's centre line to the
# house wall on one side, so a street is roughly twice the value wide.
MAIN_HALF_WIDTH_CM = (290, 345)   # main street 5.8-6.9 m (up to 0.5 m more on the bend)
LANE_HALF_WIDTH_CM = (200, 265)   # the six side lanes 4.0-5.3 m
CROSS_HALF_WIDTH_CM = 190         # cross alleys 3.8 m at the corners, 3.8-4.3 m between
CROSS_CROOK_CM = 35               # how far a cross alley wanders off its straight line
LANE_WAVER_CM = 95                # slow sideways drift of each side lane
LANTERN_MOUTH_HALF_CM = 330       # alley mouths with a lantern post on their centre line
# The market square: from the outer wall of the west central alley to the outer
# wall of the east one, and between house rows 34.5 m north and south of centre.
MARKET_X = (CROSS_STREETS[2] - CROSS_HALF_WIDTH_CM, CROSS_STREETS[3] + CROSS_HALF_WIDTH_CM)
MARKET_HALF_DEPTH_CM = 3450       # the lanterns at Y 3270 stay just inside the square
MARKET_STALL_ROWS_CM = (1450, 2200, 2850)
TOWN_X = (-23900, 23200)          # first and last house line; -23900 starts at the watch gate
TOWN_Y = (-22600, 22600)          # cross-alley rows stop here, short of the palisade
YARD_MOUTH_X = (14500, 15300)     # defended-yard mouth on the main street
YARD_BOX_CM = (14000, 1300, 15800, 3500)
# --- Plots ------------------------------------------------------------------
# How often each house mesh is chosen, per kind of row. The workshop is the
# light mesh (3,300 triangles against 9,600 and 15,000; none of them is Nanite),
# so the long alley rows are nearly all workshops to hold the triangle count.
HOUSE_WEIGHTS = {'street': {'merchants': 2, 'workshop': 9, 'compound': 1},
                 'market': {'merchants': 3, 'workshop': 5, 'compound': 2},
                 'alley': {'merchants': 1, 'workshop': 11, 'compound': 0},
                 'back': {'merchants': 0, 'workshop': 1, 'compound': 0}}
FRONT_WIDTH_CM = {'merchants': (980, 1270), 'workshop': (640, 1010), 'compound': (1010, 1270)}
# Depth as a fraction of the mesh. The merchants' mesh is L-shaped with its door
# in a forecourt; a shallow scale keeps that court under 3.4 m deep.
DEPTH_SCALE = {'merchants': (.44, .54), 'workshop': (.72, .97), 'compound': (.46, .46)}
# Share of merchants' houses turned round so their flat rear wall stands on the
# street line. The rest keep the door-and-forecourt side to the street, which
# reads as a small court but adds about 3 m to the street's width there.
MERCHANTS_FLUSH_SHARE = .65
HOUSE_GAP_CM = (2, 10)            # houses stand shoulder to shoulder
ALLEY_PLOT_STRETCH = 1.25         # wider plots along the cross alleys: fewer, broader houses
MIN_FRONT_CM = 450
# --- Back lanes ---------------------------------------------------------------
# One narrow lane through the middle of every block, entered from the cross
# alley at each end, with deep houses along both sides. It turns the open grass
# inside the blocks into built-up courts with thin private yards behind.
# The pass only adds to the town: it uses its own random stream and runs last,
# so every street house, stall and barrel keeps its exact position. The two
# exceptions: the alley house at each lane mouth is narrowed by the lane's
# width, and an infill house standing in a lane's path is removed.
BACK_LANES = True
BACK_HALF_WIDTH_CM = (120, 145)   # 2.4-2.9 m wall to wall, a little more where a lane slants
BACK_DEPTH_SCALE = (.95, 1.25)    # workshops 9-12 m deep
BACK_WANDER_CM = 70               # sideways bow of a back lane between its two mouths
# --- Plants -------------------------------------------------------------------
# Every static mesh found under PLANT_FOLDER (see import_medieval_london_plants.py)
# is scattered as a 'plant_<mesh name>' group: weeds at the foot of house walls
# and clumps on the open ground inside the palisade. With no plant meshes
# imported the town is generated without them. Plants never block anything.
PLANT_FOLDER = f'{ROOT}/Plants'
PLANT_SPREAD_CM = (50, 120)       # width each plant is grown or shrunk to (the scans are 6-100 cm)
PLANT_SCALE_LIMITS = (.8, 4.0)
PLANT_WALL_SHARE = .4             # chance of each of two weeds at the foot of a house front
PLANT_RING_CLUMPS = 150           # clumps between the outermost houses and the palisade
# --- City fence ---------------------------------------------------------------
# True closes the palisade completely: corner pieces, the short gaps beside each
# gatehouse, and a run of palisade across each gateway just behind its arch, so
# nobody can walk out of the town. False leaves the two gateways open.
FENCE_CLOSED = True
# Forecourt of SM_GLMedieval_MarkLaneMerchantsHouses in mesh space (X depth,
# Y width), measured from its ground-floor vertices on 2026-11-15.
MERCHANTS_FORECOURT_LOCAL_CM = (1329, -2364, 1952, -620)
# Paving strip widths as a Y scale of the 12.1 m paving mesh. The strips are
# left wider than the streets on purpose: the houses now stand on their edges,
# so only the street width shows, set-back courts stay cobbled, and the cobble
# texture is not squeezed (a 4 m strip would stretch it more than 2:1).
# False once ground_medieval_london.py has given the ground block its own
# cobbled streets: the strips are then left out (one piece stays buried so the
# graph keeps its paving branch).
PAVING_STRIPS = False            # the saved map uses the cobbled ground material (2026-11-15)
MAIN_PAVING_SCALE_Y = 1.45        # 17.6 m, under the houses on both sides
LANE_PAVING_SCALE_Y = .82         # 9.9 m
CROSS_PAVING_SCALE_Y = .8         # 9.7 m
# Separately saved landmarks that dressing must not touch: the market well and
# the Guildhall portal (measured actor bounds plus a small margin).
LANDMARK_BOXES_CM = ((-3250, 630, -2950, 930), (2400, 2880, 2550, 3380))
# Ground kept free of stalls, goods and plants for landmarks that other
# sessions place in the map themselves. Houses never stand in the market anyway.
# First box: the walk-in bell tower (bell-tower session): 9 m plinth centred on
# (0, -350) plus 1.5 m, door facing west. It stands on the main street's centre
# line, so through the market the walking route bends north of it; nothing the
# generator places is near it.
RESERVED_BOXES_CM = ((-600, -950, 600, 250),)
# Filled by layout() for tools that plot or audit the plan outside the editor.
LAST_LAYOUT = {}

# Keep a 2.5 m pedestrian strip around the *curved* street centre. Marker
# clearance below is only a geometric guard, not a gameplay interaction test.
WALK_HALF_WIDTH_CM = 125.0
MARKER_CLEARANCE_CM = 100.0
# The separately saved lantern-post pass, as read from the loaded map on
# 2026-11-15 (posts 03/04 stand at Y +-530). The 1 m exclusion exceeds the
# posts' measured 76 x 41 cm XY half-extents.
LANTERN_POINTS_CM = ((-23050, -425), (-23050, 425),
                     (-18300, -530), (-18300, 530),
                     (-10900, -500), (-10900, 500),
                     (-3100, -3270), (-3100, 3270),
                     (3100, -3270), (3100, 3270))
# Sessions allowed to regenerate the town; each must hold Saved/PIE_LOCK.json.
LEASE_OWNERS = ('codex-gray-london', 'fable-streets')


def main_street_center(x):
    """A gentle, deterministic bend from the watch gate into the market."""
    if x <= CURVE_X[0]:
        t = max(0.0, min(1.0, (x + 24080.0) / (CURVE_X[0] + 24080.0)))
        return 180.0 * math.sin(math.pi * t) + 55.0 * math.sin(2.0 * math.pi * t)
    if x <= CURVE_X[1]:
        return 0.0
    return 120.0 * math.sin((x - CURVE_X[1]) / 3200.0)


def curve_bounds(left, right):
    """Bound the curved centre over a plot, including between samples."""
    count = max(1, math.ceil((right - left) / 50.0))
    values = [main_street_center(left + (right - left) * i / count)
              for i in range(count + 1)]
    # Both branches have a derivative below 0.05.  A point between samples is
    # at most half a sample interval away, so this covers the unsampled curve.
    margin = .025 * (right - left) / count
    return min(values) - margin, max(values) + margin


def centered_box(bounds, key, center, yaw, scale=(1, 1, 1)):
    """Conservative XY bounds after the same rotation and scale used by PCG."""
    low, high = bounds[key]
    if (len(low) != 3 or len(high) != 3 or len(scale) != 3 or
            not all(math.isfinite(float(v)) for v in (*low, *high, *center, yaw, *scale)) or
            any(high[i] <= low[i] or scale[i] <= 0 for i in range(3))):
        raise ValueError(f'Invalid mesh bounds or transform for {key}.')
    a = math.radians(yaw)
    c, s = abs(math.cos(a)), abs(math.sin(a))
    x = (high[0] - low[0]) * scale[0] * .5
    y = (high[1] - low[1]) * scale[1] * .5
    hx, hy = c * x + s * y, s * x + c * y
    return (center[0] - hx, center[1] - hy, center[0] + hx, center[1] + hy)


def boxes_overlap(a, b, clearance=0.0):
    return (a[0] < b[2] + clearance and b[0] < a[2] + clearance and
            a[1] < b[3] + clearance and b[1] < a[3] + clearance)


def town_story_points():
    """Reproduce the exact planned marker XY positions without changing actors."""
    from populate_medieval_london_gameplay import LOCATIONS

    project = Path(__file__).resolve().parents[2]
    path = project / 'ArtDirection/WorldJump/graylondon_markers.json'
    rows = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(rows, list) or not rows:
        raise ValueError('The town story-marker source must be a nonempty list.')
    visits = Counter()
    points = []
    for row in rows:
        if row['place'] not in LOCATIONS:
            raise ValueError(f"Unknown town story location: {row['place']}")
        x, y = LOCATIONS[row['place']]
        index = visits[row['place']]
        visits[row['place']] += 1
        if 'CutsceneAnchor_' not in row['name']:
            x += (index % 4) * 120
        if not all(math.isfinite(float(v)) for v in (x, y)):
            raise ValueError(f"Invalid story-marker location: {row['name']}")
        points.append((float(x), float(y), row['name']))
    return points


def lane_center(lane, x):
    """Centre line of an east-west street: the curved main street or a wavering lane."""
    return main_street_center(x) if lane == 0 else lane + LANE_WAVER_CM * math.sin(x / 8800)


def street_bounds(lane, left, right):
    """Lowest and highest centre-line Y of an east-west street over [left, right]."""
    if lane == 0:
        return curve_bounds(left, right)
    ends = lane_center(lane, left), lane_center(lane, right)
    return min(ends) - 1, max(ends) + 1   # the waver is monotonic over any one plot


def alley_center(road, y):
    """Centre line of a north-south cross alley; it wanders, but never off the 2.5 m strip."""
    return road + CROSS_CROOK_CM * math.sin(y / 1700 + road / 1000)


def cross_mouth_half(road):
    """Half-width of a cross alley where it meets the main street."""
    lantern = any(abs(x - road) < 100 and abs(y) < 1000 for x, y in LANTERN_POINTS_CM)
    return LANTERN_MOUTH_HALF_CM if lantern else CROSS_HALF_WIDTH_CM


def free_intervals(low, high, blocked):
    """Parts of [low, high] not covered by a blocked interval and wide enough for a house."""
    result, cursor = [], low
    for a, b in sorted(blocked):
        if a > cursor:
            result.append((cursor, min(a, high)))
        cursor = max(cursor, b)
        if cursor >= high:
            break
    if cursor < high:
        result.append((cursor, high))
    return [(a, b) for a, b in result if b - a >= MIN_FRONT_CM]


def layout(bounds, existing_house_boxes=None):
    """Pack narrow lanes: house rows on every street, alley and market edge, then dressing."""
    randomizer = random.Random(1450)
    groups = defaultdict(list)
    story = town_story_points()
    keepouts = story + [(float(x), float(y), f'lantern_{i}')
                        for i, (x, y) in enumerate(LANTERN_POINTS_CM)]
    houses = []
    forecourts = []
    prop_boxes = list(LANDMARK_BOXES_CM)
    # Inset in X so the wandering alley rows on its east and west edges still fit.
    market_box = (MARKET_X[0] + CROSS_CROOK_CM + 5, -MARKET_HALF_DEPTH_CM,
                  MARKET_X[1] - CROSS_CROOK_CM - 5, MARKET_HALF_DEPTH_CM)
    no_build = (market_box, YARD_BOX_CM)
    skipped = Counter()
    placed = Counter()
    registry = []   # (box, mesh key, index in its group, row label) of every house
    prop_registry = []   # (box, mesh key, index in its group) of every stall, crate pile and cask
    fronts = []     # (axis, side, left, right, wall line, (mesh key, index)) of every row house

    def place(key, center, yaw=0, scale=(1, 1, 1)):
        low, high = bounds[key]
        x = (low[0] + high[0]) * .5 * scale[0]
        y = (low[1] + high[1]) * .5 * scale[1]
        angle = math.radians(yaw)
        c, s = math.cos(angle), math.sin(angle)
        pivot = (center[0] - (c * x - s * y), center[1] - (s * x + c * y),
                 center[2] - low[2] * scale[2])
        groups[key].append((pivot, yaw, scale, randomizer.randrange(1, 2**30)))
        return pivot

    def plot_width(key, room, stretch=1.0):
        low, high = (value * stretch for value in FRONT_WIDTH_CM[key])
        width = randomizer.uniform(low, high)
        if room - width < MIN_FRONT_CM + HOUSE_GAP_CM[1]:
            # Never leave a sliver before the corner: stretch to it, or split the rest in two.
            width = room if room <= high * 1.12 else (room - HOUSE_GAP_CM[1]) / 2
        return width

    def house_row(axis, side, start, end, frontage, label):
        """Stand houses shoulder to shoulder along one side of a street.

        axis 'x': the street runs east-west; u is world X and v is world Y.
        axis 'y': the street runs north-south; u is world Y and v is world X.
        side +1 puts the houses on the +v side, facing back across the street.
        frontage(u0, u1) gives the v coordinate of the wall line for one plot.
        """
        yaw = -side * 90 if axis == 'x' else (180 if side > 0 else 0)
        marks = [(mx, my) if axis == 'x' else (my, mx) for mx, my, _ in keepouts]
        clear = MARKER_CLEARANCE_CM
        u = start + randomizer.uniform(0, 6)
        while end - u >= MIN_FRONT_CM:
            weights = HOUSE_WEIGHTS[label]
            key = randomizer.choices(tuple(weights), tuple(weights.values()))[0]
            left, right = u, u + plot_width(key, end - u, ALLEY_PLOT_STRETCH if label in ('alley', 'back') else 1.0)
            low, high = bounds[key]
            depth_scale = BACK_DEPTH_SCALE if label == 'back' else DEPTH_SCALE[key]
            depth = min((high[0] - low[0]) * randomizer.uniform(*depth_scale), 2010)
            height = randomizer.uniform(.78, 1.10)
            inside = frontage(left, right)
            # End a plot just before a marker when a useful-sized frontage fits
            # there. This confines any required set-back to the next plot.
            v0, v1 = sorted((inside, inside + side * depth))
            cuts = [mu - clear - 1 for mu, mv in marks
                    if left + MIN_FRONT_CM + clear + 1 <= mu <= right + clear
                    and v0 - clear <= mv <= v1 + clear]
            if cuts:
                right = min(right, min(cuts))
                inside = frontage(left, right)
            if right - left < FRONT_WIDTH_CM[key][0] * .75:
                key = 'workshop'   # the two big meshes look squashed on a narrow plot
                low, high = bounds[key]
                depth = min(depth, (high[0] - low[0]) * DEPTH_SCALE[key][1])
            workshop_depth = bounds['workshop'][1][0] - bounds['workshop'][0][0]
            options = [(key, depth * f) for f in (1, .8, .62)]
            options += [('workshop', workshop_depth * f) for f in (.72, .56, .44)]
            for option, option_depth in options:
                low, high = bounds[option]
                mesh_width, mesh_depth = high[1] - low[1], high[0] - low[0]
                wall = inside
                # Keep each authored marker position outside the entire
                # conservative house box, leaving 1 m around its XY point.
                for _ in range(len(marks) + 1):
                    v0, v1 = sorted((wall, wall + side * option_depth))
                    conflicts = [mv for mu, mv in marks
                                 if left - clear <= mu <= right + clear
                                 and v0 - clear <= mv <= v1 + clear]
                    if not conflicts:
                        break
                    limit = (max(conflicts) + clear + 1 if side > 0
                             else min(conflicts) - clear - 1)
                    wall = max(wall, limit) if side > 0 else min(wall, limit)
                else:
                    raise RuntimeError('Could not keep town story points clear of a house.')
                scale = (option_depth / mesh_depth, (right - left) / mesh_width, height)
                along, across = (left + right) * .5, wall + side * option_depth * .5
                center = (along, across, 0) if axis == 'x' else (across, along, 0)
                actual = centered_box(bounds, option, center, yaw, scale)
                if (any(boxes_overlap(actual, other) for other in houses) or
                        any(boxes_overlap(actual, box) for box in no_build)):
                    continue
                houses.append(actual)
                placed[label, option] += 1
                flush = option == 'merchants' and randomizer.random() < MERCHANTS_FLUSH_SHARE
                pivot = place(option, center, yaw + 180 if flush else yaw, scale)
                registry.append((actual, option, len(groups[option]) - 1, label))
                fronts.append((axis, side, left, right, wall, (option, len(groups[option]) - 1)))
                if option == 'merchants' and not flush:
                    forecourts.append((pivot, yaw, scale))
                u = right + randomizer.uniform(*HOUSE_GAP_CM)
                break
            else:
                skipped[label] += 1   # no room: a house already backs onto this spot
                u += 150

    # 1. East-west streets: the curved main street first, then the six lanes.
    for lane in sorted(STREET_AXES, key=abs):
        main = lane == 0
        if main:
            openings = [(road - cross_mouth_half(road), road + cross_mouth_half(road))
                        for road in CROSS_STREETS]
            openings = [o for o in openings if o[1] < MARKET_X[0] or o[0] > MARKET_X[1]]
            openings.extend((MARKET_X, YARD_MOUTH_X))  # market and defended-yard mouth
        else:
            openings = [(road - CROSS_HALF_WIDTH_CM, road + CROSS_HALF_WIDTH_CM)
                        for road in CROSS_STREETS]
        half = MAIN_HALF_WIDTH_CM if main else LANE_HALF_WIDTH_CM
        borders = [TOWN_X[0], *[x for opening in sorted(openings) for x in opening], TOWN_X[1]]
        for side in (-1, 1):
            def frontage(left, right, lane=lane, side=side, half=half):
                low, high = street_bounds(lane, left, right)
                return (high if side > 0 else low) + side * randomizer.uniform(*half)
            for left, right in zip(borders[::2], borders[1::2]):
                house_row('x', side, left, right, frontage, 'street')
        if main:
            # 2. Wall in the market on its north and south sides. Its east and
            # west sides are the outer rows of the two central cross alleys.
            for side in (-1, 1):
                def market_wall(left, right, side=side):
                    return side * (MARKET_HALF_DEPTH_CM + randomizer.uniform(0, 30))
                house_row('x', side, MARKET_X[0] + 2 * CROSS_HALF_WIDTH_CM,
                          MARKET_X[1] - 2 * CROSS_HALF_WIDTH_CM, market_wall, 'market')

    # 3. Cross alleys: fill every stretch between the corner houses so each
    # alley is a walled lane instead of a view across open back yards.
    reach = max(MAIN_HALF_WIDTH_CM[1] + 40, LANE_HALF_WIDTH_CM[1] + 10)
    for road in CROSS_STREETS:
        for side in (-1, 1):
            edge = road + side * CROSS_HALF_WIDTH_CM
            far = edge + side * (450 + CROSS_CROOK_CM)
            strip = (min(edge, far), TOWN_Y[0], max(edge, far), TOWN_Y[1])
            blocked = [(lane_center(lane, road) - reach, lane_center(lane, road) + reach)
                       for lane in STREET_AXES]
            blocked += [(box[1] - 3, box[3] + 3) for box in [*houses, *no_build]
                        if boxes_overlap(box, strip)]
            for low_y, high_y in free_intervals(TOWN_Y[0], TOWN_Y[1], blocked):
                def alley_wall(a, b, road=road, side=side):
                    return alley_center(road, (a + b) * .5) + side * (
                        CROSS_HALF_WIDTH_CM + randomizer.uniform(0, 25))
                house_row('y', side, low_y, high_y, alley_wall, 'alley')

    # Paving follows each street's centre line and runs under the house fronts.
    # Neighbouring pieces overlap a little; alternate their height by a few
    # millimetres so the overlap cannot flicker.
    def pave(index, center, yaw, scale):
        if PAVING_STRIPS:
            place('paving', (center[0], center[1], center[2] + .4 * (index % 2)), yaw, scale)

    for index, x in enumerate(range(-23800, 24400, 1450)):
        pave(index, (x, main_street_center(x), 0), 0, (1, MAIN_PAVING_SCALE_Y, .16))
    for lane in STREET_AXES:
        if lane:
            for index, x in enumerate(range(-22800, 22900, 1940)):
                pave(index, (x, lane_center(lane, x), -2), 0, (1.35, LANE_PAVING_SCALE_Y, .15))
    for x in CROSS_STREETS:
        for index, y in enumerate(range(-22500, 22600, 1400)):
            pave(index, (x, y, -3), 90, (1, CROSS_PAVING_SCALE_Y, .11))
    # The whole market square is cobbled, wall to wall.
    for column, x in enumerate(range(MARKET_X[0] + 540, MARKET_X[1] + 700, 1400)):
        for row, y in enumerate((-3550, -2400, -1200, 1200, 2400, 3550)):
            pave(column + row, (x, y, -1), 0, (1, 1.08, .15))
    if not PAVING_STRIPS:
        place('paving', (0, 0, -400), 0, (1, 1, .1))

    for x in (-24200, 24200):
        place('gate', (x, 0, 0), 0 if x < 0 else 180, (1.25, 1.6, 1.35))
        for y in range(-24000, 24200, 242):
            if abs(y) >= 630:
                place('wall', (x, y, 0), 0, (1, 1.33, 1.45))
    for y in (-24200, 24200):
        for x in range(-24000, 24200, 242):
            place('wall', (x, y, 0), 90, (1, 1.33, 1.45))

    def marker_near(box):
        return any(box[0] - MARKER_CLEARANCE_CM <= mx <= box[2] + MARKER_CLEARANCE_CM and
                   box[1] - MARKER_CLEARANCE_CM <= my <= box[3] + MARKER_CLEARANCE_CM
                   for mx, my, _ in keepouts)

    def place_dressing(key, desired_x, side, yaw, lane=0, market_y=None):
        """Skip crowded candidates rather than blocking houses or the route."""
        for dx in (0, -200, 200, -400, 400, -600, 600):
            x = desired_x + dx
            # The cross-alley mouths and defended-yard mouth stay empty.
            if market_y is None and (
                    any(abs(x - road) < LANTERN_MOUTH_HALF_CM + 120 for road in CROSS_STREETS) or
                    (lane == 0 and YARD_MOUTH_X[0] - 200 < x < YARD_MOUTH_X[1] + 200)):
                continue
            probe = centered_box(bounds, key, (x, 0, 4), yaw)
            half_y = (probe[3] - probe[1]) * .5
            curve_low, curve_high = street_bounds(lane, probe[0], probe[2])
            if market_y is not None:
                y = market_y
            else:
                y = (curve_high + WALK_HALF_WIDTH_CM + half_y + 5 if side > 0
                     else curve_low - WALK_HALF_WIDTH_CM - half_y - 5)
            center = (x, y, 4)
            box = centered_box(bounds, key, center, yaw)
            if any(boxes_overlap(box, other, 5) for other in houses + prop_boxes) or marker_near(box):
                continue
            if side > 0 and box[1] < curve_high + WALK_HALF_WIDTH_CM:
                continue
            if side < 0 and box[3] > curve_low - WALK_HALF_WIDTH_CM:
                continue
            prop_boxes.append(box)
            place(key, center, yaw)
            prop_registry.append((box, key, len(groups[key]) - 1))
            return True
        return False

    # Main street: a stall with its goods every dozen metres, alternating
    # sides, and loose goods against the opposite wall.
    for index, x in enumerate(range(-23300, 23000, 1250)):
        if MARKET_X[0] - 300 < x < MARKET_X[1] + 300:
            continue
        side = 1 if index % 2 else -1
        x += randomizer.randrange(-150, 151)
        place_dressing('stall', x, side, -side * 90)
        place_dressing('crates', x + 185, side, randomizer.randrange(360))
        place_dressing('cask', x - 185, side, randomizer.randrange(360))
        place_dressing(randomizer.choice(('crates', 'cask')), x + 520, -side, randomizer.randrange(360))
    # Market square: stall rows on each side of the through route.
    for row_y in MARKET_STALL_ROWS_CM:
        for x in range(MARKET_X[0] + 700, MARKET_X[1] - 600, 900):
            for side in (-1, 1):
                x_here = x + randomizer.randrange(-120, 121)
                place_dressing('stall', x_here, side, -side * 90, market_y=side * row_y)
                place_dressing('crates', x_here + 185, side, randomizer.randrange(360), market_y=side * row_y)
                place_dressing('cask', x_here - 185, side, randomizer.randrange(360), market_y=side * row_y)
    # Side lanes are too narrow for stalls: goods stand against the walls,
    # turned so their slim side faces the lane.
    for lane in STREET_AXES:
        if lane:
            for index, x in enumerate(range(-23500, 23000, 780)):
                side = 1 if (index + lane // 100) % 2 else -1
                key = randomizer.choice(('crates', 'cask', 'cask'))
                yaw = randomizer.choice((90, 270) if key == 'crates' else (0, 180))
                place_dressing(key, x + randomizer.randrange(-200, 201), side, yaw, lane)

    # Merchants' houses are L-shaped: a wing reaches the street and the door
    # stands in a shallow forecourt beside it. Trade spills into most of them.
    x0, y0, x1, y1 = MERCHANTS_FORECOURT_LOCAL_CM
    for pivot, yaw, scale in forecourts:
        angle = math.radians(yaw)
        c, s = math.cos(angle), math.sin(angle)
        court_depth, court_width = (x1 - x0) * scale[0], (y1 - y0) * scale[1]
        if court_width < 520 or court_depth < 230:
            continue
        for key, along, chance in (('stall', 0, .6), ('crates', -.32, .7), ('cask', .32, .7)):
            if randomizer.random() > chance:
                continue
            # Stand goods at the street edge of the court so the door stays reachable.
            local = (x1 * scale[0] - 85, ((y0 + y1) * .5 + along * (y1 - y0)) * scale[1])
            center = (pivot[0] + c * local[0] - s * local[1], pivot[1] + s * local[0] + c * local[1], 4)
            box = centered_box(bounds, key, center, yaw)
            if any(boxes_overlap(box, other, 5) for other in prop_boxes) or marker_near(box):
                continue
            prop_boxes.append(box)
            place(key, center, yaw)
            prop_registry.append((box, key, len(groups[key]) - 1))

    # A second defended yard is visible at the far end of the market route.
    place('gate', (14900, 2400, 0), 0, (1.1, 1.2, 1.1))
    for y in (1680, 1910, 2890, 3120):
        place('wall', (14900, y, 0), 0, (1, 1.3, 1.2))

    # Fill the deep interiors between the existing street-front rows. Keep the
    # authored frontages and their entrances in place, with narrow alleys
    # between the added houses and every existing building.
    if existing_house_boxes is not None:
        houses = list(existing_house_boxes)
    infill_rng = random.Random(145071)
    low, high = bounds['workshop']
    mesh_depth, mesh_width = high[0] - low[0], high[1] - low[1]
    cross_clear = CROSS_HALF_WIDTH_CM + CROSS_CROOK_CM + 40
    for band, (south, north) in enumerate(zip(STREET_AXES, STREET_AXES[1:])):
        for x in range(-22000 + (band % 2) * 400, 22500, 1050):
            width = infill_rng.uniform(800, 950)
            depth = infill_rng.uniform(740, 900)
            left, right = x - width * .5, x + width * .5
            if any(left < road + cross_clear and right > road - cross_clear for road in CROSS_STREETS):
                continue
            candidates = []
            y = south + 1300
            while y <= north - 1300:
                box = (left, y - depth * .5, right, y + depth * .5)
                # Preserve the market square and defended yard around their landmarks.
                if (any(boxes_overlap(box, area) for area in no_build) or
                        any(boxes_overlap(box, other, 150) for other in houses + prop_boxes) or
                        any(box[0] - 150 <= mx <= box[2] + 150 and
                            box[1] - 150 <= my <= box[3] + 150 for mx, my, _ in keepouts)):
                    y += 150
                    continue
                # Prefer a small alley to an isolated building in an empty block.
                distance = min(math.hypot(max(h[0] - box[2], box[0] - h[2], 0),
                                          max(h[1] - box[3], box[1] - h[3], 0))
                               for h in houses)
                if distance <= 850:
                    candidates.append((distance, y, box))
                y += 150
            if not candidates:
                continue
            _, y, box = min(candidates)
            side = 1 if y - south < north - y else -1
            scale = (depth / mesh_depth, width / mesh_width, infill_rng.uniform(.83, 1.07))
            houses.append(box)
            placed['infill', 'workshop'] += 1
            place('workshop', (x, y, 0), -side * 90, scale)
            registry.append((box, 'workshop', len(groups['workshop']) - 1, 'infill'))

    # Everything below uses its own random stream, so it cannot move anything above.
    randomizer = random.Random(1451)

    # 4. Close the city fence (see FENCE_CLOSED above).
    if FENCE_CLOSED:
        for x in (-24200, 24200):
            for y in (-24200, 24200):
                place('wall', (x, y, 0), 0, (1, 1.33, 1.45))          # corner posts
            for y in (-690, 690):
                place('wall', (x, y, 0), 0, (1, 1.33, 1.45))          # beside the gatehouse
            behind = x - 70 if x < 0 else x + 70
            for y in range(-605, 606, 242):
                place('wall', (behind, y, 0), 0, (1, 1.33, 1.45))     # across the gateway

    # 5. Back lanes through the block interiors (see BACK_LANES above).
    back_lanes, removed, removed_boxes = [], set(), []
    first_added = len(registry)
    # Clear the reserved landmark ground. Dropping goods here, after everything
    # is placed, leaves all the other stalls and goods exactly where they were.
    for box, key, index in prop_registry:
        if any(boxes_overlap(box, area) for area in RESERVED_BOXES_CM):
            removed.add((key, index))
            prop_boxes.remove(box)
    if BACK_LANES:
        def drop(entry):
            removed.add((entry[1], entry[2]))
            removed_boxes.append(entry[0])
            if entry[0] in houses:
                houses.remove(entry[0])

        def mouth(road, side, target, south, north):
            """Narrow one alley workshop by the lane's width; return the lane's Y and half-width there."""
            edge = road + side * CROSS_HALF_WIDTH_CM
            half = randomizer.uniform(*BACK_HALF_WIDTH_CM)
            candidates = []
            for entry in registry:
                box, key, index, label = entry
                wall = box[0] if side > 0 else box[2]
                if (label == 'alley' and key == 'workshop' and (key, index) not in removed and
                        abs(wall - edge) < 75 and south + 900 < (box[1] + box[3]) * .5 < north - 900 and
                        box[3] - box[1] >= MIN_FRONT_CM + 2 * half):
                    candidates.append((abs((box[1] + box[3]) * .5 - target), entry))
            if not candidates:
                return None
            entry = min(candidates)[1]
            box, key, index, _ = entry
            _, yaw, scale, _ = groups[key][index]
            cut_north = target >= (box[1] + box[3]) * .5
            kept = ((box[0], box[1], box[2], box[3] - 2 * half) if cut_north
                    else (box[0], box[1] + 2 * half, box[2], box[3]))
            lane_y = box[3] - half if cut_north else box[1] + half
            new_scale = (scale[0], scale[1] * (kept[3] - kept[1]) / (box[3] - box[1]), scale[2])
            drop(entry)
            houses.append(kept)
            place(key, ((kept[0] + kept[2]) * .5, (kept[1] + kept[3]) * .5, 0), yaw, new_scale)
            registry.append((kept, key, len(groups[key]) - 1, 'mouth'))
            return lane_y, half

        columns = [TOWN_X[0], *CROSS_STREETS, TOWN_X[1]]
        for column in range(len(columns) - 1):
            west_road = CROSS_STREETS[column - 1] if column > 0 else None
            east_road = CROSS_STREETS[column] if column < len(CROSS_STREETS) else None
            x_w = west_road + CROSS_HALF_WIDTH_CM if west_road is not None else TOWN_X[0]
            x_e = east_road - CROSS_HALF_WIDTH_CM if east_road is not None else TOWN_X[1]
            for south, north in zip(STREET_AXES, STREET_AXES[1:]):
                if any(boxes_overlap((x_w, south, x_e, north), area) for area in no_build):
                    continue
                target = (south + north) * .5 + randomizer.uniform(-250, 250)
                west = mouth(west_road, 1, target, south, north) if west_road is not None else None
                east = (mouth(east_road, -1, west[0] if west else target, south, north)
                        if east_road is not None else None)
                if not west and not east:
                    continue
                y_w, half_w = west or east
                y_e, half_e = east or west
                half = max(half_w, half_e)
                bow = randomizer.choice((-1, 1)) * BACK_WANDER_CM

                def lane_y(x, x_w=x_w, x_e=x_e, y_w=y_w, y_e=y_e, bow=bow):
                    t = (x - x_w) / (x_e - x_w)
                    return y_w + (y_e - y_w) * t + bow * math.sin(math.pi * t)

                def lane_bounds(left, right, lane_y=lane_y):
                    values = [lane_y(left + (right - left) * i / 6) for i in range(7)]
                    return min(values) - 3, max(values) + 3

                for entry in list(registry):
                    box = entry[0]
                    if (entry[3] == 'infill' and (entry[1], entry[2]) not in removed and
                            box[0] < x_e and box[2] > x_w):
                        low_y, high_y = lane_bounds(max(box[0], x_w), min(box[2], x_e))
                        if box[1] < high_y + half + 25 and box[3] > low_y - half - 25:
                            drop(entry)
                for side in (-1, 1):
                    blocked = []
                    for box in houses:
                        if box[0] < x_e and box[2] > x_w:
                            low_y, high_y = lane_bounds(max(box[0], x_w), min(box[2], x_e))
                            band = (low_y, high_y + half + 350) if side > 0 else (low_y - half - 350, high_y)
                            if box[1] < band[1] and box[3] > band[0]:
                                blocked.append((box[0] - 3, box[2] + 3))

                    def back_wall(left, right, side=side, half=half, lane_bounds=lane_bounds):
                        low_y, high_y = lane_bounds(left, right)
                        return (high_y if side > 0 else low_y) + side * (half + randomizer.uniform(0, 20))
                    for left, right in free_intervals(x_w, x_e, blocked):
                        house_row('x', side, left, right, back_wall, 'back')
                back_lanes.append({'half_width': round(half, 1),
                                   'centre': [[x, round(lane_y(x), 1)] for x in range(int(x_w), int(x_e) + 1, 100)]})
    # 6. Plants (see PLANT_FOLDER above), again on their own random stream.
    plant_keys = sorted(key for key in bounds if key.startswith('plant_'))
    if plant_keys:
        randomizer = random.Random(1452)

        def plant(x, y):
            if (any(abs(x - mx) < 130 and abs(y - my) < 130 for mx, my, _ in keepouts) or
                    any(area[0] < x < area[2] and area[1] < y < area[3] for area in RESERVED_BOXES_CM)):
                return
            key = randomizer.choice(plant_keys)
            low, high = bounds[key]
            spread = max(high[0] - low[0], high[1] - low[1], 1)
            size = min(PLANT_SCALE_LIMITS[1], max(PLANT_SCALE_LIMITS[0], randomizer.uniform(*PLANT_SPREAD_CM) / spread))
            # The ground block's surface is 5 cm below the house floors.
            place(key, (x, y, -5), randomizer.uniform(0, 360), (size, size, size))

        for axis, side, left, right, wall, ident in fronts:
            if ident in removed or right - left < 200:
                continue
            for _ in range(2):
                if randomizer.random() < PLANT_WALL_SHARE:
                    along = randomizer.uniform(left + 50, right - 50)
                    across = wall - side * randomizer.uniform(12, 30)
                    plant(*((along, across) if axis == 'x' else (across, along)))
        clumps = 0
        for _ in range(PLANT_RING_CLUMPS * 40):
            if clumps >= PLANT_RING_CLUMPS:
                break
            x, y = randomizer.uniform(-24000, 24000), randomizer.uniform(-24000, 24000)
            if (not (abs(x) > 23300 or abs(y) > 21750) or
                    any(abs(y - lane_center(lane, x)) < 450 for lane in STREET_AXES) or
                    any(abs(x - road) < 330 for road in CROSS_STREETS) or
                    any(box[0] - 150 < x < box[2] + 150 and box[1] - 150 < y < box[3] + 150 for box in houses)):
                continue
            clumps += 1
            for _ in range(randomizer.randrange(3, 7)):
                plant(x + randomizer.uniform(-130, 130), y + randomizer.uniform(-130, 130))

    for key in {key for key, _ in removed}:
        groups[key] = [row for index, row in enumerate(groups[key]) if (key, index) not in removed]

    check_layout(houses, prop_boxes, keepouts)
    LAST_LAYOUT.clear()
    LAST_LAYOUT.update(houses=list(houses), props=list(prop_boxes), skipped=dict(skipped),
                       placed={f'{label} {key}': count for (label, key), count in sorted(placed.items())},
                       back_lanes=back_lanes, removed_boxes=removed_boxes,
                       added_boxes=[entry[0] for entry in registry[first_added:]])
    return dict(groups)


def check_layout(houses, props, keepouts):
    """Refuse a town with touching houses, a covered marker, or a blocked street."""
    ordered = sorted(houses)
    for index, a in enumerate(ordered):
        for b in ordered[index + 1:]:
            if b[0] >= a[2]:
                break
            if boxes_overlap(a, b):
                raise RuntimeError(f'Planned houses overlap: {a} and {b}')
    for mx, my, name in keepouts:
        for box in houses:
            if (box[0] - MARKER_CLEARANCE_CM < mx < box[2] + MARKER_CLEARANCE_CM and
                    box[1] - MARKER_CLEARANCE_CM < my < box[3] + MARKER_CLEARANCE_CM):
                raise RuntimeError(f'{name} is closer than 1 m to a house.')
    solid = [*houses, *props]
    for box in solid:
        for lane in STREET_AXES:
            low, high = street_bounds(lane, box[0], box[2])
            if box[1] < high + WALK_HALF_WIDTH_CM and box[3] > low - WALK_HALF_WIDTH_CM:
                raise RuntimeError(f'The 2.5 m walking strip of street {lane} is blocked by {box}.')
        for road in CROSS_STREETS:
            if box[0] < road + WALK_HALF_WIDTH_CM and box[2] > road - WALK_HALF_WIDTH_CM:
                raise RuntimeError(f'The 2.5 m walking strip of alley {road} is blocked by {box}.')


def require_town_editor(unreal):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    saved = Path(unreal.Paths.project_saved_dir())
    lease = json.loads((saved / 'PIE_LOCK.json').read_text(encoding='utf-8-sig'))
    if (not world or world.get_package().get_name() != MAP or editor.get_game_world() or
            lease.get('owner') not in LEASE_OWNERS or lease['expires_epoch'] < time.time() + 120):
        raise RuntimeError('Open the owned Medieval London map outside Play under the authoring lease.')
    return editor, world


def load_layout(unreal):
    meshes = {key: unreal.EditorAssetLibrary.load_asset(path) for key, path in ASSETS.items()}
    if any(not isinstance(mesh, unreal.StaticMesh) for mesh in meshes.values()):
        raise RuntimeError('A required existing London static mesh is missing.')
    if unreal.EditorAssetLibrary.does_directory_exist(PLANT_FOLDER):
        for path in sorted(unreal.EditorAssetLibrary.list_assets(PLANT_FOLDER, recursive=True, include_folder=False)):
            asset = unreal.EditorAssetLibrary.load_asset(path)
            if isinstance(asset, unreal.StaticMesh):
                meshes[f'plant_{asset.get_name()}'] = asset
    bounds = {}
    for key, mesh in meshes.items():
        box = mesh.get_bounding_box()
        bounds[key] = tuple(tuple(getattr(v, a) for a in 'xyz') for v in (box.min, box.max))
    return meshes, layout(bounds)


async def run():
    import unreal

    editor, world = require_town_editor(unreal)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if any(a.get_actor_label() == 'Medieval London | Market Street' for a in actors.get_all_level_actors()):
        raise RuntimeError('The town has already been placed.')

    meshes, groups = load_layout(unreal)

    def spawn(cls, label, location, rotation=(0, 0, 0)):
        actor = actors.spawn_actor_from_class(cls, unreal.Vector(*location), unreal.Rotator(*rotation))
        if not actor:
            raise RuntimeError(f'Could not create {label}.')
        actor.set_actor_label(label)
        return actor

    floor = spawn(unreal.StaticMeshActor, 'Ground | City footprint 500 m', (0, 0, -55))
    floor_mesh = floor.get_component_by_class(unreal.StaticMeshComponent)
    floor_mesh.set_static_mesh(unreal.EditorAssetLibrary.load_asset('/Engine/BasicShapes/Cube'))
    floor.set_actor_scale3d(unreal.Vector(500, 500, 1))
    floor_mesh.set_collision_profile_name('BlockAll')
    cobbles = unreal.EditorAssetLibrary.load_asset(f'{ROOT}/Ground/SM_GL1450_OpeningGround/Materials/M_GL1450_WornCobblesAndEarth')
    if cobbles:
        floor_mesh.set_material(0, cobbles)

    start = spawn(unreal.PlayerStart, 'Player Start | Watch Gate to Market', (-24080, 0, 100))
    start.set_editor_property('player_start_tag', 'Lanthorne')
    light = spawn(unreal.DirectionalLight, 'Daylight | Morning', (0, 0, 600), (0, -34, -125))
    light_component = light.get_component_by_class(unreal.DirectionalLightComponent)
    light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    light_component.set_editor_property('intensity', 5.0)
    spawn(unreal.SkyAtmosphere, 'Sky | London', (0, 0, 0))
    sky = spawn(unreal.SkyLight, 'Sky fill', (0, 0, 500))
    sky_component = sky.get_component_by_class(unreal.SkyLightComponent)
    sky_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    sky_component.set_editor_property('real_time_capture', True)

    pcg = unreal.get_editor_subsystem(unreal.PCGEditorSubsystem)
    graph = unreal.EditorAssetLibrary.load_asset(f'{GRAPH_DIR}/{GRAPH_NAME}')
    if not graph:
        graph = pcg.create_graph(GRAPH_NAME, GRAPH_DIR)
        populate_point_mesh_graph(unreal, pcg, graph, groups, meshes, solid_meshes=SOLID)
    info = pcg.spawn_graph_instance(graph, 'Medieval London | Market Street', cell_transform(unreal, groups))
    volume = info.get_editor_property('actor')
    component = volume.get_component_by_class(unreal.PCGComponent)
    component.set_editor_properties({'generation_trigger': unreal.PCGComponentGenerationTrigger.GENERATE_ON_DEMAND,
                                     'generate_on_drop_when_trigger_on_demand': False,
                                     'regenerate_in_editor': False, 'is_component_partitioned': False})
    return await generate_and_save(unreal, editor, world, pcg, graph, volume, meshes, groups)


async def repack(save=True):
    """Apply revised plots to the saved town while preserving its gameplay actors.

    `await repack(save=False)` regenerates without saving, so the result can be
    looked at first; `save_town()` then saves the map and the town graph.
    """
    import unreal

    editor, world = require_town_editor(unreal)
    graph = unreal.EditorAssetLibrary.load_asset(f'{GRAPH_DIR}/{GRAPH_NAME}')
    volume, = (actor for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.PCGVolume)
               if actor.get_actor_label() == 'Medieval London | Market Street')
    meshes, groups = load_layout(unreal)
    sources = {str(node.get_editor_property('node_title')).removeprefix('Points '): node.get_settings()
               for node in graph.get_editor_property('nodes')
               if isinstance(node.get_settings(), unreal.PCGCreatePointsSettings)}
    new_keys = sorted(set(groups) - set(sources))
    if any(not key.startswith('plant_') for key in new_keys) or any(key not in sources for key in ASSETS):
        raise RuntimeError('The saved town graph no longer matches the placement groups.')
    pcg = unreal.get_editor_subsystem(unreal.PCGEditorSubsystem)
    was_paused = pcg.is_graph_automatic_regeneration_paused(graph)
    pcg.set_graph_automatic_regeneration_paused(graph, True)
    try:
        graph.modify()
        for key, settings in sources.items():
            settings.modify()
            # A plant branch whose mesh is gone simply gets no points.
            settings.set_editor_property('points_to_create', [make_point(unreal, row) for row in groups.get(key, ())])
        output = graph.get_output_node()
        for offset, key in enumerate(new_keys):
            # A new plant mesh gets its own Create Points -> Static Mesh Spawner branch.
            source, settings = graph.add_node_of_type(unreal.PCGCreatePointsSettings)
            settings.set_editor_properties({
                'coordinate_space': unreal.PCGCoordinateSpace.WORLD,
                'cull_points_outside_volume': False,
                'points_to_create': [make_point(unreal, row) for row in groups[key]],
            })
            source.set_editor_property('node_title', f'Points {key}')
            source.set_node_position(0, (len(sources) + offset) * 180)
            spawner, spawn_settings = graph.add_node_of_type(unreal.PCGStaticMeshSpawnerSettings)
            configure_spawner(unreal, spawn_settings, meshes[key], solid=False)
            spawner.set_editor_property('node_title', key)
            spawner.set_node_position(360, (len(sources) + offset) * 180)
            if (not pcg.try_add_edge(source, 'Out', spawner, 'In') or
                    not pcg.try_add_edge(spawner, 'Out', output, 'Out')):
                raise RuntimeError(f'Could not connect the PCG branch for {key}.')
    finally:
        pcg.set_graph_automatic_regeneration_paused(graph, was_paused)
    start, = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.PlayerStart)
    start.set_actor_location(unreal.Vector(-24080, 0, 100), False, True)
    return await generate_and_save(unreal, editor, world, pcg, graph, volume, meshes, groups, save=save)


def save_town():
    """Save only the town map and its PCG graph, e.g. after `repack(save=False)`."""
    import unreal

    editor, world = require_town_editor(unreal)
    graph = unreal.EditorAssetLibrary.load_asset(f'{GRAPH_DIR}/{GRAPH_NAME}')
    packages = [world.get_package(), graph.get_package()]
    if [p.get_name() for p in packages] != [MAP, f'{GRAPH_DIR}/{GRAPH_NAME}']:
        raise RuntimeError('Unexpected packages for the new map and town graph.')
    if not unreal.EditorLoadingAndSavingUtils.save_packages(packages, only_dirty=False):
        raise RuntimeError('Could not save the new map and town graph.')
    return [p.get_name() for p in packages]


def rebuild_navigation():
    """Ask for a fresh static navmesh after the houses move; save the map once it is built."""
    import unreal

    _, world = require_town_editor(unreal)
    unreal.SystemLibrary.execute_console_command(world, 'RebuildNavigation')
    return 'navigation rebuild requested'


async def generate_and_save(unreal, editor, world, pcg, graph, volume, meshes, groups, save=True):
    component = volume.get_component_by_class(unreal.PCGComponent)
    pending = (pcg.wait_for_graph_instance(component) if component.get_editor_property('generation_in_progress')
               else pcg.execute_graph_instance(component))
    deadline = time.monotonic() + 40
    while not pending.get_editor_property('is_complete'):
        if time.monotonic() > deadline:
            raise RuntimeError('Town PCG generation did not finish.')
        await asyncio.sleep(.15)
    if pending.get_editor_property('error'):
        raise RuntimeError(pending.get_editor_property('error'))

    reverse = {mesh.get_path_name(): key for key, mesh in meshes.items()}
    counts = Counter()
    for ism in volume.get_components_by_class(unreal.InstancedStaticMeshComponent):
        mesh = ism.get_editor_property('static_mesh')
        key = reverse[mesh.get_path_name()]
        if key in SOLID and str(ism.get_collision_profile_name()) != 'BlockAll':
            raise RuntimeError(f'Generated {key} has no blocking collision.')
        counts[key] += ism.get_instance_count()
    if {key: count for key, count in counts.items() if count} != {key: len(points) for key, points in groups.items()}:
        raise RuntimeError(f'Town PCG instances did not match the plan: {dict(counts)}')

    editor.set_level_viewport_camera_info(unreal.Vector(-23700, 0, 210), unreal.Rotator(0, -2, 0))
    packages = [world.get_package(), graph.get_package()]
    if [p.get_name() for p in packages] != [MAP, f'{GRAPH_DIR}/{GRAPH_NAME}']:
        raise RuntimeError('Unexpected packages for the new map and town graph.')
    if save and not unreal.EditorLoadingAndSavingUtils.save_packages(packages, only_dirty=False):
        raise RuntimeError('Could not save the new map and town graph.')
    return {'map': MAP, 'saved': bool(save), 'graph': packages[1].get_name(), 'instances': dict(counts),
            'buildings': sum(counts[key] for key in HOUSES), 'size_m': 500}
