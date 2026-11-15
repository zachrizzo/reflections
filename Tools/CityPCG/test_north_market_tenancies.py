"""Small source-geometry tests; no Blender, editor or file generation."""
import io
import json
import math
from types import SimpleNamespace
import unittest

import north_market_tenancies as t
import north_market_tenancy_preview as preview


def rectangle():
    return {'id': 'test', 'footprint_local_m': [[0, 0], [10, 0], [10, 24], [0, 24]],
            'source_max_height_m': 10.,
            'entry': {'edge': 1, 'center_local_xy_m': [10, 12],
                      'recessed_closed_opening_width_height_m': [1.35, 2.3]}}


class TenancyTests(unittest.TestCase):
    def test_entry_is_reserved_and_styles_vary_deterministically(self):
        building = rectangle()
        mesh, units = t.make_details(building)
        mesh2, repeat = t.make_details(building)
        self.assertEqual(units, repeat)
        self.assertEqual(mesh.vertices, mesh2.vertices)
        self.assertEqual({u['style'] for u in units}, {0, 1, 2})
        walls = t.inset([tuple(p) for p in building['footprint_local_m']])
        center_station = 12 - walls[1][1]
        for unit in units:
            self.assertEqual(unit['edge'], 1)
            low, high = unit['station_m']
            self.assertTrue(high <= center_station - 1.225 + 1e-8 or low >= center_station + 1.225 - 1e-8)
        self.assertTrue(all(t.contains((x, y), mesh.plot) and 0 <= z <= mesh.ceiling
                            for x, y, z in mesh.vertices))
        self.assertEqual(len(mesh.faces), len(mesh.roles))

    def test_party_wall_is_never_used(self):
        with self.assertRaisesRegex(ValueError, 'No suitable'):
            t.make_details(rectangle(), party_edges={1})

    def test_concavity_crossing_fails_even_if_both_endpoints_are_inside(self):
        plot = [(0, 0), (4, 0), (4, 4), (3, 4), (3, 1), (1, 1), (1, 4), (0, 4)]
        self.assertTrue(t.contains((.5, 3), plot))
        self.assertTrue(t.contains((3.5, 3), plot))
        self.assertFalse(t.segment_inside((.5, 3), (3.5, 3), plot))
        self.assertTrue(t.segment_inside((.5, .5), (3.5, .5), plot))

    def test_box_rejects_projection_outside_envelope_and_nonfinite(self):
        mesh = t.Mesh([(0, 0), (2, 0), (2, 2), (0, 2)], 5)
        mesh.box((1.7, 0), (0, 1), (1, 0), .5, 1.5, 0, 1, .20, .29, 'Oak')
        for front in (.31, float('nan')):
            with self.assertRaises(ValueError):
                mesh.box((1.7, 0), (0, 1), (1, 0), .5, 1.5, 0, 1, .20, front, 'Oak')
        with self.assertRaisesRegex(ValueError, 'footprint'):
            mesh.box((1.9, 0), (0, 1), (1, 0), .5, 1.5, 0, 1, .20, .29, 'Oak')

    def test_obj_additions_have_valid_offsets_uvs_and_unit_normals(self):
        mesh = t.Mesh([(0, 0), (2, 0), (2, 2), (0, 2)], 5)
        mesh.box((1.7, 0), (0, 1), (1, 0), .5, 1.5, 0, 1, .20, .29, 'Oak')
        stream = io.StringIO()
        t.write_geometry(stream, mesh, (10, 20, 30))
        rows = stream.getvalue().splitlines()
        self.assertEqual(sum(row.startswith('v ') for row in rows), 8)
        self.assertEqual(sum(row.startswith('f ') for row in rows), 6)
        for row in rows:
            if row.startswith('vn '):
                values = list(map(float, row.split()[1:]))
                self.assertAlmostEqual(math.sqrt(sum(x*x for x in values)), 1.0)
            if row.startswith('f '):
                for corner in row.split()[1:]:
                    v, uv, normal = map(int, corner.split('/'))
                    self.assertTrue(11 <= v <= 18 and uv > 20 and 31 <= normal <= 36)

    def test_real_pinned_building_generates_seven_varied_inset_units(self):
        self.assertEqual(t.digest(t.PLAN), t.PINNED['plan'])
        plan = json.loads(t.PLAN.read_text(encoding='utf-8'))
        building = next(item for item in plan['buildings'] if item['id'] == t.BUILDING)
        mesh, units = t.make_details(building)
        self.assertEqual(len(units), 7)
        self.assertEqual({unit['edge'] for unit in units}, {17, 21, 25})
        self.assertEqual({unit['style'] for unit in units}, {0, 1, 2})
        self.assertTrue(all(t.contains((x, y), mesh.plot) for x, y, _ in mesh.vertices))

    def test_overlay_slot_normalization_preserves_face_assignments(self):
        red = SimpleNamespace(name='M_GLMedieval_ShopRed.001')
        oak = SimpleNamespace(name='M_GLMedieval_Oak.001')
        faces = [SimpleNamespace(material_index=0), SimpleNamespace(material_index=1)]
        obj = SimpleNamespace(data=SimpleNamespace(materials=[red, oak], polygons=faces))
        preview.normalize_overlay_slot_order(obj, ['M_GLMedieval_Oak', 'M_GLMedieval_ShopRed'])
        self.assertEqual(obj.data.materials, [oak, red])
        self.assertEqual([face.material_index for face in faces], [1, 0])
        with self.assertRaisesRegex(ValueError, 'slots differ'):
            preview.normalize_overlay_slot_order(obj, ['M_GLMedieval_Oak'])
        with self.assertRaises(ValueError):
            preview.original_material_name('M_GLMedieval_Oak.001.evil')


if __name__ == '__main__':
    unittest.main()
