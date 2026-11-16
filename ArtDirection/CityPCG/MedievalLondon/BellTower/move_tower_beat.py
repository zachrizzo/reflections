"""Move the main quest's tower beat from TowerFoot (east end) to the market bell tower (bell-tower session).

The user (2026-11-15 17:46): the cutscenes and gameplay about the tower must happen where the tower is.
Run in the editor's execute_python tool with MedievalLondon open outside Play. survey() is read-only;
move(apply=True) needs Saved/PIE_LOCK.json held by 'bell-tower' and saves ONLY the map.

    import sys, importlib
    sys.path.insert(0, r'C:/Users/zachc/Documents/Unreal Projects/reflections/ArtDirection/CityPCG/MedievalLondon/BellTower')
    import move_tower_beat as mt; importlib.reload(mt)
    mt.survey()                 # what is in the map now (markers, sealed door, pages, arena)
    mt.move(apply=False)        # dry run: old -> new for each actor
    mt.move(apply=True)         # move and save the map
"""

import json
import time
from pathlib import Path

import unreal

MAP = '/Game/GrayLondon/Maps/MedievalLondon'
OWNER = 'bell-tower'
GROUND = -5.0
BELFRY = 2355.0        # belfry floor (tower base -5 + 2360)

# Story markers by marker_name -> (x, y, z, yaw). The tower's centre is (0, -350); its door faces -X.
MARKERS = {
    'Mk_Gilt_Tower_GiltTower': (-700.0, -350.0, GROUND + 15, 0.0),       # Tower_Giltside: 3 m west of the door
    'CutsceneAnchor_GiltTower': (-520.0, -350.0, GROUND + 15, 0.0),      # CS04: at the threshold, facing in
    'CutsceneAnchor_MirrorWhole': (-1500.0, -350.0, GROUND + 15, 0.0),   # CS05: west plaza, looking at the tower
    'Mk_Frost_Tower_FrostTower': (0.0, -500.0, BELFRY + 15, 270.0),      # Tower_Frostside: the belfry
    'CutsceneAnchor_Ending': (0.0, -470.0, BELFRY + 15, 270.0),          # CS06: belfry, out of the north arch
}
MARKER_RADIUS = {'Mk_Frost_Tower_FrostTower': 300.0}
# Page pickups (single-city mode finds them by actor tag).
PAGES = {'Tower_Giltside': (-245.0, -105.0, GROUND + 1060.0 + 88.0),   # halfway landing (SW corner, +10.6 m)
         'Tower_Frostside': (120.0, -350.0, BELFRY + 88.0)}              # belfry, beside the bell (pages float 88 cm up)
SEALED_DOOR = (-355.0, -350.0, GROUND + 8.0, 180.0)              # west doorway, mid-wall; yaw 180 puts its glow outside. Saved with DoorSize (32, 340.5, 360)
# Villain arena (orchestrator 17:52, option a): open market just west of the tower.
ARENA = (-1700.0, 0.0, GROUND, 0.0)
ARENA_RADIUS = 1100.0
ARENA_LABEL = 'Medieval London | Villain Arena (west of the bell tower)'


def _lease_ok():
    path = Path(unreal.Paths.project_saved_dir()) / 'PIE_LOCK.json'
    if not path.exists():
        return False
    lease = json.loads(path.read_text(encoding='utf-8-sig'))
    return lease.get('owner') == OWNER and float(lease.get('expires_epoch', 0)) > time.time() + 60


def _world():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if not world or world.get_package().get_name() != MAP or editor.get_game_world():
        raise RuntimeError(f'Open {MAP} outside Play.')
    return world


def _actors(cls_name):
    cls = getattr(unreal, cls_name, None)
    if cls is None:
        return []
    return list(unreal.GameplayStatics.get_all_actors_of_class(_world(), cls))


def _key(door):
    try:
        return str(door.get_editor_property('required_key'))
    except Exception:
        return 'GiltTowerKey'   # the class default


def _where(actor):
    v, r = actor.get_actor_location(), actor.get_actor_rotation()
    return [round(v.x), round(v.y), round(v.z), round(r.yaw)]


def survey():
    out = {'markers': {}, 'sealed_doors': [], 'pages': [], 'arenas': []}
    for m in _actors('ReflectionsStoryMarker'):
        name = str(m.get_editor_property('marker_name'))
        if name in MARKERS or name.startswith('Tower_') or 'Tower' in name:
            out['markers'][name] = {'label': m.get_actor_label(), 'at': _where(m),
                                    'radius': m.get_editor_property('radius'),
                                    'tags': [str(t) for t in m.get_editor_property('tags')]}
    for d in _actors('ReflectionsSealedDoor'):
        out['sealed_doors'].append({'label': d.get_actor_label(), 'at': _where(d),
                                    'key': _key(d)})
    for p in _actors('ReflectionsBookPagePickup'):
        out['pages'].append({'label': p.get_actor_label(), 'at': _where(p), 'tags': [str(t) for t in p.tags]})
    for a in _actors('ReflectionsVillainArena'):
        out['arenas'].append({'label': a.get_actor_label(), 'at': _where(a), 'radius': a.get_editor_property('arena_radius')})
    out['world_anchors'] = [a.get_actor_label() for a in _actors('ReflectionsWorldAnchor')]
    out['missing_markers'] = sorted(set(MARKERS) - set(out['markers']))
    return out


def move(apply=False):
    world = _world()
    if apply and not _lease_ok():
        raise RuntimeError(f'PIE_LOCK.json is not held by {OWNER}.')
    plan = []

    def place(actor, x, y, z, yaw, kind):
        plan.append({'kind': kind, 'label': actor.get_actor_label(), 'from': _where(actor),
                     'to': [round(x), round(y), round(z), round(yaw)]})
        if apply:
            actor.set_actor_location_and_rotation(unreal.Vector(x, y, z), unreal.Rotator(0.0, 0.0, yaw), False, True)

    for m in _actors('ReflectionsStoryMarker'):
        name = str(m.get_editor_property('marker_name'))
        if name in MARKERS:
            place(m, *MARKERS[name], 'marker')
            if apply and name in MARKER_RADIUS:
                m.set_editor_property('radius', MARKER_RADIUS[name])
    for p in _actors('ReflectionsBookPagePickup'):
        tag = next((str(t) for t in p.tags if str(t) in PAGES), None)
        if tag:
            place(p, *PAGES[tag], p.get_actor_rotation().yaw, f'page {tag}')
    for d in _actors('ReflectionsSealedDoor'):
        if _key(d) == 'GiltTowerKey':
            place(d, *SEALED_DOOR, 'sealed door')
            if apply:   # the panel must span the doorway (Y), not stick out along X
                origin, extent = d.get_actor_bounds(False)
                if extent.x > extent.y:
                    d.set_actor_rotation(unreal.Rotator(0.0, 0.0, SEALED_DOOR[3] + 90.0), True)
                origin, extent = d.get_actor_bounds(False)
                plan[-1]['bounds_extent'] = [round(extent.x), round(extent.y), round(extent.z)]
                plan[-1]['yaw_after'] = round(d.get_actor_rotation().yaw)
    arenas = _actors('ReflectionsVillainArena')
    if arenas:
        for a in arenas[:1]:
            place(a, *ARENA, 'villain arena')
            if apply:
                a.set_editor_property('arena_radius', ARENA_RADIUS)
        plan.extend({'kind': 'extra arena left alone', 'label': a.get_actor_label(), 'from': _where(a)} for a in arenas[1:])
    else:
        plan.append({'kind': 'villain arena (new)', 'label': ARENA_LABEL, 'to': [round(v) for v in ARENA], 'radius': ARENA_RADIUS})
        if apply:
            actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
            arena = actors.spawn_actor_from_class(unreal.ReflectionsVillainArena, unreal.Vector(*ARENA[:3]),
                                                  unreal.Rotator(0.0, 0.0, ARENA[3]))
            arena.set_actor_label(ARENA_LABEL)
            arena.set_folder_path('MedievalLondon/BellTower')
            arena.set_editor_property('arena_radius', ARENA_RADIUS)
    result = {'applied': apply, 'moves': plan}
    if apply:
        if not unreal.EditorLoadingAndSavingUtils.save_packages([world.get_package()], only_dirty=False):
            raise RuntimeError('Map save failed.')
        result['saved'] = MAP
        result['still_dirty'] = ([p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()] +
                                 [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])
    return result
