"""Tests for keeping city-tile replacement masks cumulative and unambiguous."""

import copy
import unittest

from combine_replacement_candidates import SOURCE_FIELDS, combine


def candidate(identifier):
    result = {field: field for field in SOURCE_FIELDS}
    result.update({'status': 'offline_candidate', 'buildings': [{'id': identifier}]})
    return result


class CombinedMaskTests(unittest.TestCase):
    def test_same_source_keeps_every_building(self):
        combined = combine([candidate('first'), candidate('second')])
        self.assertEqual([row['id'] for row in combined['buildings']], ['first', 'second'])

    def test_different_tile_or_hash_is_rejected(self):
        first, second = candidate('first'), candidate('second')
        for field in ('source_tile', 'source_export_sha256', 'untouched_primitives'):
            changed = copy.deepcopy(second)
            changed[field] = 'changed'
            with self.assertRaises(ValueError):
                combine([first, changed])

    def test_duplicate_building_or_non_candidate_is_rejected(self):
        with self.assertRaises(ValueError):
            combine([candidate('same'), candidate('same')])
        second = candidate('second')
        second['status'] = 'unreviewed'
        with self.assertRaises(ValueError):
            combine([candidate('first'), second])


if __name__ == '__main__':
    unittest.main()
