"""Check exported closure and reject invalid geometry in the blocked opening-corner prototype."""

from contextlib import redirect_stderr
from importlib.util import find_spec
import io
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import build_spawn_corner_prototype as builder
from build_spawn_corner_prototype import (
    ART_ROOT, DEFAULT_REVIEW, MATERIALS, NAME, PROJECT, REVIEW_ROOT, SOURCE,
    Mesh, audit, build_shell, front_gables,
)
from extract_building_shells import signed_area
from subtract_building_shells import digest, read_json


@unittest.skipUnless((PROJECT / SOURCE).is_file(), "Requires the pinned local Gray London source export.")
class SpawnCornerPrototypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mesh, cls.report = build_shell()
        source = read_json(DEFAULT_REVIEW)["shell_geometry"]
        cls.plant = tuple(map(tuple, source["footprint_m"]))
        cls.party = cls.report["party_edges"]
        cls.floor, cls.roof_z = source["foundation_m"], source["source_roof_m"]
        cls.roof = [points for group, material, points in cls.mesh.faces if (group, material) == ("Structure", "ClayDeck")]

    def validate(self, mesh):
        return audit(mesh, self.plant, self.roof, self.party, self.floor, self.roof_z)

    def test_export_keeps_closed_faces_and_usable_projected_uvs(self):
        self.assertEqual((self.roof_z, self.party, len(self.roof)), (15., [0, 4, 6], 6))
        self.check_export(REVIEW_ROOT / "Source", self.mesh)

    def test_gable_export_keeps_party_seals_and_original_support_ceiling(self):
        mesh, report = build_shell(True)
        self.assertEqual(report["party_edges"], self.party)
        _, _, roof = front_gables(self.roof, self.plant, self.roof_z)
        z_values = [z for triangle in roof for _, _, z in triangle]
        self.assertEqual((min(z_values), max(z_values)), (13.1, 15.0))
        self.check_export(REVIEW_ROOT / "VisualStudy", mesh, roof)

    def check_export(self, output, original, render_roof=None):
        report = read_json(output / "spawn_corner_prototype_audit.json")
        model_file = output / f"{NAME}.obj"
        x, y, z = report["world_pivot_m"]
        fx, fy = report["forward_xy"]
        vertices, uvs, exported = [], [], Mesh()
        group = material = None
        for line in model_file.read_text(encoding="utf-8").splitlines():
            label, *values = line.split()
            if label == "v":
                u, v, w = map(float, values)
                vertices.append((x + u * fx - v * fy, y + u * fy + v * fx, z + w))
            elif label == "vt":
                uvs.append(tuple(map(float, values)))
            elif label == "g":
                group = values[0]
            elif label == "usemtl":
                material = values[0]
            elif label == "f":
                vertex_indices, uv_indices = zip(*(map(int, item.split("/")) for item in values))
                exported.face(group, material, *(vertices[index - 1] for index in vertex_indices))
                self.assertGreater(abs(signed_area([uvs[index - 1] for index in uv_indices])), 1e-10)
        self.assertEqual(report["status"], "blocked_review_only")
        measured = audit(exported, self.plant, self.roof, self.party, self.floor, self.roof_z, render_roof)
        self.assertEqual(measured, {key: report[key] for key in (
            "render_triangles", "closed_components", "structural_triangles",
        )})
        self.assertEqual(exported.faces, original.faces)
        for filename, expected in report["source_files_sha256"].items():
            self.assertEqual(digest((output / filename).read_bytes()), expected)

    def test_material_maps_resolve_to_the_existing_texture_directory(self):
        library = REVIEW_ROOT / "Source" / f"{NAME}.mtl"
        maps = [line[7:] for line in library.read_text(encoding="utf-8").splitlines() if line.startswith("map_Kd ")]
        expected = {image for _, image in MATERIALS.values() if image}
        self.assertEqual(len(maps), len(expected))
        for relative_path in maps:
            self.assertTrue(relative_path.startswith("../../../Textures/"))
            texture = (library.parent / relative_path).resolve(strict=True)
            self.assertEqual(texture.parent, (ART_ROOT / "Textures").resolve())
            expected.remove(texture.name)
        self.assertFalse(expected)

    def test_audit_rejects_an_open_detail_mesh(self):
        opened = Mesh()
        opened.faces = self.mesh.faces[:-1]
        with self.assertRaisesRegex(ValueError, "not a closed, consistently wound mesh"):
            self.validate(opened)

    def test_audit_rejects_geometry_above_original_roof(self):
        enlarged = Mesh()
        enlarged.faces = self.mesh.faces.copy()
        a, b, c = self.roof[0]
        enlarged.face("Duct", "ClayDeck", a, b, (*c[:2], self.roof_z + .1))
        with self.assertRaisesRegex(ValueError, "Vertex leaves the source envelope"):
            self.validate(enlarged)

    def test_audit_rejects_faces_crossing_a_concavity(self):
        # Three corners inside an L-shaped tile are insufficient to enclose a triangle.
        polygon = ((0., 0.), (2., 0.), (2., 1.), (1., 1.), (1., 2.), (0., 2.))
        src_roof = [tuple((*polygon[i], 2.) for i in indices) for indices in (
            (0, 1, 3), (1, 2, 3), (0, 3, 5), (3, 4, 5),
        )]
        invalid = Mesh()
        invalid.face("Cutout", "ClayDeck", (2., .5, 1.), (.5, 2., 1.), (.5, .5, 1.))
        with self.assertRaisesRegex(ValueError, "Projected face crosses the source perimeter"):
            audit(invalid, polygon, src_roof, set(), 0., 2.)


class SpawnCornerReproductionTests(unittest.TestCase):
    def assert_existing_output_rejected(self, module, root, arguments, message):
        diagnostics = io.StringIO()
        with patch.object(module, "REPRODUCTION_ROOT", root), patch.object(module, "build_shell") as build:
            with patch.object(sys, "argv", [module.__name__, *arguments]), redirect_stderr(diagnostics):
                with self.assertRaises(SystemExit) as error:
                    module.main()
            build.assert_not_called()
        self.assertEqual(error.exception.code, 2)
        self.assertIn(message, diagnostics.getvalue())

    def test_model_defaults_and_explicit_paths_require_new_directories(self):
        self.assertIn(PROJECT / "Saved", builder.REPRODUCTION_ROOT.parents)
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for target, arguments in (
                (root / "StructuralModel", []),
                (root / "GabledModel", ["--visual-study"]),
                (root / "Review copy", ["--output", str(root / "Review copy")]),
            ):
                with self.subTest(target=target):
                    target.mkdir()
                    sentinel = target / f"{NAME}.obj"
                    sentinel.write_bytes(b"existing OBJ")
                    self.assert_existing_output_rejected(builder, root, arguments, "Output directory must be new")
                    self.assertEqual(sentinel.read_bytes(), b"existing OBJ")
                    self.assertEqual(list(target.iterdir()), [sentinel])

    @unittest.skipUnless(find_spec("PIL"), "The preview command requires Pillow.")
    def test_preview_defaults_and_explicit_paths_require_new_files(self):
        import render_spawn_corner_prototype as renderer

        self.assertIn(PROJECT / "Saved", renderer.REPRODUCTION_ROOT.parents)
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for target, arguments in (
                (root / "StructuralPreview.png", []),
                (root / "GabledPreview.png", ["--visual-study"]),
                (root / "Review copy.png", ["--output", str(root / "Review copy.png")]),
            ):
                with self.subTest(target=target):
                    target.write_bytes(b"existing PNG")
                    self.assert_existing_output_rejected(renderer, root, arguments, "Preview file must be new")
                    self.assertEqual(target.read_bytes(), b"existing PNG")


if __name__ == "__main__":
    unittest.main()
