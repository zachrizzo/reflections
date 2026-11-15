"""Finishes an interrupted map_switch: waits (keeping my lock alive) until PIE ends, then lets the navmesh finish in
the editor world (Lvl_MockCity), saves the dirty mock levels, and switches the editor back to the home map.
Keeps the lock afterwards (the city-kit PIE look check comes next)."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from map_switch import run, LOCK, ME, HOME  # noqa: E402
from run_pie_test import session  # noqa: E402


def keep_lock(minutes=10):
    try:
        d = json.load(open(LOCK))
    except Exception:  # noqa: BLE001
        d = None
    if d and d.get('owner') != ME and float(d.get('expires_epoch', 0)) > time.time():
        print('lock taken by', d.get('owner'))
        return False
    with open(LOCK, 'w') as f:
        json.dump({'owner': ME, 'purpose': 'world-jump: finishing the mock city nav build + save, then switching the editor '
                   'back to Lvl_HeroSampleCrowd; then a ~2 min city-kit PIE look check (no PIE by others please)',
                   'acquired_epoch': time.time(), 'expires_epoch': time.time() + minutes * 60}, f)
    return True


sid = session()
for i in range(240):
    keep_lock()
    err, v = run(sid, 'import unreal\n"PIE" if unreal.EditorLevelLibrary.get_game_world() is not None else "EDIT"', 30)
    if v == 'EDIT':
        break
    time.sleep(15)
print('PIE over at', time.strftime('%H:%M:%S'))
err, v = run(sid, 'import unreal\nw = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()\n'
                  '"%s" % (w.get_path_name() if w else None)', 30)
if 'Lvl_MockCity' not in str(v):
    print('editor is not on Lvl_MockCity any more:', v, '- stopping here')
    sys.exit(0)
built = False
for i in range(36):
    keep_lock()
    err, v = run(sid, 'import unreal\n'
                      'w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()\n'
                      'zg = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.ZoneGraphData)\n'
                      'nav = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.RecastNavMesh)\n'
                      'building = unreal.NavigationSystemV1.is_navigation_being_built(w)\n'
                      'json_out = {"world": w.get_name(), "zonegraph": len(zg), "navmesh": len(nav), "nav_building": building}\n'
                      'import json\njson.dumps(json_out)', 60)
    if isinstance(v, dict) and v.get('zonegraph') and v.get('navmesh') and not v.get('nav_building'):
        if i == 0:
            run(sid, 'import unreal\nunreal.SystemLibrary.execute_console_command(unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world(), "RebuildNavigation")\n"rebuild requested"')
            time.sleep(5)
            continue
        built = True
        break
    time.sleep(5)
print('nav built:', built)
run(sid, 'import unreal\nimport json\n'
         'ok = unreal.EditorLevelLibrary.save_all_dirty_levels()\n'
         'dirty = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]\n'
         'json.dumps({"saved": ok, "still_dirty": dirty})', 300)
run(sid, 'import unreal\nok = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level("%s")\n"back home: %%s" %% ok' % HOME, 300)
keep_lock(8)
print('done at', time.strftime('%H:%M:%S'))
