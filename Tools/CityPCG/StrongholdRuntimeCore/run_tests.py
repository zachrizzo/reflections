"""Compile and run the independent stronghold rules without launching Unreal."""

import ctypes
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).resolve().parent
OUTPUT = ROOT / 'Saved/CityPCG/StrongholdRuntimeCoreTests'
TRAIN_STATUS = re.compile(r'\bTRAIN\s*#\d+\s+([A-Z][A-Z_-]*)\b')


def current_train_status(queue_text):
    """The queue puts the newest explicit train status above older entries."""
    for line in queue_text.splitlines():
        match = TRAIN_STATUS.search(line)
        if match:
            return match.group(1)
    return None


def editor_available():
    lock = ROOT / 'Saved/PIE_LOCK.json'
    if lock.exists() or lock.is_symlink():
        print('The shared editor lock exists; waiting for it to be released.')
        return False
    queue = ROOT / 'Saved/PIE_QUEUE.md'
    if queue.is_file():
        status = current_train_status(queue.read_text(encoding='utf-8-sig'))
        if status is not None and status != 'LOADED':
            print(f'The shared Unreal build train has not reported LOADED (current status: {status}).')
            return False
    return True


def memory_ok():
    if sys.platform != 'win32':
        return True

    class MemoryStatus(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong),
                    ('total_physical', ctypes.c_ulonglong), ('free_physical', ctypes.c_ulonglong),
                    ('total_page_file', ctypes.c_ulonglong), ('free_page_file', ctypes.c_ulonglong),
                    ('total_virtual', ctypes.c_ulonglong), ('free_virtual', ctypes.c_ulonglong),
                    ('free_extended_virtual', ctypes.c_ulonglong)]

    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise RuntimeError('Cannot check available Windows memory')
    print(f'Available memory: {status.free_physical / 2**30:.2f} GiB physical, '
          f'{status.free_page_file / 2**30:.2f} GiB commit')
    return status.free_physical >= 4 * 2**30 and status.free_page_file >= 10 * 2**30


def windows_compiler():
    locator = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / \
        'Microsoft Visual Studio/Installer/vswhere.exe'
    if not locator.is_file():
        raise RuntimeError('Visual Studio vswhere.exe is not installed')
    result = subprocess.run([str(locator), '-latest', '-products', '*', '-requires',
                             'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
                             '-property', 'installationPath'], capture_output=True, text=True, check=True)
    installation = Path(result.stdout.strip())
    vcvars = installation / 'VC/Auxiliary/Build/vcvars64.bat'
    if not vcvars.is_file() or any(char in str(vcvars) for char in ('"', '\r', '\n', '%', '!')):
        raise RuntimeError('Cannot locate a safe Visual Studio x64 environment script')
    # Capture the environment in memory; do not print or write its values.
    result = subprocess.run(f'call "{vcvars}" >nul && set', shell=True, capture_output=True, text=True, check=True)
    environment = {key.upper(): value for key, value in os.environ.items()}
    for line in result.stdout.splitlines():
        if '=' in line and not line.startswith('='):
            key, value = line.split('=', 1)
            environment[key.upper()] = value
    compiler = Path(environment['VCTOOLSINSTALLDIR']) / 'bin/Hostx64/x64/cl.exe'
    if not compiler.is_file():
        raise RuntimeError('The Visual Studio x64 compiler was not found')
    return compiler, environment


def main():
    if not editor_available():
        raise RuntimeError('Wait until the shared editor lock and build train are clear before compiling')
    if not memory_ok():
        raise RuntimeError('Wait for at least 4 GiB physical and 10 GiB commit memory before compiling')
    if sys.platform == 'win32':
        compiler, environment = windows_compiler()
        args = [str(compiler), '/nologo', '/std:c++17', '/EHsc', '/W4', '/WX', '/Fe:stronghold_tests.exe']
        binary = 'stronghold_tests.exe'
    else:
        compiler = shutil.which('c++')
        if not compiler:
            raise RuntimeError('A C++17 compiler is required')
        environment = os.environ.copy()
        args = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', '-o', 'stronghold_tests']
        binary = 'stronghold_tests'
    if not editor_available() or not memory_ok():
        raise RuntimeError('The shared editor or memory became unavailable before compilation')
    output = OUTPUT / ('run_' + uuid.uuid4().hex)
    output.mkdir(parents=True)
    args.extend(str(SOURCE / name) for name in ('StrongholdCampaign.cpp', 'test_stronghold_campaign.cpp'))
    subprocess.run(args, cwd=output, env=environment, check=True)
    subprocess.run([str(output / binary)], cwd=output, check=True)
    print(f'Artifacts: {output}')


if __name__ == '__main__':
    main()
