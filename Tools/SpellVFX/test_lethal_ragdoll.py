"""Run inside an existing PIE session after the combat module is built.

Call run('direct') or run('blast').  The test moves actors only in PIE and
fires a real projectile at a nearly defeated tagged NPC.  The JSON samples
health, death state, individual body velocities and the nearby NPC's health.
"""

import json
import traceback
from pathlib import Path

import unreal


def run(case):
    if case not in ('direct', 'blast'):
        raise ValueError('Expected direct or blast')
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if not world:
        raise RuntimeError('Begin a Play in Editor session before running the test')
    player = unreal.GameplayStatics.get_player_pawn(world, 0)
    actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
    npcs = {actor.get_actor_label(): actor for actor in actors
            if actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent)}
    target = npcs['Crowd Preview - White 01']
    bystander = npcs['Crowd Preview - White 02'] if case == 'blast' else None
    for actor in npcs.values():
        brain = actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent)
        driver = brain.get_locomotion_driver()
        if driver:
            driver.get_character_movement().disable_movement()
        # These independent test fixtures are held still while the projectile travels.
        brain.set_component_tick_enabled(False)

    def position(actor, location):
        brain = actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent)
        driver = brain.get_locomotion_driver()
        delta = location - actor.get_actor_location()
        if driver:
            driver.set_actor_location(driver.get_actor_location() + delta, False, True)
        else:
            actor.set_actor_location(location, False, True)

    for actor in npcs.values():
        position(actor, unreal.Vector(4000, 1500, 0))
    position(target, unreal.Vector(400, 0, 0))
    if bystander:
        position(bystander, unreal.Vector(430, 120, 0))
    player.set_actor_location(unreal.Vector(0, 0, 90), False, True)
    health = target.get_component_by_class(unreal.ReflectionsHealthComponent)
    body = next(part for part in target.get_components_by_class(unreal.SkeletalMeshComponent)
                if part.get_name() == 'Body')
    proxy = next(part for part in target.get_components_by_class(unreal.CapsuleComponent)
                 if part.get_name() == 'RuntimeNpcHitProxy')
    brain = target.get_component_by_class(unreal.ReflectionsNpcReactionComponent)
    if not target.actor_has_tag('NPC_Ragdoll') or not brain.get_editor_property('enable_ragdoll_on_death'):
        raise RuntimeError('The test target is not opted into death ragdoll')
    unreal.GameplayStatics.apply_damage(target, 95, None, player, unreal.DamageType)
    origin = proxy.get_world_location() - unreal.Vector(300, 0, 0)
    spell = unreal.HeroSpell.FIRE if case == 'direct' else unreal.HeroSpell.FIRESTORM
    combat = player.get_component_by_class(unreal.ReflectionsSpellCombatComponent)
    result = {'case': case, 'health_before': health.get_editor_property('health'),
              'samples': [], 'target': target.get_actor_label()}
    if bystander:
        other_health = bystander.get_component_by_class(unreal.ReflectionsHealthComponent)
        result['bystander_health_before'] = other_health.get_editor_property('health')
    output = Path(unreal.Paths.project_intermediate_dir()) / 'NpcReactions' / ('lethal-' + case + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    combat.release_spell(spell, unreal.Transform(location=origin, rotation=unreal.Rotator(),
                                                scale=unreal.Vector(1, 1, 1)))
    state = {'time': 0.0}

    def tick(delta):
        try:
            state['time'] += delta
            sample = {'time': round(state['time'], 3), 'health': health.get_editor_property('health'),
                      'reaction': str(brain.get_editor_property('reaction')),
                      'body_simulating': body.is_simulating_physics(), 'bones': {}}
            for bone in ('pelvis', 'upperarm_l', 'upperarm_r', 'lowerarm_l', 'lowerarm_r', 'head'):
                if body.is_simulating_physics(bone):
                    velocity = body.get_physics_linear_velocity(bone)
                    sample['bones'][bone] = [round(velocity.x, 2), round(velocity.y, 2), round(velocity.z, 2)]
            if bystander:
                sample['bystander_health'] = other_health.get_editor_property('health')
            if len(result['samples']) < 160:
                result['samples'].append(sample)
            if state['time'] >= 1.5:
                result['health_after'] = health.get_editor_property('health')
                result['body_simulating'] = body.is_simulating_physics()
                result['reaction'] = str(brain.get_editor_property('reaction'))
                output.write_text(json.dumps(result, indent=2))
                unreal.unregister_slate_post_tick_callback(tick.handle)
        except Exception:
            result['error'] = traceback.format_exc()
            output.write_text(json.dumps(result, indent=2))
            unreal.unregister_slate_post_tick_callback(tick.handle)

    tick.handle = unreal.register_slate_post_tick_callback(tick)
    return str(output)
