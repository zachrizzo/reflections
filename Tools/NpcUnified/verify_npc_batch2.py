"""Second NPC check for Lvl_HeroSampleCrowd: voices, team-look spawns, barks, scripted holds and the tarnished
hunting townspeople. Run through the editor MCP `execute_python` tool (top-level `await`, `call_tool`), with the
crowd sample map open and PIE stopped. One PIE session, about 60 seconds; it always stops PIE.

  G  Every NPC has a voice: a sex from its look, a slot that does not change, a cue suffix the component repeats.
  K  An NPC made tarnished with SetInfection goes for a clean townsperson (one of them tagged Friendly), the
     NPC system hands both to the villain's conversion, the victim turns and is counted, and both are let go.
  H  SpawnNpc and the Npc.Spawn console command give team MetaHuman looks of the asked archetype.
  I  PlayBark attaches a voice cue to the speaker and respects the per-NPC cooldown.
  J  A scripted hold stops an NPC reacting; releasing it gives the reactions back.
Results: Saved/NpcUnified/verify_batch2.json and K_*/H_* pictures in the same folder.
"""

import base64
import json
from pathlib import Path

OUT = Path(unreal.Paths.project_saved_dir()) / 'NpcUnified'
OUT.mkdir(parents=True, exist_ok=True)
result = {'checks': {}, 'shots': []}
TEAM_LOOK_WORDS = ('WhiteLook_', 'SimpleRed')


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


if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
    result['abort'] = 'PIE is already running (someone else is testing); nothing was started.'
else:
    await call_tool('EditorToolset.EditorAppToolset.StartPIE')
    try:
        await asyncio.sleep(3.0)
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        player = unreal.GameplayStatics.get_player_pawn(world, 0)
        controller = player.get_controller()
        npcs = unreal.get_world_subsystem(world, unreal.ReflectionsNpcSubsystem)
        villain_class = getattr(unreal, 'ReflectionsVillainSubsystem', None)
        villain = unreal.get_world_subsystem(world, villain_class) if villain_class else None
        flow_class = getattr(unreal, 'ReflectionsGameFlowSubsystem', None)
        flow = unreal.get_game_instance_subsystem(unreal.GameplayStatics.get_game_instance(world), flow_class) if flow_class else None

        def brain(actor):
            return actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent)

        def health(actor):
            return actor.get_component_by_class(unreal.ReflectionsHealthComponent).get_editor_property('health')

        def label(actor):
            return actor.get_actor_label() if actor else None

        def state(actor):
            b = brain(actor)
            archetype = b.get_active_archetype()
            focus = b.get_focus_actor()
            return {'archetype': str(archetype.get_editor_property('archetype_id')) if archetype else None,
                    'reaction': b.get_editor_property('reaction').name, 'infection': b.get_editor_property('infection').name,
                    'scripted': b.is_scripted(), 'focus': label(focus), 'health': health(actor)}

        def place(actor, location):
            driver = brain(actor).get_locomotion_driver()
            if driver:
                driver.set_actor_location(driver.get_actor_location() + (location - actor.get_actor_location()), False, True)
            else:
                actor.set_actor_location(location, False, True)

        def face(point, yaw_offset=0.0):
            rotation = unreal.MathLibrary.find_look_at_rotation(player.get_actor_location(), point)
            rotation.yaw += yaw_offset
            controller.set_control_rotation(rotation)

        def flat_distance(a, b):
            delta = a.get_actor_location() - b.get_actor_location()
            return round(unreal.Vector(delta.x, delta.y, 0).length())

        def voice(actor):
            profile = npcs.get_voice_profile(actor)
            b = brain(actor)
            return {'class': actor.get_class().get_name(), 'sex': profile.get_editor_property('sex').name,
                    'slot': profile.get_editor_property('slot'), 'character': str(profile.get_editor_property('character')),
                    'suffix': str(profile.get_editor_property('cue_suffix')), 'component_slot': str(b.get_editor_property('voice_slot')),
                    'voice_id': str(profile.get_editor_property('voice_id')), 'component_voice_id': str(b.get_editor_property('voice_id')),
                    'look_sex': unreal.ReflectionsNpcSubsystem.get_look_sex(actor).name}

        def sounds_on(actor):
            names = []
            seen = set()
            parts = list(actor.get_components_by_class(unreal.AudioComponent))
            for mesh in actor.get_components_by_class(unreal.SceneComponent):
                parts += [c for c in mesh.get_children_components(False) if isinstance(c, unreal.AudioComponent)]
            for part in parts:
                if part.get_name() in seen:
                    continue
                seen.add(part.get_name())
                sound = part.get_editor_property('sound')
                names.append(sound.get_name() if sound else None)
            return names

        def infected_count():
            return flow.get_infection_count() if flow else None

        def stimulus_at(location):
            stimulus = unreal.ReflectionsNpcStimulus()
            stimulus.set_editor_property('kind', unreal.ReflectionsNpcStimulusKind.SPELL_NOISE)
            stimulus.set_editor_property('location', location)
            stimulus.set_editor_property('intensity', 40.0)
            stimulus.set_editor_property('instigator', player)
            npcs.report_stimulus(stimulus)

        level_npcs = {a.get_actor_label(): a for a in npcs.get_npc_actors()}

        # ---- G: voices --------------------------------------------------------------------------------
        voices = {name: voice(a) for name, a in level_npcs.items()}
        again = {name: voice(a) for name, a in level_npcs.items()}
        result['G'] = voices
        expected_sex = {'CoinClerk': 'FEMALE', 'FestivalDrummer': 'FEMALE', 'BridgeGuard': 'FEMALE', 'ArchiveApprentice': 'MALE',
                        'WhiteLook_01': 'MALE', 'WhiteLook_06': 'FEMALE'}
        wrong = {name: v for name, v in voices.items()
                 if any(word in v['class'] and v['sex'] != sex for word, sex in expected_sex.items())}
        check('G_every_npc_has_a_sex', all(v['sex'] in ('FEMALE', 'MALE') for v in voices.values()), voices)
        check('G_sex_matches_look', not wrong, wrong)
        check('G_suffix_matches_component', all(v['suffix'] == v['component_slot'] and v['suffix'][:1] == v['sex'][:1]
                                                and v['suffix'][1:] == str(v['slot'] + 1) for v in voices.values()), voices)
        check('G_voice_is_stable', voices == again, None)
        by_sex = {}
        for v in voices.values():
            by_sex.setdefault(v['sex'], []).append(v['slot'])
        check('G_slots_spread_within_sex', all(len(set(slots)) == min(3, len(slots)) for slots in by_sex.values()), by_sex)
        # Roster voice ids: only there once audio's table is in the project. (The editor asset library refuses
        # to answer during play, so the table is looked up as an object.)
        try:
            roster = bool(unreal.load_object(None, '/Game/Audio/Jam/Voice/DT_NpcVoiceRoster.DT_NpcVoiceRoster'))
        except Exception:
            roster = False
        ids = [v['voice_id'] for v in voices.values()]
        result['G_roster'] = {'table_in_project': roster, 'ids': ids}
        check('G_voice_id_matches_component', all(v['voice_id'] == v['component_voice_id'] for v in voices.values()), None)
        if roster:
            check('G_roster_gives_every_npc_a_voice', all(i != 'None' for i in ids), ids)
            check('G_roster_voices_differ', len(set(ids)) == len(ids), ids)
        else:
            check('G_no_roster_no_voice_id', all(i == 'None' for i in ids), ids)
        result['G_roster']['named_by_lives'] = sum(1 for a in level_npcs.values() if brain(a).has_voice_override())

        # ---- K: the tarnished hunt townspeople and convert them -------------------------------------
        # Three fresh civilians and one placed townsperson that carries the Friendly tag, in the empty
        # south-west, with the player too far away to be the nearer quarry.
        player.set_actor_location(unreal.Vector(-700, 350, 90), False, True)
        spots = [unreal.Vector(-700, -800, 0), unreal.Vector(-1050, -800, 0), unreal.Vector(-700, -1150, 0)]
        clean = [npcs.spawn_npc('Civilian', spot, 90.0, None) for spot in spots]
        friendly = next((a for a in level_npcs.values() if a.actor_has_tag('Friendly')), None)
        if friendly:
            place(friendly, unreal.Vector(-1050, -1150, 0))
            clean.append(friendly)
        await asyncio.sleep(1.5)
        check('K_civilians_spawned', all(c and brain(c) for c in clean), [label(c) for c in clean])
        meter_before = infected_count()
        face(unreal.Vector(-875, -975, 60))
        await asyncio.sleep(0.2)
        result['K'] = {'villain_loaded': bool(villain), 'timeline': []}
        if not villain:
            check('K_villain_system_loaded', False, 'ReflectionsVillainSubsystem is not in this editor build')
        else:
            first = clean[0]
            check('K_first_tarnished', npcs.set_infection(first, unreal.ReflectionsNpcInfection.INFECTED, None), state(first))

            def tarnished():
                return [a for a in npcs.get_npc_actors() if brain(a).get_editor_property('infection').name != 'NONE']

            # Every conversion from here on has to be started by a hunter of ours reaching its quarry.
            handed_over = None
            pictured = False
            spawned_names = {label(c) for c in clean}
            for step in range(120):
                await asyncio.sleep(0.25)
                hunters = tarnished()
                sample = {'t': round(step * 0.25, 2), 'tarnished': [label(a) for a in hunters],
                          'hunters': {label(a): state(a) for a in hunters}}
                for hunter in hunters:
                    b = brain(hunter)
                    quarry = b.get_focus_actor()
                    if quarry and quarry != player and brain(quarry) and b.is_scripted() and brain(quarry).is_scripted() \
                            and villain.is_converting(quarry) and brain(quarry).get_editor_property('infection').name == 'NONE':
                        handed_over = handed_over or {'hunter': label(hunter), 'victim': label(quarry), 't': sample['t'],
                                                      'distance': flat_distance(hunter, quarry)}
                        if not pictured:
                            pictured = True
                            face(quarry.get_actor_location() + unreal.Vector(0, 0, 60))
                            await asyncio.sleep(0.1)
                            await shot('K_hunter_converts_npc')
                if step % 4 == 0:
                    result['K']['timeline'].append(sample)
                if handed_over and len(hunters) >= 3 and step >= 8:
                    break
                if step == 60 and not handed_over:
                    result['K']['note'] = 'no hand-over after 15 s'
                    break
            hunters = tarnished()
            result['K'].update({'handed_over': handed_over, 'tarnished_end': {label(a): state(a) for a in hunters},
                                'meter': [meter_before, infected_count()], 'player_health': health(player)
                                if player.get_component_by_class(unreal.ReflectionsHealthComponent) else None})
            went_for_npc = any(s['focus'] in spawned_names or s['focus'] in level_npcs
                               for sample in result['K']['timeline'] for s in sample['hunters'].values())
            check('K_tarnished_behave_infected', hunters and all(state(a)['archetype'] in ('Infected', 'VillainHost') for a in hunters),
                  result['K']['tarnished_end'])
            check('K_hunter_goes_for_an_npc', went_for_npc or bool(handed_over), None)
            check('K_npc_system_started_a_conversion', bool(handed_over), handed_over)
            # The nearest clean NPC stands 3.5 m from the hunter: it must be noticed and reached at once (on the
            # 14:17 build the sight test ended at the target's feet and this took 12.75 s, on a farther victim).
            check('K_hunter_takes_a_nearby_npc_quickly', bool(handed_over) and handed_over['t'] <= 6.0, handed_over)
            check('K_victim_turned', len(hunters) >= 2, [label(a) for a in hunters])
            result['K']['friendly_turned'] = bool(friendly) and brain(friendly).get_editor_property('infection').name != 'NONE'
            result['K']['friendly_alive'] = bool(friendly) and health(friendly) > 0.0
            if flow:
                check('K_meter_counts_them', infected_count() == meter_before + len(hunters), result['K']['meter'])
            await asyncio.sleep(1.5)
            still_held = [label(a) for a in tarnished() if brain(a).is_scripted() and not villain.is_converting(a)]
            check('K_holds_released', not still_held, still_held)
            face(unreal.Vector(-875, -975, 60))
            await asyncio.sleep(0.2)
            await shot('K_after')
            # Leave no hunters behind for the rest of the run.
            for actor in tarnished():
                unreal.GameplayStatics.apply_damage(actor, 999.0, None, None, unreal.DamageType)

        # ---- H: SpawnNpc and Npc.Spawn give team looks ----------------------------------------------
        player.set_actor_location(unreal.Vector(1200, 1300, 90), False, True)
        controller.set_control_rotation(unreal.Rotator(0, 0, -90))
        await asyncio.sleep(0.3)
        before = set(a.get_name() for a in npcs.get_npc_actors())
        soldier = npcs.spawn_npc('Soldier', unreal.Vector(900, 700, 0), 90.0, None)
        unreal.SystemLibrary.execute_console_command(world, 'Npc.Spawn Guard 2 600', controller)
        await asyncio.sleep(1.5)
        fresh = [a for a in npcs.get_npc_actors() if a.get_name() not in before]
        guards = [a for a in fresh if a != soldier]

        def visible_meshes(actor):
            names = []
            for mesh in actor.get_components_by_class(unreal.SkeletalMeshComponent):
                asset = mesh.get_editor_property('skeletal_mesh_asset')
                if asset and mesh.is_visible():
                    names.append(asset.get_name())
            return names

        result['H'] = {label(a): {'class': a.get_class().get_name(), 'state': state(a), 'voice': voice(a),
                                  'driver': bool(brain(a).get_locomotion_driver()), 'meshes': visible_meshes(a)} for a in fresh}
        check('H_spawn_npc_soldier', soldier and state(soldier)['archetype'] == 'Soldier' and health(soldier) == 70.0,
              state(soldier) if soldier else None)
        check('H_console_spawned_two_guards', len(guards) == 2 and all(state(g)['archetype'] == 'Guard' for g in guards),
              [state(g) for g in guards])
        check('H_team_looks_only', fresh and all(any(word in a.get_class().get_name() for word in TEAM_LOOK_WORDS) for a in fresh),
              [a.get_class().get_name() for a in fresh])
        check('H_no_visible_mannequin', not any(any(word in name for word in ('Manny', 'Quinn', 'Mannequin', 'UEFN'))
                                                for info in result['H'].values() for name in info['meshes']),
              {name: info['meshes'] for name, info in result['H'].items()})
        check('H_spawned_walk_and_have_voices', all(info['driver'] and info['voice']['sex'] in ('FEMALE', 'MALE')
                                                    for info in result['H'].values()), None)
        # An override must come and go cleanly: on the fresh soldier, which nobody else has cast as a person.
        own_id = str(brain(soldier).get_editor_property('voice_id'))
        brain(soldier).set_voice_override('V999')
        cast_id = str(npcs.get_voice_profile(soldier).get_editor_property('voice_id'))
        overridden = brain(soldier).has_voice_override()
        brain(soldier).clear_voice_override()
        check('H_voice_override_round_trip', cast_id == 'V999' and overridden and not brain(soldier).has_voice_override()
              and str(brain(soldier).get_editor_property('voice_id')) == own_id, [own_id, cast_id, overridden])
        if roster:
            # Unnamed NPCs must not share a roster voice while unused ones of their sex remain (on train #7 the
            # soldier and both guards all got V001, the only enabled voice of their side).
            spawned_ids = [info['voice']['voice_id'] for info in result['H'].values()]
            check('H_unnamed_voices_differ', 'None' not in spawned_ids and len(set(spawned_ids)) == len(spawned_ids), spawned_ids)
        await shot('H_spawned_team_looks')

        # ---- I: barks ---------------------------------------------------------------------------------
        speaker = guards[0] if guards else soldier
        group = 'Guard_Alert' if guards else 'Soldier_Command'
        await asyncio.sleep(2.5)  # past the bark it may have made when it appeared
        quiet = sounds_on(speaker)
        npcs.play_bark(speaker, group)
        await asyncio.sleep(0.15)
        spoken = sounds_on(speaker)
        npcs.play_bark(speaker, group)
        await asyncio.sleep(0.15)
        repeated = sounds_on(speaker)
        suffix = voice(speaker)['suffix']
        new = [name for name in spoken if name not in quiet] or spoken
        result['I'] = {'speaker': label(speaker), 'suffix': suffix, 'before': quiet, 'after': spoken, 'after_second_call': repeated}
        check('I_bark_plays_on_speaker', len(spoken) > len(quiet) and any(name and name.startswith('SCue_VO_' + group) for name in new),
              result['I'])
        check('I_bark_in_its_own_voice', any(name and name.endswith('_' + suffix) for name in new), [suffix, new])
        check('I_cooldown_stops_a_repeat', len(repeated) <= len(spoken), [len(spoken), len(repeated)])

        # ---- J: scripted hold -------------------------------------------------------------------------
        bystander = npcs.spawn_npc('Civilian', unreal.Vector(1500, 300, 0), 90.0, None)
        await asyncio.sleep(1.2)
        start = bystander.get_actor_location()
        npcs.hold_npc(bystander, 4.0)
        held = brain(bystander).is_scripted()
        stimulus_at(start + unreal.Vector(200, 0, 50))
        await asyncio.sleep(0.7)
        during = state(bystander)
        moved = round((bystander.get_actor_location() - start).length())
        npcs.release_npc(bystander)
        released = not brain(bystander).is_scripted()
        stimulus_at(bystander.get_actor_location() + unreal.Vector(200, 0, 50))
        await asyncio.sleep(0.7)
        after = state(bystander)
        result['J'] = {'held': held, 'during': during, 'moved_cm': moved, 'released': released, 'after': after}
        check('J_hold_takes', held, None)
        check('J_held_npc_ignores_noise', during['reaction'] == 'CALM' and moved < 20, [during, moved])
        check('J_release_gives_reactions_back', released and after['reaction'] == 'FLEEING', after)

        # ---- L: passing remarks (only when the build has them) --------------------------------------
        calm = npcs.spawn_npc('Civilian', unreal.Vector(900, 1300, 0), 90.0, None)
        await asyncio.sleep(1.0)
        if hasattr(brain(calm), 'set_remarks_muted'):
            brain(calm).set_remarks_muted(True)
            muted = brain(calm).are_remarks_muted()
            brain(calm).set_remarks_muted(False)
            cue = npcs.find_voice_cue(calm, 'Remark')
            result['L'] = {'muted_round_trip': [muted, brain(calm).are_remarks_muted()], 'remark_cue': cue.get_name() if cue else None,
                           'sounds_near_player': sounds_on(calm)}
            check('L_remarks_can_be_muted', muted and not brain(calm).are_remarks_muted(), result['L'])
        else:
            result['L'] = 'this build has no remarks yet'
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
    result['log'] = {'conversions_by_npc_system': tail.count('held for'),
                     'conversion_tackles': tail.count(' tackles '),
                     'pose_repairs': tail.count('body bone buffers were incomplete'),
                     'pose_not_ready': tail.count('body pose not ready'),
                     'bone_out_of_range': tail.count('GetBoneMatrix : BoneIndex'),
                     'errors': [line[-220:] for line in tail.splitlines() if 'Error:' in line][:8]}
    check('log_no_empty_pose', result['log']['bone_out_of_range'] == 0 and result['log']['pose_not_ready'] == 0, result['log'])
except Exception as error:
    result['log'] = repr(error)

result['passed'] = sum(1 for c in result['checks'].values() if c['ok'])
result['failed'] = sorted(name for name, c in result['checks'].items() if not c['ok'])
(OUT / 'verify_batch2.json').write_text(json.dumps(result, indent=2, default=str))
json.dumps(result, default=str)
