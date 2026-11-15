"""Find coherent groups of ordinary, street-connected whole-building candidates."""

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path

from extract_building_shells import faces
from extract_tile_frontages import (
    SpatialBins, clip, det, lerp, nearest_on_triangle, occluded, project_to_segment, read_glb,
    road_triangles, vector, wall_groups,
)
from filter_protected_frontages import overlaps_overlay, protected_triangles
from group_stacked_roofs import aligned_interval, load_roofs, ring_edges, triangle_intersection
from plan_medieval_district import exclusion_points, represented_frontage
from plan_whole_building_replacements import distance_to_building
from subtract_building_shells import digest, read_json, reviewed_faces, triangle_signature


def bounds(points, margin=0):
    x, y = zip(*points)
    return min(x) - margin, min(y) - margin, max(x) + margin, max(y) + margin


def enclosed_and_clear(ring, protected):
    for block in protected:
        corners = [(x, y) for x in block[::2] for y in block[1::2]]
        if any(clip(a, b, block) for a, b in ring_edges(ring)) or any(
                distance_to_building(point, ring) < .001 for point in corners):
            return False
    return True


def segment_distance(a, b, c, d):
    one, two = vector(a, b), vector(c, d)
    cross = det(one, two)
    offset = vector(a, c)
    if cross and 0 <= det(offset, two) / cross <= 1 and 0 <= det(offset, one) / cross <= 1:
        return 0
    return min(project_to_segment(p, start, end)[0]
               for p, start, end in ((a, c, d), (b, c, d), (c, a, b), (d, a, b)))


def guide_distance(ring, guide):
    if any(distance_to_building(point, ring) <= .001 for point in guide):
        return 0
    return min(segment_distance(a, b, c, d) for a, b in ring_edges(ring)
               for c, d in zip(guide, guide[1:]))


def on_surface(point, surfaces):
    return any(nearest_on_triangle(point, triangle)[0] <= .0001
               for triangle in surfaces.candidates((point,)))


def approaches(shell, dry_road, walls):
    for edge, (a, b) in enumerate(ring_edges(shell.outline)):
        span = math.dist(a, b)
        if span < 3.55:
            continue
        dx, dy = vector(a, b)
        tangent = (dx / span, dy / span)
        outward = (dy / span, -dx / span)
        for fraction in (.5, .25, .75):
            if min(fraction, 1 - fraction) * span < 1.2:
                continue
            midpoint = lerp(a, b, fraction)
            profiles = []
            for index, offset in enumerate((-.75, 0, .75)):
                start = tuple(v + offset * t for v, t in zip(midpoint, tangent))
                run = 0
                for step in range(2, 39):
                    end = tuple(v + step * .25 * n for v, n in zip(start, outward))
                    run = run + 1 if dry_road(end) else 0
                    if run < 5:
                        continue
                    base = min(wall.base for wall in shell.walls)
                    if not occluded(start, end, base, walls):
                        profiles.append({
                            "tangent_offset_m": offset,
                            "wall_xy_m": [round(v, 3) for v in start],
                            "first_continuous_road_distance_m": step * .25 - 1,
                            "road_clear_to_xy_m": [round(v, 3) for v in end],
                        })
                    break
                if len(profiles) == index:
                    break
            if len(profiles) == 3:
                yield {"edge": edge, "fraction": fraction, "outward": [round(v, 6) for v in outward],
                       "minimum_clear_width_m": 1.5, "verified_offline_approach": profiles}


def frontage(shell, a, b):
    dx, dy = vector(a, b)
    span = math.hypot(dx, dy)
    return {"id": shell.id, "start": list(a), "end": list(b), "outward": [dy / span, -dx / span]}


def street_link(first, second, dry_road, walls):
    nearest = None
    for left, right in ((a, b) for a in first["entries"] for b in second["entries"]):
        a = left["verified_offline_approach"][1]["road_clear_to_xy_m"]
        b = right["verified_offline_approach"][1]["road_clear_to_xy_m"]
        distance = math.dist(a, b)
        if not .25 < distance <= 52 or nearest and distance >= nearest["length_m"]:
            continue
        dx, dy = vector(a, b)
        steps = math.ceil(distance / .75)
        points = [(x - dy * offset / distance, y + dx * offset / distance)
                  for i in range(steps + 1) for x, y in [lerp(a, b, i / steps)]
                  for offset in (-.6, 0, .6)]
        if not all(dry_road(point) and min(distance_to_building(point, member["footprint"])
                                          for member in (first, second)) >= .35 for point in points):
            continue
        if any(occluded(points[index], points[index + 3], 0.20, walls)
               for index in range(len(points) - 3)):
            continue
        nearest = {"length_m": round(distance, 3), "samples": len(points),
                   "guide_m": [a, b], "entries": [left["edge"], right["edge"]]}
    return nearest


def select_groups(buildings, dry_road, walls):
    by_id = {building["id"]: building for building in buildings}
    links, neighbors = [], defaultdict(set)
    spatial = SpatialBins(buildings, lambda row: row["footprint"], size=32)
    for first in buildings:
        x0, y0, x1, y1 = bounds(first["footprint"], 60)
        for second in spatial.candidates(((x0, y0), (x1, y1))):
            if first["id"] >= second["id"]:
                continue
            link = street_link(first, second, dry_road, walls)
            if link:
                a, b = first["id"], second["id"]
                neighbors[a].add(b)
                neighbors[b].add(a)
                links.append({"members": [a, b], **link})
    unseen, groups = set(neighbors), []
    while unseen:
        pending = [min(unseen)]
        members = set()
        while pending:
            node = pending.pop()
            if node in unseen:
                unseen.remove(node)
                members.add(node)
                pending.extend(sorted(neighbors[node]))
        buildings = [by_id[identifier] for identifier in sorted(members)]
        group_links = [link for link in links if set(link["members"]) <= members]
        groups.append(
            {"id": "block_" + digest("|".join(sorted(members)).encode("ascii"))[:12],
             "members": sorted(members),
             "bounds_m": bounds([p for shell in buildings for p in shell["footprint"]]),
             "nearest_quest_approach_m": min(shell["quest_guide_distance_m"] for shell in buildings),
             "street_links": sorted(group_links, key=lambda link: link["members"])})
    return sorted(groups, key=lambda group: (group["nearest_quest_approach_m"], group["members"]))


def tile_metadata(metadata):
    return metadata["tile"] if isinstance(metadata["tile"], dict) else metadata


def neighbor_geometry(source, metadata_path):
    tile = tile_metadata(read_json(metadata_path))
    document, blob = read_glb(source)
    roof_slot = list(tile["primitives"]).index("GL_Roof")
    roof = faces(document, blob, roof_slot, tile["origin_m"])
    if len(roof) != tile["primitives"]["GL_Roof"]:
        raise ValueError("The neighboring roof triangle count differs from its metadata.")
    return {"tile": tile["tile"], "source_sha256": digest(source.read_bytes())}, [
        tuple(p[:2] for p in triangle) for triangle in roof]


def select(source, metadata, inventory, overlay_path, settings, neighbor_paths=()):
    tile = tile_metadata(metadata)
    source_sha = digest(source.read_bytes())
    if (source_sha != inventory["source_sha256"] or inventory["tile"] != tile["tile"] or
            inventory["source_origin_m"] != tile["origin_m"]):
        raise ValueError("Inventory coordinates or geometry hash differ from the source.")
    data, blob = read_glb(source)
    origin = tile["origin_m"]
    slots = list(tile["primitives"])
    roof_slot, wall_slot = (slots.index(name) for name in ("GL_Roof", "GL_Facade"))
    roof = faces(data, blob, roof_slot, origin)
    wall = faces(data, blob, wall_slot, origin)
    central_slots = [i for i, name in enumerate(slots) if name == "GL_CentralFacade"]
    central_geometry = [tri for i in central_slots for tri in faces(data, blob, i, origin)]
    central = SpatialBins(central_geometry, lambda tri: [v[:2] for v in tri])
    roads = road_triangles(data, blob, {"road_primitive": slots.index("GL_Road"), "origin_m": origin})
    water_faces = [tuple(p[:2] for p in triangle) for i, name in enumerate(slots)
                   if name == "GL_Water" for triangle in faces(data, blob, i, origin)]
    water = SpatialBins([(a, b, c) for a, b, c in water_faces if abs(det(vector(a, b), vector(a, c))) > 1e-5],
                        lambda tri: tri)

    def dry_road(point):
        return on_surface(point, roads) and not on_surface(point, water)

    wall_shapes = [row for i in (wall_slot, *central_slots) for row in wall_groups(data, blob, i, origin)]
    walls = SpatialBins(wall_shapes, lambda row: row[:2])
    overlay = metadata.get("overlay", {"tile": tile["tile"], "origin_m": origin})
    if overlay["tile"] != tile["tile"] or overlay["origin_m"] != origin:
        raise ValueError("Anonymous Shop geometry belongs to a different tile or origin.")
    shops = protected_triangles(overlay_path, overlay["origin_m"])
    previous = exclusion_points([read_json(Path(path)) for path in settings["previous_pcg_plans"]])
    markers = read_json(Path(settings["story_markers"]))
    guard = settings["quest_road_guide_m"]
    if len(guard) < 2 or not markers:
        raise ValueError("Provide a quest road polyline and the published story markers.")
    masks = [row["bounds_m"] for path in settings["protected_corridors"] for row in
             read_json(Path(path)).get("protected_landmarks", [])] + settings["additional_mask_bounds_m"]
    masks = [(a - 1.5, b - 1.5, c + 1.5, d + 1.5) for a, b, c, d in masks]

    roof_projection = [tuple(p[:2] for p in tri) for tri in roof]
    roof_index = SpatialBins(list(enumerate(roof_projection)), lambda row: row[1])
    adjacent = [neighbor_geometry(Path(mesh), Path(meta)) for mesh, meta in neighbor_paths]
    if any(tile["tile"] == pin["tile"] for pin, _ in adjacent):
        raise ValueError("Use distinct adjacent tile exports.")
    neighbors = SpatialBins([triangle for _, portions in adjacent for triangle in portions], lambda tri: tri)
    wall_hashes, roof_hashes = ([triangle_signature(tri) for tri in array] for array in (wall, roof))
    wall_count, roof_count = Counter(wall_hashes), Counter(roof_hashes)
    counts, survivors = Counter(), []
    eligible = [entry for entry in inventory["roofs"] if entry["classification"] == "complete_ground_shell"]
    for shell in load_roofs(eligible, roof, wall):
        site = shell.outline
        a, b, c, d = settings["tile_bounds_m"][tile["tile"]]
        if not all(a <= x <= c and b <= y <= d for x, y in site):
            counts["outside_review_bounds"] += 1
            continue
        area = shell.area
        base = shell.walls[0].base
        if not 40 <= area <= 1450 or not 6.5 <= shell.top - base <= 22:
            counts["outside_initial_kit_scale"] += 1
            continue
        if not enclosed_and_clear(site, masks):
            counts["landmark_or_existing_replacement"] += 1
            continue
        marker_distance = min(
            distance_to_building((m["east_m"], m["north_m"]), site) - max(25, m["radius"] / 100)
            for m in markers
        )
        path_distance = guide_distance(site, guard)
        if marker_distance < 3 or path_distance < 1:
            counts["quest_marker_or_route_buffer"] += 1
            continue
        rows = [frontage(shell, a, b) for a, b in ring_edges(site)]
        if any(overlaps_overlay(row, overlay) for row in rows for overlay in (shops, central)):
            counts["authored_shop_or_central_facade"] += 1
            continue
        if any(represented_frontage(row, previous) for row in rows):
            counts["existing_procedural_facade"] += 1
            continue
        ids = set(shell.face_ids)
        if any(triangle_intersection(triangle, other) > .01 for triangle in shell.triangles
               for i, other in roof_index.candidates(triangle) if i not in ids):
            counts["overlapping_other_roof"] += 1
            continue
        if any(triangle_intersection(triangle, other) > .01 for triangle in shell.triangles
               for other in neighbors.candidates(triangle)):
            counts["overlapping_adjacent_tile_roof"] += 1
            continue
        if any(roof_count[roof_hashes[i]] != 1 for i in shell.face_ids) or any(
                wall_count[wall_hashes[i]] != 1 for row in shell.walls for i in row.face_ids):
            counts["nonunique_source_face_geometry"] += 1
            continue
        entries = list(approaches(shell, dry_road, walls))
        if not entries:
            counts["no_clear_road_approach"] += 1
            continue
        entries.sort(key=lambda e: (max(p["first_continuous_road_distance_m"] for p in e["verified_offline_approach"]),
                                    abs(e["fraction"] - .5), e["edge"], e["fraction"]))
        survivors.append({
            "id": shell.id,
            "footprint": site,
            "origin_m": [*site[0], base],
            "area_m2": round(area, 3),
            "base_m": base,
            "source_roof_m": shell.top,
            "source_wall_faces_by_edge": [row.face_ids for row in shell.walls],
            "source_roof_faces": shell.face_ids,
            "wall_triangle_signature_by_edge": [[wall_hashes[i] for i in row.face_ids] for row in shell.walls],
            "roof_triangle_signatures": [roof_hashes[i] for i in shell.face_ids],
            "quest_guide_distance_m": round(path_distance, 3),
            "quest_marker_buffer_clearance_m": round(marker_distance, 3),
            "entries": entries[:6],
        })
    survivors.sort(key=lambda row: row["id"])
    return {
        "tile": tile["tile"],
        "coordinate_system": "ue_local_m",
        "source_origin_m": origin,
        "source_export_sha256": source_sha,
        "reviewed_neighbor_tiles": [pin for pin, _ in adjacent],
        "overlay_export_sha256": digest(overlay_path.read_bytes()),
        "ordinary_wall_primitive": wall_slot,
        "roof_primitive": roof_slot,
        "distinct_complete_ground_shells": len(eligible),
        "excluded_counts": dict(sorted(counts.items())),
        "screened_candidates": survivors,
        "connected_groups": select_groups(survivors, dry_road, walls),
        "approval": "offline candidates pending live actor bounds, route, roof, and gameplay checks",
    }


def portable_group(result, group_id, metadata, source):
    group = next((row for row in result["connected_groups"] if row["id"] == group_id), None)
    if group is None:
        raise ValueError(f"Unknown reviewed group {group_id}.")
    tile = tile_metadata(metadata)
    slots = list(tile["primitives"])
    mesh_path = tile.get("asset") or f"{tile['package']}.{tile['package'].rsplit('/', 1)[-1]}"
    buildings = []
    for row in result["screened_candidates"]:
        if row["id"] in group["members"]:
            entries = row["entries"]
            buildings.append({**{key: value for key, value in row.items() if key != "entries"},
                              "entry": entries[0], "other_entry_options": entries[1:]})
    party_edges = []
    for i, first in enumerate(buildings):
        for second in buildings[i + 1:]:
            for left_edge, (a, b) in enumerate(ring_edges(first["footprint"])):
                for right_edge, (c, d) in enumerate(ring_edges(second["footprint"])):
                    if sum(u * v for u, v in zip(vector(a, b), vector(c, d))) >= 0:
                        continue
                    interval = aligned_interval(a, b, c, d)
                    if interval and (interval[1] - interval[0]) * math.dist(a, b) >= .75:
                        party_edges.append({
                            "edges": {first["id"]: left_edge, second["id"]: right_edge},
                            "world_segment_m": [lerp(a, b, t) for t in interval],
                            "keep_sealed": True,
                        })
    candidate = {
        "name": group_id,
        "coordinate_system": "ue_local_m",
        "status": "offline_candidate",
        "source_tile": tile["tile"],
        "source_origin_m": tile["origin_m"],
        "source_tile_asset": mesh_path,
        "source_export_sha256": result["source_export_sha256"],
        "anonymous_shop_export_sha256": result["overlay_export_sha256"],
        "ordinary_wall_primitive": result["ordinary_wall_primitive"],
        "roof_primitive": result["roof_primitive"],
        "untouched_primitives": {str(i): name for i, name in enumerate(slots) if name not in ("GL_Facade", "GL_Roof")},
        "reviewed_neighbor_tiles": result["reviewed_neighbor_tiles"],
        "bounds_m": group["bounds_m"],
        "validated_road_links": group["street_links"],
        "shared_party_walls": party_edges,
        "buildings": buildings,
        "review_before_replacement": [
            "Resolve the current source tile and protect its materials, roads and gameplay collision.",
            "Combine every previously accepted replacement mask for this tile into the derivative from the canonical export.",
            "Screen live authored actor descriptors and overlays including site-specific landmarks and quest actors.",
            "Reproduce source floor and side-wall traces, capsule sweeps along road links and door approaches, and roof access checks.",
            "Contain the replacement shells, recesses and eaves inside the original horizontal extents.",
        ],
        "attribution": "Base geometry: OpenStreetMap contributors, ODbL 1.0.",
    }
    reviewed_faces(*read_glb(source), candidate)
    return candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "metadata", "inventory", "overlay", "settings", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--neighbor", nargs=2, action="append", default=[], metavar=("GLB", "METADATA"))
    parser.add_argument("--candidate", nargs=2, metavar=("GROUP_ID", "OUTPUT"))
    args = parser.parse_args()
    inputs = (args.source, args.metadata, args.inventory, args.overlay, args.settings,
              *(Path(path) for pair in args.neighbor for path in pair))
    outputs = [args.output, *([Path(args.candidate[1])] if args.candidate else [])]
    if len(set(path.resolve() for path in outputs)) != len(outputs) or set(
            path.resolve() for path in outputs) & {path.resolve() for path in inputs}:
        parser.error("Choose outputs separate from the inputs and each other.")
    metadata = read_json(args.metadata)
    result = select(args.source, metadata, read_json(args.inventory),
                    args.overlay, read_json(args.settings), args.neighbor)
    if args.candidate:
        identifier, output = args.candidate
        candidate = portable_group(result, identifier, metadata, args.source)
        Path(output).write_text(json.dumps(candidate, indent=2) + "\n", encoding="utf-8")
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"{result['tile']}: {len(result['screened_candidates'])} screened shells in "
          f"{len(result['connected_groups'])} road-connected groups.")


if __name__ == "__main__":
    main()
