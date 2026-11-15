"""Heat and crime (Npc.Heat), Giltside's allied soldiers against the tarnished, and the least-worn look first.
Lvl_HeroSampleCrowd open, PIE stopped. One PIE session, about 35 seconds; it always stops PIE. Run through the
editor MCP `execute_python` tool (top-level `await`, `call_tool`).

Npc.Heat is switched on for this run and put back to off afterwards (unless KEEP_HEAT_ON is set).

  H1  A Fire Bolt on a townsperson in front of a guard and a second townsperson: it is a crime ("Assault" in the
      log, with witnesses), heat rises to about a third, and the guard does not attack yet.
  H2  The second bolt kills ("Murder"): heat goes past one half and the guard turns on the player.
  H3  ClearPlayerHeat: heat is zero and the guard stands down.
  A1  An allied soldier and one of the tarnished, a few metres apart with the player further off: the soldier goes
      for the tarnished (recorded: who wins, or whether the soldier is turned).
  K1  Six townspeople spawned with no look given wear as many different looks as the side's pool allows.
Result: Saved/NpcUnified/verify_heat.json and H*/A*/K* pictures.
"""

import base64
import json
import time
from pathlib import Path

OUT = Path(unreal.Paths.project_saved_dir()) / 'NpcUnified'
OUT.mkdir(parents=True, exist_ok=True)
result = {'checks': {}, 'shots': []}
LOG_PATH = Path(unreal.Paths.project_log_dir()) / 'reflections.log'
try:
    log_start = LOG_PATH.stat().st_size
except OSError:
    log_start = 0


def check(name, ok, detail=None):
    result['checks'][name] = {'ok': bool(ok), 'detail': detail}


def unwrap(value):
    return value['returnValue'] if isinstance(value, dict) and 'returnValue' in value else value


def console(command, world=None):
    unreal.SystemLibrary.execute_console_command(world or unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world(), command)


async def shot(name):
    try:
        capture = unwrap(await call_tool('SceneCaptureToolset.SceneCaptureToolset.CaptureGameViewport',
                                         world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(),
                                         maxResolution=1600))
        data = capture['image'] if isinstance(capture, dict) else None
        if isinstance(data, dict):
            data = data.get('data') or data.get('base64')
        if data:
            if ',' in data[:64]:
                data = data.split(',', 1)[1]
            path = OUT / (name + '.png')
            path.write_bytes(base64.b64decode(data))
            result['shots'].append(str(path))
    except Exception as error:
        result.setdefault('shot_errors', []).append(name + ': ' + repr(error))


open_map = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world().get_name()
if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
    result['abort'] = 'PIE is already running (someone else is testing); nothing was started.'
elif open_map != 'Lvl_HeroSampleCrowd':
    result['abort'] = 'The editor has %s open, not Lvl_HeroSampleCrowd. Nothing was started.' % open_map
else:
    console('Squads.StartPatrol 0')
    await call_tool('EditorToolset.EditorAppToolset.StartPIE')
    try:
        await asyncio.sleep(3.0)
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        console('Squads.Clear', world)
        console('Npc.Heat 1', world)
        console('Npc.ElementReactions 0', world)
        player = unreal.GameplayStatics.get_player_pawn(world, 0)
        controller = player.get_controller()
        npcs = unreal.get_world_subsystem(world, unreal.ReflectionsNpcSubsystem)
        spells = player.get_component_by_class(unreal.ReflectionsSpellCombatComponent)

        def brain(actor):
            return actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent)

        def health(actor):
            return round(actor.get_component_by_class(unreal.ReflectionsHealthComponent).get_editor_property('health'), 1)

        def reaction(actor):
            return brain(actor).get_editor_property('reaction').name

        def after_player(actor):
            return reaction(actor) == 'ATTACKING' and brain(actor).get_focus_actor() == player

        def heat():
            return round(npcs.get_player_heat(), 2)

        def aim_point(actor):
            for capsule in actor.get_components_by_class(unreal.CapsuleComponent):
                if capsule.get_name() == 'RuntimeNpcHitProxy':
                    return capsule.get_world_location()
            return actor.get_actor_location() + unreal.Vector(0, 0, 100)

        def cast(spell, actor):
            point = aim_point(actor)
            controller.set_control_rotation(unreal.MathLibrary.find_look_at_rotation(player.get_actor_location(), point))
            origin = unreal.Transform(location=player.get_actor_location() + unreal.Vector(0, 0, 50), rotation=unreal.Rotator(), scale=unreal.Vector(1, 1, 1))
            spells.release_spell_at(spell, origin, point, None)

        def flat_distance(a, b):
            delta = a.get_actor_location() - b.get_actor_location()
            return round(unreal.Vector(delta.x, delta.y, 0).length())

        # ---- H: a crime in front of a guard ---------------------------------------------------------
        player.set_actor_location(unreal.Vector(-700, 350, 90), False, True)
        victim = npcs.spawn_npc('Civilian', unreal.Vector(-700, -50, 0), 90.0, None)
        witness = npcs.spawn_npc('Civilian', unreal.Vector(-1050, -150, 0), 45.0, None)
        guard = npcs.spawn_npc('Guard', unreal.Vector(-330, 150, 0), 135.0, None)
        await asyncio.sleep(1.5)
        result['H0'] = {'heat': heat(), 'guard': reaction(guard), 'victim_health': health(victim)}
        cast(unreal.HeroSpell.FIRE, victim)
        await asyncio.sleep(1.3)
        result['H1'] = {'heat': heat(), 'guard': reaction(guard), 'guard_after_player': after_player(guard), 'victim_health': health(victim),
                        'victim': reaction(victim), 'witness': reaction(witness)}
        check('H1_assault_raises_heat_to_about_a_third', 0.2 <= result['H1']['heat'] <= 0.45, result['H1'])
        check('H1_guard_does_not_attack_yet', not result['H1']['guard_after_player'], result['H1'])
        await shot('H1_after_assault')
        cast(unreal.HeroSpell.FIRE, victim)
        turned_at = None
        began = time.perf_counter()
        peak = 0.0
        killed_by = 'the second bolt'
        for step in range(16):
            await asyncio.sleep(0.25)
            if step == 3 and reaction(victim) != 'INCAPACITATED':
                # It is running by now and an unguided bolt can miss: the player kills it outright instead.
                killed_by = 'direct damage in the player\'s name (the bolt missed)'
                unreal.GameplayStatics.apply_damage(victim, 999.0, controller, player, unreal.DamageType)
            peak = max(peak, heat())
            if after_player(guard) and turned_at is None:
                turned_at = round(time.perf_counter() - began, 2)
                await shot('H2_guard_turns_on_the_player')
        result['H2'] = {'heat_peak': peak, 'heat': heat(), 'victim_health': health(victim), 'victim': reaction(victim), 'killed_by': killed_by,
                        'guard': reaction(guard), 'guard_turned_at_s': turned_at, 'guard_distance': flat_distance(guard, player)}
        check('H2_murder_takes_heat_past_half', peak >= 0.5 and result['H2']['victim'] == 'INCAPACITATED', result['H2'])
        check('H2_guard_turns_on_the_player', turned_at is not None, result['H2'])
        npcs.clear_player_heat()
        await asyncio.sleep(0.8)
        result['H3'] = {'heat': heat(), 'guard': reaction(guard), 'guard_after_player': after_player(guard)}
        check('H3_clearing_the_record_stands_the_guard_down', result['H3']['heat'] == 0.0 and not result['H3']['guard_after_player'], result['H3'])
        for actor in (witness, guard):
            unreal.GameplayStatics.apply_damage(actor, 999.0, None, None, unreal.DamageType)

        # ---- A: an allied soldier against one of the tarnished --------------------------------------
        npcs.clear_player_heat()
        player.set_actor_location(unreal.Vector(1500, 900, 90), False, True)
        ally = npcs.spawn_npc('AlliedSoldier', unreal.Vector(1500, -250, 0), -90.0, None)
        foe = npcs.spawn_npc('Civilian', unreal.Vector(1500, -850, 0), 90.0, None)
        await asyncio.sleep(1.5)
        if ally is None:
            result['A1'] = 'this build has no AlliedSoldier archetype'
            check('A1_allied_soldier_goes_for_the_tarnished', False, result['A1'])
        else:
            controller.set_control_rotation(unreal.MathLibrary.find_look_at_rotation(player.get_actor_location(), ally.get_actor_location() + unreal.Vector(0, 0, 100)))
            result['A0'] = {'class': ally.get_class().get_name(), 'archetype': str(brain(ally).get_active_archetype().get_editor_property('archetype_id')),
                            'tags': [str(t) for t in ally.tags if 'Soldier' in str(t)], 'health': health(ally), 'foe_health': health(foe)}
            npcs.set_infection(foe, unreal.ReflectionsNpcInfection.INFECTED, None)
            went_for_it = None
            pictured = False
            samples = []
            began = time.perf_counter()
            for _ in range(28):
                await asyncio.sleep(0.25)
                focus = brain(ally).get_focus_actor()
                sample = {'t': round(time.perf_counter() - began, 2), 'ally': reaction(ally), 'on_foe': focus == foe, 'on_player': focus == player,
                          'foe': reaction(foe), 'foe_health': health(foe), 'ally_health': health(ally), 'gap': flat_distance(ally, foe),
                          'ally_infection': npcs.get_infection(ally).name}
                samples.append(sample)
                if sample['ally'] == 'ATTACKING' and sample['on_foe'] and went_for_it is None:
                    went_for_it = sample['t']
                if sample['gap'] < 260 and not pictured:
                    pictured = True
                    await shot('A1_ally_fights_the_tarnished')
            result['A1'] = {'went_for_it_at_s': went_for_it, 'first': samples[0], 'last': samples[-1], 'ever_on_player': any(s['on_player'] and s['ally'] == 'ATTACKING' for s in samples),
                            'foe_hurt': samples[-1]['foe_health'] < result['A0']['foe_health'], 'ally_turned': samples[-1]['ally_infection'] != 'NONE'}
            check('A1_allied_soldier_goes_for_the_tarnished', went_for_it is not None, result['A1'])
            check('A1_allied_soldier_leaves_the_player_alone', not result['A1']['ever_on_player'], result['A1'])
            await shot('A1_after')
            for actor in (ally, foe):
                unreal.GameplayStatics.apply_damage(actor, 999.0, None, None, unreal.DamageType)

        # ---- K: the least-worn look first -----------------------------------------------------------
        player.set_actor_location(unreal.Vector(-700, 350, 90), False, True)
        crowd = [npcs.spawn_npc('Civilian', unreal.Vector(-1100 + i * 160, -700, 0), 90.0, None) for i in range(6)]
        await asyncio.sleep(1.2)
        looks = [actor.get_class().get_name() for actor in crowd if actor]
        pool = len(npcs.get_looks_at('Civilian', unreal.Vector(-1100, -700, 0))) if hasattr(npcs, 'get_looks_at') else None
        counts = None
        if hasattr(npcs, 'get_look_use_count'):
            try:
                counts = sorted({actor.get_class().get_name(): npcs.get_look_use_count(actor.get_class()) for actor in crowd if actor}.items())
            except Exception as error:
                counts = repr(error)[:200]
        result['K1'] = {'looks': looks, 'different': len(set(looks)), 'pool': pool, 'side': str(npcs.get_side_at(unreal.Vector(-1100, -700, 0))) if hasattr(npcs, 'get_side_at') else None, 'use_counts': counts}
        check('K1_six_townspeople_wear_different_looks', len(set(looks)) >= min(6, pool or 6), result['K1'])
        controller.set_control_rotation(unreal.MathLibrary.find_look_at_rotation(player.get_actor_location(), unreal.Vector(-700, -700, 100)))
        await asyncio.sleep(0.3)
        await shot('K1_six_townspeople')
    except Exception as error:
        import traceback
        result['error'] = repr(error)
        result['trace'] = traceback.format_exc()[-1500:]
    finally:
        try:
            console('Npc.Heat %d' % (1 if globals().get('KEEP_HEAT_ON', False) else 0))
        except Exception:
            pass
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')
        console('Squads.StartPatrol 1')

try:
    with open(LOG_PATH, 'rb') as handle:
        handle.seek(log_start)
        tail = handle.read().decode('utf-8', errors='replace')
    crimes = [line.split('Crime: ', 1)[1].strip()[:120] for line in tail.splitlines() if 'Crime: ' in line]
    result['log'] = {'crimes': crimes[:12], 'pose_repairs': tail.count('body bone buffers were incomplete'), 'pose_not_ready': tail.count('body pose not ready'),
                     'bone_out_of_range': tail.count('GetBoneMatrix : BoneIndex'), 'ensures': tail.count('Ensure condition failed'),
                     'accessed_none': tail.count('Accessed None')}
    check('H_log_names_an_assault_and_a_murder_with_witnesses', any(c.startswith('Assault') and ', 0 witness' not in c for c in crimes)
          and any(c.startswith('Murder') for c in crimes), crimes[:12])
    check('log_no_empty_pose', result['log']['bone_out_of_range'] == 0 and result['log']['pose_not_ready'] == 0
          and result['log']['pose_repairs'] == 0, result['log'])
except Exception as error:
    result['log'] = repr(error)

result['passed'] = sum(1 for c in result['checks'].values() if c['ok'])
result['failed'] = sorted(name for name, c in result['checks'].items() if not c['ok'])
(OUT / 'verify_heat.json').write_text(json.dumps(result, indent=2, default=str))
json.dumps(result, default=str)
