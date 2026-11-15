"""Exercise resumable city exports with a fake editor and Asset Registry."""

import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import time
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

import batch_export_geodata_unreal as batch


TILE_A = 'Tile_p03_p00'
TILE_B = 'Tile_p03_p01'
OWNER = 'codex-gray-london'


class Properties:
    def __init__(self, **properties):
        self.properties = properties

    def get_editor_property(self, name):
        return self.properties[name]


class Vector:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class Package:
    def __init__(self, name):
        self.name = name

    def get_name(self):
        return self.name


class Mesh(Properties):
    def __init__(self, package, name, role):
        self.package, self.name = package, name
        self.slots = ['GL_Facade', 'GL_Roof', 'GL_Road'] if role == 'tile' else ['GL_Shop']
        self.materials = list(self.slots)
        super().__init__(static_materials=[Properties(material_slot_name=slot) for slot in self.slots])

    def get_path_name(self):
        return f'{self.package}.{self.name}'

    def get_num_sections(self, _lod):
        return len(self.slots)

    def get_num_triangles(self, _lod):
        return len(self.slots)

    def get_bounds(self):
        return SimpleNamespace(origin=Vector(0, 0, 0), box_extent=Vector(100, 200, 300))

    def get_material(self, index):
        return SimpleNamespace(get_name=lambda: self.materials[index])


class Actor:
    def __init__(self, label, path, package, mesh):
        self.label, self.path, self.package, self.mesh = label, path, package, mesh
        self.location = Vector(300000, 0, 0)
        self.rotation = SimpleNamespace(pitch=0, yaw=0, roll=0)
        self.scale = Vector(1, 1, 1)

    def get_actor_label(self):
        return self.label

    def get_path_name(self):
        return self.path

    def get_package(self):
        return Package(self.package)

    def get_components_by_class(self, _type):
        return [self]

    def get_editor_property(self, name):
        if name != 'static_mesh':
            raise KeyError(name)
        return self.mesh

    def get_world_location(self):
        return self.location

    def get_world_rotation(self):
        return self.rotation

    def get_world_scale(self):
        return self.scale


def guid(value):
    return SimpleNamespace(to_string=lambda: f'{value:032X}')


def descriptor(label, path, package, number):
    class_ref = SimpleNamespace(get_path_name=lambda: '/Script/Engine.StaticMeshActor')
    box = SimpleNamespace(min=Vector(299900, -200, -300), max=Vector(300100, 200, 300))
    return Properties(label=label, name='TestActor', actor_package=package, actor_path=path,
                      guid=guid(number), instance_guid=guid(number), native_class=class_ref,
                      folder_path='Test', bounds=box, runtime_grid='None', is_spatially_loaded=True,
                      actor_is_editor_only=False, data_layer_assets=[])


def asset(name, package):
    return Properties(asset_name=name, package_name=package,
                      asset_class_path=Properties(package_name='/Script/Engine', asset_name='StaticMesh'))


class Registry:
    def __init__(self):
        self.assets = {batch.TILE_ROOT: [], batch.OVERLAY_ROOT: []}
        self.dependencies = {}
        self.loading = False

    def is_loading_assets(self):
        return self.loading

    def get_assets_by_path(self, root, _recursive, _disk_only):
        return self.assets[root]

    def get_dependencies(self, package, _options):
        return self.dependencies.get(package)


class Exporter:
    def __init__(self):
        self.calls = []
        self.callback = None

    def export_to_gltf(self, mesh, destination, _options, _selection):
        self.calls.append(mesh.get_path_name())
        document = {'nodes': [{'mesh': 0}], 'meshes': [{'primitives': []}], 'accessors': [],
                    'materials': [{'name': name} for name in mesh.materials],
                    'buffers': [{'byteLength': 4}]}
        for index in range(len(mesh.slots)):
            document['meshes'][0]['primitives'].append({'indices': index, 'material': index})
            document['accessors'].append({'count': 3})
        raw = json.dumps(document, separators=(',', ':')).encode()
        raw += b' ' * (-len(raw) % 4)
        data = (struct.pack('<4sIII4s', b'glTF', 2, 32 + len(raw), len(raw), b'JSON') + raw
                + struct.pack('<I4s', 4, b'BIN\x00') + b'\x00' * 4)
        Path(destination).write_bytes(data)
        if self.callback:
            self.callback()
        return Properties(errors=[])


def verify_export(path, slots, mesh):
    with path.open('rb') as stream:
        magic, version, total, size, kind = struct.unpack('<4sIII4s', stream.read(20))
        document = json.loads(stream.read(size))
    if (magic, version, total, kind) != (b'glTF', 2, path.stat().st_size, b'JSON'):
        raise RuntimeError('bad GLB')
    counts = [document['accessors'][p['indices']]['count'] // 3
              for p in document['meshes'][0]['primitives']]
    if len(counts) != len(slots) or sum(counts) != mesh.get_num_triangles(0):
        raise RuntimeError('bad sections')
    return counts


class CityBatchTests(unittest.TestCase):
    def setUp(self):
        self.project = Path(self.enterContext(TemporaryDirectory())).resolve()
        self.saved = self.project / 'Saved'
        self.saved.mkdir()
        self.enterContext(patch.object(batch, 'PROJECT', self.project))
        self.enterContext(patch.object(batch, 'memory_available', lambda: (8 * 1024**3, 16 * 1024**3)))
        self.lease = {'owner': OWNER, 'acquired_epoch': 1, 'expires_epoch': time.time() + 3600}
        (self.saved / 'PIE_LOCK.json').write_text(json.dumps(self.lease), encoding='utf-8')
        self.registry, self.exporter = Registry(), Exporter()
        self.descs, self.actors, self.meshes, self.dirty = [], [], {}, []
        self.world = SimpleNamespace(get_path_name=lambda: batch.MAP + '.GrayLondon_Geodata')
        self.editor = SimpleNamespace(get_editor_world=lambda: self.world, get_game_world=lambda: None)
        self.pie = []
        self.unreal = ModuleType('unreal')
        self.unreal.Paths = SimpleNamespace(project_dir=lambda: str(self.project),
                                            project_saved_dir=lambda: str(self.saved),
                                            convert_relative_path_to_full=lambda path: path)
        self.unreal.EditorLevelLibrary = SimpleNamespace(get_pie_worlds=lambda _dedicated: self.pie)
        self.unreal.UnrealEditorSubsystem = object()
        self.unreal.EditorActorSubsystem = object()
        self.unreal.get_editor_subsystem = lambda cls: self.editor if cls == self.unreal.UnrealEditorSubsystem else SimpleNamespace(
            get_all_level_actors=lambda: self.actors)
        self.unreal.WorldPartitionBlueprintLibrary = SimpleNamespace(get_actor_descs=lambda: self.descs)
        self.unreal.EditorLoadingAndSavingUtils = SimpleNamespace(get_dirty_map_packages=lambda: self.dirty,
                                                                  get_dirty_content_packages=lambda: [])
        self.unreal.AssetRegistryHelpers = SimpleNamespace(get_asset_registry=lambda: self.registry)
        self.unreal.AssetRegistryDependencyOptions = lambda **kwargs: kwargs
        self.unreal.EditorAssetLibrary = SimpleNamespace(load_asset=lambda package: self.meshes.get(package))
        self.unreal.StaticMesh, self.unreal.StaticMeshComponent = Mesh, Actor
        self.unreal.GLTFMaterialBakeMode = SimpleNamespace(DISABLED='disabled')
        self.unreal.GLTFExportOptions = lambda: SimpleNamespace(set_editor_properties=lambda _props: None)
        self.unreal.GLTFExporter = self.exporter
        helper = ModuleType('export_geodata_tiles_unreal')
        helper.verify_export = verify_export
        self.enterContext(patch.dict('sys.modules', {'unreal': self.unreal, 'export_geodata_tiles_unreal': helper}))

    def add(self, name, role='tile', loaded=False):
        root = batch.TILE_ROOT if role == 'tile' else batch.OVERLAY_ROOT
        package = f'{root}/{name}'
        directory = self.project / 'Content' / root.removeprefix('/Game/')
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f'{name}.uasset').write_bytes(f'asset:{role}:{name}'.encode())
        self.registry.assets[root].append(asset(name, package))
        label = f'OSM {name}' if role == 'tile' else f'Anonymous shops {name}'
        actor_package = batch.ACTOR_ROOT + f'{len(self.descs):02d}/{name}'
        actor_file = self.project / 'Content' / actor_package.removeprefix('/Game/')
        actor_file.parent.mkdir(parents=True, exist_ok=True)
        actor_file.with_suffix('.uasset').write_bytes(f'actor:{role}:{name}'.encode())
        path = batch.MAP + f'.GrayLondon_Geodata:PersistentLevel.{role}_{name}'
        desc = descriptor(label, path, actor_package, len(self.descs) + 1)
        self.descs.append(desc)
        self.registry.dependencies[actor_package] = ['/Script/Engine', package]
        mesh = Mesh(package, name, role)
        self.meshes[package] = mesh
        if loaded:
            self.actors.append(Actor(label, path, actor_package, mesh))
        return desc

    def test_missing_overlay_is_valid_but_unloaded_transform_is_never_trusted(self):
        self.add(TILE_A)
        summary = batch.run_batch(OWNER, batch_size=1)
        self.assertEqual((summary['tile_count'], summary['without_overlay_count']), (1, 1))
        result = Path(summary['completed_now'][0]['result'])
        report = json.loads(result.read_text())
        transform = report['roles']['tile']['transform']
        self.assertEqual(transform['source'], 'descriptor_bounds_hypothesis')
        self.assertFalse(transform['rotation_scale_verified'])
        self.assertTrue(transform['requires_live_confirmation'])
        self.assertTrue((result.parent / f'{TILE_A}.unverified.json').is_file())
        self.assertFalse((result.parent / f'{TILE_A}.asset.json').exists())
        self.assertEqual(len(list((self.saved / 'CityPCG').rglob(f'{TILE_A}.glb'))), 1)

    def test_loaded_tile_and_overlay_still_require_independent_section_proof(self):
        self.add(TILE_A, loaded=True)
        self.add(TILE_A, 'overlay', loaded=True)
        summary = batch.run_batch(OWNER, batch_size=1)
        result = Path(summary['completed_now'][0]['result'])
        report = json.loads(result.read_text())
        self.assertFalse(report['legacy_sidecar_eligible'])
        sidecar = json.loads((result.parent / f'{TILE_A}.unverified.json').read_text())
        self.assertEqual(sidecar['transforms']['tile']['origin_m'], [3000., 0., 0.])
        self.assertEqual(sidecar['transforms']['overlay']['source'], 'loaded_actor_component')
        self.assertTrue(sidecar['section_mapping']['tile']['names_unique_and_same_order'])
        self.assertTrue(sidecar['requires_section_mapping_verification'])
        self.assertFalse(sidecar['requires_live_transform_confirmation'])
        self.assertFalse((result.parent / f'{TILE_A}.assets.json').exists())
        self.assertFalse((result.parent / f'{TILE_A}.asset.json').exists())
        self.assertEqual(len(self.exporter.calls), 2)

    def test_duplicate_materials_never_prove_section_mapping(self):
        self.add(TILE_A, loaded=True)
        self.meshes[f'{batch.TILE_ROOT}/{TILE_A}'].materials = ['shared', 'shared', 'unique']
        result = Path(batch.run_batch(OWNER, batch_size=1)['completed_now'][0]['result'])
        mapping = json.loads(result.read_text())['roles']['tile']['section_mapping']
        self.assertFalse(mapping['names_unique_and_same_order'])
        self.assertFalse(mapping['verified'])
        self.assertTrue(mapping['requires_independent_confirmation'])

    def test_resume_does_not_overwrite_and_detects_tampering(self):
        self.add(TILE_A)
        first = batch.run_batch(OWNER, batch_size=1)
        result = Path(first['completed_now'][0]['result'])
        second = batch.run_batch(OWNER, batch_size=1)
        self.assertEqual(second['already_complete'], [TILE_A])
        self.assertEqual(len(self.exporter.calls), 1)
        mesh = result.parent / f'{TILE_A}.glb'
        mesh.write_bytes(b'tampered')
        blocked = batch.run_batch(OWNER, batch_size=1)
        self.assertIn('missing or changed', blocked['blocked'][0]['reason'])
        self.assertEqual(mesh.read_bytes(), b'tampered')
        self.assertEqual(len(self.exporter.calls), 1)

    def test_replaced_source_is_not_silently_skipped_on_resume(self):
        self.add(TILE_A)
        batch.run_batch(OWNER, batch_size=1)
        source = self.project / 'Content/GrayLondon/Geodata/Tiles' / f'{TILE_A}.uasset'
        source.write_bytes(b'different asset revision')
        result = batch.run_batch(OWNER, batch_size=1)
        self.assertIn('source identity changed', result['blocked'][0]['reason'])
        self.assertEqual(len(self.exporter.calls), 1)

    def test_moved_loaded_source_is_not_silently_skipped_on_resume(self):
        self.add(TILE_A, loaded=True)
        first = batch.run_batch(OWNER, batch_size=1)
        original = Path(first['completed_now'][0]['result'])
        self.actors[0].location.x += 50
        resumed = batch.run_batch(OWNER, batch_size=1)
        self.assertIn('source transform changed', resumed['blocked'][0]['reason'])
        self.assertEqual(len(self.exporter.calls), 1)
        self.assertEqual(json.loads(original.read_text())['roles']['tile']['transform']['origin_m'],
                         [3000., 0., 0.])

    def test_source_loading_state_change_requires_review_on_resume(self):
        self.add(TILE_A, loaded=True)
        batch.run_batch(OWNER, batch_size=1)
        self.actors.clear()
        resumed = batch.run_batch(OWNER, batch_size=1)
        self.assertIn('source identity changed', resumed['blocked'][0]['reason'])
        self.assertEqual(len(self.exporter.calls), 1)

    def test_existing_failure_does_not_starve_later_tiles(self):
        self.add(TILE_A)
        self.add(TILE_B)
        directory = self.saved / 'CityPCG/CitywideTileExports' / TILE_A
        directory.mkdir(parents=True)
        (directory / 'failure-earlier.json').write_text('{}')
        result = batch.run_batch(OWNER, batch_size=1)
        self.assertEqual([row['tile'] for row in result['skipped_failures']], [TILE_A])
        self.assertEqual([row['tile'] for row in result['completed_now']], [TILE_B])

    def test_duplicate_descriptor_and_ambiguous_dependency_fail_before_export(self):
        original = self.add(TILE_A)
        self.descs.append(original)
        result = batch.run_batch(OWNER, batch_size=1)
        self.assertIn('exactly one', result['blocked'][0]['reason'])
        self.assertEqual(self.exporter.calls, [])
        self.descs.pop()
        package = original.get_editor_property('actor_package')
        self.registry.dependencies[package].append(f'{batch.TILE_ROOT}/{TILE_B}')
        result = batch.run_batch(OWNER, batch_size=1, retry_failed=True)
        self.assertIn('exact hard geodata dependency', result['blocked'][0]['reason'])
        self.assertEqual(self.exporter.calls, [])

    def test_changed_lease_stops_before_publishing_partial_mesh(self):
        self.add(TILE_A)
        self.exporter.callback = lambda: (self.saved / 'PIE_LOCK.json').write_text(json.dumps({
            **self.lease, 'owner': 'another-session'}), encoding='utf-8')
        with self.assertRaises(batch.SessionError):
            batch.run_batch(OWNER, batch_size=1)
        self.assertEqual(list((self.saved / 'CityPCG').rglob(f'{TILE_A}.glb')), [])
        self.assertEqual(len(list((self.saved / 'CityPCGBatchStaging').rglob('tile.glb'))), 1)

    def test_other_owner_pie_and_low_memory_are_rejected(self):
        self.add(TILE_A)
        with self.assertRaises(batch.SessionError):
            batch.run_batch('someone-else', batch_size=1)
        self.pie.append(object())
        with self.assertRaises(batch.SessionError):
            batch.run_batch(OWNER, batch_size=1)
        self.pie.clear()
        with patch.object(batch, 'memory_available', lambda: (1, 1)):
            with self.assertRaises(batch.SessionError):
                batch.run_batch(OWNER, batch_size=1)
        self.assertEqual(self.exporter.calls, [])

    def test_disk_registry_disagreement_and_orphan_overlay(self):
        self.add(TILE_A)
        self.add(TILE_B, 'overlay')
        result = batch.run_batch(OWNER, batch_size=1)
        self.assertEqual(result['orphan_overlay_assets'], [TILE_B])
        extra = self.project / 'Content/GrayLondon/Geodata/Tiles' / f'{TILE_B}.uasset'
        extra.write_bytes(b'not registered')
        with self.assertRaisesRegex(RuntimeError, 'inventories disagree'):
            batch.run_batch(OWNER, batch_size=1)

    def test_live_actor_nonidentity_transform_never_gets_legacy_sidecar(self):
        self.add(TILE_A, loaded=True)
        self.actors[0].rotation.yaw = 90
        result = batch.run_batch(OWNER, batch_size=1)
        path = Path(result['completed_now'][0]['result'])
        report = json.loads(path.read_text())
        self.assertFalse(report['legacy_sidecar_eligible'])
        self.assertTrue(report['roles']['tile']['transform']['rotation_scale_verified'])
        self.assertFalse(report['roles']['tile']['transform']['compatible_translation_only'])
        self.assertTrue((path.parent / f'{TILE_A}.unverified.json').exists())


if __name__ == '__main__':
    unittest.main()
