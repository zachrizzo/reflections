"""Run the follow-on descriptor survey offline against a simulated editor."""

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import preview_west_mark_lane_unreal as preview
import survey_follow_on_actor_descs_unreal as helper


PROJECT = Path(__file__).resolve().parents[2]
MAP = "/Game/GrayLondon/Maps/GrayLondon_Geodata.GrayLondon_Geodata"
OWNER = "descriptor-survey-fixture"
ACTOR_PATH = f"{MAP}:PersistentLevel.SM_Merchant"
ACTOR_PACKAGE = "/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/1/23/FIXTURE"
LAYER_ASSET_PATH = "/Game/Example/DL_Review.DL_Review"
UNRESOLVED_LAYER_PATH = "/Game/Example/DL_Unknown.DL_Unknown"
LAYER_INSTANCE_PATH = f"{MAP}:PersistentLevel.WorldDataLayers.DL_Review"


def vector(x, y, z):
    return SimpleNamespace(x=x, y=y, z=z)


class Box:
    def set_editor_properties(self, properties):
        self.__dict__.update(properties)


def object_ref(path, package=None):
    return SimpleNamespace(
        get_path_name=lambda: path,
        get_package=lambda: SimpleNamespace(get_name=lambda: package),
    )


def fixture_layer():
    layer = object_ref(LAYER_INSTANCE_PATH, MAP.split(".")[0])
    layer.get_asset = lambda: object_ref(LAYER_ASSET_PATH, "/Game/Example/DL_Review")
    layer.get_parent = lambda: object_ref(f"{MAP}:PersistentLevel.WorldDataLayers.DL_Parent")
    layer.get_data_layer_short_name = lambda: "Review"
    layer.get_data_layer_full_name = lambda: "Parent/Review"
    layer.get_type = lambda: "Runtime"
    return layer


def fixture_descriptor():
    properties = {
        "bounds": SimpleNamespace(min=vector(250000, -50000, 0), max=vector(450000, 150000, 1540)),
        "native_class": object_ref("/Script/Engine.StaticMeshActor"),
        "actor_path": ACTOR_PATH,
        "actor_package": ACTOR_PACKAGE,
        "guid": SimpleNamespace(to_string=lambda: "fixture-original-guid"),
        "instance_guid": SimpleNamespace(to_string=lambda: "fixture-instance-guid"),
        "label": "Fixture façade",
        "name": "SM_Merchant",
        "folder_path": "Fixture",
        "runtime_grid": "None",
        "is_spatially_loaded": True,
        "actor_is_editor_only": False,
        "data_layer_assets": [LAYER_ASSET_PATH, UNRESOLVED_LAYER_PATH],
    }
    return SimpleNamespace(get_editor_property=properties.__getitem__)


class FollowOnActorSurveyTests(unittest.TestCase):
    def setUp(self):
        self.saved = Path(self.enterContext(TemporaryDirectory()))
        self.queries = []
        manager = SimpleNamespace(get_data_layer_instances=lambda: [fixture_layer()])
        self.library = SimpleNamespace(
            get_data_layer_manager_for_object=lambda world: manager,
            get_intersecting_actor_descs=self.intersect,
        )
        world = object_ref(MAP)
        self.unreal = SimpleNamespace(
            Box=Box,
            Vector=vector,
            WorldPartitionBlueprintLibrary=self.library,
            SystemLibrary=SimpleNamespace(break_soft_object_path=lambda path: path),
            Paths=SimpleNamespace(project_dir=lambda: str(PROJECT), project_saved_dir=lambda: str(self.saved)),
            EditorLevelLibrary=SimpleNamespace(get_pie_worlds=lambda include_dedicated: []),
            UnrealEditorSubsystem=object(),
            get_editor_subsystem=lambda subsystem: SimpleNamespace(get_editor_world=lambda: world),
        )
        self.enterContext(patch.dict(sys.modules, {"unreal": self.unreal}))
        self.enterContext(patch.object(preview, "SAVED", self.saved))
        self.write_lease()

    def write_lease(self, owner=OWNER, expires_in=600):
        lease = {"owner": owner, "expires_epoch": time.time() + expires_in, "expires_local": "fixture"}
        (self.saved / "PIE_LOCK.json").write_text(json.dumps(lease), encoding="utf-8")

    def intersect(self, box):
        self.assertTrue(box.is_valid)
        self.assertLess(box.min.x, box.max.x)
        self.assertLess(box.min.y, box.max.y)
        self.assertLess(box.min.z, box.max.z)
        self.queries.append(box)
        return [fixture_descriptor()]

    def test_queries_each_footprint_and_road_link(self):
        report = helper.survey(OWNER)
        self.assertEqual(set(report["blocks"]), set(helper.CANDIDATES))
        regions = [region for block in report["blocks"].values() for region in block["regions"]]
        footprints = [row for row in regions if row["kind"] == "footprint"]
        roads = [row for row in regions if row["kind"] == "road_link"]
        self.assertEqual((len(footprints), len(roads), len(self.queries)), (11, 13, 24))
        self.assertEqual(len(report["actors"]), 1)
        key, actor = next(iter(report["actors"].items()))
        self.assertEqual(actor["label"], "Fixture façade")
        self.assertEqual(actor["actor_package"], ACTOR_PACKAGE)
        self.assertEqual(actor["actor_path"], ACTOR_PATH)
        self.assertEqual(actor["instance_guid"], "fixture-instance-guid")
        self.assertEqual(actor["streaming_bounds_cm"], [[250000, -50000, 0], [450000, 150000, 1540]])
        self.assertTrue(all(row["hits"][0]["actor_key"] == key for row in regions))
        self.assertTrue(all(row["hits"][0]["footprint_touches_actor_bounds_xy"] for row in footprints))
        self.assertEqual(actor["data_layer_instance_matches"], {
            LAYER_ASSET_PATH: [LAYER_INSTANCE_PATH],
            UNRESOLVED_LAYER_PATH: [],
        })
        layer = report["data_layer_instances"][0]
        self.assertEqual(layer["instance_path"], LAYER_INSTANCE_PATH)
        self.assertEqual(layer["asset_package"], "/Game/Example/DL_Review")
        self.assertEqual(layer["parent_instance_path"], f"{MAP}:PersistentLevel.WorldDataLayers.DL_Parent")
        self.assertEqual(list(self.saved.iterdir()), [self.saved / "PIE_LOCK.json"])

    def test_expired_or_other_owner_lease_refuses_queries(self):
        with self.assertRaisesRegex(RuntimeError, "Editor reserved"):
            helper.survey("other-owner")
        self.write_lease(expires_in=-5)
        with self.assertRaisesRegex(RuntimeError, "active editor lease"):
            helper.survey(OWNER)
        self.assertEqual(self.queries, [])

    def test_changed_lease_blocks_report(self):
        def change_lease(box):
            if not self.queries:
                self.write_lease(expires_in=1200)
            return self.intersect(box)

        self.library.get_intersecting_actor_descs = change_lease
        with self.assertRaisesRegex(RuntimeError, "lease changed"):
            helper.survey(OWNER, report_name="changed.json")
        self.assertFalse((self.saved / "CityPCG").exists())

    def test_report_is_confined_and_requires_a_fresh_name(self):
        with self.assertRaisesRegex(ValueError, "JSON basename"):
            helper.survey(OWNER, report_name="../outside.json")
        output = helper.survey(OWNER, report_name="review.json")
        path = self.saved / "CityPCG/MedievalSurvey/review.json"
        self.assertEqual(Path(output["report"]), path.resolve())
        initial = path.read_bytes()
        self.assertEqual(json.loads(initial), helper.survey(OWNER))
        with self.assertRaises(FileExistsError):
            helper.survey(OWNER, report_name="review.json")
        self.assertEqual(path.read_bytes(), initial)

    def test_concave_footprint_rejects_an_actor_inside_its_notch(self):
        footprint = [(0, 0), (4, 0), (4, 1), (1, 1), (1, 4), (0, 4)]
        self.assertTrue(helper.footprint_intersects_bounds(footprint, [[20, 120, -20], [50, 170, 500]]))
        self.assertFalse(helper.footprint_intersects_bounds(footprint, [[210, 220, -20], [250, 270, 500]]))


if __name__ == "__main__":
    unittest.main()
