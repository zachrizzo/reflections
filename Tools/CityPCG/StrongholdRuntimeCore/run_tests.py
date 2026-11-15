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
TRAIN_HEADER = re.compile(r'^\s*!*\s*(?:\d{1,2}:\d{2}\s+)?TRAIN\s*#\s*\d+\b(.*)$', re.IGNORECASE)
TRAIN_STATUS = re.compile(r'\s*:?\s*([A-Za-z][A-Za-z_-]*)\b')
POLL_SECONDS = 0.5

# This process waits for one byte before it can start cl.exe. The supervisor
# first puts it in its private job, so every compiler/linker descendant is
# inside that same job before the byte is sent. EOF also exits without work.
BLOCKED_LAUNCHER = (
    'import subprocess,sys\n'
    'if sys.stdin.buffer.read(1) != b"1": sys.exit(125)\n'
    'sys.exit(subprocess.call(sys.argv[1:]))\n'
)


def current_train_status(queue_text):
    """The newest train header controls; an unreadable status fails closed."""
    for line in queue_text.splitlines():
        header = TRAIN_HEADER.match(line)
        if header:
            match = TRAIN_STATUS.match(header.group(1))
            return match.group(1).upper() if match else None
    return None


def editor_available():
    lock = ROOT / 'Saved/PIE_LOCK.json'
    if lock.exists() or lock.is_symlink():
        print('The shared editor lock exists; waiting for it to be released.')
        return False
    queue = ROOT / 'Saved/PIE_QUEUE.md'
    if not queue.is_file():
        print('Cannot read the shared Unreal build train queue.')
        return False
    status = current_train_status(queue.read_text(encoding='utf-8-sig'))
    if status != 'LOADED':
        print(f'The shared Unreal build train has not reported LOADED (current status: {status}).')
        return False
    return True


def memory_ok(*, verbose=True):
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
    enough = status.free_physical >= 4 * 2**30 and status.free_page_file >= 10 * 2**30
    if verbose or not enough:
        print(f'Available memory: {status.free_physical / 2**30:.2f} GiB physical, '
              f'{status.free_page_file / 2**30:.2f} GiB commit')
    return enough


def shared_editor_running():
    """Fail closed if the shared Windows editor is absent or cannot be checked."""
    if sys.platform != 'win32':
        raise RuntimeError('The shared-editor process check requires Windows')
    try:
        result = subprocess.run(
            ['tasklist.exe', '/FI', 'IMAGENAME eq UnrealEditor.exe', '/NH', '/FO', 'CSV'],
            capture_output=True, text=True, timeout=1, check=True,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError('Cannot confirm the shared editor is running') from error
    return any(line.lower().startswith('"unrealeditor.exe",') for line in result.stdout.splitlines())


def session_guard():
    if not editor_available():
        raise RuntimeError('The shared editor lease or build train is active')
    if not memory_ok(verbose=False):
        raise RuntimeError('Need at least 4 GiB physical and 10 GiB commit memory')
    if not shared_editor_running():
        raise RuntimeError('The shared editor is closed or restarting')
    # Checking the process list takes time; check the other guards again before
    # starting or resuming our child, and on each subsequent polling iteration.
    if not editor_available() or not memory_ok(verbose=False):
        raise RuntimeError('The shared editor or memory became unavailable')


class WindowsJob:
    """Unnamed, non-inheritable job that kills only our launched process tree."""

    def __init__(self):
        if sys.platform != 'win32':
            raise RuntimeError('The isolated process job requires Windows')
        from ctypes import wintypes

        class BasicLimits(ctypes.Structure):
            _fields_ = [
                ('process_user_time', ctypes.c_longlong), ('job_user_time', ctypes.c_longlong),
                ('flags', wintypes.DWORD), ('min_working_set', ctypes.c_size_t),
                ('max_working_set', ctypes.c_size_t), ('active_process_limit', wintypes.DWORD),
                ('affinity', ctypes.c_size_t), ('priority_class', wintypes.DWORD),
                ('scheduling_class', wintypes.DWORD),
            ]

        class IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in (
                'read_operations', 'write_operations', 'other_operations',
                'read_bytes', 'write_bytes', 'other_bytes')]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [
                ('basic', BasicLimits), ('io', IoCounters),
                ('process_memory_limit', ctypes.c_size_t), ('job_memory_limit', ctypes.c_size_t),
                ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t),
            ]

        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel.SetInformationJobObject.restype = wintypes.BOOL
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        self.kernel = kernel
        self.handle = kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.basic.flags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def assign(self, process):
        if not self.kernel.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:
            handle, self.handle = self.handle, None
            if not self.kernel.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())


def watch_child(process, args):
    """Check throughout this invocation, including after the child finishes."""
    while True:
        session_guard()
        try:
            code = process.wait(timeout=POLL_SECONDS)
        except subprocess.TimeoutExpired:
            continue
        session_guard()
        if code:
            raise subprocess.CalledProcessError(code, args)
        return


def run_guarded(args, *, cwd, env):
    """Supervise one command, terminating only its private process tree."""
    session_guard()
    job = WindowsJob()
    process = None
    assigned = False
    try:
        process = subprocess.Popen(
            [sys.executable, '-B', '-c', BLOCKED_LAUNCHER, *args],
            stdin=subprocess.PIPE, cwd=cwd, env=env,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        job.assign(process)
        assigned = True
        session_guard()
        process.stdin.write(b'1')
        process.stdin.close()
        watch_child(process, args)
    except BaseException:
        # Assignment failure leaves just the blocked launcher outside the job.
        # It has not started cl.exe and is the only process we may terminate.
        if process is not None and not assigned and process.poll() is None:
            process.terminate()
        raise
    finally:
        try:
            if process is not None and process.stdin is not None and not process.stdin.closed:
                process.stdin.close()
        finally:
            # KILL_ON_JOB_CLOSE stops the assigned launcher and all of its
            # compiler descendants, even if closing the launch pipe failed.
            try:
                job.close()
            finally:
                if process is not None and process.poll() is None:
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        if assigned:
                            raise RuntimeError('The isolated process did not exit after closing its job')
                        process.kill()
                        process.wait(timeout=5)


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
    session_guard()
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
    output = OUTPUT / ('run_' + uuid.uuid4().hex)
    output.mkdir(parents=True)
    args.extend(str(SOURCE / name) for name in ('StrongholdCampaign.cpp', 'test_stronghold_campaign.cpp'))
    run_guarded(args, cwd=output, env=environment)
    run_guarded([str(output / binary)], cwd=output, env=environment)
    print(f'Artifacts: {output}')


if __name__ == '__main__':
    main()
