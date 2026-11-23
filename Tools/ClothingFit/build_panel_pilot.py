"""Build a joined-panel tunic and gravity-settle it on one wardrobe reference in Blender.

blender -b -P build_panel_pilot.py -- BridgeGuard_FullBody.fbx output_directory
"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def finish_draped_panel(mesh, skin, waist_height):
    """Fair the settled fabric in metres while retaining its cut and openings."""
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    start = np.asarray([v.co[:] for v in bm.verts], dtype=np.float64)
    pos = start.copy()
    receivers, neighbours = [], []
    boundary = np.array([v.is_boundary for v in bm.verts])
    for v in bm.verts:
        for e in v.link_edges:
            if not v.is_boundary or e.is_boundary:
                receivers.append(v.index)
                neighbours.append(e.other_vert(v).index)
    degree = np.bincount(receivers)[:, None]
    # Pin broad features weakly and keep trim on its own edge loop. Recomputing
    # vertex normals alone cannot repair folds whose neighbouring faces turn back.
    for step in range(42):
        total = np.zeros_like(pos)
        np.add.at(total, receivers, pos[neighbours])
        delta = .62 * (total / degree - pos) + .009 * (start - pos)
        delta *= np.minimum(1, .003 / np.maximum(np.linalg.norm(delta, axis=1, keepdims=True), 1e-10))
        pos += delta
        drift = pos - start
        limit = np.where(boundary, .006, .018)[:, None]
        pos = start + drift * np.minimum(1, limit / np.maximum(np.linalg.norm(drift, axis=1, keepdims=True), 1e-10))
        if step % 3 == 2:
            for i, p in enumerate(pos):
                hit, normal, _, distance = skin.find_nearest(Vector(p))
                if hit is not None and distance < .025:
                    gap = (Vector(p) - hit).dot(normal)
                    if gap < .003:
                        pos[i] += np.asarray(normal) * min(.002, .003 - gap)
    # Restore wearing ease lost while relaxing ridges. Diffuse the displacement
    # across adjacent fabric before export so a corrective push has a soft edge.
    for _ in range(7):
        offsets = np.zeros_like(pos)
        for i, p in enumerate(pos):
            point = Vector(p)
            hit, normal, _, distance = skin.find_nearest(point)
            if hit is None or distance > .045:
                continue
            gap = (point-hit).dot(normal)
            opposing, opposite_normal, _, depth = skin.ray_cast(hit+normal*.0008, normal,.025)
            upper = np.clip((p[2]-waist_height-.025)/.075, 0., 1.)
            target = .003+.008*upper
            if opposing is not None and opposite_normal.dot(normal) < -.2:
                target = min(target, max(.002,depth*.35))
            if gap < target:
                offsets[i] = np.asarray(normal)*min(.005,target-gap)
        total = np.zeros_like(pos)
        np.add.at(total, receivers, offsets[neighbours])
        pos += .52*offsets + .48*total/degree
    for v, point in zip(bm.verts, pos):
        v.co = point
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        e.smooth = True
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def build(reference, output, loose_hem=False, motion_clearance=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(reference))
    scene = bpy.context.scene
    body = next(o for o in scene.objects if o.type == 'MESH')
    rig = next(o for o in scene.objects if o.type == 'ARMATURE')
    joints = {b.name: rig.matrix_world @ b.head_local for b in rig.data.bones}
    body.data.calc_loop_triangles()
    skin = BVHTree.FromPolygons([body.matrix_world @ v.co for v in body.data.vertices],
                                [list(t.vertices) for t in body.data.loop_triangles], all_triangles=True)
    shoulder, elbow = joints['upperarm_l'], joints['lowerarm_l']
    hem, pit = joints['pelvis'].z + .012, shoulder.z - .105
    n, rows, cap = 36, 22, 14
    pts, faces, lookup, trim, held = [], [], {}, [], set()
    panel_uvs = []

    def vertex(point):
        key = tuple(round(float(v), 6) for v in point)
        if key not in lookup:
            lookup[key] = len(pts)
            pts.append(tuple(point))
        return lookup[key]

    def join(before, after, island, row, row_count, closed=False, band=False):
        columns = len(before) if closed else len(before) - 1
        for j in range(len(before) if closed else len(before) - 1):
            k = (j + 1) % len(before)
            face = tuple(dict.fromkeys([before[j], before[k], after[k], after[j]]))
            if len(face) >= 3:
                faces.append(face)
                trim.append(band)
                # One chart per cut piece. Unwrapping by face angle creates
                # staircase-shaped UV seams across the middle of the draped chest.
                coordinates = {}
                for v, col, r in ((before[j],j,row-1),(before[k],j+1,row-1),
                                  (after[k],j+1,row),(after[j],j,row)):
                    coordinates.setdefault(v, ((island%2)*.5+.01+.48*col/columns,
                                               (island//2)*.5+.01+.48*r/row_count))
                panel_uvs.append(coordinates)

    def ray(point, direction):
        return skin.ray_cast(Vector(point), Vector(direction), 2)[0]

    # Follow the torso only up to the axilla. A smooth convex front panel bridges
    # the chest, while the side and back retain their separate wearing allowances.
    def lower_section(z, side):
        mid_y = float(np.interp(z, [hem, joints['spine_03'].z, pit], [-.029, -.038, .012]))
        front = side == -1
        angles = np.linspace(0, math.pi, n + 1)
        raw = []
        for a in angles:
            direction = (-math.cos(a), side * math.sin(a), 0)
            p = ray((0, mid_y, z), direction)
            if p is None:
                raise ValueError(f"Open torso at {z} m")
            raw.append(np.array(p) + np.array(direction) * (.010 + .003 * math.sin(a)))
        if front:
            for j in range(n // 2):
                mirror = n - j
                outer = max(.001, abs(raw[j][0]))
                for k in range(j, mirror + 1):
                    u = min(1., abs(raw[k][0]) / outer)
                    raw[k][1] = min(raw[k][1], min(raw[j][1], raw[mirror][1]) + .006 * (1 - u*u))
        return [Vector(p) for p in raw]

    armholes = {}
    for side in (-1, 1):
        island = int(side == 1)
        prev = None
        for row in range(rows + 1):
            points = lower_section(hem + (pit - hem) * row / rows, side)
            line = [vertex(p) for p in points]
            if prev is not None:
                join(prev, line, island, row, rows+cap, band=row == 1)
            prev = line
        base = points
        end_x = shoulder.x + .033
        opening = .082
        ends = []
        for j in range(n + 1):
            x = -end_x * math.cos(math.pi * j / n)
            inside = max(0., 1 - (x / opening)**2)
            y = shoulder.y + side * (.105 if side == -1 else .055) * math.sqrt(inside)
            top = ray((x, y, joints['neck_01'].z + .015), (0, 0, -1))
            if top is None:
                raise ValueError(f"Shoulder reference miss at {(x, y)}")
            ends.append(Vector((x, y, top.z + .009)))
        edge = [[prev[0]], [prev[-1]]]
        for row in range(1, cap + 1):
            t = row / cap
            line = []
            for j, (bottom, top) in enumerate(zip(base, ends)):
                p = bottom.lerp(top, t)
                lateral = abs(math.cos(math.pi * j / n))
                p.y += side * math.sin(math.pi * t) * (.028 + .032 * lateral**4)
                index = vertex(p)
                line.append(index)
                if row >= cap - 1 and abs(top.x) > opening and abs(top.x) < end_x * .94:
                    held.add(index)
            join(prev, line, island, row+rows, rows+cap, band=row == cap)
            edge[0].append(line[0])
            edge[1].append(line[-1])
            prev = line
        armholes[side] = edge

    for j, sign in enumerate((-1, 1)):
        front, back = armholes[-1][j], armholes[1][j]
        rim = front + list(reversed(back[1:-1]))
        arm = (elbow - shoulder).normalized()
        transverse = Vector((-arm.z, 0, arm.x)).normalized()
        depth = arm.cross(transverse).normalized()
        center = shoulder.lerp(elbow, .54)
        cuff = []
        for k in range(len(rim)):
            a = 2 * math.pi * k / len(rim)
            direction = -transverse * math.cos(a) - depth * math.sin(a) * (1 if depth.y > 0 else -1)
            hit = ray(center, direction)
            if hit is None:
                raise ValueError("Open upper-arm section")
            p = hit + .016 * direction
            p.x *= sign
            cuff.append(p)
        start = [Vector(pts[index]) for index in rim]
        prev = rim
        for k in range(1, 10):
            row = [vertex(a.lerp(b, k / 9)) for a, b in zip(start, cuff)]
            join(prev, row, 2+j, k, 9, closed=True, band=k == 9)
            prev = row

    mesh = bpy.data.meshes.new('Front_Back_SetInSleeves')
    mesh.from_pydata(pts, [], faces)
    mesh.update()
    uv = mesh.uv_layers.new(name='Pattern')
    for polygon, coordinates in zip(mesh.polygons, panel_uvs):
        for loop in polygon.loop_indices:
            uv.data[loop].uv = coordinates[mesh.loops[loop].vertex_index]
    garment = bpy.data.objects.new('PanelTunic', mesh)
    scene.collection.objects.link(garment)
    for name in ('Linen', 'Gold'):
        garment.data.materials.append(bpy.data.materials.new(name))
    for f, band in zip(mesh.polygons, trim):
        f.material_index = int(band)
        f.use_smooth = True
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    assert all(e.is_manifold or e.is_boundary for e in bm.edges)
    boundaries = {v for e in bm.edges if e.is_boundary for v in e.verts}
    loops = 0
    while boundaries:
        stack = [boundaries.pop()]
        loops += 1
        while stack:
            for e in stack[-1].link_edges:
                if e.is_boundary and e.other_vert(stack[-1]) in boundaries:
                    v = e.other_vert(stack[-1])
                    boundaries.remove(v)
                    stack.append(v)
                    break
            else:
                stack.pop()
    assert loops == 4, f"Expected neck, hem and two cuffs, got {loops} openings"
    bm.to_mesh(mesh)
    bm.free()
    # Use one joined surface for sewing lines. Run a reference-body drape in
    # meters, then export that rest shape for Unreal's ordinary outfit resizing.
    bpy.ops.object.select_all(action='DESELECT')
    garment.select_set(True)
    bpy.context.view_layer.objects.active = garment
    body.modifiers.new("Reference collider", 'COLLISION')
    body.collision.thickness_outer = .004
    anchors = garment.vertex_groups.new(name="Shoulder support")
    anchors.add(list(held), 1., 'REPLACE')
    cloth = garment.modifiers.new("Reference drape", 'CLOTH')
    cloth.settings.vertex_group_mass = anchors.name
    cloth.settings.quality = 8
    cloth.settings.mass = .12
    cloth.settings.tension_stiffness = 50
    cloth.settings.compression_stiffness = 40
    cloth.settings.shear_stiffness = 25
    cloth.settings.bending_stiffness = 1.1
    cloth.collision_settings.distance_min = .005
    cloth.collision_settings.collision_quality = 5
    for frame in range(1, 26):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
    bpy.ops.object.modifier_apply(modifier=cloth.name)
    travel = np.linalg.norm(np.asarray([v.co[:] for v in mesh.vertices]) - np.asarray(pts), axis=1)
    assert np.isfinite(travel).all() and travel.max() < .12
    finish_draped_panel(mesh, skin, joints['spine_03'].z)
    if loose_hem:
        for vertex in mesh.vertices:
            x, y, z = vertex.co
            level = np.clip((joints['spine_03'].z + .02 - z) / .20, 0., 1.)
            flare = level * level * (3. - 2. * level)
            if motion_clearance:
                # Keep the skirt of the tunic clear of the pelvis before it
                # starts to swing. The additional ease blends up to the waist.
                vertex.co.x = x * (1. + .32 * flare)
                vertex.co.y = -.025 + (y + .025) * (1. + .36 * flare)
                vertex.co.z = z - .032 * flare
            else:
                vertex.co.x = x * (1. + .15 * flare)
                vertex.co.y = -.025 + (y + .025) * (1. + .18 * flare)
                vertex.co.z = z - .065 * flare
    output.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.fbx(filepath=str(output/'PanelTunic.fbx'), use_selection=True,
                             object_types={'MESH'}, axis_forward='-Y', axis_up='Z',
                             apply_unit_scale=True, mesh_smooth_type='FACE', add_leaf_bones=False)
    if loose_hem:
        # A single material section keeps the simulation mesh welded through the trim.
        mesh.materials.clear()
        reduction = garment.modifiers.new('Simulation mesh resolution', 'DECIMATE')
        reduction.ratio = .15
        bpy.ops.object.modifier_apply(modifier=reduction.name)
        bpy.ops.export_scene.fbx(filepath=str(output/'HemSimulation.fbx'), use_selection=True,
                                 object_types={'MESH'}, axis_forward='-Y', axis_up='Z',
                                 apply_unit_scale=True, mesh_smooth_type='FACE', add_leaf_bones=False)
    report = {'reference': reference.name, 'vertices': len(mesh.vertices), 'openings': loops,
              'drape_frames': 25, 'median_settle_mm': round(float(np.median(travel))*1000, 2),
              'max_settle_mm': round(float(travel.max())*1000, 2)}
    (output/'pattern.json').write_text(json.dumps(report, indent=2))
    print(report)


if __name__ == '__main__':
    arguments = sys.argv[sys.argv.index('--') + 1:]
    source, destination = map(Path, arguments[:2])
    build(source, destination, loose_hem='--loose-hem' in arguments[2:],
          motion_clearance='--motion-clearance' in arguments[2:])
