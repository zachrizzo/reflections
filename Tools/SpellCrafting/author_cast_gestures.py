"""Generate the spell-crafting cast gestures with Kimodo (UE 5.9) and retarget them to the hero.

Runs inside the editor (Kimodo is an Editor-type plugin that needs the editor's Python ML packages, so it never
runs in a packaged build; the baked AnimSequences are what ship). ARGS (prepended by the runner) picks the stage:
  source  - create/extend LS_Hero_CraftGestures_Kimodo with one generated section per gesture
  status  - report which sections have finished generating
  soma    - retarget finished takes from Kimodo's Soma skeleton onto the hero body (/Game/SpellCrafting/Gestures)
  bake    - pick each release frame from hand speed and author a Spell Release notify on the clip
Same pipeline as Tools/SpellVFX/author_combat_casts.py, reusing its Soma IK rig and RTG_SomaToHero read-only.
Gestures are layered on the upper body, so leg motion in a take is ignored.
Turn off AnimGenOffline.RetiredAnimationGC.Enabled while generating: the plugin otherwise evicts finished takes.
"""
import json
import math
import time
import traceback
from pathlib import Path

ROOT = Path(unreal.Paths.project_intermediate_dir()).resolve() / 'SpellCraftingGestures'
ROOT.mkdir(exist_ok=True)
FOLDER = '/Game/SpellCrafting/Gestures'
SOURCE = FOLDER + '/LS_Hero_CraftGestures_Kimodo'
QUINN = '/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple'
BODY = '/Game/Characters/Hero/Assembled/Hero/Body/SKM_MHC_Hero_BodyMesh'
SOMA_MESH = '/Kimodo/Characters/Soma/soma_neutral'
SOMA_RTG = '/Game/Characters/Hero/Animation/CombatCasts/Rigs/RTG_SomaToHero'
MANNEQUIN_RTG = '/Game/Characters/Hero/Animation/Locomotion/RTG_MannequinToHero'
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
SAVE = unreal.EditorLoadingAndSavingUtils
FPS = 30
state_holder = []

# Name, seed, frames, release hand, expected action fraction, prompt.
GESTURES = (
    ('Conjure', 61101, 54, 'both', .45,
     'Combat stance. Bring both hands together in front of the chest with the fingers curled as if cupping a heavy glowing '
     'ball, draw them back slightly toward the body, then push both open palms forward at chest height to release the ball, '
     'slow and heavy. Hold the push for a moment, then return the hands to a guard.'),
    ('Lance', 61102, 44, 'right', .30,
     'Combat stance. Grip the right forearm with the left hand, then thrust the right arm straight forward at shoulder height '
     'with the index and middle fingers pointing, snapping it out hard. Hold the pointing arm perfectly steady, then pull it '
     'back to a guard.'),
    ('SkyCall', 61103, 54, 'right', .42,
     'Stand upright. Raise the right arm quickly straight up above the head with the palm open to the sky and look up, then '
     'sweep the arm down hard in front of the body as if pulling rain down out of the clouds. Return to a guard.'),
    ('GroundPlant', 61104, 54, 'right', .45,
     'Combat stance. Lean the torso forward and drive the right open palm down hard toward the ground in front of the feet, '
     'as if stamping a glowing seal onto the floor, with the left arm back for balance. Straighten up into a guard.'),
    ('Spiral', 61105, 60, 'both', .55,
     'Stand upright. Sweep both open hands in a wide circle around the body at waist height, then bring them up to the chest '
     'and throw both arms open wide to the sides with the palms facing out, as if releasing a ring of power around yourself. '
     'Lower the arms.'),
)


def find_asset(path):
    name = path.rsplit('/', 1)[1]
    return unreal.find_object(None, path + '.' + name) or unreal.load_object(None, path + '.' + name)


def save(asset):
    return SAVE.save_packages([asset.get_package()], False)


def load_source():
    unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous([FOLDER], True)
    return unreal.load_object(None, SOURCE + '.' + SOURCE.rsplit('/', 1)[1])


def entries():
    offset = 0
    for name, seed, frames, hand, fraction, prompt in GESTURES:
        yield dict(name=name, seed=seed, frames=frames, hand=hand, fraction=fraction, prompt=prompt, offset=offset)
        offset += frames + 12


def create_source():
    unreal.SystemLibrary.execute_console_command(None, 'AnimGenOffline.RetiredAnimationGC.Enabled 0')
    unreal.EditorAssetLibrary.make_directory(FOLDER)
    source = load_source() or TOOLS.create_asset(SOURCE.rsplit('/', 1)[1], FOLDER, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
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
        binding.set_display_name('Quinn | Crafting gestures')
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
                (ROOT / 'source-ready.json').write_text(json.dumps({'saved': saved, 'opened': opened, 'gestures': definitions}, indent=2))
                unreal.unregister_slate_post_tick_callback(state['handle'])
                return
            data = definitions[index]
            if state['request'] is not None and not state['request'].is_complete:
                return
            sections = mixer.get_sections()
            if len(sections) <= index:
                state['request'] = unreal.AnimGenOfflineMixerExtensions.add_generated_animation_section_async(mixer, index, data['offset'], generator)
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


def soma_retarget():
    """Retargets each finished take onto the hero. Takes arrive on Soma or on the bound Quinn mannequin, depending on
    the AnimGenOffline version and section settings; pick the retargeter from the take's skeleton."""
    body = find_asset(BODY)
    quinn = find_asset(QUINN)
    soma_mesh = find_asset(SOMA_MESH)
    report = {}
    for entry, section in zip(entries(), sections()):
        name = entry['name']
        inline = section_anim(section)
        if not inline or inline.data_model_interface.get_num_bone_tracks() < 20:
            report[name] = 'pending generation'
            continue
        hero_name = 'AS_Hero_Gesture' + name
        on_quinn = inline.get_skeleton() == quinn.get_editor_property('skeleton')
        source_mesh, rtg = (quinn, find_asset(MANNEQUIN_RTG)) if on_quinn else (soma_mesh, find_asset(SOMA_RTG))
        assert source_mesh and body and rtg, 'source mesh, hero body or retargeter missing'
        soma_folder = FOLDER + '/Source'
        soma_clip = unreal.load_object(None, soma_folder + '/' + hero_name + '.' + hero_name)
        if soma_clip is None:
            soma_clip = TOOLS.duplicate_asset(hero_name, soma_folder, inline)
        assert soma_clip and save(soma_clip), name
        spec = unreal.IKRetargetBatchOperationInputs(
            assets_to_retarget=[unreal.AssetRegistryHelpers.create_asset_data(soma_clip)],
            source_mesh=source_mesh, target_mesh=body, ik_retarget_asset=rtg,
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


def bake():
    body = find_asset(BODY)
    opts = unreal.AnimPoseEvaluationOptions()
    opts.set_editor_property('evaluation_type', unreal.AnimDataEvalType.RAW)
    opts.set_editor_property('optional_skeletal_mesh', body)
    notify_class = unreal.load_class(None, '/Script/reflections.ReflectionsSpellReleaseNotify')
    report = {}
    for entry in entries():
        name = entry['name']
        path = FOLDER + '/AS_Hero_Gesture' + name
        clip = unreal.find_object(None, path + '.AS_Hero_Gesture' + name) or unreal.load_object(None, path + '.AS_Hero_Gesture' + name)
        if not clip:
            report[name] = {'pending': True, 'note': 'run the soma stage first'}
            continue
        try:
            duration = clip.get_play_length()
            poses = []
            for i in range(int(duration * FPS) + 1):
                pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(clip, min(i / FPS, duration), opts)
                poses.append({b: unreal.AnimPoseExtensions.get_bone_pose(pose, b, unreal.AnimPoseSpaces.WORLD).translation.to_tuple()
                              for b in ('hand_r', 'hand_l', 'spine_03')})
            bones = ('hand_l', 'hand_r') if entry['hand'] == 'both' else ('hand_' + entry['hand'][0],)
            ideal = entry['fraction'] * len(poses)
            window = range(max(1, round(ideal - .25 * len(poses))), min(len(poses), round(ideal + .25 * len(poses))))

            def speed(i):
                s = sum(math.dist(poses[i][b], poses[i - 1][b]) for b in bones)
                return s * (1.0 - .35 * abs(i - ideal) / (.25 * len(poses)))
            peak = max(window, key=speed)
            release = min(len(poses) - 1, peak + 2)
            reach = max(math.dist(poses[release][b], poses[release]['spine_03']) for b in bones)
            if notify_class:
                if unreal.AnimationLibrary.is_valid_anim_notify_track_name(clip, 'Spell'):
                    unreal.AnimationLibrary.remove_animation_notify_events_by_track(clip, 'Spell')
                else:
                    unreal.AnimationLibrary.add_animation_notify_track(clip, 'Spell')
                unreal.AnimationLibrary.add_animation_notify_event(clip, 'Spell', release / FPS, notify_class)
            save(clip)
            report[name] = dict(clip=clip.get_path_name(), hand=entry['hand'], duration=duration, peak_frame=peak,
                                release_frame=release, release=release / FPS, reach=reach, notify=bool(notify_class))
        except Exception:
            report[name] = {'error': traceback.format_exc()}
    (ROOT / 'bake-report.json').write_text(json.dumps(report, indent=2))
    return report


stage = (ARGS or ['status'])[0]
RESULT = json.dumps({'source': create_source, 'status': status, 'soma': soma_retarget, 'bake': bake}[stage](), default=str, indent=1)
RESULT
