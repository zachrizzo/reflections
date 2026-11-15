"""Fetch a pinned TripoSR checkpoint in short, resumable, guarded sessions."""

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import Request, urlopen

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / 'Tools/CityPCG'))
from build_grouped_tile_derivatives import require_editor_available, require_memory

ROOT = (PROJECT / 'Saved/CityPCG/ImageTo3D/TripoSR-model').resolve()
REV = '5b521936b01fbe1890f6f9baed0254ab6351c04a'
URL = f'https://huggingface.co/stabilityai/TripoSR/resolve/{REV}/model.ckpt'
SIZE = 1677246742
SHA256 = '429e2c6b22a0923967459de24d67f05962b235f79cde6b032aa7ed2ffcd970ee'
CHUNK = 256 * 1024
MAX_BYTES_PER_SECOND = 16 * 1024 * 1024


def window_open():
    lock = PROJECT / 'Saved/PIE_LOCK.json'
    if lock.exists() or lock.is_symlink():
        raise RuntimeError('A shared editor lease file is present; defer the download')
    require_editor_available()
    require_memory()
    if sys.platform != 'win32':
        raise RuntimeError('The shared-editor process check requires Windows')
    result = subprocess.run(
        ['tasklist.exe', '/FI', 'IMAGENAME eq UnrealEditor.exe', '/NH', '/FO', 'CSV'],
        capture_output=True, text=True, timeout=5, check=True,
    )
    if not any(line.lower().startswith('"unrealeditor.exe",') for line in result.stdout.splitlines()):
        raise RuntimeError('The shared editor is closed or restarting; defer the download')


def verify_location(path):
    saved = (PROJECT / 'Saved').resolve(strict=True)
    if (not ROOT.is_relative_to(saved) or ROOT.resolve(strict=True) != ROOT
            or path.parent != ROOT or path.resolve().parent != ROOT or path.is_symlink()):
        raise RuntimeError('Model path is redirected outside its intended Saved folder')


def main():
    final = ROOT / 'model.ckpt'
    partial = ROOT / 'model.ckpt.partial'
    verify_location(final)
    verify_location(partial)
    if final.exists():
        print('The final checkpoint already exists; verify its hash before use.')
        return
    try:
        window_open()
    except RuntimeError as error:
        print(f'Download deferred: {error}', flush=True)
        return
    offset = partial.stat().st_size if partial.exists() else 0
    if offset > SIZE:
        raise RuntimeError('The retained partial exceeds the official file size')
    started = time.monotonic()
    initial_offset = offset
    deadline = started + 25
    if offset < SIZE:
        request = Request(URL, headers={'Range': f'bytes={offset}-', 'User-Agent': 'GrayLondonAssetPrep/1.0'})
        with urlopen(request, timeout=15) as response:
            if response.status == 206:
                expected = f'bytes {offset}-{SIZE - 1}/{SIZE}'
                if response.headers.get('Content-Range') != expected:
                    raise RuntimeError('The server returned an unexpected content range')
            elif response.status != 200 or offset:
                raise RuntimeError('The server did not honor the requested resume offset')
            mode = 'ab' if partial.exists() else 'xb'
            with partial.open(mode) as output:
                last_check = 0.0
                while offset < SIZE and time.monotonic() < deadline:
                    if time.monotonic() - last_check >= 1:
                        try:
                            window_open()
                        except RuntimeError as error:
                            print(f'Paused safely at {offset} bytes: {error}', flush=True)
                            return
                        last_check = time.monotonic()
                    data = response.read(min(CHUNK, SIZE - offset))
                    if not data:
                        break
                    output.write(data)
                    offset += len(data)
                    delay = (offset - initial_offset) / MAX_BYTES_PER_SECOND - (time.monotonic() - started)
                    if delay > 0:
                        time.sleep(min(delay, .05))
        print(f'Retained {offset} of {SIZE} bytes', flush=True)
    if offset != SIZE:
        return
    window_open()
    digest = hashlib.sha256()
    with partial.open('rb') as source:
        checked = 0
        while True:
            data = source.read(2 * 1024 * 1024)
            if not data:
                break
            digest.update(data)
            checked += len(data)
            if checked >= 64 * 1024 * 1024:
                try:
                    window_open()
                except RuntimeError as error:
                    print(f'Verification paused; full partial retained: {error}', flush=True)
                    return
                checked = 0
    if digest.hexdigest() != SHA256:
        raise RuntimeError('Downloaded checkpoint does not match the official pinned SHA-256')
    window_open()
    verify_location(partial)
    verify_location(final)
    if os.path.lexists(final):
        raise FileExistsError('The final checkpoint appeared before publication')
    partial.rename(final)
    print(f'Pinned checkpoint verified: {SHA256}', flush=True)


if __name__ == '__main__':
    main()
