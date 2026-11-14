"""Fit the travel cloak and baselayers to the exported playable MetaHuman."""

import json
import math
from pathlib import Path
import os

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree


ART = Path(__file__).resolve().parent
STAGING = ART.parents[3] / 'Intermediate/TravelCloak'
MANTLE = os.environ.get('REFLECTIONS_TRAVEL_MANTLE') == '1'
BODY = bpy.data.objects['Native MetaHuman fitting body']
RIG = next(mod.object for mod in BODY.modifiers if mod.type == 'ARMATURE')
RIG.hide_set(False)
BODY.hide_render = False
bones = {bone.name: RIG.matrix_world @ bone.head_local for bone in RIG.data.bones}
coords = [BODY.matrix_world @ vert.co for vert in BODY.data.vertices]

for obj in list(bpy.context.scene.objects):
    if obj.type == 'MESH' and obj != BODY and 'Face' not in obj.name and 'face' not in obj.name:
        bpy.data.objects.remove(obj, do_unlink=True)


def material(name, color, roughness):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = roughness
    return mat


mats = {
    'Shirt': material('Black rib-knit shirt', (.030, .027, .026), .91),
    'Trousers': material('Black wool twill', (.019, .018, .018), .9),
    'Boots': material('Black oiled leather', (.031, .026, .023), .64),
    'Sleeves': material('Charcoal broadcloth', (.041, .035, .032), .88),
    'Drape': material('Charcoal cloak drape', (.041, .035, .032), .88),
}


def wrist_distance(point, side):
    wrist = bones['hand_' + side]
    forearm = (wrist - bones['lowerarm_' + side]).normalized()
    return (point - wrist).dot(forearm)


def crop_skin(part, keep, offset, bottom=None, top=None, cuffs=None):
    obj = BODY.copy()
    obj.data = BODY.data.copy()
    obj.name = 'SK_HeroTravel_' + part
    bpy.context.scene.collection.objects.link(obj)
    obj.matrix_world = BODY.matrix_world.copy()
    inverse = obj.matrix_world.inverted()
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.normal_update()
    for vertex in bm.verts:
        vertex.co += inverse.to_3x3() @ ((obj.matrix_world.to_3x3().inverted().transposed() @ vertex.normal).normalized() * offset)
    bmesh.ops.delete(bm, geom=[face for face in bm.faces if not keep(obj.matrix_world @ face.calc_center_median())], context='FACES')

    def cut(point, normal, inner, outer):
        bmesh.ops.bisect_plane(bm, geom=[*bm.verts, *bm.edges, *bm.faces], dist=.00001,
                             plane_co=inverse @ point, plane_no=(obj.matrix_world.to_3x3().transposed() @ normal).normalized(),
                             clear_inner=inner, clear_outer=outer)

    if bottom is not None:
        cut(Vector((0, 0, bottom)), Vector((0, 0, 1)), True, False)
    if top is not None:
        cut(Vector((0, 0, top)), Vector((0, 0, 1)), False, True)
    if cuffs:
        for side in ('l', 'r'):
            hand = bones['hand_' + side]
            forearm = (hand - bones['lowerarm_' + side]).normalized()
            # Cuffs overlap the UV mask boundary at the wrist.
            cut(hand + forearm * .015, forearm, False, True)
    if part == 'Sleeves':
        bmesh.ops.delete(bm, geom=[face for face in bm.faces if abs((obj.matrix_world @ face.calc_center_median()).x) < .219], context='FACES')
        for side in ('l', 'r'):
            sign = 1 if side == 'l' else -1
            side_faces = [face for face in bm.faces if sign * (obj.matrix_world @ face.calc_center_median()).x > .05]
            side_vertices = {vertex for face in side_faces for vertex in face.verts}
            side_edges = {edge for face in side_faces for edge in face.edges}
            normal = Vector((sign, 0, -.31)).normalized()
            xyz = Vector((sign*.245, 0, 1.34))
            bmesh.ops.bisect_plane(bm, geom=[*side_vertices, *side_edges, *side_faces], dist=.00001,
                                   plane_co=inverse @ xyz,
                                   plane_no=(obj.matrix_world.to_3x3().transposed() @ normal).normalized(),
                                   clear_inner=True, clear_outer=False)
    if part == 'Shirt':
        neck_edges = [edge for edge in bm.edges if edge.is_boundary and
                      all((obj.matrix_world @ vert.co).z > 1.40 for vert in edge.verts)]
        if neck_edges:
            first = neck_edges[0]
            start, current = first.verts
            ring = [start, current]
            previous = first
            while current != start:
                next_edge = next(edge for edge in current.link_edges if edge in neck_edges and edge != previous)
                current, previous = next_edge.other_vert(current), next_edge
                if current != start:
                    ring.append(current)
            assert len(ring) == len(neck_edges)
            winding = first.link_loops[0].vert == ring[0] and first.link_loops[0].link_loop_next.vert == ring[1]
            deform = bm.verts.layers.deform.verify()
            neck = obj.vertex_groups.get('spine_05') or obj.vertex_groups.new(name='spine_05')
            original = ring
            for step in range(1, 5):
                blend = step / 4
                inner = []
                for vertex in original:
                    world = obj.matrix_world @ vertex.co
                    angle = math.atan2(world.x, -(world.y + .006))
                    target = Vector((.105*math.sin(angle), -.006-.103*math.cos(angle), 1.508-.009*math.cos(angle)))
                    new = bm.verts.new(inverse @ world.lerp(target, blend))
                    for idx, weight in vertex[deform].items():
                        new[deform][idx] = weight * (1-.8*blend)
                    new[deform][neck.index] = new[deform].get(neck.index, 0) + .8*blend
                    inner.append(new)
                for index in range(len(ring)):
                    k = (index + 1) % len(ring)
                    corners = (ring[k], ring[index], inner[index], inner[k]) if winding else (ring[index], ring[k], inner[k], inner[index])
                    face = bm.faces.new(corners)
                    face.smooth = True
                    uv = bm.loops.layers.uv.active
                    for loop in face.loops:
                        p = obj.matrix_world @ loop.vert.co
                        loop[uv].uv = (.5 + p.x*2.2, .84 + (p.z-1.45)*1.6)
                ring = inner
    if part == 'Boots':
        for vertex in bm.verts:
            point = obj.matrix_world @ vertex.co
            if point.y < -.080:
                # A broad shoe toe box smooths the source body silhouette over the toes.
                bend = min(1, (-point.y-.080) / .10)
                center_x = math.copysign(.142, point.x)
                side = min(1, abs(point.x-center_x)/.075)
                toe_box = -.234 + .052*side*side
                point.y = (1-bend)*point.y + bend*toe_box
                vertex.co = inverse @ point
        bmesh.ops.smooth_vert(bm, verts=[vertex for vertex in bm.verts if (obj.matrix_world @ vertex.co).y < -.095],
                              factor=.45, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bmesh.ops.delete(bm, geom=[edge for edge in bm.edges if not edge.link_faces], context='EDGES')
    bmesh.ops.delete(bm, geom=[vertex for vertex in bm.verts if not vertex.link_faces], context='VERTS')
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.materials.clear()
    obj.data.materials.append(mats[part])
    for polygon in obj.data.polygons:
        polygon.material_index = 0
        polygon.use_smooth = True
    for vertex in obj.data.vertices:
        groups = [(entry.group, entry.weight) for entry in vertex.groups if entry.weight > .0001]
        total = sum(weight for _, weight in groups)
        assert total > .01, (part, vertex.index)
        for group, weight in groups:
            obj.vertex_groups[group].add([vertex.index], weight / total, 'REPLACE')
    return obj


def sleeve_cut(point):
    return abs(point.x) > .15


def shirt_cut(point):
    return abs(point.x) < .36


garments = {
    'Shirt': crop_skin('Shirt', shirt_cut, .013, bottom=.955, top=1.543),
    'Trousers': crop_skin('Trousers', lambda point: abs(point.x) < .24, .012, bottom=.13, top=.985),
    'Boots': crop_skin('Boots', lambda point: abs(point.x) < .25, .017, top=.19),
    'Sleeves': crop_skin('Sleeves', sleeve_cut, .023, top=1.565, cuffs=True),
}


def fit_drape():
    source_path = ART / 'Wizard_Travel_Cloak_Projection.glb'
    bpy.ops.import_scene.gltf(filepath=str(source_path))
    source = next(item for item in bpy.context.selected_objects if item.type == 'MESH')
    source.name = 'Image reconstructed cloak source'
    source.hide_render = True
    source.hide_set(True)
    source_vertices = [source.matrix_world @ v.co for v in source.data.vertices]
    source_tree = BVHTree.FromPolygons(source_vertices, [tuple(p.vertices) for p in source.data.polygons], all_triangles=True)
    body_tree = BVHTree.FromPolygons(coords, [tuple(p.vertices) for p in BODY.data.polygons], all_triangles=True)
    shirt = garments['Shirt']
    shirt_tree = BVHTree.FromPolygons([shirt.matrix_world @ vertex.co for vertex in shirt.data.vertices],
                                     [tuple(poly.vertices) for poly in shirt.data.polygons])
    across, rows = 60, 44
    vertices, faces, weights = [], [], []
    sampled = 0
    for i in range(rows + 1):
        depth = i / rows
        taper = depth ** 1.4
        for j in range(across + 1):
            s = j / across
            start = 1.97 + .22 * math.exp(-depth * 8)
            if MANTLE:
                upper = min(1, depth / .19)
                start = 1.25 + .76 * upper*upper*(3-2*upper)
            angle = start + (math.tau - 2 * start) * s
            direction = Vector((math.sin(angle), -math.cos(angle), 0))
            side = abs(direction.x)
            top = 1.49 + .045 * (1-side) - .046 * side
            bottom = .145 + .025 * side ** 3
            if MANTLE:
                # Bring the narrow top of the cape around the back of the neck
                # and over each shoulder. The entire mantle is pinned in Chaos.
                top = 1.535 + .019 * (1-side)
                z = top + (bottom - top) * depth
                if depth < .15:
                    z -= .021 * side * math.sin(math.pi * depth / .19)
            else:
                z = top + (bottom - top) * depth
            origin = Vector((0, -.014, z))
            # Reconstruct one continuous mid-surface from radial measurements on
            # the generated coat. Use fitted upper-body clearance for the yoke.
            reference_origin = Vector((0, -.025, .61 - 1.57 * depth))
            hit, _, _, _ = source_tree.ray_cast(reference_origin + direction * .8, -direction, .8)
            source_width = .34 + .23 * taper
            source_depth = .24 + .095 * taper
            ref_expected = 1 / math.hypot(direction.x / source_width, direction.y / source_depth)
            variation = 0
            if hit is not None:
                sampled += 1
                variation = min(.085, max(-.075, ((hit - reference_origin).dot(direction) - ref_expected) * .42))
            radius_x = .211 + .188 * taper
            radius_y = (.166 if direction.y < 0 else .195) + .122 * taper
            fitted = 1 / math.hypot(direction.x / radius_x, direction.y / radius_y)
            radius = fitted + variation * (.22 + .78 * min(1, depth * 5))
            body_hit, _, _, _ = body_tree.ray_cast(origin + direction * .35, -direction, .35)
            if body_hit is not None and abs(body_hit.x) < .215:
                radius = max(radius, (body_hit - origin).dot(direction) + .045)
            if depth < .20:
                radius -= .020 * side ** 3 * (1 - depth / .20)
            if MANTLE:
                shoulder = min(1, depth / .11)
                yoke_radius = .105 + .135 * math.sin(shoulder*math.pi/2)
                if depth < .11:
                    radius = min(radius, yoke_radius)
                if depth < .23:
                    shirt_hit, _, _, _ = shirt_tree.ray_cast(origin + direction * .33, -direction, .33)
                    if shirt_hit is not None and abs(shirt_hit.x) < .23:
                        radius = max(radius, (shirt_hit - origin).dot(direction) + .028)
                    radius += .012 * (1-depth/.23)
            vertices.append(origin + direction * radius)
            clavicle = .36 * side * max(0, 1 - depth / .18)
            if MANTLE:
                clavicle = .77 * side ** 1.7 * max(0, 1 - depth / .25)
            weights.append({'spine_05': 1-clavicle, ('clavicle_l' if direction.x > 0 else 'clavicle_r'): clavicle})
            if i < rows and j < across:
                a = i * (across+1) + j
                faces.append((a, a+across+1, a+across+2, a+1))
    mesh = bpy.data.meshes.new('One image-derived continuous cape surface')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    cloak = bpy.data.objects.new('SK_HeroTravel_Drape', mesh)
    bpy.context.scene.collection.objects.link(cloak)
    mesh.materials.append(mats['Drape'])
    uv = mesh.uv_layers.new(name='CloakUV')
    for loop in mesh.loops:
        row, column = divmod(loop.vertex_index, across+1)
        uv.data[loop.index].uv = (column / across, row / rows)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    groups = {name: cloak.vertex_groups.new(name=name) for name in ('spine_05', 'clavicle_l', 'clavicle_r')}
    for index, row_weights in enumerate(weights):
        for name, value in row_weights.items():
            if value > 0:
                groups[name].add([index], value, 'REPLACE')
    cloak.parent = RIG
    cloak.matrix_parent_inverse = RIG.matrix_world.inverted()
    cloak.matrix_world = Matrix.Identity(4)
    cloak.modifiers.new('MetaHuman body pose', 'ARMATURE').object = RIG
    assert sampled > 0.75 * len(vertices), sampled
    garments['Drape'] = cloak
    return {'source_vertices': len(source_vertices), 'projected_vertices': sampled, 'panel_vertices': len(vertices)}


def write_body_mask():
    # Take the boundary from the native wrist and leave a narrow neck margin to
    # meet the separate facial mesh. All outer arm, torso, leg and foot skin is hidden.
    visible = np.array([
        point.z >= 1.510 or
        (abs(point.x) > .37 and wrist_distance(point, 'l' if point.x > 0 else 'r') > -.006)
        for point in coords
    ], dtype=np.float32)
    mesh = BODY.data
    mesh.calc_loop_triangles()
    uv = mesh.uv_layers.active.data
    size = 2048
    values = np.full((size, size), np.nan, dtype=np.float32)
    for triangle in mesh.loop_triangles:
        points = [(uv[index].uv.x % 1 * size, uv[index].uv.y % 1 * size) for index in triangle.loops]
        (x0, y0), (x1, y1), (x2, y2) = points
        xa, xb = max(0, int(min(x0, x1, x2)) - 1), min(size, int(max(x0, x1, x2)) + 2)
        ya, yb = max(0, int(min(y0, y1, y2)) - 1), min(size, int(max(y0, y1, y2)) + 2)
        denominator = (y1-y2)*(x0-x2)+(x2-x1)*(y0-y2)
        if abs(denominator) < 1e-10 or xa >= xb or ya >= yb:
            continue
        grid_x, grid_y = np.meshgrid(np.arange(xa, xb) + .5, np.arange(ya, yb) + .5)
        a = ((y1-y2)*(grid_x-x2)+(x2-x1)*(grid_y-y2))/denominator
        b = ((y2-y0)*(grid_x-x2)+(x0-x2)*(grid_y-y2))/denominator
        c = 1-a-b
        inside = (a >= -.015) & (b >= -.015) & (c >= -.015)
        va, vb, vc = (visible[index] for index in triangle.vertices)
        values[ya:yb, xa:xb][inside] = (np.clip(a, 0, 1)*va + np.clip(b, 0, 1)*vb + np.clip(c, 0, 1)*vc)[inside]
    for _ in range(12):
        known = ~np.isnan(values)
        total, count = np.zeros_like(values), np.zeros_like(values)
        for delta in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            total += np.roll(np.where(known, values, 0), delta, (0, 1))
            count += np.roll(known, delta, (0, 1))
        grow = ~known & (count > 0)
        values[grow] = total[grow] / count[grow]
    values = np.nan_to_num(values, nan=0.0)
    image = bpy.data.images.new('Travel outfit body opacity', width=size, height=size, alpha=False)
    rgba = np.ones((size, size, 4), dtype=np.float32)
    rgba[:, :, :3] = values[:, :, None]
    image.pixels.foreach_set(rgba.ravel())
    image.filepath_raw = str(STAGING / 'T_HeroTravel_BodyMask.png')
    image.file_format = 'PNG'
    image.save()
    groups = [group.name for group in BODY.vertex_groups]
    results = {}
    for name, prefixes in {
        'hand': ('thumb_', 'index_', 'middle_', 'ring_', 'pinky_', 'hand_'),
        'arm': ('upperarm_', 'lowerarm_'),
        'torso': ('spine_', 'pelvis'),
        'leg': ('thigh_', 'calf_'),
        'foot': ('foot_', 'ball_'),
    }.items():
        vertices = [vertex.index for vertex in BODY.data.vertices
                    if sum(entry.weight for entry in vertex.groups if groups[entry.group].startswith(prefixes)) >= .7]
        results[name] = {'visible': sum(bool(visible[index]) for index in vertices), 'sampled': len(vertices)}
    return results


def export(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    RIG.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(filepath=str(STAGING / (obj.name + '.fbx')), use_selection=True,
                             object_types={'MESH', 'ARMATURE'}, axis_forward='-Z', axis_up='Y',
                             apply_unit_scale=True, add_leaf_bones=False, bake_anim=False, mesh_smooth_type='FACE')


mask = write_body_mask()
projection = fit_drape()

for garment in garments.values():
    export(garment)

scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'STUDIO'
scene.display.shading.color_type = 'MATERIAL'
scene.display.shading.show_cavity = True
scene.display.shading.show_specular_highlight = False
scene.render.resolution_x = 800
scene.render.resolution_y = 1000
scene.render.resolution_percentage = 100
scene.camera.data.type = 'ORTHO'
scene.camera.data.ortho_scale = 2.02
for view, position in {'Front': (.3, -3.7, 1.26), 'Back': (-.4, 3.7, 1.22), 'Side': (3.7, -.2, 1.23)}.items():
    scene.camera.location = position
    scene.camera.rotation_euler = (Vector((0, 0, .87)) - scene.camera.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = str(STAGING / ('Travel_' + view + '.png'))
    bpy.ops.render.render(write_still=True)
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ART / ('Hero_TravelCloak_Mantle.blend' if MANTLE else 'Hero_TravelCloak_Fit.blend')))
(STAGING / 'fitting_report.json').write_text(json.dumps({
    'body_mask': mask,
    'projection': projection,
    'parts': {part: {'vertices': len(obj.data.vertices), 'faces': len(obj.data.polygons)} for part, obj in garments.items()},
}, indent=2))
