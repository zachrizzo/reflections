"""Collect floor trace observations for an offline street plan in the Unreal Editor."""

import json
from pathlib import Path

import unreal


LEVEL = '/Game/GrayLondon/Maps/GrayLondon_Geodata'


def collect(plan_path, output_path):
    world_manager = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = world_manager.get_editor_world()
    if not world or world.get_path_name().split('.')[0] != LEVEL or world_manager.get_game_world():
        raise RuntimeError('Floor evidence requires Gray London in the editor outside PIE')
    plan = json.loads(Path(plan_path).read_text(encoding='utf-8'))
    tile_label = plan['source_tile_actor']
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    if not any(actor.get_actor_label() == tile_label for actor in actors):
        raise RuntimeError(f'Load {tile_label} in the editor before collecting floor evidence')

    samples = []
    for guard in plan['floor_trace_guards']:
        x, y = guard['xy_cm']
        hit = unreal.SystemLibrary.line_trace_single(
            world, unreal.Vector(x, y, guard['from_z_cm']), unreal.Vector(x, y, guard['to_z_cm']),
            unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [], unreal.DrawDebugTrace.NONE,
        )
        record = hit.to_tuple() if hit else None
        hit_actor = record[9] if record else None
        samples.append({
            'id': guard['id'], 'xy_cm': [x, y],
            'actor': hit_actor.get_actor_label() if hit_actor else None,
            'z_cm': record[4].z if hit_actor else None,
            'normal_z': record[7].z if hit_actor else None,
        })
    path = Path(output_path)
    path.write_text(json.dumps(samples, indent=2)+'\n', encoding='utf-8')
    return {'observations': len(samples), 'file': str(path)}
