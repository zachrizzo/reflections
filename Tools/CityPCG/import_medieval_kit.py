"""Import and verify only the new medieval opening kit assets."""

import json
from pathlib import Path

from apply_facade_pcg import LEVEL, MEDIEVAL_DESTINATION
from import_facade_kit import check_type, import_options, make_material, new_import, source_path, verify_mesh

DESTINATION = f"{MEDIEVAL_DESTINATION}/Kit"
ART_DIR = "ArtDirection/CityPCG/MedievalOpening"


def opening_world(unreal):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if editor.get_game_world() or not world or world.get_path_name().split(".")[0] != LEVEL:
        raise RuntimeError(f"Open {LEVEL} in the editor and stop PIE first.")
    return world


def run():
    import unreal

    opening_world(unreal)
    art = (Path(unreal.Paths.project_dir()) / ART_DIR).resolve()
    kit = json.loads((art / "medieval_kit.json").read_text(encoding="utf-8"))
    editor = unreal.EditorAssetLibrary
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    meshes = {name: source_path(art, spec["fbx"], ".fbx") for name, spec in kit["meshes"].items()}
    textures = {name: source_path(art, spec["texture"], ".png")
                for name, spec in kit["materials"].items() if spec["texture"]}
    asset_names = {*meshes, *kit["materials"], *(path.stem for path in textures.values())}
    if not all(name.startswith(("SM_GLMedieval_", "M_GLMedieval_", "T_GLMedieval_")) for name in asset_names):
        raise RuntimeError("The manifest contains a name outside the medieval kit.")
    existing = [name for name in sorted(asset_names) if editor.does_asset_exist(f"{DESTINATION}/{name}")]
    if existing:
        raise RuntimeError(f"The medieval kit importer will not change existing packages: {existing}")

    def load(asset_type, name):
        return check_type(editor.load_asset(f"{DESTINATION}/{name}"), asset_type, name, DESTINATION)

    tools.import_asset_tasks([new_import(unreal, path, destination=DESTINATION) for path in textures.values()])
    imported_textures = {name: load(unreal.Texture2D, path.stem) for name, path in textures.items()}
    materials = {name: make_material(unreal, tools, name, spec, imported_textures.get(name), DESTINATION)
                 for name, spec in kit["materials"].items()}
    tools.import_asset_tasks([new_import(unreal, path, import_options(unreal), DESTINATION) for path in meshes.values()])
    mesh_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    created = [*imported_textures.values(), *materials.values()]
    bounds = {}
    for name, spec in kit["meshes"].items():
        mesh = load(unreal.StaticMesh, name)
        bounds[name] = verify_mesh(mesh, spec, mesh_editor)
        slots = [str(slot.get_editor_property("material_slot_name"))
                 for slot in mesh.get_editor_property("static_materials")]
        if len(slots) != len(spec["materials"]) or set(slots) != set(spec["materials"]):
            raise RuntimeError(f"Unexpected material slots on {name}: {slots}")
        for index, material_name in enumerate(slots):
            mesh.set_material(index, materials[material_name])
        created.append(mesh)
    opening_world(unreal)
    packages = [asset.get_package() for asset in created]
    names = [package.get_name() for package in packages]
    if set(names) != {f"{DESTINATION}/{name}" for name in asset_names}:
        raise RuntimeError(f"Unexpected package names: {names}")
    if not unreal.EditorLoadingAndSavingUtils.save_packages(packages, only_dirty=False):
        raise RuntimeError(f"Could not save the new medieval kit packages: {names}")
    multi_user = unreal.MultiUserClientStatics
    if multi_user.get_multi_user_connection_status_detail() == unreal.MultiUserConnectionStatus.CONNECTED:
        multi_user.persist_specified_packages(names)
    return {"mesh_bounds_cm": bounds, "saved_packages": names}
