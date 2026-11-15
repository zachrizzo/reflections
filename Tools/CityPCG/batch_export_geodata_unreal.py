"""Export Gray London source tiles in small, resumable, read-only batches.

Call ``run_batch('codex-gray-london', batch_size=2)`` from the already-open
Unreal Editor under its own editor lease. No actors are loaded, created,
modified or saved. Unloaded actor transforms are never treated as verified.
"""

from collections import defaultdict
import ctypes
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys
import time
import uuid

from survey_follow_on_actor_descs_unreal import descriptor_snapshot


PROJECT = Path(__file__).resolve().parents[2]
MAP = '/Game/GrayLondon/Maps/GrayLondon_Geodata'
ACTOR_ROOT = '/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/'
GEODATA_ROOT = '/Game/GrayLondon/Geodata'
TILE_ROOT = f'{GEODATA_ROOT}/Tiles'
OVERLAY_ROOT = f'{GEODATA_ROOT}/AnonymousCommercial'
TILE_NAME = re.compile(r'Tile_[pm]\d{2}_[pm]\d{2}\Z')
GUID = re.compile(r'[0-9a-fA-F]{32}\Z')
MAX_BATCH = 8
MIN_PHYSICAL_BYTES = 4 * 1024 ** 3
MIN_COMMIT_BYTES = 10 * 1024 ** 3
MIN_LEASE_SECONDS = 120
TRANSLATION_TOLERANCE_CM = .09
ROTATION_TOLERANCE_DEG = .0001
SCALE_TOLERANCE = .0001


class SessionError(RuntimeError):
    """The editor lease, current world, or available memory no longer permits work."""


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write_new_json(path, data):
    with path.open('x', encoding='utf-8', newline='\n') as output:
        json.dump(data, output, indent=2, ensure_ascii=False)
        output.write('\n')


def memory_available():
    """Return Windows physical and commit headroom without starting a subprocess."""
    if sys.platform != 'win32':
        raise SessionError('The memory guard requires Windows GlobalMemoryStatusEx.')

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong),
                    ('total_physical', ctypes.c_ulonglong), ('available_physical', ctypes.c_ulonglong),
                    ('total_page_file', ctypes.c_ulonglong), ('available_page_file', ctypes.c_ulonglong),
                    ('total_virtual', ctypes.c_ulonglong), ('available_virtual', ctypes.c_ulonglong),
                    ('available_extended_virtual', ctypes.c_ulonglong)]

    status = MEMORYSTATUSEX()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise SessionError('Cannot read Windows memory headroom.')
    return int(status.available_physical), int(status.available_page_file)


def require_memory(probe=None):
    probe = probe or memory_available
    physical, commit = probe()
    if physical < MIN_PHYSICAL_BYTES or commit < MIN_COMMIT_BYTES:
        raise SessionError(f'Need at least 4 GiB free physical and 10 GiB free commit memory; '
                           f'found {physical / 1024**3:.2f} and {commit / 1024**3:.2f} GiB.')
    return {'physical_bytes': physical, 'commit_bytes': commit}


def check_session(unreal, owner, expected=None, minimum_seconds=MIN_LEASE_SECONDS):
    if not owner:
        raise SessionError('Supply the exact owner of the current editor lease.')
    project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
    saved = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())).resolve()
    if project != PROJECT.resolve() or saved != (project / 'Saved').resolve():
        raise SessionError('The editor is not attached to this checkout and Saved directory.')
    try:
        lease = read_json(saved / 'PIE_LOCK.json')
        expires = float(lease['expires_epoch'])
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise SessionError('A readable current editor lease is required.') from error
    if (lease.get('owner') != owner or not math.isfinite(expires)
            or expires - time.time() < minimum_seconds):
        raise SessionError('The lease belongs to another session, has expired, or is too short.')
    if expected is not None and lease != expected:
        raise SessionError('The original editor lease changed during the batch.')
    if unreal.EditorLevelLibrary.get_pie_worlds(True):
        raise SessionError('Stop Play-In-Editor before exporting city tiles.')
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if editor.get_game_world() or not world or world.get_path_name().split('.')[0] != MAP:
        raise SessionError(f'Open {MAP} outside PIE before exporting city tiles.')
    return project, saved, world, lease


def registry_inventory(registry, project):
    """Require the registry and disk to agree on all direct tile mesh assets."""
    if registry.is_loading_assets():
        raise RuntimeError('Wait until the Asset Registry has finished its initial scan.')
    answer = {}
    for role, folder, package_root in (
        ('tile', 'Tiles', TILE_ROOT), ('overlay', 'AnonymousCommercial', OVERLAY_ROOT),
    ):
        directory = project / 'Content/GrayLondon/Geodata' / folder
        files = [path for path in directory.glob('Tile_*.uasset') if TILE_NAME.fullmatch(path.stem)]
        disk = {path.stem for path in files}
        if len(disk) != len(files):
            raise RuntimeError(f'Duplicate disk tile names under {directory}.')
        entries = registry.get_assets_by_path(package_root, False, True)
        if entries is None:
            raise RuntimeError(f'Cannot query {package_root} in the Asset Registry.')
        found = {}
        for entry in entries:
            name = str(entry.get_editor_property('asset_name'))
            if not TILE_NAME.fullmatch(name):
                continue
            package = str(entry.get_editor_property('package_name'))
            cls = entry.get_editor_property('asset_class_path')
            class_path = (str(cls.get_editor_property('package_name')),
                          str(cls.get_editor_property('asset_name')))
            if package != f'{package_root}/{name}' or class_path != ('/Script/Engine', 'StaticMesh'):
                raise RuntimeError(f'{role} {name}: unexpected asset package or class.')
            if name in found:
                raise RuntimeError(f'{role} {name}: multiple Asset Registry records.')
            found[name] = package
        if set(found) != disk:
            raise RuntimeError(f'{role} disk and registry inventories disagree: '
                               f'disk_only={sorted(disk - found.keys())}, '
                               f'registry_only={sorted(found.keys() - disk)}')
        answer[role] = found
    if not answer['tile']:
        raise RuntimeError('No canonical geodata tile assets were found.')
    return answer


def descriptors(unreal):
    values = unreal.WorldPartitionBlueprintLibrary.get_actor_descs()
    if values is None:
        raise RuntimeError('World Partition did not return actor descriptors.')
    indexed = defaultdict(list)
    for value in values:
        label = str(value.get_editor_property('label'))
        if label.startswith(('OSM Tile_', 'Anonymous shops Tile_')):
            indexed[label].append(value)
    return indexed


def loaded_actors(unreal):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    indexed = defaultdict(list)
    for actor in subsystem.get_all_level_actors():
        label = str(actor.get_actor_label())
        if label.startswith(('OSM Tile_', 'Anonymous shops Tile_')):
            indexed[label].append(actor)
    return indexed


def package_files(project, package):
    if not package.startswith('/Game/') or '..' in package.split('/'):
        raise RuntimeError(f'Unexpected package path {package!r}.')
    root = (project / 'Content').resolve()
    base = (root / package.removeprefix('/Game/')).resolve()
    if not base.is_relative_to(root):
        raise RuntimeError(f'Package escapes Content: {package!r}.')
    paths = [base.with_suffix(suffix) for suffix in ('.uasset', '.uexp', '.ubulk', '.uptnl')]
    if not paths[0].is_file():
        raise RuntimeError(f'Missing package on disk: {paths[0]}.')
    return {path.relative_to(project).as_posix(): sha256(path) for path in paths if path.is_file()}


def dirty_packages(unreal):
    utils = unreal.EditorLoadingAndSavingUtils
    return {package.get_name() for package in
            (*utils.get_dirty_map_packages(), *utils.get_dirty_content_packages())}


def dependency_options(unreal):
    return unreal.AssetRegistryDependencyOptions(
        include_hard_package_references=True, include_soft_package_references=False,
        include_searchable_names=False, include_soft_management_references=False,
        include_hard_management_references=False,
    )


def identity(unreal, registry, options, project, name, role, package, indexed_descs, indexed_loaded):
    label = f'OSM {name}' if role == 'tile' else f'Anonymous shops {name}'
    descs = indexed_descs.get(label, [])
    if len(descs) != 1:
        raise RuntimeError(f'{label}: expected exactly one saved actor descriptor, got {len(descs)}.')
    row = descriptor_snapshot(descs[0])
    if (row['label'] != label or not row['actor_package'].startswith(ACTOR_ROOT)
            or not row['actor_path'].startswith(MAP + '.')
            or row['native_class'] != '/Script/Engine.StaticMeshActor'
            or not GUID.fullmatch(row['guid']) or not GUID.fullmatch(row['instance_guid'])
            or not int(row['guid'], 16) or not int(row['instance_guid'], 16)):
        raise RuntimeError(f'{label}: descriptor actor identity is incomplete or unexpected.')
    refs = registry.get_dependencies(row['actor_package'], options)
    if refs is None:
        raise RuntimeError(f'{label}: cannot read saved hard package dependencies.')
    refs = sorted(set(map(str, refs)))
    geometry_refs = [ref for ref in refs if ref.startswith((TILE_ROOT + '/', OVERLAY_ROOT + '/'))]
    if geometry_refs != [package]:
        raise RuntimeError(f'{label}: expected only the exact hard geodata dependency {package}; got {geometry_refs}.')
    dirty = dirty_packages(unreal)
    if package in dirty or row['actor_package'] in dirty:
        raise RuntimeError(f'{label}: source mesh or actor package has unsaved changes.')
    loaded = indexed_loaded.get(label, [])
    if len(loaded) > 1:
        raise RuntimeError(f'{label}: more than one loaded actor has this label.')
    if loaded and (loaded[0].get_path_name() != row['actor_path']
                   or loaded[0].get_package().get_name() != row['actor_package']):
        raise RuntimeError(f'{label}: loaded actor differs from the saved descriptor.')
    return {'role': role, 'package': package, 'asset': f'{package}.{name}', 'descriptor': row,
            'hard_dependencies': refs, 'package_hashes': {
                **package_files(project, package), **package_files(project, row['actor_package'])},
            'actor_loaded': bool(loaded)}, loaded[0] if loaded else None


def xyz(value):
    return [float(getattr(value, axis)) for axis in 'xyz']


def transform_evidence(unreal, role, actor, mesh):
    """The bounds path is a hypothesis even when extents happen to match."""
    bounds = role['descriptor']['streaming_bounds_cm']
    if actor is None:
        local = mesh.get_bounds()
        local_origin, local_extent = xyz(local.origin), xyz(local.box_extent)
        center = [(lo + hi) * .5 for lo, hi in zip(*bounds)]
        extent = [(hi - lo) * .5 for lo, hi in zip(*bounds)]
        finite = all(math.isfinite(value) for value in center + extent + local_origin + local_extent)
        agrees = finite and max(abs(a - b) for a, b in zip(extent, local_extent)) <= TRANSLATION_TOLERANCE_CM
        estimate = [(a - b) / 100 for a, b in zip(center, local_origin)] if agrees else None
        return {'source': 'descriptor_bounds_hypothesis' if agrees else 'unknown',
                'origin_m_hypothesis': estimate, 'rotation_scale_verified': False,
                'actor_extent_cm': extent, 'mesh_extent_cm': local_extent,
                'requires_live_confirmation': True}
    components = actor.get_components_by_class(unreal.StaticMeshComponent)
    if len(components) != 1:
        raise RuntimeError(f"{role['descriptor']['label']}: loaded actor must have one static mesh component.")
    component = components[0]
    if component.get_editor_property('static_mesh') != mesh:
        raise RuntimeError(f"{role['descriptor']['label']}: loaded component uses a different mesh.")
    location, scale = xyz(component.get_world_location()), xyz(component.get_world_scale())
    rotation = component.get_world_rotation()
    angles = [float(getattr(rotation, key)) for key in ('pitch', 'yaw', 'roll')]
    if not all(math.isfinite(value) for value in location + scale + angles):
        raise RuntimeError(f"{role['descriptor']['label']}: non-finite loaded component transform.")
    translated = (all(abs(math.remainder(angle, 360)) <= ROTATION_TOLERANCE_DEG for angle in angles)
                  and all(abs(value - 1) <= SCALE_TOLERANCE for value in scale))
    return {'source': 'loaded_actor_component', 'origin_m': [value / 100 for value in location],
            'rotation_pitch_yaw_roll_deg': angles, 'scale': scale,
            'rotation_scale_verified': True, 'compatible_translation_only': translated,
            'requires_live_confirmation': False}


def export_options(unreal):
    options = unreal.GLTFExportOptions()
    options.set_editor_properties({'bake_material_inputs': unreal.GLTFMaterialBakeMode.DISABLED,
                                   'export_source_model': True, 'export_uniform_scale': .01})
    return options


def section_mapping_evidence(path, mesh, slots):
    """Record names for investigation, never infer source-section identity."""
    expected = []
    for index in range(len(slots)):
        material = mesh.get_material(index)
        expected.append(material.get_name() if material else None)
    with path.open('rb') as stream:
        header = stream.read(20)
        if len(header) != 20:
            raise RuntimeError(f'{path.name}: truncated GLB header.')
        magic, version, total, length, kind = struct.unpack('<4sIII4s', header)
        if (magic, version, kind) != (b'glTF', 2, b'JSON') or total != path.stat().st_size:
            raise RuntimeError(f'{path.name}: invalid GLB header during material mapping.')
        if length > total - 28 or length % 4:
            raise RuntimeError(f'{path.name}: invalid GLB JSON chunk length.')
        document = json.loads(stream.read(length))
        binary_header = stream.read(8)
        if len(binary_header) != 8:
            raise RuntimeError(f'{path.name}: missing GLB binary chunk.')
        binary_length, binary_kind = struct.unpack('<I4s', binary_header)
        if binary_kind != b'BIN\x00' or binary_length % 4 or 28 + length + binary_length != total:
            raise RuntimeError(f'{path.name}: incomplete or unsupported GLB binary chunk.')
        buffers = document.get('buffers', [])
        if len(buffers) != 1 or 'uri' in buffers[0] or buffers[0].get('byteLength', total) > binary_length:
            raise RuntimeError(f'{path.name}: geometry must reside in the GLB binary chunk.')
    materials = document.get('materials', [])
    found = []
    for primitive in document['meshes'][0]['primitives']:
        index = primitive.get('material')
        found.append(materials[index].get('name') if type(index) is int and 0 <= index < len(materials) else None)
    unique = all(isinstance(name, str) and name for name in expected) and len(set(expected)) == len(expected)
    return {'verified': False, 'method': 'material_names_are_not_section_proof',
            'source_material_names': expected, 'glb_primitive_material_names': found,
            'names_unique_and_same_order': bool(unique and found == expected),
            'signed_triangles_verified': False, 'requires_independent_confirmation': True}


def export_role(unreal, role, actor, stage, guard, verify_export):
    guard()
    require_memory()
    mesh = unreal.EditorAssetLibrary.load_asset(role['package'])
    if not isinstance(mesh, unreal.StaticMesh) or mesh.get_path_name() != role['asset']:
        raise RuntimeError(f"Missing or unexpected static mesh {role['asset']}.")
    evidence = transform_evidence(unreal, role, actor, mesh)
    slots = [str(slot.get_editor_property('material_slot_name'))
             for slot in mesh.get_editor_property('static_materials')]
    if not slots or len(slots) != len(set(slots)):
        raise RuntimeError(f"{role['asset']}: empty or duplicate material slot names.")
    raw = stage / (role['role'] + '.glb')
    messages = unreal.GLTFExporter.export_to_gltf(mesh, str(raw), export_options(unreal), set())
    if messages is None or messages.get_editor_property('errors') or not raw.is_file():
        raise RuntimeError(f"{role['asset']}: source geometry export failed.")
    guard()
    counts = verify_export(raw, slots, mesh)
    if len(counts) != len(slots) or any(type(count) is not int or count < 0 for count in counts):
        raise RuntimeError(f"{role['asset']}: invalid exported section counts.")
    mapping = section_mapping_evidence(raw, mesh, slots)
    return mesh, evidence, mapping, raw, slots, counts


def destination(saved, path):
    root = (path or saved / 'CityPCG/CitywideTileExports').resolve()
    if not root.is_relative_to((saved / 'CityPCG').resolve()) or root == (saved / 'CityPCG').resolve():
        raise ValueError('Choose a dedicated output directory under Saved/CityPCG.')
    return root


def tile_directory(root, name):
    directory = root / name
    if directory.is_symlink() or not directory.resolve().is_relative_to(root):
        raise RuntimeError(f'{name}: tile output directory escapes or redirects the output root.')
    return directory


def completed(root, name):
    directory = tile_directory(root, name)
    records = sorted(directory.glob('attempt-*/result.json')) if directory.exists() else []
    if len(records) > 1:
        raise RuntimeError(f'{name}: multiple completed attempts require review.')
    if not records:
        return None
    attempt = records[0].parent
    if attempt.is_symlink() or attempt.resolve().parent != directory.resolve() or records[0].is_symlink():
        raise RuntimeError(f'{name}: completed attempt redirects outside its tile directory.')
    report = read_json(records[0])
    if (report.get('schema') != 1 or report.get('tile') != name
            or report.get('status') != 'complete_review_only' or report.get('source_map') != MAP
            or report.get('legacy_sidecar_eligible') is not False
            or report.get('sidecar') != f'{name}.unverified.json'
            or set(report.get('roles', {})) not in ({'tile'}, {'tile', 'overlay'})):
        raise RuntimeError(f'{name}: completed attempt has invalid metadata.')
    for key, role in report['roles'].items():
        expected = f'{name}.glb' if key == 'tile' else f'AnonymousShops_{name}.glb'
        if role.get('role') != key or role.get('glb') != expected or role.get('section_mapping', {}).get('verified') is not False:
            raise RuntimeError(f'{name}: completed attempt has invalid role metadata.')
        path = attempt / role['glb']
        if (path.parent != records[0].parent or path.is_symlink() or
                path.resolve().parent != records[0].parent.resolve() or
                not path.is_file() or sha256(path) != role['glb_sha256']):
            raise RuntimeError(f'{name}: completed GLB is missing or changed; never overwrite it.')
    sidecar = records[0].parent / report['sidecar']
    if (sidecar.parent != records[0].parent or sidecar.is_symlink() or
            sidecar.resolve().parent != records[0].parent.resolve() or
            not sidecar.is_file() or sha256(sidecar) != report['sidecar_sha256']):
        raise RuntimeError(f'{name}: completed metadata is missing or changed; never overwrite it.')
    return report


def run_batch(owner, batch_size=2, *, names=None, output=None, retry_failed=False, start_after=None):
    """Export up to eight new tiles. All returned results require further review."""
    import unreal
    from export_geodata_tiles_unreal import verify_export

    if type(batch_size) is not int or not 1 <= batch_size <= MAX_BATCH:
        raise ValueError(f'batch_size must be an integer from 1 to {MAX_BATCH}.')
    project, saved, world, lease = check_session(unreal, owner)
    require_memory()
    root = destination(saved, Path(output) if output else None)
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    inventory = registry_inventory(registry, project)
    requested = sorted(inventory['tile']) if names is None else list(names)
    if (not requested or len(requested) != len(set(requested))
            or any(not isinstance(name, str) or not TILE_NAME.fullmatch(name) for name in requested)
            or not set(requested) <= inventory['tile'].keys()):
        raise ValueError('Provide distinct canonical tile names present in the registry.')
    if start_after is not None:
        if names is not None or start_after not in inventory['tile']:
            raise ValueError('start_after must be a canonical tile name and cannot be combined with names.')
        requested = [name for name in requested if name > start_after]
    indexed_descs, indexed_loaded = descriptors(unreal), loaded_actors(unreal)
    options = dependency_options(unreal)
    summary = {'status': 'offline_review_only', 'tile_count': len(inventory['tile']),
               'overlay_count': len(inventory['overlay'].keys() & inventory['tile'].keys()),
               'without_overlay_count': len(inventory['tile'].keys() - inventory['overlay'].keys()),
               'orphan_overlay_assets': sorted(inventory['overlay'].keys() - inventory['tile'].keys()),
               'completed_now': [], 'already_complete': [], 'blocked': [],
               'skipped_failures': [], 'remaining': [], 'next_start_after': start_after}

    def guard():
        _, _, current, _ = check_session(unreal, owner, expected=lease)
        if current != world:
            raise SessionError('The editor world changed during the batch.')

    def source_roles(name, descs, loaded):
        roles, actors = {}, {}
        for role in ('tile', 'overlay'):
            package = inventory[role].get(name)
            label = f'Anonymous shops {name}'
            if role == 'overlay' and package is None:
                if descs.get(label) or loaded.get(label):
                    raise RuntimeError(f'{label}: actor exists but its overlay asset is missing.')
                continue
            roles[role], actors[role] = identity(unreal, registry, options, project, name, role, package,
                                                 descs, loaded)
        return roles, actors

    attempted = 0
    for name in requested:
        if attempted >= batch_size:
            summary['remaining'].append(name)
            continue
        guard()
        require_memory()
        tile_dir = tile_directory(root, name)
        counted = False
        try:
            prior = completed(root, name)
            failures = list(tile_dir.glob('failure-*.json')) if tile_dir.exists() else []
            if failures and not retry_failed and not prior:
                summary['skipped_failures'].append({'tile': name, 'reason': 'Previous failure retained; set retry_failed to retry.'})
                summary['next_start_after'] = name
                continue
            if not prior:
                attempted += 1
                counted = True
            roles, actors = source_roles(name, indexed_descs, indexed_loaded)
            if prior:
                if prior['roles'].keys() != roles.keys():
                    raise RuntimeError(f'{name}: source overlay membership changed after export.')
                for role, current in roles.items():
                    old = prior['roles'][role]
                    if any(current[field] != old[field] for field in
                           ('package', 'asset', 'descriptor', 'hard_dependencies', 'package_hashes', 'actor_loaded')):
                        raise RuntimeError(f'{name}: {role} source identity changed after export.')
                    mesh = unreal.EditorAssetLibrary.load_asset(current['package'])
                    if (not isinstance(mesh, unreal.StaticMesh) or mesh.get_path_name() != current['asset']
                            or transform_evidence(unreal, current, actors[role], mesh) != old['transform']):
                        raise RuntimeError(f'{name}: {role} source transform changed after export.')
                    del mesh
                summary['already_complete'].append(name)
                summary['next_start_after'] = name
                continue
            stage_root = (saved / 'CityPCGBatchStaging').resolve()
            if not stage_root.is_relative_to(saved):
                raise RuntimeError('The staging directory escapes Saved.')
            stage_root.mkdir(parents=True, exist_ok=True)
            stage = stage_root / f'{name}-{uuid.uuid4().hex}'
            stage.mkdir()
            pre_dirty = dirty_packages(unreal)
            for role, row in roles.items():
                mesh, transform, mapping, raw, slots, counts = export_role(unreal, row, actors[role], stage, guard, verify_export)
                row.update(transform=transform, section_mapping=mapping, source_slot_names=slots,
                           primitive_triangle_counts=counts,
                           glb=f'{name}.glb' if role == 'tile' else f'AnonymousShops_{name}.glb',
                           glb_sha256=sha256(raw))
                del mesh
            guard()
            current_descs, current_loaded = descriptors(unreal), loaded_actors(unreal)
            for role, before in roles.items():
                after, actor = identity(unreal, registry, options, project, name, role, before['package'],
                                        current_descs, current_loaded)
                if any(before[field] != after[field] for field in
                       ('package', 'asset', 'descriptor', 'hard_dependencies', 'package_hashes', 'actor_loaded')):
                    raise RuntimeError(f'{name}: {role} identity changed during export.')
                mesh = unreal.EditorAssetLibrary.load_asset(before['package'])
                if not isinstance(mesh, unreal.StaticMesh) or transform_evidence(unreal, after, actor, mesh) != before['transform']:
                    raise RuntimeError(f'{name}: loaded {role} transform changed during export.')
                del mesh
            if dirty_packages(unreal) != pre_dirty:
                raise RuntimeError(f'{name}: editor dirty package state changed during export.')
            # Publish only after all roles and the original lease have been checked.
            for role, row in roles.items():
                (stage / f'{role}.glb').rename(stage / row['glb'])
            sidecar = f'{name}.unverified.json'
            write_new_json(stage / sidecar, {
                'tile': name, 'status': 'source_section_mapping_unverified',
                'requires_section_mapping_verification': True,
                'requires_live_transform_confirmation': any(row['transform']['requires_live_confirmation']
                                                            for row in roles.values()),
                'transforms': {role: row['transform'] for role, row in roles.items()},
                'section_mapping': {role: row['section_mapping'] for role, row in roles.items()}})
            report = {'schema': 1, 'status': 'complete_review_only', 'tile': name,
                      'overlay_absent': 'overlay' not in roles, 'legacy_sidecar_eligible': False,
                      'source_map': MAP, 'roles': roles, 'sidecar': sidecar,
                      'sidecar_sha256': sha256(stage / sidecar)}
            write_new_json(stage / 'result.json', report)
            guard()
            if completed(root, name):
                raise RuntimeError(f'{name}: another completed attempt appeared during export.')
            tile_dir.mkdir(parents=True, exist_ok=True)
            target = tile_dir / f'attempt-{uuid.uuid4().hex}'
            # Re-check both resolved move paths immediately before the rename.
            # A UUID also ensures a prior completed attempt is never replaced.
            if (stage_root.resolve() != (saved / 'CityPCGBatchStaging').resolve()
                    or not stage_root.resolve().is_relative_to(saved.resolve())
                    or stage.is_symlink() or stage.resolve().parent != stage_root.resolve()
                    or tile_directory(root, name).resolve().parent != root.resolve()
                    or not root.resolve().is_relative_to((saved / 'CityPCG').resolve())
                    or target.exists() or target.resolve().parent != tile_dir.resolve()):
                raise RuntimeError(f'{name}: staging or publication path changed before rename.')
            stage.rename(target)
            summary['completed_now'].append({'tile': name, 'result': str(target / 'result.json'),
                                             'legacy_sidecar_eligible': False})
            summary['next_start_after'] = name
        except SessionError:
            raise
        except Exception as error:
            guard()
            if not counted:
                attempted += 1
            tile_dir.mkdir(parents=True, exist_ok=True)
            failure = tile_dir / f'failure-{uuid.uuid4().hex}.json'
            write_new_json(failure, {'tile': name, 'status': 'blocked_review_only',
                                     'reason': f'{type(error).__name__}: {error}'})
            summary['blocked'].append({'tile': name, 'reason': str(error), 'report': str(failure)})
            summary['next_start_after'] = name
    guard()
    return summary
