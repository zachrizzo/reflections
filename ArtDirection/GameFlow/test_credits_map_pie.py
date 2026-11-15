"""Map credits layout check (one PIE run, < 60 s), with Saved/PIE_LOCK.json already claimed by this session from
outside the editor.

The editor DLL that reads the new Credits.Map key lands with the next build train. Until then this run shows the
same layout with the loaded DLL: for the run only, Credits.Thanks holds Epic's line, the five map lines and the
engine line, which is exactly the order the new code draws. Then:
  Credits screen (820 px panel) -> capture; Victory screen (660 px embedded panel) -> capture.
After PIE stops, Credits.Thanks is put back as it was and Credits.Map is added; the table is saved.

PNGs: Saved/GameFlowTest/credits_map_*.png. Result in REPORT."""
import base64
import json
import time
from pathlib import Path

APP = 'EditorToolset.EditorAppToolset.'
ST = 'EditorToolset.StringTableToolset.'
TABLE = {'refPath': '/Game/UI/ST_GameFlowText.ST_GameFlowText'}
OUT = Path(unreal.Paths.project_saved_dir()).resolve() / 'GameFlowTest'
OUT.mkdir(exist_ok=True)
LOCK = Path(unreal.Paths.project_saved_dir()).resolve() / 'PIE_LOCK.json'
ME = 'local_17412422-30df-448e-8411-6f5883a914da'
MAP_LINES = [
    'Map data © OpenStreetMap contributors, ODbL (openstreetmap.org/copyright)',
    'Landmark models adapted from Codriver 3D (3d-assets.codriver.io), CC BY 4.0',
    'Albert Memorial scan by artfletch (Zenodo), CC BY 4.0 · Street props by Minimaliano (Fab), CC BY 4.0',
    'Textures and props: Poly Haven (CC0) · Trees: Cosmo Tree Gen by FrogCosmonaut (MIT) · Signs set in Noto Serif (SIL OFL 1.1)',
    'Full licence notices: THIRD_PARTY_NOTICES.txt',
]
REPORT = {'checks': {}, 'steps': []}
T0 = time.time()


def rv(r):
    return r.get('returnValue') if isinstance(r, dict) else r


def gw():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


def flow():
    w = gw()
    gi = unreal.GameplayStatics.get_game_instance(w) if w else None
    return unreal.get_game_instance_subsystem(gi, unreal.ReflectionsGameFlowSubsystem) if gi else None


def screen():
    f = flow()
    return f.get_screen().name if f else None


def check(name, ok):
    REPORT['checks'][name] = bool(ok)


async def capture(name):
    try:
        r = await call_tool('SceneCaptureToolset.SceneCaptureToolset.CaptureGameViewport', world=None, maxResolution=1920)
        data = r['image']
        if data is not None and not isinstance(data, str):
            data = data['data']
        if data:
            (OUT / ('credits_map_' + name + '.png')).write_bytes(base64.b64decode(data))
            return True
    except Exception as e:
        REPORT.setdefault('capture_errors', []).append('%s: %s' % (name, e))
    return False


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


async def run():
    await call_tool(APP + 'StartPIE', options={'warmupSeconds': 3.0})
    check('playing', await wait_for(lambda: screen() == 'NONE', 30))
    await asyncio.sleep(1.5)
    unreal.SystemLibrary.execute_console_command(gw(), 'GameFlow.Tips 0')
    unreal.SystemLibrary.execute_console_command(gw(), 'GameFlow.Credits')
    check('credits', await wait_for(lambda: screen() == 'CREDITS', 5))
    await asyncio.sleep(1.0)
    check('credits_captured', await capture('1_credits_screen'))
    unreal.SystemLibrary.execute_console_command(gw(), 'GameFlow.Victory')
    check('victory', await wait_for(lambda: screen() == 'VICTORY', 5))
    await asyncio.sleep(1.2)
    check('victory_captured', await capture('2_victory_screen'))


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
        ORIG = rv(await call_tool(ST + 'GetEntry', stringTable=TABLE, key='Credits.Thanks'))
        REPORT['thanks_before'] = ORIG
        parts = [p for p in (ORIG or '').splitlines() if p.strip()]
        if len(parts) >= 2:
            sim = parts[:-1] + MAP_LINES + parts[-1:]
            await call_tool(ST + 'SetEntry', stringTable=TABLE, key='Credits.Thanks', value='\n'.join(sim))
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
                unreal.SystemLibrary.execute_console_command(None, 'GameFlow.Tips 1')
                await call_tool(ST + 'SetEntry', stringTable=TABLE, key='Credits.Thanks', value=ORIG)
        else:
            REPORT['error'] = 'Credits.Thanks is not two lines: %r' % ORIG
            try:
                if json.loads(LOCK.read_text()).get('owner') == ME:
                    LOCK.unlink()
            except Exception:
                pass
        # The real key, for the new code (and so the lines can change without a build).
        await call_tool(ST + 'SetEntry', stringTable=TABLE, key='Credits.Map', value='\n'.join(MAP_LINES))
        check('thanks_restored', rv(await call_tool(ST + 'GetEntry', stringTable=TABLE, key='Credits.Thanks')) == ORIG)
        check('map_key', rv(await call_tool(ST + 'GetEntry', stringTable=TABLE, key='Credits.Map')) == '\n'.join(MAP_LINES))
        check('table_saved', unreal.EditorAssetLibrary.save_asset('/Game/UI/ST_GameFlowText', only_if_is_dirty=False))
        REPORT['keys'] = len(rv(await call_tool(ST + 'ListKeys', stringTable=TABLE)) or [])
REPORT['seconds'] = round(time.time() - T0, 1)
(OUT / 'credits_map_report.json').write_text(json.dumps(REPORT, indent=1, default=str))
REPORT = json.dumps({'checks': REPORT['checks'], 'error': REPORT.get('error'), 'keys': REPORT.get('keys'),
                     'seconds': REPORT['seconds']}, default=str)
