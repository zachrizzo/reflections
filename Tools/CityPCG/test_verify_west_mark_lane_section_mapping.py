"""Offline tests of signed-geometry comparison and fake reflected UE APIs."""

import json
from contextlib import contextmanager
from pathlib import Path
import shutil
import struct
import sys
from tempfile import gettempdir, mkdtemp
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import verify_west_mark_lane_section_mapping as proof


@contextmanager
def checked_tempdir():
    """Refuse recursive cleanup unless the resolved directory remains in temp."""
    parent = Path(gettempdir()).resolve(strict=True)
    target = Path(mkdtemp(prefix='codex-section-proof-', dir=str(parent)))
    resolved = target.resolve(strict=True)
    if target.is_symlink() or not target.is_absolute() or resolved.parent != parent or resolved != target:
        raise RuntimeError('Unexpected temporary directory; refusing cleanup.')
    try:
        yield resolved
    finally:
        current = target.resolve(strict=True)
        if target.is_symlink() or current != resolved or current.parent != parent:
            raise RuntimeError('Temporary directory changed; refusing recursive cleanup.')
        shutil.rmtree(current)


def vector(x, y, z):
    return SimpleNamespace(x=x, y=y, z=z)


def make_glb(path, triangles, names=None):
    """One triangle per primitive, in GLB metres; materials intentionally repeat."""
    data = {'nodes': [{'mesh': 0}], 'meshes': [{'primitives': []}], 'accessors': [],
            'bufferViews': [], 'buffers': [{'byteLength': 0}],
            'materials': [{'name': name} for name in (names or ['WorldGridMaterial'])]}
    binary = bytearray()
    for number, triangle in enumerate(triangles):
        position_start = len(binary)
        for point in triangle:
            binary.extend(struct.pack('<3f', *point))
        pview = len(data['bufferViews'])
        data['bufferViews'].append({'buffer': 0, 'byteOffset': position_start, 'byteLength': 36})
        pindex = len(data['accessors'])
        data['accessors'].append({'bufferView': pview, 'componentType': 5126, 'type': 'VEC3', 'count': 3})
        istart = len(binary)
        binary.extend(bytes((0, 1, 2, 0)))
        iview = len(data['bufferViews'])
        data['bufferViews'].append({'buffer': 0, 'byteOffset': istart, 'byteLength': 3})
        iindex = len(data['accessors'])
        data['accessors'].append({'bufferView': iview, 'componentType': 5121, 'type': 'SCALAR', 'count': 3})
        data['meshes'][0]['primitives'].append({'attributes': {'POSITION': pindex}, 'indices': iindex,
                                                'material': number if names else 0})
    data['buffers'][0]['byteLength'] = len(binary)
    raw = json.dumps(data, separators=(',', ':')).encode()
    raw += b' ' * (-len(raw) % 4)
    path.write_bytes(struct.pack('<4sIII4s', b'glTF', 2, 28 + len(raw) + len(binary), len(raw), b'JSON')
                     + raw + struct.pack('<I4s', len(binary), b'BIN\x00') + binary)


class FakeGeometry:
    def __init__(self):
        self.slot_materials = [object(), object()]
        self.mesh = SimpleNamespace(get_editor_property=lambda name: [
            SimpleNamespace(get_editor_property=lambda key: 'GL_Facade'),
            SimpleNamespace(get_editor_property=lambda key: 'GL_Road')],
            get_material=lambda n: self.slot_materials[n])
        self.positions = [vector(0, 0, 0), vector(100, 0, 0), vector(0, 100, 0),
                          vector(0, 0, 100), vector(100, 0, 100), vector(0, 100, 100)]
        self.triangles = [vector(0, 1, 2), vector(3, 4, 5)]
        self.ids = [0, 1]
        self.success = object()
        self.found = object()
        self.source_model = object()
        self.dynamic = object()
        self.called_with_section_ids = False
        self.gaps = False
        self.unreal = SimpleNamespace(
            DynamicMesh=lambda: self.dynamic,
            GeometryScriptMeshReadLOD=lambda: SimpleNamespace(),
            GeometryScriptCopyMeshFromAssetOptions=lambda: SimpleNamespace(),
            GeometryScriptLODType=SimpleNamespace(SOURCE_MODEL=self.source_model),
            GeometryScriptOutcomePins=SimpleNamespace(SUCCESS=self.success),
            GeometryScriptSearchOutcomePins=SimpleNamespace(FOUND=self.found),
            GeometryScript_AssetUtils=SimpleNamespace(
                check_static_mesh_has_available_lod=self.available,
                copy_mesh_from_static_mesh_v2=self.copy,
                get_section_material_list_from_static_mesh=self.material_list),
            GeometryScript_MeshQueries=SimpleNamespace(
                get_all_triangle_indices=lambda mesh, skip: (mesh, self.triangles, self.gaps),
                get_all_vertex_positions=lambda mesh, skip: (mesh, self.positions, False)),
            GeometryScript_Materials=SimpleNamespace(
                get_all_triangle_material_i_ds=lambda mesh: (mesh, self.ids, True)),
            GeometryScript_List=SimpleNamespace(convert_triangle_list_to_array=list,
                                                convert_vector_list_to_array=list,
                                                convert_index_list_to_array=list))

    def available(self, mesh, lod):
        assert mesh is self.mesh and lod.lod_type is self.source_model and lod.lod_index == 0
        return self.found

    def copy(self, mesh, dynamic, options, lod, section_ids):
        assert mesh is self.mesh and dynamic is self.dynamic
        assert not options.apply_build_settings and not options.use_build_scale and not options.request_tangents
        self.called_with_section_ids = section_ids
        return dynamic, self.success

    def material_list(self, mesh, lod):
        return self.slot_materials, [0, 1], ['GL_Facade', 'GL_Road'], self.success


class SectionProofTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeGeometry()
        self.positions, self.triangles, self.ids, self.names = proof.reflected_source(
            self.fake.unreal, self.fake.mesh, lambda: None)
        self.source = proof.source_sections(self.positions, self.triangles, self.ids, len(self.names))

    def test_permuted_primitives_map_by_geometry_despite_shared_material(self):
        self.assertTrue(self.fake.called_with_section_ids)
        with checked_tempdir() as folder:
            path = Path(folder) / 'tile.glb'
            points = [proof.from_unreal_cm((p.x, p.y, p.z)) for p in self.positions]
            make_glb(path, [[points[i] for i in (3, 4, 5)], [points[i] for i in (0, 1, 2)]])
            result = proof.compare(self.source, proof.glb_sections(path), self.names)
        self.assertEqual(result['status'], 'geometry_match_review_required')
        self.assertEqual([row['source_section_candidates'] for row in result['mapping']], [[1], [0]])
        self.assertEqual(result['road_primitive_candidate'], 0)
        self.assertFalse(result['road_retention_in_filtered_replacement_verified'])
        self.assertFalse(result['activation_authorized'])

    def test_reverse_winding_does_not_match_but_cyclic_order_does(self):
        points = [proof.from_unreal_cm((p.x, p.y, p.z)) for p in self.positions[:3]]
        self.assertEqual(proof.triangle_key(points), proof.triangle_key(points[1:] + points[:1]))
        self.assertNotEqual(proof.triangle_key(points), proof.triangle_key([points[0], points[2], points[1]]))
        primitive = [{proof.triangle_key([points[0], points[2], points[1]]): 1}]
        self.assertEqual(proof.compare(self.source[:1], primitive, self.names[:1])['status'],
                         'ambiguous_or_mismatch')

    def test_identical_sections_are_reported_ambiguous(self):
        result = proof.compare([self.source[0], self.source[0]], [self.source[0], self.source[0]], self.names)
        self.assertFalse(result['exact_signed_triangle_bijection'])
        self.assertGreater(result['shared_signed_triangles_across_source_sections'], 0)
        self.assertEqual(result['mapping'][0]['source_section_candidates'], [0, 1])
        self.assertIsNone(result['road_primitive_candidate'])

    def test_lost_or_duplicate_triangles_fail_closed(self):
        modified = self.source[0].copy()
        modified[next(iter(modified))] += 1
        result = proof.compare(self.source, [modified, self.source[1]], self.names)
        self.assertFalse(result['exact_signed_triangle_bijection'])
        self.assertEqual(result['mapping'][0]['source_section_candidates'], [])

    def test_invalid_or_degenerate_source_triangles_fail(self):
        with self.assertRaises(ValueError):
            proof.source_sections(self.positions, [vector(0, 0, 1)], [0], 1)
        with self.assertRaises(ValueError):
            proof.source_sections(self.positions, self.triangles, [0, -1], 2)

    def test_missing_api_or_gaps_fail_closed(self):
        del self.fake.unreal.GeometryScript_Materials.get_all_triangle_material_i_ds
        with self.assertRaisesRegex(proof.CapabilityError, 'get_all_triangle_material_i_ds'):
            proof.reflected_source(self.fake.unreal, self.fake.mesh, lambda: None)
        self.fake = FakeGeometry()
        self.fake.gaps = True
        with self.assertRaisesRegex(proof.CapabilityError, 'gaps'):
            proof.reflected_source(self.fake.unreal, self.fake.mesh, lambda: None)

    def test_unavailable_source_lod_fails_closed(self):
        for result in (None, False, (False, self.fake.found), (True, object())):
            self.fake.unreal.GeometryScript_AssetUtils.check_static_mesh_has_available_lod = lambda *_, r=result: r
            with self.assertRaisesRegex(proof.CapabilityError, 'LOD0'):
                proof.reflected_source(self.fake.unreal, self.fake.mesh, lambda: None)

    def test_positive_reflected_bool_and_found_tuple_is_accepted(self):
        self.fake.unreal.GeometryScript_AssetUtils.check_static_mesh_has_available_lod = lambda *_: (True, self.fake.found)
        _positions, _triangles, _ids, names = proof.reflected_source(self.fake.unreal, self.fake.mesh, lambda: None)
        self.assertEqual(names, ['GL_Facade', 'GL_Road'])

    def test_changed_reflected_signature_names_missing_capability(self):
        self.fake.unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh_v2 = lambda: None
        with self.assertRaisesRegex(proof.CapabilityError, 'copy_mesh_from_static_mesh_v2'):
            proof.reflected_source(self.fake.unreal, self.fake.mesh, lambda: None)

    def test_full_run_is_read_only_and_reports_unverified_road_retention(self):
        with checked_tempdir() as folder:
            project = Path(folder)
            saved = project / 'Saved'
            source = saved / 'CityPCG' / f'{proof.TILE}.glb'
            source.parent.mkdir(parents=True)
            points = [proof.from_unreal_cm((p.x, p.y, p.z)) for p in self.positions]
            make_glb(source, [[points[i] for i in (3, 4, 5)], [points[i] for i in (0, 1, 2)]])
            survey = saved / 'CityPCG/MedievalSurvey'
            survey.mkdir()
            filtered = survey / 'Tile_p03_p00_without_three_west_shells.glb'
            named = survey / 'SM_GLMedieval_WestBlockTile.glb'
            make_glb(filtered, [[points[i] for i in (0, 1, 2)], [points[i] for i in (3, 4, 5)]])
            make_glb(named, [[points[i] for i in (3, 4, 5)], [points[i] for i in (0, 1, 2)]],
                     names=['GL_Road', 'GL_Facade'])
            self.fake.mesh.get_path_name = lambda: proof.ASSET
            self.fake.unreal.StaticMesh = SimpleNamespace
            self.fake.unreal.EditorAssetLibrary = SimpleNamespace(load_asset=lambda package: self.fake.mesh)
            self.fake.unreal.AssetRegistryHelpers = SimpleNamespace(get_asset_registry=lambda: object())
            self.fake.unreal.AssetRegistryDependencyOptions = lambda **kwargs: kwargs
            world, lease = object(), {'owner': 'codex-gray-london'}
            row = {'package_hashes': {'source.uasset': 'abc'}}
            transform = {'source': 'loaded_actor_component'}
            with patch.dict(sys.modules, {'unreal': self.fake.unreal}), \
                    patch.object(proof.lease_tools, 'check_session', return_value=(project, saved, world, lease)), \
                    patch.object(proof.lease_tools, 'require_memory'), \
                    patch.object(proof.lease_tools, 'identity', return_value=(row, None)), \
                    patch.object(proof.lease_tools, 'descriptors', return_value={}), \
                    patch.object(proof.lease_tools, 'loaded_actors', return_value={}), \
                    patch.object(proof.lease_tools, 'transform_evidence', return_value=transform), \
                    patch.object(proof.lease_tools, 'dirty_packages', return_value=set()):
                result = proof.run()
            self.assertTrue(result['exact_signed_triangle_bijection'])
            self.assertFalse(result['activation_authorized'])
            self.assertFalse(result['road_retention_in_filtered_replacement_verified'])
            road = result['road_glb_retention']
            self.assertEqual((road['source_primitive'], road['filtered_primitive'], road['import_primitive']), (0, 1, 0))
            self.assertTrue(road['original_road_geometry_in_filtered_glb_verified'])
            self.assertTrue(road['named_import_road_material_verified'])
            self.assertFalse(road['actual_unreal_replacement_verified'])
            self.assertEqual(set(p for p in saved.rglob('*') if p.is_file()), {source, filtered, named})


if __name__ == '__main__':
    unittest.main()
