"""Import the merchant hall assets and reuse the existing medieval kit materials."""

import json
from pathlib import Path

from import_facade_kit import check_type, import_options, make_material, new_import, source_path, verify_mesh
from import_medieval_kit import ART_DIR, DESTINATION, opening_world


MESH_PREFIX = 'SM_GLMedieval_Guildhall_'
MATERIALS = {'M_GLMedieval_GuildRubble', 'M_GLMedieval_GuildAshlar', 'M_GLMedieval_GuildDressed'}
SHARED = {'M_GLMedieval_ClayTile', 'M_GLMedieval_Oak', 'M_GLMedieval_WeatheredOak',
          'M_GLMedieval_LeadedGlass', 'M_GLMedieval_Lead', 'M_GLMedieval_Interior'}
MODULES = ('Portal', 'WestWing', 'EastWing', 'Frontage')


def run(modules=MODULES):
    import unreal

    opening_world(unreal)
    if not modules or any(module not in MODULES for module in modules):
        raise ValueError(f'Unknown guildhall modules: {modules}')
    root = Path(unreal.Paths.project_dir()).resolve()
    art = (root / ART_DIR / 'Guildhall').resolve()
    recipe = json.loads((art / 'guildhall_kit.json').read_text(encoding='utf-8'))
    selected = {MESH_PREFIX + module: recipe['meshes'][MESH_PREFIX + module] for module in modules}
    mesh_sources = {name: source_path(art, spec['fbx'], '.fbx') for name, spec in selected.items()}
    roles = {role for spec in selected.values() for role in spec['materials']}
    if roles - MATERIALS - SHARED:
        raise ValueError(f'Unknown guildhall material slots: {sorted(roles - MATERIALS - SHARED)}')
    texture_sources = {role: source_path(art, recipe['materials'][role]['texture'], '.png')
                       for role in roles & MATERIALS if recipe['materials'][role]['texture']}
    allowed = {*selected, *(roles & MATERIALS), *(path.stem for path in texture_sources.values())}
    editor = unreal.EditorAssetLibrary
    tools = unreal.AssetToolsHelpers.get_asset_tools()

    def load(name, asset_type):
        asset = editor.load_asset(f'{DESTINATION}/{name}')
        return check_type(asset, asset_type, name, DESTINATION)

    def missing(name):
        return not editor.does_asset_exist(f'{DESTINATION}/{name}')

    materials = {role: load(role, unreal.MaterialInterface) for role in sorted(roles & SHARED)}
    new_textures = {path.stem: path for path in texture_sources.values() if missing(path.stem)}
    if new_textures:
        tools.import_asset_tasks([new_import(unreal, path, destination=DESTINATION)
                                  for path in new_textures.values()])
    textures = {role: load(path.stem, unreal.Texture2D) for role, path in texture_sources.items()}
    created = [asset for asset in textures.values() if asset.get_name() in new_textures]
    for role in sorted(roles & MATERIALS):
        if missing(role):
            spec = recipe['materials'][role]
            materials[role] = make_material(unreal, tools, role, spec, textures.get(role), DESTINATION)
            created.append(materials[role])
        else:
            materials[role] = load(role, unreal.MaterialInterface)

    new_meshes = {name: path for name, path in mesh_sources.items() if missing(name)}
    if new_meshes:
        tools.import_asset_tasks([new_import(unreal, path, import_options(unreal), DESTINATION)
                                  for path in new_meshes.values()])
    mesh_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    report = {}
    for name, spec in selected.items():
        mesh = load(name, unreal.StaticMesh)
        bounds = verify_mesh(mesh, spec, mesh_editor)
        slots = [str(slot.get_editor_property('material_slot_name'))
                 for slot in mesh.get_editor_property('static_materials')]
        if len(slots) != len(spec['materials']) or set(slots) != set(spec['materials']):
            raise RuntimeError(f'Unexpected slot names on {name}: {slots}')
        if name in new_meshes:
            for index, role in enumerate(slots):
                mesh.set_material(index, materials[role])
            created.append(mesh)
        assigned = [slot.get_editor_property('material_interface').get_package().get_name()
                    for slot in mesh.get_editor_property('static_materials')]
        if assigned != [f'{DESTINATION}/{role}' for role in slots]:
            raise RuntimeError(f'Material assignments failed verification on {name}: {assigned}')
        report[name] = {'bounds_cm': bounds, 'lod0_triangles': mesh.get_num_triangles(0),
                        'uv_channels': mesh_editor.get_num_uv_channels(mesh, 0),
                        'material_packages': assigned, 'simple_collision': 0}

    opening_world(unreal)
    packages = [asset.get_package() for asset in created]
    names = sorted(package.get_name() for package in packages)
    if not set(names).issubset({f'{DESTINATION}/{name}' for name in allowed}):
        raise RuntimeError(f'Unexpected package paths: {names}')
    if packages and not unreal.EditorLoadingAndSavingUtils.save_packages(packages, only_dirty=False):
        raise RuntimeError(f'Could not save guildhall packages: {names}')
    multi_user = unreal.MultiUserClientStatics
    if names and multi_user.get_multi_user_connection_status_detail() == unreal.MultiUserConnectionStatus.CONNECTED:
        multi_user.persist_specified_packages(names)
    missing_files = [name for name in names if not (root / 'Content' / (name.removeprefix('/Game/') + '.uasset')).is_file()]
    if missing_files:
        raise RuntimeError(f'Expected saved package files are missing: {missing_files}')
    return {'meshes': report, 'saved_packages': names}
