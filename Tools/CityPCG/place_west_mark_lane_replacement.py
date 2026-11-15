"""Place one owned, fail-closed West Mark Lane replacement actor.

The editor must have the new runtime class loaded, the original tile loaded,
and a valid ``codex-gray-london`` editor lease. No original package is saved.
"""

import json
import math
from pathlib import Path
import time

from apply_facade_pcg import ACTOR_PACKAGES, LEVEL, make_transform
from audit_replacement_tile_unreal import OWNED_TILE, inspect_owned_mesh


LABEL = 'MedievalWholeBuildings_WestMarkLane_Pilot'
OWNER = 'codex-gray-london'
ASSET_ROOT = '/Game/GrayLondon/MedievalOpening/WholeBuildings/WestMarkLane'
BUILDINGS = {
    'Tile_p03_p00_shell_d87bb24c9cdb': 'SM_GLMedieval_MarkLaneMerchantsHouses',
    'Tile_p03_p00_shell_3b4ea8e64fcb': 'SM_GLMedieval_MarkLaneWorkshop',
    'Tile_p03_p00_shell_c3d845a67ca8': 'SM_GLMedieval_MarkLaneTradingCompound',
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def checked_plan(project):
    root = project / 'ArtDirection/CityPCG/MedievalOpening'
    kit = read_json(root / 'WholeBuildings/whole_buildings_kit.json')['buildings']
    plan = read_json(root / 'west_mark_lane_whole_building_plan.json')
    source = {row['id']: row for row in plan['buildings']}
    if set(kit) != set(BUILDINGS) or set(source) != set(BUILDINGS):
        raise RuntimeError('The placement requires the three reviewed source shells.')
    rows = []
    for shell, asset in BUILDINGS.items():
        spec, reviewed = kit[shell], source[shell]
        pivot, yaw = spec['world_pivot_m'], float(spec['yaw_deg'])
        if (len(pivot) != 3 or not all(math.isfinite(float(value)) for value in pivot) or
                not math.isfinite(yaw) or spec['fbx'] != f'Source/{asset}.fbx' or
                any(abs(a - b) > 0.00001 for a, b in zip(pivot, reviewed['origin_m'])) or
                abs(yaw - reviewed['rotation_yaw_deg']) > 0.00001):
            raise RuntimeError(f'The {shell} mesh no longer matches its reviewed placement.')
        rows.append({'shell': shell, 'asset': f'{ASSET_ROOT}/{asset}',
                     'tag': f'WestMarkLane_{asset.removeprefix("SM_GLMedieval_")}',
                     'world_cm': [float(value) * 100 for value in pivot], 'yaw_deg': yaw})
    return rows


def require_lease(unreal):
    saved = Path(unreal.Paths.project_saved_dir())
    lease_path = saved / 'PIE_LOCK.json'
    try:
        lease = read_json(lease_path)
        expiry = float(lease['expires_epoch'])
    except (OSError, ValueError, KeyError) as error:
        raise RuntimeError('An intact, current editor lease is required.') from error
    if lease.get('owner') != OWNER or not math.isfinite(expiry) or expiry <= time.time():
        raise RuntimeError(f'The editor lease is not held by {OWNER}: {lease}')


def require_lease_and_editor(unreal):
    require_lease(unreal)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if (editor.get_game_world() or unreal.EditorLevelLibrary.get_pie_worlds(True) or
            not world or world.get_path_name().split('.')[0] != LEVEL):
        raise RuntimeError(f'Open {LEVEL} and stop PIE before placing this actor.')
    return world


def vector(value):
    return [float(getattr(value, axis)) for axis in 'xyz']


def audit_component(unreal, component, mesh, expected_position, expected_yaw, source_component, parent=None, tag=None):
    actual_rotation = component.get_world_rotation()
    # The aggregate actor is inactive, so read authored collision rather than its effective NoCollision state.
    configured_collision = component.get_editor_property('body_instance').get_editor_property('collision_enabled')
    source_collision = source_component.get_editor_property('body_instance').get_editor_property('collision_enabled')
    if (component.get_editor_property('static_mesh') != mesh or
            math.dist(vector(component.get_world_location()), expected_position) > .05 or
            abs((float(actual_rotation.yaw) - expected_yaw + 180) % 360 - 180) > .0001 or
            abs(float(actual_rotation.pitch)) > .0001 or abs(float(actual_rotation.roll)) > .0001 or
            math.dist(vector(component.get_world_scale()), [1, 1, 1]) > .00001 or
            str(component.get_collision_profile_name()) != 'BlockAll' or
            configured_collision != source_collision or
            component.get_collision_object_type() != source_component.get_collision_object_type() or
            not component.get_editor_property('can_ever_affect_navigation') or
            component.get_editor_property('generate_overlap_events') or
            component.get_editor_property('mobility') != unreal.ComponentMobility.STATIC):
        raise RuntimeError(f'Component setup or world transform differs for {mesh.get_name()}.')
    if tag and [str(name) for name in component.get_editor_property('component_tags')].count(tag) != 1:
        raise RuntimeError(f'Missing unique replacement component tag {tag}.')
    if parent and (component.get_attach_parent() != parent or component.get_outer() != parent.get_outer()):
        raise RuntimeError(f'{mesh.get_name()} is not a persistent child of the filtered tile.')


def run():
    import unreal

    project = Path(unreal.Paths.project_dir()).resolve()
    rows = checked_plan(project)
    require_lease_and_editor(unreal)
    if not hasattr(unreal, 'ReflectionsCityTileReplacement') or not hasattr(unreal, 'ReflectionsCityBuildingPart'):
        raise RuntimeError('Build and reload the city replacement runtime classes before placement.')
    survey = project / 'Saved/CityPCG/MedievalSurvey'
    source = inspect_owned_mesh(project / 'Saved/CityPCG/Tile_p03_p00.asset.json',
                                survey / 'Tile_p03_p00_without_three_west_shells.audit.json')['source']
    if (source['runtime_grid'] != 'None' or not source['spatially_loaded'] or source['data_layers'] or
            source['collision_profile'] != 'BlockAll' or not source['navigation']):
        raise RuntimeError('The source actor streaming or collision contract changed; review before placement.')
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    loaded = actors.get_all_level_actors()
    source_actor, = (actor for actor in loaded if actor.get_path_name() == source['actor'])
    source_component = source_actor.get_component_by_class(unreal.StaticMeshComponent)
    if (not source_component or source_component.get_collision_enabled() != unreal.CollisionEnabled.QUERY_AND_PHYSICS or
            source_component.get_collision_object_type() != unreal.CollisionChannel.ECC_WORLD_STATIC or
            source_component.get_editor_property('generate_overlap_events')):
        raise RuntimeError('The source actor physics activation, object channel, or overlap behavior changed.')
    labels = {actor.get_actor_label() for actor in loaded}
    labels.update(str(desc.get_editor_property('label'))
                  for desc in unreal.WorldPartitionBlueprintLibrary.get_actor_descs() or [])
    if LABEL in labels:
        raise RuntimeError('A replacement with the pilot label already exists.')
    asset_paths = [OWNED_TILE, source['source_asset'].split('.')[0]] + [row['asset'] for row in rows]
    meshes = [unreal.EditorAssetLibrary.load_asset(path) for path in asset_paths]
    if any(not isinstance(mesh, unreal.StaticMesh) for mesh in meshes):
        raise RuntimeError(f'A reviewed source or replacement mesh is missing: {asset_paths}')
    tile, original, *buildings = meshes
    mesh_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    for mesh in buildings:
        sections = mesh.get_num_sections(0)
        if (mesh_editor.get_collision_complexity(mesh) != unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE or
                mesh_editor.get_simple_collision_count(mesh) or
                mesh.get_editor_property('has_navigation_data') != source['has_navigation_data'] or not sections or
                not all(mesh_editor.is_section_collision_enabled(mesh, 0, index) for index in range(sections))):
            raise RuntimeError(f'{mesh.get_name()} is missing its reviewed complex building collision.')
    origin = source['location_cm']
    actor = None
    saved = False
    try:
        actor = actors.spawn_actor_from_class(unreal.ReflectionsCityTileReplacement,
                                              unreal.Vector(*origin), unreal.Rotator(0, 0, 0))
        if not actor:
            raise RuntimeError('Could not create the replacement actor.')
        actor.set_actor_label(LABEL)
        actor.set_folder_path('MedievalOpening/WholeBuildings')
        actor.set_editor_property('is_spatially_loaded', True)
        actor.set_actor_hidden_in_game(True)
        actor.set_actor_enable_collision(False)
        actor.set_editor_properties({'source_tile_mesh': original,
                                     'source_tile_world_transform': make_transform(unreal, origin)})
        filtered = actor.get_editor_property('filtered_tile')
        filtered.set_static_mesh(tile)
        filtered.set_collision_profile_name('BlockAll')
        filtered.set_editor_properties({'can_ever_affect_navigation': True, 'generate_overlap_events': False})

        subobjects = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
        data_api = unreal.SubobjectDataBlueprintFunctionLibrary
        handles = subobjects.k2_gather_subobject_data_for_instance(actor)
        roots = [handle for handle in handles if data_api.get_associated_object(data_api.get_data(handle)) == filtered]
        if len(roots) != 1:
            raise RuntimeError('Cannot resolve the exact native filtered-tile attachment root.')
        parts, components = [], []
        for row, mesh in zip(rows, buildings):
            handle, error = subobjects.add_new_subobject(unreal.AddNewSubobjectParams(
                parent_handle=roots[0], new_class=unreal.StaticMeshComponent, blueprint_context=None))
            data = data_api.get_data(handle)
            component = data_api.get_associated_object(data)
            if not isinstance(component, unreal.StaticMeshComponent) or not data_api.is_instanced_component(data):
                raise RuntimeError(f'Cannot create the {row["tag"]} component: {error}')
            component.set_static_mesh(mesh)
            component.set_collision_profile_name('BlockAll')
            component.set_editor_properties({'can_ever_affect_navigation': True, 'generate_overlap_events': False,
                                             'component_tags': [unreal.Name(row['tag'])]})
            relative = [value - base for value, base in zip(row['world_cm'], origin)]
            transform = make_transform(unreal, relative, row['yaw_deg'])
            component.set_relative_transform(transform, False, True)
            component.set_mobility(unreal.ComponentMobility.STATIC)
            part = unreal.ReflectionsCityBuildingPart()
            part.set_editor_properties({'component_tag': unreal.Name(row['tag']), 'mesh': mesh,
                                        'relative_transform': transform})
            parts.append(part)
            components.append(component)
        actor.set_editor_property('required_buildings', parts)
        if len(actor.get_components_by_class(unreal.PrimitiveComponent)) != len(parts) + 1:
            raise RuntimeError('The replacement actor does not contain exactly the expected primitive components.')
        if (str(actor.get_editor_property('runtime_grid')) != 'None' or
                actor.get_editor_property('data_layer_assets') or actor.get_editor_property('external_data_layer_asset') or
                not actor.get_editor_property('is_spatially_loaded')):
            raise RuntimeError('The replacement inherited an incompatible editor data layer or runtime grid.')
        if actor.get_actor_enable_collision() or not actor.get_editor_property('hidden'):
            raise RuntimeError('The replacement must remain hidden and noncolliding before runtime validation.')
        center, extent = actor.get_actor_bounds(False)
        world_bounds = [vector(center - extent), vector(center + extent)]
        expected_bounds = [[location + base for location, base in zip(bound, origin)]
                           for bound in source['bounds_local_cm']]
        if any(math.dist(a, b) > .2 for a, b in zip(world_bounds, expected_bounds)):
            raise RuntimeError('The aggregate bounds differ from the original tile streaming footprint.')
        audit_component(unreal, filtered, tile, origin, 0, source_component)
        for row, mesh, component in zip(rows, buildings, components):
            audit_component(unreal, component, mesh, row['world_cm'], row['yaw_deg'],
                            source_component, parent=filtered, tag=row['tag'])
        package = actor.get_package()
        path = package.get_name()
        if not path.startswith(ACTOR_PACKAGES):
            raise RuntimeError(f'The replacement has no separate Gray London actor package: {path}')
        require_lease_and_editor(unreal)
        if not unreal.EditorLoadingAndSavingUtils.save_packages([package], only_dirty=False):
            raise RuntimeError(f'Could not save the replacement actor package: {path}')
        saved = True
        multi_user = unreal.MultiUserClientStatics
        if multi_user.get_multi_user_connection_status_detail() == unreal.MultiUserConnectionStatus.CONNECTED:
            multi_user.persist_specified_packages([path])
        return {'actor': actor.get_path_name(), 'saved_packages': [path], 'source_actor': source['actor'],
                'buildings': rows, 'note': 'Runtime streaming and gameplay still require validation.'}
    except Exception:
        if actor and not saved:
            actors.destroy_actor(actor)
        raise
