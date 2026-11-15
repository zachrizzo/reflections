"""Lives consequences check (train #12/#13): deaths ripple, fear of the player, crime witnesses, soldiers, sides.

Run through the editor MCP `execute_python`, one phase per call (each must stay under ~60 s), with Saved/PIE_LOCK.json
taken. Set PHASE ('A'..'D') and optionally MAP (default /Game/GrayLondon/Maps/GrayLondon_Geodata) in the calling namespace, then run
this file with top-level await (see verify_lives.py). State is kept on the unreal module between calls.

  A  Starts PIE (and opens MAP). Sides: every person's body is of their own side (Look_Side_* vs persona side).
  B  A death at the player's hand (OnNpcDied broadcast with the player as killer): a loved one grieves, keeps vigil in
     the evening, thinks badly of the player; with Wren close they keep away (Shun). Picture.
  C  A theft seen by a bystander (ReportPlayerCrime): the witness's events, persona and opinion change.
  D  Brask's men (Giltside soldiers) on patrol / watch in the morning; overlay reset; stops PIE; writes the results.
Results: Saved/Lives/verify_consequences.json and C_*.png pictures.
"""

import base64
import json
import math
from pathlib import Path

MAP = globals().get('MAP', '/Game/GrayLondon/Maps/GrayLondon_Geodata')
OUT = Path(unreal.Paths.project_saved_dir()) / 'Lives'
OUT.mkdir(parents=True, exist_ok=True)
if PHASE == 'A' or not hasattr(unreal, '_lives_cons'):
    unreal._lives_cons = {'checks': {}, 'shots': [], 'notes': {}, 'phases': []}
R = unreal._lives_cons
R['phases'].append(PHASE)
SOLDIERS = ('sela_brask', 'ros_thrale', 'aldric_mayne', 'bram_tolley', 'cosmo_fennick', 'damaris_hobb', 'emeric_dunstan')


def check(name, ok, detail=None):
    R['checks'][name] = {'ok': bool(ok), 'detail': detail}


def unwrap(v):
    return v['returnValue'] if isinstance(v, dict) and 'returnValue' in v else v


def world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


async def shot(name):
    try:
        cap = unwrap(await call_tool('SceneCaptureToolset.SceneCaptureToolset.CaptureGameViewport', world=world(), maxResolution=1600))
        data = cap['image'] if isinstance(cap, dict) else None
        if isinstance(data, dict):
            data = data.get('data') or data.get('base64')
        if data:
            if ',' in data[:64]:
                data = data.split(',', 1)[1]
            (OUT / ('C_' + name + '.png')).write_bytes(base64.b64decode(data))
            R['shots'].append(name)
    except Exception as e:
        R.setdefault('shot_errors', []).append(name + ': ' + repr(e))


def people(lives, npcs):
    out = []
    for a in npcs.get_npc_actors():
        try:
            if a is not None and unreal.SystemLibrary.is_valid(a) and str(lives.get_person_id(a)) not in ('None', ''):
                out.append(a)
        except Exception:
            pass
    return out


def pid(lives, a):
    return str(lives.get_person_id(a))


def look_at(target, back=600.0):
    w = world()
    player = unreal.GameplayStatics.get_player_pawn(w, 0)
    loc = target.get_actor_location()
    here = player.get_actor_location()
    dx, dy = here.x - loc.x, here.y - loc.y
    d = max(1.0, math.hypot(dx, dy))
    spot = unreal.Vector(loc.x + dx / d * back, loc.y + dy / d * back, loc.z + 20.0)
    player.teleport(spot, player.get_actor_rotation())
    player.get_controller().set_control_rotation(unreal.Rotator(0.0, -10.0, math.degrees(math.atan2(loc.y - spot.y, loc.x - spot.x))))


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
            R['abort'] = 'PIE already running; nothing started.'
            return
        await call_tool('EditorToolset.EditorAppToolset.StartPIE')
        await asyncio.sleep(4.0)
        await enter_map(world)
    w = world()
    if w is None:
        R['error'] = 'no PIE world in phase ' + PHASE
        return
    lives = unreal.get_world_subsystem(w, unreal.ReflectionsLivesSubsystem)
    npcs = unreal.get_world_subsystem(w, unreal.ReflectionsNpcSubsystem)
    player = unreal.GameplayStatics.get_player_pawn(w, 0)

    if PHASE == 'A':
        R['map'] = str(w.get_name())
        # npc-unify's crime heat is off until its own check; on for this run only (put back in phase D).
        R['heat_before'] = unreal.SystemLibrary.get_console_variable_int_value('Npc.Heat')
        unreal.SystemLibrary.execute_console_command(w, 'Npc.Heat 1')
        bad = []
        for a in people(lives, npcs):
            body = next((str(t)[10:] for t in a.tags if str(t).startswith('Look_Side_')), '')
            side = str(lives.get_persona_facts(a).side)
            if body and side and body[:4].lower() != side[:4].lower():
                bad.append(f'{lives.get_person_name(lives.get_person_id(a))}: {side} in a {body} look ({a.get_class().get_name()})')
        check('A_sides_never_mixed', not bad, {'people': len(people(lives, npcs)), 'mixed': bad})
        lives.set_time_of_day(18.5)

    elif PHASE == 'B':
        # A victim with someone who loves them, both with bodies.
        ps = people(lives, npcs)
        by_id = {pid(lives, a): a for a in ps}
        victim = mourner = None
        for a in ps:
            facts = lives.get_persona_facts(a)
            for line in facts.people:
                for b in ps:
                    if b is not a and str(lives.get_person_name(lives.get_person_id(b))) in str(line) and '(you can' not in str(line):
                        victim, mourner = b, a
                        break
                if victim:
                    break
            if victim:
                break
        if not victim:
            check('B_death_ripples', False, 'no pair of people who know each other with bodies')
            return
        vid, mid = pid(lives, victim), pid(lives, mourner)
        R['notes']['victim'] = str(lives.get_person_name(vid))
        R['notes']['mourner'] = str(lives.get_person_name(mid))
        before = lives.get_player_memory(mid).opinion
        npcs.on_npc_died.broadcast(victim, player)
        await asyncio.sleep(3.0)
        mood = lives.get_mood(mid)
        after = lives.get_player_memory(mid).opinion
        persona = str(lives.get_persona_text(mourner))
        R['notes']['mourner_persona'] = persona[-600:]
        check('B_death_ripples', mood in (unreal.ReflectionsLifeMood.GRIEVING, unreal.ReflectionsLifeMood.ANGRY) and after < before,
              {'mood': str(mood), 'opinion': [before, after]})
        check('B_persona_mentions_it', 'killed' in persona, persona[-300:])
        await asyncio.sleep(8.0)
        d = str(lives.describe())
        line = next((l for l in d.splitlines() if str(lives.get_person_name(mid)) in l), '')
        check('B_vigil_or_grief', 'vigil' in line.lower() or 'griev' in line.lower() or 'getting away' in line.lower(), line)
        feeling = lives.get_player_feeling(mid)
        R['notes']['feeling'] = feeling
        if feeling > 0 and unreal.SystemLibrary.is_valid(mourner):
            m0 = mourner.get_actor_location()
            look_at(mourner, back=350.0)
            await asyncio.sleep(5.0)
            m1 = mourner.get_actor_location()
            moved = math.hypot(m1.x - m0.x, m1.y - m0.y)
            check('B_keeps_away_from_player', moved > 250.0, {'moved_cm': moved, 'feeling': feeling})
            await shot('B_keeps_away')
        else:
            check('B_keeps_away_from_player', False, {'feeling': feeling, 'note': 'opinion not low enough to shun'})

    elif PHASE == 'C':
        ps = people(lives, npcs)
        pair = None
        for a in ps:
            for b in ps:
                if a is b:
                    continue
                d = a.get_actor_location().distance_to(b.get_actor_location()) if hasattr(a.get_actor_location(), 'distance_to') else \
                    math.dist([a.get_actor_location().x, a.get_actor_location().y], [b.get_actor_location().x, b.get_actor_location().y])
                if 150.0 < d < 700.0 and lives.get_mood(pid(lives, b)) == unreal.ReflectionsLifeMood.CONTENT:
                    pair = (a, b)
                    break
            if pair:
                break
        if not pair:
            check('C_crime_witnessed', False, 'no two people within 7 m')
            return
        victim, witness = pair
        wid = pid(lives, witness)
        before = lives.get_player_memory(wid).opinion
        lives.report_player_crime('Theft', victim, victim.get_actor_location(), witness)
        await asyncio.sleep(1.0)
        mem = lives.get_player_memory(wid)
        persona = str(lives.get_persona_text(witness))
        R['notes']['witness'] = str(lives.get_person_name(wid))
        check('C_crime_witnessed', mem.crimes >= 1 and mem.opinion < before and 'steal' in persona,
              {'crimes': mem.crimes, 'opinion': [before, mem.opinion], 'persona_tail': persona[-300:]})
        look_at(witness, back=600.0)
        lives.set_debug_level(1)
        await asyncio.sleep(1.5)
        await shot('C_crime_witness')
        lives.set_debug_level(0)
        lives.set_time_of_day(9.0)

    elif PHASE == 'D':
        await asyncio.sleep(14.0)
        d = str(lives.describe())
        R['notes']['D_describe'] = d[:4000]
        names = [str(lives.get_person_name(s)) for s in SOLDIERS]
        lines = [l for l in d.splitlines() if any(n and n in l for n in names)]
        on_duty = [l for l in lines if 'patrol' in l.lower() or 'watch' in l.lower()]
        check('D_soldiers_on_duty', len(on_duty) >= 1, {'soldier_lines': lines[:10]})
        lives.set_debug_level(0)
        unreal.SystemLibrary.execute_console_command(w, 'Lives.Debug 0')
        unreal.SystemLibrary.execute_console_command(w, 'Npc.Heat %d' % int(R.get('heat_before', 0)))


try:
    await run()
except Exception as e:
    R['error'] = PHASE + ': ' + repr(e)
if PHASE == 'D' or R.get('error') or R.get('abort'):
    if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')) and not R.get('abort'):
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')
(OUT / 'verify_consequences.json').write_text(json.dumps(R, indent=2, default=str))
passed = sum(1 for c in R['checks'].values() if c['ok'])
summary = json.dumps({'phase': PHASE, 'passed': f"{passed}/{len(R['checks'])}", 'checks': {k: v['ok'] for k, v in R['checks'].items()},
                      'error': R.get('error'), 'abort': R.get('abort'), 'notes': {k: v for k, v in R['notes'].items() if k != 'D_describe' and k != 'mourner_persona'}}, default=str)
