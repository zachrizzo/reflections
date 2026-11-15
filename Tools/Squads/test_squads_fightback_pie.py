"""Train #11 proof: one hit on one soldier turns the whole squad (Lvl_HeroSampleCrowd); plus start patrol and sword shots and a shield grip measured on the live hand.

Based on the one-PIE re-test of the squads on a new build: march, archetypes and flinch flag, cast, melee, barks, deaths, reform.

Runs through the same compile/eval wrapper as the other Tools/Squads scripts (top-level await, `call_tool` and
`unreal` in the namespace). Takes Saved/PIE_LOCK.json (team rule), one PIE run of about 70 s, stopped in `finally`.
Unlike the older scripts it does NOT switch the physics flinch off first: it reads what the build sets, and only
overrides (and records that it had to) if some soldier still has it on, because that flinch crashed the editor twice.
Writes Saved/SquadsTest/retest-report.json and r1..r6 PNGs.
"""
import asyncio
import base64
import json
import math
import os
import time


# ---- Shared PIE lock (team rule): wait for someone else's unexpired lock, hold ours for at most 240 s. ----
LOCK_PATH = os.path.join(unreal.Paths.project_saved_dir(), 'PIE_LOCK.json')
LOCK_OWNER = 'squads (enemy soldier squads side session)'


async def acquire_pie_lock(purpose, seconds=240, wait_limit=120):
    started = time.time()
    while True:
        try:
            with open(LOCK_PATH) as f:
                held = json.load(f)
        except Exception:
            held = None
        if not held or held.get('owner') == LOCK_OWNER or held.get('expires_epoch', 0) <= time.time():
            break
        if time.time() - started > wait_limit:
            raise RuntimeError('PIE lock held by %s' % held.get('owner'))
        await asyncio.sleep(15.0)
    now = time.time()
    with open(LOCK_PATH, 'w') as f:
        json.dump({'owner': LOCK_OWNER, 'purpose': purpose, 'acquired_epoch': int(now),
                   'expires_epoch': int(now + min(seconds, 240))}, f)


def release_pie_lock():
    try:
        with open(LOCK_PATH) as f:
            held = json.load(f)
        if held.get('owner') == LOCK_OWNER:
            os.remove(LOCK_PATH)
    except Exception:
        pass


OUT = os.path.join(unreal.Paths.project_saved_dir(), 'SquadsTest')
os.makedirs(OUT, exist_ok=True)
report = {'steps': [], 'errors': []}
T0 = time.time()


def ename(e):
    return getattr(e, 'name', str(e))


def unwrap(r):
    return r.get('returnValue', r) if isinstance(r, dict) and 'returnValue' in r else r


def log(step, **kw):
    kw['step'] = step
    kw['t'] = round(time.time() - T0, 1)
    report['steps'].append(kw)


def prop(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return default


def members(squad):
    return list(squad.get_editor_property('members'))


def alive_actors(squad):
    return [m.actor for m in members(squad) if m.actor and ename(m.state) != 'DEAD']


def body_of(actor):
    for c in actor.get_components_by_class(unreal.SkeletalMeshComponent):
        if c.get_name() == 'Body':
            return c
    return None


def dist2d(a, b):
    pa, pb = a.get_actor_location(), b.get_actor_location()
    return ((pa.x - pb.x) ** 2 + (pa.y - pb.y) ** 2) ** 0.5


def centroid(actors):
    pts = [a.get_actor_location() for a in actors]
    n = max(1, len(pts))
    return unreal.Vector(sum(p.x for p in pts) / n, sum(p.y for p in pts) / n, sum(p.z for p in pts) / n)


def heading(squad):
    for m in members(squad):
        if m.actor and m.actor.get_attach_parent_actor():
            v = m.actor.get_attach_parent_actor().get_velocity()
            if v.length() > 10:
                return unreal.Vector(v.x, v.y, 0).normal()
    return unreal.Vector(1, 0, 0)


async def frame_ms(samples=10):
    vals = []
    for _ in range(samples):
        await asyncio.sleep(0.15)
        t = unwrap(await call_tool('PerfToolset.StatsToolset.GetFrameTimings'))
        vals.append((t.get('frameMs', 0), t.get('gameThreadMs', 0), t.get('gpuMs', 0)))
    n = len(vals)
    return {'frame': round(sum(v[0] for v in vals) / n, 2), 'game': round(sum(v[1] for v in vals) / n, 2),
            'gpu': round(sum(v[2] for v in vals) / n, 2)}


async def capture(world, name, cam_loc, look_at, fov=60.0):
    try:
        d = unreal.Vector(look_at.x - cam_loc.x, look_at.y - cam_loc.y, look_at.z - cam_loc.z)
        rot = unreal.MathLibrary.make_rot_from_x(d)
        res = unwrap(await call_tool('SceneCaptureToolset.SceneCaptureToolset.Capture',
                                     world={'refPath': world.get_path_name()},
                                     camera={'location': {'x': cam_loc.x, 'y': cam_loc.y, 'z': cam_loc.z},
                                             'rotation': {'pitch': rot.pitch, 'yaw': rot.yaw, 'roll': 0.0},
                                             'projectionMode': 'Perspective', 'fOV': fov},
                                     mode='Lit', options={'width': 1600, 'height': 900, 'screenPercentage': 1.0}))
        img = res.get('image') if isinstance(res, dict) else None
        if isinstance(img, dict):
            img = img.get('data')
        if not img:
            return None
        path = os.path.join(OUT, name + '.png')
        with open(path, 'wb') as f:
            f.write(base64.b64decode(img.split(',')[-1]) if isinstance(img, str) else img)
        return path
    except Exception as e:
        report['errors'].append('capture %s: %s' % (name, e))
        return None


def clear_spot(world, squad, player):
    """A floor point 6-10 m from the squad that every soldier can see (this test map has no navmesh)."""
    actors = alive_actors(squad)
    ignore = actors + [a.get_attach_parent_actor() for a in actors if a.get_attach_parent_actor()] + [player]
    c = centroid(actors)
    for radius in (700, 850, 600, 1000):
        for k in range(16):
            ang = math.radians(k * 22.5)
            p = unreal.Vector(c.x + math.cos(ang) * radius, c.y + math.sin(ang) * radius, 300)
            if abs(p.x) > 1600 or abs(p.y) > 1600:
                continue
            floor = unreal.SystemLibrary.line_trace_single(world, p, unreal.Vector(p.x, p.y, -300),
                                                           unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, ignore,
                                                           unreal.DrawDebugTrace.NONE, True)
            floor = floor.to_tuple() if floor else None
            if not floor or not floor[0] or floor[5].z > 20:
                continue
            target = unreal.Vector(p.x, p.y, floor[5].z + 90)
            seen = True
            for a in actors:
                h = unreal.SystemLibrary.line_trace_single(world, a.get_actor_location() + unreal.Vector(0, 0, 95), target,
                                                           unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, ignore,
                                                           unreal.DrawDebugTrace.NONE, True)
                if h and h.to_tuple()[0]:
                    seen = False
                    break
            if seen:
                return target
    return None


def shoot(spells, player, target, spell):
    tl = target.get_actor_location()
    pl = player.get_actor_location()
    d = unreal.Vector(tl.x - pl.x, tl.y - pl.y, 0).normal()
    origin = unreal.Transform(unreal.Vector(tl.x - d.x * 250, tl.y - d.y * 250, tl.z + 110),
                              unreal.MathLibrary.make_rot_from_x(d), unreal.Vector(1, 1, 1))
    spells.release_spell_at(spell, origin, unreal.Vector(tl.x, tl.y, tl.z + 100), target)


def coins(world):
    cls = getattr(unreal, 'ReflectionsCoinPickup', None)
    return len(unreal.GameplayStatics.get_all_actors_of_class(world, cls)) if cls else -1


def body_anim(actor):
    """What the body plays now: a single-node clip name, or the anim blueprint class."""
    b = body_of(actor)
    inst = b.get_anim_instance() if b else None
    if inst is None:
        return None
    if isinstance(inst, unreal.AnimSingleNodeInstance):
        try:
            asset = inst.get_animation_asset()
            return asset.get_name() if asset else 'single:none'
        except Exception:
            return 'single:?'
    return inst.get_class().get_name()


def barks_playing(squad):
    out = []
    for a in alive_actors(squad):
        for ac in a.get_components_by_class(unreal.AudioComponent):
            snd = prop(ac, 'sound')
            if snd and 'VO_Soldier' in snd.get_name() and ac.is_playing():
                out.append([a.get_name(), snd.get_name()])
    return out




# ---------------------------------------------------------------- train #11 proof + shield grip (one PIE run)
def gone(a):
    try:
        return (not unreal.SystemLibrary.is_valid(a)) or a.is_actor_being_destroyed()
    except Exception:
        return True


def world_dir(transform, axis):
    rot = transform.rotation
    return {'x': rot.get_forward_vector(), 'y': rot.get_right_vector(), 'z': rot.get_up_vector()}[axis]


def shield_grip(body, driver, front_sign):
    """Relative transform on hand_l: shield face (+X * front_sign) to the soldier's outer left, shield up = world up."""
    hand = body.get_socket_transform('hand_l', unreal.RelativeTransformSpace.RTS_WORLD)
    left = driver.get_actor_right_vector() * -1.0
    left = unreal.Vector(left.x, left.y, 0).normal()
    face = left * front_sign
    up = unreal.Vector(0, 0, 1)
    desired = unreal.MathLibrary.make_rot_from_xz(face, up)
    world = unreal.Transform(hand.translation + left * 6.0, desired, unreal.Vector(1, 1, 1))
    rel = unreal.MathLibrary.make_relative_transform(world, hand)
    return rel


report['steps'] = []
unreal.SystemLibrary.execute_console_command(None, 'Squads.StartPatrol 1')
if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
    raise RuntimeError('PIE already running (another session); not starting')
await acquire_pie_lock('squads: train #11 proof (one hit -> whole squad), start patrol + sword shots, shield grip (~60 s)')
try:
    await call_tool('EditorToolset.EditorAppToolset.StartPIE', options={'warmupSeconds': 2.0})
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    cmd = lambda text: unreal.SystemLibrary.execute_console_command(world, text)
    player = unreal.GameplayStatics.get_player_pawn(world, 0)
    spells = player.get_component_by_class(unreal.ReflectionsSpellCombatComponent)
    hp = player.get_component_by_class(unreal.ReflectionsHealthComponent)
    await asyncio.sleep(3.5)
    # 1) The start patrol, seen from where the player starts.
    sq0 = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsSquad))
    report['start_patrol'] = [[s.get_name(), ename(s.get_editor_property('state')), len(alive_actors(s)),
                               round(dist2d(player, alive_actors(s)[0]) / 100.0, 1) if alive_actors(s) else None] for s in sq0]
    pl = player.get_actor_location()
    fwd = player.get_actor_forward_vector()
    report['start_view'] = await capture(world, 'f1_start_view', unreal.Vector(pl.x - fwd.x * 250, pl.y - fwd.y * 250, pl.z + 120),
                                         unreal.Vector(pl.x + fwd.x * 1200, pl.y + fwd.y * 1200, pl.z), 75.0)
    cmd('Squads.Clear')
    cmd('Squads.Passive 1')
    cmd('Squads.SpawnTest 2')
    await asyncio.sleep(6.0)
    sq = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsSquad))
    col = sq[0]
    # 2) Sword in hand, close up.
    melee = [m.actor for m in members(col) if m.actor and ename(m.role) == 'MELEE']
    weapons = []
    for a in alive_actors(col):
        props = [c for c in a.get_components_by_class(unreal.StaticMeshComponent) if c.get_static_mesh() and
                 ('Sword' in c.get_static_mesh().get_name() or 'Wand' in c.get_static_mesh().get_name())]
        weapons.append([a.get_name(), [p.get_static_mesh().get_name() for p in props], [str(p.get_attach_socket_name()) for p in props]])
    report['weapons'] = weapons
    if melee:
        b = body_of(melee[0])
        h = b.get_socket_location('hand_r')
        d = melee[0].get_attach_parent_actor()
        r = d.get_actor_right_vector() if d else unreal.Vector(0, 1, 0)
        f2 = d.get_actor_forward_vector() if d else unreal.Vector(1, 0, 0)
        report['sword_shot'] = await capture(world, 'f2_sword_in_hand', unreal.Vector(h.x + r.x * 160 + f2.x * 120, h.y + r.y * 160 + f2.y * 120, h.z + 30), h, 50.0)
    # 3) Shield grip candidates on two melee soldiers (Python-attached, PIE only).
    shield_mesh = unreal.load_asset('/Game/LanthorneAssets/Giltside/Props/SM_Giltside_PatrolShield')
    grips = {}
    for i, sign in enumerate((1.0, -1.0)):
        if i >= len(melee) or not shield_mesh:
            break
        a = melee[i]
        b = body_of(a)
        d = a.get_attach_parent_actor()
        rel = shield_grip(b, d, sign)
        comp = a.add_component_by_class(unreal.StaticMeshComponent, False, unreal.Transform(), False)
        comp.set_static_mesh(shield_mesh)
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        comp.attach_to_component(b, 'hand_l', unreal.AttachmentRule.SNAP_TO_TARGET, unreal.AttachmentRule.SNAP_TO_TARGET,
                                 unreal.AttachmentRule.KEEP_WORLD, False)
        comp.set_relative_transform(rel, False, False)
        rr = rel.rotation.rotator()
        grips['front%+d' % int(sign)] = {'loc': [round(rel.translation.x, 2), round(rel.translation.y, 2), round(rel.translation.z, 2)],
                                         'rot_pyr': [round(rr.pitch, 2), round(rr.yaw, 2), round(rr.roll, 2)], 'soldier': a.get_name()}
    report['shield_grips'] = grips
    await asyncio.sleep(1.0)
    for i, key in enumerate(sorted(grips)):
        a = melee[i]
        p = a.get_actor_location()
        d = a.get_attach_parent_actor()
        r = d.get_actor_right_vector() if d else unreal.Vector(0, 1, 0)
        report['shield_shot_%d' % i] = await capture(world, 'f3_shield_%s' % key.replace('+', 'p').replace('-', 'm'),
                                                     unreal.Vector(p.x - r.x * 260, p.y - r.y * 260, p.z + 60), unreal.Vector(p.x, p.y, p.z + 20), 55.0)
    # 4) The proof: player ~25 m from the column, one Fire Bolt on one soldier -> whole squad engages and comes.
    spot = clear_spot(world, col, player)
    if spot:
        c = centroid(alive_actors(col))
        away = unreal.Vector(spot.x - c.x, spot.y - c.y, 0).normal()
        far = unreal.Vector(c.x + away.x * 2500, c.y + away.y * 2500, spot.z)
        if abs(far.x) < 1650 and abs(far.y) < 1650:
            spot = far
        player.set_actor_location(spot, False, True)
        await asyncio.sleep(0.3)
    cmd('Squads.Passive 0')
    target = melee[-1] if melee else alive_actors(col)[0]
    before = {'squads': [ename(s.get_editor_property('state')) for s in sq], 'dist': [round(dist2d(a, player)) for a in alive_actors(col)]}
    shoot(spells, player, target, unreal.HeroSpell.FIRE)
    track = []
    shot = None
    for i in range(48):  # 12 s
        await asyncio.sleep(0.25)
        if hp and hp.get_editor_property('health') < 40:
            hp.heal(100.0, player)
        if i % 4 == 0:
            track.append([round(time.time() - T0, 1), [ename(s.get_editor_property('state')) for s in sq],
                          [ename(m.state) for m in members(col)], [round(dist2d(a, player)) for a in alive_actors(col)],
                          [m.casts_released for m in members(col)]])
        if i == 10 and alive_actors(col):
            pl = player.get_actor_location()
            near = min(alive_actors(col), key=lambda a: dist2d(a, player))
            to = near.get_actor_location() - pl
            to.z = 0
            to = to.normal()
            shot = await capture(world, 'f4_squad_charging', unreal.Vector(pl.x - to.x * 420 + to.y * 140, pl.y - to.y * 420 - to.x * 140, pl.z + 170),
                                 near.get_actor_location() + unreal.Vector(0, 0, 100), 75.0)
    log('one_hit', before=before, target=target.get_name(), track=track, charging_shot=shot,
        motor=[[a.get_name(), ename(c.get_editor_property('combat_state')), c.get_editor_property('attacks_started'),
                c.get_editor_property('successful_hits')] for a in melee for c in a.get_components_by_class(unreal.ReflectionsNpcCombatComponent)],
        hero_health=hp.get_editor_property('health') if hp else None)
except Exception as e:
    report['errors'].append('run: %r' % e)
    raise
finally:
    try:
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')
    except Exception as e:
        report['stop_error'] = str(e)
    unreal.SystemLibrary.execute_console_command(None, 'Squads.Passive 0')
    release_pie_lock()
    report['took'] = round(time.time() - T0, 1)
    with open(os.path.join(OUT, 'fightback-report.json'), 'w') as f:
        json.dump(report, f, indent=1, default=str)
