"""Export explicitly selected, loaded Gray London tile meshes to Saved/CityPCG.

Run in Unreal Python and call export_tiles(["Tile_p03_p00"]). This reads the
actual component transforms and exports source geometry with material baking
disabled. No level, actor, asset or editor settings are changed or saved.
"""

import json
from pathlib import Path
import re
import struct

import unreal


MAP = "/Game/GrayLondon/Maps/GrayLondon_Geodata"
TILE_NAME = re.compile(r"Tile_[pm]\d{2}_[pm]\d{2}")


def verify_export(path, slots, mesh):
    with path.open("rb") as stream:
        magic, version, _, size, kind = struct.unpack("<4sIII4s", stream.read(20))
        if (magic, version, kind) != (b"glTF", 2, b"JSON"):
            raise RuntimeError(f"{path.name}: expected GLB v2.")
        document = json.loads(stream.read(size))
    if document["nodes"] != [{"mesh": 0}]:
        raise RuntimeError(f"{path.name}: expected the tile's identity mesh node.")
    primitives = document["meshes"][0]["primitives"]
    if len(primitives) != len(slots) or len(primitives) != mesh.get_num_sections(0):
        raise RuntimeError(f"{path.name}: GLB primitives do not match Unreal's LOD0 sections and slots.")
    counts = [document["accessors"][primitive["indices"]]["count"] // 3
              for primitive in primitives]
    if sum(counts) != mesh.get_num_triangles(0):
        raise RuntimeError(f"{path.name}: GLB triangle count differs from the loaded tile.")
    return counts


def export_tiles(names, output=None):
    names = list(dict.fromkeys(names))
    if not names or any(not TILE_NAME.fullmatch(name) for name in names):
        raise ValueError("Supply explicit Tile_p00_p00-style names.")
    output = Path(output or (Path(unreal.Paths.project_saved_dir()) / "CityPCG")).resolve()
    output.mkdir(parents=True, exist_ok=True)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world():
        raise RuntimeError("Stop Play In Editor before exporting city tiles.")
    world = editor.get_editor_world()
    if not world or world.get_path_name().split(".")[0] != MAP:
        raise RuntimeError(f"Open {MAP} before exporting city tiles.")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = {actor.get_actor_label(): actor for actor in subsystem.get_all_level_actors()}
    missing = [name for name in names if f"OSM {name}" not in actors]
    if missing:
        raise RuntimeError(f"Load these authoritative OSM tile actors first: {missing}")

    options = unreal.GLTFExportOptions()
    options.set_editor_properties({
        "bake_material_inputs": unreal.GLTFMaterialBakeMode.DISABLED,
        "export_source_model": True,
        "export_uniform_scale": .01,  # UE cm to glTF metres.
    })
    results = []
    for name in names:
        actor = actors[f"OSM {name}"]
        components = actor.get_components_by_class(unreal.StaticMeshComponent)
        if len(components) != 1:
            raise RuntimeError(f"{name}: expected one geodata mesh component.")
        component = components[0]
        rotation = component.get_world_rotation()
        scale = component.get_world_scale()
        if any(abs(angle) > 1e-4 for angle in (rotation.pitch, rotation.yaw, rotation.roll)):
            raise RuntimeError(f"{name}: unexpected rotation. The extractor handles translated tiles.")
        if any(abs(axis - 1) > 1e-4 for axis in (scale.x, scale.y, scale.z)):
            raise RuntimeError(f"{name}: unexpected scale. The extractor handles translated tiles.")
        position = component.get_world_location()
        mesh = component.get_editor_property("static_mesh")
        slots = [str(slot.get_editor_property("material_slot_name"))
                 for slot in mesh.get_editor_property("static_materials")]
        if slots.count("GL_Facade") != 1 or slots.count("GL_Road") != 1:
            raise RuntimeError(f"{name}: ordinary facade and road slot mapping requires inspection.")
        path = output / f"{name}.glb"
        messages = unreal.GLTFExporter.export_to_gltf(mesh, str(path), options, set())
        if messages is None or messages.get_editor_property("errors"):
            raise RuntimeError(f"{name}: source geometry export failed: {messages}")
        counts = verify_export(path, slots, mesh)
        metadata = {
            "tile": name,
            "asset": mesh.get_path_name(),
            "actor": actor.get_path_name(),
            "origin_m": [position.x / 100, position.y / 100, position.z / 100],
            "primitive": slots.index("GL_Facade"),
            "road_primitive": slots.index("GL_Road"),
            "primitives": dict(zip(slots, counts)),
            "contains_custom_facade_slots": any(slot not in ("GL_Facade", "GL_Roof", "GL_Road", "GL_Park", "GL_Water")
                                                for slot in slots),
        }
        path.with_suffix(".asset.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8",
        )
        results.append(metadata)
    return results
