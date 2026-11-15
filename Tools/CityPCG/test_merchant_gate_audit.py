"""Exercise the gate QA with synthetic geometry and no GPU dependencies."""

from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest

from audit_merchant_gate import audit_file, audit_geometry
from subtract_building_shells import write_glb


def box(x0, x1, y0, y1, z0, z1):
    verts = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    faces = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return [tuple(verts[i] for i in triangle) for a, b, c, d in faces for triangle in ((a, b, c), (a, c, d))]


def gate(front_only=False):
    pier_back = 3.40 if front_only else -3.50
    return (box(pier_back, 3.50, -6.50, -1.65, 0, 3.50)
            + box(pier_back, 3.50, 1.65, 6.50, 0, 3.50)
            + box(-3.50, 3.50, -6.50, 6.50, 3.50, 8))


def write_fixture(path, mesh, node_transform=None):
    positions = [coord for triangle in mesh for x, y, z in triangle for coord in (x, z, y)]
    vertex_count = len(positions) // 3
    coordinate_bytes = struct.pack(f'<{len(positions)}f', *positions)
    index_bytes = struct.pack(f'<{vertex_count}I', *range(vertex_count))
    payload = coordinate_bytes + index_bytes
    document = {
        'asset': {'version': '2.0'}, 'nodes': [{'mesh': 0, **(node_transform or {})}],
        'scenes': [{'nodes': [0]}], 'scene': 0, 'buffers': [{'byteLength': len(payload)}],
        'bufferViews': [{'buffer': 0, 'byteLength': len(coordinate_bytes)},
                        {'buffer': 0, 'byteOffset': len(coordinate_bytes), 'byteLength': len(index_bytes)}],
        'accessors': [{'bufferView': 0, 'type': 'VEC3', 'componentType': 5126, 'count': vertex_count},
                      {'bufferView': 1, 'type': 'SCALAR', 'componentType': 5125, 'count': vertex_count}],
        'meshes': [{'primitives': [{'attributes': {'POSITION': 0}, 'indices': 1}]}],
    }
    write_glb(path, document, bytearray(payload))


class MerchantGateAuditTests(unittest.TestCase):
    def test_clear_passage_allows_ground_floor(self):
        result = audit_geometry(gate() + box(-3.50, 3.50, -1.65, 1.65, 0, .04))
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['obstructing_triangles'], 0)
        self.assertEqual(result['depth_width_height_m'], [7, 13, 8])

    def test_detects_thin_rear_cap_and_small_interior_face(self):
        cap = ((-3.45, -.9, 0), (-3.45, .9, 0), (-3.45, 0, 2.10))
        fragment = ((-.32, .38, .96), (-.32, .40, .98), (-.28, .37, .98))
        for part in (cap, fragment):
            with self.subTest(part=part):
                result = audit_geometry(gate() + [part])
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(result['obstructing_triangles'], 1)

    def test_detects_missing_depth_and_headroom(self):
        facade = audit_geometry(gate(front_only=True))
        self.assertTrue(any('left_pier:' in error for error in facade['errors']))
        upper_cap = ((0, -.35, 2.83), (0, .35, 2.83), (0, 0, 3.24))
        shallow_arch = audit_geometry(gate() + [upper_cap])
        self.assertEqual(shallow_arch['obstructing_triangles'], 0)
        self.assertTrue(any('upper arch is blocked' in error for error in shallow_arch['errors']))

    def test_rejects_normalized_units_and_off_ground_pivot(self):
        miniature = [tuple(tuple(value / 13 for value in vertex) for vertex in part) for part in gate()]
        shifted = [tuple((x, y, z + .4) for x, y, z in part) for part in gate()]
        self.assertTrue(any('metre envelope' in error for error in audit_geometry(miniature)['errors']))
        self.assertTrue(any('Pivot' in error for error in audit_geometry(shifted)['errors']))

    def test_reads_baked_glb_and_checks_uv0_and_transform(self):
        directory = Path(self.enterContext(TemporaryDirectory()))
        clean = directory / 'baked.glb'
        moved = directory / 'wrong_pivot.glb'
        write_fixture(clean, gate())
        self.assertEqual(audit_file(clean)['status'], 'passed')
        self.assertEqual(audit_file(clean, require_uv0=True)['status'], 'failed')
        write_fixture(moved, gate(), {'translation': [0, 1, 0]})
        with self.assertRaisesRegex(ValueError, 'non-identity node translation'):
            audit_file(moved)


if __name__ == '__main__':
    unittest.main()
