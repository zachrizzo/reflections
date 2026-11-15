"""One PIE run (under Saved/PIE_LOCK.json, < 2 min): title -> Settings screen (open, change the preset, Back restores)
-> Start with GameFlow.NewGameMap pointing at the mock city -> lands in Lvl_MockCity at the Giltside PlayerStart with
a Start checkpoint. Run like test_game_flow_pie.py; result in REPORT, PNGs in Saved/GameFlowTest/mockcity_*.png."""
import base64
import json
import math
import time
from pathlib import Path

APP = 'EditorToolset.EditorAppToolset.'
SI = 'SlateInspectorToolset.SlateInspectorToolset.'
OUT = Path(unreal.Paths.project_saved_dir()).resolve() / 'GameFlowTest'
OUT.mkdir(exist_ok=True)
LOCK = Path(unreal.Paths.project_saved_dir()) / 'PIE_LOCK.json'
ME = 'local_17412422-30df-448e-8411-6f5883a914da'
MOCK = '/Game/MockCity/Lvl_MockCity'
START = (146200.0, 1100.0, 100.0)
REPORT = {'checks': {}, 'steps': []}
T0 = time.time()


def gw():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


def flow():
    w = gw()
    gi = unreal.GameplayStatics.get_game_instance(w) if w else None
    return unreal.get_game_instance_subsystem(gi, unreal.ReflectionsGameFlowSubsystem) if gi else None


def state():
    f = flow()
    w = gw()
    pc = unreal.GameplayStatics.get_player_controller(w, 0) if w else None
    p = pc.get_controlled_pawn() if pc else None
    if not f:
        return {'screen': None}
    loc = p.get_actor_location() if p else None
    return {'screen': f.get_screen().name, 'focus': f.get_menu_focused_index(), 'buttons': list(f.get_menu_button_labels()),
            'map': w.get_outermost().get_name() if w else None, 'pawn': [round(loc.x), round(loc.y), round(loc.z)] if loc else None,
            'checkpoint': f.has_checkpoint(), 'infection': '%d/%d' % (f.get_infection_count(), f.get_infection_cap())}


def log(name, **extra):
    s = state()
    s.update(extra)
    s['t'] = round(time.time() - T0, 1)
    REPORT['steps'].append({name: s})
    return s


def check(name, ok):
    REPORT['checks'][name] = bool(ok)


async def key(name, settle=0.3):
    await call_tool(SI + 'PressKey', key=name)
    await asyncio.sleep(settle)


async def capture(name):
    try:
        r = await call_tool('SceneCaptureToolset.SceneCaptureToolset.CaptureGameViewport', world=None, maxResolution=1600)
        data = r['image']
        if data is not None and not isinstance(data, str):
            data = data['data']
        if data:
            (OUT / ('mockcity_' + name + '.png')).write_bytes(base64.b64decode(data))
    except Exception as e:
        REPORT.setdefault('capture_errors', []).append('%s: %s' % (name, e))


async def wait_for(pred, timeout, step=0.25):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if pred():
                return True
        except Exception:
            pass
        await asyncio.sleep(step)
    return False


def scalability():
    return unreal.SystemLibrary.get_console_variable_int_value('sg.ShadowQuality')


async def run():
    save = Path(unreal.Paths.project_saved_dir()) / 'SaveGames' / 'Reflections_Checkpoint.sav'
    if save.exists():
        save.unlink()
    unreal.SystemLibrary.execute_console_command(None, 'GameFlow.TitleInPIE 1')
    unreal.SystemLibrary.execute_console_command(None, 'GameFlow.NewGameMap ' + MOCK)
    await call_tool(APP + 'StartPIE', options={'warmupSeconds': 3.0})
    check('title', await wait_for(lambda: state().get('screen') == 'TITLE', 15))
    await asyncio.sleep(0.6)
    t = log('title')
    check('title_has_settings', 'Settings' in t.get('buttons', []))

    # ---- Settings: open, change the preset (live preview), Back restores ----
    shadows0 = scalability()
    idx = t['buttons'].index('Settings') if 'Settings' in t.get('buttons', []) else 2
    for _ in range(idx):
        await key('Down')
    await key('Enter', 0.6)
    s = log('settings')
    check('settings_opens', s.get('screen') == 'SETTINGS')
    check('settings_rows', len(s.get('buttons', [])) >= 10)
    await capture('1_settings')
    await key('Right', 0.6)   # focus starts on the preset row: next preset, previewed live
    shadows1 = scalability()
    await capture('2_settings_preset_changed')
    log('preset_changed', shadows_before=shadows0, shadows_after=shadows1)
    check('preset_preview_changes_scalability', shadows1 != shadows0)
    await key('Gamepad_FaceButton_Right', 0.6)   # Back (pad B): unapplied changes dropped, preview undone
    b = log('settings_back', shadows=scalability())
    check('settings_back_to_title', b.get('screen') == 'TITLE')
    check('settings_back_restores_preview', scalability() == shadows0)

    # ---- Start -> New Game map ----
    await key('Gamepad_DPad_Up')
    for _ in range(4):
        if state().get('focus') == 0:
            break
        await key('Gamepad_DPad_Up')
    await key('Gamepad_FaceButton_Bottom', 1.0)
    arrived = await wait_for(lambda: 'MockCity' in (state().get('map') or '') and state().get('screen') == 'NONE' and state().get('pawn'), 60, 0.5)
    await asyncio.sleep(2.5)
    m = log('mockcity')
    check('new_game_opens_mockcity', arrived)
    pawn = m.get('pawn') or [0, 0, 0]
    check('spawn_at_giltside_start', math.dist(pawn, START) < 600.0)
    check('start_checkpoint_saved', m.get('checkpoint'))
    cp = flow().get_checkpoint() if flow() else None
    if cp:
        REPORT['checkpoint'] = {'map': cp.map_path, 'world': str(cp.world), 'reason': cp.reason}
        check('checkpoint_in_mockcity', 'MockCity' in cp.map_path)
    await capture('3_arrived')


def lock_free():
    try:
        lock = json.loads(LOCK.read_text())
        return lock.get('owner') == ME or float(lock.get('expires_epoch', 0)) <= time.time()
    except Exception:
        return True


if await call_tool(APP + 'IsPIERunning') or not lock_free():
    REPORT['error'] = 'BLOCKED'
else:
    GROUPS = ['sg.ViewDistanceQuality', 'sg.AntiAliasingQuality', 'sg.ShadowQuality', 'sg.GlobalIlluminationQuality',
              'sg.ReflectionQuality', 'sg.PostProcessQuality', 'sg.TextureQuality', 'sg.EffectsQuality', 'sg.FoliageQuality', 'sg.ShadingQuality']
    SNAP = {g: unreal.SystemLibrary.get_console_variable_int_value(g) for g in GROUPS}
    now = int(time.time())
    LOCK.write_text(json.dumps({'owner': ME, 'purpose': 'game flow: Settings screen + New Game -> MockCity (<2 min)', 'acquired_epoch': now, 'expires_epoch': now + 180}))
    try:
        await run()
    except Exception as e:
        REPORT['error'] = repr(e)
    finally:
        if await call_tool(APP + 'IsPIERunning'):
            await call_tool(APP + 'StopPIE')
        try:
            if json.loads(LOCK.read_text()).get('owner') == ME:
                LOCK.unlink()
        except Exception:
            pass
        unreal.SystemLibrary.execute_console_command(None, 'GameFlow.TitleInPIE 0')
        unreal.SystemLibrary.execute_console_command(None, 'GameFlow.NewGameMap ""')
        # Leave the editor's scalability exactly as it was (the preset preview is global).
        for g, v in SNAP.items():
            if unreal.SystemLibrary.get_console_variable_int_value(g) != v:
                unreal.SystemLibrary.execute_console_command(None, '%s %d' % (g, v))
        REPORT['scalability_restored'] = all(unreal.SystemLibrary.get_console_variable_int_value(g) == v for g, v in SNAP.items())
REPORT['seconds'] = round(time.time() - T0, 1)
(OUT / 'mockcity_report.json').write_text(json.dumps(REPORT, indent=1, default=str))
REPORT = json.dumps({'checks': REPORT['checks'], 'error': REPORT.get('error'), 'checkpoint': REPORT.get('checkpoint'), 'seconds': REPORT['seconds']}, default=str)
