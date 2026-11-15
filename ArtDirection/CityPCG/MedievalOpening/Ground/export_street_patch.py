"""Export a trace-verified street patch without embedding its Unreal material."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import re

import numpy as np


ASSET = 'SM_GL1450_WestStreetPaving'


def export_street_patch(plan_path, output, asset=ASSET, manifest='west_street_mesh.json'):
    if not re.fullmatch(r'SM_GL1450_[A-Za-z0-9_]+', asset) or not re.fullmatch(r'[a-z_]+\.json', manifest):
        raise ValueError('Expected a medieval ground mesh name and a local JSON manifest name')
    plan_bytes = plan_path.read_bytes()
    plan = json.loads(plan_bytes)
    if plan['trace_status'] != 'verified' or plan['collision_profile'] != 'NoCollision':
        raise ValueError('Provide a trace-verified NoCollision plan')
    origin = np.array((*plan['start_cm'], 0))
    points, normals, uv, triangles = [], [], [], []
    for patch in plan['patches']:
        vertices = np.asarray(patch['world_vertices_cm'])
        first, second, third = patch['triangles'][0]
        a, b, c = vertices[[first, second, third]]
        normal = np.cross(b - a, c - a)
        if normal[2] <= 0:
            raise ValueError(f'Degenerate or downward patch: {patch["source_actor"]}')
        normal /= np.linalg.norm(normal)
        offset = len(points)
        # GLB X/Z become Unreal X/Y. The axis swap reverses winding.
        points.extend(((vertices - origin) / 100)[:, (0, 2, 1)])
        normals.extend([normal[[0, 2, 1]]] * len(vertices))
        uv.extend(patch['uv_top_left'])
        triangles.extend([offset + a, offset + c, offset + b] for a, b, c in patch['triangles'])

    binary = bytearray()
    views, accessors = [], []

    def add(values, dtype, shape, component_type, target, bounds=False):
        array = np.asarray(values, dtype=dtype)
        payload = array.tobytes()
        views.append({'buffer': 0, 'byteOffset': len(binary), 'byteLength': len(payload), 'target': target})
        binary.extend(payload)
        accessor = {'bufferView': len(views)-1, 'componentType': component_type, 'count': len(array), 'type': shape}
        if bounds:
            accessor.update(min=array.min(axis=0).tolist(), max=array.max(axis=0).tolist())
        accessors.append(accessor)
        return len(accessors)-1

    attributes = {
        'POSITION': add(points, '<f4', 'VEC3', 5126, 34962, bounds=True),
        'NORMAL': add(normals, '<f4', 'VEC3', 5126, 34962),
        'TEXCOORD_0': add(uv, '<f4', 'VEC2', 5126, 34962),
    }
    indices = add(np.asarray(triangles).reshape(-1), '<u4', 'SCALAR', 5125, 34963)
    gltf = {
        'asset': {'version': '2.0', 'generator': 'Reflections verified street patch'},
        'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0, 'name': asset}],
        'meshes': [{'name': asset, 'primitives': [{'attributes': attributes, 'indices': indices}]}],
        'buffers': [{'byteLength': len(binary)}], 'bufferViews': views, 'accessors': accessors,
    }
    header = json.dumps(gltf, separators=(',', ':')).encode('utf-8')
    header += b' ' * (-len(header) % 4)
    payload = (
        struct.pack('<4sII', b'glTF', 2, 28+len(header)+len(binary))
        + struct.pack('<I4s', len(header), b'JSON') + header
        + struct.pack('<I4s', len(binary), b'BIN\0') + binary
    )
    output.mkdir(parents=True, exist_ok=True)
    (output/f'{asset}.glb').write_bytes(payload)
    report = {
        'mesh': asset, 'actor_origin_cm': origin.tolist(), 'mesh_sha256': hashlib.sha256(payload).hexdigest(),
        'plan_sha256': hashlib.sha256(plan_bytes).hexdigest(), 'triangles': len(triangles),
        'source_frontages': plan['frontages'], 'source_tile_sha256': plan['tile_sha256'],
        'material_asset': plan['material_asset'], 'collision_profile': plan['collision_profile'],
    }
    (output/manifest).write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--asset', default=ASSET)
    parser.add_argument('--manifest', default='west_street_mesh.json')
    arguments = parser.parse_args()
    export_street_patch(arguments.plan, arguments.output, arguments.asset, arguments.manifest)
