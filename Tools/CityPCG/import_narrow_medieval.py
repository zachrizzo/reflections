"""Import the narrow timber Cellarer mesh using existing medieval kit materials."""

import json
from pathlib import Path

from import_facade_kit import check_type, import_options, new_import, source_path, verify_mesh
from import_medieval_kit import ART_DIR, DESTINATION, opening_world


NAME = 'SM_GLMedieval_Narrow_Cellarer'
PACKAGE = f'{DESTINATION}/{NAME}'


def run():
    import unreal

    opening_world(unreal)
    root = Path(unreal.Paths.project_dir()).resolve()
    art = (root / ART_DIR / 'Narrow').resolve()
    recipe = json.loads((art / 'narrow_kit.json').read_text(encoding='utf-8'))
    spec = recipe['meshes'][NAME]
    source = source_path(art, spec['fbx'], '.fbx')
    editor = unreal.EditorAssetLibrary
    materials = {}
    for slot in spec['materials']:
        if not slot.startswith('M_GLMedieval_'):
            raise RuntimeError(f'Unexpected Cellarer material slot: {slot}')
        asset = editor.load_asset(f'{DESTINATION}/{slot}')
        materials[slot] = check_type(asset, unreal.MaterialInterface, slot, DESTINATION)
    created = not editor.does_asset_exist(PACKAGE)
    if created:
        task = new_import(unreal, source, import_options(unreal), DESTINATION)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh = check_type(editor.load_asset(PACKAGE), unreal.StaticMesh, NAME, DESTINATION)
    mesh_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    bounds = verify_mesh(mesh, spec, mesh_editor)
    slots = [str(slot.get_editor_property('material_slot_name'))
             for slot in mesh.get_editor_property('static_materials')]
    if len(slots) != len(spec['materials']) or set(slots) != set(spec['materials']):
        raise RuntimeError(f'Unexpected Cellarer material slots: {slots}')
    if created:
        for index, name in enumerate(slots):
            mesh.set_material(index, materials[name])
    assigned = [slot.get_editor_property('material_interface').get_package().get_name()
                for slot in mesh.get_editor_property('static_materials')]
    if assigned != [f'{DESTINATION}/{slot}' for slot in slots]:
        raise RuntimeError(f'Unexpected Cellarer material assignments: {assigned}')

    opening_world(unreal)
    if created:
        if not unreal.EditorLoadingAndSavingUtils.save_packages([mesh.get_package()], only_dirty=False):
            raise RuntimeError(f'Could not save {PACKAGE}')
        multi_user = unreal.MultiUserClientStatics
        if multi_user.get_multi_user_connection_status_detail() == unreal.MultiUserConnectionStatus.CONNECTED:
            multi_user.persist_specified_packages([PACKAGE])
        if not (root / 'Content' / (PACKAGE.removeprefix('/Game/') + '.uasset')).is_file():
            raise RuntimeError(f'Expected saved file for {PACKAGE}')
    return {'path': PACKAGE, 'saved': created, 'bounds_cm': bounds, 'materials': assigned,
            'lod0_triangles': mesh.get_num_triangles(0), 'uv_channels': mesh_editor.get_num_uv_channels(mesh, 0),
            'simple_collision': mesh_editor.get_simple_collision_count(mesh)}
