"""One short Lives check on Medieval London (one execute_python call, under ~55 s, with Saved/PIE_LOCK.json taken).

Starts PIE (the editor's map must be MedievalLondon, or PIE travels there), lets the town fill, puts the clock at
midday, then looks at the people near the player start and in the market: how many lives have bodies, how many are
within 40 m, what they are doing (overlay activity lines) and whether they move. Two pictures with the F7 overlay
(reset to 0 after). Stops PIE. Results: Saved/Lives/verify_medieval.json and M_*.png. Top-level await.
"""

import base64
import json
import math
from pathlib import Path

MAP = globals().get('MAP', '/Game/GrayLondon/Maps/MedievalLondon')
OUT = Path(unreal.Paths.project_saved_dir()) / 'Lives'
OUT.mkdir(parents=True, exist_ok=True)
R = {'checks': {}, 'shots': [], 'notes': {}}


def unwrap(v):
    return v['returnValue'] if isinstance(v, dict) and 'returnValue' in v else v


def world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


async def shot(name):
    try:
        cap = unwrap(await call_tool('SceneCaptureToolset.SceneCaptureToolset.CaptureGameViewport', world=world(), maxResolution=1600))
        data = cap['image'] if isinstance(cap, dict) else None
        if isinstance(data, dict):
            data = data.get('data') or data.get('base64')
        if data:
            if ',' in data[:64]:
                data = data.split(',', 1)[1]
            (OUT / ('M_' + name + '.png')).write_bytes(base64.b64decode(data))
            R['shots'].append(name)
    except Exception as e:
        R.setdefault('shot_errors', []).append(name + ': ' + repr(e))


def survey(lives, npcs, centre, radius=4000.0):
    acts = [a for a in npcs.get_npc_actors() if a is not None and unreal.SystemLibrary.is_valid(a)]
    named = [a for a in acts if str(lives.get_person_id(a)) not in ('None', '')]
    near = [a for a in named if math.hypot(a.get_actor_location().x - centre.x, a.get_actor_location().y - centre.y) < radius]
    names = {str(lives.get_person_name(lives.get_person_id(a))) for a in near}
    lines = [l for l in str(lives.describe()).splitlines()[1:] if any(n and n in l for n in names)]
    doing = {}
    for l in lines:
        for key in ('Working', 'Shopping', 'Eating', 'Errand', 'Passing time', 'Seeing friends', 'Worship', 'Strolling', 'Chatting',
                    'Patrol', 'On watch', 'Waking', 'Home', 'Inside', 'Sleeping', 'Grieving', 'Getting away', 'Keeping', 'Hiding'):
            if '  ' + key in l or l.split('@')[0].rstrip().endswith(key) or (' ' + key + ' ') in l.split('@')[0]:
                doing[key] = doing.get(key, 0) + 1
                break
    return acts, named, near, lines, doing


async def run():
    if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
        R['abort'] = 'PIE already running; nothing started.'
        return
    await call_tool('EditorToolset.EditorAppToolset.StartPIE')
    await asyncio.sleep(4.0)
    w = world()
    short = MAP.rsplit('/', 1)[-1]
    if w is not None and short not in str(w.get_name()):
        unreal.SystemLibrary.execute_console_command(w, 'open ' + MAP)
        await asyncio.sleep(10.0)
    for _ in range(8):
        w = world()
        if w is not None and len(unreal.get_world_subsystem(w, unreal.ReflectionsNpcSubsystem).get_npc_actors()) >= 8:
            break
        await asyncio.sleep(2.0)
    w = world()
    R['map'] = str(w.get_name()) if w else None
    lives = unreal.get_world_subsystem(w, unreal.ReflectionsLivesSubsystem)
    npcs = unreal.get_world_subsystem(w, unreal.ReflectionsNpcSubsystem)
    player = unreal.GameplayStatics.get_player_pawn(w, 0)
    lives.set_time_of_day(12.0)
    await asyncio.sleep(8.0)
    head = str(lives.describe()).splitlines()[0]
    R['notes']['lives_head'] = head
    start = player.get_actor_location()
    acts, named, near, lines, doing = survey(lives, npcs, start)
    snap = {a.get_name(): a.get_actor_location() for a in near}
    await asyncio.sleep(3.0)
    moving = sum(1 for a in near if unreal.SystemLibrary.is_valid(a) and math.hypot(a.get_actor_location().x - snap[a.get_name()].x,
                                                                                    a.get_actor_location().y - snap[a.get_name()].y) > 40)
    R['notes']['start'] = {'npcs': len(acts), 'with_life': len(named), 'within_40m': len(near), 'moving_3s': moving, 'doing': doing,
                           'lines': lines[:14]}
    check('M_people_near_start', len(near) >= 6, R['notes']['start'])
    check('M_they_move', moving >= max(2, len(near) // 3), {'moving': moving, 'near': len(near)})
    lives.set_debug_level(1)
    await asyncio.sleep(0.5)
    await shot('start_midday')
    # The market (stall rows at y +-1450..2850, x -3890..3790): walk-in view from its west mouth.
    player.teleport(unreal.Vector(-3500.0, 0.0, start.z), unreal.Rotator(0.0, 0.0, 0.0))
    player.get_controller().set_control_rotation(unreal.Rotator(0.0, -8.0, 0.0))
    await asyncio.sleep(6.0)
    acts, named, near, lines, doing = survey(lives, npcs, player.get_actor_location())
    R['notes']['market'] = {'within_40m': len(near), 'doing': doing, 'lines': lines[:14]}
    check('M_market_busy', len(near) >= 6 and doing.get('Working', 0) + doing.get('Shopping', 0) >= 2, R['notes']['market'])
    await shot('market_midday')
    lives.set_debug_level(0)


def check(name, ok, detail=None):
    R['checks'][name] = {'ok': bool(ok), 'detail': detail}


try:
    await run()
except Exception as e:
    R['error'] = repr(e)
try:
    unreal.SystemLibrary.execute_console_command(world(), 'Lives.Debug 0')
except Exception:
    pass
if not R.get('abort') and unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
    await call_tool('EditorToolset.EditorAppToolset.StopPIE')
(OUT / 'verify_medieval.json').write_text(json.dumps(R, indent=2, default=str))
summary = json.dumps({'passed': f"{sum(1 for c in R['checks'].values() if c['ok'])}/{len(R['checks'])}",
                      'checks': {k: v['ok'] for k, v in R['checks'].items()}, 'error': R.get('error'), 'abort': R.get('abort'),
                      'head': R['notes'].get('lives_head'), 'start': {k: v for k, v in R['notes'].get('start', {}).items() if k != 'lines'},
                      'market': {k: v for k, v in R['notes'].get('market', {}).items() if k != 'lines'}}, default=str)
