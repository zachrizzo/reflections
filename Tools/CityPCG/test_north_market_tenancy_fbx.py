"""Tiny offline checks for the hosted FBX trial; no Blender or output files."""
from copy import deepcopy
import hashlib
from types import SimpleNamespace
import unittest
from unittest import mock

import north_market_tenancies as tenancy
import north_market_tenancy_fbx as fbx


def channel_data():
    corner = (1., 2., 3., .1, .2, 0., 0., 1.)
    face_a = ('M_A', (corner, corner, corner))
    face_b = ('M_B', (corner, corner, corner))
    base = {'vertices': 3, 'edges': 3, 'uv_corners': 3, 'slots': ['M_A'], 'faces': [face_a]}
    overlay = {'vertices': 3, 'edges': 3, 'uv_corners': 3, 'slots': ['M_B'], 'faces': [face_b]}
    combined = {'vertices': 6, 'edges': 6, 'uv_corners': 6, 'slots': ['M_A', 'M_B'],
                'faces': [face_a, face_b]}
    return base, overlay, combined


def generation_report(mesh, units):
    return {'status': 'review_only_not_unreal_validated', 'building': tenancy.BUILDING,
            'source_obj_sha256': tenancy.PINNED['obj'], 'source_plan_lf_sha256': tenancy.PINNED['plan'],
            'overlay_sha256': 'a'*64, 'combined_sha256': 'b'*64,
            'added_vertices': len(mesh.vertices), 'added_faces': len(mesh.faces), 'units': units}


class TenancyFbxTests(unittest.TestCase):
    def test_combined_source_must_equal_base_plus_overlay_for_every_channel(self):
        base, overlay, combined = channel_data()
        fbx.check_union(base, overlay, combined, ['M_A', 'M_B'])
        for key in ('vertices', 'edges', 'uv_corners'):
            altered = deepcopy(combined)
            altered[key] += 1
            with self.subTest(key=key), self.assertRaises(ValueError):
                fbx.check_union(base, overlay, altered, ['M_A', 'M_B'])
        for offset in (0, 3, 5):  # position, UV and normal
            altered = deepcopy(combined)
            role, corners = altered['faces'][1]
            c = list(corners[0])
            c[offset] += .1
            altered['faces'][1] = (role, (tuple(c), *corners[1:]))
            with self.subTest(channel=offset), self.assertRaises(ValueError):
                fbx.check_union(base, overlay, altered, ['M_A', 'M_B'])
        for faces in ([combined['faces'][1], combined['faces'][0]],
                      [combined['faces'][0], ('M_A', combined['faces'][1][1])]):
            altered = {**combined, 'faces': faces}
            with self.assertRaises(ValueError):
                fbx.check_union(base, overlay, altered, ['M_A', 'M_B'])
        with self.assertRaises(ValueError):
            fbx.check_union(base, overlay, {**combined, 'slots': ['M_B', 'M_A']}, ['M_A', 'M_B'])

    def test_generated_report_must_match_both_files_and_pinned_inputs(self):
        mesh = SimpleNamespace(vertices=[1, 2], faces=[3])
        units = [{'edge': 1, 'style': 0}]
        good = generation_report(mesh, units)
        fbx.check_generation_report(good, 'a'*64, 'b'*64, mesh, units)
        for key in ('source_obj_sha256', 'source_plan_lf_sha256', 'overlay_sha256',
                    'combined_sha256', 'added_vertices', 'added_faces', 'units', 'status'):
            changed = {**good, key: 'bad'}
            with self.subTest(key=key), self.assertRaises(ValueError):
                fbx.check_generation_report(changed, 'a'*64, 'b'*64, mesh, units)

    def test_regenerated_overlay_hash_includes_header_and_exact_geometry(self):
        def fake_write(stream, mesh):
            stream.write('v 1 2 3\n')
        expected = hashlib.sha256(b'# Closed visual details only; no gameplay openings.\n'
                                  b'mtllib NorthMarketDetail.mtl\nv 1 2 3\n').hexdigest()
        with mock.patch.object(tenancy, 'write_geometry', side_effect=fake_write):
            self.assertEqual(fbx.expected_overlay_sha(object()), expected)

    def test_both_fbx_kinds_use_the_correct_source_file(self):
        paths = {'combined': 'complete.obj', 'overlay': 'overlay.obj'}
        self.assertEqual(fbx.obj_for_kind(paths, 'complete'), 'complete.obj')
        self.assertEqual(fbx.obj_for_kind(paths, 'overlay'), 'overlay.obj')
        with self.assertRaises(ValueError):
            fbx.obj_for_kind(paths, 'other')

    def test_export_is_bound_to_the_previously_rendered_source(self):
        fbx.check_previewed_hashes(fbx.PREVIEWED_OVERLAY_SHA, fbx.PREVIEWED_COMBINED_SHA)
        with self.assertRaises(ValueError):
            fbx.check_previewed_hashes('0'*64, fbx.PREVIEWED_COMBINED_SHA)
        with self.assertRaises(ValueError):
            fbx.check_previewed_hashes(fbx.PREVIEWED_OVERLAY_SHA, '0'*64)

    def test_clean_process_report_must_keep_identity_and_channels(self):
        fields = ('kind', 'model', 'source_manifest_sha256', 'source_obj_sha256', 'source_plan_lf_sha256',
                  'source_mtl_sha256', 'overlay_obj_sha256', 'combined_obj_sha256', 'baseline_fbx_sha256',
                  'fbx_sha256', 'preview_run', 'preview_artifact', 'world_pivot_m', 'yaw_deg', 'source_axes', 'scene_unit', 'scene_unit_scale',
                  'blender_version', 'uv_layer', 'facts', 'textures', 'normal_repair')
        previous = {field: field for field in fields}
        previous['phase'] = 'export'
        current = dict(previous)
        current['phase'] = 'verify'
        fbx.report_matches(previous, current)
        for key in fields:
            changed = {**current, key: 'changed'}
            with self.subTest(field=key), self.assertRaises(ValueError):
                fbx.report_matches(previous, changed)
        with self.assertRaises(ValueError):
            fbx.report_matches({**previous, 'phase': 'verify'}, current)


if __name__ == '__main__':
    unittest.main()
