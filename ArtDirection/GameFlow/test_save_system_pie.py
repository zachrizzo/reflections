"""Save system PIE test (one run, < 3 min), with Saved/PIE_LOCK.json already claimed by this session from outside
the editor. Existing manual / quick saves are backed up first and put back after.

  play -> damage + spend mana -> Save screen > Slot 1 -> move, Tarnish +2 -> quick save (F5, else console)
  -> move again -> Load screen > Slot 1 > confirm -> map reloads at the Slot 1 spot with its health
  -> fall (GameFlow.Kill) -> death screen -> Respawn -> up at the Slot 1 spot
  -> quick load (F9 / console) -> at the quick-save spot.

Result in REPORT; PNGs in Saved/GameFlowTest/save_*.png. The lock is deleted when PIE stops."""
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
BACKUP = OUT / 'save_backup'
LOCK = SAVED / 'PIE_LOCK.json'
ME = 'local_17412422-30df-448e-8411-6f5883a914da'
SLOT_FILES = ['Reflections_Save_1', 'Reflections_Save_2', 'Reflections_Save_3', 'Reflections_QuickSave']
REPORT = {'checks': {}, 'steps': []}
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


def health():
    p = pawn()
    h = p.get_component_by_class(unreal.ReflectionsHealthComponent) if p else None
    return round(h.get_editor_property('health'), 1) if h else None


def driver():
    p = pawn()
    return p.get_component_by_class(unreal.ReflectionsSampleSpellDriver) if p else None


def loc():
    p = pawn()
    l = p.get_actor_location() if p else None
    return [round(l.x), round(l.y), round(l.z)] if l else None


def state():
    f = flow()
    if not f:
        return {'screen': None}
    return {'screen': f.get_screen().name, 'focus': f.get_menu_focused_index(), 'buttons': list(f.get_menu_button_labels()),
            'pawn': loc(), 'health': health(), 'tarnish': f.get_infection_count(),
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


def slot_used(slot):
    f = flow()
    return bool(f and f.get_save_slot_info(slot).used)


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
            (OUT / ('save_' + name + '.png')).write_bytes(base64.b64decode(data))
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


def playing():
    s = state()
    return s.get('screen') == 'NONE' and s.get('pawn') is not None


def teleport(offset):
    p = pawn()
    l = p.get_actor_location()
    p.set_actor_location(unreal.Vector(l.x + offset, l.y, l.z), False, True)


async def run():
    await call_tool(APP + 'StartPIE', options={'warmupSeconds': 3.0})
    check('playing', await wait_for(playing, 30))
    await asyncio.sleep(2.5)   # the Start checkpoint
    console('GameFlow.DeathScreen 1')
    console('GameFlow.Tips 0')

    # ---- Slot 1 through the Save screen, hurt and short of mana ----
    unreal.GameplayStatics.apply_damage(pawn(), 30.0, None, pawn(), None)
    d = driver()
    if d:
        d.spend_magic(40.0)
    await asyncio.sleep(0.3)
    hurt = health()
    spot1 = loc()
    console('GameFlow.SaveMenu')
    check('save_screen', await wait_for(lambda: state().get('screen') == 'SAVE_GAME', 3))
    await asyncio.sleep(0.6)
    s = log('save_screen')
    check('save_screen_slots', s.get('buttons', [])[:3] == ['Slot 1', 'Slot 2', 'Slot 3'])
    await capture('1_save_screen_empty')
    await focus_to('Slot 1')
    await key('Enter', 0.8)
    s = log('saved_slot1', hurt=hurt, spot=spot1)
    check('slot1_saved', slot_used(2))
    check('slot1_is_checkpoint', s.get('checkpoint') == 'Slot 1')
    await capture('2_save_screen_saved')
    console('GameFlow.Resume')
    await asyncio.sleep(0.5)

    # ---- Quick save somewhere else, with Tarnish 2 ----
    teleport(600.0)
    console('GameFlow.Infect 2')
    await asyncio.sleep(0.4)
    spot_quick = loc()
    await key('F5', 0.8)
    check('quick_save_f5', slot_used(1))
    if not slot_used(1):
        console('GameFlow.Save q')
        await asyncio.sleep(0.5)
    check('quick_saved', slot_used(1))
    log('quick_saved', spot=spot_quick)

    # ---- Load Slot 1 through the Load screen (with the confirm) ----
    teleport(900.0)
    console('GameFlow.LoadMenu')
    check('load_screen', await wait_for(lambda: state().get('screen') == 'LOAD_GAME', 3))
    await asyncio.sleep(0.6)
    s = log('load_screen')
    check('load_screen_rows', s.get('buttons', [])[:5] == ['Quick save', 'Autosave', 'Slot 1', 'Slot 2', 'Slot 3'])
    await capture('3_load_screen')
    await focus_to('Slot 1')
    await key('Enter', 0.8)
    check('load_confirm', state().get('screen') == 'CONFIRM')
    await capture('4_load_confirm')
    await key('Enter', 0.5)
    check('slot1_reloaded', await wait_for(lambda: playing() and state().get('checkpoint') == 'Slot 1', 60, 0.5))
    await asyncio.sleep(1.5)
    s = log('after_load_slot1')
    p = s.get('pawn') or [0, 0, 0]
    check('slot1_position', spot1 is not None and math.dist(p, spot1) < 200.0)
    check('slot1_health', hurt is not None and s.get('health') is not None and abs(s['health'] - hurt) < 1.0)
    check('slot1_tarnish', s.get('tarnish') == 0)   # Slot 1 was saved before the infections
    await capture('5_after_load')

    # ---- Fall: death screen, then respawn at the Slot 1 spot ----
    console('GameFlow.Kill')
    check('death_screen', await wait_for(lambda: state().get('screen') == 'DEATH', 5))
    await asyncio.sleep(0.6)
    s = log('death_screen')
    check('death_default_respawn', (s.get('buttons') or [''])[0].startswith('Respawn'))
    await capture('6_death_screen')
    await key('Enter', 0.5)   # the default: Respawn
    up = await wait_for(lambda: playing() and not (driver() and driver().is_defeated()), 12, 0.25)
    await asyncio.sleep(0.8)
    s = log('respawned')
    check('respawned', up)
    p = s.get('pawn') or [0, 0, 0]
    check('respawn_at_slot1', spot1 is not None and math.dist(p, spot1) < 300.0)

    # ---- Quick load ----
    await key('F9', 0.5)
    if not await wait_for(lambda: state().get('checkpoint') == 'Quick save', 3):
        console('GameFlow.Load q')
    check('quick_loaded', await wait_for(lambda: playing() and state().get('checkpoint') == 'Quick save', 60, 0.5))
    await asyncio.sleep(1.0)
    s = log('after_quick_load')
    p = s.get('pawn') or [0, 0, 0]
    check('quick_position', spot_quick is not None and math.dist(p, spot_quick) < 200.0)
    check('quick_tarnish_kept', s.get('tarnish') == 2)   # saved with 2 anonymous infections
    await capture('7_after_quick_load')


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
        # Keep anyone's real saves: move them aside for the test and put them back after.
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
(OUT / 'save_report.json').write_text(json.dumps(REPORT, indent=1, default=str))
REPORT = json.dumps({'checks': REPORT['checks'], 'error': REPORT.get('error'), 'seconds': REPORT['seconds']}, default=str)
