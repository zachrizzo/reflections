"""Lives check on the main map (GrayLondon_Geodata): identities, a compressed day, friends meeting, a witness
reacting to a friend being taken, and the debug overlay.

Run through the editor MCP `execute_python` tool, one phase per call (each call must stay under the tool's ~60 s
limit), with Saved/PIE_LOCK.json taken:  PHASE = 'A' (starts PIE), 'B', 'C', 'D', 'E' (stops PIE and writes results).
Set PHASE in the calling script, then run this file's text with top-level await. State is kept between calls on the
unreal module.

  A  Every townsperson actor has a person (named people first); names unique; persona text has no secrets.
  B  Changing the hour moves people: at noon they leave for their places.
  C  In the evening friends seek each other out and chat (a pair with chat=...).
  D  Lives.TestWitness: someone sees a friend taken by the Tarnish, their mood turns, and the event is in their persona.
  E  Night: people go home and inside. Debug overlay level 2 picture.
Results: Saved/Lives/verify_lives.json and A_..E_ pictures there.
"""

import base64
import json
import math
from pathlib import Path

MAP = globals().get('MAP', '/Game/GrayLondon/Maps/GrayLondon_Geodata')   # PIE travels there in phase A unless already on it
PREFIX = globals().get('PREFIX', '')      # picture name prefix, e.g. 'Mock_'
OUT = Path(unreal.Paths.project_saved_dir()) / 'Lives'
OUT.mkdir(parents=True, exist_ok=True)
if PHASE == 'A' or not hasattr(unreal, '_lives_verify'):
    unreal._lives_verify = {'checks': {}, 'shots': [], 'describe': {}, 'phases': []}
result = unreal._lives_verify
result['phases'].append(PHASE)


def check(name, ok, detail=None):
    result['checks'][name] = {'ok': bool(ok), 'detail': detail}


def unwrap(value):
    return value['returnValue'] if isinstance(value, dict) and 'returnValue' in value else value


def game_world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


async def shot(name):
    try:
        capture = unwrap(await call_tool('SceneCaptureToolset.SceneCaptureToolset.CaptureGameViewport',
                                         world=game_world(), maxResolution=1600))
        data = capture['image'] if isinstance(capture, dict) else None
        if isinstance(data, dict):
            data = data.get('data') or data.get('base64')
        if data:
            if ',' in data[:64]:
                data = data.split(',', 1)[1]
            path = OUT / (PREFIX + name + '.png')
            path.write_bytes(base64.b64decode(data))
            result['shots'].append(str(path))
    except Exception as error:
        result.setdefault('shot_errors', []).append(name + ': ' + repr(error))


def look_at(target, back=650.0):
    """Puts the hero a few metres from target, looking at it, so the overlay is in the picture."""
    world = game_world()
    player = unreal.GameplayStatics.get_player_pawn(world, 0)
    controller = player.get_controller()
    loc = target.get_actor_location()
    here = player.get_actor_location()
    dx, dy = here.x - loc.x, here.y - loc.y
    d = max(1.0, math.hypot(dx, dy))
    spot = unreal.Vector(loc.x + dx / d * back, loc.y + dy / d * back, loc.z + 20.0)
    player.teleport(spot, player.get_actor_rotation())
    yaw = math.degrees(math.atan2(loc.y - spot.y, loc.x - spot.x))
    controller.set_control_rotation(unreal.Rotator(0.0, -12.0, yaw))


def people(lives, npcs):
    out = []
    for a in npcs.get_npc_actors():
        try:
            if a is not None and unreal.SystemLibrary.is_valid(a) and str(lives.get_person_id(a)) not in ('None', ''):
                out.append(a)
        except Exception:
            pass
    return out


def name_of(lives, a):
    return str(lives.get_person_name(lives.get_person_id(a)))


def lines(text):
    return [l for l in text.splitlines()[1:] if l.strip()]


async def enter_map(get_world, wait_people=30.0):
    """PIE is on MAP after this: travels only when the PIE world isn't it already (World Partition map, slow to reload),
    then waits until the townspeople exist (or wait_people seconds)."""
    w = get_world()
    short = MAP.rsplit('/', 1)[-1].split('.')[0]
    if MAP and (w is None or short not in str(w.get_name())):
        unreal.SystemLibrary.execute_console_command(w, 'open ' + MAP)
        await asyncio.sleep(10.0)
    waited = 0.0
    while waited < wait_people:
        w = get_world()
        try:
            if w is not None and len(unreal.get_world_subsystem(w, unreal.ReflectionsNpcSubsystem).get_npc_actors()) >= 8:
                break
        except Exception:
            pass
        await asyncio.sleep(2.0)
        waited += 2.0
    await asyncio.sleep(3.0)   # let Lives cast the bodies


async def run():
    if PHASE == 'A':
        if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
            result['abort'] = 'PIE is already running (someone else is testing); nothing was started.'
            return
        await call_tool('EditorToolset.EditorAppToolset.StartPIE')
        await asyncio.sleep(4.0)
        await enter_map(game_world)
    world = game_world()
    if world is None:
        result['error'] = 'no PIE world in phase ' + PHASE
        return
    lives = unreal.get_world_subsystem(world, unreal.ReflectionsLivesSubsystem)
    npcs = unreal.get_world_subsystem(world, unreal.ReflectionsNpcSubsystem)

    if PHASE == 'A':
        lives.set_debug_level(1)
        lives.set_time_of_day(8.0)
        await asyncio.sleep(3.0)
        result['describe']['A_morning'] = lives.describe()
        actors = []
        for a in npcs.get_npc_actors():
            if a is None or not unreal.SystemLibrary.is_valid(a) or a.actor_has_tag('NPC_Soldier'):
                continue
            brain = npcs.find_npc(a)
            disp = str(brain.get_editor_property('disposition')) if brain else ''
            if any(k in disp.upper() for k in ('ENEMY', 'INFECTED', 'VILLAIN')):
                continue  # soldiers, enemies and the tarnished get no life
            actors.append(a)
        result['map'] = str(world.get_name()) if world else ''
        with_person = people(lives, npcs)
        names = [name_of(lives, a) for a in with_person]
        personas = {name_of(lives, a): str(lives.get_persona_text(a)) for a in with_person[:3]}
        result['personas'] = personas
        person_actor_names = {a.get_name() for a in with_person}
        missing = [a.get_name() for a in actors if a.get_name() not in person_actor_names]
        check('A_every_npc_has_a_person', len(actors) > 0 and not missing,
              {'townsfolk': len(actors), 'with_person': len(with_person), 'missing': missing, 'names': names})
        check('A_names_unique', len(set(names)) == len(names), names)
        secrets = {}
        for book in (Path(unreal.Paths.project_dir()) / 'ArtDirection' / 'Story' / 'people.json',
                     Path(unreal.Paths.project_dir()) / 'ArtDirection' / 'Lives' / 'people_stub.json'):
            if book.exists():
                for person in json.loads(book.read_text(encoding='utf-8')).get('people', []):
                    if person.get('secret'):
                        secrets[person.get('name')] = person['secret']
                break
        leaks = [n for n, p in personas.items() if n in secrets and secrets[n][:40] in p]
        check('A_persona_whitelisted', all(personas.values()) and not leaks, {'checked': list(personas.keys()), 'leaks': leaks})
        if with_person:
            look_at(with_person[0])
        await asyncio.sleep(1.0)
        await shot('A_morning_identities')
        result['before'] = {name_of(lives, a): [a.get_actor_location().x, a.get_actor_location().y] for a in people(lives, npcs)}
        lives.set_time_of_day(12.0)

    elif PHASE == 'B':
        await asyncio.sleep(12.0)
        moved = 0
        with_person = people(lives, npcs)
        for a in with_person:
            p0 = result.get('before', {}).get(name_of(lives, a))
            if p0 and math.hypot(a.get_actor_location().x - p0[0], a.get_actor_location().y - p0[1]) > 250.0:
                moved += 1
        result['describe']['B_noon'] = lives.describe()
        check('B_schedule_moves_people', moved >= max(1, len(with_person) // 2), {'moved': moved, 'of': len(with_person)})
        if with_person:
            look_at(with_person[min(1, len(with_person) - 1)], back=900.0)
        await asyncio.sleep(1.0)
        await shot('B_noon_on_the_way')
        lives.set_time_of_day(18.2)

    elif PHASE == 'C':
        chat_lines = []
        for _ in range(10):
            await asyncio.sleep(4.0)
            chat_lines = [l for l in lines(lives.describe()) if 'chat=' in l]
            if chat_lines:
                break
        result['describe']['C_evening'] = lives.describe()
        check('C_friends_meet_and_chat', len(chat_lines) > 0, chat_lines)
        if chat_lines:
            for a in people(lives, npcs):
                if a.get_name() in chat_lines[0]:
                    look_at(a, back=500.0)
                    break
        await asyncio.sleep(2.0)
        await shot('C_evening_friends_chatting')

    elif PHASE == 'D':
        witness_text = str(lives.test_witness(''))
        await asyncio.sleep(1.5)
        result['witness'] = witness_text
        witness_name = witness_text.split(' (')[0] if witness_text else ''
        witness_actor = None
        for a in people(lives, npcs):
            if name_of(lives, a) == witness_name:
                witness_actor = a
        if witness_actor:
            mood = lives.get_mood(lives.get_person_id(witness_actor))
            persona = str(lives.get_persona_text(witness_actor))
            result['witness_persona'] = persona
            check('D_witness_reacts', mood in (unreal.ReflectionsLifeMood.GRIEVING, unreal.ReflectionsLifeMood.ANGRY,
                                               unreal.ReflectionsLifeMood.AFRAID), str(mood))
            check('D_witness_remembers', 'taken by the Tarnish' in persona, persona[-400:])
            look_at(witness_actor, back=550.0)
        else:
            check('D_witness_reacts', False, witness_text or 'no witness pair near each other')
        await asyncio.sleep(1.0)
        await shot('D_witness_saw_friend_taken')
        await asyncio.sleep(6.0)
        result['describe']['D_after'] = lives.describe()
        await shot('D_witness_moves_away')
        lives.set_time_of_day(21.8)

    elif PHASE == 'E':
        await asyncio.sleep(18.0)
        d = lives.describe()
        result['describe']['E_night'] = d
        with_person = people(lives, npcs)
        home = [l for l in lines(d) if ('Home' in l or 'Sleeping' in l or 'Grieving' in l or 'Hiding' in l)]
        check('E_people_go_home', len(home) >= max(1, len(with_person) // 2), {'home': len(home), 'of': len(with_person)})
        await shot('E_night_going_home')
        lives.set_debug_level(2)
        await asyncio.sleep(1.0)
        await shot('E_debug_level_2')
        # The overlay is a playtest tool: never leave it on for the next person's Play.
        lives.set_debug_level(0)
        unreal.SystemLibrary.execute_console_command(world, 'Lives.Debug 0')


try:
    await run()
except Exception as error:
    result['error'] = PHASE + ': ' + repr(error)
if PHASE == 'E' or result.get('error') or result.get('abort'):
    if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')) and not result.get('abort'):
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')
(OUT / (PREFIX + 'verify_lives.json')).write_text(json.dumps(result, indent=2, default=str))
passed = sum(1 for c in result['checks'].values() if c['ok'])
summary = json.dumps({'phase': PHASE, 'passed': f"{passed}/{len(result['checks'])}",
                      'checks': {k: v['ok'] for k, v in result['checks'].items()}, 'error': result.get('error'),
                      'abort': result.get('abort'), 'witness': result.get('witness')}, default=str)
