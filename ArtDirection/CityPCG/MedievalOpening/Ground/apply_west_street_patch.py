"""Import and place the verified west patch using the existing opening material."""

import hashlib
import json
import math
from pathlib import Path

import unreal


ROOT = Path(__file__).resolve().parent / 'West'
DESTINATION = '/Game/GrayLondon/MedievalOpening/Ground/West'
LEVEL = '/Game/GrayLondon/Maps/GrayLondon_Geodata'
ACTOR_PACKAGES = '/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/'
ACTOR = 'GL_1450_West_StreetPaving'


def verify_current_floor(plan):
    editor_world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor_world.get_editor_world()
    if not world or world.get_path_name().split('.')[0] != LEVEL or editor_world.get_game_world():
        raise RuntimeError('West paving requires Gray London in the editor outside PIE')
    failures = []
    for guard in plan['floor_trace_guards']:
        x, y = guard['xy_cm']
        hit = unreal.SystemLibrary.line_trace_single(
            world, unreal.Vector(x, y, guard['from_z_cm']), unreal.Vector(x, y, guard['to_z_cm']),
            unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [], unreal.DrawDebugTrace.NONE,
        )
        record = hit.to_tuple() if hit else None
        if (not record or not record[9] or record[9].get_actor_label() != guard['expect_actor'] or
                abs(record[4].z - guard['expect_z_cm']) > guard['tolerance_z_cm'] or
                record[7].z < guard['min_normal_z']):
            failures.append(guard['id'])
    if failures:
        raise RuntimeError(f'Floor changed since review: {failures}')
    return len(plan['floor_trace_guards'])


def import_mesh(source, report, plan, material):
    assets = unreal.EditorAssetLibrary.list_assets(DESTINATION, recursive=True, include_folder=False)
    if not assets:
        task = unreal.AssetImportTask()
        task.set_editor_properties({
            'filename': str(source), 'destination_path': DESTINATION, 'destination_name': report['mesh'],
            'automated': True, 'save': False, 'replace_existing': False,
        })
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        imported = list(task.get_objects())
    else:
        imported = [unreal.load_asset(path) for path in assets]
    if len(imported) != 1 or not isinstance(imported[0], unreal.StaticMesh):
        raise RuntimeError(f'Expected one untextured static mesh: {imported}')
    mesh, = imported
    path = mesh.get_package().get_name()
    if not path.startswith(f'{DESTINATION}/') or mesh.get_name() != report['mesh']:
        raise RuntimeError(f'Unexpected west paving mesh: {path}')

    editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    box = mesh.get_bounding_box()
    origin = report['actor_origin_cm']
    points = [vertex for patch in plan['patches'] for vertex in patch['world_vertices_cm']]
    for key, chooser in (('min', min), ('max', max)):
        actual = box.get_editor_property(key)
        expected = [chooser(point[dim] - origin[dim] for point in points) for dim in range(3)]
        if math.dist((actual.x, actual.y, actual.z), expected) > .2:
            raise RuntimeError(f'Unexpected coordinate conversion for {path}/{key}')
    triangles = mesh.get_static_mesh_description(0).get_triangle_count()
    if triangles != report['triangles'] or editor.get_num_uv_channels(mesh, 0) != 1:
        raise RuntimeError(f'Unexpected west paving topology or UVs: {triangles} triangles')
    if editor.get_simple_collision_count(mesh):
        editor.remove_collisions(mesh)
    mesh.set_material(0, material)
    if mesh.get_material(0) != material:
        raise RuntimeError(f'Shared paving material was not assigned to {path}')
    return mesh


def place_actor(mesh, origin):
    editor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    selection = editor.get_selected_level_actors()
    matching = [actor for actor in editor.get_all_level_actors() if actor.get_actor_label() == ACTOR]
    if len(matching) > 1:
        raise RuntimeError(f'Duplicate west paving actors: {matching}')
    try:
        with unreal.ScopedEditorTransaction('Place west medieval street paving'):
            actor = matching[0] if matching else editor.spawn_actor_from_object(mesh, origin, unreal.Rotator())
            if not actor or not actor.get_package().get_name().startswith(ACTOR_PACKAGES):
                raise RuntimeError('West paving actor must be an external Gray London actor')
            actor.modify()
            actor.set_actor_label(ACTOR)
            actor.set_folder_path('Gray London/Medieval Opening/West Street')
            actor.set_actor_location(origin, False, True)
            component = actor.get_component_by_class(unreal.StaticMeshComponent)
            component.modify()
            component.set_collision_profile_name('NoCollision')
            component.set_editor_property('cast_shadow', False)
            actor.set_actor_enable_collision(False)
            if (str(component.get_collision_profile_name()) != 'NoCollision' or
                    actor.get_actor_enable_collision() or component.get_editor_property('static_mesh') != mesh):
                raise RuntimeError('West paving actor needs the exact visual-only draft mesh')
            return actor
    finally:
        editor.set_selected_level_actors(selection)


def apply(plan_path):
    plan_bytes = Path(plan_path).read_bytes()
    plan = json.loads(plan_bytes)
    report = json.loads((ROOT/'west_street_mesh.json').read_text(encoding='utf-8'))
    mesh_file = ROOT / f'{report["mesh"]}.glb'
    if (plan['trace_status'] != 'verified' or plan['collision_profile'] != 'NoCollision' or
            report['plan_sha256'] != hashlib.sha256(plan_bytes).hexdigest() or
            report['mesh_sha256'] != hashlib.sha256(mesh_file.read_bytes()).hexdigest()):
        raise RuntimeError('West paving source and floor evidence must match the verified plan')
    material = unreal.load_asset(report['material_asset'])
    if not isinstance(material, unreal.MaterialInterface) or material.get_package().get_name() != plan['material_asset']:
        raise RuntimeError('The existing shared paving material must already be available')

    probes = verify_current_floor(plan)
    mesh = import_mesh(mesh_file, report, plan, material)
    actor = place_actor(mesh, unreal.Vector(*report['actor_origin_cm']))
    asset_package = mesh.get_package().get_name()
    actor_package = actor.get_package()
    if not unreal.EditorAssetLibrary.save_asset(asset_package, only_if_is_dirty=False):
        raise RuntimeError(f'Could not save {asset_package}')
    if not unreal.EditorLoadingAndSavingUtils.save_packages([actor_package], only_dirty=False):
        raise RuntimeError(f'Could not save {actor_package.get_name()}')
    packages = [asset_package, actor_package.get_name()]
    if unreal.MultiUserClientStatics.get_multi_user_connection_status_detail() == unreal.MultiUserConnectionStatus.CONNECTED:
        unreal.MultiUserClientStatics.persist_specified_packages([unreal.Name(path) for path in packages])
    return {'packages': packages, 'actor': actor.get_actor_label(), 'material': material.get_path_name(), 'checked_floor_probes': probes}
