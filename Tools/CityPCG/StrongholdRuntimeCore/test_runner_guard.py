"""Check which shared build-train status controls the standalone runner."""

from contextlib import redirect_stdout
import io
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import run_tests
from run_tests import current_train_status, editor_available


class TrainStatusTests(unittest.TestCase):
    def test_new_loaded_status_wins_over_older_building_notice(self):
        queue = '# Queue\n\n!!! 03:41 TRAIN #18 LOADED; editor back. !!!\n\n!!! 03:37 TRAIN #18 BUILDING !!!\n'
        self.assertEqual(current_train_status(queue), 'LOADED')

    def test_current_building_status_wins_over_older_loaded_notice(self):
        queue = '# Queue\n\n!!! 03:37 TRAIN #18 BUILDING !!!\n\n!!! 03:25 TRAIN #17 LOADED !!!\n'
        self.assertEqual(current_train_status(queue), 'BUILDING')

    def test_other_explicit_status_is_not_mistaken_for_loaded(self):
        queue = '!!! TRAIN #19 FAILED; check build !!!\n!!! TRAIN #18 LOADED !!!\n'
        self.assertEqual(current_train_status(queue), 'FAILED')

    def test_schedule_text_is_not_an_explicit_train_status(self):
        queue = 'Next train #20 at 04:30.\nNo current train update.\n'
        self.assertIsNone(current_train_status(queue))

    def test_malformed_new_train_does_not_fall_back_to_old_loaded(self):
        self.assertIsNone(current_train_status('TRAIN #20\nTRAIN #19 LOADED\n'))
        self.assertEqual(current_train_status('!!! 04:30 train #20: building !!!\nTRAIN #19 LOADED\n'), 'BUILDING')

    def test_actual_guard_uses_latest_status_and_still_honors_lock(self):
        root, lock, queue = MagicMock(), MagicMock(), MagicMock()
        root.__truediv__.side_effect = lambda path: lock if path == 'Saved/PIE_LOCK.json' else queue
        lock.exists.return_value = False
        lock.is_symlink.return_value = False
        queue.is_file.return_value = True
        queue.read_text.return_value = 'TRAIN #18 LOADED\nTRAIN #18 BUILDING\n'
        with patch('run_tests.ROOT', root), redirect_stdout(io.StringIO()):
            self.assertTrue(editor_available())
            queue.read_text.return_value = 'TRAIN #19 BUILDING\nTRAIN #18 LOADED\n'
            self.assertFalse(editor_available())
            queue.read_text.return_value = 'TRAIN #19 LOADED\n'
            lock.exists.return_value = True
            self.assertFalse(editor_available())
            lock.exists.return_value = False
            queue.is_file.return_value = False
            self.assertFalse(editor_available())
            queue.is_file.return_value = True
            queue.read_text.return_value = 'TRAIN #20\nTRAIN #19 LOADED\n'
            self.assertFalse(editor_available())


class FakePipe:
    def __init__(self):
        self.closed = False
        self.data = b''

    def write(self, data):
        self.data += data

    def close(self):
        self.closed = True


class FakeChild:
    def __init__(self, waits=()):
        self.stdin = FakePipe()
        self.returncode = None
        self.waits = list(waits)
        self.terminated = False
        self.killed = False
        self.killed_by_job = False

    def poll(self):
        return self.returncode

    def wait(self, timeout):
        if self.returncode is not None:
            return self.returncode
        outcome = self.waits.pop(0) if self.waits else 0
        if isinstance(outcome, BaseException):
            raise outcome
        self.returncode = outcome
        return outcome

    def terminate(self):
        self.terminated = True
        self.returncode = -1

    def kill(self):
        self.killed = True
        self.returncode = -1


class FakeJob:
    def __init__(self, fail_assignment=False):
        self.process = None
        self.closed = False
        self.fail_assignment = fail_assignment

    def assign(self, process):
        if self.fail_assignment:
            raise OSError('cannot assign')
        self.process = process

    def close(self):
        self.closed = True
        if self.process is not None and self.process.poll() is None:
            self.process.killed_by_job = True
            self.process.returncode = -1


class ChildGuardTests(unittest.TestCase):
    def test_closed_editor_or_process_check_failure_is_rejected(self):
        with patch.object(run_tests.sys, 'platform', 'win32'), \
                patch.object(run_tests.subprocess, 'run', return_value=SimpleNamespace(stdout='INFO: No tasks found.')):
            self.assertFalse(run_tests.shared_editor_running())
        with patch.object(run_tests.sys, 'platform', 'win32'), \
                patch.object(run_tests.subprocess, 'run', side_effect=subprocess.TimeoutExpired('tasklist', 1)):
            with self.assertRaisesRegex(RuntimeError, 'Cannot confirm'):
                run_tests.shared_editor_running()
        with patch.object(run_tests.sys, 'platform', 'win32'), \
                patch.object(run_tests.subprocess, 'run', return_value=SimpleNamespace(stdout='"UnrealEditor.exe","123"\n')):
            self.assertTrue(run_tests.shared_editor_running())

    def test_new_lease_train_low_memory_or_closed_editor_stops_only_our_job(self):
        events = (
            ('lease or train', [True] * 6 + [False], [True] * 7, [True] * 4),
            ('low memory', [True] * 7, [True] * 6 + [False], [True] * 4),
            ('closed editor', [True] * 7, [True] * 7, [True] * 3 + [False]),
        )
        for label, available, memory, running in events:
            with self.subTest(event=label):
                child = FakeChild(waits=[subprocess.TimeoutExpired('fake-compiler', run_tests.POLL_SECONDS)])
                unrelated_child = FakeChild()
                job = FakeJob()
                with patch.object(run_tests, 'editor_available', side_effect=available), \
                        patch.object(run_tests, 'memory_ok', side_effect=memory), \
                        patch.object(run_tests, 'shared_editor_running', side_effect=running), \
                        patch.object(run_tests, 'WindowsJob', return_value=job), \
                        patch.object(run_tests.subprocess, 'Popen', return_value=child):
                    with self.assertRaises(RuntimeError):
                        run_tests.run_guarded(['fake-compiler'], cwd='.', env={})
                self.assertEqual(child.stdin.data, b'1')
                self.assertTrue(job.closed and child.killed_by_job)
                self.assertFalse(child.terminated)
                self.assertIsNone(unrelated_child.poll())

    def test_lock_after_launch_attachment_prevents_compiler_start(self):
        child, job = FakeChild(), FakeJob()
        with patch.object(run_tests, 'session_guard', side_effect=[None, RuntimeError('lease')]), \
                patch.object(run_tests, 'WindowsJob', return_value=job), \
                patch.object(run_tests.subprocess, 'Popen', return_value=child):
            with self.assertRaisesRegex(RuntimeError, 'lease'):
                run_tests.run_guarded(['fake-compiler'], cwd='.', env={})
        self.assertEqual(child.stdin.data, b'')
        self.assertTrue(child.killed_by_job and job.closed)

    def test_assignment_failure_stops_the_blocked_launcher(self):
        child, job = FakeChild(), FakeJob(fail_assignment=True)
        with patch.object(run_tests, 'session_guard'), patch.object(run_tests, 'WindowsJob', return_value=job), \
                patch.object(run_tests.subprocess, 'Popen', return_value=child):
            with self.assertRaisesRegex(OSError, 'cannot assign'):
                run_tests.run_guarded(['fake-compiler'], cwd='.', env={})
        self.assertEqual(child.stdin.data, b'')
        self.assertTrue(child.terminated and job.closed)

    def test_broken_launch_pipe_still_closes_the_private_job(self):
        class BrokenPipe(FakePipe):
            def close(self):
                raise BrokenPipeError('launcher exited')

        child, job = FakeChild(), FakeJob()
        child.stdin = BrokenPipe()
        with patch.object(run_tests, 'session_guard'), patch.object(run_tests, 'WindowsJob', return_value=job), \
                patch.object(run_tests.subprocess, 'Popen', return_value=child):
            with self.assertRaises(BrokenPipeError):
                run_tests.run_guarded(['fake-compiler'], cwd='.', env={})
        self.assertTrue(child.killed_by_job and job.closed)

    def test_success_and_nonzero_exit_close_only_the_private_job(self):
        for code in (0, 7):
            with self.subTest(code=code):
                child, job = FakeChild(waits=[code]), FakeJob()
                with patch.object(run_tests, 'session_guard'), patch.object(run_tests, 'WindowsJob', return_value=job), \
                        patch.object(run_tests.subprocess, 'Popen', return_value=child):
                    if code:
                        with self.assertRaises(subprocess.CalledProcessError):
                            run_tests.run_guarded(['fake-compiler'], cwd='.', env={})
                    else:
                        run_tests.run_guarded(['fake-compiler'], cwd='.', env={})
                self.assertTrue(job.closed)
                self.assertFalse(child.killed_by_job)


if __name__ == '__main__':
    unittest.main()
