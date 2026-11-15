"""Turn Gray London footprint edges or traced walls into PCG instance cells.

Coordinates in the input are local Unreal metres, with +X east and +Y north.
Kit meshes face +X and have a 4 m × 3.2 m Y/Z envelope and a ground pivot.
"""

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import zlib


BAY_WIDTH = 4.0
STOREY_HEIGHT = 3.2
WALL_OFFSET = 0.045
CORNER_GAP = 0.07
ROAD_SEARCH = 34.0
STYLES = {
    'edwardian_brick': 'EdwardianBrick',
    'stone_office': 'StoneOffice',
    'glass_office': 'GlassOffice',
}


def stable_int(key):
    return zlib.crc32(key.encode('utf-8')) & 0x7fff_ffff


def axis_name(index):
    return f'm{-index}' if index < 0 else str(index)


def coordinates(values, dimensions):
    result = tuple(float(value) for value in values)
    if len(result) != dimensions or not all(math.isfinite(value) for value in result):
        raise ValueError(f'Expected {dimensions} finite coordinates: {values}')
    return result


class RoadIndex:
    """Coarse spatial index to keep frontage selection local on city-scale input."""

    def __init__(self, roads):
        self.bins = defaultdict(list)
        for road in roads:
            vertices = [coordinates(point, 2) for point in road]
            for start, end in zip(vertices, vertices[1:]):
                # Split long source segments so their bin coverage stays narrow.
                length = math.dist(start, end)
                if length < 0.01:
                    continue
                pieces = math.ceil(length / ROAD_SEARCH)
                for i in range(pieces):
                    a = tuple(s + (e - s) * i / pieces for s, e in zip(start, end))
                    b = tuple(s + (e - s) * (i + 1) / pieces for s, e in zip(start, end))
                    for ix in range(self.key(min(a[0], b[0])), self.key(max(a[0], b[0])) + 1):
                        for iy in range(self.key(min(a[1], b[1])), self.key(max(a[1], b[1])) + 1):
                            self.bins[ix, iy].append((a, b))

    @staticmethod
    def key(value):
        return math.floor(value / ROAD_SEARCH)

    def faces_road(self, center, outward):
        x, y = center
        ix, iy = self.key(x), self.key(y)
        nearest = None
        for nx in range(ix - 1, ix + 2):
            for ny in range(iy - 1, iy + 2):
                for (ax, ay), (bx, by) in self.bins.get((nx, ny), ()):
                    dx, dy = bx - ax, by - ay
                    t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
                    ux, uy = ax + t * dx - x, ay + t * dy - y
                    distance = math.hypot(ux, uy)
                    if nearest is None or distance < nearest[0]:
                        nearest = (distance, ux, uy)
        if nearest is None:
            return False
        distance, ux, uy = nearest
        return 1.0 < distance <= ROAD_SEARCH and ux * outward[0] + uy * outward[1] > 0.60 * distance


def building_frontages(building, roads):
    outline = [coordinates(point, 2) for point in building['footprint']]
    if outline and outline[0] == outline[-1]:
        outline.pop()
    if len(outline) < 3:
        raise ValueError(f"Building {building['id']} needs an exterior ring")
    edges = list(zip(outline, outline[1:] + outline[:1]))
    twice_area = sum(ax * by - bx * ay for (ax, ay), (bx, by) in edges)
    if abs(twice_area) < 0.2:
        raise ValueError(f"Degenerate footprint: {building['id']}")
    winding = 1 if twice_area > 0 else -1
    eligible = building.get('street_edges')
    if eligible is not None and any(not isinstance(index, int) or not 0 <= index < len(edges) for index in eligible):
        raise ValueError(f"Invalid street edge index: {building['id']}")
    z = float(building.get('base_m', 0.0))
    frontages = []
    for index, ((ax, ay), (bx, by)) in enumerate(edges):
        length = math.hypot(bx - ax, by - ay)
        if length < 0.1:
            continue
        outward = ((by - ay) / length * winding, (ax - bx) / length * winding)
        center = ((ax + bx) / 2, (ay + by) / 2)
        if eligible is None and not roads.faces_road(center, outward):
            continue
        if eligible is not None and index not in eligible:
            continue
        frontages.append((index, length, {
            **building,
            'id': f"{building['id']}.edge{index}",
            'building_id': building['id'],
            'start': (ax, ay, z),
            'end': (bx, by, z),
            'outward': outward,
        }))
    if not frontages:
        return
    entrance_edge = building.get('entrance_edge', max(frontages, key=lambda entry: entry[1])[0])
    for index, _, frontage in frontages:
        yield {**frontage, 'entrance': building.get('entrance', True) and index == entrance_edge}


def facade_points(frontage, max_storeys):
    identifier = frontage['id']
    building_id = frontage.get('building_id', identifier)
    a, b = (coordinates(frontage[name], 3) for name in ('start', 'end'))
    nx, ny = coordinates(frontage['outward'], 2)
    dx, dy = b[0] - a[0], b[1] - a[1]
    span = math.hypot(dx, dy)
    if span < 2.6:
        return
    length = math.hypot(nx, ny)
    if length < .01 or abs(nx * dx + ny * dy) > 0.07 * span * length:
        raise ValueError(f'Outward direction must be perpendicular to wall: {identifier}')
    nx, ny = nx / length, ny / length
    height = float(frontage['height_m'])
    if not math.isfinite(height) or height < 2.35:
        raise ValueError(f'Invalid wall height: {identifier}')
    if abs(b[2] - a[2]) > 0.20 * span:
        raise ValueError(f'Grade too steep for facade strips: {identifier}')
    count = int(frontage.get('levels') or max(1, round(height / STOREY_HEIGHT)))
    floor_height = height / count if count > 0 else 0
    if not 2.30 <= floor_height <= 5.0:
        raise ValueError(f'Storey height {floor_height:.2f} m outside kit range: {identifier}')
    style = frontage.get('style') or ('glass_office' if count >= 8 else 'edwardian_brick')
    if style not in STYLES:
        raise ValueError(f'Unknown style {style!r} for {identifier}')
    course_span = span - 2 * CORNER_GAP
    bays = max(1, round(course_span / BAY_WIDTH))
    width = course_span / bays
    entrance = bays // 2 if frontage.get('entrance', span >= 6) else None
    yaw = math.degrees(math.atan2(ny, nx))
    for bay in range(bays):
        t = (CORNER_GAP + (bay + .5) * width) / span
        x = a[0] + dx * t + nx * WALL_OFFSET
        y = a[1] + dy * t + ny * WALL_OFFSET
        z = a[2] + (b[2] - a[2]) * t
        for floor in range(min(count, max_storeys)):
            identity = f'{identifier}.{bay}.{floor}'
            role = 'Base' if floor == 0 else 'Upper'
            if floor == 0 and bay == entrance:
                role = 'Entrance'
            yield {
                'id': identity,
                'building_id': building_id,
                'mesh_id': f'SM_GLPCG_{STYLES[style]}_{role}',
                'location_cm': [round(value * 100, 3) for value in (x, y, z + floor_height * floor)],
                'yaw_deg': round(yaw, 4),
                'scale': [1.0, round(width / BAY_WIDTH, 6), round(floor_height / STOREY_HEIGHT, 6)],
                'seed': stable_int(identity),
            }


def plan(source, cell_size, cell_budget, max_storeys):
    if source.get('coordinate_system') != 'ue_local_m':
        raise ValueError('Expected ue_local_m input. Project and verify geography before planning.')
    exclusions = set(source.get('exclude_buildings', []))
    roads = RoadIndex(source.get('roads', []))
    frontages = list(source.get('frontages', []))
    for building in source.get('buildings', []):
        if not building.get('exclude') and building['id'] not in exclusions:
            if 'street_edges' not in building and not source.get('roads'):
                raise ValueError(f"No street_edges or road data for {building['id']}")
            frontages.extend(building_frontages(building, roads))
    cells = defaultdict(list)
    identities = set()
    for frontage in sorted(frontages, key=lambda value: value['id']):
        key = frontage['id']
        if key in identities:
            raise ValueError(f'Duplicate frontage ID: {key}')
        identities.add(key)
        if frontage.get('exclude') or frontage.get('building_id', key) in exclusions or key in exclusions:
            continue
        for point in facade_points(frontage, max_storeys):
            x, y, _ = point['location_cm']
            cell = (math.floor(x / (100 * cell_size)), math.floor(y / (100 * cell_size)))
            if len(cells[cell]) >= cell_budget:
                raise ValueError(f'Cell {cell} exceeds {cell_budget} instances; reduce grid or storey budget.')
            cells[cell].append(point)
    return {
        'coordinate_system': 'ue_cm',
        'grid_size_m': cell_size,
        'source': source.get('source', ''),
        'cells': [{'id': f'x{axis_name(x)}_y{axis_name(y)}', 'points': points}
                  for (x, y), points in sorted(cells.items())],
    }


def apply_overrides(source, overrides):
    supported = {'style', 'levels', 'entrance', 'entrance_edge', 'exclude', 'building_id'}
    records = list(source.get('frontages', [])) + list(source.get('buildings', []))
    by_id = {record['id']: record for record in records}
    for name, edits in overrides.items():
        if name not in by_id or set(edits) - supported:
            raise ValueError(f'Unknown source ID or override field: {name}')
        by_id[name].update(edits)


def merge_sources(paths):
    merged = {'coordinate_system': 'ue_local_m', 'source': ''}
    labels = []
    for path in paths:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        if data.get('coordinate_system') != merged['coordinate_system']:
            raise ValueError(f'Project {path} to ue_local_m before combining tiles.')
        labels.append(data.get('source') or path.stem)
        for key in ('buildings', 'frontages', 'roads', 'exclude_buildings'):
            merged.setdefault(key, []).extend(data.get(key, []))
    merged['source'] = ', '.join(sorted(set(labels)))
    return merged


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--cell-size-m', type=int, default=160)
    parser.add_argument('--cell-budget', type=int, default=2500)
    parser.add_argument('--max-storeys', type=int, default=8)
    parser.add_argument('--overrides', type=Path, help='Art direction keyed by source frontage/building ID')
    parser.add_argument('--add-source', type=Path, action='append', default=[],
                        help='Include another reviewed tile or district in the same plan')
    args = parser.parse_args()
    if not all(value > 0 for value in (args.cell_size_m, args.cell_budget, args.max_storeys)):
        parser.error('Cell size, instance budget, and storey limit must be positive.')
    sources = [args.source, *args.add_source]
    if any(source.resolve() == args.output.resolve() for source in sources):
        parser.error('Output must differ from every source.')
    data = merge_sources(sources)
    if args.overrides:
        apply_overrides(data, json.loads(args.overrides.read_text(encoding='utf-8-sig')))
    result = plan(data, args.cell_size_m, args.cell_budget, args.max_storeys)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, separators=(',', ':')) + '\n', encoding='utf-8')
    print(f"{len(result['cells'])} cells, {sum(len(cell['points']) for cell in result['cells'])} facade instances")


if __name__ == '__main__':
    main()
