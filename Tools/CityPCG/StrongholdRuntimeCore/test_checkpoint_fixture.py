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


def reference_fixture(version):
    """Independently encode the fresh v1 cure and v2 defended fixtures."""
    payload = b'GLSH' + struct.pack('<HQH', version, 123456789, 1)
    payload += length_prefixed('A')
    payload += length_prefixed('0' * 31 + 'a')
    if version == 1:
        payload += length_prefixed('person-A')
    else:
        payload += b'\x01' + length_prefixed('defenders-A')
    payload += struct.pack('<8d', 10.0, 20.0, 0.0, 0.25, 7.0, 2.5, 2.0, 12.0)
    payload += struct.pack('<Bd', 0, 0.0)  # AwaitingCure, no held time.
    return payload + struct.pack('<I', zlib.crc32(payload))


class CheckpointFixtureTests(unittest.TestCase):
    def fixture_in(self, function):
        source = CPP_TEST.read_text(encoding='utf-8')
        match = re.search(
            rf'void\s+{re.escape(function)}\s*\(\s*\)\s*\{{.*?'
            r'expected\s*=\s*\{(.*?)\};', source, re.DOTALL,
        )
        self.assertIsNotNone(match, 'Cannot find the C++ wire-test fixture')
        text = match.group(1)
        values = re.findall(r'0x[0-9a-fA-F]{2}', text)
        self.assertFalse(re.sub(r'0x[0-9a-fA-F]{2}|[\s,]', '', text),
                         'Unexpected text in the C++ byte fixture')
        return bytes(int(value, 16) for value in values)

    def test_v1_cure_fixture_matches_independent_wire_encoding(self):
        self.assertEqual(self.fixture_in('TestWireCompatibility'), reference_fixture(1))

    def test_v2_defender_fixture_matches_independent_wire_encoding(self):
        self.assertEqual(self.fixture_in('TestDefenderWireCompatibility'), reference_fixture(2))


if __name__ == '__main__':
    unittest.main()
