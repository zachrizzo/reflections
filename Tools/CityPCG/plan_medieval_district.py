"""Fit reusable medieval bays to protected, verified Gray London facade runs."""

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

from extract_tile_frontages import SpatialBins
from plan_facades import axis_name, coordinates, stable_int

WALL_OFFSET_M = .035
CORNER_INSET_M = .13
BAY_WIDTH_M = 4.5
BAY_HEIGHT_M = 14.84
STYLES = ("Chandler", "Mercer", "Scrivener")


def frontage_points(row, floor_samples):
    identifier = row["id"]
    a, b = (coordinates(row[key], 3) for key in ("start", "end"))
    normal = coordinates(row["outward"], 2)
    norm = math.hypot(*normal)
    height = float(row["height_m"])
    span = math.dist(a[:2], b[:2])
    if not (3.55 <= span <= 65 and 13.25 <= height <= 16.95 and norm > .95 and abs(a[2] - b[2]) < .3):
        return
    nx, ny = (value / norm for value in normal)
    if abs((b[0] - a[0]) * nx + (b[1] - a[1]) * ny) > span * .015:
        raise ValueError(f"Outward direction is not perpendicular to {identifier}.")
    usable = span - 2 * CORNER_INSET_M
    count = max(1, round(usable / BAY_WIDTH_M))
    width = usable / count
    if not 3.25 <= width <= 5.15:
        return
    floor_m = min(floor_samples) / 100 if floor_samples else min(a[2], b[2])
    limit_m = min(a[2], b[2]) + height
    start_style = stable_int(identifier) % len(STYLES)
    for i in range(count):
        t = (CORNER_INSET_M + (i + .5) * width) / span
        x = a[0] + (b[0] - a[0]) * t + nx * WALL_OFFSET_M
        y = a[1] + (b[1] - a[1]) * t + ny * WALL_OFFSET_M
        identity = f"{identifier}.{i}"
        yield {
            "id": identity,
            "building_id": identifier,
            "mesh_id": f"SM_GLMedieval_{STYLES[(start_style + i) % len(STYLES)]}",
            "location_cm": [round(x * 100, 3), round(y * 100, 3), round(floor_m * 100 - .35, 3)],
            "yaw_deg": round(math.degrees(math.atan2(ny, nx)), 5),
            "scale": [.56, round(width / BAY_WIDTH_M, 6), round((limit_m - floor_m) / BAY_HEIGHT_M, 6)],
            "seed": stable_int(identity),
        }


def represented_frontage(row, existing_points):
    a, b = row["start"], row["end"]
    span = math.dist(a[:2], b[:2])
    if span < 3.55:
        return False
    tx, ty = ((b[axis] - a[axis]) / span for axis in range(2))
    nx, ny = row["outward"]
    envelope = ((min(a[0], b[0]) - .65, min(a[1], b[1]) - .65),
                (max(a[0], b[0]) + .65, max(a[1], b[1]) + .65))
    for x, y, yaw, half_width in existing_points.candidates(envelope):
        dx, dy = x - a[0], y - a[1]
        if not -half_width <= dx * tx + dy * ty <= span + half_width or abs(dx * nx + dy * ny) > .65:
            continue
        if nx * math.cos(yaw) + ny * math.sin(yaw) >= .95:
            return True
    return False


def exclusion_points(plans):
    occupied = set()
    for existing in plans:
        if existing.get("coordinate_system") != "ue_cm":
            raise ValueError("Exclude only placed plans in Unreal world centimetres.")
        for cell in existing["cells"]:
            for point in cell["points"]:
                x, y, _ = coordinates(point["location_cm"], 3)
                _, scale_y, _ = coordinates(point["scale"], 3)
                width = BAY_WIDTH_M if point["mesh_id"].startswith("SM_GLMedieval_") else 4.0
                occupied.add((x / 100, y / 100, math.radians(point["yaw_deg"]), width * scale_y / 2 + .15))
    return SpatialBins(tuple(occupied),
                       lambda point: ((point[0] - point[3], point[1] - point[3]),
                                      (point[0] + point[3], point[1] + point[3])))


def plan(source, verification=None, previous=(), grid_size=160, cell_budget=125):
    if source.get("coordinate_system") != "ue_local_m" or not source.get("protected_mesh_filters"):
        raise ValueError("Use protected frontages in Unreal local metres.")
    reports = defaultdict(list)
    if verification is not None:
        if verification["expected_actor"] != f"OSM {source['source']}":
            raise ValueError("The live report does not match the source tile.")
        for hit in verification["samples"]:
            reports[hit["id"]].append(hit)
    cells = defaultdict(list)
    skipped = []
    already_dressed = []
    occupied = exclusion_points(previous)
    for row in sorted(source["frontages"], key=lambda value: value["id"]):
        identifier = row["id"]
        if represented_frontage(row, occupied):
            already_dressed.append(identifier)
            continue
        hits = reports[identifier]
        if verification is not None and (len(hits) != 9 or not all(
                hit["passes"] and hit["exterior_floor_z_cm"] is not None for hit in hits)):
            skipped.append(identifier)
            continue
        floors = [hit["exterior_floor_z_cm"] for hit in hits]
        if floors and max(floors) - min(floors) > 20:
            skipped.append(identifier)
            continue
        for point in frontage_points(row, floors):
            x, y, _ = point["location_cm"]
            key = (math.floor(x / (grid_size * 100)), math.floor(y / (grid_size * 100)))
            if len(cells[key]) >= cell_budget:
                raise ValueError(f"Medieval cell {key} exceeds {cell_budget} instances.")
            cells[key].append(point)
    return {
        "coordinate_system": "ue_cm",
        "source": source["source"],
        "kit": "/Game/GrayLondon/MedievalOpening/Kit",
        "verified": verification is not None,
        "skipped_frontages": skipped,
        "previously_dressed_frontages": already_dressed,
        "cells": [{"id": f"Medieval_x{axis_name(x)}_y{axis_name(y)}", "points": points}
                  for (x, y), points in sorted(cells.items())],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--verification", type=Path, help="Output from verify_tile_frontages_unreal")
    parser.add_argument("--exclude-plan", type=Path, action="append", default=[],
                        help="An already placed modern or medieval facade plan. May be repeated.")
    args = parser.parse_args()
    inputs = [args.source, *args.exclude_plan]
    if args.verification:
        inputs.append(args.verification)
    if args.output.resolve() in {path.resolve() for path in inputs}:
        parser.error("Use a separate output file.")
    source = json.loads(args.source.read_text(encoding="utf-8-sig"))
    verification = json.loads(args.verification.read_text(encoding="utf-8-sig")) if args.verification else None
    previous = [json.loads(path.read_text(encoding="utf-8-sig")) for path in args.exclude_plan]
    result = plan(source, verification, previous)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"{sum(len(cell['points']) for cell in result['cells'])} bays in {len(result['cells'])} cells. "
          f"{len(result['skipped_frontages'])} live-verification exclusions, "
          f"{len(result['previously_dressed_frontages'])} already dressed.")


if __name__ == "__main__":
    main()
