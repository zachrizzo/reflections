"""Headless Blender: a jagged mirror shard (SM_Villain_Shard) for the Tarnish's orbiting halo.

    blender.exe -b --factory-startup --python Tools/Villain/make_villain_shard.py -- <out_dir>

A thin, irregular triangular sliver, about 34 cm long and 13 cm wide, pivot at its centre, long axis +Z.
Instanced many times with random scale and spin, so one shape is enough.
"""
import os
import sys

import bmesh
import bpy

OUT = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else os.getcwd()
os.makedirs(OUT, exist_ok=True)
CM = 0.01

# Outline in the XZ plane (cm), roughly a broken-glass sliver; extruded 0.8 cm in Y.
OUTLINE = [(-5.5, -17.0), (1.0, -15.5), (6.5, -6.0), (4.0, 2.0), (6.0, 9.0), (1.5, 17.0), (-2.0, 8.5), (-6.5, 1.0), (-4.0, -7.0)]
HALF = 0.4

bpy.ops.wm.read_factory_settings(use_empty=True)
bm = bmesh.new()
uv = bm.loops.layers.uv.new('UVMap')
front = [bm.verts.new((x * CM, -HALF * CM, z * CM)) for x, z in OUTLINE]
back = [bm.verts.new((x * CM, HALF * CM, z * CM)) for x, z in OUTLINE]
faces = [bm.faces.new(front), bm.faces.new(list(reversed(back)))]
n = len(OUTLINE)
for i in range(n):
    j = (i + 1) % n
    faces.append(bm.faces.new([front[i], front[j], back[j], back[i]]))
for face in faces:
    for loop in face.loops:
        x, _, z = loop.vert.co
        loop[uv].uv = (x / (14 * CM) + 0.5, z / (36 * CM) + 0.5)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bmesh.ops.triangulate(bm, faces=bm.faces)
mesh = bpy.data.meshes.new('SM_Villain_Shard')
bm.to_mesh(mesh)
bm.free()
obj = bpy.data.objects.new('SM_Villain_Shard', mesh)
bpy.context.scene.collection.objects.link(obj)
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
path = os.path.join(OUT, 'SM_Villain_Shard.fbx')
bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={'MESH'}, bake_anim=False, add_leaf_bones=False,
                         apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE', bake_space_transform=False,
                         mesh_smooth_type='FACE', axis_forward='-Z', axis_up='Y')
print('VILLAIN_SHARD', path, [round(d * 100, 1) for d in obj.dimensions])
