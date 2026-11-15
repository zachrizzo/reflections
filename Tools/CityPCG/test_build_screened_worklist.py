"""Offline worklist checks for mixed groups, source overlap and connectivity."""

from copy import deepcopy
from pathlib import Path
import json
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

import build_screened_worklist as worklist
from test_verify_west_mark_lane_section_mapping import checked_tempdir


def building(tile, suffix, seed):
    return {"id": f"{tile}_roof_{suffix}", "footprint": [[0., 0.], [1., 0.], [0., 1.]],
            "origin_m": [0., 0., 0.], "area_m2": .5, "entries": [{"edge": 0}],
            "source_wall_faces_by_edge": [[seed * 10, seed * 10 + 1]],
            "wall_triangle_signature_by_edge": [[f"{seed * 10:020x}", f"{seed * 10 + 1:020x}"]],
            "source_roof_faces": [seed], "roof_triangle_signatures": [f"{seed:020x}"]}


def fixture():
    reports, masks = {}, {}
    for index, tile in enumerate(worklist.TILES, 1):
        old = building(tile, "old", index)
        common = {"source_tile": tile, "source_export_sha256": "a" * 64,
                  "source_origin_m": [0., 0., 0.], "ordinary_wall_primitive": 0, "roof_primitive": 1}
        masks[tile] = {**common, "buildings": [old]}
        reports[tile] = {**common, "tile": tile, "overlay_export_sha256": "b" * 64,
                         "reviewed_neighbor_tiles": [], "screened_candidates": [old], "connected_groups": []}
    first = worklist.TILES[0]
    old = masks[first]["buildings"][0]
    b, c, alone = (building(first, "b", 11), building(first, "c", 12), building(first, "alone", 13))
    members = sorted([old["id"], b["id"], c["id"]])
    identifier = "block_" + worklist.sha("|".join(members).encode("ascii"))[:12]
    reports[first]["screened_candidates"].extend([b, c, alone])
    reports[first]["connected_groups"] = [{"id": identifier, "members": members, "street_links": [
        {"members": [old["id"], b["id"]], "samples": 9},
        {"members": [old["id"], c["id"]], "samples": 9}]}]
    previous = {"status": "offline_only", "requested_mask_failures": [], "requested_pin_failures": [],
                "source_tile_count": 117, "locally_exported_tile_count": 3, "cumulative_masks": masks}
    return previous, reports, {"baseline": {}, **{tile: {} for tile in worklist.TILES}}


class ScreenedWorklistTests(unittest.TestCase):
    def test_fresh_minimal_checkout_regenerates_without_saved_inputs_or_glbs(self):
        with checked_tempdir() as root:
            tool = root / "Tools/CityPCG/build_screened_worklist.py"
            tool.parent.mkdir(parents=True)
            shutil.copyfile(worklist.ROOT / "Tools/CityPCG/build_screened_worklist.py", tool)
            snapshot = root / "ArtDirection/CityPCG/MedievalOpening/ScreenedSurveySnapshot20261115"
            snapshot.mkdir(parents=True)
            names = [worklist.PREVIOUS.name, *(path.name for path in worklist.REPORTS.values()),
                     worklist.SNAPSHOT_MANIFEST.name]
            for name in names:
                shutil.copyfile(worklist.SNAPSHOT / name, snapshot / name)
            self.assertFalse((root / "Saved").exists())
            subprocess.run([sys.executable, "-B", str(tool)], cwd=root, check=True, capture_output=True, text=True)
            result_path = root / "Saved/CityPCG/MedievalSurvey/screened_worklist_from_snapshot_20261115_codex.json"
            result = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual((result["baseline_building_count"], result["additional_screened_candidates"]), (18, 52))
            self.assertEqual((len(result["connected_groups"]), len(result["singletons"])), (8, 22))
            self.assertFalse(result["source_binary_hashes_rechecked"])
            self.assertFalse(any((root / "Saved").rglob("*.glb")))
            previous, baseline = worklist.read_input(worklist.PREVIOUS)
            pairs = {tile: worklist.read_input(path) for tile, path in worklist.REPORTS.items()}
            expected = worklist.make_worklist(previous, {tile: pair[0] for tile, pair in pairs.items()},
                                              {"baseline": baseline, **{tile: pair[1] for tile, pair in pairs.items()}})
            result.pop("review_snapshot_manifest")
            self.assertEqual(result, expected)

    def test_fresh_checkout_creates_only_checked_saved_output_parents(self):
        with checked_tempdir() as root:
            output = root / "Saved/CityPCG/MedievalSurvey/worklist.json"
            with patch.object(worklist, "ROOT", root), patch.object(worklist, "OUTPUT", output):
                self.assertEqual(worklist.checked_output_parent(), output.parent)
                self.assertTrue(output.parent.is_dir())
                self.assertEqual(worklist.checked_output_parent(), output.parent)

    def test_redirected_saved_parent_is_rejected(self):
        with checked_tempdir() as root:
            output = root / "Saved/CityPCG/MedievalSurvey/worklist.json"
            original = Path.resolve

            def redirected(path, *args, **kwargs):
                return root / "outside" if path == root / "Saved" else original(path, *args, **kwargs)

            with patch.object(worklist, "ROOT", root), patch.object(worklist, "OUTPUT", output), \
                    patch.object(Path, "resolve", autospec=True, side_effect=redirected):
                with self.assertRaisesRegex(RuntimeError, "redirected"):
                    worklist.checked_output_parent()

    def test_snapshot_reconstructs_52_review_only_candidates(self):
        worklist.checked_snapshot()
        previous, baseline = worklist.read_input(worklist.PREVIOUS)
        pairs = {tile: worklist.read_input(path) for tile, path in worklist.REPORTS.items()}
        result = worklist.make_worklist(previous, {tile: pair[0] for tile, pair in pairs.items()},
                                        {"baseline": baseline, **{tile: pair[1] for tile, pair in pairs.items()}})
        self.assertEqual((result["baseline_building_count"], result["additional_screened_candidates"]), (18, 52))
        self.assertEqual((len(result["connected_groups"]), len(result["singletons"])), (8, 22))
        self.assertFalse(result["source_binary_hashes_rechecked"])
        self.assertFalse(result["runtime_activation_eligible"])

    def test_snapshot_rejects_changed_bytes_and_private_paths(self):
        original = Path.read_bytes
        victim = worklist.REPORTS[worklist.TILES[0]]

        def changed(path):
            data = original(path)
            return data + b" " if path == victim else data

        with patch.object(Path, "read_bytes", autospec=True, side_effect=changed):
            with self.assertRaisesRegex(ValueError, "recorded identity"):
                worklist.checked_snapshot()
        for value in ("C:/Users/name/private", "C:\\Users\\name\\private", "/home/name/private",
                      "file:///private/file", "\\\\server\\private"):
            with self.subTest(value=value):
                self.assertTrue(worklist.has_private_absolute_path({"path": value}))
        self.assertFalse(worklist.has_private_absolute_path({"asset": "/Game/GrayLondon/Map"}))

    def test_mixed_group_does_not_assume_connectivity_through_existing_building(self):
        result = worklist.make_worklist(*fixture())
        self.assertEqual(result["baseline_building_count"], 3)
        self.assertEqual(result["additional_screened_candidates"], 3)
        self.assertFalse(result["runtime_activation_eligible"])
        block, = result["connected_groups"]
        self.assertTrue(block["group_has_baseline_or_conflicting_members"])
        parts = block["new_connected_components"]
        self.assertEqual([len(row["building_ids"]) for row in parts], [1, 1])
        self.assertTrue(all(row["requires_new_connectivity_evidence"] and not row["retained_street_links"] for row in parts))
        self.assertEqual(len(result["singletons"]), 1)

    def test_different_ids_sharing_faces_are_not_counted_as_new_candidates(self):
        previous, reports, inputs = fixture()
        tile = worklist.TILES[0]
        duplicate = deepcopy(reports[tile]["screened_candidates"][-1])
        duplicate["id"] = f"{tile}_roof_duplicate"
        reports[tile]["screened_candidates"].append(duplicate)
        result = worklist.make_worklist(previous, reports, inputs)
        self.assertEqual(result["additional_screened_candidates"], 2)
        self.assertEqual(len(result["singletons"]), 0)
        self.assertEqual(len(result["source_face_conflicts"]), 2)

    def test_changed_source_or_disconnected_original_group_is_rejected(self):
        previous, reports, inputs = fixture()
        reports[worklist.TILES[0]]["source_export_sha256"] = "c" * 64
        with self.assertRaisesRegex(ValueError, "source pins"):
            worklist.make_worklist(previous, reports, inputs)
        previous, reports, inputs = fixture()
        reports[worklist.TILES[0]]["connected_groups"][0]["street_links"].pop()
        with self.assertRaisesRegex(ValueError, "not connected"):
            worklist.make_worklist(previous, reports, inputs)


if __name__ == "__main__":
    unittest.main()
