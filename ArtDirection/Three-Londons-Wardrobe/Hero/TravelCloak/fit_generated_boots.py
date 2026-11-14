"""Fit an actual Hunyuan reconstruction to both of the hero's native feet."""

import json
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree


ART = Path(__file__).resolve().parent
ROOT = ART.parents[3] / 'Intermediate/TravelCloak'
body = bpy.data.objects['Native MetaHuman fitting body']
rig = next(mod.object for mod in body.modifiers if mod.type == 'ARMATURE')
rig.hide_set(False)
points = [body.matrix_world @ vertex.co for vertex in body.data.vertices]
body.data.calc_loop_triangles()
triangles = [tuple(row.vertices) for row in body.data.loop_triangles]
body_tree = BVHTree.FromPolygons(points, triangles, all_triangles=True)
group_names = [entry.name for entry in body.vertex_groups]

prior = bpy.data.objects.get('SK_HeroTravel_Boots')
if prior:
    prior.hide_render = True
    prior.hide_set(True)
material = prior.data.materials[0]
bpy.ops.import_scene.gltf(filepath=str(ART / 'Hero_BlackBoot_Projection.glb'))
boot = next(obj for obj in bpy.context.selected_objects if obj.type == 'MESH')
boot.name = 'Image reconstructed boot source'
source_count = len(boot.data.vertices)
bpy.context.view_layer.objects.active = boot
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bm = bmesh.new()
bm.from_mesh(boot.data)
remaining = set(bm.verts)
components = []
while remaining:
    group = [remaining.pop()]
    for vertex in group:
        for edge in vertex.link_edges:
            other = edge.other_vert(vertex)
            if other in remaining:
                remaining.remove(other)
                group.append(other)
    components.append(group)
components.sort(key=len, reverse=True)
bmesh.ops.delete(bm, geom=[v for group in components[1:] for v in group], context='VERTS')
bm.to_mesh(boot.data)
bm.free()
reduce = boot.modifiers.new('Preserve generated footwear silhouette', 'DECIMATE')
reduce.ratio = .016
bpy.ops.object.modifier_apply(modifier=reduce.name)
raw = [vert.co.copy() for vert in boot.data.vertices]
faces = [tuple(polygon.vertices) for polygon in boot.data.polygons]
low = [min(point[i] for point in raw) for i in range(3)]
high = [max(point[i] for point in raw) for i in range(3)]
shaft = [p for p in raw if p.z > high[2] - .15]
shaft_mid_x = (max(p.x for p in shaft) + min(p.x for p in shaft)) * .5
shaft_mid_y = (max(p.y for p in shaft) + min(p.y for p in shaft)) * .5
boot.hide_render = True
boot.hide_set(True)


def weights(position):
    hit, _, face_index, _ = body_tree.find_nearest(position)
    triangle = triangles[face_index]
    a, b, c = [points[i] for i in triangle]
    u, v, r = b-a, c-a, hit-a
    uu, uv, vv = u.dot(u), u.dot(v), v.dot(v)
    denominator = uu*vv-uv*uv
    s = (vv*u.dot(r)-uv*v.dot(r))/denominator if abs(denominator) > 1e-12 else 0
    t = (uu*v.dot(r)-uv*u.dot(r))/denominator if abs(denominator) > 1e-12 else 0
    barycentric = [max(0, 1-s-t), max(0, s), max(0, t)]
    output = {}
    for index, blend in zip(triangle, barycentric):
        for influence in body.data.vertices[index].groups:
            name = group_names[influence.group]
            output[name] = output.get(name, 0) + blend * influence.weight
    biggest = sorted(output.items(), key=lambda item: item[1], reverse=True)[:8]
    total = sum(value for _, value in biggest)
    return {name: value/total for name, value in biggest if value > 0}


positions, combined_faces, skin = [], [], []
fit = {}
for side, mirror in [('l', 1), ('r', -1)]:
    ankle = rig.matrix_world @ rig.data.bones['foot_' + side].head_local
    ball = rig.matrix_world @ rig.data.bones['ball_' + side].head_local
    forward = (ball - ankle)
    forward.z = 0
    forward.normalize()
    across = Vector((-forward.y, forward.x, 0))
    body_foot = [p for p in points if p.x*mirror > .03 and p.z < .115]
    rear = min((p - ankle).dot(forward) for p in body_foot) - .009
    toe = max((p - ankle).dot(forward) for p in body_foot) + .014
    side_min = min((p-ankle).dot(across) for p in body_foot)
    side_max = max((p-ankle).dot(across) for p in body_foot)
    width = side_max-side_min + .020
    foot_mid_side = (side_max+side_min)/2
    height = .177
    base = min(p.z for p in body_foot) - .006
    fit[side] = {'foot_length_m': round(toe-rear-.023, 4), 'boot_length_m': round(toe-rear, 4),
                 'boot_width_m': round(width, 4), 'boot_height_m': height}
    cumulative = len(positions)
    for p in raw:
        # Use the generated heel-to-toe surface and align its cuff to the ankle.
        # Width remains generous only around the ankle where the trousers enter.
        dist = toe + (rear-toe) * ((p.x-low[0])/(high[0]-low[0]))
        z_fraction = (p.z-low[2])/(high[2]-low[2])
        bottom_expansion = 1 + .12 * max(0, 1-z_fraction/.36)
        centered = (p.y-shaft_mid_y) * width/(high[1]-low[1]) * mirror * bottom_expansion
        centered += foot_mid_side * max(0, 1-z_fraction/.72)
        reference_shaft = toe + (rear-toe) * ((shaft_mid_x-low[0])/(high[0]-low[0]))
        adjust = min(1, z_fraction ** 2 * 1.40)
        pos = ankle + forward * (dist - reference_shaft*adjust) + across * centered
        pos.z = base + z_fraction * height
        longitudinal = (pos-ankle).dot(forward)
        if pos.z < .095:
            # Correct clearance against the fitted foot cross section while
            # retaining the model's sole, toe profile and shaft folds.
            center = ankle + forward * longitudinal + across * foot_mid_side
            center.z = .030
            radial = pos-center
            if radial.length > .004 and abs(radial.normalized().z) < .95:
                direction = radial.normalized()
                outer, _, _, _ = body_tree.ray_cast(center+direction*.16, -direction, .16)
                if outer is not None and outer.x*mirror > .03:
                    distance = (outer-center).dot(direction)
                    if distance > radial.length-.006:
                        gain = min(.022, distance+.006-radial.length)
                        pos += direction * gain
        positions.append(pos)
        skin.append(weights(pos))
    # The mirrored transform flips winding on the opposite side.
    flip = mirror < 0
    combined_faces.extend(tuple(cumulative+i for i in (reversed(face) if flip else face)) for face in faces)

mesh = bpy.data.meshes.new('Image reconstructed foot-fitted pair')
mesh.from_pydata(positions, [], combined_faces)
mesh.update()
pair = bpy.data.objects.new('SK_HeroTravel_GeneratedBoots', mesh)
bpy.context.scene.collection.objects.link(pair)
mesh.materials.append(material)
uv = mesh.uv_layers.new(name='BootMaterialUV')
for loop in mesh.loops:
    local = raw[loop.vertex_index % len(raw)]
    uv.data[loop.index].uv = ((local.x-low[0])/(high[0]-low[0]), (local.z-low[2])/(high[2]-low[2]))
for face in mesh.polygons:
    face.use_smooth = True
groups = {}
for index, influence in enumerate(skin):
    assert abs(sum(influence.values()) - 1) < .001
    for name, value in influence.items():
        if name not in groups:
            groups[name] = pair.vertex_groups.new(name=name)
        groups[name].add([index], value, 'REPLACE')
pair.parent = rig
pair.matrix_parent_inverse = rig.matrix_world.inverted()
pair.matrix_world = Matrix.Identity(4)
pair.modifiers.new('MetaHuman footwear weights', 'ARMATURE').object = rig

bpy.ops.object.select_all(action='DESELECT')
rig.select_set(True)
pair.select_set(True)
bpy.context.view_layer.objects.active = pair
bpy.ops.export_scene.fbx(filepath=str(ROOT / 'SK_HeroTravel_Boots.fbx'), use_selection=True,
                         object_types={'MESH', 'ARMATURE'}, axis_forward='-Z', axis_up='Y',
                         apply_unit_scale=True, add_leaf_bones=False, bake_anim=False, mesh_smooth_type='FACE')
scene = bpy.context.scene
for view, camera in {'Front': (.56,-1.30,.43), 'Side': (1.5,-.15,.25)}.items():
    scene.camera.location = camera
    scene.camera.data.ortho_scale = .61
    scene.camera.rotation_euler = (Vector((0,-.07,.15))-scene.camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath = str(ROOT / ('GeneratedBoots_' + view + '.png'))
    bpy.ops.render.render(write_still=True)
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ART / 'Hero_TravelCloak_GeneratedBoots.blend'))
(ROOT / 'generated_boot_fit.json').write_text(json.dumps({'source_vertices': source_count,
    'source_components': [len(component) for component in components[:10]], 'base_vertices_per_boot': len(raw),
    'target_fit': fit, 'pair_vertices': len(positions), 'pair_faces': len(combined_faces)}, indent=2))
