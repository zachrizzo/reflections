"""Exercise grouped import safety without Unreal, Blender or package changes."""

import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import import_grouped_buildings_unreal as importer
from group_whole_buildings import write_cell
from subtract_building_shells import digest, read_json, write_glb
from extract_tile_frontages import read_glb


TILE = "Tile_p03_p00"
SLOT = "M_GLMedieval_Oak"
MATERIAL_PATH = f"{importer.MATERIAL_ROOT}/{SLOT}.{SLOT}"
CELLS = ("Tile_p03_p00_xp0_yp0", "Tile_p03_p00_xp1_yp0")
CHECK = {"status": "offline_geometry_only", "cells": 2, "triangles": 2, "grouped_sections": 2,
         "checked_corners": 6, "source_sections": 2, "buildings": 2}


class ImportTask:
    def set_editor_properties(self, values):
        self.values = values
        self.objects = []

    def get_objects(self):
        return self.objects


class Material:
    def __init__(self, path):
        self.path = path

    def get_path_name(self):
        return self.path


class Mesh:
    def __init__(self, package, slots):
        self.package = package
        self.slots = slots
        self.materials = [None] * len(slots)
        self.collision = [False] * len(slots)
        self.complexity = None
        self.navigation = False

    def get_path_name(self):
        return f'{self.package}.{self.package.rsplit("/", 1)[-1]}'

    def get_name(self):
        return self.package.rsplit("/", 1)[-1]

    def get_package(self):
        return SimpleNamespace(get_name=lambda: self.package)

    def get_num_sections(self, _lod):
        return len(self.slots)

    def get_num_triangles(self, _lod):
        return 1

    def get_editor_property(self, key):
        if key == "static_materials":
            return [SimpleNamespace(get_editor_property=lambda _key, value=value: value) for value in self.slots]
        if key == "has_navigation_data":
            return self.navigation
        raise AttributeError(key)

    def set_editor_property(self, key, value):
        if key != "has_navigation_data":
            raise AttributeError(key)
        self.navigation = value

    def set_material(self, index, material):
        self.materials[index] = material

    def get_material(self, index):
        return self.materials[index]

    def get_bounding_box(self):
        return SimpleNamespace(min=SimpleNamespace(x=0., y=0., z=0.),
                               max=SimpleNamespace(x=100., y=100., z=0.))


class MeshEditor:
    def enable_section_collision(self, mesh, value, _lod, index):
        mesh.collision[index] = value

    def is_section_collision_enabled(self, mesh, _lod, index):
        return mesh.collision[index]

    def set_collision_complexity(self, mesh, value):
        mesh.complexity = value
        return True

    def get_collision_complexity(self, mesh):
        return mesh.complexity

    def get_simple_collision_count(self, _mesh):
        return 0

    def get_convex_collision_count(self, _mesh):
        return 0

    def get_lod_count(self, _mesh):
        return 1

    def get_num_uv_channels(self, _mesh, _lod):
        return 1


class GroupedImportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = self.enterContext(TemporaryDirectory())
        self.root = Path(self.temporary).resolve()
        self.saved = self.root / "Saved"
        self.bundle = self.root / "ArtDirection/CityPCG/GroupedPrototype"
        self.bundle.mkdir(parents=True)
        (self.root / "Models").mkdir()
        (self.root / "Models/kit.json").write_text("{}", encoding="utf-8")
        for name in ("canonical.fbx", "prepared.fbx"):
            (self.root / "Models" / name).write_bytes(name.encode())

        buildings = [{"id": "one"}, {"id": "two"}]
        mask = {"source_tile": TILE, "source_tile_asset": f"/Game/Tiles/{TILE}.{TILE}",
                "source_origin_m": [3000., 0., 0.], "source_export_sha256": "a" * 64,
                "buildings": buildings}
        cells = {}
        vertices = [((0., 0., 0.), (0., 1., 0.), (0., 0.)),
                    ((1., 0., 0.), (0., 1., 0.), (1., 0.)),
                    ((0., 0., 1.), (0., 1., 0.), (0., 1.))]
        for index, name in enumerate(CELLS):
            path = self.bundle / f"{name}.glb"
            write_cell(path, {SLOT: (vertices, [0, 1, 2])})
            cells[name] = {"tile": TILE, "file": path.name, "sha256": digest(path.read_bytes()),
                           "origin_ue_m": [3000. + 64 * index, 0., 0.],
                           "sections": [{"slot": SLOT, "material_asset": MATERIAL_PATH, "triangles": 1}],
                           "buildings": [{"id": buildings[index]["id"], "kit": "Models/kit.json",
                                          "canonical_fbx": "Models/canonical.fbx",
                                          "prepared_fbx": "Models/prepared.fbx"}]}
        self.manifest = {"schema": 2, "status": "offline_geometry_only", "source_paths": "project_relative_posix",
                         "cells": cells, "tile_barriers": {TILE: {
                             "source_tile_asset": mask["source_tile_asset"], "source_origin_m": mask["source_origin_m"],
                             "source_export_sha256": mask["source_export_sha256"],
                             "required_building_ids": ["one", "two"], "required_cells": list(CELLS)}}}
        self.evidence = {"status": "offline_only", "cumulative_masks": {TILE: mask}}
        self.write_metadata()

        self.enterContext(patch.object(importer, "PROJECT", self.root))
        self.enterContext(patch.object(importer, "SAVED", self.saved))
        self.enterContext(patch.object(importer, "BUNDLE", self.bundle))
        self.enterContext(patch.object(importer, "load_decoder", return_value=object()))
        self.independent = self.enterContext(patch.object(importer, "verify_grouped", return_value=CHECK))
        self.report_file = self.saved / "CityPCG/GroupedImport/preflight.json"
        self.report = importer.preflight(self.root / "decoder", self.report_file)

        self.lease = {"owner": importer.OWNER, "acquired_epoch": 900., "expires_epoch": 1200.}
        self.write_lease()
        self.enterContext(patch.object(importer.time, "time", return_value=1000.))
        self.editor_cls, self.mesh_editor_cls = object(), object()
        self.editor = SimpleNamespace(get_editor_world=lambda: SimpleNamespace(
            get_path_name=lambda: importer.LEVEL + ".GrayLondon_Geodata"), get_game_world=lambda: None)
        self.mesh_editor = MeshEditor()
        self.asset_paths = set()
        self.existing_registry = set()
        self.existing_memory = set()
        self.meshes = []
        self.wrong_slot = False
        self.add_extra = False
        self.import_assets = Mock(side_effect=self.import_one)
        self.save = Mock(side_effect=self.save_packages)
        self.registry = self.enterContext(patch.object(importer, "verify_registry"))
        self.roundtrip = self.enterContext(patch.object(importer, "compare_roundtrip", return_value={"roundtrip": "pass"}))
        self.enterContext(patch.object(importer, "import_options", return_value=(object(), object())))
        self.memory = [5 * 1024 ** 3, 12 * 1024 ** 3]
        self.enterContext(patch.object(importer, "memory_headroom", side_effect=lambda: tuple(self.memory)))
        self.connected = False
        self.pie = []
        self.unreal = SimpleNamespace(
            Paths=SimpleNamespace(project_dir=lambda: str(self.root), convert_relative_path_to_full=lambda path: path),
            UnrealEditorSubsystem=self.editor_cls, StaticMeshEditorSubsystem=self.mesh_editor_cls,
            get_editor_subsystem=lambda cls: self.editor if cls is self.editor_cls else self.mesh_editor,
            EditorLevelLibrary=SimpleNamespace(get_pie_worlds=lambda _all: self.pie),
            MultiUserClientStatics=SimpleNamespace(get_multi_user_connection_status_detail=lambda: self.connected),
            MultiUserConnectionStatus=SimpleNamespace(CONNECTED=True),
            EditorAssetLibrary=SimpleNamespace(does_asset_exist=self.existing_registry.__contains__,
                                               list_assets=lambda *_args, **_kwargs: list(self.asset_paths)),
            find_package=lambda path: object() if path in self.existing_memory else None,
            AssetToolsHelpers=SimpleNamespace(get_asset_tools=lambda: SimpleNamespace(import_asset_tasks=self.import_assets)),
            AssetImportTask=ImportTask, MaterialInterface=Material, StaticMesh=Mesh,
            load_asset=lambda path, cls: Material(path) if cls is Material else None,
            CollisionTraceFlag=SimpleNamespace(CTF_USE_COMPLEX_AS_SIMPLE="complex"),
            EditorLoadingAndSavingUtils=SimpleNamespace(save_packages=self.save),
        )
        self.enterContext(patch.dict("sys.modules", {"unreal": self.unreal}))

    def write_metadata(self):
        for name, value in ((importer.MANIFEST, self.manifest), (importer.EVIDENCE, self.evidence)):
            (self.bundle / name).write_text(json.dumps(value), encoding="utf-8")

    def write_lease(self):
        self.saved.mkdir(parents=True, exist_ok=True)
        (self.saved / "PIE_LOCK.json").write_text(json.dumps(self.lease), encoding="utf-8")

    def import_one(self, tasks):
        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        values = task.values
        self.assertFalse(values["save"])
        self.assertFalse(values["replace_existing"])
        package = f'{values["destination_path"]}/{values["destination_name"]}'
        slots = ["wrong_slot"] if self.wrong_slot and len(self.meshes) == 1 else [SLOT]
        mesh = Mesh(package, slots)
        self.meshes.append(mesh)
        self.asset_paths.add(mesh.get_path_name())
        if self.add_extra:
            self.asset_paths.add(importer.DEST + "/Unexpected.Unexpected")
        task.objects = [mesh]

    def save_packages(self, packages, only_dirty):
        self.assertFalse(only_dirty)
        for package in packages:
            path = importer.package_file(package.get_name())
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"test mesh")
        return True

    def test_preflight_runs_independent_geometry_check_and_refuses_overwrite(self):
        self.independent.assert_called_once()
        self.assertEqual(self.report["geometry_check"]["checked_corners"], 6)
        self.assertEqual(self.report["cells"][CELLS[0]]["bounds_cm"], [[0., 0., 0.], [100., 100., 0.]])
        with self.assertRaises(FileExistsError):
            importer.preflight(self.root / "decoder", self.report_file)

    def test_stale_group_or_source_cannot_reuse_preflight(self):
        for path in (self.bundle / f"{CELLS[0]}.glb", self.root / "Models/prepared.fbx"):
            with self.subTest(path=path):
                original = path.read_bytes()
                path.write_bytes(original + b"changed")
                with self.assertRaisesRegex(RuntimeError, "stale"):
                    importer.run([TILE], self.report_file)
                path.write_bytes(original)
        self.import_assets.assert_not_called()
        self.save.assert_not_called()

    def test_rejects_missing_or_misassigned_cells(self):
        barrier = self.manifest["tile_barriers"][TILE]
        barrier["required_cells"] = [CELLS[0]]
        self.write_metadata()
        with self.assertRaisesRegex(ValueError, "exactly one complete tile"):
            importer.validate_manifest()
        self.import_assets.assert_not_called()

    def test_wrong_section_material_is_rejected_even_with_new_hash(self):
        name = CELLS[0]
        path = self.bundle / f"{name}.glb"
        document, binary = read_glb(path)
        document["materials"][0]["name"] = "Wrong"
        changed = self.bundle / "changed.glb"
        write_glb(changed, document, bytearray(binary))
        path.write_bytes(changed.read_bytes())
        self.manifest["cells"][name]["sha256"] = digest(path.read_bytes())
        with self.assertRaisesRegex(ValueError, "material slot"):
            importer.describe_cell(self.bundle, name, self.manifest["cells"][name])

    def test_nonfinite_uv_and_normal_are_rejected(self):
        name = CELLS[0]
        path = self.bundle / f"{name}.glb"
        document, binary = read_glb(path)
        for attribute in ("TEXCOORD_0", "NORMAL"):
            with self.subTest(attribute=attribute):
                modified = bytearray(binary)
                idx = document["meshes"][0]["primitives"][0]["attributes"][attribute]
                record = document["accessors"][idx]
                view = document["bufferViews"][record["bufferView"]]
                offset = view.get("byteOffset", 0) + record.get("byteOffset", 0)
                struct.pack_into("<f", modified, offset, float("nan"))
                changed = self.bundle / f"changed_{attribute}.glb"
                write_glb(changed, document, modified)
                original = path.read_bytes()
                try:
                    path.write_bytes(changed.read_bytes())
                    self.manifest["cells"][name]["sha256"] = digest(path.read_bytes())
                    with self.assertRaisesRegex(ValueError, "non-finite UVs or invalid normals"):
                        importer.describe_cell(self.bundle, name, self.manifest["cells"][name])
                finally:
                    path.write_bytes(original)

    def test_tampered_bounds_in_report_cannot_weaken_import_check(self):
        report = read_json(self.report_file)
        report["cells"][CELLS[0]]["bounds_cm"] = []
        self.report_file.write_text(json.dumps(report), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "signed bounds"):
            importer.run([TILE], self.report_file)
        self.import_assets.assert_not_called()

    def test_existing_package_anywhere_is_never_overwritten(self):
        package = importer.group_package(CELLS[-1])
        file_path = importer.package_file(package)
        for location in ("disk", "registry", "memory"):
            with self.subTest(location=location):
                if location == "disk":
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_bytes(b"existing")
                elif location == "registry":
                    self.existing_registry.add(package)
                else:
                    self.existing_memory.add(package)
                with self.assertRaisesRegex(FileExistsError, "Refusing to overwrite"):
                    importer.run([TILE], self.report_file)
                if location == "disk":
                    file_path.unlink()
                self.existing_registry.clear()
                self.existing_memory.clear()
        self.import_assets.assert_not_called()
        self.save.assert_not_called()

    def test_selection_requires_complete_distinct_tiles(self):
        for tiles in ([], [TILE, TILE], ["Tile_p99_p99"], [CELLS[0]]):
            with self.subTest(tiles=tiles):
                with self.assertRaises(ValueError):
                    importer.selected_cells(self.manifest, self.report, tiles)
        self.assertEqual([name for name, _ in importer.selected_cells(self.manifest, self.report, [TILE])], list(CELLS))

    def test_pie_multiuser_and_other_lease_refuse_import(self):
        for mode in ("pie", "multiuser", "lease"):
            with self.subTest(mode=mode):
                self.pie[:] = [object()] if mode == "pie" else []
                self.connected = mode == "multiuser"
                self.lease["owner"] = "other" if mode == "lease" else importer.OWNER
                self.write_lease()
                with self.assertRaises(RuntimeError):
                    importer.run([TILE], self.report_file)
        self.import_assets.assert_not_called()
        self.save.assert_not_called()

    def test_low_physical_or_commit_headroom_refuses_import(self):
        for physical, commit in ((importer.MIN_PHYSICAL_BYTES - 1, importer.MIN_COMMIT_BYTES),
                                 (importer.MIN_PHYSICAL_BYTES, importer.MIN_COMMIT_BYTES - 1)):
            with self.subTest(physical=physical, commit=commit):
                self.memory[:] = [physical, commit]
                with self.assertRaisesRegex(RuntimeError, "memory|headroom"):
                    importer.run([TILE], self.report_file)
        self.import_assets.assert_not_called()
        self.save.assert_not_called()

    def test_second_mesh_failure_leaves_entire_tile_unsaved(self):
        self.wrong_slot = True
        with self.assertRaisesRegex(RuntimeError, "slot"):
            importer.run([TILE], self.report_file)
        self.assertEqual(self.import_assets.call_count, 2)
        self.save.assert_not_called()
        self.registry.assert_not_called()

    def test_lease_change_after_first_mesh_prevents_any_save(self):
        def audit(*_args):
            self.lease["expires_epoch"] = 999.
            self.write_lease()
            return {"roundtrip": "pass"}

        self.roundtrip.side_effect = audit
        with self.assertRaisesRegex(RuntimeError, "lease"):
            importer.run([TILE], self.report_file)
        self.assertEqual(self.import_assets.call_count, 1)
        self.save.assert_not_called()

    def test_unexpected_imported_asset_prevents_save(self):
        self.add_extra = True
        with self.assertRaisesRegex(RuntimeError, "save scope"):
            importer.run([TILE], self.report_file)
        self.save.assert_not_called()

    def test_source_changed_during_import_prevents_any_save(self):
        def audit(*_args):
            if self.roundtrip.call_count == 2:
                (self.root / "Models/canonical.fbx").write_bytes(b"new source")
            return {"roundtrip": "pass"}

        self.roundtrip.side_effect = audit
        with self.assertRaisesRegex(RuntimeError, "stale"):
            importer.run([TILE], self.report_file)
        self.assertEqual(self.import_assets.call_count, 2)
        self.save.assert_not_called()

    def test_partial_save_reports_exact_written_package(self):
        def partial(packages, only_dirty):
            self.save_packages(packages[:1], only_dirty)
            return False

        self.save.side_effect = partial
        with self.assertRaisesRegex(RuntimeError, importer.group_package(CELLS[0])):
            importer.run([TILE], self.report_file)
        self.assertTrue(importer.package_file(importer.group_package(CELLS[0])).is_file())
        self.assertFalse(importer.package_file(importer.group_package(CELLS[1])).exists())
        self.registry.assert_not_called()

    def test_post_save_registry_failure_reports_saved_packages(self):
        self.registry.side_effect = RuntimeError("missing material dependency")
        with self.assertRaisesRegex(RuntimeError, "Saved packages failed registry verification"):
            importer.run([TILE], self.report_file)
        self.assertTrue(all(importer.package_file(importer.group_package(name)).is_file() for name in CELLS))

    def test_import_binds_exact_materials_and_saves_only_selected_group(self):
        report = importer.run([TILE], self.report_file)
        self.assertEqual(report["status"], "assets_imported_not_placed")
        expected = [importer.group_package(name) for name in CELLS]
        self.assertEqual(report["saved_packages"], expected)
        self.assertEqual(self.save.call_count, 1)
        self.assertEqual([package.get_name() for package in self.save.call_args.args[0]], expected)
        self.assertTrue(all(mesh.materials[0].get_path_name() == MATERIAL_PATH for mesh in self.meshes))
        self.assertTrue(all(mesh.collision == [True] and mesh.navigation and mesh.complexity == "complex"
                            for mesh in self.meshes))
        self.assertEqual(self.roundtrip.call_count, 2)
        self.registry.assert_called_once()


if __name__ == "__main__":
    unittest.main()
