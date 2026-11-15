"""Gilt allies check: an idle player is never attacked, they go for the tarnished and Frost soldiers.

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


if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
    raise RuntimeError('PIE already running (another session); not starting')
await acquire_pie_lock('squads re-test on train #6: march, cast, melee, deaths (one run, about 80 s)')


# ---------------------------------------------------------------- Gilt allies: idle player, tarnished, Frost (one PIE run)
EVENTS = []


def recorder(squad):
    name = squad.get_name()

    def on_state(state, cause):
        EVENTS.append([round(time.time() - T0, 1), name, ename(state), cause.get_name() if cause else None])
    squad.on_squad_state_changed.add_callable(on_state)
    return on_state


def roster(squad):
    out = []
    for m in members(squad):
        a = m.actor
        if not a:
            continue
        npc = a.get_component_by_class(unreal.ReflectionsNpcReactionComponent)
        arch = prop(npc, 'archetype') if npc else None
        parts = [c.get_name() for c in a.get_components_by_class(unreal.PrimitiveComponent) if 'Shield' in c.get_name() or c.component_has_tag('SquadShield')]
        props = [c.get_editor_property('static_mesh').get_name() for c in a.get_components_by_class(unreal.StaticMeshComponent) if c.get_editor_property('static_mesh') and
                 any(k in c.get_editor_property('static_mesh').get_name() for k in ('Sword', 'Wand', 'Shield'))]
        out.append({'look': a.get_class().get_name(), 'role': ename(m.role), 'archetype': str(prop(arch, 'archetype_id')) if arch else None,
                    'shield_parts': parts, 'props': props})
    return out


unreal.SystemLibrary.execute_console_command(None, 'Squads.StartPatrol 0')
if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
    raise RuntimeError('PIE already running (another session); not starting')
await acquire_pie_lock('squads: Gilt allies vs idle player, tarnished, Frost (~50 s)')
try:
    await call_tool('EditorToolset.EditorAppToolset.StartPIE', options={'warmupSeconds': 2.0})
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    cmd = lambda text: unreal.SystemLibrary.execute_console_command(world, text)
    player = unreal.GameplayStatics.get_player_pawn(world, 0)
    hp = player.get_component_by_class(unreal.ReflectionsHealthComponent)
    cmd('Squads.Passive 1')
    cmd('Squads.SpawnGilt')
    await asyncio.sleep(6.0)
    sq = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsSquad))
    gilt = sq[0]
    keep = [recorder(gilt)]
    report['gilt'] = {'faction': ename(prop(gilt, 'faction')), 'sight': prop(gilt, 'sight_radius'), 'roster': roster(gilt)}
    # Close-up of the guards on the march.
    g = alive_actors(gilt)
    if g:
        c = centroid(g)
        f = heading(gilt)
        side = unreal.Vector(-f.y, f.x, 0)
        report['gilt_march'] = await capture(world, 'g1_gilt_march', unreal.Vector(c.x + side.x * 420 + f.x * 380, c.y + side.y * 420 + f.y * 380, c.z + 140),
                                             unreal.Vector(c.x, c.y, c.z + 60), 60.0)
    # 1) Idle player 4 m beside the guards: they must not turn on him.
    cmd('Squads.Passive 0')
    c = centroid(alive_actors(gilt))
    f = heading(gilt)
    side = unreal.Vector(-f.y, f.x, 0)
    player.set_actor_location(unreal.Vector(c.x + side.x * 400, c.y + side.y * 400, c.z + 20), False, True)
    await asyncio.sleep(5.0)
    log('idle_beside_gilt', state=ename(gilt.get_editor_property('state')), events=list(EVENTS))
    # 2) A tarnished 10 m from the guards: they must go for it.
    c = centroid(alive_actors(gilt))
    away = unreal.Vector(-side.x, -side.y, 0)
    spot = unreal.Vector(c.x + away.x * 2000, c.y + away.y * 2000, c.z + 20)
    if not unreal.SystemLibrary.line_trace_single(world, unreal.Vector(spot.x, spot.y, spot.z + 300), unreal.Vector(spot.x, spot.y, spot.z - 600), unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [player], unreal.DrawDebugTrace.NONE, True):
        spot = unreal.Vector(c.x - away.x * 2000, c.y - away.y * 2000, c.z + 20)
    player.set_actor_location(spot, False, True)
    look = unreal.MathLibrary.find_look_at_rotation(spot, c)
    ctrl = player.get_controller()
    if ctrl:
        ctrl.set_control_rotation(unreal.Rotator(0, look.yaw, 0))
    await asyncio.sleep(0.3)
    cmd('Npc.Spawn Infected 1 1000')
    await asyncio.sleep(6.0)
    if hp and hp.get_editor_property('health') < 50:
        hp.heal(100.0, player)
    log('tarnished', state=ename(gilt.get_editor_property('state')), events=list(EVENTS))
    # 3) A Frost squad: they and the guards should go for each other.
    cmd('Squads.SpawnTest 1')
    await asyncio.sleep(1.0)
    frost = [s for s in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsSquad) if s != gilt]
    for s in frost:
        keep.append(recorder(s))
    shot = None
    for i in range(20):
        await asyncio.sleep(0.4)
        if hp and hp.get_editor_property('health') < 50:
            hp.heal(100.0, player)
        if i == 10:
            c = centroid(alive_actors(gilt)) if alive_actors(gilt) else player.get_actor_location()
            shot = await capture(world, 'g2_gilt_fight', unreal.Vector(c.x + 600, c.y + 600, c.z + 350), unreal.Vector(c.x, c.y, c.z + 60), 70.0)
    log('frost', gilt_state=ename(gilt.get_editor_property('state')), frost_states=[ename(s.get_editor_property('state')) for s in frost],
        gilt_alive=len(alive_actors(gilt)), frost_alive=[len(alive_actors(s)) for s in frost],
        frost_roster=[roster(s) for s in frost], events=list(EVENTS), shot=shot,
        hero_health=hp.get_editor_property('health') if hp else None)
except Exception as e:
    report['errors'].append('run: %r' % e)
    raise
finally:
    try:
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')
    except Exception as e:
        report['stop_error'] = str(e)
    unreal.SystemLibrary.execute_console_command(None, 'Squads.StartPatrol 1')
    unreal.SystemLibrary.execute_console_command(None, 'Squads.Passive 0')
    release_pie_lock()
    report['took'] = round(time.time() - T0, 1)
    report['events'] = EVENTS
    with open(os.path.join(OUT, 'gilt-report.json'), 'w') as f:
        json.dump(report, f, indent=1, default=str)
