"""Active-ragdoll prototype for Reflections (UE 5.9 Physics Control), driven from editor Python during Simulate/PIE.
Write-up: ArtDirection/Physics/ActiveRagdoll.md. PROTOTYPE ONLY - the production version belongs in C++.

One BP_Hero spawned in the play world (body gets PHYS_Hero_ActiveRagdoll), plus one APhysicsControlActor whose
PhysicsControlComponent drives the Hero's Body mesh from outside (no Blueprint changes). A slate post-tick callback
runs the reaction state machine:

  DORMANT  the default: pure animation. Every body kinematic on the animated pose, controls off, control component
           tick off. Only a hit, stagger, knockdown or a prop contact harder than imp_hit wakes the physics.
  STAND    pelvis + legs kinematic (follow the animation), upper body simulated with parent-space controls.
           Muscle tone: an unhit limb feels no gravity (holds its pose); a weakened limb feels it in proportion.
           Reaction envelope: full physics while a limb is badly weakened, blending back to the animation as
           strength returns (never faster than 'fadeout'), then DORMANT again.
  hit()    (wakes from DORMANT) the struck limb and the spine lose most of their strength, a velocity kick on the
           bone, strength comes back over ~1 s. Stays standing because the legs/pelvis are kinematic.
  STAGGER  upper body weak + kick; legs take real steps from a GASP run-stop clip started part-way.
  FALL     everything simulated, legs stiff on their bind pose (topple about the feet), arms follow a GASP reach
           (brace) clip, legs soften, then everything goes limp on landing.
  DOWN     limp (4 % strength + extra damping) until the pelvis is still.
  GETUP    actor re-placed under the ragdoll (back/front chosen from the chest normal), GASP get-up clip; a
           0.45 s visual blend from the lying pose into the clip (bodies stay limp, nothing is pulled), then
  GETUP_ANIM the rest of the get-up is pure animation (all kinematic, controls and their tick off). A new force
           wakes physics from that pose: a light hit makes the upper body react while the legs keep getting up,
           a stagger-strength hit or prop knocks him back down (no balance mid get-up). Clip end -> idle, DORMANT.
  drop()   physics crate dropped/thrown at a bone; its momentum on contact picks hit / stagger / knockdown.

State lives in builtins so importlib.reload keeps it. Every runtime property write uses notify NEVER: a notified
write on the Body re-runs BP_Hero's construction script and replaces the component under the controls.
"""
import builtins
import json
import math
import time

import unreal

S = builtins.__dict__.setdefault('_AR_STATE', {})
NEVER = unreal.PropertyAccessChangeNotifyMode.NEVER
TAG = 'AR_PROTO'
LOG = builtins.__dict__.setdefault('_AR_LOG', [])

ROOT = '/Game/Physics/ActiveRagdollTest'
HERO_BP = '/Game/Characters/Hero/Assembled/Hero/BP_Hero'
PA = ROOT + '/PHYS_Hero_ActiveRagdoll'
ANIM = {
    'idle': '/Game/Characters/Hero/Animation/Locomotion/AS_Hero_Idle',
    'stag_back': ROOT + '/Anims/AS_Hero_Run_Stop_B_Lfoot',   # GASP run-stop: backward steps settling to a stand
    'stag_fwd': ROOT + '/Anims/AS_Hero_Run_Stop_F_Lfoot',
    'brace_fwd': ROOT + '/Anims/AS_Hero_reach_forward',
    'brace_back': ROOT + '/Anims/AS_Hero_reach_back',
    'getup_back': ROOT + '/Anims/AS_Hero_getup_stand_B',
    'getup_front': ROOT + '/Anims/AS_Hero_getup_stand_F',
    'walk': ROOT + '/Anims/AS_Hero_Walk_RM',  # root motion on, root locked: walks in place
}
# First-frame pose of each get-up clip in the body's component space (forward = +Y, up = +Z):
# pelvis position and the pelvis->head direction. Measured with AnimationLibrary.get_bone_pose_for_time.
GETUP0 = {
    'getup_back': {'pelvis': (0.0, -35.0), 'head_dir': (-2.0, -56.0)},
    'getup_front': {'pelvis': (3.0, -1.0), 'head_dir': (5.0, 56.0)},
}

# ---------------------------------------------------------------------------------------------- tuning
P = {
    # parent-space angular strength (Hz-like, acceleration mode) per limb while standing
    'ps_stand': {'Spine': 9.0, 'Head': 8.0, 'ArmLeft': 7.0, 'ArmRight': 7.0, 'LegLeft': 10.0, 'LegRight': 10.0},
    'ps_damping': 1.0,
    'ps_extra_damping': 0.0,
    # partial hit
    'hit_weak': 0.9,            # strength lost on the struck limb (0..1)
    'hit_weak_spine': 0.8,      # strength lost on the spine
    'hit_recover': 1.1,         # weakness decay per second
    'hit_dv': 900.0,            # velocity change on the struck body, cm/s
    'hit_dv_neighbour': 0.45,   # fraction given to the parent body
    # stagger
    'stag_weak': 0.92, 'stag_weak_spine': 0.85, 'stag_recover': 1.0,
    'stag_dv': 380.0,
    # stagger clips: (start time, play rate, time to hand over to idle); the start time sets how far it steps
    'stag_clip': {'stag_back': (0.45, 1.0, 1.7), 'stag_fwd': (0.62, 0.75, 1.9)},
    # fall / knockdown
    'fall_mult': {'LegLeft': 1.8, 'LegRight': 1.8, 'Spine': 1.0, 'Head': 0.6, 'ArmLeft': 1.3, 'ArmRight': 1.3},
    'fall_legs_soften': 0.6,   # legs go from stiff to soft over this time (topple, then fold)
    'getup_knock_scale': 0.6,  # knocked down mid get-up: smaller kick (he is already low)
    'getup_knock_legs': 0.35,  # ... and soft legs holding the frozen get-up pose, so he collapses instead of flipping
    'fall_dv': 380.0,           # velocity change on the upper body at the hit (topples about the feet)
    'fall_dv_profile': {'head': 1.0, 'neck_01': 1.0, 'spine_04': 1.0, 'clavicle_l': 0.9, 'clavicle_r': 0.9,
                        'upperarm_l': 0.8, 'upperarm_r': 0.8, 'spine_02': 0.6, 'pelvis': 0.25},
    'limp_after': 1.3,          # seconds after the hit before going limp at the latest
    'fall_ps_mult': 1.0,
    'limp_ps_mult': 0.04,       # residual tone when limp
    'limp_extra_damping': 2.0,
    'limp_ramp': 0.35,
    'still_speed': 22.0, 'still_time': 0.7, 'down_max': 4.0, 'down_min': 1.2,
    # get-up
    'getup_blend': 0.45,        # physics -> animation blend time
    'getup_rate': 1.25,         # play rate of the get-up clip
    'getup_hold': 2.6,          # seconds of the (rate-scaled) clip before idling
    # physical triggers (crate hits): normal impulse thresholds, kg*cm/s
    # classified by the prop's momentum at contact (mass * speed): contact impulses split across light bodies
    'imp_hit': 1500.0, 'mom_stagger': 11000.0, 'mom_knockdown': 20000.0,
    # physics only while reacting: DORMANT (pure animation) until a hit; back to DORMANT after recovering
    'start_dormant': True,
    'envelope_full_weak': 0.15,  # full physics while any upper limb is weaker than this; blends to animation below
    'fadeout': 0.35,             # fastest physics -> animation blend (also the hand-off after a get-up)
    # muscle tone: upper-body gravity while standing = stand_gravity + weakness * weak_gravity (full when falling)
    'stand_gravity': 0.0,
    'weak_gravity': 1.0,
}
# test harnesses override tuning here; kept in builtins so importlib.reload does not undo it mid-run
P.update(builtins.__dict__.setdefault('_AR_P_OVERRIDE', {}))

BONES = ['pelvis', 'spine_02', 'spine_04', 'neck_01', 'head', 'clavicle_l', 'upperarm_l', 'lowerarm_l', 'hand_l',
         'clavicle_r', 'upperarm_r', 'lowerarm_r', 'hand_r', 'thigh_l', 'calf_l', 'foot_l', 'ball_l', 'thigh_r', 'calf_r',
         'foot_r', 'ball_r']
PARENT = {'spine_02': 'pelvis', 'spine_04': 'spine_02', 'neck_01': 'spine_04', 'head': 'neck_01', 'clavicle_l': 'spine_04',
          'upperarm_l': 'clavicle_l', 'lowerarm_l': 'upperarm_l', 'hand_l': 'lowerarm_l', 'clavicle_r': 'spine_04',
          'upperarm_r': 'clavicle_r', 'lowerarm_r': 'upperarm_r', 'hand_r': 'lowerarm_r'}
LIMBS = ['ArmLeft', 'ArmRight', 'Head', 'LegLeft', 'LegRight', 'Spine']
UPPER = ['Spine', 'Head', 'ArmLeft', 'ArmRight']
LEGS = ['LegLeft', 'LegRight']


def log(*a):
    LOG.append('%.2f %s' % (S.get('t', 0.0), ' '.join(str(x) for x in a)))
    del LOG[:-400]


def load(path):
    name = path.rsplit('/', 1)[1]
    return unreal.load_object(None, path + '.' + name)


def world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


def V(x, y, z):
    return unreal.Vector(float(x), float(y), float(z))


def spawn(cls, loc, yaw):
    w = world()
    xf = unreal.Transform(location=loc, rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw), scale=V(1, 1, 1))
    gs = unreal.get_default_object(unreal.GameplayStatics)
    a = gs.call_method('BeginDeferredActorSpawnFromClass',
                       (w, cls, xf, unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN, None,
                        unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
    if isinstance(a, tuple):
        a = a[0]
    assert a is not None, 'deferred spawn failed for %s' % cls
    r = gs.call_method('FinishSpawningActor', (a, xf, unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
    return r[0] if isinstance(r, tuple) else r


def body():
    return S.get('body')


def pcc():
    return S.get('pcc')


# ---------------------------------------------------------------------------------------------- setup
def make_limb(name, start, include_parent=False):
    l = unreal.PhysicsControlLimbSetupData()
    l.set_editor_property('limb_name', name)
    l.set_editor_property('start_bone', start)
    l.set_editor_property('include_parent_bone', include_parent)
    l.set_editor_property('create_world_space_controls', True)
    l.set_editor_property('create_parent_space_controls', True)
    l.set_editor_property('create_body_modifiers', True)
    return l


def control_data(ang, lin=0.0, damping=1.0, extra=0.0):
    d = unreal.PhysicsControlData()
    d.set_editor_property('enabled', True)
    d.set_editor_property('angular_strength', ang)
    d.set_editor_property('angular_damping_ratio', damping)
    d.set_editor_property('angular_extra_damping', extra)
    d.set_editor_property('linear_strength', lin)
    d.set_editor_property('linear_damping_ratio', damping)
    d.set_editor_property('use_skeletal_animation', True)
    d.set_editor_property('disable_collision', False)
    return d


def setup(loc=(700.0, 0.0, 8.0), yaw=180.0, pa_path=PA):
    """Spawn the Hero and the control actor in the play world and create controls. Returns a summary."""
    w = world()
    assert w, 'no PIE/Simulate world'
    teardown(destroy=True)
    S.clear()
    S['t'] = 0.0
    S['world'] = w
    hero_cls = unreal.load_class(None, HERO_BP + '.BP_Hero_C')
    hero = spawn(hero_cls, V(*loc), yaw)
    hero.tags = list(hero.tags) + [TAG]
    S['hero'] = hero
    skms = hero.get_components_by_class(unreal.SkeletalMeshComponent)
    b = [c for c in skms if c.get_name() == 'Body'][0]
    S['body'] = b
    S['followers'] = {c.get_name(): (c.get_editor_property('leader_pose_component').get_name()
                                     if c.get_editor_property('leader_pose_component') else None) for c in skms}
    pa = load(pa_path)
    b.set_physics_asset(pa, True)
    b.set_collision_object_type(unreal.CollisionChannel.ECC_PHYSICS_BODY)
    b.set_collision_response_to_all_channels(unreal.CollisionResponseType.ECR_BLOCK)
    b.set_collision_response_to_channel(unreal.CollisionChannel.ECC_PAWN, unreal.CollisionResponseType.ECR_IGNORE)
    b.set_collision_response_to_channel(unreal.CollisionChannel.ECC_CAMERA, unreal.CollisionResponseType.ECR_IGNORE)
    b.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    # bodies simulate in world space; the component stays on the actor (the engine would otherwise drag it
    # along with a simulated pelvis)
    S['body_rel0'] = b.get_relative_transform()
    S['anims'] = {k: load(v) for k, v in ANIM.items()}
    play('idle', loop=True)
    ground = unreal.SystemLibrary.line_trace_single(
        w, V(loc[0], loc[1], loc[2] + 100), V(loc[0], loc[1], loc[2] - 300),
        unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [hero], unreal.DrawDebugTrace.NONE, True)
    S['ground_z'] = float(loc[2])
    try:
        hr = ground.to_tuple()
        S['ground_z'] = float(hr[4].z) if hr[0] else float(loc[2])
    except Exception as e:
        log('ground trace parse failed', e)
    ca = spawn(unreal.PhysicsControlActor, V(loc[0], loc[1], loc[2]), 0.0)
    ca.tags = list(ca.tags) + [TAG]
    S['control_actor'] = ca
    c = ca.get_component_by_class(unreal.PhysicsControlComponent)
    S['pcc'] = c
    c.set_editor_property('show_debug_visualization', False, NEVER)
    c.set_editor_property('teleport_distance_threshold', 0.0, NEVER)
    # (attempt_to_recreate_disabled_controls stays off: it retries kinematic-kinematic leg joints every frame,
    #  +0.25 ms; disabling the controls while every body is kinematic avoids the dead joints instead)
    limbs = [make_limb('ArmLeft', 'clavicle_l'), make_limb('ArmRight', 'clavicle_r'), make_limb('Head', 'neck_01'),
             make_limb('LegLeft', 'thigh_l'), make_limb('LegRight', 'thigh_r'), make_limb('Spine', 'spine_01', True)]
    bm = unreal.PhysicsControlModifierData()
    bm.set_editor_property('movement_type', unreal.PhysicsMovementType.KINEMATIC)
    bm.set_editor_property('collision_type', unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    bm.set_editor_property('physics_blend_weight', 1.0)
    bm.set_editor_property('gravity_multiplier', 1.0)
    r = c.create_controls_and_body_modifiers_from_limb_bones(b, limbs, control_data(0.0), control_data(8.0), bm)
    S['created'] = r is not None
    b.set_editor_property('physics_transform_update_mode', unreal.PhysicsTransformUpdateMode.COMPONENT_TRANSFORM_IS_KINEMATIC, NEVER)
    S['ps_sets'] = {l: list(c.get_control_names_in_set('ParentSpace_' + l)) for l in LIMBS}
    S['ws_sets'] = {l: list(c.get_control_names_in_set('WorldSpace_' + l)) for l in LIMBS}
    S['bm_sets'] = {l: list(c.get_body_modifier_names_in_set(l)) for l in LIMBS}
    S['weak'] = {l: 0.0 for l in LIMBS}
    S['applied'] = {}
    S['state'] = 'STAND'
    S['state_t'] = 0.0
    S['pending'] = []
    S['events'] = []
    enter_stand(first=True)
    if P['start_dormant']:
        dormant(True)
    b.set_notify_rigid_body_collision(True)
    b.on_component_hit.add_callable(_on_body_hit)
    register_tick()
    return summary()


def summary():
    b = body()
    out = {'state': S.get('state'), 'ground_z': S.get('ground_z'), 'created': S.get('created'),
           'ps_sets': {k: [str(n) for n in v] for k, v in S.get('ps_sets', {}).items()},
           'bm_sets': {k: [str(n) for n in v] for k, v in S.get('bm_sets', {}).items()},
           'followers': S.get('followers')}
    if b:
        out['body_rel'] = str(b.get_relative_transform())[:200]
        out['pelvis'] = str(b.get_socket_location('pelvis'))
        out['simulating'] = b.is_simulating_physics('pelvis'), b.is_simulating_physics('spine_04')
    return out


# ---------------------------------------------------------------------------------------------- helpers
def play(key, loop=False, rate=1.0, start=0.0):
    b = body()
    b.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
    b.play_animation(S['anims'][key], loop)
    inst = b.get_anim_instance()
    if inst:  # 'walk' extracts (locks) its root motion so it walks in place; everything else plays as authored
        inst.set_root_motion_mode(unreal.RootMotionMode.ROOT_MOTION_FROM_EVERYTHING if key == 'walk'
                                  else unreal.RootMotionMode.ROOT_MOTION_FROM_MONTAGES_ONLY)
    b.set_play_rate(rate)
    if start:
        b.set_position(start, False)
    S['anim'] = key


def set_movement(limbs, kinematic):
    mt = unreal.PhysicsMovementType.KINEMATIC if kinematic else unreal.PhysicsMovementType.SIMULATED
    c = pcc()
    for l in limbs:
        c.set_body_modifiers_in_set_movement_type(l, mt)


def set_bm(name, kinematic):
    pcc().set_body_modifier_movement_type(name, unreal.PhysicsMovementType.KINEMATIC if kinematic else unreal.PhysicsMovementType.SIMULATED,
                                          True, False)  # this modifier only, not a set that shares its name


def apply_strengths(mult_all=1.0, extra=None, ws=None, mult=None):
    """Parent-space strengths = stand strength * (1 - weak[limb]) * mult_all * mult[limb]. ws: {limb: (ang, lin)}."""
    c = pcc()
    extra = P['ps_extra_damping'] if extra is None else extra
    mult = mult or {}
    for l in LIMBS:
        k = P['ps_stand'][l] * max(0.0, 1.0 - S['weak'][l]) * mult_all * mult.get(l, 1.0)
        key = ('ps', l)
        val = (round(k, 3), round(extra, 3))
        if S['applied'].get(key) != val:
            S['applied'][key] = val
            for n in S['ps_sets'][l]:
                c.set_control_angular_data(n, k, P['ps_damping'], extra, 0.0, True, True, False)
    ws = ws or {}
    for l in LIMBS:
        a, lin = ws.get(l, (0.0, 0.0))
        key = ('ws', l)
        if S['applied'].get(key) != (a, lin):
            S['applied'][key] = (a, lin)
            for n in S['ws_sets'][l]:
                # apply_to_sets_with_name=False: the world-space control 'head' would otherwise also hit the limb set
                # 'Head' (FNames ignore case) and zero the neck/head parent-space controls
                c.set_control_angular_data(n, a, 1.0, 0.0, 0.0, True, True, False)
                c.set_control_linear_data(n, lin, 1.0, 0.0, 0.0, True, True, False)
    apply_gravity()


RELAX_JOINTS = ('spine_02', 'spine_04', 'neck_01', 'head', 'clavicle_l', 'clavicle_r', 'upperarm_l', 'upperarm_r',
                'lowerarm_l', 'lowerarm_r', 'hand_l', 'hand_r')


def joint_limits(relaxed, joints=RELAX_JOINTS):
    """relaxed=True frees the angular limits of the upper-body joints (the controls hold the pose while standing,
    and the physics asset's limits are tighter than our animations). False restores the asset's own limits."""
    if S.get('limits_relaxed') == (relaxed, tuple(joints)):
        return
    b = body()
    L = unreal.ConstraintInstanceBlueprintLibrary
    orig = S.setdefault('limits0', {})
    for j in RELAX_JOINTS:
        if j in orig:
            continue
        acc = b.get_constraint_by_name(j, False)
        if acc is None:
            continue
        lim = L.get_angular_limits(acc)  # (accessor, s1 motion, s1, s2 motion, s2, twist motion, twist)
        orig[j] = (lim[0], tuple(lim[1:7]))
    free = unreal.AngularConstraintMotion.ACM_FREE
    for j, (acc, lim) in orig.items():
        if relaxed and j in joints:
            L.set_angular_limits(acc, free, 0.0, free, 0.0, free, 0.0)
        else:
            L.set_angular_limits(acc, *lim)
    S['limits_relaxed'] = (relaxed, tuple(joints))
    log('joint limits', 'relaxed' if relaxed else 'asset', len(orig))


GRAVITY_FULL_STATES = ('FALL', 'DOWN', 'GETUP')


def apply_gravity():
    """Muscle tone: while standing, each upper-body limb feels gravity in proportion to how weakened it is, so an
    unhit body holds its animated pose (no sag) and a struck limb gets heavy and drops. Full gravity when falling."""
    c = pcc()
    full = S.get('state') in GRAVITY_FULL_STATES
    for l in UPPER:
        g = 1.0 if full else min(1.0, P['stand_gravity'] + S['weak'][l] * P['weak_gravity'])
        key = ('g', l)
        if S['applied'].get(key) != round(g, 3):
            S['applied'][key] = round(g, 3)
            c.set_body_modifiers_in_set_gravity_multiplier(l, g)


def bone_loc(b, name):
    return b.get_socket_location(name)


def vsub(a, b):
    return V(a.x - b.x, a.y - b.y, a.z - b.z)


def vlen(a):
    return math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z)


def norm2d(x, y):
    l = math.hypot(x, y) or 1.0
    return x / l, y / l


def reset_cloth():
    for c in S['hero'].get_components_by_class(unreal.SkeletalMeshComponent):
        try:
            c.force_cloth_next_update_teleport_and_reset()
        except Exception as e:
            log('cloth reset failed', c.get_name(), e)


def set_state(s):
    log('state', S.get('state'), '->', s)
    S['state'] = s
    S['state_t'] = 0.0


# ---------------------------------------------------------------------------------------------- states
def enter_stand(first=False, keep_anim=False):
    pcc().set_component_tick_enabled(True)  # it is switched off while dormant
    S['pcc_tick_off'] = False
    pcc().set_controls_in_set_enabled('All', True)
    for l in LIMBS:
        for n in S['ps_sets'][l]:
            pcc().set_control_use_skeletal_animation(n, True, 1.0, 1.0, True, False)
    set_movement(LEGS, True)
    set_movement(['Spine'], False)
    set_bm(bm_for('Spine', 'pelvis'), True)
    set_movement(['Head', 'ArmLeft', 'ArmRight'], False)
    pcc().set_body_modifiers_in_set_physics_blend_weight('All', 1.0)
    S['applied'] = {}
    apply_strengths()
    if not first and not keep_anim:
        play('idle', loop=True)
    S['env'] = 1.0  # reaction envelope starts at full physics (see tick)
    set_state('STAND')


def bm_for(limb, bone):
    for n in S['bm_sets'][limb]:
        if str(n).startswith(bone):
            return n
    return None


def limb_of(bone):
    for l in LIMBS:
        for n in S['bm_sets'][l]:
            if str(n).startswith(bone + '_') or str(n) == bone:
                return l
    return 'Spine'


def wake():
    """DORMANT -> STAND: physics switches on from the exact animated pose (the kinematic bodies were on it)."""
    if S.get('state') not in ('DORMANT', 'GETUP_ANIM'):
        return S.get('state')
    pcc().set_body_modifiers_in_set_physics_blend_weight('All', 1.0)
    enter_stand(keep_anim=True)
    log('wake')
    return S['state']


def getting_up():
    """True while the get-up clip is still playing (pure animation, or woken by a hit mid get-up)."""
    return S.get('getup_until') is not None and str(S.get('anim', '')).startswith('getup')


def when(state, delay, fn, kw=None, not_before=0.0):
    """Test trigger: call fn(**kw) once, delay seconds after the state machine enters state (and not before the
    world time not_before)."""
    S.setdefault('when', []).append({'state': state, 'delay': delay, 'fn': fn, 'kw': kw or {}, 'not_before': not_before})
    return len(S['when'])


def hit(bone='spine_04', direction=(1.0, 0.0, 0.0), strength=1.0):
    """Partial hit: impulse on one bone, struck limb + spine weakened, stays standing."""
    wake()
    if S.get('state') not in ('STAND',):
        log('hit ignored in', S.get('state'))
        return S.get('state')
    l = limb_of(bone)
    S['weak'][l] = max(S['weak'][l], P['hit_weak'] * min(1.0, strength))
    S['weak']['Spine'] = max(S['weak']['Spine'], P['hit_weak_spine'] * min(1.0, strength))
    if l in ('ArmLeft', 'ArmRight'):
        S['weak']['Head'] = max(S['weak']['Head'], 0.3 * strength)
    if l == 'Head':
        S['weak']['Head'] = max(S['weak']['Head'], P['hit_weak'] * strength)
    S['recover'] = P['hit_recover']
    apply_strengths()
    d = V(*direction)
    dl = vlen(d) or 1.0
    dv = P['hit_dv'] * strength
    S['pending'].append(('dv', bone, V(d.x / dl * dv, d.y / dl * dv, d.z / dl * dv)))
    par = PARENT.get(bone)
    if par:
        k = P['hit_dv_neighbour']
        S['pending'].append(('dv', par, V(d.x / dl * dv * k, d.y / dl * dv * k, d.z / dl * dv * k)))
    S['events'].append(['hit', round(S['t'], 2), bone, l])
    log('hit', bone, l, strength)
    return 'hit ' + bone


def stagger(bone='spine_04', direction=(1.0, 0.0, 0.0), strength=1.0):
    """Strong hit: upper body goes weak and flails while the legs take real backward/forward steps (a GASP run-stop
    clip started part-way, so the steps decelerate into a stand). The actor is moved back by the clip's root offset
    first, so the body does not jump; the clip's root motion then walks it onto the actor.
    Mid get-up there is no balance to step with: a stagger-strength hit knocks him back down instead."""
    if getting_up():
        return knockdown(bone, direction, strength)
    wake()
    if S.get('state') not in ('STAND',):
        return S.get('state')
    for l in UPPER:
        S['weak'][l] = max(S['weak'][l], P['stag_weak'])
    S['weak']['Spine'] = max(S['weak']['Spine'], P['stag_weak_spine'])
    S['recover'] = P['stag_recover']
    apply_strengths()
    d = V(*direction)
    dx, dy = norm2d(d.x, d.y)
    b = body()
    f = b.get_right_vector()
    backward = (dx * f.x + dy * f.y) < 0.0
    key = 'stag_back' if backward else 'stag_fwd'
    t0, rate, hold = P['stag_clip'][key]
    anim = S['anims'][key]
    root0 = unreal.AnimationLibrary.get_bone_pose_for_time(anim, 'root', t0, False).translation
    cyaw = math.radians(b.get_world_rotation().yaw)                # component -> world (yaw only)
    off = V(math.cos(cyaw) * root0.x - math.sin(cyaw) * root0.y, math.sin(cyaw) * root0.x + math.cos(cyaw) * root0.y, 0.0)
    h = S['hero']
    loc = h.get_actor_location()
    h.set_actor_location(V(loc.x - off.x, loc.y - off.y, loc.z), False, True)
    S['cloth_reset_frames'] = 2
    play(key, loop=False, rate=rate, start=t0)
    S['stag'] = {'hold': (hold - t0) / rate}
    dv = P['stag_dv'] * strength
    S['pending'].append(('dv', bone, V(dx * dv, dy * dv, 0.0)))
    S['pending'].append(('dv', 'spine_02', V(dx * dv * 0.5, dy * dv * 0.5, 0.0)))
    set_state('STAGGER')
    S['events'].append(['stagger', round(S['t'], 2), bone, key])
    return 'stagger ' + key


def knockdown(bone='spine_04', direction=(1.0, 0.0, 0.0), strength=1.0):
    from_getup = getting_up()  # mid get-up: crouched/kneeling, no stance to topple from
    wake()
    if S.get('state') not in ('STAND', 'STAGGER'):
        return S.get('state')
    d = V(*direction)
    dx, dy = norm2d(d.x, d.y)
    # Facing of the hero: brace forward when pushed from behind, back when pushed from the front.
    fwd = body().get_right_vector()
    falling_forward = (dx * fwd.x + dy * fwd.y) > 0.0
    if from_getup:
        # Freeze the get-up pose as the target and keep the legs soft: he collapses from where he is. (Straight
        # stiff legs plus the standing kick would lever a kneeling body into a flip.)
        body().set_play_rate(0.0)
        S['getup_until'] = None
        strength *= P['getup_knock_scale']
    else:
        play('brace_fwd' if falling_forward else 'brace_back', loop=False)
    S['weak'] = {l: 0.0 for l in LIMBS}
    S['applied'] = {}
    pcc().set_body_modifiers_in_set_gravity_multiplier('All', 1.0)  # falling: full gravity everywhere
    for l in UPPER:
        S['applied'][('g', l)] = 1.0
    set_movement(LIMBS, False)
    # the brace clips crouch, so the legs hold their straight bind pose instead and the body topples about the feet
    # (not mid get-up: there the legs keep the frozen get-up pose, soft)
    if not from_getup:
        for l in LEGS:
            for n in S['ps_sets'][l]:
                pcc().set_control_use_skeletal_animation(n, False, 1.0, 1.0, True, False)
    set_state('FALL')  # before apply_strengths, so apply_gravity keeps full gravity
    legs0 = P['getup_knock_legs'] if from_getup else None
    m0 = dict(P['fall_mult'])
    if legs0 is not None:
        m0.update({l: legs0 for l in LEGS})
    apply_strengths(mult=m0)
    dv = P['fall_dv'] * strength
    for bn, k in P['fall_dv_profile'].items():
        S['pending'].append(('dv', bn, V(dx * dv * k, dy * dv * k, 0.0)))
    S['fall'] = {'forward': falling_forward, 'limp_t': None, 'legs0': legs0, 'from_getup': from_getup}
    S['events'].append(['knockdown', round(S['t'], 2), bone, 'forward' if falling_forward else 'backward'])
    return 'knockdown ' + ('forward' if falling_forward else 'backward')


def begin_getup():
    b = body()
    hero = S['hero']
    pel = bone_loc(b, 'pelvis')
    head = bone_loc(b, 'head')
    tr = bone_loc(b, 'thigh_r')
    tl = bone_loc(b, 'thigh_l')
    hips = vsub(tr, tl)
    spine = vsub(head, pel)
    nz = hips.x * spine.y - hips.y * spine.x  # z of hips x spine: chest normal points up -> on the back
    on_back = nz > 0.0
    key = 'getup_back' if on_back else 'getup_front'
    g = GETUP0[key]
    # world yaw of the pelvis->head direction, and of the clip's head direction in component space
    hx, hy = norm2d(spine.x, spine.y)
    world_yaw = math.degrees(math.atan2(hy, hx))
    comp_yaw0 = math.degrees(math.atan2(g['head_dir'][1], g['head_dir'][0]))
    comp_world_yaw = world_yaw - comp_yaw0
    rel = S.get('body_rel0') or b.get_relative_transform()
    rel_yaw = rel.rotation.rotator().yaw
    actor_yaw = comp_world_yaw - rel_yaw
    cy, sy = math.cos(math.radians(comp_world_yaw)), math.sin(math.radians(comp_world_yaw))
    px, py = g['pelvis']
    comp_x = pel.x - (cy * px - sy * py)
    comp_y = pel.y - (sy * px + cy * py)
    ay = math.radians(actor_yaw)
    rl = rel.translation
    ax = comp_x - (math.cos(ay) * rl.x - math.sin(ay) * rl.y)
    ay_ = comp_y - (math.sin(ay) * rl.x + math.cos(ay) * rl.y)
    az = S['ground_z'] - rl.z
    hero.set_actor_location_and_rotation(V(ax, ay_, az), unreal.Rotator(roll=0.0, pitch=0.0, yaw=actor_yaw), False, True)
    reset_cloth()
    S['cloth_reset_frames'] = 3
    play(key, loop=False, rate=P['getup_rate'])
    S['getup'] = {'key': key, 'blend': 1.0}
    S['getup_until'] = S['t'] + P['getup_hold']
    set_state('GETUP')
    S['events'].append(['getup', round(S['t'], 2), key, round(actor_yaw, 1)])
    log('getup', key, 'pelvis', round(pel.x), round(pel.y), round(pel.z), 'yaw', round(actor_yaw, 1))


# ---------------------------------------------------------------------------------------------- tick
def tick(dt):
    w = world()
    if not w or not S.get('body') or S.get('world') != w:
        unregister_tick()
        return
    dt = unreal.GameplayStatics.get_world_delta_seconds(w)
    if dt <= 0.0:
        return
    S['t'] += dt
    S['state_t'] += dt
    b = body()
    c = pcc()
    # impulses are applied one frame after the movement change so the bodies are simulating
    if S['pending']:
        for kind, bone, v in S['pending']:
            if kind == 'dv':
                b.add_impulse(v, bone, True)
            elif kind == 'dv_all':
                for bn in BONES:
                    b.add_impulse(v, bn, True)
        S['pending'] = []
    # scripted demo events: [(time, fn_name, kwargs)] relative to schedule() call
    if S.get('script'):
        due = [e for e in S['script'] if e[0] <= S['t']]
        S['script'] = [e for e in S['script'] if e[0] > S['t']]
        for _, fn, kw in due:
            try:
                r = globals()[fn](**kw)
                log('script', fn, r)
            except Exception as e:
                log('script error', fn, repr(e))
    if S.get('cloth_reset_frames', 0) > 0:
        S['cloth_reset_frames'] -= 1
        reset_cloth()
    if S.get('getup_until') is not None and S['t'] >= S['getup_until']:
        S['getup_until'] = None
        if str(S.get('anim', '')).startswith('getup'):
            play('idle', loop=True)
        if S['state'] == 'GETUP_ANIM':
            set_state('DORMANT')
    # event-driven test triggers: when(state, delay, fn, kw) fires once, delay seconds into that state
    for w_ in S.get('when') or []:
        if not w_.get('done') and S['state'] == w_['state'] and S['state_t'] >= w_['delay'] and S['t'] >= w_.get('not_before', 0.0):
            w_['done'] = True
            try:
                log('when', w_['state'], w_['fn'], globals()[w_['fn']](**w_['kw']))
            except Exception as e:
                log('when error', w_['fn'], repr(e))
    st = S['state']
    if st in ('STAND', 'STAGGER'):
        rec = S.get('recover', 1.5) * dt
        changed = False
        for l in LIMBS:
            if S['weak'][l] > 0.0:
                S['weak'][l] = max(0.0, S['weak'][l] - rec)
                changed = True
        if changed:
            apply_strengths()
        # Reaction envelope (physics only while reacting): the whole body shows full physics while any limb is
        # badly weakened and blends back to the animation as strength returns, never faster than 'fadeout'.
        # Whatever the springs cannot follow (fast arm swings while walking or casting) fades out with the reaction.
        if P['start_dormant']:
            worst = max(S['weak'][l] for l in UPPER)
            target = min(1.0, worst / P['envelope_full_weak'])
            env = max(target, S.get('env', 1.0) - dt / P['fadeout'])
            if abs(env - S.get('env', -1.0)) > 1e-3:
                c.set_body_modifiers_in_set_physics_blend_weight('All', env)
            S['env'] = env
            if st == 'STAND' and env <= 0.0 and worst <= 0.0:
                dormant(True)
                c.set_body_modifiers_in_set_physics_blend_weight('All', 1.0)  # kinematic bodies sit on the animation
    elif st in ('DORMANT', 'GETUP_ANIM'):
        # the control component costs ~0.1 ms even when dormant; switch its tick off once the kinematic switch applied
        if not S.get('pcc_tick_off') and S['state_t'] > 0.1:
            c.set_component_tick_enabled(False)
            S['pcc_tick_off'] = True
    if st == 'STAGGER':
        if S['state_t'] > S['stag']['hold']:
            play('idle', loop=True)
            set_state('STAND')
    elif st == 'FALL':
        pel = bone_loc(b, 'pelvis')
        low = (pel.z - S['ground_z']) < 45.0
        f = S['fall']
        if f['limp_t'] is None:
            a = min(1.0, S['state_t'] / P['fall_legs_soften'])
            m = dict(P['fall_mult'])
            for l in LEGS:
                l0 = f['legs0'] if f.get('legs0') is not None else P['fall_mult'][l]
                m[l] = l0 + (0.35 - l0) * a
            f['m'] = m
            apply_strengths(mult=m)
        if f['limp_t'] is None and (low or S['state_t'] > P['limp_after']):
            f['limp_t'] = 0.0
            log('limp start, pelvis h', round(pel.z - S['ground_z']))
        if f['limp_t'] is not None:
            f['limp_t'] += dt
            a = min(1.0, f['limp_t'] / P['limp_ramp'])
            m0 = f.get('m', P['fall_mult'])
            m = {l: m0.get(l, 1.0) + (P['limp_ps_mult'] - m0.get(l, 1.0)) * a for l in LIMBS}
            apply_strengths(mult=m, extra=P['limp_extra_damping'] * a)
            if a >= 1.0:
                set_state('DOWN')
                S['still'] = 0.0
    elif st == 'DOWN':
        v = b.get_physics_linear_velocity('pelvis')
        S['still'] = S['still'] + dt if vlen(v) < P['still_speed'] else 0.0
        if (S['state_t'] > P['down_min'] and S['still'] > P['still_time']) or S['state_t'] > P['down_max']:
            begin_getup()
    elif st == 'GETUP':
        # Only a visual blend from the lying ragdoll pose into the get-up clip: the bodies keep lying limp (no pull
        # toward the clip), so physics drives nothing here. Then the whole get-up is pure animation (GETUP_ANIM).
        g = S['getup']
        g['blend'] = max(0.0, g['blend'] - dt / P['getup_blend'])
        c.set_body_modifiers_in_set_physics_blend_weight('All', g['blend'])
        if g['blend'] <= 0.0:
            dormant(True)
            c.set_body_modifiers_in_set_physics_blend_weight('All', 1.0)  # kinematic bodies sit on the clip
            set_state('GETUP_ANIM')
            log('getup: pure animation')
    S['last'] = {'state': S['state'], 't': round(S['t'], 2)}


def _trampoline(dt):
    try:
        import sys
        sys.modules['ar_proto'].tick(dt)
    except Exception as e:
        LOG.append('TICK ERROR %r' % (e,))
        try:
            unregister_tick()
        except Exception:
            pass


def register_tick():
    unregister_tick()
    builtins.__dict__['_AR_TICK'] = unreal.register_slate_post_tick_callback(_trampoline)


def unregister_tick():
    h = builtins.__dict__.pop('_AR_TICK', None)
    if h is not None:
        unreal.unregister_slate_post_tick_callback(h)


def teardown(destroy=True):
    unregister_tick()
    if not destroy:
        return
    w = world()
    if not w:
        return
    for a in unreal.GameplayStatics.get_all_actors_with_tag(w, TAG):
        try:
            a.destroy_actor()
        except Exception:
            pass
    for k in ('control_actor', 'hero'):
        a = S.get(k)
        try:
            if a:
                a.destroy_actor()
        except Exception:
            pass


PROJ = 'AR_PROJ'


def drop(kind='crate', target='head', height=230.0, mass=12.0, speed=0.0, from_dir=None, size=0.35):
    """Spawn a physics crate above (or, with speed, flying at) a bone. Its collision with the body picks the reaction."""
    b = body()
    t = bone_loc(b, target)
    if speed > 0.0:
        d = from_dir or mesh_dir(1.0)          # from_dir: direction the crate travels
        dx, dy = norm2d(d[0], d[1])
        start = V(t.x - dx * 160.0, t.y - dy * 160.0, t.z - 4.0)
    else:
        start = V(t.x, t.y, t.z + height)
    a = spawn(unreal.StaticMeshActor, start, 17.0)
    a.tags = list(a.tags) + [TAG, PROJ]
    m = a.static_mesh_component
    m.set_mobility(unreal.ComponentMobility.MOVABLE)
    m.set_static_mesh(load('/Engine/BasicShapes/Cube'))
    m.set_world_scale3d(V(size, size, size))
    m.set_collision_profile_name('PhysicsActor')
    m.set_simulate_physics(True)
    m.set_mass_override_in_kg('None', mass, True)
    m.set_notify_rigid_body_collision(True)
    if speed > 0.0:
        m.set_physics_linear_velocity(V(dx * speed, dy * speed, 85.0), False, 'None')
    S.setdefault('props', []).append(a)
    S.setdefault('prop_speed', {})[a.get_name()] = speed if speed > 0.0 else math.sqrt(2.0 * 980.0 * height)
    log('drop', kind, target, 'mass', mass, 'speed', speed)
    return 'dropped %s on %s' % (kind, target)


def _on_body_hit(hit_comp, other_actor, other_comp, normal_impulse, hit):
    try:
        import sys
        sys.modules['ar_proto'].on_body_hit(hit_comp, other_actor, other_comp, normal_impulse, hit)
    except Exception as e:
        LOG.append('HIT CB ERROR %r' % (e,))


def on_body_hit(hit_comp, other_actor, other_comp, normal_impulse, hit_result):
    if not other_actor or PROJ not in [str(t) for t in other_actor.tags]:
        return
    imp = vlen(normal_impulse)
    tup = hit_result.to_tuple()
    bone = None
    for v in tup:
        if isinstance(v, unreal.Name) and str(v) in BONES:
            bone = str(v)
    vel = other_comp.get_physics_linear_velocity('None')
    mom = other_comp.get_mass() * max(vlen(vel), S.get('prop_speed', {}).get(other_actor.get_name(), 0.0))
    dx, dy = norm2d(vel.x, vel.y) if (abs(vel.x) + abs(vel.y)) > 1.0 else norm2d(*mesh_dir(-1.0)[:2])
    S.setdefault('impacts', []).append([round(S['t'], 2), str(other_actor.get_name()), bone, round(imp), round(mom)])
    # only a contact harder than normal motion reacts; a dormant body wakes up for it
    if S.get('state') not in ('STAND', 'STAGGER', 'DORMANT', 'GETUP_ANIM') or imp < P['imp_hit']:
        return
    other_actor.tags = [t for t in other_actor.tags if str(t) != PROJ]   # one reaction per prop
    bone = bone or 'spine_04'
    if mom >= P['mom_knockdown']:
        knockdown(bone, (dx, dy, 0.0), 0.6)
    elif mom >= P['mom_stagger'] and S.get('state') in ('STAND', 'DORMANT', 'GETUP_ANIM'):
        stagger(bone, (dx, dy, 0.0), 0.8)
    else:
        hit(bone, (dx, dy, 0.0), min(1.0, mom / P['mom_stagger']) * 0.8)
    log('impact', bone, round(imp), round(mom), S.get('state'))


def dormant(on=True):
    """Default state: pure animation. Every body kinematic (on the animated pose), every control disabled, and the
    control component's tick switched off a moment later by the tick. wake() / any reaction leaves it."""
    if on:
        pcc().set_controls_in_set_enabled('All', False)
        set_movement(LIMBS, True)
        S['pcc_tick_off'] = False
        set_state('DORMANT')
    else:
        wake()
    return S['state']


def schedule(events):
    """events: [(delay_s, fn_name, kwargs)]; run by the tick at world time t + delay."""
    t0 = S.get('t', 0.0)
    S['script'] = sorted([(t0 + d, fn, kw) for d, fn, kw in events], key=lambda e: e[0])
    return len(S['script'])


def mesh_dir(sign=1.0, side=0.0):
    """Direction from the hero's mesh facing: sign=+1 pushes the hero forward (hit from behind),
    -1 pushes it backward (hit from the front); side adds a sideways part (+ = to the hero's right)."""
    b = body()
    f = b.get_right_vector()
    r = b.get_forward_vector()
    # MetaHuman body: component +Y is the facing, component -X is the character's right
    return (f.x * sign - r.x * side, f.y * sign - r.y * side, 0.0)


def status():
    b = body()
    out = {'state': S.get('state'), 't': round(S.get('t', 0.0), 2), 'state_t': round(S.get('state_t', 0.0), 2),
           'anim': S.get('anim'), 'weak': {k: round(v, 2) for k, v in S.get('weak', {}).items()},
           'events': S.get('events'), 'log': LOG[-25:], 'tick': '_AR_TICK' in builtins.__dict__}
    try:
        if b:
            p = b.get_socket_location('pelvis')
            out['pelvis'] = [round(p.x), round(p.y), round(p.z)]
            h = b.get_socket_location('head')
            out['head'] = [round(h.x), round(h.y), round(h.z)]
            out['actor'] = str(S['hero'].get_actor_location())
    except Exception as e:
        out['err'] = str(e)
    return out
