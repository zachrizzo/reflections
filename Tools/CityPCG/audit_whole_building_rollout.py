"""Inventory canonical city exports and preflight cumulative masks offline."""

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import re

from combine_replacement_candidates import SOURCE_FIELDS, combine
from extract_tile_frontages import read_glb
from inventory_building_geometry import inventory
from subtract_building_shells import digest, read_json, reviewed_faces


TILE = re.compile(r"Tile_[pm]\d{2}_[pm]\d{2}")
PACKAGE_ROOT = "/Game/GrayLondon/Geodata/Tiles"
SLOTS = ("GL_Facade", "GL_Roof", "GL_Road")


def discover_exports(directory, tiles):
    found = defaultdict(list)
    for path in sorted(directory.rglob("Tile_*.glb")):
        if path.stem in tiles:
            found[path.stem].append((digest(path.read_bytes()), path))
    return found


def tile_metadata(path):
    record = read_json(path)
    raw = record["tile"] if isinstance(record.get("tile"), dict) else record
    name = raw["tile"]
    object_path = f"{PACKAGE_ROOT}/{name}.{name}"
    asset = raw.get("asset") or (f"{raw['package']}.{name}" if raw.get("package") else None)
    slots = raw["primitives"]
    origin = raw["origin_m"]
    if (asset != object_path or len(origin) != 3 or not all(math.isfinite(value) for value in origin)
            or not all(slot in slots for slot in SLOTS)
            or not all(type(count) is int and count > 0 for count in slots.values())):
        raise ValueError(f"{path}: incomplete original tile identity or primitive metadata.")
    return object_path, origin, slots


def select_source(name, versions, pinned=None):
    hashes = {sha for sha, _ in versions}
    if pinned is not None and pinned not in hashes:
        raise ValueError("No local export matches the candidate's pinned source SHA-256.")
    if pinned is None and len(hashes) != 1:
        raise ValueError("Multiple export hashes exist. Supply a source pin or an explicit candidate.")
    chosen = pinned or next(iter(hashes))
    records = []
    for sha, source in versions:
        if sha != chosen:
            continue
        for suffix in (".asset.json", ".assets.json"):
            metadata = source.with_suffix(suffix)
            if metadata.is_file():
                records.append((source, metadata, tile_metadata(metadata)))
    if not records:
        raise ValueError("The matching source export has no supported tile metadata sidecar.")
    expected = f"{PACKAGE_ROOT}/{name}.{name}"
    if any(record[2][0] != expected or record[2][:2] != records[0][2][:2] or
           list(record[2][2].items()) != list(records[0][2][2].items()) for record in records):
        raise ValueError("Metadata sidecars for the selected export disagree on tile, origin, or ordered slots.")
    return chosen, *records[0]


def validate_mask(source, identity, mask):
    asset, origin, slots = identity
    names = list(slots)
    selected_slots = (names.index("GL_Facade"), names.index("GL_Roof"))
    protected = {str(index): name for index, name in enumerate(names) if index not in selected_slots}
    if (mask["coordinate_system"] != "ue_local_m" or mask["source_tile_asset"] != asset
            or mask["source_origin_m"] != origin or mask["untouched_primitives"] != protected
            or (mask["ordinary_wall_primitive"], mask["roof_primitive"]) != selected_slots):
        raise ValueError("Cumulative mask disagrees with the canonical source identity or immutable sections.")
    selected, _ = reviewed_faces(*read_glb(source), mask)
    if digest(source.read_bytes()) != mask["source_export_sha256"]:
        raise ValueError("The source changed while validating the cumulative mask.")
    if any(len(faces) >= slots[names[index]] for index, faces in selected.items()):
        raise ValueError("Cumulative mask empties an original render section.")
    return {names[index]: len(faces) for index, faces in selected.items()}


def require_cumulative(previous, checked):
    for name, old in previous.items():
        new = checked.get(name)
        if new is None:
            raise ValueError(f"{name}: a previously preflighted mask tile was omitted.")
        if any(old[field] != new[field] for field in SOURCE_FIELDS):
            raise ValueError(f"{name}: the canonical source changed; repeat live review before rebasing.")
        buildings = {row["id"]: row for row in new["buildings"]}
        if any(buildings.get(row["id"]) != row for row in old["buildings"]):
            raise ValueError(f"{name}: a previously preflighted building mask changed or was removed.")


def audit(tiles_directory, exports, candidate_paths=(), previous=None, source_pins=None):
    tiles = {path.stem for path in tiles_directory.glob("Tile_*.uasset") if TILE.fullmatch(path.stem)}
    if not tiles:
        raise ValueError(f"No canonical geodata tile assets found in {tiles_directory}.")
    source_pins = source_pins or {}
    if not source_pins.keys() <= tiles or any(not re.fullmatch(r"[a-f0-9]{64}", sha) for sha in source_pins.values()):
        raise ValueError("Source pins require a canonical tile name and lowercase SHA-256.")
    versions = discover_exports(exports, tiles)
    groups = defaultdict(list)
    evidence = defaultdict(list)
    for path in candidate_paths:
        candidate = read_json(path)
        name = candidate["source_tile"]
        if name not in tiles or candidate.get("status") != "offline_candidate":
            raise ValueError(f"{path}: expected an explicit offline candidate for a canonical tile.")
        groups[name].append(candidate)
        evidence[name].append({"file": str(path), "sha256": digest(path.read_bytes())})

    report = {"source_tile_count": len(tiles), "locally_exported_tile_count": len(versions),
              "status": "offline_only", "tile_inventory": {}, "cumulative_masks": {}}
    for name in sorted(tiles):
        sources = versions.get(name, [])
        row = {"exports": [{"file": str(path), "sha256": sha} for sha, path in sources]}
        report["tile_inventory"][name] = row
        group = groups.get(name, [])
        if group:
            row["candidate_files"] = evidence[name]
        if not sources and not group and name not in source_pins:
            row["status"] = "needs_original_export"
            continue
        try:
            mask = combine(group) if len(group) > 1 else group[0] if group else None
            pin = source_pins.get(name)
            if mask:
                if pin is not None and pin != mask["source_export_sha256"]:
                    raise ValueError("The requested source pin differs from the candidate's source SHA-256.")
                pin = mask["source_export_sha256"]
            sha, source, metadata, identity = select_source(name, sources, pin)
            geometry = inventory(source, metadata)
            if geometry["source_sha256"] != sha:
                raise ValueError("The selected source changed while it was being read.")
            row.update(status="inventoried", source=str(source), source_sha256=sha, metadata=str(metadata),
                       roof_triangles=geometry["roof_triangles"], component_counts=geometry["component_counts"])
            if mask:
                counts = validate_mask(source, identity, mask)
                row.update(offline_mask_face_counts=counts, offline_mask_buildings=len(mask["buildings"]))
                report["cumulative_masks"][name] = mask
        except (OSError, ValueError, KeyError, TypeError) as error:
            row.update(status="blocked", reason=str(error))
    require_cumulative(previous or {}, report["cumulative_masks"])
    report["inventoried_tile_count"] = sum(row["status"] == "inventoried" for row in report["tile_inventory"].values())
    report["requested_mask_failures"] = sorted(groups.keys() - report["cumulative_masks"].keys())
    report["requested_pin_failures"] = sorted(name for name in source_pins
                                              if report["tile_inventory"][name]["status"] != "inventoried")
    return report


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("output", type=Path, help="Fresh JSON report path")
    cli.add_argument("--tiles", type=Path, default=Path("Content/GrayLondon/Geodata/Tiles"))
    cli.add_argument("--exports", type=Path, default=Path("Saved/CityPCG"))
    cli.add_argument("--candidate", type=Path, action="append", default=[], help="Explicit candidate, repeatable")
    cli.add_argument("--source-pin", nargs=2, action="append", default=[], metavar=("TILE", "SHA256"),
                     help="Select an exact export revision for inventory")
    cli.add_argument("--previous-report", type=Path, help="Ensure every earlier preflighted mask survives")
    args = cli.parse_args()
    source_pins = dict(args.source_pin)
    if len(source_pins) != len(args.source_pin):
        cli.error("Provide one source pin per tile.")
    previous = read_json(args.previous_report)["cumulative_masks"] if args.previous_report else {}
    report = audit(args.tiles, args.exports, args.candidate, previous, source_pins)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(f'{report["inventoried_tile_count"]}/{report["source_tile_count"]} tiles inventoried, '
          f'{len(report["cumulative_masks"])} cumulative offline masks checked.')
    failures = set(report["requested_mask_failures"] + report["requested_pin_failures"])
    if failures:
        print("Requested tile preflights blocked: " + ", ".join(sorted(failures)))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
