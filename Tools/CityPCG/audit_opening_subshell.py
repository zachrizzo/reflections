"""Audit the opening eight-wall loop and its roof without editing the source tile."""

import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

from extract_building_shells import boundary_ring, component_faces, edges, faces, signed_area, wall_rectangles
from extract_tile_frontages import primitive_mesh, read_glb
from inventory_building_geometry import identity, point_inside
from subtract_building_shells import triangle_signature

PROJECT = Path(__file__).resolve().parents[2]
SAVED = PROJECT / 'Saved'
CITY = SAVED / 'CityPCG'
TILE = CITY / 'Tile_p03_p00.glb'
REVIEWED_SOURCE_SHA256 = '5c946436fce01c086598966fcca3c379381b29776e1e03df2b37ada9fb4b08f4'
WALL_IDS = tuple(range(5014, 5030))


def diff(a, b):
    return tuple(x - y for x, y in zip(a, b))


def det(a, b):
    return a[0] * b[1] - a[1] * b[0]


def twice_area(polygon):
    return sum(det(a, b) for a, b in zip(polygon, polygon[1:] + polygon[:1]))


def projected(triangle):
    return [(round(point[0] * 1000), round(point[1] * 1000)) for point in triangle]


def bounds(polygon):
    return tuple(fn(p[axis] for p in polygon) for axis in (0, 1) for fn in (min, max))


def intersects(a, b):
    return max(a[0], b[0]) <= min(a[1], b[1]) and max(a[2], b[2]) <= min(a[3], b[3])


def intersection_area(first, second):
    """Exact area in square millimeters for two projected source triangles."""
    direction = twice_area(second)
    if not direction or not twice_area(first):
        return Fraction(0)
    if direction < 0:
        second = list(reversed(second))
    result = first
    for a, b in zip(second, second[1:] + second[:1]):
        segment = diff(b, a)
        clipped = []
        for start, end in zip(result, result[1:] + result[:1]):
            first_side = det(segment, diff(start, a))
            last_side = det(segment, diff(end, a))
            if first_side >= 0:
                clipped.append(start)
            if (first_side >= 0) != (last_side >= 0):
                t = Fraction(first_side, first_side - last_side)
                clipped.append(tuple(value + t * delta for value, delta in zip(start, diff(end, start))))
        result = clipped
        if len(result) < 3:
            return Fraction(0)
    return abs(Fraction(twice_area(result), 2))


def point_segment_distance(point, a, b):
    edge = diff(b, a)
    relative = diff(point, a)
    along = max(0, min(1, sum(x * y for x, y in zip(edge, relative)) / sum(x * x for x in edge)))
    return math.dist(point, tuple(x + along * y for x, y in zip(a, edge)))


def distance_to_ring(point, ring):
    return min(point_segment_distance(point, a, b) for a, b in zip(ring, ring[1:] + ring[:1]))


def signature_rows(faces_by_primitive, selected):
    counts = Counter(triangle_signature(triangle) for triangle in faces_by_primitive)
    result = {}
    for ordinal in selected:
        signature = triangle_signature(faces_by_primitive[ordinal])
        result[ordinal] = {'signature': signature, 'global_frequency': counts[signature]}
    return result


def projected_overlaps(target_triangles, others, subset):
    minmax = bounds([point for poly in target_triangles for point in poly])
    overlaps = []
    for ordinal, triangle in enumerate(others):
        if ordinal in subset:
            continue
        candidate = projected(triangle)
        if not intersects(minmax, bounds(candidate)):
            continue
        area = sum(intersection_area(poly, candidate) for poly in target_triangles)
        if area > 0:
            overlaps.append({'retained_face': ordinal, 'area_m2': round(float(area) / 1e6, 8),
                             'height_range_m': [min(p[2] for p in triangle), max(p[2] for p in triangle)]})
    return overlaps


def audit(source):
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if source_hash != REVIEWED_SOURCE_SHA256:
        raise ValueError('Source GLB does not match the pinned p03_p00 tile export')
    metadata = json.loads((CITY / 'Tile_p03_p00.asset.json').read_text())
    document, blob = read_glb(source)
    if hashlib.sha256(source.read_bytes()).hexdigest() != source_hash:
        raise ValueError('Source GLB changed while the geometry was being read')
    origin = metadata['origin_m']
    if origin != [3000, 0, 0] or list(metadata['primitives'])[:2] != ['GL_Facade', 'GL_Roof']:
        raise ValueError('Source tile origin or primitive addresses changed')
    walls, roof = (faces(document, blob, primitive, origin) for primitive in (0, 1))
    authored = faces(document, blob, 5, origin)
    rectangles = wall_rectangles([walls[ordinal] for ordinal in WALL_IDS])
    if len(rectangles) != 8 or len({z for _, z in rectangles}) != 1 or any(len(rows) != 1 for rows in rectangles.values()):
        raise RuntimeError('The selected wall ordinals no longer form eight equal-height rectangles')
    top = next(iter(rectangles))[1]
    bases = {rows[0][0] for rows in rectangles.values()}
    if len(bases) != 1:
        raise RuntimeError('The selected wall loop has inconsistent foundation heights')
    ring = boundary_ring([edge for edge, _ in rectangles])
    if len(ring) != 8:
        raise RuntimeError('The selected wall rectangles do not close')
    if signed_area(ring) < 0:
        ring = [ring[0], *reversed(ring[1:])]
    roof_ids = [i for i, triangle in enumerate(roof) if all(point[2] == top and point[:2] in ring for point in triangle)]
    if roof_ids != list(range(2279, 2285)):
        raise RuntimeError('The source export does not resolve the six reviewed roof ordinals')
    subset = set(roof_ids)
    boundary = {tuple(sorted((a + (top,), b + (top,)))) for a, b in zip(ring, ring[1:] + ring[:1])}
    topology = Counter(edge for ordinal in roof_ids for edge in edges(roof[ordinal]))
    if {edge for edge, count in topology.items() if count == 1} != boundary or max(topology.values()) != 2:
        raise RuntimeError('Roof subset does not have the exact wall loop as its only boundary')
    area = abs(twice_area(projected(ring)))
    if area != sum(abs(twice_area(projected(roof[i]))) for i in roof_ids):
        raise RuntimeError('Roof subset area does not equal the eight-wall plan')
    for pos, ordinal in enumerate(roof_ids):
        if any(intersection_area(projected(roof[ordinal]), projected(roof[other])) for other in roof_ids[pos + 1:]):
            raise RuntimeError('Selected roof triangles overlap each other')

    source_component = next(component for component in component_faces(roof) if roof_ids[0] in component)
    if not subset <= set(source_component):
        raise RuntimeError('Expected all six cap triangles within the same source component')
    adjacent = defaultdict(list)
    for ordinal in source_component:
        if ordinal not in subset:
            for edge in edges(roof[ordinal]):
                if edge in topology:
                    adjacent[edge].append(ordinal)

    _, normals, indices = primitive_mesh(document, blob, 0, origin)
    wall_keys = defaultdict(list)
    for ordinal, triangle in enumerate(walls):
        xy = tuple(sorted({point[:2] for point in triangle}))
        if len(xy) == 2 and (xy, top) in rectangles:
            directions = [normals[index] for index in indices[ordinal * 3:ordinal * 3 + 3]]
            normal = tuple(round(sum(v[axis] for v in directions) / 3, 6) for axis in (0, 2))
            wall_keys[xy].append({'ordinal': ordinal, 'inside_selected': ordinal in WALL_IDS,
                                  'height_m': sorted({point[2] for point in triangle}), 'normal_xy': normal})

    plans = PROJECT / 'ArtDirection/CityPCG/MedievalOpening/opening_frontage_plan.json'
    facades = []
    for cell in json.loads(plans.read_text())['cells']:
        for item in cell['points']:
            xy = tuple(value / 100 for value in item['location_cm'][:2])
            clearance = distance_to_ring(xy, ring)
            if clearance <= .10:
                facades.append({'actor_label': item['label'], 'distance_to_wall_m': round(clearance, 5),
                                'location_cm': item['location_cm'], 'yaw_deg': item['yaw_deg']})

    marker_path = PROJECT / 'ArtDirection/WorldJump/graylondon_markers.json'
    markers = []
    for marker in json.loads(marker_path.read_text(encoding='utf-8-sig')):
        xy = (marker['east_m'], marker['north_m'])
        distance = distance_to_ring(xy, ring)
        inside = point_inside(xy, ring)
        if inside or distance <= max(3, marker['radius'] / 100):
            markers.append({'name': marker['name'], 'side': marker['side'], 'tags': marker.get('tags', []),
                            'inside_footprint': inside, 'wall_distance_m': round(distance, 4),
                            'z_m': marker['z_m'], 'radius_cm': marker['radius']})

    target_triangles = [projected(roof[ordinal]) for ordinal in roof_ids]
    authored_roof_overlap = projected_overlaps(target_triangles, authored, set())
    retained_overlap = projected_overlaps(target_triangles, roof, subset)
    return {
        'status': 'geometry_diagnostic_hold_for_story_and_wall_ownership',
        'source_export_sha256': source_hash,
        'source_tile_actor': metadata['actor'], 'source_mesh': metadata['asset'],
        'footprint_world_m': ring, 'cap_area_m2': float(Fraction(area, 2 * 10**6)),
        'base_z_m': bases.pop(), 'roof_z_m': top,
        'ordinary_wall_diagnostics': [{'edge_world_xy_m': edge, 'triangles': rows} for edge, rows in wall_keys.items()],
        'ordinary_wall_signatures': signature_rows(walls, WALL_IDS),
        'roof_signatures': signature_rows(roof, roof_ids),
        'source_roof_component_id': identity(metadata['tile'], [roof[i] for i in source_component]),
        'source_roof_component_faces': len(source_component),
        'roof_edge_contacts_with_retained_component': [{'edge_world_xyz_m': edge, 'retained_faces': rows,
                                                         'edge_in_wall_perimeter': edge in boundary}
                                                        for edge, rows in sorted(adjacent.items())],
        'retained_roof_positive_area_overlaps': retained_overlap,
        'authored_primitive_5_positive_area_overlaps': authored_roof_overlap,
        'opening_frontage_actors_near_wall': facades, 'story_marker_xy_proximity': markers,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True, help='New .json report path inside project Saved')
    parser.add_argument('--source', type=Path, default=TILE, help='Copy of the pinned tile GLB')
    args = parser.parse_args()
    output = args.report.resolve()
    if not output.is_relative_to(SAVED.resolve()) or output.suffix.casefold() != '.json':
        parser.error('Choose a report path ending in .json within this project’s Saved directory')
    if output.exists():
        parser.error('Choose a new report filename to preserve earlier results')
    report = audit(args.source)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(f'Roof ordinals {list(report["roof_signatures"])}; {report["cap_area_m2"]:.6f} m²; '
          f'{len(report["retained_roof_positive_area_overlaps"])} positive-area overlaps; '
          f'{len(report["roof_edge_contacts_with_retained_component"])} retained edge contacts. Report: {output}')


if __name__ == '__main__':
    main()
