"""One-system NPC check for Lvl_HeroSampleCrowd. Run through the editor MCP `execute_python` tool (it uses the
tool's top-level `await` and `call_tool`), with the crowd sample map open and PIE stopped.

It starts PIE, runs four short scenarios through UReflectionsNpcSubsystem, saves a PNG per scenario under
Saved/NpcUnified/, writes Saved/NpcUnified/verify.json and always stops PIE. About 40 seconds.

  A  A real Fireball lands on a civilian: civilians flee, the guard and the brave walk over.
  B  An enemy spawned during play (late enrolment) is hit from outside its sight radius and comes to fight.
  C  A lethal Fire Bolt on an NPC with no NPC_Ragdoll tag: it ragdolls from its archetype.
  D  SetInfection puts a host on game flow's infection meter and takes it off again; a killed enemy pays a coin.
  E  A hit that does not kill: damage, a lean away from the impact, the pose stays valid.
  F  Deaths with before/after pictures: a placed guard to a Fireball, a spawned soldier to a Fire Bolt.
Afterwards it counts pose warnings and watchdog repairs in the editor log for the run.
"""

import base64
import json
from pathlib import Path

OUT = Path(unreal.Paths.project_saved_dir()) / 'NpcUnified'
OUT.mkdir(parents=True, exist_ok=True)
result = {'checks': {}, 'shots': []}


def check(name, ok, detail=None):
    result['checks'][name] = {'ok': bool(ok), 'detail': detail}


def unwrap(value):
    return value['returnValue'] if isinstance(value, dict) and 'returnValue' in value else value


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
    await asyncio.sleep(1.0)
    W(1500.0, 500.0, 90.0)


if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
    result['abort'] = 'PIE is already running (someone else is testing); nothing was started.'
else:
    await call_tool('EditorToolset.EditorAppToolset.StartPIE')
    try:
        await hero_is_down()
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        player = unreal.GameplayStatics.get_player_pawn(world, 0)
        controller = player.get_controller()
        npcs = unreal.get_world_subsystem(world, unreal.ReflectionsNpcSubsystem)
        combat = player.get_component_by_class(unreal.ReflectionsSpellCombatComponent)
        flow_class = getattr(unreal, 'ReflectionsGameFlowSubsystem', None)
        flow = unreal.get_game_instance_subsystem(unreal.GameplayStatics.get_game_instance(world), flow_class) if flow_class else None

        def brain(actor):
            return actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent)

        def health(actor):
            return actor.get_component_by_class(unreal.ReflectionsHealthComponent).get_editor_property('health')

        def state(actor):
            b = brain(actor)
            archetype = b.get_active_archetype()
            return {'archetype': str(archetype.get_editor_property('archetype_id')) if archetype else None,
                    'reaction': b.get_editor_property('reaction').name,
                    'fear': round(b.get_editor_property('fear'), 2), 'health': health(actor)}

        def proxy_point(actor):
            for capsule in actor.get_components_by_class(unreal.CapsuleComponent):
                if capsule.get_name() == 'RuntimeNpcHitProxy':
                    return capsule.get_world_location()
            return actor.get_actor_location() + unreal.Vector(0, 0, 90)

        def place(actor, location):
            driver = brain(actor).get_locomotion_driver()
            if driver:
                driver.set_actor_location(driver.get_actor_location() + (location - actor.get_actor_location()), False, True)
            else:
                actor.set_actor_location(location, False, True)

        def face(point, yaw_offset=0.0):
            player_location = player.get_actor_location()
            rotation = unreal.MathLibrary.find_look_at_rotation(player_location, point)
            rotation.yaw += yaw_offset
            controller.set_control_rotation(rotation)

        def cast(spell, point):
            start = player.get_actor_location() + unreal.Vector(0, 0, 50)
            origin = unreal.Transform(location=start, rotation=unreal.Rotator(), scale=unreal.Vector(1, 1, 1))
            combat.release_spell_at(spell, origin, point, None)

        def body_state(actor):
            body = next((m for m in actor.get_components_by_class(unreal.SkeletalMeshComponent) if m.get_name() == 'Body'), None)
            if not body:
                return None
            info = {}
            probes = {
                'visible': lambda: body.is_visible(),
                'tick': lambda: body.is_component_tick_enabled(),
                'interval': lambda: round(body.get_component_tick_interval(), 3),
                'sim_any': lambda: body.is_any_simulating_physics(),
                'collision': lambda: body.get_collision_enabled().name,
                'anim': lambda: body.get_anim_instance().get_class().get_name() if body.get_anim_instance() else None,
                'parent': lambda: body.get_attach_parent().get_name() if body.get_attach_parent() else None,
                'leader': lambda: (body.get_editor_property('leader_pose_component').get_name()
                                   if body.get_editor_property('leader_pose_component') else None),
                'spine_z': lambda: round(body.get_socket_location('spine_04').z - actor.get_actor_location().z, 1),
                'rendered': lambda: actor.was_recently_rendered(0.3),
            }
            for key, probe in probes.items():
                try:
                    info[key] = probe()
                except Exception as error:
                    info[key] = 'n/a'
            return info

        def pelvis_height(actor):
            body = next(m for m in actor.get_components_by_class(unreal.SkeletalMeshComponent) if m.get_name() == 'Body')
            return round(body.get_center_of_mass('pelvis').z - actor.get_actor_location().z, 1)

        def lean(actor):
            rotation = actor.get_actor_rotation()
            return round(abs(rotation.pitch) + abs(rotation.roll), 1)

        async def kill_and_picture(tag, actor, spell, aim_feet):
            """Stands the player 450 cm north of the NPC, leaves it one hit from death, casts, pictures before and after."""
            spot = player.get_actor_location() + W(0, -450, -90)
            place(actor, spot)
            await asyncio.sleep(0.5)
            unreal.GameplayStatics.apply_damage(actor, max(0.0, health(actor) - 5.0), None, player, unreal.DamageType)
            face(proxy_point(actor), -7.0)
            await asyncio.sleep(0.25)
            await shot(tag + '_before')
            cast(spell, actor.get_actor_location() + unreal.Vector(0, 0, 30) if aim_feet else proxy_point(actor))
            await asyncio.sleep(1.6)
            origin, extent = actor.get_actor_bounds(False)
            player.set_actor_location(unreal.Vector(origin.x - 330, origin.y + 60, 90), False, True)
            await asyncio.sleep(0.25)
            face(unreal.Vector(origin.x, origin.y, 20.0), -6.0)
            await asyncio.sleep(0.25)
            await shot(tag + '_after')
            body = next(m for m in actor.get_components_by_class(unreal.SkeletalMeshComponent) if m.get_name() == 'Body')
            info = {'state': state(actor), 'simulating': body.is_any_simulating_physics(), 'pelvis_height': pelvis_height(actor),
                    'lean': lean(actor)}
            result.setdefault('F', {})[tag] = info
            check(tag + '_dead', info['state']['reaction'] == 'INCAPACITATED' and info['state']['health'] <= 0.0, info['state'])
            check(tag + '_ragdolled_on_ground', info['simulating'] and info['pelvis_height'] < 60.0, info)

        def diag(tag):
            result.setdefault('diag', {})[tag] = {label: body_state(a) for label, a in actors.items()}

        actors = {a.get_actor_label(): a for a in npcs.get_npc_actors()}
        diag('start')
        result['enrolled'] = {label: state(a) for label, a in actors.items()}
        check('enrolled_six', len(actors) >= 6, sorted(actors))

        # ---- A: fireball on a civilian ---------------------------------------------------------------
        # Staged in the empty south-west of the practice ground so nothing stands between caster and target.
        clerk = actors['Crowd Preview - Red 02']
        place(clerk, W(-700, -800, 0))
        place(actors['Crowd Preview - Red 01'], W(-900, -1000, 0))
        place(actors['BP_BridgeGuard'], W(-300, -1150, 0))
        player.set_actor_location(W(-700, -300, 90), False, True)
        await asyncio.sleep(0.4)
        clerk_health = health(clerk)
        point = clerk.get_actor_location() + unreal.Vector(0, 0, 30)
        face(point)
        await asyncio.sleep(0.2)
        cast(unreal.HeroSpell.FIRESTORM, point)
        await asyncio.sleep(1.4)
        after = {label: state(a) for label, a in actors.items()}
        result['A'] = after
        diag('after_fireball')
        check('A_pose_intact_after_hit', isinstance(result['diag']['after_fireball']['Crowd Preview - Red 02'].get('spine_z'), float)
              and result['diag']['after_fireball']['Crowd Preview - Red 02']['spine_z'] > 50.0,
              result['diag']['after_fireball']['Crowd Preview - Red 02'])
        await shot('A_fireball_civilians_flee')
        check('A_civilian_flees', after['Crowd Preview - Red 02']['reaction'] == 'FLEEING', after['Crowd Preview - Red 02'])
        check('A_timid_flees', after['Crowd Preview - Red 01']['reaction'] == 'FLEEING', after['Crowd Preview - Red 01'])
        check('A_guard_investigates', after['BP_BridgeGuard']['reaction'] == 'INVESTIGATING', after['BP_BridgeGuard'])
        check('A_fireball_damaged', after['Crowd Preview - Red 02']['health'] < clerk_health,
              [clerk_health, after['Crowd Preview - Red 02']['health']])

        # ---- B: late-spawned enemy fights back -------------------------------------------------------
        enemy_class = unreal.load_class(None, '/Game/Characters/CrowdMotion/SimpleRed/BridgeGuard/BP_BridgeGuard_SimpleRed.BP_BridgeGuard_SimpleRed_C')
        # A clear lane down the east edge: the player 1400 cm north of the enemy, outside its 1200 cm sight.
        player.set_actor_location(W(1500, 500, 90), False, True)
        spawn = unreal.Transform(location=W(1500, -900, 0), rotation=unreal.Rotator(0, 0, 90), scale=unreal.Vector(1, 1, 1))
        enemy = unreal.ReflectionsWorldLibrary.spawn_actor_into_world(world, enemy_class, spawn)
        enemy.set_editor_property('tags', [unreal.Name(tag) for tag in ('NPC_Reactive', 'NPC_HitProxy', 'NPC_SampleLocomotion', 'NPC_CombatEnemy')])
        await asyncio.sleep(1.0)
        diag('player_far_1s')
        check('B_late_enrolment', brain(enemy) is not None, None)
        motor = enemy.get_component_by_class(unreal.ReflectionsNpcCombatComponent)
        check('B_enemy_archetype', brain(enemy) and state(enemy)['archetype'] == 'Enemy', state(enemy) if brain(enemy) else None)
        check('B_idle_out_of_sight', state(enemy)['reaction'] == 'CALM', state(enemy))
        player_health = player.get_component_by_class(unreal.ReflectionsHealthComponent)
        health_before = player_health.get_editor_property('health') if player_health else None
        face(proxy_point(enemy))
        await asyncio.sleep(0.2)
        cast(unreal.HeroSpell.FIRE, proxy_point(enemy))
        samples = []
        captured = False
        for _ in range(60):
            await asyncio.sleep(0.25)
            sample = {'reaction': state(enemy)['reaction'], 'health': health(enemy),
                      'combat': motor.get_editor_property('combat_state').name if motor else None,
                      'attacks': motor.get_editor_property('attacks_started') if motor else 0,
                      'hits': motor.get_editor_property('successful_hits') if motor else 0,
                      'distance': round((enemy.get_actor_location() - player.get_actor_location()).length())}
            samples.append(sample)
            if sample['attacks'] >= 1 and not captured:
                face(proxy_point(enemy), -14.0)
                await asyncio.sleep(0.15)
                await shot('B_enemy_fights_back')
                captured = True
            if sample['hits'] >= 1:
                break
        result['B'] = {'first': samples[0], 'last': samples[-1], 'count': len(samples)}
        diag('after_enemy_fight')
        if not captured:
            face(proxy_point(enemy))
            await asyncio.sleep(0.1)
            await shot('B_enemy_fights_back')
        check('B_enemy_hit_and_angry', any(s['reaction'] == 'ATTACKING' for s in samples), samples[0])
        check('B_enemy_closed_in', samples[-1]['distance'] < samples[0]['distance'] - 200, [samples[0]['distance'], samples[-1]['distance']])
        check('B_enemy_struck_player', samples[-1]['hits'] >= 1, samples[-1])
        if player_health:
            check('B_player_lost_health', player_health.get_editor_property('health') < health_before,
                  [health_before, player_health.get_editor_property('health')])

        # ---- D (part 1): a killed enemy pays a coin --------------------------------------------------
        def coins():
            return sum(unreal.ReflectionsWorldLibrary.get_coins(world, w) for w in
                       (unreal.ReflectionsWorld.GRAY, unreal.ReflectionsWorld.RED, unreal.ReflectionsWorld.WHITE))
        coins_before = coins()
        unreal.GameplayStatics.apply_damage(enemy, 999.0, None, player, unreal.DamageType)
        await asyncio.sleep(0.3)
        check('D_enemy_paid_coin', coins() == coins_before + 1, [coins_before, coins()])

        # ---- C: lethal hit ragdolls (no NPC_Ragdoll tag on this one) ---------------------------------
        victim = actors['Crowd Preview - Red 01']
        place(victim, player.get_actor_location() + W(0, -420, -90))
        await asyncio.sleep(0.3)
        unreal.GameplayStatics.apply_damage(victim, max(0.0, health(victim) - 5.0), None, player, unreal.DamageType)
        body = next(m for m in victim.get_components_by_class(unreal.SkeletalMeshComponent) if m.get_name() == 'Body')
        face(proxy_point(victim), -7.0)
        await asyncio.sleep(0.2)
        await shot('C_walker_before')
        cast(unreal.HeroSpell.FIRE, proxy_point(victim))
        await asyncio.sleep(0.7)
        speed = body.get_physics_linear_velocity('pelvis').length() if body.is_simulating_physics() else 0.0
        await asyncio.sleep(0.8)
        # Step to the side of the body and look at it for the picture.
        origin, extent = victim.get_actor_bounds(False)
        player.set_actor_location(unreal.Vector(origin.x - 330, origin.y + 60, 90), False, True)
        await asyncio.sleep(0.25)
        face(unreal.Vector(origin.x, origin.y, 20.0), -6.0)
        await asyncio.sleep(0.25)
        await shot('C_lethal_hit_ragdoll')
        result['C'] = {'state': state(victim), 'simulating': body.is_simulating_physics(), 'pelvis_speed': round(speed, 1),
                       'pelvis_height': pelvis_height(victim), 'tagged_ragdoll': victim.actor_has_tag('NPC_Ragdoll')}
        check('C_dead', result['C']['state']['reaction'] == 'INCAPACITATED' and result['C']['state']['health'] <= 0.0, result['C']['state'])
        check('C_ragdoll_from_archetype', result['C']['simulating'] and not result['C']['tagged_ragdoll'], result['C'])
        check('C_body_on_ground', result['C']['pelvis_height'] < 60.0, result['C']['pelvis_height'])

        # ---- E: a nonlethal hit reads (flinch, stumble, flash) --------------------------------------
        struck = actors['Crowd Preview - Red 03']
        player.set_actor_location(W(1200, 1300, 90), False, True)
        place(struck, W(1200, 900, 0))
        await asyncio.sleep(0.4)
        struck_health = health(struck)
        struck_before = struck.get_actor_location()
        face(proxy_point(struck), -5.0)
        await asyncio.sleep(0.15)
        cast(unreal.HeroSpell.FIRE, proxy_point(struck))
        struck_body = next(m for m in struck.get_components_by_class(unreal.SkeletalMeshComponent) if m.get_name() == 'Body')
        flinched = False
        for _ in range(40):
            await asyncio.sleep(0.03)
            if health(struck) < struck_health:
                leans = []
                for _ in range(6):
                    await asyncio.sleep(0.04)
                    leans.append(lean(struck))
                flinched = max(leans) > 2.0
                await shot('E_nonlethal_hit_reads')
                break
        await asyncio.sleep(0.5)
        diag('after_E')
        result['E'] = {'health': [struck_health, health(struck)], 'state': state(struck), 'flinch_physics': flinched,
                       'stumbled_cm': round((struck.get_actor_location() - struck_before).length())}
        check('E_hit_damaged', health(struck) < struck_health, result['E']['health'])
        check('E_leans_away', flinched, result['E'])
        check('E_upright_again', lean(struck) < 1.0, lean(struck))
        check('E_pose_intact_after_hit', isinstance(result['diag']['after_E']['Crowd Preview - Red 03'].get('spine_z'), float)
              and result['diag']['after_E']['Crowd Preview - Red 03']['spine_z'] > 50.0, result['diag']['after_E']['Crowd Preview - Red 03'])
        check('E_brave_fights_back', result['E']['state']['reaction'] == 'ATTACKING', result['E']['state'])

        # ---- D (part 2): infection meter -------------------------------------------------------------
        host = actors['Crowd Preview - White 02']
        place(host, player.get_actor_location() + W(-350, 250, -90))
        await asyncio.sleep(0.3)
        count_before = flow.get_infection_count() if flow else None
        friendly_before = host.actor_has_tag('Friendly')
        changed = npcs.set_infection(host, unreal.ReflectionsNpcInfection.INFECTED, None)
        await asyncio.sleep(1.2)
        infected = state(host)
        count_infected = flow.get_infection_count() if flow else None
        face(proxy_point(host))
        await asyncio.sleep(0.2)
        await shot('D_infected_host_on_meter')
        result['D'] = {'changed': changed, 'state': infected, 'meter': [count_before, count_infected],
                       'friendly': [friendly_before, host.actor_has_tag('Friendly')],
                       'on_meter_flag': brain(host).get_editor_property('on_infection_meter')}
        check('D_behaves_infected', infected['archetype'] == 'Infected', infected)
        check('D_infected_hunts_player', infected['reaction'] == 'ATTACKING', infected)
        check('D_friendly_lifted', friendly_before and not host.actor_has_tag('Friendly'), result['D']['friendly'])
        if flow:
            check('D_meter_counts_host', count_infected == count_before + 1, result['D']['meter'])
        else:
            check('D_meter_counts_host', False, 'ReflectionsGameFlowSubsystem is not loaded in this editor build')
        npcs.set_infection(host, unreal.ReflectionsNpcInfection.NONE, None)
        await asyncio.sleep(0.2)
        if flow:
            check('D_meter_cured', flow.get_infection_count() == count_before, flow.get_infection_count())
        check('D_friendly_restored', host.actor_has_tag('Friendly') == friendly_before, host.actor_has_tag('Friendly'))

        # ---- F: deaths with before/after pictures ---------------------------------------------------
        player.set_actor_location(W(-1200, 1300, 90), False, True)
        await kill_and_picture('F_guard_fireball', actors['BP_BridgeGuard'], unreal.HeroSpell.FIRESTORM, True)
        soldier_class = unreal.load_class(None, '/Game/Characters/WhiteLondon/CrowdPreview/BP_WhiteLook_06_GuardBoldRunes.BP_WhiteLook_06_GuardBoldRunes_C')
        player.set_actor_location(W(-1200, 300, 90), False, True)
        place_at = unreal.Transform(location=W(-1200, -150, 0), rotation=unreal.Rotator(0, 0, 90), scale=unreal.Vector(1, 1, 1))
        soldier = unreal.ReflectionsWorldLibrary.spawn_actor_into_world(world, soldier_class, place_at)
        soldier.set_editor_property('tags', [unreal.Name(tag) for tag in ('NPC_HitProxy', 'NPC_SampleLocomotion')])
        npcs.enroll_actor(soldier, npcs.find_archetype('Soldier'))
        await asyncio.sleep(1.5)
        check('F_soldier_enrolled', state(soldier)['archetype'] == 'Soldier' and health(soldier) == 70.0, state(soldier))
        await kill_and_picture('F_soldier_firebolt', soldier, unreal.HeroSpell.FIRE, False)
    except Exception as error:
        import_error = repr(error)
        result['error'] = import_error
    finally:
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')

try:
    log_path = Path(unreal.Paths.project_log_dir()) / 'reflections.log'
    text = log_path.read_text(encoding='utf-8', errors='replace')
    marker = text.rfind('NPC system: enrolled')
    tail = text[marker:] if marker >= 0 else text[-400000:]
    result['log'] = {'pose_repairs': tail.count('body bone buffers were incomplete'),
                     'pose_not_ready': tail.count('body pose not ready'),
                     'bone_out_of_range': tail.count('GetBoneMatrix : BoneIndex'),
                     'bone_index_oob': tail.count('Bone index out of bounds')}
    check('log_no_empty_pose', result['log']['bone_out_of_range'] == 0 and result['log']['pose_not_ready'] == 0, result['log'])
except Exception as error:
    result['log'] = repr(error)

result['passed'] = sum(1 for c in result['checks'].values() if c['ok'])
result['failed'] = sorted(name for name, c in result['checks'].items() if not c['ok'])
(OUT / 'verify.json').write_text(json.dumps(result, indent=2, default=str))
json.dumps(result, default=str)
