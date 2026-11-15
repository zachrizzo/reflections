"""Check MerchantGate size, pivot and an unobstructed passage in a baked GLB."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

from extract_tile_frontages import accessor


PROJECT = Path(__file__).resolve().parents[2]
SAVED = PROJECT / 'Saved'
TARGET_M = (7.0, 13.0, 8.0)  # Depth, width, height in the audit's Z-up frame.
SIZE_TOLERANCE_M = (.55, .60, .60)
CLEAR_HALF_WIDTH_M = 1.25
CLEAR_FLOOR_M = .06
CLEAR_HEIGHT_M = 2.70
PROBES_M = {'left_pier': (-2.20, 1.10), 'right_pier': (2.20, 1.10),
            'above_arch': (0, 3.75), 'upper_lumen': (0, 3.05)}
MIN_BUILDING_DEPTH_HIT_M = 3.80


def glb(raw):
    if len(raw) < 28 or struct.unpack_from('<4sII', raw) != (b'glTF', 2, len(raw)):
        raise ValueError('Expected a complete glTF 2 binary')
    size, kind = struct.unpack_from('<I4s', raw, 12)
    if kind != b'JSON' or 28 + size > len(raw):
        raise ValueError('GLB does not contain a complete JSON chunk')
    binary_size, kind = struct.unpack_from('<I4s', raw, 20 + size)
    if kind != b'BIN\0' or 28 + size + binary_size != len(raw):
        raise ValueError('Expected exactly one binary mesh chunk')
    return json.loads(raw[20:20 + size]), memoryview(raw)[28 + size:]


def identity_mesh(document):
    nodes, meshes = document['nodes'], document['meshes']
    scene = document['scenes'][document.get('scene', 0)]
    if len(nodes) != 1 or len(meshes) != 1 or scene.get('nodes') != [0] or nodes[0].get('mesh') != 0:
        raise ValueError('Bake one selected StaticMesh to an identity GLB node before QA')
    node = nodes[0]
    identity = {'translation': [0, 0, 0], 'rotation': [0, 0, 0, 1], 'scale': [1, 1, 1],
                'matrix': [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]}
    for attribute, expected in identity.items():
        values = node.get(attribute, expected)
        if len(values) != len(expected) or not all(math.isfinite(a) and abs(a - b) < 1e-6 for a, b in zip(values, expected)):
            raise ValueError(f'Bake the non-identity node {attribute} into the vertices')
    if any(field in node for field in ('children', 'skin', 'weights')) or document.get('animations'):
        raise ValueError('Expected a plain static building mesh')
    primitives = meshes[0]['primitives']
    if not primitives or any(part.get('mode', 4) != 4 or part.get('extensions') or part.get('targets')
                             for part in primitives):
        raise ValueError('Expected indexed, uncompressed triangle primitives')
    return primitives


def triangles(document, binary, primitives):
    valid_indices = {('SCALAR', 5121), ('SCALAR', 5123), ('SCALAR', 5125)}
    for part in primitives:
        coords = accessor(document, binary, part['attributes']['POSITION'], {('VEC3', 5126)})
        # +X longitudinal, glTF +Y up. Lateral sign is immaterial to the centered QA.
        points = [(x, z, y) for x, y, z in coords]
        corners = accessor(document, binary, part['indices'], valid_indices)
        if len(corners) % 3 or not corners or any(index >= len(points) for (index,) in corners):
            raise ValueError('Invalid triangle index stream')
        for i in range(0, len(corners), 3):
            yield tuple(points[corners[j][0]] for j in (i, i + 1, i + 2))


def clip(vertices, axis, limit, sign):
    result = []
    for a, b in zip(vertices, vertices[1:] + vertices[:1]):
        da, db = sign * (a[axis] - limit), sign * (b[axis] - limit)
        if da >= 0:
            result.append(a)
        if (da >= 0) != (db >= 0):
            t = da / (da - db)
            result.append(tuple(x + t * (y - x) for x, y in zip(a, b)))
    return result


def intersects_clearance(triangle, low, high):
    # Exact polygon clipping against the four corridor planes tests a continuous
    # cross-section through the full depth, including caps between sample rays.
    if (low[1] > CLEAR_HALF_WIDTH_M or high[1] < -CLEAR_HALF_WIDTH_M
            or low[2] > CLEAR_HEIGHT_M or high[2] < CLEAR_FLOOR_M):
        return False
    candidate = triangle
    for axis, limit, sign in ((1, -CLEAR_HALF_WIDTH_M, 1), (1, CLEAR_HALF_WIDTH_M, -1),
                              (2, CLEAR_FLOOR_M, 1), (2, CLEAR_HEIGHT_M, -1)):
        candidate = clip(candidate, axis, limit, sign)
        if not candidate:
            return False
    return True


def longitudinal_hit(triangle, y, z):
    a, b, c = triangle
    b_y, b_z, c_y, c_z = b[1] - a[1], b[2] - a[2], c[1] - a[1], c[2] - a[2]
    determinant = b_y * c_z - b_z * c_y
    if abs(determinant) < 1e-10:
        return None
    dy, dz = y - a[1], z - a[2]
    u, v = (dy * c_z - dz * c_y) / determinant, (b_y * dz - b_z * dy) / determinant
    if min(u, v, 1 - u - v) < -1e-7:
        return None
    return a[0] + u * (b[0] - a[0]) + v * (c[0] - a[0])


def audit_geometry(mesh_triangles):
    low = [math.inf] * 3
    high = [-math.inf] * 3
    intersecting = 0
    examples = []
    hits = {name: [] for name in PROBES_M}
    count = 0
    for triangle in mesh_triangles:
        if not all(math.isfinite(value) for point in triangle for value in point):
            raise ValueError('Non-finite mesh vertex')
        tmin = [min(point[axis] for point in triangle) for axis in range(3)]
        tmax = [max(point[axis] for point in triangle) for axis in range(3)]
        for axis in range(3):
            low[axis], high[axis] = min(low[axis], tmin[axis]), max(high[axis], tmax[axis])
        if intersects_clearance(triangle, tmin, tmax):
            intersecting += 1
            if len(examples) < 10:
                examples.append({'triangle': count, 'bounds_m': [tmin, tmax]})
        for name, (y, z) in PROBES_M.items():
            if tmin[1] <= y <= tmax[1] and tmin[2] <= z <= tmax[2]:
                hit = longitudinal_hit(triangle, y, z)
                if hit is not None:
                    hits[name].append(hit)
        count += 1
    if not count:
        raise ValueError('Empty gate mesh')
    size = [end - start for start, end in zip(low, high)]
    errors = []
    if any(abs(found - expected) > tolerance for found, expected, tolerance in zip(size, TARGET_M, SIZE_TOLERANCE_M)):
        errors.append('Depth, width or height is outside the approved metre envelope')
    if abs(low[2]) > .04 or any(abs(low[axis] + high[axis]) / 2 > .25 for axis in (0, 1)):
        errors.append('Pivot is not centered at the building base')
    if intersecting:
        errors.append('Geometry obstructs the continuous passage clearance')
    if hits['upper_lumen']:
        errors.append('Center of the upper arch is blocked at 3.05 m')
    for name in ('left_pier', 'right_pier', 'above_arch'):
        if not hits[name] or max(hits[name]) - min(hits[name]) < MIN_BUILDING_DEPTH_HIT_M:
            errors.append(f'{name}: missing full-depth masonry or header silhouette')
    return {'status': 'failed' if errors else 'passed', 'errors': errors, 'triangles': count,
            'bounds_m': [low, high], 'depth_width_height_m': size,
            'clear_width_m': 2 * CLEAR_HALF_WIDTH_M, 'clear_height_m': CLEAR_HEIGHT_M,
            'ignored_floor_band_m': CLEAR_FLOOR_M,
            'obstructing_triangles': intersecting, 'obstruction_examples': examples,
            'probes': {name: {'lateral_height_m': PROBES_M[name], 'hit_count': len(values),
                              'longitudinal_hit_bounds_m': [min(values), max(values)] if values else None}
                       for name, values in hits.items()}}


def audit_file(path, require_uv0=False):
    raw = path.read_bytes()
    document, binary = glb(raw)
    primitives = identity_mesh(document)
    report = audit_geometry(triangles(document, binary, primitives))
    report.update(mesh=str(path), sha256=hashlib.sha256(raw).hexdigest(), primitives=len(primitives),
                  uv0_primitives=sum('TEXCOORD_0' in part['attributes'] for part in primitives))
    if require_uv0 and report['uv0_primitives'] != len(primitives):
        report['status'] = 'failed'
        report['errors'].append('At least one final material primitive lacks UV0')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mesh', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--require-uv0', action='store_true')
    args = parser.parse_args()
    report_path = args.report.resolve()
    if not report_path.is_relative_to(SAVED.resolve()) or report_path.suffix.casefold() != '.json' or report_path.exists():
        parser.error('Choose a new .json report inside this project’s Saved directory')
    try:
        report = audit_file(args.mesh, args.require_uv0)
    except (KeyError, ValueError, IndexError, TypeError, struct.error) as exc:
        report = {'status': 'failed', 'errors': [str(exc)], 'mesh': str(args.mesh)}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(f'{report["status"].upper()}: {report_path}')
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
