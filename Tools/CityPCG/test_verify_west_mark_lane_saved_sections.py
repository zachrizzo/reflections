"""Small, in-memory corruption tests for the two pinned saved packages."""

import struct
import unittest

import verify_west_mark_lane_saved_sections as proof


class SavedSectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (proof.PROJECT / proof.SPECS["source"]["path"]).read_bytes()
        cls.replacement = (proof.PROJECT / proof.SPECS["replacement"]["path"]).read_bytes()

    def parsed(self, name="source"):
        data = bytearray(getattr(self, name))
        spec = proof.SPECS[name]
        reader, _ = proof.initialize(data, spec)
        root = reader.tag(spec["root"], len(data))
        inner = reader.tag(root["value"], root["end"])
        materials = reader.tag(spec["materials"], len(data))
        return data, spec, reader, root, inner, materials

    def test_saved_files_and_material_references(self):
        for name in ("source", "replacement"):
            with self.subTest(name=name):
                result = proof.verify_bytes(getattr(self, name), proof.SPECS[name])
                self.assertEqual([x["material_index"] for x in result["sections"]], list(range(6)))
                self.assertTrue(all(x["collision_enabled"] for x in result["sections"]))
                self.assertEqual([x["slot"] for x in result["materials"]], list(proof.SLOTS))
                self.assertEqual([x["saved_material_path"] for x in result["materials"]],
                                 list(proof.SPECS[name]["refs"]))

    def test_asset_identity_and_length_fail_closed(self):
        data = bytearray(self.source)
        data[-1] ^= 1
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            proof.verify_bytes(data, proof.SPECS["source"])
        with self.assertRaisesRegex(ValueError, "size"):
            proof.parse_structure(data[:-1], proof.SPECS["source"])
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            proof.verify_bytes(self.source, proof.SPECS["replacement"])

    def test_unsupported_ue_version_rejected(self):
        data, spec, *_ = self.parsed()
        struct.pack_into("<i", data, 16, 1017)
        with self.assertRaisesRegex(ValueError, "version"):
            proof.parse_structure(data, spec)

    def test_name_table_terminator_and_digest_are_required(self):
        data, spec, *_ = self.parsed()
        start = spec["name_start"]
        length = struct.unpack_from("<i", data, start)[0]
        self.assertGreater(length, 0)
        data[start + 4 + length - 1] = ord("X")
        with self.assertRaisesRegex(ValueError, "terminator"):
            proof.parse_structure(data, spec)
        data, spec, *_ = self.parsed()
        data[start + 4] ^= 1
        with self.assertRaisesRegex(ValueError, "name table"):
            proof.parse_structure(data, spec)

    def test_bad_type_tree_or_size_rejected(self):
        data, spec, _, root, _, _ = self.parsed()
        struct.pack_into("<i", data, root["start"] + 16, 5)
        with self.assertRaises(ValueError):
            proof.parse_structure(data, spec)
        data, spec, _, root, _, _ = self.parsed()
        struct.pack_into("<i", data, root["value"] - 5, 0x7fffffff)
        with self.assertRaises(ValueError):
            proof.parse_structure(data, spec)

    def test_removed_key_and_duplicate_key_rejected(self):
        data, spec, _, _, inner, _ = self.parsed()
        struct.pack_into("<i", data, inner["value"], 1)
        with self.assertRaisesRegex(ValueError, "removed"):
            proof.parse_structure(data, spec)
        data, spec, reader, _, inner, _ = self.parsed()
        first = inner["value"] + 8
        _, second = reader.fields(first + 4, inner["end"])
        data[second:second+4] = data[first:first+4]
        with self.assertRaisesRegex(ValueError, "Duplicate section-map key"):
            proof.parse_structure(data, spec)

    def test_lod_and_material_index_mismatch_rejected(self):
        data, spec, reader, _, inner, _ = self.parsed()
        first = inner["value"] + 8
        struct.pack_into("<I", data, first, 0x10000)
        with self.assertRaisesRegex(ValueError, "LOD"):
            proof.parse_structure(data, spec)
        data, spec, reader, _, inner, _ = self.parsed()
        first = inner["value"] + 8
        fields, _ = reader.fields(first + 4, inner["end"])
        struct.pack_into("<i", data, fields[("MaterialIndex", 0)]["value"], 5)
        with self.assertRaisesRegex(ValueError, "mapping"):
            proof.parse_structure(data, spec)

    def test_duplicate_section_property_rejected(self):
        data, spec, reader, _, inner, _ = self.parsed()
        fields, _ = reader.fields(inner["value"] + 12, inner["end"])
        a = fields[("bEnableCollision", 0)]["start"]
        b = fields[("bCastShadow", 0)]["start"]
        data[b:b+8] = data[a:a+8]
        with self.assertRaisesRegex(ValueError, "Duplicate tagged property"):
            proof.parse_structure(data, spec)

    def test_struct_and_row_terminators_are_required(self):
        data, spec, reader, root, _, _ = self.parsed()
        struct.pack_into("<ii", data, root["end"] - 8, reader.names.index("MaterialIndex"), 0)
        with self.assertRaises(ValueError):
            proof.parse_structure(data, spec)
        data, spec, reader, _, _, materials = self.parsed()
        _, end = reader.fields(materials["value"] + 4, materials["end"])
        struct.pack_into("<ii", data, end - 8, reader.names.index("MaterialSlotName"), 0)
        with self.assertRaises(ValueError):
            proof.parse_structure(data, spec)

    def test_duplicate_material_name_and_uv_array_index_rejected(self):
        data, spec, reader, _, _, root = self.parsed()
        fields, _ = reader.fields(root["value"] + 4, root["end"])
        a = fields[("MaterialSlotName", 0)]["start"]
        b = fields[("ImportedMaterialSlotName", 0)]["start"]
        data[b:b+8] = data[a:a+8]
        with self.assertRaisesRegex(ValueError, "Duplicate tagged property"):
            proof.parse_structure(data, spec)
        data, spec, reader, _, _, root = self.parsed()
        fields, _ = reader.fields(root["value"] + 4, root["end"])
        uv = fields[("UVChannelData", 0)]
        sub, _ = reader.fields(uv["value"], uv["end"])
        struct.pack_into("<i", data, sub[("LocalUVDensities", 2)]["value"] - 4, 1)
        with self.assertRaisesRegex(ValueError, "Duplicate tagged property"):
            proof.parse_structure(data, spec)

    def test_wrong_material_reference_and_import_outer_rejected(self):
        data, spec, reader, _, _, root = self.parsed("replacement")
        fields, _ = reader.fields(root["value"] + 4, root["end"])
        struct.pack_into("<i", data, fields[("MaterialInterface", 0)]["value"], -6)
        with self.assertRaisesRegex(ValueError, "material reference"):
            proof.parse_structure(data, spec)
        data, spec, _, _, _, _ = self.parsed("replacement")
        struct.pack_into("<i", data, spec["import_start"] + 9 * 40 + 16, 0)
        with self.assertRaisesRegex(ValueError, "outer"):
            proof.parse_structure(data, spec)


if __name__ == "__main__":
    unittest.main()
