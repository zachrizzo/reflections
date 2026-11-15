"""Tests for export identity and cumulative preflight across city tiles."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from audit_whole_building_rollout import PACKAGE_ROOT, audit, validate_mask
from subtract_building_shells import digest


TILE = "Tile_p04_p00"
OTHER = "Tile_p03_p00"


class WholeBuildingRolloutTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.tiles, self.exports = self.root / "Tiles", self.root / "Exports"
        self.tiles.mkdir()
        for name in (TILE, OTHER):
            (self.tiles / f"{name}.uasset").touch()
        self.asset = f"{PACKAGE_ROOT}/{TILE}.{TILE}"
        self.origin = [4000, 0, 0]
        self.slots = {"GL_Facade": 80, "GL_Roof": 60, "GL_Road": 20, "GL_CentralFacade": 10}
        self.metadata = {"tile": TILE, "asset": self.asset, "origin_m": self.origin, "primitives": self.slots}
        self.inventory = self.enterContext(patch("audit_whole_building_rollout.inventory", side_effect=self.inspect))
        self.enterContext(patch("audit_whole_building_rollout.read_glb", return_value=({}, b"")))
        self.faces = self.enterContext(patch("audit_whole_building_rollout.reviewed_faces",
                                            return_value=({0: {5, 6}, 1: {11}}, {})))

    def inspect(self, source, metadata):
        return {"source_sha256": digest(source.read_bytes()), "roof_triangles": 60,
                "component_counts": {"complete_ground_shell": 20}}

    def export(self, directory, payload):
        export_dir = self.exports / directory
        export_dir.mkdir(parents=True)
        source = export_dir / f"{TILE}.glb"
        source.write_bytes(payload)
        source.with_suffix(".asset.json").write_text(json.dumps(self.metadata), encoding="utf-8")
        return source

    def candidate(self, name, source):
        path = self.root / f"{name}.json"
        mask = {"status": "offline_candidate", "coordinate_system": "ue_local_m", "source_tile": TILE,
                "source_origin_m": self.origin, "source_tile_asset": self.asset,
                "source_export_sha256": digest(source.read_bytes()), "ordinary_wall_primitive": 0,
                "roof_primitive": 1, "untouched_primitives": {"2": "GL_Road", "3": "GL_CentralFacade"},
                "buildings": [{"id": name}]}
        path.write_text(json.dumps(mask), encoding="utf-8")
        return path

    def test_multiple_export_hashes_require_a_reviewed_pin(self):
        self.export("old", b"older export")
        current = self.export("new", b"newer export")
        report = audit(self.tiles, self.exports)
        self.assertEqual(report["tile_inventory"][TILE]["status"], "blocked")
        self.assertEqual(report["tile_inventory"][OTHER]["status"], "needs_original_export")
        self.inventory.assert_not_called()
        report = audit(self.tiles, self.exports, [self.candidate("one", current)])
        self.assertEqual(report["tile_inventory"][TILE]["source"], str(current))
        self.assertEqual(report["tile_inventory"][TILE]["offline_mask_face_counts"], {"GL_Facade": 2, "GL_Roof": 1})

    def test_explicit_pin_can_inventory_an_export_without_a_candidate(self):
        old = self.export("old", b"older export")
        current = self.export("new", b"newer export")
        pin = {TILE: digest(old.read_bytes())}
        report = audit(self.tiles, self.exports, source_pins=pin)
        self.assertEqual(report["tile_inventory"][TILE]["source"], str(old))
        self.assertEqual(report["cumulative_masks"], {})
        report = audit(self.tiles, self.exports, [self.candidate("one", current)], source_pins=pin)
        self.assertEqual(report["requested_mask_failures"], [TILE])
        self.assertIn("differs from the candidate", report["tile_inventory"][TILE]["reason"])

    def test_previous_masks_must_survive_rollout(self):
        original = self.export("canonical", b"one original export")
        first, second = (self.candidate(name, original) for name in ("first", "second"))
        previous = audit(self.tiles, self.exports, [first])["cumulative_masks"]
        report = audit(self.tiles, self.exports, [first, second], previous)
        self.assertEqual([row["id"] for row in report["cumulative_masks"][TILE]["buildings"]], ["first", "second"])
        combined_mask = self.faces.call_args.args[2]
        self.assertEqual(len(combined_mask["buildings"]), 2)
        with self.assertRaisesRegex(ValueError, "mask changed or was removed"):
            audit(self.tiles, self.exports, [second], previous)
        with self.assertRaisesRegex(ValueError, "mask tile was omitted"):
            audit(self.tiles, self.exports, [], previous)

    def test_same_sha_with_conflicting_slot_orders_is_blocked(self):
        original = self.export("one", b"same export")
        self.metadata["primitives"] = dict(reversed(list(self.slots.items())))
        self.export("two", original.read_bytes())
        report = audit(self.tiles, self.exports)
        self.assertIn("ordered slots", report["tile_inventory"][TILE]["reason"])
        self.inventory.assert_not_called()

    def test_protected_slots_and_zeroed_sections_fail_closed(self):
        source = self.export("canonical", b"one original export")
        mask = json.loads(self.candidate("one", source).read_text(encoding="utf-8"))
        identity = self.asset, self.origin, self.slots
        with self.assertRaisesRegex(ValueError, "immutable sections"):
            validate_mask(source, identity, {**mask, "untouched_primitives": {"2": "GL_Road"}})
        self.faces.assert_not_called()
        self.faces.return_value = {0: set(range(80)), 1: {11}}, {}
        with self.assertRaisesRegex(ValueError, "empties"):
            validate_mask(source, identity, mask)


if __name__ == "__main__":
    unittest.main()
