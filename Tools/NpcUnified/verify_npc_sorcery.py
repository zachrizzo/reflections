"""Tarnished spellcasting, weapon props and walker strike montages: the check to pass BEFORE the archetype assets
are re-saved (which switches these on for everyone). Lvl_HeroSampleCrowd open, PIE stopped. One PIE session, about
50 seconds; it always stops PIE. Run through the editor MCP `execute_python` tool (top-level `await`, `call_tool`).

Everything is switched on IN MEMORY ONLY: the Infected, Guard and Enemy archetype assets are reset to their built-ins
and not saved. The caller re-syncs and saves the ten archetypes if this passes, or reloads the packages if it fails.

  L  Look pools are side-aware: Frostside gets only the rag looks, Giltside only the red ones, a side without a
     look for a role uses its own nearest role, and Pewterside borrows Giltside's.
  T  A tarnished NPC 12 m from the player stops, faces the player and casts: projectiles appear, the player loses
     health, the casts are spaced by the cooldown, and the NPC stays at range instead of walking into the player.
  X  Next to the player the same NPC does something too (burst or claws): the player keeps losing health.
  W  A Guard spawned by archetype holds a sword mesh in its hand (pictured close up for grip and scale).
  D  Only when a strike clip for the hidden walker exists (AS_Melee_Sword_Slash_LR_Walker): an Enemy's strike plays
     a montage on the walker while the visible body stays on its animation blueprint, and killing it mid-swing is
     an ordinary ragdoll death. This is the case that crashed the editor with the old clip route, so it is run
     last, and only when RUN_DIE_MID_STRIKE is True (default True; set False to skip).
Result: Saved/NpcUnified/verify_sorcery.json and T_*/W_*/D_* pictures.
"""

import base64
import json
import os
import time
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


open_map = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world().get_name()
LOG_PATH = Path(unreal.Paths.project_log_dir()) / 'reflections.log'
try:
    log_start = LOG_PATH.stat().st_size
except OSError:
    log_start = 0


def console(command, world=None):
    unreal.SystemLibrary.execute_console_command(world or unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world(), command)


if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
    result['abort'] = 'PIE is already running (someone else is testing); nothing was started.'
elif open_map != 'Lvl_HeroSampleCrowd':
    result['abort'] = 'The editor has %s open, not Lvl_HeroSampleCrowd. Nothing was started.' % open_map
else:
    # The squad that patrols by the player start from train #11 would join in: this check wants an empty start.
    console('Squads.StartPatrol 0')
    await call_tool('EditorToolset.EditorAppToolset.StartPIE')
    try:
        await asyncio.sleep(3.0)
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        console('Squads.Clear', world)
        player = unreal.GameplayStatics.get_player_pawn(world, 0)
        controller = player.get_controller()
        npcs = unreal.get_world_subsystem(world, unreal.ReflectionsNpcSubsystem)
        player_health = player.get_component_by_class(unreal.ReflectionsHealthComponent)

        def brain(actor):
            return actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent)

        def health(actor):
            return actor.get_component_by_class(unreal.ReflectionsHealthComponent).get_editor_property('health')

        def hero_health():
            return player_health.get_editor_property('health') if player_health else None

        def body_of(actor):
            return next(m for m in actor.get_components_by_class(unreal.SkeletalMeshComponent) if m.get_name() == 'Body')

        def face(point):
            controller.set_control_rotation(unreal.MathLibrary.find_look_at_rotation(player.get_actor_location(), point))

        def flat_distance(a, b):
            delta = a.get_actor_location() - b.get_actor_location()
            return round(unreal.Vector(delta.x, delta.y, 0).length())

        def projectiles_of(owner):
            found = []
            for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
                name = actor.get_class().get_name()
                if ('SpellProjectile' in name or 'Tarnish' in name) and actor.get_owner() == owner:
                    found.append(actor.get_name())
            return found

        # Switched on in memory only.
        switched = {}
        for archetype_id in ('Infected', 'Guard', 'Enemy'):
            asset = npcs.find_archetype(archetype_id)
            asset.reset_to_built_in()
            combat = asset.get_editor_property('combat')
            switched[archetype_id] = {'casts_at_player': combat.get_editor_property('casts_at_player'),
                                      'spells': [s.name for s in combat.get_editor_property('ranged_spells')],
                                      'range': [combat.get_editor_property('ranged_min_range'), combat.get_editor_property('ranged_max_range')],
                                      'walker_strikes': len(combat.get_editor_property('walker_attack_animations')),
                                      'strike_clips_on_body': len(combat.get_editor_property('attack_animations')),
                                      'weapon': str(combat.get_editor_property('weapon_prop').get_asset_name()) if hasattr(combat.get_editor_property('weapon_prop'), 'get_asset_name') else str(combat.get_editor_property('weapon_prop'))}
        result['switched_on_in_memory'] = switched
        result['tarnish_caster_in_build'] = hasattr(unreal, 'ReflectionsTarnishCasterComponent')
        check('T_builtin_makes_the_tarnished_casters', switched['Infected']['casts_at_player'] and switched['Infected']['spells'], switched['Infected'])

        # ---- L: side-aware look pools ---------------------------------------------------------------
        if hasattr(npcs, 'get_looks_for_side'):
            def pool(archetype_id, side):
                names = []
                for look in npcs.get_looks_for_side(archetype_id, side):
                    text = str(look.get_path_name()) if hasattr(look, 'get_path_name') else str(look)
                    names.append(text.rsplit('.', 1)[-1].replace("'", '').replace('>', ''))
                return names

            def of_side(names, words):
                return bool(names) and all(any(word in name for word in words) for name in names)

            frost = ('Frost', 'WhiteLook')
            gilt = ('Gilt', 'SimpleRed')
            pools = {key: pool(*key.split('@')) for key in ('Civilian@Giltside', 'Civilian@Frostside', 'Civilian@Pewterside', 'Guard@Giltside',
                                                           'Guard@Frostside', 'Soldier@Frostside', 'Soldier@Giltside', 'SoldierCaster@Frostside')}
            result['L'] = {'pools': pools, 'side_here': str(npcs.get_side_at(player.get_actor_location()))}
            check('L_giltside_gets_only_red', all(of_side(pools[k], gilt) for k in ('Civilian@Giltside', 'Guard@Giltside', 'Soldier@Giltside')), pools)
            check('L_frostside_gets_only_rags', all(of_side(pools[k], frost) for k in ('Civilian@Frostside', 'Guard@Frostside', 'Soldier@Frostside', 'SoldierCaster@Frostside')), pools)
            check('L_pewterside_borrows_giltside', of_side(pools['Civilian@Pewterside'], gilt), pools['Civilian@Pewterside'])
        else:
            result['L'] = 'this build has no side-aware look pools'

        # ---- T: a tarnished NPC casts at the player from range -------------------------------------
        player.set_actor_location(unreal.Vector(1500, 500, 90), False, True)
        sorcerer = npcs.spawn_npc('Civilian', unreal.Vector(1500, -700, 0), 90.0, None)
        await asyncio.sleep(1.2)
        face(sorcerer.get_actor_location() + unreal.Vector(0, 0, 100))
        start_health = hero_health()
        npcs.set_infection(sorcerer, unreal.ReflectionsNpcInfection.INFECTED, None)
        seen = set()
        cast_times = []
        samples = []
        pictured = False
        began = time.perf_counter()
        for step in range(48):
            await asyncio.sleep(0.25)
            live = projectiles_of(sorcerer)
            fresh = [name for name in live if name not in seen]
            if fresh:
                cast_times.append(round(time.perf_counter() - began, 2))
                seen.update(fresh)
            lights = len(sorcerer.get_components_by_class(unreal.PointLightComponent))
            samples.append({'t': round(step * 0.25, 2), 'reaction': brain(sorcerer).get_editor_property('reaction').name,
                            'distance': flat_distance(sorcerer, player), 'lights': lights, 'projectiles': len(live), 'hero': hero_health()})
            if (fresh or lights > 0) and not pictured and step > 2:
                pictured = True
                await shot('T_tarnished_casts')
        result['T'] = {'casts_seen': len(seen), 'cast_times': cast_times, 'hero_health': [start_health, hero_health()],
                       'distance_range': [min(s['distance'] for s in samples), max(s['distance'] for s in samples)],
                       'first': samples[0], 'last': samples[-1],
                       'archetype': str(brain(sorcerer).get_active_archetype().get_editor_property('archetype_id'))}
        gaps = [round(b - a, 2) for a, b in zip(cast_times, cast_times[1:])]
        result['T']['gaps'] = gaps
        check('T_tarnished_casts_at_the_player', len(seen) >= 2, result['T'])
        check('T_player_loses_health', start_health is not None and hero_health() < start_health, result['T']['hero_health'])
        check('T_stays_at_range', result['T']['distance_range'][0] >= 350, result['T']['distance_range'])
        check('T_casts_are_spaced', not gaps or min(gaps) >= 2.0, gaps)
        await shot('T_after_casts')

        # ---- X: right next to the player it still hurts --------------------------------------------
        driver = brain(sorcerer).get_locomotion_driver()
        near = player.get_actor_location() + unreal.Vector(0, -230, 0)
        if driver:
            driver.set_actor_location(driver.get_actor_location() + (unreal.Vector(near.x, near.y, sorcerer.get_actor_location().z) - sorcerer.get_actor_location()), False, True)
        close_health = hero_health()
        await asyncio.sleep(6.0)
        result['X'] = {'hero_health': [close_health, hero_health()], 'distance': flat_distance(sorcerer, player),
                       'reaction': brain(sorcerer).get_editor_property('reaction').name}
        check('X_close_up_it_still_attacks', hero_health() < close_health, result['X'])
        await shot('X_close_up')
        unreal.GameplayStatics.apply_damage(sorcerer, 999.0, None, None, unreal.DamageType)
        await asyncio.sleep(0.5)

        # ---- W: a guard holds a sword ----------------------------------------------------------------
        player.set_actor_location(unreal.Vector(-700, 350, 90), False, True)
        guard = npcs.spawn_npc('Guard', unreal.Vector(-700, 120, 0), 90.0, None)
        await asyncio.sleep(1.5)
        props = []
        for part in guard.get_components_by_class(unreal.StaticMeshComponent):
            mesh = part.get_editor_property('static_mesh')
            if mesh:
                parent = part.get_attach_parent()
                bounds = mesh.get_bounds().box_extent
                props.append({'mesh': mesh.get_name(), 'parent': parent.get_name() if parent else None, 'socket': str(part.get_attach_socket_name()),
                              'size_cm': [round(bounds.x * 2), round(bounds.y * 2), round(bounds.z * 2)],
                              'above_feet': round(part.get_world_location().z - guard.get_actor_location().z)})
        result['W'] = {'class': guard.get_class().get_name(), 'props': props}
        check('W_guard_holds_a_sword', any('Sword' in p['mesh'] and p['parent'] == 'Body' for p in props), props)
        face(guard.get_actor_location() + unreal.Vector(0, 0, 105))
        await asyncio.sleep(0.3)
        await shot('W_guard_with_sword')

        # ---- D: strike montage on the walker, and dying mid-swing -----------------------------------
        walker_clip = os.path.exists(os.path.join(unreal.Paths.project_content_dir(), 'Combat', 'Melee', 'AS_Melee_Sword_Slash_LR_Walker.uasset'))
        result['D'] = {'walker_clip_on_disk': walker_clip, 'walker_strikes_listed': switched['Enemy']['walker_strikes']}
        if walker_clip and switched['Enemy']['walker_strikes'] > 0 and globals().get('RUN_DIE_MID_STRIKE', True):
            player.set_actor_location(unreal.Vector(1500, 500, 90), False, True)
            fighter = npcs.spawn_npc('Enemy', unreal.Vector(1500, 150, 0), 90.0, None)
            await asyncio.sleep(1.0)
            face(fighter.get_actor_location() + unreal.Vector(0, 0, 100))
            motor = fighter.get_component_by_class(unreal.ReflectionsNpcCombatComponent)
            body = body_of(fighter)
            walker = brain(fighter).get_locomotion_driver()
            anim = walker.get_editor_property('mesh').get_anim_instance() if walker else None
            modes = set()
            montage_seen = False
            killed_mid_swing = False
            for step in range(120):
                await asyncio.sleep(0.05)
                modes.add(body.get_editor_property('animation_mode').name)
                playing = bool(anim and anim.is_any_montage_playing())
                state = motor.get_editor_property('combat_state').name if motor else None
                if playing and not montage_seen:
                    montage_seen = True
                    await shot('D_strike_montage')
                if playing and state == 'WINDUP' and motor.get_editor_property('attacks_started') >= 2:
                    unreal.GameplayStatics.apply_damage(fighter, 999.0, None, player, unreal.DamageType)
                    killed_mid_swing = True
                    break
            await asyncio.sleep(1.8)
            try:
                pelvis = round(body.get_center_of_mass('pelvis').z - fighter.get_actor_location().z, 1)
            except Exception:
                pelvis = None
            result['D'].update({'montage_seen': montage_seen, 'body_modes': sorted(modes), 'killed_mid_swing': killed_mid_swing,
                                'attacks': motor.get_editor_property('attacks_started') if motor else None,
                                'simulating': body.is_any_simulating_physics(), 'pelvis': pelvis,
                                'reaction': brain(fighter).get_editor_property('reaction').name})
            check('D_strike_plays_on_the_walker', montage_seen, result['D'])
            check('D_body_never_leaves_its_blueprint', modes and all('BLUEPRINT' in m for m in modes), sorted(modes))
            check('D_killed_mid_swing_is_an_ordinary_death', killed_mid_swing and result['D']['simulating'] and result['D']['reaction'] == 'INCAPACITATED'
                  and pelvis is not None and pelvis < 60.0, result['D'])
            await shot('D_after_death_mid_swing')
        else:
            result['D']['skipped'] = 'no walker strike clip in the project yet' if not walker_clip else 'not listed or switched off'
    except Exception as error:
        import traceback
        result['error'] = repr(error)
        result['trace'] = traceback.format_exc()[-1500:]
    finally:
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')
        console('Squads.StartPatrol 1')

try:
    # Only what this run wrote: the log is read from where it stood before PIE started.
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
(OUT / 'verify_sorcery.json').write_text(json.dumps(result, indent=2, default=str))
json.dumps(result, default=str)
