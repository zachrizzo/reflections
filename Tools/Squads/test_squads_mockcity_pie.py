"""One-PIE check of the three placed Lanthorne squads on /Game/MockCity/Lvl_MockCity (world-jump's levels).

Needs Lvl_MockCity to be the editor's open map already (it never switches maps). Takes Saved/PIE_LOCK.json, one PIE
run kept under ~45 s (the MCP call stops scripts at ~60 s), stopped in `finally`. Checks:
  - the placed squads spawn from their streamed side levels and march (anchor progress over ~10 s),
  - frame time with the three squads and again with them despawned (editor background throttling switched off for
    the run on the in-memory settings object, restored after; throttled numbers are meaningless),
  - a provoked-only patrol (SightRadius 0) stays calm with the player beside it; a hostile one engages,
  - streaming: unloading a side level removes its soldiers; loading it again raises a fresh squad.
Navmesh use is read from the log afterwards ("N route points, navmesh paths"). Writes Saved/SquadsTest/mockcity-report.json.
"""
import asyncio
import json
import math
import os
import time


LOCK_PATH = os.path.join(unreal.Paths.project_saved_dir(), 'PIE_LOCK.json')
LOCK_OWNER = 'squads (enemy soldier squads side session)'


async def acquire_pie_lock(purpose, seconds=240, wait_limit=60):
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


def alive(squad):
    return [m.actor for m in members(squad) if m.actor and ename(m.state) != 'DEAD']


def label(actor):
    try:
        return actor.get_actor_label()
    except Exception:
        return actor.get_name()


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


def ground(world, p, ignore):
    hit = unreal.SystemLibrary.line_trace_single(world, unreal.Vector(p.x, p.y, p.z + 600), unreal.Vector(p.x, p.y, p.z - 900),
                                                 unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, ignore,
                                                 unreal.DrawDebugTrace.NONE, True)
    t = hit.to_tuple() if hit else None
    return unreal.Vector(p.x, p.y, t[5].z + 95) if t and t[0] else unreal.Vector(p.x, p.y, p.z + 95)


async def frame_ms(samples=8):
    vals = []
    for _ in range(samples):
        await asyncio.sleep(0.12)
        t = unwrap(await call_tool('PerfToolset.StatsToolset.GetFrameTimings'))
        vals.append((t.get('frameMs', 0), t.get('gameThreadMs', 0), t.get('gpuMs', 0)))
    n = len(vals)
    return {'frame': round(sum(v[0] for v in vals) / n, 2), 'game': round(sum(v[1] for v in vals) / n, 2),
            'gpu': round(sum(v[2] for v in vals) / n, 2)}


def squads_by_side(world):
    out = {}
    for s in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsSquad):
        name = label(s)
        side = 'Gilt' if 'Gilt' in name else 'Frost' if 'Frost' in name else 'Pew' if 'Pew' in name else name
        out[side] = s
    return out


def snapshot(sq):
    return {side: {'name': label(s), 'level': s.get_level().get_outer().get_name() if s.get_level() else None,
                   'state': ename(s.get_editor_property('state')), 'alive': len(alive(s)),
                   'sight': prop(s, 'sight_radius'), 'alert': prop(s, 'alert_radius'),
                   'formation': ename(prop(s, 'formation')),
                   'at': [round(c) for c in (lambda c: (c.x, c.y, c.z))(centroid(alive(s)))] if alive(s) else None}
            for side, s in sq.items()}


if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
    raise RuntimeError('PIE already running (another session); not starting')

perf_settings = None
try:
    perf_settings = unreal.find_object(None, '/Script/UnrealEd.Default__EditorPerformanceSettings')
    if perf_settings is None:
        cls = unreal.load_class(None, '/Script/UnrealEd.EditorPerformanceSettings')
        perf_settings = unreal.get_default_object(cls) if cls else None
except Exception as e:
    report['errors'].append('perf settings: %r' % e)
throttle_was = prop(perf_settings, 'throttle_cpu_when_not_foreground') if perf_settings else None
await acquire_pie_lock('squads: Lanthorne squads on the navmesh, frame cost, provoked-only, streaming (one run, ~45 s)')
try:
    if throttle_was:
        perf_settings.set_editor_property('throttle_cpu_when_not_foreground', False)
    report['throttle_was'] = throttle_was
    await call_tool('EditorToolset.EditorAppToolset.StartPIE', options={'warmupSeconds': 2.0})
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    # The editor's open map is never switched: if PIE did not start on the mock city, travel there inside PIE.
    if 'Lvl_MockCity' not in world.get_path_name():
        report['opened_in_pie_from'] = world.get_path_name()
        unreal.SystemLibrary.execute_console_command(world, 'open /Game/MockCity/Lvl_MockCity')
        for _ in range(100):
            await asyncio.sleep(0.25)
            w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
            if w and 'Lvl_MockCity' in w.get_path_name() and unreal.GameplayStatics.get_player_pawn(w, 0):
                world = w
                break
        if 'Lvl_MockCity' not in world.get_path_name():
            raise RuntimeError('could not open Lvl_MockCity in PIE')
        report['mock_city_open_at'] = round(time.time() - T0, 1)
    cmd = lambda text: unreal.SystemLibrary.execute_console_command(world, text)
    player = unreal.GameplayStatics.get_player_pawn(world, 0)
    hp = player.get_component_by_class(unreal.ReflectionsHealthComponent)
    await asyncio.sleep(3.0)
    sq = squads_by_side(world)
    first = snapshot(sq)
    log('spawned', squads=first)
    report['perf_three_squads'] = await frame_ms()

    # Provoked-only: stand 3.5 m beside the Gilt column (SightRadius 0) for 4 s; it should keep marching.
    ignore_all = [a for s in sq.values() for a in alive(s)] + [player]
    if 'Gilt' in sq and alive(sq['Gilt']):
        g = sq['Gilt']
        c, f = centroid(alive(g)), heading(g)
        side = unreal.Vector(-f.y, f.x, 0)
        player.set_actor_location(ground(world, unreal.Vector(c.x + side.x * 350 + f.x * 300, c.y + side.y * 350 + f.y * 300, c.z), ignore_all), False, True)
        await asyncio.sleep(3.0)
        log('gilt_beside_player', state=ename(g.get_editor_property('state')),
            member_states=[ename(m.state) for m in members(g)],
            dist=[round((a.get_actor_location() - player.get_actor_location()).length()) for a in alive(g)])
    # Hostile: 12 m in front of the Frost line; it should engage.
    if 'Frost' in sq and alive(sq['Frost']):
        fr = sq['Frost']
        c, f = centroid(alive(fr)), heading(fr)
        player.set_actor_location(ground(world, unreal.Vector(c.x + f.x * 1200, c.y + f.y * 1200, c.z), ignore_all), False, True)
        await asyncio.sleep(3.0)
        if hp and hp.get_editor_property('health') < 50:
            hp.heal(100.0, player)
        log('frost_in_front_of_player', state=ename(fr.get_editor_property('state')),
            member_states=[ename(m.state) for m in members(fr)])
        cmd('Squads.Passive 1')
    moved = snapshot(sq)
    log('after_10s', squads=moved,
        moved_m={k: round(math.dist(first[k]['at'][:2], moved[k]['at'][:2]) / 100.0, 1)
                 for k in moved if first.get(k, {}).get('at') and moved[k]['at']})

    # Streaming: the mock city's sides are Always Loaded, so stream in an extra dynamic copy of Pewterside 4.5 km out
    # (PIE only). Its spawner must raise a squad on load, and unloading it must take the soldiers with it.
    before_ids = set(s.get_path_name() for s in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsSquad))
    res = unreal.LevelStreamingDynamic.load_level_instance(world, '/Game/MockCity/Lvl_MockCity_Pewterside',
                                                            unreal.Vector(450000, 0, 0), unreal.Rotator(0, 0, 0))
    stream = res[0] if isinstance(res, tuple) else res
    if stream:
        await asyncio.sleep(3.5)
        extra = [s for s in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsSquad)
                 if s.get_path_name() not in before_ids]
        soldiers = [a for s in extra for a in alive(s)]
        log('copy_loaded', squads=[label(s) for s in extra], soldiers=len(soldiers),
            at=[round(c) for c in (lambda c: (c.x, c.y, c.z))(centroid(soldiers))] if soldiers else None)
        stream.set_should_be_visible(False)
        stream.set_should_be_loaded(False)
        stream.set_is_requesting_unload_and_removal(True)
        await asyncio.sleep(3.0)
        left = [a for a in soldiers if unreal.SystemLibrary.is_valid(a) and not a.is_actor_being_destroyed()]
        log('copy_unloaded', soldiers_before=len(soldiers), soldiers_left=len(left),
            squads_left=[label(s) for s in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsSquad)
                         if s.get_path_name() not in before_ids])
    else:
        report['errors'].append('could not load a Pewterside instance')

    # Baseline: despawn every squad and measure again.
    for s in sq.values():
        s.despawn_squad()
    await asyncio.sleep(1.5)
    report['perf_no_squads'] = await frame_ms()
    log('despawned', alive=[len(alive(s)) for s in sq.values()])
except Exception as e:
    report['errors'].append('run: %r' % e)
    raise
finally:
    try:
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')
    except Exception as e:
        report['stop_error'] = str(e)
    try:
        if throttle_was:
            perf_settings.set_editor_property('throttle_cpu_when_not_foreground', True)
    except Exception as e:
        report['errors'].append('restore throttle: %r' % e)
    release_pie_lock()
    report['took'] = round(time.time() - T0, 1)
    with open(os.path.join(OUT, 'mockcity-report.json'), 'w') as f:
        json.dump(report, f, indent=1, default=str)
