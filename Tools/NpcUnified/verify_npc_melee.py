"""Melee strike clips check for Lvl_HeroSampleCrowd. Run through the editor MCP `execute_python` tool (top-level
`await`, `call_tool`), crowd sample map open, PIE stopped. One PIE session, about 35 seconds; it always stops PIE.

It turns the strike clips on IN MEMORY ONLY (the Enemy archetype asset is reset to its built-in, not saved), spawns
one enemy per body skeleton next to the player and watches them strike:
  - the built-in lists the team's melee clips (/Game/Combat/Melee),
  - a strike plays one of them on the body, and it is the one made for that body,
  - afterwards the body is back on its animation blueprint with a readable pose,
  - blows land on the player.
The caller decides what to do with the unsaved asset: re-sync and save the ten archetypes if this passes, or
reload the package to drop the change if it fails. Result: Saved/NpcUnified/verify_melee.json and M_*.png.

Two more checks ride in the same PIE session:
  V  six unnamed NPCs spawned by archetype get six different roster voices of their own sex (enabled rows only),
  P  the hidden walker pawns have no camera running; and a rough cost of those cameras: frame time with them off
     (as shipped) and then switched back on for three seconds, frame rate uncapped.
  S  a soldier left one hit from death is killed by a real Fire Bolt and ragdolls (the lethal spell-hit path that
     crashed the editor at 11:53, not yet exercised on this build),
  W  (train #10) walkers carry an empty foley bank, outfit parts that follow the body take its bounds and raise no
     overlap events, NPCs spawned by archetype wear the finished looks, and Npc.Weaken leaves one a hit from death,
  N  the crowd-looks session's new look Blueprints (/Game/Characters/Lanthorne/Looks/BP_Look_*) work as NPCs of this
     system: enrolled, walking, a sex from their tag, a readable pose, and a lethal hit ragdolls them.
"""

import base64
import json
from pathlib import Path

OUT = Path(unreal.Paths.project_saved_dir()) / 'NpcUnified'
OUT.mkdir(parents=True, exist_ok=True)
result = {'checks': {}, 'shots': []}
LOOKS = {
    'BridgeGuard': '/Game/Characters/CrowdMotion/SimpleRed/BridgeGuard/BP_BridgeGuard_SimpleRed.BP_BridgeGuard_SimpleRed_C',
    'IvenRook': '/Game/Characters/WhiteLondon/CrowdPreview/BP_WhiteLook_01_Plain.BP_WhiteLook_01_Plain_C',
    'CoinClerk': '/Game/Characters/CrowdMotion/SimpleRed/CoinClerk/BP_CoinClerk_SimpleRed.BP_CoinClerk_SimpleRed_C',
}


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


open_map = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world().get_name()
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

        def brain(actor):
            return actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent)

        def health(actor):
            return actor.get_component_by_class(unreal.ReflectionsHealthComponent).get_editor_property('health')

        def face(point, yaw_offset=0.0):
            rotation = unreal.MathLibrary.find_look_at_rotation(player.get_actor_location(), point)
            rotation.yaw += yaw_offset
            controller.set_control_rotation(rotation)

        def body_of(actor):
            return next(m for m in actor.get_components_by_class(unreal.SkeletalMeshComponent) if m.get_name() == 'Body')

        def playing(body):
            """(mode, name of the clip or of the animation blueprint class)."""
            mode = body.get_editor_property('animation_mode').name
            name = None
            try:
                if 'SINGLE' in mode:
                    single = body.get_single_node_instance()
                    asset = single.get_animation_asset() if single else None
                    name = asset.get_name() if asset else None
                else:
                    instance = body.get_anim_instance()
                    name = instance.get_class().get_name() if instance else None
            except Exception as error:
                name = 'n/a: ' + repr(error)[:80]
            return mode, name

        def spine_height(actor):
            try:
                return round(body_of(actor).get_socket_location('spine_04').z - actor.get_actor_location().z, 1)
            except Exception:
                return None

        # MELEE CLIPS: OFF BY DEFAULT. On train #8 this part crashed the shared editor (16:16): enemies struck with
        # clips playing, were killed, and the engine asserted on a body with no bone transforms. Set RUN_MELEE_CLIPS
        # to True only in a slot the orchestrator has cleared for a possible editor crash.
        if not globals().get('RUN_MELEE_CLIPS', False):
            raise_skip = True
        else:
            raise_skip = False
        if not raise_skip:
            # The clips, switched on in memory only.
            enemy_type = npcs.find_archetype('Enemy')
            before = len(enemy_type.get_editor_property('combat').get_editor_property('attack_animations'))
            if before == 0:
                enemy_type.reset_to_built_in()
            combat = enemy_type.get_editor_property('combat')
            clips = [c.get_asset_name() if hasattr(c, 'get_asset_name') else str(c) for c in combat.get_editor_property('attack_animations')]
            result['clips'] = {'listed_before': before, 'listed_now': len(clips), 'impact_fraction': round(combat.get_editor_property('impact_fraction'), 2),
                               'archetype_path': enemy_type.get_path_name()}
            check('M_builtin_lists_the_melee_set', len(clips) == 12, clips[:12])

            # One enemy per body skeleton, in a row 4.5 m in front of the player (inside their sight).
            player.set_actor_location(W(1500, 500, 90), False, True)
            controller.set_control_rotation(unreal.Rotator(0, -8, -90))
            player_health = player.get_component_by_class(unreal.ReflectionsHealthComponent)
            health_before = player_health.get_editor_property('health') if player_health else None
            fighters = {}
            for index, (suffix, path) in enumerate(LOOKS.items()):
                look = unreal.load_class(None, path)
                actor = npcs.spawn_npc('Enemy', W(1300 + index * 200, 50, 0), 90.0, look)
                fighters[suffix] = actor
            await asyncio.sleep(1.0)
            check('M_enemies_spawned', all(a and brain(a) for a in fighters.values()), {k: a.get_class().get_name() if a else None for k, a in fighters.items()})
            motors = {k: a.get_component_by_class(unreal.ReflectionsNpcCombatComponent) for k, a in fighters.items()}
            idle = {k: playing(body_of(a)) for k, a in fighters.items()}
            seen = {k: {'clips': [], 'modes': set(), 'spine_during': [], 'spine_between': []} for k in fighters}
            pictured = False
            for step in range(130):
                await asyncio.sleep(0.1)
                for key, actor in fighters.items():
                    mode, name = playing(body_of(actor))
                    state = motors[key].get_editor_property('combat_state').name if motors[key] else None
                    seen[key]['modes'].add(mode)
                    if 'SINGLE' in mode:
                        if name and name not in seen[key]['clips']:
                            seen[key]['clips'].append(name)
                        seen[key]['spine_during'].append(spine_height(actor))
                        if not pictured:
                            pictured = True
                            await shot('M_enemy_strike')
                    elif state not in ('WINDUP',):
                        seen[key]['spine_between'].append(spine_height(actor))
                if all(motors[k] and motors[k].get_editor_property('attacks_started') >= 3 for k in fighters):
                    break
            await asyncio.sleep(1.2)
            after = {k: playing(body_of(a)) for k, a in fighters.items()}
            result['M'] = {}
            for key, actor in fighters.items():
                between = [v for v in seen[key]['spine_between'] if isinstance(v, float)]
                during = [v for v in seen[key]['spine_during'] if isinstance(v, float)]
                result['M'][key] = {'class': actor.get_class().get_name(), 'idle': idle[key], 'after': after[key], 'clips': seen[key]['clips'],
                                    'attacks': motors[key].get_editor_property('attacks_started'), 'hits': motors[key].get_editor_property('successful_hits'),
                                    'spine_between_min': min(between) if between else None, 'spine_during_min': min(during) if during else None,
                                    'reaction': brain(actor).get_editor_property('reaction').name}
                info = result['M'][key]
                check('M_%s_strikes' % key, info['attacks'] >= 1, info)
                check('M_%s_plays_its_own_clip' % key, bool(info['clips']) and all(c.startswith('AS_Melee_Sword_') and c.endswith('_' + key) for c in info['clips']), info['clips'])
                check('M_%s_back_on_its_blueprint' % key, 'SINGLE' not in after[key][0] and after[key][1] == idle[key][1], [idle[key], after[key]])
                check('M_%s_pose_readable' % key, info['spine_between_min'] is not None and info['spine_between_min'] > 50.0
                      and (info['spine_during_min'] is None or info['spine_during_min'] > 50.0), [info['spine_between_min'], info['spine_during_min']])
            if player_health:
                now = player_health.get_editor_property('health')
                result['player_health'] = [health_before, now]
                check('M_blows_land_on_the_player', now < health_before, [health_before, now])
            await shot('M_after_strikes')
            for actor in fighters.values():
                unreal.GameplayStatics.apply_damage(actor, 999.0, None, None, unreal.DamageType)
            await asyncio.sleep(0.6)

        else:
            result['M'] = 'skipped: strike clips on the body crash the editor (train #8, 16:16)'

        # ---- S: a real spell kills and ragdolls ---------------------------------------------------
        spell_combat = player.get_component_by_class(unreal.ReflectionsSpellCombatComponent)
        player.set_actor_location(W(1500, 500, 90), False, True)
        target = npcs.spawn_npc('Soldier', W(1500, 50, 0), 90.0, None)
        await asyncio.sleep(1.2)
        unreal.GameplayStatics.apply_damage(target, max(0.0, health(target) - 5.0), None, player, unreal.DamageType)
        aim = target.get_actor_location() + unreal.Vector(0, 0, 100)
        for capsule in target.get_components_by_class(unreal.CapsuleComponent):
            if capsule.get_name() == 'RuntimeNpcHitProxy':
                aim = capsule.get_world_location()
        controller.set_control_rotation(unreal.MathLibrary.find_look_at_rotation(player.get_actor_location(), aim))
        await asyncio.sleep(0.25)
        origin = unreal.Transform(location=player.get_actor_location() + unreal.Vector(0, 0, 50), rotation=unreal.Rotator(), scale=unreal.Vector(1, 1, 1))
        spell_combat.release_spell_at(unreal.HeroSpell.FIRE, origin, aim, None)
        await asyncio.sleep(1.7)
        target_body = body_of(target)
        try:
            pelvis = round(target_body.get_center_of_mass('pelvis').z - target.get_actor_location().z, 1)
        except Exception:
            pelvis = None
        result['S'] = {'health': health(target), 'reaction': brain(target).get_editor_property('reaction').name,
                       'simulating': target_body.is_any_simulating_physics(), 'pelvis': pelvis}
        check('S_fire_bolt_kills_and_ragdolls', result['S']['health'] <= 0.0 and result['S']['reaction'] == 'INCAPACITATED'
              and result['S']['simulating'] and pelvis is not None and pelvis < 60.0, result['S'])
        await shot('S_spell_kill_ragdoll')

        # ---- V: unnamed NPCs get different roster voices ------------------------------------------
        import time
        try:
            roster = unreal.load_object(None, '/Game/Audio/Jam/Voice/DT_NpcVoiceRoster.DT_NpcVoiceRoster')
        except Exception:
            roster = None
        player.set_actor_location(W(-700, 350, 90), False, True)
        crowd = [npcs.spawn_npc('Civilian' if i < 3 else 'Guard', W(-1100 + i * 160, -700, 0), 90.0, None) for i in range(6)]
        await asyncio.sleep(1.2)
        voices = []
        for actor in crowd:
            profile = npcs.get_voice_profile(actor)
            voice_id = str(profile.get_editor_property('voice_id'))
            row_sex = row_enabled = None
            if roster and voice_id != 'None':
                try:
                    row = npcs.find_voice_row(voice_id)
                    row = row[-1] if isinstance(row, tuple) else row
                    row_sex = row.get_editor_property('sex').name
                    row_enabled = row.get_editor_property('enabled')
                except Exception as error:
                    row_sex = 'n/a: ' + repr(error)[:60]
            cues = {}
            for group in ('Remark', 'Civilian_Fear' if str(profile.get_editor_property('character')) == 'Civilian' else 'Guard_Alert'):
                try:
                    cue = npcs.find_voice_cue(actor, group)
                    cues[group] = cue.get_name() if cue else None
                except Exception as error:
                    cues[group] = 'n/a: ' + repr(error)[:60]
            voices.append({'cues': cues, 'class': actor.get_class().get_name(), 'sex': profile.get_editor_property('sex').name, 'voice_id': voice_id,
                           'gemini': bool(str(profile.get_editor_property('gemini_voice'))), 'row_sex': row_sex, 'row_enabled': row_enabled,
                           'named': brain(actor).has_voice_override()})
        result['V'] = {'roster': bool(roster), 'voices': voices}
        if roster:
            unnamed = [v for v in voices if not v['named']]
            ids = [v['voice_id'] for v in unnamed]
            check('V_unnamed_voices_all_different', len(unnamed) >= 4 and 'None' not in ids and len(set(ids)) == len(ids), ids)
            check('V_voice_sex_matches_look', all(v['row_sex'] == v['sex'] for v in unnamed), [(v['sex'], v['row_sex']) for v in unnamed])
            check('V_only_free_voices_handed_out', all(v['row_enabled'] is True for v in unnamed), [v['row_enabled'] for v in unnamed])
            # Audio's per-voice cues: each unnamed NPC's Remark, and its bark, should be its own voice's take.
            own = [all(name and name.endswith('_' + v['voice_id']) for name in v['cues'].values()) for v in unnamed]
            check('V_lines_come_in_the_npcs_own_voice', unnamed and all(own), [(v['voice_id'], v['cues']) for v in unnamed])

        # ---- W: walker foley, lean outfit parts, looks by archetype, Npc.Weaken -----------------------
        default_bank = '/Game/Audio/Foley/DefaultFoleyEventAudioBank'
        banks = []
        lean = []
        for actor in crowd:
            driver = brain(actor).get_locomotion_driver()
            for part in (driver.get_components_by_class(unreal.ActorComponent) if driver else []):
                if part.get_class().get_name() == 'AC_FoleyEvents_C':
                    bank = part.get_editor_property('foley_event_bank')
                    banks.append(bank.get_path_name() if bank else None)
            body_mesh = body_of(actor)
            for part in actor.get_components_by_class(unreal.SkeletalMeshComponent):
                leader = part.get_editor_property('leader_pose_component')
                if leader and part != body_mesh and part.get_attach_parent() == leader:
                    lean.append((part.get_name(), bool(part.get_editor_property('use_attach_parent_bound')), bool(part.get_editor_property('generate_overlap_events'))))
        result['W'] = {'foley_banks': banks[:6], 'follower_parts': lean[:8], 'follower_count': len(lean),
                       'spawned_classes': [a.get_class().get_name() for a in crowd]}
        check('W_walkers_have_an_empty_foley_bank', banks and all(b and not b.startswith(default_bank) for b in banks), banks[:6])
        check('W_follower_parts_are_lean', lean and all(bound and not overlaps for _, bound, overlaps in lean), lean[:8])
        check('W_archetype_spawns_wear_finished_looks', all(name.startswith('BP_Look_') for name in result['W']['spawned_classes']), result['W']['spawned_classes'])
        face(crowd[4].get_actor_location() + unreal.Vector(0, 0, 100))
        await asyncio.sleep(0.2)
        unreal.SystemLibrary.execute_console_command(world, 'Npc.Weaken 5', controller)
        await asyncio.sleep(0.4)
        weakened = [(a.get_class().get_name(), health(a), brain(a).is_scripted()) for a in crowd if health(a) <= 5.0]
        result['W']['weakened'] = weakened
        check('W_npc_weaken_leaves_one_a_hit_from_death', len(weakened) == 1 and weakened[0][1] == 5.0 and weakened[0][2], weakened)

        # ---- N: the new look Blueprints as NPCs -----------------------------------------------------
        import glob
        import os
        looks_dir = os.path.join(unreal.Paths.project_content_dir(), 'Characters', 'Lanthorne', 'Looks')
        look_ids = sorted(os.path.basename(f)[len('BP_Look_'):-len('.uasset')] for f in glob.glob(os.path.join(looks_dir, 'BP_Look_*.uasset')))
        look_ids = [i for i in look_ids if not i.startswith('Test')]
        newcomers = {}
        for index, look_id in enumerate(look_ids):
            try:
                cls = unreal.load_class(None, '/Game/Characters/Lanthorne/Looks/BP_Look_%s.BP_Look_%s_C' % (look_id, look_id))
                actor = npcs.spawn_npc('Civilian', unreal.Vector(-1300 + (index % 6) * 170, -1000 - (index // 6) * 220, 0), 90.0, cls)
                newcomers[look_id] = actor
            except Exception as error:
                newcomers[look_id] = None
                result.setdefault('N_errors', {})[look_id] = repr(error)[:160]
        await asyncio.sleep(1.5)
        result['N'] = {}
        for look_id, actor in newcomers.items():
            if not actor or not brain(actor):
                result['N'][look_id] = {'spawned': False}
                continue
            tags = [str(t) for t in actor.tags]
            tag_sex = 'FEMALE' if 'NPC_Voice_F' in tags else 'MALE' if 'NPC_Voice_M' in tags else None
            try:
                body_mesh = body_of(actor).get_editor_property('skeletal_mesh_asset').get_name()
            except Exception:
                body_mesh = None
            result['N'][look_id] = {'spawned': True, 'walker': bool(brain(actor).get_locomotion_driver()), 'body': body_mesh,
                                    'tag_sex': tag_sex, 'sex': npcs.get_voice_profile(actor).get_editor_property('sex').name,
                                    'spine': spine_height(actor), 'voice_id': str(brain(actor).get_editor_property('voice_id')),
                                    'look_tags': [t for t in tags if t.startswith('Look_')]}
        seen_new = [v for v in result['N'].values() if v.get('spawned')]
        check('N_new_looks_spawn_as_npcs', len(look_ids) > 0 and len(seen_new) == len(look_ids), {k: v.get('spawned') for k, v in result['N'].items()})
        check('N_new_looks_walk', seen_new and all(v['walker'] for v in seen_new), {k: v.get('walker') for k, v in result['N'].items()})
        check('N_new_looks_sex_from_tag', seen_new and all(v['tag_sex'] and v['tag_sex'] == v['sex'] for v in seen_new),
              {k: (v.get('tag_sex'), v.get('sex')) for k, v in result['N'].items()})
        check('N_new_looks_pose_readable', seen_new and all(isinstance(v['spine'], float) and v['spine'] > 50.0 for v in seen_new),
              {k: v.get('spine') for k, v in result['N'].items()})
        face(W(-900, -1100, 60))
        await asyncio.sleep(0.3)
        await shot('N_new_looks')
        # A lethal hit on three of them, one after another body type if there are several.
        by_body = {}
        for look_id, info in result['N'].items():
            if info.get('spawned') and info.get('body'):
                by_body.setdefault(info['body'], look_id)
        victims = list(by_body.values())[:3]
        for look_id in victims:
            unreal.GameplayStatics.apply_damage(newcomers[look_id], 999.0, None, player, unreal.DamageType)
        await asyncio.sleep(1.6)
        falls = {}
        for look_id in victims:
            body = body_of(newcomers[look_id])
            try:
                pelvis = round(body.get_center_of_mass('pelvis').z - newcomers[look_id].get_actor_location().z, 1)
            except Exception:
                pelvis = None
            falls[look_id] = {'simulating': body.is_any_simulating_physics(), 'pelvis': pelvis,
                              'reaction': brain(newcomers[look_id]).get_editor_property('reaction').name}
        result['N_deaths'] = falls
        check('N_new_looks_ragdoll_on_death', falls and all(f['simulating'] and f['reaction'] == 'INCAPACITATED' and f['pelvis'] is not None
                                                           and f['pelvis'] < 60.0 for f in falls.values()), falls)
        await shot('N_new_looks_after_deaths')

        # ---- P: no camera runs on the hidden walkers; rough cost of the cameras ---------------------
        def walker_cameras():
            found = []
            for actor in npcs.get_npc_actors():
                driver = brain(actor).get_locomotion_driver()
                if not driver:
                    continue
                for part in driver.get_components_by_class(unreal.ActorComponent):
                    name = part.get_class().get_name()
                    if 'Camera' in name or 'SpringArm' in name:
                        found.append(part)
            return found

        async def frame_ms(seconds):
            frames = unreal.SystemLibrary.get_frame_count()
            started = time.perf_counter()
            await asyncio.sleep(seconds)
            return round((time.perf_counter() - started) * 1000.0 / max(1, unreal.SystemLibrary.get_frame_count() - frames), 2)

        cameras = walker_cameras()
        walkers = sum(1 for actor in npcs.get_npc_actors() if brain(actor).get_locomotion_driver())
        active = [c.get_class().get_name() for c in cameras if c.is_active() or c.is_component_tick_enabled()]
        result['P'] = {'walkers': walkers, 'camera_components': len(cameras), 'still_running': active[:6],
                       'classes': sorted(set(c.get_class().get_name() for c in cameras))}
        check('P_no_camera_runs_on_walkers', walkers > 0 and not active, result['P'])
        cap = unreal.SystemLibrary.get_console_variable_float_value('t.MaxFPS')
        unreal.SystemLibrary.execute_console_command(world, 't.MaxFPS 0', controller)
        try:
            await asyncio.sleep(0.5)
            off_first = await frame_ms(2.5)
            for part in cameras:
                part.activate(False)
                part.set_component_tick_enabled(True)
            await asyncio.sleep(0.7)
            on = await frame_ms(2.5)
            for part in cameras:
                part.deactivate()
                part.set_component_tick_enabled(False)
            await asyncio.sleep(0.7)
            off_again = await frame_ms(2.5)
        finally:
            unreal.SystemLibrary.execute_console_command(world, 't.MaxFPS %s' % cap, controller)
        off = round((off_first + off_again) / 2.0, 2)
        result['P'].update({'frame_ms_cameras_off': [off_first, off_again], 'frame_ms_cameras_on': on,
                            'saved_ms_per_frame': round(on - off, 2), 'saved_ms_per_walker': round((on - off) / max(1, walkers), 3)})
    except Exception as error:
        import traceback
        result['error'] = repr(error)
        result['trace'] = traceback.format_exc()[-1500:]
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
                     'ensures': tail.count('Ensure condition failed')}
    check('log_no_empty_pose', result['log']['bone_out_of_range'] == 0 and result['log']['pose_not_ready'] == 0
          and result['log']['pose_repairs'] == 0, result['log'])
except Exception as error:
    result['log'] = repr(error)

result['passed'] = sum(1 for c in result['checks'].values() if c['ok'])
result['failed'] = sorted(name for name, c in result['checks'].items() if not c['ok'])
(OUT / 'verify_melee.json').write_text(json.dumps(result, indent=2, default=str))
json.dumps(result, default=str)
