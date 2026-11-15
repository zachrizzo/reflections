"""Small synthetic checks for the unapproved North Market review converter."""

from collections import Counter
import base64
import hashlib
import io
import json
from pathlib import Path
import secrets
import struct
import unittest
from unittest import mock

import build_north_market_review_glbs as convert


class NorthMarketReviewTests(unittest.TestCase):
    def test_concave_polygons_keep_winding_and_area_in_either_direction(self):
        points = [(0., 0., 0.), (4., 0., 0.), (4., 3., 0.), (2., 1., 0.), (0., 3., 0.)]
        for ring in (points, list(reversed(points))):
            triangles, nonplanar, _ = convert.triangulate(ring)
            self.assertEqual(len(triangles), 3)
            self.assertEqual(nonplanar, 0.0)
            area = sum(a[0]*b[1] - a[1]*b[0] for a, b in zip(ring, ring[1:] + ring[:1]))
            parts = [convert.cross2(*(ring[i][:2] for i in tri)) for tri in triangles]
            self.assertAlmostEqual(sum(parts), area)
            self.assertTrue(all(part * area > 0 for part in parts))

    def test_degenerate_self_intersecting_and_nonplanar_rings_are_rejected(self):
        bad = [
            [(0., 0., 0.), (1., 0., 0.), (1., 0., 0.), (0., 1., 0.)],
            [(0., 0., 0.), (2., 2., 0.), (0., 2., 0.), (2., 0., 0.)],
            [(0., 0., 0.), (4., 0., 0.), (1., 3., 0.), (1., -1., 0.), (4., 3., 0.)],
            [(0., 0., 0.), (1., 0., 0.), (1., 1., 0.001), (0., 1., 0.)],
        ]
        for points in bad:
            with self.subTest(points=points), self.assertRaises(ValueError):
                convert.triangulate(points)

    def test_micrometre_rounding_is_accepted_but_visible_warp_is_not(self):
        near_planar = [(0., 0., 0.), (2., 0., 0.), (2., 2., 0.000011), (0., 2., 0.)]
        triangles, deviation, _ = convert.triangulate(near_planar)
        self.assertEqual(len(triangles), 2)
        self.assertGreater(deviation, 0.000005)
        self.assertLess(deviation, 0.000006)
        self.assertLess(deviation, convert.MAX_NONPLANAR_M)
        materially_warped = [(0., 0., 0.), (2., 0., 0.), (2., 2., 0.0002), (0., 2., 0.)]
        with self.assertRaisesRegex(ValueError, "Non-planar polygon"):
            convert.triangulate(materially_warped)

    def test_reserved_train_fails_closed(self):
        def queue(line):
            return mock.patch.object(Path, "open", return_value=io.StringIO(line))
        with queue("!!! 05:04 TRAIN #22 LOADED: npc-unify final proof round; restarts next. !!!\n"):
            with self.assertRaisesRegex(RuntimeError, "reserves"):
                convert.leading_train()
        with queue("!!! 05:04 TRAIN #22 BUILDING: editor closed. !!!\n"):
            with self.assertRaisesRegex(RuntimeError, "not LOADED"):
                convert.leading_train()
        with queue("!!! 05:04 TRAIN #22 LOADED: queue clear. !!!\n"):
            self.assertEqual(convert.leading_train(), "22")

    def test_session_stops_when_a_lease_or_memory_pressure_appears(self):
        gib = 1024**3
        with mock.patch.object(convert, "window_open"), mock.patch.object(convert, "leading_train", return_value="22"), \
                mock.patch.object(convert, "memory_headroom", return_value=(12*gib, 20*gib)), \
                mock.patch("os.path.lexists", return_value=False) as exists:
            guard = convert.SessionGuard()
            exists.return_value = True
            with self.assertRaisesRegex(RuntimeError, "lease appeared"):
                guard.check()
        with mock.patch.object(convert, "window_open"), mock.patch.object(convert, "leading_train", return_value="22"), \
                mock.patch.object(convert, "memory_headroom", side_effect=[(12*gib, 20*gib), (12*gib, 20*gib), (10*gib, 20*gib)]), \
                mock.patch("os.path.lexists", return_value=False):
            guard = convert.SessionGuard()
            with self.assertRaisesRegex(RuntimeError, "memory fell"):
                guard.check(force=True)

    def remove_own_file(self, path):
        if path.exists():
            root = (convert.PROJECT / "Saved/CityPCG/MedievalSurvey").resolve(strict=True)
            if path.is_symlink() or path.resolve(strict=True).parent != root:
                raise RuntimeError("Refusing to remove a test file outside its intended directory")
            path.unlink()

    def test_fresh_output_path_rejects_existing_or_redirected_targets(self):
        parent = (convert.PROJECT / "Saved/CityPCG/MedievalSurvey").resolve(strict=True)
        output = parent / ("codex_review_folder_test_" + secrets.token_hex(8))
        output.mkdir()
        target = output / "test.glb"
        try:
            self.assertEqual(convert.fresh_output_file(output, parent, "test.glb"), target)
            with target.open("xb") as stream:
                stream.write(b"existing")
            with self.assertRaisesRegex(ValueError, "already exists"):
                convert.fresh_output_file(output, parent, "test.glb")
            with self.assertRaisesRegex(ValueError, "filename"):
                convert.fresh_output_file(output, parent, "../escape.glb")
            fake = mock.Mock()
            fake.parent = parent
            fake.is_symlink.return_value = False
            fake.is_junction.return_value = False
            fake.resolve.return_value = parent / "different_folder"
            with self.assertRaisesRegex(ValueError, "folder was redirected"):
                convert.fresh_output_file(fake, parent, "test.glb")
        finally:
            if target.exists():
                if target.is_symlink() or target.resolve(strict=True).parent != output.resolve(strict=True):
                    raise RuntimeError("Refusing to remove a redirected test file")
                target.unlink()
            if output.is_symlink() or output.resolve(strict=True).parent != parent:
                raise RuntimeError("Refusing to remove a redirected test directory")
            output.rmdir()

    def test_obj_to_glb_preserves_corner_data_and_detects_corruption(self):
        saved = (convert.PROJECT / "Saved/CityPCG/MedievalSurvey").resolve(strict=True)
        prefix = "codex_north_market_conversion_test_" + secrets.token_hex(8)
        obj, glb = saved / (prefix + ".obj"), saved / (prefix + ".glb")
        source = ("mtllib NorthMarketDetail.mtl\n"
                  "v 0 0 0\nv 4 0 0\nv 4 3 0\nv 2 1 0\nv 0 3 0\nv 5 0 0\nv 6 0 0\nv 5 1 0\n"
                  "vt 0 0\nvt 4 0\nvt 4 3\nvt 2 1\nvt 0 3\nvt 5 0\nvt 6 0\nvt 5 1\n"
                  "vn 0 0 1\nusemtl M_GLMedieval_Oak\nf 1/1/1 2/2/1 3/3/1 4/4/1 5/5/1\n"
                  "usemtl M_GLMedieval_Fieldstone\nf 6/6/1 7/7/1 8/8/1\n")
        try:
            with obj.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(source)
            record = {"source_artifact": {"sha256": hashlib.sha256(obj.read_bytes()).hexdigest(),
                                            "readback": {"uv_corners": 8}},
                      "vertices": 8, "polygons": 2, "material_polygons": {"Oak": 1, "Fieldstone": 1}}
            palette = {"M_GLMedieval_Oak": {"color": [0.2, 0.1, 0.05]},
                       "M_GLMedieval_Fieldstone": {"color": [0.3, 0.3, 0.3]}}
            png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z0kwAAAAASUVORK5CYII=")
            palette["M_GLMedieval_Oak"].update({"texture": "Textures/test.png", "data": png,
                                                 "sha256": hashlib.sha256(png).hexdigest()})
            groups, info = convert.convert_obj(obj, record, palette, lambda: None)
            self.assertEqual(info["triangles"], 4)
            self.assertEqual(groups["M_GLMedieval_Oak"]["count"], 9)
            for group in groups.values():
                positions = list(struct.iter_unpack("<fff", group["POSITION"]))
                normals = list(struct.iter_unpack("<fff", group["NORMAL"]))
                uvs = list(struct.iter_unpack("<ff", group["TEXCOORD_0"]))
                for (x, y, z), normal, (u, v) in zip(positions, normals, uvs):
                    self.assertEqual(y, 0.)
                    self.assertEqual(normal, (0., 1., -0.))
                    self.assertEqual((u, v), (x, 1. + z))
            blob = convert.glb_bytes(groups, palette)
            with glb.open("xb") as stream:
                stream.write(blob)
            self.assertEqual(convert.verify_glb(glb, groups, palette, lambda: None), hashlib.sha256(blob).hexdigest())
            json_len = struct.unpack_from("<I", blob, 12)[0]
            doc = json.loads(blob[20:20+json_len])
            self.assertEqual(doc["nodes"], [{"mesh": 0}])
            self.assertEqual(Counter(item["name"] for item in doc["materials"]), Counter(palette.keys()))
            self.assertEqual(doc["images"][0]["name"], "test.png")
            material_pbr = {item["name"]: item["pbrMetallicRoughness"] for item in doc["materials"]}
            self.assertEqual(material_pbr["M_GLMedieval_Oak"]["baseColorFactor"], [1., 1., 1., 1.])
            self.assertIn("baseColorTexture", material_pbr["M_GLMedieval_Oak"])
            self.assertEqual(material_pbr["M_GLMedieval_Fieldstone"]["baseColorFactor"], [0.3, 0.3, 0.3, 1.])
            self.assertNotIn("baseColorTexture", material_pbr["M_GLMedieval_Fieldstone"])
            palette["M_GLMedieval_Oak"]["color"] = [0.01, 0.02, 0.03]
            self.assertEqual(convert.verify_glb(glb, groups, palette, lambda: None), hashlib.sha256(blob).hexdigest())
            palette["M_GLMedieval_Fieldstone"]["color"] = [0.2, 0.2, 0.2]
            with self.assertRaisesRegex(ValueError, "Material color readback"):
                convert.verify_glb(glb, groups, palette, lambda: None)
            palette["M_GLMedieval_Fieldstone"]["color"] = [0.3, 0.3, 0.3]
            first_view = doc["bufferViews"][doc["accessors"][doc["meshes"][0]["primitives"][0]["attributes"]["POSITION"]]["bufferView"]]
            with glb.open("r+b") as stream:
                stream.seek(28 + json_len + first_view["byteOffset"])
                byte = stream.read(1)
                stream.seek(-1, 1)
                stream.write(bytes([byte[0] ^ 1]))
            with self.assertRaisesRegex(ValueError, "attribute readback"):
                convert.verify_glb(glb, groups, palette, lambda: None)
        finally:
            self.remove_own_file(obj)
            self.remove_own_file(glb)


if __name__ == "__main__":
    unittest.main()
