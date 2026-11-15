"""Compare source, filtered and import GLBs without assuming primitive order.

This is a read-only offline comparison. A source primitive's identity as
GL_Road comes only from the separate live source-section geometry proof.
"""

import json
from pathlib import Path

from extract_tile_frontages import read_glb
from verify_west_mark_lane_section_mapping import glb_sections
from batch_export_geodata_unreal import sha256


PROJECT = Path(__file__).resolve().parents[2]
SOURCE = Path('Saved/CityPCG/Tile_p03_p00.glb')
FILTERED = Path('Saved/CityPCG/MedievalSurvey/Tile_p03_p00_without_three_west_shells.glb')
IMPORT = Path('Saved/CityPCG/MedievalSurvey/SM_GLMedieval_WestBlockTile.glb')


def materials(path):
    data, _ = read_glb(path)
    values = data.get('materials', [])
    result = []
    for primitive in data['meshes'][0]['primitives']:
        index = primitive.get('material')
        result.append(values[index].get('name') if type(index) is int and 0 <= index < len(values) else None)
    return result


def exact_matches(left, right):
    """Match complete, signed triangle multisets, including multiplicity."""
    forward = [[index for index, candidate in enumerate(right) if candidate == section] for section in left]
    reverse = [[index for index, candidates in enumerate(forward) if target in candidates]
               for target in range(len(right))]
    return forward, reverse


def compare_exports(source_path, filtered_path, import_path):
    paths = [Path(path).resolve() for path in (source_path, filtered_path, import_path)]
    if len(set(paths)) != 3 or any(not path.is_file() for path in paths):
        raise ValueError('Source, filtered and named import GLBs must be three distinct existing files.')
    before = [sha256(path) for path in paths]
    source, filtered, named = (glb_sections(path) for path in paths)
    named_materials = materials(paths[2])
    if len(named_materials) != len(named):
        raise ValueError('Named import material count disagrees with its primitives.')
    source_forward, filtered_reverse = exact_matches(source, filtered)
    filtered_forward, named_reverse = exact_matches(filtered, named)
    rows = []
    for primitive, candidates in enumerate(source_forward):
        filtered_unique = (len(candidates) == 1 and filtered_reverse[candidates[0]] == [primitive])
        filtered_index = candidates[0] if filtered_unique else None
        import_candidates = filtered_forward[filtered_index] if filtered_unique else []
        import_unique = (len(import_candidates) == 1 and
                         named_reverse[import_candidates[0]] == [filtered_index])
        named_index = import_candidates[0] if import_unique else None
        rows.append({'source_primitive': primitive, 'source_triangles': sum(source[primitive].values()),
                     'exact_filtered_candidates': candidates,
                     'unique_filtered_primitive': filtered_index,
                     'exact_import_candidates': import_candidates,
                     'unique_import_primitive': named_index,
                     'import_material_name': named_materials[named_index] if named_index is not None else None})
    after = [sha256(path) for path in paths]
    if before != after:
        raise RuntimeError('An input GLB changed while its geometry was being compared.')
    return {'status': 'source_section_mapping_required',
            'source_glb': str(paths[0]), 'source_glb_sha256': before[0],
            'filtered_glb': str(paths[1]), 'filtered_glb_sha256': before[1],
            'named_import_glb': str(paths[2]), 'named_import_glb_sha256': before[2],
            'comparison': 'exact signed float32 triangle multisets, with multiplicity and cyclic rotation',
            'rows': rows, 'named_import_material_names': named_materials,
            'activation_authorized': False}


def integrate(source_proof, exports):
    """Bind the independent GLB comparisons to a successful in-memory UE proof."""
    result = {'status': 'source_section_mapping_unverified',
              'source_primitive': None, 'filtered_primitive': None, 'import_primitive': None,
              'original_road_geometry_in_filtered_glb_verified': False,
              'original_road_geometry_in_named_import_glb_verified': False,
              'named_import_road_material_verified': False,
              'actual_unreal_replacement_verified': False, 'activation_authorized': False}
    if (source_proof.get('status') != 'geometry_match_review_required'
            or source_proof.get('exact_signed_triangle_bijection') is not True
            or source_proof.get('source_glb_sha256') != exports['source_glb_sha256']):
        return result
    primitive = source_proof.get('road_primitive_candidate')
    rows = exports['rows']
    if (type(primitive) is not int or not 0 <= primitive < len(rows)
            or rows[primitive]['source_primitive'] != primitive):
        result['status'] = 'road_section_missing_or_ambiguous'
        return result
    row = rows[primitive]
    result.update(source_primitive=primitive, filtered_primitive=row['unique_filtered_primitive'],
                  import_primitive=row['unique_import_primitive'])
    if row['unique_filtered_primitive'] is None:
        result['status'] = 'road_geometry_missing_changed_or_ambiguous_in_filtered_glb'
        return result
    result['original_road_geometry_in_filtered_glb_verified'] = True
    if row['unique_import_primitive'] is None:
        result['status'] = 'road_geometry_missing_changed_or_ambiguous_in_named_import_glb'
        return result
    result['original_road_geometry_in_named_import_glb_verified'] = True
    names = exports['named_import_material_names']
    if row['import_material_name'] != 'GL_Road' or names.count('GL_Road') != 1:
        result['status'] = 'named_import_road_material_missing_or_ambiguous'
        return result
    result['named_import_road_material_verified'] = True
    result['status'] = 'glb_road_geometry_matches_actual_unreal_asset_still_unverified'
    return result


def main():
    report = compare_exports(PROJECT / SOURCE, PROJECT / FILTERED, PROJECT / IMPORT)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
