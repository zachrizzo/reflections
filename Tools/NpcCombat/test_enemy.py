"""Exercise the opt-in opponent in the default map, with a temporary PIE wall."""
import json
import time
import traceback
from pathlib import Path

import unreal

OUT = Path(unreal.Paths.project_intermediate_dir()) / 'NpcCombat'
OUT.mkdir(parents=True, exist_ok=True)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if editor.get_game_world():
    raise RuntimeError('End existing Play in Editor before this test')

wall = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(50000, 50000, -5000), unreal.Rotator())
wall.set_actor_label('Temporary Combat Test Wall')
wall.set_editor_property('tags', [unreal.Name('NpcCombatTempWall')])
wall.set_actor_scale3d(unreal.Vector(.15, 1.5, 2.0))
wall_component = wall.get_component_by_class(unreal.StaticMeshComponent)
wall_component.set_mobility(unreal.ComponentMobility.MOVABLE)
wall_component.set_static_mesh(unreal.EditorAssetLibrary.load_asset('/Engine/BasicShapes/Cube'))
wall_component.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
wall.set_actor_hidden_in_game(True)

state = {'phase': 'init', 'started': time.monotonic(), 'time': 0.0, 'phase_time': 0.0,
         'results': {'assertions': {}}, 'last': 0.0}


def location(actor):
    return [round(value, 2) for value in actor.get_actor_location().to_tuple()]


def move(actor, position):
    actor.set_actor_location(unreal.Vector(*position), False, True)


def transition(name):
    state['phase'] = name
    state['phase_time'] = 0.0


def check(name, condition):
    state['results']['assertions'][name] = bool(condition)


def finish(error=None):
    if error:
        state['results']['error'] = error
    state['results']['passed'] = not error and all(state['results']['assertions'].values())
    (OUT / 'enemy-pie.json').write_text(json.dumps(state['results'], indent=2))
    unreal.unregister_slate_post_tick_callback(observe.handle)
    if editor.get_game_world():
        levels.editor_request_end_play()

    def cleanup(_delta):
        if not editor.get_game_world():
            actors.destroy_actor(wall)
            unreal.unregister_slate_post_tick_callback(cleanup.handle)
    cleanup.handle = unreal.register_slate_post_tick_callback(cleanup)


def observe(delta):
    try:
        if time.monotonic() - state['started'] > 90:
            finish('Timed out in phase ' + state['phase'])
            return
        world = editor.get_game_world()
        player = unreal.GameplayStatics.get_player_pawn(world, 0) if world else None
        if not player:
            return
        state['time'] += delta
        state['phase_time'] += delta
        if state['phase'] == 'init':
            candidates = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor) if a.actor_has_tag('NPC_CombatEnemy')]
            if len(candidates) != 1:
                raise RuntimeError('Expected exactly one test combat enemy')
            enemy = candidates[0]
            ai = enemy.get_component_by_class(unreal.ReflectionsNpcCombatComponent)
            brain = enemy.get_component_by_class(unreal.ReflectionsNpcReactionComponent)
            driver = brain.get_locomotion_driver() if brain else None
            enemy_health = enemy.get_component_by_class(unreal.ReflectionsHealthComponent)
            player_health = player.get_component_by_class(unreal.ReflectionsHealthComponent)
            body = next(c for c in enemy.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == 'Body')
            runtime_walls = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.StaticMeshActor) if a.actor_has_tag('NpcCombatTempWall')]
            if not ai or not driver or not enemy_health or not player_health or not runtime_walls:
                if state['time'] > 8.0:
                    raise RuntimeError('Combat components or runtime wall were not created')
                return
            move(player, (0, -700, 95))
            move(driver, (135, -700, 95))
            state.update(enemy=enemy, ai=ai, brain=brain, driver=driver, player=player,
                         enemy_health=enemy_health, player_health=player_health,
                         body=body, wall=runtime_walls[0], baseline=player_health.get_editor_property('health'),
                         baseline_attacks=ai.get_editor_property('attacks_started'))
            state['results']['map'] = world.get_path_name()
            state['results']['enemy'] = enemy.get_actor_label()
            transition('range_wait')
            return

        enemy, ai, driver = state['enemy'], state['ai'], state['driver']
        player, health = state['player'], state['player_health']
        phase = state['phase']
        combat_state = str(ai.get_editor_property('combat_state'))
        started = ai.get_editor_property('attacks_started')
        hp = health.get_editor_property('health')
        if state['phase_time'] > 18.0:
            raise RuntimeError('Timed out waiting for ' + phase + '; state=' + combat_state + ' player_health=' + str(hp))

        if phase == 'range_wait' and 'WINDUP' in combat_state:
            state['results']['windup_animation_instance'] = state['body'].get_anim_instance().get_class().get_name() if state['body'].get_anim_instance() else None
            state['results']['windup_health_before'] = hp
            check('attack_animation_playing', state['results']['windup_animation_instance'] == 'AnimSingleNodeInstance')
            check('no_damage_at_start_of_windup', hp == state['baseline'])
            state['range_attack'] = started
            move(player, (500, -700, 95))
            transition('range_check')
        elif phase == 'range_check' and 'RECOVERING' in combat_state:
            state['results']['out_of_range'] = {'health_before': state['baseline'], 'health_after': hp}
            check('no_damage_out_of_range_at_impact', hp == state['baseline'])
            check('attack_enters_recovery', 'RECOVERING' in combat_state)
            move(player, (0, -700, 95))
            move(driver, (135, -700, 95))
            transition('interrupt_wait')
        elif phase == 'interrupt_wait' and 'WINDUP' in combat_state and started > state['range_attack']:
            state['interrupt_hp'] = hp
            state['interrupt_attack'] = started
            unreal.GameplayStatics.apply_damage(enemy, 1.0, None, player, unreal.DamageType)
            transition('interrupt_check')
        elif phase == 'interrupt_check' and state['phase_time'] > 0.7:
            state['results']['interrupted'] = {
                'health_before': state['interrupt_hp'], 'health_after': hp,
                'interrupted_attacks': ai.get_editor_property('interrupted_attacks'),
                'state': combat_state,
            }
            check('damage_interrupts_attack', ai.get_editor_property('interrupted_attacks') >= 1)
            check('interrupted_attack_deals_no_damage', hp == state['interrupt_hp'])
            transition('wall_wait')
        elif phase == 'wall_wait' and 'WINDUP' in combat_state and started > state['interrupt_attack']:
            state['wall_hp'] = hp
            state['wall_attack'] = started
            move(state['wall'], (67.5, -700, 100))
            transition('wall_check')
        elif phase == 'wall_check' and 'RECOVERING' in combat_state:
            state['results']['behind_wall'] = {'health_before': state['wall_hp'], 'health_after': hp}
            check('no_damage_through_wall', hp == state['wall_hp'])
            move(state['wall'], (50000, 50000, -5000))
            transition('hit_wait')
        elif phase == 'hit_wait' and hp < state['wall_hp']:
            state['results']['real_hit'] = {'health_before': state['wall_hp'], 'health_after': hp,
                                             'attacks_started': started,
                                             'successful_hits': ai.get_editor_property('successful_hits')}
            check('attack_damages_player_in_range', hp < state['wall_hp'] and ai.get_editor_property('successful_hits') >= 1)
            unreal.GameplayStatics.apply_damage(player, 1000.0, None, enemy, unreal.DamageType)
            state['dead_hits'] = ai.get_editor_property('successful_hits')
            transition('death_check')
        elif phase == 'death_check' and state['phase_time'] > 0.6:
            state['results']['dead_player'] = {'health': hp, 'target': str(ai.get_editor_property('target')),
                                                'state': combat_state,
                                                'additional_hits': ai.get_editor_property('successful_hits') - state['dead_hits']}
            check('dead_player_stops_being_targeted', hp <= 0 and ai.get_editor_property('target') is None)
            check('no_attacks_during_player_death', ai.get_editor_property('successful_hits') == state['dead_hits'])
            transition('respawn_wait')
        elif phase == 'respawn_wait' and hp > 0:
            state['results']['respawn'] = {'health': hp, 'same_player': player == state['player']}
            check('player_respawns_with_health', hp > 0)
            move(player, (0, -700, 95))
            move(driver, (135, -700, 95))
            transition('reacquire_wait')
        elif phase == 'reacquire_wait' and ai.get_editor_property('target') == player:
            state['results']['reacquired_player'] = True
            check('enemy_reacquires_living_player', ai.get_editor_property('target') == player)
            unreal.GameplayStatics.apply_damage(enemy, 1000.0, None, player, unreal.DamageType)
            state['enemy_dead_hits'] = ai.get_editor_property('successful_hits')
            transition('enemy_death_check')
        elif phase == 'enemy_death_check' and state['phase_time'] > 1.5:
            state['results']['enemy_death'] = {'health': state['enemy_health'].get_editor_property('health'),
                'state': combat_state, 'additional_hits': ai.get_editor_property('successful_hits') - state['enemy_dead_hits']}
            check('dead_enemy_stops_attacking', state['enemy_health'].get_editor_property('health') <= 0 and 'DEAD' in combat_state and ai.get_editor_property('successful_hits') == state['enemy_dead_hits'])
            finish()
    except BaseException:
        finish(traceback.format_exc())


observe.handle = unreal.register_slate_post_tick_callback(observe)
levels.editor_request_begin_play()
