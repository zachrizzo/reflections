"""widen_limits.py - widen upper-body joint limits of our physics asset copy so normal animations fit inside them.

MetaHuman's limits are tighter than our animations: at idle the shoulders already sit past their 60 deg swing limit,
the spell cast bends elbows/neck past theirs. While reacting, the limits then shove the arms off the animated pose
(a visible pop when physics wakes). For each upper-body joint: sample the clips below, take the largest |swing1|,
|swing2|, |twist| in the joint's own frames, and set limit = max(current, largest + MARGIN), capped per joint kind.
Lower body and the virtual calf->pelvis limits are left alone. Globals: APPLY (False = report only).
Run with joint_angles.py's helpers in the same execute_python call (concatenate joint_angles.py first).
"""
APPLY = globals().get('APPLY', False)
MARGIN = 10.0
ROOT_A = '/Game/Physics/ActiveRagdollTest/Anims/'
SAMPLE = [(LOCO + 'AS_Hero_Idle', 12), (LOCO + 'AS_Hero_Walk', 8), (LOCO + 'AS_Hero_Jog', 8), (LOCO + 'AS_Hero_Fire', 12),
          (LOCO + 'AS_Hero_Healing', 10), (ROOT_A + 'AS_Hero_Run_Stop_B_Lfoot', 8), (ROOT_A + 'AS_Hero_Run_Stop_F_Lfoot', 8),
          (ROOT_A + 'AS_Hero_getup_stand_B', 10), (ROOT_A + 'AS_Hero_getup_stand_F', 10)]
UPPER_PARENTS = ('spine_04', 'clavicle_l', 'clavicle_r', 'upperarm_l', 'upperarm_r', 'lowerarm_l', 'lowerarm_r', 'neck_01')
CAPS = {'clavicle': (45, 45, 40), 'upperarm': (100, 100, 75), 'lowerarm': (25, 20, 90), 'hand': (40, 70, 60),
        'neck_01': (40, 40, 45), 'head': (40, 35, 45)}
assert PA_PATH.startswith('/Game/Physics/ActiveRagdollTest/')
peak = {}
for path, n in SAMPLE:
    seq = unreal.load_asset(path)
    if not seq:
        continue
    L = seq.get_play_length()
    for i in range(n):
        pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(seq, L * i / max(1, n - 1) * 0.999, opt)
        for j in joints:
            if j['parent'] not in UPPER_PARENTS:
                continue
            qp = unreal.AnimPoseExtensions.get_bone_pose(pose, j['parent'], W).rotation
            qc = unreal.AnimPoseExtensions.get_bone_pose(pose, j['child'], W).rotation
            a = swing_twist(j['f2'].inversed() * (qp.inversed() * qc) * j['f1'])
            k = '%s<-%s' % (j['parent'], j['child'])
            pk = peak.setdefault(k, [0.0, 0.0, 0.0, ''])
            for x in range(3):
                if abs(a[x]) > pk[x]:
                    pk[x] = abs(a[x])
                    if x == 0:
                        pk[3] = path.rsplit('/', 1)[1]
res = {}
for j in joints:
    k = '%s<-%s' % (j['parent'], j['child'])
    if k not in peak:
        continue
    cap = next((v for kk, v in CAPS.items() if j['child'].startswith(kk)), (60, 60, 60))
    new = [round(min(cap[x], max(j['lim'][x], peak[k][x] + MARGIN)), 1) for x in range(3)]
    res[k] = {'old': j['lim'], 'peak': [round(v, 1) for v in peak[k][:3]], 'new': new}
    if APPLY and new != list(j['lim']):
        o = j['obj']
        vals = {'DefaultInstance.ProfileInstance.ConeLimit.Swing1LimitDegrees': new[0],
                'DefaultInstance.ProfileInstance.ConeLimit.Swing2LimitDegrees': new[1],
                'DefaultInstance.ProfileInstance.TwistLimit.TwistLimitDegrees': new[2]}
        await call_tool('EditorToolset.ObjectToolset.SetProperties', instance={'refPath': o}, values=json.dumps(vals))
        g = await call_tool('EditorToolset.ObjectToolset.GetProperties', instance={'refPath': o},
                            properties=['DefaultInstance.ProfileInstance.ConeLimit', 'DefaultInstance.ProfileInstance.TwistLimit'])
        g = json.loads(g) if isinstance(g, str) else g
        res[k]['after'] = [g['DefaultInstance.ProfileInstance.ConeLimit']['swing1LimitDegrees'],
                           g['DefaultInstance.ProfileInstance.ConeLimit']['swing2LimitDegrees'],
                           g['DefaultInstance.ProfileInstance.TwistLimit']['twistLimitDegrees']]
if APPLY:
    pa.modify()
    res['_saved'] = unreal.EditorLoadingAndSavingUtils.save_packages([pa.get_package()], False)
json.dumps(res)
