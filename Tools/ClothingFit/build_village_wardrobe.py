"""Build matching sleeveless jerkins and trousers from MetaHuman fitting bodies.

Run with Blender --background --python build_village_wardrobe.py -- SOURCE OUTPUT.
SOURCE contains the full-body FBXs in their MetaHuman A-pose.
"""

import json
import sys
from collections import Counter
from math import atan2, pi
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree


MATERIALS = {
    "RussetLeather": (0.18, 0.054, 0.022, 1.0),
    "DarkLeather": (0.051, 0.022, 0.012, 1.0),
    "OldBrass": (0.40, 0.253, 0.089, 1.0),
    "CharcoalWool": (0.049, 0.057, 0.062, 1.0),
    "WoolBinding": (0.095, 0.074, 0.058, 1.0),
}


def clip(polygon, boundary):
    result = []
    for (p, n), (q, m) in zip(polygon, polygon[1:] + polygon[:1]):
        a, b = boundary(p), boundary(q)
        if a >= 0:
            result.append((p, n))
        if (a >= 0) != (b >= 0):
            t = a / (a - b)
            result.append((p.lerp(q, t), n.lerp(m, t)))
    return result


def smoothstep(value):
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def front_panel(skin, width, low, high):
    """Follow chest volume with one shallow curve at each height."""
    heights = np.linspace(low - 0.035, high + 0.02, 78)
    bow = 0.035
    depths = []
    for z in heights:
        hits = []
        for column in np.linspace(-0.69, 0.69, 17):
            origin = Vector((column * width, -1.0, z))
            point = skin.ray_cast(origin, Vector((0, 1, 0)), 2)[0]
            if point is not None:
                hits.append(point.y - bow * column ** 2)
        depths.append(min(hits) if hits else np.nan)
    valid = np.isfinite(depths)
    envelope = np.interp(heights, heights[valid], np.asarray(depths)[valid])
    envelope = np.convolve(np.pad(envelope, (2, 2), mode="edge"), [1/9, 2/9, 3/9, 2/9, 1/9], mode="valid")
    fall = np.maximum(heights[None, :] - heights[:, None], 0)
    slope = 0.63 * np.maximum(fall - 0.011, 0)
    below = np.where(fall > 0, envelope[None, :] + slope, np.inf)
    envelope = np.minimum(envelope, below.min(axis=1))
    return lambda z, column: float(np.interp(z, heights, envelope)) + bow * column ** 2


def build_garment(body, joints, style, name, output):
    mesh = body.data
    coords = [body.matrix_world @ vertex.co for vertex in mesh.vertices]
    normal_matrix = body.matrix_world.to_3x3().inverted().transposed()
    normals = [(normal_matrix @ vertex.normal).normalized() for vertex in mesh.vertices]
    mesh.calc_loop_triangles()
    triangles = [tuple(triangle.vertices) for triangle in mesh.loop_triangles]
    skin = BVHTree.FromPolygons(coords, triangles, all_triangles=True)

    shoulder = joints["upperarm_l"]
    neck = joints["neck_01"]
    waist = joints["spine_02"]
    hip = joints["pelvis"]
    ankle = joints["foot_l"]
    width = abs(shoulder.x)
    jerkin = style == "MarketJerkin"
    if jerkin:
        low, high = hip.z + 0.034, neck.z + 0.024
        trim = 0.012
        slots = ("RussetLeather", "DarkLeather", "OldBrass")
        front = front_panel(skin, width, low, high)

        def neck_cut(p):
            delta = p - neck
            if delta.y < 0:
                # Open into a shallow V across the upper chest.
                opening = neck.z - 0.126 + 0.80 * abs(delta.x)
                radial = max(abs(delta.x) - width * 0.42, -delta.y - 0.195)
            else:
                opening = neck.z - 0.047
                radial = max(abs(delta.x) - width * 0.38, delta.y - 0.078)
            return max(opening - p.z, radial)

        def arm_cut(p):
            curve = min(0.024, max(-0.023, (p.z - shoulder.z) * 0.28))
            torso = smoothstep((shoulder.z - 0.063 - p.z) / 0.14)
            return width * (0.96 + 0.37 * torso) + curve - abs(p.x)

        boundaries = (lambda p: p.z - low - 0.013 * (abs(p.x) / width) ** 2,
                      lambda p: high - p.z, neck_cut, arm_cut)
    else:
        low, high = ankle.z + 0.041, max(hip.z + 0.075, waist.z - 0.045)
        trim = 0.023
        slots = ("CharcoalWool", "WoolBinding")
        boundaries = (lambda p: p.z - low, lambda p: high - p.z)

    positions = []
    faces = []
    indices = {}
    material_ids = []

    def add(poly, material):
        face = []
        for p, normal in poly:
            key = tuple(round(value, 6) for value in p)
            if key not in indices:
                facing = skin.ray_cast(p + normal * 0.0007, normal, 0.064)
                ease = 0.016 if jerkin else 0.014
                if facing[0] is not None and facing[1].dot(normal) < -0.12:
                    ease = min(ease, max(0.001, 0.32 * facing[3]))
                indices[key] = len(positions)
                position = p + ease * normal.normalized()
                if jerkin:
                    column = abs(p.x) / width
                    front_weight = smoothstep((neck.y - p.y - 0.028) / 0.040)
                    front_weight *= 1 - smoothstep((column - 0.65) / 0.50)
                    front_weight *= smoothstep((high - p.z) / 0.083)
                    surface = skin.ray_cast(Vector((position.x, -1.0, position.z)),
                                            Vector((0, 1, 0)), 2)[0]
                    if surface is not None and front_weight > 0:
                        chest = smoothstep((p.z - waist.z - 0.065) / 0.14)
                        allowed = 0.024 + 0.025 * chest
                        target_y = max(surface.y - allowed, front(position.z, column) - 0.015)
                        position.y += min(0.0, target_y - position.y) * front_weight
                positions.append(position)
            face.append(indices[key])
        for i in range(1, len(face) - 1):
            tri = (face[0], face[i], face[i + 1])
            if len(set(tri)) == 3:
                faces.append(tri)
                material_ids.append(material)

    def border(p):
        value = min(boundary(p) for boundary in boundaries)
        if jerkin and p.y < neck.y - 0.065:
            value = min(value, abs(p.x) + 0.003)
        return value - trim

    for triangle in triangles:
        poly = [(coords[i], normals[i]) for i in triangle]
        if max(p.z for p, _ in poly) <= low or min(p.z for p, _ in poly) >= high:
            continue
        for boundary in boundaries:
            poly = clip(poly, boundary)
            if not poly:
                break
        if poly:
            add(clip(poly, border), 0)
            add(clip(poly, lambda p: -border(p)), 1)

    garment = bpy.data.meshes.new(style)
    garment.from_pydata(positions, [], faces)
    garment.update()
    obj = bpy.data.objects.new(f"{style}_{name}", garment)
    bpy.context.collection.objects.link(obj)
    for slot in slots:
        material = bpy.data.materials.get(slot) or bpy.data.materials.new(slot)
        material.diffuse_color = MATERIALS[slot]
        garment.materials.append(material)
    uv = garment.uv_layers.new(name="GarmentUV")
    for poly, material in zip(garment.polygons, material_ids):
        poly.material_index = material
        poly.use_smooth = True
        for i in poly.loop_indices:
            p = garment.vertices[garment.loops[i].vertex_index].co
            u = 0.5 + atan2(p.x, -(p.y - hip.y)) / (2 * pi)
            uv.data[i].uv = (u, (p.z - low) / (high - low))

    bm = bmesh.new()
    bm.from_mesh(garment)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.000016)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    remaining = set(bm.verts)
    islands = []
    while remaining:
        queue = [remaining.pop()]
        island = []
        while queue:
            vert = queue.pop()
            island.append(vert)
            for edge in vert.link_edges:
                other = edge.other_vert(vert)
                if other in remaining:
                    remaining.remove(other)
                    queue.append(other)
        islands.append(island)
    main = max(islands, key=len)
    bmesh.ops.delete(bm, geom=[v for island in islands if island is not main for v in island],
                     context="VERTS")
    bmesh.ops.holes_fill(bm, edges=[edge for edge in bm.edges if edge.is_boundary], sides=8)
    smooth = [vert for vert in bm.verts if not vert.is_boundary]
    for _ in range(8):
        bmesh.ops.smooth_vert(bm, verts=smooth, factor=0.28,
                              use_axis_x=True, use_axis_y=True, use_axis_z=True)

    for vert in bm.verts:
        surface, normal, _, distance = skin.find_nearest(vert.co)
        if surface is None or distance > 0.045:
            continue
        opposite = skin.ray_cast(surface + normal * 0.0007, normal, 0.064)
        clearance = 0.006
        if opposite[0] is not None and opposite[1].dot(normal) < -0.12:
            clearance = min(clearance, max(0.001, 0.31 * opposite[3]))
        gap = (vert.co - surface).dot(normal)
        if gap < clearance:
            vert.co += (clearance - gap) * normal

    if jerkin:
        garment_tree = BVHTree.FromBMesh(bm)
        for step in (0.25, 0.36, 0.47, 0.58):
            z = low + (high - low) * step
            front, _, _, _ = garment_tree.ray_cast(Vector((0.0, -1.0, z)), Vector((0, 1, 0)), 2)
            if front is None:
                continue
            button = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.007)
            for vertex in button["verts"]:
                vertex.co = front + Vector((vertex.co.x, vertex.co.y * 0.50 - 0.003, vertex.co.z))
                for face in vertex.link_faces:
                    face.material_index = 2
                    face.smooth = True

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    edge_count = sum(edge.is_boundary for edge in bm.edges)
    assert edge_count > 50 and len(bm.faces) > 2000, (name, style, edge_count)
    bm.to_mesh(garment)
    bm.free()
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(filepath=str(output / f"{style}_{name}.fbx"), use_selection=True,
                             object_types={"MESH"}, axis_forward="-Y", axis_up="Z",
                             apply_unit_scale=True, mesh_smooth_type="FACE", add_leaf_bones=False)
    return {"vertices": len(garment.vertices), "faces": len(garment.polygons),
            "open_edges": edge_count, "material_faces": dict(Counter(p.material_index for p in garment.polygons))}


def main():
    source, output = (Path(arg).resolve() for arg in sys.argv[sys.argv.index("--") + 1:])
    output.mkdir(parents=True, exist_ok=True)
    report = {}
    for name in ("BridgeGuard", "Dwarf", "Elf", "Orc"):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=str(source / f"{name}_FullBody.fbx"), use_custom_normals=True)
        body = next(obj for obj in bpy.context.scene.objects if obj.type == "MESH")
        rig = next(obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE")
        joints = {bone.name: rig.matrix_world @ bone.head_local for bone in rig.data.bones}
        report[name] = {
            style: build_garment(body, joints, style, name, output)
            for style in ("MarketJerkin", "TravelTrousers")
        }
        body.hide_set(True)
        rig.hide_set(True)
        bpy.ops.wm.save_as_mainfile(filepath=str(output / f"VillageWardrobe_{name}.blend"))
    (output / "MeshReport.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
