"""Extract traffic-facing runs and mask authored buildings on a specific tile."""

import argparse
import json
from pathlib import Path

from extract_tile_frontages import extract, read_glb
from filter_protected_frontages import overlaps_overlay, protected_triangles


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def survey(metadata_file, corridor):
    assets = read(metadata_file)
    tile, overlay = (assets[key] for key in ("tile", "overlay"))
    if tile["tile"] != corridor["tile"] or overlay["tile"] != corridor["tile"]:
        raise ValueError("The corridor and both saved mesh exports must refer to the same tile.")
    source_dir = metadata_file.parent
    data, blob = read_glb(source_dir / tile["glb"])
    landmarks = corridor.get("protected_landmarks", [])
    masks = [item["bounds_m"] for item in landmarks]
    spec = {
        **tile,
        "bounds": corridor["bounds_m"],
        "exclude_bounds": masks,
        "minimum_span_m": 3.55,
        "minimum_height_m": 13.25,
        "maximum_height_m": 16.95,
    }
    candidates = extract(data, blob, spec)
    overlay_index = protected_triangles(source_dir / overlay["glb"], overlay["origin_m"])
    frontages, excluded = [], []
    for frontage in candidates:
        if overlaps_overlay(frontage, overlay_index):
            excluded.append(frontage["id"])
        else:
            frontages.append(frontage)
    return {
        "coordinate_system": "ue_local_m",
        "source": tile["tile"],
        "attribution": "Base geometry: OpenStreetMap contributors, ODbL 1.0.",
        "source_geometry": {"facade_primitive": tile["primitive"], "origin_m": tile["origin_m"],
                            "road_primitive": tile["road_primitive"]},
        "frontages": frontages,
        "protected_mesh_filters": [{"overlay": overlay["glb"], "origin_m": overlay["origin_m"],
                                    "excluded_ids": excluded}],
        "protected_landmarks": landmarks,
        "review_scope": {"name": corridor["name"], "bounds_m": corridor["bounds_m"]},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("corridor", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.resolve() in (args.metadata.resolve(), args.corridor.resolve()):
        parser.error("Use a separate result file.")
    report = survey(args.metadata, read(args.corridor))
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{len(report['frontages'])} street-facing runs after removing authored overlaps.")


if __name__ == "__main__":
    main()
