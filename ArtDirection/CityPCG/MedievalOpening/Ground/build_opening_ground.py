"""Build a cosmetic medieval yard/runnel overlay from the opening road geometry."""

import io
import json
import math
from pathlib import Path
import struct
import sys

import numpy as np
from PIL import Image


ORIGIN_XY = (329290, 31090)  # Unreal cm
OSM_TILE_ORIGIN = (300000, 0)  # verified in the Gray London editor
# Four sides taper into the market yard. Street wall bounds stay untouched.
OUTLINE = np.asarray([
    (328885, 30690),
    (329560, 30628),
    (330260, 30725),
    (330397, 31794),
    (329423, 31841),
    (328900, 31600),
], dtype=np.float64)
MIN_XY = OUTLINE.min(axis=0)
MAX_XY = OUTLINE.max(axis=0)


def read_glb(path):
    with path.open('rb') as source:
        magic, version, _ = struct.unpack('<4sII', source.read(12))
        assert magic == b'glTF' and version == 2
        length, kind = struct.unpack('<I4s', source.read(8))
        assert kind == b'JSON'
        gltf = json.loads(source.read(length))
        length, kind = struct.unpack('<I4s', source.read(8))
        assert kind == b'BIN\0'
        return gltf, source.read(length)


def accessor(gltf, payload, index):
    description = gltf['accessors'][index]
    view = gltf['bufferViews'][description['bufferView']]
    dtype = {5123: '<u2', 5125: '<u4', 5126: '<f4'}[description['componentType']]
    width = {'SCALAR': 1, 'VEC3': 3}[description['type']]
    offset = view.get('byteOffset', 0) + description.get('byteOffset', 0)
    return np.frombuffer(payload, dtype, description['count'] * width, offset).reshape(-1, width)


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def clip(points, boundary):
    for left, right in zip(boundary, np.roll(boundary, -1, axis=0)):
        if len(points) < 3:
            break
        edge = right - left
        clipped = []
        previous = points[-1]
        distance = cross(edge, previous - left)
        for current in points:
            next_distance = cross(edge, current - left)
            if (next_distance >= 0) != (distance >= 0):
                clipped.append(previous + (current - previous) * distance / (distance - next_distance))
            if next_distance >= 0:
                clipped.append(current)
            previous, distance = current, next_distance
        points = clipped
    return points


def build_geometry(source):
    gltf, data = read_glb(source)
    vertices, triangles = [], []

    def polygon(points, z):
        if len(points) < 3:
            return
        # GLTF X/Z correspond to Unreal X/Y; clockwise in X/Z faces GLTF +Y.
        offset = len(vertices)
        area = sum(cross(a, b) for a, b in zip(points, np.roll(points, -1, axis=0)))
        if abs(area) < 1:
            return
        if area > 0:
            points = points[::-1]
        vertices.extend(((p[0]-ORIGIN_XY[0])/100, z/100, (p[1]-ORIGIN_XY[1])/100) for p in points)
        triangles.extend((offset, offset+i, offset+i+1) for i in range(1, len(points)-1))

    # Ground rays show the flat City ground at Z=10 cm. Keep the difference to
    # collision at 0.7 cm. Painted tile surface follows its exact flat geometry.
    polygon(OUTLINE, 10.7)
    tiers = {}
    for primitive in gltf['meshes'][0]['primitives']:
        position = accessor(gltf, data, primitive['attributes']['POSITION'])
        mip_low, mip_high = position[:, 1].min(), position[:, 1].max()
        if not np.isclose(mip_low, mip_high) or not np.isclose(mip_low, .28):
            continue
        indices = accessor(gltf, data, primitive['indices']).reshape(-1, 3)
        xy_world = position[:, [0, 2]].astype(np.float64) * 100 + OSM_TILE_ORIGIN
        samples = xy_world[indices]
        mesh_in_rect = np.all(samples.max(axis=1) >= MIN_XY, axis=1) & np.all(samples.min(axis=1) <= MAX_XY, axis=1)
        for triangle in samples[mesh_in_rect]:
            before = len(triangles)
            polygon(clip(triangle, OUTLINE), 28.7)
            if len(triangles) > before:
                tiers["OSM_28cm"] = tiers.get("OSM_28cm", 0) + len(triangles) - before
    if not tiers:
        raise RuntimeError('No high road tier overlapped the proposed opening')
    positions = np.asarray(vertices, dtype='<f4')
    xy = positions[:, [0, 2]] * 100 + ORIGIN_XY
    uv = ((xy - MIN_XY) / (MAX_XY - MIN_XY)).astype('<f4')
    return positions, np.asarray(triangles, dtype='<u4'), uv, tiers


def smooth_noise(rng, ny, nx, size):
    data = rng.random((ny, nx)).astype(np.float32)
    return np.asarray(Image.fromarray(data).resize(size, Image.Resampling.BICUBIC))


def build_textures():
    size = (2048, 2048)
    rng = np.random.default_rng(145008)
    width_m, length_m = (MAX_XY - MIN_XY) / 100
    x, y = np.meshgrid(np.linspace(0, width_m, size[0], dtype=np.float32),
                       np.linspace(0, length_m, size[1], dtype=np.float32))
    broad = smooth_noise(rng, 11, 13, size)
    grit = smooth_noise(rng, 191, 221, size)
    fine = rng.random(x.shape, dtype=np.float32)
    seam_center = 3.6 + .205*x + .18*np.sin(x*1.15)
    cross_seam = y - seam_center
    seam = np.exp(-((cross_seam / .105)**2))
    damp = np.exp(-((cross_seam / .46)**2))

    # A jittered, randomly spaced field of rounded stones with large stones in
    # the gutter's shoulders, and partially buried pebbles at the yard edges.
    step = .142
    rows, columns = int(math.ceil(length_m/step)) + 6, int(math.ceil(width_m/step)) + 6
    centres_x = rng.uniform(-.47, .47, (rows, columns)).astype(np.float32)
    centres_y = rng.uniform(-.46, .46, (rows, columns)).astype(np.float32)
    stone_scale = rng.uniform(.29, .59, (rows, columns)).astype(np.float32)
    stone_choice = rng.random((rows, columns), dtype=np.float32)
    hues = rng.random((rows, columns), dtype=np.float32)
    px, py = x/step+2, y/step+2
    ix, iy = px.astype(np.int32), py.astype(np.int32)
    nearest = np.full(x.shape, 9, dtype=np.float32)
    radius, priority, color = np.zeros_like(x), np.zeros_like(x), np.zeros_like(x)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            row, col = iy+dy, ix+dx
            dist = ((px - col - centres_x[row, col])**2
                    + (py - row - centres_y[row, col])**2 * .87)
            closer = dist < nearest
            np.copyto(nearest, dist, where=closer)
            np.copyto(radius, stone_scale[row, col], where=closer)
            np.copyto(priority, stone_choice[row, col], where=closer)
            np.copyto(color, hues[row, col], where=closer)
    rut = np.exp(-(((cross_seam+.83)/.30)**2)) + np.exp(-(((cross_seam-1.03)/.33)**2))
    bed = .89 - .22 * np.clip(abs(cross_seam)/3.7, 0, 1)
    bed += (broad-.5)*.42 - .52*seam - .37*np.clip(rut, 0, 1)
    shoulder = np.exp(-(((abs(cross_seam)-.24)/.115)**2))
    bed = np.maximum(bed, shoulder*.97)
    has_stone = priority < bed
    stone_edge = radius - np.sqrt(nearest) + (grit-.5)*.04
    face = np.clip(stone_edge / .095, 0, 1) * has_stone
    shape = np.clip(stone_edge/.24, 0, 1) * has_stone

    dirt_brightness = .81 + .31*broad + .22*grit + .12*fine -.24*damp -.16*seam
    stone_brightness = .71 + color*.44 + (grit-.5)*.18 + (fine-.5)*.17 - .12*damp
    # Deep joints darken organically along the base of the stones.
    dirt_brightness -= np.clip(stone_edge/.08+.59, 0, 1) * has_stone * .11
    dirt = np.dstack((87*dirt_brightness, 72*dirt_brightness, 54*dirt_brightness))
    slate = np.dstack(((118+13*color)*stone_brightness,
                       (114+4*color)*stone_brightness, (99+8*(1-color))*stone_brightness))
    albedo = np.clip(dirt*(1-face[:, :, None]) + slate*face[:, :, None], 0, 255).astype(np.uint8)

    height = shape*.018 + (grit-.5)*.0015 + (broad-.5)*.010 - .010*damp - .009*seam
    dy_map, dx_map = np.gradient(height, length_m/size[1], width_m/size[0])
    nx, ny = -dx_map*.67, -dy_map*.67
    length = np.sqrt(nx*nx + ny*ny + 1)
    normals = ((np.dstack((nx/length, ny/length, 1/length)) * .5 + .5)*255).astype(np.uint8)

    roughness = np.clip(.94 - .24*damp - .17*seam - .12*face + (grit-.5)*.10, 0, 1)
    mr = np.dstack((np.ones_like(roughness), roughness, np.zeros_like(roughness)))
    return {
        'T_GL1450_Ground_Color': albedo,
        'T_GL1450_Ground_Normal': normals,
        'T_GL1450_Ground_Roughness': (mr*255).astype(np.uint8),
    }


def write_glb(path, position, triangle, uv, textures):
    data = bytearray()
    views, accessors, images = [], [], []

    def buffer_view(payload, target=None):
        if len(data) % 4:
            data.extend(bytes(4 - len(data) % 4))
        view = {'buffer': 0, 'byteOffset': len(data), 'byteLength': len(payload)}
        if target is not None:
            view['target'] = target
        data.extend(payload)
        views.append(view)
        return len(views) - 1

    def add_array(values, data_type, component, target, bounds=False):
        index = buffer_view(values.tobytes(), target)
        descriptor = {'bufferView': index, 'componentType': component, 'count': len(values), 'type': data_type}
        if bounds:
            descriptor.update(min=values.min(axis=0).tolist(), max=values.max(axis=0).tolist())
        accessors.append(descriptor)
        return len(accessors)-1

    normals = np.tile(np.array((0., 1., 0.), dtype='<f4'), (len(position), 1))
    tangents = np.tile(np.array((1., 0., 0., -1.), dtype='<f4'), (len(position), 1))
    attributes = {
        'POSITION': add_array(position, 'VEC3', 5126, 34962, bounds=True),
        'NORMAL': add_array(normals, 'VEC3', 5126, 34962),
        'TANGENT': add_array(tangents, 'VEC4', 5126, 34962),
        'TEXCOORD_0': add_array(uv, 'VEC2', 5126, 34962),
    }
    indices = add_array(triangle.reshape(-1), 'SCALAR', 5125, 34963)
    for name, values in textures.items():
        raw = io.BytesIO()
        Image.fromarray(values).save(raw, format='PNG', compress_level=4)
        image_bytes = raw.getvalue()
        images.append({'bufferView': buffer_view(image_bytes), 'mimeType': 'image/png', 'name': name})
        (path.parent / f'{name}.png').write_bytes(image_bytes)
    doc = {
        'asset': {'version': '2.0', 'generator': 'Reflections medieval opening ground'},
        'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0, 'name': path.stem}],
        'meshes': [{'name': path.stem, 'primitives': [{'attributes': attributes, 'indices': indices, 'material': 0}]}],
        'materials': [{
            'name': 'M_GL1450_WornCobblesAndEarth',
            'pbrMetallicRoughness': {
                'baseColorTexture': {'index': 0},
                'metallicFactor': 0,
                'roughnessFactor': 1,
                'metallicRoughnessTexture': {'index': 2},
            },
            'normalTexture': {'index': 1},
        }],
        'textures': [{'source': i} for i in range(len(images))], 'images': images,
        'buffers': [{'byteLength': len(data)}], 'bufferViews': views, 'accessors': accessors,
    }
    header = json.dumps(doc, separators=(',', ':')).encode()
    header += b' ' * (-len(header) % 4)
    data.extend(bytes(-len(data) % 4))
    glb = struct.pack('<4sII', b'glTF', 2, 28+len(header)+len(data))
    glb += struct.pack('<I4s', len(header), b'JSON') + header
    glb += struct.pack('<I4s', len(data), b'BIN\0') + data
    path.write_bytes(glb)


if __name__ == '__main__':
    source = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    output.mkdir(exist_ok=True, parents=True)
    position, triangle, uv, tiers = build_geometry(source)
    assets = build_textures()
    write_glb(output/'SM_GL1450_OpeningGround.glb', position, triangle, uv, assets)
    report = {
        'base_actor_position_cm': [*ORIGIN_XY, 0],
        'world_outline_cm': OUTLINE.tolist(),
        'source_ground_levels_cm': [10.0, 28.0],
        'offset_cm': .7, 'geometry_triangles': len(triangle), 'triangles_by_upper_tier': tiers,
        'source_texture_dimensions': list(next(iter(assets.values())).shape[1::-1]),
        'actor_collision': 'NoCollision', 'complex_as_simple': False,
    }
    (output/'opening_ground_report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
