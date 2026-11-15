"""Offline mocked preservation tests; no network, Git writes or real assets."""
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import subprocess
from types import SimpleNamespace
import unittest
from unittest import mock
import warnings
import zipfile

import preserve_north_market_tenancy_fbx as p


def metadata():
    return {'id': p.ITEM['id'], 'name': p.ITEM['name'], 'expired': False,
            'size_in_bytes': p.ITEM['size'], 'digest': 'sha256:'+p.ITEM['sha256'],
            'workflow_run': {'id': p.ITEM['run'], 'repository_id': 1457160414,
                             'head_repository_id': 1457160414, 'head_branch': 'main',
                             'head_sha': p.ITEM['head_sha']}}


def report(kind, phase):
    model = p.MODELS[kind]
    return {'phase': phase, 'status': 'review_only_no_unreal_approval', 'kind': kind,
            'model': model['name'], 'fbx_sha256': model['sha256'], 'source_obj_sha256': p.SOURCE_OBJ,
            'source_manifest_sha256': p.SOURCE_MANIFEST, 'overlay_obj_sha256': p.OVERLAY_OBJ,
            'combined_obj_sha256': p.COMBINED_OBJ, 'baseline_fbx_sha256': p.BASELINE_FBX,
            'preview_run': 43731156271, 'preview_artifact': 14167854997, 'source_plan_lf_sha256': 'a'*64,
            'source_mtl_sha256': 'b'*64, 'scene_unit': 'metres', 'scene_unit_scale': 1.0,
            'source_axes': '+X entrance, +Z up', 'blender_version': '4.5.3 LTS', 'uv_layer': 'UVMap',
            'normal_repair': None, 'world_pivot_m': [3310.546, 522.412, .2], 'yaw_deg': 24.35984172,
            'facts': {'vertices': model['vertices'], 'polygons': model['polygons'],
                      'slots': ['s'+str(i) for i in range(model['slots'])]}, 'textures': {}}


class MemoryStage:
    def __init__(self):
        self.files = {}

    def __truediv__(self, name):
        parent = self
        class File:
            def open(self, mode):
                if mode != 'xb' or name in parent.files:
                    raise RuntimeError('not-exclusive')
                class Sink(io.BytesIO):
                    def close(self):
                        parent.files[name] = self.getvalue()
                        super().close()
                return Sink()
        return File()


class DummyPath:
    def __init__(self, label):
        self.label = label

    def __str__(self):
        return self.label

    def open(self, mode):
        if mode != 'xb':
            raise ValueError('unexpected mode')
        return io.BytesIO()


class DummyStage:
    def __truediv__(self, name):
        return DummyPath(name)


def fake_archive(corrupt=None, duplicate=None):
    contents = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        with zipfile.ZipFile(contents, 'w', zipfile.ZIP_DEFLATED) as archive:
            for kind, model in p.MODELS.items():
                for phase in ('export', 'verify'):
                    value = json.dumps(report(kind, phase)).encode()
                    archive.writestr(f'{kind}/{phase}.report.json', value)
                name = f"{kind}/{model['name']}.fbx"
                value = (kind+'-fbx').encode()
                archive.writestr(name, value+b'bad' if corrupt == kind else value)
                if duplicate == kind:
                    archive.writestr(name, value)
    contents.seek(0)
    return contents


class PreservationTests(unittest.TestCase):
    def test_context_is_specific_to_hosted_main_and_this_workflow(self):
        env = {'GITHUB_ACTIONS': 'true', 'RUNNER_ENVIRONMENT': 'github-hosted', 'RUNNER_OS': 'Linux',
               'GITHUB_REPOSITORY': p.base.REPO, 'GITHUB_REPOSITORY_ID': '1457160414',
               'GITHUB_REF': 'refs/heads/main', 'GITHUB_WORKFLOW_REF': p.WORKFLOW_REF,
               'GITHUB_SERVER_URL': 'https://github.com', 'GITHUB_API_URL': 'https://api.github.com',
               'GITHUB_SHA': 'a'*40, 'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '1',
               'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_WORKSPACE': str(p.base.ROOT),
               'RUNNER_TEMP': str(Path(p.base.ROOT.anchor)), 'GH_TOKEN': 'mock-token'}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(p.sys, 'platform', 'linux'):
            self.assertEqual(p.context()['sha'], 'a'*40)
            for key, value in (('GITHUB_WORKFLOW_REF', 'other'), ('GITHUB_REF', 'refs/heads/other'),
                               ('RUNNER_ENVIRONMENT', 'self-hosted'), ('GITHUB_EVENT_NAME', 'pull_request')):
                with mock.patch.dict(os.environ, {key: value}), self.assertRaises(RuntimeError):
                    p.context()

    def test_metadata_binds_run_repo_commit_name_and_exact_zip(self):
        p.validate_metadata(metadata())
        for key, value in (('id', 1), ('name', 'other'), ('expired', True), ('size_in_bytes', 1),
                           ('digest', 'sha256:'+'0'*64)):
            changed = metadata()
            changed[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'metadata'):
                p.validate_metadata(changed)
        for key, value in (('id', 1), ('repository_id', 1), ('head_repository_id', 1),
                           ('head_branch', 'other'), ('head_sha', '0'*40)):
            changed = metadata()
            changed['workflow_run'][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'metadata'):
                p.validate_metadata(changed)

    def test_reports_require_both_matching_phases_and_known_geometry(self):
        for kind in p.MODELS:
            old, new = report(kind, 'export'), report(kind, 'verify')
            p.check_reports(kind, old, new)
            for key in ('model', 'fbx_sha256', 'overlay_obj_sha256', 'combined_obj_sha256',
                        'baseline_fbx_sha256', 'source_manifest_sha256', 'preview_run', 'scene_unit_scale'):
                changed = {**new, key: 'bad'}
                with self.subTest(kind=kind, key=key), self.assertRaises(RuntimeError):
                    p.check_reports(kind, old, changed)
            with self.assertRaises(RuntimeError):
                p.check_reports(kind, {**old, 'textures': {'changed': 1}}, new)
            with self.assertRaises(RuntimeError):
                p.check_reports(kind, {**old, 'status': 'changed'}, new)
            with self.assertRaises(RuntimeError):
                p.check_reports(kind, old, {**new, 'facts': {**new['facts'], 'vertices': 1}})

    def test_archive_checks_both_real_fbx_bytes_and_writes_only_two_reports(self):
        models = {key: {**value, 'sha256': hashlib.sha256((key+'-fbx').encode()).hexdigest()}
                  for key, value in p.MODELS.items()}
        with mock.patch.object(p, 'MODELS', models):
            stage = MemoryStage()
            result = p.inspect_archive(fake_archive(), stage)
            self.assertEqual(set(result), {'overlay.verify.report.json', 'complete.verify.report.json'})
            self.assertEqual(set(stage.files), set(result))
            for name, data in stage.files.items():
                self.assertEqual(hashlib.sha256(data).hexdigest(), result[name])
            for kind in models:
                with self.subTest(corrupt=kind), self.assertRaises(RuntimeError):
                    p.inspect_archive(fake_archive(corrupt=kind), MemoryStage())
                with self.subTest(duplicate=kind), self.assertRaises(RuntimeError):
                    p.inspect_archive(fake_archive(duplicate=kind), MemoryStage())

    def test_duplicate_report_fields_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'report-duplicate'):
            json.loads('{"phase":"export","phase":"verify"}', object_pairs_hook=p.unique_pairs)

    def test_push_event_and_workflow_only_single_parent(self):
        sha, before = 'a'*40, 'b'*40
        payload = {'before': before, 'after': sha, 'ref': 'refs/heads/main',
                   'forced': False, 'created': False, 'deleted': False,
                   'repository': {'full_name': p.base.REPO}}
        self.assertEqual(p.push_before(payload, sha), before)
        for key, value in (('after', before), ('forced', True), ('created', True), ('deleted', True),
                           ('ref', 'refs/heads/elsewhere'), ('repository', {'full_name': 'other/repo'})):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                p.push_before({**payload, key: value}, sha)
        parents = (sha+' '+before+'\n').encode()
        paths = p.WORKFLOW.encode()+b'\0'
        p.check_push_shape(sha, before, parents, paths)
        for bad_parents, bad_paths in ((parents+b'c'*40, paths), (parents, paths+b'other\0')):
            with self.assertRaises(RuntimeError):
                p.check_push_shape(sha, before, bad_parents, bad_paths)

    def test_exact_staged_paths_and_existing_head_check(self):
        expected = [p.ZIP_REL, *((p.TARGET_REL/(kind+'.verify.report.json')).as_posix() for kind in p.MODELS)]
        encode = lambda rows: b''.join(row.encode()+b'\0' for row in rows)
        self.assertEqual(p.expected_paths(encode(expected)), sorted(expected))
        for rows in (expected[:-1], expected+['other'], expected+[expected[0]]):
            with self.assertRaises(RuntimeError):
                p.expected_paths(encode(rows))
        with mock.patch.object(p.base, 'remote_head', return_value='b'*40):
            with self.assertRaisesRegex(RuntimeError, 'remote-advanced'):
                p.require_head({}, 'a'*40)

    def test_pointer_is_exact_and_readback_uses_isolated_lfs_options(self):
        pointer = p.base.pointer_bytes(p.ITEM)
        p.base.check_pointer(pointer, p.ITEM)
        with self.assertRaises(RuntimeError):
            p.base.check_pointer(pointer.replace(p.ITEM['sha256'].encode(), b'0'*64), p.ITEM)
        store = Path('/private/readback')
        options = p.base.readback_options(store)
        self.assertIn('lfs.storage='+str(store), options)
        self.assertIn('lfs.basictransfersonly=true', options)
        self.assertIn('lfs.skipdownloaderrors=false', options)
        self.assertEqual(p.base.smudge_file_ceiling(p.ITEM['size']), 64*2**20)

    def test_smudge_kills_and_reaps_its_process_group_on_timeout_and_error(self):
        pointer = p.base.pointer_bytes(p.ITEM)
        for timeout in (True, False):
            process = mock.Mock(pid=123, returncode=9)
            if timeout:
                process.communicate.side_effect = subprocess.TimeoutExpired('mock', 60)
            with self.subTest(timeout=timeout), mock.patch.object(p.os, 'open', return_value=42), \
                    mock.patch.object(p.os, 'fdopen', return_value=io.BytesIO()), \
                    mock.patch.object(p.os, 'killpg', create=True) as kill, \
                    mock.patch.object(p.signal, 'SIGKILL', 9, create=True), \
                    mock.patch.object(p.subprocess, 'Popen', return_value=process), \
                    mock.patch.object(p.base, 'report_smudge_error'):
                with self.assertRaises(subprocess.TimeoutExpired if timeout else RuntimeError):
                    p.smudge({}, DummyStage(), Path('/private/readback'), pointer)
                kill.assert_called_once_with(123, signal.SIGKILL)
                process.wait.assert_called_once_with(timeout=5)

    def test_readback_rejects_wrong_or_oversized_output_and_cache(self):
        pointer = p.base.pointer_bytes(p.ITEM)
        wanted = (p.ITEM['size'], p.ITEM['sha256'])
        git_results = [SimpleNamespace(stdout=b'lfs environment'), SimpleNamespace(stdout=pointer)]
        for hashes in ((wanted, wanted), ((p.ITEM['size'], '0'*64),),
                       (wanted, (p.ITEM['size']+1, p.ITEM['sha256'])),
                       (RuntimeError('file-size'),), (wanted, RuntimeError('file-size'))):
            with self.subTest(hashes=hashes), mock.patch.object(Path, 'mkdir'), \
                    mock.patch.object(Path, 'exists', return_value=False), \
                    mock.patch.object(Path, 'is_symlink', return_value=False), \
                    mock.patch.object(p.base, 'git', side_effect=git_results), \
                    mock.patch.object(p.base, 'check_readback_environment'), \
                    mock.patch.object(p.base, 'sha_file', side_effect=hashes), \
                    mock.patch.object(p, 'smudge', return_value=Path('/private/output')):
                if hashes == (wanted, wanted):
                    p.readback({}, Path('/private/stage'), 'a'*40)
                else:
                    with self.assertRaises(RuntimeError):
                        p.readback({}, Path('/private/stage'), 'a'*40)


if __name__ == '__main__':
    unittest.main()
