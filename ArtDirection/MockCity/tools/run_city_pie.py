"""City-kit look check, kept short: start PIE, open the mock city, run city_driver.py (teleport + screenshot at
each spot), stop PIE, then read the editor log written during the run for Lumen surface-cache warnings."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import uepy  # noqa: E402
from run_mock_pie import session, tool, py, capture, PIE_WORLD  # noqa: E402
import run_mock_pie  # noqa: E402

SP = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(SP, 'city_results.json')
SHOTS = os.path.join(SP, 'shots_city')
os.makedirs(SHOTS, exist_ok=True)
run_mock_pie.SHOTS = SHOTS
LOG = 'C:/Users/zachc/Documents/Unreal Projects/reflections/Saved/Logs/reflections.log'
LOCK = 'C:/Users/zachc/Documents/Unreal Projects/reflections/Saved/PIE_LOCK.json'
ME = 'local_830b60d0-e78a-4297-82b7-84148e788d04'


def results():
    try:
        with open(RESULTS) as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


def main():
    t0 = time.time()
    log_start = os.path.getsize(LOG)
    for name in os.listdir(SP):
        if name.startswith('cap_') and name.endswith('.done'):
            os.remove(os.path.join(SP, name))
    if os.path.exists(RESULTS):
        os.remove(RESULTS)
    try:
        held = json.load(open(LOCK))
    except Exception:  # noqa: BLE001
        held = None
    if held and held.get('owner') != ME and float(held.get('expires_epoch', 0)) > time.time():
        print('lock held by', held.get('owner'), '- not starting')
        return
    sid = session()
    err, text = py(sid, 'import unreal\n"PIE=%s" % (unreal.EditorLevelLibrary.get_game_world() is not None)')
    if 'PIE=True' in text:
        print('PIE busy, not starting')
        return
    with open(LOCK, 'w') as f:
        json.dump({'owner': ME, 'purpose': 'world-jump: city kit look + Frostside re-shoot on Lvl_MockCity (~2 min)',
                   'acquired_epoch': time.time(), 'expires_epoch': time.time() + 200}, f)
    print('start', tool(sid, "EditorToolset.EditorAppToolset", "StartPIE", {}, 90))
    try:
        time.sleep(3)
        print('open', py(sid, 'import unreal\nunreal.SystemLibrary.execute_console_command(unreal.EditorLevelLibrary.get_game_world(), "open /Game/MockCity/Lvl_MockCity")\n"ok"'))
        for _ in range(90):
            time.sleep(1)
            err, text = py(sid, 'import unreal\nw = unreal.EditorLevelLibrary.get_game_world()\n(w.get_path_name() if w else "none")', 30)
            if 'Lvl_MockCity' in text:
                PIE_WORLD['path'] = json.loads(text)['returnValue']
                break
        print('world', text)
        time.sleep(2)
        print('driver', py(sid, open(os.path.join(SP, 'city_driver.py'), encoding='utf-8').read()))
        captured = set()
        deadline = time.time() + 120
        while time.time() < deadline:
            time.sleep(0.5)
            r = results()
            for tag, _ in r.get('shots', []):
                if tag not in captured:
                    captured.add(tag)
                    print('capture', tag, capture(sid, tag))
                    open(os.path.join(SP, 'cap_%s.done' % tag), 'w').close()
            if r.get('done'):
                break
    finally:
        print('stop', tool(sid, "EditorToolset.EditorAppToolset", "StopPIE", {}, 60))
        try:
            if json.load(open(LOCK)).get('owner') == ME:
                os.remove(LOCK)
        except Exception:  # noqa: BLE001
            pass
        print('elapsed %.0fs' % (time.time() - t0))
    r = results()
    print(json.dumps({'done': r.get('done'), 'shots': len(r.get('shots', [])), 'log_tail': r.get('log', [])[-4:]}, indent=1))
    with open(LOG, 'rb') as f:
        f.seek(log_start)
        text = f.read().decode('utf-8', 'replace')
    lines = text.splitlines()
    hits = [l for l in lines if any(k in l.lower() for k in ('surface cache', 'surfacecache', 'oversubscribed', 'atlas'))]
    print('lumen warnings during run: %d' % len(hits))
    for l in hits[:8]:
        print('  ', l[:220])
    nav = [l for l in lines if 'navmesh' in l.lower() or 'nav mesh' in l.lower()]
    print('navmesh lines during run: %d' % len(nav))
    for l in nav[:6]:
        print('  ', l[:220])
    errs = [l for l in lines if ('Error' in l or 'Warning' in l) and ('MockCity' in l or 'Kit_' in l or 'CityKit' in l)]
    print('mock/kit warnings+errors: %d' % len(errs))
    for l in errs[:10]:
        print('  ', l[:220])


if __name__ == '__main__':
    main()
