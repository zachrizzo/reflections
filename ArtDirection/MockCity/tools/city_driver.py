"""City-kit look check in PIE (after /Game/MockCity/Lvl_MockCity is open): teleports the hero to the old m-shot spots
plus two Frostside streets and asks for a screenshot at each. Writes city_results.json. No world jumps, no pickups."""
import json
import os
import time
import unreal

SP = r'C:\Users\zachc\AppData\Local\Temp\claude\79559c54b34378d8\78cc39ce-9d46-4909-af94-0891e5e47ccf\scratchpad'
RESULTS = os.path.join(SP, 'city_results.json')
OFF = {'Pew': 0.0, 'Gilt': 150000.0, 'Frost': 300000.0}
state = {'step': 0, 'log': [], 'shots': [], 'done': False, 't0': time.time()}

SPOTS = [  # tag, side, x, y, z (m, local), yaw, pitch
    ('m01_gilt_start', 'Gilt', -38.0, 11.0, 1.0, 57.0, -12.0),
    ('m02_gilt_lantern_row', 'Gilt', 58.0, 33.0, 1.0, 0.0, -12.0),
    ('m03_gilt_bell_square', 'Gilt', -48.0, 2.0, 1.0, 150.0, -12.0),
    ('m07_gilt_lantern_gate', 'Gilt', 139.5, 37.0, 1.6, 200.0, -12.0),
    ('m04_pew_weighhouse_corner', 'Pew', -77.0, 10.0, 1.0, 225.0, -12.0),
    ('m05_pew_weighhouse_stair', 'Pew', -97.0, -10.5, 1.0, 90.0, -12.0),
    ('m12_pew_coal_lane', 'Pew', 40.0, -58.0, 1.0, 10.0, -12.0),
    ('m11_frost_bone_market', 'Frost', 55.0, 33.0, 1.0, 10.0, -12.0),
    ('f01_frost_north_street', 'Frost', -30.0, 105.0, 1.0, 0.0, -8.0),
    ('f02_frost_bell_square', 'Frost', -48.0, 2.0, 1.0, 150.0, -12.0),
    ('m10_frost_crown_arena', 'Frost', 8.0, 78.0, 25.2, 250.0, -18.0),
]
SETTLE = 2.6


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


def captured(tag):
    return os.path.exists(os.path.join(SP, 'cap_%s.done' % tag))


def tick(delta):
    try:
        if state['done']:
            unreal.unregister_slate_post_tick_callback(handle[0])
            save()
            return
        if game() is None or pawn() is None:
            return
        if 'ramp_path' not in state:
            # Frost Tower: a navmesh path from the floor inside to the crown arena (the ramps must carry it).
            a = unreal.Vector(OFF['Frost'] + 300.0, 7000.0 - 300.0, 50.0)
            b = unreal.Vector(OFF['Frost'] + 1300.0, 7000.0, 2450.0)
            p = unreal.NavigationSystemV1.find_path_to_location_synchronously(game(), a, b)
            pts = list(p.path_points) if p else []
            state['ramp_path'] = {'points': len(pts), 'partial': bool(p.is_partial()) if p else None,
                                  'max_z': round(max([q.z for q in pts]) if pts else 0),
                                  'length_m': round(p.get_path_length() / 100.0, 1) if p else None}
            log('ramp path %s' % state['ramp_path'])
        now = time.time()
        i = state['step']
        if i >= len(SPOTS):
            state['done'] = True
            log('done')
            return
        tag, s, x, y, z, yaw, pitch = SPOTS[i]
        if state.get('at') != i:
            state['at'] = i
            state['entered'] = now
            state['asked'] = False
            pawn().set_actor_location(unreal.Vector(OFF[s] + x * 100.0, y * 100.0, z * 100.0), False, True)
            pc().set_control_rotation(unreal.Rotator(0.0, pitch, yaw))
            log('at %s' % tag)
            return
        pc().set_control_rotation(unreal.Rotator(0.0, pitch, yaw))
        if not state['asked'] and now - state['entered'] >= SETTLE:
            state['asked'] = True
            state['shots'].append([tag, now])
            log('shot ' + tag)
        if state['asked'] and (captured(tag) or now - state['entered'] > SETTLE + 15.0):
            state['step'] = i + 1
    except Exception as e:  # noqa: BLE001
        log('ERROR at step %s: %s' % (state.get('step'), e))
        state['step'] += 1


handle = [unreal.register_slate_post_tick_callback(tick)]
save()
'city driver started with %d spots' % len(SPOTS)
