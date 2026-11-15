"""Check which shared build-train status controls the standalone runner."""

from contextlib import redirect_stdout
import io
import unittest
from unittest.mock import MagicMock, patch

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


if __name__ == '__main__':
    unittest.main()
