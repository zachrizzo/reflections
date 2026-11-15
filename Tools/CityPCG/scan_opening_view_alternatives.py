"""Check which nearby source buildings intersect the saved opening camera view."""

from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import sys

if __name__ == "__main__":
    sys.dont_write_bytecode = True

from extract_building_shells import boundary_ring, faces, signed_area
from extract_tile_frontages import read_glb
from group_stacked_roofs import triangle_intersection
from plan_whole_building_replacements import distance_to_building
from subtract_building_shells import digest, read_json, triangle_signature
from verify_spawn_building_review import ART, DEFAULT_REVIEW, PROJECT, SOURCE, WEIGH_HOUSE


RANGES = {"south": range(6982, 6990), "first_view": range(5014, 5030), "north": range(6950, 6982)}
ELEVATIONS = (-12, 0, 12, 24, 36)
NEAR_RANGE_M = 70
START_M = [3292.9, 310.9, 1.1]
CAMERA_PATH = Path("Saved/CityPCG/rebuilt_play_audit.json")


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def delta(a, b):
    return tuple(x - y for x, y in zip(a, b))


def ray_distance(direction, triangle):
    edge1, edge2, offset = triangle
    normal = cross(direction, edge2)
    determinant = dot(edge1, normal)
    if abs(determinant) < 1e-9:
        return math.inf
    reciprocal = 1 / determinant
    u = dot(offset, normal) * reciprocal
    q = cross(offset, edge1)
    v = dot(direction, q) * reciprocal
    t = dot(edge2, q) * reciprocal
    if u >= -1e-9 and v >= -1e-9 and u + v <= 1 + 1e-9 and 0 < t <= NEAR_RANGE_M:
        return t
    return math.inf


def footprint_edge(vertices):
    return tuple(sorted({vertex[:2] for vertex in vertices}))


def survey_shells(source, review):
    markers = read_json(PROJECT / "ArtDirection/WorldJump/graylondon_markers.json")
    opening = read_json(PROJECT / ART / "opening_frontage_plan.json")
    mark_lane = read_json(PROJECT / ART / "Verified/mark_lane_conversion_plan.json")
    x0, y0, x1, y1 = review["quest_blockers"][WEIGH_HOUSE]["protected_rectangle_m"]
    reservation = [((x0, y0), (x1, y0), (x1, y1)), ((x0, y0), (x1, y1), (x0, y1))]
    wall, roofs = source[0], source[1]
    folded_walls, folded_roofs = (list(map(triangle_signature, rows)) for rows in (wall, roofs))
    wall_counts, roof_counts = Counter(folded_walls), Counter(folded_roofs)
    owners, evidence = defaultdict(set), {}
    for name, wall_ids in RANGES.items():
        boundary = {footprint_edge(wall[i] + wall[i + 1]) for i in range(wall_ids.start, wall_ids.stop, 2)}
        ring = boundary_ring(boundary)
        if len(ring) != len(boundary):
            raise ValueError(f"The observed {name} source walls do not form the recorded ring.")
        corners = set(ring)
        roof_ids = [i for i, triangle in enumerate(roofs)
                    if all(p[:2] in corners and p[2] == 15.0 for p in triangle)]
        for i, triangle in enumerate(wall):
            if footprint_edge(triangle) in boundary and {p[2] for p in triangle} == {.2, 15.}:
                owners[0, i].add(name)
        for i in roof_ids:
            owners[1, i].add(name)
        # Coincident South roof covers must contribute only once to the protected-area test.
        unique_cap = {folded_roofs[i]: roofs[i] for i in roof_ids}
        overlap = sum(triangle_intersection([p[:2] for p in triangle], patch)
                      for triangle in unique_cap.values() for patch in reservation)
        evidence[name] = {
            "status": "blocked_review_only",
            "area_m2": round(abs(signed_area(ring)), 6),
            "footprint_m": ring,
            "wall_faces_observed": list(wall_ids),
            "roof_faces_observed": roof_ids,
            "wall_faces_with_duplicate_signatures": sum(wall_counts[folded_walls[i]] > 1 for i in wall_ids),
            "roof_faces_with_duplicate_signatures": sum(roof_counts[folded_roofs[i]] > 1 for i in roof_ids),
            "marker_projections_inside": [m["name"] for m in markers
                                          if distance_to_building((m["east_m"], m["north_m"]), ring) <= .0001],
            "weigh_house_overlap_m2": round(overlap, 6),
            "opening_and_mark_lane_facade_points": [
                point.get("label") or point["id"]
                for plan in (opening, mark_lane) for cell in plan["cells"] for point in cell["points"]
                if distance_to_building([v / 100 for v in point["location_cm"][:2]], ring) <= .65
            ],
        }
    return owners, evidence


def scan():
    review = read_json(DEFAULT_REVIEW)
    source_path = PROJECT / SOURCE
    if review["status"] != "blocked_review_only" or digest(source_path.read_bytes()) != review["source_export_sha256"]:
        raise ValueError("Use the blocked first-view review and its original tile export.")
    camera = read_json(PROJECT / CAMERA_PATH)["crowd"]
    if camera["map"] != "/Game/GrayLondon/Maps/GrayLondon_Geodata" or [
        v / 100 for v in camera["lanthorne_start_cm"]
    ] != START_M:
        raise ValueError("The saved camera belongs to a different map or opening spawn.")
    origin = [v / 100 for v in camera["camera_location_cm"]]
    document, blob = read_glb(source_path)
    source = [faces(document, blob, slot, [3000, 0, 0]) for slot in range(6)]
    owners, shells = survey_shells(source, review)

    local = []
    for slot, triangles in enumerate(source):
        for index, (a, b, c) in enumerate(triangles):
            if all(max(p[axis] for p in (a, b, c)) >= origin[axis] - NEAR_RANGE_M and
                   min(p[axis] for p in (a, b, c)) <= origin[axis] + NEAR_RANGE_M for axis in (0, 1)):
                local.append(((slot, index), (delta(b, a), delta(c, a), delta(origin, a))))

    fans = {}
    for elevation in ELEVATIONS:
        pitch = math.radians(elevation)
        samples = []
        for offset in range(-44, 45, 4):
            yaw = camera["camera_yaw"] + offset
            angle = math.radians(yaw)
            direction = (math.cos(pitch) * math.cos(angle), math.cos(pitch) * math.sin(angle), math.sin(pitch))
            distance, element = min((ray_distance(direction, triangle), address) for address, triangle in local)
            classification = "no_tile_hit"
            if math.isfinite(distance):
                classification = "+".join(sorted(owners.get(element, [])))
                if not classification:
                    classification = "other_building" if element[0] in (0, 1, 5) else "ground"
            samples.append({"yaw_deg": yaw, "hit": classification,
                            "primitive_and_face": element if math.isfinite(distance) else None,
                            "distance_m": round(distance, 3) if math.isfinite(distance) else None})
        fans[elevation] = {"counts": dict(Counter(row["hit"] for row in samples)), "samples": samples}

    return {"status": "review_only", "source_export_sha256": review["source_export_sha256"],
            "camera_source": str(CAMERA_PATH), "camera_origin_m": origin, "camera_yaw_deg": camera["camera_yaw"],
            "probe_max_distance_m": NEAR_RANGE_M, "shells": shells, "view_fans_by_elevation_deg": fans}


if __name__ == "__main__":
    print(json.dumps(scan(), indent=2))
