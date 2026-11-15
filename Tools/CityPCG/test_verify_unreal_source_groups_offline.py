"""Small offline tests for source group bijection and parser pinning."""

from collections import Counter
from pathlib import Path
import shutil
import subprocess
import unittest

import verify_unreal_source_groups_offline as proof


class OfflineSourceGroupTests(unittest.TestCase):
    def test_groups_are_matched_by_complete_geometry_not_order(self):
        groups = [Counter({'wall': 2}), Counter({'road': 3})]
        forward, reverse, valid = proof.match_groups(groups, list(reversed(groups)))
        self.assertTrue(valid)
        self.assertEqual(forward, [[1], [0]])
        self.assertEqual(reverse, [[1], [0]])

    def test_missing_duplicate_and_shared_triangles_fail_closed(self):
        self.assertFalse(proof.match_groups([], [])[2])
        self.assertFalse(proof.match_groups([Counter({'a': 1})], [Counter({'a': 2})])[2])
        self.assertFalse(proof.match_groups([Counter({'a': 1}), Counter({'a': 1})],
                                            [Counter({'a': 1}), Counter({'a': 1})])[2])
        self.assertFalse(proof.match_groups([Counter({'a': 1}), Counter({'a': 1, 'b': 1})],
                                            [Counter({'a': 1}), Counter({'a': 1, 'b': 1})])[2])

    @unittest.skipUnless(shutil.which('node'), 'Node is needed to test the parser identity guard')
    def test_unpinned_parser_is_rejected_before_any_asset_read(self):
        wrong_parser = Path(__file__).resolve()
        result = subprocess.run(['node', str(proof.EXTRACTOR), str(wrong_parser), 'missing-asset', 'missing-payload'],
                                capture_output=True, text=True, timeout=10,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Expected unmodified raw-unreal 0.1.13', result.stderr)


if __name__ == '__main__':
    unittest.main()
