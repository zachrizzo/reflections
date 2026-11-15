"""PIE check: player spells kill soldiers -> NPC death, ragdoll, coin; a hit caster flees; frame cost of two squads.

Run with the same compile/eval wrapper as test_squads_pie.py. One PIE run (~45 s), stopped in `finally`.
Needs the NPC session's lethal-hit guard (BodyPoseReady) in the loaded DLL: without it a lethal hit crashed the
editor at 11:53. Writes Saved/SquadsTest/kill-report.json and 7_ragdoll.png.
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


async def acquire_pie_lock(purpose, seconds=240, wait_limit=600):
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
report = {'steps': []}
T0 = time.time()
KILLS = globals().get('KILLS', True)


def ename(e):
    return getattr(e, 'name', str(e))


def unwrap(r):
    return r.get('returnValue', r) if isinstance(r, dict) and 'returnValue' in r else r


def log(step, **kw):
    kw['step'] = step
    kw['t'] = round(time.time() - T0, 1)
    report['steps'].append(kw)


def members(squad):
    return list(squad.get_editor_property('members'))


def body_of(actor):
    for c in actor.get_components_by_class(unreal.SkeletalMeshComponent):
        if c.get_name() == 'Body':
            return c
    return None


async def frame_ms(samples=12):
    vals = []
    for _ in range(samples):
        await asyncio.sleep(0.15)
        t = unwrap(await call_tool('PerfToolset.StatsToolset.GetFrameTimings'))
        vals.append((t.get('frameMs', 0), t.get('gameThreadMs', 0), t.get('gpuMs', 0)))
    n = len(vals)
    return {'frame': round(sum(v[0] for v in vals) / n, 2), 'game': round(sum(v[1] for v in vals) / n, 2),
            'gpu': round(sum(v[2] for v in vals) / n, 2)}


async def capture(world, name, cam_loc, look_at, fov=60.0):
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


if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
    raise RuntimeError('PIE already running (another session); not starting')
await acquire_pie_lock('squads: kills, ragdoll, coins, flee, frame cost')
unreal.SystemLibrary.execute_console_command(None, 'Squads.StartPatrol 0')  # scripted checks index their own squads
await call_tool('EditorToolset.EditorAppToolset.StartPIE', options={'warmupSeconds': 2.0})
try:
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    player = unreal.GameplayStatics.get_player_pawn(world, 0)
    spells = player.get_component_by_class(unreal.ReflectionsSpellCombatComponent)
    hp = player.get_component_by_class(unreal.ReflectionsHealthComponent)
    report['perf_without_squads'] = await frame_ms()
    cmd = lambda text: unreal.SystemLibrary.execute_console_command(world, text)
    cmd('Squads.Passive 1')
    cmd('Squads.SpawnTest 2')
    await asyncio.sleep(7.0)
    report['perf_two_squads_marching'] = await frame_ms()
    squad = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsSquad))[0]
    # Builds before 12:45 still turned the old physics flinch on for soldiers (it emptied body poses and crashed the
    # editor twice); switch it off at runtime before any hit, and refuse to continue if that is not possible.
    flinch = []
    for sq in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsSquad):
        for m in members(sq):
            npc = m.actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent) if m.actor else None
            if npc:
                npc.set_editor_property('enable_physical_hit_reaction', False)
                flinch.append(npc.get_editor_property('enable_physical_hit_reaction'))
    report['flinch_after_override'] = flinch
    if not flinch or any(flinch):
        raise RuntimeError('could not switch the physics flinch off; not hitting soldiers')
    coins_before = coins(world)
    cmd('Squads.Passive 0')
    cmd('Squads.Engage 0')
    await asyncio.sleep(1.5)

    # One hit on a caster: the NPC system makes it flinch away (flee), the squad lets go and takes it back.
    caster = [m.actor for m in members(squad) if m.actor and ename(m.role) == 'CASTER'][0]
    shoot(spells, player, caster, unreal.HeroSpell.FIRE)
    await asyncio.sleep(0.6)
    log('caster_hit', caster=caster.get_name(),
        member_state=[ename(m.state) for m in members(squad) if m.actor == caster],
        reaction=ename(caster.get_component_by_class(unreal.ReflectionsNpcReactionComponent).get_editor_property('reaction')))

    # Kill three soldiers with real player spells.
    targets = [m.actor for m in members(squad) if m.actor][:3] if KILLS else []
    for target in targets:
        for shot in range(7):
            if hp and hp.get_editor_property('health') < 50:
                hp.heal(100.0, player)
            h = target.get_component_by_class(unreal.ReflectionsHealthComponent)
            if h and h.get_editor_property('health') <= 0:
                break
            shoot(spells, player, target, unreal.HeroSpell.FIRESTORM if shot % 2 else unreal.HeroSpell.FIRE)
            await asyncio.sleep(0.5)
    await asyncio.sleep(1.5)
    dead = []
    for m in members(squad):
        if KILLS and m.actor and ename(m.state) == 'DEAD':
            b = body_of(m.actor)
            dead.append({'actor': m.actor.get_name(), 'ragdoll': bool(b and b.is_simulating_physics()),
                         'body_z': round(b.get_socket_location('pelvis').z) if b else None})
    log('kills', dead=dead, alive=squad.get_alive_count(), squad_state=ename(squad.get_editor_property('state')),
        coins_before=coins_before, coins_after=coins(world),
        caster_state_now=[ename(m.state) for m in members(squad) if m.actor == caster])
    if dead:
        d0 = [m.actor for m in members(squad) if m.actor and ename(m.state) == 'DEAD'][0]
        p = body_of(d0).get_socket_location('pelvis')
        report['ragdoll_shot'] = await capture(world, '7_ragdoll', unreal.Vector(p.x + 300, p.y + 220, p.z + 230), p, 60.0)
    await asyncio.sleep(2.0)
    log('later', caster_state=[ename(m.state) for m in members(squad) if m.actor == caster],
        casts=[m.casts_released for m in members(squad)])
finally:
    try:
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')
        unreal.SystemLibrary.execute_console_command(None, 'Squads.StartPatrol 1')
    except Exception as e:
        report['stop_error'] = str(e)
    release_pie_lock()
    with open(os.path.join(OUT, 'kill-report.json'), 'w') as f:
        json.dump(report, f, indent=1, default=str)
