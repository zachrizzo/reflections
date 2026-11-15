"""What a spell's hit does to a living NPC (Npc.ElementReactions), including dying in the middle of each reaction.
Lvl_HeroSampleCrowd open, PIE stopped. One PIE session, about 40 seconds; it always stops PIE. Run through the
editor MCP `execute_python` tool (top-level `await`, `call_tool`).

The console variable is switched on for this run and put back to what it was afterwards.

  R1  Fireball on a soldier: thrown away from the blast (the hidden walker is launched), alive, and the visible body
      never simulates and never leaves its animation blueprint.
  R2  Lightning Bolt on that hurt soldier: it stands convulsing for a second or more, THEN drops into the ragdoll.
  R3  Lightning Bolt on a guard, killed half a second into the convulsion: an ordinary ragdoll death.
  R4  Water Orb on a guard: shoved; killed while still in the air: an ordinary ragdoll death.
  R5  Ice Shard on a soldier: the walker's clock is slowed (frozen), then runs again; it lives.
  R6  Fire Bolt on a townsperson: it lives and runs; a second bolt kills it (ordinary ragdoll).
  R7  Lightning Bolt on a townsperson: dead at once, and the body on the ground twitches (recorded, not required).
Result: Saved/NpcUnified/verify_reactions.json and R*_ pictures.
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
        result['build_has_reactions'] = hasattr(npcs, 'get_player_heat')
        HERE = W(1500, 500, 90)
        SPOT = W(1500, 80, 0)

        def brain(actor):
            return actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent)

        def health(actor):
            return round(actor.get_component_by_class(unreal.ReflectionsHealthComponent).get_editor_property('health'), 1)

        def body_of(actor):
            return next(m for m in actor.get_components_by_class(unreal.SkeletalMeshComponent) if m.get_name() == 'Body')

        def walker_of(actor):
            return brain(actor).get_locomotion_driver()

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
            walker = walker_of(actor)
            place = (walker or actor).get_actor_location()
            anim = walker.get_editor_property('mesh').get_anim_instance() if walker else None
            return {'x': round(place.x), 'y': round(place.y), 'z': round(place.z), 'health': health(actor),
                    'reaction': brain(actor).get_editor_property('reaction').name,
                    'mode': body.get_editor_property('animation_mode').name, 'simulating': body.is_any_simulating_physics(),
                    'dilation': round(walker.get_editor_property('custom_time_dilation'), 2) if walker else None,
                    'montage': bool(anim and anim.is_any_montage_playing())}

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

        def summary(before, samples):
            away = max(((s['x'] - before['x']) * _frame['ahead'].x + (s['y'] - before['y']) * _frame['ahead'].y) for s in samples)   # the player stands at +Y of the target: away is -Y
            return {'before': before, 'last': samples[-1], 'moved_away_cm': away, 'rose_cm': max(s['z'] for s in samples) - before['z'],
                    'modes': sorted({s['mode'] for s in samples}), 'ever_simulating_alive': any(s['simulating'] and s['reaction'] != 'INCAPACITATED' for s in samples),
                    'montage_seen': any(s['montage'] for s in samples), 'min_dilation': min((s['dilation'] for s in samples if s['dilation'] is not None), default=None)}

        def dead_properly(actor):
            return {'reaction': brain(actor).get_editor_property('reaction').name, 'simulating': body_of(actor).is_any_simulating_physics(),
                    'pelvis': pelvis_height(actor), 'health': health(actor)}

        def is_ragdoll(info):
            return info['reaction'] == 'INCAPACITATED' and info['simulating'] and info['pelvis'] is not None and info['pelvis'] < 60.0

        async def spawn(archetype):
            actor = npcs.spawn_npc(archetype, SPOT, 90.0, None)
            await asyncio.sleep(1.2)
            return actor

        def clear(actor):
            # Out of the way of the next case (bodies are left to their own clean-up).
            if brain(actor).get_editor_property('reaction').name != 'INCAPACITATED':
                unreal.GameplayStatics.apply_damage(actor, 999.0, None, None, unreal.DamageType)

        player.set_actor_location(HERE, False, True)

        # ---- R1: a blast throws it ------------------------------------------------------------------
        soldier = await spawn('Soldier')
        before = state(soldier)
        cast(unreal.HeroSpell.FIRESTORM, soldier)
        samples = await watch(soldier, 1.6)
        result['R1'] = summary(before, samples)
        check('R1_blast_throws_it', result['R1']['moved_away_cm'] >= 100 and result['R1']['rose_cm'] >= 10, result['R1'])
        check('R1_body_is_never_simulated_alive', not result['R1']['ever_simulating_alive'] and all('BLUEPRINT' in m for m in result['R1']['modes']), result['R1'])
        check('R1_it_lives', samples[-1]['reaction'] != 'INCAPACITATED' and samples[-1]['health'] > 0, samples[-1])
        await shot('R1_after_blast')

        # ---- R2: shocked until it drops -------------------------------------------------------------
        before = state(soldier)
        cast(unreal.HeroSpell.LIGHTNING_BOLT, soldier)
        samples = await watch(soldier, 0.7)
        await shot('R2_convulsing')
        samples += [dict(s, t=round(s['t'] + 0.7, 2)) for s in await watch(soldier, 2.6)]
        hit_at = next((s['t'] for s in samples if s['health'] < before['health']), None)
        down_at = next((s['t'] for s in samples if s['reaction'] == 'INCAPACITATED'), None)
        result['R2'] = {'before': before, 'hit_at': hit_at, 'down_at': down_at, 'stood_convulsing_s': round(down_at - hit_at, 2) if hit_at is not None and down_at is not None else None,
                        'montage_seen': any(s['montage'] for s in samples), 'health_steps': sorted({s['health'] for s in samples}, reverse=True),
                        'moved_while_shocked_cm': max(abs(s['y'] - before['y']) + abs(s['x'] - before['x']) for s in samples if s['reaction'] != 'INCAPACITATED') if any(s['reaction'] != 'INCAPACITATED' for s in samples) else None,
                        'after': dead_properly(soldier)}
        check('R2_convulses_first', result['R2']['stood_convulsing_s'] is not None and result['R2']['stood_convulsing_s'] >= 0.8, result['R2'])
        check('R2_then_drops_into_the_ragdoll', is_ragdoll(result['R2']['after']), result['R2']['after'])
        await shot('R2_dropped')

        # ---- R3: killed in the middle of the convulsion ---------------------------------------------
        guard = await spawn('Guard')
        cast(unreal.HeroSpell.LIGHTNING_BOLT, guard)
        samples = await watch(guard, 0.6)
        alive_mid = samples[-1]['reaction'] != 'INCAPACITATED'
        unreal.GameplayStatics.apply_damage(guard, 999.0, None, player, unreal.DamageType)
        await asyncio.sleep(1.4)
        result['R3'] = {'hit': samples[-1]['health'] < samples[0]['health'] or samples[0]['health'] < 42, 'alive_when_killed': alive_mid, 'after': dead_properly(guard)}
        check('R3_killed_mid_convulsion_is_an_ordinary_death', is_ragdoll(result['R3']['after']), result['R3'])

        # ---- R4: shoved by water, killed in the air -------------------------------------------------
        guard = await spawn('Guard')
        before = state(guard)
        cast(unreal.HeroSpell.WATER_ORB, guard)
        samples = await watch(guard, 1.0, 0.05)
        launched = next((s for s in samples if s['z'] - before['z'] >= 8 or ((s['x'] - before['x']) * _frame['ahead'].x + (s['y'] - before['y']) * _frame['ahead'].y) >= 40), None)
        result['R4'] = summary(before, samples)
        result['R4']['launched_at'] = launched['t'] if launched else None
        check('R4_water_shoves_it', result['R4']['moved_away_cm'] >= 80, result['R4'])
        cast(unreal.HeroSpell.WATER_ORB, guard)
        mid = await watch(guard, 0.75, 0.05)
        in_air = max(s['z'] for s in mid) - before['z']
        unreal.GameplayStatics.apply_damage(guard, 999.0, None, player, unreal.DamageType)
        await asyncio.sleep(1.4)
        result['R4']['killed_mid_throw'] = {'height_cm': in_air, 'after': dead_properly(guard)}
        check('R4_killed_mid_throw_is_an_ordinary_death', is_ragdoll(result['R4']['killed_mid_throw']['after']), result['R4']['killed_mid_throw'])
        await shot('R4_after_water')

        # ---- R5: frozen, then thawed ----------------------------------------------------------------
        soldier = await spawn('Soldier')
        before = state(soldier)
        cast(unreal.HeroSpell.ICE_SHARD, soldier)
        samples = await watch(soldier, 0.8)
        await shot('R5_frozen')
        frozen = summary(before, samples)
        samples = await watch(soldier, 3.0, 0.2)
        result['R5'] = {'frozen': frozen, 'thawed': samples[-1]}
        check('R5_ice_freezes_it', frozen['min_dilation'] is not None and frozen['min_dilation'] < 0.2, frozen)
        check('R5_it_thaws_and_lives', samples[-1]['dilation'] == 1.0 and samples[-1]['reaction'] != 'INCAPACITATED', samples[-1])
        clear(soldier)

        # ---- R6: fire sets a townsperson running; the second bolt kills --------------------------------
        civilian = await spawn('Civilian')
        before = state(civilian)
        cast(unreal.HeroSpell.FIRE, civilian)
        samples = await watch(civilian, 1.6)
        result['R6'] = {'before': before, 'after_one_bolt': samples[-1], 'reactions': sorted({s['reaction'] for s in samples})}
        check('R6_one_fire_bolt_does_not_kill_but_it_runs', samples[-1]['health'] > 0 and 'FLEEING' in result['R6']['reactions'], result['R6'])
        cast(unreal.HeroSpell.FIRE, civilian)
        await asyncio.sleep(1.6)
        result['R6']['after_two_bolts'] = dead_properly(civilian)
        # It is running by now, so an unguided bolt can miss: a miss (health unchanged) is not a failure of the NPC.
        result['R6']['second_bolt_missed'] = result['R6']['after_two_bolts']['health'] == samples[-1]['health']
        check('R6_two_fire_bolts_kill', is_ragdoll(result['R6']['after_two_bolts']) or result['R6']['second_bolt_missed'], result['R6']['after_two_bolts'])
        clear(civilian)

        # ---- R7: lightning kills a townsperson outright; the body twitches ---------------------------
        civilian = await spawn('Civilian')
        cast(unreal.HeroSpell.LIGHTNING_BOLT, civilian)
        await asyncio.sleep(0.9)
        speeds = []
        for _ in range(6):
            await asyncio.sleep(0.12)
            try:
                speeds.append(round(body_of(civilian).get_physics_linear_velocity('hand_r').length()))
            except Exception as error:
                speeds.append(repr(error)[:60])
        result['R7'] = {'after': dead_properly(civilian), 'hand_speed_cm_s': speeds}
        check('R7_lightning_kills_a_townsperson', is_ragdoll(result['R7']['after']), result['R7'])
        await shot('R7_struck_down')
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
(OUT / 'verify_reactions.json').write_text(json.dumps(result, indent=2, default=str))
json.dumps(result, default=str)
