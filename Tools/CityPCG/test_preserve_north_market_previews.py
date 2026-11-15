"""Small offline checks; no network, archive extraction, editor or Git writes."""
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

import preserve_north_market_previews as p


def report():
    return {'status': 'diagnostic only: visual/game approval pending',
            'model': p.MODEL, 'fbx_sha256': p.FBX_SHA,
            'bounds_m': [[-2, 2], [0, 3], [0, 8]],
            'render': 'Blender Cycles CPU, 8 samples, 720x480; artificial light and background',
            'placement': 'local source only; no Unreal placement or gameplay context',
            'source_world_pivot_m': [1, 2, 3], 'source_yaw_deg': 15.0}


class PreviewPreservationTests(unittest.TestCase):
    def test_report_pins_identity_diagnostic_status_and_finite_coordinates(self):
        p.check_report(report())
        for key, value in (('status', 'approved'), ('model', 'another'),
                           ('fbx_sha256', '0' * 64), ('bounds_m', [[0, 1]] * 2),
                           ('bounds_m', [[1, 0], [0, 1], [0, 1]]),
                           ('source_world_pivot_m', [0, float('nan'), 1]),
                           ('source_yaw_deg', float('inf')), ('source_yaw_deg', True)):
            changed = report()
            changed[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(RuntimeError):
                p.check_report(changed)
        for changed in ({**report(), 'extra': 1}, {k: v for k, v in report().items() if k != 'render'}):
            with self.assertRaises(RuntimeError):
                p.check_report(changed)

    def test_duplicate_report_keys_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'duplicate'):
            json.loads('{"model":1,"model":2}', object_pairs_hook=p.unique_json)

    def test_pin_and_inspector_contract_cannot_drift(self):
        shared_guard = p.base.WORKFLOW, p.base.WORKFLOW_REF
        p.check_helper_contract()
        self.assertEqual((p.base.WORKFLOW, p.base.WORKFLOW_REF), shared_guard)
        with mock.patch.object(p.base, 'ARTIFACTS', ({**p.ITEM, 'size': 1},)):
            with self.assertRaisesRegex(RuntimeError, 'helper-contract'):
                p.check_helper_contract()
        with mock.patch.object(p.base, 'PREVIEW_FILES', {**p.FILES, 'preview/other.png': 'other.png'}):
            with self.assertRaisesRegex(RuntimeError, 'helper-contract'):
                p.check_helper_contract()

    def test_context_accepts_only_expected_hosted_main_workflow(self):
        env = {'GITHUB_ACTIONS': 'true', 'RUNNER_ENVIRONMENT': 'github-hosted', 'RUNNER_OS': 'Linux',
               'GITHUB_REPOSITORY': p.base.REPO, 'GITHUB_REPOSITORY_ID': '1457160414',
               'GITHUB_REF': 'refs/heads/main', 'GITHUB_WORKFLOW_REF': p.WORKFLOW_REF,
               'GITHUB_SERVER_URL': 'https://github.com', 'GITHUB_API_URL': 'https://api.github.com',
               'GITHUB_SHA': 'a' * 40, 'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '1',
               'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_WORKSPACE': str(p.base.ROOT),
               'RUNNER_TEMP': str(Path(p.base.ROOT.anchor)), 'GH_TOKEN': 'mock-token'}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(p.sys, 'platform', 'linux'):
            self.assertEqual(p.context()['sha'], 'a' * 40)
            for key, value in (('GITHUB_WORKFLOW_REF', p.base.WORKFLOW_REF),
                               ('GITHUB_REF', 'refs/heads/other'), ('GITHUB_REPOSITORY_ID', '1'),
                               ('RUNNER_ENVIRONMENT', 'self-hosted'), ('GITHUB_EVENT_NAME', 'pull_request')):
                with mock.patch.dict(os.environ, {key: value}), self.assertRaises(RuntimeError):
                    p.context()

    def test_push_event_identity_and_flags_are_checked(self):
        head, parent = 'a' * 40, 'b' * 40
        payload = {'before': parent, 'after': head, 'ref': 'refs/heads/main',
                   'forced': False, 'created': False, 'deleted': False,
                   'repository': {'full_name': p.base.REPO}}
        self.assertEqual(p.push_before(payload, head), parent)
        for key, value in (('before', '0' * 40), ('after', parent), ('ref', 'refs/heads/other'),
                           ('forced', True), ('created', True), ('deleted', True),
                           ('repository', {'full_name': 'other/repo'})):
            changed = {**payload, key: value}
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                p.push_before(changed, head)

    def test_existing_tracked_or_redirected_target_rejected(self):
        path = Path('/runner/work/repo/parent')
        p.check_target(False, False, path, path, b'')
        for args in ((True, False, path, path, b''), (False, True, path, path, b''),
                     (False, False, Path('/different'), path, b''),
                     (False, False, path, path, b'existing')):
            with self.subTest(args=args), self.assertRaises(RuntimeError):
                p.check_target(*args)

    def test_only_exact_staged_preview_files_are_accepted(self):
        paths = sorted((p.TARGET_REL / name).as_posix() for name in (*p.FILES.values(), 'README.md'))
        encoded = lambda names: b''.join(name.encode() + b'\0' for name in names)
        self.assertEqual(p.checked_names(encoded(paths)), paths)
        for bad in (paths[:-1], paths + ['unrelated'], paths + [paths[0]]):
            with self.assertRaisesRegex(RuntimeError, 'staged-paths'):
                p.checked_names(encoded(bad))

    def test_lfs_pointer_or_changed_blob_is_rejected(self):
        good = b'actual png bytes'
        name = p.FILES['preview/eye_level.png']
        hashes = {name: hashlib.sha256(good).hexdigest()}
        with mock.patch.object(p.base, 'git', return_value=SimpleNamespace(stdout=good)):
            p.check_blobs({}, '', hashes)
        pointer = b'version https://git-lfs.github.com/spec/v1\noid sha256:' + b'0' * 64
        with mock.patch.object(p.base, 'git', return_value=SimpleNamespace(stdout=pointer)):
            with self.assertRaisesRegex(RuntimeError, 'git-blob-integrity'):
                p.check_blobs({}, '', hashes)

    def test_concurrent_main_advance_is_rejected(self):
        with mock.patch.object(p.base, 'remote_head', return_value='b' * 40):
            with self.assertRaisesRegex(RuntimeError, 'remote-advanced'):
                p.require_current_head({}, 'a' * 40)
        with mock.patch.object(p.base, 'remote_head', return_value='a' * 40):
            p.require_current_head({}, 'a' * 40)

    def test_push_trigger_requires_exactly_one_parent_and_only_this_workflow(self):
        head, parent = 'a' * 40, 'b' * 40
        parents = (head + ' ' + parent + '\n').encode()
        changed = p.WORKFLOW.encode() + b'\0'
        p.check_push_shape(head, parent, parents, changed)
        for bad_parents, bad_changed in ((parents + b'c' * 40, changed),
                                         (parents, changed + b'other\0'),
                                         (parents, b'.github/workflows/other.yml\0')):
            with self.assertRaises(RuntimeError):
                p.check_push_shape(head, parent, bad_parents, bad_changed)


if __name__ == '__main__':
    unittest.main()
