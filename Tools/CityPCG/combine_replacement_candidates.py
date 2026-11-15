"""Combine reviewed building masks from the same original city tile.

Use one cumulative mask per source tile. This utility only produces an offline
candidate; it does not approve or place any model in the game.
"""

import argparse
from pathlib import Path
import json

from extract_tile_frontages import read_glb
from subtract_building_shells import digest, read_json, reviewed_faces


SOURCE_FIELDS = ('coordinate_system', 'source_tile', 'source_origin_m', 'source_tile_asset',
                 'source_export_sha256', 'ordinary_wall_primitive', 'roof_primitive', 'untouched_primitives')


def combine(candidates):
    if len(candidates) < 2:
        raise ValueError('At least two independently reviewed candidate groups are required.')
    first = candidates[0]
    if any(candidate.get('status') != 'offline_candidate' for candidate in candidates):
        raise ValueError('Only offline reviewed candidates can be combined.')
    if any(any(candidate[field] != first[field] for field in SOURCE_FIELDS) for candidate in candidates[1:]):
        raise ValueError('Candidate source tile, origin, hash or protected sections differ.')
    buildings = [building for candidate in candidates for building in candidate['buildings']]
    if not buildings or len({building['id'] for building in buildings}) != len(buildings):
        raise ValueError('A candidate building is missing or included more than once.')
    return {'name': 'Cumulative whole-building replacement for ' + first['source_tile'],
            'status': 'offline_candidate', **{field: first[field] for field in SOURCE_FIELDS},
            'buildings': buildings,
            'note': 'Cumulative offline mask; every model and gameplay route still needs live review.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('candidates', type=Path, nargs='+')
    args = parser.parse_args()
    if args.output.resolve() in {path.resolve() for path in [args.source, *args.candidates]}:
        parser.error('Use a separate, new output file.')
    combined = combine([read_json(path) for path in args.candidates])
    if digest(args.source.read_bytes()) != combined['source_export_sha256']:
        raise ValueError('The source export does not match the combined candidate masks.')
    selected, _ = reviewed_faces(*read_glb(args.source), combined)
    combined['candidate_sources'] = [{'path': str(path), 'sha256': digest(path.read_bytes())}
                                     for path in args.candidates]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(combined, output, indent=2)
        output.write('\n')
    print(f"Combined {len(combined['buildings'])} surveyed shells; "
          f"checked {sum(len(faces) for faces in selected.values())} unique face signatures.")


if __name__ == '__main__':
    main()
