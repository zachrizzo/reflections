"""Mock Lanthorne PIE check. Run after PIE has travelled to /Game/MockCity/Lvl_MockCity.

Walks (teleports) the hero along the win path with real world jumps: Giltside start, quest givers, step down to
Pewterside at Weigh-House Corner, page 1 on the Weigh-House roof, back up, the key at the Lantern Gate, the Gilt Tower
door, page 2, step up into the Frost Tower, page 3 (book complete), the crown arena. Also checks every story marker
name (no fallback) and samples named people's routines. Writes mock_results.json and asks for screenshots.
"""
import json
import os
import time
import unreal

SP = r'C:\Users\zachc\AppData\Local\Temp\claude\79559c54b34378d8\78cc39ce-9d46-4909-af94-0891e5e47ccf\scratchpad'
RESULTS = os.path.join(SP, 'mock_results.json')
MARKERS = r'C:\Users\zachc\Documents\Unreal Projects\reflections\ArtDirection\MockCity\tools\mockcity_markers.json'
OFF = {'Pew': 0.0, 'Gilt': 150000.0, 'Frost': 300000.0}
W = unreal.ReflectionsWorld
UP, DOWN = unreal.ReflectionsJumpDirection.UP, unreal.ReflectionsJumpDirection.DOWN
FRAMES = []
state = {'step': 0, 't': time.time(), 'log': [], 'checks': {}, 'shots': [], 'done': False}


def save():
    with open(RESULTS, 'w') as f:
        json.dump(state, f, indent=1, default=str)


def log(msg):
    state['log'].append('%.1f %s' % (time.time() - state['t0'], msg))
    save()


def game():
    return unreal.EditorLevelLibrary.get_game_world()


def pc():
    w = game()
    return unreal.GameplayStatics.get_player_controller(w, 0) if w else None


def pawn():
    c = pc()
    return c.get_controlled_pawn() if c else None


def comp():
    p = pawn()
    return p.get_component_by_class(unreal.ReflectionsWorldJumpComponent) if p else None


def side():
    t = str(unreal.ReflectionsWorldLibrary.get_current_world(game())).upper()
    for k in ('GRAY', 'RED', 'WHITE'):
        if k in t:
            return k
    return t


def loc(s, x, y, z):
    return unreal.Vector(OFF[s] + x * 100.0, y * 100.0, z * 100.0)


def put(s, x, y, z=1.0, yaw=None):
    p = pawn()
    p.set_actor_location(loc(s, x, y, z), False, True)
    if yaw is not None:
        pc().set_control_rotation(unreal.Rotator(0.0, -12.0, yaw))


def look(yaw, pitch=-12.0):
    pc().set_control_rotation(unreal.Rotator(0.0, pitch, yaw))


def magic():
    c = comp()
    if not c:
        return None
    r = c.get_magic()
    return [round(float(x), 1) for x in r] if isinstance(r, (tuple, list)) else r


def magic_ready():
    m = magic()
    c = comp()
    if not m or not c:
        return True
    cur = m[1] if len(m) == 3 else m[0]
    return cur >= c.get_jump_magic_cost() + 0.5


def coins():
    w = game()
    return {n: unreal.ReflectionsWorldLibrary.get_coins(w, e) for n, e in (('Pew', W.GRAY), ('Gilt', W.RED), ('Frost', W.WHITE))}


def snapshot(tag):
    p = pawn()
    l = p.get_actor_location() if p else None
    entry = {'tag': tag, 'side': side(), 'loc': [round(l.x), round(l.y), round(l.z)] if l else None, 'coins': coins(),
             'pages': unreal.ReflectionsWorldLibrary.get_page_count(game()), 'magic': magic()}
    state['checks'][tag] = entry
    log('snapshot %s' % json.dumps(entry, default=str))


def shot(tag):
    state['shots'].append((tag, time.time()))
    log('shot ' + tag)


def captured(tag):
    return os.path.exists(os.path.join(SP, 'cap_%s.done' % tag))


def jump(direction):
    ok = unreal.ReflectionsWorldLibrary.request_world_jump(game(), direction)
    log('request jump %s -> %s' % (direction, ok))


def sub(cls):
    try:
        return unreal.SubsystemBlueprintLibrary.get_world_subsystem(game(), cls)
    except Exception as e:  # noqa: BLE001
        log('subsystem %s: %s' % (cls, e))
        return None


def marker_check(tag):
    data = json.load(open(MARKERS, encoding='utf-8'))
    names = []
    for e in data:
        if e.get('optional') or e['name'] == 'VillainArena':
            continue
        names.append(e['name'])
    missing = []
    for n in sorted(set(names)):
        m = unreal.ReflectionsStoryMarkerSubsystem.find_marker(game(), n, False)
        if m is None:
            missing.append(n)
    ms = sub(unreal.ReflectionsStoryMarkerSubsystem)
    auto = [str(x) for x in ms.get_auto_placed_names()] if ms else None
    total = len(ms.get_all_markers()) if ms else None
    state['checks'][tag] = {'names_checked': len(set(names)), 'missing': missing, 'auto_placed': auto, 'markers_in_map': total}
    log('markers %s: checked %d, missing %d, auto-placed %s, in map %s' % (tag, len(set(names)), len(missing), auto, total))


PEOPLE = ['ilse_varrow', 'goldie_fairweather', 'jory_pell', 'dov_merriman', 'barnaby_thrale', 'lucan_marlowe',
          'corin_ashby', 'nell_bramley', 'kit_marrow', 'edie_bramley', 'hester_quaile', 'ada_pollard', 'sorrel_vey',
          'greta_holm', 'gunnar_skarre']


def people(tag):
    lives = sub(unreal.ReflectionsLivesSubsystem)
    ms = sub(unreal.ReflectionsStoryMarkerSubsystem)
    allm = ms.get_all_markers() if ms else []
    rows = {}
    if lives:
        rows['_clock'] = lives.get_clock_text()
        for pid in PEOPLE:
            a = lives.find_actor_for_person(pid)
            if not a:
                rows[pid] = None
                continue
            l = a.get_actor_location()
            near, best = None, 1e18
            for m in allm:
                d = (m.get_actor_location() - l).length()
                if d < best:
                    near, best = str(m.get_editor_property('marker_name')), d
            act = None
            try:
                act = str(lives.get_persona_facts(a).get_editor_property('activity'))
            except Exception:  # noqa: BLE001
                pass
            rows[pid] = {'loc': [round(l.x), round(l.y)], 'near': near, 'dist_m': round(best / 100.0, 1), 'activity': act}
    state['checks'][tag] = rows
    log('people %s: %s' % (tag, json.dumps(rows)[:1500]))


def console(cmd):
    unreal.SystemLibrary.execute_console_command(game(), cmd)
    log('console ' + cmd)


steps = []


def add(name, action=None, until=None, timeout=3.0, wait=0.0):
    steps.append((name, action, until, timeout, wait))


add('wait_hero', None, lambda: comp() is not None and pawn() is not None, 25)
add('settle', None, None, 0, 3.0)
add('start', lambda: (snapshot('start'), console('Lives.TimeScale 120'), console('stat unit')))
add('markers_start', lambda: marker_check('markers_start'))
add('people_0', lambda: people('people_0'))
add('shot_start', lambda: (look(57.0), shot('m01_gilt_start')), lambda: captured('m01_gilt_start'), 12, 0.3)
add('shards', lambda: put('Gilt', -37.5, 6.0), None, 0, 0.4)
add('shards2', lambda: put('Gilt', -38.5, 3.5), None, 0, 0.4)
add('lantern_row', lambda: put('Gilt', 58.0, 33.0, 1.0, 0.0), None, 0, 1.5)
add('shot_row', lambda: shot('m02_gilt_lantern_row'), lambda: captured('m02_gilt_lantern_row'), 12, 0.3)
add('bell_square', lambda: put('Gilt', -48.0, 2.0, 1.0, 150.0), None, 0, 1.5)
add('shot_square', lambda: shot('m03_gilt_bell_square'), lambda: captured('m03_gilt_bell_square'), 12, 0.3)
add('to_corner', lambda: put('Gilt', -77.0, 10.0, 1.0, 225.0), None, 0, 0.5)
add('magic_1', None, magic_ready, 16)
add('jump_down', lambda: (snapshot('pre_jump_down'), jump(DOWN)), lambda: side() == 'GRAY', 5)
add('after_down', lambda: snapshot('pew_corner'), None, 0, 1.5)
add('shot_pew', lambda: shot('m04_pew_weighhouse_corner'), lambda: captured('m04_pew_weighhouse_corner'), 12, 0.3)
add('stair_foot', lambda: put('Pew', -97.0, -10.5, 1.0, 90.0), None, 0, 1.0)
add('shot_stair', lambda: shot('m05_pew_weighhouse_stair'), lambda: captured('m05_pew_weighhouse_stair'), 12, 0.3)
add('roof_page', lambda: put('Pew', -85.5, -1.5, 11.2, 0.0), None, 0, 0.6)
add('roof_shard', lambda: put('Pew', -89.5, 0.5, 11.2, 45.0), None, 0, 0.8)
add('shot_roof', lambda: (snapshot('pew_roof'), shot('m06_pew_weighhouse_roof_page')), lambda: captured('m06_pew_weighhouse_roof_page'), 12, 0.3)
add('magic_2', None, magic_ready, 16)
add('jump_up', lambda: jump(UP), lambda: side() == 'RED', 5)
add('after_up', lambda: snapshot('gilt_roof'), None, 0, 1.0)
add('to_key', lambda: put('Gilt', 139.5, 37.0, 1.6, 0.0), None, 0, 1.0)
add('shot_gate', lambda: (look(200.0), shot('m07_gilt_lantern_gate')), lambda: captured('m07_gilt_lantern_gate'), 12, 0.3)
add('to_door', lambda: put('Gilt', 0.0, 61.3, 1.0, 90.0), None, 0, 2.5)
add('shot_door', lambda: (snapshot('door'), shot('m08_gilt_tower_door_open')), lambda: captured('m08_gilt_tower_door_open'), 12, 0.3)
add('page_2', lambda: put('Gilt', 2.0, 72.0, 1.0), None, 0, 0.6)
add('frost_shard', lambda: put('Gilt', -2.5, 72.5, 1.0), None, 0, 0.6)
add('in_tower', lambda: (put('Gilt', 0.0, 70.0, 1.0, 90.0), snapshot('gilt_tower')), None, 0, 0.8)
add('magic_3', None, magic_ready, 16)
add('jump_up_2', lambda: jump(UP), lambda: side() == 'WHITE', 5)
add('after_up_2', lambda: snapshot('frost_tower'), None, 0, 1.0)
add('page_3', lambda: put('Frost', 1.0, 71.0, 1.0, 45.0), None, 0, 1.5)
add('shot_book', lambda: (snapshot('book'), shot('m09_frost_tower_book_complete')), lambda: captured('m09_frost_tower_book_complete'), 12, 0.3)
add('crown', lambda: put('Frost', 8.0, 78.0, 25.2, 250.0), None, 0, 1.5)
add('shot_crown', lambda: (snapshot('crown'), shot('m10_frost_crown_arena')), lambda: captured('m10_frost_crown_arena'), 12, 0.3)
add('frost_market', lambda: put('Frost', 55.0, 33.0, 1.0, 10.0), None, 0, 1.5)
add('shot_frost_row', lambda: shot('m11_frost_bone_market'), lambda: captured('m11_frost_bone_market'), 12, 0.3)
add('pew_lane', lambda: put('Pew', 40.0, -58.0, 1.0, 10.0), None, 0, 1.5)
add('shot_pew_lane', lambda: shot('m12_pew_coal_lane'), lambda: captured('m12_pew_coal_lane'), 12, 0.3)
add('people_1', lambda: people('people_1'))
add('markers_end', lambda: marker_check('markers_end'))
def frame_stats():
    f = sorted(FRAMES)
    if f:
        state['checks']['frame_ms'] = {'n': len(f), 'median': round(f[len(f) // 2] * 1000.0, 1),
                                       'p95': round(f[int(len(f) * 0.95)] * 1000.0, 1)}
        log('frames %s' % state['checks']['frame_ms'])


add('finish', lambda: (frame_stats(), console('stat unit'), console('Lives.TimeScale 1'), state.update(done=True)))


def tick(delta):
    try:
        if state['done']:
            unreal.unregister_slate_post_tick_callback(handle[0])
            save()
            return
        if game() is None:
            return
        if state['step'] > 3 and 0.0 < delta < 1.0:
            FRAMES.append(delta)
        i = state['step']
        name, action, until, timeout, wait = steps[i]
        now = time.time()
        if state.get('entered_step') != i:
            state['entered_step'] = i
            state['entered'] = now
            state['acted'] = False
        if not state['acted']:
            state['current'] = name
            state['acted'] = True
            if action:
                action()
            save()
        elapsed = now - state['entered']
        finished = (until() if until else True) and elapsed >= wait
        if until and not finished and elapsed > timeout:
            log('TIMEOUT at %s' % name)
            finished = True
        if finished:
            state['step'] = i + 1
            if state['step'] >= len(steps):
                state['done'] = True
    except Exception as e:  # noqa: BLE001
        log('ERROR at step %s: %s' % (state.get('current'), e))
        state['step'] += 1
        if state['step'] >= len(steps):
            state['done'] = True


state['t0'] = time.time()
handle = [unreal.register_slate_post_tick_callback(tick)]
save()
'mock driver started with %d steps' % len(steps)
