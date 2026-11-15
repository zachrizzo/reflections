"""Headless Blender: builds the villain's robe (SM_Villain_Shroud) and hood (SM_Villain_Hood) and exports one FBX each.

    blender.exe -b --factory-startup --python Tools/Villain/make_villain_cloth.py -- <out_dir>

Both meshes are modelled for the UE5 mannequin at scale 1 (about 180 cm tall), pivot at the feet, front = +X
(Blender +X exports to UE +X with these settings). UV v runs 0 at the top to 1 at the hem: the shroud material
tatters the hem by v and sways the cloth more toward v = 1, so the UVs carry the cloth behaviour.
"""
import math
import os
import sys

import bmesh
import bpy

OUT = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else os.path.join(os.getcwd(), 'VillainMeshes')
os.makedirs(OUT, exist_ok=True)
CM = 0.01

# (z, depth radius, width radius) in cm, collar to hem.
ROBE = [(157, 9, 11), (151, 15, 23), (143, 19, 30), (131, 22, 33), (112, 25, 36), (90, 30, 40), (60, 37, 46),
        (30, 45, 52), (-2, 55, 59)]


def lerp(a, b, t):
    return a + (b - a) * t


def profile(z):
    for (z0, x0, y0), (z1, x1, y1) in zip(ROBE, ROBE[1:]):
        if z1 <= z <= z0:
            t = (z0 - z) / (z0 - z1)
            t = t * t * (3 - 2 * t) * 0.35 + t * 0.65
            return lerp(x0, x1, t), lerp(y0, y1, t)
    return ROBE[-1][1], ROBE[-1][2]


def new_object(name, bm):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    for poly in mesh.polygons:
        poly.use_smooth = True
    return obj


def grid(bm, rows, cols, point, keep=lambda r, c: True):
    """rows x (cols + 1) vertices (seam duplicated for clean UVs); quads where keep(r, c)."""
    uv = bm.loops.layers.uv.new('UVMap')
    verts = [[bm.verts.new(point(r, c)) for c in range(cols + 1)] for r in range(rows)]
    for r in range(rows - 1):
        for c in range(cols):
            if not keep(r, c):
                continue
            quad = [verts[r][c], verts[r + 1][c], verts[r + 1][c + 1], verts[r][c + 1]]
            face = bm.faces.new(quad)
            for loop, (rr, cc) in zip(face.loops, [(r, c), (r + 1, c), (r + 1, c + 1), (r, c + 1)]):
                loop[uv].uv = (cc / cols, rr / (rows - 1))
    bmesh.ops.remove_doubles(bm, verts=[v for v in bm.verts if not v.link_faces], dist=0.0)
    for v in [v for v in bm.verts if not v.link_faces]:
        bm.verts.remove(v)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)


def robe():
    rows, cols = 34, 56
    top, bottom = ROBE[0][0], ROBE[-1][0]

    def point(r, c):
        v = r / (rows - 1)
        z = lerp(top, bottom, v)
        theta = (c / cols) * 2 * math.pi - math.pi  # 0 = front (+X), seam at the back
        rx, ry = profile(z)
        hem = (top - z) / (top - bottom)
        fold = 1 + hem * (0.075 * math.sin(9 * theta + 0.7) + 0.035 * math.sin(23 * theta + 2.1))
        x = math.cos(theta) * rx * fold - 7 * hem * hem  # the cloth trails behind him
        y = math.sin(theta) * ry * fold
        return (x * CM, y * CM, z * CM)

    bm = bmesh.new()
    grid(bm, rows, cols, point)
    return new_object('SM_Villain_Shroud', bm)


def hood():
    rows, cols = 26, 44
    cx, cz = -1.5, 168.0

    def point(r, c):
        phi = (r / (rows - 1)) * math.radians(160)  # 0 = crown, 160 deg = lower rim on the shoulders
        theta = (c / cols) * 2 * math.pi - math.pi
        rx, ry, rz = 14.5, 13.0, 16.0
        flare = max(0.0, (phi - math.radians(105)) / math.radians(55))
        spread = 1 + 1.1 * flare * flare
        back = max(0.0, -math.cos(theta))
        peak = 9.0 * back * max(0.0, math.cos(phi)) ** 2  # pointed back of the hood
        ring = math.sin(phi) if phi <= math.pi / 2 else 1.0  # below the jaw it drapes down instead of closing
        x = cx + ring * math.cos(theta) * rx * spread - 4.0 * back * flare
        y = ring * math.sin(theta) * ry * spread
        z = cz + math.cos(phi) * rz + peak - 10.0 * flare
        return (x * CM, y * CM, z * CM)

    def keep(r, c):
        phi = ((r + 0.5) / (rows - 1)) * math.radians(160)
        theta = ((c + 0.5) / cols) * 2 * math.pi - math.pi
        # Face opening: the front, from the brow to below the chin.
        return not (math.cos(theta) > 0.38 and math.radians(38) < phi < math.radians(132))

    bm = bmesh.new()
    grid(bm, rows, cols, point, keep)
    return new_object('SM_Villain_Hood', bm)


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 1.0
report = {}
for obj in (robe(), hood()):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = os.path.join(OUT, obj.name + '.fbx')
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={'MESH'}, bake_anim=False,
                             add_leaf_bones=False, apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE',
                             bake_space_transform=False, mesh_smooth_type='FACE', axis_forward='-Z', axis_up='Y')
    xs = [v.co.x for v in obj.data.vertices]
    zs = [v.co.z for v in obj.data.vertices]
    report[obj.name] = {'verts': len(obj.data.vertices), 'faces': len(obj.data.polygons), 'dims_cm': [round(d * 100, 1) for d in obj.dimensions],
                        'x_range_cm': [round(min(xs) * 100, 1), round(max(xs) * 100, 1)], 'z_range_cm': [round(min(zs) * 100, 1), round(max(zs) * 100, 1)],
                        'fbx': path}
print('VILLAIN_CLOTH_REPORT', report)
