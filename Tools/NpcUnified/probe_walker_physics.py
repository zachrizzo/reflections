"""Splits the 23:42 crash (train #14, SkinnedAsset.cpp:471 on a visible body, Npc.WalkerPhysics 2, lightning).

THIS MAY CRASH THE EDITOR. Run it only in a slot where that costs nothing, with everything saved beforehand.
Run inside the editor (the project's Python MCP: top-level await, `call_tool`), one PART per call:

  PART = 'Y'  the dead one. A Frost soldier (the IvenRook body of the crash) is shocked by a hit injected on it
              alone (no projectile, no chain to bystanders) and killed 0.67 s into the shock, eight times. Its body
              then twitches on the ground for 0.9 s as in the crash.
  PART = 'X'  the living ones. People who are already in the street (crowd walkers and Lives' people, with the
              crowd's own animation throttling) are shocked the same way and left alone: the current runs out,
              townspeople drop at the end of it, the jolts end by themselves. Then the same with six fresh
              soldiers and townspeople in the IvenRook body.
  PART = 'W'  the crash as it was: a real Lightning Bolt at a Frost soldier among the bystanders, killed mid-shock,
              four times.
  PHYSICS = 2 (default) | 1 | 0   the value of Npc.WalkerPhysics for the run (0 gives the control run).

Progress is written to Saved/NpcUnified/probe_walker_<PART>.json after every step, so that a crash leaves a record of
how far it got. PIE is always stopped and Npc.WalkerPhysics put back to 0 at the end. Nothing is saved.
"""

import json
import time
from pathlib import Path

OUT = Path(unreal.Paths.project_saved_dir()) / 'NpcUnified'
OUT.mkdir(parents=True, exist_ok=True)
PART = globals().get('PART', 'Y')
PHYSICS = int(globals().get('PHYSICS', 2))
result = {'part': PART, 'physics': PHYSICS, 'steps': [], 'finished': False, 'started': time.strftime('%H:%M:%S')}
LOG_PATH = Path(unreal.Paths.project_log_dir()) / 'reflections.log'
try:
    log_start = LOG_PATH.stat().st_size
except OSError:
    log_start = 0


def note(step):
    """Writes the progress file at once: after a crash this is all that is left."""
    step['at'] = time.strftime('%H:%M:%S')
    result['steps'].append(step)
    (OUT / ('probe_walker_%s.json' % PART)).write_text(json.dumps(result, indent=1, default=str))


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
        await asyncio.sleep(2.5)
        console('Squads.Clear', world)
        console('Npc.Heat 0', world)
        controller = player.get_controller()
        npcs = unreal.get_world_subsystem(world, unreal.ReflectionsNpcSubsystem)
        spells = player.get_component_by_class(unreal.ReflectionsSpellCombatComponent)
        hero_health = player.get_component_by_class(unreal.ReflectionsHealthComponent)
        hero_health.set_editor_property('max_health', 1000000.0)
        hero_health.reset_health()
        HERE = player.get_actor_location()
        GROUND = HERE.z - 90.0
        ahead = player.get_actor_forward_vector()
        ahead = unreal.Vector(ahead.x, ahead.y, 0.0).normal()
        side = unreal.Vector(-ahead.y, ahead.x, 0.0)

        def at(forward_cm, right_cm=0.0, up_cm=0.0):
            return unreal.Vector(HERE.x + ahead.x * forward_cm + side.x * right_cm, HERE.y + ahead.y * forward_cm + side.y * right_cm, GROUND + up_cm)

        TOWARD_HERO = unreal.MathLibrary.find_look_at_rotation(at(300), unreal.Vector(HERE.x, HERE.y, GROUND)).yaw

        def brain(actor):
            return actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent)

        def reaction(actor):
            try:
                return brain(actor).get_editor_property('reaction').name
            except Exception as error:
                return repr(error)[:40]

        def body_class(actor):
            try:
                for mesh in actor.get_components_by_class(unreal.SkeletalMeshComponent):
                    if mesh.get_name() == 'Body':
                        asset = mesh.get_skeletal_mesh_asset()
                        return asset.get_name() if asset else None
            except Exception as error:
                return repr(error)[:50]
            return None

        def look_class(look_id):
            """The look's class: a dressed soldier look (Looks/Soldiers/<id>) or one of the older cast (Looks/BP_Look_<id>)."""
            for path in ('/Game/Characters/Lanthorne/Looks/Soldiers/%s.%s_C' % (look_id, look_id),
                         '/Game/Characters/Lanthorne/Looks/BP_Look_%s.BP_Look_%s_C' % (look_id, look_id)):
                try:
                    found = unreal.load_object(None, path)
                    if found:
                        return found
                except Exception:
                    pass
            return None

        def shock(actor, seconds=1.5):
            """A lightning hit on this NPC alone: no projectile, so nothing chains to anyone else."""
            where = brain(actor).get_aim_point()
            hit = unreal.ReflectionsSpellHitData()
            hit.set_editor_property('spell', unreal.HeroSpell.LIGHTNING_BOLT)
            hit.set_editor_property('location', where)
            hit.set_editor_property('impulse', unreal.Vector(ahead.x * 260.0, ahead.y * 260.0, 0.0))
            hit.set_editor_property('caster', player)
            hit.set_editor_property('target', actor)
            hit.set_editor_property('reaction', unreal.ReflectionsSpellReaction.ELECTRIFY)
            hit.set_editor_property('magnitude', 0.7)
            hit.set_editor_property('duration', seconds)
            hit.set_editor_property('origin', player.get_actor_location())
            npcs.report_spell_hit(hit)

        def kill(actor):
            unreal.GameplayStatics.apply_damage(actor, 999.0, None, player, unreal.DamageType)

        console('Npc.WalkerPhysics %d' % PHYSICS, world)
        note({'step': 'setup done', 'npcs_in_world': len(npcs.get_npc_actors())})

        if PART == 'Y':
            for index in range(int(globals().get('RUNS', 8))):
                soldier = npcs.spawn_npc('Soldier', at(300, (index % 4 - 1.5) * 140.0), TOWARD_HERO, look_class('FrostSoldier_Iven'))
                await asyncio.sleep(1.3)
                brain(soldier).set_externally_steered(True)
                note({'step': 'Y%d spawned' % index, 'body': body_class(soldier)})
                shock(soldier)
                await asyncio.sleep(0.67)
                state = reaction(soldier)
                kill(soldier)
                note({'step': 'Y%d killed mid-shock' % index, 'reaction_before': state})
                await asyncio.sleep(1.4)                      # the corpse twitches for 0.9 s
                note({'step': 'Y%d survived the twitching' % index, 'reaction': reaction(soldier)})

        if PART == 'X':
            # People already in the street, nearest first (not anyone's quest person at the far end of the map).
            near = []
            for actor in npcs.get_npc_actors():
                try:
                    gap = (actor.get_actor_location() - HERE).length()
                    if gap < 3000.0 and reaction(actor) != 'INCAPACITATED':
                        near.append((gap, actor))
                except Exception:
                    continue
            near.sort(key=lambda pair: pair[0])
            chosen = [actor for _, actor in near[:6]]
            note({'step': 'X street people chosen', 'count': len(chosen), 'who': [[a.get_class().get_name(), body_class(a), round(g)] for g, a in near[:6]]})
            for index, actor in enumerate(chosen):
                shock(actor)
                note({'step': 'X street %d shocked' % index, 'class': actor.get_class().get_name()})
                await asyncio.sleep(0.25)
            await asyncio.sleep(4.0)                           # the current runs out, some drop, the jolts end
            note({'step': 'X street people after 4 s', 'reactions': [reaction(a) for a in chosen]})
            fresh = []
            for index in range(6):
                archetype = 'Soldier' if index % 2 == 0 else 'Civilian'
                actor = npcs.spawn_npc(archetype, at(320, (index - 2.5) * 130.0), TOWARD_HERO, look_class('FrostSoldier_Iven'))
                await asyncio.sleep(0.5)
                fresh.append(actor)
            await asyncio.sleep(1.0)
            for actor in fresh:
                brain(actor).set_externally_steered(True)
            for index, actor in enumerate(fresh):
                shock(actor)
                note({'step': 'X fresh %d shocked' % index})
                await asyncio.sleep(0.2)
            await asyncio.sleep(4.0)
            note({'step': 'X fresh after 4 s', 'reactions': [reaction(a) for a in fresh]})

        if PART == 'W':
            for index in range(int(globals().get('RUNS', 4))):
                soldier = npcs.spawn_npc('Soldier', at(260, (index % 4 - 1.5) * 140.0), TOWARD_HERO, look_class('FrostSoldier_Iven'))
                await asyncio.sleep(1.3)
                aim = brain(soldier).get_aim_point()
                controller.set_control_rotation(unreal.MathLibrary.find_look_at_rotation(player.get_actor_location(), aim))
                origin = unreal.Transform(location=player.get_actor_location() + unreal.Vector(0, 0, 50), rotation=unreal.Rotator(), scale=unreal.Vector(1, 1, 1))
                spells.release_spell_at(unreal.HeroSpell.LIGHTNING_BOLT, origin, aim, None)
                note({'step': 'W%d bolt cast' % index})
                await asyncio.sleep(0.67)
                state = reaction(soldier)
                kill(soldier)
                note({'step': 'W%d killed mid-shock' % index, 'reaction_before': state})
                await asyncio.sleep(2.2)
                note({'step': 'W%d two seconds later' % index, 'reaction': reaction(soldier)})

        result['finished'] = True
    except Exception as error:
        import traceback
        result['error'] = repr(error)
        result['trace'] = traceback.format_exc()[-1500:]
    finally:
        try:
            console('Npc.WalkerPhysics 0')
            console('Npc.Heat 1')
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
                     'skinned_asset': tail.count('SkinnedAsset.cpp'), 'asserts': tail.count('Assertion failed'),
                     'move_simulated_warnings': tail.count('Attempting to move a fully simulated skeletal mesh')}
except Exception as error:
    result['log'] = repr(error)
result['ended'] = time.strftime('%H:%M:%S')
(OUT / ('probe_walker_%s.json' % PART)).write_text(json.dumps(result, indent=1, default=str))
json.dumps({'part': PART, 'physics': PHYSICS, 'finished': result['finished'], 'steps': len(result['steps']), 'error': result.get('error'), 'log': result.get('log')}, default=str)
