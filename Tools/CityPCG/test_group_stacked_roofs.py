"""Geometry regressions for diagnostic roof-stack grouping."""

import unittest

from group_stacked_roofs import Roof, Wall, relation, ring_edges, select_links


def rectangle(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def triangulate(ring):
    a, b, c, d = ring
    return (a, b, c), (a, c, d)


def roof(identifier, ring, top, base):
    walls = tuple(Wall(a, b, base, (2 * i, 2 * i + 1))
                  for i, (a, b) in enumerate(ring_edges(ring)))
    return Roof(identifier, top, "complete_ground_shell", (ring,), triangulate(ring), (0, 1), walls)


class StackTests(unittest.TestCase):
    def test_source_base_offset_and_shared_wall(self):
        lower = roof("lower", rectangle(0, 0, 8, 6), 5.0, .2)
        upper = roof("upper", rectangle(2, 0, 6, 4), 9.0, 5.2)
        result = relation(lower, upper)
        self.assertEqual(result["status"], "aligned_wall_continuation")
        self.assertEqual(result["height_offsets_m"], [.2])
        self.assertEqual(result["shared_wall_length_m"], 4)

    def test_genuine_inset_has_bearing_without_aligned_wall(self):
        lower = roof("lower", rectangle(0, 0, 8, 6), 5.0, .2)
        upper = roof("upper", rectangle(2, 1, 6, 4), 9.0, 5.0)
        result = relation(lower, upper)
        self.assertEqual(result["status"], "inset_wall_bearing")
        self.assertEqual(result["shared_wall_length_m"], 0)

    def test_nearby_vertical_level_is_not_a_supported_join(self):
        lower = roof("lower", rectangle(0, 0, 8, 6), 5.0, .2)
        upper = roof("upper", rectangle(2, 0, 6, 4), 9.0, 5.09)
        self.assertEqual(relation(lower, upper)["status"], "no_height_transition")

    def test_abutting_buildings_share_edge_but_do_not_stack(self):
        lower = roof("lower", rectangle(0, 0, 8, 6), 5.0, .2)
        upper = roof("upper", rectangle(8, 0, 10, 6), 9.0, 5.2)
        result = relation(lower, upper)
        self.assertEqual(result["status"], "insufficient_footprint_overlap")
        self.assertEqual(result["shared_wall_length_m"], 6)

    def test_courtyard_is_not_support(self):
        outside = rectangle(0, 0, 8, 6)
        hole = rectangle(2, 2, 6, 4)
        strips = (rectangle(0, 0, 8, 2), rectangle(0, 4, 8, 6),
                  rectangle(0, 2, 2, 4), rectangle(6, 2, 8, 4))
        triangles = tuple(triangle for strip in strips for triangle in triangulate(strip))
        lower = Roof("lower", 5.0, "complete_ground_courtyard", (outside, hole), triangles, (), ())
        upper = roof("upper", rectangle(2.5, 2.5, 5.5, 3.5), 9.0, 5.2)
        result = relation(lower, upper)
        self.assertEqual(result["status"], "insufficient_footprint_overlap")
        self.assertEqual(result["overlap_m2"], 0)

    def test_wall_overhang_is_rejected_despite_area_overlap(self):
        lower = roof("lower", rectangle(0, 0, 20, 1), 5.0, .2)
        upper = roof("upper", rectangle(0, .03, 20, 1.03), 9.0, 5.2)
        result = relation(lower, upper)
        self.assertEqual(result["status"], "insufficient_wall_bearing")
        self.assertEqual(result["upper_footprint_overlap_fraction"], .97)

    def test_two_plausible_parents_remain_unmerged(self):
        shared = {"upper": "upper", "status": "aligned_wall_continuation"}
        candidates = [{**shared, "lower": "lower_1"}, {**shared, "lower": "lower_2"}]
        self.assertEqual(select_links(candidates), [])
        self.assertEqual([row["status"] for row in candidates], ["ambiguous_support", "ambiguous_support"])


if __name__ == "__main__":
    unittest.main()
