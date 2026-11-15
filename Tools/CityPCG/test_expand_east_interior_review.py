"""Fail-closed coordination checks for the east-interior review runner."""

from pathlib import Path
import unittest
from unittest.mock import mock_open, patch

import expand_east_interior_review as runner


class ExpansionGuardTests(unittest.TestCase):
    def test_only_current_loaded_train_and_running_editor_are_accepted(self):
        for line in ("!!! 04:50 TRAIN #21 BUILDING !!!\n!!! 04:40 TRAIN #20 LOADED !!!\n",
                     "!!! 05:00 TRAIN #21 LOADED. Now: NPC proof. Others wait; restart between rounds. !!!\n",
                     "!!! 05:00 TRAIN #22 LOADED. Next: npc-unify final proof round. !!!\n",
                     "!!! 05:00 TRAIN #22 LOADED. A restart is scheduled next. !!!\n",
                     "!!! 05:00 TRAIN #22 LOADED. The next slot is reserved. !!!\n",
                     "!!! 05:00 TRAIN #22 LOADED. A proof round is next. !!!\n",
                     "!!! 04:40 TRAIN #20 LOADED !!!\n",
                     "!!! 04:50 TRAIN #21 ???\n!!! 04:40 TRAIN #20 LOADED !!!\n", "# no current status\n"):
            with self.subTest(line=line), patch.object(Path, "open", mock_open(read_data=line)), \
                    patch.object(runner, "editor_process_running", return_value=True):
                with self.assertRaises(RuntimeError):
                    runner.require_loaded_editor()
        with patch.object(Path, "open", mock_open(read_data="!!! 05:00 TRAIN #21 LOADED !!!\n"
                                                        "!!! 04:50 TRAIN #21 BUILDING !!!\n")), \
                patch.object(runner, "editor_process_running", return_value=True):
            runner.require_loaded_editor()
        with patch.object(Path, "open", mock_open(read_data="!!! 05:00 TRAIN #21 LOADED !!!\n")), \
                patch.object(runner, "editor_process_running", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "editor has not returned"):
                runner.require_loaded_editor()

    def test_low_physical_or_commit_memory_blocks_each_stage(self):
        with patch.object(runner, "require_unleased_editor"), patch.object(runner, "require_train_not_building"), \
                patch.object(runner, "require_loaded_editor"):
            for values in ((runner.MIN_PHYSICAL - 1, runner.MIN_COMMIT),
                           (runner.MIN_PHYSICAL, runner.MIN_COMMIT - 1)):
                with self.subTest(values=values), patch.object(runner, "memory_headroom", return_value=values):
                    with self.assertRaisesRegex(RuntimeError, "headroom"):
                        runner.guard()
            safe = (runner.MIN_PHYSICAL, runner.MIN_COMMIT)
            with patch.object(runner, "memory_headroom", return_value=safe):
                self.assertEqual(runner.guard(), safe)

    def test_active_lease_stops_before_any_memory_work(self):
        with patch.object(runner, "require_unleased_editor", side_effect=RuntimeError("active lease")), \
                patch.object(runner, "memory_headroom") as memory:
            with self.assertRaisesRegex(RuntimeError, "active lease"):
                runner.guard()
            memory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
