"""Read-only audit of the crowd setup and Mark Lane slots in Unreal Editor.

Run in GrayLondon_Geodata via Unreal Python. Call take_play_audit() to inspect
an existing Play In Editor session without touching the player or camera.
"""

from collections import Counter
import json
import math
from pathlib import Path
import re

import unreal


MAP = '/Game/GrayLondon/Maps/GrayLondon_Geodata'
PLUGINS = ('MassGameplay', 'MassAI', 'MassCrowd', 'MetaHumanCrowd',
           'ZoneGraph', 'ZoneGraphAnnotations')
ACTOR_TYPES = ('ZoneShape', 'ZoneGraphData', 'MassSpawner')
MARK_LANE_SPOTS = {'mark_lane_provisions_browse', 'mark_lane_lantern_room_chat'}
CROWD_OBJECTS = (unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1,
                 unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2)
PLAY_CLASSES = ('ReflectionsCrowdRingSubsystem', 'ReflectionsCrowdSpotSubsystem',
                'ReflectionsCrowdLaneLibrary', 'ReflectionsWorldLibrary',
                'ReflectionsGameFlowSubsystem', 'ReflectionsCutsceneSubsystem')


def lane_actor_counts(world):
    # An unloaded World Partition actor is absent from GameplayStatics.
    descriptors = unreal.WorldPartitionBlueprintLibrary.get_actor_descs() or []
    counts = Counter()
    for descriptor in descriptors:
        actor_class = descriptor.get_editor_property('native_class')
        if actor_class and actor_class.get_name() in ACTOR_TYPES:
            counts[actor_class.get_name()] += 1
    loaded = {name: len(unreal.GameplayStatics.get_all_actors_of_class(world, getattr(unreal, name)))
              for name in ACTOR_TYPES if hasattr(unreal, name)}
    return {'descriptors': dict.fromkeys(ACTOR_TYPES, 0) | dict(counts), 'loaded': loaded}


def probe_floor(world, x, y, z, radius, half_height, clearance):
    hit = unreal.SystemLibrary.line_trace_single_for_objects(
        world, unreal.Vector(x, y, z + 15000), unreal.Vector(x, y, z - 5000),
        CROWD_OBJECTS, False, [], unreal.DrawDebugTrace.NONE, True,
    )
    if not hit:
        return {'point': (x, y, z), 'clear': False, 'floor': None}
    fields = hit.to_tuple()
    point, normal, actor = fields[4], fields[7], fields[9]
    center = point + unreal.Vector(0, 0, half_height + clearance)
    overlap = unreal.SystemLibrary.capsule_trace_single_for_objects(
        world, center, center + unreal.Vector(0, 0, 0.01), radius, half_height,
        CROWD_OBJECTS, False, [], unreal.DrawDebugTrace.NONE, True,
    )
    return {
        'point': (round(x, 1), round(y, 1), round(point.z, 1)),
        'floor': actor.get_actor_label() if actor else None,
        'clear': normal.z >= 0.8 and abs(point.z - z) <= 10 and not overlap,
    }


def mark_lane_slots(world, project_dir):
    path = project_dir / 'Content/Crowd/Spots/GrayLondon_Geodata.json'
    spots = json.loads(path.read_text(encoding='utf-8-sig'))['spots']
    result = []
    for spot in spots:
        if spot['name'] not in MARK_LANE_SPOTS:
            continue
        x, y, z = (spot[axis] for axis in ('x', 'y', 'z'))
        if spot['kind'] == 'chat':
            # Align the two 85 cm offsets with the shopfront's long axis.
            angle = math.radians(spot['yaw'])
            dx, dy = 85 * math.cos(angle), 85 * math.sin(angle)
            points = ((x + dx, y + dy), (x - dx, y - dy))
        else:
            points = ((x, y),)
        entries = []
        for sx, sy in points:
            # East pavement opens toward -X, with the wall at +X.
            # 86 cm separates the 38 cm spot capsule from a 42 cm player.
            entries.append({
                'slot': probe_floor(world, sx, sy, z, 38, 88, 4),
                'pass_beside': [probe_floor(world, sx - 86 + dy * 0.153, sy + dy, z, 42, 96, 4)
                                for dy in (-45, 0, 45)],
            })
        cx = probe_floor(world, x, y, z, 38, 88, 4)
        result.append({'name': spot['name'], 'center': cx, 'slots': entries,
                       'pinned': spot['pinned']})
    return {'total_spots': len(spots), 'mark_lane': result}


def vector_cm(vector):
    return [round(value, 1) for value in (vector.x, vector.y, vector.z)]


def walker_in_view(world, controller, eye, viewport, walker):
    if walker.get_editor_property('hidden'):
        return False
    origin, extent = walker.get_actor_bounds(False, True)
    for height in (0.3, 0.8):
        point = origin + unreal.Vector(0, 0, extent.z * height)
        pixel = unreal.GameplayStatics.project_world_to_screen(controller, point)
        if pixel is None or not (0 <= pixel.x < viewport[0] and 0 <= pixel.y < viewport[1]):
            continue
        block = unreal.SystemLibrary.line_trace_single(
            world, eye, point, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True,
            [controller.get_controlled_pawn(), walker], unreal.DrawDebugTrace.NONE, True,
        )
        if not block:
            return True
    return False


def take_play_audit():
    """Read the running local player's crowd and camera state in one sample."""
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_game_world()
    classes = {name: getattr(unreal, name, None) for name in PLAY_CLASSES}
    results = {'pie_running': world is not None,
               'compiled': {name: cls is not None for name, cls in classes.items()}}
    if world is None:
        return results

    gs = unreal.GameplayStatics
    ring_class = classes['ReflectionsCrowdRingSubsystem']
    spot_class = classes['ReflectionsCrowdSpotSubsystem']
    flow_class = classes['ReflectionsGameFlowSubsystem']
    cutscene_class = classes['ReflectionsCutsceneSubsystem']
    world_library = classes['ReflectionsWorldLibrary']
    ring = unreal.get_world_subsystem(world, ring_class) if ring_class else None
    spots = unreal.get_world_subsystem(world, spot_class) if spot_class else None
    cutscene = unreal.get_world_subsystem(world, cutscene_class) if cutscene_class else None
    instance = gs.get_game_instance(world)
    flow = unreal.get_game_instance_subsystem(instance, flow_class) if flow_class and instance else None
    starts = gs.get_all_actors_of_class(world, unreal.PlayerStart)
    start = next((a for a in starts if str(a.get_editor_property('player_start_tag')) == 'Lanthorne'), None)
    controller = gs.get_player_controller(world, 0)
    pawn = gs.get_player_pawn(world, 0)
    walkers = [actor for actor in ring.get_walkers() if actor] if ring else []
    results.update({
        'map': re.sub(r'/UEDPIE_\d+_', '/', world.get_path_name().split('.')[0]),
        'world_side': str(world_library.get_current_world(world)) if world_library else None,
        'menu_screen': str(flow.get_screen()) if flow else None,
        'run_live': flow.is_run_live() if flow and hasattr(flow, 'is_run_live') else None,
        'cutscene_playing': cutscene.is_cutscene_playing() if cutscene else None,
        'lanthorne_start_cm': vector_cm(start.get_actor_location()) if start else None,
        'pawn_location_cm': vector_cm(pawn.get_actor_location()) if pawn else None,
        'ring_requested': unreal.SystemLibrary.get_console_variable_int_value('Crowd.Ring.Count'),
        'ring_walkers': ring.get_walker_count() if ring else None,
        'ring_status': ring.describe().splitlines()[0] if ring else None,
        'spots_loaded': spots.get_spot_count() if spots else None,
        'spot_occupants': spots.get_occupied_count() if spots else None,
        'mark_lane_spots': [line for line in spots.describe().splitlines()
                            if any(name in line for name in MARK_LANE_SPOTS)] if spots else [],
        'visible_ring_walkers': None,
    })
    camera = controller.player_camera_manager if controller else None
    if pawn and camera:
        eye = camera.get_camera_location()
        viewport = controller.get_viewport_size()
        results['camera_location_cm'] = vector_cm(eye)
        results['camera_yaw'] = round(camera.get_camera_rotation().yaw, 1)
        results['viewport_px'] = list(viewport)
        if ring and min(viewport) > 0:
            names = [actor.get_name() for actor in walkers
                     if walker_in_view(world, controller, eye, viewport, actor)]
            results['visible_ring_walkers'] = len(names)
            results['visible_walker_names'] = names
    return results


def run():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world.get_path_name().split('.')[0] != MAP:
        return {'error': f'Open {MAP} to audit it.', 'world': world.get_path_name()}

    project_dir = Path(unreal.Paths.project_dir())
    enabled = set(unreal.PluginBlueprintLibrary.get_enabled_plugin_names())
    console = unreal.SystemLibrary
    lane_library = getattr(unreal, 'ReflectionsCrowdLaneLibrary', None)
    results = {
        'world': world.get_path_name(),
        'plugins_enabled': {name: name in enabled for name in PLUGINS},
        'native_route_actors': lane_actor_counts(world),
        'built_lanes': lane_library.describe_lanes(world) if lane_library else None,
        'mass': {
            'enabled': console.get_console_variable_int_value('Crowd.Mass.Enable'),
            'host_map': console.get_console_variable_string_value('Crowd.Mass.HostMap'),
            'level': console.get_console_variable_string_value('Crowd.Mass.Level'),
        },
        'ring': {
            'enabled': console.get_console_variable_int_value('Crowd.Ring.Enable'),
            'maps': console.get_console_variable_string_value('Crowd.Ring.Maps'),
            'count': console.get_console_variable_int_value('Crowd.Ring.Count'),
        },
        'spots': mark_lane_slots(world, project_dir),
    }
    play = take_play_audit()
    results['live_spot_subsystem_compiled'] = play['compiled']['ReflectionsCrowdSpotSubsystem']
    results['play'] = play
    return results


if __name__ == '__main__':
    unreal.log(json.dumps(run()))
