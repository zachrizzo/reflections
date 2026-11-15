"""Independent readback checks for the light North Market massing shells."""

from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import build_north_market_massing as massing


def read_obj(path):
    vertices, uvs, normals, faces, materials = [], [], [], [], set()
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0] in {"v", "vt", "vn"}:
            row = tuple(float(value) for value in fields[1:])
            if not all(math.isfinite(value) for value in row):
                raise ValueError("Nonfinite OBJ channel")
            {"v": vertices, "vt": uvs, "vn": normals}[fields[0]].append(row)
        elif fields[0] == "usemtl":
            materials.add(fields[1])
        elif fields[0] == "f":
            corners = [tuple(int(value) for value in corner.split("/")) for corner in fields[1:]]
            if (len(corners) != 3 or any(len(corner) != 3 or not 1 <= corner[0] <= len(vertices) or
                                         not 1 <= corner[1] <= len(uvs) or not 1 <= corner[2] <= len(normals)
                                         for corner in corners)):
                raise ValueError("OBJ face references missing vertices, UVs or normals")
            faces.append(tuple(corner[0] - 1 for corner in corners))
    edges = Counter()
    directed = Counter()
    volume = 0.
    for face in faces:
        for a, b in zip(face, face[1:] + face[:1]):
            edges[tuple(sorted((a, b)))] += 1
            directed[(a, b)] += 1
        a, b, c = (vertices[index] for index in face)
        volume += (a[0] * (b[1] * c[2] - b[2] * c[1]) +
                   a[1] * (b[2] * c[0] - b[0] * c[2]) +
                   a[2] * (b[0] * c[1] - b[1] * c[0])) / 6
    if (not faces or any(count != 2 or directed[(a, b)] != directed[(b, a)]
                         for (a, b), count in edges.items()) or volume <= 0 or
            any(not math.isclose(math.sqrt(sum(value * value for value in normal)), 1., abs_tol=2e-6)
                for normal in normals)):
        raise ValueError("OBJ readback is not a closed, consistently wound shell with unit normals")
    return vertices, faces, materials, volume


class NorthMarketMassingTests(unittest.TestCase):
    def test_actual_candidates_produce_readable_closed_and_pinned_obj_files(self):
        with TemporaryDirectory() as temp, patch.object(massing, "PROJECT", Path(temp)):
            saved = Path(temp) / "Saved"
            saved.mkdir()
            output = saved / "review"
            report = massing.build(output)
            self.assertEqual(report["status"], "review_only_massing")
            self.assertFalse(report["runtime_activation_eligible"])
            self.assertFalse(report["source_glb_reverified_in_this_run"])
            self.assertEqual(len(report["buildings"]), 4)
            self.assertEqual(report, json.loads((output / "massing_manifest.json").read_text()))
            for row in report["buildings"].values():
                file = output / row["file"]
                vertices, faces, materials, volume = read_obj(file)
                self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(), row["sha256"])
                self.assertEqual(len(vertices), row["vertices"])
                self.assertEqual(len(faces), row["triangles"])
                self.assertEqual(materials, {"ClayRoof", "LimeWall", "StoneBase"})
                self.assertAlmostEqual(volume, row["volume_m3"], places=3)
            before = {path.name: path.read_bytes() for path in output.iterdir()}
            with self.assertRaises(FileExistsError):
                massing.build(output)
            self.assertEqual(before, {path.name: path.read_bytes() for path in output.iterdir()})

    def test_changed_surveyed_footprint_or_roof_is_rejected(self):
        plan = json.loads((massing.SURVEY / "north_market_east_plan_20261115.json").read_text())
        candidate = json.loads((massing.SURVEY / "north_market_east_candidate_20261115.json").read_text())
        original = plan["buildings"][0]
        record = candidate["buildings"][0]
        massing.verify_record(record, original)
        changed = deepcopy(original)
        changed["footprint_local_m"][0][0] += .1
        with self.assertRaisesRegex(ValueError, "footprint or yaw"):
            massing.verify_record(record, changed)
        changed = deepcopy(original)
        changed["roof_profile_local_y_z_m"][1][1] = original["source_max_height_m"] + 1
        with self.assertRaisesRegex(ValueError, "roof profile"):
            massing.make_mesh(changed)

    def test_broken_or_reversed_surfaces_are_rejected(self):
        mesh = massing.Mesh()
        mesh.face("LimeWall", ((0, 0, 0), (1, 0, 0), (0, 1, 0)))
        with self.assertRaisesRegex(ValueError, "closed"):
            mesh.audit()
        plan = json.loads((massing.SURVEY / "north_market_west_plan_20261115.json").read_text())
        changed = deepcopy(plan["buildings"][0])
        changed["surface_triangulation"]["ccw_faces"][0].reverse()
        with self.assertRaisesRegex(ValueError, "triangulation"):
            massing.make_mesh(changed)


if __name__ == "__main__":
    unittest.main()
