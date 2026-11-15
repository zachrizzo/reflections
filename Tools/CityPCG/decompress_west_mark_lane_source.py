"""Decode one pinned UE 5.9 source mesh payload using the installed Oodle DLL.

Read-only for project assets. The verified payload is written once under the
project's Saved directory; an existing file is never overwritten.
"""

import argparse
import ctypes
import hashlib
from pathlib import Path
import struct
import sys
import zlib


PROJECT = Path(__file__).resolve().parents[2]
ASSET = PROJECT / 'Content/GrayLondon/Geodata/Tiles/Tile_p03_p00.uasset'
SAVED = PROJECT / 'Saved'
DEFAULT_OUTPUT = SAVED / 'CityPCG/MedievalSurvey/Tile_p03_p00_mesh_payload.bin'
DEPENDENCIES = SAVED / 'CityPCG/OfflineGeometryDeps'
OODLE_DLL = Path('C:/Program Files/Epic Games/UE_5.9/Engine/Binaries/DotNET/UnrealBuildTool/runtimes/win-x64/native/oo2core.dll')
ASSET_SHA256 = 'fad42a2a33c47b14298e5206fbbd3f3e60b3124ea8316f4f35077539824673f1'
RAW_SHA256 = '147621d39e17a2288a7559e8fa846ed07e3090e384d4855b266891d29953f83c'
RAW_BLAKE3 = bytes.fromhex('894085384a512d1de43b1f6ced6c5b491153308e264e0ec3bc2e35a60c782a07')
HEADER = struct.Struct('>IIBBBBIQQ32s')
MAGIC = bytes.fromhex('b7756362')


def find_buffer(data):
    """Validate the UE FCompressedBuffer header, block table, and CRC."""
    offsets = []
    position = 0
    while (index := data.find(MAGIC, position)) != -1:
        offsets.append(index)
        position = index + 1
    if len(offsets) != 1:
        raise ValueError(f'Expected exactly one compressed-buffer magic, found {len(offsets)}.')
    offset = offsets[0]
    if len(data) - offset < HEADER.size:
        raise ValueError('Truncated compressed-buffer header.')
    magic, crc, method, codec, level, exponent, count, raw_size, total_size, raw_hash = HEADER.unpack_from(data, offset)
    if (magic != 0xb7756362 or method != 3 or not 1 <= exponent <= 30
            or count < 1 or count > 65536 or raw_size < 1
            or count != (raw_size + (1 << exponent) - 1) // (1 << exponent)):
        raise ValueError('Unsupported compressed-buffer header or block count.')
    header_size = HEADER.size + 4 * count
    if total_size < header_size or offset + total_size > len(data):
        raise ValueError('Compressed-buffer size or block table exceeds the file.')
    table = struct.unpack_from('>' + str(count) + 'I', data, offset + HEADER.size)
    if (sum(table) + header_size != total_size
            or zlib.crc32(data[offset + 8:offset + header_size]) & 0xffffffff != crc):
        raise ValueError('Compressed-buffer block table or header CRC is invalid.')
    for index, size in enumerate(table):
        expected = min(1 << exponent, raw_size - index * (1 << exponent))
        if size < 1 or size > expected:
            raise ValueError(f'Compressed block {index} has invalid length.')
    return {'offset': offset, 'method': method, 'codec': codec, 'level': level,
            'exponent': exponent, 'count': count, 'raw_size': raw_size,
            'total_size': total_size, 'raw_hash': raw_hash, 'table': table,
            'payload_offset': offset + header_size}


def decode_blocks(data, header, decode):
    """Decompress bounded blocks; exact-sized raw blocks are stored verbatim."""
    output = bytearray()
    position = header['payload_offset']
    for index, size in enumerate(header['table']):
        expected = min(1 << header['exponent'], header['raw_size'] - len(output))
        chunk = data[position:position + size]
        if len(chunk) != size:
            raise ValueError(f'Compressed block {index} is truncated.')
        result = chunk if size == expected else decode(chunk, expected)
        if len(result) != expected:
            raise ValueError(f'Oodle returned the wrong size for block {index}.')
        output.extend(result)
        position += size
    if len(output) != header['raw_size'] or position != header['offset'] + header['total_size']:
        raise ValueError('Decoded payload length or final block position is incorrect.')
    return output


def oodle_decoder():
    if sys.platform != 'win32' or not OODLE_DLL.is_file():
        raise RuntimeError(f'The locally installed Unreal 5.9 Oodle DLL is required: {OODLE_DLL}')
    library = ctypes.WinDLL(str(OODLE_DLL))
    function = library.OodleLZ_Decompress
    function.restype = ctypes.c_int64
    function.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_void_p, ctypes.c_int64,
                         ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int64,
                         ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int]

    def decompress(chunk, expected):
        source = ctypes.create_string_buffer(chunk, len(chunk))
        target = ctypes.create_string_buffer(expected)
        received = function(source, len(chunk), target, expected, 1, 0, 0, None, 0, None, None, None, 0, 3)
        if received != expected:
            raise ValueError(f'Oodle returned {received} of {expected} expected bytes.')
        return target.raw

    return decompress


def output_path(value):
    saved = SAVED.resolve(strict=True)
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT / path
    resolved = path.resolve()
    if (path.is_symlink() or not resolved.is_relative_to(saved) or resolved == saved
            or not resolved.parent.is_dir() or resolved.exists()):
        raise ValueError('Choose a fresh file inside the project Saved directory; its parent must exist.')
    return resolved


def run(output=DEFAULT_OUTPUT):
    destination = output_path(output)
    raw_asset = ASSET.read_bytes()
    if hashlib.sha256(raw_asset).hexdigest() != ASSET_SHA256:
        raise ValueError('Source uasset does not match the pinned SHA-256.')
    header = find_buffer(raw_asset)
    if ((header['offset'], header['codec'], header['level'], header['exponent'], header['count'],
         header['raw_size'], header['total_size'], header['raw_hash']) !=
            (81133, 3, 3, 18, 52, 13390229, 1623280, RAW_BLAKE3)):
        raise ValueError('The source compressed-buffer layout or BLAKE3 is not the pinned version.')
    sys.path.insert(0, str(DEPENDENCIES))
    try:
        from blake3 import blake3
    except ImportError as error:
        raise RuntimeError('Install the external blake3 module in Saved/CityPCG/OfflineGeometryDeps or the active Python environment.') from error
    payload = decode_blocks(raw_asset, header, oodle_decoder())
    if (blake3(payload).digest() != RAW_BLAKE3 or hashlib.sha256(payload).hexdigest() != RAW_SHA256
            or hashlib.sha256(ASSET.read_bytes()).hexdigest() != ASSET_SHA256):
        raise ValueError('Payload hash or source asset hash changed during decoding.')
    # Re-resolve immediately before creating the file. Exclusive creation
    # rejects an output that appeared during decoding.
    if output_path(output) != destination:
        raise RuntimeError('Output path changed during decoding.')
    with destination.open('xb') as file:
        file.write(payload)
    return {'asset_sha256': ASSET_SHA256, 'payload_sha256': RAW_SHA256,
            'payload_blake3': RAW_BLAKE3.hex(), 'payload_bytes': len(payload),
            'output': str(destination), 'runtime_activation_authorized': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT, help='Fresh output file under Saved.')
    args = parser.parse_args()
    import json
    print(json.dumps(run(args.output), indent=2))


if __name__ == '__main__':
    main()
