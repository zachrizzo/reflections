"""drift_test.py - does the prototype's STAND state still look like the plain animation?

Spawns a plain BP_Hero (reference: no physics, same clip from the same frame) beside the ar_proto Hero and samples
component-space bone transforms of both every frame. The difference is what the physics adds on top of the
animation: gravity sag of the simulated upper body plus spring lag on fast motion.

Phases: idle, spell cast (AS_Hero_Fire), walk in place, walk while the actors move at walking speed, then the same
with upper-body gravity off, then dormant (all kinematic) as a zero check.
Needs ar_proto.setup() in a Simulate/PIE world. Results land in builtins._AR_DRIFT['results'].
"""
import builtins
import math

import unreal

import ar_proto as AR

D = builtins.__dict__.setdefault('_AR_DRIFT', {})
CS = unreal.RelativeTransformSpace.RTS_COMPONENT
BONES = ['pelvis', 'spine_02', 'thigh_l', 'calf_l', 'spine_04', 'neck_01', 'head', 'upperarm_l', 'lowerarm_l', 'hand_l', 'upperarm_r', 'lowerarm_r', 'hand_r']
LOCO = '/Game/Characters/Hero/Animation/Locomotion/'
CLIPS = {'idle': LOCO + 'AS_Hero_Idle', 'fire': LOCO + 'AS_Hero_Fire', 'walk': AR.ROOT + '/Anims/AS_Hero_Walk_RM'}
WALK_SPEED = 277.0  # AS_Hero_Walk root travel 415.9 cm over 1.5 s
# name, clip, upper-body gravity multiplier, actor speed cm/s, mode, measured seconds, settle seconds (not measured)
PHASES = [
    ('idle', 'idle', 1.0, 0.0, 'stand', 5.0, 1.0),
    ('spell_cast', 'fire', 1.0, 0.0, 'stand', 3.5, 0.3),
    ('walk_in_place', 'walk', 1.0, 0.0, 'stand', 4.5, 0.75),
    ('walk_moving', 'walk', 1.0, WALK_SPEED, 'stand', 3.5, 0.0),
    ('idle_no_gravity', 'idle', 0.0, 0.0, 'stand', 5.0, 1.2),
    ('spell_cast_no_gravity', 'fire', 0.0, 0.0, 'stand', 3.5, 0.3),
    ('walk_in_place_no_gravity', 'walk', 0.0, 0.0, 'stand', 4.5, 0.75),
    ('idle_dormant', 'idle', 1.0, 0.0, 'dormant', 2.0, 0.5),
]
# Second run: same tests after making the control component tick after the Hero's body (tick prerequisite), so its
# animation targets are this frame's animation and not last frame's physics-blended pose.
DIAG_PHASES = [
    ('idle_default_order', 'idle', 1.0, 0.0, 'stand', 3.0, 1.0),
    ('reset_and_fix_order', 'idle', 1.0, 0.0, 'dormant_fix', 0.6, 0.4),
    ('idle_fixed', 'idle', 1.0, 0.0, 'stand', 5.0, 0.0),
    ('spell_cast_fixed', 'fire', 1.0, 0.0, 'stand', 3.5, 0.3),
    ('walk_in_place_fixed', 'walk', 1.0, 0.0, 'stand', 4.5, 0.75),
    ('walk_moving_fixed', 'walk', 1.0, WALK_SPEED, 'stand', 3.5, 0.0),
    ('idle_fixed_no_gravity', 'idle', 0.0, 0.0, 'stand', 4.0, 1.2),
]
TGT_BONES = ['spine_04', 'head', 'hand_r']
# Third run: why does the standing upper body slump? Each variant starts from a fresh animated pose (dormant reset).
_R = ('reset', 'idle', 1.0, 0.0, 'dormant', 0.6, 0.4)
AB_PHASES = [
    _R, ('ab_base', 'idle', 1.0, 0.0, 'stand', 2.0, 2.0, {}),
    _R, ('ab_strength_x4', 'idle', 1.0, 0.0, 'stand', 2.0, 2.0, {'mult': 4.0}),
    _R, ('ab_no_body_collision', 'idle', 1.0, 0.0, 'stand', 2.0, 2.0, {'coll': 'query'}),
    _R, ('ab_no_gravity_from_start', 'idle', 0.0, 0.0, 'stand', 2.0, 2.0, {}),
    _R, ('ab_strength_x4_spell_cast', 'fire', 1.0, 0.0, 'stand', 3.3, 0.5, {'mult': 4.0}),
]
# Fifth run: which constraint pulls spine_02 onto the pelvis? Controls switched off by kind.
CTRL_PHASES = [
    _R, ('ctrl_all_on', 'idle', 1.0, 0.0, 'stand', 1.2, 0.0, {}),
    _R, ('ctrl_all_off', 'idle', 1.0, 0.0, 'stand', 1.2, 0.0, {'ctrl': 'none'}),
    _R, ('ctrl_world_space_off', 'idle', 1.0, 0.0, 'stand', 1.2, 0.0, {'ctrl': 'no_ws'}),
    _R, ('ctrl_parent_space_off', 'idle', 1.0, 0.0, 'stand', 1.2, 0.0, {'ctrl': 'no_ps'}),
]
# Sixth run: pelvis simulated too (held up by the kinematic thighs) so no joint links a kinematic body to the spine.
_PS = {'pelvis_sim': True}
PELVIS_PHASES = [
    _R, ('psim_idle', 'idle', 1.0, 0.0, 'stand', 3.0, 1.0, _PS),
    ('psim_spell_cast', 'fire', 1.0, 0.0, 'stand', 3.5, 0.3, _PS),
    ('psim_walk_in_place', 'walk', 1.0, 0.0, 'stand', 4.5, 0.75, _PS),
    ('psim_walk_moving', 'walk', 1.0, WALK_SPEED, 'stand', 3.5, 0.0, _PS),
    ('psim_idle_after_stop', 'idle', 1.0, 0.0, 'stand', 2.5, 1.0, _PS),
]
# Arm strength sweep (fixed asset): how strong must the arm controls be to follow walking and casting?
_A2 = {'limb_mult': {'ArmLeft': 2.0, 'ArmRight': 2.0}}
_A3 = {'limb_mult': {'ArmLeft': 3.0, 'ArmRight': 3.0}}
_A3H = {'limb_mult': {'ArmLeft': 3.0, 'ArmRight': 3.0, 'Head': 2.0, 'Spine': 1.5}}
ARM_PHASES = [
    ('walk_x1', 'walk', 1.0, 0.0, 'stand', 3.0, 1.0, {}),
    ('walk_arms_x2', 'walk', 1.0, 0.0, 'stand', 3.0, 1.0, _A2),
    ('walk_arms_x3', 'walk', 1.0, 0.0, 'stand', 3.0, 1.0, _A3),
    ('cast_x1', 'fire', 1.0, 0.0, 'stand', 3.5, 0.3, {}),
    ('cast_arms_x2', 'fire', 1.0, 0.0, 'stand', 3.5, 0.3, _A2),
    ('cast_arms_x3', 'fire', 1.0, 0.0, 'stand', 3.5, 0.3, _A3),
    ('cast_arms_x3_head_x2', 'fire', 1.0, 0.0, 'stand', 3.5, 0.3, _A3H),
]
# Relaxed (free) upper-body joint limits while standing: do the arms then follow walking and casting?
_NOELB = tuple(j for j in ('spine_02', 'spine_04', 'neck_01', 'head', 'clavicle_l', 'clavicle_r', 'upperarm_l', 'upperarm_r', 'hand_l', 'hand_r'))
RELAX_PHASES = [
    ('walk_asset_limits', 'walk', 1.0, 0.0, 'stand', 3.0, 1.0, {'relax': False}),
    ('walk_relaxed', 'walk', 1.0, 0.0, 'stand', 3.0, 1.0, {'relax': True}),
    ('walk_relaxed_keep_elbows', 'walk', 1.0, 0.0, 'stand', 3.0, 1.0, {'relax': True, 'relax_joints': _NOELB}),
    ('cast_asset_limits', 'fire', 1.0, 0.0, 'stand', 3.5, 0.3, {'relax': False}),
    ('cast_relaxed', 'fire', 1.0, 0.0, 'stand', 3.5, 0.3, {'relax': True}),
    ('cast_relaxed_keep_elbows', 'fire', 1.0, 0.0, 'stand', 3.5, 0.3, {'relax': True, 'relax_joints': _NOELB}),
    ('idle_relaxed', 'idle', 1.0, 0.0, 'stand', 3.0, 1.0, {'relax': True}),
]
# Do the arms bump the hips/thighs? Same clips with body collision off.
COLL_PHASES = [
    ('walk_collision_on', 'walk', 1.0, 0.0, 'stand', 3.0, 1.0, {}),
    ('walk_collision_off', 'walk', 1.0, 0.0, 'stand', 3.0, 1.0, {'coll': 'query'}),
    ('cast_collision_on', 'fire', 1.0, 0.0, 'stand', 3.5, 0.3, {}),
    ('cast_collision_off', 'fire', 1.0, 0.0, 'stand', 3.5, 0.3, {'coll': 'query'}),
    ('walk_collision_off_arms_x2', 'walk', 1.0, 0.0, 'stand', 3.0, 1.0, {'coll': 'query', 'limb_mult': {'ArmLeft': 2.0, 'ArmRight': 2.0}}),
]
# Sanity: the same clips with the prototype dormant (pure animation) must give zero, or the clips are out of sync.
SYNC_PHASES = [
    ('walk_dormant', 'walk', 1.0, 0.0, 'dormant', 3.0, 1.0),
    ('cast_dormant', 'fire', 1.0, 0.0, 'dormant', 3.5, 0.3),
    ('walk_stand', 'walk', 1.0, 0.0, 'stand', 3.0, 1.0),
]
# Fourth run: where do the physics bodies sit relative to their bones (dormant vs standing)?
COM_BONES = ['pelvis', 'spine_02', 'spine_04', 'head']
BODY_PHASES = [
    ('dormant_ref', 'idle', 1.0, 0.0, 'dormant', 1.0, 0.5),
    ('stand_base', 'idle', 1.0, 0.0, 'stand', 2.0, 1.0),
]


def world():
    return AR.world()


def now():
    return unreal.GameplayStatics.get_time_seconds(world())


def start(ref_offset=(0.0, -260.0, 0.0), phases=None, auto_dormant=False):
    """Spawn the reference Hero beside the prototype and start the phase sequence. auto_dormant=False keeps STAND
    phases in STAND (the prototype otherwise fades back to DORMANT after recovering)."""
    assert AR.body(), 'run ar_proto.setup() first'
    builtins.__dict__.setdefault('_AR_P_OVERRIDE', {})['start_dormant'] = auto_dormant
    AR.P['start_dormant'] = auto_dormant
    stop_tick()
    D.clear()
    hero = AR.S['hero']
    loc = hero.get_actor_location()
    yaw = hero.get_actor_rotation().yaw
    cls = unreal.load_class(None, AR.HERO_BP + '.BP_Hero_C')
    ref = AR.spawn(cls, AR.V(loc.x + ref_offset[0], loc.y + ref_offset[1], loc.z + ref_offset[2]), yaw)
    ref.tags = list(ref.tags) + [AR.TAG]
    rb = [c for c in ref.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == 'Body'][0]
    D['ref'] = ref
    D['ref_body'] = rb
    D['anims'] = {k: AR.load(v) for k, v in CLIPS.items()}
    D['phases'] = list(phases or PHASES)
    D['i'] = -1
    D['results'] = []
    D['done'] = False
    # crate/self hits must not trigger reactions during the measurement
    AR.body().set_notify_rigid_body_collision(False)
    # path check for the moving phase: both actors walk along the mesh facing
    f = AR.body().get_right_vector()
    D['dir'] = (f.x, f.y)
    D['path_clear'] = path_len(hero, ref)
    next_phase()
    D['tick'] = unreal.register_slate_post_tick_callback(_tick)
    return {'ref': ref.get_name(), 'dir': D['dir'], 'path_clear_cm': D['path_clear']}


def path_len(*actors):
    """Free distance ahead of every actor at knee and chest height, capped at 14 m."""
    best = 1400.0
    dx, dy = D['dir']
    for a in actors:
        p = a.get_actor_location()
        gz = AR.S.get('ground_z', p.z)
        for h in (60.0, 140.0):  # knee and chest height above the ground
            s = AR.V(p.x, p.y, gz + h)
            e = AR.V(p.x + dx * 1400.0, p.y + dy * 1400.0, gz + h)
            r = unreal.SystemLibrary.sphere_trace_single(world(), s, e, 35.0, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False,
                                                         [AR.S['hero'], D['ref'], AR.S['control_actor']],
                                                         unreal.DrawDebugTrace.NONE, True)
            if r is None:  # UE Python returns None when the trace's bool result is False (no hit)
                continue
            t = r.to_tuple()  # (blocking, initial_overlap, time, distance, location, ...)
            if t[0]:
                best = min(best, 0.0 if t[1] else float(t[3]))
    return round(best)


def play_both(key):
    a = D['anims'][key]
    mode = unreal.RootMotionMode.ROOT_MOTION_FROM_EVERYTHING if key == 'walk' else unreal.RootMotionMode.ROOT_MOTION_FROM_MONTAGES_ONLY
    for b in (AR.body(), D['ref_body']):
        b.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
        b.play_animation(a, True)
        b.set_play_rate(1.0)
        inst = b.get_anim_instance()
        if inst:
            inst.set_root_motion_mode(mode)
    AR.S['anim'] = key


def next_phase():
    if D['i'] >= 0:
        finish_phase()
    D['i'] += 1
    if D['i'] >= len(D['phases']):
        D['done'] = True
        stop_tick()
        return
    ph = D['phases'][D['i']]
    name, clip, grav, speed, mode, dur, settle = ph[:7]
    opts = ph[7] if len(ph) > 7 else {}
    if speed > 0.0:
        # fit the walk into the free path (keep 1.5 m spare); skip when there is no room
        room = (D['path_clear'] - 150.0) / speed
        if room < 1.5:
            D['results'].append({'phase': name, 'skipped': 'path blocked after %d cm' % D['path_clear']})
            next_phase()
            return
        dur = min(dur, room)
    c = AR.pcc()
    if mode in ('dormant', 'dormant_fix'):
        AR.dormant(True)
        c.set_body_modifiers_in_set_gravity_multiplier('All', 1.0)
        if mode == 'dormant_fix':
            c.add_tick_prerequisite_component(AR.body())
            D['fixed_order'] = True
    else:
        if AR.S.get('state') != 'STAND':
            AR.enter_stand()
        c.set_body_modifiers_in_set_gravity_multiplier('All', grav)
        AR.S['applied'] = {}
        AR.apply_strengths(mult_all=opts.get('mult', 1.0), mult=opts.get('limb_mult'))
        if 'relax' in opts:
            AR.joint_limits(bool(opts['relax']), opts.get('relax_joints', AR.RELAX_JOINTS))
        ct = unreal.CollisionEnabled.QUERY_ONLY if opts.get('coll') == 'query' else unreal.CollisionEnabled.QUERY_AND_PHYSICS
        c.set_body_modifiers_in_set_collision_type('All', ct)
        if opts.get('pelvis_sim'):
            AR.set_bm(AR.bm_for('Spine', 'pelvis'), False)
        kind = opts.get('ctrl')
        if kind:
            for l in AR.LIMBS:
                if kind in ('none', 'no_ws'):
                    c.set_controls_in_set_enabled('WorldSpace_' + l, False)
                if kind in ('none', 'no_ps'):
                    c.set_controls_in_set_enabled('ParentSpace_' + l, False)
    play_both(clip)
    D['cur'] = {'phase': name, 'clip': clip, 'gravity': grav, 'speed': speed, 'mode': mode, 'dur': dur,
                'settle': settle, 't0': now(), 'frames': 0, 'dts': [],
                'acc': {b: {'err': [], 'dz': [], 'ang': []} for b in BONES},
                'ref_pelvis_y': [], 'start_actor': vec(AR.S['hero'].get_actor_location()),
                'tgt': {b: {'vs_anim': [], 'vs_physics': []} for b in TGT_BONES}, 'series': [],
                'com': {b: [] for b in COM_BONES},
                'start_ref': vec(D['ref'].get_actor_location())}


def vec(v):
    return [round(v.x, 1), round(v.y, 1), round(v.z, 1)]


def qangle(a, b):
    d = abs(a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w)
    return math.degrees(2.0 * math.acos(min(1.0, d)))


def _tick(dt):
    try:
        if D.get('done') or not world():
            stop_tick()
            return
        cur = D['cur']
        t = now() - cur['t0']
        wdt = unreal.GameplayStatics.get_world_delta_seconds(world())
        if cur['speed'] > 0.0:
            v = cur['speed'] * min(1.0, t / 0.4)
            dx, dy = D['dir']
            for a in (AR.S['hero'], D['ref']):
                p = a.get_actor_location()
                a.set_actor_location(AR.V(p.x + dx * v * wdt, p.y + dy * v * wdt, p.z), False, False)
        if len(cur['series']) < 400:
            hp = AR.body().get_socket_transform('head', CS).translation.z
            hr = D['ref_body'].get_socket_transform('head', CS).translation.z
            sp = AR.body().get_socket_transform('spine_02', CS).translation.z
            sr = D['ref_body'].get_socket_transform('spine_02', CS).translation.z
            cur['series'].append((round(t, 3), round(hp - hr, 2), round(sp - sr, 2)))
        if t >= cur['settle']:
            sample(cur, wdt)
        if t >= cur['settle'] + cur['dur']:
            next_phase()
    except Exception as e:
        D['error'] = repr(e)
        D['done'] = True
        stop_tick()


def sample(cur, wdt):
    pb, rb = AR.body(), D['ref_body']
    cur['frames'] += 1
    cur['dts'].append(wdt)
    for bn in BONES:
        tp = pb.get_socket_transform(bn, CS)
        tr = rb.get_socket_transform(bn, CS)
        a, b = tp.translation, tr.translation
        dx, dy, dz = a.x - b.x, a.y - b.y, a.z - b.z
        acc = cur['acc'][bn]
        acc['err'].append(math.sqrt(dx * dx + dy * dy + dz * dz))
        acc['dz'].append(dz)
        acc['ang'].append(qangle(tp.rotation, tr.rotation))
    cur['ref_pelvis_y'].append(rb.get_socket_transform('pelvis', CS).translation.y)
    # body centre of mass relative to its bone, in the component frame (world offset rotated by the actor yaw)
    yaw = math.radians(AR.S['hero'].get_actor_rotation().yaw)
    for bn in COM_BONES:
        try:
            cm = pb.get_center_of_mass(bn)
        except Exception as e:
            D['com_error'] = repr(e)
            break
        bl = pb.get_socket_location(bn)
        dx, dy, dz = cm.x - bl.x, cm.y - bl.y, cm.z - bl.z
        cur['com'][bn].append((dx * math.cos(-yaw) - dy * math.sin(-yaw), dx * math.sin(-yaw) + dy * math.cos(-yaw), dz))
    # where the control component thinks the animation is (its cached bone transforms, world space)
    off = vsub3(AR.S['hero'].get_actor_location(), D['ref'].get_actor_location())
    for bn in TGT_BONES:
        try:
            tg = AR.pcc().get_cached_bone_transform(pb, bn).translation
        except Exception as e:
            D['tgt_error'] = repr(e)
            return
        pw = pb.get_socket_location(bn)
        rw = rb.get_socket_location(bn)
        rw = (rw.x + off[0], rw.y + off[1], rw.z + off[2])
        cur['tgt'][bn]['vs_anim'].append(math.dist((tg.x, tg.y, tg.z), rw))
        cur['tgt'][bn]['vs_physics'].append(math.dist((tg.x, tg.y, tg.z), (pw.x, pw.y, pw.z)))


def vsub3(a, b):
    return (a.x - b.x, a.y - b.y, a.z - b.z)


def pct(xs, q):
    if not xs:
        return None
    s = sorted(xs)
    return s[min(len(s) - 1, int(q * (len(s) - 1) + 0.5))]


def finish_phase():
    cur = D.get('cur')
    if not cur:
        return
    out = {k: cur[k] for k in ('phase', 'clip', 'gravity', 'speed', 'mode', 'frames')}
    out['seconds'] = round(cur['dur'], 2)
    out['fps'] = round(len(cur['dts']) / max(1e-6, sum(cur['dts'])), 1) if cur['dts'] else None
    py = cur['ref_pelvis_y']
    out['ref_pelvis_travel_cm'] = round(max(py) - min(py), 1) if py else None
    out['actor_travel_cm'] = round(math.dist(cur['start_actor'], vec(AR.S['hero'].get_actor_location())), 1)
    bones = {}
    for bn, acc in cur['acc'].items():
        if not acc['err']:
            continue
        n = len(acc['err'])
        bones[bn] = {'mean_cm': round(sum(acc['err']) / n, 2), 'p95_cm': round(pct(acc['err'], 0.95), 2),
                     'max_cm': round(max(acc['err']), 2), 'mean_dz_cm': round(sum(acc['dz']) / n, 2),
                     'mean_deg': round(sum(acc['ang']) / n, 2), 'p95_deg': round(pct(acc['ang'], 0.95), 2)}
    out['bones'] = bones
    out['target_cm'] = {bn: {k: round(sum(v) / len(v), 2) for k, v in d.items() if v} for bn, d in cur['tgt'].items()}
    out['fixed_order'] = bool(D.get('fixed_order'))
    out['com_minus_bone_cm'] = {bn: [round(sum(v[i] for v in vs) / len(vs), 2) for i in range(3)] for bn, vs in cur['com'].items() if vs}
    out['com_error'] = D.get('com_error')
    if cur['series']:
        out['head_dz_series'] = cur['series'][::3]
    D['results'].append(out)


def stop_tick():
    h = D.pop('tick', None)
    if h is not None:
        unreal.unregister_slate_post_tick_callback(h)


def prep_idle(grav=1.0):
    """Back to the prototype's normal standing setup on idle, for the comparison stills."""
    if AR.S.get('state') != 'STAND':
        AR.enter_stand()
    AR.pcc().set_body_modifiers_in_set_gravity_multiplier('All', grav)
    play_both('idle')


def cam_for(view):
    """Camera (eye, aim) for 'front' (both actors), 'side_proto' or 'side_ref' (each from its outer side)."""
    h, r = AR.S['hero'].get_actor_location(), D['ref'].get_actor_location()
    gz = AR.S.get('ground_z', h.z)
    dx, dy = D['dir']
    px, py = -dy, dx  # perpendicular to the facing: a true profile view
    if view == 'front':
        mx, my = (h.x + r.x) / 2.0, (h.y + r.y) / 2.0
        return (mx + px * 520.0 + dx * 200.0, my + py * 520.0 + dy * 200.0, gz + 150.0), (mx, my, gz + 105.0)
    a = h if view == 'side_proto' else r
    return (a.x + px * 260.0, a.y + py * 260.0, gz + 125.0), (a.x, a.y, gz + 115.0)


def table():
    """Compact per-phase summary: head, neck, hands."""
    rows = []
    for r in D.get('results', []):
        if 'skipped' in r:
            rows.append({'phase': r['phase'], 'skipped': r['skipped']})
            continue
        b = r['bones']
        row = {'phase': r['phase'], 'fps': r['fps'], 'frames': r['frames'], 'actor_travel_cm': r['actor_travel_cm'],
               'ref_pelvis_travel_cm': r['ref_pelvis_travel_cm']}
        for bn in ('spine_04', 'head', 'hand_l', 'hand_r'):
            if bn in b:
                row[bn] = '%.1f/%.1f cm (dz %.1f), %.1f/%.1f deg' % (b[bn]['mean_cm'], b[bn]['p95_cm'], b[bn]['mean_dz_cm'],
                                                                     b[bn]['mean_deg'], b[bn]['p95_deg'])
        rows.append(row)
    return rows
