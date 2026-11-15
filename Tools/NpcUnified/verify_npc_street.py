"""Train #14, the bustling-streets pieces: street scenes on the hidden walker, the panic ripple, fleeing to where the
street lets go. Run inside the editor (the project's Python MCP: top-level await, `call_tool`), in halves:
PART = 'A' (scenes, about 35 s of PIE) or 'B' (ripple and fleeing, about 40 s). Always stops PIE.

Before: the city map open, PIE stopped, the PIE lock held by the caller.

PART A, one civilian 3.5 m ahead of the hero at the 'Lanthorne' start:
  A1  BeginNpcScene with a standing loop: true, IsNpcInScene, a montage plays on the walker, and for two seconds the
      NPC stays where it is (no roaming).
  A2  PlayNpcSceneClip (an idle break) plays over the loop and the scene is still on afterwards with a montage playing.
  A3  The same scene pinned: the walker's movement mode is None. EndNpcScene: not in a scene, walking again.
  A4  Disturbed by a noise 2 m away while pinned: out of the scene, moving again and no longer calm within 0.4 s.
  A5  A second civilian in a scene is hit by a Fire Bolt: out of the scene at once.
  A6  A third, pinned, is killed: out of the scene, incapacitated.
  A7  One that is frightened is refused (BeginNpcScene false).
PART B:
  B1  Three civilians 3 m, 8 m and 13 m from a noise: the near one stops being calm at once, the far ones later
      (measured 03:44 on train #18: 0, 0.68 and 0.70 s). With Npc.PanicRipple 0 they all react within a tenth of a second.
  B2  A frightened civilian runs: further than the old 7 m, and it is not standing against a wall at the end.
  B3  GetSecondsSinceViolence is small here and very large 2 km away.
Result: Saved/NpcUnified/verify_street_<PART>.json. Console variables are put back afterwards.
"""

import json
import time
from pathlib import Path

OUT = Path(unreal.Paths.project_saved_dir()) / 'NpcUnified'
OUT.mkdir(parents=True, exist_ok=True)
PART = globals().get('PART', 'A')
result = {'part': PART, 'checks': {}}
LOG_PATH = Path(unreal.Paths.project_log_dir()) / 'reflections.log'
try:
    log_start = LOG_PATH.stat().st_size
except OSError:
    log_start = 0

IDLE = '/Game/Characters/UEFN_Mannequin/Animations/Idle/'


def check(name, ok, detail=None):
    result['checks'][name] = {'ok': bool(ok), 'detail': detail}


def unwrap(value):
    return value['returnValue'] if isinstance(value, dict) and 'returnValue' in value else value


def console(command, world=None):
    unreal.SystemLibrary.execute_console_command(world or unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world(), command)


if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
    result['abort'] = 'PIE is already running (someone else is testing); nothing was started.'
else:
    console('Squads.StartPatrol 0')
    await call_tool('EditorToolset.EditorAppToolset.StartPIE')
    try:
        world = None
        player = None
        for _ in range(40):
            await asyncio.sleep(0.5)
            world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
            player = unreal.GameplayStatics.get_player_pawn(world, 0) if world else None
            if player and abs(player.get_velocity().z) < 5.0:
                break
        await asyncio.sleep(1.0)
        console('Squads.Clear', world)
        console('Crowd.Ring.Enable 0', world)
        controller = player.get_controller()
        # Team rule (21:27): go to the start tagged 'Lanthorne' first and give the streamed city a few seconds.
        starts = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.PlayerStart)
                  if str(a.get_editor_property('player_start_tag')) == 'Lanthorne']
        result['lanthorne_start'] = bool(starts)
        if starts:
            player.set_actor_location(starts[0].get_actor_location(), False, True)
            player.set_actor_rotation(unreal.Rotator(0.0, 0.0, starts[0].get_actor_rotation().yaw), False)
            controller.set_control_rotation(starts[0].get_actor_rotation())
            await asyncio.sleep(4.0)
            for _ in range(20):
                if abs(player.get_velocity().z) < 5.0:
                    break
                await asyncio.sleep(0.3)
        npcs = unreal.get_world_subsystem(world, unreal.ReflectionsNpcSubsystem)
        spells = player.get_component_by_class(unreal.ReflectionsSpellCombatComponent)
        HERE = player.get_actor_location()
        GROUND = HERE.z - 90.0
        ahead = player.get_actor_forward_vector()
        ahead = unreal.Vector(ahead.x, ahead.y, 0.0).normal()
        side = unreal.Vector(-ahead.y, ahead.x, 0.0)

        def at(forward_cm, right_cm=0.0, up_cm=0.0):
            return unreal.Vector(HERE.x + ahead.x * forward_cm + side.x * right_cm, HERE.y + ahead.y * forward_cm + side.y * right_cm, GROUND + up_cm)

        def brain(actor):
            return actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent)

        def walker(actor):
            return brain(actor).get_locomotion_driver()

        def reaction(actor):
            return brain(actor).get_editor_property('reaction').name

        def place(actor):
            where = (walker(actor) or actor).get_actor_location()
            return unreal.Vector(where.x, where.y, 0.0)

        def moved(actor, start):
            return round((place(actor) - start).length())

        def mode(actor):
            return walker(actor).get_component_by_class(unreal.CharacterMovementComponent).get_editor_property('movement_mode').name

        def montage(actor):
            anim = walker(actor).get_editor_property('mesh').get_anim_instance()
            return bool(anim and anim.is_any_montage_playing())

        def noise(point, kind=unreal.ReflectionsNpcStimulusKind.SPELL_NOISE, radius=2000.0):
            stimulus = unreal.ReflectionsNpcStimulus()
            stimulus.set_editor_property('kind', kind)
            stimulus.set_editor_property('location', point)
            stimulus.set_editor_property('intensity', 20.0)
            stimulus.set_editor_property('radius', radius)
            stimulus.set_editor_property('instigator', player)
            npcs.report_stimulus(stimulus)

        async def spawn(forward, right=0.0, wait=1.4):
            actor = npcs.spawn_npc('Civilian', at(forward, right), unreal.MathLibrary.find_look_at_rotation(at(forward, right), at(0)).yaw, None)
            await asyncio.sleep(wait)
            return actor

        def kill(actor):
            if actor:
                unreal.GameplayStatics.apply_damage(actor, 999.0, None, None, unreal.DamageType)

        loop = unreal.load_asset(IDLE + 'M_Relaxed_Stand_Idle_Loop')
        idle_break = unreal.load_asset(IDLE + 'M_Relaxed_Stand_Idle_Break_v01')
        result['clips'] = {'loop': bool(loop), 'break': bool(idle_break)}
        for other in npcs.get_npc_actors():
            npcs.hold_npc(other, 90.0)

        if 'A' in PART:
            # ---- A1: a scene holds a calm NPC with its loop --------------------------------------------------
            first = await spawn(350)
            start = place(first)
            began = npcs.begin_npc_scene(first, loop, False, 0.25)
            await asyncio.sleep(0.4)
            playing = montage(first)
            await asyncio.sleep(2.0)
            result['A1'] = {'began': began, 'in_scene': npcs.is_npc_in_scene(first), 'montage': playing, 'moved_cm': moved(first, start), 'reaction': reaction(first)}
            check('A1_scene_begins_and_holds', began and result['A1']['in_scene'] and playing and result['A1']['moved_cm'] < 40, result['A1'])

            # ---- A2: a one-off clip over the loop, then the loop again ---------------------------------------
            played = npcs.play_npc_scene_clip(first, idle_break, 0.2, 0.2, False)
            await asyncio.sleep(min(idle_break.get_play_length() if idle_break else 1.0, 5.0) + 0.5)
            result['A2'] = {'played': played, 'in_scene': npcs.is_npc_in_scene(first), 'montage_after': montage(first)}
            check('A2_one_off_clip_then_the_loop_again', played and result['A2']['in_scene'] and result['A2']['montage_after'], result['A2'])

            # ---- A3: pinned, then released --------------------------------------------------------------------
            pinned = npcs.begin_npc_scene(first, loop, True, 0.25)
            await asyncio.sleep(0.3)
            pinned_mode = mode(first)
            npcs.end_npc_scene(first, 0.25)
            await asyncio.sleep(0.5)
            result['A3'] = {'pinned': pinned, 'mode_pinned': pinned_mode, 'mode_after': mode(first), 'in_scene_after': npcs.is_npc_in_scene(first), 'montage_after': montage(first)}
            check('A3_pinned_then_released', pinned and 'NONE' in pinned_mode and 'WALKING' in result['A3']['mode_after']
                  and not result['A3']['in_scene_after'] and not result['A3']['montage_after'], result['A3'])

            # ---- A4: a noise ends a pinned scene --------------------------------------------------------------
            npcs.begin_npc_scene(first, loop, True, 0.25)
            await asyncio.sleep(0.4)
            start = place(first)
            noise(unreal.Vector(start.x + ahead.x * -200.0, start.y + ahead.y * -200.0, GROUND + 90.0))
            await asyncio.sleep(0.4)
            soon = {'in_scene': npcs.is_npc_in_scene(first), 'mode': mode(first), 'reaction': reaction(first)}
            await asyncio.sleep(2.2)
            result['A4'] = {'after_0.4s': soon, 'moved_cm_after_2.6s': moved(first, start), 'reaction': reaction(first)}
            check('A4_a_noise_ends_the_scene_and_it_can_run', not soon['in_scene'] and 'WALKING' in soon['mode'] and soon['reaction'] != 'CALM', result['A4'])
            kill(first)

            # ---- A5: a hit ends a scene -----------------------------------------------------------------------
            second = await spawn(350, 150)
            # (The first run's civilian was frightened by the death just before it and was refused: wait for calm.)
            for _ in range(20):
                if reaction(second) == 'CALM':
                    break
                await asyncio.sleep(0.5)
            began_second = npcs.begin_npc_scene(second, loop, False, 0.25)
            await asyncio.sleep(0.4)
            aim = brain(second).get_aim_point()
            controller.set_control_rotation(unreal.MathLibrary.find_look_at_rotation(player.get_actor_location(), aim))
            origin = unreal.Transform(location=player.get_actor_location() + unreal.Vector(0, 0, 50), rotation=unreal.Rotator(), scale=unreal.Vector(1, 1, 1))
            in_before = npcs.is_npc_in_scene(second)
            spells.release_spell_at(unreal.HeroSpell.FIRE, origin, aim, None)
            await asyncio.sleep(1.0)
            result['A5'] = {'began': began_second, 'in_scene_before': in_before, 'in_scene_after': npcs.is_npc_in_scene(second), 'reaction': reaction(second)}
            check('A5_a_hit_ends_the_scene', in_before and not result['A5']['in_scene_after'] and result['A5']['reaction'] != 'CALM', result['A5'])
            kill(second)

            # ---- A6: killed in a pinned scene -----------------------------------------------------------------
            third = await spawn(350, -150)
            pinned = npcs.begin_npc_scene(third, loop, True, 0.25)
            await asyncio.sleep(0.4)
            kill(third)
            await asyncio.sleep(0.5)
            result['A6'] = {'pinned': pinned, 'in_scene_after': npcs.is_npc_in_scene(third), 'reaction': reaction(third)}
            check('A6_death_ends_the_scene', pinned and not result['A6']['in_scene_after'] and result['A6']['reaction'] == 'INCAPACITATED', result['A6'])

            # ---- A7: the frightened are refused ---------------------------------------------------------------
            fourth = await spawn(350, 300)
            noise(place(fourth) + unreal.Vector(0, 0, GROUND + 90.0), unreal.ReflectionsNpcStimulusKind.DEATH)
            await asyncio.sleep(0.3)
            result['A7'] = {'reaction': reaction(fourth), 'began': npcs.begin_npc_scene(fourth, loop, False, 0.25)}
            check('A7_not_calm_is_refused', result['A7']['reaction'] != 'CALM' and not result['A7']['began'], result['A7'])
            kill(fourth)

        if 'B' in PART:
            # ---- B1: the ripple ---------------------------------------------------------------------------------
            async def ripple(per_ring):
                console('Npc.PanicRipple %s' % per_ring, world)
                people = [await spawn(300, 0, 0.5), await spawn(800, 80, 0.5), await spawn(1300, -80, 1.4)]
                for person in people:
                    brain(person).set_externally_steered(True)      # they stand where they were put
                await asyncio.sleep(0.3)
                noise(unreal.Vector(HERE.x, HERE.y, GROUND + 90.0))
                began = time.perf_counter()
                first_seen = [None, None, None]
                while time.perf_counter() - began < 1.5 and None in first_seen:
                    await asyncio.sleep(0.0)
                    for index, person in enumerate(people):
                        if first_seen[index] is None and reaction(person) != 'CALM':
                            first_seen[index] = round(time.perf_counter() - began, 2)
                distances = [round((place(p) - unreal.Vector(HERE.x, HERE.y, 0.0)).length()) for p in people]
                for person in people:
                    kill(person)
                await asyncio.sleep(0.4)
                return {'distance_cm': distances, 'left_calm_after_s': first_seen}

            result['B1_ripple'] = await ripple(0.2)
            result['B1_at_once'] = await ripple(0)
            console('Npc.PanicRipple 0.2', world)
            t = result['B1_ripple']['left_calm_after_s']
            flat = result['B1_at_once']['left_calm_after_s']
            # (NPC brains far from the player tick slowly, so the delay comes out longer than the nominal 0.2 s per ring,
            # and two NPCs in the same 5 m ring react together.)
            check('B1_alarm_spreads_outward', None not in t and t[1] - t[0] >= 0.1 and t[2] >= t[1] and max(t) <= 1.3, result['B1_ripple'])
            check('B1_ripple_off_is_all_at_once', None not in flat and max(flat) - min(flat) < 0.12, result['B1_at_once'])

            # ---- B2: running for the way out ----------------------------------------------------------------------
            runner = await spawn(300)
            start = place(runner)
            noise(unreal.Vector(HERE.x, HERE.y, GROUND + 90.0), unreal.ReflectionsNpcStimulusKind.DEATH)
            track = []
            began = time.perf_counter()
            while time.perf_counter() - began < 6.0:
                await asyncio.sleep(0.5)
                track.append([round(time.perf_counter() - began, 1), moved(runner, start), reaction(runner), round(walker(runner).get_velocity().length())])
            result['B2'] = {'track': track, 'ran_cm': track[-1][1], 'slow_samples_while_fleeing': sum(1 for s in track[2:] if s[2] == 'FLEEING' and s[3] < 40)}
            check('B2_runs_further_than_seven_metres', result['B2']['ran_cm'] > 850 and result['B2']['slow_samples_while_fleeing'] <= 2, result['B2'])
            kill(runner)

            # ---- B3: how long since anything happened here --------------------------------------------------------
            near = npcs.get_seconds_since_violence(HERE, 6000.0)
            far = npcs.get_seconds_since_violence(unreal.Vector(HERE.x + 200000.0, HERE.y, HERE.z), 1000.0)
            result['B3'] = {'here_s': round(near, 1), 'two_km_away_s': round(far)}
            check('B3_seconds_since_violence', near < 10.0 and far > 1000.0, result['B3'])
    except Exception as error:
        import traceback
        result['error'] = repr(error)
        result['trace'] = traceback.format_exc()[-1500:]
    finally:
        try:
            console('Npc.PanicRipple 0.2')
            console('Crowd.Ring.Enable 1')
        except Exception:
            pass
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')
        console('Squads.StartPatrol 1')

try:
    with open(LOG_PATH, 'rb') as handle:
        handle.seek(log_start)
        tail = handle.read().decode('utf-8', errors='replace')
    result['log'] = {'pose_repairs': tail.count('body bone buffers were incomplete'), 'pose_not_ready': tail.count('body pose not ready'),
                     'bone_out_of_range': tail.count('GetBoneMatrix : BoneIndex'), 'ensures': tail.count('Ensure condition failed'),
                     'accessed_none': tail.count('Accessed None')}
    check('log_clean', result['log']['bone_out_of_range'] == 0 and result['log']['pose_not_ready'] == 0 and result['log']['ensures'] == 0, result['log'])
except Exception as error:
    result['log'] = repr(error)

result['passed'] = sum(1 for c in result['checks'].values() if c['ok'])
result['failed'] = sorted(name for name, c in result['checks'].items() if not c['ok'])
(OUT / ('verify_street_%s.json' % PART)).write_text(json.dumps(result, indent=2, default=str))
json.dumps({'part': PART, 'passed': result['passed'], 'failed': result['failed'], 'error': result.get('error'), 'abort': result.get('abort')})
