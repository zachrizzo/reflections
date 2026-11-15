"""Import, place and persist the Great Tower Street signs in the Unreal Editor."""

from pathlib import Path

import unreal


ROOT = Path(__file__).resolve().parent
DESTINATION = '/Game/GrayLondon/CityDetailPilot/StreetFinish/Signs'
LEVEL = '/Game/GrayLondon/Maps/GrayLondon_Geodata'
ACTOR_PACKAGE_PREFIX = '/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/'
MESH_NAME = 'SM_GL_Fascia'
SIGNS = (
    ('CityDetailPilot_1_Bookshop', 'Books', 'LamplightBooks'),
    ('CityDetailPilot_3_Provisions', 'Provisions', 'MarkLaneProvisions'),
    ('CityDetailPilot_4_Bookshop', 'Lantern', 'LanternRoom'),
)
TOWNHOUSE = 'CityDetailPilot_2_Townhouse'


def load_or_import(source, settings=None):
    path = f'{DESTINATION}/{source.stem}'
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        return unreal.EditorAssetLibrary.load_asset(path)
    task = unreal.AssetImportTask()
    task.filename = str(source)
    task.destination_path = DESTINATION
    task.automated = True
    task.save = False
    if settings is not None:
        task.options = settings
        task.factory = unreal.FbxFactory()
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if asset is None:
        raise RuntimeError(f'Import failed for {source.name}')
    return asset


def asset_or_create(name, asset_class, factory):
    path = f'{DESTINATION}/{name}'
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        return unreal.EditorAssetLibrary.load_asset(path), False
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    asset = tools.create_asset(name, DESTINATION, asset_class, factory)
    if asset is None:
        raise RuntimeError(f'Could not create {path}')
    return asset, True


def create_materials(textures):
    parent, created = asset_or_create('M_GL_Fascia', unreal.Material, unreal.MaterialFactoryNew())
    edit = unreal.MaterialEditingLibrary
    if created:
        texture = edit.create_material_expression(parent, unreal.MaterialExpressionTextureSampleParameter2D, -560, -120)
        texture.set_editor_property('parameter_name', 'SignArtwork')
        texture.set_editor_property('texture', textures['Books'])
        gloss = edit.create_material_expression(parent, unreal.MaterialExpressionConstant, -260, 90)
        gloss.set_editor_property('r', 0.74)
        legibility = edit.create_material_expression(parent, unreal.MaterialExpressionMultiply, -280, 250)
        legibility.set_editor_property('const_b', 0.028)
        connections = [
            edit.connect_material_property(texture, 'RGB', unreal.MaterialProperty.MP_BASE_COLOR),
            edit.connect_material_property(gloss, '', unreal.MaterialProperty.MP_ROUGHNESS),
            edit.connect_material_expressions(texture, 'RGB', legibility, 'A'),
            edit.connect_material_property(legibility, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR),
        ]
        if not all(connections):
            raise RuntimeError(f'Unable to build the fascia material graph: {connections}')
        errors = edit.recompile_material(parent)
        if errors:
            raise RuntimeError(f'Fascia material failed to compile: {errors}')

    instances = {}
    for identifier, artwork in textures.items():
        instance, _ = asset_or_create(f'MI_GL_Fascia_{identifier}', unreal.MaterialInstanceConstant,
                                      unreal.MaterialInstanceConstantFactoryNew())
        edit.set_material_instance_parent(instance, parent)
        if not edit.set_material_instance_texture_parameter_value(instance, 'SignArtwork', artwork):
            raise RuntimeError(f'Unable to assign artwork for {identifier}')
        instances[identifier] = instance
    return parent, instances


def import_assets():
    fbx_settings = unreal.FbxImportUI()
    fbx_settings.import_mesh = True
    fbx_settings.import_as_skeletal = False
    fbx_settings.import_materials = False
    fbx_settings.import_textures = False
    fbx_settings.static_mesh_import_data.auto_generate_collision = False
    fbx_settings.static_mesh_import_data.generate_lightmap_u_vs = True
    mesh = load_or_import(ROOT / 'Source' / f'{MESH_NAME}.fbx', fbx_settings)
    textures = {}
    for _, identifier, _ in SIGNS:
        texture = load_or_import(ROOT / 'Textures' / f'T_GL_Fascia_{identifier}.png')
        texture.set_editor_property('address_x', unreal.TextureAddress.TA_CLAMP)
        texture.set_editor_property('address_y', unreal.TextureAddress.TA_CLAMP)
        textures[identifier] = texture

    material, instances = create_materials(textures)
    mesh.set_material(0, instances['Books'])
    editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    bounds = mesh.get_bounds()
    width, height, depth = 2 * bounds.box_extent.y, 2 * bounds.box_extent.z, 2 * bounds.box_extent.x
    if not (abs(width - 308) < 0.5 and abs(height - 27.2) < 0.5 and abs(depth - 1.8) < 0.2):
        raise RuntimeError(f'Wrong fascia dimensions in cm: {width}, {height}, {depth}')
    if mesh.get_num_sections(0) != 1 or editor.get_num_uv_channels(mesh, 0) < 1:
        raise RuntimeError('Fascia must have one material section and a UV channel')
    if editor.get_simple_collision_count(mesh):
        editor.remove_collisions(mesh)
    assets = [*textures.values(), material, *instances.values(), mesh]
    return mesh, instances, assets


def disable_collision(actor):
    actor.modify()
    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    component.modify()
    component.set_collision_profile_name('NoCollision')
    actor.set_actor_enable_collision(False)
    if str(component.get_collision_profile_name()) != 'NoCollision' or actor.get_actor_enable_collision():
        raise RuntimeError(f'Collision remains enabled on {actor.get_actor_label()}')


def apply_actors(mesh, instances):
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world.get_path_name().split('.')[0] != LEVEL:
        raise RuntimeError(f'Open {LEVEL} before placing the fascia panels')
    editor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = {actor.get_actor_label(): actor for actor in editor.get_all_level_actors()}
    originals = [actors[name] for name in (*[entry[0] for entry in SIGNS], TOWNHOUSE)]
    original_selection = editor.get_selected_level_actors()
    placed = []
    try:
        with unreal.ScopedEditorTransaction('Finish Gray London storefront fascia panels'):
            for actor in originals:
                disable_collision(actor)
            for original_label, identifier, suffix in SIGNS:
                original = actors[original_label]
                label = f'CityDetailPilot_Fascia_{suffix}'
                position = unreal.MathLibrary.transform_location(original.get_actor_transform(), unreal.Vector(37.1, 0, 272))
                actor = actors.get(label)
                if actor is None:
                    actor = editor.spawn_actor_from_object(mesh, position, original.get_actor_rotation())
                    if actor is None:
                        raise RuntimeError(f'Could not place {label}')
                    actor.set_actor_label(label)
                    actor.set_folder_path('CityDetailPilot/StreetFinish/Fascias')
                if not actor.get_package().get_name().startswith(ACTOR_PACKAGE_PREFIX):
                    raise RuntimeError(f'{label} must be assigned a Gray London external actor package')
                disable_collision(actor)
                component = actor.get_component_by_class(unreal.StaticMeshComponent)
                component.set_material(0, instances[identifier])
                placed.append(actor)
    finally:
        editor.set_selected_level_actors(original_selection)

    return originals + placed


def save_packages(assets, actors):
    asset_paths = [asset.get_package().get_name() for asset in assets]
    actor_packages = [actor.get_package() for actor in actors]
    actor_paths = [package.get_name() for package in actor_packages]
    if not all(path.startswith(f'{DESTINATION}/') for path in asset_paths):
        raise RuntimeError(f'Unexpected fascia assets: {asset_paths}')
    if len(set(actor_paths)) != len(actors) or not all(path.startswith(ACTOR_PACKAGE_PREFIX) for path in actor_paths):
        raise RuntimeError(f'Unexpected fascia actor packages: {actor_paths}')
    for path in asset_paths:
        if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            raise RuntimeError(f'Could not save {path}')
    if not unreal.EditorLoadingAndSavingUtils.save_packages(actor_packages, only_dirty=False):
        raise RuntimeError(f'Could not save fascia actor packages: {actor_paths}')
    packages = [*asset_paths, *actor_paths]
    if unreal.MultiUserClientStatics.get_multi_user_connection_status_detail() == unreal.MultiUserConnectionStatus.CONNECTED:
        unreal.MultiUserClientStatics.persist_specified_packages(packages)
    return packages


def main():
    mesh, instances, assets = import_assets()
    actors = apply_actors(mesh, instances)
    return {'assets': save_packages(assets, actors),
            'actors': [actor.get_actor_label() for actor in actors]}


if __name__ == '__main__':
    unreal.log(str(main()))
