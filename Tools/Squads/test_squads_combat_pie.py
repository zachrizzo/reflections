"""PIE check (no kills): one squad breaks formation, melee close in, casters cast, then the squad reforms.

Run through the same compile/eval wrapper as test_squads_pie.py. One PIE run (~40 s), stopped in `finally`.
Writes Saved/SquadsTest/combat-report.json and 5_spell_in_flight.png.
"""
import asyncio
import base64
import json
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
SQUAD_INDEX = globals().get('SQUAD_INDEX', 0)


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


def clear_spot(world, squad, player):
    """A floor point 6-9 m from the squad that every soldier can see (this test map has no navmesh)."""
    import math
    actors = [m.actor for m in members(squad) if m.actor]
    ignore = actors + [a.get_attach_parent_actor() for a in actors if a.get_attach_parent_actor()] + [player]
    c = unreal.Vector(sum(a.get_actor_location().x for a in actors) / len(actors),
                      sum(a.get_actor_location().y for a in actors) / len(actors), 0)
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


def dist2d(a, b):
    pa, pb = a.get_actor_location(), b.get_actor_location()
    return ((pa.x - pb.x) ** 2 + (pa.y - pb.y) ** 2) ** 0.5


if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
    raise RuntimeError('PIE already running (another session); not starting')
await acquire_pie_lock('squads: one squad fights, then reforms')
unreal.SystemLibrary.execute_console_command(None, 'Squads.StartPatrol 0')  # scripted checks index their own squads
await call_tool('EditorToolset.EditorAppToolset.StartPIE', options={'warmupSeconds': 2.0})
try:
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    unreal.SystemLibrary.execute_console_command(world, 'Squads.Passive 1')
    unreal.SystemLibrary.execute_console_command(world, 'Squads.SpawnTest %d' % (SQUAD_INDEX + 1))
    await asyncio.sleep(8.0)
    squad = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsSquad))[SQUAD_INDEX]
    for sq in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsSquad):
        for m in members(sq):
            npc = m.actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent) if m.actor else None
            if npc:
                npc.set_editor_property('enable_physical_hit_reaction', False)
    player = unreal.GameplayStatics.get_player_pawn(world, 0)
    hp = player.get_component_by_class(unreal.ReflectionsHealthComponent)
    melee = [m.actor for m in members(squad) if m.actor and ename(m.role) == 'MELEE']
    spot = clear_spot(world, squad, player)
    if spot:
        player.set_actor_location(spot, False, True)
        await asyncio.sleep(0.3)
    log('before', spot=str(spot), state=ename(squad.get_editor_property('state')), melee_dist=[round(dist2d(a, player)) for a in melee])
    unreal.SystemLibrary.execute_console_command(world, 'Squads.Passive 0')
    unreal.SystemLibrary.execute_console_command(world, 'Squads.Engage %d' % SQUAD_INDEX)
    shot = None
    seen_projectile = False
    for i in range(40):
        await asyncio.sleep(0.25)
        if hp and hp.get_editor_property('health') < 40:
            hp.heal(100.0, player)
        if i == 14:
            # Melee closing in, seen from behind the player.
            pl = player.get_actor_location()
            near = min(melee, key=lambda a: dist2d(a, player))
            to = near.get_actor_location() - pl
            to.z = 0
            to = to.normal()
            cam = unreal.Vector(pl.x - to.x * 380 + to.y * 120, pl.y - to.y * 380 - to.x * 120, pl.z + 160)
            report['melee_shot'] = await capture(world, '6_melee_closing_in_%d' % SQUAD_INDEX, cam, near.get_actor_location() + unreal.Vector(0, 0, 100), 70.0)
        projectiles = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsSpellProjectile))
        mine = [p for p in projectiles if p.get_owner() and p.get_owner() in [m.actor for m in members(squad)]]
        if mine and not seen_projectile:
            seen_projectile = True
            p = mine[0].get_actor_location()
            pl = player.get_actor_location()
            mid = unreal.Vector((p.x + pl.x) / 2, (p.y + pl.y) / 2, p.z)
            d = unreal.Vector(pl.x - p.x, pl.y - p.y, 0).normal()
            side = unreal.Vector(-d.y, d.x, 0)
            shot = await capture(world, '5_spell_in_flight_%d' % SQUAD_INDEX, unreal.Vector(mid.x + side.x * 700, mid.y + side.y * 700, mid.z + 180),
                                 mid, 70.0)
    log('fight', state=ename(squad.get_editor_property('state')),
        melee_dist=[round(dist2d(a, player)) for a in melee],
        motor=[[ename(c.get_editor_property('combat_state')), c.get_editor_property('attacks_started'), c.get_editor_property('successful_hits')]
               for a in melee for c in a.get_components_by_class(unreal.ReflectionsNpcCombatComponent)],
        casts=[m.casts_released for m in members(squad)], projectile_seen=seen_projectile, shot=shot,
        hero_health=hp.get_editor_property('health') if hp else None)
    unreal.SystemLibrary.execute_console_command(world, 'Squads.Passive 1')
    unreal.SystemLibrary.execute_console_command(world, 'Squads.Reform')
    await asyncio.sleep(9.0)
    log('reform', state=ename(squad.get_editor_property('state')),
        members=[ename(m.state) for m in members(squad)])
finally:
    try:
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')
        unreal.SystemLibrary.execute_console_command(None, 'Squads.StartPatrol 1')
    except Exception as e:
        report['stop_error'] = str(e)
    release_pie_lock()
    with open(os.path.join(OUT, 'combat-report-%d.json' % SQUAD_INDEX), 'w') as f:
        json.dump(report, f, indent=1, default=str)
