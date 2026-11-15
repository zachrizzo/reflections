"""Read-only West Mark Lane pilot checks for an operator-controlled PIE session.

Hold the codex-gray-london PIE lease. Call audit("baseline") in the loaded editor,
then start PIE normally and call audit("active", baseline=baseline) after walking
to West Mark Lane. For World Partition coverage, walk away, wait for streaming,
call audit("away"), return and call audit("active", baseline=baseline) again.
Use assess_cycle(first_active, away, second_active) to verify the same PIE run.
The audit never starts PIE, changes streaming sources, moves a player or camera,
or modifies an actor, world or package. Call audit("baseline") again after PIE.
"""

import math
from pathlib import Path
import re

from place_west_mark_lane_replacement import (
    LABEL, LEVEL, OWNED_TILE, audit_component, checked_plan, require_lease, vector,
)


SOURCE_MESH = '/Game/GrayLondon/Geodata/Tiles/Tile_p03_p00.Tile_p03_p00'
TILE_ORIGIN_CM = (300000., 0., 0.)
# Original heights from the source GLB; replacement heights from the authored FBXs.
ROOFS_CM = (
    ((311746.833, 40360.133), 1500., 1002.59, 'WestMarkLane_MarkLaneMerchantsHouses'),
    ((312594.167, 38240.233), 1280., 813.55, 'WestMarkLane_MarkLaneWorkshop'),
    ((314064.367, 38223.467), 1500., 1278.67, 'WestMarkLane_MarkLaneTradingCompound'),
)
ROADS_CM = {
    'north_merchant_street': ((311700., 40800.), (311800., 40730.), (311900., 40700.)),
    'south_workshop_street': ((312080., 36700.), (312280., 36740.), (312480., 36780.)),
}
ROAD_Z_CM = 28.


def component_asset(component):
    mesh = component.get_editor_property('static_mesh') if component else None
    return mesh.get_path_name() if mesh else None


def describe_actor(actor):
    if actor is None:
        return None
    return {
        'path': actor.get_path_name(),
        'level': actor.get_level().get_path_name(),
        'hidden': actor.get_editor_property('hidden'),
        'collision_enabled': actor.get_actor_enable_collision(),
    }


def hit_data(unreal, hit):
    if not hit:
        return None
    result = hit.to_tuple()
    return {'impact_cm': vector(result[5]), 'normal': vector(result[7]),
            'initial_overlap': bool(result[1]), 'actor': result[9].get_path_name() if result[9] else None,
            'mesh': component_asset(result[10]) if isinstance(result[10], unreal.StaticMeshComponent) else None}


def roof_report(unreal, world, replaced, rows, failures):
    expected_parts = {row['tag']: f"{row['asset']}.{row['asset'].rsplit('/', 1)[-1]}" for row in rows}

    def ray(point, stop):
        return hit_data(unreal, unreal.SystemLibrary.line_trace_single(
            world, unreal.Vector(*point, 2400.), unreal.Vector(*point, stop),
            unreal.TraceTypeQuery.ECC_VISIBILITY, True, [], unreal.DrawDebugTrace.NONE, False))

    report = {}
    for xy, old_z, new_z, part in ROOFS_CM:
        old_band = ray(xy, (old_z + new_z) / 2)
        actual = ray(xy, 300.)
        expected_mesh, expected_z = (expected_parts[part], new_z) if replaced else (SOURCE_MESH, old_z)
        if not actual or actual['mesh'] != expected_mesh or abs(actual['impact_cm'][2] - expected_z) > 4.:
            failures.append(f'{part}: Expected the {expected_mesh} roof at {expected_z} cm.')
        if replaced and old_band:
            failures.append(f'{part}: Collision still spans the original roof elevation band.')
        if not replaced and (not old_band or old_band['mesh'] != SOURCE_MESH):
            failures.append(f'{part}: Original roof collision was not observed.')
        report[part] = {'xy_cm': xy, 'original_band_hit': old_band, 'highest_hit': actual}
    return report


def road_report(unreal, world, floor_mesh, pawn, failures):
    capsule = pawn.get_component_by_class(unreal.CapsuleComponent) if pawn else None
    radius = capsule.get_scaled_capsule_radius() if capsule else 42.
    half_height = capsule.get_scaled_capsule_half_height() if capsule else 96.
    blockers_to_ignore = [pawn] if pawn else []
    report = {'capsule_radius_cm': radius, 'capsule_half_height_cm': half_height,
              'capsule_from_player': bool(capsule), 'routes': {}}
    for name, route in ROADS_CM.items():
        samples = []
        for xy in route:
            ground = hit_data(unreal, unreal.SystemLibrary.line_trace_single(
                world, unreal.Vector(*xy, 80.), unreal.Vector(*xy, -20.),
                unreal.TraceTypeQuery.ECC_VISIBILITY, True, blockers_to_ignore,
                unreal.DrawDebugTrace.NONE, False))
            if (not ground or ground['mesh'] != floor_mesh or abs(ground['impact_cm'][2] - ROAD_Z_CM) > 1.
                    or ground['normal'][2] < .98):
                failures.append(f'{name} {xy}: Expected the retained walkable road at Z {ROAD_Z_CM} cm.')
            nav = unreal.NavigationSystemV1.project_point_to_navigation(
                world, unreal.Vector(*xy, ROAD_Z_CM + 8.), None, None, unreal.Vector(75., 75., 100.))
            samples.append({'xy_cm': xy, 'floor': ground, 'nav_cm': vector(nav) if nav is not None else None})
        clearance = []
        center_z = ROAD_Z_CM + half_height + 3.
        for start, end in zip(route, route[1:]):
            hit = hit_data(unreal, unreal.SystemLibrary.capsule_trace_single_by_profile(
                world, unreal.Vector(*start, center_z), unreal.Vector(*end, center_z),
                radius, half_height, 'Pawn', False, blockers_to_ignore, unreal.DrawDebugTrace.NONE, False))
            if hit:
                failures.append(f'{name}: Player-profile capsule blocked on {start} to {end} by {hit["actor"]}.')
            clearance.append({'start_xy_cm': start, 'end_xy_cm': end, 'hit': hit})
        path = None
        if samples[0]['nav_cm'] is not None and samples[-1]['nav_cm'] is not None:
            status, length = unreal.NavigationSystemV1.get_path_length(
                world, unreal.Vector(*samples[0]['nav_cm']), unreal.Vector(*samples[-1]['nav_cm']), None, None)
            path = {'status': str(status), 'success': status == unreal.NavigationQueryResult.SUCCESS,
                    'length_cm': float(length)}
        report['routes'][name] = {'samples': samples, 'capsule_sweeps': clearance, 'nav_path': path}
    return report


def compare_navigation(unreal, world, report, baseline, require_navigation, failures):
    nav_data = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.NavigationData)
    modes = {actor.get_path_name(): str(actor.get_editor_property('runtime_generation')) for actor in nav_data}
    total = 0
    projected = 0
    routes_passed = 0
    old_routes = baseline['roads']['routes'] if baseline else {}
    for name, route in report['routes'].items():
        old_route = old_routes.get(name)
        new_path, old_path = route['nav_path'], old_route['nav_path'] if old_route else None
        path_exists = bool(new_path and new_path['success'])
        routes_passed += path_exists
        if ((require_navigation or (old_path and old_path['success'])) and not path_exists):
            failures.append(f'{name}: No complete navigation path across the tested road.')
        if (path_exists and old_path and old_path['success'] and
                new_path['length_cm'] > old_path['length_cm'] * 1.25 + 50.):
            failures.append(f'{name}: Navigation path length increased after the swap.')
        for index, sample in enumerate(route['samples']):
            total += 1
            point = sample['nav_cm']
            projected += point is not None
            previous = old_route['samples'][index]['nav_cm'] if old_route else None
            if (require_navigation and point is None) or (previous and (not point or math.dist(point, previous) > 50.)):
                failures.append(f'{name} {sample["xy_cm"]}: Expected comparable navigation projection.')
    return {'projected': projected, 'samples': total, 'complete_paths': routes_passed,
            'compared_to_editor_baseline': bool(baseline), 'runtime_generation_modes': modes,
            'build_in_progress': unreal.NavigationSystemV1.is_navigation_being_built(world),
            'static_nav_can_retain_original_geometry': any(
                actor.get_editor_property('runtime_generation') != unreal.RuntimeGenerationType.DYNAMIC
                for actor in nav_data)}


def audit(phase='active', *, pie_world_index=None, baseline=None, require_navigation=False):
    """Inspect one world snapshot and compare navigation with an optional passing editor baseline."""
    import unreal

    if phase not in ('baseline', 'active', 'away'):
        raise ValueError('Expected baseline, active or away.')
    if baseline and (baseline['phase'] != 'baseline' or baseline['status'] != 'pass'):
        raise ValueError('Navigation comparison requires a passing editor baseline.')
    require_lease(unreal)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    pie_worlds = unreal.EditorLevelLibrary.get_pie_worlds(True)
    if phase == 'baseline':
        if pie_worlds or editor.get_game_world():
            raise RuntimeError('Collect the editor baseline outside PIE.')
        world = editor.get_editor_world()
    elif pie_world_index is None:
        world = editor.get_game_world()
    else:
        if not 0 <= pie_world_index < len(pie_worlds):
            raise ValueError(f'PIE world index {pie_world_index} is unavailable.')
        world = pie_worlds[pie_world_index]
    path = world.get_path_name() if world else ''
    package = re.sub(r'/UEDPIE_\d+_', '/', path.split('.')[0])
    if package != LEVEL or (phase != 'baseline' and world not in pie_worlds):
        raise RuntimeError(f'Expected the requested Gray London world, got {path!r}.')

    actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.StaticMeshActor)
    sources = []
    for actor in actors:
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        if (component_asset(component) == SOURCE_MESH and
                math.dist(vector(component.get_world_location()), TILE_ORIGIN_CM) <= .05):
            sources.append((actor, component))
    groups = [actor for actor in unreal.GameplayStatics.get_all_actors_of_class(
        world, unreal.ReflectionsCityTileReplacement) if actor.get_actor_label(False) == LABEL]
    source, source_component = sources[0] if len(sources) == 1 else (None, None)
    group = groups[0] if len(groups) == 1 else None
    pawn = unreal.GameplayStatics.get_player_pawn(world, 0) if phase != 'baseline' else None
    wp = unreal.get_world_subsystem(world, unreal.WorldPartitionSubsystem)
    result = {
        'phase': phase, 'world': path, 'seconds': unreal.GameplayStatics.get_real_time_seconds(world),
        'player_location_cm': vector(pawn.get_actor_location()) if pawn else None,
        'streaming_completed': wp.is_all_streaming_completed() if wp else None,
        'source': describe_actor(source), 'group': describe_actor(group),
        'matching_sources': len(sources), 'matching_groups': len(groups), 'failures': [],
    }
    failures = result['failures']
    if len(sources) > 1 or len(groups) > 1:
        failures.append('Multiple actors match the single pilot source or replacement.')
        result['status'] = 'fail'
        return result
    if phase != 'baseline' and result['streaming_completed'] is not True:
        result['status'] = 'pending_streaming'
        return result
    if phase == 'active' and (not source or not group):
        failures.append('The source and replacement must both be streamed at West Mark Lane.')
    if phase == 'baseline' and not source:
        failures.append('Load the exact original tile in the editor before collecting the baseline.')
    if phase == 'away' and source and group:
        result['status'] = 'still_loaded'
        return result

    replaced = phase == 'active'
    if source:
        state = result['source']
        if state['hidden'] != replaced or state['collision_enabled'] == replaced:
            failures.append('Original tile render or collision gate is incorrect for this phase.')
        expected_collision = unreal.CollisionEnabled.NO_COLLISION if replaced else unreal.CollisionEnabled.QUERY_AND_PHYSICS
        try:
            audit_component(unreal, source_component, source_component.get_editor_property('static_mesh'),
                            TILE_ORIGIN_CM, 0., source_component)
        except RuntimeError as error:
            failures.append(str(error))
        if (source_component.get_collision_enabled() != expected_collision or
                not source_component.get_editor_property('static_mesh').get_editor_property('has_navigation_data')):
            failures.append('Original tile has incorrect effective collision or mesh navigation.')
    if group:
        state = result['group']
        if state['hidden'] == replaced or state['collision_enabled'] != replaced:
            failures.append('Replacement render or collision gate is incorrect for this phase.')
    rows = checked_plan(Path(unreal.Paths.project_dir()).resolve())
    if source and group and replaced:
        filtered = group.get_editor_property('filtered_tile')
        components = group.get_components_by_class(unreal.PrimitiveComponent)
        tagged = {str(tag): component for component in components
                  for tag in component.get_editor_property('component_tags')}
        if len(components) != 4 or filtered not in components:
            failures.append('The replacement does not have exactly four primitive components.')
        expected = [(filtered, OWNED_TILE, TILE_ORIGIN_CM, 0., None)]
        expected.extend((tagged.get(row['tag']), row['asset'], row['world_cm'], row['yaw_deg'], row['tag']) for row in rows)
        result['components'] = []
        for component, asset, xyz, yaw, tag in expected:
            if not isinstance(component, unreal.StaticMeshComponent) or (
                    component_asset(component) or '').split('.')[0] != asset:
                failures.append(f'Missing required replacement component for {asset}.')
                continue
            mesh = component.get_editor_property('static_mesh')
            try:
                audit_component(unreal, component, mesh, xyz, yaw, source_component,
                                parent=filtered if tag else None, tag=tag)
            except RuntimeError as error:
                failures.append(str(error))
            collision = component.get_collision_enabled()
            if (collision != unreal.CollisionEnabled.QUERY_AND_PHYSICS or
                    not component.is_visible() or component.get_editor_property('hidden_in_game') or
                    not mesh.get_editor_property('has_navigation_data')):
                failures.append(f'{asset} has a visibility, effective collision or mesh navigation mismatch.')
            result['components'].append({'asset': asset, 'collision': str(collision),
                                         'can_affect_navigation': component.get_editor_property('can_ever_affect_navigation')})
    if source and (not replaced or group):
        floor_mesh = f'{OWNED_TILE}.{OWNED_TILE.rsplit("/", 1)[-1]}' if replaced else SOURCE_MESH
        result['roofs'] = roof_report(unreal, world, replaced, rows, failures)
        result['roads'] = road_report(unreal, world, floor_mesh, pawn, failures)
        result['navigation'] = compare_navigation(unreal, world, result['roads'], baseline, require_navigation, failures)
    result['restored_source_observed'] = phase == 'away' and bool(source) and not group and not failures
    result['status'] = 'fail' if failures else 'pass'
    return result


def assess_cycle(first, away, last):
    """Check active -> away -> active results taken in chronological order in one PIE world."""
    ordered = (first['world'] == away['world'] == last['world'] and first['seconds'] < away['seconds'] < last['seconds'])
    phases = [result['phase'] for result in (first, away, last)]
    passed = all(result['status'] == 'pass' for result in (first, away, last))
    return {'pass': ordered and phases == ['active', 'away', 'active'] and passed,
            'replacement_unload_observed': away.get('group') is None and away['status'] == 'pass',
            'source_unload_observed': away.get('source') is None and away['status'] == 'pass',
            'source_restore_observed': away.get('restored_source_observed', False),
            'statuses': [result['status'] for result in (first, away, last)]}
