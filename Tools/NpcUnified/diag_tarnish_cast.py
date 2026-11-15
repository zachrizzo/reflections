"""Why did the tarnished not cast from 12 m? One short PIE (about 25 s) on Lvl_HeroSampleCrowd; always stops PIE.

Every other NPC is held (so the tarnished has no townsperson to run down), the Infected archetype is switched to its
built-in in memory only, and one tarnished is watched from 7 m (inside its sight radius) and then from 13 m.
Sampled five times a second: its reaction, what it is after, the distance, the player's health, every spell
projectile in the world with its owner, and whether the Tarnish caster component says it is casting.
Result: Saved/NpcUnified/diag_tarnish_cast.json
"""

import json
import time
from pathlib import Path

OUT = Path(unreal.Paths.project_saved_dir()) / 'NpcUnified'
result = {}


def unwrap(value):
    return value['returnValue'] if isinstance(value, dict) and 'returnValue' in value else value


def console(command, world=None):
    unreal.SystemLibrary.execute_console_command(world or unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world(), command)


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
    result['abort'] = 'PIE is already running'
else:
    console('Squads.StartPatrol 0')
    await call_tool('EditorToolset.EditorAppToolset.StartPIE')
    try:
        await hero_is_down()
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        console('Squads.Clear', world)
        player = unreal.GameplayStatics.get_player_pawn(world, 0)
        controller = player.get_controller()
        npcs = unreal.get_world_subsystem(world, unreal.ReflectionsNpcSubsystem)
        hero = player.get_component_by_class(unreal.ReflectionsHealthComponent)

        def brain(actor):
            return actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent)

        infected = npcs.find_archetype('Infected')
        if globals().get('RESET_IN_MEMORY', True):
            infected.reset_to_built_in()
        combat = infected.get_editor_property('combat')
        result['archetype'] = {'casts_at_player': combat.get_editor_property('casts_at_player'), 'sight': combat.get_editor_property('sight_radius'),
                               'range': [combat.get_editor_property('ranged_min_range'), combat.get_editor_property('ranged_max_range')],
                               'hunts_npcs': combat.get_editor_property('hunts_npcs'), 'motor': combat.get_editor_property('use_melee_motor')}
        others = list(npcs.get_npc_actors())
        for other in others:
            npcs.hold_npc(other, 60.0)
        result['others_held'] = [[o.get_class().get_name(), round(o.get_actor_location().x), round(o.get_actor_location().y)] for o in others]

        async def watch(label, gap, seconds):
            player.set_actor_location(W(1500, 500, 90), False, True)
            sorcerer = npcs.spawn_npc('Civilian', W(1500, 500 - gap, 0), 90.0, None)
            await asyncio.sleep(1.2)
            controller.set_control_rotation(unreal.MathLibrary.find_look_at_rotation(player.get_actor_location(), sorcerer.get_actor_location() + unreal.Vector(0, 0, 100)))
            before = hero.get_editor_property('health')
            npcs.set_infection(sorcerer, unreal.ReflectionsNpcInfection.INFECTED, None)
            caster_class = getattr(unreal, 'ReflectionsTarnishCasterComponent', None)
            samples = []
            seen = {}
            began = time.perf_counter()
            while time.perf_counter() - began < seconds:
                await asyncio.sleep(0.2)
                focus = brain(sorcerer).get_focus_actor()
                delta = sorcerer.get_actor_location() - player.get_actor_location()
                flying = []
                for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
                    name = actor.get_class().get_name()
                    if 'Projectile' in name or 'Tarnish' in name:
                        owner = actor.get_owner()
                        flying.append(name)
                        seen.setdefault(actor.get_name(), [name, owner.get_name() if owner else None, round(time.perf_counter() - began, 1)])
                caster = sorcerer.get_component_by_class(caster_class) if caster_class else None
                casting = None
                if caster:
                    try:
                        casting = caster.is_casting()
                    except Exception as error:
                        casting = repr(error)[:40]
                samples.append([round(time.perf_counter() - began, 1), brain(sorcerer).get_editor_property('reaction').name,
                                'player' if focus == player else (focus.get_class().get_name() if focus else None),
                                round(unreal.Vector(delta.x, delta.y, 0).length()), hero.get_editor_property('health'), len(flying), casting,
                                len(sorcerer.get_components_by_class(unreal.PointLightComponent))])
            result[label] = {'hero_health': [before, hero.get_editor_property('health')], 'projectiles': list(seen.values())[:12],
                             'samples': samples[::2], 'has_caster_component': bool(sorcerer.get_component_by_class(caster_class)) if caster_class else None}
            unreal.GameplayStatics.apply_damage(sorcerer, 999.0, None, None, unreal.DamageType)
            await asyncio.sleep(0.4)

        await watch('from_7m', 700, 9.0)
        await watch('from_13m', 1300, 6.0)
    except Exception as error:
        import traceback
        result['error'] = repr(error)
        result['trace'] = traceback.format_exc()[-1200:]
    finally:
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')
        console('Squads.StartPatrol 1')

(OUT / 'diag_tarnish_cast.json').write_text(json.dumps(result, indent=1, default=str))
json.dumps({'done': True, 'error': result.get('error'), 'abort': result.get('abort')})
