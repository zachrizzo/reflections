"""Offline guard/provenance tests; never start the model or a GPU."""

import hashlib
import json
from pathlib import Path
from contextlib import contextmanager
import shutil
from tempfile import gettempdir, mkdtemp
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import run_merchant_gate_triposr as runner
import fetch_triposr_weights as fetch


@contextmanager
def checked_tempdir():
    """Check the exact resolved target immediately before recursive cleanup."""
    parent = Path(gettempdir()).resolve(strict=True)
    target = Path(mkdtemp(prefix='codex-triposr-test-', dir=str(parent)))
    resolved = target.resolve(strict=True)
    if target.is_symlink() or not target.is_absolute() or resolved.parent != parent or resolved != target:
        raise RuntimeError('Unexpected redirected temporary directory; refusing cleanup.')
    try:
        yield resolved
    finally:
        current = target.resolve(strict=True)
        if target.is_symlink() or current != resolved or current.parent != parent:
            raise RuntimeError('Temporary directory changed before cleanup; refusing recursive deletion.')
        shutil.rmtree(current)


class GuardTests(unittest.TestCase):
    def test_lease_or_memory_failure_stops_before_input_hash_or_gpu_probe(self):
        with patch.object(runner, 'session_guard', side_effect=RuntimeError('leased')), \
                patch.object(runner, 'validate_inputs') as inputs, patch.object(runner, 'free_vram_mib') as gpu:
            with self.assertRaisesRegex(RuntimeError, 'leased'):
                runner.supervise('trial')
        inputs.assert_not_called()
        gpu.assert_not_called()

    def test_memory_thresholds_are_distinct_for_start_and_running(self):
        with patch.object(runner, 'memory_headroom', return_value=(6 * 1024**3, 12 * 1024**3)):
            runner.memory_guard()
            with self.assertRaisesRegex(RuntimeError, 'headroom'):
                runner.memory_guard(start=True)

    def test_closed_editor_stops_guard_and_running_worker(self):
        class Child:
            returncode = None
            terminated = False

            def poll(self):
                return self.returncode

            def terminate(self):
                self.terminated, self.returncode = True, 1

            def wait(self, timeout):
                return self.returncode

        child = Child()
        with checked_tempdir() as root:
            (root / 'Saved').mkdir()
            with patch.object(fetch, 'PROJECT', root), \
                    patch.object(fetch, 'require_editor_available'), patch.object(fetch, 'require_memory'), \
                    patch.object(fetch.sys, 'platform', 'win32'), \
                    patch.object(fetch.subprocess, 'run', return_value=SimpleNamespace(stdout='INFO: No tasks found.')), \
                    patch.object(runner, 'memory_guard') as memory:
                with self.assertRaisesRegex(RuntimeError, 'closed or restarting'):
                    runner.session_guard(start=True)
                with self.assertRaisesRegex(RuntimeError, 'closed or restarting'):
                    runner.watch(child, check=runner.session_guard, delay=0)
                memory.assert_not_called()
        self.assertTrue(child.terminated)

    def test_any_editor_lease_file_blocks_without_gpu_probe(self):
        with checked_tempdir() as root:
            (root / 'Saved').mkdir()
            (root / 'Saved/PIE_LOCK.json').write_text('{"expires_epoch": 1}')
            with patch.object(fetch, 'PROJECT', root), patch.object(fetch, 'require_editor_available') as availability, \
                    patch.object(runner, 'free_vram_mib') as gpu:
                with self.assertRaisesRegex(RuntimeError, 'lease file is present'):
                    runner.supervise('trial')
                availability.assert_not_called()
                gpu.assert_not_called()

    def test_watch_terminates_only_its_child_when_another_session_takes_lease(self):
        class Child:
            returncode = None
            terminated = False

            def poll(self):
                return self.returncode

            def terminate(self):
                self.terminated, self.returncode = True, 1

            def wait(self, timeout):
                return self.returncode

        child = Child()
        def taken():
            raise RuntimeError('lease taken')
        with self.assertRaisesRegex(RuntimeError, 'lease taken'):
            runner.watch(child, check=taken, delay=0)
        self.assertTrue(child.terminated)

    def test_pinned_hash_size_and_clean_checkout_are_enforced(self):
        with checked_tempdir() as folder:
            root = Path(folder)
            fake_python = root / 'python.exe'
            fake_python.write_bytes(b'python')
            checkpoint = root / 'model.ckpt'
            checkpoint.write_bytes(b'weights')
            expected = {'checkpoint': (checkpoint, hashlib.sha256(b'weights').hexdigest())}
            with patch.object(runner, 'PYTHON', fake_python), patch.object(runner.sys, 'executable', str(fake_python)), \
                    patch.object(runner, 'EXPECTED', expected), patch.object(runner, 'CHECKPOINT_SIZE', 7), \
                    patch.object(runner, 'git', side_effect=[runner.COMMIT, '', runner.COMMIT, '']):
                self.assertEqual(runner.validate_inputs()['checkpoint'], expected['checkpoint'][1])
                checkpoint.write_bytes(b'changed')
                with self.assertRaisesRegex(RuntimeError, 'hash mismatch'):
                    runner.validate_inputs()
            with patch.object(runner, 'PYTHON', fake_python), patch.object(runner.sys, 'executable', str(fake_python)), \
                    patch.object(runner, 'git', side_effect=[runner.COMMIT, ' M source.py']):
                with self.assertRaisesRegex(RuntimeError, 'dirty'):
                    runner.validate_inputs()

    def test_fresh_run_stays_under_saved_and_never_overwrites(self):
        with checked_tempdir() as folder:
            root = Path(folder)
            (root / 'Saved').mkdir()
            with patch.object(runner, 'PROJECT', root), patch.object(runner, 'RUNS', root / 'Saved/CityPCG/Runs'):
                created = runner.fresh_run('merchant_001')
                self.assertTrue(created.is_dir())
                with self.assertRaises(FileExistsError):
                    runner.fresh_run('merchant_001')
                with self.assertRaises(ValueError):
                    runner.fresh_run('../escape')
            with patch.object(runner, 'PROJECT', root), patch.object(runner, 'RUNS', root / 'outside'):
                with self.assertRaisesRegex(RuntimeError, 'outside'):
                    runner.fresh_run('merchant_002')

    def test_fake_worker_publishes_provenance_only_after_verification(self):
        with checked_tempdir() as folder:
            root = Path(folder)
            (root / 'Saved').mkdir()
            upstream = root / 'upstream'
            upstream.mkdir()
            (upstream / 'LICENSE').write_bytes(b'license')
            reference = root / 'reference.png'
            reference.write_bytes(b'reference')
            hashes = {'reference': hashlib.sha256(b'reference').hexdigest(),
                      'upstream_license': hashlib.sha256(b'license').hexdigest()}

            def fake_child(*args, **kwargs):
                run = root / 'Saved/CityPCG/Runs/trial'
                for name in ('foreground_rgba.png', 'conditioned.png', 'MerchantGate_raw.glb'):
                    (run / name).write_bytes(name.encode())
                (run / 'worker.result.json').write_text(json.dumps({'status': 'provisional_raw_mesh'}))
                return SimpleNamespace(returncode=0)

            with patch.object(runner, 'PROJECT', root), patch.object(runner, 'RUNS', root / 'Saved/CityPCG/Runs'), \
                    patch.object(runner, 'UPSTREAM', upstream), patch.object(runner, 'REFERENCE', reference), \
                    patch.object(runner, 'session_guard', return_value={'physical_bytes': 1}), \
                    patch.object(runner, 'validate_inputs', return_value=hashes), \
                    patch.object(runner, 'free_vram_mib', return_value=8192), \
                    patch.object(runner.subprocess, 'Popen', side_effect=fake_child), patch.object(runner, 'watch'):
                result = runner.supervise('trial')
            self.assertEqual(result['status'], 'raw_mesh_requires_review')
            self.assertFalse(result['gameplay_ready'])
            self.assertTrue((root / 'Saved/CityPCG/Runs/trial/provenance.complete.json').exists())


if __name__ == '__main__':
    unittest.main()
