"""Short PIE diagnostic for mouse input on the title menu (under Saved/PIE_LOCK.json). Run like test_game_flow_pie.py."""
import json
import re
import time
from pathlib import Path

APP = 'EditorToolset.EditorAppToolset.'
SI = 'SlateInspectorToolset.SlateInspectorToolset.'
LOCK = Path(unreal.Paths.project_saved_dir()) / 'PIE_LOCK.json'
ME = 'local_17412422-30df-448e-8411-6f5883a914da'
DIAG = {'candidates': []}


def flow():
    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    gi = unreal.GameplayStatics.get_game_instance(w) if w else None
    return unreal.get_game_instance_subsystem(gi, unreal.ReflectionsGameFlowSubsystem) if gi else None


def st():
    f = flow()
    return {'screen': f.get_screen().name, 'focus': f.get_menu_focused_index()} if f else None


def lock_free():
    try:
        lock = json.loads(LOCK.read_text())
        return lock.get('owner') == ME or float(lock.get('expires_epoch', 0)) <= time.time()
    except Exception:
        return True


async def run():
    unreal.SystemLibrary.execute_console_command(None, 'GameFlow.TitleInPIE 1')
    await call_tool(APP + 'StartPIE', options={'warmupSeconds': 3.0})
    for _ in range(40):
        s = st()
        if s and s['screen'] == 'TITLE':
            break
        await asyncio.sleep(0.25)
    await asyncio.sleep(0.8)
    DIAG['start'] = st()
    snap = await call_tool(SI + 'Snapshot', ref='', maxDepth=200)
    DIAG['snapshot_lines'] = len(snap.splitlines())
    for line in snap.splitlines():
        if '"Credits"' in line or '"Start"' in line:
            m = re.search(r'\[ref=([^\]]+)\]', line)
            DIAG['candidates'].append(line.strip()[:200])
            if m and '"Credits"' in line:
                ref = m.group(1)
                hit = await call_tool(SI + 'HitTest', ref=ref)
                hov = await call_tool(SI + 'Hover', ref=ref)
                await asyncio.sleep(0.4)
                after_hover = st()
                clk = await call_tool(SI + 'Click', ref=ref)
                await asyncio.sleep(0.6)
                after_click = st()
                refusal = await call_tool(SI + 'LastRefusal')
                DIAG.setdefault('tries', []).append({'ref': ref, 'hit': hit, 'hover': hov, 'after_hover': after_hover,
                                                    'click': clk, 'after_click': after_click, 'refusal': refusal})
                if after_click and after_click['screen'] != 'TITLE':
                    break


if await call_tool(APP + 'IsPIERunning') or not lock_free():
    DIAG['error'] = 'BLOCKED'
else:
    now = int(time.time())
    LOCK.write_text(json.dumps({'owner': ME, 'purpose': 'game flow mouse diagnostic (<40 s)', 'acquired_epoch': now, 'expires_epoch': now + 90}))
    try:
        await run()
    except Exception as e:
        DIAG['error'] = repr(e)
    finally:
        if await call_tool(APP + 'IsPIERunning'):
            await call_tool(APP + 'StopPIE')
        try:
            if json.loads(LOCK.read_text()).get('owner') == ME:
                LOCK.unlink()
        except Exception:
            pass
        unreal.SystemLibrary.execute_console_command(None, 'GameFlow.TitleInPIE 0')
DIAG = json.dumps(DIAG, default=str)
