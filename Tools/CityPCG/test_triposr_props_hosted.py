"""Small, offline input and hosted-only guard checks; no model execution."""
import json
import os
from pathlib import Path
import struct
import unittest
from unittest import mock

import triposr_props_hosted as runner


class InputTests(unittest.TestCase):
    def test_reference_pngs_match_manifest_and_have_alpha(self):
        manifest=json.loads((runner.BASE/'inputs.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['schema'],1)
        self.assertGreaterEqual(len(manifest['assets']),4)
        for name,sha in manifest['assets'].items():
            path=runner.BASE/'Inputs'/f'{name}.png'
            self.assertEqual(runner.digest(path),sha)
            with path.open('rb') as stream: header=stream.read(29)
            self.assertEqual(header[:8],b'\x89PNG\r\n\x1a\n')
            self.assertEqual(struct.unpack('>II',header[16:24]),(1254,1254))
            self.assertEqual(header[25],6)  # PNG RGBA

    def test_config_pins_and_local_rejection(self):
        self.assertEqual(runner.digest(runner.BASE/'Configs/config.yaml'),runner.CONFIG_SHA)
        self.assertEqual(runner.digest(runner.BASE/'Configs/dino_config.json'),runner.DINO_SHA)
        with mock.patch.dict(os.environ,{},clear=True):
            with self.assertRaises(RuntimeError): runner.context()


if __name__=='__main__': unittest.main()
