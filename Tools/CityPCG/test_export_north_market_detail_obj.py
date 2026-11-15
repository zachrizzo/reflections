"""Test detailed OBJ preservation and independent corruption detection."""

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from tempfile import gettempdir, mkdtemp
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import export_north_market_detail_obj as exporter
import verify_north_market_detail_obj as verifier


PROMOTED = (exporter.ROOT / "ArtDirection/CityPCG/MedievalOpening/WholeBuildings/NorthMarketDetailedObj")


@contextmanager
def checked_tempdir():
    """Refuse recursive cleanup if this unique temp path or parent redirects."""
    parent = Path(gettempdir()).resolve(strict=True)
    target = Path(mkdtemp(prefix="codex-north-market-test-", dir=str(parent)))
    resolved = target.resolve(strict=True)
    if target.is_symlink() or not target.is_absolute() or resolved != target or resolved.parent != parent:
        raise RuntimeError("Unexpected temporary directory; refusing cleanup.")

    def clear_readonly(function, path, error):
        if not isinstance(error[1], PermissionError):
            raise error[1]
        current = target.resolve(strict=True)
        item = Path(path)
        actual = item.resolve(strict=True)
        if (target.is_symlink() or current != resolved or current.parent != parent or item.is_symlink() or
                not actual.is_relative_to(resolved)):
            raise RuntimeError("Temporary directory changed; refusing permission change.")
        os.chmod(item, stat.S_IREAD | stat.S_IWRITE)
        function(path)

    try:
        yield resolved
    finally:
        current = target.resolve(strict=True)
        if target.is_symlink() or current != resolved or current.parent != parent:
            raise RuntimeError("Temporary directory changed; refusing recursive cleanup.")
        shutil.rmtree(current, onerror=clear_readonly)


class DetailedObjTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(self.enterContext(checked_tempdir()))
        self.palette = {"WarmPlaster": ((.46, .35, .23), .96, 1.8),
                        "Interior": ((.016, .012, .009), .96, None)}
        # A concave n-gon must stay intact and retain its source winding.
        self.bay = SimpleNamespace(vertices=[(0., 0., 0.), (4., 0., 0.), (4., 4., 0.),
                                             (2., 2., 0.), (0., 4., 0.)],
                                   polygons=[(0, 1, 2, 3, 4)], roles=["WarmPlaster"])

    def obj(self, path):
        exporter.write_obj(path, self.bay, self.palette)
        return path.read_text(encoding="utf-8")

    def test_concave_polygon_uv_and_material_are_preserved(self):
        path = self.temp / "detail.obj"
        text = self.obj(path)
        facts = verifier.audit_obj(path, self.bay, self.palette)
        self.assertEqual((facts["vertices"], facts["polygons"], facts["uv_corners"]), (5, 1, 5))
        self.assertEqual(sum(line.startswith("f ") for line in text.splitlines()), 1)
        self.assertEqual(len(next(line for line in text.splitlines() if line.startswith("f ")).split()) - 1, 5)

    def test_independent_readback_rejects_vertex_uv_winding_and_material_changes(self):
        for kind in ("vertex", "uv", "winding", "material"):
            with self.subTest(kind=kind):
                path = self.temp / f"{kind}.obj"
                text = self.obj(path)
                if kind == "vertex":
                    text = text.replace("v 0.0 0.0 0.0", "v 1.0 0.0 0.0", 1)
                elif kind == "uv":
                    text = text.replace("vt 0.0 0.0", "vt 0.25 0.0", 1)
                elif kind == "winding":
                    text = text.replace("f 1/1/1 2/2/1", "f 2/1/1 1/2/1", 1)
                else:
                    text = text.replace("usemtl M_GLMedieval_WarmPlaster", "usemtl M_GLMedieval_Interior", 1)
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    verifier.audit_obj(path, self.bay, self.palette)

    def test_material_readback_rejects_changed_texture_bytes(self):
        source = self.temp / "input" / "T_GLMedieval_WarmPlaster.png"
        source.parent.mkdir()
        source.write_bytes(b"mock texture bytes")
        textures = {"WarmPlaster": {"path": source.relative_to(self.temp).as_posix(),
                                    "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}}
        output = self.temp / "output"
        output.mkdir()
        roles = {"WarmPlaster", "Interior"}
        with patch.object(exporter, "ROOT", self.temp):
            material = exporter.write_materials(output, self.palette, roles, textures)
        manifest = {"material_file": material.name, "material_sha256": hashlib.sha256(material.read_bytes()).hexdigest(),
                    "textures": textures}
        verifier.audit_materials(output, manifest, roles, self.palette)
        (output / "Textures" / source.name).write_bytes(b"changed texture bytes")
        with self.assertRaisesRegex(ValueError, "texture bytes"):
            verifier.audit_materials(output, manifest, roles, self.palette)

    def test_source_text_provenance_accepts_line_endings_only(self):
        path = self.temp / "source.json"
        lf = b'{\n  "role": "market"\n}\n'
        crlf = lf.replace(b"\n", b"\r\n")
        path.write_bytes(lf)
        self.assertTrue(verifier.matches_recorded_text(path, hashlib.sha256(crlf).hexdigest()))
        path.write_bytes(crlf)
        self.assertTrue(verifier.matches_recorded_text(path, hashlib.sha256(lf).hexdigest()))
        path.write_bytes(crlf.replace(b"market", b"workshop"))
        self.assertFalse(verifier.matches_recorded_text(path, hashlib.sha256(lf).hexdigest()))

    @unittest.skipUnless(PROMOTED.is_dir() and shutil.which("git"), "requires promoted bundle and Git")
    def test_git_checkout_preserves_obj_and_mtl_bytes_with_autocrlf(self):
        repo = self.temp / "git_checkout"
        repo.mkdir()
        names = [".gitattributes", "SM_GLMedieval_NorthMarketDetail_east_0a73564b.obj",
                 "NorthMarketDetail.mtl", "detailed_obj_manifest.json"]
        hashes = {}
        for name in names:
            source, destination = PROMOTED / name, repo / name
            shutil.copyfile(source, destination)
            hashes[name] = hashlib.sha256(destination.read_bytes()).hexdigest()
        subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "core.autocrlf", "true"], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "--", *names], check=True, capture_output=True)
        for name in names:
            path = repo / name
            self.assertEqual(path.resolve().parent, repo.resolve())
            path.unlink()
        subprocess.run(["git", "-C", str(repo), "checkout-index", "--all", "--force"], check=True)
        self.assertEqual(hashes, {name: hashlib.sha256((repo / name).read_bytes()).hexdigest() for name in names})

    @unittest.skipUnless(verifier.OUTPUT.is_dir() and verifier.preflight.TILE.is_file(),
                         "requires the local generated source-art bundle and pinned tile export in Saved")
    def test_actual_four_source_files_pass_independent_readback(self):
        result = subprocess.run([sys.executable, "-B", "Tools/CityPCG/verify_north_market_detail_obj.py"],
                                cwd=exporter.ROOT, capture_output=True, text=True, check=True)
        self.assertIn("Independently verified 4 detailed source OBJs", result.stdout)

    @unittest.skipUnless(PROMOTED.is_dir() and verifier.preflight.TILE.is_file(),
                         "requires promoted bundle and the pinned tile export in Saved")
    def test_promoted_bundle_path_passes_independent_readback(self):
        result = subprocess.run([sys.executable, "-B", "Tools/CityPCG/verify_north_market_detail_obj.py", str(PROMOTED)],
                                cwd=exporter.ROOT, capture_output=True, text=True, check=True)
        self.assertIn("Independently verified 4 detailed source OBJs", result.stdout)


if __name__ == "__main__":
    unittest.main()
