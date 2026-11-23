"""snap_frames.py - re-snap a physics asset's joint frames to a skeletal mesh's own reference pose.

Why: PHYS_MHC_Hero's joints match the shared metahuman_base_skel proportions, but SKM_MHC_Hero_BodyMesh is bigger
(pelvis->spine_02 12.6 cm vs 6.2 cm in the asset, spine_04->neck_01 31.7 vs 25.7, ...). Locked joints then pull the
simulated bodies to the shorter lengths and the spine/arms collapse 15-20 cm as soon as they simulate.

For each constraint Frame1 (child side, in the child bone frame) is kept. Frame2 (parent side) is TRANSFERRED: the
old Frame2 is taken back into the child frame with the skeleton's reference pose (the proportions the asset was made
for) and forward into the parent frame with the mesh's reference pose. Any deliberate angular offset the authors gave
the joint (cone centred off the reference pose) is kept; only the proportions change. 'snap' (the Physics Asset
editor's snap: Frame2 = Frame1 carried by the mesh pose) is reported for comparison.
Run inside the editor (execute_python, async call_tool available).
Globals: PA_PATH (asset to edit), MESH_PATH, APPLY (False = report only).
"""
import json
import math

PA_PATH = globals().get('PA_PATH', '/Game/Physics/ActiveRagdollTest/PHYS_Hero_ActiveRagdoll')
MESH_PATH = globals().get('MESH_PATH', '/Game/Characters/Hero/Assembled/Hero/Body/SKM_MHC_Hero_BodyMesh')
APPLY = globals().get('APPLY', False)
assert PA_PATH.startswith('/Game/Physics/ActiveRagdollTest/'), 'only edit our own copy'

mesh = unreal.load_asset(MESH_PATH)
smc = unreal.SkeletalMeshComponent()          # transient, only used to read the mesh reference skeleton
smc.set_skeletal_mesh_asset(mesh)


def ref_local(bone):
    return smc.get_ref_pose_transform(smc.get_bone_index(bone))


def child_in_parent(parent, child):
    chain, bn = [], child
    while bn != parent:
        chain.append(bn)
        bn = str(smc.get_parent_bone(bn))
        if bn in ('None', ''):
            return None
    xf = unreal.Transform()
    for c in reversed(chain):
        xf = ref_local(c) * xf
    return xf


skel = mesh.get_editor_property('skeleton')
base_pose = unreal.AnimPoseExtensions.get_reference_pose(skel)


def base_local(bone):
    return unreal.AnimPoseExtensions.get_bone_pose(base_pose, bone, unreal.AnimPoseSpaces.LOCAL)


def chain_xf(parent, child, local_fn):
    chain, bn = [], child
    while bn != parent:
        chain.append(bn)
        bn = str(smc.get_parent_bone(bn))
        if bn in ('None', ''):
            return None
    xf = unreal.Transform()
    for c in reversed(chain):
        xf = local_fn(c) * xf
    return xf


def vec(d):
    return unreal.Vector(float(d['x']), float(d['y']), float(d['z']))


def jv(v):
    return {'x': round(v.x, 4), 'y': round(v.y, 4), 'z': round(v.z, 4)}


pa = unreal.load_asset(PA_PATH)
rows = []
for i in range(0, 200):
    o = unreal.find_object(pa, 'PhysicsConstraintTemplate_' + str(i))
    if not o:
        continue
    keys = ['DefaultInstance.ConstraintBone1', 'DefaultInstance.ConstraintBone2', 'DefaultInstance.Pos1', 'DefaultInstance.Pos2',
            'DefaultInstance.PriAxis1', 'DefaultInstance.SecAxis1', 'DefaultInstance.PriAxis2', 'DefaultInstance.SecAxis2']
    g = await call_tool('EditorToolset.ObjectToolset.GetProperties', instance={'refPath': o.get_path_name()}, properties=keys)
    g = json.loads(g) if isinstance(g, str) else g
    child, parent = g['DefaultInstance.ConstraintBone1'], g['DefaultInstance.ConstraintBone2']
    xf = child_in_parent(parent, child)
    xb = chain_xf(parent, child, base_local)
    if xf is None or xb is None:
        rows.append({'joint': '%s<-%s' % (parent, child), 'error': 'parent not an ancestor'})
        continue
    p1, a1, s1 = vec(g['DefaultInstance.Pos1']), vec(g['DefaultInstance.PriAxis1']), vec(g['DefaultInstance.SecAxis1'])
    old2 = vec(g['DefaultInstance.Pos2'])
    oa2, os2 = vec(g['DefaultInstance.PriAxis2']), vec(g['DefaultInstance.SecAxis2'])
    # transfer: parent frame (base proportions) -> child frame -> parent frame (mesh proportions)
    p2 = xf.transform_location(xb.inverse_transform_location(old2))
    a2 = xf.transform_direction(xb.inverse_transform_direction(oa2))
    s2 = xf.transform_direction(xb.inverse_transform_direction(os2))
    snap_a2 = xf.transform_direction(a1)
    base_snap_a2 = xb.transform_direction(a1)
    base_snap_p2 = xb.transform_location(p1)
    row = {'joint': '%s<-%s' % (parent, child), 'old_pos2': jv(old2), 'new_pos2': jv(p2),
           'moved_cm': round((p2 - old2).length(), 2),
           'old_pri2': jv(oa2), 'new_pri2': jv(a2), 'snap_pri2': jv(snap_a2),
           'authored_offset_deg': round(math.degrees(math.acos(max(-1.0, min(1.0, oa2.dot(base_snap_a2))))), 1),
           'old_pos2_vs_base_ref_cm': round((old2 - base_snap_p2).length(), 2),
           'axis_change_deg': round(math.degrees(math.acos(max(-1.0, min(1.0, oa2.dot(a2))))), 1)}
    if APPLY:
        vals = {'DefaultInstance.Pos2': jv(p2), 'DefaultInstance.PriAxis2': jv(a2), 'DefaultInstance.SecAxis2': jv(s2)}
        r = await call_tool('EditorToolset.ObjectToolset.SetProperties', instance={'refPath': o.get_path_name()}, values=json.dumps(vals))
        chk = await call_tool('EditorToolset.ObjectToolset.GetProperties', instance={'refPath': o.get_path_name()}, properties=['DefaultInstance.Pos2'])
        chk = json.loads(chk) if isinstance(chk, str) else chk
        row['after_pos2'] = chk['DefaultInstance.Pos2']
    rows.append(row)
out = {'pa': PA_PATH, 'mesh': MESH_PATH, 'applied': APPLY, 'rows': rows}
if APPLY:
    pa.modify()
    out['saved'] = unreal.EditorLoadingAndSavingUtils.save_packages([pa.get_package()], False)
json.dumps(out, default=str)
