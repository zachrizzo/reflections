"""Synthetic checks for the read-only Gray London package audit."""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import audit_london_package as audit


class PackageAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp_parent = Path(tempfile.gettempdir()).resolve()
        self.temp = tempfile.TemporaryDirectory(prefix='london-package-audit-', dir=str(self.temp_parent))
        self.root = Path(self.temp.name).resolve()
        self.assertEqual(self.root.parent, self.temp_parent)
        self.assertTrue(self.root.name.startswith('london-package-audit-'))

        def cleanup():
            target = Path(self.temp.name)
            if target.is_symlink() or target.resolve() != self.root or self.root.parent != self.temp_parent:
                raise RuntimeError('Refusing cleanup of a redirected package-audit test directory')
            self.temp.cleanup()
        self.addCleanup(cleanup)

        self.base = 1_700_000_000_000_000_000
        self.write('Config/DefaultEngine.ini',
                   f'[/Script/EngineSettings.GameMapsSettings]\nGameDefaultMap={audit.MAP_OBJECT}\n'
                   f'EditorStartupMap={audit.MAP_OBJECT}\nGlobalDefaultGameMode={audit.GAME_MODE}\n')
        self.write('Config/DefaultGame.ini',
                   f'[/Script/UnrealEd.ProjectPackagingSettings]\n+MapsToCook=(FilePath="{audit.MAP_PACKAGE}")\n'
                   f'[/Script/reflections.ReflectionsGameFlowSubsystem]\nNewGameMap={audit.MAP_OBJECT}\n')
        self.write('ArtDirection/Packaging/PackageJamBuild.bat',
                   f'set ARGS=BuildCookRun -cook -map={audit.MAP_PACKAGE} -stage\n')
        self.write('reflections.uproject', '{}')
        self.write('Binaries/Win64/reflections.target', json.dumps({
            'TargetName': 'reflections', 'TargetType': 'Game', 'Platform': 'Win64', 'Configuration': 'Development'}))
        self.write('Binaries/Win64/reflections.exe', b'game-target')
        self.write('Saved/JamBuild/Windows/reflections.exe', b'launcher')
        self.write('Saved/JamBuild/Windows/reflections/Binaries/Win64/reflections.exe', b'game-target')
        for path in audit.RUNTIME_SOURCE:
            self.write(path, '// source\n')
        self.write('Content/GrayLondon/Maps/GrayLondon_Geodata.umap', b'map')
        for folder in audit.WORLD_PARTITION:
            self.write(f'{folder}/part.uasset', b'partition')
        for name in audit.PILOT_ASSETS:
            self.write(f'Content/{audit.PILOT}/{name}.uasset', b'asset')
        for name in ('global.utoc', 'global.ucas', 'reflections-Windows.pak',
                     'reflections-Windows.utoc', 'reflections-Windows.ucas'):
            self.write(f'Saved/JamBuild/Windows/reflections/Content/Paks/{name}', b'container')
        self.manifest = self.root / audit.STAGE / 'Manifest_UFSFiles_Win64.txt'
        entries = ['reflections/Content/GrayLondon/Maps/GrayLondon_Geodata.umap',
                   'reflections/Content/GrayLondon/Maps/GrayLondon_Geodata/_Generated_/cell.umap']
        entries.extend(f'reflections/Content/{audit.PILOT}/{name}.uasset' for name in audit.PILOT_ASSETS)
        self.write(self.manifest.relative_to(self.root), ''.join(entry + '\t2026-01-01\n' for entry in entries))
        for path in self.root.rglob('*'):
            if path.is_file():
                self.touch(path, self.at(1))
        self.touch(self.root / 'Binaries/Win64/reflections.exe', self.at(10))
        self.touch(self.root / audit.STAGE / 'reflections/Binaries/Win64/reflections.exe', self.at(10))
        self.touch(self.manifest, self.at(20))

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode('utf-8') if isinstance(content, str) else content)
        return path

    @staticmethod
    def touch(path, value):
        os.utime(path, ns=(value, value))

    def at(self, seconds):
        # Whole seconds survive Windows filesystem timestamp granularity.
        return self.base + seconds * 1_000_000_000

    def codes(self):
        result = audit.audit(self.root)
        return result, [finding['code'] for finding in result['failures']]

    def test_clean_synthetic_evidence_is_inconclusive_not_proven_fresh(self):
        before = {path: (path.stat().st_size, path.stat().st_mtime_ns)
                  for path in self.root.rglob('*') if path.is_file()}
        result, codes = self.codes()
        after = {path: (path.stat().st_size, path.stat().st_mtime_ns)
                 for path in self.root.rglob('*') if path.is_file()}
        self.assertEqual(result['status'], 'inconclusive')
        self.assertEqual(codes, [])
        self.assertTrue(all(result['details']['configured_gray_london_map'].values()))
        self.assertEqual(before, after)
        self.assertTrue(any('do not prove freshness' in line for line in result['limitations']))
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = audit.main(['--project', str(self.root), '--json'])
        self.assertEqual(exit_code, 2)
        self.assertEqual(json.loads(output.getvalue())['status'], 'inconclusive')

    def test_newer_source_flags_game_executable(self):
        self.touch(self.root / audit.RUNTIME_SOURCE[0], self.at(30))
        result, codes = self.codes()
        self.assertEqual(result['status'], 'failed')
        self.assertIn('game_executable_stale_indicator', codes)
        self.assertIn(audit.RUNTIME_SOURCE[0].replace('/', os.sep), result['details']['newer_game_input_examples'])
        self.assertIn(audit.RUNTIME_SOURCE[0], result['details']['newer_replacement_runtime'])

    def test_newer_project_descriptor_flags_game_executable(self):
        self.touch(self.root / 'reflections.uproject', self.at(30))
        _, codes = self.codes()
        self.assertIn('game_executable_stale_indicator', codes)

    def test_staged_game_older_or_different_size_is_rejected(self):
        staged = self.root / audit.STAGE / 'reflections/Binaries/Win64/reflections.exe'
        self.touch(staged, self.at(5))
        _, codes = self.codes()
        self.assertIn('staged_executable_stale', codes)
        staged.write_bytes(b'different size')
        self.touch(staged, self.at(10))
        _, codes = self.codes()
        self.assertIn('staged_executable_stale', codes)

    def test_missing_required_manifest_entry_is_named(self):
        target = audit.PILOT_ASSETS[0] + '.uasset'
        lines = self.manifest.read_text(encoding='utf-8').splitlines()
        self.manifest.write_text('\n'.join(line for line in lines if target not in line) + '\n', encoding='utf-8')
        result, codes = self.codes()
        self.assertIn('missing_staged_entry', codes)
        self.assertEqual(len(result['details']['missing_staged_entries']), 1)
        self.assertTrue(result['details']['missing_staged_entries'][0].endswith(target))

    def test_missing_world_partition_cells_fail_closed(self):
        lines = self.manifest.read_text(encoding='utf-8').splitlines()
        self.manifest.write_text('\n'.join(line for line in lines if '/_Generated_/' not in line) + '\n', encoding='utf-8')
        _, codes = self.codes()
        self.assertIn('missing_staged_cells', codes)

    def test_newer_partition_actor_and_pilot_asset_flag_stage(self):
        self.touch(self.root / audit.WORLD_PARTITION[0] / 'part.uasset', self.at(30))
        self.touch(self.root / 'Content' / audit.PILOT / (audit.PILOT_ASSETS[0] + '.uasset'), self.at(31))
        result, codes = self.codes()
        self.assertIn('staged_content_stale_indicator', codes)
        self.assertEqual(result['details']['newer_stage_input_count'], 2)

    def test_missing_or_wrong_config_and_ambiguous_cook_maps_fail(self):
        engine = self.root / 'Config/DefaultEngine.ini'
        engine.write_text(engine.read_text(encoding='utf-8').replace(audit.MAP_OBJECT, '/Game/Other/Map', 1), encoding='utf-8')
        _, codes = self.codes()
        self.assertIn('wrong_map_config', codes)
        engine.write_text(f'[/Script/EngineSettings.GameMapsSettings]\nGameDefaultMap={audit.MAP_OBJECT}\n'
                          f'GameDefaultMap={audit.MAP_OBJECT}\nEditorStartupMap={audit.MAP_OBJECT}\n', encoding='utf-8')
        _, codes = self.codes()
        self.assertIn('wrong_map_config', codes)
        game = self.root / 'Config/DefaultGame.ini'
        game.write_text(game.read_text(encoding='utf-8').replace(
            '+MapsToCook=', '+MapsToCook=(FilePath="/Game/Other/Map")\n+MapsToCook='), encoding='utf-8')
        _, codes = self.codes()
        self.assertIn('wrong_map_config', codes)

    def test_missing_wrong_or_duplicate_game_mode_fails_closed(self):
        engine = self.root / 'Config/DefaultEngine.ini'
        prefix = (f'[/Script/EngineSettings.GameMapsSettings]\nGameDefaultMap={audit.MAP_OBJECT}\n'
                  f'EditorStartupMap={audit.MAP_OBJECT}\n')
        for entries in ('', 'GlobalDefaultGameMode=/Script/Other.GameMode\n',
                        f'GlobalDefaultGameMode={audit.GAME_MODE}\nGlobalDefaultGameMode={audit.GAME_MODE}\n'):
            with self.subTest(entries=entries):
                engine.write_text(prefix + entries, encoding='utf-8')
                result, codes = self.codes()
                self.assertIn('wrong_game_mode', codes)
                self.assertFalse(result['details']['configured_gray_london_map']['game_mode'])

    def test_windows_reparse_point_and_symlink_are_rejected(self):
        class FakePath:
            def __init__(self, mode, attributes=None):
                self.info = SimpleNamespace(st_mode=mode)
                if attributes is not None:
                    self.info.st_file_attributes = attributes

            def lstat(self):
                return self.info

        with patch.object(audit.os, 'name', 'nt'):
            self.assertTrue(audit.is_redirected(FakePath(stat.S_IFDIR, 0x400)))  # junction/reparse point
            self.assertTrue(audit.is_redirected(FakePath(stat.S_IFLNK, 0)))
            self.assertFalse(audit.is_redirected(FakePath(stat.S_IFDIR, 0)))
            with self.assertRaises(OSError):
                audit.is_redirected(FakePath(stat.S_IFDIR))

    def test_junction_in_source_or_partition_path_fails_closed(self):
        nested = self.root / audit.WORLD_PARTITION[0] / 'nested'
        nested.mkdir()
        real_check = audit.is_redirected
        junctions = (self.root / 'Source', self.root / 'Source/reflections',
                     self.root / 'Content/__ExternalActors__/GrayLondon',
                     self.root / audit.WORLD_PARTITION[0], nested)
        for junction in junctions:
            with self.subTest(junction=junction):
                def redirected(path):
                    return path == junction or real_check(path)
                with patch.object(audit, 'is_redirected', side_effect=redirected):
                    result, codes = self.codes()
                self.assertEqual(result['status'], 'failed')
                self.assertIn('unreadable_evidence', codes)

    def test_packaging_map_override_is_rejected(self):
        self.write('ArtDirection/Packaging/PackageJamBuild.bat', 'set ARGS=BuildCookRun -map=/Game/Other/Map\n')
        _, codes = self.codes()
        self.assertIn('wrong_package_map', codes)

    def test_missing_manifest_container_receipt_and_partition_fail_closed(self):
        targets = (
            'Saved/JamBuild/Windows/Manifest_UFSFiles_Win64.txt',
            'Saved/JamBuild/Windows/reflections/Content/Paks/reflections-Windows.ucas',
            'Binaries/Win64/reflections.target',
            audit.WORLD_PARTITION[1] + '/part.uasset',
        )
        for relative in targets:
            with self.subTest(path=relative):
                path = self.root / relative
                previous = path.read_bytes()
                previous_time = path.stat().st_mtime_ns
                path.unlink()
                result, codes = self.codes()
                self.assertEqual(result['status'], 'failed')
                self.assertIn('missing_evidence', codes)
                path.write_bytes(previous)
                self.touch(path, previous_time)

    def test_corrupt_manifest_and_target_receipt_fail_closed(self):
        self.manifest.write_bytes(b'\xff')
        self.write('Binaries/Win64/reflections.target', '{not json')
        _, codes = self.codes()
        self.assertGreaterEqual(codes.count('unreadable_evidence'), 2)

    def test_missing_project_is_failure(self):
        result = audit.audit(self.root / 'not-a-project')
        self.assertEqual(result['status'], 'failed')
        self.assertTrue(result['failures'])


if __name__ == '__main__':
    unittest.main()
