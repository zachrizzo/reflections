"""One-PIE re-test of the squads on a new build: march, archetypes and flinch flag, cast, melee, barks, deaths, reform.

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


if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
    raise RuntimeError('PIE already running (another session); not starting')
await acquire_pie_lock('squads re-test on train #6: march, cast, melee, deaths (one run, about 80 s)')
unreal.SystemLibrary.execute_console_command(None, 'Squads.StartPatrol 0')  # scripted checks index their own squads
await call_tool('EditorToolset.EditorAppToolset.StartPIE', options={'warmupSeconds': 2.0})
try:
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    cmd = lambda text: unreal.SystemLibrary.execute_console_command(world, text)
    player = unreal.GameplayStatics.get_player_pawn(world, 0)
    spells = player.get_component_by_class(unreal.ReflectionsSpellCombatComponent)
    hp = player.get_component_by_class(unreal.ReflectionsHealthComponent)
    cmd('Squads.Passive 1')
    cmd('Squads.SpawnTest 2')
    await asyncio.sleep(8.0)
    sq = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsSquad))

    # --- What the build gives each soldier (no overrides yet). ---
    roster, flinch_on = [], []
    for i, s in enumerate(sq):
        for m in members(s):
            if not m.actor:
                continue
            npc = m.actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent)
            arch = prop(npc, 'archetype') if npc else None
            row = {'squad': i, 'look': m.actor.get_class().get_name(), 'role': ename(m.role), 'state': ename(m.state),
                   'archetype': str(prop(arch, 'archetype_id')) if arch else None,
                   'archetype_obj': arch.get_name() if arch else None,
                   'archetype_flinch': prop(arch, 'physical_hit_reaction') if arch else None,
                   'component_flinch': prop(npc, 'enable_physical_hit_reaction') if npc else None,
                   'ragdoll_on_death': prop(npc, 'enable_ragdoll_on_death') if npc else None,
                   'has_spell_component': bool(m.actor.get_component_by_class(unreal.ReflectionsSpellCombatComponent))}
            roster.append(row)
            if npc and (row['component_flinch'] and row['archetype_flinch'] is not False):
                flinch_on.append(m.actor.get_name())
    report['roster'] = roster
    report['caster_tuning'] = [{k: str(prop(s, k)) for k in ('caster_min_range', 'caster_max_range', 'cast_range',
                                                               'cast_cooldown', 'cast_windup', 'caster_damage_scale',
                                                               'caster_spells', 'cast_animations')} for s in sq]
    # Safety: the old flinch crashed the editor; if the build still leaves it on anywhere, switch it off and say so.
    report['flinch_on_from_build'] = flinch_on
    if flinch_on:
        for s in sq:
            for m in members(s):
                npc = m.actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent) if m.actor else None
                if npc:
                    npc.set_editor_property('enable_physical_hit_reaction', False)
    log('spawned', squads=[(s.get_name(), ename(s.get_editor_property('state')), s.get_alive_count()) for s in sq])

    # --- March: both squads, captures and frame cost. ---
    col = sq[0]
    c = centroid(alive_actors(col))
    fwd = heading(col)
    side = unreal.Vector(-fwd.y, fwd.x, 0)
    report['march_column'] = await capture(world, 'r1_march_column', unreal.Vector(c.x + side.x * 650 + fwd.x * 500, c.y + side.y * 650 + fwd.y * 500, c.z + 330),
                                           unreal.Vector(c.x, c.y, c.z + 80))
    if len(sq) > 1:
        c2 = centroid(alive_actors(sq[1]))
        f2 = heading(sq[1])
        report['march_line'] = await capture(world, 'r2_march_line', unreal.Vector(c2.x + f2.x * 900, c2.y + f2.y * 900, c2.z + 380),
                                             unreal.Vector(c2.x, c2.y, c2.z + 80))
    report['perf_two_squads_marching'] = await frame_ms()
    log('marching', states=[ename(s.get_editor_property('state')) for s in sq],
        member_states=[[ename(m.state) for m in members(s)] for s in sq],
        march_clip=[[bool(m.march_clip_active) if hasattr(m, 'march_clip_active') else None for m in members(s)] for s in sq])

    # --- Engage squad 0 from a spot every soldier can see. Squad 1 should keep marching unless it spots us. ---
    melee = [m.actor for m in members(col) if m.actor and ename(m.role) == 'MELEE']
    spot = clear_spot(world, col, player)
    if spot:
        player.set_actor_location(spot, False, True)
        await asyncio.sleep(0.3)
    coins_before = coins(world)
    log('before_engage', spot=str(spot), melee_dist=[round(dist2d(a, player)) for a in melee])
    cmd('Squads.Passive 0')
    cmd('Squads.Engage 0')
    seen_projectile, caster_shot, forced_cast, barks = False, None, False, []
    melee_track = []
    cast_anim_track, last_anim = [], {}
    casters = [m.actor for m in members(col) if m.actor and ename(m.role) == 'CASTER']
    for i in range(80):  # 5 s at 10 Hz, then 7.5 s at 4 Hz
        await asyncio.sleep(0.1 if i < 50 else 0.25)
        for m in members(col):
            if m.actor in casters:
                now = (ename(m.cast_phase), body_anim(m.actor))
                if last_anim.get(m.actor.get_name()) != now:
                    last_anim[m.actor.get_name()] = now
                    cast_anim_track.append([round(time.time() - T0, 2), m.actor.get_name(), now[0], now[1], m.casts_released])
        if hp and hp.get_editor_property('health') < 40:
            hp.heal(100.0, player)
        for b in barks_playing(col) + (barks_playing(sq[1]) if len(sq) > 1 else []):
            if b not in barks:
                barks.append(b)
        if i % 5 == 4:
            pl = player.get_actor_location()
            melee_track.append([round(time.time() - T0, 1)] + [
                [round(dist2d(a, player)), round(math.degrees(math.atan2(a.get_actor_location().y - pl.y, a.get_actor_location().x - pl.x)))]
                for a in melee])
        if not caster_shot:
            for m in members(col):
                if m.actor and ename(m.cast_phase).endswith('WINDUP'):
                    p = m.actor.get_actor_location()
                    to = player.get_actor_location() - p
                    to.z = 0
                    to = to.normal()
                    right = unreal.Vector(-to.y, to.x, 0)
                    caster_shot = await capture(world, 'r3_caster_mid_cast', unreal.Vector(p.x + to.x * 330 + right.x * 260, p.y + to.y * 330 + right.y * 260, p.z + 150),
                                                unreal.Vector(p.x, p.y, p.z + 110), 55.0)
                    report['caster_mid_cast'] = [m.actor.get_name(), caster_shot, round(time.time() - T0, 1)]
                    break
            if not caster_shot and i == 50:
                cmd('Squads.Cast')
                forced_cast = True
        if not seen_projectile:
            mine = [p for p in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsSpellProjectile)
                    if p.get_owner() and p.get_owner() in [m.actor for m in members(col)]]
            if mine:
                seen_projectile = True
                p = mine[0].get_actor_location()
                pl = player.get_actor_location()
                mid = unreal.Vector((p.x + pl.x) / 2, (p.y + pl.y) / 2, p.z)
                d = unreal.Vector(pl.x - p.x, pl.y - p.y, 0).normal()
                sd = unreal.Vector(-d.y, d.x, 0)
                report['spell_in_flight'] = await capture(world, 'r4_spell_in_flight', unreal.Vector(mid.x + sd.x * 700, mid.y + sd.y * 700, mid.z + 180), mid, 70.0)
        if i == 60 and melee:
            pl = player.get_actor_location()
            near = min(melee, key=lambda a: dist2d(a, player))
            to = near.get_actor_location() - pl
            to.z = 0
            to = to.normal()
            report['melee_shot'] = await capture(world, 'r5_melee_closing_in', unreal.Vector(pl.x - to.x * 380 + to.y * 120, pl.y - to.y * 380 - to.x * 120, pl.z + 160),
                                                 near.get_actor_location() + unreal.Vector(0, 0, 100), 70.0)
    log('fight', states=[ename(s.get_editor_property('state')) for s in sq],
        member_states=[[ename(m.state) for m in members(s)] for s in sq],
        casts=[[m.casts_released for m in members(s)] for s in sq], forced_cast=forced_cast,
        projectile_seen=seen_projectile, barks=barks, melee_track=melee_track, cast_anim_track=cast_anim_track,
        motor=[[a.get_name(), ename(c.get_editor_property('combat_state')), c.get_editor_property('attacks_started'),
                c.get_editor_property('successful_hits')]
               for a in melee for c in a.get_components_by_class(unreal.ReflectionsNpcCombatComponent)],
        hero_health=hp.get_editor_property('health') if hp else None)

    # --- Deaths: real player spells kill three soldiers of squad 0 -> ragdoll + coin. ---
    targets = alive_actors(col)[:3]
    for target in targets:
        for shot in range(8):
            if hp and hp.get_editor_property('health') < 50:
                hp.heal(100.0, player)
            h = target.get_component_by_class(unreal.ReflectionsHealthComponent)
            if h and h.get_editor_property('health') <= 0:
                break
            shoot(spells, player, target, unreal.HeroSpell.FIRESTORM if shot % 2 else unreal.HeroSpell.FIRE)
            await asyncio.sleep(0.5)
    await asyncio.sleep(1.5)
    dead = []
    for m in members(col):
        if m.actor and ename(m.state) == 'DEAD':
            b = body_of(m.actor)
            dead.append({'actor': m.actor.get_name(), 'role': ename(m.role), 'ragdoll': bool(b and b.is_simulating_physics()),
                         'pelvis_z': round(b.get_socket_location('pelvis').z) if b else None})
    log('kills', targets=[t.get_name() for t in targets], dead=dead, alive=col.get_alive_count(),
        squad_state=ename(col.get_editor_property('state')), coins_before=coins_before, coins_after=coins(world))
    if dead:
        d0 = [m.actor for m in members(col) if m.actor and ename(m.state) == 'DEAD'][0]
        p = body_of(d0).get_socket_location('pelvis')
        report['ragdoll_shot'] = await capture(world, 'r6_ragdoll', unreal.Vector(p.x + 300, p.y + 220, p.z + 230), p, 60.0)

    # --- Stand down: survivors reform and march on. ---
    cmd('Squads.Passive 1')
    cmd('Squads.Reform')
    await asyncio.sleep(7.0)
    log('reform', states=[ename(s.get_editor_property('state')) for s in sq],
        member_states=[[ename(m.state) for m in members(s)] for s in sq])
except Exception as e:
    report['errors'].append('run: %r' % e)
    raise
finally:
    try:
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')
        unreal.SystemLibrary.execute_console_command(None, 'Squads.StartPatrol 1')
    except Exception as e:
        report['stop_error'] = str(e)
    release_pie_lock()
    report['took'] = round(time.time() - T0, 1)
    with open(os.path.join(OUT, 'retest-report.json'), 'w') as f:
        json.dump(report, f, indent=1, default=str)
