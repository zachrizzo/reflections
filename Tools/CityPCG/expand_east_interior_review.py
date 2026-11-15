"""Recover and model one previously screened east-interior block offline.

The source, overlay and available neighbors must match the existing survey.
Outputs are review-only and never replace the Unreal tile or collision.
"""

import ctypes
import hashlib
import json
from pathlib import Path
import re
import sys

from audit_whole_building_rollout import require_cumulative, tile_metadata, validate_mask
from build_grouped_tile_derivatives import TRAIN_HEADER, require_train_not_building, require_unleased_editor
from combine_replacement_candidates import combine
import export_north_market_detail_obj as obj_export
from import_grouped_buildings_unreal import memory_headroom
from plan_replacement_block import plan as make_plan
import preflight_north_market_details as detail
from select_whole_building_blocks import portable_group
from verify_north_market_detail_obj import audit_obj


ROOT = Path(__file__).resolve().parents[2]
SAVED = ROOT / "Saved"
SURVEY = SAVED / "CityPCG/MedievalSurvey"
DESTINATION = SAVED / "CityPCG/WholeBuildingExpansion_269eb22dac5f_codex_20261115"
GROUP = "block_269eb22dac5f"
TILE = "Tile_p04_p00"
MIN_PHYSICAL = int(2.5 * 1024 ** 3)
MIN_COMMIT = int(6.5 * 1024 ** 3)
MIN_LOADED_TRAIN = 21
SOURCE = SURVEY / f"{TILE}.glb"
METADATA = SURVEY / f"{TILE}.assets.json"
OVERLAY = SURVEY / f"AnonymousShops_{TILE}.glb"
SCREENING = SURVEY / f"{TILE}_next_building_blocks.json"
INVENTORY = SURVEY / f"{TILE}_building_inventory.json"
PREVIOUS = SURVEY / "rollout_18_buildings_20261115.json"
SETTINGS = ROOT / "ArtDirection/CityPCG/MedievalOpening/east_tower_whole_building_blocks_settings.json"
NEIGHBORS = {
    "Tile_p03_p00": SAVED / "CityPCG/Tile_p03_p00.glb",
    "Tile_p03_p01": SURVEY / "Tile_p03_p01.glb",
}
CODE_INPUTS = set(obj_export.CODE_INPUTS) | {
    Path(__file__).resolve(), ROOT / "Tools/CityPCG/select_whole_building_blocks.py",
    ROOT / "Tools/CityPCG/plan_replacement_block.py", ROOT / "Tools/CityPCG/plan_whole_building_replacements.py",
    ROOT / "Tools/CityPCG/audit_whole_building_rollout.py", ROOT / "Tools/CityPCG/combine_replacement_candidates.py",
    ROOT / "Tools/CityPCG/verify_north_market_detail_obj.py",
}


def editor_process_running():
    """Check the existing Windows process list without starting the editor."""
    if sys.platform != "win32":
        raise RuntimeError("Cannot verify the shared Windows editor process on this platform.")
    from ctypes import wintypes

    class ProcessEntry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = (wintypes.HANDLE, ctypes.POINTER(ProcessEntry))
    kernel.Process32FirstW.restype = wintypes.BOOL
    kernel.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(ProcessEntry))
    kernel.Process32NextW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise RuntimeError("Cannot inspect the shared editor process.")
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        found = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        if not found:
            raise RuntimeError("Cannot enumerate the shared editor processes.")
        while found:
            if entry.szExeFile.casefold() == "unrealeditor.exe":
                return True
            found = kernel.Process32NextW(snapshot, ctypes.byref(entry))
        return False
    finally:
        kernel.CloseHandle(snapshot)


def require_loaded_editor():
    """Require the leading train to have returned to the running editor."""
    try:
        with (SAVED / "PIE_QUEUE.md").open("r", encoding="utf-8-sig") as queue:
            for line in queue:
                match = TRAIN_HEADER.match(line)
                if match:
                    state = re.match(r"\s*:?\s*([A-Za-z_]+)\b", match.group(2))
                    if int(match.group(1)) < MIN_LOADED_TRAIN or state is None or state.group(1).upper() != "LOADED":
                        raise RuntimeError(f"Wait for train #{MIN_LOADED_TRAIN} or later to report LOADED.")
                    if re.search(r"\b(others?\s+wait|reserv\w*|proof\s+round|npc-unify|restart\w*)\b",
                                 line, re.IGNORECASE):
                        raise RuntimeError("The leading queue status reserves the editor window; others must wait.")
                    if not editor_process_running():
                        raise RuntimeError("The shared editor has not returned; defer this offline stage.")
                    return
    except (OSError, UnicodeError) as error:
        raise RuntimeError("Cannot read the shared editor queue.") from error
    raise RuntimeError("Cannot determine whether the current train is loaded.")


def guard():
    """Recheck shared resources immediately before each bounded work stage."""
    require_unleased_editor()
    require_train_not_building()
    require_loaded_editor()
    physical, commit = memory_headroom()
    if physical < MIN_PHYSICAL or commit < MIN_COMMIT:
        raise RuntimeError(f"Insufficient headroom: {physical / 1024 ** 3:.2f} GiB physical, "
                           f"{commit / 1024 ** 3:.2f} GiB commit; defer this offline stage.")
    return physical, commit


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def expand(destination=DESTINATION):
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError("Choose a fresh output folder under this project's Saved directory.")
    destination = destination.resolve()
    if not destination.is_relative_to(SAVED.resolve()) or destination == SAVED.resolve() or destination.exists():
        raise ValueError("Choose a fresh output folder under this project's Saved directory.")
    guard()
    screening, inventory, metadata, previous = map(read_json, (SCREENING, INVENTORY, METADATA, PREVIOUS))
    if (screening.get("tile") != TILE or inventory.get("tile") != TILE or
            previous.get("status") != "offline_only" or previous.get("requested_mask_failures") or
            previous.get("requested_pin_failures") or digest(SOURCE) != screening.get("source_export_sha256") or
            digest(SOURCE) != inventory.get("source_sha256") or digest(OVERLAY) != screening.get("overlay_export_sha256")):
        raise ValueError("Screening, inventory, baseline, source tile or overlay differ from reviewed inputs.")
    pins = {row["tile"]: row["source_sha256"] for row in screening["reviewed_neighbor_tiles"]}
    if pins.keys() != NEIGHBORS.keys() or any(digest(NEIGHBORS[tile]) != sha for tile, sha in pins.items()):
        raise ValueError("The available neighboring exports differ from the original screening pins.")
    group = next((row for row in screening["connected_groups"] if row["id"] == GROUP), None)
    if group is None or len(group["members"]) != 2:
        raise ValueError("The previously screened two-building block was not found.")
    old = previous["cumulative_masks"][TILE]
    if set(group["members"]) & {row["id"] for mask in previous["cumulative_masks"].values()
                                for row in mask["buildings"]}:
        raise ValueError("The new group overlaps an existing 18-building rollout candidate.")
    input_files = [SOURCE, METADATA, OVERLAY, SCREENING, INVENTORY, PREVIOUS, SETTINGS,
                   *NEIGHBORS.values(), *sorted(CODE_INPUTS)]
    input_hashes = {path.relative_to(ROOT).as_posix(): digest(path) for path in input_files}
    guard()
    candidate = portable_group(screening, GROUP, metadata, SOURCE)
    destination.mkdir(exist_ok=False)
    candidate_path = destination / "east_interior_candidate.json"
    write_json(candidate_path, candidate)
    print("Verified and saved the two source-backed building candidates", flush=True)

    guard()
    planned = make_plan(SOURCE, candidate_path)
    plan_path = destination / "east_interior_plan.json"
    write_json(plan_path, planned)
    print("Rechecked the candidate road link and built the source geometry plan", flush=True)

    guard()
    cumulative = combine([old, candidate])
    require_cumulative({TILE: old}, {TILE: cumulative})
    selected = validate_mask(SOURCE, tile_metadata(METADATA), cumulative)
    write_json(destination / "p04_p00_six_building_cumulative_mask.json", cumulative)
    print("Verified the complete six-building tile mask against source face signatures", flush=True)

    guard()
    generator = detail.load_generator()
    import build_mark_lane as mark_lane
    records = {item["id"]: item for item in candidate["buildings"]}
    party = generator.paired_edges(planned)
    roles, palette, models, model_failures = set(), {}, {}, {}
    for row in planned["buildings"]:
        guard()
        key = row["id"]
        detail_record = records[key]
        from build_north_market_massing import verify_record
        verify_record(detail_record, row)
        try:
            bay, outline, profile, style, axis_x, axis_y, stacks = generator.from_plan(
                detail_record, row, planned["styles"][key], party.get(key, set()))
        except ValueError as error:
            model_failures[key] = str(error)
            print(f"Detailed generation requires review for {key}: {error}", flush=True)
            continue
        name = f'SM_GLMedieval_EastInterior_{style.name}_{key.rsplit("_", 1)[-1][:8]}.obj'
        path = destination / name
        uv_count = obj_export.write_obj(path, bay, mark_lane.PALETTE)
        checked = audit_obj(path, bay, mark_lane.PALETTE)
        if uv_count != checked["uv_corners"]:
            raise RuntimeError(f"UV readback changed for {name}")
        roles.update(bay.roles)
        palette.update({role: mark_lane.PALETTE[role] for role in bay.roles})
        models[key] = {"file": name, "sha256": digest(path), "style": style.name,
                       "world_pivot_m": row["origin_m"], "yaw_deg": row["rotation_yaw_deg"],
                       "axis_x_world_xy": tuple(axis_x), "axis_y_world_xy": tuple(axis_y),
                       "roof_profile_local_y_z_m": profile, "chimney_count": len(stacks),
                       "geometry_readback": checked}
        del bay
        print(f"Generated and independently read back {name}", flush=True)

    guard()
    textures = {}
    for role in sorted(roles):
        if mark_lane.PALETTE[role][2]:
            folder = ("ArtDirection/CityPCG/MedievalOpening/Guildhall/Textures" if role == "GuildRubble"
                      else "ArtDirection/CityPCG/MedievalOpening/Textures")
            path = ROOT / folder / f"T_GLMedieval_{role}.png"
            with path.open("rb") as stream:
                if stream.read(8) != b"\x89PNG\r\n\x1a\n":
                    raise ValueError(f"Invalid texture for {role}")
            textures[role] = {"path": path.relative_to(ROOT).as_posix(), "sha256": digest(path)}
    material = obj_export.write_materials(destination, palette, roles, textures)
    obj_export.verify_materials(material, palette, roles, textures)
    if any(digest(ROOT / path) != expected for path, expected in input_hashes.items()):
        raise RuntimeError("A pinned source input changed during the offline survey; leave the output for review.")
    report = {
        "status": "unreviewed_detailed_obj_source" if models else "offline_candidates_without_source_models",
        "runtime_activation_eligible": False,
        "source_ue_section_mapping": "unverified", "survey_group": GROUP, "source_tile": TILE,
        "source_inputs_sha256": input_hashes,
        "candidate": candidate_path.name, "candidate_sha256": digest(candidate_path),
        "plan": plan_path.name, "plan_sha256": digest(plan_path),
        "prior_rollout_buildings": sum(len(mask["buildings"]) for mask in previous["cumulative_masks"].values()),
        "new_candidate_buildings": len(candidate["buildings"]), "new_model_buildings": len(models),
        "model_generation_failures": model_failures,
        "candidate_total_buildings": (sum(len(mask["buildings"]) for mask in previous["cumulative_masks"].values()) +
                                      len(candidate["buildings"])),
        "p04_cumulative_buildings": len(cumulative["buildings"]),
        "p04_removed_source_triangles_by_metadata_slot": selected,
        "matches_existing_grouped_meshes": False,
        "material_file": material.name, "material_sha256": digest(material), "textures": textures,
        "models": models,
        "limits": ["Prior report screens were inherited, not rerun; its historical settings hash was not recorded.",
                   "Current live actor bounds and site-specific protection were not reviewed.",
                   "Missing neighboring tile exports and GLB-to-Unreal section identity are not verified.",
                   "Python math/tessellation shims differ from Blender; OBJ winding is not recalculated.",
                   "No FBX, Unreal import, collision, navigation, story, streaming or gameplay checks were run.",
                   "The six-building p04 mask is incompatible with the current four-building grouped meshes."]}
    write_json(destination / "east_interior_source_manifest.json", report)
    with (destination / "README.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("# East-interior whole-building source review\n\n")
        stream.write(f"Offline group `{GROUP}` contributes {len(candidate['buildings'])} surveyed footprints; "
                     f"{len(models)} detailed OBJ source models were generated. The JSON manifest records "
                     "source hashes, local-to-world pivots and axes, texture roles and geometry readback.\n\n")
        stream.write("The inherited selector report was not rerun, and current authored actor bounds remain "
                     "unverified. Meshes use a Python math/tessellation shim; their source winding, n-gon "
                     "triangulation and UVs require Blender review. No collision or Unreal validation was run. "
                     "The complete six-building tile mask does not match the current four-building grouped kit. "
                     "Do not replace the original tile until the source-section identity, complete grouped "
                     "cells, navigation, story routes, streaming and rollback have been verified.\n")
    return report


if __name__ == "__main__":
    result = expand()
    print(f'Completed {result["new_model_buildings"]} review-only detailed building sources: {DESTINATION}')
