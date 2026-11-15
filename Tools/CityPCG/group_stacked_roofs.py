"""Find geometrically supported roof stacks in a reviewed Gray London inventory."""

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

from extract_building_shells import faces, signed_area
from extract_tile_frontages import SpatialBins, det, lerp, read_glb, vector


HEIGHT_OFFSETS_M = (0.0, 0.2)
HEIGHT_TOLERANCE_M = .015
MIN_FOOTPRINT_FRACTION = .95
MIN_HEIGHT_MATCH_FRACTION = .95
MIN_WALL_BEARING_FRACTION = .90
MIN_ALIGNED_WALL_M = .75
GROUND_SHELLS = {"complete_ground_shell", "complete_ground_courtyard"}
ELIGIBLE = GROUND_SHELLS | {"raised_foundations", "varying_foundations", "missing_wall", "ambiguous_wall"}


def ring_edges(ring):
    return tuple(zip(ring, (*ring[1:], ring[0])))


@dataclass(frozen=True)
class Wall:
    a: tuple
    b: tuple
    base: float
    face_ids: tuple

    @property
    def length(self):
        return math.dist(self.a, self.b)


@dataclass(frozen=True)
class Roof:
    id: str
    top: float
    classification: str
    rings: tuple
    triangles: tuple
    face_ids: tuple
    walls: tuple

    @property
    def outline(self):
        return self.rings[0]

    @property
    def perimeter(self):
        return sum(math.dist(a, b) for ring in self.rings for a, b in ring_edges(ring))

    @property
    def area(self):
        return sum(abs(signed_area(triangle)) for triangle in self.triangles)


def load_roofs(entries, source_roof, source_wall):
    for entry in entries:
        if entry["classification"] not in ELIGIBLE:
            continue
        rings = tuple(tuple(map(tuple, ring)) for ring in [entry["footprint_m"], *entry.get("courtyards_m", [])])
        boundaries = tuple(map(ring_edges, rings))
        ids = tuple(entry["roof_faces"])
        top = entry["roof_height_m"]
        if not ids or any(type(i) is not int or not 0 <= i < len(source_roof) for i in ids):
            raise ValueError(f"Invalid roof face addresses for {entry['id']}.")
        source = [source_roof[i] for i in ids]
        if any(point[2] != top for triangle in source for point in triangle):
            raise ValueError(f"Inventory roof height differs from its source faces for {entry['id']}.")
        triangles = tuple(tuple(point[:2] for point in triangle) for triangle in source)
        walls = tuple(Wall(*boundaries[match["ring"]][match["edge"]],
                           match["base_m"], tuple(match["wall_faces"])) for match in entry["wall_matches"])
        for wall in walls:
            if len(wall.face_ids) != 2 or any(type(i) is not int or not 0 <= i < len(source_wall)
                                             for i in wall.face_ids):
                raise ValueError(f"Invalid wall face addresses for {entry['id']}.")
            corners = {(*xy, z) for xy in (wall.a, wall.b) for z in (wall.base, top)}
            wall_vertices = {p for i in wall.face_ids for p in source_wall[i]}
            if wall_vertices != corners:
                raise ValueError(f"Inventory wall coordinates differ from source for {entry['id']}.")
        yield Roof(entry["id"], top, entry["classification"], rings, triangles, ids, walls)


def triangle_intersection(a, b):
    """Return the planar intersection area of two roof triangles."""
    polygon = list(a)
    area = signed_area(b)
    if not area:
        return 0.0
    side = 1 if area > 0 else -1
    for start, end in ring_edges(b):
        edge = vector(start, end)
        clipped = []
        for p, q in ring_edges(polygon):
            dp = side * det(edge, vector(start, p))
            dq = side * det(edge, vector(start, q))
            if (dp >= 0) != (dq >= 0):
                clipped.append(lerp(p, q, dp / (dp - dq)))
            if dq >= 0:
                clipped.append(q)
        if len(clipped) < 3:
            return 0.0
        polygon = clipped
    return abs(signed_area(polygon))


def segment_in_triangle(a, b, triangle):
    """Return the parameter interval where an upper wall sits on a lower roof face."""
    left, right = 0.0, 1.0
    area = signed_area(triangle)
    if not area:
        return None
    side = 1 if area > 0 else -1
    for start, end in ring_edges(triangle):
        edge = vector(start, end)
        epsilon = 1e-7
        p = side * det(edge, vector(start, a)) + epsilon
        q = side * det(edge, vector(start, b)) + epsilon
        if p < 0 and q < 0:
            return None
        if (p < 0) != (q < 0):
            t = p / (p - q)
            if p < 0:
                left = max(left, t)
            else:
                right = min(right, t)
    return (left, right) if right > left else None


def aligned_interval(a, b, c, d):
    dx, dy = vector(a, b)
    length_sq = dx * dx + dy * dy
    if not length_sq:
        return None
    length = math.sqrt(length_sq)
    if any(abs(det((dx, dy), vector(a, p))) > length * .005 for p in (c, d)):
        return None
    one, two = sorted(((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length_sq for p in (c, d))
    left, right = max(0.0, one), min(1.0, two)
    return (left, right) if right > left else None


def interval_fraction(intervals):
    total = end = 0.0
    for left, right in sorted(interval for interval in intervals if interval is not None):
        total += max(0.0, right - max(end, left))
        end = max(end, right)
    return total


def matched_offset(base, top):
    gap = base - top
    match = min(HEIGHT_OFFSETS_M, key=lambda offset: abs(offset - gap))
    return match if abs(match - gap) <= HEIGHT_TOLERANCE_M else None


def relation(lower, upper):
    """Measure actual support and keep shared walls distinct from inset bearing."""
    if lower.top >= upper.top:
        return {"status": "not_height_ordered"}
    matched = [(wall, gap) for wall in upper.walls
               if (gap := matched_offset(wall.base, lower.top)) is not None]
    if not matched:
        return {"status": "no_height_transition"}
    area = sum(triangle_intersection(a, b) for a in upper.triangles for b in lower.triangles)
    overlap = min(1.0, area / upper.area)
    height = sum(wall.length for wall, _ in matched) / upper.perimeter
    bearing = sum(wall.length * interval_fraction(segment_in_triangle(wall.a, wall.b, triangle)
                                                  for triangle in lower.triangles)
                  for wall, _ in matched) / upper.perimeter
    aligned = sum(wall.length * interval_fraction(aligned_interval(wall.a, wall.b, other.a, other.b)
                                                  for other in lower.walls)
                  for wall, _ in matched)
    if overlap < MIN_FOOTPRINT_FRACTION:
        status = "insufficient_footprint_overlap"
    elif height < MIN_HEIGHT_MATCH_FRACTION:
        status = "incomplete_height_transition"
    elif bearing < MIN_WALL_BEARING_FRACTION:
        status = "insufficient_wall_bearing"
    else:
        status = "aligned_wall_continuation" if aligned >= MIN_ALIGNED_WALL_M else "inset_wall_bearing"
    return {
        "status": status,
        "overlap_m2": round(area, 3),
        "upper_footprint_overlap_fraction": round(overlap, 5),
        "upper_height_matched_perimeter_fraction": round(height, 5),
        "upper_roof_supported_perimeter_fraction": round(bearing, 5),
        "shared_wall_length_m": round(aligned, 3),
        "height_matched_upper_wall_face_ids": sorted(i for wall, _ in matched for i in wall.face_ids),
        "height_offsets_m": sorted({gap for _, gap in matched}),
    }


def bounds_overlap(a, b):
    for axis in (0, 1):
        a1, a2 = min(p[axis] for p in a), max(p[axis] for p in a)
        b1, b2 = min(p[axis] for p in b), max(p[axis] for p in b)
        if a1 > b2 or b1 > a2:
            return False
    return True


def inspect_relations(roofs):
    spatial = SpatialBins(roofs, lambda roof: roof.outline, size=32)
    for upper in roofs:
        if not any(wall.base > .75 for wall in upper.walls):
            continue
        for lower in sorted(spatial.candidates(upper.outline), key=lambda r: r.id):
            if not bounds_overlap(lower.outline, upper.outline):
                continue
            result = relation(lower, upper)
            if result["status"] not in {"not_height_ordered", "no_height_transition"}:
                yield {"lower": lower.id, "upper": upper.id, **result}


def select_links(relations):
    possible = defaultdict(list)
    for row in relations:
        if row["status"] in {"aligned_wall_continuation", "inset_wall_bearing"}:
            possible[row["upper"]].append(row)
    selected = []
    for _, rows in sorted(possible.items()):
        if len(rows) == 1:
            selected.append(rows[0])
        else:
            for row in rows:
                row["evidence_status"] = row["status"]
                row["status"] = "ambiguous_support"
    return selected


def clusters(roofs, links, roof_faces, wall_faces):
    by_id = {roof.id: roof for roof in roofs}
    children = defaultdict(list)
    for link in links:
        children[link["lower"]].append(link)
    supported = {row["upper"] for row in links}
    roof_frequency, wall_frequency = (Counter(tuple(sorted(triangle)) for triangle in source)
                                      for source in (roof_faces, wall_faces))
    claims = {
        "roof": Counter(i for part in roofs for i in part.face_ids),
        "wall": Counter(i for part in roofs for wall in part.walls for i in wall.face_ids),
    }
    for root in sorted(children.keys() - supported):
        pending, members, bonds = [root], [], []
        while pending:
            part = pending.pop()
            members.append(by_id[part])
            bonds.extend(children[part])
            pending.extend(row["upper"] for row in children[part])
        member_ids = sorted(part.id for part in members)
        roof_ids = [i for member in members for i in member.face_ids]
        wall_ids = [i for member in members for wall in member.walls for i in wall.face_ids]
        conflicts = {}
        for name, ids, source, frequency in (("roof", roof_ids, roof_faces, roof_frequency),
                                              ("wall", wall_ids, wall_faces, wall_frequency)):
            conflicts[name] = sorted(i for i in set(ids)
                                     if claims[name][i] != 1 or frequency[tuple(sorted(source[i]))] != 1)
        local = [p for member in members for p in member.outline]
        yield {
            "id": "stack_" + hashlib.sha256("|".join(member_ids).encode("ascii")).hexdigest()[:16],
            "members": member_ids,
            "ground_root": root if by_id[root].classification in GROUND_SHELLS else None,
            "bounds_m": [min(p[0] for p in local), min(p[1] for p in local),
                         max(p[0] for p in local), max(p[1] for p in local)],
            "roof_elevations_m": sorted({member.top for member in members}),
            "links": sorted(bonds, key=lambda row: (row["lower"], row["upper"])),
            "roof_face_ids": sorted(set(roof_ids)),
            "wall_face_ids": sorted(set(wall_ids)),
            "duplicate_triangle_geometry_or_claims": conflicts,
            "unresolved_wall_components": sorted(m.id for m in members if m.classification in
                                                 {"missing_wall", "ambiguous_wall", "varying_foundations"}),
            "neighbor_protection_review": "pending",
            "replacement_ready": False,
        }


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def group(source, metadata_path, inventory_path):
    metadata, inventory = read_json(metadata_path), read_json(inventory_path)
    tile = metadata["tile"] if isinstance(metadata["tile"], dict) else metadata
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if (digest != inventory["source_sha256"] or tile["tile"] != inventory["tile"]
            or tile["origin_m"] != inventory["source_origin_m"]):
        raise ValueError("The inventory or origin belongs to a different source export.")
    slots = list(tile["primitives"])
    document, blob = read_glb(source)
    roof_faces, wall_faces = (faces(document, blob, slots.index(slot), tile["origin_m"])
                              for slot in ("GL_Roof", "GL_Facade"))
    roofs = sorted(load_roofs(inventory["roofs"], roof_faces, wall_faces), key=lambda roof: roof.id)
    if len({roof.id for roof in roofs}) != len(roofs):
        raise ValueError("The inventory contains duplicate roof component IDs.")
    relations = list(inspect_relations(roofs))
    links = select_links(relations)
    return {
        "tile": tile["tile"],
        "source_sha256": digest,
        "source_origin_m": tile["origin_m"],
        "coordinate_system": "ue_local_m",
        "review_scope": "Geometric candidates. Authored neighbors and original building/OSM ownership need additional review.",
        "thresholds": {
            "height_offsets_m": HEIGHT_OFFSETS_M, "height_tolerance_m": HEIGHT_TOLERANCE_M,
            "min_upper_footprint_overlap_fraction": MIN_FOOTPRINT_FRACTION,
            "min_upper_height_match_fraction": MIN_HEIGHT_MATCH_FRACTION,
            "min_upper_wall_bearing_fraction": MIN_WALL_BEARING_FRACTION,
            "min_aligned_shared_wall_m": MIN_ALIGNED_WALL_M,
        },
        "classified_roof_components": len(roofs),
        "relation_counts": dict(sorted(Counter(row["status"] for row in relations).items())),
        "relations": relations,
        "clusters": list(clusters(roofs, links, roof_faces, wall_faces)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "metadata", "inventory", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.output.resolve() in {p.resolve() for p in (args.source, args.metadata, args.inventory)}:
        parser.error("Choose an output separate from the source files.")
    report = group(args.source, args.metadata, args.inventory)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['tile']}: {len(report['clusters'])} review-only roof stack candidates.")


if __name__ == "__main__":
    main()
