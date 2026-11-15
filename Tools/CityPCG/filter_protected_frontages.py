"""Exclude generated facade runs overlapping an exported authored overlay mesh."""

import argparse
import json
import math
from pathlib import Path

from extract_tile_frontages import primitive_mesh, read_glb, SpatialBins


def protected_triangles(path, origin):
    document, blob = read_glb(path)
    triangles = []
    for index, _ in enumerate(document["meshes"][0]["primitives"]):
        vertices, _, indices = primitive_mesh(document, blob, index, origin)
        for start in range(0, len(indices), 3):
            corners = [vertices[i] for i in indices[start:start + 3]]
            if max(point[2] for point in corners) > .4:
                triangles.append(corners)
    return SpatialBins(triangles, lambda triangle: [point[:2] for point in triangle])


def overlaps_overlay(frontage, overlay):
    a, b = frontage["start"], frontage["end"]
    nx, ny = frontage["outward"]
    run = math.dist(a[:2], b[:2])
    if run <= 0:
        raise ValueError(f"Zero-width facade {frontage['id']}")
    tx, ty = (b[0] - a[0]) / run, (b[1] - a[1]) / run
    # The strip covers 45 cm behind the wall, 1.7 m forward, and 75 cm
    # beyond each endpoint. This is a conservative projection, not a mesh boolean.
    query = ((min(a[0], b[0]) - 2, min(a[1], b[1]) - 2),
             (max(a[0], b[0]) + 2, max(a[1], b[1]) + 2))
    for triangle in overlay.candidates(query):
        along = [(x - a[0]) * tx + (y - a[1]) * ty for x, y, _ in triangle]
        across = [(x - a[0]) * nx + (y - a[1]) * ny for x, y, _ in triangle]
        if min(along) <= run + .75 and max(along) >= -.75 and min(across) <= 1.7 and max(across) >= -.45:
            return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frontages", type=Path)
    parser.add_argument("overlay_glb", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--overlay-origin-m", nargs=3, type=float, required=True)
    args = parser.parse_args()
    if args.output.resolve() == args.frontages.resolve():
        parser.error("Write the filtered feed to a different file.")
    report = json.loads(args.frontages.read_text(encoding="utf-8-sig"))
    if report.get("coordinate_system") != "ue_local_m":
        parser.error("Expected ue_local_m facade coordinates.")
    overlay = protected_triangles(args.overlay_glb, args.overlay_origin_m)
    excluded, kept = [], []
    for frontage in report["frontages"]:
        if overlaps_overlay(frontage, overlay):
            excluded.append(frontage["id"])
        else:
            kept.append(frontage)
    report["frontages"] = kept
    report.setdefault("protected_mesh_filters", []).append({
        "overlay": args.overlay_glb.name, "origin_m": args.overlay_origin_m, "excluded_ids": excluded,
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Kept {len(kept)} facades, excluded {len(excluded)} overlapping {args.overlay_glb.name}.")


if __name__ == "__main__":
    main()
