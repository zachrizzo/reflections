"""Strict, Blender-independent checks for the review-only North Market export.

OBJ has no material-slot ordering. We use the declared MTL order, restricted to
materials actually used by each OBJ, as the explicit FBX slot contract.
"""

from collections import Counter, defaultdict
import hashlib
import itertools
import json
import math
from pathlib import Path


SOURCE_REL = Path('ArtDirection/CityPCG/MedievalOpening/WholeBuildings/NorthMarketDetailedObj')
MANIFEST_SHA = 'a9aeb89aab3a35914d505475b697ddfa01fb48ad43b1a98c6562bf89bdf49095'
NAMES = (
    'SM_GLMedieval_NorthMarketDetail_east_0a73564b',
    'SM_GLMedieval_NorthMarketDetail_east_31c9ff1a',
    'SM_GLMedieval_NorthMarketDetail_west_736fd5c6',
    'SM_GLMedieval_NorthMarketDetail_west_d08bbb3b',
)
POS_TOL = 3e-5  # metres, 0.03 mm
UV_TOL = 3e-5
NORMAL_TOL = 1e-3


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(256 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def within(child, parent):
    child, parent = Path(child).resolve(strict=True), Path(parent).resolve(strict=True)
    if child == parent or not child.is_relative_to(parent) or not child.is_file():
        raise ValueError(f'File must be inside the expected bundle: {child}')
    return child


def read_mtl(source, manifest):
    mtl = within(source / 'NorthMarketDetail.mtl', source)
    if digest(mtl) != manifest['material_sha256']:
        raise ValueError('MTL hash differs from the source manifest')
    mats, current = {}, None
    for raw in mtl.read_text(encoding='utf-8').splitlines():
        fields = raw.split()
        if not fields or fields[0].startswith('#'):
            continue
        if fields[0] == 'newmtl' and len(fields) == 2 and fields[1] not in mats:
            current = fields[1]
            mats[current] = {'kd': None, 'texture': None}
        elif fields[0] == 'Kd' and len(fields) == 4 and current and mats[current]['kd'] is None:
            value = tuple(map(float, fields[1:]))
            if not all(math.isfinite(x) and 0 <= x <= 1 for x in value):
                raise ValueError('Invalid material color')
            mats[current]['kd'] = value
        elif fields[0] == 'map_Kd' and len(fields) == 2 and current and mats[current]['texture'] is None:
            rel = Path(fields[1])
            if rel.parts != ('Textures', rel.name) or rel.suffix != '.png':
                raise ValueError('Unexpected texture path')
            role = current.removeprefix('M_GLMedieval_')
            spec = manifest['textures'].get(role)
            if not spec or Path(spec['path']).name != rel.name:
                raise ValueError('Texture does not match source manifest')
            path = within(source / rel, source / 'Textures')
            if digest(path) != spec['sha256'] or path.read_bytes()[:8] != b'\x89PNG\r\n\x1a\n':
                raise ValueError('Texture hash or PNG signature mismatch')
            mats[current]['texture'] = {'name': rel.name, 'sha256': spec['sha256']}
        else:
            raise ValueError(f'Unexpected or duplicate MTL record: {raw}')
    if not mats or any(v['kd'] is None for v in mats.values()):
        raise ValueError('Incomplete material definitions')
    return mats


def source_spec(source, name):
    if name not in NAMES:
        raise ValueError('Unknown North Market source')
    source = Path(source).resolve(strict=True)
    manifest_path = within(source / 'detailed_obj_manifest.json', source)
    if digest(manifest_path) != MANIFEST_SHA:
        raise ValueError('North Market manifest hash differs from the reviewed snapshot')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    rows = [v for v in manifest['buildings'].values() if v['source_artifact']['file'] == name + '.obj']
    if len(rows) != 1:
        raise ValueError('Source manifest does not identify exactly one building')
    row = rows[0]
    pivot, yaw = row.get('world_pivot_m'), row.get('yaw_deg')
    if (not isinstance(pivot, list) or len(pivot) != 3 or
            any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in pivot) or
            not isinstance(yaw, (int, float)) or isinstance(yaw, bool) or not math.isfinite(yaw)):
        raise ValueError('Invalid or non-finite source placement metadata')
    obj = within(source / (name + '.obj'), source)
    if digest(obj) != row['source_artifact']['sha256']:
        raise ValueError('OBJ hash differs from source manifest')
    return manifest, row, obj, read_mtl(source, manifest)


def _finite(values, count):
    if len(values) != count:
        raise ValueError('Unexpected vector width')
    result = tuple(map(float, values))
    if not all(math.isfinite(v) for v in result):
        raise ValueError('Non-finite geometry channel')
    return result


def read_obj(path, material_names):
    vertices, uvs, normals, faces = [], [], [], []
    edges = set()
    material = None
    libraries = []
    with Path(path).open(encoding='utf-8') as stream:
        for raw in stream:
            f = raw.split()
            if not f or f[0].startswith('#'):
                continue
            if f[0] == 'v':
                vertices.append(_finite(f[1:], 3))
            elif f[0] == 'vt':
                uvs.append(_finite(f[1:], 2))
            elif f[0] == 'vn':
                normals.append(_finite(f[1:], 3))
            elif f[0] == 'mtllib' and len(f) == 2:
                libraries.append(f[1])
            elif f[0] == 'usemtl' and len(f) == 2 and f[1] in material_names:
                material = f[1]
            elif f[0] == 'f' and len(f) >= 4 and material:
                corners, face_vertices = [], []
                for token in f[1:]:
                    fields = token.split('/')
                    if len(fields) != 3 or not all(v.isdigit() and int(v) > 0 for v in fields):
                        raise ValueError('Unsupported or missing OBJ vertex/UV/normal index')
                    vi, ti, ni = (int(v) - 1 for v in fields)
                    try:
                        corners.append(vertices[vi] + uvs[ti] + normals[ni])
                    except IndexError as exc:
                        raise ValueError('OBJ face index out of range') from exc
                    face_vertices.append(vi)
                for a, b in zip(face_vertices, face_vertices[1:] + face_vertices[:1]):
                    if a == b:
                        raise ValueError('Degenerate consecutive OBJ edge')
                    edges.add((min(a, b), max(a, b)))
                faces.append((material, tuple(corners)))
            else:
                raise ValueError(f'Unsupported OBJ record: {f[0]}')
    if libraries != ['NorthMarketDetail.mtl'] or not faces:
        raise ValueError('Missing, duplicate or unexpected OBJ material library')
    used = {m for m, _ in faces}
    return {'vertices': len(vertices), 'edges': len(edges), 'uv_corners': sum(len(f) for _, f in faces),
            'slots': [m for m in material_names if m in used], 'faces': faces}


def _close_corner(a, b):
    return (all(abs(a[i] - b[i]) <= POS_TOL for i in range(3)) and
            all(abs(a[i] - b[i]) <= UV_TOL for i in range(3, 5)) and
            all(abs(a[i] - b[i]) <= NORMAL_TOL for i in range(5, 8)))


def same_face(a, b):
    """Only cyclic shifts match: reversed winding is deliberately rejected."""
    if a[0] != b[0] or len(a[1]) != len(b[1]):
        return False
    x, y = a[1], b[1]
    return any(all(_close_corner(x[i], y[(i + shift) % len(y)]) for i in range(len(x)))
               for shift in range(len(y)) if _close_corner(x[0], y[shift]))


def _bucket(face):
    corners = face[1]
    center = [sum(c[i] for c in corners) / len(corners) for i in range(3)]
    return face[0], len(corners), *(math.floor(v / POS_TOL) for v in center)


def _centroid(face):
    corners = face[1]
    return tuple(sum(c[i] for c in corners) / len(corners) for i in range(3))


def _alignment_difference(expected, actual):
    """Rank diagnostic alignments without changing the strict match decision."""
    left, right = expected[1], actual[1]
    best = None
    for reversed_order in (False, True):
        values = tuple(reversed(right)) if reversed_order else right
        for shift in range(len(values)):
            aligned = [values[(i + shift) % len(values)] for i in range(len(values))]
            position = max(abs(left[i][j] - aligned[i][j]) for i in range(len(left)) for j in range(3))
            uv = max(abs(left[i][j] - aligned[i][j]) for i in range(len(left)) for j in range(3, 5))
            normal = max(abs(left[i][j] - aligned[i][j]) for i in range(len(left)) for j in range(5, 8))
            score = max(position / POS_TOL, uv / UV_TOL, normal / NORMAL_TOL)
            candidate = (score, reversed_order, shift, position, uv, normal)
            if best is None or candidate < best:
                best = candidate
    return best


def _diagnose_missing(face_index, face, actual_faces, used):
    """Explain one unmatched polygon; never allow diagnostics to accept it."""
    material, corners = face
    center = _centroid(face)
    # Include other materials: a changed assignment must not hide an otherwise
    # exact geometry/UV/normal diagnostic. This scan occurs only on failure.
    options = [i for i, candidate in enumerate(actual_faces) if len(candidate[1]) == len(corners)]
    options = sorted(options, key=lambda i: sum((_centroid(actual_faces[i])[j] - center[j]) ** 2
                                                for j in range(3)))[:32]
    details = []
    for i in options:
        score, reversed_order, shift, pos, uv, normal = _alignment_difference(face, actual_faces[i])
        details.append((score, i, reversed_order, shift, pos, uv, normal))
    if not details:
        return (f'source_polygon={face_index} material={material} corners={len(corners)} '
                f'centroid={center}; no candidate with the same corner count')
    score, i, reversed_order, shift, pos, uv, normal = min(details)
    return (f'source_polygon={face_index} material={material} corners={len(corners)} centroid={center}; '
            f'diagnostic_candidate={i} candidate_material={actual_faces[i][0]} already_used={i in used} '
            f'reversed_winding={reversed_order} '
            f'cyclic_shift={shift} max_position_delta_m={pos:.9g} max_uv_delta={uv:.9g} '
            f'max_normal_component_delta={normal:.9g} tolerance_ratio={score:.9g}')


def _validate_pair(expected, actual):
    for model in (expected, actual):
        for material, corners in model['faces']:
            if (not isinstance(material, str) or len(corners) < 3 or
                    any(len(c) != 8 or not all(math.isfinite(v) for v in c) for c in corners)):
                raise ValueError('Invalid or non-finite polygon channel')
    for key in ('vertices', 'edges', 'uv_corners', 'slots'):
        if expected[key] != actual[key]:
            raise ValueError(f'{key} differs: {expected[key]} != {actual[key]}')
    if len(expected['faces']) != len(actual['faces']):
        raise ValueError('Polygon count differs')


def _same_shape(expected, actual):
    """Match material and cyclic position/UV corners, ignoring normals only."""
    if expected[0] != actual[0] or len(expected[1]) != len(actual[1]):
        return False
    left, right = expected[1], actual[1]
    def close(a, b):
        return (all(abs(a[i] - b[i]) <= POS_TOL for i in range(3)) and
                all(abs(a[i] - b[i]) <= UV_TOL for i in range(3, 5)))
    return any(all(close(left[i], right[(i + shift) % len(right)]) for i in range(len(left)))
               for shift in range(len(right)) if close(left[0], right[shift]))


def _neighbor_indices(face, buckets):
    material, count, x, y, z = _bucket(face)
    for dx, dy, dz in itertools.product((-1, 0, 1), repeat=3):
        yield from buckets.get((material, count, x + dx, y + dy, z + dz), ())


def flat_source_normal_plan(expected, actual):
    """Map authored flat face normals only after a fail-closed channel match.

    OBJ normals must be unit and constant across each face. Identical source
    shapes carrying different normals, or multiple possible imported faces,
    are rejected. This is a preparation step, never a substitute for compare().
    """
    _validate_pair(expected, actual)
    source_buckets, actual_buckets = defaultdict(list), defaultdict(list)
    normals = []
    for i, face in enumerate(expected['faces']):
        normal = face[1][0][5:8]
        if (abs(math.sqrt(sum(v * v for v in normal)) - 1.0) > 1e-4 or
                any(any(abs(c[5 + k] - normal[k]) > 1e-7 for k in range(3)) for c in face[1])):
            raise ValueError('Source normals are not finite, unit and flat per face')
        normals.append(normal)
        source_buckets[_bucket(face)].append(i)
    for i, face in enumerate(actual['faces']):
        actual_buckets[_bucket(face)].append(i)
    result, used = [None] * len(actual['faces']), set()
    for i, face in enumerate(expected['faces']):
        for j in _neighbor_indices(face, source_buckets):
            if j != i and _same_shape(face, expected['faces'][j]) and normals[i] != normals[j]:
                raise ValueError('Ambiguous overlapping source shapes carry different normals')
        matches = [j for j in _neighbor_indices(face, actual_buckets)
                   if j not in used and _same_shape(face, actual['faces'][j])]
        if len(matches) != 1:
            raise ValueError('Source shape/UV/material match is missing or ambiguous')
        result[matches[0]] = normals[i]
        used.add(matches[0])
    if any(v is None for v in result):
        raise ValueError('Incomplete source normal mapping')
    return result


def compare(expected, actual):
    """Compare signed polygon geometry, per-corner UV/normals, and named slots.

    Ambiguous matches fail closed, except byte-identical duplicate polygons.
    """
    _validate_pair(expected, actual)
    buckets = defaultdict(list)
    for idx, face in enumerate(actual['faces']):
        buckets[_bucket(face)].append(idx)
    used = set()
    for face_index, face in enumerate(expected['faces']):
        material, count, x, y, z = _bucket(face)
        candidates = []
        for dx, dy, dz in itertools.product((-1, 0, 1), repeat=3):
            for idx in buckets.get((material, count, x + dx, y + dy, z + dz), ()):
                if idx not in used and same_face(face, actual['faces'][idx]):
                    candidates.append(idx)
        if not candidates:
            detail = _diagnose_missing(face_index, face, actual['faces'], used)
            raise ValueError('A source polygon, winding, UV, normal or assignment changed: ' + detail)
        if len(candidates) > 1 and len({actual['faces'][i] for i in candidates}) != 1:
            raise ValueError('Ambiguous polygon match')
        used.add(candidates[0])
    return {'polygons': len(expected['faces']), 'vertices': expected['vertices'], 'edges': expected['edges'],
            'polygon_triangle_count': sum(len(face) - 2 for _, face in expected['faces']),
            'uv_corners': expected['uv_corners'], 'slots': expected['slots'],
            'material_polygons': dict(Counter(m for m, _ in expected['faces'])),
            'position_tolerance_m': POS_TOL, 'uv_tolerance': UV_TOL, 'normal_tolerance': NORMAL_TOL}
