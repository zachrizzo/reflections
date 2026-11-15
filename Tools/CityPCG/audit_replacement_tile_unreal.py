"""Audit the original and an owned replacement tile without altering either."""

import json
import math
from pathlib import Path

from import_medieval_kit import opening_world

SOURCE_TILE_ACTOR = "/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/6/RK/40RMT8C5SHUKBGPOO36KRE"
OWNED_TILE = "/Game/GrayLondon/MedievalOpening/WholeBuildings/WestMarkLane/SM_GLMedieval_WestBlockTile"


def vec(vector):
    return [float(getattr(vector, axis)) for axis in "xyz"]


def mesh_slots(mesh):
    return [str(slot.get_editor_property("material_slot_name"))
            for slot in mesh.get_editor_property("static_materials")]


def mesh_box(mesh):
    box = mesh.get_bounding_box()
    return vec(box.min), vec(box.max)


def material_path(material):
    return material.get_path_name() if material else None


def inspect_source(tile_metadata):
    import unreal

    opening_world(unreal)
    metadata = json.loads(Path(tile_metadata).read_text(encoding="utf-8"))
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    matches = [actor for actor in actors.get_all_level_actors() if actor.get_path_name() == metadata["actor"]]
    if len(matches) != 1 or matches[0].get_package().get_name() != SOURCE_TILE_ACTOR:
        raise RuntimeError("The exact original tile actor must already be loaded.")
    actor = matches[0]
    components = actor.get_components_by_class(unreal.StaticMeshComponent)
    if len(components) != 1:
        raise RuntimeError("The source tile must have one mesh component.")
    component = components[0]
    source = component.get_editor_property("static_mesh")
    if not source or source.get_path_name() != metadata["asset"]:
        raise RuntimeError("The source actor's mesh changed from the reviewed export.")
    position = vec(component.get_world_location())
    axes = component.get_world_rotation()
    rotation = [float(getattr(axes, axis)) for axis in ("pitch", "yaw", "roll")]
    scale = vec(component.get_world_scale())
    if (math.dist(position, [100 * value for value in metadata["origin_m"]]) > .03 or
            any(abs(angle) > .001 for angle in rotation) or math.dist(scale, [1, 1, 1]) > .00001):
        raise RuntimeError("The source transform no longer matches the reviewed translation.")
    names = mesh_slots(source)
    if names != list(metadata["primitives"]) or source.get_num_sections(0) != len(names):
        raise RuntimeError("The source mesh section layout changed.")
    descs = [desc for desc in unreal.WorldPartitionBlueprintLibrary.get_actor_descs() or []
             if str(desc.get_editor_property("actor_package")) == SOURCE_TILE_ACTOR]
    if len(descs) != 1:
        raise RuntimeError("The source actor's streaming configuration could not be resolved.")
    desc = descs[0]
    subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    return {
        "actor": metadata["actor"],
        "actor_package": SOURCE_TILE_ACTOR,
        "source_asset": metadata["asset"],
        "location_cm": position,
        "pitch_yaw_roll_deg": rotation,
        "scale": scale,
        "bounds_local_cm": mesh_box(source),
        "runtime_grid": str(desc.get_editor_property("runtime_grid")),
        "spatially_loaded": desc.get_editor_property("is_spatially_loaded"),
        "data_layers": [str(value) for value in desc.get_editor_property("data_layer_assets") or []],
        "collision_profile": str(component.get_collision_profile_name()),
        "collision_enabled": str(component.get_collision_enabled()),
        "navigation": component.get_editor_property("can_ever_affect_navigation"),
        "collision_complexity": str(subsystem.get_collision_complexity(source)),
        "simple_collision_count": subsystem.get_simple_collision_count(source),
        "has_navigation_data": source.get_editor_property("has_navigation_data"),
        "lod_count": subsystem.get_lod_count(source),
        "uv_channel_count": subsystem.get_num_uv_channels(source, 0),
        "sections": [
            {"slot": name,
             "source_material": material_path(source.get_material(index)),
             "component_material": material_path(component.get_material(index)),
             "casts_shadow": subsystem.is_section_cast_shadow_enabled(source, 0, index),
             "collision_enabled": subsystem.is_section_collision_enabled(source, 0, index)}
            for index, name in enumerate(names)
        ],
    }


def inspect_owned_mesh(tile_metadata, derivative_audit):
    import unreal

    source = inspect_source(tile_metadata)
    evidence = json.loads(Path(derivative_audit).read_text(encoding="utf-8"))
    names = [section["slot"] for section in source["sections"]]
    if [row["unreal_slot"] for row in evidence["primitives"]] != names:
        raise RuntimeError("The derivative belongs to a different source mesh.")
    mesh = unreal.EditorAssetLibrary.load_asset(OWNED_TILE)
    if not isinstance(mesh, unreal.StaticMesh) or mesh.get_package().get_name() != OWNED_TILE:
        raise RuntimeError("Import the owned tile first.")
    subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    source_materials = [section["component_material"] for section in source["sections"]]
    materials = [material_path(mesh.get_material(index)) for index in range(len(names))]
    collision = [subsystem.is_section_collision_enabled(mesh, 0, section) for section in range(len(names))]
    expected_triangles = sum(section["output_triangles"] for section in evidence["primitives"])
    bounds = mesh_box(mesh)
    if (mesh_slots(mesh) != names or mesh.get_num_sections(0) != len(names) or materials != source_materials or
            mesh.get_num_triangles(0) != expected_triangles or
            any(math.dist(a, b) > .2 for a, b in zip(bounds, source["bounds_local_cm"])) or
            subsystem.get_num_uv_channels(mesh, 0) != source["uv_channel_count"] or
            subsystem.get_lod_count(mesh) != source["lod_count"]):
        raise RuntimeError("Owned tile material, geometry, LOD, UV, or bounds differ from the audited derivative.")
    if (str(subsystem.get_collision_complexity(mesh)) != source["collision_complexity"] or
            subsystem.get_simple_collision_count(mesh) != source["simple_collision_count"] or
            mesh.get_editor_property("has_navigation_data") != source["has_navigation_data"] or
            [subsystem.is_section_cast_shadow_enabled(mesh, 0, i) for i in range(len(names))] !=
            [section["casts_shadow"] for section in source["sections"]] or
            collision != [section["collision_enabled"] for section in source["sections"]]):
        raise RuntimeError("Owned tile collision settings do not match the source.")
    return {"source": source, "replacement_package": OWNED_TILE,
            "replacement_triangles": expected_triangles, "replacement_bounds_local_cm": bounds}
