"""Temporary play test; no map changes are saved."""
import json, traceback
from pathlib import Path
import unreal

output = Path(unreal.Paths.project_dir()) / 'ArtDirection' / 'SpellVFX'
output.mkdir(parents=True, exist_ok=True)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
state = {'time': 0.0, 'stage': 0, 'tick': 0.0, 'systems_seen': set()}
result = {'mode': 'Play-in-Editor; calls real combat component'}


def screenshot(world, name):
    path = str(output / name).replace('\\', '/')
    unreal.SystemLibrary.execute_console_command(world, f'HighResShot 1280x720 filename="{path}"')


def tick(delta):
    state['time'] += delta
    try:
        world = editor.get_game_world()
        if world:
            for component in unreal.ObjectIterator(unreal.NiagaraComponent):
                try:
                    asset = component.get_asset()
                    if asset and component.is_active():
                        state['systems_seen'].add(asset.get_path_name())
                except Exception:
                    pass
        pawn = unreal.GameplayStatics.get_player_pawn(world, 0) if world else None
        if not pawn:
            return
        combat = pawn.get_component_by_class(unreal.ReflectionsSpellCombatComponent)
        if not combat:
            if state['time'] > 15:
                raise RuntimeError('No combat component on test pawn')
            return
        if state['stage'] == 0 and state['time'] > 2:
            result['pawn'] = pawn.get_class().get_name()
            combat.release_spell(unreal.HeroSpell.HEALING, unreal.Transform())
            state.update(stage=1, tick=state['time'])
        elif state['stage'] == 1 and state['time'] - state['tick'] > 0.25:
            screenshot(world, 'HealingCandidate_PIE.png')
            state.update(stage=2, tick=state['time'])
        elif state['stage'] == 2 and state['time'] - state['tick'] > 1.5:
            location = pawn.get_actor_location() + pawn.get_actor_forward_vector() * 160 + unreal.Vector(0, 0, 180)
            direction = unreal.Rotator(pitch=-80, yaw=pawn.get_actor_rotation().yaw, roll=0)
            combat.release_spell(unreal.HeroSpell.WATER, unreal.Transform(location=location, rotation=direction))
            state.update(stage=3, tick=state['time'])
        elif state['stage'] == 3 and state['time'] - state['tick'] > 0.4:
            screenshot(world, 'WaterCandidate_PIE.png')
            state.update(stage=4, tick=state['time'])
        elif state['stage'] == 4 and state['time'] - state['tick'] > 1.5:
            result['completed'] = True
            result['niagara_systems_seen'] = sorted(state['systems_seen'])
            (output / 'candidate_pie_test.json').write_text(json.dumps(result, indent=2))
            unreal.unregister_slate_post_tick_callback(tick.handle)
            unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
        elif state['time'] > 60:
            raise RuntimeError('Play test timed out')
    except Exception:
        result['error'] = traceback.format_exc()
        (output / 'candidate_pie_test.json').write_text(json.dumps(result, indent=2))
        unreal.unregister_slate_post_tick_callback(tick.handle)
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()

tick.handle = unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
