"""Targeted in-memory corruption checks for the pinned saved actor."""

import struct
import unittest

import verify_west_mark_lane_saved_actor as actor
import verify_west_mark_lane_saved_sections as sections


class SavedActorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (sections.PROJECT / actor.PATH).read_bytes()

    def tags(self):
        data = bytearray(self.original)
        reader = actor.initialize(data)
        mesh = reader.tag(4197, len(data))
        collision = reader.tag(mesh["end"], len(data))
        override = reader.tag(collision["end"], len(data))
        return data, reader, mesh, collision, override

    def test_pinned_saved_values(self):
        result = actor.verify_bytes(self.original)
        self.assertEqual(result["saved_static_mesh"], actor.MESH_PATH)
        self.assertEqual(result["saved_override_materials"], list(sections.REPLACEMENT_REFS[:5]))
        self.assertEqual(result["serialized_relative_location_cm"], (300000.0, 0.0, 0.0))

    def test_asset_hash_and_version_required(self):
        data, *_ = self.tags()
        data[-1] ^= 1
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            actor.verify_bytes(data)
        data, *_ = self.tags()
        struct.pack_into("<i", data, 16, 1017)
        with self.assertRaisesRegex(ValueError, "version"):
            actor.parse_structure(data)

    def test_name_table_and_import_bounds_required(self):
        data, *_ = self.tags()
        data[609] ^= 1
        with self.assertRaisesRegex(ValueError, "name table"):
            actor.parse_structure(data)
        data, *_ = self.tags()
        # The last two summary integers are import count and import offset.
        reader = actor.initialize(data)
        _, pos = reader.string(344, 605)
        struct.pack_into("<i", data, pos + 20, 1891)
        with self.assertRaisesRegex(ValueError, "import table"):
            actor.parse_structure(data)

    def test_wrong_mesh_or_material_import_rejected(self):
        data, _, mesh, _, _ = self.tags()
        struct.pack_into("<i", data, mesh["value"], -7)
        with self.assertRaisesRegex(ValueError, "mesh import"):
            actor.parse_structure(data)
        data, _, _, _, override = self.tags()
        struct.pack_into("<i", data, override["value"] + 4, -6)
        with self.assertRaisesRegex(ValueError, "override materials"):
            actor.parse_structure(data)

    def test_wrong_override_count_and_duplicate_property_rejected(self):
        data, _, _, _, override = self.tags()
        struct.pack_into("<i", data, override["value"], 4)
        with self.assertRaisesRegex(ValueError, "count"):
            actor.parse_structure(data)
        data, _, mesh, collision, _ = self.tags()
        data[collision["start"]:collision["start"]+8] = data[mesh["start"]:mesh["start"]+8]
        with self.assertRaises(ValueError):
            actor.parse_structure(data)

    def test_vector_type_value_and_component_terminator_required(self):
        data, reader, _, _, override = self.tags()
        vector = override["end"]
        data[vector + 52] ^= 1  # first IEEE-754 double, after native-vector tag
        with self.assertRaisesRegex(ValueError, "location differs"):
            actor.parse_structure(data)
        data, reader, _, _, override = self.tags()
        data[override["end"] + 48] = 0  # native serialization flag
        with self.assertRaisesRegex(ValueError, "flags"):
            actor.parse_structure(data)
        data, reader, _, _, override = self.tags()
        _, end = actor.native_relative_location(reader, override["end"], len(data))
        struct.pack_into("<ii", data, end, reader.names.index("StaticMesh"), 0)
        with self.assertRaises(ValueError):
            actor.parse_structure(data)


if __name__ == "__main__":
    unittest.main()
