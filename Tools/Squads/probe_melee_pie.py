"""PIE probe: why engaged melee soldiers do not close in. One short PIE run (~25 s), stopped in `finally`."""
import asyncio
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
report = {'samples': []}


def ename(e):
    return getattr(e, 'name', str(e))


def unwrap(r):
    return r.get('returnValue', r) if isinstance(r, dict) and 'returnValue' in r else r


if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
    raise RuntimeError('PIE already running (another session); not starting')
await acquire_pie_lock('squads: melee probe')
unreal.SystemLibrary.execute_console_command(None, 'Squads.StartPatrol 0')  # scripted checks index their own squads
await call_tool('EditorToolset.EditorAppToolset.StartPIE', options={'warmupSeconds': 2.0})
try:
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    unreal.SystemLibrary.execute_console_command(world, 'Squads.Passive 1')
    unreal.SystemLibrary.execute_console_command(world, 'Squads.SpawnTest 1')
    await asyncio.sleep(7.0)
    squad = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsSquad))[0]
    player = unreal.GameplayStatics.get_player_pawn(world, 0)
    hp = player.get_component_by_class(unreal.ReflectionsHealthComponent)
    melee = [m.actor for m in squad.get_editor_property('members') if m.actor and ename(m.role) == 'MELEE']
    unreal.SystemLibrary.execute_console_command(world, 'Squads.Passive 0')
    unreal.SystemLibrary.execute_console_command(world, 'Squads.Engage 0')
    for i in range(12):
        await asyncio.sleep(0.5)
        if hp and hp.get_editor_property('health') < 40:
            hp.heal(100.0, player)
        row = []
        for a in melee:
            drv = a.get_attach_parent_actor()
            npc = a.get_component_by_class(unreal.ReflectionsNpcReactionComponent)
            motor = a.get_component_by_class(unreal.ReflectionsNpcCombatComponent)
            start = a.get_actor_location() + unreal.Vector(0, 0, 95)
            end = player.get_actor_location()
            hit = unreal.SystemLibrary.line_trace_single(world, start, end, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False,
                                                         [a, drv] if drv else [a], unreal.DrawDebugTrace.NONE, True)
            h = hit.to_tuple() if hasattr(hit, 'to_tuple') else hit[1].to_tuple()
            blocked = (h[9].get_name() if h[9] else 'None') if h[0] else None
            cmc = drv.get_component_by_class(unreal.CharacterMovementComponent) if drv else None
            row.append({
                'npc_reaction': ename(npc.get_editor_property('reaction')) if npc else None,
                'steered': npc.is_externally_steered() if npc and hasattr(npc, 'is_externally_steered') else None,
                'motor': [ename(motor.get_editor_property('combat_state')), motor.get_editor_property('attacks_started'),
                          motor.get_editor_property('successful_hits')] if motor else None,
                'los_blocked_by': blocked,
                'drv_vel': round(drv.get_velocity().length()) if drv else None,
                'move_mode': ename(cmc.get_editor_property('movement_mode')) if cmc else None,
                'max_speed': round(cmc.get_max_speed()) if cmc else None,
                'last_input': str(cmc.get_last_input_vector()) if cmc else None,
                'dist': round((a.get_actor_location() - player.get_actor_location()).length()),
            })
        report['samples'].append(row)
finally:
    try:
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')
        unreal.SystemLibrary.execute_console_command(None, 'Squads.StartPatrol 1')
    except Exception as e:
        report['stop_error'] = str(e)
    release_pie_lock()
    with open(os.path.join(OUT, 'probe-melee.json'), 'w') as f:
        json.dump(report, f, indent=1, default=str)
