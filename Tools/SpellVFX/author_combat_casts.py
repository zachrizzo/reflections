"""Generate short, punchy combat casts with Kimodo (UE 5.9) and retarget them to the hero.

Runs inside the editor. ARGS (prepended by the runner) picks the stage:
  source  - create/extend the Kimodo level sequence with one generated section per cast
  status  - report which sections have finished generating
  bake    - duplicate finished takes, retarget to the hero body and pick each release frame from hand speed
Precedent: author_distinct_casts.py (same sequence, retargeter and sampling approach).
These casts are layered on the upper body by ABP_HeroSampleCastBlend, so leg motion in a take is ignored.
"""
import json
import math
import time
import traceback
from pathlib import Path

ROOT = Path(unreal.Paths.project_intermediate_dir()).resolve() / 'CombatCasts'
ROOT.mkdir(exist_ok=True)
FOLDER = '/Game/Characters/Hero/Animation/CombatCasts'
SOURCE = FOLDER + '/LS_Hero_CombatCasts_Kimodo'
QUINN = '/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple'
BODY = '/Game/Characters/Hero/Assembled/Hero/Body/SKM_MHC_Hero_BodyMesh'
RETARGET = '/Game/Characters/Hero/Animation/Locomotion/RTG_MannequinToHero'
EA = unreal.EditorAssetLibrary
state_holder = []
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
FPS = 30

# Name, seed, frames, release hand, expected action fraction, prompt.
CASTS = (
    ('BoltRight', 51101, 48, 'right', .32,
     'Combat ready stance with knees bent. Quickly cock the right hand back beside the right ear, then snap the right arm '
     'straight forward and throw an open palm hard at shoulder height, like hurling a fireball. Hold the extended arm for a '
     'moment, then pull it back to a guard in front of the chest.'),
    ('BoltLeft', 51102, 48, 'left', .32,
     'Combat ready stance with knees bent. Quickly cock the left hand back beside the left ear, then snap the left arm '
     'straight forward and throw an open palm hard at shoulder height. Hold the extended arm for a moment, then pull it '
     'back to a guard in front of the chest. The right hand stays near the right hip.'),
    ('HeavyPush', 51103, 54, 'both', .36,
     'Wide combat stance. Gather both hands together beside the right hip with the torso twisted right, then twist forward '
     'and thrust both palms forward explosively at chest height, leaning into the push. Hold briefly, then bring both '
     'hands back to a guard.'),
    ('Slam', 51104, 54, 'both', .40,
     'Combat stance. Raise both fists quickly above the head, then slam both fists down hard in front of the waist while '
     'bending forward slightly, as if smashing the ground with magic. Straighten up into a guard.'),
    ('Sweep', 51105, 50, 'right', .38,
     'Combat stance. Reach the right open hand across to the left shoulder, then swing the right arm in a fast flat arc '
     'across the body to the right at chest height, palm facing forward, like sweeping a wave outward. Return the hand '
     'to the chest.'),
    ('HealRaise', 51106, 66, 'both', .40,
     'Stand upright. Bring both open palms together in front of the belly, then lift them smoothly up past the face and '
     'open the arms wide above the head with palms turned up, looking slightly upward, as if releasing light. Lower the '
     'arms gracefully.'),
    ('AimHold', 51107, 90, 'right', .50,
     'Steady combat stance, perfectly still. The right arm is extended straight forward at shoulder height with the open '
     'palm facing forward and fingers spread, aiming. The left hand is raised in a loose fist near the chest. Breathe '
     'slowly and keep the extended arm steady the whole time.'),
)


SAVE = unreal.EditorLoadingAndSavingUtils


def find_asset(path):
    """PIE-safe lookup (EditorAssetLibrary refuses to run while Play-in-Editor is active)."""
    name = path.rsplit('/', 1)[1]
    return unreal.find_object(None, path + '.' + name) or unreal.load_object(None, path + '.' + name)


def save(asset):
    return SAVE.save_packages([asset.get_package()], False)


def load_source():
    unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous([FOLDER], True)
    return unreal.load_object(None, SOURCE + '.' + SOURCE.rsplit('/', 1)[1])


def entries():
    offset = 0
    for name, seed, frames, hand, fraction, prompt in CASTS:
        yield dict(name=name, seed=seed, frames=frames, hand=hand, fraction=fraction, prompt=prompt, offset=offset)
        offset += frames + 12


def create_source():
    source = load_source() or TOOLS.create_asset(
        SOURCE.rsplit('/', 1)[1], FOLDER, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    # Persist immediately: an unsaved, unreferenced sequence can be garbage-collected between ticks.
    save(source)
    state_holder.append(source)
    definitions = list(entries())
    end = definitions[-1]['offset'] + definitions[-1]['frames']
    source.set_display_rate(unreal.FrameRate(FPS, 1))
    source.set_playback_start(0)
    source.set_playback_end(end)
    source.set_view_range(-.15, end / FPS + .3)
    source.set_work_range(-1., end / FPS + 1.)
    bindings = source.get_bindings()
    if bindings:
        mixer = next(t for t in bindings[0].get_tracks() if isinstance(t, unreal.MovieSceneAnimationMixerTrack))
    else:
        binding = source.add_spawnable_from_class(unreal.SkeletalMeshActor)
        binding.set_display_name('Quinn | Combat casts')
        binding.get_object_template().get_editor_property('skeletal_mesh_component').set_editor_property('skeletal_mesh_asset', find_asset(QUINN))
        mixer = binding.add_track(unreal.MovieSceneAnimationMixerTrack)
    generator = unreal.load_class(None, '/Script/Kimodo.KimodoPoseGenerator')
    state = {'request': None, 'i': 0, 'start': time.monotonic()}

    def attach(delta):
        try:
            if time.monotonic() - state['start'] > 200:
                raise TimeoutError('Kimodo section insertion timed out')
            index = state['i']
            if index == len(definitions):
                saved = save(source)
                opened = unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(source)
                if opened:
                    unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
                (ROOT / 'source-ready.json').write_text(json.dumps({'saved': saved, 'opened': opened, 'casts': definitions}, indent=2))
                unreal.unregister_slate_post_tick_callback(state['handle'])
                return
            data = definitions[index]
            if state['request'] is not None and not state['request'].is_complete:
                return
            sections = mixer.get_sections()
            if len(sections) <= index:
                state['request'] = unreal.AnimGenOfflineMixerExtensions.add_generated_animation_section_async(
                    mixer, index, data['offset'], generator)
                return
            section = sections[index]
            section.set_range(data['offset'], data['offset'] + data['frames'])
            settings = section.get_editor_property('pose_generator')
            settings.set_editor_property('AnimDescriptionOverride', data['prompt'])
            settings.set_editor_property('RandomSeed', data['seed'])
            settings.set_editor_property('movement_source', unreal.AnimGenOfflineMovementSource.GENERATED_ANIMATION)
            state['i'] += 1
            state['request'] = None
        except Exception:
            (ROOT / 'source-error.txt').write_text(traceback.format_exc())
            unreal.unregister_slate_post_tick_callback(state['handle'])
            raise

    state['handle'] = unreal.register_slate_post_tick_callback(attach)
    return 'source authoring started'


def section_anim(section):
    """The section's current generated take: regeneration retires AnimSequence_N and writes N+1."""
    prefix = section.get_path_name() + '.AnimSequence_'
    best, best_index = None, -1
    for anim in unreal.ObjectIterator(unreal.AnimSequence):
        path = anim.get_path_name()
        if path.startswith(prefix) and path[len(prefix):].isdigit() and int(path[len(prefix):]) > best_index:
            best, best_index = anim, int(path[len(prefix):])
    return best


def sections():
    source = load_source()
    mixer = next(t for t in source.get_bindings()[0].get_tracks() if isinstance(t, unreal.MovieSceneAnimationMixerTrack))
    return mixer.get_sections()


def status():
    out = {}
    for entry, section in zip(entries(), sections()):
        inline = section_anim(section)
        ready = bool(inline) and inline.data_model_interface.get_num_bone_tracks() >= 20
        out[entry['name']] = (ready, inline.get_skeleton().get_name() if inline and inline.get_skeleton() else None)
    return out


def bake():
    quinn, body, retargeter = (find_asset(path) for path in (QUINN, BODY, RETARGET))
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    opts = unreal.AnimPoseEvaluationOptions()
    opts.set_editor_property('evaluation_type', unreal.AnimDataEvalType.RAW)
    opts.set_editor_property('optional_skeletal_mesh', body)
    report = {}
    for entry, section in zip(entries(), sections()):
        name = entry['name']
        inline = section_anim(section)
        clip = find_asset(FOLDER + '/AS_Hero_Combat' + name)
        if not clip or clip.get_package().get_name() != FOLDER + '/AS_Hero_Combat' + name:
            report[name] = {'pending': True, 'note': 'run the soma stage first'}
            continue
        try:
            assert clip.get_skeleton() == body.get_editor_property('skeleton')
            clip.set_preview_skeletal_mesh(body)
            clip.set_editor_property('enable_root_motion', False)
            clip.set_editor_property('force_root_lock', True)
            assert save(clip)
            duration = clip.get_play_length()
            poses = []
            for i in range(int(duration * FPS) + 1):
                pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(clip, min(i / FPS, duration), opts)
                poses.append({b: unreal.AnimPoseExtensions.get_bone_pose(pose, b, unreal.AnimPoseSpaces.WORLD).translation.to_tuple()
                              for b in ('hand_r', 'hand_l', 'spine_03')})
            bones = ('hand_l', 'hand_r') if entry['hand'] == 'both' else ('hand_' + entry['hand'][0],)
            # Release on the frame where the casting hand(s) move fastest, near the prompt's action beat.
            ideal = entry['fraction'] * len(poses)
            window = range(max(1, round(ideal - .25 * len(poses))), min(len(poses), round(ideal + .25 * len(poses))))

            def speed(i):
                s = sum(math.dist(poses[i][b], poses[i - 1][b]) for b in bones)
                return s * (1.0 - .35 * abs(i - ideal) / (.25 * len(poses)))
            peak = max(window, key=speed)
            # Fire a couple of frames after peak speed, when the arm is near full extension.
            release = min(len(poses) - 1, peak + 2)
            reach = max(math.dist(poses[release][b], poses[release]['spine_03']) for b in bones)
            # Author the release as a Spell Release notify so gameplay reads it from the clip (no code change to retune).
            notify_class = unreal.load_class(None, '/Script/reflections.ReflectionsSpellReleaseNotify')
            if notify_class and name != 'AimHold':
                unreal.AnimationLibrary.remove_animation_notify_events_by_track(clip, 'Spell') if unreal.AnimationLibrary.is_valid_anim_notify_track_name(clip, 'Spell') else None
                if not unreal.AnimationLibrary.is_valid_anim_notify_track_name(clip, 'Spell'):
                    unreal.AnimationLibrary.add_animation_notify_track(clip, 'Spell')
                unreal.AnimationLibrary.add_animation_notify_event(clip, 'Spell', release / FPS, notify_class)
                assert save(clip)
            report[name] = dict(clip=clip.get_path_name(), hand=entry['hand'], duration=duration, peak_frame=peak,
                                release_frame=release, release=release / FPS, reach=reach, notify=bool(notify_class))
        except Exception:
            report[name] = {'error': traceback.format_exc()}
    (ROOT / 'bake-report.json').write_text(json.dumps(report, indent=2))
    return report


async def mixbake():
    """Kimodo generates on its own Soma skeleton; baking the mixer track evaluates it onto the bound Quinn mesh."""
    source = load_source()
    # Reopen so the spawnable preview actor is respawned with the bound Quinn mesh.
    unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
    await asyncio.sleep(0.5)
    unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(source)
    for _ in range(10):
        unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(1)
        await asyncio.sleep(0.2)
    mixer = next(t for t in source.get_bindings()[0].get_tracks() if isinstance(t, unreal.MovieSceneAnimationMixerTrack))
    skeleton = find_asset(QUINN).get_editor_property('skeleton')
    done = {}
    for entry in entries():
        raw_name = 'AS_Quinn_Combat' + entry['name']
        raw = unreal.find_object(None, FOLDER + '/' + raw_name + '.' + raw_name)
        if raw is not None and raw.get_package().get_name() != FOLDER + '/' + raw_name:
            raw = None
        if raw is None:
            factory = unreal.AnimSequenceFactory()
            factory.set_editor_property('target_skeleton', skeleton)
            raw = TOOLS.create_asset(raw_name, FOLDER, unreal.AnimSequence, factory)
        options = unreal.AnimSeqExportOption()
        options.set_editor_property('use_custom_time_range', True)
        options.set_editor_property('custom_start_frame', unreal.FrameNumber(entry['offset']))
        options.set_editor_property('custom_end_frame', unreal.FrameNumber(entry['offset'] + entry['frames']))
        options.set_editor_property('record_in_world_space', False)
        await call_tool('MovieSceneAnimMixerScripting.MovieSceneAnimMixerBakeExtensions.BakeToAnimSequenceAsync',
                        track=mixer, animSequence=raw, exportOptions=options, firstLayer=-1, lastLayer=-1)
        raw.set_editor_property('enable_root_motion', False)
        done[entry['name']] = (raw.get_skeleton().get_name(), round(raw.get_play_length(), 3), save(raw))
        await asyncio.sleep(0)
    return done


RIGS = FOLDER + '/Rigs'
SOMA_MESH = '/Kimodo/Characters/Soma/soma_neutral'
# Soma uses Mixamo-style names; chains are named like the hero rig's so they map exactly.
SOMA_CHAINS = (
    ('Spine', 'Spine1', 'Chest'), ('Neck', 'Neck1', 'Neck2'), ('Head', 'Head', 'Head'),
    ('LeftClavicle', 'LeftShoulder', 'LeftShoulder'), ('LeftArm', 'LeftArm', 'LeftHand'),
    ('RightClavicle', 'RightShoulder', 'RightShoulder'), ('RightArm', 'RightArm', 'RightHand'),
    ('LeftLeg', 'LeftLeg', 'LeftFoot'), ('LeftFoot', 'LeftToeBase', 'LeftToeBase'),
    ('RightLeg', 'RightLeg', 'RightFoot'), ('RightFoot', 'RightToeBase', 'RightToeBase'),
)


def fresh_object(path):
    """Moves any stale object at path aside so a new asset can take the name."""
    name = path.rsplit('/', 1)[1]
    old = unreal.find_object(None, path + '.' + name)
    if old is not None and old.get_package().get_name() == path:
        old.rename(name + '_Stale%d' % (int(time.time() * 1000) % 100000), unreal.find_object(None, '/Engine/Transient'))


def soma_retarget():
    """Kimodo writes takes on its own Soma skeleton; retarget them straight onto the hero body."""
    soma_mesh = find_asset(SOMA_MESH)
    body = find_asset(BODY)
    rig_path = RIGS + '/IK_Soma_Combat'
    rig = unreal.find_object(None, rig_path + '.IK_Soma_Combat')
    if rig is None or rig.get_package().get_name() != rig_path:
        rig = TOOLS.create_asset('IK_Soma_Combat', RIGS, unreal.IKRigDefinition, unreal.IKRigDefinitionFactory())
        rc = unreal.IKRigController.get_controller(rig)
        assert rc.set_skeletal_mesh(soma_mesh)
        assert rc.set_retarget_root('Hips')
        for chain, first, last in SOMA_CHAINS:
            rc.add_retarget_chain(chain, first, last, 'None')
        save(rig)
    rtg_path = RIGS + '/RTG_SomaToHero'
    rtg = unreal.find_object(None, rtg_path + '.RTG_SomaToHero')
    if rtg is None or rtg.get_package().get_name() != rtg_path:
        rtg = TOOLS.duplicate_asset('RTG_SomaToHero', RIGS, find_asset(RETARGET))
        c = unreal.IKRetargeterController.get_controller(rtg)
        c.set_ik_rig(unreal.RetargetSourceOrTarget.SOURCE, rig)
        c.set_preview_mesh(unreal.RetargetSourceOrTarget.SOURCE, soma_mesh)
        c.auto_map_chains(unreal.AutoMapChainType.EXACT, True)
        pose = c.create_retarget_pose('AlignedToHero', unreal.RetargetSourceOrTarget.SOURCE)
        c.set_current_retarget_pose(pose, unreal.RetargetSourceOrTarget.SOURCE)
        c.auto_align_all_bones(unreal.RetargetSourceOrTarget.SOURCE)
        save(rtg)
    report = {}
    for entry, section in zip(entries(), sections()):
        name = entry['name']
        inline = section_anim(section)
        if not inline or inline.data_model_interface.get_num_bone_tracks() < 20:
            report[name] = 'pending generation'
            continue
        # The Soma copy carries the final clip name in a subfolder, so the retarget writes (and overwrites)
        # FOLDER/AS_Hero_Combat<Name> directly without a rename.
        hero_name = 'AS_Hero_Combat' + name
        soma_folder = FOLDER + '/Soma'
        soma_clip = unreal.load_object(None, soma_folder + '/' + hero_name + '.' + hero_name)
        if soma_clip is None:
            soma_clip = TOOLS.duplicate_asset(hero_name, soma_folder, inline)
        assert soma_clip and save(soma_clip), name
        spec = unreal.IKRetargetBatchOperationInputs(
            assets_to_retarget=[unreal.AssetRegistryHelpers.create_asset_data(soma_clip)],
            source_mesh=soma_mesh, target_mesh=body, ik_retarget_asset=rtg,
            target_path=FOLDER, use_source_path=False, include_referenced_assets=False,
            overwrite_existing_files=True, suffix='')
        result = unreal.IKRetargetBatchOperation.run_batch_retarget(spec)
        assert len(result) == 1, name
        clip = result[0].get_asset()
        assert clip.get_package().get_name() == FOLDER + '/' + hero_name, clip.get_path_name()
        clip.set_preview_skeletal_mesh(body)
        clip.set_editor_property('enable_root_motion', False)
        clip.set_editor_property('force_root_lock', True)
        save(clip)
        report[name] = clip.get_path_name()
    return report


stage = (ARGS or ['status'])[0]
result = await mixbake() if stage == 'mixbake' else {'source': create_source, 'status': status, 'bake': bake, 'soma': soma_retarget}[stage]()
json.dumps(result, default=str, indent=1)
