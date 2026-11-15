"""One short PIE run (< 90 s), with Saved/PIE_LOCK.json already claimed by this session from outside the editor:
1. Settings Back from a Custom quality mix: open Settings, change the preset (live preview), press Back, and every
   scalability group must be exactly as before (the train #10 fix; PreviewPreset could not restore "Custom").
2. Credits screen and Victory screen with the 9-line Credits.Tools, captured to check nothing is cut off.
No map change. Result in REPORT; PNGs in Saved/GameFlowTest/credits_*.png. The lock is deleted when PIE stops."""
import base64
import json
import time
from pathlib import Path

APP = 'EditorToolset.EditorAppToolset.'
SI = 'SlateInspectorToolset.SlateInspectorToolset.'
OUT = Path(unreal.Paths.project_saved_dir()).resolve() / 'GameFlowTest'
OUT.mkdir(exist_ok=True)
LOCK = Path(unreal.Paths.project_saved_dir()) / 'PIE_LOCK.json'
ME = 'local_17412422-30df-448e-8411-6f5883a914da'
GROUPS = ['sg.ViewDistanceQuality', 'sg.AntiAliasingQuality', 'sg.ShadowQuality', 'sg.GlobalIlluminationQuality',
          'sg.ReflectionQuality', 'sg.PostProcessQuality', 'sg.TextureQuality', 'sg.EffectsQuality', 'sg.FoliageQuality',
          'sg.ShadingQuality']
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
    if not f:
        return {'screen': None}
    return {'screen': f.get_screen().name, 'focus': f.get_menu_focused_index(), 'buttons': list(f.get_menu_button_labels())}


def levels():
    return {g: unreal.SystemLibrary.get_console_variable_int_value(g) for g in GROUPS}


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
        r = await call_tool('SceneCaptureToolset.SceneCaptureToolset.CaptureGameViewport', world=None, maxResolution=1920)
        data = r['image']
        if data is not None and not isinstance(data, str):
            data = data['data']
        if data:
            (OUT / ('credits_' + name + '.png')).write_bytes(base64.b64decode(data))
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


async def focus_to(label):
    s = state()
    if label not in s.get('buttons', []):
        return False
    target = s['buttons'].index(label)
    for _ in range(12):
        f = state().get('focus')
        if f == target:
            return True
        await key('Down' if f is None or f < target else 'Up')
    return state().get('focus') == target


async def run():
    # A Custom mix: shadows one step away from everything else, so no single preset number describes it.
    base = levels()
    odd = 1 if base['sg.TextureQuality'] != 1 else 2
    unreal.SystemLibrary.execute_console_command(None, 'sg.ShadowQuality %d' % odd)
    unreal.SystemLibrary.execute_console_command(None, 'GameFlow.TitleInPIE 1')
    await call_tool(APP + 'StartPIE', options={'warmupSeconds': 3.0})
    check('title', await wait_for(lambda: state().get('screen') == 'TITLE', 20))
    await asyncio.sleep(0.6)
    t = log('title')

    # ---- 1. Settings Back from Custom ----
    before = levels()
    REPORT['custom_before'] = before
    check('start_is_custom', len(set(before.values())) > 1)
    check('focus_settings', await focus_to('Settings'))
    await key('Enter', 0.6)
    s = log('settings')
    check('settings_opens', s.get('screen') == 'SETTINGS')
    await key('Right', 0.8)   # focus starts on the preset row: next preset, previewed live
    preview = levels()
    log('preset_preview', levels=preview)
    check('preview_changes_levels', preview != before)
    await key('Gamepad_FaceButton_Right', 0.8)   # Back (pad B): drop unapplied changes
    after = levels()
    b = log('settings_back', levels=after)
    check('settings_back_to_title', b.get('screen') == 'TITLE')
    check('back_restores_every_group', after == before)
    if after != before:
        REPORT['mismatch'] = {g: [before[g], after[g]] for g in GROUPS if before[g] != after[g]}

    # ---- 2. Credits screen ----
    check('focus_credits', await focus_to('Credits'))
    await key('Enter', 0.8)
    c = log('credits')
    check('credits_opens', c.get('screen') == 'CREDITS')
    await capture('1_credits_screen')
    await key('Escape', 0.6)
    check('credits_back_to_title', state().get('screen') == 'TITLE')

    # ---- 3. Victory screen (embedded credits, the narrow 660 px panel) ----
    unreal.SystemLibrary.execute_console_command(gw(), 'GameFlow.Victory')
    check('victory', await wait_for(lambda: state().get('screen') == 'VICTORY', 5))
    await asyncio.sleep(1.2)
    log('victory')
    await capture('2_victory_screen')


if await call_tool(APP + 'IsPIERunning'):
    REPORT['error'] = 'BLOCKED: PIE already running'
else:
    try:
        lock = json.loads(LOCK.read_text())
    except Exception:
        lock = {}
    if lock.get('owner') != ME or float(lock.get('expires_epoch', 0)) <= time.time():
        REPORT['error'] = 'BLOCKED: the PIE lock is not mine'
    else:
        SNAP = levels()
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
            # Leave the editor's scalability exactly as it was (the Custom mix and the preview are global).
            for g, v in SNAP.items():
                if unreal.SystemLibrary.get_console_variable_int_value(g) != v:
                    unreal.SystemLibrary.execute_console_command(None, '%s %d' % (g, v))
            REPORT['scalability_restored'] = levels() == SNAP
REPORT['seconds'] = round(time.time() - T0, 1)
(OUT / 'credits_report.json').write_text(json.dumps(REPORT, indent=1, default=str))
REPORT = json.dumps({'checks': REPORT['checks'], 'error': REPORT.get('error'), 'mismatch': REPORT.get('mismatch'),
                     'restored': REPORT.get('scalability_restored'), 'seconds': REPORT['seconds']}, default=str)
