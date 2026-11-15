"""Compare hash-bound UE 5.9 source groups with all pilot GLB primitives.

Requires externally supplied raw-unreal 0.1.13 index.js and a previously
verified local decompression. No editor, asset or package writes occur.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / 'Tools/CityPCG'))
from verify_west_mark_lane_section_mapping import glb_sections
from verify_west_mark_lane_road_retention import compare_exports, FILTERED, IMPORT

ASSET = PROJECT / 'Content/GrayLondon/Geodata/Tiles/Tile_p03_p00.uasset'
PAYLOAD = PROJECT / 'Saved/CityPCG/MedievalSurvey/Tile_p03_p00_mesh_payload.bin'
GLB = PROJECT / 'Saved/CityPCG/Tile_p03_p00.glb'
EXTRACTOR = Path(__file__).resolve().with_name('extract_unreal_source_groups.mjs')
EXPECTED_GLB_SHA = '5c946436fce01c086598966fcca3c379381b29776e1e03df2b37ada9fb4b08f4'
EXPECTED_FILTERED_SHA = '94e699f5e2b4e1ae0f1a023c7db3d3988db0f4c8461fec474d522835624e7f16'
EXPECTED_NAMED_SHA = 'dcbd8f89b2975cea4db92771d0126e7f1867ecf912ee301183f9ff4f8443581e'


def sha(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def match_groups(originals, primitives):
    forward = [[i for i, primitive in enumerate(primitives) if primitive == group] for group in originals]
    reverse = [[i for i, candidates in enumerate(forward) if primitive in candidates]
               for primitive in range(len(primitives))]
    seen = set()
    disjoint = True
    for group in originals:
        keys = set(group)
        if not keys or seen.intersection(keys):
            disjoint = False
        seen.update(keys)
    bijection = (bool(originals) and disjoint and len(originals) == len(primitives)
                 and all(len(row) == 1 for row in forward)
                 and all(len(row) == 1 for row in reverse))
    return forward, reverse, bijection


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--parser-js', type=Path, required=True, help='Unmodified @threenative/raw-unreal 0.1.13 dist/index.js')
    args = cli.parse_args()
    parser = args.parser_js.resolve(strict=True)
    start = {label: sha(path) for label, path in
             [('asset', ASSET), ('payload', PAYLOAD), ('glb', GLB), ('raw_unreal_parser', parser),
              ('group_extractor', EXTRACTOR)]}
    if start['glb'] != EXPECTED_GLB_SHA:
        raise RuntimeError('Source GLB differs from the pinned West Mark Lane pilot input.')
    process = subprocess.run(['node', '--max-old-space-size=256', str(EXTRACTOR), str(parser),
                              str(ASSET), str(PAYLOAD)], check=True, capture_output=True, text=True, timeout=30,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    source = json.loads(process.stdout)
    if (source['asset_sha256'] != start['asset'] or source['payload_sha256'] != start['payload']
            or source['parser_sha256'] != start['raw_unreal_parser']):
        raise RuntimeError('Source, payload or parser does not match the pinned identities.')
    sections = source['sections']
    originals = [Counter(row['triangles']) for row in sections]
    primitives = [Counter({b''.join(key).hex(): count for key, count in section.items()})
                  for section in glb_sections(GLB)]
    forward, reverse, bijection = match_groups(originals, primitives)
    after = {label: sha(path) for label, path in
             [('asset', ASSET), ('payload', PAYLOAD), ('glb', GLB), ('raw_unreal_parser', parser),
              ('group_extractor', EXTRACTOR)]}
    if start != after:
        raise RuntimeError('Input or experimental parser changed during comparison.')
    result = {'status': 'offline_source_group_match_runtime_binding_unverified' if bijection else 'ambiguous_or_mismatch',
              'hashes': start, 'payload_consumed': source['consumed'], 'trailing_bytes': source['trailing'],
              'sections': [{'source_group': row['section'], 'slot': row['slot'],
                            'triangle_count': sum(originals[i].values()), 'matching_glb_primitives': forward[i]}
                           for i, row in enumerate(sections)],
              'glb_primitive_candidate_groups': reverse,
              'exact_signed_triangle_bijection': bijection,
              'runtime_section_slot_binding_verified': False,
              'live_actor_and_transform_verified': False,
              'actual_filtered_unreal_asset_verified': False, 'activation_authorized': False}
    if bijection:
        road_groups = [i for i, row in enumerate(sections) if row['slot'] == 'GL_Road']
        if len(road_groups) != 1:
            raise RuntimeError('Source ImportedMaterialSlotName GL_Road is missing or ambiguous.')
        road_primitive = forward[road_groups[0]][0]
        exports = compare_exports(GLB, PROJECT / FILTERED, PROJECT / IMPORT)
        if (exports['source_glb_sha256'] != start['glb']
                or exports['filtered_glb_sha256'] != EXPECTED_FILTERED_SHA
                or exports['named_import_glb_sha256'] != EXPECTED_NAMED_SHA):
            raise RuntimeError('A pilot GLB changed or does not match the pinned derivative.')
        row = exports['rows'][road_primitive]
        if (row['unique_filtered_primitive'] is None or row['unique_import_primitive'] is None
                or row['import_material_name'] != 'GL_Road'
                or exports['named_import_material_names'].count('GL_Road') != 1):
            raise RuntimeError('Source-road geometry or its named import material is missing or ambiguous.')
        result['road_glb_evidence'] = {
            'source_primitive': road_primitive, 'filtered_primitive': row['unique_filtered_primitive'],
            'named_import_primitive': row['unique_import_primitive'],
            'named_import_material': row['import_material_name'],
            'filtered_sha256': exports['filtered_glb_sha256'],
            'named_import_sha256': exports['named_import_glb_sha256'],
            'geometry_retained_through_named_import': row['unique_filtered_primitive'] is not None
                and row['unique_import_primitive'] is not None,
            'runtime_section_slot_binding_verified': False,
        }
    print(json.dumps(result, indent=2))
    if not bijection:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
