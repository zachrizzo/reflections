"""Export one Gray London tile and its authored frontage mask from saved assets."""

import json
from pathlib import Path

from export_geodata_tiles_unreal import MAP, TILE_NAME, verify_export


def export_inputs(tile_name, output=None):
    import unreal

    if not TILE_NAME.fullmatch(tile_name):
        raise ValueError("Supply one Tile_p00_p00-style name.")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if editor.get_game_world() or not world or world.get_path_name().split(".")[0] != MAP:
        raise RuntimeError(f"Open {MAP} outside PIE before exporting tile data.")
    output = Path(output or (Path(unreal.Paths.project_saved_dir()) / "CityPCG")).resolve()
    output.mkdir(parents=True, exist_ok=True)
    descriptors = {str(desc.get_editor_property("label")): desc
                   for desc in unreal.WorldPartitionBlueprintLibrary.get_actor_descs() or []}
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    deps_options = unreal.AssetRegistryDependencyOptions(
        include_hard_package_references=True, include_soft_package_references=False,
        include_searchable_names=False, include_soft_management_references=False,
        include_hard_management_references=False,
    )
    options = unreal.GLTFExportOptions()
    options.set_editor_properties({
        "bake_material_inputs": unreal.GLTFMaterialBakeMode.DISABLED,
        "export_source_model": True,
        "export_uniform_scale": .01,
    })
    report = {}
    for role, expected_actor, folder in (
        ("tile", f"OSM {tile_name}", "Tiles"),
        ("overlay", f"Anonymous shops {tile_name}", "AnonymousCommercial"),
    ):
        if expected_actor not in descriptors:
            raise RuntimeError(f"Cannot verify archetype of {expected_actor}.")
        desc = descriptors[expected_actor]
        actor_package = str(desc.get_editor_property("actor_package"))
        expected_package = f"/Game/GrayLondon/Geodata/{folder}/{tile_name}"
        refs = {str(path) for path in registry.get_dependencies(actor_package, deps_options) or []}
        if expected_package not in refs:
            raise RuntimeError(f"{expected_actor} does not reference {expected_package}.")
        mesh = unreal.EditorAssetLibrary.load_asset(expected_package)
        if not isinstance(mesh, unreal.StaticMesh):
            raise RuntimeError(f"Missing static mesh {expected_package}.")
        bounds = desc.get_editor_property("bounds")
        center = (bounds.min + bounds.max) * .5
        extent = (bounds.max - bounds.min) * .5
        mesh_bounds = mesh.get_bounds()
        if max(abs(getattr(extent - mesh_bounds.box_extent, axis)) for axis in "xyz") > .09:
            raise RuntimeError(f"Actor and package bounds differ on {expected_actor}; inspect live transform.")
        origin = center - mesh_bounds.origin
        directory = output / "MedievalSurvey"
        directory.mkdir(exist_ok=True)
        path = directory / (f"{tile_name}.glb" if role == "tile" else f"AnonymousShops_{tile_name}.glb")
        slots = [str(slot.get_editor_property("material_slot_name"))
                 for slot in mesh.get_editor_property("static_materials")]
        if role == "tile" and (slots.count("GL_Facade") != 1 or slots.count("GL_Road") != 1):
            raise RuntimeError(f"Inspect facade and road slots on {expected_actor}.")
        messages = unreal.GLTFExporter.export_to_gltf(mesh, str(path), options, set())
        if messages is None or messages.get_editor_property("errors"):
            raise RuntimeError(f"Could not export {expected_actor}: {messages}")
        counts = verify_export(path, slots, mesh)
        report[role] = {
            "tile": tile_name,
            "package": expected_package,
            "actor_package": actor_package,
            "glb": path.name,
            "origin_m": [round(getattr(origin, axis) / 100, 5) for axis in "xyz"],
            "primitives": dict(zip(slots, counts)),
        }
        if role == "tile":
            report[role].update(primitive=slots.index("GL_Facade"), road_primitive=slots.index("GL_Road"))
    metadata = directory / f"{tile_name}.assets.json"
    metadata.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
