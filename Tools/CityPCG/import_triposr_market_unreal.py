"""Draft single-prop Unreal importer; no editor calls happen on module import.

Run only from the lease-owning editor session after the raw image-to-3D source
has been visually reviewed and its exact SHA-256 independently verified.
"""

import hashlib
import json
import math
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import time

from triposr_market_geometry import (ASSET_ROOT, LEVEL, MAX_BYTES, TARGET_LONGEST_CM,
                                    compare_glb, normalize_z_up_glb, parse_glb)
from triposr_market_sources import preserve_normalized


PROJECT = Path(__file__).resolve().parents[2]
SAVED = PROJECT / "Saved"
SOURCE_DIR = SAVED / "CityPCG" / "TripoSRMarketSources"
OWNER = "codex-gray-london"
PURPOSE = "Dense Medieval London streets and dressing"
MIN_LEASE_SECONDS = 60


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_path(kind, expected_sha):
    if kind not in TARGET_LONGEST_CM or not re.fullmatch(r"[0-9a-f]{64}", expected_sha or ""):
        raise ValueError("Expected a known prop kind and an independently verified SHA-256")
    path = SOURCE_DIR / (kind + ".glb")
    # Reject Windows reparse points as well as ordinary symlinks, without
    # following them first. Only this fixed Saved subdirectory is accepted.
    for part in (SAVED, SAVED / "CityPCG", SOURCE_DIR, path):
        st = part.lstat()
        if part.is_symlink() or (getattr(st, "st_file_attributes", 0) & 0x400):
            raise ValueError("Source path contains a link or junction")
    if not path.is_file() or not 28 <= path.stat().st_size <= MAX_BYTES or sha256(path) != expected_sha:
        raise ValueError("Source GLB does not match the reviewed size and digest")
    return path


def lease_check(unreal, previous=None):
    project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
    if project != PROJECT:
        raise RuntimeError("The editor uses a different checkout")
    try:
        lease = json.loads((SAVED / "PIE_LOCK.json").read_text(encoding="utf-8-sig"))
        seconds = float(lease["expires_epoch"]) - time.time()
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise RuntimeError("Cannot verify the explicit authoring lease") from error
    if (lease.get("owner") != OWNER or lease.get("purpose") != PURPOSE or
            not math.isfinite(seconds) or seconds < MIN_LEASE_SECONDS or
            (previous is not None and lease != previous)):
        raise RuntimeError("The original market authoring lease is missing or changed")
    subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = subsystem.get_editor_world()
    if (not world or world.get_path_name().split(".")[0] != LEVEL or subsystem.get_game_world() or
            unreal.EditorLevelLibrary.get_pie_worlds(True)):
        raise RuntimeError("Open MedievalLondon with PIE stopped before authoring")
    if (unreal.MultiUserClientStatics.get_multi_user_connection_status_detail() ==
            unreal.MultiUserConnectionStatus.CONNECTED):
        raise RuntimeError("This draft requires the editor outside a Multi-User session")
    return lease


def asset_package(kind):
    if kind not in TARGET_LONGEST_CM:
        raise ValueError("Unknown prop")
    return f"{ASSET_ROOT}/Meshes/SM_GLMarket_{kind}"


def material_package(kind):
    if kind not in TARGET_LONGEST_CM:
        raise ValueError("Unknown prop")
    return f"{ASSET_ROOT}/Materials/M_GLMarket_VertexColor_{kind}"


def assert_absent(unreal, package):
    if not package.startswith(ASSET_ROOT + "/"):
        raise ValueError("Unexpected package outside the owned market directory")
    path = PROJECT / "Content" / (package.removeprefix("/Game/") + ".uasset")
    if path.exists() or unreal.EditorAssetLibrary.does_asset_exist(package) or unreal.find_package(package):
        raise FileExistsError(f"Refusing to overwrite {package}")


def make_material(unreal, kind):
    package = material_package(kind)
    destination, name = package.rsplit("/", 1)
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, destination, unreal.Material, unreal.MaterialFactoryNew())
    if not isinstance(material, unreal.Material) or material.get_package().get_name() != package:
        raise RuntimeError("Did not create the exact owned material")
    material.set_editor_property("used_with_instanced_static_meshes", True)
    edit = unreal.MaterialEditingLibrary
    color = edit.create_material_expression(material, unreal.MaterialExpressionVertexColor, -400, -100)
    rough = edit.create_material_expression(material, unreal.MaterialExpressionConstant, -400, 100)
    metal = edit.create_material_expression(material, unreal.MaterialExpressionConstant, -400, 220)
    if not all((color, rough, metal)):
        raise RuntimeError("Failed to create material expressions")
    rough.set_editor_property("r", .8)
    metal.set_editor_property("r", 0.)
    if not (edit.connect_material_property(color, "", unreal.MaterialProperty.MP_BASE_COLOR) and
            edit.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS) and
            edit.connect_material_property(metal, "", unreal.MaterialProperty.MP_METALLIC)):
        raise RuntimeError("Failed to connect the vertex-color material")
    errors = edit.recompile_material(material)
    if errors:
        raise RuntimeError(f"Material compilation failed: {errors}")
    return material


def options(unreal, *, has_normals):
    # Based on the existing replacement-tile importer, with colour explicitly
    # required rather than trusting the Interchange default.
    from import_replacement_tile_unreal import import_options
    pipeline, stack = import_options(unreal)
    pipeline.get_editor_property("common_meshes_properties").set_editor_properties({
        "vertex_color_import_option": unreal.InterchangeVertexColorImportOption.IVCIO_REPLACE,
        # TripoSR's first candidate has no normal stream. Let Unreal generate
        # lighting normals in that case; do not pretend they were authored.
        "recompute_normals": not has_normals,
        "recompute_tangents": not has_normals,
    })
    return pipeline, stack


def compare_unreal(unreal, mesh, raw):
    scratch = SAVED / "CityPCG" / "TripoSRMarketRoundtrip"
    scratch.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="import_", dir=scratch) as folder:
        output = Path(folder) / "mesh.glb"
        settings = unreal.GLTFExportOptions()
        settings.set_editor_properties({"bake_material_inputs": unreal.GLTFMaterialBakeMode.DISABLED,
                                        "export_source_model": True, "export_uniform_scale": .01,
                                        "export_vertex_colors": True})
        result = unreal.GLTFExporter.export_to_gltf(mesh, str(output), settings, set())
        if result is None or result.get_editor_property("errors") or not output.is_file():
            raise RuntimeError("The imported mesh could not be exported for colour verification")
        if output.stat().st_size > MAX_BYTES:
            raise RuntimeError("Round-trip GLB exceeds the checked size bound")
        return compare_glb(raw, output.read_bytes())


def prepare_normalized_source(kind, expected_sha256):
    """Recreate/reuse the exact digest-named GLB without opening Unreal."""
    path = source_path(kind, expected_sha256)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise RuntimeError("Source changed during inspection")
    normalized, evidence = normalize_z_up_glb(raw)
    prepared = preserve_normalized(SOURCE_DIR, kind, expected_sha256, normalized)
    return prepared, evidence


def run(kind, expected_sha256, *, source_visually_reviewed=False, axis_conversion=None):
    """Import and explicitly save one new mesh/material pair after strict checks.

    No position is invented, no PCG actor is created, and no existing package
    is replaced. A failure can leave new *unsaved* assets in memory; do not
    remove them until the authoring lease is coordinated.
    """
    import unreal

    if source_visually_reviewed is not True:
        raise ValueError("Review the actual candidate and explicitly acknowledge that review first")
    if axis_conversion != "z_up_to_gltf_y_up":
        raise ValueError("Explicitly confirm the source is Z-up before axis conversion")
    lease = lease_check(unreal)
    path = source_path(kind, expected_sha256)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise RuntimeError("Source changed during inspection")
    source = parse_glb(raw)
    normalized, normalization = normalize_z_up_glb(raw)
    normalized_path = preserve_normalized(SOURCE_DIR, kind, expected_sha256, normalized)
    return _import_normalized(unreal, kind, path, normalized_path, normalized, normalization,
                              source, expected_sha256, lease)


def _import_normalized(unreal, kind, path, normalized_path, normalized, normalization, source, expected_sha256, lease):
    lease_check(unreal, lease)
    mesh_package, mat_package = asset_package(kind), material_package(kind)
    for package in (mesh_package, mat_package):
        assert_absent(unreal, package)
    lease_check(unreal, lease)
    destination, name = mesh_package.rsplit("/", 1)
    editor = unreal.EditorAssetLibrary
    before = set(editor.list_assets(ASSET_ROOT, recursive=True, include_folder=False))
    _pipeline, stack = options(unreal, has_normals=source["has_normals"])
    task = unreal.AssetImportTask()
    task.set_editor_properties({"filename": str(normalized_path), "destination_path": destination,
                                "destination_name": name, "automated": True, "save": False,
                                "replace_existing": False, "options": stack})
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    assets = list(task.get_objects())
    new_paths = set(editor.list_assets(ASSET_ROOT, recursive=True, include_folder=False)) - before
    if (len(assets) != 1 or not isinstance(assets[0], unreal.StaticMesh) or
            assets[0].get_package().get_name() != mesh_package or
            new_paths != {f"{mesh_package}.{name}"}):
        raise RuntimeError(f"Import produced unexpected assets, none saved: {sorted(new_paths)}")
    return _verify_and_save(unreal, kind, assets[0], path, normalized, normalization,
                            source, expected_sha256, lease)


def resume_bakers_tray(*, source_visually_reviewed=False, axis_conversion=None):
    """Finish only the known unsaved BakersTray left by the earlier audit.

    Freshly reexports the live mesh and compares every oriented RGB corner to
    its exact normalized source before touching its material or saving.
    """
    import unreal

    if source_visually_reviewed is not True or axis_conversion != "z_up_to_gltf_y_up":
        raise ValueError("Explicit visual and Z-up review are required")
    kind = "BakersTray"
    expected_sha256 = "ecc804f8ea40c2ba013090e0baedfa77e0055ab846b4854cd99ebeeeb9d26d89"
    lease = lease_check(unreal)
    package = asset_package(kind)
    disk = PROJECT / "Content" / (package.removeprefix("/Game/") + ".uasset")
    if disk.exists():
        raise FileExistsError("This rescue path refuses a mesh already saved on disk")
    assert_absent(unreal, material_package(kind))
    mesh = unreal.EditorAssetLibrary.load_asset(package)
    name = package.rsplit("/", 1)[-1]
    if not isinstance(mesh, unreal.StaticMesh) or mesh.get_path_name() != f"{package}.{name}":
        raise RuntimeError("The exact unsaved BakersTray mesh is not loaded")
    path = source_path(kind, expected_sha256)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise RuntimeError("Source changed during inspection")
    source = parse_glb(raw)
    normalized, normalization = normalize_z_up_glb(raw)
    return _verify_and_save(unreal, kind, mesh, path, normalized, normalization,
                            source, expected_sha256, lease)


def _verify_and_save(unreal, kind, mesh, path, normalized, normalization, source, expected_sha256, lease):
    mesh_package, mat_package = asset_package(kind), material_package(kind)
    if not isinstance(mesh, unreal.StaticMesh) or mesh.get_package().get_name() != mesh_package:
        raise RuntimeError("Expected the exact owned mesh")
    assert_absent(unreal, mat_package)
    mesh_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    if mesh_editor.get_simple_collision_count(mesh) or mesh_editor.get_convex_collision_count(mesh):
        raise RuntimeError("Unexpected simple collision in imported prop")
    if sha256(path) != expected_sha256:
        raise RuntimeError("Source changed during import")
    check = compare_unreal(unreal, mesh, normalized)
    if check["triangles"] != source["triangles"]:
        raise RuntimeError("Round-trip triangle count changed")
    lease_check(unreal, lease)
    material = make_material(unreal, kind)
    sections = mesh.get_num_sections(0)
    if sections < 1 or sections > 16:
        raise RuntimeError("Unexpected section count")
    slots = mesh.get_editor_property("static_materials")
    if len(slots) < sections or len(slots) > 16:
        raise RuntimeError("Unexpected material slots")
    for index in range(len(slots)):
        mesh.set_material(index, material)
    if any(mesh.get_material(index) != material for index in range(len(slots))):
        raise RuntimeError("The vertex-color material is not assigned to every slot")
    mesh.set_editor_property("has_navigation_data", False)
    bounds = mesh.get_bounds()
    origin, extent = bounds.origin, bounds.box_extent
    box = [[origin.x - extent.x, origin.y - extent.y, origin.z - extent.z],
           [origin.x + extent.x, origin.y + extent.y, origin.z + extent.z]]
    if any(not math.isfinite(float(value)) for row in box for value in row) or any(
            hi <= lo for lo, hi in zip(*box)):
        raise RuntimeError("Invalid imported local bounds")
    lease_check(unreal, lease)
    packages = [material.get_package(), mesh.get_package()]
    names = [p.get_name() for p in packages]
    if names != [mat_package, mesh_package]:
        raise RuntimeError("Unexpected save targets")
    if not unreal.EditorLoadingAndSavingUtils.save_packages(packages, only_dirty=False):
        raise RuntimeError(f"Explicit save failed; inspect these owned packages for partial writes: {names}")
    return {"status": "imported_color_roundtrip_only", "kind": kind, "local_bounds_cm": box,
            "axis_normalization": normalization, "authored_normals": source["has_normals"],
            "color_check": check, "saved_packages": names,
            "remaining": "Review appearance, orientation, scale, placement and collision in Unreal/PIE."}
