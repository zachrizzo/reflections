"""Check plan-pinned style recipes with regular Python."""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whole_building_styles import plan_lf_sha256, read_style_overrides


ART = Path(__file__).resolve().parents[2] / 'ArtDirection/CityPCG/MedievalOpening'
MERCHANT = 'Tile_p03_p01_roof_ee3443afee1e1296'


class WholeBuildingStyleTests(unittest.TestCase):
    def setUp(self):
        directory = Path(self.enterContext(TemporaryDirectory()))
        self.lf = directory / 'plan-lf.json'
        self.crlf = directory / 'plan-crlf.json'
        self.recipe = directory / 'styles.json'
        self.content = b'{\n  "buildings": [{"id": "merchant"}]\n}\n'
        self.lf.write_bytes(self.content)
        self.crlf.write_bytes(self.content.replace(b'\n', b'\r\n'))
        self.valid = {'schema': 1, 'plan_lf_sha256': hashlib.sha256(self.content).hexdigest(),
                      'styles': {'merchant': 'TradingRange'}}
        self.write_recipe(self.valid)

    def write_recipe(self, data):
        self.recipe.write_text(json.dumps(data), encoding='utf-8')

    def test_lf_and_crlf_match_through_validation(self):
        expected = self.valid['plan_lf_sha256']
        self.assertNotEqual(self.lf.read_bytes(), self.crlf.read_bytes())
        self.assertNotEqual(hashlib.sha256(self.lf.read_bytes()).hexdigest(),
                            hashlib.sha256(self.crlf.read_bytes()).hexdigest())
        for plan in (self.lf, self.crlf):
            with self.subTest(plan=plan.name):
                self.assertEqual(plan_lf_sha256(plan), expected)
                self.assertEqual(read_style_overrides(self.recipe, plan, {'merchant'}), self.valid['styles'])

    def test_plan_content_changes_are_rejected(self):
        self.crlf.write_bytes(self.crlf.read_bytes().replace(b'merchant', b'workshop'))
        with self.assertRaisesRegex(ValueError, 'LF-normalized SHA-256'):
            read_style_overrides(self.recipe, self.crlf, {'merchant'})

    def test_invalid_recipes_are_rejected(self):
        invalid = (
            ([], 'schema 1'),
            ({**self.valid, 'schema': True}, 'schema 1'),
            ({**self.valid, 'plan_lf_sha256': 'wrong'}, 'LF-normalized SHA-256'),
            ({'schema': 1, 'plan_sha256': self.valid['plan_lf_sha256'],
              'styles': self.valid['styles']}, 'LF-normalized SHA-256'),
            ({**self.valid, 'styles': {}}, 'building IDs'),
            ({**self.valid, 'styles': {'unknown': 'TradingRange'}}, 'building IDs'),
            ({**self.valid, 'styles': {'merchant': 'UnknownStyle'}}, 'unknown style preset'),
            ({**self.valid, 'styles': {'merchant': ['TradingRange']}}, 'unknown style preset'),
        )
        for body, message in invalid:
            with self.subTest(body=body):
                self.write_recipe(body)
                with self.assertRaisesRegex(ValueError, message):
                    read_style_overrides(self.recipe, self.lf, {'merchant'})

    def test_leadenhall_recipe_matches_both_checkout_formats(self):
        plan = ART / 'WholeBuildings/LeadenhallNorthwest/leadenhall_northwest_whole_building_plan.json'
        recipe = ART / 'leadenhall_northwest_style_variation.json'
        source = plan.read_bytes().replace(b'\r\n', b'\n')
        building_ids = {row['id'] for row in json.loads(source)['buildings']}
        self.lf.write_bytes(source)
        self.crlf.write_bytes(source.replace(b'\n', b'\r\n'))
        for checkout in (self.lf, self.crlf):
            with self.subTest(checkout=checkout.name):
                self.assertEqual(read_style_overrides(recipe, checkout, building_ids), {MERCHANT: 'TradingRange'})


if __name__ == '__main__':
    unittest.main()
