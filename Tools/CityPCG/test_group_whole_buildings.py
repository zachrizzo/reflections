"""CPU-only checks for grouped whole-building geometry and rollback manifests."""

from dataclasses import replace
import json
import math
from pathlib import Path
from shutil import copytree
import struct
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from extract_tile_frontages import accessor, read_glb
from group_whole_buildings import build, collect, gltf_point, group_cells, resolve_project_file
from read_prepared_building_fbx import BuildingMesh, material_definitions
from subtract_building_shells import digest, indices, write_glb
from verify_grouped_whole_buildings import verify


TILE = "Tile_p03_p00"
MATERIAL = "M_GLMedieval_Oak"
SHA = "a" * 64


class GroupedBuildingsTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(TemporaryDirectory()))
        self.kit = self.directory / "kit.json"
        (self.directory / "Source").mkdir()
        (self.directory / "UnrealSource").mkdir()
        self.specs = {}
        self.shells = []
        for identifier, x in (("first", 3001.), ("second", 3002.)):
            fbx = f"{identifier}.fbx"
            data = identifier.encode()
            for folder in ("Source", "UnrealSource"):
                (self.directory / folder / fbx).write_bytes(data)
            self.specs[identifier] = {
                "fbx": f"Source/{fbx}", "world_pivot_m": [x, 2., .2], "yaw_deg": 90.,
                "axis_x_world_xy": [0., 1.], "axis_y_world_xy": [-1., 0.],
                "footprint_local_m": [[0., 0.], [1., 0.], [0., 1.]],
                "bounds_cm": [[0., 0., 0.], [100., 100., 0.]],
                "materials": [MATERIAL], "triangles": 1,
                "unreal_bridge": {"fbx": f"UnrealSource/{fbx}", "canonical_sha256": digest(data),
                                  "prepared_sha256": digest(data), "geometry_sha256": SHA, "pivot_m": [0, 0, 0],
                                  "reflected_axis": "Y", "uv_layers": ["UV0"], "materials": [MATERIAL],
                                  "triangles": 1, "matched_footprint_vertices": 3},
            }
            self.shells.append({"id": identifier, "origin_m": [x, 2., .2], "entry": {"outward": [0., 1.]},
                                "footprint": [[x, 2.], [x, 3.], [x - 1., 2.]],
                                "source_roof_faces": [3 if identifier == "first" else 4]})
        self.rollout = {
            "status": "offline_only",
            "cumulative_masks": {TILE: {"source_tile": TILE, "source_tile_asset": f"/Game/Tiles/{TILE}.{TILE}",
                                        "source_origin_m": [3000., 0., 0.], "source_export_sha256": SHA,
                                        "buildings": self.shells}},
            "tile_inventory": {TILE: {"status": "inventoried", "offline_mask_buildings": 2, "source_sha256": SHA,
                                      "offline_mask_face_counts": {"GL_Roof": 2}}},
        }
        self.write_kit()
        self.mesh = BuildingMesh([(0., 0., 0.), (1., 0., 0.), (0., -1., 0.)],
                                 [0, 2, 1], [(0., 0., 1.)] * 3, [(0.2, .75), (0., 1.), (1., 0.)],
                                 [MATERIAL], [0])

    def write_kit(self):
        self.kit.write_text(json.dumps({"source_tile": TILE, "buildings": self.specs}), encoding="utf-8")

    def test_requires_every_cumulative_mask_member_once(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            collect(self.rollout, [self.kit, self.kit])
        self.specs.pop("second")
        self.write_kit()
        with self.assertRaisesRegex(ValueError, "Missing meshes.*second"):
            collect(self.rollout, [self.kit])

    def test_positions_are_signed_and_source_fbx_is_pinned(self):
        self.specs["first"]["footprint_local_m"][2][1] = -1.
        self.write_kit()
        with self.assertRaisesRegex(ValueError, "signed local footprint"):
            collect(self.rollout, [self.kit])
        self.specs["first"]["footprint_local_m"][2][1] = 1.
        self.write_kit()
        (self.directory / "UnrealSource/first.fbx").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            collect(self.rollout, [self.kit])

    def test_grouping_is_stable_bounded_and_respects_source_tiles(self):
        buildings = collect(self.rollout, [self.kit])
        masks = self.rollout["cumulative_masks"]
        cell, anchor, members = list(group_cells(buildings, masks, 64., 2))[0]
        self.assertEqual(cell, (TILE, 0, 0))
        self.assertEqual(anchor, (3000., 0., 0.))
        self.assertEqual([row.id for row in members], ["first", "second"])
        self.assertEqual(len(list(group_cells(buildings, masks, 1., 1))), 2)
        neighbor = "Tile_p03_p01"
        split = dict(buildings, second=replace(buildings["second"], tile=neighbor))
        self.assertEqual(len(list(group_cells(split, {**masks, neighbor: masks[TILE]}, 64., 2))), 2)
        with self.assertRaisesRegex(ValueError, "triangle budget"):
            list(group_cells(buildings, masks, 64., 1))

    def test_output_geometry_preserves_transforms_winding_uv_and_provenance(self):
        output = self.directory / "result"
        buildings = collect(self.rollout, [self.kit])
        with patch("group_whole_buildings.read_mesh", return_value=self.mesh), patch(
                "group_whole_buildings.material_definitions", return_value={MATERIAL: SHA}):
            manifest = build(self.rollout, buildings, None, output, project_root=self.directory)
        key, cell = next(iter(manifest["cells"].items()))
        self.assertEqual(manifest["tile_barriers"][TILE]["required_cells"], [key])
        self.assertEqual(manifest["tile_barriers"][TILE]["required_building_ids"], ["first", "second"])
        self.assertEqual(cell["sections"][0]["triangles"], 2)
        self.assertEqual(cell["buildings"][1]["survey"], self.shells[1])
        self.assertEqual(cell["buildings"][1]["face_ranges_by_material"][MATERIAL],
                         {"first_triangle": 1, "triangles": 1})
        glb = output / cell["file"]
        self.assertEqual(digest(glb.read_bytes()), cell["sha256"])
        doc, blob = read_glb(glb)
        primitive = doc["meshes"][0]["primitives"][0]
        self.assertEqual(indices(doc, blob, 0), (0, 1, 2, 3, 4, 5))
        attrs = primitive["attributes"]
        xyz = accessor(doc, blob, attrs["POSITION"], {("VEC3", 5126)})
        normal = accessor(doc, blob, attrs["NORMAL"], {("VEC3", 5126)})
        self.assertTrue(all(math.dist(a, b) < 1e-6
                            for a, b in zip(xyz[:3], [(1., .2, 2.), (0., .2, 2.), (1., .2, 3.)])))
        self.assertEqual(normal[:3], [(0., 1., 0.)] * 3)
        # An upward normal agrees with the emitted winding.
        self.assertGreater((xyz[2][0] - xyz[0][0]) * (xyz[1][2] - xyz[0][2])
                           - (xyz[1][0] - xyz[0][0]) * (xyz[2][2] - xyz[0][2]), 0)
        uv = doc["accessors"][attrs["TEXCOORD_0"]]
        start = doc["bufferViews"][uv["bufferView"]]["byteOffset"]
        self.assertAlmostEqual(struct.unpack_from("<2f", blob, start)[0], .2)
        self.assertEqual(struct.unpack_from("<2f", blob, start)[1], .25)
        self.assertTrue(math.dist(gltf_point((1., 0., 0.), (0., 0., 0.), 90., (0., 0., 0.)), (0., 0., 1.)) < 1e-9)

    def test_independent_readback_detects_winding_change_even_with_updated_hash(self):
        output = self.directory / "readback"
        buildings = collect(self.rollout, [self.kit])
        with patch("group_whole_buildings.read_mesh", return_value=self.mesh), patch(
                "group_whole_buildings.material_definitions", return_value={MATERIAL: SHA}):
            manifest = build(self.rollout, buildings, None, output, project_root=self.directory)
        key, cell = next(iter(manifest["cells"].items()))
        with patch("verify_grouped_whole_buildings.read_mesh", return_value=self.mesh):
            self.assertEqual(verify(output, self.rollout, None, project_root=self.directory)["checked_corners"], 6)
            path = output / f"{key}.glb"
            doc, binary = read_glb(path)
            slab = bytearray(binary)
            accessor_id = doc["meshes"][0]["primitives"][0]["indices"]
            view_id = doc["accessors"][accessor_id]["bufferView"]
            offset = doc["bufferViews"][view_id]["byteOffset"]
            a, b = struct.unpack_from("<II", slab, offset)
            struct.pack_into("<II", slab, offset, b, a)
            path.unlink()
            write_glb(path, doc, slab)
            cell["sha256"] = digest(path.read_bytes())
            (output / "grouped_buildings.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "triangle 0, corner 0"):
                verify(output, self.rollout, None, project_root=self.directory)

    def test_conflicting_material_aborts_without_publishing_a_tile(self):
        output = self.directory / "conflict"
        buildings = collect(self.rollout, [self.kit])
        different = [{MATERIAL: SHA}, {MATERIAL: "b" * 64}]
        with patch("group_whole_buildings.read_mesh", return_value=self.mesh), patch(
                "group_whole_buildings.material_definitions", side_effect=different):
            with self.assertRaisesRegex(ValueError, "incompatible authored texture or material"):
                build(self.rollout, buildings, None, output, project_root=self.directory)
        self.assertFalse(output.exists())

    def test_portable_bundle_reads_only_from_the_relocated_checkout(self):
        buildings = collect(self.rollout, [self.kit])
        output = self.directory / "portable"
        with patch("group_whole_buildings.read_mesh", return_value=self.mesh), patch(
                "group_whole_buildings.material_definitions", return_value={MATERIAL: SHA}):
            manifest = build(self.rollout, buildings, None, output, project_root=self.directory)
        record = next(iter(manifest["cells"].values()))["buildings"][0]
        self.assertEqual(record["kit"], "kit.json")
        self.assertEqual(record["canonical_fbx"], "Source/first.fbx")
        self.assertEqual(record["prepared_fbx"], "UnrealSource/first.fbx")
        copy_root = Path(self.enterContext(TemporaryDirectory())) / "relocated checkout"
        copytree(self.directory, copy_root)
        with patch("verify_grouped_whole_buildings.read_mesh", return_value=self.mesh) as decoder:
            report = verify(copy_root / "portable", self.rollout, None, project_root=copy_root)
        self.assertEqual(report["checked_corners"], 6)
        self.assertEqual({call.args[0].parent for call in decoder.call_args_list}, {copy_root / "UnrealSource"})

    def test_manifest_path_traversal_is_refused(self):
        for reference in ("/tmp/kit.json", "C:/kits/kit.json", "D:kit.json", "\\\\server\\kit.json",
                          "../kit.json", "Source/../kit.json", "Source//kit.json", "Source/./kit.json",
                          "Source/.. /kit.json", "Source/NUL.json"):
            with self.subTest(reference=reference):
                with self.assertRaisesRegex(ValueError, "Unsafe project-relative path"):
                    resolve_project_file(self.directory, reference, ".json")
        outer = Path(self.enterContext(TemporaryDirectory()))
        target = outer / "kit.json"
        target.write_text("{}", encoding="utf-8")
        link = self.directory / "linked.json"
        try:
            link.symlink_to(target)
        except OSError:
            return  # Some Windows test accounts cannot create symbolic links.
        with self.assertRaisesRegex(ValueError, "escapes the checkout"):
            resolve_project_file(self.directory, link.name, ".json")


def node(identifier, props=(), children=()):
    return SimpleNamespace(id=identifier, props=list(props), elems=list(children))


class MaterialFingerprintTests(unittest.TestCase):
    def fingerprint(self, image, diffuse=0.1, ambient=0.2, ambient_factor=0.):
        properties = node(b"Properties70", children=[
            node(b"P", (name, b"Value", b"", b"A", value)) for name, value in
            ((b"DiffuseColor", diffuse), (b"AmbientColor", ambient), (b"AmbientFactor", ambient_factor))])
        material = node(b"Material", (1, MATERIAL.encode(), b""), [properties])
        texture = node(b"Texture", (2, b"Texture", b""))
        video = node(b"Video", (3, b"Image", b""), [node(b"Content", (image,))])
        objects = node(b"Objects", children=[material, texture, video])
        connections = node(b"Connections", children=[node(b"C", (b"OP", 2, 1, b"DiffuseColor")),
                                                     node(b"C", (b"OO", 3, 2))])
        return material_definitions(Path("fixture.fbx"), lambda _path: (node(b"", children=[objects, connections]), 7400))

    def test_embedded_bytes_and_active_shader_properties_affect_the_material_key(self):
        key = self.fingerprint(b"image")
        self.assertNotEqual(key, self.fingerprint(b"changed"))
        self.assertNotEqual(key, self.fingerprint(b"image", diffuse=.7))
        self.assertEqual(key, self.fingerprint(b"image", ambient=.7))
        self.assertNotEqual(self.fingerprint(b"image", ambient_factor=.5),
                            self.fingerprint(b"image", ambient=.7, ambient_factor=.5))


if __name__ == "__main__":
    unittest.main()
