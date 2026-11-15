"""Check the lightweight shim and the real North Market detail inputs."""

import json
import math
from pathlib import Path
import subprocess
import sys
import unittest

import preflight_north_market_details as preflight


class DetailedNorthMarketPreflightTests(unittest.TestCase):
    def test_concave_roof_tessellation_covers_area_with_ccw_triangles(self):
        points = [(0, 0), (4, 0), (4, 4), (2, 2), (0, 4)]
        faces = preflight.tessellate_polygon([[preflight.Vector(point) for point in points]])
        areas = [preflight.cross(*(points[index] for index in face)) / 2 for face in faces]
        self.assertEqual(len(faces), len(points) - 2)
        self.assertTrue(all(area > 0 for area in areas))
        self.assertTrue(math.isclose(sum(areas), 12.))

    def test_bad_roof_rings_and_zero_vectors_fail(self):
        with self.assertRaises(ValueError):
            preflight.tessellate_polygon([[preflight.Vector(point) for point in [(0, 0), (0, 1), (1, 0)]]])
        with self.assertRaises(ValueError):
            preflight.tessellate_polygon([[preflight.Vector(point) for point in [(0, 0), (1, 0), (0, 0)]]])
        with self.assertRaises(ValueError):
            preflight.Vector((0, 0)).normalized()

    @unittest.skipUnless(preflight.TILE.is_file(), "requires the pinned local source tile export in Saved")
    def test_actual_generator_builds_all_four_detailed_intermediates(self):
        code = ("import json,sys;sys.path.insert(0,'Tools/CityPCG');"
                "import preflight_north_market_details as p;print(json.dumps(p.generate_preflight()))")
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=preflight.ROOT,
                                capture_output=True, text=True, check=True)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "detail_geometry_input_preflight_only")
        self.assertEqual(len(report["buildings"]), 4)
        self.assertEqual(len(report["textures"]), 9)
        self.assertEqual({row["style"] for row in report["buildings"].values()},
                         {"TradingRange", "DeepWorkshop", "SteppedMarket"})
        self.assertTrue(all(row["vertices"] > 5000 and row["fan_triangle_estimate"] > 8000
                            for row in report["buildings"].values()))


if __name__ == "__main__":
    unittest.main()
