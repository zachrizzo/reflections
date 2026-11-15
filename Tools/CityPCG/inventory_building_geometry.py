"""Catalog complete and irregular roof shells in an exported Gray London tile.

The report identifies what a whole-building replacement pipeline can recover
and records why other roofs need additional analysis. It does not authorize
removing geometry, choose protected landmarks, or change the source tile.
"""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

from extract_building_shells import boundary_ring, component_faces, edges, faces, signed_area, wall_rectangles
from extract_tile_frontages import read_glb


def identity(tile, triangles):
    """Return a deterministic identifier based on the roof geometry itself."""
    geometry = sorted(tuple(sorted(triangle)) for triangle in triangles)
    digest = hashlib.sha256(json.dumps(geometry, separators=(",", ":")).encode("ascii")).hexdigest()
    return f"{tile}_roof_{digest[:16]}"


def describe_component(tile, indices, roof, walls):
    triangles = [roof[index] for index in indices]
    topology = Counter(edge for triangle in triangles for edge in edges(triangle))
    result = {
        "id": identity(tile, triangles),
        "roof_faces": indices,
        "roof_height_m": triangles[0][0][2],
    }
    if max(topology.values()) > 2:
        result["classification"] = "nonmanifold_roof"
        return result

    boundary = [edge for edge, count in topology.items() if count == 1]
    ring = boundary_ring(boundary)
    if len(ring) < 3:
        result["classification"] = "complex_roof_boundary"
        result["boundary_edges"] = len(boundary)
        return result

    footprint = [point[:2] for point in ring]
    area = signed_area(footprint)
    result["area_m2"] = round(abs(area), 3)
    if abs(area) < 1:
        result["classification"] = "small_roof"
        return result
    if area < 0:
        footprint = [footprint[0], *reversed(footprint[1:])]
    result["footprint_m"] = footprint
    roof_area = sum(abs(signed_area([point[:2] for point in triangle])) for triangle in triangles)
    if not math.isclose(abs(area), roof_area, rel_tol=1e-6, abs_tol=1e-6):
        result["classification"] = "roof_area_mismatch"
        result["triangle_area_m2"] = round(roof_area, 3)
        return result

    matches = []
    missing, ambiguous = [], []
    for edge_index, (start, end) in enumerate(zip(footprint, footprint[1:] + footprint[:1])):
        options = walls.get((tuple(sorted((start, end))), result["roof_height_m"]), [])
        if not options:
            missing.append(edge_index)
        elif len(options) != 1:
            ambiguous.append(edge_index)
        else:
            matches.append({"edge": edge_index, "base_m": options[0][0], "wall_faces": options[0][1]})
    result["wall_matches"] = matches
    if missing:
        result["classification"] = "missing_wall"
        result["missing_wall_edges"] = missing
    elif ambiguous:
        result["classification"] = "ambiguous_wall"
        result["ambiguous_wall_edges"] = ambiguous
    else:
        bases = sorted({match["base_m"] for match in matches})
        result["base_heights_m"] = bases
        if len(bases) != 1:
            result["classification"] = "varying_foundations"
        elif not -.5 <= bases[0] <= .75:
            result["classification"] = "raised_foundations"
        else:
            result["classification"] = "complete_ground_shell"
    return result


def inventory(mesh_path, metadata_path):
    metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    tile = metadata.get("tile") if isinstance(metadata.get("tile"), dict) else metadata
    name = tile["tile"]
    origin = tile["origin_m"]
    slots = list(tile["primitives"])
    if len(origin) != 3 or slots.count("GL_Facade") != 1 or slots.count("GL_Roof") != 1:
        raise ValueError("Expected a translated tile with distinct facade and roof sections.")

    document, blob = read_glb(mesh_path)
    primitives = document["meshes"][0]["primitives"]
    if len(primitives) != len(slots):
        raise ValueError("The source export and tile material slots do not match.")
    for index, slot in enumerate(slots):
        index_count = document["accessors"][primitives[index]["indices"]]["count"]
        if index_count != tile["primitives"][slot] * 3:
            raise ValueError(f"The source triangle count changed in {slot}.")

    roof = faces(document, blob, slots.index("GL_Roof"), origin)
    wall = faces(document, blob, slots.index("GL_Facade"), origin)
    rectangles = wall_rectangles(wall)
    entries = [describe_component(name, indices, roof, rectangles) for indices in component_faces(roof)]
    ids = [entry["id"] for entry in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("Two roof components have the same geometric identity.")

    counts = Counter(entry["classification"] for entry in entries)
    triangle_counts = Counter()
    for entry in entries:
        triangle_counts[entry["classification"]] += len(entry["roof_faces"])
    included = sum(triangle_counts.values())
    if included > len(roof):
        raise ValueError("Roof components do not form disjoint sets of triangles.")
    return {
        "tile": name,
        "source_asset": tile.get("package", tile.get("asset")),
        "source_sha256": hashlib.sha256(mesh_path.read_bytes()).hexdigest(),
        "source_origin_m": origin,
        "roof_triangles": len(roof),
        "flat_roof_components": len(entries),
        "uncatalogued_roof_triangles": len(roof) - included,
        "component_counts": dict(sorted(counts.items())),
        "triangle_counts": dict(sorted(triangle_counts.items())),
        "roofs": entries,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mesh", type=Path)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.resolve() in {args.mesh.resolve(), args.metadata.resolve()}:
        parser.error("Choose an output separate from the source files.")
    result = inventory(args.mesh, args.metadata)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"{result['tile']}: {result['component_counts'].get('complete_ground_shell', 0)} complete ground "
          f"shells, {result['flat_roof_components']} flat roof components, {result['roof_triangles']} roof triangles.")


if __name__ == "__main__":
    main()
