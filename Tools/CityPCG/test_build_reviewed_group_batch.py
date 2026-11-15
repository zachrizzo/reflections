"""Tiny offline tests for guarded whole-building batch selection."""

from pathlib import Path
import hashlib
import json
import unittest
from unittest.mock import patch

import build_reviewed_group_batch as batch
from test_verify_west_mark_lane_section_mapping import checked_tempdir


TILE = "Tile_p04_p00"


def group(name, ids):
    links = [{"members": [a, b]} for a, b in zip(ids, ids[1:])]
    return {"tile": TILE, "source_group_id": name, "status": "offline_screened_needs_revalidation",
            "group_has_baseline_or_conflicting_members": False, "baseline_members": [], "conflicting_members": [],
            "original_members": ids, "new_buildings": [{"id": value} for value in ids],
            "new_connected_components": [{"building_ids": ids, "retained_street_links": links,
                                           "requires_new_connectivity_evidence": False,
                                           "requires_current_road_revalidation": True,
                                           "exceeds_four_model_batch": False}]}


def fixture():
    document = {"status": "offline_review_worklist_only", "runtime_activation_eligible": False,
                "connected_groups": [group("block_a", ["a", "b"]), group("block_b", ["c", "d"])]}
    baseline = {"status": "offline_only", "requested_mask_failures": [], "requested_pin_failures": [],
                "cumulative_masks": {TILE: {"buildings": [{"id": "old"}]}}}
    return document, baseline


class ReviewedGroupBatchTests(unittest.TestCase):
    def test_closed_or_reserved_guard_prevents_any_input_or_output_work(self):
        with patch.object(batch, "Guard", side_effect=RuntimeError("reserved")), \
                patch.object(batch, "read_json") as read, patch.object(batch, "fresh_destination") as create:
            with self.assertRaisesRegex(RuntimeError, "reserved"):
                batch.run(TILE, ["block_a"], "batch_001")
            read.assert_not_called()
            create.assert_not_called()

    def test_full_groups_are_batched_deterministically_up_to_four_models(self):
        document, baseline = fixture()
        selected = batch.select_groups(document, TILE, ["block_b", "block_a"], baseline)
        self.assertEqual([row["source_group_id"] for row in selected], ["block_a", "block_b"])

    def test_duplicate_mixed_already_used_or_disconnected_groups_fail(self):
        document, baseline = fixture()
        with self.assertRaises(ValueError):
            batch.select_groups(document, TILE, ["block_a", "block_a"], baseline)
        baseline["cumulative_masks"][TILE]["buildings"].append({"id": "a"})
        with self.assertRaisesRegex(ValueError, "already used"):
            batch.select_groups(document, TILE, ["block_a"], baseline)
        document, baseline = fixture()
        document["connected_groups"][0]["group_has_baseline_or_conflicting_members"] = True
        with self.assertRaisesRegex(ValueError, "mixed"):
            batch.select_groups(document, TILE, ["block_a"], baseline)
        document, baseline = fixture()
        document["connected_groups"][0]["new_connected_components"][0]["retained_street_links"] = []
        with self.assertRaisesRegex(ValueError, "disconnected"):
            batch.select_groups(document, TILE, ["block_a"], baseline)

    def test_cross_group_batch_above_four_models_is_rejected(self):
        document, baseline = fixture()
        document["connected_groups"][0] = group("block_a", ["a", "b", "e"])
        with self.assertRaisesRegex(ValueError, "At most 4"):
            batch.select_groups(document, TILE, ["block_a", "block_b"], baseline)

    def test_output_is_a_fresh_safe_named_directory(self):
        with checked_tempdir() as root, patch.object(batch, "ROOT", root):
            with self.assertRaises(ValueError):
                batch.fresh_destination("../escape")
            output = batch.fresh_destination("batch_001")
            self.assertEqual(output, root / "Saved/CityPCG/ReviewedWholeBuildingBatches/batch_001")
            sentinel = output / "keep.txt"
            sentinel.write_text("unchanged", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                batch.fresh_destination("batch_001")
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "unchanged")

    def test_redirected_output_parent_is_rejected(self):
        with checked_tempdir() as root, patch.object(batch, "ROOT", root):
            original = Path.resolve

            def redirected(path, *args, **kwargs):
                return root / "outside" if path == root / "Saved" else original(path, *args, **kwargs)

            with patch.object(Path, "resolve", autospec=True, side_effect=redirected):
                with self.assertRaisesRegex(ValueError, "redirected"):
                    batch.fresh_destination("batch_001")

    def test_continuation_requires_a_completed_pinned_preceding_batch(self):
        with checked_tempdir() as root:
            batches = root / "Saved/CityPCG/ReviewedWholeBuildingBatches"
            previous = batches / "previous"
            previous.mkdir(parents=True)
            baseline = previous / "next_rollout_baseline.json"
            baseline.write_text('{"status":"offline_only"}\n', encoding="utf-8")
            with patch.object(batch, "ROOT", root), patch.object(batch, "BATCHES", batches):
                with self.assertRaises(FileNotFoundError):
                    batch.completed_baseline(baseline, lambda: None)
                manifest = previous / "batch_manifest.json"
                value = {"status": "unreviewed_detailed_obj_source", "runtime_activation_eligible": False,
                         "next_baseline_sha256": hashlib.sha256(baseline.read_bytes()).hexdigest()}
                manifest.write_text(json.dumps(value), encoding="utf-8")
                self.assertEqual(batch.completed_baseline(baseline, lambda: None),
                                 (baseline.resolve(), manifest.resolve()))
                baseline.write_text('{"status":"changed"}\n', encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "baseline hash changed"):
                    batch.completed_baseline(baseline, lambda: None)

    @unittest.skipUnless(batch.DEFAULT_WORKLIST.is_file(), "requires the locally generated snapshot worklist")
    def test_current_worklist_matches_the_tracked_snapshot_without_parsing_glbs(self):
        document, baseline, _ = batch.verified_worklist(batch.DEFAULT_WORKLIST)
        selected = batch.select_groups(document, TILE, ["block_269eb22dac5f"], baseline)
        self.assertEqual(len(selected[0]["new_buildings"]), 2)


if __name__ == "__main__":
    unittest.main()
