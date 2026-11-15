"""Import only the audited West Mark Lane replacement tile into its owned package."""

from collections import Counter, defaultdict
import math
from pathlib import Path
import struct
from tempfile import TemporaryDirectory

from apply_facade_pcg import verify_editor
from audit_replacement_tile_unreal import OWNED_TILE, inspect_owned_mesh, inspect_source, mesh_slots
from extract_tile_frontages import accessor, read_glb
from name_replacement_tile_slots import write_import_copy
from subtract_building_shells import digest, indices, read_json

NORMAL_TOLERANCE_DEG = .25


def uv_corners(document, blob, index):
    specification = document["accessors"][index]
    view = document["bufferViews"][specification["bufferView"]]
    if (specification["type"], specification["componentType"]) != ("VEC2", 5126) or view.get("buffer") != 0:
        raise ValueError("Expected a float TEXCOORD_0 stream in the main binary buffer.")
    offset = view.get("byteOffset", 0) + specification.get("byteOffset", 0)
    stride = view.get("byteStride", 8)
    return [struct.unpack_from("<2f", blob, offset + stride * i) for i in range(specification["count"])]


def sections_by_corners(glb, include_normals=False):
    """Preserve signed axis coordinates, facing and UV attachment regardless of index order."""
    document, binary = read_glb(glb)
    sections = []
    for index, primitive in enumerate(document["meshes"][0]["primitives"]):
        attrs = primitive["attributes"]
        vertices = accessor(document, binary, attrs["POSITION"], {("VEC3", 5126)})
        uv = uv_corners(document, binary, attrs["TEXCOORD_0"])
        if len(vertices) != len(uv):
            raise ValueError("Position and UV counts differ.")
        corners = [tuple(round(v, 3) for v in position) + tuple(round(v, 5) for v in texcoord)
                   for position, texcoord in zip(vertices, uv)]
        face_indices = indices(document, binary, index)
        if len(face_indices) % 3:
            raise ValueError("A section does not contain indexed triangles.")
        faces = defaultdict(list) if include_normals else Counter()
        if include_normals:
            normals = accessor(document, binary, attrs["NORMAL"], {("VEC3", 5126)})
            if len(normals) != len(vertices):
                raise ValueError("Position and normal counts differ.")
        for start in range(0, len(face_indices), 3):
            triple = face_indices[start:start + 3]
            positions = tuple(corners[i] for i in triple)
            rotation = min(range(3), key=lambda i: positions[i:] + positions[:i])
            positions = positions[rotation:] + positions[:rotation]
            if include_normals:
                faces[positions].append(tuple(normals[i] for i in triple[rotation:] + triple[:rotation]))
            else:
                faces[positions] += 1
        sections.append(faces)
    return sections


def direction_error(source, result):
    source_length, result_length = math.hypot(*source), math.hypot(*result)
    source_valid = math.isfinite(source_length) and source_length > 1e-4
    result_valid = math.isfinite(result_length) and result_length > 1e-4
    if not source_valid or not result_valid:
        return (180.0 if source_valid != result_valid else 0.0), not source_valid, not result_valid
    cosine = sum(a * b for a, b in zip(source, result)) / (source_length * result_length)
    return math.degrees(math.acos(min(1.0, max(-1.0, cosine)))), False, False


def compare_normals(reference_glb, imported_glb):
    source_sections = sections_by_corners(reference_glb, include_normals=True)
    result_sections = sections_by_corners(imported_glb, include_normals=True)
    if len(source_sections) != len(result_sections):
        raise RuntimeError("Source and import have different section counts.")
    reports = []
    for index, (source, result) in enumerate(zip(source_sections, result_sections)):
        if {key: len(faces) for key, faces in source.items()} != {key: len(faces) for key, faces in result.items()}:
            raise RuntimeError(f"Signed triangle corners differ in section {index}.")
        report = {"section": index, "maximum_angle_deg": 0.0, "corner_count": 0, "deviating_corners": 0,
                  "invalid_source_corners": 0, "invalid_import_corners": 0, "examples": []}
        for corners, original_faces in source.items():
            remaining = list(result[corners])
            for original in original_faces:
                scores = [tuple(direction_error(a, b) for a, b in zip(original, candidate))
                          for candidate in remaining]
                best = min(range(len(scores)), key=lambda i: max(error[0] for error in scores[i]))
                imported = remaining.pop(best)
                for corner, a, b, (angle, bad_a, bad_b) in zip(corners, original, imported, scores[best]):
                    report["corner_count"] += 1
                    report["maximum_angle_deg"] = max(report["maximum_angle_deg"], angle)
                    report["invalid_source_corners"] += bad_a
                    report["invalid_import_corners"] += bad_b
                    if angle > NORMAL_TOLERANCE_DEG:
                        report["deviating_corners"] += 1
                        if len(report["examples"]) < 3:
                            report["examples"].append({"local_gltf_m": corner[:3], "source": a,
                                                       "import": b, "angle_deg": angle})
        reports.append(report)
    return {"tolerance_deg": NORMAL_TOLERANCE_DEG, "sections": reports}


def check_input(named, filtered, audit, source_glb, source_metadata):
    evidence, metadata = read_json(audit), read_json(source_metadata)
    if named.stem != OWNED_TILE.rsplit("/", 1)[-1]:
        raise ValueError("The named import file must match the one owned asset.")
    if digest(source_glb.read_bytes()) != evidence["original_sha256"]:
        raise ValueError("The saved source GLB differs from the geometry audit.")
    if (evidence["source_actor_location_m"] != metadata["origin_m"] or
            [section["unreal_slot"] for section in evidence["primitives"]] != list(metadata["primitives"])):
        raise ValueError("The source section or transform metadata changed.")
    with TemporaryDirectory() as location:
        recreated = Path(location) / named.name
        write_import_copy(filtered, audit, recreated)
        if digest(recreated.read_bytes()) != digest(named.read_bytes()):
            raise ValueError("The import file differs from the audited six-slot transport.")
    return evidence


def import_options(unreal):
    pipeline = unreal.InterchangeGenericAssetsPipeline()
    material = pipeline.get_editor_property("material_pipeline")
    material.set_editor_property("import_materials", False)
    material.get_editor_property("texture_pipeline").set_editor_property("import_textures", False)
    pipeline.get_editor_property("animation_pipeline").set_editor_property("import_animations", False)
    meshes = pipeline.get_editor_property("mesh_pipeline")
    meshes.set_editor_properties({"import_static_meshes": True, "import_skeletal_meshes": False,
                                  "collision": False, "build_nanite": False, "generate_lightmap_u_vs": False})
    pipeline.get_editor_property("common_meshes_properties").set_editor_properties({
        "recompute_normals": False, "recompute_tangents": False, "remove_degenerates": False,
    })
    stack = unreal.InterchangePipelineStackOverride()
    stack.add_pipeline(pipeline)
    return pipeline, stack


def compare_roundtrip(unreal, mesh, expected_slots, import_glb, evidence):
    from export_geodata_tiles_unreal import verify_export

    with TemporaryDirectory() as location:
        roundtrip = Path(location) / "ImportedTile.glb"
        options = unreal.GLTFExportOptions()
        options.set_editor_properties({"bake_material_inputs": unreal.GLTFMaterialBakeMode.DISABLED,
                                       "export_source_model": True, "export_uniform_scale": .01})
        messages = unreal.GLTFExporter.export_to_gltf(mesh, str(roundtrip), options, set())
        if messages is None or messages.get_editor_property("errors"):
            raise RuntimeError(f"Could not export the imported mesh for geometry comparison: {messages}")
        actual_counts = verify_export(roundtrip, expected_slots, mesh)
        expected_counts = [section["output_triangles"] for section in evidence["primitives"]]
        if actual_counts != expected_counts:
            raise RuntimeError("Imported section triangle counts differ from the audit.")
        normals = compare_normals(import_glb, roundtrip)
    return actual_counts, normals


def audit_saved_normals():
    import unreal

    city = Path(unreal.Paths.project_saved_dir()).resolve() / "CityPCG"
    survey = city / "MedievalSurvey"
    audit = survey / "Tile_p03_p00_without_three_west_shells.audit.json"
    source = inspect_owned_mesh(city / "Tile_p03_p00.asset.json", audit)
    mesh = unreal.EditorAssetLibrary.load_asset(OWNED_TILE)
    expected_slots = [section["slot"] for section in source["source"]["sections"]]
    counts, normals = compare_roundtrip(
        unreal, mesh, expected_slots, survey / "SM_GLMedieval_WestBlockTile.glb", read_json(audit))
    return {"section_triangle_counts": counts, "normals": normals}


def run():
    import unreal

    verify_editor(unreal)
    city = Path(unreal.Paths.project_saved_dir()).resolve() / "CityPCG"
    survey = city / "MedievalSurvey"
    source_metadata = city / "Tile_p03_p00.asset.json"
    source_glb = city / "Tile_p03_p00.glb"
    audit = survey / "Tile_p03_p00_without_three_west_shells.audit.json"
    filtered = survey / "Tile_p03_p00_without_three_west_shells.glb"
    named = survey / "SM_GLMedieval_WestBlockTile.glb"
    evidence = check_input(named, filtered, audit, source_glb, source_metadata)
    source = inspect_source(source_metadata)
    if source["lod_count"] != 1 or source["simple_collision_count"] != 0:
        raise RuntimeError("This exact replacement cannot reconstruct additional source LODs or simple collision.")
    property_names = ("has_navigation_data", "light_map_coordinate_index", "light_map_resolution")
    source_mesh = unreal.EditorAssetLibrary.load_asset(source["source_asset"])
    if source_mesh.get_editor_property("complex_collision_mesh"):
        raise RuntimeError("The source has a separate complex mesh that the filtered tile cannot reuse.")

    editor = unreal.EditorAssetLibrary
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mesh_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    destination, asset_name = OWNED_TILE.rsplit("/", 1)
    if editor.does_asset_exist(OWNED_TILE):
        raise RuntimeError("The importer does not overwrite existing packages.")
    before = set(editor.list_assets(destination, recursive=True, include_folder=False))
    _pipeline, stack = import_options(unreal)
    task = unreal.AssetImportTask()
    task.set_editor_properties({"filename": str(named), "destination_path": destination, "destination_name": asset_name,
                                "automated": True, "save": False, "replace_existing": False, "options": stack})
    tools.import_asset_tasks([task])
    assets = list(task.get_objects())
    new_paths = set(editor.list_assets(destination, recursive=True, include_folder=False)) - before
    if (len(assets) != 1 or not isinstance(assets[0], unreal.StaticMesh) or
            assets[0].get_package().get_name() != OWNED_TILE or new_paths != {f"{OWNED_TILE}.{asset_name}"}):
        raise RuntimeError(f"Import created unexpected assets. Nothing saved: {new_paths}")
    mesh = assets[0]
    sections = source["sections"]
    expected_slots = [section["slot"] for section in sections]
    if mesh_slots(mesh) != expected_slots or mesh_editor.get_simple_collision_count(mesh):
        raise RuntimeError("Unexpected imported material slot or generated simple collision.")
    for index, section in enumerate(sections):
        path = section["component_material"]
        material = editor.load_asset(path) if path else None
        if path and (not isinstance(material, unreal.MaterialInterface) or material.get_path_name() != path):
            raise RuntimeError(f"Could not resolve source override for {section['slot']}.")
        mesh.set_material(index, material)
        mesh_editor.enable_section_collision(mesh, section["collision_enabled"], 0, index)
        mesh_editor.enable_section_cast_shadow(mesh, section["casts_shadow"], 0, index)
    mesh.set_editor_properties({key: source_mesh.get_editor_property(key) for key in property_names})
    mesh_editor.set_lod_build_settings(mesh, 0, mesh_editor.get_lod_build_settings(source_mesh, 0))
    complexity = mesh_editor.get_collision_complexity(source_mesh)
    if not mesh_editor.set_collision_complexity(mesh, complexity):
        raise RuntimeError("Could not apply the original collision complexity.")
    source_body = source_mesh.get_editor_property("body_setup")
    new_body = mesh.get_editor_property("body_setup")
    if not source_body or not new_body:
        raise RuntimeError("The original or filtered tile is missing collision asset data.")
    properties = ("default_instance", "phys_material")
    new_body.set_editor_properties({key: source_body.get_editor_property(key) for key in properties})
    original_profile = source_body.get_editor_property("default_instance").get_editor_property("collision_profile_name")
    copy_profile = new_body.get_editor_property("default_instance").get_editor_property("collision_profile_name")
    if (copy_profile != original_profile or
            new_body.get_editor_property("phys_material") != source_body.get_editor_property("phys_material")):
        raise RuntimeError("The filtered tile's default collision profile or physical material differs.")

    counts, normals = compare_roundtrip(unreal, mesh, expected_slots, named, evidence)
    if any(section["deviating_corners"] for section in normals["sections"]):
        raise RuntimeError(f"Imported normal directions differ from the reviewed tile: {normals}")
    verified = inspect_owned_mesh(source_metadata, audit)
    verify_editor(unreal)
    package = mesh.get_package()
    if package.get_name() != OWNED_TILE:
        raise RuntimeError("Unexpected asset save path.")
    if not unreal.EditorLoadingAndSavingUtils.save_packages([package], only_dirty=False):
        raise RuntimeError(f"Could not save {OWNED_TILE}.")
    multi_user = unreal.MultiUserClientStatics
    if multi_user.get_multi_user_connection_status_detail() == unreal.MultiUserConnectionStatus.CONNECTED:
        multi_user.persist_specified_packages([OWNED_TILE])
    return {**verified, "section_triangle_counts": counts, "normals": normals, "saved_packages": [OWNED_TILE]}
