"""Import and mount the wheatsheaf sign on the east opening shopfront in Unreal."""

import json
from pathlib import Path

import unreal


ROOT = Path(unreal.Paths.project_dir()) / 'ArtDirection/CityPCG/MedievalOpening'
LEVEL = '/Game/GrayLondon/Maps/GrayLondon_Geodata'
EXTERNAL = '/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/'
KIT = '/Game/GrayLondon/MedievalOpening/Kit'
DESTINATION = '/Game/GrayLondon/MedievalOpening/Signs'
HOST_LABEL = 'MedievalOpening_East_01_Chandler'
SIGN_LABEL = 'MedievalOpening_Sign_Wheatsheaf'
# Eye center, in shopfront-local cm. The hook extends back into the lintel.
MOUNT = (48.0, 54.0, 247.8)


def import_asset(source, asset_class, fbx_options=None):
    asset_path = f'{DESTINATION}/{source.stem}'
    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        return unreal.load_asset(asset_path, asset_class)
    task = unreal.AssetImportTask()
    task.set_editor_properties({'filename': str(source.resolve()), 'automated': True,
                                'destination_path': DESTINATION, 'destination_name': source.stem,
                                'replace_existing': False, 'save': False})
    if fbx_options is not None:
        task.options = fbx_options
        task.factory = unreal.FbxFactory()
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    asset = unreal.load_asset(asset_path, asset_class)
    if not isinstance(asset, asset_class):
        raise RuntimeError(f'Import did not create {asset_path}')
    return asset


def face_material(texture):
    name = 'M_GLMedieval_Wheatsheaf'
    asset_path = f'{DESTINATION}/{name}'
    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        return unreal.load_asset(asset_path, unreal.Material)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    material = tools.create_asset(name, DESTINATION, unreal.Material, unreal.MaterialFactoryNew())
    edit = unreal.MaterialEditingLibrary
    color = edit.create_material_expression(material, unreal.MaterialExpressionTextureSample, -520, -110)
    color.texture = texture
    roughness = edit.create_material_expression(material, unreal.MaterialExpressionConstant, -310, 70)
    roughness.set_editor_property('r', 0.84)
    if not edit.connect_material_property(color, 'RGB', unreal.MaterialProperty.MP_BASE_COLOR):
        raise RuntimeError('Could not connect wheatsheaf paint texture')
    if not edit.connect_material_property(roughness, '', unreal.MaterialProperty.MP_ROUGHNESS):
        raise RuntimeError('Could not connect wheatsheaf roughness')
    errors = edit.recompile_material(material)
    if errors:
        raise RuntimeError(f'Wheatsheaf material failed to compile: {errors}')
    return material


def build_assets():
    recipe = json.loads((ROOT / 'wheatsheaf_kit.json').read_text(encoding='utf-8'))
    fbx = unreal.FbxImportUI()
    fbx.set_editor_properties({'import_mesh': True, 'import_as_skeletal': False,
                               'import_materials': False, 'import_textures': False,
                               'mesh_type_to_import': unreal.FBXImportType.FBXIT_STATIC_MESH,
                               'automated_import_should_detect_type': False})
    fbx.static_mesh_import_data.set_editor_properties({'auto_generate_collision': False,
                                                       'generate_lightmap_u_vs': False})
    mesh = import_asset(ROOT / recipe['fbx'], unreal.StaticMesh, fbx)
    texture = import_asset(ROOT / recipe['texture'], unreal.Texture2D)
    texture.set_editor_property('address_x', unreal.TextureAddress.TA_CLAMP)
    texture.set_editor_property('address_y', unreal.TextureAddress.TA_CLAMP)
    material = face_material(texture)
    slots = {'M_GLMedieval_Wheatsheaf': material}
    for shared in ('M_GLMedieval_Oak', 'M_GLMedieval_Lead'):
        slots[shared] = unreal.load_asset(f'{KIT}/{shared}', unreal.MaterialInterface)
        if not slots[shared]:
            raise RuntimeError(f'Missing shared kit material {shared}')
    imported_slots = [str(slot.get_editor_property('material_slot_name'))
                      for slot in mesh.get_editor_property('static_materials')]
    if set(imported_slots) != set(slots):
        raise RuntimeError(f'Unexpected wheatsheaf material slots: {imported_slots}')
    for i, name in enumerate(imported_slots):
        mesh.set_material(i, slots[name])

    bounds = mesh.get_bounds()
    mesh_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    extent, center = bounds.box_extent, bounds.origin
    for component, low, high in zip('xyz', recipe['min_cm'], recipe['max_cm']):
        mid, half = getattr(center, component), getattr(extent, component)
        if abs(mid - half - low) > .15 or abs(mid + half - high) > .15:
            raise RuntimeError(f'Wheatsheaf {component} bounds drifted from the eye-centered source')
    if mesh_editor.get_num_uv_channels(mesh, 0) < 1 or mesh.get_num_sections(0) != 3:
        raise RuntimeError('Wheatsheaf requires UV0 and all three surface sections')
    if mesh_editor.get_simple_collision_count(mesh):
        raise RuntimeError('Wheatsheaf imported with unexpected collision')
    return mesh, [mesh, material, texture]


def find_actors(editor):
    relevant = {HOST_LABEL, SIGN_LABEL}
    actors = {actor.get_actor_label(): actor for actor in editor.get_all_level_actors()
              if actor.get_actor_label() in relevant}
    descriptors = [desc for desc in unreal.WorldPartitionBlueprintLibrary.get_actor_descs() or []
                   if str(desc.get_editor_property('label')) in relevant - actors.keys()]
    if descriptors:
        unreal.WorldPartitionBlueprintLibrary.load_actors([desc.get_editor_property('guid') for desc in descriptors])
        actors.update({actor.get_actor_label(): actor for actor in editor.get_all_level_actors()
                       if actor.get_actor_label() in relevant})
    if HOST_LABEL not in actors:
        raise RuntimeError(f'Could not load shopfront {HOST_LABEL}')
    return actors[HOST_LABEL], actors.get(SIGN_LABEL)


def place(editor, host, existing, mesh):
    position = unreal.MathLibrary.transform_location(host.get_actor_transform(), unreal.Vector(*MOUNT))
    rotation = host.get_actor_rotation()
    selection = editor.get_selected_level_actors()
    try:
        with unreal.ScopedEditorTransaction('Hang wheatsheaf relief on the London opening shopfront'):
            sign = existing or editor.spawn_actor_from_object(mesh, position, rotation)
            if sign is None:
                raise RuntimeError('Could not spawn wheatsheaf sign')
            sign.modify()
            sign.set_actor_label(SIGN_LABEL)
            sign.set_folder_path('MedievalOpening/Signs')
            sign.set_actor_enable_collision(False)
            component = sign.get_component_by_class(unreal.StaticMeshComponent)
            component.modify()
            component.set_collision_profile_name('NoCollision')
            component.set_editor_property('can_ever_affect_navigation', False)
    finally:
        editor.set_selected_level_actors(selection)
    if sign.get_actor_enable_collision() or str(component.get_collision_profile_name()) != 'NoCollision':
        raise RuntimeError('Wheatsheaf should be cosmetic and noncolliding')
    return sign


def run():
    if unreal.EditorLevelLibrary.get_pie_worlds(True):
        raise RuntimeError('End the active PIE session before mounting the sign')
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if not world or world.get_path_name().split('.')[0] != LEVEL:
        raise RuntimeError(f'Open {LEVEL} before mounting the sign')
    editor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    host, existing = find_actors(editor)
    mesh, assets = build_assets()
    sign = place(editor, host, existing, mesh)
    asset_packages = [item.get_package() for item in assets]
    if not all(item.get_name().startswith(f'{DESTINATION}/') for item in asset_packages):
        raise RuntimeError('Unexpected wheatsheaf asset package')
    actor_package = sign.get_package()
    if not actor_package.get_name().startswith(EXTERNAL):
        raise RuntimeError('Wheatsheaf needs its own World Partition actor package')
    packages = [*asset_packages, actor_package]
    paths = [item.get_name() for item in packages]
    if not unreal.EditorLoadingAndSavingUtils.save_packages(packages, False):
        raise RuntimeError(f'Could not save sign packages: {paths}')
    if unreal.MultiUserClientStatics.get_multi_user_connection_status_detail() == unreal.MultiUserConnectionStatus.CONNECTED:
        unreal.MultiUserClientStatics.persist_specified_packages(paths)
    return {'actor': sign.get_actor_label(), 'location': sign.get_actor_location().export_text(),
            'triangles': mesh.get_num_triangles(0), 'packages': paths}
