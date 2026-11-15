"""Build a 3 m timber Cellarer frontage for narrow Gray London plot walls."""

import json
from pathlib import Path
import random
import sys

import bmesh
import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from build_medieval_facades import Bay, PAL, backfill, crossbeam, leaded, plinth, shutter


HALF = 1.5
GROUND = 2.70
UPPER = 2.42
EAVES = GROUND + 4 * UPPER
RIDGE = 14.53
HEIGHT = 14.84
NAME = 'SM_GLMedieval_Narrow_Cellarer'
PLASTER = 'WarmPlaster'
OAK = 'WeatheredOak'


def shop(bay):
    door = (-1.27, -.16)
    hatch = (.16, 1.27)
    backfill(bay, -HALF, HALF, 0, GROUND, .025, 'Interior')
    for left, right in ((-HALF, door[0]), (door[1], hatch[0]), (hatch[1], HALF)):
        backfill(bay, left, right, .02, GROUND, .19, PLASTER)
    plinth(bay, hatch[0], hatch[1], random.Random(378))
    shutter(bay, door[0] + .046, door[1] - .045, .042, 2.08, .045, 'ShopRed')
    shutter(bay, hatch[0] + .035, hatch[1] - .032, .77, 1.52, .098, 'Oak')
    bay.band(hatch[0] - .066, hatch[1] + .065, .72, .806, .152, .423, OAK)
    bay.band(hatch[0], hatch[1], 1.53, 1.86, .163, .207, PLASTER)
    leaded(bay, hatch[0] + .082, hatch[1] - .072, 1.886, 2.275, .046, False)
    for left, right, head in ((*door, 2.24), (*hatch, 2.36)):
        for y in (left, right):
            bay.band(y - .075, y + .074, 0, head, .032, .287, OAK)
        bay.band(left - .066, right + .068, head - .09, head + .065, .025, .316, 'Oak')
        backfill(bay, left, right, head + .065, GROUND, .185, PLASTER)
    crossbeam(bay, .073, .137, (-.43, 1.08), (-.33, 1.08), .046, 'Lead')
    bay.band(door[0], door[1], 0, .060, -.011, .296, 'Fieldstone')
    bay.band(-HALF, HALF, 2.51, 2.70, .027, .48, 'Oak')
    for y in (-1.29, -.51, .44, 1.27):
        crossbeam(bay, .191, .453, (y, 2.25), (y + .062, 2.64), .116, OAK)


def upper_storey(bay, index):
    low = GROUND + index * UPPER
    high = low + UPPER
    depth = (.46, .58, .60, .615)[index]
    center = (.10, -.15, .32, -.28)[index]
    window_width = (1.64, 1.07, .97, 1.12)[index]
    left, right = center - window_width / 2, center + window_width / 2
    sill = low + (.61 if index == 0 else .81)
    head = high - .39
    backfill(bay, -HALF, HALF, low, high, depth - .157, 'Interior')
    backfill(bay, -HALF, HALF, low, sill - .019, depth, PLASTER)
    backfill(bay, -HALF, HALF, head + .034, high, depth, PLASTER)
    backfill(bay, -HALF, left, sill - .02, head + .036, depth, PLASTER)
    backfill(bay, right, HALF, sill - .02, head + .036, depth, PLASTER)
    glass_plane = depth - .055 if index == 0 else depth - .104
    leaded(bay, left, right, sill, head, glass_plane, False)
    if index == 0:
        # The larger display light sits in a shallow projecting oak oriel.
        bay.band(left - .108, right + .108, sill - .12, sill - .058, .430, .847, OAK)
        bay.band(left - .106, right + .106, head + .065, head + .13, .431, .791, OAK)
        for y in (left + .04, right - .04):
            crossbeam(bay, .514, .704, (y, sill - .45), (y + .103, sill - .095), .122, OAK)
    bay.band(-HALF, HALF, low, low + .135, depth - .055, depth + .111, 'Oak')
    bay.band(-HALF, HALF, high - .16, high, depth - .058, depth + .129, OAK)
    for y in (-1.407, 1.407):
        bay.band(y - .093, y + .093, low, high, depth - .04, depth + .118, 'Oak')
    for side in (-1, 1):
        joint = (side * (1.15 - .055 * index), low + .16)
        brace = (side * .39 + center * .31, sill - .049)
        crossbeam(bay, depth - .068, depth + .115, joint, brace, .126, OAK)
    if index >= 1:
        wide_side = 1 if center < 0 else -1
        y = wide_side * 1.1
        crossbeam(bay, depth - .05, depth + .104, (y, sill - .01),
                  (wide_side * 1.39, head + .047), .104, 'Oak')


def gable(bay):
    center = -.15
    # The shadowed crown backing covers the old flat wall above the silhouette.
    bay.band(-HALF, HALF, EAVES, HEIGHT, -.061, .032, 'ClayTile')
    bay.prism(((-HALF, EAVES), (HALF, EAVES), (center, RIDGE)), -.065, .65, PLASTER)
    window_l, window_r = -.58, .22
    leaded(bay, window_l, window_r, EAVES + .31, EAVES + 1.11, .647, False)
    for endpoint in (-HALF, HALF):
        start, end = (endpoint, EAVES), (center, RIDGE)
        crossbeam(bay, .57, .806, start, end, .143, OAK)
        crossbeam(bay, -.065, .879, (endpoint, EAVES + .084), (center, RIDGE + .092), .104, 'ClayTile')
        for index in range(1, 9):
            t = index / 9
            y = endpoint + (center - endpoint) * t
            z = EAVES + (RIDGE - EAVES) * t + .106
            crossbeam(bay, .75, .906, (y - .049, z - .025), (y + .049, z + .025), .060, 'ClayTile')
    for y in (-.92, .76):
        crossbeam(bay, .61, .776, (y, EAVES + .04),
                  (.67 * y + .33 * center, EAVES + .84), .099, 'Oak')
    bay.band(center - .061, center + .061, RIDGE - .036, HEIGHT - .06, .65, .822, OAK)


def material(role):
    mat = bpy.data.materials.new('M_GLMedieval_' + role)
    rgb, roughness, tile_size = PAL[role]
    mat.diffuse_color = (*rgb, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*rgb, 1)
    shader.inputs['Roughness'].default_value = roughness
    if tile_size is not None:
        image = mat.node_tree.nodes.new('ShaderNodeTexImage')
        image.image = bpy.data.images.load(str(ROOT.parent / 'Textures' / f'T_GLMedieval_{role}.png'))
        mat.node_tree.links.new(image.outputs['Color'], shader.inputs['Base Color'])
    return mat


def make_mesh(bay):
    mesh = bpy.data.meshes.new(NAME)
    mesh.from_pydata([(x, max(-HALF, min(HALF, y)), z) for x, y, z in bay.vertices], [], bay.polygons)
    mesh.update()
    roles = list(dict.fromkeys(bay.roles))
    indices = {role: index for index, role in enumerate(roles)}
    for role in roles:
        mesh.materials.append(material(role))
    for polygon, role in zip(mesh.polygons, bay.roles):
        polygon.material_index = indices[role]
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    uv = mesh.uv_layers.new(name='UV0')
    for face in mesh.polygons:
        tile_size = PAL[roles[face.material_index]][2] or 1
        axis = max(range(3), key=lambda i: abs(face.normal[i]))
        a, b = ((1, 2), (0, 2), (1, 0))[axis]
        for i in face.loop_indices:
            local = mesh.vertices[mesh.loops[i].vertex_index].co
            uv.data[i].uv = (local[a] / tile_size, local[b] / tile_size)
    mesh.calc_loop_triangles()
    obj = bpy.data.objects.new(NAME, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def preview(output):
    for location, power, size in (((9, -6, 12), 3100, 11), ((7, 6, 9), 1400, 12)):
        bpy.ops.object.light_add(type='AREA', location=location)
        lamp = bpy.context.object
        lamp.data.energy = power
        lamp.data.size = size
        lamp.rotation_euler = (Vector((0, 0, 6.7)) - lamp.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.ops.object.camera_add(location=(20, -4, 10.4))
    camera = bpy.context.object
    camera.rotation_euler = (Vector((0, 0, 7.4)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 16.0
    scene = bpy.context.scene
    scene.camera = camera
    scene.world = bpy.data.worlds.new('Overcast workshop')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .52
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 12
    scene.cycles.use_denoising = True
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 4
    scene.render.resolution_x = 720
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(output.resolve())
    bpy.ops.render.render(write_still=True)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = 'METRIC'
    bay = Bay()
    shop(bay)
    for index in range(4):
        upper_storey(bay, index)
    gable(bay)
    obj = make_mesh(bay)
    path = ROOT / 'Source' / f'{NAME}.fbx'
    path.parent.mkdir(parents=True, exist_ok=True)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, object_types={'MESH'},
                             axis_forward='-Z', axis_up='Y', mesh_smooth_type='FACE',
                             bake_anim=False, path_mode='COPY', embed_textures=True)
    entry = {'fbx': f'Source/{NAME}.fbx',
             'min_cm': [round(min(v[i] for v in obj.bound_box) * 100, 3) for i in range(3)],
             'max_cm': [round(max(v[i] for v in obj.bound_box) * 100, 3) for i in range(3)],
             'materials': [mat.name for mat in obj.data.materials],
             'triangles': len(obj.data.loop_triangles)}
    manifest = {'schema': 1, 'width_cm': 300, 'height_cm': 1484,
                'pivot': 'bottom-center wall seam, +X street face, +Z up', 'meshes': {NAME: entry}}
    (ROOT / 'narrow_kit.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    if '--' in sys.argv:
        preview(Path(sys.argv[sys.argv.index('--') + 1]))


if __name__ == '__main__':
    main()
