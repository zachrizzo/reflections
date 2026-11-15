"""Small synthetic guard and matching tests; never decompress real assets."""

from collections import Counter
import hashlib
import io
from pathlib import Path
import secrets
import subprocess
import unittest
from unittest import mock

import verify_west_mark_lane_saved_geometry as proof


class SavedGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = proof.EXTRACTOR.read_text(encoding="utf-8")

    def test_extractor_adapter_rejects_changed_code_and_invalid_hash(self):
        script = proof.extractor_for_payload(self.source, "a" * 64)
        self.assertIn(proof.ASSET_SHA, script)
        self.assertIn("a" * 64, script)
        self.assertIn("const payload = fs.readFileSync(payloadPath);", script)
        self.assertIn("sha(fs.readFileSync(payloadPath)) === expectedPayload", script)
        with self.assertRaisesRegex(ValueError, "extractor differs"):
            proof.extractor_for_payload(self.source + " ", "a" * 64)
        with self.assertRaisesRegex(ValueError, "payload SHA-256"):
            proof.extractor_for_payload(self.source, "invalid")

    def test_reserved_and_building_trains_fail_closed(self):
        def queue(text):
            return mock.patch.object(Path, "open", return_value=io.StringIO(text))
        with queue("!!! 04:45 TRAIN #21 LOADED: npc-unify proof round 1; others wait. !!!\n"):
            with self.assertRaisesRegex(RuntimeError, "reserves"):
                proof.train_window()
        with queue("!!! 04:45 TRAIN #21 BUILDING: editor closed. !!!\n"):
            with self.assertRaisesRegex(RuntimeError, "not LOADED"):
                proof.train_window()
        with queue("!!! 04:45 TRAIN #21 LOADED: queue clear. !!!\n"):
            self.assertEqual(proof.train_window(), "21")
        with queue("no recognizable train status\n"):
            with self.assertRaisesRegex(RuntimeError, "cannot be determined"):
                proof.train_window()

    def test_new_lease_and_memory_drop_stop_guard(self):
        gib = 1024 ** 3
        with mock.patch.object(proof, "window_open"), mock.patch.object(proof, "train_window", return_value="21"), \
                mock.patch.object(proof, "memory_headroom", return_value=(12*gib, 20*gib)), \
                mock.patch("os.path.lexists", return_value=False) as lock:
            guard = proof.Guard()
            lock.return_value = True
            with self.assertRaisesRegex(RuntimeError, "lease appeared"):
                guard.check()
        with mock.patch.object(proof, "window_open"), mock.patch.object(proof, "train_window", return_value="21"), \
                mock.patch.object(proof, "memory_headroom", side_effect=[(12*gib, 20*gib),
                                                                           (12*gib, 20*gib),
                                                                           (10*gib, 20*gib)]), \
                mock.patch("os.path.lexists", return_value=False):
            guard = proof.Guard()
            with self.assertRaisesRegex(RuntimeError, "memory fell"):
                guard.check(force=True)

    def test_wrong_asset_is_rejected_before_decompressing(self):
        with mock.patch.object(proof.decoder, "find_buffer") as find:
            with self.assertRaisesRegex(ValueError, "asset hash differs"):
                proof.decode_replacement(b"wrong", lambda: None, lambda *_: None, lambda *_: None)
            find.assert_not_called()

    def fresh_payload_path(self):
        return proof.PAYLOAD_DIR / ("WestBlockTile_mesh_payload_test_" + secrets.token_hex(8) + ".bin")

    def remove_own_test_file(self, path):
        if path.exists():
            root = proof.PAYLOAD_DIR.resolve(strict=True)
            if path.is_symlink() or path.resolve(strict=True).parent != root:
                raise RuntimeError("Refusing to remove a test file outside its intended directory")
            path.unlink()

    def test_payload_path_rejects_overwrite_and_outside_saved_directory(self):
        path = self.fresh_payload_path()
        try:
            with path.open("xb") as stream:
                stream.write(b"existing contents")
            with self.assertRaisesRegex(FileExistsError, "already exists"):
                proof.payload_path(path)
            self.assertEqual(path.read_bytes(), b"existing contents")
            outside = proof.PAYLOAD_DIR.parent / path.name
            with self.assertRaisesRegex(ValueError, "intended Saved folder"):
                proof.payload_path(outside)
            with self.assertRaisesRegex(ValueError, "filename"):
                proof.payload_path(proof.PAYLOAD_DIR / "unrelated.bin")
        finally:
            self.remove_own_test_file(path)

    def test_redirected_payload_directory_is_rejected(self):
        target = self.fresh_payload_path()
        intended = proof.PAYLOAD_DIR.absolute()
        fake_directory = mock.Mock()
        fake_directory.absolute.return_value = intended
        fake_directory.is_symlink.return_value = False
        fake_directory.is_junction.return_value = False
        fake_directory.resolve.return_value = intended.parent / "OtherSurvey"
        with mock.patch.object(proof, "PAYLOAD_DIR", fake_directory):
            with self.assertRaisesRegex(ValueError, "directory is redirected"):
                proof.payload_path(target)
            fake_directory.resolve.return_value = intended
            fake_directory.is_symlink.return_value = True
            with self.assertRaisesRegex(ValueError, "directory is redirected"):
                proof.payload_path(target)
            fake_directory.is_symlink.return_value = False
            fake_directory.is_junction.return_value = True
            with self.assertRaisesRegex(ValueError, "directory is redirected"):
                proof.payload_path(target)

    def test_lease_during_chunk_write_stops_and_retains_partial(self):
        path = self.fresh_payload_path()
        calls = 0
        def check():
            nonlocal calls
            calls += 1
            if calls == 3:
                raise RuntimeError("lease appeared")
        try:
            with self.assertRaisesRegex(RuntimeError, "lease appeared"):
                proof.save_verified_payload(path, b"A" * (256 * 1024 + 1), "unused", check, None)
            self.assertTrue(path.is_file())
            self.assertEqual(path.stat().st_size, 256 * 1024)
        finally:
            self.remove_own_test_file(path)

    def test_payload_is_read_back_before_parser_use(self):
        path = self.fresh_payload_path()
        data = b"synthetic-data" * 30000
        digest = hashlib.sha256(data).digest()
        try:
            with mock.patch.object(proof, "RAW_BLAKE3", digest):
                output = proof.save_verified_payload(path, data, digest.hex(), lambda: None, hashlib.sha256)
            self.assertEqual(output, path.resolve(strict=True))
            self.assertEqual(path.read_bytes(), data)
            with self.assertRaisesRegex(FileExistsError, "already exists"):
                proof.save_verified_payload(path, data, digest.hex(), lambda: None, hashlib.sha256)
        finally:
            self.remove_own_test_file(path)

    def test_geometry_mapping_is_order_independent_and_rejects_ambiguity(self):
        groups = [{"section": i, "slot": name, "triangles": [f"triangle-{i}"]}
                  for i, name in enumerate(proof.SLOTS)]
        primitives = [Counter({f"triangle-{i}": 1}) for i in reversed(range(6))]
        names = list(reversed(proof.SLOTS))
        result = proof.compare_groups(groups, primitives, names)
        self.assertEqual([x["glb_primitive"] for x in result], list(reversed(range(6))))
        wrong = list(primitives)
        wrong[0] = Counter({"triangle-1": 1})
        with self.assertRaisesRegex(ValueError, "geometry"):
            proof.compare_groups(groups, wrong, names)
        names[0], names[1] = names[1], names[0]
        with self.assertRaisesRegex(ValueError, "slot names differ"):
            proof.compare_groups(groups, primitives, names)
        groups[1]["triangles"] = ["triangle-0"]
        with self.assertRaisesRegex(ValueError, "geometry"):
            proof.compare_groups(groups, primitives, list(reversed(proof.SLOTS)))

    def test_lease_change_kills_parser_child(self):
        class FakeChild:
            killed = False
            def poll(self):
                return 0 if self.killed else None
            def kill(self):
                self.killed = True
            def communicate(self, timeout=None):
                if not self.killed:
                    raise subprocess.TimeoutExpired("fake-node", timeout)
                return b"", b""
        class FakeGuard:
            calls = 0
            def check(self, force=False):
                self.calls += 1
                if self.calls == 3:
                    raise RuntimeError("lease appeared")
        child = FakeChild()
        retained_path = self.fresh_payload_path()
        with mock.patch.object(proof, "payload_path", return_value=retained_path), \
                mock.patch.object(proof.subprocess, "Popen", return_value=child) as popen:
            with self.assertRaisesRegex(RuntimeError, "lease appeared"):
                proof.extract_groups(retained_path, 12, "a" * 64, self.source, FakeGuard())
            self.assertEqual(popen.call_args.kwargs["stdin"], subprocess.DEVNULL)
            self.assertEqual(popen.call_args.args[0][-1], str(retained_path))
        self.assertTrue(child.killed)


if __name__ == "__main__":
    unittest.main()
