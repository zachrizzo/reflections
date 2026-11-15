"""Small offline checks; no Blender, editor, generated files or network."""
import hashlib
import json
import math
from pathlib import Path
import struct
import unittest
from unittest import mock

import stronghold_entrance_review_common as c


def read_glb(raw):
    signature, version, size = struct.unpack_from('<4sII', raw)
    json_length, kind = struct.unpack_from('<I4s', raw, 12)
    binary_length, binary_kind = struct.unpack_from('<I4s', raw, 20+json_length)
    if (signature != b'glTF' or version != 2 or size != len(raw) or kind != b'JSON'
            or binary_kind != b'BIN\0' or 28+json_length+binary_length != size):
        raise ValueError('Unexpected pinned source GLB structure')
    return json.loads(raw[20:20+json_length]), raw[28+json_length:]


def read_accessor(document, binary, index):
    accessor = document['accessors'][index]
    view = document['bufferViews'][accessor['bufferView']]
    width = {'SCALAR': 1, 'VEC3': 3}[accessor['type']]
    fmt = {5123: 'H', 5125: 'I', 5126: 'f'}[accessor['componentType']]
    decoder = struct.Struct('<'+fmt*width)
    offset = view.get('byteOffset', 0)+accessor.get('byteOffset', 0)
    stride = view.get('byteStride', decoder.size)
    return [decoder.unpack_from(binary, offset+i*stride) for i in range(accessor['count'])]


class EntranceReviewTests(unittest.TestCase):
    def test_triangle_box_separation_and_contact(self):
        low, high = (-1., -1., -1.), (1., 1., 1.)
        self.assertTrue(c.triangle_intersects_box([(0, 0, 0), (.5, 0, 0), (0, .5, 0)], low, high))
        self.assertTrue(c.triangle_intersects_box([(1, -.5, 0), (1, .5, 0), (1, 0, .5)], low, high))
        # All three vertices are outside, but the triangle crosses the box.
        self.assertTrue(c.triangle_intersects_box([(-3, 0, 0), (3, 0, 0), (0, 3, 0)], low, high))
        # This triangle's AABB overlaps the box, but the triangle misses it.
        self.assertFalse(c.triangle_intersects_box([(2, .8, 0), (.8, 2, 0), (2, 2, 0)], low, high))
        self.assertFalse(c.triangle_intersects_box([(2, 0, 0), (3, 0, 0), (2, 1, 0)], low, high))
        with self.assertRaises(ValueError):
            c.triangle_intersects_box([(math.nan, 0, 0), (0, 0, 0), (1, 0, 0)], low, high)

    def test_existing_gate_and_both_flags_have_no_surface_in_passage_box(self):
        names = ('SM_GL1450_StrongholdGateFrame', 'SM_GL1450_StrongholdPennantsOccupied',
                 'SM_GL1450_StrongholdPennantsReclaimed')
        counts = (2856, 5392, 5392)
        for name, count in zip(names, counts):
            path = c.ROOT/c.KIT/(name+'.glb')
            self.assertEqual(c.sha(path), c.SOURCE_HASHES[c.KIT/(name+'.glb')])
            document, binary = read_glb(path.read_bytes())
            self.assertEqual(document['nodes'], [{'mesh': 0, 'name': name}])
            total = 0
            for primitive in document['meshes'][0]['primitives']:
                positions = read_accessor(document, binary, primitive['attributes']['POSITION'])
                indices = read_accessor(document, binary, primitive['indices'])
                self.assertEqual(len(indices) % 3, 0)
                for i in range(0, len(indices), 3):
                    # glTF Y-up -> Blender Z-up: (x,y,z) -> (x,-z,y).
                    triangle = []
                    for j in range(3):
                        x, y, z = positions[indices[i+j][0]]
                        triangle.append((x, -z, y))
                    self.assertFalse(c.triangle_intersects_box(triangle), f'{name}: triangle {total}')
                    total += 1
            self.assertEqual(total, count)

    def test_workflow_only_guard_rejects_other_commits_and_paths(self):
        head, before = 'a'*40, 'b'*40
        event = {'before': before, 'after': head, 'ref': 'refs/heads/main',
                 'deleted': False, 'created': False, 'forced': False}
        parents = (head+' '+before+'\n').encode()
        changed = c.WORKFLOW.encode()+b'\0'
        c.push_shape(event, head, parents, changed)
        for ev, par, paths in (({**event, 'forced': True}, parents, changed),
                               (event, parents+b'c'*40, changed), (event, parents, changed+b'other\0')):
            with self.assertRaises(ValueError):
                c.push_shape(ev, head, par, paths)

    def test_source_text_pin_normalizes_only_line_endings(self):
        with mock.patch.object(Path, 'read_bytes', return_value=b'a\r\nb\r\n'):
            self.assertEqual(c.text_sha(Path('unused')), hashlib.sha256(b'a\nb\n').hexdigest())
        with mock.patch.object(Path, 'read_bytes', return_value=b'a\rb'):
            with self.assertRaises(ValueError):
                c.text_sha(Path('unused'))


if __name__ == '__main__':
    unittest.main()
