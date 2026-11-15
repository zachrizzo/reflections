"""Build a bounded offline batch from complete, previously screened groups.

This consumes measured source geometry and produces review-only OBJ source art.
It never places actors, changes map packages or authorizes a runtime swap.
"""

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re

from audit_whole_building_rollout import require_cumulative, tile_metadata, validate_mask
import build_screened_worklist as worklist
from combine_replacement_candidates import combine
import export_north_market_detail_obj as obj_export
from plan_replacement_block import plan as make_plan
import preflight_north_market_details as detail
from select_whole_building_blocks import portable_group
from verify_north_market_detail_obj import audit_obj
from verify_west_mark_lane_saved_geometry import Guard


ROOT = Path(__file__).resolve().parents[2]
SAVED = ROOT / "Saved"
CITY = SAVED / "CityPCG"
SURVEY = CITY / "MedievalSurvey"
BATCHES = CITY / "ReviewedWholeBuildingBatches"
DEFAULT_WORKLIST = SURVEY / "screened_worklist_from_snapshot_20261115_codex_v2.json"
SOURCES = {
    "Tile_p03_p00": (CITY / "Tile_p03_p00.glb", CITY / "Tile_p03_p00.asset.json",
                     CITY / "AnonymousShops_Tile_p03_p00.glb"),
    "Tile_p03_p01": (SURVEY / "Tile_p03_p01.glb", SURVEY / "Tile_p03_p01.assets.json",
                     SURVEY / "AnonymousShops_Tile_p03_p01.glb"),
    "Tile_p04_p00": (SURVEY / "Tile_p04_p00.glb", SURVEY / "Tile_p04_p00.assets.json",
                     SURVEY / "AnonymousShops_Tile_p04_p00.glb"),
}
MAX_MODELS = 4
CODE_INPUTS = set(obj_export.CODE_INPUTS) | {
    Path(__file__).resolve(), ROOT / "Tools/CityPCG/build_screened_worklist.py",
    ROOT / "Tools/CityPCG/select_whole_building_blocks.py", ROOT / "Tools/CityPCG/plan_replacement_block.py",
    ROOT / "Tools/CityPCG/plan_whole_building_replacements.py", ROOT / "Tools/CityPCG/audit_whole_building_rollout.py",
    ROOT / "Tools/CityPCG/combine_replacement_candidates.py", ROOT / "Tools/CityPCG/verify_north_market_detail_obj.py",
    ROOT / "Tools/CityPCG/verify_west_mark_lane_saved_geometry.py",
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def project_input(path):
    original = Path(path)
    resolved = original.resolve(strict=True)
    if original.is_symlink() or not resolved.is_relative_to(ROOT) or not resolved.is_file():
        raise ValueError("Inputs must be regular files inside the current project")
    return resolved


def write_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def pinned_hash(path, check):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(256 * 1024)
            if not chunk:
                break
            check()
            result.update(chunk)
    return result.hexdigest()


def completed_baseline(path, check):
    """Accept continuation only from a finished batch with its pinned mask."""
    baseline = project_input(path)
    root = BATCHES.resolve(strict=True)
    if (BATCHES.is_symlink() or getattr(BATCHES, "is_junction", lambda: False)() or root != BATCHES or
            baseline.name != "next_rollout_baseline.json" or baseline.parent.parent != root):
        raise ValueError("A later baseline must come directly from a completed reviewed batch")
    manifest = project_input(baseline.parent / "batch_manifest.json")
    before = pinned_hash(manifest, check)
    previous = read_json(manifest)
    if (previous.get("status") != "unreviewed_detailed_obj_source" or
            previous.get("runtime_activation_eligible") is not False or
            previous.get("next_baseline_sha256") != pinned_hash(baseline, check) or
            pinned_hash(manifest, check) != before):
        raise ValueError("The preceding batch is incomplete or its baseline hash changed")
    return baseline, manifest


def select_groups(document, tile, identifiers, baseline):
    """Never silently split mixed, oversized, missing or already-used groups."""
    if (document.get("status") != "offline_review_worklist_only" or
            document.get("runtime_activation_eligible") is not False or tile not in SOURCES or
            not identifiers or len(identifiers) != len(set(identifiers))):
        raise ValueError("Select distinct screened groups for one known review-only tile")
    if (baseline.get("status") != "offline_only" or baseline.get("requested_mask_failures") or
            baseline.get("requested_pin_failures") or tile not in baseline["cumulative_masks"]):
        raise ValueError("An intact offline cumulative rollout baseline is required")
    used = {row["id"] for mask in baseline["cumulative_masks"].values() for row in mask["buildings"]}
    choices = [row for row in document["connected_groups"] if row["tile"] == tile and row["source_group_id"] in identifiers]
    if len(choices) != len(identifiers):
        raise ValueError("A requested group is not an unused connected group in this tile's worklist")
    selected, total = set(), 0
    for row in choices:
        ids = [item["id"] for item in row["new_buildings"]]
        components = row["new_connected_components"]
        if (row["status"] != "offline_screened_needs_revalidation" or row["group_has_baseline_or_conflicting_members"] or
                row["baseline_members"] or row["conflicting_members"] or len(ids) < 2 or len(ids) != len(set(ids)) or
                set(ids) != set(row["original_members"]) or selected & set(ids) or used & set(ids) or
                len(components) != 1 or set(components[0]["building_ids"]) != set(ids) or
                components[0]["requires_new_connectivity_evidence"] is not False or
                components[0]["requires_current_road_revalidation"] is not True or
                components[0]["exceeds_four_model_batch"] is not False or
                len(worklist.components(set(ids), components[0]["retained_street_links"])) != 1):
            raise ValueError(f'{row["source_group_id"]}: mixed, disconnected, oversized or already used; re-review first')
        selected.update(ids)
        total += len(ids)
    if total > MAX_MODELS:
        raise ValueError(f"At most {MAX_MODELS} models per guarded batch; choose fewer complete groups")
    return sorted(choices, key=lambda row: row["source_group_id"])


def fresh_destination(name):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name):
        raise ValueError("Batch name must be a simple ASCII basename")
    current = ROOT
    for part in ("Saved", "CityPCG", "ReviewedWholeBuildingBatches"):
        child = current / part
        if not os.path.lexists(child):
            child.mkdir()
        if child.is_symlink() or getattr(child, "is_junction", lambda: False)() or child.resolve(strict=True) != child:
            raise ValueError("Batch parent is redirected")
        current = child
    destination = current / name
    if os.path.lexists(destination) or destination.resolve().parent != current:
        raise FileExistsError("Choose a fresh batch folder; existing work is never overwritten")
    destination.mkdir()
    return destination


def verified_worklist(path):
    """Recompute the entire pinned snapshot worklist before selecting jobs."""
    index = worklist.checked_snapshot()
    baseline, baseline_input = worklist.read_input(worklist.PREVIOUS)
    pairs = {tile: worklist.read_input(source) for tile, source in worklist.REPORTS.items()}
    result = worklist.make_worklist(baseline, {tile: pair[0] for tile, pair in pairs.items()},
                                    {"baseline": baseline_input, **{tile: pair[1] for tile, pair in pairs.items()}})
    result["review_snapshot_manifest"] = index
    if read_json(path) != result:
        raise ValueError("Worklist differs from the current pinned review snapshot")
    return result, baseline, {tile: pair[0] for tile, pair in pairs.items()}


def run(tile, group_ids, batch_name, worklist_path=DEFAULT_WORKLIST, baseline_path=None):
    guard = Guard()  # Requires loaded/unreserved editor, no lease, and 4/10 GiB headroom.
    check = guard.check  # Checks leases on every call; throttles expensive full probes.
    stage = lambda: guard.check(force=True)
    stage()
    worklist_path = project_input(worklist_path)
    if tile not in SOURCES:
        raise ValueError("Unknown source tile")
    source, metadata_path, overlay = SOURCES[tile]
    previous_manifest_path = None
    if baseline_path is not None:
        baseline_path, previous_manifest_path = completed_baseline(baseline_path, check)
    input_paths = {worklist_path, baseline_path or worklist.PREVIOUS, source, metadata_path, overlay,
                   worklist.SNAPSHOT_MANIFEST, worklist.PREVIOUS, *worklist.REPORTS.values(),
                   *(row[0] for row in SOURCES.values()), *CODE_INPUTS}
    if previous_manifest_path is not None:
        input_paths.add(previous_manifest_path)
    input_hashes = {path.relative_to(ROOT).as_posix(): pinned_hash(path, check) for path in sorted(input_paths)}
    if baseline_path is not None:
        previous_manifest = read_json(previous_manifest_path)
        if (previous_manifest.get("status") != "unreviewed_detailed_obj_source" or
                previous_manifest.get("runtime_activation_eligible") is not False or
                previous_manifest.get("next_baseline_sha256") != input_hashes[baseline_path.relative_to(ROOT).as_posix()]):
            raise ValueError("The preceding batch is incomplete or its baseline hash changed")
    document, original_baseline, reports = verified_worklist(worklist_path)
    latest_baseline = read_json(baseline_path) if baseline_path else original_baseline
    require_cumulative(original_baseline["cumulative_masks"], latest_baseline["cumulative_masks"])
    choices = select_groups(document, tile, group_ids, latest_baseline)
    report = reports[tile]
    metadata = read_json(metadata_path)
    if (input_hashes[source.relative_to(ROOT).as_posix()] != report["source_export_sha256"] or
            input_hashes[overlay.relative_to(ROOT).as_posix()] != report["overlay_export_sha256"]):
        raise ValueError("The source tile or overlay differs from the reviewed screening pin")
    for neighbor in report["reviewed_neighbor_tiles"]:
        name = neighbor["tile"]
        if name not in SOURCES or input_hashes[SOURCES[name][0].relative_to(ROOT).as_posix()] != neighbor["source_sha256"]:
            raise ValueError("An available neighbor differs from its screening pin")
    if any(pinned_hash(ROOT / name, check) != expected for name, expected in input_hashes.items()):
        raise RuntimeError("An input changed during preflight; no batch was created")
    stage()
    destination = fresh_destination(batch_name)
    old_mask = latest_baseline["cumulative_masks"][tile]
    candidates, candidate_paths, plans = [], [], []
    for choice in choices:
        stage()
        identifier = choice["source_group_id"]
        candidate = portable_group(report, identifier, metadata, source)
        path = destination / f"{identifier}_candidate.json"
        write_json(path, candidate)
        candidates.append(candidate)
        candidate_paths.append(path)
        stage()
        planned = make_plan(source, path)
        write_json(destination / f"{identifier}_plan.json", planned)
        plans.append(planned)
    stage()
    cumulative = combine([old_mask, *candidates])
    require_cumulative({tile: old_mask}, {tile: cumulative})
    removed = validate_mask(source, tile_metadata(metadata_path), cumulative)
    write_json(destination / f"{tile}_cumulative_mask.json", cumulative)
    next_baseline = deepcopy(latest_baseline)
    next_baseline["cumulative_masks"][tile] = cumulative
    if tile in next_baseline.get("tile_inventory", {}):
        next_baseline["tile_inventory"][tile]["offline_mask_buildings"] = len(cumulative["buildings"])
        next_baseline["tile_inventory"][tile]["offline_mask_face_counts"] = removed
    next_baseline["note"] = "Offline cumulative source masks only; no live replacement is authorized."
    stage()
    generator = detail.load_generator()
    import build_mark_lane as mark_lane
    from build_north_market_massing import verify_record
    roles, palette, models = set(), {}, {}
    for candidate, planned in zip(candidates, plans):
        records = {item["id"]: item for item in candidate["buildings"]}
        party = generator.paired_edges(planned)
        for row in planned["buildings"]:
            stage()
            key = row["id"]
            verify_record(records[key], row)
            bay, outline, profile, style, axis_x, axis_y, stacks = generator.from_plan(
                records[key], row, planned["styles"][key], party.get(key, set()))
            name = f'SM_GLMedieval_{tile}_{style.name}_{key.rsplit("_", 1)[-1][:8]}.obj'
            path = destination / name
            written = obj_export.write_obj(path, bay, mark_lane.PALETTE)
            checked = audit_obj(path, bay, mark_lane.PALETTE)
            if checked["uv_corners"] != written:
                raise RuntimeError(f"UV readback differs for {name}")
            roles.update(bay.roles)
            palette.update({role: mark_lane.PALETTE[role] for role in bay.roles})
            models[key] = {"file": name, "sha256": pinned_hash(path, check), "style": style.name,
                           "world_pivot_m": row["origin_m"], "yaw_deg": row["rotation_yaw_deg"],
                           "axis_x_world_xy": tuple(axis_x), "axis_y_world_xy": tuple(axis_y),
                           "roof_profile_local_y_z_m": profile, "chimney_count": len(stacks),
                           "geometry_readback": checked}
            del bay
    stage()
    textures = {}
    for role in sorted(roles):
        if palette[role][2]:
            folder = ("ArtDirection/CityPCG/MedievalOpening/Guildhall/Textures" if role == "GuildRubble"
                      else "ArtDirection/CityPCG/MedievalOpening/Textures")
            path = ROOT / folder / f"T_GLMedieval_{role}.png"
            with path.open("rb") as stream:
                if stream.read(8) != b"\x89PNG\r\n\x1a\n":
                    raise ValueError(f"Invalid source texture for {role}")
            textures[role] = {"path": path.relative_to(ROOT).as_posix(), "sha256": pinned_hash(path, check)}
            input_hashes[textures[role]["path"]] = textures[role]["sha256"]
    material = obj_export.write_materials(destination, palette, roles, textures)
    obj_export.verify_materials(material, palette, roles, textures)
    stage()
    if any(pinned_hash(ROOT / name, check) != expected for name, expected in input_hashes.items()):
        raise RuntimeError("An input changed during batch; leave incomplete output for review")
    write_json(destination / "next_rollout_baseline.json", next_baseline)
    manifest = {"status": "unreviewed_detailed_obj_source", "runtime_activation_eligible": False,
                "source_ue_section_mapping": "unverified", "tile": tile,
                "source_export_sha256": report["source_export_sha256"],
                "overlay_export_sha256": report["overlay_export_sha256"],
                "worklist_sha256": pinned_hash(Path(worklist_path), check),
                "input_sha256": input_hashes,
                "selected_groups": [row["source_group_id"] for row in choices],
                "candidate_files": [{"candidate": path.name, "candidate_sha256": pinned_hash(path, check),
                                     "plan": f'{candidate["name"]}_plan.json',
                                     "plan_sha256": pinned_hash(destination / f'{candidate["name"]}_plan.json', check)}
                                    for path, candidate in zip(candidate_paths, candidates)],
                "cumulative_mask": f"{tile}_cumulative_mask.json",
                "cumulative_mask_sha256": pinned_hash(destination / f"{tile}_cumulative_mask.json", check),
                "next_baseline": "next_rollout_baseline.json",
                "next_baseline_sha256": pinned_hash(destination / "next_rollout_baseline.json", check),
                "baseline_buildings": len(old_mask["buildings"]),
                "cumulative_buildings": len(cumulative["buildings"]), "source_triangles_by_slot": removed,
                "matches_existing_grouped_meshes": False, "material_file": material.name,
                "material_sha256": pinned_hash(material, check), "textures": textures, "models": models,
                "limits": ["Historic screening and actor/protection data must be refreshed before accepting a block.",
                           "Missing adjacent tile exports and live Unreal primitive/section mapping are not proven.",
                           "Python math/tessellation shim is not Blender; no FBX, collision or gameplay validation.",
                           "The new cumulative mask needs exact matching complete grouped meshes before any tile swap."]}
    write_json(destination / "batch_manifest.json", manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tile", required=True, choices=sorted(SOURCES))
    parser.add_argument("--group", action="append", required=True, help="Complete unused group; repeat to batch up to 4 models")
    parser.add_argument("--batch", required=True, help="Fresh output folder basename")
    parser.add_argument("--worklist", type=Path, default=DEFAULT_WORKLIST)
    parser.add_argument("--baseline", type=Path, help="Latest complete offline rollout baseline from a previous batch")
    args = parser.parse_args()
    result = run(args.tile, args.group, args.batch, args.worklist, args.baseline)
    print(f'Built {len(result["models"])} unreviewed detailed source meshes in {BATCHES / args.batch}')


if __name__ == "__main__":
    main()
