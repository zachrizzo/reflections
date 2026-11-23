"""Blender side of garment fit preparation: read the garment mesh, write the prepared one.

Run with Blender's Python:
  blender -b --python blender_io.py -- dump  <in.blend|in.obj|in.fbx> <object or ''> <out.npz> [triangle budget]
  blender -b --python blender_io.py -- build <folder with P.npy F.npy UV.npy> <out.fbx> <out.blend> [object name]

`dump` writes welded positions P, triangles F and per-corner UVs in the convention of the
Unreal captures: actor-local centimetres = Blender world metres * (100, -100, 100), with the
triangle winding flipped. `build` makes a mesh from such arrays and exports it for Unreal.
"""
import sys
from pathlib import Path

import bpy
import numpy as np

TO_CAPTURE = np.array([100., -100., 100.])


def garment_object(name=""):
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if name:
        return next(o for o in meshes if o.name == name)
    return max(meshes, key=lambda o: len(o.data.polygons))


def load(path, name=""):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(path))
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if suffix == ".obj":
            bpy.ops.wm.obj_import(filepath=str(path), forward_axis="NEGATIVE_Z", up_axis="Y")
        elif suffix == ".ply":                       # generator space is Y up, facing +Z, like the OBJ
            bpy.ops.wm.ply_import(filepath=str(path))
            for obj in bpy.context.selected_objects:
                obj.rotation_euler.x = 1.5707963267948966
            bpy.context.view_layer.update()
        else:
            bpy.ops.import_scene.fbx(filepath=str(path), use_custom_normals=False, use_image_search=False)
    return garment_object(name)


def arrays(obj):
    mesh = obj.data
    mesh.calc_loop_triangles()
    co = np.empty(len(mesh.vertices) * 3)
    mesh.vertices.foreach_get("co", co)
    world = np.array(obj.matrix_world)
    P = (co.reshape(-1, 3) @ world[:3, :3].T + world[:3, 3]) * TO_CAPTURE
    tri = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int64)
    mesh.loop_triangles.foreach_get("vertices", tri)
    loops = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int64)
    mesh.loop_triangles.foreach_get("loops", loops)
    uv = np.zeros(len(mesh.loops) * 2)
    if mesh.uv_layers.active:                        # an untextured mesh has none
        mesh.uv_layers.active.data.foreach_get("uv", uv)
    F = tri.reshape(-1, 3)[:, [0, 2, 1]]
    UV = uv.reshape(-1, 2)[loops.reshape(-1, 3)[:, [0, 2, 1]]]
    return P, F, UV


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    mode = args[0]
    if mode == "dump":
        src, name, out_npz = args[1:4]
        triangles = int(args[4]) if len(args) > 4 else 0
        obj = load(src, name)
        obj.hide_set(False)
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        obj.data.calc_loop_triangles()
        source_triangles = len(obj.data.loop_triangles)
        if triangles and source_triangles > triangles:
            decimate = obj.modifiers.new("Game mesh", "DECIMATE")
            decimate.ratio = triangles / source_triangles
            bpy.ops.object.modifier_apply(modifier=decimate.name)
        P, F, UV = arrays(obj)
        material = obj.data.materials[0].name if obj.data.materials else ""
        np.savez(out_npz, P=P, F=F, UV=UV, name=obj.name, material=material, source_triangles=source_triangles)
        print(f"DUMP {obj.name}: {source_triangles} -> {len(F)} triangles, {len(P)} vertices")
    elif mode == "build":
        src, out_fbx, out_blend = args[1:4]
        name = args[4] if len(args) > 4 else "Garment_Fit"
        # plain .npy files: Blender's Python cannot open .npz archives
        P, F, UV = (np.load(str(Path(src) / f"{key}.npy")) for key in ("P", "F", "UV"))
        bpy.ops.wm.read_factory_settings(use_empty=True)
        mesh = bpy.data.meshes.new(name)
        faces = F[:, [0, 2, 1]]
        mesh.vertices.add(len(P))
        mesh.vertices.foreach_set("co", (P / TO_CAPTURE).astype(np.float32).ravel())
        mesh.loops.add(faces.size)
        mesh.loops.foreach_set("vertex_index", faces.ravel().astype(np.int32))
        mesh.polygons.add(len(faces))
        mesh.polygons.foreach_set("loop_start", np.arange(0, faces.size, 3, dtype=np.int32))
        mesh.polygons.foreach_set("loop_total", np.full(len(faces), 3, dtype=np.int32))
        mesh.polygons.foreach_set("use_smooth", np.ones(len(faces), dtype=bool))
        layer = mesh.uv_layers.new(name="UVMap")
        layer.data.foreach_set("uv", UV[:, [0, 2, 1]].reshape(-1).astype(np.float32))
        mesh.update(calc_edges=True)
        mesh.validate()
        mesh.materials.append(bpy.data.materials.new("material_0"))
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.wm.save_as_mainfile(filepath=out_blend)
        bpy.ops.export_scene.fbx(filepath=out_fbx, use_selection=True, object_types={"MESH"}, axis_forward="-Y",
                                 axis_up="Z", apply_unit_scale=True, mesh_smooth_type="FACE", add_leaf_bones=False)
        print(f"BUILD {out_fbx}: {len(faces)} triangles, {len(P)} vertices")


if __name__ == "__main__":
    main()
