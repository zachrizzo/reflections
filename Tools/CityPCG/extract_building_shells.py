"""Recover complete flat roof and ordinary wall shells from a Gray London GLB."""

import argparse
from collections import Counter, defaultdict
from itertools import combinations
import json
import math
from pathlib import Path

from extract_tile_frontages import primitive_mesh, read_glb


def faces(data, blob, primitive, origin):
    vertices, _, indices = primitive_mesh(data, blob, primitive, origin)
    rounded = [tuple(round(value, 3) for value in point) for point in vertices]
    return [tuple(rounded[index] for index in indices[i:i + 3]) for i in range(0, len(indices), 3)]


def edges(triangle):
    return [tuple(sorted(edge)) for edge in combinations(triangle, 2)]


def wall_rectangles(source):
    groups = defaultdict(list)
    for index, triangle in enumerate(source):
        xy = tuple(sorted({point[:2] for point in triangle}))
        heights = sorted({point[2] for point in triangle})
        if len(xy) == 2 and len(heights) == 2 and heights[1] - heights[0] >= 3:
            groups[(xy, *heights)].append(index)

    rectangles = defaultdict(list)
    for (xy, base, top), pair in groups.items():
        if len(pair) != 2:
            continue
        left, right = (set(source[index]) for index in pair)
        corners = {(x, y, z) for x, y in xy for z in (base, top)}
        diagonal = left & right
        if left | right == corners and len(diagonal) == 2 and len({p[2] for p in diagonal}) == 2:
            if len({p[:2] for p in diagonal}) == 2:
                rectangles[(xy, top)].append((base, pair))
    return rectangles


def component_faces(roof):
    flat_edges = defaultdict(list)
    pending = set()
    for index, triangle in enumerate(roof):
        if len(set(triangle)) == 3 and len({point[2] for point in triangle}) == 1:
            pending.add(index)
            for edge in edges(triangle):
                flat_edges[edge].append(index)
    for seed in range(len(roof)):
        if seed not in pending:
            continue
        pending.remove(seed)
        stack, component = [seed], [seed]
        while stack:
            for edge in edges(roof[stack.pop()]):
                for index in flat_edges[edge]:
                    if index in pending:
                        pending.remove(index)
                        stack.append(index)
                        component.append(index)
        yield sorted(component)


def boundary_ring(boundary):
    neighbors = defaultdict(list)
    for a, b in boundary:
        neighbors[a].append(b)
        neighbors[b].append(a)
    if not neighbors or any(len(group) != 2 for group in neighbors.values()):
        return []
    start = min(neighbors)
    ring, current = [start], min(neighbors[start])
    while current not in ring:
        ring.append(current)
        current = next(point for point in neighbors[current] if point != ring[-2])
    return ring if current == start and len(ring) == len(neighbors) else []


def signed_area(ring):
    x0, y0 = ring[0]
    return sum((a[0] - x0) * (b[1] - y0) - (b[0] - x0) * (a[1] - y0)
               for a, b in zip(ring, ring[1:] + ring[:1])) / 2


def extract_shells(data, blob, origin, bounds, wall_primitive=0, roof_primitive=1):
    """Yield single-ring roofs supported by unique wall quads at one base height."""
    roof = faces(data, blob, roof_primitive, origin)
    walls = wall_rectangles(faces(data, blob, wall_primitive, origin))
    x0, y0, x1, y1 = bounds
    for face_ids in component_faces(roof):
        if not all(x0 <= x <= x1 and y0 <= y <= y1 for index in face_ids for x, y, _ in roof[index]):
            continue
        topology = Counter(edge for index in face_ids for edge in edges(roof[index]))
        if max(topology.values()) > 2:
            continue
        ring = boundary_ring([edge for edge, count in topology.items() if count == 1])
        if len(ring) < 3:
            continue
        top = ring[0][2]
        footprint = [point[:2] for point in ring]
        area = signed_area(footprint)
        if abs(area) < 1:
            continue
        if area < 0:
            footprint = [footprint[0], *reversed(footprint[1:])]
        unique_source = []
        for a, b in zip(footprint, footprint[1:] + footprint[:1]):
            rectangles = walls.get((tuple(sorted((a, b))), top), [])
            if len(rectangles) != 1:
                break
            unique_source.append(rectangles[0])
        else:
            bases = {base for base, _ in unique_source}
            if len(bases) != 1 or not -.5 <= next(iter(bases)) <= .75:
                continue
            roof_area = sum(abs(signed_area([p[:2] for p in roof[index]])) for index in face_ids)
            if not math.isclose(abs(area), roof_area, rel_tol=1e-6, abs_tol=1e-6):
                continue
            yield {
                "footprint": footprint,
                "area_m2": round(abs(area), 3),
                "base_m": next(iter(bases)),
                "source_roof_m": top,
                "source_wall_faces_by_edge": [ids for _, ids in unique_source],
                "source_roof_faces": face_ids,
            }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mesh", type=Path)
    parser.add_argument("result", type=Path)
    parser.add_argument("--origin", metavar=("X", "Y", "Z"), nargs=3, type=float, required=True)
    parser.add_argument("--bounds", metavar=("XMin", "YMin", "XMax", "YMax"), nargs=4,
                        type=float, required=True)
    parser.add_argument("--wall-primitive", type=int, default=0)
    parser.add_argument("--roof-primitive", type=int, default=1)
    args = parser.parse_args()
    if args.mesh.resolve() == args.result.resolve():
        parser.error("Use a separate result file.")
    data, blob = read_glb(args.mesh)
    shells = list(extract_shells(data, blob, args.origin, args.bounds,
                                 args.wall_primitive, args.roof_primitive))
    args.result.write_text(json.dumps(shells, indent=2) + "\n", encoding="utf-8")
    print(f"Recovered {len(shells)} closed ordinary shells in the requested bounds.")


if __name__ == "__main__":
    main()
