"""Extract street-facing walls from an Unreal-exported Gray London tile.

Use an identity-node source-model GLB, material baking disabled. Its local
positions are glTF metres. The caller supplies the tile actor's translation
and the verified ordinary facade primitive; custom facade sections are excluded.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct


def read_glb(path):
    raw = path.read_bytes()
    if struct.unpack_from("<4sII", raw) != (b"glTF", 2, len(raw)):
        raise ValueError("Expected a complete GLB v2 file.")
    size, kind = struct.unpack_from("<I4s", raw, 12)
    if kind != b"JSON":
        raise ValueError("GLB is missing its JSON chunk.")
    data = json.loads(raw[20:20 + size])
    bin_size, bin_kind = struct.unpack_from("<I4s", raw, 20 + size)
    if bin_kind != b"BIN\x00":
        raise ValueError("GLB is missing its binary mesh chunk.")
    if data.get("nodes") != [{"mesh": 0}] or len(data["meshes"]) != 1:
        raise ValueError("Export the StaticMesh asset itself with an identity node.")
    return data, memoryview(raw)[28 + size:28 + size + bin_size]


def accessor(data, blob, index, allowed):
    spec = data["accessors"][index]
    formats = {("VEC3", 5126): "3f", ("SCALAR", 5125): "I",
               ("SCALAR", 5123): "H", ("SCALAR", 5121): "B"}
    layout = (spec["type"], spec["componentType"])
    if layout not in allowed or "sparse" in spec or spec.get("normalized"):
        raise ValueError(f"Unsupported accessor {layout}.")
    view = data["bufferViews"][spec["bufferView"]]
    if view.get("buffer") != 0 or view.get("extensions"):
        raise ValueError("Expected an uncompressed GLB mesh buffer.")
    reader = struct.Struct("<" + formats[layout])
    start = view.get("byteOffset", 0) + spec.get("byteOffset", 0)
    stride = view.get("byteStride", reader.size)
    return [reader.unpack_from(blob, start + i * stride) for i in range(spec["count"])]


def det(a, b):
    return a[0] * b[1] - a[1] * b[0]


def vector(a, b):
    return b[0] - a[0], b[1] - a[1]


def primitive_mesh(data, blob, index, origin):
    primitive = data["meshes"][0]["primitives"][index]
    if primitive.get("mode", 4) != 4 or primitive.get("extensions"):
        raise ValueError("Expected an indexed triangle primitive.")
    attributes = primitive["attributes"]
    positions = accessor(data, blob, attributes["POSITION"], {("VEC3", 5126)})
    normals = accessor(data, blob, attributes["NORMAL"], {("VEC3", 5126)})
    indices = accessor(data, blob, primitive["indices"],
                       {("SCALAR", 5125), ("SCALAR", 5123), ("SCALAR", 5121)})
    if len(indices) % 3 or len(positions) != len(normals):
        raise ValueError("GLB triangle attributes are inconsistent.")
    tx, ty, tz = origin
    vertices = [(tx + x, ty + z, tz + y) for x, y, z in positions]
    return vertices, normals, [index[0] for index in indices]


def wall_groups(data, blob, index, origin):
    vertices, normals, indices = primitive_mesh(data, blob, index, origin)
    groups = {}

    for i in range(0, len(indices), 3):
        ids = indices[i:i + 3]
        if any(abs(normals[idx][1]) > .05 for idx in ids):
            continue
        points = [vertices[idx] for idx in ids]
        xy = sorted({(round(p[0], 3), round(p[1], 3)) for p in points})
        if len(xy) != 2:  # Reject ramps, slanted/curved wall facets, and columns.
            continue
        heights = sorted({round(p[2], 3) for p in points})
        if len(heights) != 2:
            continue
        z0, z1 = heights
        if z1 - z0 < 3:
            continue
        midpoint_normal = (
            sum(normals[idx][0] for idx in ids) / 3,
            sum(normals[idx][2] for idx in ids) / 3,
        )
        length = math.hypot(*midpoint_normal)
        if length < .9:
            continue
        outward = tuple(round(n / length, 4) for n in midpoint_normal)
        key = (*xy, z0, z1, outward)
        groups.setdefault(key, set()).add(tuple(sorted(tuple(round(v, 3) for v in p) for p in points)))

    walls = []
    for (a, b, base, top, outward), triangles in groups.items():
        # Both diagonally opposed triangles must cover the full rectangle.
        # At their shared diagonal the two unique points differ in both XY and Z.
        if len(triangles) != 2:
            continue
        shared = set.intersection(*(set(triangle) for triangle in triangles))
        if len(shared) != 2:
            continue
        s, t = sorted(shared)
        if s[:2] == t[:2] or s[2] == t[2]:
            continue
        walls.append((a, b, base, top, outward))
    return walls


def lerp(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def clip(a, b, bounds):
    lo, hi = 0.0, 1.0
    for axis, start in enumerate(a):
        delta = b[axis] - start
        minimum, maximum = bounds[axis], bounds[axis + 2]
        if abs(delta) < 1e-8:
            if not minimum <= start <= maximum:
                return None
        else:
            enter, leave = sorted(((minimum - start) / delta, (maximum - start) / delta))
            lo, hi = max(lo, enter), min(hi, leave)
            if lo > hi:
                return None
    return lerp(a, b, lo), lerp(a, b, hi)


def project_to_segment(point, a, b):
    dx, dy = vector(a, b)
    length_sq = dx * dx + dy * dy
    if length_sq:
        t = ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length_sq
        nearest = lerp(a, b, max(0.0, min(1.0, t)))
    else:
        nearest = tuple(a)
    return math.dist(point, nearest), nearest


class SpatialBins:
    def __init__(self, features, xy, size=24.0):
        self.features = features
        self.size = size
        self.bins = {}
        for index, feature in enumerate(features):
            for cell in self.cells(xy(feature)):
                self.bins.setdefault(cell, []).append(index)

    def cells(self, points):
        xs, ys = zip(*points)
        for x in range(math.floor(min(xs) / self.size), math.floor(max(xs) / self.size) + 1):
            for y in range(math.floor(min(ys) / self.size), math.floor(max(ys) / self.size) + 1):
                yield x, y

    def candidates(self, points):
        seen = set()
        for cell in self.cells(points):
            for index in self.bins.get(cell, ()):
                if index not in seen:
                    seen.add(index)
                    yield self.features[index]


def road_triangles(data, blob, spec):
    vertices, _, indices = primitive_mesh(data, blob, spec["road_primitive"], spec["origin_m"])
    triangles = []
    for i in range(0, len(indices), 3):
        corners = [vertices[index] for index in indices[i:i + 3]]
        zs = [corner[2] for corner in corners]
        if min(zs) < -1 or max(zs) > 2:
            continue
        a, b, c = (corner[:2] for corner in corners)
        if abs(det(vector(a, b), vector(a, c))) > 1e-5:
            triangles.append((a, b, c))
    if not triangles:
        raise ValueError("Verified road primitive contains no near-ground triangles.")
    return SpatialBins(triangles, lambda triangle: triangle)


def nearest_on_triangle(point, triangle):
    edges = tuple(zip(triangle, (*triangle[1:], triangle[0])))
    signs = [det(vector(a, b), vector(a, point)) for a, b in edges]
    if min(signs) >= 0 or max(signs) <= 0:
        return 0, point
    return min(project_to_segment(point, a, b) for a, b in edges)


def occluded(point, road_point, base, wall_index):
    ray = vector(road_point, point)
    for a, b, z0, z1, _ in wall_index.candidates((point, road_point)):
        if not z0 <= base + 1.5 <= z1:
            continue
        segment = vector(a, b)
        denom = det(ray, segment)
        if abs(denom) < 1e-8:
            continue
        relative = vector(road_point, a)
        t = det(relative, segment) / denom
        u = det(relative, ray) / denom
        if .01 < t < .99 and 0 <= u <= 1:
            return True
    return False


def extract(data, blob, spec):
    x0, y0, x1, y1 = spec["bounds"]
    maximum_distance = spec.get("maximum_distance_m", 14.0)
    expanded = (x0 - maximum_distance, y0 - maximum_distance,
                x1 + maximum_distance, y1 + maximum_distance)
    walls = [wall for wall in wall_groups(data, blob, spec["primitive"], spec["origin_m"])
             if clip(wall[0], wall[1], expanded)]
    wall_index = SpatialBins(walls, lambda wall: wall[:2])
    if "road" in spec:
        if len(spec["road"]) < 2:
            raise ValueError("Road guide needs at least two points.")
        segments = tuple(zip(spec["road"], spec["road"][1:]))
        minimum_distance = spec.get("minimum_distance_m", 2.0)
        confidence = "rectangular_wall_road_guide_visible"

        def nearest_road(point):
            return min(project_to_segment(point, a, b) for a, b in segments)
    else:
        road_index = road_triangles(data, blob, spec)
        minimum_distance = spec.get("minimum_distance_m", .15)
        confidence = "rectangular_wall_road_surface_visible"

        def nearest_road(point):
            x, y = point
            margin = maximum_distance
            query = ((x - margin, y - margin), (x + margin, y + margin))
            nearby = road_index.candidates(query)
            return min((nearest_on_triangle(point, triangle) for triangle in nearby),
                       default=(math.inf, point))

    faces = []
    for a, b, base, top, outward in sorted(walls):
        span = clip(a, b, spec["bounds"])
        height = top - base
        if not span or not -1 <= base <= 1.0:
            continue
        if not spec.get("minimum_height_m", 6) <= height <= spec.get("maximum_height_m", 45):
            continue
        if math.dist(*span) < spec.get("minimum_span_m", 3.0):
            continue
        stable = hashlib.sha256(repr((a, b, base, top, outward)).encode()).hexdigest()[:12]
        stable_id = f"{spec['tile']}_{stable}"
        if stable_id in spec.get("exclude_ids", ()):
            continue
        if any(clip(*span, protected) for protected in spec.get("exclude_bounds", ())):
            continue
        for fraction in (.15, .50, .85):
            point = lerp(*span, fraction)
            distance, road = nearest_road(point)
            dx, dy = vector(point, road)
            heading = (outward[0] * dx + outward[1] * dy) / max(distance, .01)
            if not minimum_distance <= distance <= maximum_distance or heading < .75:
                break
            if occluded(point, road, base, wall_index):
                break
        else:
            start, end = ([round(x, 3), round(y, 3), base] for x, y in span)
            faces.append({
                "id": stable_id, "start": start, "end": end,
                "height_m": round(height, 3), "outward": list(outward),
                "source_primitive": spec["primitive"], "confidence": confidence,
            })
    return faces


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tile_glb", type=Path)
    parser.add_argument("survey", type=Path, help="Road guide, tile origin, primitive and clipping bounds JSON.")
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    spec = json.loads(arguments.survey.read_text(encoding="utf-8"))
    data, blob = read_glb(arguments.tile_glb)
    frontages = extract(data, blob, spec)
    if not frontages:
        raise SystemExit("No walls passed the survey bounds and street-exposure checks.")
    report = {
        "coordinate_system": "ue_local_m",
        "source": spec["tile"],
        "attribution": "Base geometry: OpenStreetMap contributors, ODbL 1.0.",
        "source_geometry": {"facade_primitive": spec["primitive"], "origin_m": spec["origin_m"],
                            "road_primitive": spec.get("road_primitive") if "road" not in spec else None},
        "frontages": frontages,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Extracted {len(frontages)} street-facing facades.")


if __name__ == "__main__":
    main()
