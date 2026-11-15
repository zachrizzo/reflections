"""Slot 7b PIE check on /Game/MockCity/Lvl_MockCity (after it is open): navmesh path checks for playtest run 3's gaps,
a real-movement climb of the Weigh-House stair (Pewterside) and descent (Giltside), then the Frostside look shots.
Writes frost_results.json; screenshots are taken by the runner when a 'shot' entry appears."""
import json
import os
import time
import unreal

SP = r'C:\Users\zachc\AppData\Local\Temp\claude\79559c54b34378d8\78cc39ce-9d46-4909-af94-0891e5e47ccf\scratchpad'
RESULTS = os.path.join(SP, 'frost_results.json')
OFF = {'Pew': 0.0, 'Gilt': 150000.0, 'Frost': 300000.0}
state = {'log': [], 'shots': [], 'paths': {}, 'walks': {}, 'done': False, 't0': time.time(), 'i': 0}

PATHS = [  # name, side, from (m), to (m)
    ('weighhouse_stair_up', 'Pew', (-99.0, -12.0, 0.5), (-85.5, -1.5, 10.5)),
    ('gilt_roof_down_to_gate', 'Gilt', (-87.5, -1.5, 10.5), (137.0, 35.0, 0.5)),
    ('gate_key_to_tower_door', 'Gilt', (137.5, 34.5, 0.5), (0.0, 61.3, 0.5)),
    ('frost_tower_to_crown', 'Frost', (3.0, 67.0, 0.5), (13.0, 70.0, 24.5)),
]
# Real movement (CharacterMovement, held input steered at waypoints): (name, side, start m, yaw, waypoints m, pass)
WALKS = [
    ('climb_weighhouse_stair', 'Pew', (-96.25, -9.6, 1.1), 90.0, [(-96.25, 4.5), (-88.0, 0.0)],
     lambda p: p.z > 980.0 and p.x > -9450.0),
    ('descend_gilt_weighhouse', 'Gilt', (-90.0, 4.0, 11.1), 180.0, [(-96.25, 4.5), (-96.25, -9.8)],
     lambda p: p.z < 150.0),
]
LEG_TIMEOUT = 12.0
SPOTS = [  # tag, side, x, y, z (m, local), yaw, pitch
    ('m11_frost_bone_market', 'Frost', 55.0, 33.0, 1.0, 10.0, -12.0),
    ('f01_frost_north_street', 'Frost', -30.0, 105.0, 1.0, 0.0, -8.0),
    ('f02_frost_bell_square', 'Frost', -48.0, 2.0, 1.0, 150.0, -12.0),
    ('f03_frost_tower_ramps', 'Frost', -4.9, 65.1, 12.6, 90.0, 22.0),
    ('m10_frost_crown_arena', 'Frost', 8.0, 78.0, 25.2, 250.0, -18.0),
    ('f04_frost_crown_view', 'Frost', 16.0, 70.0, 25.2, 180.0, -6.0),
    ('p01_pew_weighhouse_stair', 'Pew', -101.0, -14.0, 1.0, 60.0, 8.0),
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


def v(side, p):
    return unreal.Vector(OFF[side] + p[0] * 100.0, p[1] * 100.0, p[2] * 100.0)


def run_paths():
    for name, side, a, b in PATHS:
        path = unreal.NavigationSystemV1.find_path_to_location_synchronously(game(), v(side, a), v(side, b))
        pts = list(path.path_points) if path else []
        last = pts[-1] if pts else None
        state['paths'][name] = {'points': len(pts), 'partial': bool(path.is_partial()) if path else None,
                                'length_m': round(path.get_path_length() / 100.0, 1) if path else None,
                                'end_short_m': round((last - v(side, b)).length() / 100.0, 1) if last else None}
        log('path %s %s' % (name, state['paths'][name]))


def phase_list():
    out = [('paths', None)]
    out += [('walk', w) for w in WALKS]
    out += [('spot', s) for s in SPOTS]
    return out


PHASES = phase_list()


def tick(delta):
    try:
        if state['done']:
            unreal.unregister_slate_post_tick_callback(handle[0])
            save()
            return
        if game() is None or pawn() is None:
            return
        now = time.time()
        if state['i'] >= len(PHASES):
            state['done'] = True
            log('done')
            return
        kind, item = PHASES[state['i']]
        fresh = state.get('at') != state['i']
        if fresh:
            state['at'] = state['i']
            state['entered'] = now
            state['asked'] = False
        el = now - state['entered']
        if kind == 'paths':
            if el > 1.5:
                run_paths()
                state['i'] += 1
            return
        if kind == 'walk':
            name, side, start, yaw, legs, test = item
            if fresh:
                pawn().set_actor_location(v(side, start), False, True)
                pc().set_control_rotation(unreal.Rotator(0.0, -10.0, yaw))
                state['walk_max_z'] = -1e9
                return
            if el < 1.0:      # settle a second first
                state['leg'] = 0
                state['leg_t'] = now
                return
            p = pawn().get_actor_location()
            state['walk_max_z'] = max(state['walk_max_z'], p.z)
            if state['leg'] < len(legs):
                tx, ty = legs[state['leg']]
                dx, dy = OFF[side] + tx * 100.0 - p.x, ty * 100.0 - p.y
                dist = (dx * dx + dy * dy) ** 0.5
                if dist < 60.0 or now - state['leg_t'] > LEG_TIMEOUT:
                    if dist >= 60.0:
                        log('walk %s leg %d timed out %.1f m short' % (name, state['leg'], dist / 100.0))
                    state['leg'] += 1
                    state['leg_t'] = now
                    return
                pawn().add_movement_input(unreal.Vector(dx / dist, dy / dist, 0.0), 1.0, False)
                return
            ok = test(unreal.Vector(p.x - OFF[side], p.y, p.z))
            state['walks'][name] = {'pass': bool(ok), 'end_local_m': [round((p.x - OFF[side]) / 100.0, 2), round(p.y / 100.0, 2),
                                                                     round(p.z / 100.0, 2)],
                                    'max_z_m': round(state['walk_max_z'] / 100.0, 2)}
            log('walk %s %s' % (name, state['walks'][name]))
            state['i'] += 1
            return
        tag, s, x, y, z, yaw, pitch = item
        if fresh:
            pawn().set_actor_location(v(s, (x, y, z)), False, True)
            pc().set_control_rotation(unreal.Rotator(0.0, pitch, yaw))
            return
        pc().set_control_rotation(unreal.Rotator(0.0, pitch, yaw))
        if not state['asked'] and el >= SETTLE:
            state['asked'] = True
            state['shots'].append([tag, now])
            log('shot ' + tag)
        if state['asked'] and (os.path.exists(os.path.join(SP, 'cap_%s.done' % tag)) or el > SETTLE + 15.0):
            state['i'] += 1
    except Exception as e:  # noqa: BLE001
        log('ERROR at phase %s: %s' % (state.get('i'), e))
        state['i'] += 1


handle = [unreal.register_slate_post_tick_callback(tick)]
save()
'fix driver started with %d phases' % len(PHASES)
