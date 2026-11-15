"""Import and verify the three West Mark Lane static meshes by explicit package path."""

import hashlib
import json
import math
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[3]
WORK = PROJECT / 'Saved/MedievalOpening/WestMarkLaneImport'
DEST = '/Game/GrayLondon/MedievalOpening/WholeBuildings/WestMarkLane'
MATERIALS = '/Game/GrayLondon/MedievalOpening/Kit'
NAMES = {
    'Tile_p03_p00_shell_d87bb24c9cdb': 'SM_GLMedieval_MarkLaneMerchantsHouses',
    'Tile_p03_p00_shell_3b4ea8e64fcb': 'SM_GLMedieval_MarkLaneWorkshop',
    'Tile_p03_p00_shell_c3d845a67ca8': 'SM_GLMedieval_MarkLaneTradingCompound',
}
TOLERANCE_CM = .15


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preflight():
    recipe = read_json(ROOT / 'whole_buildings_kit.json')['buildings']
    audited = read_json(WORK / 'prepared_fbx_audit.json')
    candidate = read_json(ROOT.parent / 'west_mark_lane_whole_buildings_candidate.json')['buildings']
    surveys = {record['id']: record for record in candidate}
    if recipe.keys() != NAMES.keys() or audited.keys() != NAMES.keys() or surveys.keys() != NAMES.keys():
        raise RuntimeError('Expected the same three reviewed Mark Lane shells in both manifests')
    for shell_id, name in NAMES.items():
        spec, audit = recipe[shell_id], audited[shell_id]
        source = ROOT / 'Source' / f'{name}.fbx'
        prepared = WORK / 'Source' / source.name
        if spec['fbx'] != f'Source/{source.name}' or spec['collision']:
            raise RuntimeError(f'Unexpected source or collision contract for {name}')
        if digest(source) != audit['canonical_sha256'] or digest(prepared) != audit['prepared_sha256']:
            raise RuntimeError(f'{name}: regenerate and audit the prepared FBX before import')
        if (audit['triangles'], audit['materials'], audit['uv_layers'], audit['pivot_m'], audit['reflected_axis']) != (
            spec['triangles'], spec['materials'], ['UV0'], [0, 0, 0], 'Y'
        ) or audit['signed_volume_m3'] <= 0:
            raise RuntimeError(f'{name}: invalid bridge audit')
        verify_survey(spec, surveys[shell_id], audit)
    return recipe, audited


def verify_survey(spec, survey, audit):
    pivot = spec['world_pivot_m']
    yaw = math.radians(spec['yaw_deg'])
    forward, right = (math.cos(yaw), math.sin(yaw)), (-math.sin(yaw), math.cos(yaw))
    for measured, expected in ((forward, spec['axis_x_world_xy']), (right, spec['axis_y_world_xy']),
                               (forward, survey['entry']['outward'])):
        if math.dist(measured, expected) > 1e-5:
            raise RuntimeError(f'{survey["id"]}: yaw does not reproduce the surveyed axes')
    outline, world = spec['footprint_local_m'], survey['footprint']
    if (pivot != survey['origin_m'] or len(outline) != len(world)
            or audit['matched_footprint_vertices'] != len(outline)):
        raise RuntimeError(f'{survey["id"]}: surveyed origin or outline disagrees with the bridge')
    for (x, y), expected in zip(outline, world):
        point = (pivot[0] + x * forward[0] + y * right[0], pivot[1] + x * forward[1] + y * right[1])
        if math.dist(point, expected) > TOLERANCE_CM / 100:
            raise RuntimeError(f'{survey["id"]}: mapped footprint vertex {point} != {expected}')


def require_idle(unreal):
    lease = PROJECT / 'Saved/PIE_LOCK.json'
    if lease.is_file():
        record = read_json(lease)
        if float(record['expires_epoch']) > time.time():
            raise RuntimeError(f'PIE is reserved by {record["owner"]} until {record["expires_local"]}')
    if unreal.EditorLevelLibrary.get_pie_worlds(True):
        raise RuntimeError('The editor still has an active PIE world')


def fbx_options(unreal):
    options = unreal.FbxImportUI()
    options.set_editor_properties({
        'automated_import_should_detect_type': False,
        'mesh_type_to_import': unreal.FBXImportType.FBXIT_STATIC_MESH,
        'import_as_skeletal': False,
        'import_mesh': True,
        'import_materials': False,
        'import_textures': False,
        'import_animations': False,
        'override_full_name': True,
    })
    options.static_mesh_import_data.set_editor_properties({
        'auto_generate_collision': False,
        'generate_lightmap_u_vs': False,
        'build_nanite': False,
        'remove_degenerates': False,
        'import_mesh_lods': False,
        'combine_meshes': False,
        'reorder_material_to_fbx_order': True,
        'static_mesh_lod_group': 'None',
        'convert_scene': False,
        'convert_scene_unit': True,
        'force_front_x_axis': False,
        'transform_vertex_to_absolute': True,
        'bake_pivot_in_vertex': False,
        'import_translation': unreal.Vector(0, 0, 0),
        'import_rotation': unreal.Rotator(0, 0, 0),
        'import_uniform_scale': 1.0,
        'normal_import_method': unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS,
    })
    return options


def package_path(name):
    return f'{DEST}/{name}'


def package_file(name):
    return PROJECT / 'Content' / (package_path(name).removeprefix('/Game/') + '.uasset')


def import_mesh(unreal, name, options):
    task = unreal.AssetImportTask()
    task.set_editor_properties({
        'filename': str(WORK / 'Source' / f'{name}.fbx'),
        'destination_path': DEST,
        'destination_name': name,
        'automated': True,
        'replace_existing': False,
        'save': False,
        'factory': unreal.FbxFactory(),
        'options': options,
    })
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    reported = [str(path) for path in task.get_editor_property('imported_object_paths')]
    exact = f'{package_path(name)}.{name}'
    if reported != [exact]:
        raise RuntimeError(f'{name}: expected only {exact}, import reported {reported}')
    return unreal.load_asset(exact, unreal.StaticMesh)


def get_slots(mesh):
    return [str(slot.get_editor_property('material_slot_name'))
            for slot in mesh.get_editor_property('static_materials')]


def verify_geometry(unreal, mesh, outline, audit):
    desc = mesh.get_static_mesh_description(0)
    if desc is None:
        raise RuntimeError(f'{mesh.get_name()}: no editable LOD0 geometry')
    positions = []
    for index in range(desc.get_vertex_count()):
        vertex = unreal.VertexID(index)
        if not desc.is_vertex_valid(vertex):
            raise RuntimeError(f'{mesh.get_name()}: LOD0 has an invalid vertex ID')
        point = desc.get_vertex_position(vertex)
        positions.append((point.x, point.y, point.z))
    ground = [(x, y) for x, y, z in positions if abs(z) < TOLERANCE_CM]
    for x, y in outline:
        if not any(abs(gx - 100 * x) < TOLERANCE_CM and abs(gy - 100 * y) < TOLERANCE_CM for gx, gy in ground):
            raise RuntimeError(f'{mesh.get_name()}: missing source ground vertex ({x}, {y}); axes or pivot drifted')
    if desc.get_triangle_count() != audit['triangles']:
        raise RuntimeError(f'{mesh.get_name()}: stored LOD0 geometry triangle count drifted')
    tetrahedra = []
    for index in range(desc.get_triangle_count()):
        triangle = unreal.TriangleID(index)
        if not desc.is_triangle_valid(triangle):
            raise RuntimeError(f'{mesh.get_name()}: LOD0 has an invalid triangle ID')
        # The per-corner accessors return valid IDs in UE 5.9. The array
        # accessor can return corrupt struct values to Python.
        vertices = [desc.get_vertex_instance_vertex(desc.get_triangle_vertex_instance(triangle, corner))
                    for corner in range(3)]
        if not all(desc.is_vertex_valid(vertex) for vertex in vertices):
            raise RuntimeError(f'{mesh.get_name()}: triangle {index} has an invalid corner')
        a, b, c = (positions[vertex.id_value] for vertex in vertices)
        tetrahedra.append(a[0] * (b[1] * c[2] - b[2] * c[1]) + a[1] * (b[2] * c[0] - b[0] * c[2])
                          + a[2] * (b[0] * c[1] - b[1] * c[0]))
    # Unreal's clockwise triangle convention negates the right-handed formula.
    volume = math.fsum(tetrahedra) / -6e6
    if not math.isclose(volume, audit['signed_volume_m3'], rel_tol=1e-4, abs_tol=.001):
        raise RuntimeError(f'{mesh.get_name()}: LOD0 winding or volume drifted ({volume} m³)')
    return len(outline), volume


def verify_mesh(unreal, mesh, name, spec, audit):
    path = package_path(name)
    if not isinstance(mesh, unreal.StaticMesh) or mesh.get_path_name() != f'{path}.{name}':
        raise RuntimeError(f'Expected owned static mesh {path}')
    editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    bounds = mesh.get_bounds()
    actual_bounds = [[getattr(bounds.origin, axis) + sign * getattr(bounds.box_extent, axis) for axis in 'xyz']
                     for sign in (-1, 1)]
    if any(abs(a - b) > TOLERANCE_CM for lhs, rhs in zip(actual_bounds, spec['bounds_cm']) for a, b in zip(lhs, rhs)):
        raise RuntimeError(f'{name}: signed centimetre bounds {actual_bounds} != {spec["bounds_cm"]}')
    sections = mesh.get_num_sections(0)
    uv_channels = editor.get_num_uv_channels(mesh, 0)
    triangles = mesh.get_num_triangles(0)
    mesh_materials = [mesh.get_material(i) for i in range(len(spec['materials']))]
    material_packages = [mat.get_package().get_name() if mat else None for mat in mesh_materials]
    expected_packages = [f'{MATERIALS}/{slot}' for slot in spec['materials']]
    if get_slots(mesh) != spec['materials'] or material_packages != expected_packages:
        raise RuntimeError(f'{name}: LOD0 slot names or direct material references do not match the source')
    if (sections, uv_channels, triangles) != (len(spec['materials']), 1, spec['triangles']):
        raise RuntimeError(f'{name}: unexpected sections/UVs/triangles {(sections, uv_channels, triangles)}')
    simple = editor.get_simple_collision_count(mesh)
    convex = editor.get_convex_collision_count(mesh)
    collision_sections = [i for i in range(sections) if editor.is_section_collision_enabled(mesh, 0, i)]
    complexity = editor.get_collision_complexity(mesh)
    if (simple or convex or len(collision_sections) != sections
            or complexity != unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE):
        raise RuntimeError(f'{name}: invalid collision: {simple} simple, {convex} convex, {complexity}, '
                           f'{len(collision_sections)}/{sections} enabled sections')
    matched, volume = verify_geometry(unreal, mesh, spec['footprint_local_m'], audit)
    return {'package': path, 'bounds_cm': actual_bounds, 'lod0_triangles': triangles, 'uv_channels': uv_channels,
            'sections': sections, 'material_packages': material_packages, 'simple_collision': simple,
            'convex_collision': convex, 'collision_complexity': 'ComplexAsSimple',
            'collision_sections': collision_sections, 'matched_ground_vertices': matched, 'signed_volume_m3': volume}


def configure_collision(unreal, mesh):
    editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    for index in range(mesh.get_num_sections(0)):
        if not editor.is_section_collision_enabled(mesh, 0, index):
            editor.enable_section_collision(mesh, True, 0, index)
    if not editor.set_collision_complexity(mesh, unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE):
        raise RuntimeError(f'{mesh.get_name()}: could not configure ComplexAsSimple collision')


def verify_registry(unreal, rows):
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.scan_paths_synchronous([DEST], True)
    options = unreal.AssetRegistryDependencyOptions()
    options.set_editor_property('include_soft_package_references', False)
    for row in rows.values():
        dependencies = {str(name) for name in registry.get_dependencies(row['package'], options) or []}
        missing = set(row['material_packages']) - dependencies
        if missing:
            raise RuntimeError(f'{row["package"]}: saved registry is missing hard material refs {sorted(missing)}')
        row['hard_material_packages'] = sorted(set(row['material_packages']) & dependencies)


def run(verify_only=False):
    import unreal

    recipe, audit = preflight()
    require_idle(unreal)
    material_names = sorted({name for spec in recipe.values() for name in spec['materials']})
    materials = {name: unreal.load_asset(f'{MATERIALS}/{name}.{name}', unreal.MaterialInterface)
                 for name in material_names}
    missing = [name for name, material in materials.items() if not material]
    if missing:
        raise RuntimeError(f'Missing shared medieval materials: {missing}')

    report = {'meshes': {}, 'saved_packages': []}
    created = []
    assets = unreal.EditorAssetLibrary
    for shell_id, name in NAMES.items():
        path, spec = package_path(name), recipe[shell_id]
        if assets.does_asset_exist(path):
            mesh = unreal.load_asset(f'{path}.{name}', unreal.StaticMesh)
            if not package_file(name).is_file():
                # Reuse a prior attempt's in-memory asset only if its source
                # is this exact audited FBX. It still needs all checks and a save.
                source = Path(mesh.get_editor_property('asset_import_data').get_first_filename()).resolve()
                if verify_only or source != WORK / 'Source' / f'{name}.fbx':
                    raise RuntimeError(f'{name}: unexpected unsaved asset from {source}')
                created.append(mesh)
        else:
            if verify_only:
                raise RuntimeError(f'Missing {path}')
            mesh = import_mesh(unreal, name, fbx_options(unreal))
            if not mesh or get_slots(mesh) != spec['materials']:
                raise RuntimeError(f'{name}: FBX material slot order differs from the canonical export')
            for index, slot in enumerate(spec['materials']):
                mesh.set_material(index, materials[slot])
            configure_collision(unreal, mesh)
            created.append(mesh)
        row = verify_mesh(unreal, mesh, name, spec, audit[shell_id])
        row['prepared_sha256'] = audit[shell_id]['prepared_sha256']
        row['geometry_sha256'] = audit[shell_id]['geometry_sha256']
        report['meshes'][name] = row

    if created:
        require_idle(unreal)
        expected_packages = {package_path(name) for name in NAMES.values()}
        packages = [mesh.get_package() for mesh in created]
        paths = [package.get_name() for package in packages]
        if len(set(paths)) != len(paths) or not set(paths) <= expected_packages:
            raise RuntimeError(f'Unexpected owned save scope: {paths}')
        if not unreal.EditorLoadingAndSavingUtils.save_packages(packages, False):
            raise RuntimeError(f'Failed to save exact static mesh packages: {paths}')
        report['saved_packages'] = paths
    verify_registry(unreal, report['meshes'])
    (WORK / 'ue_import_report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__' and '--preflight' in sys.argv:
    preflight()
    print(f'Audited source and import hashes match for {len(NAMES)} meshes under {DEST}')
