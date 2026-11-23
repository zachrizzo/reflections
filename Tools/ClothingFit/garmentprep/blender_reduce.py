"""Blender: reduce a dense generated mesh to a triangle budget and write it as PLY for the texture step.

  blender -b --python blender_reduce.py -- <in.ply|in.glb> <out.ply> [triangles=125000]
"""
import sys
from pathlib import Path

import bpy

src, dst = Path(sys.argv[sys.argv.index("--") + 1]), Path(sys.argv[sys.argv.index("--") + 2])
budget = int(sys.argv[sys.argv.index("--") + 3]) if len(sys.argv) > sys.argv.index("--") + 3 else 125000
bpy.ops.wm.read_factory_settings(use_empty=True)
if src.suffix.lower() == ".ply":
    bpy.ops.wm.ply_import(filepath=str(src))
else:
    bpy.ops.import_scene.gltf(filepath=str(src))
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
assert meshes, "no mesh in " + str(src)
bpy.ops.object.select_all(action="DESELECT")
for mesh in meshes:
    mesh.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()
obj = bpy.context.object
faces = len(obj.data.polygons)
if faces > budget:
    reduce = obj.modifiers.new("Texture-step mesh", "DECIMATE")
    reduce.ratio = budget / faces
    bpy.ops.object.modifier_apply(modifier=reduce.name)
bpy.ops.wm.ply_export(filepath=str(dst), export_selected_objects=True, export_normals=False, export_uv=False)
print(f"REDUCED {faces} -> {len(obj.data.polygons)} triangles: {dst}")
