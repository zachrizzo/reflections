"""Prepare measured replacement shells and road guards from a reviewed Gray London block."""

import argparse
import json
import math
from pathlib import Path

from extract_building_shells import faces, signed_area
from extract_tile_frontages import lerp, nearest_on_triangle, project_to_segment, read_glb, road_triangles
from subtract_building_shells import digest, read_json, reviewed_faces


def ring_edges(ring):
    return zip(ring, (*ring[1:], ring[0]))


def distance_to_building(point, ring):
    x, y = point
    crossings = sum((a[1] > y) != (b[1] > y) and
                    x < a[0] + (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1])
                    for a, b in ring_edges(ring))
    return 0.0 if crossings % 2 else min(project_to_segment(point, a, b)[0] for a, b in ring_edges(ring))


def building_input(building, style, roof_faces):
    ring = [tuple(point) for point in building["footprint"]]
    origin = building["origin_m"]
    entry = building["entry"]
    edge = entry["edge"]
    a, b = ring[edge], ring[(edge + 1) % len(ring)]
    width = math.dist(a, b)
    axis_x = ((b[1] - a[1]) / width, (a[0] - b[0]) / width)
    axis_y = (-axis_x[1], axis_x[0])
    if signed_area(ring) <= 0 or math.dist(axis_x, entry["outward"]) > 1e-5:
        raise ValueError(f"Unexpected orientation on {building['id']}.")

    def local(point):
        dx, dy = point[0] - origin[0], point[1] - origin[1]
        return [round(dx * x + dy * y, 6) for x, y in (axis_x, axis_y)]

    local_outline = [local(point) for point in ring]
    coordinate_index = {point: i for i, point in enumerate(ring)}
    local_vertices, triangles = list(local_outline), []
    for face in building["source_roof_faces"]:
        projected = [point[:2] for point in roof_faces[face]]
        if signed_area(projected) < 0:
            projected.reverse()
        for point in projected:
            if point not in coordinate_index:
                coordinate_index[point] = len(local_vertices)
                local_vertices.append(local(point))
        triangles.append([coordinate_index[point] for point in projected])

    x0, y0 = map(min, zip(*local_outline))
    x1, y1 = map(max, zip(*local_outline))
    eave, ridge = style["eave_m"], style["ridge_m"]
    bays = style["roof_ranges"]
    if not 0 < eave < ridge <= building["source_roof_m"] - origin[2] or type(bays) is not int or bays < 1:
        raise ValueError(f"Roof settings exceed the source envelope for {building['id']}.")
    profile = [[round(y0 + (y1 - y0) * i / (2 * bays), 6), ridge if i % 2 else eave]
               for i in range(2 * bays + 1)]
    door = style["entry_opening_m"]
    if not 0 < door[0] <= min(width - .3, entry["minimum_clear_width_m"]) or not 0 < door[1] < eave:
        raise ValueError(f"Entry does not fit the surveyed clear width on {building['id']}.")
    return {
        "id": building["id"],
        "role": style["role"],
        "origin_m": origin,
        "rotation_yaw_deg": round(math.degrees(math.atan2(axis_x[1], axis_x[0])), 8),
        "footprint_local_m": local_outline,
        "dimensions_x_y_m": [round(x1 - x0, 6), round(y1 - y0, 6)],
        "source_max_height_m": round(building["source_roof_m"] - origin[2], 6),
        "surface_triangulation": {"vertices_local_m": local_vertices, "ccw_faces": triangles},
        "roof_profile_local_y_z_m": profile,
        "entry": {
            "edge": edge,
            "center_local_xy_m": local(lerp(a, b, entry["fraction"])),
            "recessed_closed_opening_width_height_m": door,
            "approach_sweep_guard_profiles_m": entry["verified_offline_approach"],
        },
        "treatment": style["treatment"],
    }


def party_wall(candidate):
    shared = candidate["shared_party_wall"]
    rings = {b["id"]: b["footprint"] for b in candidate["buildings"]}
    first, second = (rings[identifier] for identifier in shared["connects"])
    matches = [(i, j, a, b) for i, (a, b) in enumerate(ring_edges(first))
               for j, (c, d) in enumerate(ring_edges(second)) if a == d and b == c]
    if len(matches) != 1:
        raise ValueError("Expected exactly one shared, oppositely oriented party wall.")
    i, j, a, b = matches[0]
    if abs(math.dist(a, b) - shared["length_m"]) > .001:
        raise ValueError("Measured party wall length differs from the reviewed plan.")
    return {"keep_sealed": True, "world_segment_m": [a, b], "length_m": shared["length_m"],
            "edges": dict(zip(shared["connects"], (i, j)))}


def check_road(guide, roads, rings, settings):
    if len(guide) < 2 or settings["step_max_m"] <= 0 or not settings["offsets_m"]:
        raise ValueError("A road guard needs a guide, positive step size, and sample offsets.")
    nearest, count = math.inf, 0
    length = 0.0
    for a, b in zip(guide, guide[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        span = math.hypot(dx, dy)
        if span <= 0:
            raise ValueError("Each road guard segment must have positive length.")
        length += span
        steps = math.ceil(span / settings["step_max_m"])
        for i in range(steps + 1):
            x, y = lerp(a, b, i / steps)
            for offset in settings["offsets_m"]:
                point = x - dy / span * offset, y + dx / span * offset
                if not any(nearest_on_triangle(point, t)[0] <= .0001 for t in roads.candidates((point,))):
                    raise ValueError(f"Guard point {point} leaves the exported ground road.")
                distance = min(distance_to_building(point, ring) for ring in rings)
                if distance < settings["minimum_footprint_clearance_m"]:
                    raise ValueError(f"Guard point {point} is too close to a source footprint.")
                nearest = min(nearest, distance)
                count += 1
    return {"length_m": round(length, 3), "sample_count": count,
            "minimum_distance_to_footprint_m": round(nearest, 3)}


def plan(source, candidate_path, settings_path):
    candidate, settings = read_json(candidate_path), read_json(settings_path)
    if digest(source.read_bytes()) != candidate["source_export_sha256"]:
        raise ValueError("The source GLB differs from the reviewed candidate export.")
    document, blob = read_glb(source)
    reviewed_faces(document, blob, candidate)
    roof = faces(document, blob, candidate["roof_primitive"], candidate["source_origin_m"])
    styles = settings["building_styles"]
    if set(styles) != {b["id"] for b in candidate["buildings"]}:
        raise ValueError("Style settings must cover exactly the reviewed building IDs.")
    buildings = [building_input(b, styles[b["id"]], roof) for b in candidate["buildings"]]
    controls = settings["road_sampling"]
    road_faces = faces(document, blob, settings["road_primitive"], candidate["source_origin_m"])
    if {point[2] for triangle in road_faces for point in triangle} != {controls["exported_road_z_m"]}:
        raise ValueError("The source road no longer has the reviewed floor elevation.")
    road = road_triangles(document, blob, {"road_primitive": settings["road_primitive"],
                                          "origin_m": candidate["source_origin_m"]})
    rings = [b["footprint"] for b in candidate["buildings"]]
    return {
        "coordinate_system": "ue_local_m",
        "status": "offline_generation_input",
        "source_tile": candidate["source_tile"],
        "source_export_sha256": candidate["source_export_sha256"],
        "reviewed_candidate": candidate_path.name,
        "frame": "+X points out of the door, +Y is its counterclockwise horizontal rotation, and +Z is up.",
        "geometry_contract": [
            "Seal every footprint edge, including party walls and decorative recessed exterior doors.",
            "Use the triangulation for the bottom cap and as the plan mesh for the roof.",
            "Split roof triangles and wall top edges at every profile Y knot before interpolating Z.",
            "Keep roofs, trims, jetties and sills within each source footprint and source max height.",
            "Preserve source collision during visual review and compare rooftop traversal before release.",
        ],
        "buildings": buildings,
        "party_wall": party_wall(candidate),
        "road_sampling": controls,
        "local_road_corridors": [
            {"name": name, "guide_m": guide, **check_road(guide, road, rings, controls)}
            for name, guide in settings["local_road_corridors"].items()
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "candidate", "settings", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.output.resolve() in {p.resolve() for p in (args.source, args.candidate, args.settings)}:
        parser.error("Use a separate output file.")
    result = plan(args.source, args.candidate, args.settings)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Planned {len(result['buildings'])} closed buildings and checked "
          f"{sum(route['sample_count'] for route in result['local_road_corridors'])} road guards.")


if __name__ == "__main__":
    main()
