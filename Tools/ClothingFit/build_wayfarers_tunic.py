"""Construct one short-sleeved tunic pattern on MetaHuman full-body fitting meshes."""
import bpy
import bmesh
import numpy as np
from mathutils.bvhtree import BVHTree
from math import atan2, pi
from mathutils import Vector
from pathlib import Path
import json
import sys

args = sys.argv[sys.argv.index('--') + 1:]
ROOT = Path(args[0]).resolve()


def crop(polygon, values, keep_positive=True):
    if not polygon:
        return []
    output = []
    for idx, a in enumerate(polygon):
        other = (idx + 1) % len(polygon)
        b, da, db = polygon[other], values[idx], values[other]
        ia, ib = da >= 0, db >= 0
        if ia == keep_positive:
            output.append(a)
        if ia != ib:
            t = da / (da - db)
            output.append(tuple(av.lerp(bv, t) for av, bv in zip(a, b)))
    return output


def smoothstep(value):
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def front_profile(coords, triangles, width, hem, neck):
    """Bridge the center chest within each horizontal section, then smooth vertically."""
    tree = BVHTree.FromPolygons(coords, triangles, all_triangles=True)
    heights = np.linspace(hem - 0.04, neck + 0.08, 96)
    arc = 0.038
    depths = []
    for z in heights:
        samples = []
        for fraction in np.linspace(-0.72, 0.72, 21):
            hit = tree.ray_cast(Vector((float(fraction * width), -1.5, float(z))), Vector((0, 1, 0)), 3)[0]
            if hit is not None:
                samples.append(hit.y - arc * fraction ** 2)
        depths.append(min(samples) if samples else float('nan'))
    valid = np.isfinite(depths)
    envelope = np.interp(heights, heights[valid], np.asarray(depths)[valid])
    envelope = np.convolve(np.pad(envelope, (3, 3), mode='edge'), [1/16,2/16,3/16,4/16,3/16,2/16,1/16], mode='valid')
    # A woven panel falls from the fullest part of the chest and gradually
    # returns to the waist. Limit the inward slope below each section.
    fall = np.maximum(heights[None, :] - heights[:, None], 0)
    below = np.where(heights[:, None] <= heights[None, :],
                     envelope[None, :] + 0.40 * (np.hypot(fall, 0.04) - 0.04), np.inf)
    envelope = np.minimum(envelope, below.min(axis=1))
    return lambda z, lateral: float(np.interp(z, heights, envelope)) + arc * lateral ** 2


def build(name):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(ROOT / f'{name}_FullBody.fbx'), use_custom_normals=True)
    body = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
    rig = next(obj for obj in bpy.context.scene.objects if obj.type == 'ARMATURE')
    joints = {b.name: rig.matrix_world @ b.head_local for b in rig.data.bones}
    width = abs(joints['upperarm_l'].x)
    elbow = joints['lowerarm_l']
    shoulder = joints['upperarm_l']
    hem = joints['pelvis'].z + 0.012
    neck_base = joints['neck_01'].z
    sleeve_x = width + (abs(elbow.x) - width) * 0.53
    cuff_z = shoulder.z + (elbow.z - shoulder.z) * 0.53
    trim = 0.010

    def neckline(p):
        # Cut an oval opening around the actual neck rather than retaining a
        # strip of the original vertical neck surface. The tip opens toward -Y.
        delta = p - joints['neck_01']
        angle = atan2(delta.x, -delta.y)
        notch = max(0, 1 - abs(angle) / 0.35)
        radius_x = 0.057 + 0.21 * width
        depth = (0.063 + 0.28 * width + 0.024 * notch
                 if delta.y < 0 else 0.056 + 0.16 * width)
        radius = ((delta.x / radius_x) ** 2 + (delta.y / depth) ** 2) ** 0.5
        collar_drop = 0.046 + (0.025 + 0.025 * notch if delta.y < 0 else 0)
        opening = max((radius - 1) * min(radius_x, depth), neck_base - collar_drop - p.z)
        return min(opening, neck_base + 0.019 - p.z)

    def cuffs(p):
        delta = max(-0.050, min(0.050, (p.z - cuff_z) * 0.48))
        return sleeve_x + delta - abs(p.x)

    def hemline(p):
        return p.z - hem - 0.012 * (abs(p.x) / max(0.15, width)) ** 2

    def band(p):
        return min(neckline(p), cuffs(p), hemline(p)) - trim

    coords = [body.matrix_world @ vertex.co for vertex in body.data.vertices]
    loops = body.data.uv_layers.active.data
    normal_xform = body.matrix_world.to_3x3().inverted().transposed()
    body.data.calc_loop_triangles()
    mesh_verts = []
    face_indices = []
    face_materials = []
    keyed = {}
    captured_uv = []

    def add_poly(poly, material):
        if len(poly) < 3:
            return
        face = []
        for pos, normal, body_uv in poly:
            key = tuple(round(v, 6) for v in pos)
            if key not in keyed:
                index = keyed[key] = len(mesh_verts)
                mesh_verts.append([pos.copy(), normal.copy()])
            else:
                index = keyed[key]
                mesh_verts[index][1] += normal
            face.append(index)
        for i in range(1, len(face)-1):
            tri = (face[0], face[i], face[i+1])
            if len(set(tri)) == 3:
                face_indices.append(tri)
                face_materials.append(material)

    for tri in body.data.loop_triangles:
        xyz = [coords[index] for index in tri.vertices]
        if max(p.z for p in xyz) < hem - 0.01 or min(p.z for p in xyz) > neck_base + 0.10:
            continue
        if min(abs(p.x) for p in xyz) > sleeve_x + 0.06:
            continue
        poly = [(p, (normal_xform @ body.data.vertices[index].normal).normalized(), Vector(loops[loop].uv))
                for p, index, loop in zip(xyz, tri.vertices, tri.loops)]
        for boundary in (neckline, cuffs, hemline):
            poly = crop(poly, [boundary(q[0]) for q in poly])
            if not poly:
                break
        if not poly:
            continue
        values = [band(v[0]) for v in poly]
        add_poly(crop(poly, values), 0)
        add_poly(crop(poly, values, False), 1)
        # Conservative coverage for a possible Unreal body-face mask.
        clear = crop(poly, [band(v[0]) - 0.014 for v in poly])
        if clear:
            captured_uv.append([list(v[2]) for v in clear])

    assert 1000 < len(face_indices) < 100000, (name, len(face_indices))
    triangles = [tuple(t.vertices) for t in body.data.loop_triangles]
    front = front_profile(coords, triangles, width, hem, neck_base)
    skin = BVHTree.FromPolygons(coords, triangles, all_triangles=True)
    positions = []
    for p, n in mesh_verts:
        normal = n.normalized()
        lateral = abs(p.x) / width
        toward_hem = 1 - smoothstep((p.z - hem) / 0.16)
        sleeve = smoothstep((lateral - 0.85) / 0.45)
        ease = 0.010 + 0.006 * toward_hem + 0.004 * sleeve
        # The MetaHuman face mesh extends down across the clavicles. Leave room
        # for that moving surface between the upper chest and the neck opening.
        yoke = smoothstep((p.z - joints['spine_05'].z) / max(0.05, neck_base - joints['spine_05'].z))
        yoke *= 1 - smoothstep((lateral - 0.82) / 0.42)
        ease += 0.014 * yoke
        q = p + normal * ease
        q.z += 0.012 * yoke
        # The underside of the chest can face down or back. Its position
        # determines membership in the front panel, independent of that normal.
        front_weight = smoothstep((joints['spine_05'].y - p.y - 0.005) / 0.045)
        front_weight *= 1 - smoothstep((lateral - 0.67) / 0.47)
        front_weight *= smoothstep((neck_base + 0.015 - p.z) / 0.085)
        if front_weight:
            target = front(p.z, lateral) - ease
            q.y += min(0, target - q.y) * front_weight
        # Keep the top panel outside the actual shoulder on either side of the neck.
        if lateral > 0.55 and normal.z > 0.16 and p.z > shoulder.z - 0.035:
            top = skin.ray_cast(Vector((q.x, q.y, neck_base + 0.4)), Vector((0, 0, -1)), 0.65)[0]
            if top is not None and abs(top.z - p.z) < 0.044:
                q.z = max(q.z, top.z + 0.012)
        positions.append(q)
    # Construct a surface with open cuffs, collar and hem. The two regions share vertices.
    mesh = bpy.data.meshes.new('WayfarersTunic_Pattern')
    mesh.from_pydata(positions, [], face_indices)
    mesh.validate(verbose=False)
    mesh.update()
    obj = bpy.data.objects.new(f'WayfarersTunic_{name}', mesh)
    bpy.context.collection.objects.link(obj)
    for mat_name, color in [('Linen', (0.025, 0.115, 0.108, 1)), ('GoldBinding', (0.43, 0.25, 0.074, 1))]:
        mat = bpy.data.materials.new(mat_name)
        mat.diffuse_color = color
        mesh.materials.append(mat)
    uv = mesh.uv_layers.new(name='GarmentUV')
    for face, material in zip(mesh.polygons, face_materials):
        face.material_index = material
        face.use_smooth = True
        for loop_idx in face.loop_indices:
            coord = mesh.vertices[mesh.loops[loop_idx].vertex_index].co
            uv.data[loop_idx].uv = (atan2(coord.x, -coord.y) / (2 * pi) + 0.5, (coord.z - hem) / (neck_base - hem))

    # Relax body-surface details while holding the cut edges and avoiding gaps at UV seams.
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    movable = [v for v in bm.verts if not v.is_boundary]
    for _ in range(3):
        bmesh.ops.smooth_vert(bm, verts=movable, factor=0.29, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.000008)
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=8)
    # Drop disconnected fragments from the chin at the top of the source scan.
    remaining = set(bm.verts)
    islands = []
    while remaining:
        stack = [remaining.pop()]
        island = []
        while stack:
            vert = stack.pop()
            island.append(vert)
            for edge in vert.link_edges:
                other = edge.other_vert(vert)
                if other in remaining:
                    remaining.remove(other)
                    stack.append(other)
        islands.append(island)
    main = max(islands, key=len)
    debris = [v for island in islands if island is not main for v in island]
    if debris:
        bmesh.ops.delete(bm, geom=debris, context='VERTS')

    # Ensure clearance after relaxation, including the collar edge and seams.
    # Skip narrow armpit folds where opposing skin surfaces face one another.
    for v in bm.verts:
        hit, n, _, distance = skin.find_nearest(v.co)
        if hit is None:
            continue
        gap = (v.co - hit).dot(n)
        if distance < 0.045 and gap < 0.008 and (v.co.z > joints['spine_05'].z or n.dot(v.normal) > 0.35):
            v.co += n * min(0.020, 0.008 - gap)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    boundary_count = sum(edge.is_boundary for edge in bm.edges)
    nonmanifold_count = sum(not edge.is_manifold and not edge.is_boundary for edge in bm.edges)
    bm.to_mesh(mesh)
    bm.free()

    for other in bpy.context.scene.objects:
        other.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(filepath=str(ROOT / f'WayfarersTunic_{name}.fbx'), use_selection=True,
                             object_types={'MESH'}, axis_forward='-Y', axis_up='Z', apply_unit_scale=True,
                             mesh_smooth_type='FACE', add_leaf_bones=False)
    if name == 'BridgeGuard':
        for other in bpy.context.scene.objects:
            if other != obj:
                other.hide_set(True)
                other.hide_render = True
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'WayfarersTunic_Source.blend'))
    (ROOT / f'mask_uv_{name}.json').write_text(json.dumps(captured_uv), encoding='utf-8')
    return {'faces': len(mesh.polygons), 'verts': len(mesh.vertices), 'boundary_edges': boundary_count,
            'nonmanifold_interior_edges': nonmanifold_count, 'materials': list({p.material_index for p in mesh.polygons}),
            'bounds': [[round(fn(v.co[i] for v in mesh.vertices),4) for i in range(3)] for fn in (min,max)]}


names = args[1:] or ['BridgeGuard', 'Dwarf', 'Elf', 'Orc']
result = {name: build(name) for name in names}
(ROOT / 'garment_mesh_report.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(result)
