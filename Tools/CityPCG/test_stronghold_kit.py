"""Verify the portable stronghold GLBs without Blender or Unreal."""

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from build_stronghold_kit import NEUTRAL, OCCUPIED, RECLAIMED, WATCH_GATE, build, read_glb, split_source, triangle_count


def primitives(document):
    return document['meshes'][0]['primitives']


def streams(document):
    return [(part['indices'], part['attributes']) for part in primitives(document)]


class StrongholdKitTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(TemporaryDirectory()))
        self.source, self.buffer = read_glb(WATCH_GATE.read_bytes())

    def asset(self, name):
        return read_glb(WATCH_GATE.with_name(f'{name}.glb').read_bytes())

    def test_portable_variants_reproduce_byte_for_byte(self):
        output = self.directory / 'rebuilt'
        report = build(WATCH_GATE, output)
        self.assertEqual(WATCH_GATE.parent.name, 'Source')
        self.assertEqual(report['source_triangles'], 8248)
        for name in (NEUTRAL, OCCUPIED, RECLAIMED):
            with self.subTest(name=name):
                asset_name = f'{name}.glb'
                self.assertEqual((output / asset_name).read_bytes(), WATCH_GATE.with_name(asset_name).read_bytes())

    def test_frame_and_pennants_preserve_geometry_and_pivot(self):
        frame, frame_bin = self.asset(NEUTRAL)
        occupied, occupied_bin = self.asset(OCCUPIED)
        self.assertEqual(frame_bin, self.buffer)
        self.assertEqual(occupied_bin, self.buffer)
        self.assertEqual(frame['nodes'], [{'mesh': 0, 'name': NEUTRAL}])
        self.assertEqual(occupied['nodes'], [{'mesh': 0, 'name': OCCUPIED}])
        self.assertCountEqual(streams(frame) + streams(occupied), streams(self.source))
        self.assertEqual(triangle_count(frame, primitives(frame)), 2856)
        self.assertEqual(triangle_count(occupied, primitives(occupied)), 5392)

    def test_pennant_variants_share_geometry_and_differ_in_colors(self):
        occupied, occupied_bin = self.asset(OCCUPIED)
        reclaimed, reclaimed_bin = self.asset(RECLAIMED)
        self.assertEqual(occupied_bin, reclaimed_bin)
        self.assertEqual(primitives(occupied), primitives(reclaimed))
        self.assertEqual(occupied['accessors'], reclaimed['accessors'])
        self.assertEqual(occupied['bufferViews'], reclaimed['bufferViews'])
        occupied_colors = [row['pbrMetallicRoughness']['baseColorFactor'] for row in occupied['materials']]
        reclaimed_colors = [row['pbrMetallicRoughness']['baseColorFactor'] for row in reclaimed['materials']]
        self.assertNotEqual(occupied_colors, reclaimed_colors)
        self.assertNotEqual(occupied_colors[0], occupied_colors[1])
        self.assertEqual(reclaimed_colors[0], reclaimed_colors[1])
        self.assertNotEqual(reclaimed_colors[0], reclaimed_colors[2])

    def test_bad_source_hash_leaves_no_output(self):
        altered = self.directory / WATCH_GATE.name
        altered.write_bytes(WATCH_GATE.read_bytes() + b'x')
        output = self.directory / 'rejected'
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            build(altered, output)
        self.assertFalse(output.exists())

    def test_changed_material_slot_and_primitive_orders_are_rejected(self):
        changed = deepcopy(self.source)
        slots = changed['materials']
        slots[0], slots[1] = slots[1], slots[0]
        with self.assertRaisesRegex(ValueError, 'material names or slot order'):
            split_source(changed)

        changed = deepcopy(self.source)
        parts = primitives(changed)
        parts[0], parts[1] = parts[1], parts[0]
        with self.assertRaisesRegex(ValueError, 'primitive material order'):
            split_source(changed)

    def test_build_refuses_to_overwrite_existing_outputs(self):
        output = self.directory / 'existing'
        output.mkdir()
        sentinel = output / f'{NEUTRAL}.glb'
        sentinel.write_bytes(b'leave this original alone')
        with self.assertRaises(FileExistsError):
            build(WATCH_GATE, output)
        self.assertEqual(sentinel.read_bytes(), b'leave this original alone')
        self.assertEqual(list(output.iterdir()), [sentinel])


if __name__ == '__main__':
    unittest.main()
