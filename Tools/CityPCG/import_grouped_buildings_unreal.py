"""Preflight and import complete groups of medieval buildings as new UE meshes.

The offline preflight independently compares the grouped GLBs with their source
FBXs. The Unreal entry point imports complete tile groups under a held editor
lease, compares a GLB export of each imported mesh, and saves only the verified
new static-mesh packages. It never places actors or changes the source map.
"""

import argparse
import ctypes
import hashlib
import json
import math
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import time

from audit_replacement_tile_unreal import mesh_box, mesh_slots
from extract_tile_frontages import accessor, read_glb
from group_whole_buildings import MATERIAL, MATERIAL_ROOT, PROJECT_ROOT, resolve_project_file
from import_replacement_tile_unreal import compare_normals, import_options
from read_prepared_building_fbx import load_decoder
from subtract_building_shells import indices, read_json
from verify_grouped_whole_buildings import CELL, decode_uv, verify as verify_grouped


PROJECT = PROJECT_ROOT.resolve()
BUNDLE = PROJECT / "ArtDirection/CityPCG/MedievalOpening/WholeBuildings/GroupedPrototype"
MANIFEST = "grouped_buildings.json"
EVIDENCE = "rollout_mask_evidence.json"
DEST = "/Game/GrayLondon/MedievalOpening/WholeBuildings/GroupedCells"
LEVEL = "/Game/GrayLondon/Maps/GrayLondon_Geodata"
SAVED = PROJECT / "Saved"
OWNER = "codex-gray-london"
MIN_LEASE_SECONDS = 30.
MIN_PHYSICAL_BYTES = 4 * 1024 ** 3
MIN_COMMIT_BYTES = 10 * 1024 ** 3
BOUNDS_TOLERANCE_CM = .2
TILE = re.compile(r"Tile_[pm]\d{2}_[pm]\d{2}")


def file_sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def project_ref(path, root=None):
    root = (root or PROJECT).resolve()
    path = path.resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Input is outside this checkout: {path}")
    return path.relative_to(root).as_posix()


def group_package(cell):
    if not CELL.fullmatch(cell):
        raise ValueError(f"Invalid grouped cell name: {cell!r}")
    name = f"SM_GLMedieval_Group_{cell}"
    return f"{DEST}/{name}"


def validate_manifest(bundle=None):
    bundle = bundle or BUNDLE
    manifest = read_json(bundle / MANIFEST)
    evidence = read_json(bundle / EVIDENCE)
    cells, barriers = manifest["cells"], manifest["tile_barriers"]
    if (manifest.get("schema") != 2 or manifest.get("status") != "offline_geometry_only" or
            manifest.get("source_paths") != "project_relative_posix" or
            evidence.get("status") != "offline_only" or not cells or not barriers or
            barriers.keys() != evidence["cumulative_masks"].keys()):
        raise ValueError("Expected a portable grouped bundle and its offline mask evidence.")
    assigned = []
    for tile, barrier in barriers.items():
        mask = evidence["cumulative_masks"][tile]
        required = barrier["required_cells"]
        if (not TILE.fullmatch(tile) or mask["source_tile"] != tile or
                barrier["source_tile_asset"] != mask["source_tile_asset"] or
                barrier["source_origin_m"] != mask["source_origin_m"] or
                barrier["source_export_sha256"] != mask["source_export_sha256"] or
                not required or len(required) != len(set(required))):
            raise ValueError(f"{tile}: inconsistent or incomplete source tile barrier.")
        if sorted(row["id"] for row in mask["buildings"]) != barrier["required_building_ids"]:
            raise ValueError(f"{tile}: building identities differ from the cumulative mask.")
        for name in required:
            if name not in cells or cells[name]["tile"] != tile:
                raise ValueError(f"{tile}: missing or wrongly assigned grouped cell {name}.")
        assigned.extend(required)
    if len(assigned) != len(set(assigned)) or set(assigned) != set(cells):
        raise ValueError("Each grouped cell must belong to exactly one complete tile barrier.")
    return manifest, evidence


def describe_cell(bundle, name, cell):
    if not CELL.fullmatch(name) or cell["file"] != f"{name}.glb":
        raise ValueError(f"Unexpected grouped cell identity {name!r}.")
    path = bundle / cell["file"]
    if path.resolve().parent != bundle.resolve() or file_sha(path) != cell["sha256"]:
        raise ValueError(f"{name}: grouped geometry does not match the reviewed digest.")
    document, binary = read_glb(path)
    sections = cell["sections"]
    primitives = document["meshes"][0]["primitives"]
    materials = document["materials"]
    names = [row["slot"] for row in sections]
    if (not sections or len(names) != len(set(names)) or len(primitives) != len(names) or
            len(materials) != len(names) or len(cell["origin_ue_m"]) != 3 or
            not all(math.isfinite(value) for value in cell["origin_ue_m"])):
        raise ValueError(f"{name}: invalid sections or group origin.")
    bounds = [[math.inf] * 3, [-math.inf] * 3]
    counts = []
    for index, (section, primitive, material) in enumerate(zip(sections, primitives, materials)):
        slot = section["slot"]
        if (not MATERIAL.fullmatch(slot) or material.get("name") != slot or primitive.get("material") != index or
                section["material_asset"] != f"{MATERIAL_ROOT}/{slot}.{slot}" or
                primitive.get("mode", 4) != 4 or primitive.get("extensions") or
                set(primitive["attributes"]) != {"POSITION", "NORMAL", "TEXCOORD_0"}):
            raise ValueError(f"{name}: section {index} does not map to the exact reviewed material slot.")
        attributes = primitive["attributes"]
        positions = accessor(document, binary, attributes["POSITION"], {("VEC3", 5126)})
        normals = accessor(document, binary, attributes["NORMAL"], {("VEC3", 5126)})
        corners = indices(document, binary, index)
        uv = document["accessors"][attributes["TEXCOORD_0"]]
        texcoords = decode_uv(document, binary, attributes["TEXCOORD_0"])
        if (not positions or len(positions) != len(normals) or uv["type"] != "VEC2" or
                uv["componentType"] != 5126 or uv["count"] != len(positions) or
                len(texcoords) != len(positions) or
                len(corners) != section["triangles"] * 3 or not corners or
                any(i < 0 or i >= len(positions) for i in corners)):
            raise ValueError(f"{name}: section {index} has invalid position, normal, UV or triangle streams.")
        if (any(not all(math.isfinite(value) for value in normal) or
                not math.isclose(math.hypot(*normal), 1., rel_tol=.001, abs_tol=.001) for normal in normals) or
                any(not all(math.isfinite(value) for value in coord) for coord in texcoords)):
            raise ValueError(f"{name}: section {index} has non-finite UVs or invalid normals.")
        for x, y, z in positions:
            if not all(math.isfinite(value) for value in (x, y, z)):
                raise ValueError(f"{name}: non-finite position.")
            for axis, value in enumerate((100 * x, 100 * z, 100 * y)):
                bounds[0][axis] = min(bounds[0][axis], value)
                bounds[1][axis] = max(bounds[1][axis], value)
        counts.append(len(corners) // 3)
    return {"source": project_ref(path), "source_sha256": cell["sha256"],
            "package": group_package(name), "tile": cell["tile"],
            "origin_ue_m": cell["origin_ue_m"], "bounds_cm": bounds,
            "slots": names, "material_assets": [row["material_asset"] for row in sections],
            "section_triangles": counts, "triangles": sum(counts)}


def input_fingerprints(bundle, manifest):
    paths = {bundle / MANIFEST, bundle / EVIDENCE}
    for name, cell in manifest["cells"].items():
        path = bundle / f"{name}.glb"
        if not CELL.fullmatch(name) or path.resolve().parent != bundle.resolve():
            raise ValueError(f"Unsafe grouped mesh path: {name!r}")
        paths.add(path)
        for row in cell["buildings"]:
            for field, suffix in (("kit", ".json"), ("canonical_fbx", ".fbx"), ("prepared_fbx", ".fbx")):
                paths.add(resolve_project_file(PROJECT, row[field], suffix))
    return {project_ref(path): file_sha(path) for path in sorted(paths)}


def preflight(decoder_dir, report_path, bundle=None):
    """Run the complete offline source-to-grouped comparison and create a fresh report."""
    bundle = bundle or BUNDLE
    report_path = Path(report_path).resolve()
    if not report_path.is_relative_to(SAVED.resolve()) or report_path.suffix.lower() != ".json":
        raise ValueError("Choose a new JSON report under this project's Saved directory.")
    if report_path.exists():
        raise FileExistsError(f"Choose a fresh preflight report: {report_path}")
    manifest, evidence = validate_manifest(bundle)
    before = input_fingerprints(bundle, manifest)
    checked = verify_grouped(bundle, evidence, load_decoder(decoder_dir), project_root=PROJECT)
    if checked.get("status") != "offline_geometry_only":
        raise RuntimeError("The independent grouped geometry comparison did not pass.")
    cells = {name: describe_cell(bundle, name, cell) for name, cell in sorted(manifest["cells"].items())}
    after = input_fingerprints(bundle, manifest)
    if before != after:
        raise RuntimeError("Grouped inputs changed while preflight was running; repeat the audit.")
    if (checked["cells"] != len(cells) or checked["triangles"] != sum(row["triangles"] for row in cells.values()) or
            checked["grouped_sections"] != sum(len(row["slots"]) for row in cells.values())):
        raise RuntimeError("The independent comparison and import plan disagree.")
    report = {"schema": 1, "status": "offline_preflight_passed", "bundle": project_ref(bundle),
              "inputs_sha256": after, "geometry_check": checked, "cells": cells}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    return report


def checked_report(path, bundle=None):
    bundle = bundle or BUNDLE
    path = Path(path).resolve()
    if not path.is_relative_to(SAVED.resolve()) or path.suffix.lower() != ".json":
        raise ValueError("The preflight report must be under this project's Saved directory.")
    report = read_json(path)
    manifest, _ = validate_manifest(bundle)
    if (report.get("schema") != 1 or report.get("status") != "offline_preflight_passed" or
            report.get("bundle") != project_ref(bundle) or report.get("cells", {}).keys() != manifest["cells"].keys() or
            report.get("geometry_check", {}).get("status") != "offline_geometry_only" or
            report.get("inputs_sha256") != input_fingerprints(bundle, manifest)):
        raise RuntimeError("The grouped preflight is missing, stale, or for a different bundle.")
    for name, row in report["cells"].items():
        cell = manifest["cells"][name]
        sections = cell["sections"]
        if (row["source"] != project_ref(bundle / cell["file"]) or row["source_sha256"] != cell["sha256"] or
                row["package"] != group_package(name) or row["tile"] != cell["tile"] or
                row["origin_ue_m"] != cell["origin_ue_m"] or
                row["slots"] != [section["slot"] for section in sections] or
                row["material_assets"] != [section["material_asset"] for section in sections] or
                row["section_triangles"] != [section["triangles"] for section in sections] or
                row["triangles"] != sum(section["triangles"] for section in sections)):
            raise RuntimeError(f"{name}: preflight import plan disagrees with the checked bundle.")
        if row != describe_cell(bundle, name, cell):
            raise RuntimeError(f"{name}: preflight geometry or signed bounds changed.")
    return manifest, report


def selected_cells(manifest, report, tiles):
    tiles = list(tiles)
    if (not tiles or len(tiles) != len(set(tiles)) or
            any(not TILE.fullmatch(tile) or tile not in manifest["tile_barriers"] for tile in tiles)):
        raise ValueError("Choose one or more distinct tiles from the preflight bundle.")
    names = [name for tile in sorted(tiles) for name in manifest["tile_barriers"][tile]["required_cells"]]
    if len(names) != len(set(names)) or any(name not in report["cells"] for name in names):
        raise RuntimeError("Every selected tile must include all of its checked cells exactly once.")
    return [(name, report["cells"][name]) for name in names]


def memory_headroom():
    """Read Windows physical and system commit headroom without starting a process."""
    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                    ("total_physical", ctypes.c_ulonglong), ("available_physical", ctypes.c_ulonglong),
                    ("total_page_file", ctypes.c_ulonglong), ("available_page_file", ctypes.c_ulonglong),
                    ("total_virtual", ctypes.c_ulonglong), ("available_virtual", ctypes.c_ulonglong),
                    ("available_extended_virtual", ctypes.c_ulonglong)]

    try:
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise ctypes.WinError()
    except (AttributeError, OSError) as error:
        raise RuntimeError("Cannot verify Windows memory headroom for a grouped import.") from error
    return status.available_physical, status.available_page_file


def require_editor(unreal, expected_lease=None):
    active_project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
    if active_project != PROJECT:
        raise RuntimeError("The running Unreal editor is attached to a different checkout.")
    try:
        lease = read_json(SAVED / "PIE_LOCK.json")
        remaining = float(lease["expires_epoch"]) - time.time()
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise RuntimeError(f"An active {OWNER} editor lease is required.") from error
    if (lease.get("owner") != OWNER or not math.isfinite(remaining) or remaining < MIN_LEASE_SECONDS or
            (expected_lease is not None and lease != expected_lease)):
        raise RuntimeError(f"The original {OWNER} lease needs at least {MIN_LEASE_SECONDS:g} seconds remaining.")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if (not world or world.get_path_name().split(".")[0] != LEVEL or editor.get_game_world() or
            unreal.EditorLevelLibrary.get_pie_worlds(True)):
        raise RuntimeError(f"Open {LEVEL} outside PIE before importing.")
    if (unreal.MultiUserClientStatics.get_multi_user_connection_status_detail() ==
            unreal.MultiUserConnectionStatus.CONNECTED):
        raise RuntimeError("The grouped importer requires the editor outside a Multi-User session.")
    physical, commit = memory_headroom()
    if physical < MIN_PHYSICAL_BYTES or commit < MIN_COMMIT_BYTES:
        raise RuntimeError(f"Grouped import requires 4 GiB physical and 10 GiB system commit headroom; "
                           f"available {physical / 1024 ** 3:.2f} / {commit / 1024 ** 3:.2f} GiB.")
    return lease


def package_file(package):
    if not package.startswith(DEST + "/"):
        raise ValueError(f"Unexpected package outside the grouped destination: {package}")
    return PROJECT / "Content" / (package.removeprefix("/Game/") + ".uasset")


def assert_absent(unreal, package):
    if (package_file(package).exists() or unreal.EditorAssetLibrary.does_asset_exist(package) or
            unreal.find_package(package) is not None):
        raise FileExistsError(f"Refusing to overwrite existing disk, registry or in-memory package {package}.")


def compare_roundtrip(unreal, mesh, row):
    from export_geodata_tiles_unreal import verify_export

    scratch = SAVED / "CityPCG/GroupedImport/roundtrip"
    scratch.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="mesh_", dir=scratch) as directory:
        temporary = Path(directory).resolve()
        if not temporary.is_relative_to(scratch.resolve()):
            raise RuntimeError("Round-trip scratch directory escaped the intended Saved folder.")
        output = temporary / "ImportedGroup.glb"
        options = unreal.GLTFExportOptions()
        options.set_editor_properties({"bake_material_inputs": unreal.GLTFMaterialBakeMode.DISABLED,
                                       "export_source_model": True, "export_uniform_scale": .01})
        messages = unreal.GLTFExporter.export_to_gltf(mesh, str(output), options, set())
        if messages is None or messages.get_editor_property("errors"):
            raise RuntimeError(f"Could not export the imported mesh for geometry comparison: {messages}")
        counts = verify_export(output, row["slots"], mesh)
        if counts != row["section_triangles"]:
            raise RuntimeError("Imported section triangle counts differ from the checked grouped mesh.")
        normals = compare_normals(PROJECT / row["source"], output)
        if any(section["deviating_corners"] or section["invalid_source_corners"] or
               section["invalid_import_corners"] for section in normals["sections"]):
            raise RuntimeError(f"Imported winding, UV or normal directions differ from the grouped mesh: {normals}")
        return {"section_triangle_counts": counts, "normal_comparison": normals}


def verify_mesh(unreal, mesh, row):
    package = row["package"]
    name = package.rsplit("/", 1)[-1]
    if not isinstance(mesh, unreal.StaticMesh) or mesh.get_path_name() != f"{package}.{name}":
        raise RuntimeError(f"Import did not produce the exact owned mesh {package}.")
    mesh_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    bounds = mesh_box(mesh)
    materials = [mesh.get_material(index) for index in range(len(row["slots"]))]
    if (mesh_slots(mesh) != row["slots"] or
            [material.get_path_name() if material else None for material in materials] != row["material_assets"] or
            mesh.get_num_sections(0) != len(row["slots"]) or mesh.get_num_triangles(0) != row["triangles"] or
            mesh_editor.get_lod_count(mesh) != 1 or mesh_editor.get_num_uv_channels(mesh, 0) != 1 or
            any(abs(actual - expected) > BOUNDS_TOLERANCE_CM
                for actual_bound, expected_bound in zip(bounds, row["bounds_cm"])
                for actual, expected in zip(actual_bound, expected_bound))):
        raise RuntimeError(f"{name}: slot bindings, geometry, UVs, LODs or signed bounds differ.")
    if (mesh_editor.get_simple_collision_count(mesh) or mesh_editor.get_convex_collision_count(mesh) or
            mesh_editor.get_collision_complexity(mesh) != unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE or
            not all(mesh_editor.is_section_collision_enabled(mesh, 0, index) for index in range(len(row["slots"]))) or
            not mesh.get_editor_property("has_navigation_data")):
        raise RuntimeError(f"{name}: collision or navigation data does not match the import contract.")
    return {"package": package, "bounds_cm": bounds, "origin_ue_m": row["origin_ue_m"],
            "triangles": row["triangles"], "material_packages": [path.split(".")[0] for path in row["material_assets"]],
            "has_navigation_data": True, "collision_complexity": "ComplexAsSimple"}


def verify_registry(unreal, rows):
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.scan_paths_synchronous([DEST], True)
    options = unreal.AssetRegistryDependencyOptions()
    options.set_editor_property("include_soft_package_references", False)
    for row in rows:
        dependencies = {str(name) for name in registry.get_dependencies(row["package"], options) or []}
        missing = set(row["material_packages"]) - dependencies
        if missing:
            raise RuntimeError(f'{row["package"]}: saved asset lacks hard material dependencies {sorted(missing)}.')


def run(tiles, report_path):
    """Import every checked cell for each explicitly named tile, without placing it."""
    import unreal

    tiles = list(tiles)
    lease = require_editor(unreal)
    manifest, report = checked_report(report_path)
    chosen = selected_cells(manifest, report, tiles)
    require_editor(unreal, lease)
    expected = [row["package"] for _, row in chosen]
    for package in expected:
        assert_absent(unreal, package)
    materials = {}
    for path in sorted({path for _, row in chosen for path in row["material_assets"]}):
        material = unreal.load_asset(path, unreal.MaterialInterface)
        if not isinstance(material, unreal.MaterialInterface) or material.get_path_name() != path:
            raise RuntimeError(f"Missing or mismatched existing medieval material {path}.")
        materials[path] = material

    assets = unreal.EditorAssetLibrary
    mesh_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    before = set(assets.list_assets(DEST, recursive=True, include_folder=False))
    _, stack = import_options(unreal)
    rows, packages = [], []
    for name, row in chosen:
        require_editor(unreal, lease)
        assert_absent(unreal, row["package"])
        source = resolve_project_file(PROJECT, row["source"], ".glb")
        if file_sha(source) != row["source_sha256"]:
            raise RuntimeError(f"{name}: grouped source changed after preflight.")
        task = unreal.AssetImportTask()
        asset_name = row["package"].rsplit("/", 1)[-1]
        task.set_editor_properties({"filename": str(source), "destination_path": DEST,
                                    "destination_name": asset_name, "automated": True, "save": False,
                                    "replace_existing": False, "options": stack})
        tools.import_asset_tasks([task])
        imported = list(task.get_objects())
        if (len(imported) != 1 or not isinstance(imported[0], unreal.StaticMesh) or
                imported[0].get_package().get_name() != row["package"]):
            raise RuntimeError(f"{name}: import produced unexpected objects; none were saved by this script.")
        require_editor(unreal, lease)
        mesh = imported[0]
        if mesh_slots(mesh) != row["slots"] or mesh.get_num_sections(0) != len(row["slots"]):
            raise RuntimeError(f"{name}: imported material slots do not preserve the grouped section order.")
        for index, path in enumerate(row["material_assets"]):
            mesh.set_material(index, materials[path])
            mesh_editor.enable_section_collision(mesh, True, 0, index)
        mesh.set_editor_property("has_navigation_data", True)
        if not mesh_editor.set_collision_complexity(mesh, unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE):
            raise RuntimeError(f"{name}: could not enable ComplexAsSimple collision.")
        audited = verify_mesh(unreal, mesh, row)
        audited.update(compare_roundtrip(unreal, mesh, row))
        require_editor(unreal, lease)
        rows.append(audited)
        packages.append(mesh.get_package())

    require_editor(unreal, lease)
    checked_report(report_path)
    found = set(assets.list_assets(DEST, recursive=True, include_folder=False)) - before
    expected_objects = {f'{row["package"]}.{row["package"].rsplit("/", 1)[-1]}' for _, row in chosen}
    if (found != expected_objects or [package.get_name() for package in packages] != expected or
            any(package_file(path).exists() for path in expected)):
        raise RuntimeError(f"Grouped import produced an unexpected save scope; nothing saved: {sorted(found)}")
    try:
        saved = unreal.EditorLoadingAndSavingUtils.save_packages(packages, only_dirty=False)
    except Exception as error:
        present = [path for path in expected if package_file(path).exists()]
        raise RuntimeError(f"Saving selected packages raised an error; files present: {present}") from error
    if not saved:
        present = [path for path in expected if package_file(path).exists()]
        raise RuntimeError(f"Could not save all selected packages; files present: {present}")
    missing = [path for path in expected if not package_file(path).is_file()]
    if missing:
        raise RuntimeError(f"Saved packages were not found on disk: {missing}")
    try:
        verify_registry(unreal, rows)
    except Exception as error:
        raise RuntimeError(f"Saved packages failed registry verification: {expected}") from error
    return {"status": "assets_imported_not_placed", "tiles": sorted(tiles), "meshes": rows,
            "saved_packages": expected,
            "note": "Tile masks, actor placement, collision and navigation in the world still need live review."}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--preflight", action="store_true", required=True,
                     help="Run the offline grouped-geometry verification")
    cli.add_argument("--fbx-decoder-dir", type=Path, required=True)
    cli.add_argument("--report", type=Path, required=True, help="Fresh report path under Saved")
    args = cli.parse_args()
    report = preflight(args.fbx_decoder_dir, args.report)
    print(f'{len(report["cells"])} grouped meshes passed offline preflight: {args.report}')


if __name__ == "__main__":
    main()
