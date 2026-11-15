"""Exercise West Connector import safeguards with mocked Unreal services."""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import import_west_connector as importer


DESTINATION = '/Game/GrayLondon/MedievalOpening/WholeBuildings/WestConnector'
NAMES = (
    'SM_GLMedieval_WestConnector_TradingRange_0aa6599e',
    'SM_GLMedieval_WestConnector_DeepWorkshop_4bd93af4',
    'SM_GLMedieval_WestConnector_SteppedMarket_d02f9ebc',
)
PACKAGES = [f'{DESTINATION}/{name}' for name in NAMES]


class ImportTask:
    def set_editor_properties(self, properties):
        self.properties = properties.copy()

    def get_editor_property(self, name):
        return self.properties[name]


class Material:
    def __init__(self, path):
        self.path = path

    def get_path_name(self):
        return self.path


class Mesh:
    def __init__(self, package, slots):
        self.package = package
        self.slots = slots
        self.set_material = Mock()

    def get_package(self):
        return SimpleNamespace(get_name=lambda: self.package)

    def get_editor_property(self, name):
        if name != 'has_navigation_data':
            raise AttributeError(name)
        return True


class WestConnectorImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reviewed = importer.preflight()

    def setUp(self):
        self.temp = Path(self.enterContext(TemporaryDirectory()))
        self.lease = {'owner': 'codex-gray-london', 'expires_epoch': 1060.}
        self.pie_worlds = []
        self.existing_registry = set()
        self.existing_memory = set()
        self.loaded_meshes = {}
        self.import_assets = Mock(side_effect=self._import_assets)
        self.verify_mesh = Mock(side_effect=lambda _unreal, mesh, *_args, **_kwargs: {'package': mesh.package})
        self.save = Mock(return_value=True)
        self.persist = Mock(side_effect=self._persist)
        self.verify_registry = Mock()
        unreal = SimpleNamespace(
            Paths=SimpleNamespace(project_dir=lambda: str(importer.PROJECT),
                                  convert_relative_path_to_full=lambda path: path),
            UnrealEditorSubsystem=object(),
            get_editor_subsystem=lambda _cls: SimpleNamespace(get_editor_world=object, get_game_world=lambda: None),
            EditorLevelLibrary=SimpleNamespace(get_pie_worlds=lambda _include_dedicated: self.pie_worlds),
            EditorAssetLibrary=SimpleNamespace(does_asset_exist=self.existing_registry.__contains__),
            find_package=lambda path: object() if path in self.existing_memory else None,
            AssetImportTask=ImportTask,
            FbxFactory=object,
            AssetToolsHelpers=SimpleNamespace(get_asset_tools=lambda: SimpleNamespace(import_asset_tasks=self.import_assets)),
            load_asset=lambda path, cls: self.loaded_meshes[path] if cls is Mesh else Material(path),
            MaterialInterface=Material,
            StaticMesh=Mesh,
            EditorLoadingAndSavingUtils=SimpleNamespace(save_packages=self.save),
            MultiUserClientStatics=SimpleNamespace(get_multi_user_connection_status_detail=lambda: 'connected',
                                                  persist_specified_packages=self.persist),
            MultiUserConnectionStatus=SimpleNamespace(CONNECTED='connected'),
        )
        self.enterContext(patch.dict(sys.modules, {'unreal': unreal}))
        for name, value in {
            'preflight': lambda: self.reviewed,
            'read_json': lambda _path: self.lease,
            'time': SimpleNamespace(time=lambda: 1000.),
            'package_file': self._package_file,
            'fbx_options': lambda _unreal: object(),
            'get_slots': lambda mesh: mesh.slots,
            'configure_collision': Mock(),
            'verify_mesh': self.verify_mesh,
            'verify_registry': self.verify_registry,
        }.items():
            self.enterContext(patch.object(importer, name, value))

    def _package_file(self, path):
        return self.temp / f'{path.rsplit("/", 1)[-1]}.uasset'

    def _import_assets(self, tasks):
        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        settings = task.properties
        name = settings['destination_name']
        self.assertIn(name, NAMES)
        self.assertEqual(settings['destination_path'], DESTINATION)
        self.assertFalse(settings['replace_existing'])
        self.assertFalse(settings['save'])
        self.assertEqual(Path(settings['filename']), self.reviewed[name][0])
        package = f'{DESTINATION}/{name}'
        path = f'{package}.{name}'
        self.loaded_meshes[path] = Mesh(package, self.reviewed[name][1]['materials'])
        settings['imported_object_paths'] = [path]

    def _persist(self, packages):
        for path in packages:
            self._package_file(path).touch()

    def assert_no_save(self):
        self.save.assert_not_called()
        self.persist.assert_not_called()
        self.verify_registry.assert_not_called()

    def test_requires_our_live_lease(self):
        for lease in ({'owner': 'another-team', 'expires_epoch': 1060.},
                      {'owner': 'codex-gray-london', 'expires_epoch': 1000.}, {}):
            with self.subTest(lease=lease):
                self.lease = lease
                with self.assertRaisesRegex(RuntimeError, 'lease'):
                    importer.run()
                self.import_assets.assert_not_called()
                self.assert_no_save()

    def test_rejects_pie_before_import(self):
        self.pie_worlds.append(object())
        with self.assertRaisesRegex(RuntimeError, 'no PIE worlds'):
            importer.run()
        self.import_assets.assert_not_called()
        self.assert_no_save()

    def test_rejects_existing_destination_before_any_import(self):
        self.existing_memory.add(PACKAGES[-1])
        with self.assertRaisesRegex(FileExistsError, 'in-memory package'):
            importer.run()
        self.existing_memory.clear()
        self.existing_registry.add(PACKAGES[-1])
        with self.assertRaises(FileExistsError):
            importer.run()
        self.existing_registry.clear()
        self._package_file(PACKAGES[-1]).touch()
        with self.assertRaises(FileExistsError):
            importer.run()
        self.import_assets.assert_not_called()
        self.assert_no_save()

    def test_failed_verification_leaves_all_packages_unsaved(self):
        self.verify_mesh.side_effect = [{'package': PACKAGES[0]}, RuntimeError('geometry verification failed')]
        with self.assertRaisesRegex(RuntimeError, 'geometry verification failed'):
            importer.run()
        self.assertEqual(self.import_assets.call_count, 2)
        self.assert_no_save()

    def test_checks_lease_again_after_verification(self):
        def verify(_unreal, mesh, *_args, **_kwargs):
            if mesh.package == PACKAGES[-1]:
                self.lease['expires_epoch'] = 1000.
            return {'package': mesh.package}

        self.verify_mesh.side_effect = verify
        with self.assertRaisesRegex(RuntimeError, 'lease'):
            importer.run()
        self.assertEqual(self.verify_mesh.call_count, 3)
        self.assert_no_save()

    def test_saves_and_persists_only_the_three_verified_packages(self):
        report = importer.run()
        self.assertEqual(self.verify_mesh.call_count, 3)
        self.save.assert_called_once()
        args, kwargs = self.save.call_args
        self.assertEqual([package.get_name() for package in args[0]], PACKAGES)
        self.assertEqual(kwargs, {'only_dirty': False})
        self.persist.assert_called_once_with(PACKAGES)
        self.verify_registry.assert_called_once_with(sys.modules['unreal'], report['meshes'], destination=DESTINATION)
        self.assertEqual(report['saved_packages'], PACKAGES)
        self.assertTrue(all(self._package_file(path).is_file() for path in PACKAGES))


if __name__ == '__main__':
    unittest.main()
