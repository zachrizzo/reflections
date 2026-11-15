"""Focused geometry regressions for district-level whole-building screening."""

import unittest

from extract_tile_frontages import SpatialBins
from select_whole_building_blocks import enclosed_and_clear, guide_distance, street_link


def rectangle(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def shell(x, road_x):
    return {
        "footprint": rectangle(x - 2, 3, x + 2, 7),
        "entries": [{"edge": 0, "verified_offline_approach":
                     [None, {"road_clear_to_xy_m": [road_x, 0]}, None]}],
    }


class ScreeningTests(unittest.TestCase):
    def test_guard_crossing_and_guard_inside_both_fail(self):
        building = rectangle(0, 0, 5, 5)
        self.assertEqual(guide_distance(building, [(-1, 2), (6, 2)]), 0)
        self.assertEqual(guide_distance(building, [(2, 2), (3, 3)]), 0)
        self.assertEqual(guide_distance(building, [(-1, -1), (6, -1)]), 1)

    def test_protected_landmark_contained_by_footprint(self):
        building = rectangle(0, 0, 5, 5)
        self.assertFalse(enclosed_and_clear(building, [(1, 1, 2, 2)]))
        self.assertTrue(enclosed_and_clear(building, [(7, 7, 9, 9)]))

    def test_link_needs_continuous_dry_road(self):
        a, b = shell(0, 0), shell(15, 15)
        walls = SpatialBins([], lambda wall: wall[:2])
        link = street_link(a, b, lambda point: abs(point[1]) < 1, walls)
        self.assertEqual(link["length_m"], 15)
        self.assertEqual(link["samples"], 63)
        dry_with_gap = lambda point: abs(point[1]) < 1 and not 7 < point[0] < 8
        self.assertIsNone(street_link(a, b, dry_with_gap, walls))

    def test_link_rejects_crossing_source_wall(self):
        a, b = shell(0, 0), shell(15, 15)
        wall = ((7.3, -3), (7.3, 3), .2, 4, (1, 0))
        walls = SpatialBins([wall], lambda wall: wall[:2])
        self.assertIsNone(street_link(a, b, lambda point: abs(point[1]) < 1, walls))


if __name__ == "__main__":
    unittest.main()
