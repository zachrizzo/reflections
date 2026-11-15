"""Exercise road retention without using legacy primitive or slot order."""

from pathlib import Path
import unittest

from test_verify_west_mark_lane_section_mapping import checked_tempdir, make_glb
import verify_west_mark_lane_road_retention as road


FACADE = [(0, 0, 0), (2, 0, 0), (0, 2, 0)]
ROAD = [(0, 0, 1), (2, 0, 1), (0, 2, 1)]
PARK = [(0, 0, 2), (2, 0, 2), (0, 2, 2)]
OTHER = [(0, 0, 3), (2, 0, 3), (0, 2, 3)]


class RoadRetentionTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(checked_tempdir()))
        self.source, self.filtered, self.named = [self.root / name for name in ('source.glb', 'filtered.glb', 'named.glb')]
        make_glb(self.source, [FACADE, ROAD, PARK])
        make_glb(self.filtered, [PARK, ROAD, FACADE])
        make_glb(self.named, [ROAD, FACADE, PARK], names=['GL_Road', 'GL_Facade', 'GL_Park'])

    def exports(self):
        return road.compare_exports(self.source, self.filtered, self.named)

    def proof(self, report):
        return {'status': 'geometry_match_review_required', 'exact_signed_triangle_bijection': True,
                'road_primitive_candidate': 1, 'source_glb_sha256': report['source_glb_sha256']}

    def test_permuted_files_are_matched_by_signed_geometry(self):
        report = self.exports()
        self.assertEqual([row['unique_filtered_primitive'] for row in report['rows']], [2, 1, 0])
        self.assertEqual([row['unique_import_primitive'] for row in report['rows']], [1, 0, 2])
        self.assertEqual(report['status'], 'source_section_mapping_required')
        result = road.integrate(self.proof(report), report)
        self.assertEqual((result['source_primitive'], result['filtered_primitive'], result['import_primitive']), (1, 1, 0))
        self.assertTrue(result['original_road_geometry_in_filtered_glb_verified'])
        self.assertTrue(result['original_road_geometry_in_named_import_glb_verified'])
        self.assertTrue(result['named_import_road_material_verified'])
        self.assertFalse(result['actual_unreal_replacement_verified'])
        self.assertFalse(result['activation_authorized'])

    def test_section_proof_and_source_hash_are_required(self):
        report = self.exports()
        self.assertEqual(road.integrate({}, report)['status'], 'source_section_mapping_unverified')
        stale = {**self.proof(report), 'source_glb_sha256': 'different'}
        self.assertFalse(road.integrate(stale, report)['original_road_geometry_in_filtered_glb_verified'])
        ambiguous = {**self.proof(report), 'exact_signed_triangle_bijection': False}
        self.assertEqual(road.integrate(ambiguous, report)['status'], 'source_section_mapping_unverified')

    def test_changed_or_reversed_triangle_fails_despite_same_count(self):
        for replacement in (OTHER, [ROAD[0], ROAD[2], ROAD[1]]):
            make_glb(self.filtered, [PARK, replacement, FACADE])
            report = self.exports()
            result = road.integrate(self.proof(report), report)
            self.assertEqual(result['status'], 'road_geometry_missing_changed_or_ambiguous_in_filtered_glb')
            self.assertFalse(result['original_road_geometry_in_filtered_glb_verified'])

    def test_duplicate_matching_primitives_are_ambiguous(self):
        make_glb(self.filtered, [PARK, ROAD, ROAD, FACADE])
        report = self.exports()
        self.assertEqual(report['rows'][1]['exact_filtered_candidates'], [1, 2])
        self.assertEqual(road.integrate(self.proof(report), report)['status'],
                         'road_geometry_missing_changed_or_ambiguous_in_filtered_glb')

    def test_missing_road_in_named_import_and_wrong_material_fail(self):
        make_glb(self.named, [OTHER, FACADE, PARK], names=['GL_Road', 'GL_Facade', 'GL_Park'])
        report = self.exports()
        result = road.integrate(self.proof(report), report)
        self.assertTrue(result['original_road_geometry_in_filtered_glb_verified'])
        self.assertEqual(result['status'], 'road_geometry_missing_changed_or_ambiguous_in_named_import_glb')
        make_glb(self.named, [ROAD, FACADE, PARK], names=['GL_Park', 'GL_Facade', 'GL_Road'])
        report = self.exports()
        self.assertEqual(road.integrate(self.proof(report), report)['status'],
                         'named_import_road_material_missing_or_ambiguous')

    def test_identical_paths_rejected(self):
        with self.assertRaisesRegex(ValueError, 'distinct'):
            road.compare_exports(self.source, self.source, self.named)


if __name__ == '__main__':
    unittest.main()
