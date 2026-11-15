"""Capture spell presentation from the default map during an owned PIE session.

The script uses the real combat component and captures multiple frames around
each release. It creates a temporary camera and only moves actors in PIE.
Run with PIE stopped, through Unreal's editor Python tool. The JSON records
which effects were active; inspect the frames to judge actual visual quality.
"""

import json
import traceback
from pathlib import Path

import unreal


output = Path(unreal.Paths.project_intermediate_dir()) / 'CombatPresentation'
output.mkdir(parents=True, exist_ok=True)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor_actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if editor.get_game_world():
    raise RuntimeError('A Play session is already active')

camera_source = editor_actors.spawn_actor_from_class(unreal.CameraActor, unreal.Vector(0, 0, -10000), unreal.Rotator())
camera_source.tags = [unreal.Name('TemporaryCombatPresentationCamera')]
level.editor_request_begin_play()
state = {'start': None, 'case': -1, 'case_start': 0.0, 'frames': set(), 'systems': {}, 'done': False}
result = {'mode': 'default map, actual combat releases in Play in Editor', 'cases': {}, 'completed': False}
cases = [('fire_bolt', unreal.HeroSpell.FIRE), ('water_bolt', unreal.HeroSpell.WATER),
         ('healing', unreal.HeroSpell.HEALING), ('fireball', unreal.HeroSpell.FIRESTORM),
         ('tidal_surge', unreal.HeroSpell.TIDAL_SURGE), ('shield', unreal.HeroSpell.SHIELD)]


def cleanup():
    if state['done']:
        return
    state['done'] = True
    unreal.unregister_slate_post_tick_callback(handle)
    level.editor_request_end_play()

    def remove_camera(_delta):
        if not editor.get_game_world():
            if camera_source:
                editor_actors.destroy_actor(camera_source)
            unreal.unregister_slate_post_tick_callback(cleanup_handle)

    cleanup_handle = unreal.register_slate_post_tick_callback(remove_camera)


def position_npc(actor, location):
    brain = actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent)
    if not brain:
        return
    driver = brain.get_locomotion_driver()
    delta = location - actor.get_actor_location()
    if driver:
        driver.get_character_movement().disable_movement()
        driver.set_actor_location(driver.get_actor_location() + delta, False, True)
    else:
        actor.set_actor_location(location, False, True)
    brain.set_component_tick_enabled(False)


def begin_case(world, pawn, combat, target, case, spell):
    if case in ('fire_bolt', 'water_bolt', 'fireball'):
        proxy = next(c for c in target.get_components_by_class(unreal.CapsuleComponent)
                     if c.get_name() == 'RuntimeNpcHitProxy')
        aim = proxy.get_world_location()
        origin = aim - unreal.Vector(300, 0, 0)
        rotation = unreal.Rotator()
    else:
        origin = pawn.get_actor_location()
        rotation = unreal.Rotator()
    result['cases'][case] = {'systems': [], 'captures': [], 'target_health_before':
                             target.get_component_by_class(unreal.ReflectionsHealthComponent).get_editor_property('health')}
    combat.release_spell(spell, unreal.Transform(location=origin, rotation=rotation, scale=unreal.Vector(1, 1, 1)))


def tick(_delta):
    try:
        world = editor.get_game_world()
        if not world:
            return
        pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
        controller = unreal.GameplayStatics.get_player_controller(world, 0)
        if not pawn or not controller:
            return
        combat = pawn.get_component_by_class(unreal.ReflectionsSpellCombatComponent)
        if not combat:
            return
        now = unreal.GameplayStatics.get_time_seconds(world)
        if state['start'] is None:
            state['start'] = now
            state['camera'] = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.CameraActor)
                                   if a.actor_has_tag('TemporaryCombatPresentationCamera'))
            camera = state['camera']
            camera_component = next(iter(camera.get_components_by_class(unreal.CameraComponent)))
            camera_component.set_field_of_view(70)
            location = unreal.Vector(215, -500, 190)
            rotation = unreal.MathLibrary.find_look_at_rotation(location, unreal.Vector(215, 0, 100))
            camera.set_actor_location_and_rotation(location, rotation, False, True)
            controller.set_view_target_with_blend(camera, 0.0)
            npcs = {a.get_actor_label(): a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                    if a.get_component_by_class(unreal.ReflectionsNpcReactionComponent)}
            for actor in npcs.values():
                position_npc(actor, unreal.Vector(4000, 1500, 0))
            target = npcs['Crowd Preview - White 01']
            position_npc(target, unreal.Vector(400, 0, 0))
            pawn.set_actor_location(unreal.Vector(0, 0, 90), False, True)
            pawn.set_actor_rotation(unreal.Rotator(), True)
            state['target'] = target

        elapsed = now - state['start']
        if state['case'] < 0 and elapsed > 2.0:
            state['case'] = 0
            state['case_start'] = now
            begin_case(world, pawn, combat, state['target'], *cases[0])
        if state['case'] >= 0:
            case, _spell = cases[state['case']]
            age = now - state['case_start']
            for component in unreal.ObjectIterator(unreal.NiagaraComponent):
                try:
                    system = component.get_asset()
                    if system and component.is_active():
                        state['systems'].setdefault(case, set()).add(system.get_path_name())
                except Exception:
                    pass
            for mark in (0.12, 0.28, 0.55, 0.90):
                key = (case, mark)
                if age >= mark and key not in state['frames']:
                    state['frames'].add(key)
                    image_path = output / ('%s_%03d.png' % (case, round(mark * 100)))
                    unreal.SystemLibrary.execute_console_command(world, 'HighResShot 1280x720 filename="%s"' % image_path.as_posix())
                    result['cases'][case]['captures'].append(str(image_path))
                    break
            if age > 2.6:
                result['cases'][case]['systems'] = sorted(state['systems'].get(case, set()))
                result['cases'][case]['target_health_after'] = state['target'].get_component_by_class(
                    unreal.ReflectionsHealthComponent).get_editor_property('health')
                state['case'] += 1
                if state['case'] < len(cases):
                    state['case_start'] = now
                    begin_case(world, pawn, combat, state['target'], *cases[state['case']])
                else:
                    result['completed'] = True
                    (output / 'presentation_results.json').write_text(json.dumps(result, indent=2))
                    cleanup()
    except Exception:
        result['error'] = traceback.format_exc()
        (output / 'presentation_results.json').write_text(json.dumps(result, indent=2))
        cleanup()


handle = unreal.register_slate_post_tick_callback(tick)
