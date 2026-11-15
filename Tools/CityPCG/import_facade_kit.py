"""Explicitly import the London kit into its dedicated Unreal content folder.

Run in an idle Gray London editor with `run()` from Unreal Python. The first
batch brings in three styles with base, upper and entrance meshes. Add
`cornice` to `roles` when ready to import the optional fourth module.
"""

import json
from pathlib import Path

from apply_facade_pcg import MESH_ROOT, verify_editor


def package_path(name, destination=MESH_ROOT):
    return f'{destination}/{name}'


def check_type(asset, asset_type, name, destination=MESH_ROOT):
    path = package_path(name, destination)
    if not isinstance(asset, asset_type) or asset.get_package().get_name() != path:
        raise RuntimeError(f'Expected {asset_type.__name__} at {path}.')
    return asset


def new_import(unreal, source, options=None, destination=MESH_ROOT):
    task = unreal.AssetImportTask()
    task.filename = str(source)
    task.destination_path = destination
    task.automated = True
    task.save = False
    task.replace_existing = False
    if options is not None:
        task.factory = unreal.FbxFactory()
        task.options = options
    return task


def source_path(root, relative, suffix):
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.suffix.lower() != suffix:
        raise RuntimeError(f'Invalid kit source: {relative}')
    return path


def make_material(unreal, tools, name, spec, texture, destination=MESH_ROOT):
    asset = check_type(tools.create_asset(name, destination, unreal.Material, unreal.MaterialFactoryNew()),
                       unreal.Material, name, destination)
    asset.set_editor_property('used_with_instanced_static_meshes', True)
    edit = unreal.MaterialEditingLibrary
    if texture is None:
        base = edit.create_material_expression(asset, unreal.MaterialExpressionConstant3Vector, -410, -80)
        base.set_editor_property('constant', unreal.LinearColor(*spec['linear_rgba']))
        output = ''
    else:
        base = edit.create_material_expression(asset, unreal.MaterialExpressionTextureSample, -410, -100)
        base.set_editor_property('texture', texture)
        output = 'RGB'
    if not edit.connect_material_property(base, output, unreal.MaterialProperty.MP_BASE_COLOR):
        raise RuntimeError(f'Unable to connect base color for {name}.')
    for prop, field, y in ((unreal.MaterialProperty.MP_ROUGHNESS, 'roughness', 110),
                           (unreal.MaterialProperty.MP_METALLIC, 'metallic', 230)):
        value = edit.create_material_expression(asset, unreal.MaterialExpressionConstant, -220, y)
        value.set_editor_property('r', spec[field])
        if not edit.connect_material_property(value, '', prop):
            raise RuntimeError(f'Unable to connect {field} for {name}.')
    errors = edit.recompile_material(asset)
    if errors:
        raise RuntimeError(f'Material compilation failed for {name}: {errors}')
    return asset


def import_options(unreal):
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
    return settings


def verify_mesh(mesh, spec, mesh_editor):
    bounds = mesh.get_bounds()
    actual = [tuple(getattr(bounds.origin, axis) + sign * getattr(bounds.box_extent, axis) for axis in 'xyz')
              for sign in (-1, 1)]
    if any(abs(expected - measured) > 1.0 for expected_row, measured_row in zip(
            (spec['min_cm'], spec['max_cm']), actual) for expected, measured in zip(expected_row, measured_row)):
        raise RuntimeError(f'{mesh.get_name()} has incorrect cm bounds: {actual}')
    if mesh.get_num_sections(0) != len(spec['materials']) or mesh_editor.get_num_uv_channels(mesh, 0) < 1:
        raise RuntimeError(f'{mesh.get_name()} has incorrect section or UV counts.')
    if mesh_editor.get_simple_collision_count(mesh):
        raise RuntimeError(f'{mesh.get_name()} unexpectedly has simple collision.')
    return actual


def run(roles=('base', 'upper', 'entrance')):
    import unreal

    verify_editor(unreal)
    root = (Path(unreal.Paths.project_dir()) / 'ArtDirection/CityPCG/Kit').resolve()
    kit = json.loads((root / 'kit_manifest.json').read_text(encoding='utf-8'))
    specs = {spec['mesh']: spec for style in kit['styles'].values()
             for role, spec in style.items() if role in roles}
    if not specs or any(role not in ('base', 'upper', 'entrance', 'cornice') for role in roles):
        raise ValueError(f'Invalid module roles: {roles}')
    editor = unreal.EditorAssetLibrary
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    expected_meshes = {name: source_path(root, spec['fbx'], '.fbx') for name, spec in specs.items()}
    material_specs = {name: kit['materials'][name] for name in sorted(
        {name for spec in specs.values() for name in spec['materials']})}
    expected_textures = {name: source_path(root, spec['texture'], '.png') for name, spec in material_specs.items()
                         if spec['texture'] is not None}
    missing_textures = {path.stem: path for path in expected_textures.values()
                        if not editor.does_asset_exist(package_path(path.stem))}
    if missing_textures:
        tools.import_asset_tasks([new_import(unreal, path) for path in missing_textures.values()])
    textures = {name: check_type(editor.load_asset(package_path(path.stem)), unreal.Texture2D, path.stem)
                for name, path in expected_textures.items()}
    created = [asset for asset in textures.values() if asset.get_name() in missing_textures]
    materials = {}
    for name, spec in material_specs.items():
        if editor.does_asset_exist(package_path(name)):
            materials[name] = check_type(editor.load_asset(package_path(name)), unreal.Material, name)
        else:
            materials[name] = make_material(unreal, tools, name, spec, textures.get(name))
            created.append(materials[name])

    missing_meshes = {name: path for name, path in expected_meshes.items()
                      if not editor.does_asset_exist(package_path(name))}
    if missing_meshes:
        tools.import_asset_tasks([new_import(unreal, path, import_options(unreal))
                                  for path in missing_meshes.values()])
    mesh_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    bounds_report = {}
    for name, spec in specs.items():
        mesh = check_type(editor.load_asset(package_path(name)), unreal.StaticMesh, name)
        bounds_report[name] = verify_mesh(mesh, spec, mesh_editor)
        slots = mesh.get_editor_property('static_materials')
        slot_names = [str(slot.get_editor_property('material_slot_name')) for slot in slots]
        if set(slot_names) != set(spec['materials']) or len(slot_names) != len(spec['materials']):
            raise RuntimeError(f'Unexpected material slots on {name}: {slot_names}')
        if name in missing_meshes:
            for index, material_name in enumerate(slot_names):
                mesh.set_material(index, materials[material_name])
            created.append(mesh)
    verify_editor(unreal)
    packages = list({asset.get_package().get_name(): asset.get_package() for asset in created}.values())
    names = [package.get_name() for package in packages]
    if packages and not unreal.EditorLoadingAndSavingUtils.save_packages(packages, only_dirty=False):
        raise RuntimeError(f'Could not save the new kit packages: {names}')
    multi_user = unreal.MultiUserClientStatics
    if names and multi_user.get_multi_user_connection_status_detail() == unreal.MultiUserConnectionStatus.CONNECTED:
        multi_user.persist_specified_packages(names)
    return {'mesh_bounds_cm': bounds_report, 'saved_packages': names}
