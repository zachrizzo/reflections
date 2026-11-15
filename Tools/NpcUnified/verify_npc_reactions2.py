"""The three spell reactions the first run could not judge because its unguided spells missed targets that had
wandered off (verify_npc_reactions.py R4, R6, R7). Same rules: Lvl_HeroSampleCrowd open, PIE stopped, one PIE
session of about 25 seconds, always stops PIE, Npc.ElementReactions on for the run only.

Targets stand 2.6 m from the player and are struck within a second of settling, so a walking pace cannot carry them
out of the spell's path.
  P1  Water Orb on a soldier (does not roam): shoved away; alive; the body never simulates.
  P2  Fire Bolt on a townsperson: hurt but alive (20 -> 6), and it runs. A second bolt is not tried here (the heat
      check kills a townsperson with two bolts).
  P3  Lightning Bolt on a townsperson: dead at once in the ragdoll, and the body twitches for a moment.
Result: Saved/NpcUnified/verify_reactions2.json and P*_ pictures.
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


# retargeted: positions are relative to where the hero stands when PIE starts (see retarget_checks.py)
_frame = {}


def W(x, y, z=0.0):
    """A position of the old test level, as the same offset from where the hero stood when PIE started."""
    if not _frame:
        game = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        hero = unreal.GameplayStatics.get_player_pawn(game, 0)
        here = hero.get_actor_location()
        ahead = hero.get_actor_forward_vector()
        ahead = unreal.Vector(ahead.x, ahead.y, 0.0).normal()
        _frame.update(here=here, ahead=ahead, right=unreal.Vector(-ahead.y, ahead.x, 0.0))
    sites = ((1500.0, 500.0), (-700.0, 350.0))
    ox, oy = min(sites, key=lambda s: (x - s[0]) ** 2 + (y - s[1]) ** 2)
    forward, right = -(y - oy), x - ox          # the old checks looked down -Y, with +X to their right
    here, a, r = _frame['here'], _frame['ahead'], _frame['right']
    return unreal.Vector(here.x + a.x * forward + r.x * right, here.y + a.y * forward + r.y * right, here.z - 90.0 + z)


async def hero_is_down():
    """Waits (up to 20 s) until PIE has a hero that has stopped falling, then fixes the frame W() measures from."""
    for _ in range(40):
        await asyncio.sleep(0.5)
        game = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        hero = unreal.GameplayStatics.get_player_pawn(game, 0) if game else None
        if hero and abs(hero.get_velocity().z) < 5.0:
            break
    # Team rule (21:27): until the game puts the hero there itself, go to the start tagged 'Lanthorne' (Great Tower
    # St) first, look the way it looks, and give the streamed city a few seconds to arrive.
    game = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    hero = unreal.GameplayStatics.get_player_pawn(game, 0) if game else None
    starts = [a for a in unreal.GameplayStatics.get_all_actors_of_class(game, unreal.PlayerStart)
              if str(a.get_editor_property('player_start_tag')) == 'Lanthorne'] if hero else []
    if starts:
        hero.set_actor_location(starts[0].get_actor_location(), False, True)
        hero.set_actor_rotation(unreal.Rotator(0.0, 0.0, starts[0].get_actor_rotation().yaw), False)
        if hero.get_controller():
            hero.get_controller().set_control_rotation(starts[0].get_actor_rotation())
        await asyncio.sleep(4.0)
        for _ in range(20):
            if abs(hero.get_velocity().z) < 5.0:
                break
            await asyncio.sleep(0.25)
    await asyncio.sleep(1.0)
    W(1500.0, 500.0, 90.0)


open_map = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world().get_name()
if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
    result['abort'] = 'PIE is already running (someone else is testing); nothing was started.'
else:
    console('Squads.StartPatrol 0')
    await call_tool('EditorToolset.EditorAppToolset.StartPIE')
    try:
        await hero_is_down()
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        console('Squads.Clear', world)
        console('Npc.ElementReactions 1', world)
        console('Npc.Heat 0', world)
        player = unreal.GameplayStatics.get_player_pawn(world, 0)
        controller = player.get_controller()
        npcs = unreal.get_world_subsystem(world, unreal.ReflectionsNpcSubsystem)
        spells = player.get_component_by_class(unreal.ReflectionsSpellCombatComponent)
        HERE = W(1500, 500, 90)
        SPOT = W(1500, 240, 0)

        def brain(actor):
            return actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent)

        def health(actor):
            return round(actor.get_component_by_class(unreal.ReflectionsHealthComponent).get_editor_property('health'), 1)

        def body_of(actor):
            return next(m for m in actor.get_components_by_class(unreal.SkeletalMeshComponent) if m.get_name() == 'Body')

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

        def state(actor):
            body = body_of(actor)
            walker = brain(actor).get_locomotion_driver()
            place = (walker or actor).get_actor_location()
            return {'x': round(place.x), 'y': round(place.y), 'z': round(place.z), 'health': health(actor),
                    'reaction': brain(actor).get_editor_property('reaction').name,
                    'mode': body.get_editor_property('animation_mode').name, 'simulating': body.is_any_simulating_physics()}

        async def watch(actor, seconds, step=0.1):
            began = time.perf_counter()
            samples = []
            while time.perf_counter() - began < seconds:
                await asyncio.sleep(step)
                sample = state(actor)
                sample['t'] = round(time.perf_counter() - began, 2)
                samples.append(sample)
            return samples

        def pelvis_height(actor):
            try:
                return round(body_of(actor).get_center_of_mass('pelvis').z - actor.get_actor_location().z, 1)
            except Exception:
                return None

        async def spawn(archetype):
            actor = npcs.spawn_npc(archetype, SPOT, 90.0, None)
            await asyncio.sleep(0.9)
            return actor

        player.set_actor_location(HERE, False, True)

        # ---- P1: water shoves ----------------------------------------------------------------------
        soldier = await spawn('Soldier')
        before = state(soldier)
        cast(unreal.HeroSpell.WATER_ORB, soldier)
        samples = await watch(soldier, 1.5, 0.05)
        result['P1'] = {'before': before, 'last': samples[-1], 'moved_away_cm': max(((s['x'] - before['x']) * _frame['ahead'].x + (s['y'] - before['y']) * _frame['ahead'].y) for s in samples),
                        'rose_cm': max(s['z'] for s in samples) - before['z'], 'modes': sorted({s['mode'] for s in samples}),
                        'ever_simulating_alive': any(s['simulating'] and s['reaction'] != 'INCAPACITATED' for s in samples)}
        check('P1_water_orb_hits_and_shoves', samples[-1]['health'] < before['health'] and result['P1']['moved_away_cm'] >= 80, result['P1'])
        check('P1_body_is_never_simulated_alive', not result['P1']['ever_simulating_alive'] and all('BLUEPRINT' in m for m in result['P1']['modes']), result['P1'])
        await shot('P1_after_water_orb')
        unreal.GameplayStatics.apply_damage(soldier, 999.0, None, None, unreal.DamageType)
        await asyncio.sleep(0.3)

        # ---- P2: one fire bolt on a townsperson -------------------------------------------------------
        civilian = await spawn('Civilian')
        before = state(civilian)
        cast(unreal.HeroSpell.FIRE, civilian)
        samples = await watch(civilian, 1.6)
        result['P2'] = {'before': before, 'after': samples[-1], 'reactions': sorted({s['reaction'] for s in samples}),
                        'ran_cm': max(abs(s['x'] - before['x']) + abs(s['y'] - before['y']) for s in samples)}
        check('P2_fire_bolt_hurts_but_does_not_kill_and_it_runs', 0 < samples[-1]['health'] < before['health'] and 'FLEEING' in result['P2']['reactions'], result['P2'])
        await shot('P2_burning_and_running')
        unreal.GameplayStatics.apply_damage(civilian, 999.0, None, None, unreal.DamageType)
        await asyncio.sleep(0.3)

        # ---- P3: lightning kills a townsperson outright; the body twitches -----------------------------
        civilian = await spawn('Civilian')
        before = state(civilian)
        cast(unreal.HeroSpell.LIGHTNING_BOLT, civilian)
        await asyncio.sleep(0.7)
        await shot('P3_struck_down')
        speeds = []
        for _ in range(6):
            await asyncio.sleep(0.1)
            try:
                speeds.append(round(body_of(civilian).get_physics_linear_velocity('hand_r').length()))
            except Exception as error:
                speeds.append(repr(error)[:60])
        after = {'reaction': brain(civilian).get_editor_property('reaction').name, 'simulating': body_of(civilian).is_any_simulating_physics(),
                 'pelvis': pelvis_height(civilian), 'health': health(civilian)}
        result['P3'] = {'before': before, 'after': after, 'hand_speed_cm_s': speeds}
        check('P3_lightning_kills_a_townsperson', after['reaction'] == 'INCAPACITATED' and after['simulating'] and after['pelvis'] is not None and after['pelvis'] < 60.0, result['P3'])
        check('P3_the_body_twitches', any(isinstance(v, int) and v > 15 for v in speeds), speeds)
    except Exception as error:
        import traceback
        result['error'] = repr(error)
        result['trace'] = traceback.format_exc()[-1500:]
    finally:
        try:
            console('Npc.ElementReactions %d' % (1 if globals().get('KEEP_REACTIONS_ON', False) else 0))
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
    check('log_no_empty_pose', result['log']['bone_out_of_range'] == 0 and result['log']['pose_not_ready'] == 0
          and result['log']['pose_repairs'] == 0, result['log'])
except Exception as error:
    result['log'] = repr(error)

result['passed'] = sum(1 for c in result['checks'].values() if c['ok'])
result['failed'] = sorted(name for name, c in result['checks'].items() if not c['ok'])
(OUT / 'verify_reactions2.json').write_text(json.dumps(result, indent=2, default=str))
json.dumps(result, default=str)
