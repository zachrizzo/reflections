"""Retopologize the image-to-3D Red London clothes for each actual NPC rig."""
import json
import math
from pathlib import Path
import runpy

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector
from mathutils.bvhtree import BVHTree


ART = Path(__file__).resolve().parent
PROJECT = ART.parents[3]
STAGING = PROJECT / "Intermediate/NpcMovement/SimpleRed"
FIT = runpy.run_path(str(PROJECT / "ArtDirection/NPC_Reactions/refit_crowd_wardrobe.py"))
IDENTITIES = ("BridgeGuard", "ArchiveApprentice", "CoinClerk", "FestivalDrummer")


def source_mesh(name):
    bpy.ops.import_scene.gltf(filepath=str(ART / f"{name}_Projection.glb"))
    obj = next(ob for ob in bpy.context.selected_objects if ob.type == "MESH")
    obj.data.calc_loop_triangles()
    points = [obj.matrix_world @ v.co for v in obj.data.vertices]
    polygons = [tuple(tri.vertices) for tri in obj.data.loop_triangles]
    bpy.data.objects.remove(obj, do_unlink=True)
    return points, polygons


def reduced_boot():
    bpy.ops.import_scene.gltf(filepath=str(ART / "RedWalkingBoot_Projection.glb"))
    obj = next(ob for ob in bpy.context.selected_objects if ob.type == "MESH")
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    remaining = set(bm.verts)
    components = []
    while remaining:
        group = [remaining.pop()]
        for vertex in group:
            for edge in vertex.link_edges:
                opposite = edge.other_vert(vertex)
                if opposite in remaining:
                    remaining.remove(opposite)
                    group.append(opposite)
        components.append(group)
    components.sort(key=len, reverse=True)
    bmesh.ops.delete(bm, geom=[v for group in components[1:] for v in group], context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    reduction = obj.modifiers.new("Decimate generated boot silhouette", "DECIMATE")
    reduction.ratio = min(1.0, 4400 / len(obj.data.vertices))
    bpy.ops.object.modifier_apply(modifier=reduction.name)
    points = [v.co.copy() for v in obj.data.vertices]
    faces = [tuple(face.vertices) for face in obj.data.polygons]
    bpy.data.objects.remove(obj, do_unlink=True)
    return points, faces


def axes(points):
    return [(min(p[i] for p in points), max(p[i] for p in points)) for i in range(3)]


def fit_surface(body, rig, bones, kind, reference):
    obj = body.copy()
    obj.data = body.data.copy()
    obj.name = "SimpleRed_" + kind
    bpy.context.scene.collection.objects.link(obj)
    obj.matrix_world = body.matrix_world.copy()
    inverse = obj.matrix_world.inverted()
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    z_cut = bones["spine_01"].z - 0.025
    toe_min = min(bones[f"foot_{side}"].z for side in ("l", "r"))
    ankle = toe_min + 0.065
    placket_min = z_cut - 0.025
    placket_max = bones["neck_01"].z - 0.014
    source_points, source_faces = reference
    ref_bounds = axes(source_points)
    tree = BVHTree.FromPolygons(source_points, source_faces, all_triangles=True)
    cloth_offset = 0.019 if kind == "Tunic" else 0.010

    def cut(point, normal, discard_below=False, verts=None, edges=None, faces=None):
        bmesh.ops.bisect_plane(
            bm,
            geom=[*(bm.verts if verts is None else verts), *(bm.edges if edges is None else edges), *(bm.faces if faces is None else faces)],
            dist=1e-5,
            plane_co=inverse @ point,
            plane_no=(obj.matrix_world.to_3x3().transposed() @ normal).normalized(),
            clear_inner=discard_below,
            clear_outer=not discard_below,
        )

    if kind == "Tunic":
        cut(Vector((0, 0, placket_min)), Vector((0, 0, 1)), True)
        cut(Vector((0, 0, placket_max)), Vector((0, 0, 1)))
        for side in ("l", "r"):
            wrist = bones["hand_" + side]
            direction = (wrist - bones["lowerarm_" + side]).normalized()
            sign = 1 if side == "l" else -1
            fr = [f for f in bm.faces if sign * (obj.matrix_world @ f.calc_center_median()).x > 0.24]
            vr = {v for f in fr for v in f.verts}
            er = {e for f in fr for e in f.edges}
            cut(wrist + direction * 0.012, direction, False, vr, er, fr)
    else:
        cut(Vector((0, 0, z_cut + 0.024)), Vector((0, 0, 1)))
        cut(Vector((0, 0, ankle - 0.015)), Vector((0, 0, 1)), True)
        bmesh.ops.delete(
            bm,
            geom=[f for f in bm.faces if abs((obj.matrix_world @ f.calc_center_median()).x) > 0.285],
            context="FACES",
        )
    bmesh.ops.delete(bm, geom=[edge for edge in bm.edges if not edge.link_faces], context="EDGES")
    bmesh.ops.delete(bm, geom=[vertex for vertex in bm.verts if not vertex.link_faces], context="VERTS")
    world_mat3 = obj.matrix_world.to_3x3()
    n_transform = world_mat3.inverted().transposed()
    body_top = bones["neck_01"].z if kind == "Tunic" else z_cut + 0.024
    body_bottom = placket_min if kind == "Tunic" else ankle - 0.015
    width = abs(bones["hand_l"].x) if kind == "Tunic" else abs(bones["thigh_l"].x) + 0.12
    back_middle = (ref_bounds[1][0] + ref_bounds[1][1]) * 0.5
    half_depth = (ref_bounds[1][1] - ref_bounds[1][0]) * 0.5
    sampled = 0
    for v in bm.verts:
        p = obj.matrix_world @ v.co
        normal = (n_transform @ v.normal).normalized()
        local_direction = p - Vector((p.x if kind == "Trousers" else 0.0, -0.025, p.z))
        if local_direction.length > 0.045 and normal.dot(local_direction) < -0.02:
            normal = -normal
        z_norm = max(0.0, min(1.0, (p.z - body_bottom) / max(0.01, body_top - body_bottom)))
        source_x = ((max(-1.0, min(1.0, p.x / width)) + 1.0) * 0.5)
        x = ref_bounds[0][0] + source_x * (ref_bounds[0][1] - ref_bounds[0][0])
        z = ref_bounds[2][0] + z_norm * (ref_bounds[2][1] - ref_bounds[2][0])
        sign = -1 if p.y < -0.025 else 1
        origin = Vector((x, back_middle + sign * (half_depth + 0.2), z))
        hit, _, _, _ = tree.ray_cast(origin, Vector((0, -sign, 0)), (half_depth + 0.2) * 2)
        detail = 0.0
        if hit is not None:
            sampled += 1
            # Use a locally high-passed depth to retain the source's folds without
            # inheriting the dimensions of its virtual mannequin.
            nearby = []
            for dx, dz in [(-0.025, 0), (0.025, 0), (0, -0.024), (0, 0.024)]:
                candidate, _, _, _ = tree.ray_cast(origin + Vector((dx, 0, dz)), Vector((0, -sign, 0)), (half_depth + 0.2) * 2)
                if candidate:
                    nearby.append(candidate.y)
            if nearby:
                detail = max(-0.003, min(0.006, (hit.y - sum(nearby) / len(nearby)) * sign * 0.22))
        v.co = inverse @ (p + normal * (cloth_offset + detail))

    uv_layer = bm.loops.layers.uv.active
    for face in bm.faces:
        face.smooth = True
        face.material_index = 0
        if uv_layer:
            for loop in face.loops:
                p = obj.matrix_world @ loop.vert.co
                u = min(0.99, max(0.01, 0.5 + p.x / (2.12 * width)))
                v = min(0.99, max(0.01, (p.z - body_bottom) / max(0.01, body_top - body_bottom)))
                # Front source texture occupies the left half, the simpler rear
                # fabric uses the right half of the matching texture atlas.
                loop[uv_layer].uv = (u * 0.50 + (0.0 if p.y < -0.025 else 0.50), v)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.materials.clear()
    mat = bpy.data.materials.new(f"RedLondon_{kind}")
    obj.data.materials.append(mat)
    for vertex in obj.data.vertices:
        weights = [(g.group, g.weight) for g in vertex.groups if g.weight > 0.0001]
        total = sum(w for _, w in weights)
        if total <= 0.0:
            raise RuntimeError(f"Unweighted vertex {vertex.index} on {kind}")
        for group, weight in weights:
            obj.vertex_groups[group].add([vertex.index], weight / total, "REPLACE")
    return obj, dict(projected_vertices=sampled, total_vertices=len(obj.data.vertices))


def export_skin(body, rig, bones, identity):
    # Preserve the native baked torso material on the exposed cuffs and neck.
    # Remove the covered skin on a separate mesh instead of editing shared body assets.
    obj = body.copy()
    obj.data = body.data.copy()
    bpy.context.scene.collection.objects.link(obj)
    obj.matrix_world = body.matrix_world.copy()
    cut_mesh = bmesh.new()
    cut_mesh.from_mesh(obj.data)
    neck_floor = bones["neck_01"].z - 0.022
    inverse = obj.matrix_world.inverted()
    keep_faces = set()
    head = [f for f in cut_mesh.faces if (obj.matrix_world @ f.calc_center_median()).z > neck_floor - 0.06]
    regions = [(head, Vector((0, 0, neck_floor)), Vector((0, 0, 1)))]
    for side, sign in (("l", 1), ("r", -1)):
        wrist = bones["hand_" + side]
        axis = (wrist - bones["lowerarm_" + side]).normalized()
        hand_faces = [f for f in cut_mesh.faces if sign * (obj.matrix_world @ f.calc_center_median()).x > 0.27]
        regions.append((hand_faces, wrist - axis * 0.002, axis))
    for faces, point, normal in regions:
        verts = {v for f in faces for v in f.verts}
        edges = {e for f in faces for e in f.edges}
        result = bmesh.ops.bisect_plane(cut_mesh, geom=[*verts, *edges, *faces], dist=1e-5,
                                       plane_co=inverse @ point,
                                       plane_no=(obj.matrix_world.to_3x3().transposed() @ normal).normalized())
        for f in [*faces, *(element for element in result["geom"] if isinstance(element, bmesh.types.BMFace))]:
            if f.is_valid and (obj.matrix_world @ f.calc_center_median() - point).dot(normal) >= -1e-5:
                keep_faces.add(f)
    bmesh.ops.delete(cut_mesh, geom=[face for face in cut_mesh.faces if face not in keep_faces], context="FACES")
    bmesh.ops.delete(cut_mesh, geom=[edge for edge in cut_mesh.edges if not edge.link_faces], context="EDGES")
    bmesh.ops.delete(cut_mesh, geom=[vertex for vertex in cut_mesh.verts if not vertex.link_faces], context="VERTS")
    cut_mesh.to_mesh(obj.data)
    cut_mesh.free()
    obj.name = f"SK_{identity}_Exposed_SimpleRed"
    FIT["export_fbx"](obj, rig, STAGING / f"{obj.name}.fbx")
    return obj


def fit_boots(body, rig, bones, identity, source):
    points, faces = source
    bounds = axes(points)
    cuff = [p for p in points if p.z > bounds[2][1] - (bounds[2][1] - bounds[2][0]) * 0.11]
    cuff_long = statistics_midpoint(p.x for p in cuff)
    cuff_across = statistics_midpoint(p.y for p in cuff)
    native = [body.matrix_world @ v.co for v in body.data.vertices]
    verts, polygons, weights = [], [], []
    report = {}
    for side, sign in (("l", 1), ("r", -1)):
        ankle = bones["foot_" + side]
        ball = bones["ball_" + side]
        forward = (ball - ankle).to_2d().to_3d().normalized()
        across = Vector((-forward.y, forward.x, 0))
        foot = [p for p in native if p.x * sign > 0.035 and p.z < ankle.z + 0.022]
        lng = [(p-ankle).dot(forward) for p in foot]
        lat = [(p-ankle).dot(across) for p in foot]
        back, front = min(lng) - 0.008, max(lng) + 0.013
        width = max(lat) - min(lat) + 0.010
        bottom = min(p.z for p in foot) - 0.007
        height = ankle.z - bottom + 0.089
        t_cuff = (cuff_long - bounds[0][0]) / (bounds[0][1] - bounds[0][0])
        cuff_offset = front + (back - front) * t_cuff
        roll_center = (ball - ankle).dot(forward)
        index_offset = len(verts)
        for p in points:
            u = (p.x - bounds[0][0]) / (bounds[0][1] - bounds[0][0])
            v = (p.z - bounds[2][0]) / (bounds[2][1] - bounds[2][0])
            along = front + (back - front) * u - cuff_offset * min(1, v**2 * 1.35)
            side_dist = (p.y - cuff_across) * width / (bounds[1][1] - bounds[1][0]) * sign
            position = ankle + forward * along + across * side_dist
            position.z = bottom + height * v
            verts.append(position)
            calf = max(0.0, min(0.74, (position.z - ankle.z - 0.008) / max(0.01, height - ankle.z) * 0.74))
            toe_blend = max(0.0, min(0.75, (along - roll_center * .78) / 0.075)) * (1 - calf)
            weights.append({f"calf_{side}": calf, f"ball_{side}": toe_blend, f"foot_{side}": 1 - calf - toe_blend})
        polygons.extend(tuple(index_offset + j for j in (reversed(face) if sign > 0 else face)) for face in faces)
        report[side] = dict(
            foot_length_cm=round((max(lng) - min(lng)) * 100, 2),
            boot_length_cm=round((front - back) * 100, 2),
            boot_width_cm=round(width * 100, 2),
            boot_height_cm=round(height * 100, 2),
        )
    mesh = bpy.data.meshes.new(f"SK_{identity}_Boots_SimpleRed")
    mesh.from_pydata(verts, [], polygons)
    mesh.update()
    boot = bpy.data.objects.new(mesh.name, mesh)
    bpy.context.scene.collection.objects.link(boot)
    boot.parent = rig
    boot.matrix_parent_inverse = rig.matrix_world.inverted()
    boot.matrix_world = Matrix.Identity(4)
    boot.modifiers.new("MetaHuman foot and calf", "ARMATURE").object = rig
    mat = bpy.data.materials.new("RedLondon_Boots")
    boot.data.materials.append(mat)
    uv = mesh.uv_layers.new(name="Boot Material UV")
    for loop in mesh.loops:
        point = points[loop.vertex_index % len(points)]
        u = (point.x - bounds[0][0]) / (bounds[0][1] - bounds[0][0])
        v = (point.z - bounds[2][0]) / (bounds[2][1] - bounds[2][0])
        uv.data[loop.index].uv = (u * 0.5 + (0.5 if point.y < cuff_across else 0.0), v)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    groups = {}
    for index, row in enumerate(weights):
        for name, weight in row.items():
            if weight < 0.00001:
                continue
            if name not in groups:
                groups[name] = boot.vertex_groups.new(name=name)
            groups[name].add([index], weight, "REPLACE")
    return boot, report


def statistics_midpoint(values):
    values = list(values)
    return (min(values) + max(values)) * 0.5


def run(identity, references):
    source, body_name, _, _ = FIT["WARDROBE"][identity]
    bpy.ops.wm.open_mainfile(filepath=str(ART.parent.parent / source))
    body = bpy.data.objects[body_name]
    rig = next(modifier.object for modifier in body.modifiers if modifier.type == "ARMATURE")
    bones = {bone.name: rig.matrix_world @ bone.head_local for bone in rig.data.bones}
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH" and obj != body and obj.name.startswith("SK_"):
            obj.hide_render = True
    info = {}
    for kind in ("Tunic", "Trousers", "Boots"):
        if kind == "Boots":
            obj, details = fit_boots(body, rig, bones, identity, references[kind])
        else:
            obj, details = fit_surface(body, rig, bones, kind, references[kind])
        obj.name = f"SK_{identity}_{kind}_SimpleRed"
        FIT["export_fbx"](obj, rig, STAGING / f"{obj.name}.fbx")
        info[kind] = details
    export_skin(body, rig, bones, identity)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(STAGING / f"{identity}_SimpleRed.blend"))
    (STAGING / f"{identity}_SimpleRed.json").write_text(json.dumps(info, indent=2))


if __name__ == "__main__":
    STAGING.mkdir(parents=True, exist_ok=True)
    sources = {part: source_mesh("Red" + part) for part in ("Tunic", "Trousers")}
    sources["Boots"] = reduced_boot()
    for name in IDENTITIES:
        run(name, sources)
