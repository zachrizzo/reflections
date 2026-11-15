"""Create independently checked city-tile filters for the grouped buildings.

The checked-in group manifest owns the baseline 6/4/4 masks. Optional additional
offline candidates produce a separate, explicitly incompatible future variant;
they never change the baseline output or the original tile assets.
"""

import argparse
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from tempfile import mkdtemp
import time

from audit_whole_building_rollout import tile_metadata, validate_mask
from combine_replacement_candidates import SOURCE_FIELDS, combine
from extract_tile_frontages import read_glb
from group_whole_buildings import PROJECT_ROOT, mask_sha
from import_grouped_buildings_unreal import memory_headroom
from name_replacement_tile_slots import write_import_copy
from subtract_building_shells import indices, read_json, reviewed_faces, subtract


PROJECT = PROJECT_ROOT.resolve()
SAVED = PROJECT / "Saved"
BUNDLE = PROJECT / "ArtDirection/CityPCG/MedievalOpening/WholeBuildings/GroupedPrototype"
DEFAULT_SOURCES = {
    "Tile_p03_p00": (SAVED / "CityPCG/Tile_p03_p00.glb", SAVED / "CityPCG/Tile_p03_p00.asset.json"),
    "Tile_p03_p01": (SAVED / "CityPCG/MedievalSurvey/Tile_p03_p01.glb", SAVED / "CityPCG/MedievalSurvey/Tile_p03_p01.assets.json"),
    "Tile_p04_p00": (SAVED / "CityPCG/MedievalSurvey/Tile_p04_p00.glb", SAVED / "CityPCG/MedievalSurvey/Tile_p04_p00.assets.json"),
}
MIN_PHYSICAL_BYTES = 4 * 1024 ** 3
MIN_COMMIT_BYTES = 10 * 1024 ** 3
TRAIN_HEADER = re.compile(r"^\s*!*\s*(?:\d{1,2}:\d{2}\s+)?TRAIN\s*#\s*(\d+)\b(.*)$", re.IGNORECASE)
TRAIN_IDLE_STATUSES = {"LOADED", "BUILT", "DONE", "COMPLETE", "COMPLETED", "FAILED", "CANCELLED", "CANCELED"}


def file_sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def relative(path):
    path = path.resolve()
    if not path.is_relative_to(PROJECT):
        raise ValueError(f"Input is outside this project: {path}")
    return path.relative_to(PROJECT).as_posix()


def require_memory():
    physical, commit = memory_headroom()
    if physical < MIN_PHYSICAL_BYTES or commit < MIN_COMMIT_BYTES:
        raise RuntimeError(f"Tile filtering needs 4 GiB physical and 10 GiB system commit headroom; "
                           f"available {physical / 1024 ** 3:.2f} / {commit / 1024 ** 3:.2f} GiB.")


def require_unleased_editor():
    path = SAVED / "PIE_LOCK.json"
    if not path.exists():
        return
    try:
        lease = read_json(path)
        expiry = float(lease["expires_epoch"])
    except (OSError, TypeError, ValueError, KeyError) as error:
        raise RuntimeError("Cannot verify whether the shared editor lease is active.") from error
    if not math.isfinite(expiry) or expiry > time.time():
        raise RuntimeError("A shared editor session holds the lease; defer tile filtering.")


def require_train_not_building():
    """Use only the first explicit train status, not historical queue entries."""
    try:
        with (SAVED / "PIE_QUEUE.md").open("r", encoding="utf-8-sig") as queue:
            for line in queue:
                header = TRAIN_HEADER.match(line)
                if header is None:
                    continue
                status = re.match(r"\s*:?\s*([A-Za-z_]+)\b", header.group(2))
                if status is None:
                    break
                state = status.group(1).upper()
                if state == "BUILDING":
                    raise RuntimeError(f"Shared editor train #{header.group(1)} is BUILDING; defer tile filtering.")
                if state not in TRAIN_IDLE_STATUSES:
                    raise RuntimeError(f"Unrecognized shared editor train status {state!r}; defer tile filtering.")
                return
    except (OSError, UnicodeError) as error:
        raise RuntimeError("Cannot read the shared editor train queue; defer tile filtering.") from error
    raise RuntimeError("Cannot determine the current shared editor train status; defer tile filtering.")


def require_editor_available():
    require_unleased_editor()
    require_train_not_building()


def mask_buildings(mask):
    rows = mask["buildings"]
    records = {row["id"]: row for row in rows}
    if not records or len(records) != len(rows):
        raise ValueError("A cumulative mask must contain unique reviewed buildings.")
    return records


def checked_group_barriers(bundle=BUNDLE):
    grouped = read_json(bundle / "grouped_buildings.json")
    evidence = read_json(bundle / "rollout_mask_evidence.json")
    masks, barriers, cells = evidence["cumulative_masks"], grouped["tile_barriers"], grouped["cells"]
    if (grouped.get("schema") != 2 or grouped.get("status") != "offline_geometry_only" or
            evidence.get("status") != "offline_only" or not masks or masks.keys() != barriers.keys()):
        raise ValueError("Expected the reviewed grouped bundle and its cumulative masks.")
    seen = []
    for tile, mask in masks.items():
        barrier = barriers[tile]
        if (mask.get("status") != "offline_candidate" or mask["source_tile"] != tile or
                barrier["source_tile_asset"] != mask["source_tile_asset"] or
                barrier["source_origin_m"] != mask["source_origin_m"] or
                barrier["source_export_sha256"] != mask["source_export_sha256"] or
                barrier["cumulative_mask_sha256"] != mask_sha(mask) or
                barrier["required_building_ids"] != sorted(mask_buildings(mask))):
            raise ValueError(f"{tile}: grouped barrier and cumulative source mask differ.")
        required = barrier["required_cells"]
        if not required or len(required) != len(set(required)):
            raise ValueError(f"{tile}: grouped barrier has missing or repeated cells.")
        buildings = []
        for name in required:
            cell = cells[name]
            path = bundle / f"{name}.glb"
            if (cell["tile"] != tile or cell["file"] != path.name or
                    path.resolve().parent != bundle.resolve() or file_sha(path) != cell["sha256"]):
                raise ValueError(f"{tile}: missing or changed grouped mesh {name}.")
            buildings.extend(row["id"] for row in cell["buildings"])
        if sorted(buildings) != barrier["required_building_ids"]:
            raise ValueError(f"{tile}: grouped cells do not cover the complete cumulative mask.")
        seen.extend(required)
    if len(seen) != len(set(seen)) or set(seen) != set(cells):
        raise ValueError("Every grouped cell must belong to exactly one source-tile barrier.")
    return grouped, masks


def checked_source(tile, source, metadata, mask):
    relative(source)
    relative(metadata)
    asset, origin, primitives = tile_metadata(metadata)
    if (mask["source_tile"] != tile or mask["source_tile_asset"] != asset or
            mask["source_origin_m"] != origin or file_sha(source) != mask["source_export_sha256"]):
        raise ValueError(f"{tile}: source export or metadata differs from the reviewed mask.")
    return {"tile": tile, "asset": asset, "origin_m": origin, "primitives": primitives}


def extended_mask(base, candidates, extended_evidence):
    if not candidates or extended_evidence is None:
        raise ValueError("An extended variant requires additional candidates and its offline rollout evidence.")
    variant = combine([base, *candidates])
    reviewed = extended_evidence["cumulative_masks"].get(base["source_tile"])
    if (extended_evidence.get("status") != "offline_only" or reviewed is None or
            any(variant[field] != reviewed[field] for field in SOURCE_FIELDS) or
            mask_buildings(variant) != mask_buildings(reviewed) or
            not mask_buildings(base).keys() < mask_buildings(variant).keys()):
        raise ValueError("The extended mask does not match the independently reviewed larger rollout.")
    return variant


def independent_check(source, mask, derivative, transport, slot_names):
    """Compare every output index and all source attribute and material data."""
    original, original_binary = read_glb(source)
    filtered, filtered_binary = read_glb(derivative)
    named, named_binary = read_glb(transport)
    selected, _ = reviewed_faces(original, original_binary, mask)
    source_primitives = original["meshes"][0]["primitives"]
    filtered_primitives = filtered["meshes"][0]["primitives"]
    named_primitives = named["meshes"][0]["primitives"]
    if (len(source_primitives) != len(filtered_primitives) or len(source_primitives) != len(named_primitives) or
            len(source_primitives) != len(slot_names) or len(named["materials"]) != len(slot_names) or
            filtered_binary[:len(original_binary)] != original_binary or named_binary != filtered_binary or
            filtered["materials"] != original["materials"]):
        raise RuntimeError("Filtered or import geometry changed the original source data.")
    protected = {int(index): name for index, name in mask["untouched_primitives"].items()}
    results = []
    for index, (before, after, imported) in enumerate(zip(source_primitives, filtered_primitives, named_primitives)):
        source_indices = indices(original, original_binary, index)
        blocked = selected.get(index, set())
        expected = tuple(value for offset in range(0, len(source_indices), 3) if offset // 3 not in blocked
                         for value in source_indices[offset:offset + 3])
        if ({key: value for key, value in before.items() if key != "indices"} !=
                {key: value for key, value in after.items() if key != "indices"} or
                {key: value for key, value in after.items() if key != "material"} !=
                {key: value for key, value in imported.items() if key != "material"} or
                indices(filtered, filtered_binary, index) != expected or
                indices(named, named_binary, index) != expected or
                (index in protected and after != before) or imported["material"] != index or
                named["materials"][index].get("name") != slot_names[index]):
            raise RuntimeError(f"Unexpected geometry, index or protected section change in primitive {index}.")
        source_material = deepcopy(original["materials"][before["material"]])
        named_material = deepcopy(named["materials"][index])
        source_material.pop("name", None)
        named_material.pop("name", None)
        if source_material != named_material:
            raise RuntimeError(f"Import transport changed non-name material properties in primitive {index}.")
        results.append({"index": index, "source_triangles": len(source_indices) // 3,
                        "removed_triangles": len(blocked), "remaining_triangles": len(expected) // 3,
                        "protected_by_export_metadata": index in protected})
    return results


def write_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def require_scratch_paths(saved_root, parent, root, staging=None, output=None):
    """Recheck captured canonical anchors, rejecting redirected path components."""
    try:
        if (not parent.is_relative_to(saved_root) or root.parent != parent or
                SAVED.resolve(strict=True) != saved_root or saved_root.resolve(strict=True) != saved_root or
                parent.resolve(strict=True) != parent or root.resolve(strict=True) != root):
            raise RuntimeError("Saved, output parent, or scratch path was redirected.")
        if staging is not None and (staging.parent != root or
                                    staging.resolve(strict=True) != staging or not staging.is_dir()):
            raise RuntimeError("Staging path was redirected or is not a directory.")
        if output is not None:
            if output.parent != parent or output.resolve() != output:
                raise RuntimeError("Output destination was redirected.")
            if os.path.lexists(output):
                raise FileExistsError(f"Output appeared during filtering: {output}")
    except OSError as error:
        if isinstance(error, FileExistsError):
            raise
        raise RuntimeError("Unable to verify Saved, scratch and output path anchors.") from error


@contextmanager
def staging_directory(saved_root, parent):
    # No TemporaryDirectory: failed work is intentionally left in place, never
    # recursively deleted through a path that could have been redirected.
    root = Path(mkdtemp(prefix="grouped_tile_filters_", dir=parent))
    require_scratch_paths(saved_root, parent, root)
    yield root
    try:
        require_scratch_paths(saved_root, parent, root)
        if any(root.iterdir()):
            raise OSError("scratch directory is not empty")
        root.rmdir()  # rmdir is non-recursive and only succeeds on an empty directory.
    except (OSError, RuntimeError) as error:
        print(f"Published output; leaving scratch directory untouched: {root} ({error})", file=sys.stderr)


def build(output, sources=None, tiles=None, additional=None, extended_evidence=None, bundle=BUNDLE):
    """Produce fresh offline outputs, one complete mask per source tile."""
    if os.path.lexists(output):
        raise ValueError("Choose a fresh output directory inside this project's Saved directory.")
    output = Path(output).resolve()
    saved_root = SAVED.resolve(strict=True)
    if not output.is_relative_to(saved_root) or output == saved_root or os.path.lexists(output):
        raise ValueError("Choose a fresh output directory inside this project's Saved directory.")
    require_editor_available()
    require_memory()
    group_manifest_sha = file_sha(bundle / "grouped_buildings.json")
    group_evidence_sha = file_sha(bundle / "rollout_mask_evidence.json")
    grouped, masks = checked_group_barriers(bundle)
    sources = DEFAULT_SOURCES if sources is None else sources
    chosen = list(sorted(masks) if tiles is None else tiles)
    if (sources.keys() - masks.keys() or not chosen or len(chosen) != len(set(chosen)) or
            any(tile not in masks or tile not in sources for tile in chosen)):
        raise ValueError("Select distinct grouped tiles with exact source and metadata paths.")
    extras = [read_json(path) for path in (additional or [])]
    if extras and (len(chosen) != 1 or any(item["source_tile"] != chosen[0] for item in extras)):
        raise ValueError("Each extended variant must select exactly one matching source tile.")
    if bool(extras) != bool(extended_evidence):
        raise ValueError("Provide extended candidates and their reviewed rollout evidence together.")
    if extended_evidence:
        relative(Path(extended_evidence))
        extended_evidence = read_json(extended_evidence)
    for path in additional or []:
        relative(Path(path))

    require_editor_available()
    require_memory()
    output.parent.mkdir(parents=True, exist_ok=True)
    with staging_directory(saved_root, output.parent) as root:
        staging = root / "bundle"
        staging.mkdir()
        records = {}
        for tile in chosen:
            require_editor_available()
            require_memory()
            source, metadata = (Path(value).resolve() for value in sources[tile])
            metadata_sha = file_sha(metadata)
            baseline = masks[tile]
            mask = extended_mask(baseline, extras, extended_evidence) if extras else baseline
            normalized = checked_source(tile, source, metadata, mask)
            face_counts = validate_mask(source, (normalized["asset"], normalized["origin_m"], normalized["primitives"]), mask)
            suffix = f'{tile}_{len(mask["buildings"])}_{mask_sha(mask)[:12]}'
            candidate_path = staging / f"{suffix}.mask.json"
            meta_path = staging / f"{suffix}.metadata.json"
            raw = staging / f"{suffix}.filtered.glb"
            named = staging / f"SM_GLMedieval_GroupedTile_{suffix}.glb"
            audit_path = staging / f"{suffix}.audit.json"
            write_json(candidate_path, mask)
            write_json(meta_path, normalized)
            audit = subtract(source, meta_path, candidate_path, raw, audit_path)
            names = write_import_copy(raw, audit_path, named)
            checked = independent_check(source, mask, raw, named, names)
            if file_sha(source) != mask["source_export_sha256"] or file_sha(metadata) != metadata_sha:
                raise RuntimeError(f"{tile}: original export or its metadata changed during subtraction.")
            if names != list(normalized["primitives"]):
                raise RuntimeError(f"{tile}: transport slots do not preserve the source section order.")
            # Scratch locations are not stable after publishing the completed directory.
            audit["source"] = relative(source)
            audit["derivative"] = raw.name
            audit_path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
            barrier = grouped["tile_barriers"][tile]
            records[tile] = {
                "status": "offline_review_only", "source": relative(source), "source_sha256": file_sha(source),
                "source_metadata": relative(metadata), "source_metadata_sha256": metadata_sha,
                "normalized_metadata": meta_path.name,
                "mask": candidate_path.name, "mask_sha256": mask_sha(mask), "building_count": len(mask["buildings"]),
                "required_building_ids": sorted(mask_buildings(mask)),
                "matches_checked_in_grouped_cells": not bool(extras),
                "required_grouped_cells": barrier["required_cells"] if not extras else None,
                "source_ue_section_mapping": "unverified",
                "runtime_activation_eligible": False,
                "incompatibility": ("The current grouped cells cover only the baseline mask; build and review "
                                    "matching groups for this extended mask before use.") if extras else None,
                "removed_triangles_by_slot": face_counts, "section_check": checked,
                "filtered_glb": raw.name, "filtered_sha256": file_sha(raw),
                "import_glb": named.name, "import_sha256": file_sha(named),
                "audit": audit_path.name, "audit_sha256": file_sha(audit_path),
            }
        report = {"schema": 1, "status": "offline_review_only", "source_bundle": relative(bundle),
                  "source_ue_section_mapping": "unverified",
                  "group_manifest_sha256": group_manifest_sha,
                  "group_evidence_sha256": group_evidence_sha,
                  "variant": "extended_unmatched_groups" if extras else "baseline_grouped_masks",
                  "tiles": records}
        write_json(staging / "tile_derivatives.json", report)
        require_editor_available()
        if (file_sha(bundle / "grouped_buildings.json") != group_manifest_sha or
                file_sha(bundle / "rollout_mask_evidence.json") != group_evidence_sha):
            raise RuntimeError("Grouped inputs changed during filtering; no derivative folder was published.")
        checked_group_barriers(bundle)
        require_scratch_paths(saved_root, output.parent, root, staging, output)
        staging.rename(output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Fresh directory under Saved")
    parser.add_argument("--tile", action="append", help="Reviewed tile; repeat for multiple tiles")
    parser.add_argument("--source", nargs=3, action="append", default=[], metavar=("TILE", "GLB", "METADATA"))
    parser.add_argument("--additional-candidate", type=Path, action="append", default=[])
    parser.add_argument("--extended-evidence", type=Path)
    args = parser.parse_args()
    sources = dict(DEFAULT_SOURCES)
    replacements = {}
    for tile, glb, metadata in args.source:
        if tile in replacements:
            parser.error(f"Give one source export per tile: {tile}")
        replacements[tile] = (Path(glb), Path(metadata))
    sources.update(replacements)
    report = build(args.output, sources, args.tile, args.additional_candidate, args.extended_evidence)
    print(f'{report["variant"]}: validated {len(report["tiles"])} offline tile derivatives in {args.output}')


if __name__ == "__main__":
    main()
