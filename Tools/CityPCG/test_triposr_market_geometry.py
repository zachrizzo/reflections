import asyncio
import json
import math
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import import_triposr_market_unreal as importer
import place_triposr_market_pcg as pcg
import triposr_market_geometry as geometry
import triposr_market_sources as sources


def glb(*, color=True, winding=(0, 1, 2), translated=False, invalid=False, rgb=None):
    xyz = [(0., 0., 0.), (1., 0., 0.), (0., 1., float("nan") if invalid else 0.)]
    rgb = rgb or [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]
    binary = b"".join(struct.pack("<3f", *v) for v in xyz)
    binary += b"".join(struct.pack("<4B", *v) for v in rgb)
    binary += struct.pack("<3H", *winding)
    views = [{"buffer": 0, "byteOffset": 0, "byteLength": 36},
             {"buffer": 0, "byteOffset": 36, "byteLength": 12},
             {"buffer": 0, "byteOffset": 48, "byteLength": 6}]
    accessors = [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"},
                 {"bufferView": 1, "componentType": 5121, "count": 3, "type": "VEC4", "normalized": True},
                 {"bufferView": 2, "componentType": 5123, "count": 3, "type": "SCALAR"}]
    attributes = {"POSITION": 0}
    if color:
        attributes["COLOR_0"] = 1
    node = {"mesh": 0}
    if translated:
        node["translation"] = [1, 0, 0]
    doc = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": len(binary)}],
           "bufferViews": views, "accessors": accessors,
           "meshes": [{"primitives": [{"attributes": attributes, "indices": 2}]}],
           "nodes": [node], "scenes": [{"nodes": [0]}], "scene": 0}
    j = json.dumps(doc, separators=(",", ":")).encode()
    j += b" " * (-len(j) % 4)
    binary += b"\0" * (-len(binary) % 4)
    body = struct.pack("<I4s", len(j), b"JSON") + j + struct.pack("<I4s", len(binary), b"BIN\0") + binary
    return struct.pack("<4sII", b"glTF", 2, len(body) + 12) + body


class GlbTests(unittest.TestCase):
    def test_color_and_winding_roundtrip(self):
        self.assertEqual(geometry.compare_glb(glb(), glb(winding=(1, 2, 0)))["triangles"], 1)
        with self.assertRaises(ValueError):
            geometry.compare_glb(glb(), glb(winding=(0, 2, 1)))

    def test_true_distance_tolerance_not_rounding_grid(self):
        def shifted(delta):
            raw = bytearray(glb())
            json_length = struct.unpack_from("<I", raw, 12)[0]
            first_position = 20 + json_length + 8
            struct.pack_into("<f", raw, first_position, delta)
            return bytes(raw)
        report = geometry.compare_glb(glb(), shifted(.0000005))
        self.assertGreater(report["max_corner_distance_gltf_units"], 0)
        with self.assertRaises(ValueError):
            geometry.compare_glb(glb(), shifted(.00001))

    def test_changed_or_missing_color_rejected(self):
        changed = [(255, 0, 0, 255), (0, 255, 0, 255), (1, 0, 255, 255)]
        with self.assertRaises(ValueError):
            geometry.compare_glb(glb(), glb(rgb=changed))
        with self.assertRaises(ValueError):
            geometry.parse_glb(glb(color=False))
        with self.assertRaises(ValueError):
            geometry.parse_glb(glb(rgb=[(255, 255, 255, 255)] * 3))

    def test_transforms_and_nonfinite_rejected(self):
        for raw in (glb(translated=True), glb(invalid=True)):
            with self.subTest(raw=raw[-12:]), self.assertRaises(ValueError):
                geometry.parse_glb(raw)

    def test_truncated_or_bad_index_rejected(self):
        for raw in (glb()[:-1], glb(winding=(0, 1, 3))):
            with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                geometry.parse_glb(raw)

    def test_explicit_z_up_conversion_rotates_vertices_and_keeps_colors(self):
        raw = glb()
        result, report = geometry.normalize_z_up_glb(raw)
        self.assertNotEqual(report["raw_sha256"], report["normalized_sha256"])
        parsed = geometry.parse_glb(result)
        face = next(iter(parsed["faces"]))
        self.assertIn((0, 0, -10000, 0, 0, 255), face)
        self.assertIn((10000, 0, 0, 0, 255, 0), face)
        self.assertEqual(parsed["triangles"], 1)


class PlacementTests(unittest.TestCase):
    def test_proportional_scale_and_off_center_pivot(self):
        row = geometry.placement("AppleBasket", ((-20, -30, -10), (80, 20, 40)), (1000, 400, 12), 90)
        self.assertEqual(row["scale"], (.55, .55, .55))
        self.assertAlmostEqual(row["location_cm"][0], 997.25)
        self.assertAlmostEqual(row["location_cm"][1], 383.5)
        self.assertAlmostEqual(row["location_cm"][2], 17.5)
        for actual, expected in zip(row["size_cm"], (55., 27.5, 27.5)):
            self.assertAlmostEqual(actual, expected)

    def test_corridor_and_footprint_overlap_rejected(self):
        path = [{"a_cm": (0, 0), "b_cm": (1000, 0), "half_width_cm": 125}]
        row = geometry.placement("AppleBasket", ((-20, -20, 0), (20, 20, 40)), (500, 220, 0), 0)
        self.assertTrue(geometry.check_clearance([row], path))
        with self.assertRaises(ValueError):
            geometry.check_clearance([dict(row, support_cm=(500, 150, 0))], path)
        with self.assertRaises(ValueError):
            geometry.check_clearance([row, row], path)

    def test_incomplete_evidence_and_unsafe_numbers_rejected(self):
        with self.assertRaises(ValueError):
            geometry.placement("AppleBasket", ((0, 0, 0), (1, 1, 1)), (0, 0, math.nan), 0)
        with self.assertRaises(ValueError):
            geometry.check_clearance([], [])
        with self.assertRaises(ValueError):
            geometry.placement("Unknown", ((0, 0, 0), (1, 1, 1)), (0, 0, 0), 0)

    def test_transformed_scene_box_and_ground_contact(self):
        box = pcg.transformed_box(((-5, -10, 0), (5, 10, 10)), ((100, 50, 5), (0, 0, 90), (2, 2, 2)))
        for actual, expected in zip(box[0], (80, 40, 5)):
            self.assertAlmostEqual(actual, expected)
        prop = {"support_cm": (100, 50, 25), "size_cm": (20, 20, 20), "radius_cm": 15}
        self.assertFalse(pcg.box_overlaps_prop(box, prop))
        prop["support_cm"] = (100, 50, 20)
        self.assertTrue(pcg.box_overlaps_prop(box, prop))
        with self.assertRaises(ValueError):
            pcg.transformed_box(((-1, -1, -1), (1, 1, 1)), ((0, 0, 0), (5, 0, 0), (1, 1, 1)))

    def test_rejects_curved_road_and_live_story_positions(self):
        row = {"support_cm": (1000., 210., 0.), "radius_cm": 30.}
        with patch.object(pcg.town, "curve_bounds", return_value=(-10., 10.)):
            pcg.xy_clear([row], [(1000., 800., "story")])
            with self.assertRaises(ValueError):
                pcg.xy_clear([dict(row, support_cm=(1000., 170., 0.))], [])
            with self.assertRaises(ValueError):
                pcg.xy_clear([row], [(1000., 270., "story")])

    def test_exact_generated_transform(self):
        expected = ((1., 2., 3.), (0., 0., 359.99), (.5, .5, .5))
        self.assertTrue(pcg.matches_transform(((1.01, 2, 3), (0, 0, -.01), (.5, .5, .5)), expected))
        self.assertFalse(pcg.matches_transform(((1.1, 2, 3), (0, 0, -.01), (.5, .5, .5)), expected))
        self.assertFalse(pcg.matches_transform(((1, 2, 3), (1, 0, -.01), (.5, .5, .5)), expected))

    def test_cosmetic_floor_limit_and_known_paving_only(self):
        paving = pcg.town.PAVING + "." + pcg.town.PAVING.rsplit("/", 1)[-1]
        box = ((0, 0, -10), (100, 100, 7))
        self.assertTrue(pcg.is_cosmetic_paving(paving, box, -5))
        self.assertFalse(pcg.is_cosmetic_paving(paving + "Other", box, -5))
        self.assertFalse(pcg.is_cosmetic_paving(paving, ((0, 0, -10), (100, 100, 7.01)), -5))
        actor = SimpleNamespace(get_path_name=lambda: "/Town/Floor")
        component = SimpleNamespace(get_path_name=lambda: "/Town/Floor.Component")
        hit = [None] * 11
        hit[1], hit[5], hit[7], hit[9], hit[10] = (False, SimpleNamespace(z=-5),
            SimpleNamespace(x=0, y=0, z=1), actor, component)
        unreal = SimpleNamespace(Vector=lambda x, y, z: (x, y, z),
            TraceTypeQuery=SimpleNamespace(ECC_VISIBILITY=1), DrawDebugTrace=SimpleNamespace(NONE=0),
            SystemLibrary=SimpleNamespace(line_trace_single=lambda *args: SimpleNamespace(to_tuple=lambda: hit)))
        row = {"support_cm": [10, 20, 7], "surface": {"actor_path": "/Town/Floor",
               "component_path": "/Town/Floor.Component", "cosmetic_offset_cm": 12}}
        self.assertEqual(pcg.verify_support(unreal, object(), row), -5)
        row["surface"]["cosmetic_offset_cm"] = 12.01
        with self.assertRaises(ValueError):
            pcg.verify_support(unreal, object(), row)


class SessionTests(unittest.TestCase):
    def test_normalized_source_is_deterministic_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            data = glb()
            path = sources.preserve_normalized(directory, "BakersTray", "a" * 64, data)
            self.assertEqual(path.name, "BakersTray_aaaaaaaaaaaaaaaa.glb")
            self.assertEqual(sources.preserve_normalized(directory, "BakersTray", "a" * 64, data), path)
            path.write_bytes(b"changed")
            with self.assertRaises(ValueError):
                sources.preserve_normalized(directory, "BakersTray", "a" * 64, data)
            self.assertEqual(path.read_bytes(), b"changed")

    def test_refuses_wrong_or_changed_lease_and_pie(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Saved").mkdir()
            lock = root / "Saved" / "PIE_LOCK.json"
            valid = {"owner": importer.OWNER, "purpose": importer.PURPOSE, "expires_epoch": 2000}
            lock.write_text(json.dumps(valid), encoding="utf-8")
            editor = SimpleNamespace(get_editor_world=lambda: SimpleNamespace(get_path_name=lambda: geometry.LEVEL + ".Town"),
                                     get_game_world=lambda: None)
            unreal = SimpleNamespace(
                Paths=SimpleNamespace(project_dir=lambda: str(root), convert_relative_path_to_full=lambda value: value),
                UnrealEditorSubsystem=object, get_editor_subsystem=lambda _: editor,
                EditorLevelLibrary=SimpleNamespace(get_pie_worlds=lambda _: []),
                MultiUserClientStatics=SimpleNamespace(get_multi_user_connection_status_detail=lambda: "offline"),
                MultiUserConnectionStatus=SimpleNamespace(CONNECTED="connected"))
            with patch.object(importer, "PROJECT", root), patch.object(importer, "SAVED", root / "Saved"), \
                    patch.object(importer.time, "time", return_value=1000):
                self.assertEqual(importer.lease_check(unreal), valid)
                with self.assertRaises(RuntimeError):
                    importer.lease_check(unreal, {**valid, "owner": "somebody_else"})
                lock.write_text(json.dumps({**valid, "owner": "somebody_else"}), encoding="utf-8")
                with self.assertRaises(RuntimeError):
                    importer.lease_check(unreal)
                lock.write_text(json.dumps(valid), encoding="utf-8")
                editor.get_game_world = lambda: object()
                with self.assertRaises(RuntimeError):
                    importer.lease_check(unreal)

    def test_vertex_color_uses_unnamed_material_output(self):
        class Material:
            def get_package(self):
                return SimpleNamespace(get_name=lambda: importer.material_package("BakersTray"))
            def set_editor_property(self, *args):
                pass
        class Expression:
            def set_editor_property(self, *args):
                pass
        connected = []
        edit = SimpleNamespace(create_material_expression=lambda *args: Expression(),
            connect_material_property=lambda node, output, prop: connected.append((output, prop)) or True,
            recompile_material=lambda material: None)
        tools = SimpleNamespace(create_asset=lambda *args: Material())
        unreal = SimpleNamespace(Material=Material, MaterialFactoryNew=lambda: None,
            MaterialEditingLibrary=edit, MaterialExpressionVertexColor=object,
            MaterialExpressionConstant=object, MaterialProperty=SimpleNamespace(
                MP_BASE_COLOR="base", MP_ROUGHNESS="rough", MP_METALLIC="metal"),
            AssetToolsHelpers=SimpleNamespace(get_asset_tools=lambda: tools))
        importer.make_material(unreal, "BakersTray")
        self.assertIn(("", "base"), connected)
        self.assertNotIn(("RGB", "base"), connected)

    def test_survey_returns_plan_without_generating_or_saving(self):
        class StaticMesh:
            pass
        class InstancedStaticMeshComponent:
            pass
        def v(x, y, z):
            return SimpleNamespace(x=x, y=y, z=z)
        rot = SimpleNamespace(roll=0., pitch=0., yaw=90.)
        transform = SimpleNamespace(get_editor_property=lambda name: {
            "translation": v(1000, 500, 4), "rotation": SimpleNamespace(rotator=lambda: rot),
            "scale3d": v(1, 1, 1)}[name])
        prop_mesh = StaticMesh()
        prop_mesh.get_package = lambda: SimpleNamespace(get_name=lambda: importer.asset_package("BakersTray"))
        prop_mesh.get_bounds = lambda: SimpleNamespace(origin=v(0, 0, 5), box_extent=v(20, 20, 10))
        stall_path = pcg.town.PROPS["stall"] + "." + pcg.town.PROPS["stall"].rsplit("/", 1)[-1]
        stall_mesh = SimpleNamespace(get_path_name=lambda: stall_path)
        component = InstancedStaticMeshComponent()
        component.get_editor_property = lambda name: stall_mesh
        component.get_path_name = lambda: "/Town/PCG.Stall"
        component.get_instance_count = lambda: 1
        component.get_instance_transform = lambda *args, **kwargs: transform
        volume = SimpleNamespace(get_actor_label=lambda: pcg.TOWN_ACTOR, get_path_name=lambda: "/Town/PCG",
                                 get_components_by_class=lambda cls: [component])
        floor = SimpleNamespace(get_path_name=lambda: "/Town/Floor")
        floor_component = SimpleNamespace(get_path_name=lambda: "/Town/Floor.Component")
        hit = [None] * 11
        hit[1], hit[5], hit[7], hit[9], hit[10] = False, v(1000, 700, -5), v(0, 0, 1), floor, floor_component
        editor_class, actor_class = object(), object()
        editor = SimpleNamespace(get_editor_world=lambda: object())
        actor_subsystem = SimpleNamespace(get_all_level_actors=lambda: [volume])
        unreal = SimpleNamespace(StaticMesh=StaticMesh, InstancedStaticMeshComponent=InstancedStaticMeshComponent,
            UnrealEditorSubsystem=editor_class, EditorActorSubsystem=actor_class,
            get_editor_subsystem=lambda cls: editor if cls is editor_class else actor_subsystem,
            EditorAssetLibrary=SimpleNamespace(load_asset=lambda package: prop_mesh),
            Vector=v, TraceTypeQuery=SimpleNamespace(ECC_VISIBILITY=1), DrawDebugTrace=SimpleNamespace(NONE=0),
            SystemLibrary=SimpleNamespace(line_trace_single=lambda *args: SimpleNamespace(to_tuple=lambda: hit)))
        sha = "1" * 64
        with patch.dict(sys.modules, {"unreal": unreal}), patch.object(importer, "lease_check", return_value={}), \
             patch.object(importer, "source_path", return_value=Path("unused")), \
             patch.object(importer, "sha256", return_value=sha), patch.object(pcg, "verify_material"), \
             patch.object(pcg, "verified_stories", return_value=[]), \
             patch.object(pcg, "verify_scene_clearance", return_value=3), patch.object(pcg, "checked_plan"):
            survey = pcg.survey_one("BakersTray", sha, 0, (0, 200), identifier="Test01")
        self.assertEqual(survey["saved_packages"], [])
        self.assertEqual(survey["plan"]["placements"][0]["support_cm"], [1000., 700., 3.])
        self.assertEqual(survey["plan"]["placements"][0]["anchor"]["instance_index"], 0)
        self.assertEqual(survey["plan"]["status"], "live_survey_requires_visual_review")

    def test_pcg_authoring_requires_visual_acknowledgement(self):
        with patch.dict(sys.modules, {"unreal": SimpleNamespace()}):
            with self.assertRaises(ValueError):
                asyncio.run(pcg.run({}))


if __name__ == "__main__":
    unittest.main()
