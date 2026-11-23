"""rel_test.py - what offset does each joint actually hold in game?

For each physics-asset joint, the child bone's position in its parent body's bone frame:
  - 'anim':  a plain BP_Hero playing AS_Hero_Idle (what the animation wants),
  - 'phys':  the ar_proto Hero in STAND (what the simulated joint enforces),
  - 'mesh_ref': the Body mesh's own reference pose (GetRefPoseTransform), composed through the bones in between.
Compare with the physics asset's Pos2 values.
"""
import builtins
import math

import unreal

import ar_proto as AR

T = builtins.__dict__.setdefault('_AR_REL', {})
CS = unreal.RelativeTransformSpace.RTS_COMPONENT
JOINTS = [('pelvis', 'spine_02'), ('spine_02', 'spine_04'), ('spine_04', 'neck_01'), ('neck_01', 'head'), ('spine_04', 'head'),
          ('spine_04', 'clavicle_l'), ('clavicle_l', 'upperarm_l'), ('upperarm_l', 'lowerarm_l'), ('pelvis', 'thigh_l')]


def start():
    T.clear()
    builtins.__dict__.setdefault('_AR_P_OVERRIDE', {})['start_dormant'] = False
    AR.P['start_dormant'] = False  # stay in STAND: the measurement is what the simulated joints hold
    AR.enter_stand()
    h = AR.S['hero']
    base = h.get_actor_location()
    cls = unreal.load_class(None, AR.HERO_BP + '.BP_Hero_C')
    ref = AR.spawn(cls, AR.V(base.x + 260.0, base.y, base.z), h.get_actor_rotation().yaw)
    ref.tags = list(ref.tags) + [AR.TAG]
    rb = [c for c in ref.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == 'Body'][0]
    idle = AR.load(AR.ANIM['idle'])
    rb.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
    rb.play_animation(idle, True)
    AR.play('idle', loop=True)
    T['ref_body'] = rb
    T['done'] = False
    return {'ref': ref.get_name()}


def rel(b, parent, child):
    pt = b.get_socket_transform(parent, CS)
    ct = b.get_socket_transform(child, CS)
    p = pt.inverse_transform_location(ct.translation)
    return [round(p.x, 2), round(p.y, 2), round(p.z, 2)]


def mesh_ref(b, parent, child):
    """Child position in the parent's frame from the mesh reference pose (local transforms composed)."""
    chain = []
    bn = child
    while bn and bn != parent:
        chain.append(bn)
        bn = str(b.get_parent_bone(bn))
        if bn in ('None', ''):
            return None
    xf = unreal.Transform()
    for c in reversed(chain):
        local = b.get_ref_pose_transform(b.get_bone_index(c))
        xf = local * xf  # UE order: child local * parent-accumulated
    t = xf.translation
    return [round(t.x, 2), round(t.y, 2), round(t.z, 2)]


def rel_rot(b, parent, child):
    pt = b.get_socket_transform(parent, CS)
    ct = b.get_socket_transform(child, CS)
    return pt.rotation.inversed() * ct.rotation  # child rotation in the parent frame (UE: A * B applies B first)


def rot_diff(qa, qp):
    """(total angle, twist about local X) of qp relative to qa, degrees."""
    d = qa.inversed() * qp
    w = max(-1.0, min(1.0, abs(d.w)))
    total = math.degrees(2.0 * math.acos(w))
    tw = math.degrees(2.0 * math.atan2(d.x, d.w))
    tw = (tw + 180.0) % 360.0 - 180.0
    return round(total, 1), round(tw, 1)


def get():
    rb, pb = T['ref_body'], AR.body()
    out = {}
    for p, c in JOINTS:
        k = '%s<-%s' % (p, c)
        out[k] = {'anim': rel(rb, p, c), 'phys': rel(pb, p, c), 'mesh_ref': mesh_ref(rb, p, c),
                  'rot_diff_total_twist': rot_diff(rel_rot(rb, p, c), rel_rot(pb, p, c))}
    # the control component's view: control names/settings for the neck and head, and its cached (target) bone
    # orientations against the plain animation (same actor yaw, so world rotations compare directly)
    c = AR.pcc()
    ctl = {}
    for st in ('ParentSpace_Head', 'ParentSpace_ArmLeft', 'ParentSpace_ArmRight', 'WorldSpace_ArmLeft', 'ParentSpace_Spine'):
        for n in c.get_control_names_in_set(st):
            d = c.get_control_data(n)
            ctl[str(n)] = {'set': st, 'enabled': c.get_control_enabled(n),
                           'data': {k: getattr(d, k) for k in ('angular_strength', 'linear_strength', 'use_skeletal_animation',
                                                                'use_acceleration_drive_mode', 'only_control_child_object',
                                                                'use_custom_control_point')} if d else None}
    out['controls'] = ctl
    cached = {}
    for bn in ('spine_02', 'spine_04', 'neck_01', 'head'):
        cq = c.get_cached_bone_transform(pb, bn).rotation
        aq = rb.get_socket_transform(bn).rotation
        pq = pb.get_socket_transform(bn).rotation
        cached[bn] = {'cached_vs_anim_deg': rot_diff(aq, cq)[0], 'phys_vs_anim_deg': rot_diff(aq, pq)[0], 'cached_vs_phys_deg': rot_diff(pq, cq)[0]}
    out['cached'] = cached
    out['mesh'] = rb.get_skinned_asset().get_path_name() if hasattr(rb, 'get_skinned_asset') else str(rb.get_editor_property('skeletal_mesh_asset'))
    out['state'] = AR.S.get('state')
    T['results'] = out
    T['done'] = True
    return out


# ---------------------------------------------------------------------------------------------- neck A/B
AB = [('base', {}), ('head_x4', {'mult': {'Head': 4.0}}), ('no_collision', {'coll': True}), ('no_gravity', {'grav': 0.0}),
      ('all_x4', {'mult_all': 4.0})]
AB_JOINTS = [('spine_04', 'neck_01'), ('neck_01', 'head'), ('spine_04', 'clavicle_l'), ('clavicle_l', 'upperarm_l')]


def ab_start(hold=2.0, measure=0.6):
    r = start()
    T['ab'] = {'i': -1, 'hold': hold, 'measure': measure, 'rows': {}, 't0': 0.0}
    _ab_next()
    T['tick'] = unreal.register_slate_post_tick_callback(_ab_tick)
    T['done'] = False
    return r


def _ab_apply(opts):
    c = AR.pcc()
    AR.S['applied'] = {}
    c.set_body_modifiers_in_set_collision_type('All', unreal.CollisionEnabled.QUERY_ONLY if opts.get('coll') else unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    c.set_body_modifiers_in_set_gravity_multiplier('All', opts.get('grav', 1.0))
    AR.apply_strengths(mult_all=opts.get('mult_all', 1.0), mult=opts.get('mult'))


def _ab_next():
    ab = T['ab']
    ab['i'] += 1
    if ab['i'] >= len(AB):
        T['done'] = True
        _ab_stop()
        return
    _ab_apply(AB[ab['i']][1])
    ab['t0'] = unreal.GameplayStatics.get_time_seconds(AR.world())
    ab['acc'] = {'%s<-%s' % j: [] for j in AB_JOINTS}


def _ab_tick(dt):
    try:
        ab = T['ab']
        t = unreal.GameplayStatics.get_time_seconds(AR.world()) - ab['t0']
        if t >= ab['hold'] - ab['measure']:
            rb, pb = T['ref_body'], AR.body()
            for p, c in AB_JOINTS:
                ab['acc']['%s<-%s' % (p, c)].append(rot_diff(rel_rot(rb, p, c), rel_rot(pb, p, c)))
        if t >= ab['hold']:
            name = AB[ab['i']][0]
            ab['rows'][name] = {k: [round(sum(v[i] for v in vs) / len(vs), 1) for i in range(2)] if vs else None for k, vs in ab['acc'].items()}
            _ab_next()
    except Exception as e:
        T['error'] = repr(e)
        T['done'] = True
        _ab_stop()


def _ab_stop():
    h = T.pop('tick', None)
    if h is not None:
        unreal.unregister_slate_post_tick_callback(h)
