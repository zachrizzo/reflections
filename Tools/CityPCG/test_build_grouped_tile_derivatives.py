"""Exercise cumulative tile filtering with synthetic GLBs, without Unreal."""

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import build_grouped_tile_derivatives as builder
from combine_replacement_candidates import SOURCE_FIELDS, combine
from extract_building_shells import faces
from extract_tile_frontages import read_glb
from group_whole_buildings import mask_sha, write_cell
from subtract_building_shells import indices, triangle_signature, write_glb


TILE = "Tile_p03_p00"
CELL = TILE + "_xp0_yp0"
ASSET = f"/Game/GrayLondon/Geodata/Tiles/{TILE}.{TILE}"


def vertex(x, y, z):
    return ((x, y, z), (0., 0., 1.), (x / 10., y / 10.))


def write_fixture(path):
    wall = [vertex(0, 0, 0), vertex(1, 0, 0), vertex(0, 1, 0), vertex(1, 1, 0),
            vertex(3, 0, 0), vertex(4, 0, 0), vertex(3, 1, 0), vertex(4, 1, 0),
            vertex(6, 0, 0), vertex(7, 0, 0), vertex(6, 1, 0)]
    roofs = [vertex(0, 3, 0), vertex(1, 3, 0), vertex(0, 3, 1),
             vertex(3, 3, 0), vertex(4, 3, 0), vertex(3, 3, 1),
             vertex(6, 3, 0), vertex(7, 3, 0), vertex(6, 3, 1)]
    road = [vertex(0, 0, 2), vertex(1, 0, 2), vertex(0, 0, 3)]
    write_cell(path, {"GL_Facade": (wall, [0, 1, 2, 1, 3, 2, 4, 5, 6, 5, 7, 6, 8, 9, 10]),
                      "GL_Road": (road, [0, 1, 2]),
                      "GL_Roof": (roofs, list(range(9)))})


class GroupedTileDerivativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(TemporaryDirectory())
        self.root = Path(self.temp).resolve()
        self.saved = self.root / "Saved"
        self.saved.mkdir()
        self.queue = self.saved / "PIE_QUEUE.md"
        self.queue.write_text("# Queue\n!!! 03:25 TRAIN #17 LOADED (editor back) !!!\n"
                              "!!! 03:24 TRAIN #17 BUILDING (historical) !!!\n", encoding="utf-8")
        self.bundle = self.root / "Grouped"
        self.bundle.mkdir()
        self.source = self.saved / f"{TILE}.glb"
        self.metadata = self.saved / f"{TILE}.assets.json"
        write_fixture(self.source)
        original_sha = builder.file_sha(self.source)
        self.meta = {"tile": {"tile": TILE, "package": f"/Game/GrayLondon/Geodata/Tiles/{TILE}",
                              "origin_m": [3000., 0., 0.],
                              "primitives": {"GL_Facade": 5, "GL_Road": 1, "GL_Roof": 3}}, "overlay": {}}
        self.metadata.write_text(json.dumps(self.meta), encoding="utf-8")
        document, binary = read_glb(self.source)
        walls = faces(document, binary, 0, [3000., 0., 0.])
        roofs = faces(document, binary, 2, [3000., 0., 0.])

        def building(name, wall, roof):
            return {"id": name, "source_wall_faces_by_edge": [[wall, wall + 1]],
                    "wall_triangle_signature_by_edge": [[triangle_signature(walls[wall]),
                                                          triangle_signature(walls[wall + 1])]],
                    "source_roof_faces": [roof], "roof_triangle_signatures": [triangle_signature(roofs[roof])]}

        self.first, self.second = building("one", 0, 0), building("two", 2, 1)
        self.mask = {"name": "fixture", "status": "offline_candidate", "coordinate_system": "ue_local_m",
                     "source_tile": TILE, "source_tile_asset": ASSET, "source_export_sha256": original_sha,
                     "source_origin_m": [3000., 0., 0.], "ordinary_wall_primitive": 0,
                     "roof_primitive": 2, "untouched_primitives": {"1": "GL_Road"},
                     "buildings": [self.first]}
        self.extra = {"name": "extra", "status": "offline_candidate", **{key: self.mask[key] for key in SOURCE_FIELDS},
                      "buildings": [self.second]}
        self.extra_file = self.root / "extra.json"
        self.extra_file.write_text(json.dumps(self.extra), encoding="utf-8")
        ext = {"status": "offline_only", "cumulative_masks": {TILE: combine([self.mask, self.extra])}}
        self.extra_evidence = self.root / "extra_evidence.json"
        self.extra_evidence.write_text(json.dumps(ext), encoding="utf-8")
        group_file = self.bundle / f"{CELL}.glb"
        group_file.write_bytes(b"fixture grouped building")
        self.grouped = {"schema": 2, "status": "offline_geometry_only", "tile_barriers": {TILE: {
            "source_tile_asset": ASSET, "source_origin_m": self.mask["source_origin_m"],
            "source_export_sha256": original_sha, "cumulative_mask_sha256": mask_sha(self.mask),
            "required_building_ids": ["one"], "required_cells": [CELL]}},
            "cells": {CELL: {"tile": TILE, "file": group_file.name, "sha256": builder.file_sha(group_file),
                              "buildings": [{"id": "one"}]}}}
        self.evidence = {"status": "offline_only", "cumulative_masks": {TILE: self.mask}}
        self.write_group_files()
        self.enterContext(patch.object(builder, "PROJECT", self.root))
        self.enterContext(patch.object(builder, "SAVED", self.saved))
        self.enterContext(patch.object(builder, "memory_headroom", return_value=(
            builder.MIN_PHYSICAL_BYTES + 1, builder.MIN_COMMIT_BYTES + 1)))
        self.sources = {TILE: (self.source, self.metadata)}
        self.original_sha = original_sha

    def write_group_files(self):
        (self.bundle / "grouped_buildings.json").write_text(json.dumps(self.grouped), encoding="utf-8")
        (self.bundle / "rollout_mask_evidence.json").write_text(json.dumps(self.evidence), encoding="utf-8")

    def test_baseline_preserves_protected_road_and_original_source(self):
        output = self.saved / "baseline"
        report = builder.build(output, self.sources, bundle=self.bundle)
        row = report["tiles"][TILE]
        self.assertEqual(report["variant"], "baseline_grouped_masks")
        self.assertTrue(row["matches_checked_in_grouped_cells"])
        self.assertEqual(row["required_grouped_cells"], [CELL])
        self.assertEqual(row["removed_triangles_by_slot"], {"GL_Facade": 2, "GL_Roof": 1})
        self.assertEqual(row["section_check"][1], {"index": 1, "source_triangles": 1,
                                                   "removed_triangles": 0, "remaining_triangles": 1,
                                                   "protected_by_export_metadata": True})
        self.assertEqual(row["source_ue_section_mapping"], "unverified")
        self.assertFalse(row["runtime_activation_eligible"])
        self.assertEqual(builder.file_sha(self.source), self.original_sha)
        src, raw = read_glb(self.source), read_glb(output / row["filtered_glb"])
        self.assertEqual(indices(*src, 1), indices(*raw, 1))
        self.assertEqual(builder.file_sha(output / row["audit"]), row["audit_sha256"])
        self.assertFalse(list(output.parent.glob("grouped_tile_filters_*")))

    def test_extended_variant_cannot_claim_baseline_group_compatibility(self):
        report = builder.build(self.saved / "extended", self.sources, [TILE], [self.extra_file],
                               self.extra_evidence, bundle=self.bundle)
        row = report["tiles"][TILE]
        self.assertEqual(report["variant"], "extended_unmatched_groups")
        self.assertFalse(row["matches_checked_in_grouped_cells"])
        self.assertIsNone(row["required_grouped_cells"])
        self.assertEqual(row["required_building_ids"], ["one", "two"])
        self.assertEqual(row["removed_triangles_by_slot"], {"GL_Facade": 4, "GL_Roof": 2})
        self.assertIn("baseline mask", row["incompatibility"])

    def test_bad_source_or_group_hash_leaves_no_final_output(self):
        group = self.bundle / f"{CELL}.glb"
        for bad in (self.source, group):
            original = bad.read_bytes()
            try:
                bad.write_bytes(original + b"changed")
                output = self.saved / ("bad_source" if bad == self.source else "bad_group")
                with self.assertRaises(ValueError):
                    builder.build(output, self.sources, bundle=self.bundle)
                self.assertFalse(output.exists())
            finally:
                bad.write_bytes(original)

    def test_changed_inputs_during_subtraction_are_not_published(self):
        subtract = builder.subtract
        for name, target in (("metadata", self.metadata),
                             ("manifest", self.bundle / "grouped_buildings.json"),
                             ("cell", self.bundle / f"{CELL}.glb")):
            with self.subTest(input=name):
                original = target.read_bytes()
                output = self.saved / f"changed_{name}"

                def mutate_after_subtraction(*args, **kwargs):
                    result = subtract(*args, **kwargs)
                    target.write_bytes(original + b" ")
                    return result

                try:
                    with patch.object(builder, "subtract", side_effect=mutate_after_subtraction):
                        with self.assertRaises((RuntimeError, ValueError)):
                            builder.build(output, self.sources, bundle=self.bundle)
                    self.assertFalse(output.exists())
                finally:
                    target.write_bytes(original)

    def test_redirected_paths_cannot_publish_or_trigger_scratch_cleanup(self):
        resolve = Path.resolve
        checked_barriers = builder.checked_group_barriers
        outside = self.root / "outside"
        outside.mkdir()
        sentinel = outside / "keep.txt"
        sentinel.write_bytes(b"do not remove")
        for redirected_part in ("saved", "parent", "scratch", "staging", "destination"):
            with self.subTest(redirected_part=redirected_part):
                output = self.saved / f"parent_{redirected_part}" / "result"
                active = False
                checks = 0

                def activate_after_final_check(bundle):
                    nonlocal active, checks
                    result = checked_barriers(bundle)
                    checks += 1
                    active = checks == 2
                    return result

                def resolve_with_redirect(path, *args, **kwargs):
                    if active and ((redirected_part == "saved" and path == self.saved) or
                                   (redirected_part == "parent" and path == output.parent) or
                                   (redirected_part == "scratch" and
                                    path.name.startswith("grouped_tile_filters_")) or
                                   (redirected_part == "staging" and path.name == "bundle" and
                                    path.parent.name.startswith("grouped_tile_filters_")) or
                                   (redirected_part == "destination" and path == output)):
                        return outside
                    return resolve(path, *args, **kwargs)

                with patch.object(builder, "checked_group_barriers", side_effect=activate_after_final_check), \
                        patch.object(Path, "resolve", autospec=True, side_effect=resolve_with_redirect):
                    with self.assertRaisesRegex(RuntimeError, "redirected"):
                        builder.build(output, self.sources, bundle=self.bundle)
                self.assertFalse(output.exists())
                self.assertEqual(sentinel.read_bytes(), b"do not remove")
                scratches = list(output.parent.glob("grouped_tile_filters_*"))
                self.assertEqual(len(scratches), 1)
                self.assertTrue((scratches[0] / "bundle" / "tile_derivatives.json").is_file())

    def test_bad_extended_evidence_refuses_unreviewed_mask(self):
        self.extra_evidence.write_text(json.dumps({"status": "offline_only", "cumulative_masks": {TILE: self.mask}}),
                                       encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "independently reviewed"):
            builder.build(self.saved / "unreviewed", self.sources, [TILE], [self.extra_file],
                          self.extra_evidence, bundle=self.bundle)
        self.assertFalse((self.saved / "unreviewed").exists())

    def test_changed_protected_indices_fail_independent_comparison(self):
        output = self.saved / "checked"
        row = builder.build(output, self.sources, bundle=self.bundle)["tiles"][TILE]
        raw = output / row["filtered_glb"]
        named = output / row["import_glb"]
        document, binary = read_glb(raw)
        changed = deepcopy(document)
        changed["meshes"][0]["primitives"][1]["indices"] = changed["meshes"][0]["primitives"][0]["indices"]
        damaged = self.saved / "damaged.glb"
        write_glb(damaged, changed, bytearray(binary))
        with self.assertRaisesRegex(RuntimeError, "protected section change"):
            builder.independent_check(self.source, self.mask, damaged, named, ["GL_Facade", "GL_Road", "GL_Roof"])

    def test_no_overwrite_or_low_memory_work(self):
        output = self.saved / "existing"
        output.mkdir()
        sentinel = output / "keep.txt"
        sentinel.write_bytes(b"untouched")
        with self.assertRaises(ValueError):
            builder.build(output, self.sources, bundle=self.bundle)
        self.assertEqual(sentinel.read_bytes(), b"untouched")
        with patch.object(builder, "memory_headroom", return_value=(builder.MIN_PHYSICAL_BYTES - 1,
                                                                    builder.MIN_COMMIT_BYTES)):
            with self.assertRaisesRegex(RuntimeError, "headroom"):
                builder.build(self.saved / "low_memory", self.sources, bundle=self.bundle)
        self.assertFalse((self.saved / "low_memory").exists())

    def test_rejects_empty_selection_and_unrecognized_source_tile(self):
        with self.assertRaisesRegex(ValueError, "Select distinct grouped tiles"):
            builder.build(self.saved / "empty", self.sources, [], bundle=self.bundle)
        with self.assertRaisesRegex(ValueError, "Select distinct grouped tiles"):
            builder.build(self.saved / "unknown", {**self.sources, "Tile_p99_p99": (self.source, self.metadata)},
                          bundle=self.bundle)

    def test_active_or_unreadable_shared_editor_lease_prevents_filtering(self):
        lock = self.saved / "PIE_LOCK.json"
        for content in ('{"owner":"other","expires_epoch":9999999999}', '{"owner":"other"}', 'not-json'):
            with self.subTest(content=content):
                lock.write_text(content, encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "lease"):
                    builder.build(self.saved / "leased", self.sources, bundle=self.bundle)
                self.assertFalse((self.saved / "leased").exists())

    def test_current_train_status_blocks_building_but_ignores_history(self):
        output = self.saved / "train_guard"
        self.queue.write_text("# Queue\n!!! 03:36 TRAIN #18 BUILDING (editor closed) !!!\n"
                              "!!! 03:25 TRAIN #17 LOADED !!!\n", encoding="utf-8")
        with patch.object(builder, "read_glb", side_effect=AssertionError("must not read tile geometry")):
            with self.assertRaisesRegex(RuntimeError, "train #18 is BUILDING"):
                builder.build(output, self.sources, bundle=self.bundle)
        self.assertFalse(output.exists())

        self.queue.write_text("# Queue\n!!! 03:45 TRAIN #18 LOADED !!!\n"
                              "!!! 03:36 TRAIN #18 BUILDING (historical) !!!\n", encoding="utf-8")
        self.assertEqual(builder.build(output, self.sources, bundle=self.bundle)["status"], "offline_review_only")

    def test_missing_or_unrecognized_train_status_fails_closed(self):
        output = self.saved / "unknown_train"
        for content in ("# Queue\nno current status\n", "!!! 03:36 TRAIN #18 ???\n!!! 03:25 TRAIN #17 LOADED\n",
                        "!!! 03:36 TRAIN #18 PREPARING\n!!! 03:25 TRAIN #17 LOADED\n"):
            with self.subTest(content=content):
                self.queue.write_text(content, encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "train"):
                    builder.build(output, self.sources, bundle=self.bundle)
                self.assertFalse(output.exists())
        self.queue.unlink()
        with self.assertRaisesRegex(RuntimeError, "train queue"):
            builder.build(output, self.sources, bundle=self.bundle)

    def test_train_starting_during_preflight_stops_before_geometry(self):
        checked_barriers = builder.checked_group_barriers

        def start_train(bundle):
            result = checked_barriers(bundle)
            self.queue.write_text("!!! 03:36 TRAIN #18 BUILDING !!!\n"
                                  "!!! 03:25 TRAIN #17 LOADED !!!\n", encoding="utf-8")
            return result

        with patch.object(builder, "checked_group_barriers", side_effect=start_train), \
                patch.object(builder, "read_glb", side_effect=AssertionError("must not read tile geometry")):
            with self.assertRaisesRegex(RuntimeError, "train #18 is BUILDING"):
                builder.build(self.saved / "train_started", self.sources, bundle=self.bundle)
        self.assertFalse((self.saved / "train_started").exists())


if __name__ == "__main__":
    unittest.main()
