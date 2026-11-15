"""Import exactly the three reviewed West Connector meshes into Unreal.

Run this file with --preflight in system Python to verify source files offline.
For import, add this directory to Unreal Python's import path and call run()
under the active codex-gray-london editor lease. All live checks precede the
exact package save. A failed import can leave unsaved meshes in the session;
the overwrite guard also rejects these until they are cleared.
"""

import hashlib
import math
from pathlib import Path
import re
import sys
import time

from import_west_mark_lane import (
    MATERIALS, PROJECT, configure_collision, digest, fbx_options, get_slots,
    import_mesh, package_path, read_json, verify_mesh, verify_registry, verify_survey,
)


ROOT = Path(__file__).resolve().parent / 'WestConnector'
DEST = '/Game/GrayLondon/MedievalOpening/WholeBuildings/WestConnector'
OWNER = 'codex-gray-london'
MANIFEST_SHA256 = 'f2df18b96455500a6b563ebeabb6544e603a1d0c1d1b2e1a4f6bbfdd20ac614a'
NAMES = {
    'Tile_p03_p00_roof_0aa6599e2de6d057': 'SM_GLMedieval_WestConnector_TradingRange_0aa6599e',
    'Tile_p03_p00_roof_4bd93af4cb0bc367': 'SM_GLMedieval_WestConnector_DeepWorkshop_4bd93af4',
    'Tile_p03_p00_roof_d02f9ebc78cd0939': 'SM_GLMedieval_WestConnector_SteppedMarket_d02f9ebc',
}


def text_digest(path, line_ending=b'\n'):
    normalized = path.read_bytes().replace(b'\r\n', b'\n')
    return hashlib.sha256(normalized.replace(b'\n', line_ending)).hexdigest()


def preflight():
    manifest_path = ROOT / 'whole_buildings_kit.json'
    candidate_path = ROOT.parents[1] / 'west_connector_whole_buildings_candidate.json'
    plan_path = ROOT / 'west_connector_whole_building_plan.json'
    if text_digest(manifest_path) != MANIFEST_SHA256:
        raise RuntimeError('West Connector kit does not match the pinned reviewed manifest.')
    manifest = read_json(manifest_path)
    # The generator hashed the survey and plan from its Windows checkout.
    if (manifest['schema'] != 1 or text_digest(candidate_path, b'\r\n') != manifest['candidate_sha256'] or
            text_digest(plan_path, b'\r\n') != manifest['plan_sha256']):
        raise RuntimeError('West Connector candidate or plan differs from the reviewed source.')
    candidate, plan = read_json(candidate_path), read_json(plan_path)
    surveys = {row['id']: row for row in candidate['buildings']}
    plans = {row['id']: row for row in plan['buildings']}
    specs = manifest['buildings']
    if (specs.keys() != NAMES.keys() or plans.keys() != NAMES.keys() or surveys.keys() != NAMES.keys() or
            len(plan['buildings']) != len(NAMES) or len(candidate['buildings']) != len(NAMES) or
            manifest['source_tile'] != plan['source_tile'] or plan['source_tile'] != candidate['source_tile'] or
            plan['source_export_sha256'] != candidate['source_export_sha256']):
        raise RuntimeError('The kit, plan and survey must agree on the three reviewed West Connector shells.')

    verified = {}
    for shell_id, name in NAMES.items():
        spec, review = specs[shell_id], plans[shell_id]
        bridge, roundtrip = spec['unreal_bridge'], spec['roundtrip']
        original = ROOT / 'Source' / f'{name}.fbx'
        prepared = ROOT / 'UnrealSource' / original.name
        original_hash = digest(original)
        if (spec['fbx'] != f'Source/{original.name}' or bridge['fbx'] != f'UnrealSource/{prepared.name}' or
                original_hash != bridge['canonical_sha256'] or original_hash != roundtrip['fbx_sha256'] or
                digest(prepared) != bridge['prepared_sha256']):
            raise RuntimeError(f'{name}: canonical or prepared FBX does not match the reviewed file hash.')
        low, high = spec['bounds_cm']
        mirrored_bounds = [[low[0], -high[1], low[2]], [high[0], -low[1], high[2]]]
        slots = spec['materials']
        if (not slots or len(slots) != len(set(slots)) or
                not all(re.fullmatch(r'M_GLMedieval_[A-Za-z0-9_]+', slot) for slot in slots) or
                slots != bridge['materials'] or spec['uv_layers'] != ['UV0'] or
                bridge['uv_layers'] != spec['uv_layers'] or spec['triangles'] <= 0 or
                spec['triangles'] != bridge['triangles'] or bridge['bounds_cm'] != mirrored_bounds or
                spec['collision'] or not roundtrip['closed_solid_edges'] or
                bridge['signed_volume_m3'] <= 0 or not math.isclose(
                    bridge['signed_volume_m3'], roundtrip['signed_volume_m3'], rel_tol=1e-5) or
                not re.fullmatch(r'[a-f0-9]{64}', bridge['geometry_sha256']) or
                bridge['pivot_m'] != [0, 0, 0] or bridge['reflected_axis'] != 'Y' or
                spec['world_pivot_m'] != review['origin_m'] or spec['yaw_deg'] != review['rotation_yaw_deg']):
            raise RuntimeError(f'{name}: invalid reviewed geometry, UV, material or transform contract.')
        verify_survey(spec, surveys[shell_id], bridge)
        verified[name] = (prepared, spec, bridge)
    return verified


def require_idle(unreal):
    active_project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
    if active_project != PROJECT:
        raise RuntimeError('The editor is attached to a different checkout.')
    try:
        lease = read_json(PROJECT / 'Saved/PIE_LOCK.json')
        expiry = float(lease['expires_epoch'])
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise RuntimeError(f'A current {OWNER} editor lease is required.') from error
    if lease.get('owner') != OWNER or not math.isfinite(expiry) or expiry <= time.time():
        raise RuntimeError(f'The active editor lease must be held by {OWNER}.')
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if not editor.get_editor_world() or editor.get_game_world() or unreal.EditorLevelLibrary.get_pie_worlds(True):
        raise RuntimeError('The editor must have an open level and no PIE worlds.')


def package_file(path):
    return PROJECT / 'Content' / (path.removeprefix('/Game/') + '.uasset')


def assert_absent(unreal, path):
    if (package_file(path).exists() or unreal.EditorAssetLibrary.does_asset_exist(path) or
            unreal.find_package(path) is not None):
        raise FileExistsError(f'Refusing to overwrite an existing on-disk or in-memory package: {path}')


def run():
    """Import and verify the three assets, then save and persist their exact packages."""
    import unreal

    verified = preflight()
    require_idle(unreal)
    expected = [package_path(name, DEST) for name in verified]
    for path in expected:
        assert_absent(unreal, path)
    slot_names = sorted({slot for _, spec, _ in verified.values() for slot in spec['materials']})
    materials = {}
    for slot in slot_names:
        path = f'{MATERIALS}/{slot}.{slot}'
        material = unreal.load_asset(path, unreal.MaterialInterface)
        if not isinstance(material, unreal.MaterialInterface) or material.get_path_name() != path:
            raise RuntimeError(f'Missing existing medieval material {path}.')
        materials[slot] = material

    rows = {}
    packages = []
    for name, (prepared, spec, audit) in verified.items():
        require_idle(unreal)
        assert_absent(unreal, package_path(name, DEST))
        if digest(prepared) != audit['prepared_sha256']:
            raise RuntimeError(f'{name}: prepared FBX changed after preflight.')
        mesh = import_mesh(unreal, name, fbx_options(unreal), source_file=prepared, destination=DEST)
        if not isinstance(mesh, unreal.StaticMesh) or get_slots(mesh) != spec['materials']:
            raise RuntimeError(f'{name}: mesh or FBX material slot order differs from the canonical export.')
        for index, slot in enumerate(spec['materials']):
            mesh.set_material(index, materials[slot])
        configure_collision(unreal, mesh)
        row = verify_mesh(unreal, mesh, name, spec, audit, destination=DEST)
        if not mesh.get_editor_property('has_navigation_data'):
            raise RuntimeError(f'{name}: imported mesh lacks navigation geometry data.')
        rows[name] = {**row, 'has_navigation_data': True, 'prepared_sha256': audit['prepared_sha256']}
        packages.append(mesh.get_package())

    require_idle(unreal)
    paths = [package.get_name() for package in packages]
    if paths != expected or any(package_file(path).exists() for path in paths):
        raise RuntimeError(f'Unexpected save scope or destination appeared during import: {paths}.')
    if not unreal.EditorLoadingAndSavingUtils.save_packages(packages, only_dirty=False):
        written = [path for path in paths if package_file(path).exists()]
        raise RuntimeError(f'Could not save all exact West Connector packages. Files present: {written}.')
    multi_user = unreal.MultiUserClientStatics
    if multi_user.get_multi_user_connection_status_detail() == unreal.MultiUserConnectionStatus.CONNECTED:
        require_idle(unreal)
        multi_user.persist_specified_packages(paths)
    missing = [path for path in paths if not package_file(path).is_file()]
    if missing:
        raise RuntimeError(f'Expected local asset packages after save: {missing}.')
    verify_registry(unreal, rows, destination=DEST)
    return {'meshes': rows, 'saved_packages': paths}


if __name__ == '__main__' and '--preflight' in sys.argv:
    for name, (_, spec, audit) in preflight().items():
        print(f'{package_path(name, DEST)}: {spec["triangles"]} triangles, '
              f'{len(spec["materials"])} slots, prepared SHA-256 {audit["prepared_sha256"]}')
