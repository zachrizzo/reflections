"""Small standard-library checks; do not import Blender or generate assets."""

import io
import json
from pathlib import Path
import textwrap
from types import SimpleNamespace as Stub
import unittest
from unittest import mock

import north_market_roundtrip_common as qa
import north_market_hosted_blender as adapter


def corner(x, y, z=0, u=0, v=0, nx=0, ny=0, nz=1):
    return (x, y, z, u, v, nx, ny, nz)


TRI = ('M_wall', (corner(0, 0, u=0), corner(2, 0, u=1), corner(0, 3, v=1)))


def mesh(*faces):
    return {'vertices': 3, 'edges': 3, 'uv_corners': 3 * len(faces),
            'slots': ['M_wall'], 'faces': list(faces)}


class PolygonComparisonTests(unittest.TestCase):
    def test_cyclic_reordering_preserves_winding(self):
        rotated = ('M_wall', TRI[1][1:] + TRI[1][:1])
        self.assertEqual(qa.compare(mesh(TRI), mesh(rotated))['polygons'], 1)

    def test_reversed_winding_fails(self):
        with self.assertRaises(ValueError):
            qa.compare(mesh(TRI), mesh(('M_wall', tuple(reversed(TRI[1])))))

    def test_material_uv_normal_and_position_changes_fail(self):
        base = list(TRI[1])
        for index, delta in ((0, 0.01), (3, 0.01), (5, 0.1)):
            changed = list(base[1])
            changed[index] += delta
            corners = base.copy()
            corners[1] = tuple(changed)
            with self.subTest(channel=index), self.assertRaises(ValueError):
                qa.compare(mesh(TRI), mesh(('M_wall', tuple(corners))))
        with self.assertRaises(ValueError):
            qa.compare(mesh(TRI), mesh(('M_other', TRI[1])))

    def test_small_round_trip_numerical_change_passes(self):
        changed = tuple(tuple(v + (1e-6 if i in (0, 3, 5) else 0) for i, v in enumerate(c))
                        for c in TRI[1])
        qa.compare(mesh(TRI), mesh(('M_wall', changed)))

    def test_nonidentical_ambiguous_matches_fail(self):
        shifted = tuple(tuple(v + (1e-6 if i == 0 else 0) for i, v in enumerate(c)) for c in TRI[1])
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            qa.compare(mesh(TRI, TRI), mesh(TRI, ('M_wall', shifted)))

    def test_identical_duplicates_keep_multiplicity(self):
        qa.compare(mesh(TRI, TRI), mesh(TRI, TRI))
        with self.assertRaises(ValueError):
            qa.compare(mesh(TRI, TRI), mesh(TRI))

    def test_changed_edges_or_slot_order_fails(self):
        altered = mesh(TRI)
        altered['edges'] = 4
        with self.assertRaisesRegex(ValueError, 'edges'):
            qa.compare(mesh(TRI), altered)
        altered = mesh(TRI)
        altered['slots'] = ['M_other', 'M_wall']
        with self.assertRaisesRegex(ValueError, 'slots'):
            qa.compare(mesh(TRI), altered)

    def test_nonfinite_corner_values_fail_closed(self):
        for value in (float('nan'), float('inf'), float('-inf')):
            changed = list(TRI[1][1])
            changed[3] = value
            face = ('M_wall', (TRI[1][0], tuple(changed), TRI[1][2]))
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'non-finite'):
                qa.compare(mesh(TRI), mesh(face))

    def test_missing_polygon_reports_channel_deltas_without_accepting(self):
        changed = list(TRI[1][1])
        changed[3] += 0.01
        face = ('M_wall', (TRI[1][0], tuple(changed), TRI[1][2]))
        with self.assertRaisesRegex(ValueError, r'source_polygon=0.*max_uv_delta=0\.01'):
            qa.compare(mesh(TRI), mesh(face))

    def test_reversed_winding_is_reported_not_accepted(self):
        face = ('M_wall', tuple(reversed(TRI[1])))
        with self.assertRaisesRegex(ValueError, r'reversed_winding=True.*max_position_delta_m=0'):
            qa.compare(mesh(TRI), mesh(face))

    def test_changed_assignment_reports_matching_geometry_material(self):
        before, after = mesh(TRI), mesh(('M_other', TRI[1]))
        before['slots'] = after['slots'] = ['M_wall', 'M_other']
        with self.assertRaisesRegex(ValueError, r'candidate_material=M_other.*max_position_delta_m=0'):
            qa.compare(before, after)


class SourceParserTests(unittest.TestCase):
    def parse(self, source):
        with mock.patch('pathlib.Path.open', return_value=io.StringIO(source)):
            return qa.read_obj('unused.obj', ['M_wall'])

    def test_read_corner_channels_and_edges(self):
        source = ('mtllib NorthMarketDetail.mtl\nv 0 0 0\nv 2 0 0\nv 0 3 0\n'
                  'vt 0 0\nvt 1 0\nvt 0 1\nvn 0 0 1\nusemtl M_wall\n'
                  'f 1/1/1 2/2/1 3/3/1\n')
        qa.compare(mesh(TRI), self.parse(source))

    def test_reject_missing_uv_or_unexpected_library(self):
        with self.assertRaises(ValueError):
            self.parse('mtllib wrong.mtl\nusemtl M_wall\nf 1//1 2//1 3//1\n')

    def test_reject_modified_manifest_before_reading_its_content(self):
        with mock.patch.object(qa, 'within', return_value=Path('unused')), \
             mock.patch.object(qa, 'digest', return_value='f' * 64), \
             self.assertRaisesRegex(ValueError, 'manifest hash'):
            qa.source_spec(Path(__file__).resolve().parent, qa.NAMES[0])

    def test_reject_nonfinite_placement_metadata(self):
        for pivot, yaw in (([float('nan'), 0, 0], 0), ([0, 0, 0], float('inf'))):
            manifest = {'buildings': {'candidate': {'source_artifact': {'file': qa.NAMES[0] + '.obj'},
                                                    'world_pivot_m': pivot, 'yaw_deg': yaw}}}
            with self.subTest(pivot=pivot, yaw=yaw), \
                 mock.patch.object(qa, 'within', side_effect=lambda path, _: path), \
                 mock.patch.object(qa, 'digest', return_value=qa.MANIFEST_SHA), \
                 mock.patch('pathlib.Path.read_text', return_value=json.dumps(manifest)), \
                 self.assertRaisesRegex(ValueError, 'placement metadata'):
                qa.source_spec(Path(__file__).resolve().parent, qa.NAMES[0])


class MaterialGraphTests(unittest.TestCase):
    @staticmethod
    def obj(color, alpha=None):
        if alpha is None:
            alpha = Stub(links=[], default_value=1.0)
        shader = Stub(type='BSDF_PRINCIPLED', inputs={'Base Color': color, 'Alpha': alpha})
        output = Stub(type='OUTPUT_MATERIAL', is_active_output=True,
                      inputs={'Surface': Stub(links=[Stub(from_node=shader)])})
        material = Stub(name='M_wall', use_nodes=True, node_tree=Stub(nodes=[output]))
        return Stub(data=Stub(materials=[material]))

    def test_wrong_solid_color_is_rejected(self):
        specs = {'M_wall': {'texture': None, 'kd': (0.052, 0.054, 0.041)}}
        with self.assertRaisesRegex(ValueError, 'base color'):
            adapter.material_textures(None, self.obj(Stub(links=[], default_value=(1, 0, 0, 1))), specs, '.')
        correct = Stub(links=[], default_value=(0.052, 0.054, 0.041, 1))
        self.assertEqual(adapter.material_textures(None, self.obj(correct), specs, '.')['M_wall']['kind'], 'solid')

    def test_nonfinite_solid_color_is_rejected(self):
        specs = {'M_wall': {'texture': None, 'kd': (0.052, 0.054, 0.041)}}
        for value in (float('nan'), float('inf'), float('-inf')):
            color = Stub(links=[], default_value=(value, 0.054, 0.041, 1))
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'base color'):
                adapter.material_textures(None, self.obj(color), specs, '.')

    def test_unexpected_or_nonfinite_alpha_is_rejected(self):
        specs = {'M_wall': {'texture': None, 'kd': (0.052, 0.054, 0.041)}}
        color = Stub(links=[], default_value=(0.052, 0.054, 0.041, 1))
        for alpha in (Stub(links=[], default_value=0.0), Stub(links=[], default_value=float('nan')),
                      Stub(links=[], default_value=float('inf')), Stub(links=[object()], default_value=1.0)):
            with self.subTest(alpha=alpha), self.assertRaisesRegex(ValueError, 'alpha'):
                adapter.material_textures(None, self.obj(color, alpha), specs, '.')

    def test_texture_hidden_behind_tint_node_is_rejected(self):
        specs = {'M_wall': {'texture': {'name': 'wall.png', 'sha256': 'abc'}, 'kd': (1, 1, 1)}}
        mixed = Stub(links=[Stub(from_node=Stub(type='MIX_RGB'), from_socket=Stub(name='Color'))])
        with self.assertRaisesRegex(ValueError, 'texture graph'):
            adapter.material_textures(None, self.obj(mixed), specs, '.')

    def test_texture_using_a_custom_vector_mapping_is_rejected(self):
        specs = {'M_wall': {'texture': {'name': 'wall.png', 'sha256': 'abc'}, 'kd': (1, 1, 1)}}
        image = Stub(packed_file=None)
        image_node = Stub(type='TEX_IMAGE', image=image, inputs={'Vector': Stub(links=[object()])})
        color = Stub(links=[Stub(from_node=image_node, from_socket=Stub(name='Color'))])
        with self.assertRaisesRegex(ValueError, 'texture graph'):
            adapter.material_textures(None, self.obj(color), specs, '.')

    def test_texture_sampling_must_match_source_defaults(self):
        specs = {'M_wall': {'texture': {'name': 'wall.png', 'sha256': 'abc'}, 'kd': (1, 1, 1)}}
        image = Stub(packed_file=None, filepath='wall.png', colorspace_settings=Stub(name='sRGB'))
        node = Stub(type='TEX_IMAGE', image=image, inputs={'Vector': Stub(links=[])},
                    extension='REPEAT', interpolation='Linear', projection='FLAT')
        color = Stub(links=[Stub(from_node=node, from_socket=Stub(name='Color'))])
        bpy = Stub(path=Stub(abspath=lambda _: '/sandbox/wall.png'))
        with mock.patch.object(qa, 'within', return_value=Path('/sandbox/wall.png')), \
             mock.patch.object(qa, 'digest', return_value='abc'):
            self.assertEqual(adapter.material_textures(bpy, self.obj(color), specs, '.')['M_wall']['kind'], 'texture')
            for attr, value in (('extension', 'CLIP'), ('interpolation', 'Closest'), ('projection', 'BOX')):
                original = getattr(node, attr)
                setattr(node, attr, value)
                with self.subTest(attr=attr), self.assertRaisesRegex(ValueError, 'sampling'):
                    adapter.material_textures(bpy, self.obj(color), specs, '.')
                setattr(node, attr, original)
            image.colorspace_settings.name = 'Non-Color'
            with self.assertRaisesRegex(ValueError, 'sampling'):
                adapter.material_textures(bpy, self.obj(color), specs, '.')

    def test_local_hosted_guard_refuses(self):
        with mock.patch.dict('os.environ', {}, clear=True), self.assertRaises(RuntimeError):
            adapter.hosted_context()


class ImportedTransformTests(unittest.TestCase):
    def test_nonfinite_matrix_is_rejected(self):
        for value in (float('nan'), float('inf'), float('-inf')):
            matrix = [[float(i == j) for j in range(4)] for i in range(4)]
            matrix[0][3] = value
            data = Stub(shape_keys=None, uv_layers=[object()], color_attributes=[])
            obj = Stub(type='MESH', parent=None, modifiers=[], vertex_groups=[], data=data, matrix_world=matrix)
            bpy = Stub(context=Stub(scene=Stub(objects=[obj])))
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'identity transform'):
                adapter.one_mesh(bpy)


class WorkflowPushGuardTests(unittest.TestCase):
    def run_guard(self, event, parents=None, changed=None):
        workflow = (Path(__file__).resolve().parents[2] /
                    '.github/workflows/north-market-hosted-roundtrip.yml').read_text(encoding='utf-8')
        marker = "python3 -B - <<'PY'\n"
        self.assertEqual(workflow.count(marker), 1)
        code = textwrap.dedent(workflow.split(marker, 1)[1].split('\n          PY', 1)[0])
        head, before = 'a' * 40, 'b' * 40
        parents = parents if parents is not None else f'{head} {before}\n'
        changed = changed if changed is not None else b'.github/workflows/north-market-hosted-roundtrip.yml\0'
        with mock.patch.dict('os.environ', {'GITHUB_EVENT_PATH': 'event.json', 'GITHUB_SHA': head}), \
             mock.patch('builtins.open', mock.mock_open(read_data=json.dumps(event))), \
             mock.patch('subprocess.check_output', side_effect=[parents, changed]):
            exec(compile(code, 'workflow-push-guard', 'exec'), {})

    @staticmethod
    def event():
        return {'ref': 'refs/heads/main', 'deleted': False, 'forced': False,
                'before': 'b' * 40, 'after': 'a' * 40}

    def test_accept_exact_single_workflow_push(self):
        self.run_guard(self.event())

    def test_reject_extra_changed_file_or_merge(self):
        with self.assertRaises(SystemExit):
            self.run_guard(self.event(), changed=b'.github/workflows/north-market-hosted-roundtrip.yml\0extra\0')
        with self.assertRaises(SystemExit):
            self.run_guard(self.event(), parents=('a' * 40 + ' ' + 'b' * 40 + ' ' + 'c' * 40))

    def test_reject_force_push_branch_and_mismatched_head(self):
        for key, value in (('forced', True), ('deleted', True), ('ref', 'refs/heads/other'), ('after', 'd' * 40)):
            event = self.event()
            event[key] = value
            with self.subTest(key=key), self.assertRaises(SystemExit):
                self.run_guard(event)


class WorkflowPreviewGuardTests(unittest.TestCase):
    @staticmethod
    def workflow():
        return (Path(__file__).resolve().parents[2] /
                '.github/workflows/north-market-hosted-roundtrip.yml').read_text(encoding='utf-8')

    def validate_preview(self, png=b'\x89PNG\r\n\x1a\n', preview_sha='abc', verified_sha='abc'):
        workflow = self.workflow()
        marker = ('python3 -B - "$stage" "$bundle/'
                  'SM_GLMedieval_NorthMarketDetail_east_0a73564b/verify.report.json" <<\'PY\'\n')
        self.assertEqual(workflow.count(marker), 1)
        code = textwrap.dedent(workflow.split(marker, 1)[1].split('\n          PY', 1)[0])

        def fake_open(path, *args, **kwargs):
            return io.BytesIO(png)

        def fake_text(path, *args, **kwargs):
            return json.dumps({'fbx_sha256': preview_sha if path.name == 'preview.report.json' else verified_sha})

        with mock.patch('sys.argv', ['workflow', '/stage', '/verify.report.json']), \
             mock.patch('pathlib.Path.open', autospec=True, side_effect=fake_open), \
             mock.patch('pathlib.Path.read_text', autospec=True, side_effect=fake_text):
            exec(compile(code, 'workflow-preview-guard', 'exec'), {})

    def test_preview_requires_pngs_and_matching_verified_hash(self):
        self.validate_preview()
        for options in ({'png': b'bad'}, {'preview_sha': 'different'}, {'preview_sha': ''}):
            with self.subTest(options=options), self.assertRaises(SystemExit):
                self.validate_preview(**options)

    def test_hidden_staging_precedes_atomic_publish(self):
        workflow = self.workflow()
        self.assertIn('stage="$bundle/.preview-staging"', workflow)
        self.assertIn('include-hidden-files: false', workflow)
        self.assertLess(workflow.index('cp --no-clobber -- "$source/$name" "$stage/$name"'),
                        workflow.index('mv -T -- "$stage" "$bundle/preview"'))


if __name__ == '__main__':
    unittest.main()
