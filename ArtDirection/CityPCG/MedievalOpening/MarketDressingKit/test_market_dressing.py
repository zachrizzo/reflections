"""Tiny guard and geometry tests; no real kit or preview generation."""

import io
import json
import math
from pathlib import Path
import unittest
from unittest import mock

import build_market_dressing as kit


class MarketDressingTests(unittest.TestCase):
    def test_non_degenerate_triangle_and_explicit_obj_attributes(self):
        mesh = kit.Mesh("Synthetic")
        mesh.triangle((0., 0., 0.), (1., 0., 0.), (0., 1., 0.), "M_MarketOak")
        with self.assertRaisesRegex(ValueError, "Degenerate"):
            mesh.triangle((0., 0., 0.), (0., 0., 0.), (1., 0., 0.), "M_MarketOak")
        text = kit.obj_bytes(mesh).decode("utf-8")
        self.assertIn("mtllib LondonMarketProps.mtl", text)
        self.assertIn("usemtl M_MarketOak", text)
        self.assertIn("vn 0.0000000 0.0000000 1.0000000", text)
        self.assertIn("f 1/1/1 2/2/1 3/3/1", text)

    def test_prism_has_outward_winding(self):
        mesh = kit.Mesh("Box")
        kit.box(mesh, (0., 0., 0.), (2., 2., 2.), "M_MarketOak")
        self.assertEqual(len(mesh.triangles), 12)
        for points, _, normal in mesh.triangles:
            centroid = tuple(sum(point[i] for point in points) / 3 for i in range(3))
            self.assertGreater(kit.dot(centroid, normal), 0.)

    def test_each_trestle_leg_has_ground_and_board_contact(self):
        for y in (-0.63, 0.63):
            for foot_x, top_x in ((0.075, 0.30), (0.605, 0.38)):
                with self.subTest(y=y, foot_x=foot_x):
                    leg = kit.Mesh("Leg")
                    kit.trestle_leg(leg, foot_x, top_x, y)
                    ground = [(points, normal) for points, _, normal in leg.triangles
                              if all(point[2] == 0. for point in points)]
                    top = [(points, normal) for points, _, normal in leg.triangles
                           if all(point[2] == kit.BOARD_UNDERSIDE_Z for point in points)]
                    self.assertEqual(len(ground), 2)
                    self.assertEqual(len(top), 2)
                    self.assertTrue(all(normal[2] == -1. for _, normal in ground))
                    self.assertTrue(all(normal[2] == 1. for _, normal in top))
                    for points, _ in top:
                        center_x = sum(point[0] for point in points) / 3
                        center_y = sum(point[1] for point in points) / 3
                        self.assertTrue(0. <= center_x <= 0.68)
                        self.assertTrue(any(abs(center_y - (-0.70 + i * 0.20)) <= 0.194 / 2 for i in range(8)))
                    self.assertGreaterEqual(min(point[2] for points, _, _ in leg.triangles for point in points), 0.)
        mesh = kit.stallboard()
        ground_triangles = [points for points, _, _ in mesh.triangles if all(point[2] == 0. for point in points)]
        self.assertEqual(len(ground_triangles), 8)

    def test_three_props_have_finite_oriented_obj_geometry(self):
        meshes = [(kit.stallboard(), 372), (kit.turned_bowl(), 704), (kit.ale_stake(), 396)]
        self.assertLess(sum(len(mesh.triangles) for mesh, _ in meshes), kit.MAX_TRIANGLES)
        for mesh, expected in meshes:
            with self.subTest(mesh=mesh.name):
                positions, uvs, normals, faces = [], [], [], []
                for line in kit.obj_bytes(mesh).decode("utf-8").splitlines():
                    parts = line.split()
                    if not parts:
                        continue
                    if parts[0] in ("v", "vt", "vn"):
                        values = tuple(map(float, parts[1:]))
                        self.assertTrue(all(map(math.isfinite, values)))
                        {"v": positions, "vt": uvs, "vn": normals}[parts[0]].append(values)
                    elif parts[0] == "f":
                        faces.append([tuple(map(int, item.split("/"))) for item in parts[1:]])
                self.assertEqual(len(faces), expected)
                self.assertEqual(len(positions), 3 * expected)
                self.assertEqual(len(uvs), 3 * expected)
                self.assertEqual(len(normals), expected)
                for face in faces:
                    self.assertEqual(len(face), 3)
                    self.assertTrue(all(len(corner) == 3 and 1 <= corner[0] <= len(positions) and
                                        1 <= corner[1] <= len(uvs) and 1 <= corner[2] <= len(normals)
                                        for corner in face))
                    self.assertEqual(len({corner[2] for corner in face}), 1)
                    a, b, c = [positions[corner[0] - 1] for corner in face]
                    normal = normals[face[0][2] - 1]
                    self.assertAlmostEqual(kit.dot(normal, normal), 1., places=6)
                    # Check the emitted, rounded positions and normal, not just the in-memory inputs.
                    surface = kit.cross(kit.sub(b, a), kit.sub(c, a))
                    self.assertGreater(kit.dot(surface, normal), 1e-12)

    def test_bowl_bounds_ground_and_outward_surfaces(self):
        mesh = kit.turned_bowl()
        self.assertEqual(len(mesh.triangles), 32 * 22)
        points = [point for triangle, _, _ in mesh.triangles for point in triangle]
        for axis, (low, high) in enumerate(((-0.0975, 0.0975), (-0.0975, 0.0975), (0., 0.045))):
            self.assertAlmostEqual(min(point[axis] for point in points), low)
            self.assertAlmostEqual(max(point[axis] for point in points), high)
        for sector in range(32):
            faces = mesh.triangles[sector * 22:(sector + 1) * 22]
            self.assertAlmostEqual(faces[0][2][2], -1.)
            self.assertAlmostEqual(faces[11][2][2], 1.)
            self.assertAlmostEqual(faces[12][2][2], 1.)
            self.assertAlmostEqual(faces[21][2][2], 1.)
            for indexes, direction in ((range(1, 11), 1), (range(13, 21), -1)):
                for index in indexes:
                    triangle, _, normal = faces[index]
                    center = tuple(sum(point[i] for point in triangle) / 3 for i in range(3))
                    self.assertGreater(direction * (center[0]*normal[0] + center[1]*normal[1]), 0.)
        volume = sum(kit.dot(triangle[0], kit.cross(triangle[1], triangle[2]))
                     for triangle, _, _ in mesh.triangles) / 6
        self.assertGreater(volume, 0.)

    def test_ale_stake_mount_and_projection_bounds(self):
        mesh = kit.ale_stake()
        mount = [point for triangle, _, _ in mesh.triangles[:12] for point in triangle]
        for axis in range(3):
            self.assertLess(min(point[axis] for point in mount), 0.)
            self.assertGreater(max(point[axis] for point in mount), 0.)
        all_points = [point for triangle, _, _ in mesh.triangles for point in triangle]
        self.assertAlmostEqual(min(point[0] for point in all_points), -0.0375)
        self.assertGreater(max(point[0] for point in all_points), 1.2)
        self.assertLess(max(point[0] for point in all_points), 1.31)
        self.assertAlmostEqual(max(point[2] for point in all_points), 0.23)
        self.assertGreater(min(point[2] for point in all_points), -0.68)
        self.assertEqual({material for _, material, _ in mesh.triangles},
                         {"M_MarketOak", "M_MarketOakDark", "M_MarketIron", "M_MarketIvy", "M_MarketIvyLight"})

    def test_only_loaded_train_is_allowed(self):
        def queue(line):
            return mock.patch.object(Path, "open", return_value=io.StringIO(line))
        with queue("!!! 05:22 TRAIN #23 LOADED: NPC PIE. !!!\n"):
            self.assertEqual(kit.loaded_train(), "23")
        for text in ("!!! 05:22 TRAIN #23 BUILDING. !!!\n", "!!! 05:22 TRAIN #23 LOADED: editor closed. !!!\n"):
            with queue(text), self.assertRaises(RuntimeError):
                kit.loaded_train()

    def test_pie_lease_is_allowed_but_restart_or_malformed_lease_is_not(self):
        lock = {"owner": "npc", "purpose": "NPC PIE appearance check"}
        with mock.patch("os.path.lexists", return_value=True), \
                mock.patch.object(Path, "read_text", return_value=json.dumps(lock)) as read:
            kit.no_restart_lease()
            read.return_value = json.dumps({"owner": "orchestrator", "purpose": "restart then NPC check"})
            with self.assertRaisesRegex(RuntimeError, "restart"):
                kit.no_restart_lease()
            read.return_value = "{}"
            with self.assertRaisesRegex(RuntimeError, "purpose"):
                kit.no_restart_lease()

    def test_guard_stops_for_compiler_memory_and_closed_editor(self):
        gib = 1024**3
        editor = {"name": "unrealeditor.exe", "pid": 100, "parent_pid": 1}
        compiler = {"name": "cl.exe", "pid": 101, "parent_pid": 1}
        with mock.patch.object(kit, "loaded_train", return_value="23"), \
                mock.patch.object(kit, "no_restart_lease"), \
                mock.patch.object(kit, "process_snapshot", return_value=[editor]) as processes, \
                mock.patch.object(kit, "memory_status", return_value=(12*gib, 20*gib, 30*1024**2)) as memory:
            guard = kit.LightGuard()
            processes.return_value = [editor, compiler]
            with self.assertRaisesRegex(RuntimeError, "Compiler"):
                guard.check(force=True)
            processes.return_value = [editor]
            memory.return_value = (3*gib, 20*gib, 30*1024**2)
            with self.assertRaisesRegex(RuntimeError, "memory"):
                guard.check(force=True)
            memory.return_value = (12*gib, 20*gib, 161*1024**2)
            with self.assertRaisesRegex(RuntimeError, "memory"):
                guard.check(force=True)
            processes.return_value = [{"name": "other.exe", "pid": 102, "parent_pid": 1}]
            with self.assertRaisesRegex(RuntimeError, "not returned"):
                guard.check(force=True)

    def test_guard_stops_after_time_budget(self):
        gib = 1024**3
        with mock.patch.object(kit, "loaded_train", return_value="23"), \
                mock.patch.object(kit, "no_restart_lease"), \
                mock.patch.object(kit, "process_snapshot", return_value=[{"name": "unrealeditor.exe", "pid": 100, "parent_pid": 1}]), \
                mock.patch.object(kit, "memory_status", return_value=(12*gib, 20*gib, 30*1024**2)):
            guard = kit.LightGuard()
            guard.started -= kit.MAX_SECONDS + 1
            with self.assertRaisesRegex(RuntimeError, "time budget"):
                guard.check()

    def test_only_identified_gigabyte_parent_with_matching_child_is_exempt(self):
        editor = {"name": "UnrealEditor.exe", "pid": 100, "parent_pid": 1}
        app = {"name": "GCC.exe", "pid": 200, "parent_pid": 1}
        child = {"name": "GBT_DL_LIB.exe", "pid": 201, "parent_pid": 200}
        identities = {200: {"path": kit.GIGABYTE_GCC, "created": 10},
                      201: {"path": r"C:\Program Files\GIGABYTE\Control Center\GBT_DL_LIB.exe", "created": 11}}
        identity = lambda pid: identities.get(pid)
        running, blocked = kit.classify_processes([editor, app, child], identity)
        self.assertTrue(running)
        self.assertEqual(blocked, [])
        other_gcc = {"name": "gcc.exe", "pid": 202, "parent_pid": 1}
        _, blocked = kit.classify_processes([editor, app, child, other_gcc], identity)
        self.assertEqual(blocked, ["gcc.exe (pid 202)"])
        _, blocked = kit.classify_processes([editor, app], identity)
        self.assertEqual(blocked, ["gcc.exe (pid 200)"])
        unrelated_child = dict(child, parent_pid=999)
        _, blocked = kit.classify_processes([editor, app, unrelated_child], identity)
        self.assertEqual(blocked, ["gcc.exe (pid 200)"])
        cl = {"name": "cl.exe", "pid": 203, "parent_pid": 1}
        _, blocked = kit.classify_processes([editor, app, child, cl], identity)
        self.assertEqual(blocked, ["cl.exe (pid 203)"])

    def test_missing_identity_wrong_path_or_reused_parent_pid_still_blocks(self):
        app = {"name": "gcc.exe", "pid": 200, "parent_pid": 1}
        child = {"name": "GBT_DL_LIB.exe", "pid": 201, "parent_pid": 200}
        valid_child = {"path": r"C:\Program Files\GIGABYTE\Control Center\GBT_DL_LIB.exe", "created": 11}
        cases = [None, {"path": r"C:\compiler\gcc.exe", "created": 10},
                 {"path": kit.GIGABYTE_GCC, "created": 12}]
        for parent in cases:
            identity = lambda pid: parent if pid == 200 else valid_child
            with self.subTest(parent=parent):
                _, blocked = kit.classify_processes([app, child], identity)
                self.assertEqual(blocked, ["gcc.exe (pid 200)"])
        _, blocked = kit.classify_processes([app, child], lambda pid: None)
        self.assertEqual(blocked, ["gcc.exe (pid 200)"])

    def test_unreadable_or_ambiguous_snapshot_fails_closed(self):
        for records in ([], [{"name": "gcc.exe", "pid": 1}],
                        [{"name": "gcc.exe", "pid": 1, "parent_pid": 0},
                         {"name": "unrealeditor.exe", "pid": 1, "parent_pid": 0}]):
            with self.subTest(records=records), self.assertRaises(RuntimeError):
                kit.classify_processes(records, lambda _: None)
        with mock.patch.object(kit, "loaded_train", return_value="23"), \
                mock.patch.object(kit, "no_restart_lease"), \
                mock.patch.object(kit, "process_snapshot", side_effect=OSError("unreadable")):
            with self.assertRaisesRegex(OSError, "unreadable"):
                kit.LightGuard()


if __name__ == "__main__":
    unittest.main()
