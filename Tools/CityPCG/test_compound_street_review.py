"""Small offline checks; no Blender, archive extraction or editor access."""
import hashlib
from pathlib import Path
import stat
from types import SimpleNamespace
import unittest

import compound_review_common as c
import stronghold_entrance_review_common as triangles


class CompoundReviewTests(unittest.TestCase):
    def test_gate_pose_is_invertible_and_preserves_orientation(self):
        self.assertAlmostEqual(c.gate_to_world((1, 0, 0))[0], 32.2)
        self.assertAlmostEqual(c.gate_to_world((1, 0, 0))[1], -19.5)
        self.assertAlmostEqual(c.gate_to_world((0, 1, 0))[0], 31.2)
        for point in ((0, 0, 0), (5, -1.1, 2.4), (-2.8, 3.4, .2)):
            actual = c.world_to_gate(c.gate_to_world(point))
            for got, expected in zip(actual, point):
                self.assertAlmostEqual(got, expected, places=10)

    def test_transformed_surface_crossing_the_passage_is_rejected(self):
        world = [c.gate_to_world(point) for point in ((-6, 0, 1), (6, 0, 1), (0, 3, 1))]
        local = [c.world_to_gate(point) for point in world]
        self.assertTrue(triangles.triangle_intersects_box(local, c.CORRIDOR_LOW, c.CORRIDOR_HIGH))
        outside = [(-4, 2.7, 1), (4, 2.7, 1), (0, 3.2, 1)]
        self.assertFalse(triangles.triangle_intersects_box(outside, c.CORRIDOR_LOW, c.CORRIDOR_HIGH))

    def test_expected_archive_member_rejects_duplicates_and_symlinks(self):
        def entry(name, mode=0, encrypted=0, compression=8, size=42, directory=False):
            return SimpleNamespace(filename=name, external_attr=mode << 16, flag_bits=encrypted,
                                   compress_type=compression, file_size=size, is_dir=lambda: directory)
        wanted = entry('inside.glb')
        archive = SimpleNamespace(infolist=lambda: [wanted, entry('../other.glb')])
        self.assertIs(c.member(archive, 'inside.glb'), wanted)
        for rows in ([wanted, wanted], [entry('inside.glb', stat.S_IFLNK)],
                     [entry('inside.glb', encrypted=1)], [entry('inside.glb', compression=99)],
                     [entry('inside.glb', size=129*2**20)], [entry('inside.glb', directory=True)]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                c.member(SimpleNamespace(infolist=lambda: rows), 'inside.glb')

    def test_source_artifact_pins_and_helper_identity(self):
        self.assertEqual(c.ARCHIVES[c.STREET_ZIP][0], 35334942)
        self.assertEqual(c.MEMBER_SIZES['street'], 18499916)
        self.assertEqual(c.MEMBERS['street'][2], '36c0f99f20230e7e2404d491d499c9b26dfce49d1dbd434194a3c6fad97227e2')
        for rel, expected in ((c.TRIANGLE_HELPER, c.TRIANGLE_HELPER_LF_SHA),
                              (c.KIT_HELPER, c.KIT_HELPER_LF_SHA)):
            data = (c.ROOT/rel).read_bytes().replace(b'\r\n', b'\n')
            self.assertEqual(hashlib.sha256(data).hexdigest(), expected)

    def test_workflow_trigger_is_one_nonmerge_main_commit(self):
        head, before = 'a'*40, 'b'*40
        event = {'before': before, 'after': head, 'ref': 'refs/heads/main',
                 'created': False, 'deleted': False, 'forced': False}
        parents = (head+' '+before+'\n').encode()
        paths = c.WORKFLOW.encode()+b'\0'
        c.check_push_shape(event, head, parents, paths)
        for ev, par, changed in (({**event, 'forced': True}, parents, paths),
                                 (event, parents+b'c'*40, paths), (event, parents, paths+b'other\0')):
            with self.assertRaises(ValueError): c.check_push_shape(ev, head, par, changed)


if __name__ == '__main__':
    unittest.main()
