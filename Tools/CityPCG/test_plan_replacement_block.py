"""Tests for safe planning of complete, adjoining replacement buildings."""

import copy
import unittest

from plan_replacement_block import shared_party_walls, style_for


def adjacent():
    return {
        'buildings': [
            {'id': 'west', 'footprint': [[0, 0], [3, 0], [3, 4], [0, 4]]},
            {'id': 'east', 'footprint': [[3, 0], [6, 0], [6, 4], [3, 4]]},
        ],
        'shared_party_walls': [{'keep_sealed': True, 'world_segment_m': [[3, 0], [3, 4]],
                                'edges': {'west': 1, 'east': 3}}],
    }


class ReplacementBlockTests(unittest.TestCase):
    def test_shared_edges_are_exact_and_reversed(self):
        walls = shared_party_walls(adjacent())
        self.assertEqual(len(walls), 1)
        self.assertEqual(walls[0]['length_m'], 4)
        wrong = adjacent()
        wrong['shared_party_walls'][0]['world_segment_m'][1] = [3, 3]
        with self.assertRaises(ValueError):
            shared_party_walls(wrong)

    def test_an_edge_cannot_be_claimed_twice(self):
        candidate = adjacent()
        candidate['shared_party_walls'].append(copy.deepcopy(candidate['shared_party_walls'][0]))
        with self.assertRaises(ValueError):
            shared_party_walls(candidate)

    def test_style_is_deterministic_and_within_source_height(self):
        building = {'id': 'surveyed-house', 'footprint': [[0, 0], [12, 0], [12, 8], [0, 8]],
                    'entry': {'edge': 0, 'minimum_clear_width_m': 1.5}, 'base_m': .2, 'source_roof_m': 13}
        style = style_for(building)
        self.assertEqual(style, style_for(building))
        self.assertGreater(style['eave_m'], style['entry_opening_m'][1])
        self.assertLess(style['eave_m'], style['ridge_m'])
        self.assertLess(style['ridge_m'], building['source_roof_m'] - building['base_m'])
        self.assertLessEqual(style['entry_opening_m'][0], building['entry']['minimum_clear_width_m'])

    def test_low_source_envelopes_fail_closed(self):
        building = {'id': 'too-low', 'footprint': [[0, 0], [12, 0], [12, 8], [0, 8]],
                    'entry': {'edge': 0, 'minimum_clear_width_m': 1.5}, 'base_m': .2, 'source_roof_m': 6}
        with self.assertRaises(ValueError):
            style_for(building)


if __name__ == '__main__':
    unittest.main()
