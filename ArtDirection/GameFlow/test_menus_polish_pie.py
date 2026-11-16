"""Menus-polish PIE test (11-15): screenshots of the credits, title, settings and loading screens, then the save
and load paths with the new loading screen and async saves. One run, about 3 min. Claim Saved/PIE_LOCK.json
(owner "menus-polish") from outside the editor first. Existing manual and quick saves are backed up and put back.

  play -> Credits, Title, Settings, loading screen (GameFlow.HoldLoadingScreen) screenshots
  -> coins +3, quest item x2, standing +7 -> Save screen > Slot 1 (cached at once, on disk within 1 s)
  -> move, coins +2, item +1 -> Pause > Quit to title > confirm (loading screen) -> title -> Continue
     -> Slot 1 spot, coins, item, standing back
  -> move, item +1 -> Load screen > Slot 1 > confirm (loading screen) -> the same checks
  -> Pause > Quit to desktop > confirm opens, then Escape cancels it (the test never presses the quit itself
     in the shared editor; a packaged build checks the real exit).

Result in REPORT; PNGs in Saved/GameFlowTest/polish_*.png."""
import base64
import json
import math
import shutil
import time
from pathlib import Path

APP = 'EditorToolset.EditorAppToolset.'
SI = 'SlateInspectorToolset.SlateInspectorToolset.'
SAVED = Path(unreal.Paths.project_saved_dir()).resolve()
OUT = SAVED / 'GameFlowTest'
OUT.mkdir(exist_ok=True)
SAVES = SAVED / 'SaveGames'
BACKUP = OUT / 'polish_save_backup'
LOCK = SAVED / 'PIE_LOCK.json'
ME = 'menus-polish'
SLOT_FILES = ['Reflections_Save_1', 'Reflections_Save_2', 'Reflections_Save_3', 'Reflections_QuickSave']
ITEM = 'polish_test_satchel'
PERSON = 'polish_test_person'
REPORT = {'checks': {}, 'steps': []}
T0 = time.time()


def gw():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


def gi():
    w = gw()
    return unreal.GameplayStatics.get_game_instance(w) if w else None


def flow():
    g = gi()
    return unreal.get_game_instance_subsystem(g, unreal.ReflectionsGameFlowSubsystem) if g else None


def quests():
    g = gi()
    return unreal.get_game_instance_subsystem(g, unreal.ReflectionsQuestSubsystem) if g else None


def jump():
    g = gi()
    return unreal.get_game_instance_subsystem(g, unreal.ReflectionsWorldJumpSubsystem) if g else None


def pawn():
    w = gw()
    pc = unreal.GameplayStatics.get_player_controller(w, 0) if w else None
    return pc.get_controlled_pawn() if pc else None


def loc():
    p = pawn()
    l = p.get_actor_location() if p else None
    return [round(l.x), round(l.y), round(l.z)] if l else None


def coins():
    j = jump()
    if not j:
        return None
    return [j.get_coins(w) for w in (unreal.ReflectionsWorld.GRAY, unreal.ReflectionsWorld.RED, unreal.ReflectionsWorld.WHITE)]


def items():
    q = quests()
    return q.get_item_count(ITEM) if q else None


def standing():
    q = quests()
    return round(q.get_standing(PERSON), 1) if q else None


def journal():
    q = quests()
    if not q:
        return None
    return sorted('%s=%s' % (str(i), q.get_status(i).name) for i in q.get_journal_quests())


def state():
    f = flow()
    if not f:
        return {'screen': None}
    return {'screen': f.get_screen().name, 'focus': f.get_menu_focused_index(), 'buttons': list(f.get_menu_button_labels()),
            'pawn': loc(), 'coins': coins(), 'items': items(), 'standing': standing(),
            'checkpoint': f.get_checkpoint().reason if f.has_checkpoint() else None}


def log(name, **extra):
    s = state()
    s.update(extra)
    s['t'] = round(time.time() - T0, 1)
    REPORT['steps'].append({name: s})
    return s


def check(name, ok):
    REPORT['checks'][name] = bool(ok)


def console(cmd):
    unreal.SystemLibrary.execute_console_command(gw(), cmd)


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
            path = OUT / ('polish_' + name + '.png')
            path.write_bytes(base64.b64decode(data))
            REPORT.setdefault('screenshots', []).append(str(path))
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
    for _ in range(14):
        f = state().get('focus')
        if f == target:
            return True
        await key('Down' if f is None or f < target else 'Up')
    return state().get('focus') == target


def playing():
    s = state()
    return s.get('screen') == 'NONE' and s.get('pawn') is not None


def loading():
    f = flow()
    return bool(f and f.is_loading_screen_active()) if hasattr(f, 'is_loading_screen_active') else False


def teleport(offset):
    p = pawn()
    l = p.get_actor_location()
    p.set_actor_location(unreal.Vector(l.x + offset, l.y, l.z), False, True)


async def screenshots():
    console('GameFlow.Credits')
    check('credits_screen', await wait_for(lambda: state().get('screen') == 'CREDITS', 3))
    await asyncio.sleep(0.8)
    log('credits')
    await capture('1_credits')
    console('GameFlow.Title')
    check('title_screen', await wait_for(lambda: state().get('screen') == 'TITLE', 3))
    await asyncio.sleep(0.8)
    s = log('title')
    check('title_has_quit', 'Quit' in s.get('buttons', []))
    await capture('2_title')
    if await focus_to('Settings'):
        await key('Enter', 0.8)
        check('settings_screen', state().get('screen') == 'SETTINGS')
        await capture('3_settings')
        await key('Escape', 0.5)
    console('GameFlow.Resume')
    await asyncio.sleep(0.5)
    console('GameFlow.HoldLoadingScreen 1')
    await asyncio.sleep(0.8)
    await capture('4_loading_screen')
    console('GameFlow.HoldLoadingScreen 0')
    check('loading_screen_ends', await wait_for(lambda: not loading(), 5))
    console('GameFlow.Pause')
    check('pause_screen', await wait_for(lambda: state().get('screen') == 'PAUSE', 3))
    await asyncio.sleep(0.6)
    s = log('pause')
    check('pause_has_quit_to_desktop', 'Quit to desktop' in s.get('buttons', []))
    await capture('5_pause')
    console('GameFlow.Resume')
    await asyncio.sleep(0.5)


async def run():
    await call_tool(APP + 'StartPIE', options={'warmupSeconds': 3.0})
    check('playing', await wait_for(playing, 40))
    await asyncio.sleep(2.5)   # the Start checkpoint
    console('GameFlow.Tips 0')
    await capture('0_play_hud_top_left')   # health and mana bars should sit top left, under the world-jump panel
    await screenshots()

    # ---- Progress, then Slot 1 through the Save screen ----
    j, q = jump(), quests()
    if j:
        j.award_coin(unreal.ReflectionsWorld.RED, 3)
    if q:
        q.give_item(ITEM, 2)
        q.adjust_standing(PERSON, 7.0)
    await asyncio.sleep(0.3)
    saved = log('before_save')
    console('GameFlow.SaveMenu')
    check('save_screen', await wait_for(lambda: state().get('screen') == 'SAVE_GAME', 3))
    await asyncio.sleep(0.5)
    await focus_to('Slot 1')
    t = time.time()
    await key('Enter', 0.1)
    f = flow()
    check('slot1_listed_at_once', f.get_save_slot_info(2).used)
    check('slot1_on_disk', await wait_for(lambda: (SAVES / 'Reflections_Save_1.sav').exists(), 2, 0.05))
    REPORT['save_to_disk_s'] = round(time.time() - t, 2)
    s = log('saved_slot1')
    check('slot1_is_checkpoint', s.get('checkpoint') == 'Slot 1')
    await capture('6_saved_slot1')
    console('GameFlow.Resume')
    await asyncio.sleep(0.5)

    # ---- Change things, Quit to title (loading screen), Continue ----
    teleport(700.0)
    if j:
        j.award_coin(unreal.ReflectionsWorld.RED, 2)
    if q:
        q.give_item(ITEM, 1)
    console('GameFlow.Pause')
    await wait_for(lambda: state().get('screen') == 'PAUSE', 3)
    await asyncio.sleep(0.4)
    await focus_to('Quit to title')
    await key('Enter', 0.5)
    check('quit_title_confirm', state().get('screen') == 'CONFIRM')
    await key('Enter', 0.05)
    check('loading_screen_on_quit_to_title', loading())
    await capture('7_loading_quit_to_title')
    t = time.time()
    check('back_at_title', await wait_for(lambda: state().get('screen') == 'TITLE' and not loading(), 90, 0.25))
    REPORT['quit_to_title_s'] = round(time.time() - t, 1)
    await asyncio.sleep(0.6)
    s = log('title_after_quit')
    check('title_continue', 'Continue' in s.get('buttons', []))
    await capture('8_title_after_quit')
    await focus_to('Continue')
    await key('Enter', 0.05)
    t = time.time()
    check('continued', await wait_for(lambda: playing() and not loading(), 90, 0.25))
    REPORT['continue_s'] = round(time.time() - t, 1)
    await asyncio.sleep(1.0)
    s = log('after_continue')
    p = s.get('pawn') or [0, 0, 0]
    check('continue_position', saved.get('pawn') is not None and math.dist(p, saved['pawn']) < 200.0)
    check('continue_coins', s.get('coins') == saved.get('coins'))
    check('continue_items', s.get('items') == saved.get('items'))
    check('continue_standing', s.get('standing') == saved.get('standing'))
    await capture('9_after_continue')

    # ---- Change again, Load Slot 1 through the Load screen ----
    teleport(-700.0)
    if q:
        q.give_item(ITEM, 1)
    console('GameFlow.LoadMenu')
    check('load_screen', await wait_for(lambda: state().get('screen') == 'LOAD_GAME', 3))
    await asyncio.sleep(0.5)
    await focus_to('Slot 1')
    await key('Enter', 0.5)
    check('load_confirm', state().get('screen') == 'CONFIRM')
    await key('Enter', 0.05)
    check('loading_screen_on_load', loading())
    await capture('10_loading_load_slot1')
    t = time.time()
    check('slot1_loaded', await wait_for(lambda: playing() and not loading() and state().get('checkpoint') == 'Slot 1', 90, 0.25))
    REPORT['load_slot_s'] = round(time.time() - t, 1)
    await asyncio.sleep(1.0)
    s = log('after_load_slot1')
    p = s.get('pawn') or [0, 0, 0]
    check('load_position', saved.get('pawn') is not None and math.dist(p, saved['pawn']) < 200.0)
    check('load_coins', s.get('coins') == saved.get('coins'))
    check('load_items', s.get('items') == saved.get('items'))
    check('load_standing', s.get('standing') == saved.get('standing'))
    await capture('11_after_load')

    # ---- Quit to desktop: open the confirm and cancel it. The quit itself is never pressed in the shared editor
    # (in the editor it only drops the screen; the packaged build checks the real exit). ----
    console('GameFlow.Pause')
    await wait_for(lambda: state().get('screen') == 'PAUSE', 3)
    await asyncio.sleep(0.4)
    await focus_to('Quit to desktop')
    await key('Enter', 0.5)
    check('quit_desktop_confirm', state().get('screen') == 'CONFIRM')
    await capture('12_quit_desktop_confirm')
    await key('Escape', 0.5)
    check('quit_cancel_back_to_pause', state().get('screen') == 'PAUSE')
    check('pie_still_running_after_cancel', gw() is not None)
    console('GameFlow.Resume')
    await asyncio.sleep(0.4)


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
        BACKUP.mkdir(exist_ok=True)
        moved = []
        for name in SLOT_FILES:
            f = SAVES / (name + '.sav')
            if f.exists():
                shutil.move(str(f), str(BACKUP / f.name))
                moved.append(f.name)
        REPORT['backed_up'] = moved
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
            for name in SLOT_FILES:
                test_file = SAVES / (name + '.sav')
                if test_file.exists():
                    test_file.unlink()
            for name in moved:
                shutil.move(str(BACKUP / name), str(SAVES / name))
            unreal.SystemLibrary.execute_console_command(None, 'GameFlow.Tips 1')
REPORT['seconds'] = round(time.time() - T0, 1)
(OUT / 'polish_report.json').write_text(json.dumps(REPORT, indent=1, default=str))
REPORT = json.dumps({'checks': REPORT['checks'], 'error': REPORT.get('error'), 'seconds': REPORT['seconds'],
                     'timing': {k: REPORT.get(k) for k in ('save_to_disk_s', 'quit_to_title_s', 'continue_s', 'load_slot_s', 'quit_s')}},
                    default=str)
