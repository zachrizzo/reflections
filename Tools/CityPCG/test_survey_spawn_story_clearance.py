"""Run the blocked spawn story-clearance checks against the saved checkout."""

import unittest

from survey_spawn_story_clearance import survey
from verify_spawn_building_review import PROJECT, SOURCE


@unittest.skipUnless((PROJECT / SOURCE).is_file(), "Requires the pinned local Gray London source export.")
class SpawnStoryClearanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = survey()

    def test_typed_relative_locations_preserve_nominal_guard(self):
        points = self.report["markers"]
        self.assertEqual(self.report["status"], "blocked_review_only")
        self.assertTrue(self.report["nominal_stair_guard_covers_entire_shell"])
        for name, offset, outside in (
            ("CutsceneAnchor_FirstPage", 4642, 1.781927),
            ("Home_frank_dunning", 4661, 1.582611),
        ):
            with self.subTest(name=name):
                point = points[name]
                self.assertEqual(point["property"], "RelativeLocation/StructProperty/Vector")
                self.assertEqual(point["value_offset"], offset)
                self.assertEqual(len(point["package_sha256"]), 64)
                self.assertEqual(len(point["value_sha256"]), 64)
                self.assertLess(point["nominal"]["signed_shell_edge_clearance_m"], 0)
                self.assertEqual(point["saved_relative_as_world_hypothesis"]["signed_shell_edge_clearance_m"], outside)
                self.assertEqual(point["nominal"]["source_surface_z_at_xy_m"], {"GL_Roof": [15.0]})
                self.assertEqual(point["saved_relative_as_world_hypothesis"]["source_surface_z_at_xy_m"], {})

    def test_saved_route_probe_reserves_capsule_clearance(self):
        routes = self.report["frank_to_stair_straight_probe"]
        self.assertEqual(routes["nominal_m"]["capsule_radius_plus_padding_clearance_m"], -.52)
        self.assertEqual(routes["serialized_relative_m"]["capsule_radius_plus_padding_clearance_m"], .223549)

    def test_saved_yaw_zero_camera_has_baseline_shell_intersections(self):
        keys = self.report["first_page_yaw_zero_keys"]["serialized_relative_m"]
        self.assertEqual(len(keys), 8)
        self.assertEqual(sum(row["camera_inside_source_shell"] for row in keys), 3)
        self.assertEqual(sum(row["view_ray_intersects_source_before_target"] for row in keys), 3)


if __name__ == "__main__":
    unittest.main()
