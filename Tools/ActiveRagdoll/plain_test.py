"""plain_test.py - does the spine snap happen without Physics Control?

Spawns three more BP_Heroes beside the ar_proto Hero: a plain reference (animation only), one with the test physics
asset copy and one with the original PHYS_MHC_Hero. All play AS_Hero_Idle from the same frame. After 0.5 s the two
test Heroes simulate every body from spine_02 up with the engine's own calls (SetAllBodiesBelowSimulatePhysics), with
no Physics Control involved. Samples spine_02 / spine_04 / head against the reference every frame.
Results land in builtins._AR_PLAIN['results'].
"""
import builtins
import math

import unreal

import ar_proto as AR

T = builtins.__dict__.setdefault('_AR_PLAIN', {})
CS = unreal.RelativeTransformSpace.RTS_COMPONENT
BONES = ['pelvis', 'spine_02', 'spine_04', 'neck_01', 'head', 'hand_r']
ORIG_PA = '/Game/Characters/Hero/Assembled/Hero/Body/PHYS_MHC_Hero'
SIM_FROM = 'spine_02'


def now():
    return unreal.GameplayStatics.get_time_seconds(AR.world())


def hero_at(loc, yaw):
    cls = unreal.load_class(None, AR.HERO_BP + '.BP_Hero_C')
    a = AR.spawn(cls, loc, yaw)
    a.tags = list(a.tags) + [AR.TAG]
    b = [c for c in a.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == 'Body'][0]
    return a, b


def physics_body(b, pa_path):
    b.set_physics_asset(AR.load(pa_path), True)
    b.set_collision_object_type(unreal.CollisionChannel.ECC_PHYSICS_BODY)
    b.set_collision_response_to_all_channels(unreal.CollisionResponseType.ECR_BLOCK)
    b.set_collision_response_to_channel(unreal.CollisionChannel.ECC_PAWN, unreal.CollisionResponseType.ECR_IGNORE)
    b.set_collision_response_to_channel(unreal.CollisionChannel.ECC_CAMERA, unreal.CollisionResponseType.ECR_IGNORE)
    b.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)


def start(sim_delay=0.5, measure=2.5):
    stop()
    T.clear()
    h = AR.S['hero']
    base = h.get_actor_location()
    yaw = h.get_actor_rotation().yaw
    T['heroes'] = {
        'ref': hero_at(AR.V(base.x + 260.0, base.y, base.z), yaw),
        'copy': hero_at(AR.V(base.x - 260.0, base.y, base.z), yaw),
        'orig': hero_at(AR.V(base.x - 520.0, base.y, base.z), yaw),
    }
    physics_body(T['heroes']['copy'][1], AR.PA)
    physics_body(T['heroes']['orig'][1], ORIG_PA)
    idle = AR.load(AR.ANIM['idle'])
    for _, b in T['heroes'].values():
        b.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
        b.play_animation(idle, True)
        b.set_play_rate(1.0)
    AR.play('idle', loop=True)  # the Physics Control prototype, on the same frame, for comparison
    T['bodies'] = {'copy': T['heroes']['copy'][1], 'orig': T['heroes']['orig'][1], 'proto': AR.body()}
    T['t0'] = now()
    T['sim_delay'] = sim_delay
    T['measure'] = measure
    T['t_sim'] = None
    T['series'] = {k: [] for k in T['bodies']}
    T['acc'] = {k: {bn: [] for bn in BONES} for k in T['bodies']}
    T['done'] = False
    T['tick'] = unreal.register_slate_post_tick_callback(_tick)
    return {'heroes': {k: v[0].get_name() for k, v in T['heroes'].items()}}


def _tick(dt):
    try:
        if T.get('done') or not AR.world():
            stop()
            return
        t = now() - T['t0']
        if T['t_sim'] is None and t >= T['sim_delay']:
            for key in ('copy', 'orig'):
                b = T['bodies'][key]
                b.set_all_bodies_below_physics_blend_weight(SIM_FROM, 1.0, False, True)
                b.set_all_bodies_below_simulate_physics(SIM_FROM, True, True)
            T['t_sim'] = t
            T['sim_check'] = {k: T['bodies'][k].is_simulating_physics(SIM_FROM) for k in ('copy', 'orig')}
        if T['t_sim'] is None:
            return
        ts = t - T['t_sim']
        rb = T['heroes']['ref'][1]
        for key, b in T['bodies'].items():
            row = [round(ts, 3)]
            for bn in BONES:
                a = b.get_socket_transform(bn, CS).translation
                r = rb.get_socket_transform(bn, CS).translation
                d = (a.x - r.x, a.y - r.y, a.z - r.z)
                T['acc'][key][bn].append(d)
                if bn in ('spine_02', 'head'):
                    row.append(round(d[2], 2))
            if len(T['series'][key]) < 200:
                T['series'][key].append(row)
        if ts >= T['measure']:
            finish()
    except Exception as e:
        T['error'] = repr(e)
        T['done'] = True
        stop()


def finish():
    out = {'sim_check': T.get('sim_check')}
    for key, acc in T['acc'].items():
        rows = {}
        for bn, ds in acc.items():
            if not ds:
                continue
            n = len(ds)
            first = ds[0]
            last = [sum(d[i] for d in ds[-10:]) / len(ds[-10:]) for i in range(3)]
            rows[bn] = {'first_frame': [round(v, 2) for v in first], 'end_avg': [round(v, 2) for v in last],
                        'end_len': round(math.sqrt(sum(v * v for v in last)), 2), 'frames': n}
        out[key] = {'bones': rows, 'series': T['series'][key][::2][:40]}
    T['results'] = out
    T['done'] = True
    stop()


def stop():
    h = T.pop('tick', None)
    if h is not None:
        unreal.unregister_slate_post_tick_callback(h)
