"""Small offline tests of compressed-buffer checks and no-overwrite policy."""

from pathlib import Path
import struct
import unittest
from unittest.mock import patch
import zlib

import decompress_west_mark_lane_source as proof
from test_verify_west_mark_lane_section_mapping import checked_tempdir


def synthetic_buffer():
    # Two blocks: 8 raw bytes compressed to one byte, then two verbatim bytes.
    count, exponent, raw_size = 2, 3, 10
    table = struct.pack('>2I', 1, 2)
    total = proof.HEADER.size + len(table) + 3
    header = proof.HEADER.pack(0xb7756362, 0, 3, 3, 3, exponent, count, raw_size, total, b'x' * 32)
    packet = bytearray(header + table + b'Zab')
    crc = zlib.crc32(packet[8:proof.HEADER.size + len(table)]) & 0xffffffff
    struct.pack_into('>I', packet, 4, crc)
    return bytes(packet)


class DecompressionTests(unittest.TestCase):
    def test_validated_blocks_reconstruct_exact_payload(self):
        packet = synthetic_buffer()
        header = proof.find_buffer(packet)
        calls = []
        def decode(chunk, expected):
            calls.append((chunk, expected))
            return b'12345678'
        self.assertEqual(proof.decode_blocks(packet, header, decode), b'12345678ab')
        self.assertEqual(calls, [(b'Z', 8)])

    def test_corrupt_header_table_and_decoder_fail_closed(self):
        packet = bytearray(synthetic_buffer())
        packet[proof.HEADER.size] ^= 1
        with self.assertRaisesRegex(ValueError, 'table or header CRC'):
            proof.find_buffer(bytes(packet))
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            proof.find_buffer(synthetic_buffer() + proof.MAGIC)
        with self.assertRaisesRegex(ValueError, 'exceeds'):
            proof.find_buffer(synthetic_buffer()[:-1])
        header = proof.find_buffer(synthetic_buffer())
        with self.assertRaisesRegex(ValueError, 'wrong size'):
            proof.decode_blocks(synthetic_buffer(), header, lambda _chunk, _size: b'wrong')

    def test_outputs_must_be_fresh_and_resolve_inside_saved(self):
        with checked_tempdir() as root:
            saved = root / 'Saved'
            saved.mkdir()
            existing = saved / 'existing.bin'
            existing.write_bytes(b'preserve')
            with patch.object(proof, 'PROJECT', root), patch.object(proof, 'SAVED', saved):
                self.assertEqual(proof.output_path(saved / 'new.bin'), saved.resolve() / 'new.bin')
                with self.assertRaisesRegex(ValueError, 'fresh'):
                    proof.output_path(existing)
                with self.assertRaisesRegex(ValueError, 'inside'):
                    proof.output_path(root / 'outside.bin')
            self.assertEqual(existing.read_bytes(), b'preserve')


if __name__ == '__main__':
    unittest.main()
