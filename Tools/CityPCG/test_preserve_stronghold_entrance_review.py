"""Mocked offline stronghold preservation tests; no network or real assets."""
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
from types import SimpleNamespace
import unittest
from unittest import mock
import warnings
import zipfile

import preserve_stronghold_entrance_review as p


def metadata():
    return {'id': p.ITEM['id'], 'name': p.ITEM['name'], 'expired': False,
            'size_in_bytes': p.ITEM['size'], 'digest': 'sha256:'+p.ITEM['sha256'],
            'workflow_run': {'id': p.ITEM['run'], 'repository_id': 1457160414,
                             'head_repository_id': 1457160414, 'head_branch': 'main',
                             'head_sha': p.ITEM['head_sha']}}


def synthetic_bundle():
    glbs = {path: (path+' mock geometry').encode() for path in p.GLBS}
    hashes = {path: hashlib.sha256(data).hexdigest() for path, data in glbs.items()}
    png = b'\x89PNG\r\n\x1a\n'+struct.pack('>I', 13)+b'IHDR'+struct.pack('>II', 960, 540)+b'mock'
    images = {name: png+name.encode() for name in p.FILES if name.endswith('.png')}
    image_hashes = {name: hashlib.sha256(data).hexdigest() for name, data in images.items()}
    facts = lambda count: {'triangles': count, 'material_count': 3, 'bounds_m': [[-1, -2, 0], [1, 2, 3]]}
    build = {'status': 'illustrative_source_review_not_in_game', 'corridor_box_m': p.CORRIDOR,
             'corridor_result': 'no source triangle surface intersects the box', 'preview_sha256': image_hashes,
             'assets': {}, 'scenes': {}}
    verify = {'status': 'review_only_clean_glb_reimport', 'corridor_box_m': p.CORRIDOR, 'assets': {}}
    for path, digest in hashes.items():
        name = Path(path).stem
        evidence = {'sha256': digest, 'facts': facts(10366 if name.startswith('StrongholdEntrance_') else 12)}
        verify['assets'][name] = evidence
        if name.startswith('StrongholdEntrance_'):
            build['scenes'][name.rsplit('_', 1)[1].lower()] = evidence
        else:
            build['assets'][name] = evidence
    files = {**images, 'build.report.json': json.dumps(build).encode(), 'verify.report.json': json.dumps(verify).encode()}
    pins = {name: (len(data), hashlib.sha256(data).hexdigest()) for name, data in files.items()}
    return glbs, hashes, files, pins, build, verify


def make_zip(glbs, files, corrupt=None, duplicate=None):
    result = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        with zipfile.ZipFile(result, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, data in {**glbs, **files}.items():
                archive.writestr(name, data+b'bad' if name == corrupt else data)
                if name == duplicate:
                    archive.writestr(name, data)
    result.seek(0)
    return result


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
    def __init__(self, name): self.name = name
    def __str__(self): return self.name
    def open(self, mode):
        if mode != 'xb': raise ValueError('unexpected mode')
        return io.BytesIO()


class DummyStage:
    def __truediv__(self, name): return DummyPath(name)


class StrongholdPreservationTests(unittest.TestCase):
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

    def test_metadata_binds_exact_run_commit_repository_and_zip(self):
        p.validate_metadata(metadata())
        for key, value in (('id', 1), ('name', 'other'), ('expired', True), ('size_in_bytes', 1),
                           ('digest', 'sha256:'+'0'*64)):
            changed = metadata(); changed[key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError): p.validate_metadata(changed)
        for key, value in (('id', 1), ('repository_id', 1), ('head_repository_id', 1),
                           ('head_branch', 'other'), ('head_sha', '0'*40)):
            changed = metadata(); changed['workflow_run'][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError): p.validate_metadata(changed)

    def test_archive_validates_all_assets_and_copies_only_labeled_images_and_reports(self):
        glbs, hashes, files, pins, _, _ = synthetic_bundle()
        with mock.patch.object(p, 'GLBS', hashes), mock.patch.object(p, 'FILES', pins):
            stage = MemoryStage()
            result = p.inspect_archive(make_zip(glbs, files), stage)
            self.assertEqual(set(result), set(files))
            self.assertEqual(stage.files, files)
            for name, data in files.items():
                self.assertEqual(result[name], hashlib.sha256(data).hexdigest())
            for name in ('ReusableAssets/GuardRack.glb', '02_occupied_dressed.png', 'verify.report.json'):
                with self.subTest(corrupt=name), self.assertRaises(RuntimeError):
                    p.inspect_archive(make_zip(glbs, files, corrupt=name), MemoryStage())
                with self.subTest(duplicate=name), self.assertRaises(RuntimeError):
                    p.inspect_archive(make_zip(glbs, files, duplicate=name), MemoryStage())

    def test_reimport_report_mismatch_and_corridor_changes_fail(self):
        _, hashes, _, pins, build, verify = synthetic_bundle()
        with mock.patch.object(p, 'GLBS', hashes), mock.patch.object(p, 'FILES', pins):
            p.check_reports(build, verify)
            with self.assertRaises(RuntimeError):
                p.check_reports(build, {**verify, 'corridor_box_m': [[0, 0, 0], [1, 1, 1]]})
            changed = json.loads(json.dumps(verify))
            changed['assets']['StrongholdEntrance_Occupied']['facts']['bounds_m'][0][0] += .1
            with self.assertRaises(RuntimeError): p.check_reports(build, changed)

    def test_workflow_only_push_and_exact_staged_paths(self):
        sha, before = 'a'*40, 'b'*40
        event = {'before': before, 'after': sha, 'ref': 'refs/heads/main', 'forced': False,
                 'created': False, 'deleted': False, 'repository': {'full_name': p.base.REPO}}
        self.assertEqual(p.guarded.push_before(event, sha), before)
        parents, changed = (sha+' '+before+'\n').encode(), p.WORKFLOW.encode()+b'\0'
        p.check_push_shape(sha, before, parents, changed)
        for par, paths in ((parents+b'c'*40, changed), (parents, changed+b'other\0')):
            with self.assertRaises(RuntimeError): p.check_push_shape(sha, before, par, paths)
        names = [p.ZIP_REL, *((p.TARGET_REL/name).as_posix() for name in p.FILES)]
        encode = lambda xs: b''.join(x.encode()+b'\0' for x in xs)
        self.assertEqual(p.expected_paths(encode(names)), sorted(names))
        for xs in (names[:-1], names+['other'], names+[names[0]]):
            with self.assertRaises(RuntimeError): p.expected_paths(encode(xs))

    def test_smudge_kills_and_reaps_on_timeout_or_failure(self):
        pointer = p.base.pointer_bytes(p.ITEM)
        for timeout in (True, False):
            process = mock.Mock(pid=123, returncode=9)
            if timeout: process.communicate.side_effect = subprocess.TimeoutExpired('mock', 60)
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
                    with self.assertRaises(RuntimeError): p.readback({}, Path('/private/stage'), 'a'*40)


if __name__ == '__main__':
    unittest.main()
