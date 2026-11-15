"""Plan complete medieval buildings for a reviewed, street-connected source block.

Input candidates are a conservative survey, not approval to replace the live
city. The resulting plans and styles still need live actor, collision and route
checks before they can be used in the playable map.
"""

import argparse
import json
import math
from pathlib import Path

from extract_building_shells import faces
from extract_tile_frontages import read_glb, road_triangles
from plan_whole_building_replacements import building_input, check_road
from subtract_building_shells import digest, read_json, reviewed_faces


def shared_party_walls(candidate):
    """Validate every specified shared edge, including multi-edge party walls."""
    rings = {row['id']: row['footprint'] for row in candidate['buildings']}
    seen = set()
    result = []
    for shared in candidate['shared_party_walls']:
        edges, segment = shared['edges'], shared['world_segment_m']
        if shared.get('keep_sealed') is not True or len(edges) != 2 or len(segment) != 2:
            raise ValueError('Each party wall must identify two buildings and stay sealed.')
        directed = []
        for identifier, index in edges.items():
            ring = rings[identifier]
            if type(index) is not int or not 0 <= index < len(ring) or (identifier, index) in seen:
                raise ValueError('A party wall has an invalid or repeated footprint edge.')
            seen.add((identifier, index))
            directed.append((ring[index], ring[(index + 1) % len(ring)]))
        if directed[0] != tuple(reversed(directed[1])) or directed[0] not in (tuple(segment), tuple(reversed(segment))):
            raise ValueError('Party wall endpoints do not match oppositely directed footprint edges.')
        result.append({'keep_sealed': True, 'world_segment_m': segment,
                       'length_m': round(math.dist(*segment), 3), 'edges': edges})
    return result


def style_for(building):
    """Choose reproducible, bounded starting proportions for art review."""
    ring, entry = building['footprint'], building['entry']
    a, b = ring[entry['edge']], ring[(entry['edge'] + 1) % len(ring)]
    length = math.dist(a, b)
    if length <= 0:
        raise ValueError('The surveyed entry edge has zero length.')
    axis_y = ((b[0] - a[0]) / length, (b[1] - a[1]) / length)
    along = [point[0] * axis_y[0] + point[1] * axis_y[1] for point in ring]
    frontage = max(along) - min(along)
    source_height = building['source_roof_m'] - building['base_m']
    if not math.isfinite(source_height) or source_height < 7:
        raise ValueError('The source envelope is too low for this starting kit.')
    variant = int(digest(building['id'].encode('utf-8'))[:8], 16) % 3
    eave = min((6.15, 7.2, 8.1)[variant], source_height - 3.5)
    ridge = min(eave + (3.1, 3.55, 4.1)[variant], source_height - .4)
    ranges = max(1, min(4, round(frontage / 8)))
    return {'role': ('workshop', 'merchant house', 'market building')[variant],
            'eave_m': round(eave, 3), 'ridge_m': round(ridge, 3), 'roof_ranges': ranges,
            'entry_opening_m': [min(1.35, entry['minimum_clear_width_m']), 2.3],
            'treatment': 'Surveyed closed shell with pitched clay-tile ranges, timber, lime render and stone.'}


def plan(source, candidate_path):
    candidate = read_json(candidate_path)
    if candidate.get('status') != 'offline_candidate' or digest(source.read_bytes()) != candidate['source_export_sha256']:
        raise ValueError('The candidate or its pinned source tile is not the reviewed input.')
    identifiers = [building['id'] for building in candidate['buildings']]
    road_slots = [int(slot) for slot, name in candidate['untouched_primitives'].items() if name == 'GL_Road']
    if not identifiers or len(set(identifiers)) != len(identifiers) or len(road_slots) != 1:
        raise ValueError('The block must have unique buildings and one protected road section.')
    document, blob = read_glb(source)
    reviewed_faces(document, blob, candidate)
    source_roof = faces(document, blob, candidate['roof_primitive'], candidate['source_origin_m'])
    styles = {building['id']: style_for(building) for building in candidate['buildings']}
    buildings = [building_input(building, styles[building['id']], source_roof)
                 for building in candidate['buildings']]
    walls = shared_party_walls(candidate)
    roads = road_triangles(document, blob, {'road_primitive': road_slots[0],
                                            'origin_m': candidate['source_origin_m']})
    rings = [building['footprint'] for building in candidate['buildings']]
    # Match the candidate selector's 1.2 m road sampling and recheck against
    # every candidate footprint, not just the two endpoints of each link.
    controls = {'step_max_m': .75, 'offsets_m': [-.6, 0, .6], 'minimum_footprint_clearance_m': .35}
    routes = [{'members': link['members'], 'guide_m': link['guide_m'],
               **check_road(link['guide_m'], roads, rings, controls)}
              for link in candidate['validated_road_links']]
    return {'status': 'offline_generation_input', 'coordinate_system': 'ue_local_m',
            'source_tile': candidate['source_tile'], 'source_export_sha256': candidate['source_export_sha256'],
            'reviewed_candidate': candidate_path.name, 'styles': styles, 'buildings': buildings,
            'party_walls': walls, 'road_sampling': controls, 'local_road_corridors': routes,
            'review_before_replacement': candidate['review_before_replacement']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ('source', 'candidate', 'output'):
        parser.add_argument(argument, type=Path)
    args = parser.parse_args()
    if args.output.resolve() in {args.source.resolve(), args.candidate.resolve()}:
        parser.error('Use a separate output file.')
    result = plan(args.source, args.candidate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f"Planned {len(result['buildings'])} complete building envelopes, "
          f"{len(result['party_walls'])} sealed party edges and "
          f"{sum(route['sample_count'] for route in result['local_road_corridors'])} road samples.")


if __name__ == '__main__':
    main()
