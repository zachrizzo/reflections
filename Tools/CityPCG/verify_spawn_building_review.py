"""Verify the blocked first-view building review without writing any files."""

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import sys

if __name__ == "__main__":
    sys.dont_write_bytecode = True

from extract_building_shells import edges, faces, signed_area
from extract_tile_frontages import SpatialBins, det, read_glb, vector, wall_groups
from group_stacked_roofs import ring_edges, triangle_intersection
from plan_whole_building_replacements import distance_to_building
from subtract_building_shells import digest, read_json, reviewed_faces


PROJECT = Path(__file__).resolve().parents[2]
ART = Path("ArtDirection/CityPCG/MedievalOpening")
DEFAULT_REVIEW = PROJECT / ART / "spawn_first_view_whole_building_review.json"
SOURCE = Path("Saved/CityPCG/Tile_p03_p00.glb")
WEIGH_HOUSE = "Seething Lane Garden, Weigh-House and watch gate"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_boundary(shell, roof, wall):
    ring = tuple(map(tuple, shell["footprint_m"]))
    pairs = shell["wall_faces_by_ring_edge"]
    require(len(ring) == len(pairs) and len(ring) >= 3 and signed_area(ring) > 0,
            "The recorded footprint and wall-edge list disagree.")
    floor, height = shell["foundation_m"], shell["source_roof_m"]
    by_edge = defaultdict(list)
    for ordinal, triangle in enumerate(wall):
        xy = tuple(sorted({point[:2] for point in triangle}))
        if len(xy) == 2:
            by_edge[xy].append(ordinal)
    seams = []
    for index, (a, b) in enumerate(ring_edges(ring)):
        own = pairs[index]
        ids = own["ordinary_wall_faces"]
        corners = {(*point, z) for point in (a, b) for z in (floor, height)}
        require(own["edge"] == index and {p for face in ids for p in wall[face]} == corners,
                f"The wall triangles no longer close footprint edge {index}.")
        relatives = [face for face in by_edge[tuple(sorted((a, b)))] if face not in ids]
        if relatives:
            seams.append({"edge": index, "segment_m": [list(a), list(b)], "own_faces": ids,
                          "retain_neighbor_faces": relatives})
    require(seams == shell["party_wall_review"], "The recorded party-wall triangles differ.")

    ids = set(shell["roof_face_ordinals"])
    triangles = [roof[index] for index in sorted(ids)]
    topology = Counter(edge for triangle in triangles for edge in edges(triangle))
    expected = {tuple(sorted((a, b))) for a, b in ring_edges(ring)}
    actual = {tuple(p[:2] for p in edge) for edge, count in topology.items() if count == 1}
    require(max(topology.values()) == 2 and actual == expected and
            all(p[2] == height for triangle in triangles for p in triangle),
            "The recorded roof is not a closed cap on the footprint boundary.")
    area = sum(abs(signed_area([p[:2] for p in triangle])) for triangle in triangles)
    require(math.isclose(area, signed_area(ring), abs_tol=1e-6) and
            round(area, 6) == shell["area_m2"], "The roof and footprint areas differ.")

    projected = [(i, tuple(p[:2] for p in triangle)) for i, triangle in enumerate(roof) if i not in ids]
    adjacent = SpatialBins(projected, lambda row: row[1])
    overlaps = {i for triangle in triangles for points in [tuple(p[:2] for p in triangle)]
                for i, other in adjacent.candidates(points) if triangle_intersection(points, other) > 1e-5}
    require(not overlaps and shell["other_projected_roof_overlap_count"] == 0,
            f"Other roof faces overlap the reviewed cap: {sorted(overlaps)}.")
    return ring, triangles, sum(len(row["retain_neighbor_faces"]) for row in seams)


def verify_rays(spawn, ring, walls):
    expected = spawn["rays"]
    origin = spawn["location_m"][:2]
    height = spawn["ray_origin_z_m"]
    outline = {tuple(sorted(edge)) for edge in ring_edges(ring)}
    yaws = range(spawn["yaw_deg"] - 44, spawn["yaw_deg"] + 45, 4)
    require([row["yaw_deg"] for row in expected] == list(yaws), "The 23-ray view fan differs.")
    hit_count = 0
    for row in expected:
        yaw = math.radians(row["yaw_deg"])
        direction = math.cos(yaw), math.sin(yaw)
        hits = []
        for slot, a, b, base, top, _ in walls:
            if not base <= height <= top:
                continue
            line = vector(a, b)
            determinant = det(direction, line)
            if abs(determinant) < 1e-8:
                continue
            offset = vector(origin, a)
            distance, fraction = det(offset, line) / determinant, det(offset, direction) / determinant
            if distance > 0 and 0 <= fraction <= 1:
                hits.append((distance, slot, a, b, top))
        require(bool(hits), f"Spawn ray at {row['yaw_deg']}° no longer hits a wall.")
        distance, slot, a, b, top = min(hits)
        isolated = tuple(sorted((a, b))) in outline
        require([round(distance, 3), slot, [list(a), list(b)], top, isolated] ==
                [row["distance_m"], row["primitive"], row["wall_m"], row["source_roof_height_m"],
                 row["isolated_shell_hit"]], f"Spawn ray evidence changed at {row['yaw_deg']}°.")
        hit_count += isolated
    return hit_count


def verify_quests(project, evidence, ring, triangles):
    nearby = []
    for marker in read_json(project / "ArtDirection/WorldJump/graylondon_markers.json"):
        point = [marker["east_m"], marker["north_m"]]
        radius = marker["radius"] / 100
        distance = distance_to_building(point, ring)
        if distance <= max(25, radius):
            nearby.append({"name": marker["name"], "xy_m": point, "planned_z_m": marker["z_m"],
                           "configured_radius_m": radius, "distance_to_ring_m": round(distance, 3),
                           "xy_inside_or_on_ring": distance <= .0001})
    require(nearby == evidence["nearby_marker_projections"], "The story-marker overlap evidence differs.")

    masks = read_json(project / ART / "tower_approach_west_corridor.json")["protected_landmarks"]
    limits = next(row["bounds_m"] for row in masks if row["label"] == WEIGH_HOUSE)
    recorded = evidence[WEIGH_HOUSE]
    x0, y0, x1, y1 = limits
    a, b, c, d = (x0, y0), (x1, y0), (x1, y1), (x0, y1)
    area = sum(triangle_intersection([p[:2] for p in triangle], part)
               for triangle in triangles for part in ((a, b, c), (a, c, d)))
    require(limits == recorded["protected_rectangle_m"] and round(area, 6) == recorded["intersection_m2"],
            "The protected Weigh-House overlap differs.")
    return round(area, 6), [row["name"] for row in nearby if row["xy_inside_or_on_ring"]]


def verify(review_path=DEFAULT_REVIEW, project=PROJECT):
    review = read_json(review_path)
    require(review["status"] == "blocked_review_only" and review["coordinate_system"] == "ue_local_m",
            "The opening review must retain its blocked_review_only status and Unreal metre frame.")
    require(Path(review["source_export_file"]) == SOURCE, "The opening review names a different source export.")
    source_path = project / SOURCE
    source_hash = digest(source_path.read_bytes())
    require(source_hash == review["source_export_sha256"], "The pinned source export hash differs.")
    metadata = read_json(source_path.with_suffix(".asset.json"))
    origin, slots = metadata["origin_m"], list(metadata["primitives"])
    shell = review["shell_geometry"]
    wall_slot, roof_slot = shell["source_ordinary_wall_primitive"], shell["source_ordinary_roof_primitive"]
    require(slots[wall_slot] == "GL_Facade" and slots[roof_slot] == "GL_Roof" and
            review["source_tile_actor"] == f"OSM {metadata['tile']}", "The reviewed source slots or tile differ.")
    document, blob = read_glb(source_path)
    pairs = shell["wall_faces_by_ring_edge"]
    selected, _ = reviewed_faces(document, blob, {
        "source_origin_m": origin, "ordinary_wall_primitive": wall_slot, "roof_primitive": roof_slot,
        "buildings": [{"id": review["name"], "source_wall_faces_by_edge": [row["ordinary_wall_faces"] for row in pairs],
                       "wall_triangle_signature_by_edge": [row["wall_signatures"] for row in pairs],
                       "source_roof_faces": shell["roof_face_ordinals"],
                       "roof_triangle_signatures": shell["roof_signatures"]}],
    })
    wall, roof = (faces(document, blob, slot, origin) for slot in (wall_slot, roof_slot))
    ring, triangles, retained = verify_boundary(shell, roof, wall)
    walls = [(slot, *entry) for slot in (wall_slot, slots.index("GL_CentralFacade"))
             for entry in wall_groups(document, blob, slot, origin)]
    hits = verify_rays(review["spawn"], ring, walls)
    area, inside = verify_quests(project, review["quest_blockers"], ring, triangles)
    require(digest(source_path.read_bytes()) == source_hash, "The source export changed during verification.")
    return {"status": review["status"], "source_sha256": source_hash,
            "wall_triangles": len(selected[wall_slot]), "roof_triangles": len(selected[roof_slot]),
            "retained_party_wall_triangles": retained, "spawn_rays_hitting_shell": hits, "spawn_rays": 23,
            "protected_overlap_m2": area, "inside_or_on_boundary_marker_projections": inside}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    args = parser.parse_args()
    print(json.dumps(verify(args.review), indent=2))


if __name__ == "__main__":
    main()
