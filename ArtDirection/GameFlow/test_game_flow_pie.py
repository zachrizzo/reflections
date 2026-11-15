"""PIE test for the game flow (title -> play -> pause -> respawn at checkpoint -> lose at the cap -> try again ->
victory -> title), driven with real keyboard and gamepad key events through Slate.

Run inside the editor through the MCP Python tool (execute_python):

    import ast
    from pathlib import Path
    p = Path(unreal.Paths.project_dir()) / 'ArtDirection/GameFlow/test_game_flow_pie.py'
    await eval(compile(p.read_text(), str(p), 'exec', flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT), globals())
    REPORT

Refuses to run while someone else's PIE is up. Starts PIE in the open level, stops it at the end (about 2 minutes),
writes PNGs and report.json to Saved/GameFlowTest. Deletes the game-flow save first so the title shows "Start".
"""
import asyncio
import base64
import json
import math
import re
import os
import time
from pathlib import Path

OUT = Path(unreal.Paths.project_saved_dir()).resolve() / 'GameFlowTest'
OUT.mkdir(exist_ok=True)
APP = 'EditorToolset.EditorAppToolset.'
SI = 'SlateInspectorToolset.SlateInspectorToolset.'
REPORT = {'steps': [], 'checks': {}, 'shots': []}
T0 = time.time()


def gw():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


def flow():
    w = gw()
    gi = unreal.GameplayStatics.get_game_instance(w) if w else None
    return unreal.get_game_instance_subsystem(gi, unreal.ReflectionsGameFlowSubsystem) if gi else None


def pawn():
    w = gw()
    pc = unreal.GameplayStatics.get_player_controller(w, 0) if w else None
    return pc.get_controlled_pawn() if pc else None


def console(cmd):
    unreal.SystemLibrary.execute_console_command(gw(), cmd)


def state():
    f = flow()
    p = pawn()
    if not f:
        return {'screen': None}
    cp = f.get_checkpoint()
    return {
        'screen': getattr(f.get_screen(), 'name', str(f.get_screen()).split('.')[-1].split(':')[0].strip('<> ')),
        'buttons': list(f.get_menu_button_labels()),
        'focus': f.get_menu_focused_index(),
        'tip': f.get_active_tip_name(),
        'infection': '%d/%d' % (f.get_infection_count(), f.get_infection_cap()),
        'game_over': f.is_game_over(),
        'gamepad': f.is_using_gamepad(),
        'checkpoint': bool(cp.valid) if hasattr(cp, 'valid') else None,
        'pawn': [round(v) for v in (p.get_actor_location().x, p.get_actor_location().y, p.get_actor_location().z)] if p else None,
    }


def log(name, **extra):
    s = state()
    s.update(extra)
    s['t'] = round(time.time() - T0, 1)
    REPORT['steps'].append({name: s})
    return s


def check(name, ok):
    REPORT['checks'][name] = bool(ok)
    return ok


async def key(name, settle=0.25):
    await call_tool(SI + 'PressKey', key=name)
    await asyncio.sleep(settle)


async def capture(name):
    try:
        r = await call_tool('SceneCaptureToolset.SceneCaptureToolset.CaptureGameViewport', world=None, maxResolution=1600)
        data = r['image']
        if data is not None and not isinstance(data, str):
            data = data['data']
        if data:
            path = OUT / (name + '.png')
            path.write_bytes(base64.b64decode(data))
            REPORT['shots'].append(str(path))
            return str(path)
    except Exception as e:
        REPORT['shots'].append('%s: %s' % (name, e))
    return None


BUDGET = 175.0  # house rule: one PIE at a time, 3 minutes at most


class OutOfTime(Exception):
    pass


def left():
    return BUDGET - (time.time() - T0)


def need(seconds):
    """Skip the rest of the run (PIE still stops in finally) when the budget can't cover the next phase."""
    if left() < seconds:
        raise OutOfTime('%.0fs left, phase needs %.0fs' % (left(), seconds))


async def wait_for(pred, timeout, step=0.25):
    end = time.time() + min(timeout, max(0.0, left() - 5.0))
    while time.time() < end:
        try:
            if pred():
                return True
        except Exception:
            pass
        await asyncio.sleep(step)
    return False


async def find_ref(label):
    """Ref of the widget whose text is exactly `label` in the Slate snapshot (menu buttons' text blocks)."""
    snap = await call_tool(SI + 'Snapshot', ref='', maxDepth=120)
    for line in snap.splitlines():
        if ('"%s"' % label) in line:
            m = re.search(r'\[ref=([^\]]+)\]', line)
            if m:
                return m.group(1)
    return None


def screen_is(name):
    return lambda: state().get('screen') == name


def dist(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


async def run():
    # Fresh save so the title offers Start (not Continue).
    save = Path(unreal.Paths.project_saved_dir()) / 'SaveGames' / 'Reflections_Checkpoint.sav'
    if save.exists():
        save.unlink()
    unreal.SystemLibrary.execute_console_command(None, 'GameFlow.TitleInPIE 1')
    await call_tool(APP + 'StartPIE', options={'warmupSeconds': 3.0})

    # ---- Title, keyboard ----
    check('title_shown', await wait_for(screen_is('TITLE'), 15))
    await asyncio.sleep(0.6)
    log('title')
    await capture('01_title')
    await key('Down')
    s1 = log('title_down')
    await key('Down')
    s2 = log('title_down2')
    check('keyboard_nav_moves_focus', s1['focus'] == 1 and s2['focus'] == 2)
    await key('Up')
    s = log('title_up_to_controls')
    await key('Enter', 0.5)
    check('enter_opens_controls', screen_is('CONTROLS')())
    log('controls_keyboard')
    await capture('02_controls_keyboard')
    await key('Escape', 0.5)
    check('escape_back_to_title', screen_is('TITLE')() and await call_tool(APP + 'IsPIERunning'))
    log('back_on_title')

    # ---- Title, mouse (hover takes focus, click presses, Back by click) ----
    try:
        # The Slate inspector only sees editor windows, not the game viewport's layers: if the menu's own
        # buttons are not in its snapshot, skip rather than click an editor widget that happens to match.
        ref = await find_ref('Credits') if await find_ref('Start') else None
        if ref:
            await call_tool(SI + 'Hover', ref=ref)
            await asyncio.sleep(0.35)
            h = log('mouse_hover_credits')
            await call_tool(SI + 'Click', ref=ref)
            await asyncio.sleep(0.6)
            c = log('mouse_click_credits')
            await capture('02b_credits_mouse')
            back = await find_ref('Back')
            if back:
                await call_tool(SI + 'Click', ref=back)
                await asyncio.sleep(0.6)
            check('mouse_hover_focuses', h['focus'] == 2)
            check('mouse_click_opens_credits', c['screen'] == 'CREDITS')
            check('mouse_click_back', screen_is('TITLE')())
        else:
            REPORT['mouse_skipped'] = 'menu buttons not visible to SlateInspector (game viewport content)'
    except Exception as e:
        REPORT['mouse_error'] = repr(e)
    if not screen_is('TITLE')():
        await key('Gamepad_FaceButton_Right', 0.5)

    # ---- Title -> play, gamepad ----
    await key('Gamepad_DPad_Down')
    g1 = log('pad_down')
    await key('Gamepad_DPad_Up')
    g0 = log('pad_up')
    check('gamepad_nav_moves_focus', g1['focus'] == 1 and g0['focus'] == 0 and g0['gamepad'])
    await key('Gamepad_FaceButton_Bottom', 0.8)
    check('a_starts_game', screen_is('NONE')())
    log('playing')
    await wait_for(lambda: state().get('tip'), 8)
    await asyncio.sleep(0.8)  # let the tip card fade in
    log('first_tip')
    await capture('03_playing_tip_meter')

    # ---- Pause, gamepad ----
    await key('Gamepad_Special_Right', 0.5)
    check('start_opens_pause', screen_is('PAUSE')())
    log('pause_pad')
    await capture('04_pause_gamepad')
    await key('Gamepad_DPad_Down')
    await key('Gamepad_FaceButton_Bottom', 0.5)
    check('pause_controls_gamepad', screen_is('CONTROLS')())
    await capture('05_controls_gamepad')
    await key('Gamepad_FaceButton_Right', 0.4)
    check('b_back_to_pause', screen_is('PAUSE')())
    await key('Gamepad_FaceButton_Right', 0.5)
    check('b_resumes', screen_is('NONE')())

    # ---- Pause, keyboard (P; Esc stops PIE in the editor) ----
    await key('P', 0.5)
    check('p_opens_pause', screen_is('PAUSE')())
    await key('Down')
    await key('Down')
    k = log('pause_kb_focus')
    check('pause_keyboard_nav', k['focus'] == 2)
    await key('P', 0.5)
    check('p_resumes', screen_is('NONE')())

    # ---- Checkpoint away from the spawn, then death -> respawn at the checkpoint (not the spawn) ----
    need(20)
    p = pawn()
    spawn = p.get_actor_location()
    p.set_actor_location(unreal.Vector(spawn.x + 600.0, spawn.y + 300.0, spawn.z + 60.0), False, True)
    await asyncio.sleep(1.2)  # land
    pc = unreal.GameplayStatics.get_player_controller(gw(), 0)
    pc.set_control_rotation(unreal.Rotator(roll=0.0, pitch=-10.0, yaw=35.0))
    await asyncio.sleep(0.2)
    console('GameFlow.Checkpoint')
    await asyncio.sleep(0.4)
    cp_loc = [p.get_actor_location().x, p.get_actor_location().y, p.get_actor_location().z]
    cp_yaw = pc.get_control_rotation().yaw
    log('checkpoint_saved', cp=[round(v) for v in cp_loc], spawn=[round(spawn.x), round(spawn.y), round(spawn.z)], cp_yaw=round(cp_yaw))
    p.set_actor_location(unreal.Vector(spawn.x - 400.0, spawn.y, spawn.z + 60.0), False, True)
    # Look well away from the checkpoint's facing before dying.
    pc.set_control_rotation(unreal.Rotator(roll=0.0, pitch=-5.0, yaw=cp_yaw + 140.0))
    await asyncio.sleep(0.8)
    moved = log('moved_away', yaw=round(pc.get_control_rotation().yaw))
    driver = p.get_component_by_class(unreal.ReflectionsSampleSpellDriver)
    console('GameFlow.Kill')
    died = await wait_for(lambda: driver.is_defeated(), 3)
    log('defeated', died=died)
    await capture('06_defeated')
    back = await wait_for(lambda: not driver.is_defeated(), 9)
    await asyncio.sleep(0.4)
    yaw_after = pc.get_control_rotation().yaw
    r = log('respawned', yaw=round(yaw_after))
    check('respawn_at_checkpoint', died and back and r['pawn'] and dist(r['pawn'], cp_loc) < 250.0)
    check('respawn_camera_facing', abs(((yaw_after - cp_yaw) + 180.0) % 360.0 - 180.0) < 5.0)
    await capture('07_respawned')

    # ---- Infection to the cap -> lose ----
    need(8)
    console('GameFlow.Cap 5')
    console('GameFlow.Infect 3')
    await asyncio.sleep(0.6)
    log('infected_3_of_5')
    await capture('08_infection_meter')
    console('GameFlow.Infect 2')
    await asyncio.sleep(0.8)
    check('lose_at_cap', screen_is('LOSE')())
    log('lose')
    await capture('09_lose')

    # ---- Try again -> reload, back at the checkpoint, infection reset ----
    need(25)
    await key('Gamepad_FaceButton_Bottom', 0.5)
    reloaded = await wait_for(lambda: state().get('screen') == 'NONE' and state().get('infection', '').startswith('0/'), 60, 0.5)
    await asyncio.sleep(1.5)
    t = log('after_try_again')
    check('try_again_restores', reloaded and t['pawn'] and dist(t['pawn'], cp_loc) < 250.0)
    await capture('10_after_try_again')

    # ---- Victory -> credits -> title ----
    need(20)
    console('GameFlow.Victory')
    await asyncio.sleep(0.8)
    check('victory_shown', screen_is('VICTORY')())
    log('victory')
    await capture('11_victory_credits')
    await key('Gamepad_FaceButton_Bottom', 0.5)
    titled = await wait_for(screen_is('TITLE'), 60, 0.5)
    await asyncio.sleep(1.0)
    ti = log('title_after_victory')
    check('return_to_title_with_continue', titled and 'Continue' in ti.get('buttons', []))
    await capture('12_title_continue')


# Shared PIE lock (Saved/PIE_LOCK.json): take it before StartPIE, delete it as soon as PIE stops.
LOCK = Path(unreal.Paths.project_saved_dir()) / 'PIE_LOCK.json'
ME = 'local_17412422-30df-448e-8411-6f5883a914da'


def lock_owner():
    try:
        lock = json.loads(LOCK.read_text(encoding='utf-8'))
        return lock.get('owner') if float(lock.get('expires_epoch', 0)) > time.time() else None
    except Exception:
        return None


def take_lock():
    owner = lock_owner()
    if owner and owner != ME:
        return False
    now = int(time.time())
    LOCK.write_text(json.dumps({'owner': ME, 'purpose': 'game flow PIE test (one run, <3 min)', 'acquired_epoch': now,
                                'expires_epoch': now + 240, 'expires_local': time.strftime('%H:%M:%S', time.localtime(now + 240))}, indent=2))
    return True


def release_lock():
    try:
        if json.loads(LOCK.read_text(encoding='utf-8')).get('owner') == ME:
            LOCK.unlink()
    except Exception:
        pass


started = False
if await call_tool(APP + 'IsPIERunning'):
    REPORT['error'] = 'BLOCKED: PIE is already running (someone else is testing).'
elif not take_lock():
    REPORT['error'] = 'BLOCKED: PIE_LOCK.json is held by %s.' % lock_owner()
else:
    started = True
    try:
        await run()
    except Exception as e:
        REPORT['error'] = repr(e)
    finally:
        if await call_tool(APP + 'IsPIERunning'):
            await call_tool(APP + 'StopPIE')
        release_lock()
        unreal.SystemLibrary.execute_console_command(None, 'GameFlow.TitleInPIE 0')
REPORT['seconds'] = round(time.time() - T0, 1)
(OUT / 'report.json').write_text(json.dumps(REPORT, indent=1, default=str))
REPORT = json.dumps({'checks': REPORT['checks'], 'error': REPORT.get('error'), 'seconds': REPORT['seconds']}, default=str)
