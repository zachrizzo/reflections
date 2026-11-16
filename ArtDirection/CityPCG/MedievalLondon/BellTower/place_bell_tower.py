"""Import, place and walk-test the Medieval London bell tower (bell-tower session).

Run in the editor's execute_python tool (top-level await available), with
/Game/GrayLondon/Maps/MedievalLondon open outside Play and Saved/PIE_LOCK.json
held by OWNER. One step per call:

    import sys, importlib
    sys.path.insert(0, r'C:/Users/zachc/Documents/Unreal Projects/reflections/ArtDirection/CityPCG/MedievalLondon/BellTower')
    import place_bell_tower as bt; importlib.reload(bt)
    bt.preflight()            # memory, dirty packages, Multi-User, map, lease
    bt.import_meshes()        # 4 FBX -> /Game/GrayLondon/MedievalOpening/BellTower, kit materials, collision
    bt.place()                # actors in the map (replaces an earlier placement)
    bt.save_meshes(); bt.save_map()
    bt.rebuild_navigation()   # then poll bt.navigation_busy() and bt.save_map() again
    await bt.walk_test(call_tool)   # PIE: walk from the street through the door to the belfry

The meshes come from build_bell_tower.py (headless Blender) in this folder.
"""

import asyncio
import base64
import json
import math
import time
from pathlib import Path

import unreal

MAP = '/Game/GrayLondon/Maps/MedievalLondon'
DEST = '/Game/GrayLondon/MedievalOpening/BellTower'
SRC = Path(__file__).resolve().parent
SHOTS = Path(unreal.Paths.project_saved_dir()) / 'BellTower'
OWNER = 'bell-tower'
MESHES = ('SM_BellTower_Shell', 'SM_BellTower_Stairs', 'SM_BellTower_Rails', 'SM_BellTower_Bell')
KIT = '/Game/GrayLondon/MedievalOpening/Kit/M_GLMedieval_'
MATERIALS = {role: KIT + role for role in ('GuildAshlar', 'GuildDressed', 'GuildRubble', 'Fieldstone',
                                           'ClayTile', 'Oak', 'WeatheredOak', 'Lead')}
MATERIALS['Bronze'] = '/Game/GrayLondon/CityPCG/Kit/M_GLPCG_Bronze'
CENTRE = (0.0, -350.0)            # reserved box X -600..600, Y -950..250 in the town generator
YAW = 0.0                         # door on the tower's -X face: looks west, back down the main street
LABEL = 'Medieval London | Bell Tower'
FOLDER = 'MedievalLondon/BellTower'
HANG_CM = 2800.0
BELFRY_CM = 2360.0
LIGHT_HEIGHTS_CM = (320.0, 900.0, 1480.0, 2060.0)


def _manifest():
    return json.loads((SRC / 'bell_tower_manifest.json').read_text(encoding='utf-8'))


def _lease_ok():
    path = Path(unreal.Paths.project_saved_dir()) / 'PIE_LOCK.json'
    if not path.exists():
        return False, 'no PIE_LOCK.json'
    lease = json.loads(path.read_text(encoding='utf-8-sig'))
    ok = lease.get('owner') == OWNER and float(lease.get('expires_epoch', 0)) > time.time() + 60
    return ok, lease


def require_editor(allow_pie=False):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    ok, lease = _lease_ok()
    if not world or world.get_package().get_name() != MAP:
        raise RuntimeError(f'Open {MAP} first.')
    if editor.get_game_world() and not allow_pie:
        raise RuntimeError('PIE is running.')
    if not ok:
        raise RuntimeError(f'PIE_LOCK.json is not held by {OWNER}: {lease}')
    return editor, world


def preflight():
    """Read-only: what would be saved, and is it safe to save."""
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    out = {'map': world.get_package().get_name() if world else None,
           'pie': bool(editor.get_game_world()), 'lease': _lease_ok()[1]}
    try:
        out['dirty_content'] = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
        out['dirty_maps'] = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    except Exception as error:
        out['dirty_error'] = repr(error)
    concert = {}
    for name in ('MultiUserClientLibrary', 'ConcertSyncClientLibrary'):
        lib = getattr(unreal, name, None)
        if lib is None:
            continue
        for fn in ('get_current_session_id', 'is_in_session', 'get_local_client_info'):
            if hasattr(lib, fn):
                try:
                    concert[f'{name}.{fn}'] = str(getattr(lib, fn)())
                except Exception as error:
                    concert[f'{name}.{fn}'] = repr(error)
    out['multi_user'] = concert or 'no Multi-User library loaded'
    out['existing'] = [a.get_actor_label() for a in _tower_actors(world)] if world else []
    out['assets_exist'] = {name: unreal.EditorAssetLibrary.does_asset_exist(f'{DEST}/{name}') for name in MESHES}
    return out


def _fbx_task(name):
    options = unreal.FbxImportUI()
    options.set_editor_properties({
        'import_mesh': True, 'import_as_skeletal': False, 'import_materials': False,
        'import_textures': False, 'import_animations': False,
        'mesh_type_to_import': unreal.FBXImportType.FBXIT_STATIC_MESH,
        'automated_import_should_detect_type': False})
    options.static_mesh_import_data.set_editor_properties({
        'auto_generate_collision': False, 'generate_lightmap_u_vs': False, 'combine_meshes': True,
        'convert_scene': True, 'convert_scene_unit': True, 'import_uniform_scale': 1.0})
    task = unreal.AssetImportTask()
    task.filename = str(SRC / f'{name}.fbx')
    task.destination_path = DEST
    task.destination_name = name
    task.automated = True
    task.save = False
    task.replace_existing = True
    task.factory = unreal.FbxFactory()
    task.options = options
    return task


def _bounds(mesh):
    box = mesh.get_bounding_box()
    return [[round(getattr(v, a), 1) for a in 'xyz'] for v in (box.min, box.max)]


def import_meshes():
    require_editor()
    spec = _manifest()['meshes']
    tasks = [_fbx_task(name) for name in MESHES]
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    mesh_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    report = {}
    for name in MESHES:
        mesh = unreal.EditorAssetLibrary.load_asset(f'{DEST}/{name}')
        if not isinstance(mesh, unreal.StaticMesh):
            raise RuntimeError(f'{name} did not import as a static mesh: {mesh}')
        # Materials by slot name (= kit role).
        slots = [str(s.get_editor_property('material_slot_name')) for s in mesh.get_editor_property('static_materials')]
        for index, slot in enumerate(slots):
            role = slot if slot in MATERIALS else next(
                (r for r in sorted(MATERIALS, key=len, reverse=True) if slot.startswith(r + '_')), None)
            if role is None:
                raise RuntimeError(f'{name}: unknown material slot {slot}')
            material = unreal.EditorAssetLibrary.load_asset(MATERIALS[role])
            if material is None:
                raise RuntimeError(f'Missing kit material {MATERIALS[role]}')
            mesh.set_material(index, material)
        # Collision: the render triangles themselves (boxes and steps), no simple shapes.
        mesh_editor.remove_collisions(mesh)
        body = mesh.get_editor_property('body_setup')
        body.set_editor_property('collision_trace_flag', unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        # Expected bounds: Blender X kept, Y flipped.
        lo, hi = spec[name]['min_cm'], spec[name]['max_cm']
        want = [[lo[0], -hi[1], lo[2]], [hi[0], -lo[1], hi[2]]]
        got = _bounds(mesh)
        bad = max(abs(a - b) for ra, rb in zip(want, got) for a, b in zip(ra, rb))
        report[name] = {'bounds': got, 'expected': want, 'bounds_ok': bad < 2.0, 'slots': slots,
                        'materials': [s.get_editor_property('material_interface').get_path_name()
                                      for s in mesh.get_editor_property('static_materials')],
                        'trace_flag': str(mesh.get_editor_property('body_setup').get_editor_property('collision_trace_flag')),
                        'simple_collision': mesh_editor.get_simple_collision_count(mesh),
                        'verts': mesh_editor.get_number_verts(mesh, 0)}
    # Anything else the importer made in our own folder (e.g. Interchange materials) is not wanted.
    stray = [path for path in unreal.EditorAssetLibrary.list_assets(DEST, recursive=True, include_folder=False)
             if path.split('/')[-1].split('.')[0] not in MESHES]
    for path in stray:
        unreal.EditorAssetLibrary.delete_asset(path)
    report['stray_deleted'] = stray
    return report


def save_meshes():
    require_editor()
    saved = {}
    for name in MESHES:
        saved[name] = unreal.EditorAssetLibrary.save_asset(f'{DEST}/{name}', only_if_is_dirty=False)
    return saved


def _tower_actors(world):
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return [a for a in actors.get_all_level_actors() if a.get_actor_label().startswith(LABEL)]


def _local(x, y, z=0.0):
    """Tower-local cm (Unreal axes) -> world, for the placed centre and yaw."""
    c, s = math.cos(math.radians(YAW)), math.sin(math.radians(YAW))
    return unreal.Vector(CENTRE[0] + c * x - s * y, CENTRE[1] + s * x + c * y, _GROUND[0] + z)


_GROUND = [0.0]


def ground_height(world):
    """Highest blocking surface under the tower footprint that is not the tower itself."""
    mine = _tower_actors(world)
    heights = []
    for dx, dy in ((0, 0), (-500, -500), (500, -500), (-500, 500), (500, 500)):
        start = unreal.Vector(CENTRE[0] + dx, CENTRE[1] + dy, 3000.0)
        end = unreal.Vector(CENTRE[0] + dx, CENTRE[1] + dy, -3000.0)
        hit = unreal.SystemLibrary.line_trace_single(world, start, end, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
                                                     True, mine, unreal.DrawDebugTrace.NONE, True)
        if hit:
            parts = hit.to_tuple()
            location = next((p for p in parts if isinstance(p, unreal.Vector)), None)   # Location precedes ImpactPoint
            component = next((p for p in parts if isinstance(p, unreal.PrimitiveComponent)), None)
            actor = component.get_owner() if component else None
            if location is not None:
                heights.append((round(location.z, 1), actor.get_actor_label() if actor else None))
    return heights


def place():
    _, world = require_editor()
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for old in _tower_actors(world):
        actors.destroy_actor(old)
    heights = ground_height(world)
    _GROUND[0] = max([h for h, _ in heights if abs(h) < 300], default=0.0)
    rotation = unreal.Rotator(0.0, 0.0, YAW)  # roll, pitch, yaw
    placed = []
    for name, part, z in (('SM_BellTower_Shell', 'Shell', 0.0), ('SM_BellTower_Stairs', 'Stairs', 0.0),
                          ('SM_BellTower_Rails', 'Rails', 0.0), ('SM_BellTower_Bell', 'Bell', HANG_CM)):
        mesh = unreal.EditorAssetLibrary.load_asset(f'{DEST}/{name}')
        actor = actors.spawn_actor_from_object(mesh, _local(0, 0, z), rotation)
        actor.set_actor_label(f'{LABEL} {part}')
        actor.set_folder_path(FOLDER)
        component = actor.static_mesh_component
        component.set_mobility(unreal.ComponentMobility.MOVABLE if part == 'Bell' else unreal.ComponentMobility.STATIC)
        if part in ('Rails', 'Bell'):
            # Keep blocking the player but let the follow camera pass (the well rail and the bell).
            component.set_collision_response_to_channel(unreal.CollisionChannel.ECC_CAMERA,
                                                        unreal.CollisionResponseType.ECR_IGNORE)
        placed.append(actor.get_actor_label())
    # Warm lamps down the stair well; the slits alone leave it too dark under Lumen.
    for index, height in enumerate(LIGHT_HEIGHTS_CM):
        light = actors.spawn_actor_from_class(unreal.PointLight, _local(0, 0, height), unreal.Rotator(0, 0, 0))
        light.set_actor_label(f'{LABEL} Lamp {index + 1}')
        light.set_folder_path(FOLDER)
        component = light.point_light_component
        component.set_mobility(unreal.ComponentMobility.MOVABLE)
        component.set_editor_property('intensity_units', unreal.LightUnits.CANDELAS)
        component.set_editor_property('intensity', 30.0)
        component.set_editor_property('attenuation_radius', 900.0)
        component.set_editor_property('light_color', unreal.Color(r=255, g=176, b=110, a=255))
        component.set_editor_property('cast_shadows', False)
        placed.append(light.get_actor_label())
    return {'ground_hits': heights, 'base_z': _GROUND[0], 'placed': placed,
            'door_world': [round(v, 1) for v in (_local(-420, 0).x, _local(-420, 0).y)]}


def save_map():
    _, world = require_editor()
    package = world.get_package()
    if package.get_name() != MAP:
        raise RuntimeError('Unexpected map package.')
    if not unreal.EditorLoadingAndSavingUtils.save_packages([package], only_dirty=False):
        raise RuntimeError('Map save failed.')
    return package.get_name()


def rebuild_navigation():
    _, world = require_editor()
    unreal.SystemLibrary.execute_console_command(world, 'RebuildNavigation')
    return 'navigation rebuild requested'


def navigation_busy():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    return bool(unreal.NavigationSystemV1.is_navigation_being_built_or_locked(world))


def nav_path_check():
    """Editor-world nav path along the main street through the market, (-3000, 0) to (3000, 0)."""
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    a, b = unreal.Vector(-3000.0, 0.0, 50.0), unreal.Vector(3000.0, 0.0, 50.0)
    path = unreal.NavigationSystemV1.find_path_to_location_synchronously(world, a, b)
    points = [p for p in path.get_editor_property('path_points')] if path else []
    # Any straight leg that crosses the plinth (X -450..450, Y -800..100) means the navmesh ignores the tower.
    crossings = 0
    for p, q in zip(points, points[1:]):
        for i in range(21):
            x, y = p.x + (q.x - p.x) * i / 20, p.y + (q.y - p.y) * i / 20
            if abs(x - CENTRE[0]) < 440 and abs(y - CENTRE[1]) < 440:
                crossings += 1
                break
    length = sum((points[i + 1] - points[i]).length() for i in range(len(points) - 1))
    return {'points': [[round(p.x), round(p.y)] for p in points], 'length_cm': round(length), 'straight_cm': 6000,
            'legs_through_plinth': crossings}


# --- PIE walk test ----------------------------------------------------------------
# Route through the tower in tower-local cm (Unreal axes: Blender Y flipped). The
# stair strips are 130 cm wide; their centre lines are 245 cm from the tower axis.
C = 245.0
CORNERS = {'SW': (-C, C), 'SE': (C, C), 'NE': (C, -C), 'NW': (-C, -C)}   # Blender S (-Y) is Unreal +Y
ROUTE = ([('street', (-650.0, 0.0)), ('door', (-360.0, 0.0)), ('inside', (-C, 0.0)), ('foot', CORNERS['SW'])] +
         [(f'landing{k + 1}', CORNERS['SE NE NW SW'.split()[k % 4]]) for k in range(9)] +
         [('hatch', (C, 120.0)), ('floor', (100.0, 120.0)), ('bell', (0.0, -100.0)), ('arch', (0.0, -230.0))])


def _world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


def _unwrap(value):
    return value['returnValue'] if isinstance(value, dict) and 'returnValue' in value else value


async def _shot(call_tool, name, result):
    try:
        cap = _unwrap(await call_tool('SceneCaptureToolset.SceneCaptureToolset.CaptureGameViewport',
                                      world=_world(), maxResolution=1600))
        data = cap['image'] if isinstance(cap, dict) else None
        if isinstance(data, dict):
            data = data.get('data') or data.get('base64')
        if data:
            if ',' in data[:64]:
                data = data.split(',', 1)[1]
            SHOTS.mkdir(parents=True, exist_ok=True)
            path = SHOTS / f'BellTower_{name}.png'
            path.write_bytes(base64.b64decode(data))
            result['shots'].append(str(path))
    except Exception as error:
        result.setdefault('shot_errors', []).append(f'{name}: {error!r}')


async def walk_test(call_tool, timeout_s=150.0):
    """Start PIE, put the hero on the street west of the door and walk the route to the belfry."""
    require_editor()
    result = {'reached': [], 'shots': [], 'ok': False}
    if _unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
        return {'abort': 'PIE already running; not ours, nothing started.'}
    # Read the editor world before PIE starts (during PIE the actor subsystem sees the PIE world).
    editor_world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    shell = next((a for a in _tower_actors(editor_world) if a.get_actor_label() == f'{LABEL} Shell'), None)
    if shell is None:
        return {'abort': 'tower not placed'}
    ground = shell.get_actor_location().z
    anchor = next((a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
                   if 'BurningEyes' in a.get_actor_label()), None)
    ax, ay = ((anchor.get_actor_location().x, anchor.get_actor_location().y) if anchor else (-1020.0, 600.0))
    result['bellsquare_anchor'] = [round(ax), round(ay), anchor.get_actor_label() if anchor else 'default (-1020, 600)']
    await call_tool('EditorToolset.EditorAppToolset.StartPIE')
    handle = None
    try:
        await asyncio.sleep(4.0)
        world = _world()
        if world is not None and MAP.rsplit('/', 1)[-1] not in str(world.get_name()):
            unreal.SystemLibrary.execute_console_command(world, 'open ' + MAP)
            await asyncio.sleep(10.0)
        for _ in range(20):
            await asyncio.sleep(1.0)
            world = _world()
            if world and unreal.GameplayStatics.get_player_pawn(world, 0):
                break
        world = _world()
        pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
        if pawn is None:
            result['error'] = 'no player pawn'
            return result
        target_index = [0]
        state = {'z_max': -1e9, 'fell': None}

        def local_to_world(x, y):
            c, s = math.cos(math.radians(YAW)), math.sin(math.radians(YAW))
            return CENTRE[0] + c * x - s * y, CENTRE[1] + s * x + c * y

        # Street view of the tower first (player stands 30 m west, looking up at it).
        sx, sy = local_to_world(-3200.0, 600.0)
        pawn.teleport(unreal.Vector(sx, sy, ground + 120.0), unreal.Rotator(0, 0, 0))
        controller = pawn.get_controller()
        await asyncio.sleep(1.5)
        controller.set_control_rotation(unreal.Rotator(0.0, 22.0, -8.0))   # roll, pitch, yaw
        await asyncio.sleep(1.0)
        await _shot(call_tool, 'street', result)
        # The opening BurningEyes cutscene is anchored at the BellSquare markers, 2.4 m west of the box.
        pawn.teleport(unreal.Vector(ax, ay, ground + 120.0), unreal.Rotator(0, 0, 0))
        await asyncio.sleep(1.2)
        look = math.degrees(math.atan2(CENTRE[1] - ay, CENTRE[0] - ax))
        controller.set_control_rotation(unreal.Rotator(0.0, 30.0, look))
        await asyncio.sleep(1.0)
        await _shot(call_tool, 'bellsquare_to_tower', result)
        x0, y0 = local_to_world(*ROUTE[0][1])
        pawn.teleport(unreal.Vector(x0, y0, ground + 120.0), unreal.Rotator(0, 0, 0))
        await asyncio.sleep(1.0)

        def drive(delta):
            p = _world() and unreal.GameplayStatics.get_player_pawn(_world(), 0)
            if not p or target_index[0] >= len(ROUTE):
                return
            here = p.get_actor_location()
            state['z_max'] = max(state['z_max'], here.z)
            if state['z_max'] - here.z > 150 and state['fell'] is None:
                state['fell'] = [round(here.x), round(here.y), round(here.z)]
            tx, ty = local_to_world(*ROUTE[target_index[0]][1])
            dx, dy = tx - here.x, ty - here.y
            dist = math.hypot(dx, dy)
            if dist < 45.0:
                result['reached'].append((ROUTE[target_index[0]][0], round(here.z - ground)))
                target_index[0] += 1
                return
            p.add_movement_input(unreal.Vector(dx / dist, dy / dist, 0.0), 1.0, False)

        handle = unreal.register_slate_post_tick_callback(drive)
        start = time.monotonic()
        last_progress, last_pos, shot_stairs = time.monotonic(), None, False
        while target_index[0] < len(ROUTE) and time.monotonic() - start < timeout_s and state['fell'] is None:
            await asyncio.sleep(0.5)
            here = pawn.get_actor_location()
            if last_pos is None or (here - last_pos).length() > 20:
                last_pos, last_progress = here, time.monotonic()
            elif time.monotonic() - last_progress > 4.0:
                result['stuck_at'] = {'next': ROUTE[target_index[0]][0], 'local': _to_local(here),
                                      'z_above_ground': round(here.z - ground)}
                break
            if not shot_stairs and target_index[0] >= 9:
                shot_stairs = True
                unreal.unregister_slate_post_tick_callback(handle)
                handle = None
                await asyncio.sleep(0.4)
                await _shot(call_tool, 'stairs', result)
                handle = unreal.register_slate_post_tick_callback(drive)
        if handle is not None:
            unreal.unregister_slate_post_tick_callback(handle)
            handle = None
        here = pawn.get_actor_location()
        result['final'] = {'local': _to_local(here), 'z_above_ground': round(here.z - ground)}
        result['fell'] = state['fell']
        result['seconds'] = round(time.monotonic() - start, 1)
        result['ok'] = target_index[0] >= len(ROUTE) and state['fell'] is None and here.z - ground > BELFRY_CM - 30
        if result['ok']:
            controller.set_control_rotation(unreal.Rotator(0.0, -6.0, -90.0 + YAW))   # out of the north arch
            await asyncio.sleep(1.0)
            await _shot(call_tool, 'view_from_top', result)
            controller.set_control_rotation(unreal.Rotator(0.0, 35.0, 90.0 + YAW))    # back at the bell
            await asyncio.sleep(0.8)
            await _shot(call_tool, 'bell', result)
    except Exception as error:
        result['error'] = repr(error)
    finally:
        if handle is not None:
            unreal.unregister_slate_post_tick_callback(handle)
        if _unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
            await call_tool('EditorToolset.EditorAppToolset.StopPIE')
    SHOTS.mkdir(parents=True, exist_ok=True)
    (SHOTS / 'walk_test.json').write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')
    return result


def _to_local(v):
    c, s = math.cos(math.radians(-YAW)), math.sin(math.radians(-YAW))
    x, y = v.x - CENTRE[0], v.y - CENTRE[1]
    return [round(c * x - s * y), round(s * x + c * y), round(v.z)]
