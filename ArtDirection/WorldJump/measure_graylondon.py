"""Step 0 of GrayLondon_Plan.md: open Gray London in the editor, survey it, calibrate its axes, load the Tower district,
switch back. SAVES NOTHING. Run stage by stage through the MCP Python tool (ARGS = [stage]):
  open    - open the map (refuses if any map is dirty); returns seconds
  survey  - World Partition actor descriptors: counts by class, data layers, landmark candidates and their bounds
  calib   - axis mapping from the Tower of London and Tower Bridge landmark bounds vs graylondon_places.json
  load    - load the actors inside the district box (after calib); returns seconds and count
  back    - reopen the home map without saving
Measure the editor's memory from outside between stages (Get-Process UnrealEditor).
"""
import json
import time
import unreal

MAP = '/Game/GrayLondon/Maps/GrayLondon_Geodata'
HOME = '/Game/Characters/Hero/Sample/Lvl_HeroSampleCrowd'
PLACES = unreal.Paths.project_dir() + 'ArtDirection/WorldJump/graylondon_places.json'
CALIB = unreal.Paths.project_saved_dir() + 'GrayLondon_calib.json'
STAGE = ARGS[0] if ARGS else 'survey'
WPL = unreal.WorldPartitionBlueprintLibrary
res = {'stage': STAGE}


def editor_world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def descs():
    try:
        return list(WPL.get_actor_descs())
    except Exception as e:  # noqa: BLE001
        res['descs_error'] = str(e)[:200]
        return []


def field(d, *names):
    for n in names:
        try:
            return d.get_editor_property(n)
        except Exception:  # noqa: BLE001
            continue
    return None


if unreal.EditorLevelLibrary.get_game_world() is not None:
    res['abort'] = 'PIE running'
elif STAGE == 'open':
    dirty = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    if dirty:
        res['abort'] = 'dirty maps, not switching: %s' % dirty
    else:
        t = time.time()
        res['opened'] = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(MAP)
        res['seconds'] = round(time.time() - t, 1)
        w = editor_world()
        res['world'] = w.get_path_name() if w else None
elif STAGE == 'survey':
    ds = descs()
    res['actor_descs'] = len(ds)
    by_class, layers, landmarks, spatial = {}, {}, [], 0
    for d in ds:
        cls = str(field(d, 'native_class', 'class_') or '?').split('.')[-1].strip("'>")
        by_class[cls] = by_class.get(cls, 0) + 1
        for dl in (field(d, 'data_layer_assets') or []):
            layers[str(dl)] = layers.get(str(dl), 0) + 1
        if field(d, 'is_spatially_loaded'):
            spatial += 1
        label = str(field(d, 'label', 'name') or '')
        if any(k in label.lower() for k in ('tower', 'bridge', 'trinity', 'leadenhall', 'hallows', 'mint')):
            b = field(d, 'bounds')
            landmarks.append([label, str(b)[:160]])
    res['by_class'] = dict(sorted(by_class.items(), key=lambda kv: -kv[1])[:25])
    res['spatially_loaded'] = spatial
    res['data_layers'] = layers
    res['landmark_candidates'] = landmarks[:40]
    w = editor_world()
    ws = w.get_world_settings() if w else None
    for p in ('world_partition', 'enable_world_composition'):
        try:
            res['ws_' + p] = str(ws.get_editor_property(p))[:120]
        except Exception as e:  # noqa: BLE001
            res['ws_' + p] = 'n/a'
elif STAGE == 'calib':
    places = json.load(open(PLACES, encoding='utf-8'))
    want = {'tower of london': 'TowerFoot', 'tower bridge': 'LanternGate'}
    found = {}
    for d in descs():
        label = str(field(d, 'label', 'name') or '').lower()
        for key, place in want.items():
            if key.replace(' ', '') in label.replace(' ', '').replace('_', ''):
                b = field(d, 'bounds')
                try:
                    c = b.get_center() if hasattr(b, 'get_center') else (b.min + b.max) * 0.5
                    found[place] = [c.x / 100.0, c.y / 100.0, label]
                except Exception as e:  # noqa: BLE001
                    found[place] = str(e)[:80]
    res['found'] = found
    calib = {}
    for place, v in found.items():
        if isinstance(v, list):
            e, n = places[place]['east_m'], places[place]['north_m']
            calib[place] = {'ue_x_m': round(v[0], 1), 'ue_y_m': round(v[1], 1), 'east_m': e, 'north_m': n}
    # Expect UE X = +east and UE Y = -north (Unreal is left-handed, Y "south") or similar; report what fits.
    for place, c in calib.items():
        c['fits'] = {'x=+E,y=-N': [round(c['ue_x_m'] - c['east_m'], 1), round(c['ue_y_m'] + c['north_m'], 1)],
                     'x=+E,y=+N': [round(c['ue_x_m'] - c['east_m'], 1), round(c['ue_y_m'] - c['north_m'], 1)]}
    res['calib'] = calib
    json.dump(calib, open(CALIB, 'w'), indent=1)
elif STAGE == 'load':
    calib = json.load(open(CALIB))
    places = json.load(open(PLACES, encoding='utf-8'))
    # District box from the places, mapped with the best-fitting sign (y = -north unless calib says otherwise).
    sign_y = -1.0
    if calib:
        c = list(calib.values())[0]
        if abs(c['fits']['x=+E,y=+N'][1]) < abs(c['fits']['x=+E,y=-N'][1]):
            sign_y = 1.0
    xs = [p['east_m'] * 100.0 for p in places.values()]
    ys = [sign_y * p['north_m'] * 100.0 for p in places.values()]
    box = unreal.Box(unreal.Vector(min(xs) - 15000, min(ys) - 15000, -10000), unreal.Vector(max(xs) + 15000, max(ys) + 15000, 30000))
    t = time.time()
    try:
        got = WPL.get_intersecting_actor_descs(box) if hasattr(WPL, 'get_intersecting_actor_descs') else []
        guids = [field(d, 'guid') for d in got]
        ok = WPL.load_actors(guids)
        res['loaded'] = [len(guids), ok]
    except Exception as e:  # noqa: BLE001
        res['load_error'] = str(e)[:200]
    res['seconds'] = round(time.time() - t, 1)
    res['box_m'] = [[round(v / 100.0) for v in (box.min.x, box.min.y)], [round(v / 100.0) for v in (box.max.x, box.max.y)]]
elif STAGE == 'back':
    # No save: discard nothing of others either, just reopen the home map (refuses if this map got dirty).
    dirty = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    res['dirty_maps'] = dirty
    if not dirty:
        res['back'] = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(HOME)
json.dumps(res, default=str)
