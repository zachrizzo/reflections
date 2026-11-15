"""Read-only source-section/GLB geometry comparison for Tile_p03_p00.

Run only in an allocated Gray London editor turn. No packages or actors are
modified or saved. Results are returned to the caller and never activate the
pilot or write rollout metadata. See README_WEST_MARK_LANE_SECTION_PROOF.md.
"""

from collections import Counter
import math
from pathlib import Path
import struct

import batch_export_geodata_unreal as lease_tools
from extract_tile_frontages import read_glb


TILE = 'Tile_p03_p00'
PACKAGE = f'{lease_tools.TILE_ROOT}/{TILE}'
ASSET = f'{PACKAGE}.{TILE}'
MAX_TRIANGLES = 1_000_000
MAX_VERTICES = 3_000_000
MAX_GLB_BYTES = 256 * 1024 * 1024
SCALE = struct.unpack('<f', struct.pack('<f', .01))[0]


class CapabilityError(RuntimeError):
    """A required reflected GeometryScript operation is not safely available."""


def f32(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('Non-finite vertex coordinates cannot be compared.')
    value = struct.unpack('<f', struct.pack('<f', value))[0]
    return 0.0 if value == 0 else value


def from_unreal_cm(vertex):
    # UE 5.9 GLTFCoreUtilities::ConvertPosition: FVector3f * float scale,
    # then (X,Z,Y). Preserve float32 rounding and keep winding intact.
    x, y, z = (f32(v) for v in vertex)
    return tuple(f32(v * SCALE) for v in (x, z, y))


def triangle_key(points):
    """Cyclic rotations are equal; reversed winding remains different."""
    if len(points) != 3:
        raise ValueError('A triangle must contain exactly three vertices.')
    vertices = tuple(struct.pack('<3f', *(f32(c) for c in vertex)) for vertex in points)
    if len(set(vertices)) != 3:
        raise ValueError('Degenerate triangle: mapping needs manual review.')
    return min(vertices, vertices[1:] + vertices[:1], vertices[2:] + vertices[:2])


def read_accessor(data, blob, index, expected):
    if type(index) is not int or not 0 <= index < len(data['accessors']):
        raise ValueError('GLB references an invalid accessor.')
    spec = data['accessors'][index]
    formats = {('VEC3', 5126): '<3f', ('SCALAR', 5121): '<B',
               ('SCALAR', 5123): '<H', ('SCALAR', 5125): '<I'}
    layout = (spec.get('type'), spec.get('componentType'))
    if layout not in expected or 'sparse' in spec or spec.get('normalized'):
        raise ValueError(f'Unsupported GLB accessor: {layout}.')
    view_index = spec['bufferView']
    if type(view_index) is not int or not 0 <= view_index < len(data['bufferViews']):
        raise ValueError('GLB references an invalid buffer view.')
    view = data['bufferViews'][view_index]
    if view.get('buffer') != 0 or view.get('extensions'):
        raise ValueError('Expected a single uncompressed binary mesh buffer.')
    reader = struct.Struct(formats[layout])
    count = spec['count']
    start = view.get('byteOffset', 0) + spec.get('byteOffset', 0)
    stride = view.get('byteStride', reader.size)
    view_start, view_length = view.get('byteOffset', 0), view['byteLength']
    if (type(count) is not int or count < 0 or count > MAX_VERTICES
            or type(start) is not int or type(stride) is not int or stride < reader.size
            or type(view_start) is not int or type(view_length) is not int
            or view_start < 0 or view_length < 0 or start < view_start
            or view_start + view_length > len(blob)
            or (count and start + (count - 1) * stride + reader.size > view_start + view_length)):
        raise ValueError('Invalid GLB accessor bounds.')
    return [reader.unpack_from(blob, start + n * stride) for n in range(count)]


def glb_sections(path):
    if path.stat().st_size > MAX_GLB_BYTES:
        raise ValueError('GLB exceeds the bounded comparison size.')
    data, blob = read_glb(path)
    with path.open('rb') as stream:
        stream.seek(12)
        chunk = stream.read(8)
        if len(chunk) != 8:
            raise ValueError('GLB JSON chunk header is truncated.')
        json_size, json_kind = struct.unpack('<I4s', chunk)
        stream.seek(20 + json_size)
        chunk = stream.read(8)
        if len(chunk) != 8:
            raise ValueError('GLB binary chunk header is truncated.')
        bin_size, bin_kind = struct.unpack('<I4s', chunk)
        if (json_kind != b'JSON' or bin_kind != b'BIN\x00' or json_size % 4 or bin_size % 4
                or 28 + json_size + bin_size != path.stat().st_size or len(blob) != bin_size):
            raise ValueError('GLB chunk boundaries are inconsistent.')
    if (len(data.get('buffers', [])) != 1 or 'uri' in data['buffers'][0]
            or data['buffers'][0].get('byteLength', len(blob)) > len(blob)):
        raise ValueError('GLB geometry must be self-contained.')
    sections = []
    total = 0
    for primitive in data['meshes'][0]['primitives']:
        if primitive.get('mode', 4) != 4 or primitive.get('extensions'):
            raise ValueError('Expected uncompressed indexed triangles.')
        positions = read_accessor(data, blob, primitive['attributes']['POSITION'], {('VEC3', 5126)})
        indices = read_accessor(data, blob, primitive['indices'],
                                {('SCALAR', 5121), ('SCALAR', 5123), ('SCALAR', 5125)})
        if not indices or len(indices) % 3:
            raise ValueError('Empty or incomplete GLB triangle list.')
        total += len(indices) // 3
        if total > MAX_TRIANGLES:
            raise ValueError('GLB exceeds the bounded triangle count.')
        counter = Counter()
        for start in range(0, len(indices), 3):
            corners = [entry[0] for entry in indices[start:start + 3]]
            if any(index >= len(positions) for index in corners):
                raise ValueError('GLB index exceeds its position accessor.')
            counter[triangle_key([positions[index] for index in corners])] += 1
        sections.append(counter)
    if not sections:
        raise ValueError('No GLB primitives found.')
    return sections


def source_sections(positions, triangles, section_ids, section_count):
    if (not triangles or len(triangles) > MAX_TRIANGLES or len(positions) > MAX_VERTICES
            or len(triangles) != len(section_ids) or section_count <= 0):
        raise ValueError('Source triangle lists are empty, too large, or inconsistent.')
    positions = [from_unreal_cm((point.x, point.y, point.z)) for point in positions]
    sections = [Counter() for _ in range(section_count)]
    for triangle, section in zip(triangles, section_ids):
        indexes = (triangle.x, triangle.y, triangle.z)
        if (type(section) is not int or not 0 <= section < section_count
                or any(type(i) is not int or not 0 <= i < len(positions) for i in indexes)):
            raise ValueError('Source triangle or section ID is invalid.')
        sections[section][triangle_key([positions[i] for i in indexes])] += 1
    if any(not section for section in sections):
        raise ValueError('Empty source sections need manual review.')
    return sections


def compare(source, primitives, slot_names):
    if len(source) != len(slot_names):
        raise ValueError('Source section IDs and source slot names disagree.')
    candidates = [[i for i, section in enumerate(source) if section == primitive]
                  for primitive in primitives]
    reverse = [[i for i, matches in enumerate(candidates) if section in matches]
               for section in range(len(source))]
    shared = set()
    seen = set()
    for section in source:
        shared.update(seen.intersection(section))
        seen.update(section)
    bijective = (len(primitives) == len(source) and all(len(x) == 1 for x in candidates)
                 and all(len(x) == 1 for x in reverse) and not shared)
    mapping = [{'primitive': i, 'source_section_candidates': matches,
                'source_slot_candidates': [slot_names[j] for j in matches],
                'triangle_count': sum(primitives[i].values())}
               for i, matches in enumerate(candidates)]
    roads = [i for i, name in enumerate(slot_names) if name == 'GL_Road']
    road = next((i for i, matches in enumerate(candidates) if len(roads) == 1 and matches == roads), None)
    return {'status': 'geometry_match_review_required' if bijective else 'ambiguous_or_mismatch',
            'exact_signed_triangle_bijection': bijective,
            'section_count': len(source), 'primitive_count': len(primitives),
            'shared_signed_triangles_across_source_sections': len(shared),
            'mapping': mapping, 'road_section_candidates': roads,
            'road_primitive_candidate': road if bijective else None,
            'road_retention_in_filtered_replacement_verified': False,
            'activation_authorized': False}


def require_capabilities(unreal):
    required = {
        'GeometryScript_AssetUtils': ('check_static_mesh_has_available_lod', 'copy_mesh_from_static_mesh_v2',
                                      'get_section_material_list_from_static_mesh'),
        'GeometryScript_MeshQueries': ('get_all_triangle_indices', 'get_all_vertex_positions'),
        'GeometryScript_Materials': ('get_all_triangle_material_i_ds',),
        'GeometryScript_List': ('convert_triangle_list_to_array', 'convert_vector_list_to_array',
                                'convert_index_list_to_array'),
    }
    missing = [f'{cls}.{method}' for cls, methods in required.items() for method in methods
               if not hasattr(getattr(unreal, cls, None), method)]
    missing += [name for name in ('DynamicMesh', 'GeometryScriptMeshReadLOD',
                                   'GeometryScriptCopyMeshFromAssetOptions', 'GeometryScriptLODType',
                                   'GeometryScriptOutcomePins') if not hasattr(unreal, name)]
    if missing:
        raise CapabilityError('Required reflected GeometryScript capability missing: ' + ', '.join(missing))


def reflected_call(name, operation, *args):
    try:
        return operation(*args)
    except (AttributeError, TypeError) as error:
        raise CapabilityError(f'Reflected GeometryScript call {name} is unavailable or has an unexpected signature: {error}') from error


def reflected_source(unreal, mesh, guard):
    """Copy only into a transient DynamicMesh, then query its source-section IDs."""
    require_capabilities(unreal)
    lod = unreal.GeometryScriptMeshReadLOD()
    lod.lod_type, lod.lod_index = unreal.GeometryScriptLODType.SOURCE_MODEL, 0
    available = reflected_call('check_static_mesh_has_available_lod',
                               unreal.GeometryScript_AssetUtils.check_static_mesh_has_available_lod, mesh, lod)
    if not isinstance(available, tuple) or len(available) != 2 or available[0] is not True:
        raise CapabilityError('LOD0 source model is unavailable or the reflected availability result is unexpected.')
    opts = unreal.GeometryScriptCopyMeshFromAssetOptions()
    opts.apply_build_settings = False
    opts.request_tangents = False
    opts.use_build_scale = False
    dynamic = unreal.DynamicMesh()
    copied = reflected_call('copy_mesh_from_static_mesh_v2',
                            unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh_v2, mesh, dynamic, opts, lod, True)
    if (not isinstance(copied, tuple) or len(copied) != 2 or copied[0] != dynamic
            or copied[1] != unreal.GeometryScriptOutcomePins.SUCCESS):
        raise CapabilityError('CopyMeshFromStaticMeshV2 failed or returned an unexpected reflected result.')
    guard()
    materials = reflected_call('get_section_material_list_from_static_mesh',
                               unreal.GeometryScript_AssetUtils.get_section_material_list_from_static_mesh, mesh, lod)
    if (not isinstance(materials, tuple) or len(materials) != 4
            or materials[3] != unreal.GeometryScriptOutcomePins.SUCCESS):
        raise CapabilityError('Cannot obtain source section-to-slot identity from GeometryScript.')
    section_materials, material_indices, slot_names, _outcome = materials
    slots = [str(slot.get_editor_property('material_slot_name'))
             for slot in mesh.get_editor_property('static_materials')]
    if (not len(slot_names) == len(material_indices) == len(section_materials)
            or any(type(index) is not int or not 0 <= index < len(slots)
                   or str(slot_names[n]) != slots[index] or section_materials[n] != mesh.get_material(index)
                   for n, index in enumerate(material_indices))):
        raise CapabilityError('Source section material/slot identities do not agree.')
    queries = unreal.GeometryScript_MeshQueries
    triangles_result = reflected_call('get_all_triangle_indices', queries.get_all_triangle_indices, dynamic, False)
    vertices_result = reflected_call('get_all_vertex_positions', queries.get_all_vertex_positions, dynamic, False)
    ids_result = reflected_call('get_all_triangle_material_i_ds',
                                unreal.GeometryScript_Materials.get_all_triangle_material_i_ds, dynamic)
    if (not all(isinstance(result, tuple) and len(result) == 3 and result[0] == dynamic
                for result in (triangles_result, vertices_result, ids_result))
            or triangles_result[2] is not False or vertices_result[2] is not False or ids_result[2] is not True):
        raise CapabilityError('Dynamic mesh has ID gaps, no section IDs, or unexpected reflected results.')
    lists = unreal.GeometryScript_List
    triangles = list(lists.convert_triangle_list_to_array(triangles_result[1]))
    positions = list(lists.convert_vector_list_to_array(vertices_result[1]))
    section_ids = list(lists.convert_index_list_to_array(ids_result[1]))
    guard()
    return positions, triangles, section_ids, [str(name) for name in slot_names]


def run(owner='codex-gray-london'):
    """Return a provisional report, or fail closed. Never save or activate."""
    import unreal

    project, saved, world, lease = lease_tools.check_session(unreal, owner)
    lease_tools.require_memory()
    glb = (saved / 'CityPCG' / f'{TILE}.glb').resolve()
    if glb.parent != (saved / 'CityPCG').resolve() or not glb.is_file():
        raise RuntimeError('The existing canonical source GLB is missing or redirected.')
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    options = lease_tools.dependency_options(unreal)

    def guard():
        _, _, current, _ = lease_tools.check_session(unreal, owner, expected=lease)
        if current != world:
            raise lease_tools.SessionError('The editor world changed during comparison.')
        lease_tools.require_memory()

    def identity():
        return lease_tools.identity(unreal, registry, options, project, TILE, 'tile', PACKAGE,
                                    lease_tools.descriptors(unreal), lease_tools.loaded_actors(unreal))

    initial, actor = identity()
    mesh = unreal.EditorAssetLibrary.load_asset(PACKAGE)
    if not isinstance(mesh, unreal.StaticMesh) or mesh.get_path_name() != ASSET:
        raise RuntimeError('The source mesh identity is unexpected.')
    transform = lease_tools.transform_evidence(unreal, initial, actor, mesh)
    dirty = lease_tools.dirty_packages(unreal)
    glb_hash = lease_tools.sha256(glb)
    primitives = glb_sections(glb)
    guard()
    positions, triangles, ids, names = reflected_source(unreal, mesh, guard)
    source = source_sections(positions, triangles, ids, len(names))
    result = compare(source, primitives, names)
    guard()
    after, actor_after = identity()
    if (initial != after or lease_tools.dirty_packages(unreal) != dirty or lease_tools.sha256(glb) != glb_hash
            or lease_tools.transform_evidence(unreal, after, actor_after, mesh) != transform):
        raise RuntimeError('Source identity, transform, dirty packages, or GLB changed during comparison.')
    result.update(tile=TILE, source_asset=ASSET, source_package_hashes=initial['package_hashes'],
                  source_glb=str(glb), source_glb_sha256=glb_hash, source_transform=transform,
                  source_lod='SourceModel LOD0; build settings and build scale disabled',
                  comparison='exact float32 signed triangle multisets; cyclic rotations accepted')
    return result
