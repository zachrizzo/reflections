"""joint_angles.py - where do the animations sit inside each physics joint's limits?

For every constraint of PA_PATH and a few clips, the child's rotation relative to its parent body (from the clip;
bone rotations are the same on every MetaHuman body) is put into the joint's frames and split into swing1 (about Z),
swing2 (about Y) and twist (about X), then compared with the joint's limits. Editor only, no PIE.
"""
import json
import math

PA_PATH = globals().get('PA_PATH', '/Game/Physics/ActiveRagdollTest/PHYS_Hero_ActiveRagdoll')
LOCO = '/Game/Characters/Hero/Animation/Locomotion/'
CLIPS = globals().get('CLIPS', [('idle', LOCO + 'AS_Hero_Idle', 0.0), ('idle_3s', LOCO + 'AS_Hero_Idle', 3.0),
                                ('walk', LOCO + 'AS_Hero_Walk', 0.5), ('cast', LOCO + 'AS_Hero_Fire', 1.5)])
W = unreal.AnimPoseSpaces.WORLD
opt = unreal.AnimPoseEvaluationOptions()


def vec(d):
    return unreal.Vector(float(d['x']), float(d['y']), float(d['z']))


def frame_quat(pri, sec):
    return unreal.MathLibrary.make_rot_from_xy(pri, sec).quaternion()


def swing_twist(q):
    if q.w < 0.0:
        q = unreal.Quat(-q.x, -q.y, -q.z, -q.w)
    twist = math.degrees(2.0 * math.atan2(q.x, q.w))
    tq = unreal.Quat(q.x, 0.0, 0.0, q.w)
    n = math.sqrt(tq.x * tq.x + tq.w * tq.w) or 1.0
    tq = unreal.Quat(tq.x / n, 0.0, 0.0, tq.w / n)
    s = q * tq.inversed()
    sw1 = math.degrees(2.0 * math.atan2(s.z, s.w))  # about Z
    sw2 = math.degrees(2.0 * math.atan2(s.y, s.w))  # about Y
    return round(sw1, 1), round(sw2, 1), round(twist, 1)


pa = unreal.load_asset(PA_PATH)
joints = []
for i in range(0, 200):
    o = unreal.find_object(pa, 'PhysicsConstraintTemplate_' + str(i))
    if not o:
        continue
    keys = ['DefaultInstance.ConstraintBone1', 'DefaultInstance.ConstraintBone2', 'DefaultInstance.PriAxis1', 'DefaultInstance.SecAxis1',
            'DefaultInstance.PriAxis2', 'DefaultInstance.SecAxis2', 'DefaultInstance.ProfileInstance.ConeLimit', 'DefaultInstance.ProfileInstance.TwistLimit']
    g = await call_tool('EditorToolset.ObjectToolset.GetProperties', instance={'refPath': o.get_path_name()}, properties=keys)
    g = json.loads(g) if isinstance(g, str) else g
    cl, tl = g['DefaultInstance.ProfileInstance.ConeLimit'], g['DefaultInstance.ProfileInstance.TwistLimit']
    joints.append({'obj': o.get_path_name(), 'child': g['DefaultInstance.ConstraintBone1'], 'parent': g['DefaultInstance.ConstraintBone2'],
                   'f1': frame_quat(vec(g['DefaultInstance.PriAxis1']), vec(g['DefaultInstance.SecAxis1'])),
                   'f2': frame_quat(vec(g['DefaultInstance.PriAxis2']), vec(g['DefaultInstance.SecAxis2'])),
                   'lim': (cl['swing1LimitDegrees'], cl['swing2LimitDegrees'], tl['twistLimitDegrees']),
                   'mot': (cl['swing1Motion'][4:7], cl['swing2Motion'][4:7], tl['twistMotion'][4:7])})
out = {}
skel = unreal.load_asset(CLIPS[0][1]).get_editor_property('skeleton')
poses = [('ref_pose', unreal.AnimPoseExtensions.get_reference_pose(skel))]
for tag, path, t in CLIPS:
    poses.append((tag, unreal.AnimPoseExtensions.get_anim_pose_at_time(unreal.load_asset(path), t, opt)))
for j in joints:
    k = '%s<-%s' % (j['parent'], j['child'])
    row = {'limits_s1_s2_tw': j['lim'], 'motion': j['mot']}
    for tag, pose in poses:
        qp = unreal.AnimPoseExtensions.get_bone_pose(pose, j['parent'], W).rotation
        qc = unreal.AnimPoseExtensions.get_bone_pose(pose, j['child'], W).rotation
        qrel = qp.inversed() * qc
        qj = j['f2'].inversed() * qrel * j['f1']
        row[tag] = swing_twist(qj)
    out[k] = row
json.dumps(out)
