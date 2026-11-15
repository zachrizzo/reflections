"""Exercise Mark Lane preview recovery without importing or opening Unreal."""

import json
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import preview_west_mark_lane_unreal as qa


OWNER = 'west mark lane preview test'


def vector(x, y, z):
    return SimpleNamespace(x=x, y=y, z=z)


def rotation(*_):
    return SimpleNamespace(pitch=0, yaw=0, roll=0)


class Component:
    def __init__(self, mesh):
        self.properties = {'static_mesh': mesh, 'can_ever_affect_navigation': True}
        self.profile = 'BlockAll'

    def get_editor_property(self, key):
        return self.properties[key]

    def set_editor_property(self, key, value):
        self.properties[key] = value

    def get_collision_enabled(self):
        return 'QueryAndPhysics'

    def get_collision_profile_name(self):
        return self.profile

    def set_collision_profile_name(self, value):
        self.profile = value


class Actor:
    def __init__(self, path, mesh=None, position=None, facing=None):
        self.path = path
        self.component = Component(mesh)
        self.location = position
        self.rotation = facing
        self.scale = vector(1, 1, 1)
        self.collision = True
        self.hidden = False

    def get_path_name(self):
        return self.path

    def get_component_by_class(self, _):
        return self.component

    def set_actor_enable_collision(self, enabled):
        self.collision = enabled

    def get_actor_enable_collision(self):
        return self.collision

    def set_actor_scale3d(self, scale):
        self.scale = scale

    def get_actor_scale3d(self):
        return self.scale

    def get_actor_location(self):
        return self.location

    def get_actor_rotation(self):
        return self.rotation

    def set_is_temporarily_hidden_in_editor(self, hidden):
        self.hidden = hidden

    def is_temporarily_hidden_in_editor(self, _):
        return self.hidden


class PreviewTests(unittest.TestCase):
    def setUp(self):
        temp = self.enterContext(TemporaryDirectory())
        self.directory = Path(temp)
        self.lease_file = self.directory / 'PIE_LOCK.json'
        self.protected = self.directory / 'original.uasset'
        self.protected.write_bytes(b'original city tile')
        self.original_camera = (vector(10, 10, 10), rotation())
        self.camera = self.original_camera
        self.source = Actor('source')
        self.original_selection = [Actor('selected'), self.source]
        self.selection = self.original_selection.copy()
        self.spawned = []
        self.captures = 0
        self.fail_capture = False
        self.fail_spawn = False
        self.world = SimpleNamespace(get_path_name=lambda: f'{qa.LEVEL}.GrayLondon_Geodata')
        self.viewport = SimpleNamespace(get_editor_world=lambda: self.world,
                                        get_level_viewport_camera_info=lambda: self.camera,
                                        set_level_viewport_camera_info=self.move_camera)
        self.unreal = SimpleNamespace(
            Vector=vector, StaticMeshComponent=object(), UnrealEditorSubsystem=object(),
            EditorLevelLibrary=SimpleNamespace(get_pie_worlds=lambda _: []),
            get_editor_subsystem=lambda _: self.viewport,
            MathLibrary=SimpleNamespace(find_look_at_rotation=rotation),
            AutomationLibrary=SimpleNamespace(take_high_res_screenshot=self.capture),
            register_slate_post_tick_callback=lambda _: 1,
            unregister_slate_post_tick_callback=lambda _: None,
        )
        self.enterContext(patch.dict(sys.modules, unreal=self.unreal))
        self.enterContext(patch.multiple(qa, SAVED=self.directory, OUT=self.directory,
                                         preflight=self.preflight, dirty_paths=lambda _: set()))
        self.write_lease()

    def write_lease(self, owner=OWNER, seconds=180):
        current = time.time()
        self.lease_file.write_text(json.dumps({'owner': owner, 'acquired_epoch': current,
                                               'expires_epoch': current + seconds, 'expires_local': 'then'}))

    def preflight(self, unreal, owner, *, preview=False):
        view, world, lock = qa.editor_available(unreal, owner, require_lease=preview,
                                                minimum_seconds=qa.MINIMUM_LEASE_SECONDS if preview else 0)
        mesh = SimpleNamespace(get_name=lambda: 'replacement')
        placements = [(mesh, vector(12, 13, 14), rotation(), vector(1, 1, 1))] * 4
        source_contract = {'actor_package': '/Game/Test/A', 'source_asset': '/Game/Test/T.T'}
        return view, self, world, lock, self.source, source_contract, placements, self.camera, [self.protected]

    def move_camera(self, location, facing):
        self.camera = (location, facing)

    def get_selected_level_actors(self):
        return self.selection.copy()

    def set_selected_level_actors(self, actors):
        self.selection = list(actors)

    def spawn_actor_from_object(self, mesh, position, facing, *, transient):
        self.assertTrue(transient)
        if self.fail_spawn and self.spawned:
            self.selection.clear()
            return None
        actor = Actor(f'transient {len(self.spawned)}', mesh, position, facing)
        self.spawned.append(actor)
        self.selection = [actor]
        return actor

    def destroy_actor(self, actor):
        self.spawned.remove(actor)
        self.selection.clear()
        return True

    def capture(self, width, height, dest, **_):
        self.captures += 1
        self.assertEqual(self.selection, self.original_selection)
        if self.captures == 3:
            self.assertTrue(self.source.hidden)
            if self.fail_capture:
                raise RuntimeError('simulated screenshot failure')
        Path(dest).write_bytes(b'\x89PNG\r\n\x1a\n' + bytes(8) + struct.pack('>II', width, height))
        return SimpleNamespace(is_task_done=lambda: True)

    def start(self):
        qa.run(lease_owner=OWNER)
        return getattr(self.unreal, qa.SESSION_ATTRIBUTE)

    def advance(self, preview, pause_after_hide=False):
        for _ in range(20):
            preview.tick(0)
            if preview.warm_at is not None:
                preview.warm_at = 0
            if preview.stopping or (pause_after_hide and self.source.hidden):
                break

    def read_report(self, preview):
        return json.loads((preview.output / 'report.json').read_text())

    def assert_restored(self, report, status):
        self.assertEqual(report['status'], status)
        self.assertTrue(report['selection_restored'])
        self.assertTrue(report['source_collision_unchanged'])
        self.assertEqual(report['original_files_sha256_before'], report['original_files_sha256_after'])
        self.assertFalse(self.source.hidden)
        self.assertEqual(self.spawned, [])
        self.assertEqual(self.camera, self.original_camera)
        self.assertEqual(self.selection, self.original_selection)
        self.assertFalse(hasattr(self.unreal, qa.SESSION_ATTRIBUTE))

    def test_normal_run_restores_selection_and_editor(self):
        preview = self.start()
        self.advance(preview)
        report = self.read_report(preview)
        self.assertEqual(len(report['captures']), 4)
        self.assert_restored(report, 'passed')

    def test_capture_failure_and_spawn_failure_restore_selection(self):
        for failure in ('fail_capture', 'fail_spawn'):
            with self.subTest(failure=failure):
                self.captures = 0
                setattr(self, failure, True)
                preview = self.start()
                self.advance(preview)
                self.assert_restored(self.read_report(preview), 'failed')
                setattr(self, failure, False)

    def test_start_requires_exact_owner_and_120_seconds_remaining(self):
        for owner, seconds in ((OWNER, -1), (OWNER, 119), ('another owner', 180)):
            with self.subTest(owner=owner, seconds=seconds):
                self.write_lease(owner, seconds)
                with self.assertRaises(RuntimeError):
                    qa.run(lease_owner=OWNER)
        self.lease_file.unlink()
        with self.assertRaises(RuntimeError):
            qa.run(lease_owner=OWNER)
        self.assertFalse(hasattr(self.unreal, qa.SESSION_ATTRIBUTE))

    def test_manual_cancellation_restores_selection(self):
        preview = self.start()
        self.advance(preview, pause_after_hide=True)
        self.assertTrue(self.source.hidden)
        self.assert_restored(qa.cleanup(lease_owner=OWNER), 'failed')

    def test_premature_removal_stops_preview_until_owner_reacquires(self):
        preview = self.start()
        self.advance(preview, pause_after_hide=True)
        self.assertTrue(self.source.hidden)
        self.lease_file.unlink()
        preview.tick(0)
        self.assertEqual(self.read_report(preview)['status'], 'cleanup_pending')
        self.assertTrue(self.source.hidden)
        self.assertEqual(len(self.spawned), 4)
        with self.assertRaises(RuntimeError):
            qa.cleanup(lease_owner=OWNER)
        self.write_lease('other owner')
        with self.assertRaises(RuntimeError):
            qa.cleanup(lease_owner=OWNER)
        self.assertEqual(len(self.spawned), 4)
        self.write_lease()
        self.assert_restored(qa.cleanup(lease_owner=OWNER), 'failed')

    def test_same_owner_replacing_exact_lease_stops_capture(self):
        preview = self.start()
        self.advance(preview, pause_after_hide=True)
        self.write_lease()
        preview.tick(0)
        self.assertEqual(self.read_report(preview)['status'], 'cleanup_pending')
        self.assertEqual(self.captures, 2)
        self.assert_restored(qa.cleanup(lease_owner=OWNER), 'failed')


if __name__ == '__main__':
    unittest.main()
