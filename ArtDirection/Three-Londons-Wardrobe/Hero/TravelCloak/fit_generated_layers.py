"""Conform reconstructed garment surfaces to the native hero fitting topology."""

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


ART = Path(__file__).resolve().parent
ROOT = ART.parents[3] / 'Intermediate/TravelCloak'
body = bpy.data.objects['Native MetaHuman fitting body']
rig = next(mod.object for mod in body.modifiers if mod.type == 'ARMATURE')
rig.hide_set(False)


def source(name):
    existing = bpy.data.objects.get('Image reconstructed cloak source') if name == 'Wizard_Travel_Cloak' else None
    if existing:
        obj = existing
    else:
        bpy.ops.import_scene.gltf(filepath=str(ART / (name + '_Projection.glb')))
        obj = next(item for item in bpy.context.selected_objects if item.type == 'MESH')
        obj.name = name + ' raw reconstructed source'
    obj.hide_render = True
    obj.hide_set(True)
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    bounds = [[fn(p[dim] for p in points) for dim in range(3)] for fn in (min, max)]
    return BVHTree.FromPolygons(points, [tuple(poly.vertices) for poly in obj.data.polygons], all_triangles=True), bounds, len(points)


def project_basal(part, object_name, source_name):
    obj = bpy.data.objects[object_name]
    target = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    source_tree, bounds, count = source(source_name)
    (xmin, ymin, zmin), (xmax, ymax, zmax) = bounds
    y_away = max(abs(ymin), abs(ymax)) + .4
    zlo = min(pos.z for pos in target)
    zhi = max(pos.z for pos in target)
    normals = obj.matrix_world.to_3x3().inverted().transposed()
    back = obj.matrix_world.inverted().to_3x3()
    hits = moved = 0
    displacement_mm = []

    def depth(x, z, ysign):
        ray_o = Vector((x, ysign*y_away, z))
        ray_d = Vector((0, -ysign, 0))
        point, _, _, _ = source_tree.ray_cast(ray_o, ray_d, 2*y_away)
        return point.y if point is not None else None

    for i, vertex in enumerate(obj.data.vertices):
        p = target[i]
        normal = (normals @ vertex.normal).normalized()
        ysign = -1 if normal.y < 0 else 1
        blend_z = min(.975, max(.025, (p.z-zlo)/(zhi-zlo)))
        sz = zmin + (zmax-zmin) * blend_z
        middle = (xmin+xmax)*.5
        if part == 'Sleeves':
            # Stretch the source sleeve centerline onto the native wrist axis.
            arm_fraction = min(1, max(0, (abs(p.x)-.20)/.33))
            sz = .69-.63*arm_fraction
            sx = math.copysign(.24+.46*arm_fraction, p.x)
            sx += math.copysign(.025*(p.z-1.38+.37*arm_fraction)/.07, p.x)
        elif part == 'Trousers':
            if blend_z < .80:
                # Preserve separated garment legs even though the source was
                # photographed with different ankle spacing than the body.
                expected_axis = .142-(.142-.106)*blend_z
                center_fraction = .57 - .17*blend_z
                sx = middle + math.copysign(center_fraction*(xmax-xmin)*.5 + (abs(p.x)-expected_axis)*2.0, p.x)
            else:
                sx = middle + p.x * (xmax-xmin)/.39
        else:
            sx = middle + p.x * (xmax-xmin)/.72

        central = depth(sx, sz, ysign)
        if central is None and part == 'Trousers':
            # A narrow inseam or upper hip may fall beyond the source silhouette.
            # Use the closest sampled silhouette point for the local cloth detail.
            for normalized in (.06, -.06, .12, -.12, .18, -.18):
                cx = sx + math.copysign(1, p.x) * normalized * (xmax-xmin)
                central = depth(cx, sz, ysign)
                if central is not None:
                    sx = cx
                    break
        if central is None:
            continue
        hits += 1
        neighbor_width = (xmax-xmin) * .043
        neighbor_height = (zmax-zmin) * .048
        neighbors = [sample for dx, dz in ((neighbor_width, 0),(-neighbor_width, 0),(0, neighbor_height),(0,-neighbor_height))
                     if (sample := depth(sx+dx, sz+dz, ysign)) is not None]
        if len(neighbors) < 3:
            continue
        # The low-frequency volume is fit to the exact MetaHuman. Carry the
        # reconstructed folds and thickness onto that close-fitting surface.
        feature = (central-sum(neighbors)/len(neighbors)) * ysign
        amplitude = min(.009, max(-.004, feature * (.17 if part == 'Sleeves' else .205)))
        fade = min(1, blend_z*12, (1-blend_z)*13)
        factor = max(.23, abs(normal.y)) * fade
        if part == 'Sleeves':
            factor *= min(1, max(0, (abs(p.x)-.21)*9))
        offset = amplitude * factor
        vertex.co += back @ (normal * offset)
        displacement_mm.append(round(offset*1000, 4))
        moved += int(abs(offset) > .0001)
    obj.data.update()
    assert hits > .68 * len(target), (part, hits, len(target))
    assert moved > .24 * len(target), (part, moved, len(target))
    return obj, {'source_vertices': count, 'fit_vertex_count': len(target), 'projected_vertices': hits,
                 'changed_vertices': moved, 'min_offset_mm': min(displacement_mm), 'max_offset_mm': max(displacement_mm)}


report = {}
for part, source_name in [('Shirt', 'Hero_TightShirt'), ('Trousers', 'Hero_TightTrousers'), ('Sleeves', 'Wizard_Travel_Cloak')]:
    obj, stats = project_basal(part, 'SK_HeroTravel_' + part, source_name)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(filepath=str(ROOT / (obj.name + '.fbx')), use_selection=True,
                             object_types={'MESH', 'ARMATURE'}, axis_forward='-Z', axis_up='Y',
                             apply_unit_scale=True, add_leaf_bones=False, bake_anim=False, mesh_smooth_type='FACE')
    report[part] = stats

scene = bpy.context.scene
scene.camera.location = Vector((.62,-3.52,1.26))
scene.camera.rotation_euler = (Vector((0,0,.91))-scene.camera.location).to_track_quat('-Z','Y').to_euler()
scene.camera.data.ortho_scale = 2.03
scene.render.filepath = str(ROOT / 'Travel_GeneratedLayers_Front.png')
bpy.ops.render.render(write_still=True)
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ART / 'Hero_TravelCloak_GeneratedFit.blend'))
(ROOT / 'generated_layers_fit.json').write_text(json.dumps(report, indent=2))
