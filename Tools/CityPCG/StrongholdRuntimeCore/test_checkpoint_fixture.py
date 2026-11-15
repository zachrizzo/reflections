"""Independently check the example bytes in the standalone C++ wire test.

This check caught a previous fixture transcription error. It does not execute
the C++ codec; run run_tests.py when the shared editor and memory guards allow.
"""

from pathlib import Path
import re
import struct
import unittest
import zlib


CPP_TEST = Path(__file__).with_name('test_stronghold_campaign.cpp')


def length_prefixed(text):
    encoded = text.encode('utf-8')
    return struct.pack('<H', len(encoded)) + encoded


def reference_fixture():
    """Encode Config("A")'s fresh state as documented GLSH version 1."""
    payload = b'GLSH' + struct.pack('<HQH', 1, 123456789, 1)
    payload += length_prefixed('A')
    payload += length_prefixed('0' * 31 + 'a')
    payload += length_prefixed('person-A')
    payload += struct.pack('<8d', 10.0, 20.0, 0.0, 0.25, 7.0, 2.5, 2.0, 12.0)
    payload += struct.pack('<Bd', 0, 0.0)  # AwaitingCure, no held time.
    return payload + struct.pack('<I', zlib.crc32(payload))


class CheckpointFixtureTests(unittest.TestCase):
    def test_cpp_golden_fixture_matches_independent_wire_encoding(self):
        source = CPP_TEST.read_text(encoding='utf-8')
        match = re.search(
            r'void\s+TestWireCompatibility\s*\(\s*\)\s*\{.*?'
            r'expected\s*=\s*\{(.*?)\};', source, re.DOTALL,
        )
        self.assertIsNotNone(match, 'Cannot find the C++ wire-test fixture')
        text = match.group(1)
        values = re.findall(r'0x[0-9a-fA-F]{2}', text)
        self.assertFalse(re.sub(r'0x[0-9a-fA-F]{2}|[\s,]', '', text),
                         'Unexpected text in the C++ byte fixture')
        actual = bytes(int(value, 16) for value in values)
        self.assertEqual(actual, reference_fixture())


if __name__ == '__main__':
    unittest.main()
