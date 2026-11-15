"""Apply the intro street's supported paving and furniture in Unreal Editor.

Run through the live Unreal Python tool. Saves/persists only this pass's meshes
and newly created World Partition actors. All measurements are in UE cm.
"""

from pathlib import Path

import unreal


LEVEL = '/Game/GrayLondon/Maps/GrayLondon_Geodata'
DESTINATION = '/Game/GrayLondon/CityDetailPilot/StreetFinish/Dressing'
ACTOR_FOLDER = 'CityDetailPilot/StreetFinish/Dressing'
ACTOR_PREFIX = 'CityDetailPilot_Dressing_'
SOURCE = Path(unreal.Paths.project_dir()) / 'ArtDirection/CityDetailPilot/Source'
PAVING = {
    'West': (329225, 31671, 10),
    'East': (330199, 31815, 28),
}
HERITAGE_LAMP = ('/Game/GrayLondon/Geodata/Props/street_lamp_01_1k/'
                 'StaticMeshes/SM_HeritageStreetLamp')
FURNITURE = (
    ('LampWest', HERITAGE_LAMP, (329278, 31485, 11.2), 81.0),
    ('LampEast', HERITAGE_LAMP, (330379, 32395, 29.2), 81.0),
    ('BenchEast', '/Game/GrayLondon/Geodata/Props/StreetFurniture/GrayLondonBench',
     (330400, 32235, 29.2), 81.0),
    ('CycleHoop1', '/Game/GrayLondon/Geodata/Props/CycleStand/GenericCycleStand',
     (330242, 31130, 29.2), -9.0),
    ('CycleHoop2', '/Game/GrayLondon/Geodata/Props/CycleStand/GenericCycleStand',
     (330252, 31205, 29.2), -9.0),
)


def checked_asset(path, asset_class):
    asset = unreal.load_asset(path, asset_class)
    if not isinstance(asset, asset_class):
        raise RuntimeError(f'Expected {asset_class.__name__} at {path}')
    return asset


def import_paving(side):
    name = f'SM_GL_IntroPaving_{side}'
    path = f'{DESTINATION}/{name}'
    existing = unreal.EditorAssetLibrary.does_asset_exist(path)
    if existing:
        return checked_asset(path, unreal.StaticMesh)

    settings = unreal.FbxImportUI()
    settings.set_editor_properties({
        'import_mesh': True,
        'import_as_skeletal': False,
        'import_materials': False,
        'import_textures': False,
        'mesh_type_to_import': unreal.FBXImportType.FBXIT_STATIC_MESH,
        'automated_import_should_detect_type': False,
    })
    settings.static_mesh_import_data.set_editor_properties({
        'auto_generate_collision': False,
        'generate_lightmap_u_vs': False,
    })
    task = unreal.AssetImportTask()
    task.set_editor_properties({
        'filename': str((SOURCE / f'{name}.fbx').resolve()),
        'destination_path': DESTINATION,
        'destination_name': name,
        'automated': True,
        'replace_existing': False,
        'save': False,
        'options': settings,
    })
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh = checked_asset(path, unreal.StaticMesh)
    materials = {
        'GL_Flagstones': '/Game/GrayLondon/Geodata/PedestrianPaving/M_GrayLondonStonePaving',
        'GL_Kerb': '/Game/GrayLondon/Geodata/Materials/M_OSM_Pavement',
    }
    for i, slot in enumerate(mesh.get_editor_property('static_materials')):
        role = str(slot.get_editor_property('material_slot_name'))
        mesh.set_material(i, checked_asset(materials.pop(role), unreal.MaterialInterface))
    if materials:
        raise RuntimeError(f'Unmapped paving materials: {list(materials)}')
    return mesh


def trace_floor(world, x, y, ignore):
    hit = unreal.SystemLibrary.line_trace_single(
        world, unreal.Vector(x, y, 160), unreal.Vector(x, y, -50),
        unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, ignore, unreal.DrawDebugTrace.NONE,
    )
    return hit.to_tuple()[4].z if hit else None


def label(actor, name):
    actor.set_actor_label(ACTOR_PREFIX + name)
    actor.set_folder_path(ACTOR_FOLDER)
    return actor


def place_mesh(subsystem, name, mesh, position, yaw):
    placed = subsystem.spawn_actor_from_object(mesh, unreal.Vector(*position), unreal.Rotator(0, 0, yaw))
    actor = label(placed, name)
    component = actor.get_components_by_class(unreal.StaticMeshComponent)[0]
    actor.set_actor_enable_collision(False)
    component.set_collision_profile_name('NoCollision')
    component.set_editor_property('can_ever_affect_navigation', False)
    return actor


def place_practical(subsystem):
    location = unreal.Vector(329278, 31485, 365)
    actor = label(subsystem.spawn_actor_from_class(unreal.PointLight, location), 'LampWestWarmGlow')
    component = actor.get_components_by_class(unreal.PointLightComponent)[0]
    component.set_mobility(unreal.ComponentMobility.MOVABLE)
    component.set_editor_properties({
        'intensity_units': unreal.LightUnits.LUMENS,
        'intensity': 28.0,
        'attenuation_radius': 245.0,
        'use_temperature': True,
        'temperature': 2800.0,
        'source_radius': 8.0,
        'cast_shadows': False,
    })
    return actor


def run():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if not world or world.get_path_name().split('.')[0] != LEVEL:
        raise RuntimeError('Open the Gray London editor world before placing street dressing.')
    descs = unreal.WorldPartitionBlueprintLibrary.get_actor_descs() or []
    if any(str(desc.get_editor_property('label')).startswith(ACTOR_PREFIX) for desc in descs):
        raise RuntimeError('Dressing actors already exist. Review and update them in place.')

    ignore = [actor for actor in subsystem.get_all_level_actors()
              if actor.get_actor_label().startswith('CityDetailPilot_')]
    for name, _, (x, y, z), _ in FURNITURE:
        support = trace_floor(world, x, y, ignore)
        if support is None or abs(support - (z - 1.2)) > 0.4:
            raise RuntimeError(f'{name} lost its traced support at {(x, y)}: {support}')
    support_points = (
        (329172, 31500, 10), (329295, 31500, 10),
        (329240, 31900, 10), (329364, 31900, 10),
        (330286, 31300, 28), (330180, 31300, 28),
        (330419, 32200, 28), (330302, 32200, 28),
    )
    for x, y, expected in support_points:
        support = trace_floor(world, x, y, ignore)
        if support is None or abs(support - expected) > 0.4:
            raise RuntimeError(f'Paving lost its support at {(x, y)}: {support}')

    furnishings = [(name, checked_asset(path, unreal.StaticMesh), position, yaw)
                   for name, path, position, yaw in FURNITURE]
    meshes = [(side, import_paving(side), position) for side, position in PAVING.items()]
    with unreal.ScopedEditorTransaction('Dress Great Tower Street intro'):
        actors = [place_mesh(subsystem, f'Paving{side}', mesh, pos, 0)
                  for side, mesh, pos in meshes]
        actors += [place_mesh(subsystem, *spec) for spec in furnishings]
        actors.append(place_practical(subsystem))

    packages = [mesh.get_package() for _, mesh, _ in meshes]
    for actor in actors:
        package = actor.get_package()
        if not str(package.get_path_name()).startswith('/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/'):
            raise RuntimeError(f'Unexpected external package for {actor.get_actor_label()}: {package}')
        packages.append(package)
    paths = [package.get_path_name() for package in packages]
    if not unreal.EditorLoadingAndSavingUtils.save_packages(packages, False):
        raise RuntimeError(f'Failed to save one or more specified packages: {paths}')
    status = unreal.MultiUserClientStatics.get_multi_user_connection_status_detail()
    if status == unreal.MultiUserConnectionStatus.CONNECTED:
        unreal.MultiUserClientStatics.persist_specified_packages(paths)
    return {
        'saved_packages': paths,
        'actors': [(actor.get_actor_label(), actor.get_actor_location().export_text()) for actor in actors],
        'paving_triangles': {side: mesh.get_num_triangles(0) for side, mesh, _ in meshes},
    }
