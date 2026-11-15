"""Capture a reversible, editor-only comparison of the West Mark Lane pilot."""

import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import time
import traceback
import uuid


PROJECT = Path(__file__).resolve().parents[2]
KIT = PROJECT / 'ArtDirection/CityPCG/MedievalOpening/WholeBuildings'
SAVED = PROJECT / 'Saved'
CITY = SAVED / 'CityPCG'
OUT = CITY / 'MedievalSurvey' / 'WestMarkLaneVisualQA'
LEVEL = '/Game/GrayLondon/Maps/GrayLondon_Geodata'
SESSION_ATTRIBUTE = '_west_mark_lane_visual_qa'
SIZE = (1280, 720)
PREVIEW_SECONDS = 85
MINIMUM_LEASE_SECONDS = 120
VIEWS = {
    'north_merchant_street': ((3119.0, 407.0, 2.05), (3145.0, 392.8, 6.60)),
    'south_workshop_street': ((3120.8, 367.0, 2.05), (3128.9, 376.9, 4.4)),
}


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def load_project_manifests():
    candidate = read_json(KIT.parent / 'west_mark_lane_whole_buildings_candidate.json')
    plan = read_json(KIT.parent / 'west_mark_lane_whole_building_plan.json')
    kit = read_json(KIT / 'whole_buildings_kit.json')['buildings']
    reviewed = {row['id']: row for row in plan['buildings']}
    if not (set(kit) == set(reviewed) == {row['id'] for row in candidate['buildings']}) or len(kit) != 3:
        raise RuntimeError('Expected the same three reviewed buildings in all manifests')
    for key, spec in kit.items():
        reference = reviewed[key]
        if (math.dist(spec['world_pivot_m'], reference['origin_m']) > .001
                or abs(spec['yaw_deg'] - reference['rotation_yaw_deg']) > .001
                or len(spec['footprint_local_m']) != len(reference['footprint_local_m'])
                or any(math.dist(a, b) > .001 for a, b in zip(spec['footprint_local_m'], reference['footprint_local_m']))):
            raise RuntimeError(f'{key}: placement disagrees with the reviewed plan')
    return candidate, kit


def active_lease():
    try:
        record = read_json(SAVED / 'PIE_LOCK.json')
    except FileNotFoundError:
        return None
    if float(record['expires_epoch']) > time.time():
        return record
    return None


def editor_available(unreal, lease_owner, *, require_lease=False, expected_lease=None, minimum_seconds=0):
    lock = active_lease()
    if require_lease and not lease_owner:
        raise RuntimeError('Supply the exact owner of the active editor lease')
    if lock is not None and lock['owner'] != lease_owner:
        raise RuntimeError(f'Editor reserved by {lock["owner"]} through {lock["expires_local"]}')
    if require_lease and lock is None:
        raise RuntimeError('An active editor lease is required for the visual preview')
    if expected_lease is not None and lock != expected_lease:
        raise RuntimeError('The original preview lease changed or was removed')
    if minimum_seconds and float(lock['expires_epoch']) - time.time() < minimum_seconds:
        raise RuntimeError(f'At least {minimum_seconds} seconds must remain on the editor lease before starting')
    if unreal.EditorLevelLibrary.get_pie_worlds(True):
        raise RuntimeError('Visual QA requires the editor world outside PIE')
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split('.')[0] != LEVEL:
        raise RuntimeError(f'Expected {LEVEL} to be open')
    return editor, world, lock


def dirty_paths(unreal):
    utils = unreal.EditorLoadingAndSavingUtils
    return {package.get_name() for package in (*utils.get_dirty_map_packages(), *utils.get_dirty_content_packages())}


def package_file(package, extension):
    if not package.startswith('/Game/'):
        raise RuntimeError(f'Unexpected package {package}')
    return PROJECT / 'Content' / f'{package.removeprefix("/Game/")}{extension}'


def file_hashes(paths):
    hashes = {}
    for path in paths:
        with path.open('rb') as stream:
            hashes[str(path)] = hashlib.file_digest(stream, 'sha256').hexdigest()
    return hashes


def camera_vector(unreal, meters):
    return unreal.Vector(*(100 * value for value in meters))


def vector_values(vector):
    return tuple(getattr(vector, axis) for axis in 'xyz')


def actor_collision(actor, unreal):
    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    return (actor.get_actor_enable_collision(), str(component.get_collision_enabled()),
            str(component.get_collision_profile_name()), component.get_editor_property('can_ever_affect_navigation'))


def preflight(unreal, lease_owner=None, *, preview=False):
    if str(Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()).casefold() != str(PROJECT).casefold():
        raise RuntimeError('The running Unreal editor is attached to a different checkout')
    viewport, world, lock = editor_available(unreal, lease_owner, require_lease=preview,
                                             minimum_seconds=MINIMUM_LEASE_SECONDS if preview else 0)
    actor_editor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    candidate, kit = load_project_manifests()
    if str(Path(__file__).resolve().parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
    from audit_replacement_tile_unreal import inspect_owned_mesh

    metadata = CITY / 'Tile_p03_p00.asset.json'
    derivative = CITY / 'MedievalSurvey' / 'Tile_p03_p00_without_three_west_shells.audit.json'
    audit = inspect_owned_mesh(metadata, derivative)
    source_contract = audit['source']
    if source_contract['actor'] != candidate['source_tile_actor'] or source_contract['source_asset'] != candidate['source_tile_asset']:
        raise RuntimeError('The audited source does not match the surveyed source tile')
    matches = [actor for actor in actor_editor.get_all_level_actors() if actor.get_path_name() == source_contract['actor']]
    if len(matches) != 1 or matches[0].get_package().get_name() != source_contract['actor_package']:
        raise RuntimeError('The exact p03_p00 actor must already be loaded once')
    source = matches[0]
    if source.is_temporarily_hidden_in_editor(False):
        raise RuntimeError('The original tile is already hidden; restore the normal street view before capture')
    component = source.get_components_by_class(unreal.StaticMeshComponent)[0]

    replacement_package = audit['replacement_package']
    destination = replacement_package.rsplit('/', 1)[0]
    tile_name = replacement_package.rsplit('/', 1)[1]
    tile = unreal.load_asset(f'{replacement_package}.{tile_name}', unreal.StaticMesh)
    placements = [(tile, component.get_world_location(), component.get_world_rotation(), component.get_world_scale())]
    for spec in kit.values():
        name = Path(spec['fbx']).stem
        package = f'{destination}/{name}'
        mesh = unreal.load_asset(f'{package}.{name}', unreal.StaticMesh)
        if not isinstance(mesh, unreal.StaticMesh) or mesh.get_num_triangles(0) != spec['triangles']:
            raise RuntimeError(f'Missing or incompatible replacement {package}')
        position = camera_vector(unreal, spec['world_pivot_m'])
        placements.append((mesh, position, unreal.Rotator(yaw=spec['yaw_deg']), unreal.Vector(1, 1, 1)))
    if not isinstance(tile, unreal.StaticMesh):
        raise RuntimeError(f'Missing filtered tile {replacement_package}')
    replacement_meshes = {mesh.get_path_name() for mesh, *_ in placements}
    for actor in actor_editor.get_all_level_actors():
        for mesh_component in actor.get_components_by_class(unreal.StaticMeshComponent):
            mesh = mesh_component.get_editor_property('static_mesh')
            if mesh and mesh.get_path_name() in replacement_meshes:
                raise RuntimeError(f'{actor.get_path_name()} already uses a replacement mesh; preview would double it')

    camera = viewport.get_level_viewport_camera_info()
    if camera is None:
        raise RuntimeError('An active perspective editor viewport is required')
    protected = (package_file(source_contract['actor_package'], '.uasset'),
                 package_file(source_contract['source_asset'].split('.')[0], '.uasset'), package_file(LEVEL, '.umap'))
    return viewport, actor_editor, world, lock, source, source_contract, placements, camera, protected


def inspect(lease_owner=None):
    """Return a read-only check of the four exact placements and editor state."""
    import unreal

    viewport, _, world, _, _, source, placements, _, protected = preflight(unreal, lease_owner)
    return {'world': world.get_path_name(), 'source': source, 'protected_sha256': file_hashes(protected),
            'placement_assets': [mesh.get_path_name() for mesh, *_ in placements],
            'active_perspective_viewport': viewport.get_level_viewport_camera_info() is not None}


class Preview:
    def __init__(self, unreal, lease_owner):
        self.unreal, self.lease_owner = unreal, lease_owner
        (self.viewport, self.actors, self.world, self.lock, self.source, self.source_contract,
         self.placements, self.camera, self.protected) = preflight(unreal, lease_owner, preview=True)
        self.selection = tuple(self.actors.get_selected_level_actors())
        self.selection_paths = tuple(actor.get_path_name() for actor in self.selection)
        self.original_dirty = dirty_paths(unreal)
        self.original_hashes = file_hashes(self.protected)
        self.original_collision = actor_collision(self.source, unreal)
        self.output = OUT / (time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8])
        self.output.mkdir(parents=True)
        self.shots = [(stage, name, loc, aim) for stage in ('before', 'after') for name, (loc, aim) in VIEWS.items()]
        self.index = 0
        self.spawned = []
        self.captures = []
        self.deadline = time.monotonic() + PREVIEW_SECONDS
        self.warm_at = None
        self.task = None
        self.handle = None
        self.hide_applied = False
        self.camera_changed = False
        self.selection_changed = False
        self.first_error = None
        self.stopping = False

    def require_editor(self, *, lease=None, minimum_seconds=0):
        _, world, lock = editor_available(self.unreal, self.lease_owner, require_lease=True,
                                           expected_lease=self.lock if lease is None else lease,
                                           minimum_seconds=minimum_seconds)
        if world != self.world:
            raise RuntimeError('The original editor world is no longer active')
        return lock

    def selected_paths(self):
        return tuple(actor.get_path_name() for actor in self.actors.get_selected_level_actors())

    def restore_selection(self):
        if self.selected_paths() != self.selection_paths:
            self.actors.set_selected_level_actors(list(self.selection))
        if self.selected_paths() != self.selection_paths:
            raise RuntimeError('The editor did not restore the original actor selection')
        self.selection_changed = False

    def place(self):
        for mesh, position, rotation, scale in self.placements:
            self.require_editor()
            self.selection_changed = True
            actor = self.actors.spawn_actor_from_object(mesh, position, rotation, transient=True)
            if actor is None:
                raise RuntimeError(f'Could not spawn transient preview of {mesh.get_name()}')
            self.spawned.append(actor)
            self.require_editor()
            actor.set_actor_enable_collision(False)
            component = actor.get_component_by_class(self.unreal.StaticMeshComponent)
            if component is None or component.get_editor_property('static_mesh') != mesh:
                raise RuntimeError(f'{mesh.get_name()}: wrong transient actor')
            component.set_collision_profile_name('NoCollision')
            component.set_editor_property('can_ever_affect_navigation', False)
            actor.set_actor_scale3d(scale)
            actual_rotation = actor.get_actor_rotation()
            if (math.dist(vector_values(actor.get_actor_location()), vector_values(position)) > .03
                    or math.dist(vector_values(actor.get_actor_scale3d()), vector_values(scale)) > .00001
                    or any(abs(math.remainder(getattr(actual_rotation, axis) - getattr(rotation, axis), 360)) > .001
                           for axis in ('pitch', 'yaw', 'roll'))):
                raise RuntimeError(f'{mesh.get_name()}: preview actor transform drifted')
            if (actor.get_actor_enable_collision() or str(component.get_collision_profile_name()) != 'NoCollision'
                    or component.get_editor_property('can_ever_affect_navigation')):
                raise RuntimeError(f'{mesh.get_name()}: preview can affect collision/navigation')
        self.require_editor()
        self.restore_selection()
        self.require_editor()
        self.hide_applied = True
        self.selection_changed = True
        self.source.set_is_temporarily_hidden_in_editor(True)
        if not self.source.is_temporarily_hidden_in_editor(False):
            raise RuntimeError('Could not temporarily hide original tile rendering')

    def tick(self, _delta):
        if self.stopping:
            return
        try:
            self.require_editor()
            if time.monotonic() > self.deadline:
                raise TimeoutError(f'Visual preview exceeded its {PREVIEW_SECONDS} second budget')
            if self.index == len(self.shots):
                self.finish()
                return
            stage, name, eye, aim = self.shots[self.index]
            dest = self.output / f'{self.index + 1:02d}_{stage}_{name}.png'
            if self.task is not None:
                if self.task.is_task_done() and dest.is_file():
                    with dest.open('rb') as image:
                        header = image.read(24)
                    if header[:8] != b'\x89PNG\r\n\x1a\n' or struct.unpack('>II', header[16:24]) != SIZE:
                        raise RuntimeError(f'Unexpected screenshot output: {dest}')
                    self.captures.append(str(dest))
                    self.index += 1
                    self.task = self.warm_at = None
                return
            if self.warm_at is None:
                if stage == 'after' and not self.hide_applied:
                    self.place()
                position = camera_vector(self.unreal, eye)
                look = self.unreal.MathLibrary.find_look_at_rotation(position, camera_vector(self.unreal, aim))
                self.require_editor()
                self.camera_changed = True
                self.viewport.set_level_viewport_camera_info(position, look)
                self.warm_at = time.monotonic() + 1.0
            elif time.monotonic() >= self.warm_at:
                camera = self.viewport.get_level_viewport_camera_info()
                expected = camera_vector(self.unreal, eye)
                if camera is None or math.dist(vector_values(camera[0]), vector_values(expected)) > 1:
                    raise RuntimeError('The active perspective camera moved before capture')
                self.require_editor()
                self.task = self.unreal.AutomationLibrary.take_high_res_screenshot(
                    *SIZE, str(dest), delay=.15, force_game_view=False)
                if self.task is None:
                    raise RuntimeError('The perspective viewport could not start a screenshot')
        except Exception:
            self.finish(traceback.format_exc())

    def finish(self, error=None, *, cleanup_lease=None):
        self.stopping = True
        if self.first_error is None and error is not None:
            self.first_error = error
        failures = []

        def attempt(label, callback):
            try:
                return callback()
            except Exception as exc:
                failures.append(f'{label}: {exc}')
                return None

        def restore(label, callback):
            def guarded():
                self.require_editor(lease=cleanup_lease)
                return callback()
            return attempt(label, guarded)

        if self.handle is not None:
            def stop_callback():
                self.unreal.unregister_slate_post_tick_callback(self.handle)
                self.handle = None
            attempt('unregister preview callback', stop_callback)
        if self.hide_applied:
            def restore_source():
                self.source.set_is_temporarily_hidden_in_editor(False)
                self.hide_applied = self.source.is_temporarily_hidden_in_editor(False)
            restore('restore original tile rendering', restore_source)
        for actor in reversed(tuple(self.spawned)):
            def destroy_actor():
                self.selection_changed = True
                return self.actors.destroy_actor(actor)
            status = restore('destroy transient preview actor', destroy_actor)
            if status:
                self.spawned.remove(actor)
            elif status is False:
                failures.append(f'Transient actor destruction returned false: {actor}')
        if self.camera_changed:
            def restore_camera():
                self.viewport.set_level_viewport_camera_info(*self.camera)
                self.camera_changed = False
            restore('restore perspective viewport', restore_camera)
        if self.selection_changed:
            restore('restore original actor selection', self.restore_selection)
        pending = bool(self.handle is not None or self.spawned or self.hide_applied or self.camera_changed
                       or self.selection_changed)
        final_hashes = attempt('hash original actor, mesh and level', lambda: file_hashes(self.protected))
        hidden = collision = final_dirty = selected = None
        if not pending:
            hidden = attempt('read restored source visibility', lambda: self.source.is_temporarily_hidden_in_editor(False))
            collision = attempt('read original collision flags', lambda: actor_collision(self.source, self.unreal))
            final_dirty = attempt('read dirty package list', lambda: dirty_paths(self.unreal))
            selected = attempt('read restored actor selection', self.selected_paths)
        added_dirty = sorted(final_dirty - self.original_dirty) if final_dirty is not None else None
        source_packages = {self.source_contract['actor_package'], self.source_contract['source_asset'].split('.')[0]}
        if added_dirty is not None and source_packages.intersection(added_dirty):
            failures.append('An original source package became dirty')
        complete = not self.first_error and not failures and hidden is False and final_hashes == self.original_hashes
        complete = complete and collision == self.original_collision and len(self.captures) == len(self.shots)
        complete = complete and selected == self.selection_paths
        report = {
            'status': 'cleanup_pending' if pending else 'passed' if complete else 'failed',
            'error': self.first_error, 'cleanup_errors': failures, 'source': self.source_contract,
            'editor_lease_owner': self.lease_owner, 'editor_lease_acquired_epoch': self.lock['acquired_epoch'],
            'captures': self.captures, 'source_temporarily_hidden_after': hidden,
            'source_collision_unchanged': collision == self.original_collision,
            'selection_before': self.selection_paths, 'selection_after': selected,
            'selection_restored': selected == self.selection_paths,
            'original_files_sha256_before': self.original_hashes, 'original_files_sha256_after': final_hashes,
            'dirty_packages_added': added_dirty,
        }
        if getattr(self.unreal, SESSION_ATTRIBUTE, None) is self and not pending:
            delattr(self.unreal, SESSION_ATTRIBUTE)
        (self.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        return report


def run(*, lease_owner):
    """Schedule screenshots and restore source visibility, actors and view on exit."""
    import unreal

    if getattr(unreal, SESSION_ATTRIBUTE, None):
        raise RuntimeError('A Mark Lane visual QA session is already running')
    preview = Preview(unreal, lease_owner)
    preview.require_editor(minimum_seconds=MINIMUM_LEASE_SECONDS)
    setattr(unreal, SESSION_ATTRIBUTE, preview)
    try:
        preview.handle = unreal.register_slate_post_tick_callback(preview.tick)
    except Exception:
        preview.finish(traceback.format_exc())
        raise
    return {'output': str(preview.output), 'shots': len(preview.shots), 'deadline_seconds': PREVIEW_SECONDS}


def cleanup(*, lease_owner):
    """Manually stop the active comparison and restore the original editor view."""
    import unreal

    preview = getattr(unreal, SESSION_ATTRIBUTE, None)
    if preview is None:
        return {'status': 'no active preview'}
    if lease_owner != preview.lease_owner:
        raise RuntimeError('Only the original preview lease owner may request cleanup')
    _, world, lock = editor_available(unreal, lease_owner, require_lease=True)
    if world != preview.world:
        raise RuntimeError('The original editor world must be active to retry preview cleanup')
    return preview.finish('Preview cancelled', cleanup_lease=lock)


if __name__ == '__main__' and '--check-manifests' in sys.argv:
    candidate, kit = load_project_manifests()
    print(f'Checked {len(kit)} reviewed placements for {candidate["source_tile"]}')
