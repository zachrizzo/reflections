"""Editor map-switch window: build the mock city's ZoneGraph lanes and navmesh in an editor world, save, switch back.

Holds Saved/PIE_LOCK.json the whole time. Aborts (and switches nothing) if PIE runs or the open map is dirty.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import uepy  # noqa: E402
from run_pie_test import session, py  # noqa: E402

LOCK = 'C:/Users/zachc/Documents/Unreal Projects/reflections/Saved/PIE_LOCK.json'
ME = 'local_830b60d0-e78a-4297-82b7-84148e788d04'
HOME = '/Game/Characters/Hero/Sample/Lvl_HeroSampleCrowd'
MOCK = '/Game/MockCity/Lvl_MockCity'


def val(text):
    try:
        v = json.loads(text).get('returnValue')
    except Exception:  # noqa: BLE001
        return text
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:  # noqa: BLE001
            return v
    return v


def run(sid, code, timeout=300):
    err, text = py(sid, code, timeout)
    v = val(text)
    print(time.strftime('%H:%M:%S'), 'ERR' if err else 'ok', str(v)[:1500])
    return err, v


def main():
    held = None
    try:
        held = json.load(open(LOCK))
    except Exception:  # noqa: BLE001
        pass
    if held and held.get('owner') != ME and float(held.get('expires_epoch', 0)) > time.time():
        print('lock held by', held.get('owner'), '- not switching')
        return
    sid = session()
    err, v = run(sid, 'import unreal\n'
                      'pie = unreal.EditorLevelLibrary.get_game_world() is not None\n'
                      'dirty = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]\n'
                      'w = unreal.EditorLevelLibrary.get_editor_world()\n'
                      '{"pie": pie, "dirty": dirty, "world": w.get_path_name() if w else None}')
    if err or not isinstance(v, dict) or v.get('pie') or v.get('dirty'):
        print('not safe to switch:', v)
        return
    home = (v.get('world') or HOME).split('.')[0]
    keep = bool(held and held.get('owner') == ME)   # already holding a longer slot: keep it afterwards
    with open(LOCK, 'w') as f:
        json.dump({'owner': ME, 'purpose': 'world-jump: editor map switch to build mock city ZoneGraph + navmesh, then back (~3 min, no PIE please)',
                   'acquired_epoch': time.time(),
                   'expires_epoch': max(time.time() + 300, float((held or {}).get('expires_epoch', 0)))}, f)
    try:
        run(sid, 'import unreal\n'
                 'w = unreal.EditorLevelLibrary.get_editor_world()\n'
                 'unreal.SystemLibrary.execute_console_command(w, "Crowd.City.SetupZoneGraph")\n'
                 'ok = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level("%s")\n'
                 '"loaded %%s" %% ok' % MOCK, 300)
        built = False
        for i in range(24):
            time.sleep(5)
            err, v = run(sid, 'import unreal\n'
                              'w = unreal.EditorLevelLibrary.get_editor_world()\n'
                              'zg = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.ZoneGraphData)\n'
                              'nav = unreal.NavigationSystemV1.get_navigation_system(w)\n'
                              'building = unreal.NavigationSystemV1.is_navigation_being_built(w)\n'
                              'pts = {}\n'
                              'for name, x in (("Gray", 0.0), ("Red", 150000.0), ("White", 300000.0)):\n'
                              '    try:\n'
                              '        p = unreal.NavigationSystemV1.k2_project_point_to_navigation(w, unreal.Vector(x - 3800.0, 1100.0, 100.0), None, None, unreal.Vector(300, 300, 300))\n'
                              '    except Exception:\n'
                              '        p = None\n'
                              '    if isinstance(p, tuple):\n'
                              '        p = p[0] if p and p[-1] else None\n'
                              '    pts[name] = [round(p.x), round(p.y), round(p.z)] if p is not None and abs(p.z) < 100000 else None\n'
                              '{"world": w.get_name(), "zonegraph": len(zg), "nav_building": building, "nav_points": pts}', 120)
            if isinstance(v, dict) and v.get('zonegraph') and not v.get('nav_building') and all(v.get('nav_points', {}).values()):
                built = True
                break
            if i == 3 and isinstance(v, dict) and not any(v.get('nav_points', {}).values()):
                run(sid, 'import unreal\nunreal.SystemLibrary.execute_console_command(unreal.EditorLevelLibrary.get_editor_world(), "RebuildNavigation")\n"rebuild nav requested"')
        print('built:', built)
        run(sid, 'import unreal\n'
                 'ok = unreal.EditorLevelLibrary.save_all_dirty_levels()\n'
                 'dirty = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]\n'
                 '{"saved": ok, "still_dirty": dirty}', 300)
    finally:
        run(sid, 'import unreal\n'
                 'ok = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level("%s")\n'
                 '"back to %%s: %%s" %% ("%s", ok)' % (home, home), 300)
        try:
            if json.load(open(LOCK)).get('owner') == ME and not keep:
                os.remove(LOCK)
        except Exception:  # noqa: BLE001
            pass


if __name__ == '__main__':
    main()
