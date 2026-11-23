"""Select the covered torso and sleeve caps on the shared source body's UVs.

blender -b -P panel_mask_coverage.py -- FullBody.fbx PanelTunic.fbx output_directory
Then call bake_tunic_coverage.bake(directory, ['Panel'], 'Body', 1).
"""
import json
import sys
from collections import Counter
from pathlib import Path

import bpy
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree


def polygons(reference, garment, output):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(reference))
    body = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
    rig = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
    bpy.ops.import_scene.fbx(filepath=str(garment))
    cloth = next(o for o in bpy.context.selected_objects if o.type == 'MESH')
    points = [cloth.matrix_world @ v.co for v in cloth.data.vertices]
    cloth.data.calc_loop_triangles()
    cloth_tree = BVHTree.FromPolygons(points, [tuple(f.vertices) for f in cloth.data.loop_triangles],
                                     all_triangles=True)
    edge_counts = Counter(tuple(sorted(edge)) for f in cloth.data.polygons for edge in f.edge_keys)
    rim_points = []
    for (i, j), count in edge_counts.items():
        if count == 1:
            steps = max(1, int((points[i] - points[j]).length / .002) + 1)
            rim_points.extend(points[i].lerp(points[j], k/steps) for k in range(steps))
    assert rim_points
    rim = KDTree(len(rim_points))
    for i, p in enumerate(rim_points):
        rim.insert(p, i)
    rim.balance()
    bones = {b.name: rig.matrix_world @ b.head_local for b in rig.data.bones}
    skin = [body.matrix_world @ v.co for v in body.data.vertices]
    normal_matrix = body.matrix_world.to_3x3().inverted().transposed()
    eligible = []
    for v, p in zip(body.data.vertices, skin):
        dominant = max(v.groups, key=lambda g:g.weight, default=None)
        bone = body.vertex_groups[dominant.group].name if dominant else ''
        side = 'l' if p.x >= 0 else 'r'
        axis = bones['lowerarm_'+side]-bones['upperarm_'+side]
        along_arm = (p-bones['upperarm_'+side]).dot(axis)/axis.length_squared
        core = bone.startswith(('spine','pelvis','clavicle')) and abs(p.x)<abs(bones['upperarm_l'].x)+.03
        sleeve_cap = bone.startswith('upperarm') and along_arm < .26
        inside = ((core or sleeve_cap) and
                  bones['pelvis'].z + .045 < p.z < bones['neck_01'].z - .065 and
                  rim.find(p)[2] > .045)
        if inside:
            normal = (normal_matrix @ v.normal).normalized()
            hit, _, _, _ = cloth_tree.ray_cast(p - normal*.014, normal, .08)
            inside = hit is not None and rim.find(hit)[2] > .045
        eligible.append(inside)
    body.data.calc_loop_triangles()
    uv = body.data.uv_layers.active.data
    covered = [[list(uv[i].uv) for i in f.loops] for f in body.data.loop_triangles
               if all(eligible[i] for i in f.vertices)]
    assert covered
    (output/'mask_uv_Panel.json').write_text(json.dumps(covered))
    print(f'{len(covered)} covered source triangles')


if __name__ == '__main__':
    polygons(*map(Path, sys.argv[sys.argv.index('--')+1:]))
