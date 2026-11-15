"""Rebuild the hero's simulated travel coat as a clean, smooth Chaos Cloth panel.

Run headless from the project root:
    blender -b ArtDirection/Three-Londons-Wardrobe/Hero/TravelCloak/Hero_TravelCloak_Mantle.blend \
        --python ArtDirection/Three-Londons-Wardrobe/Hero/TravelCloak/fit_heavy_coat.py

Why this replaces the mantle drape from fit_travel_cloak.py:
- The old panel added per-vertex radial "variation" sampled from the image-to-3D
  reconstruction, and measured body clearance with rays cast from outside inward
  that switched between arm and torso hits at a hard |x| < 0.215 cutoff. The rest
  mesh therefore had zig-zag pleats along the side edges and a stepped notch at
  the shoulder (radial second difference up to 17 cm between neighbours). Chaos
  keeps rest lengths and bends, so the simulated cloak kept those broken vertices.
- Every vertex down to the ankle hem was skinned 100% to spine_05, so the
  animated target of the hem swung rigidly with the upper chest.

This version samples a smooth flared surface, enforces body clearance by pushing
along the nearest torso surface normal (arms are ignored below the shoulder top),
smooths only the displacement from that surface (which does not shrink the panel),
and blends skin weights from the collar (spine_05/clavicles) down through the
spine to the pelvis, with a small thigh influence at the hem.
It writes Intermediate/TravelCloak/SK_HeroTravel_Drape_Coat.fbx and saves
Hero_TravelCloak_Coat.blend next to this script. The source .blend is not modified.
"""

import json
import math
import os
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree


ART = Path(__file__).resolve().parent
STAGING = ART.parents[3] / 'Intermediate/TravelCloak'
STAGING.mkdir(parents=True, exist_ok=True)
NAME = os.environ.get('COAT_NAME', 'SK_HeroTravel_Drape_Coat')

BODY = bpy.data.objects['Native MetaHuman fitting body']
RIG = next(mod.object for mod in BODY.modifiers if mod.type == 'ARMATURE')
SHIRT = bpy.data.objects.get('SK_HeroTravel_Shirt')

# 64 x 50 (3,315 vertices) was the first build; COAT_ACROSS/COAT_ROWS give a lighter sim mesh.
ACROSS = int(os.environ.get('COAT_ACROSS', 64))
ROWS = int(os.environ.get('COAT_ROWS', 50))
TOP_Z, HEM_Z = 1.545, 0.135    # collar to just above the ankle
ORIGIN_Y = -0.014              # body axis used by the original fit
START_TOP, START_HEM = 1.15, 1.92  # half-opening (rad from the front) at collar and below the mantle


def smoothstep(edge0, edge1, x):
    t = min(1.0, max(0.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- clearance surfaces
def torso_tree():
    """BVH of body (and shirt) faces that belong to the torso and legs.

    Arm-weighted faces (weight > 0.3) are excluded below the shoulder top (z < 1.40) so the coat's side edges are not
    pushed out by hands and forearms (the arms collide with the cloth in Chaos).
    """
    depsgraph = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for obj in (BODY, SHIRT):
        if obj is None:
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        groups = {group.index: group.name for group in obj.vertex_groups}
        arm_prefixes = ('upperarm', 'lowerarm', 'hand', 'thumb', 'index', 'middle', 'ring', 'pinky')
        arm_weight = []
        for vertex in mesh.vertices:
            arm_weight.append(sum(entry.weight for entry in vertex.groups
                                  if groups.get(entry.group, '').startswith(arm_prefixes)))
        base = len(verts)
        verts.extend(obj.matrix_world @ vertex.co for vertex in mesh.vertices)
        for poly in mesh.polygons:
            centre_z = (obj.matrix_world @ poly.center).z
            arm = sum(arm_weight[index] for index in poly.vertices) / len(poly.vertices)
            if arm > 0.3 and centre_z < 1.40:
                continue
            polys.append(tuple(base + index for index in poly.vertices))
        evaluated.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys, all_triangles=False)


TREE = torso_tree()


# ---------------------------------------------------------------- parameterisation
def row_z(depth, side):
    top = TOP_Z + 0.012 * (1 - side)
    return top + (HEM_Z - top) * depth


def row_start(depth):
    # The mantle wraps over the shoulders to the chest, then the body panel opens
    # to hang behind the arms. Spread the change over many rows so quads stay even.
    return START_TOP + (START_HEM - START_TOP) * smoothstep(0.03, 0.24, depth)


def fitted_radius(depth, direction):
    taper = depth ** 1.35
    collar = smoothstep(0.0, 0.10, depth)
    rx = 0.10 + 0.13 * collar + 0.22 * taper
    ry_back = 0.095 + 0.085 * collar + 0.17 * taper
    ry_front = 0.09 + 0.10 * collar + 0.12 * taper
    ry = ry_back if direction.y > 0 else ry_front
    return 1 / math.hypot(direction.x / rx, direction.y / ry)


def clearance(depth):
    # Collar sits close; the long panel keeps a hand's width from the legs.
    return 0.020 + 0.030 * smoothstep(0.05, 0.55, depth)


grid = []  # (depth, side, angle, direction, z)
for i in range(ROWS + 1):
    depth = i / ROWS
    start = row_start(depth)
    row = []
    for j in range(ACROSS + 1):
        s = j / ACROSS
        angle = start + (math.tau - 2 * start) * s
        direction = Vector((math.sin(angle), -math.cos(angle), 0.0))
        side = abs(direction.x)
        row.append((depth, side, angle, direction, row_z(depth, side)))
    grid.append(row)

BASE = [[Vector((0.0, ORIGIN_Y, cell[4])) + cell[3] * fitted_radius(cell[0], cell[3]) for cell in row]
        for row in grid]
# Displacement from the smooth fitted surface. Pushes act along the body's surface
# normal (so the collar rises over the trapezius instead of flaring sideways), and
# smoothing acts on the displacement field, which does not shrink the panel.
offset = [[Vector((0.0, 0.0, 0.0)) for _ in row] for row in grid]


def point(i, j):
    return BASE[i][j] + offset[i][j]


def push_out():
    moved = 0
    for i, row in enumerate(grid):
        for j, cell in enumerate(row):
            p = point(i, j)
            hit, normal, _, _ = TREE.find_nearest(p, 0.6)
            if hit is None:
                continue
            gap = (p - hit).dot(normal)
            need = clearance(cell[0])
            if gap < need:
                offset[i][j] += normal * (need - gap)
                moved += 1
    return moved


def smooth(passes):
    global offset
    for _ in range(passes):
        nxt = [[v.copy() for v in row] for row in offset]
        for i in range(ROWS + 1):
            for j in range(ACROSS + 1):
                acc, wsum = Vector((0.0, 0.0, 0.0)), 0.0
                for di in (-1, 0, 1):
                    for dj in (-1, 0, 1):
                        ii, jj = i + di, j + dj
                        if 0 <= ii <= ROWS and 0 <= jj <= ACROSS:
                            w = 2.0 if (di == 0 and dj == 0) else 1.0
                            acc += offset[ii][jj] * w
                            wsum += w
                nxt[i][j] = acc / wsum
        offset = nxt


history = []
for iteration in range(16):
    history.append(push_out())
    smooth(2)
history.append(push_out())
smooth(1)
history.append(push_out())

# ---------------------------------------------------------------- mesh
vertices, faces = [], []
for i in range(ROWS + 1):
    for j in range(ACROSS + 1):
        vertices.append(point(i, j))
for i in range(ROWS):
    for j in range(ACROSS):
        a = i * (ACROSS + 1) + j
        faces.append((a, a + ACROSS + 1, a + ACROSS + 2, a + 1))

old = bpy.data.objects.get(NAME)
if old:
    bpy.data.objects.remove(old, do_unlink=True)
previous = bpy.data.objects.get('SK_HeroTravel_Drape')
if previous:
    previous.name = 'Previous mantle drape (reference only)'
    previous.hide_render = True
    previous.hide_set(True)

mesh = bpy.data.meshes.new(NAME)
mesh.from_pydata(vertices, [], faces)
mesh.update()
# Outward normals so the exterior material faces out (two-sided lining on the back).
outward = sum(1 for poly in mesh.polygons
              if poly.normal.dot(Vector((poly.center.x, poly.center.y - ORIGIN_Y, 0.0))) > 0)
if outward < len(mesh.polygons) / 2:
    for poly in mesh.polygons:
        poly.flip()
    mesh.update()
for poly in mesh.polygons:
    poly.use_smooth = True
coat = bpy.data.objects.new(NAME, mesh)
bpy.context.scene.collection.objects.link(coat)
material = bpy.data.materials.get('Charcoal cloak drape') or bpy.data.materials.new('Charcoal cloak drape')
mesh.materials.append(material)
uv = mesh.uv_layers.new(name='CloakUV')
for loop in mesh.loops:
    row, column = divmod(loop.vertex_index, ACROSS + 1)
    uv.data[loop.index].uv = (column / ACROSS, row / ROWS)

# ---------------------------------------------------------------- skin weights
BONES = ('neck_01', 'spine_05', 'spine_04', 'spine_03', 'spine_02', 'spine_01', 'pelvis',
         'clavicle_l', 'clavicle_r', 'thigh_l', 'thigh_r')
assert all(name in RIG.data.bones for name in BONES), [n for n in BONES if n not in RIG.data.bones]
groups = {name: coat.vertex_groups.new(name=name) for name in BONES}
# Spine chain keyed by height; linear blend between neighbouring keys.
SPINE_KEYS = [(1.40, 'spine_05'), (1.27, 'spine_04'), (1.14, 'spine_03'), (1.03, 'spine_02'),
              (0.96, 'spine_01'), (0.90, 'pelvis')]


def spine_weights(z):
    if z >= SPINE_KEYS[0][0]:
        return {SPINE_KEYS[0][1]: 1.0}
    for (z0, b0), (z1, b1) in zip(SPINE_KEYS, SPINE_KEYS[1:]):
        if z1 <= z <= z0:
            t = (z0 - z) / (z0 - z1)
            return {b0: 1 - t, b1: t}
    return {'pelvis': 1.0}


weight_rows = []
for index, vertex in enumerate(vertices):
    i, j = divmod(index, ACROSS + 1)
    depth, side, angle, direction, z = grid[i][j]
    weights = spine_weights(vertex.z)
    clav = 0.75 * side ** 1.7 * max(0.0, 1 - depth / 0.26)
    if clav > 0:
        weights = {bone: w * (1 - clav) for bone, w in weights.items()}
        clav_bone = 'clavicle_l' if vertex.x > 0 else 'clavicle_r'
        weights[clav_bone] = weights.get(clav_bone, 0) + clav
    thigh = 0.25 * smoothstep(0.88, 0.30, vertex.z)
    if thigh > 0:
        left = 0.5 + 0.5 * max(-1.0, min(1.0, vertex.x / 0.10))
        weights = {bone: w * (1 - thigh) for bone, w in weights.items()}
        weights['thigh_l'] = weights.get('thigh_l', 0) + thigh * left
        weights['thigh_r'] = weights.get('thigh_r', 0) + thigh * (1 - left)
    total = sum(weights.values())
    for bone, w in weights.items():
        if w / total > 1e-4:
            groups[bone].add([index], w / total, 'REPLACE')
    weight_rows.append(weights)

coat.parent = RIG
coat.matrix_parent_inverse = RIG.matrix_world.inverted()
coat.matrix_world = Matrix.Identity(4)
coat.modifiers.new('MetaHuman body pose', 'ARMATURE').object = RIG

# ---------------------------------------------------------------- measurements
P = [coat.matrix_world @ v.co for v in mesh.vertices]


def rad(p):
    return math.hypot(p.x, p.y - ORIGIN_Y)


A = ACROSS + 1
d2c = sorted(abs(rad(P[i*A+j-1]) - 2*rad(P[i*A+j]) + rad(P[i*A+j+1])) for i in range(ROWS + 1) for j in range(1, ACROSS))
d2r = sorted(abs(rad(P[(i-1)*A+j]) - 2*rad(P[i*A+j]) + rad(P[(i+1)*A+j])) for i in range(1, ROWS) for j in range(A))
edges = sorted((mesh.vertices[e.vertices[0]].co - mesh.vertices[e.vertices[1]].co).length for e in mesh.edges)
gaps = []
for p in P:
    hit, normal, _, _ = TREE.find_nearest(p, 0.6)
    if hit is not None:
        gaps.append((p - hit).dot(normal))
gaps.sort()
report = {
    'vertices': len(mesh.vertices), 'faces': len(mesh.polygons),
    'z_range_m': [round(min(p.z for p in P), 4), round(max(p.z for p in P), 4)],
    'x_range_m': [round(min(p.x for p in P), 4), round(max(p.x for p in P), 4)],
    'y_range_m': [round(min(p.y for p in P), 4), round(max(p.y for p in P), 4)],
    'radial_second_difference_cm': {
        'across_p95': round(d2c[int(len(d2c) * .95)] * 100, 3), 'across_max': round(d2c[-1] * 100, 3),
        'down_p95': round(d2r[int(len(d2r) * .95)] * 100, 3), 'down_max': round(d2r[-1] * 100, 3)},
    'edge_length_cm': {'min': round(edges[0] * 100, 2), 'median': round(edges[len(edges)//2] * 100, 2),
                       'max': round(edges[-1] * 100, 2)},
    'torso_clearance_cm': {'min': round(gaps[0] * 100, 2), 'p05': round(gaps[int(len(gaps) * .05)] * 100, 2)},
    'push_history': history,
    'bones': list(BONES),
}

# ---------------------------------------------------------------- export (same settings as the earlier travel garments)
bpy.ops.object.select_all(action='DESELECT')
coat.select_set(True)
RIG.select_set(True)
bpy.context.view_layer.objects.active = coat
bpy.ops.export_scene.fbx(filepath=str(STAGING / (NAME + '.fbx')), use_selection=True,
                         object_types={'MESH', 'ARMATURE'}, axis_forward='-Z', axis_up='Y',
                         apply_unit_scale=True, add_leaf_bones=False, bake_anim=False, mesh_smooth_type='FACE')
(STAGING / (NAME + '_report.json')).write_text(json.dumps(report, indent=2))
(ART / (NAME + '_report.json')).write_text(json.dumps(report, indent=2))
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ART / os.environ.get('COAT_BLEND', 'Hero_TravelCloak_Coat.blend')))
print('COAT_REPORT=' + json.dumps(report))
