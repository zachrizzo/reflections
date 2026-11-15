"""Small local tests for the guarded, resumable model download."""

import hashlib
import io
from itertools import count
from pathlib import Path
from tempfile import TemporaryDirectory, gettempdir
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import fetch_triposr_weights as fetch


class Response(io.BytesIO):
    def __init__(self, data, status, content_range):
        super().__init__(data)
        self.status = status
        self.headers = {'Content-Range': content_range}


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        project = Path(self.temp.name).resolve()
        temp_root = Path(gettempdir()).resolve()
        self.assertEqual(project.parent, temp_root)
        def cleanup():
            if Path(self.temp.name).is_symlink() or Path(self.temp.name).resolve().parent != temp_root:
                raise RuntimeError('Temporary test directory was redirected')
            self.temp.cleanup()
        self.addCleanup(cleanup)
        root = project / 'Saved/CityPCG/ImageTo3D/TripoSR-model'
        root.mkdir(parents=True)
        self.root = root
        self.data = b'0123456789ABCDEF'
        self.patchers = [
            patch.object(fetch, 'PROJECT', project),
            patch.object(fetch, 'ROOT', root),
            patch.object(fetch, 'SIZE', len(self.data)),
            patch.object(fetch, 'SHA256', hashlib.sha256(self.data).hexdigest()),
            patch.object(fetch, 'CHUNK', 4),
            patch.object(fetch, 'window_open'),
        ]
        for item in self.patchers:
            item.start()
            self.addCleanup(item.stop)

    def response(self, start):
        return Response(self.data[start:], 206, f'bytes {start}-{len(self.data)-1}/{len(self.data)}')

    def test_new_download_verifies_and_publishes(self):
        with patch.object(fetch, 'urlopen', return_value=self.response(0)) as request:
            fetch.main()
        self.assertEqual((self.root / 'model.ckpt').read_bytes(), self.data)
        self.assertFalse((self.root / 'model.ckpt.partial').exists())
        self.assertEqual(request.call_args.args[0].get_header('Range'), 'bytes=0-')

    def test_resume_appends_only_the_requested_remaining_bytes(self):
        (self.root / 'model.ckpt.partial').write_bytes(self.data[:5])
        with patch.object(fetch, 'urlopen', return_value=self.response(5)) as request:
            fetch.main()
        self.assertEqual((self.root / 'model.ckpt').read_bytes(), self.data)
        self.assertEqual(request.call_args.args[0].get_header('Range'), 'bytes=5-')

    def test_rejects_wrong_range_without_changing_partial(self):
        partial = self.root / 'model.ckpt.partial'
        partial.write_bytes(self.data[:5])
        with patch.object(fetch, 'urlopen', return_value=self.response(0)):
            with self.assertRaisesRegex(RuntimeError, 'unexpected content range'):
                fetch.main()
        self.assertEqual(partial.read_bytes(), self.data[:5])
        self.assertFalse((self.root / 'model.ckpt').exists())

    def test_hash_mismatch_retains_partial_without_publishing(self):
        with patch.object(fetch, 'SHA256', '0' * 64), patch.object(fetch, 'urlopen', return_value=self.response(0)):
            with self.assertRaisesRegex(RuntimeError, 'SHA-256'):
                fetch.main()
        self.assertEqual((self.root / 'model.ckpt.partial').read_bytes(), self.data)
        self.assertFalse((self.root / 'model.ckpt').exists())

    def test_active_editor_prevents_network_access(self):
        with patch.object(fetch, 'window_open', side_effect=RuntimeError('lease held')), patch.object(fetch, 'urlopen') as request:
            fetch.main()
        request.assert_not_called()
        self.assertFalse((self.root / 'model.ckpt.partial').exists())


    def test_new_lease_pauses_a_partial_download(self):
        ticks = count()
        with patch.object(fetch, 'window_open', side_effect=[None, None, RuntimeError('lease held')]), \
             patch.object(fetch, 'urlopen', return_value=self.response(0)), \
             patch.object(fetch.time, 'monotonic', side_effect=lambda: next(ticks) * 1.1):
            fetch.main()
        self.assertEqual((self.root / 'model.ckpt.partial').read_bytes(), self.data[:4])
        self.assertFalse((self.root / 'model.ckpt').exists())


class EditorStateTests(unittest.TestCase):
    def test_closed_editor_is_not_treated_as_an_idle_window(self):
        with patch.object(fetch, 'require_editor_available'), patch.object(fetch, 'require_memory'), \
             patch.object(fetch.Path, 'exists', return_value=False), patch.object(fetch.Path, 'is_symlink', return_value=False), \
             patch.object(fetch.sys, 'platform', 'win32'), \
             patch.object(fetch.subprocess, 'run', return_value=SimpleNamespace(stdout='INFO: No tasks found.')):
            with self.assertRaisesRegex(RuntimeError, 'closed or restarting'):
                fetch.window_open()

    def test_running_editor_allows_window_after_other_guards(self):
        with patch.object(fetch, 'require_editor_available'), patch.object(fetch, 'require_memory'), \
             patch.object(fetch.Path, 'exists', return_value=False), patch.object(fetch.Path, 'is_symlink', return_value=False), \
             patch.object(fetch.sys, 'platform', 'win32'), \
             patch.object(fetch.subprocess, 'run', return_value=SimpleNamespace(stdout='"UnrealEditor.exe","123","Console"\n')):
            fetch.window_open()

    def test_any_lease_file_blocks_even_before_its_expiration_is_examined(self):
        with patch.object(fetch.Path, 'exists', return_value=True), patch.object(fetch, 'require_editor_available') as check:
            with self.assertRaisesRegex(RuntimeError, 'lease file'):
                fetch.window_open()
        check.assert_not_called()


if __name__ == '__main__':
    unittest.main()
