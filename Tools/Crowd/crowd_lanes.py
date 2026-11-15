"""Crowd sidewalk lanes (ZoneGraph, CitySidewalk) for Gray London, generated from the map itself.

Owner: crowd-react. Run in an editor-connected session with the editor world = /Game/GrayLondon/Maps/GrayLondon_Geodata,
no PIE running, through PythonScriptingTools.execute_python. Set ARGS = [stage] first. Stages:
  json    - PREFERRED. Make lanes from Tools/Crowd/graylondon_lanes.json, computed offline from the OSM tile by
            Tools/Crowd/lanes_from_tile.py (roads = the tile's GL_Road triangles at 28 cm; pavement = city ground at
            10 cm between road and buildings). No traces, so no World Partition loading needed. Then build, save.
  survey  - classify pavement on a 2 m grid round LT_PlayerStart_Intro (pilot box); report mesh names and counts.
            No changes. NOTE (23:50 run): with the OSM tiles not loaded in the editor, every trace hits the 'City
            ground' cylinder (z 10), so survey/pilot/route need the district loaded first (world-jump's 'load' stage).
  pilot   - make lanes for the pilot box (2-3 blocks round the intro).
  route   - make lanes for the hero route boxes (intro -> Tower Hill, Fenchurch St, Leadenhall). Replaces earlier lanes.
  build   - ASYNC (top-level await): Crowd.City.SetupZoneGraph (build-while-editing on), wait for the ZoneGraph data,
            then report UReflectionsCrowdLaneLibrary.DescribeLanes and CountLanesNear(intro, 50 m).
  save    - save ONLY the packages of actors this script made (tag Crowd.Lane) plus the ZoneGraphData actor.
  clear   - remove this script's lanes (not saved until 'save').
Run order: survey -> pilot -> build -> (look in PIE / at the result) -> save; later route -> build -> save.

How lanes are found (World-jump plan, section 3): floor traces from 150 m up on a 2 m grid. The first hit is the
outdoor floor; a cell is pavement if its mesh is named like a pavement (sidewalk, pavement, footway, kerb, curb), or,
when no names match, if it stands 8-35 cm above the lowest floor within 6 m (the carriageway) and is flat. Pavement
cells are thinned to centrelines (Zhang-Suen), cut into polylines at junctions, sampled every 8 m (<= 10 m), Z from
the trace + 3 cm. Each polyline becomes one spline ZoneShape with the CitySidewalk profile, not spatially loaded,
in outliner folder CrowdLanes, tagged Crowd.Lane. Closed rings are cut in four so their ends meet and link.
Self-checks are in the result: shapes and points made, how many points read back with their values, the profile read
back, the build result and the lane count near the intro.
"""
import json
import math
import unreal

STAGE = ARGS[0] if 'ARGS' in globals() and ARGS else 'survey'
EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
LANE_TAG = 'Crowd.Lane'
FOLDER = 'CrowdLanes'
PROFILE_TEXT = '(Name="CitySidewalk",ID=5C17E0A12B3D4E5F6A7B8C9D0E1F2A3B)'
CELL = 200.0              # cm
PAVEMENT_WORDS = ('sidewalk', 'pavement', 'footway', 'kerb', 'curb')
res = {'stage': STAGE}


def world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def intro():
    for a in unreal.GameplayStatics.get_all_actors_of_class(world(), unreal.PlayerStart):
        if a.get_actor_label() == 'LT_PlayerStart_Intro':
            return a.get_actor_location()
    return unreal.Vector(328290.0, 31090.0, 0.0)   # Great Tower Street (east_m 3282.9, north_m 310.9)


def boxes():
    """(min_x, min_y, max_x, max_y) in cm. Pilot: about 160 x 120 m round the intro. Route: the hero's way."""
    i = intro()
    pilot = [(i.x - 8000.0, i.y - 6000.0, i.x + 8000.0, i.y + 6000.0)]
    if STAGE in ('pilot', 'survey'):
        return pilot
    m = lambda e, n: (e * 100.0, n * 100.0)   # calib is identity: x = east_m * 100, y = north_m * 100
    route = [
        (*m(3240, 250), *m(3560, 350)),   # Great Tower St, Byward St, All Hallows, Trinity Square / Tower Hill
        (*m(3400, 340), *m(3530, 500)),   # Fenchurch St station, Crutched Friars
        (*m(3000, 520), *m(3170, 660)),   # Lime St, Leadenhall Market, Gracechurch St
        (*m(3240, 330), *m(3320, 430)),   # Mark Lane north
    ]
    return route


def trace(x, y, z_top=15000.0, z_bottom=-5000.0):
    hit = unreal.SystemLibrary.line_trace_single(world(), unreal.Vector(x, y, z_top), unreal.Vector(x, y, z_bottom),
                                                 unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [],
                                                 unreal.DrawDebugTrace.NONE, True)
    hs = [v for v in (hit if isinstance(hit, tuple) else (hit,)) if isinstance(v, unreal.HitResult)]
    if not hs:
        return None
    t = hs[0].to_tuple()
    if not t[0]:
        return None
    loc, normal, actor, comp = t[5], t[7], t[9], t[10]
    name = ''
    try:
        mesh = comp.get_editor_property('static_mesh') if comp else None
        name = (mesh.get_name() if mesh else '') + ' ' + (actor.get_actor_label() if actor else '')
    except Exception:  # noqa: BLE001
        name = actor.get_actor_label() if actor else ''
    return loc.z, normal.z, name.lower()


def sample(box):
    x0, y0, x1, y1 = box
    nx, ny = int((x1 - x0) // CELL) + 1, int((y1 - y0) // CELL) + 1
    z = [[None] * ny for _ in range(nx)]
    named = [[False] * ny for _ in range(nx)]
    flat = [[False] * ny for _ in range(nx)]
    names = {}
    for i in range(nx):
        for j in range(ny):
            h = trace(x0 + i * CELL, y0 + j * CELL)
            if h is None:
                continue
            z[i][j] = h[0]
            flat[i][j] = h[1] > 0.9
            named[i][j] = any(w in h[2] for w in PAVEMENT_WORDS)
            key = h[2].split(' ')[0][:40]
            names[key] = names.get(key, 0) + 1
    return {'box': box, 'nx': nx, 'ny': ny, 'z': z, 'named': named, 'flat': flat, 'names': names}


def classify(g):
    nx, ny, z = g['nx'], g['ny'], g['z']
    any_named = any(any(r) for r in g['named'])
    pave = [[False] * ny for _ in range(nx)]
    for i in range(nx):
        for j in range(ny):
            if z[i][j] is None or not g['flat'][i][j]:
                continue
            if any_named:
                pave[i][j] = g['named'][i][j]
            else:
                lo = min((z[a][b] for a in range(max(0, i - 3), min(nx, i + 4)) for b in range(max(0, j - 3), min(ny, j + 4))
                          if z[a][b] is not None), default=z[i][j])
                pave[i][j] = 8.0 <= z[i][j] - lo <= 35.0
    return pave, ('mesh names' if any_named else 'kerb height')


def thin(img):
    """Zhang-Suen thinning of a 0/1 grid (lists), in place; returns the skeleton."""
    nx, ny = len(img), len(img[0]) if img else 0
    a = [[1 if img[i][j] else 0 for j in range(ny)] for i in range(nx)]

    def nb(i, j):
        return [a[i - 1][j], a[i - 1][j + 1], a[i][j + 1], a[i + 1][j + 1], a[i + 1][j], a[i + 1][j - 1], a[i][j - 1], a[i - 1][j - 1]]

    changed = True
    while changed:
        changed = False
        for step in (0, 1):
            kill = []
            for i in range(1, nx - 1):
                for j in range(1, ny - 1):
                    if not a[i][j]:
                        continue
                    p = nb(i, j)
                    b = sum(p)
                    if b < 2 or b > 6:
                        continue
                    t = sum(1 for k in range(8) if p[k] == 0 and p[(k + 1) % 8] == 1)
                    if t != 1:
                        continue
                    if step == 0 and (p[0] * p[2] * p[4] or p[2] * p[4] * p[6]):
                        continue
                    if step == 1 and (p[0] * p[2] * p[6] or p[0] * p[4] * p[6]):
                        continue
                    kill.append((i, j))
            for i, j in kill:
                a[i][j] = 0
            changed = changed or bool(kill)
    return a


def polylines(sk):
    nx, ny = len(sk), len(sk[0]) if sk else 0
    on = {(i, j) for i in range(nx) for j in range(ny) if sk[i][j]}

    def neigh(p):
        i, j = p
        return [(i + di, j + dj) for di in (-1, 0, 1) for dj in (-1, 0, 1) if (di or dj) and (i + di, j + dj) in on]

    nodes = {p for p in on if len(neigh(p)) != 2}
    used, lines = set(), []
    for n in nodes:
        for m in neigh(n):
            if (n, m) in used:
                continue
            line, prev, cur = [n], n, m
            used.add((n, m))
            while True:
                line.append(cur)
                if cur in nodes:
                    used.add((cur, prev))
                    break
                nxt = [q for q in neigh(cur) if q != prev]
                if not nxt:
                    break
                prev, cur = cur, nxt[0]
                used.add((prev, cur))
                if cur == line[0]:
                    line.append(cur)
                    break
            lines.append(line)
    # Rings with no node at all (a pavement right round a block).
    seen = {p for l in lines for p in l}
    for p in on - seen:
        if p in seen:
            continue
        ring, prev, cur = [p], None, p
        while True:
            nxt = [q for q in neigh(cur) if q != prev and q not in ring[1:]]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            ring.append(cur)
            seen.add(cur)
            if cur in neigh(p) and len(ring) > 3:
                ring.append(p)
                break
        seen.add(p)
        lines.append(ring)
    return lines


def to_points(line, g, step=4):
    x0, y0 = g['box'][0], g['box'][1]
    picks = line[::step]
    if picks[-1] != line[-1]:
        picks.append(line[-1])
    pts = []
    for i, j in picks:
        z = g['z'][i][j]
        if z is None:
            continue
        pts.append((x0 + i * CELL, y0 + j * CELL, z + 3.0))
    return pts


def pieces(pts):
    """Closed rings become four shapes whose ends meet (ZoneGraph links coinciding ends)."""
    closed = len(pts) > 4 and math.dist(pts[0][:2], pts[-1][:2]) < 1.0
    if not closed or len(pts) < 8:
        return [pts]
    q = len(pts) // 4
    return [pts[0:q + 1], pts[q:2 * q + 1], pts[2 * q:3 * q + 1], pts[3 * q:]]


def make_shape(pts, label):
    a = EAS.spawn_actor_from_class(unreal.ZoneShape, unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator(0.0, 0.0, 0.0))
    a.set_actor_label(label)
    a.set_folder_path(FOLDER)
    a.set_editor_property('tags', [unreal.Name(LANE_TAG)])
    try:
        a.set_editor_property('is_spatially_loaded', False)
    except Exception:  # noqa: BLE001
        res.setdefault('spatial_flag_failed', 0)
        res['spatial_flag_failed'] += 1
    comp = a.get_component_by_class(unreal.ZoneShapeComponent)
    out = []
    for (x, y, z) in pts:
        p = unreal.ZoneShapePoint()
        p.set_editor_property('position', unreal.Vector(x, y, z))
        p.set_editor_property('type', unreal.FZoneShapePointType.AUTO_BEZIER)
        out.append(p)
    comp.set_editor_property('points', out)
    comp.set_editor_property('shape_type', unreal.FZoneShapeType.SPLINE)
    prof = comp.get_editor_property('lane_profile')
    try:
        prof.import_text(PROFILE_TEXT)
    except Exception:  # noqa: BLE001
        pass
    comp.set_editor_property('lane_profile', prof)
    # Read back: the points and the profile really took their values.
    back = comp.get_editor_property('points')
    ok = len(back) == len(pts) and all(abs(b.get_editor_property('position').x - p[0]) < 1.0 for b, p in zip(back, pts))
    return a, ok, str(comp.get_editor_property('lane_profile'))


def ours():
    return [a for a in unreal.GameplayStatics.get_all_actors_of_class(world(), unreal.ZoneShape) if a.actor_has_tag(LANE_TAG)]


DELETED = unreal.Paths.project_saved_dir() + 'CrowdLanes_deleted_packages.json'


def load_deleted():
    try:
        return json.load(open(DELETED, encoding='utf-8'))
    except Exception:  # noqa: BLE001
        return []


def clear():
    """Destroy our lane shapes and remember their external-actor packages, so 'save' also writes the deletions
    (otherwise the old packages stay on disk and come back as duplicates on the next load)."""
    actors = ours()
    names = [a.get_outermost().get_name() for a in actors]
    for a in actors:
        EAS.destroy_actor(a)
    pending = load_deleted()
    pending += [n for n in names if n not in pending]
    json.dump(pending, open(DELETED, 'w', encoding='utf-8'), indent=0)
    return len(actors)


def generate():
    res['removed_old'] = clear()
    made, points, readback_ok, profiles, rule = 0, 0, 0, {}, None
    for b, box in enumerate(boxes()):
        g = sample(box)
        pave, rule = classify(g)
        res.setdefault('pavement_cells', []).append(sum(sum(1 for v in r if v) for r in pave))
        sk = thin(pave)
        for k, line in enumerate(polylines(sk)):
            if len(line) < 5:          # under 10 m: drop
                continue
            for p, piece in enumerate(pieces(to_points(line, g))):
                if len(piece) < 2:
                    continue
                a, ok, prof = make_shape(piece, 'Crowd_Lane_%d_%03d_%d' % (b, k, p))
                made += 1
                points += len(piece)
                readback_ok += 1 if ok else 0
                profiles[prof[:90]] = profiles.get(prof[:90], 0) + 1
    res.update({'rule': rule, 'shapes': made, 'points': points, 'points_read_back_ok_shapes': readback_ok,
                'profiles_read_back': profiles,
                'expect': 'shapes > 0; points_read_back_ok_shapes == shapes; profile shows CitySidewalk and ID 5C17E0A1...'})


if unreal.EditorLevelLibrary.get_game_world() is not None:
    res['abort'] = 'PIE running'
elif 'GrayLondon_Geodata' not in world().get_name():
    res['abort'] = 'editor world is %s, not GrayLondon_Geodata' % world().get_name()
elif STAGE == 'survey':
    g = sample(boxes()[0])
    pave, rule = classify(g)
    res['rule'] = rule
    res['cells'] = g['nx'] * g['ny']
    res['pavement_cells'] = sum(sum(1 for v in r if v) for r in pave)
    res['top_mesh_names'] = dict(sorted(g['names'].items(), key=lambda kv: -kv[1])[:25])
    res['expect'] = 'pavement cells 10-35% of the box; if 0 or most of it, tell crowd-react the mesh names'
elif STAGE in ('pilot', 'route'):
    generate()
elif STAGE == 'json':
    # Lanes computed offline from the OSM tile (Tools/Crowd/lanes_from_tile.py): no traces, no tile loading needed.
    src = json.load(open(unreal.Paths.project_dir() + 'Tools/Crowd/graylondon_lanes.json', encoding='utf-8'))
    res['removed_old'] = clear()
    made, points, readback_ok, profiles = 0, 0, 0, {}
    for k, pts in enumerate(src['lanes']):
        a, ok, prof = make_shape([tuple(p) for p in pts], 'Crowd_Lane_json_%03d' % k)
        made += 1
        points += len(pts)
        readback_ok += 1 if ok else 0
        profiles[prof[:90]] = profiles.get(prof[:90], 0) + 1
    res.update({'source': src.get('source'), 'source_stats': src.get('stats'), 'shapes': made, 'points': points,
                'points_read_back_ok_shapes': readback_ok, 'profiles_read_back': profiles,
                'expect': 'shapes == source lanes; points_read_back_ok_shapes == shapes; profile CitySidewalk / 5C17E0A1...'})
elif STAGE == 'clear':
    res['removed'] = clear()
elif STAGE == 'build':
    unreal.SystemLibrary.execute_console_command(world(), 'Crowd.City.SetupZoneGraph')
    for _ in range(40):
        await asyncio.sleep(0.5)
        if unreal.GameplayStatics.get_all_actors_of_class(world(), unreal.ZoneGraphData):
            break
    await asyncio.sleep(2.0)
    data = unreal.GameplayStatics.get_all_actors_of_class(world(), unreal.ZoneGraphData)
    for d in data:
        if not d.actor_has_tag(LANE_TAG):
            d.set_editor_property('tags', list(d.tags) + [unreal.Name(LANE_TAG)])
    i = intro()
    res['zonegraph_data_actors'] = len(data)
    res['lanes'] = unreal.ReflectionsCrowdLaneLibrary.describe_lanes(world())
    res['lanes_within_50m_of_intro'] = unreal.ReflectionsCrowdLaneLibrary.count_lanes_near(world(), i, 5000.0)
    res['expect'] = 'zonegraph_data_actors == 1; lanes > 0; lanes_within_50m_of_intro > 0'
elif STAGE == 'save':
    actors = ours() + [d for d in unreal.GameplayStatics.get_all_actors_of_class(world(), unreal.ZoneGraphData)]
    pkgs = list({a.get_outermost().get_name(): a.get_outermost() for a in actors}.values())
    res['saved'] = unreal.EditorLoadingAndSavingUtils.save_packages(pkgs, True)
    res['packages'] = len(pkgs)
    res['package_names'] = sorted(p.get_name() for p in pkgs)[:10]
    # Deleted lane shapes: save their (now empty) external-actor packages too, which removes them from disk.
    pending = load_deleted()
    live = {p.get_name() for p in pkgs}
    gone = [unreal.find_object(None, n) for n in pending if n not in live]
    gone = [p for p in gone if p is not None]
    res['deleted_pending'] = len(pending)
    res['deleted_packages_found'] = len(gone)
    res['saved_deletions'] = unreal.EditorLoadingAndSavingUtils.save_packages(gone, False) if gone else True
    if res['saved_deletions']:
        json.dump([], open(DELETED, 'w', encoding='utf-8'))
    res['expect'] = 'saved True; saved_deletions True; deleted_packages_found == deleted_pending (else check Content/__ExternalActors__ by hand)'
json.dumps(res, default=str)
