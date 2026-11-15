"""Row B on Gray London (the editor world must be /Game/GrayLondon/Maps/GrayLondon_Geodata). Run stage by stage through
the MCP Python tool with ARGS = [stage, ...]:
  survey          - WorldSettings game mode, World Partition actor descriptor counts, landmark candidates (no changes)
  calib [label]   - axis mapping from a landmark descriptor (default: best match for the Tower of London)
  load            - load the Tower district region in the editor (editor-only state, nothing saved)
  place           - PlayerStart + 89 story markers by name (new actors, not spatially loaded), traced to the street
  nav             - RecastNavMesh (ledge filter None) + NavMeshBoundsVolume over the district, build
  save            - save ONLY the packages of actors this script spawned (labels in OURS), list them
Our actors carry the tag 'Lanthorne.Overlay' and labels starting 'LT_' so they are easy to find, re-run and merge.
"""
import json
import math
import time
import unreal

WJ = unreal.Paths.project_dir() + 'ArtDirection/WorldJump/'
CALIB = unreal.Paths.project_saved_dir() + 'GrayLondon_calib.json'
OURS = unreal.Paths.project_saved_dir() + 'GrayLondon_ours.json'
STAGE = ARGS[0] if ARGS else 'survey'
WPL = unreal.WorldPartitionBlueprintLibrary
EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
OVERLAY_TAG = 'Lanthorne.Overlay'
SIDE_ENUM = {'Pewterside': 'PEWTERSIDE', 'Giltside': 'GILTSIDE', 'Frostside': 'FROSTSIDE'}
res = {'stage': STAGE}


def world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def field(d, *names):
    for n in names:
        try:
            return d.get_editor_property(n)
        except Exception:  # noqa: BLE001
            continue
    return None


def descs():
    return list(WPL.get_actor_descs())


def load_json(path, default):
    try:
        return json.load(open(path, encoding='utf-8'))
    except Exception:  # noqa: BLE001
        return default


def to_ue(east_m, north_m, c):
    """London metres (east, north of the map origin) -> Unreal cm, with the calibrated signs and offset."""
    return (c['sx'] * east_m * 100.0 + c['ox'], c['sy'] * north_m * 100.0 + c['oy'])


def ground(x, y, search_m=20.0):
    """Street-level point near (x, y): trace down on a small spiral, take the lowest hit (roofs are higher)."""
    w = world()
    best = None
    pts = [(0.0, 0.0)] + [(r * math.cos(a), r * math.sin(a)) for r in (3.0, 6.0, 10.0, 15.0, search_m)
                          for a in [k * math.pi / 4 for k in range(8)]]
    for dx, dy in pts:
        s = unreal.Vector(x + dx * 100.0, y + dy * 100.0, 15000.0)
        e = unreal.Vector(x + dx * 100.0, y + dy * 100.0, -5000.0)
        hit = unreal.SystemLibrary.line_trace_single(w, s, e, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [],
                                                     unreal.DrawDebugTrace.NONE, True)
        hs = [v for v in (hit if isinstance(hit, tuple) else (hit,)) if isinstance(v, unreal.HitResult)]
        try:
            tup = hs[0].to_tuple()
            ok, loc = bool(tup[0]), tup[4]
        except Exception:  # noqa: BLE001
            ok, loc = False, None
        if ok and loc is not None and (best is None or loc.z < best[2] - 50.0):
            best = (loc.x, loc.y, loc.z)
            if dx == 0.0 and dy == 0.0:
                pass
    return best


def mark_ours(a, extra_tags=()):
    a.set_editor_property('tags', [unreal.Name(OVERLAY_TAG)] + [unreal.Name(t) for t in extra_tags])
    for p in ('is_spatially_loaded', 'b_is_spatially_loaded'):
        try:
            a.set_editor_property(p, False)
            return True
        except Exception:  # noqa: BLE001
            continue
    res.setdefault('spatial_flag_failed', []).append(a.get_actor_label())
    return False


def remember(actors):
    ours = load_json(OURS, [])
    for a in actors:
        p = a.get_outermost().get_name()
        if p not in ours:
            ours.append(p)
    json.dump(ours, open(OURS, 'w'), indent=0)


def ours_in_world():
    return [a for a in unreal.GameplayStatics.get_all_actors_of_class(world(), unreal.Actor)
            if a.actor_has_tag(OVERLAY_TAG)]


if unreal.EditorLevelLibrary.get_game_world() is not None:
    res['abort'] = 'PIE running'
elif STAGE == 'survey':
    w = world()
    res['world'] = w.get_path_name() if w else None
    ws = w.get_world_settings()
    for p in ('default_game_mode', 'world_partition', 'kill_z', 'enable_world_bounds_checks'):
        try:
            res['ws_' + p] = str(ws.get_editor_property(p))[:160]
        except Exception as e:  # noqa: BLE001
            res['ws_' + p] = 'n/a: ' + str(e)[:60]
    ds = descs()
    res['actor_descs'] = len(ds)
    by_class, spatial, cands = {}, 0, []
    for d in ds:
        cls = str(field(d, 'native_class', 'class_')).split('.')[-1].strip("'>")
        by_class[cls] = by_class.get(cls, 0) + 1
        spatial += 1 if field(d, 'is_spatially_loaded') else 0
        label = str(field(d, 'label') or field(d, 'name'))
        if any(k in label.lower() for k in ('tower', 'bridge', 'trinity', 'leadenhall', 'hallows', 'mint', 'billingsgate',
                                            'fenchurch', 'playerstart', 'nav', 'zonegraph', 'pcg')):
            b = field(d, 'bounds')
            try:
                c = (b.min + b.max) * 0.5
                cands.append([label, cls, [round(c.x / 100.0), round(c.y / 100.0), round(c.z / 100.0)]])
            except Exception:  # noqa: BLE001
                cands.append([label, cls, None])
    res['by_class'] = dict(sorted(by_class.items(), key=lambda kv: -kv[1])[:30])
    res['spatially_loaded'] = spatial
    res['candidates'] = cands[:60]
elif STAGE == 'calib':
    # ARGS: calib <tower label substring> <bridge label substring>; matches World Partition descriptor labels.
    places = load_json(WJ + 'graylondon_places.json', {})
    keys = [('Ref_TowerOfLondon', ARGS[1].lower() if len(ARGS) > 1 else 'toweroflondon'),
            ('Ref_TowerBridge', ARGS[2].lower() if len(ARGS) > 2 else 'towerbridge')]
    found = {}
    for d in descs():
        label = str(field(d, 'label') or field(d, 'name'))
        norm = label.lower().replace(' ', '').replace('_', '')
        for ref, want in keys:
            if ref not in found and want in norm:
                b = field(d, 'bounds')
                c = (b.min + b.max) * 0.5
                found[ref] = (label, c.x, c.y)
    res['found'] = {k: [v[0], round(v[1] / 100.0, 1), round(v[2] / 100.0, 1)] for k, v in found.items()}
    if 'Ref_TowerOfLondon' not in found:
        res['error'] = 'tower landmark not found; pass a label substring from survey candidates'
    else:
        t = found['Ref_TowerOfLondon']
        e, n = places['Ref_TowerOfLondon']['east_m'], places['Ref_TowerOfLondon']['north_m']
        fits = {}
        for sx in (1.0, -1.0):
            for sy in (1.0, -1.0):
                ox, oy = t[1] - sx * e * 100.0, t[2] - sy * n * 100.0
                if 'Ref_TowerBridge' in found:
                    b = found['Ref_TowerBridge']
                    be, bn = places['Ref_TowerBridge']['east_m'], places['Ref_TowerBridge']['north_m']
                    fits['%+d,%+d' % (sx, sy)] = round(math.hypot(b[1] - (sx * be * 100.0 + ox), b[2] - (sy * bn * 100.0 + oy)) / 100.0, 1)
                else:
                    fits['%+d,%+d' % (sx, sy)] = round(math.hypot(ox, oy) / 100.0, 1)   # expect a near-zero offset
        best = min(fits, key=fits.get)
        sx, sy = [float(v) for v in best.split(',')]
        calib = {'tower_label': t[0], 'sx': sx, 'sy': sy, 'ox': t[1] - sx * e * 100.0, 'oy': t[2] - sy * n * 100.0,
                 'residual_m_by_sign': fits, 'offset_m': [round((t[1] - sx * e * 100.0) / 100.0, 1), round((t[2] - sy * n * 100.0) / 100.0, 1)]}
        json.dump(calib, open(CALIB, 'w'), indent=1)
        res['calib'] = calib
elif STAGE == 'load':
    c = load_json(CALIB, None)
    places = load_json(WJ + 'graylondon_places.json', {})
    pts = [to_ue(p['east_m'], p['north_m'], c) for p in places.values()]
    box = unreal.Box(unreal.Vector(min(p[0] for p in pts) - 15000, min(p[1] for p in pts) - 15000, -20000),
                     unreal.Vector(max(p[0] for p in pts) + 15000, max(p[1] for p in pts) + 15000, 40000))
    t = time.time()
    guids = []
    for d in descs():
        b = field(d, 'bounds')
        try:
            if b.min.x < box.max.x and b.max.x > box.min.x and b.min.y < box.max.y and b.max.y > box.min.y:
                guids.append(field(d, 'guid'))
        except Exception:  # noqa: BLE001
            continue
    res['to_load'] = len(guids)
    try:
        res['loaded'] = WPL.load_actors(guids)
    except Exception as e:  # noqa: BLE001
        res['load_error'] = str(e)[:200]
    res['seconds'] = round(time.time() - t, 1)
elif STAGE == 'place':
    c = load_json(CALIB, None)
    places = load_json(WJ + 'graylondon_places.json', {})
    spec = load_json(WJ + 'graylondon_markers.json', [])
    # Re-run safety: remove our earlier markers / start first.
    removed = 0
    for a in ours_in_world():
        if a.get_actor_label().startswith(('LT_Marker_', 'LT_PlayerStart')):
            EAS.destroy_actor(a)
            removed += 1
    res['removed_old'] = removed
    spawned, misses = [], []
    # PlayerStart: Great Tower Street outside the inn, facing east (towards the Tower down Byward Street).
    ix, iy = to_ue(places['Intro']['east_m'], places['Intro']['north_m'], c)
    g = ground(ix, iy)
    face = math.degrees(math.atan2(c['sy'] * 0.0, c['sx'] * 1.0))   # +east in Unreal yaw
    ps = EAS.spawn_actor_from_class(unreal.PlayerStart, unreal.Vector(g[0], g[1], g[2] + 100.0) if g else unreal.Vector(ix, iy, 200.0),
                                    unreal.Rotator(0.0, 0.0, face))
    ps.set_actor_label('LT_PlayerStart_Intro')
    mark_ours(ps)
    spawned.append(ps)
    res['player_start'] = [round(v / 100.0, 1) for v in (ps.get_actor_location().x, ps.get_actor_location().y, ps.get_actor_location().z)]
    for m in spec:
        x, y = to_ue(m['east_m'], m['north_m'], c)
        g = ground(x, y)
        if g is None:
            misses.append(m['name'])
            g = (x, y, 0.0)
        yaw_mock = m['yaw']   # mock yaw: degrees from +east towards +north
        yaw = math.degrees(math.atan2(c['sy'] * math.sin(math.radians(yaw_mock)), c['sx'] * math.cos(math.radians(yaw_mock))))
        a = EAS.spawn_actor_from_class(unreal.ReflectionsStoryMarker, unreal.Vector(g[0], g[1], g[2] + 5.0), unreal.Rotator(0.0, 0.0, yaw))
        a.set_actor_label('LT_Marker_' + m['name'])
        a.set_editor_property('marker_name', m['name'])
        # One London (user, 21:10): every marker resolves to the single side (Auto -> the config's default world).
        a.set_editor_property('side', unreal.ReflectionsMarkerSide.AUTO)
        a.set_editor_property('radius', float(m['radius']))
        a.set_editor_property('notes', 'Gray London overlay: %s (mock place %s, was %s)' % (places[m['place']]['spot'], m['place'], m['side']))
        mark_ours(a, m['tags'])
        spawned.append(a)
    remember(spawned)
    res['spawned'] = len(spawned)
    res['no_ground'] = misses
elif STAGE == 'nav':
    # Static district navmesh (packaging, 21:20: no HLOD/nav existed; static nav bounded to the play area only, ~10-20 MB).
    # Spawn OUR RecastNavMesh first, so the editor doesn't auto-create one when the bounds volume registers.
    c = load_json(CALIB, None)
    places = load_json(WJ + 'graylondon_places.json', {})
    pts = [to_ue(p['east_m'], p['north_m'], c) for p in places.values()]
    cx, cy = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2, (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
    hx, hy = (max(p[0] for p in pts) - min(p[0] for p in pts)) / 2 + 10000, (max(p[1] for p in pts) - min(p[1] for p in pts)) / 2 + 10000
    for a in ours_in_world():
        if a.get_actor_label().startswith(('LT_NavBounds', 'LT_RecastNavMesh')):
            EAS.destroy_actor(a)
    existing = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world(), unreal.RecastNavMesh)]
    res['existing_navmesh'] = [a.get_actor_label() for a in existing]
    if existing:
        nav = existing[0]
        res['existing_ledge_filter'] = str(nav.get_editor_property('ledge_slope_filter_mode'))
    else:
        nav = EAS.spawn_actor_from_class(unreal.RecastNavMesh, unreal.Vector(0, 0, 0))
        nav.set_actor_label('LT_RecastNavMesh')
        mark_ours(nav)
        nav.set_editor_property('ledge_slope_filter_mode', unreal.NavigationLedgeSlopeFilterMode.NONE)
        nav.set_editor_property('runtime_generation', unreal.RuntimeGenerationType.STATIC)
    nb = EAS.spawn_actor_from_class(unreal.NavMeshBoundsVolume, unreal.Vector(cx, cy, 2000.0))
    nb.set_actor_label('LT_NavBounds_TowerDistrict')
    mark_ours(nb)
    res['bounds_ok'] = unreal.ReflectionsWorldLibrary.set_volume_box(nb, unreal.Vector(hx, hy, 6000.0))
    remember([nb] + ([] if existing else [nav]))
    unreal.SystemLibrary.execute_console_command(world(), 'RebuildNavigation')
    res['bounds_half_m'] = [round(hx / 100.0), round(hy / 100.0)]
    res['note'] = 'poll NavigationSystemV1.is_navigation_being_built, then save (our packages only)'
elif STAGE == 'da':
    # One London: no world jump. Clear DA_WorldJumpConfig's map refs to the deleted mock sides; save only the DA.
    cfg = unreal.load_asset('/Game/Worlds/DA_WorldJumpConfig')
    worlds = list(cfg.get_editor_property('worlds'))
    before = []
    for info in worlds:
        before.append(str(info.get_editor_property('map')))
        info.set_editor_property('map', None)
    cfg.set_editor_property('worlds', worlds)
    res['maps_before'] = before
    res['saved'] = unreal.EditorAssetLibrary.save_loaded_asset(cfg, only_if_is_dirty=False)
elif STAGE == 'save':
    ours = ours_in_world()
    pkgs = list({a.get_outermost().get_name(): a.get_outermost() for a in ours}.values())
    ok = unreal.EditorLoadingAndSavingUtils.save_packages(pkgs, True)
    res['saved'] = ok
    res['packages'] = sorted(p.get_name() for p in pkgs)
    res['count'] = len(pkgs)
    remember(ours)
json.dumps(res, default=str)
