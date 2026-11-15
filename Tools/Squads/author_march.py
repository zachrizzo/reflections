"""Generate the soldier march cycle with Kimodo (UE 5.9) and retarget it to both soldier skeletons.

Runs inside the editor's execute_python with ARGS = [stage] prepended (top-level await is used):
  source - create /Game/Squads/Animation/LS_Soldier_March_Kimodo: a Quinn spawnable with one generated (Kimodo)
           section, opened in Sequencer, then generation armed by a finished editor transaction on the section
           (Kimodo only queues work on a transaction while Sequencer shows the section). ~20 s on the GPU.
  status - is the take there yet
  bake   - copy the take (it lands on the bound Quinn mesh, SK_Mannequin skeleton), retarget it with the existing
           RTG_MannequinToHero (IvenRook/hero skeleton: caster looks) and RTG_Crowd_BridgeGuard (BridgeGuard skeleton:
           melee looks), crop both to the best-looping cycle, lock the root (plays in place) and save.
What it produced on 2026-11-14 (seed 61201): cycle frames 88-117 (0.97 s, two steps, ~124 steps/min), 80 cm steps,
~157 cm/s on the ground -> AS_Soldier_March_Iven, AS_Soldier_March_BridgeGuard (MarchAnimationSpeed 155).
"""
import asyncio
import json
import math
import time

FOLDER = '/Game/Squads/Animation'
SOURCE = FOLDER + '/LS_Soldier_March_Kimodo'
QUINN = '/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple'
HERO_BODY = '/Game/Characters/Hero/Assembled/Hero/Body/SKM_MHC_Hero_BodyMesh'
BG_BODY = '/Game/Characters/RedLondon/BridgeGuard/Assembled/BridgeGuard/Body/SKM_MHC_BridgeGuard_BodyMesh'
RTG_HERO = '/Game/Characters/Hero/Animation/Locomotion/RTG_MannequinToHero'
RTG_BG = '/Game/Characters/CrowdMotion/RTG_Crowd_BridgeGuard'
FPS = 30
FRAMES = 120
SEED = 61201
PROMPT = ('A soldier marching in formation at a steady, unhurried pace, walking straight ahead. Upright posture, chest '
          'out, chin up, eyes forward. Firm heel-to-toe steps with a slightly longer stride than normal walking. Both '
          'arms hang straight and swing forward and back in a strict rhythm opposite to the legs, hands loosely closed. '
          'No turning, no looking around, the same rhythm the whole time.')
LOOP_BONES = ['thigh_l', 'thigh_r', 'calf_l', 'calf_r', 'upperarm_l', 'upperarm_r', 'lowerarm_l', 'lowerarm_r']
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
SAVE = unreal.EditorLoadingAndSavingUtils


def find_asset(path):
    name = path.rsplit('/', 1)[1]
    return unreal.find_object(None, path + '.' + name) or unreal.load_object(None, path + '.' + name)


def save(asset):
    return SAVE.save_packages([asset.get_package()], False)


def mixer_of(source):
    return next(t for t in source.get_bindings()[0].get_tracks() if isinstance(t, unreal.MovieSceneAnimationMixerTrack))


def take(source):
    section = mixer_of(source).get_sections()[0]
    prefix = section.get_path_name() + '.AnimSequence_'
    best, best_index = None, -1
    for anim in unreal.ObjectIterator(unreal.AnimSequence):
        path = anim.get_path_name()
        if path.startswith(prefix) and path[len(prefix):].isdigit() and int(path[len(prefix):]) > best_index:
            best, best_index = anim, int(path[len(prefix):])
    return best


async def source_stage():
    unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous([FOLDER], True)
    source = unreal.load_object(None, SOURCE + '.LS_Soldier_March_Kimodo')
    if source is None:
        source = TOOLS.create_asset('LS_Soldier_March_Kimodo', FOLDER, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    save(source)
    source.set_display_rate(unreal.FrameRate(FPS, 1))
    source.set_playback_start(0)
    source.set_playback_end(FRAMES)
    if source.get_bindings():
        mixer = mixer_of(source)
    else:
        binding = source.add_spawnable_from_class(unreal.SkeletalMeshActor)
        binding.set_display_name('Quinn | Soldier march')
        binding.get_object_template().get_editor_property('skeletal_mesh_component').set_editor_property(
            'skeletal_mesh_asset', find_asset(QUINN))
        mixer = binding.add_track(unreal.MovieSceneAnimationMixerTrack)
    if not mixer.get_sections():
        generator = unreal.load_class(None, '/Script/Kimodo.KimodoPoseGenerator')
        request = unreal.AnimGenOfflineMixerExtensions.add_generated_animation_section_async(mixer, 0, 0, generator)
        started = time.monotonic()
        while not request.is_complete and time.monotonic() - started < 60:
            await asyncio.sleep(0.1)
    section = mixer.get_sections()[0]
    section.set_range(0, FRAMES)
    settings = section.get_editor_property('pose_generator')
    settings.set_editor_property('RandomSeed', SEED)
    settings.set_editor_property('movement_source', unreal.AnimGenOfflineMovementSource.GENERATED_ANIMATION)
    save(source)
    unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(source)
    await asyncio.sleep(1.2)
    with unreal.ScopedEditorTransaction('Generate soldier march'):
        section.modify()
        section.get_editor_property('pose_generator').set_editor_property('AnimDescriptionOverride', PROMPT)
    return 'generation armed; run status in ~30 s, then bake (save the sequence once the take exists)'


def status_stage():
    inline = take(find_asset(SOURCE))
    return {'ready': bool(inline) and inline.data_model_interface.get_num_bone_tracks() >= 20,
            'take': inline.get_path_name() if inline else None}


def angle_deg(a, b):
    d = abs(a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w)
    return math.degrees(2.0 * math.acos(min(1.0, d)))


def best_loop(clip):
    n = int(round(clip.get_play_length() * FPS)) + 1
    pose = lambda f: [unreal.AnimationLibrary.get_bone_pose_for_frame(clip, b, f, False).rotation for b in LOOP_BONES]
    poses = [pose(f) for f in range(n)]
    best = (1e9, 0, 0)
    for a in range(20, n - 30):
        for length in range(24, 46):
            b = a + length
            if b >= n:
                break
            score = sum(angle_deg(x, y) for x, y in zip(poses[a], poses[b]))
            best = min(best, (score, a, b))
    return best


def retarget(clip, source_mesh, target_mesh, rtg, suffix):
    spec = unreal.IKRetargetBatchOperationInputs(
        assets_to_retarget=[unreal.AssetRegistryHelpers.create_asset_data(clip)],
        source_mesh=source_mesh, target_mesh=target_mesh, ik_retarget_asset=rtg,
        target_path=FOLDER, use_source_path=False, include_referenced_assets=False,
        overwrite_existing_files=True, suffix=suffix)
    return unreal.IKRetargetBatchOperation.run_batch_retarget(spec)[0].get_asset()


def crop(clip, a, b):
    ctrl = clip.get_editor_property('controller')
    total = int(round(clip.get_play_length() * FPS))
    ctrl.open_bracket(unreal.Text('Crop march cycle'), False)
    ctrl.resize_in_frames(unreal.FrameNumber(b), unreal.FrameNumber(b), unreal.FrameNumber(total), False)
    ctrl.resize_in_frames(unreal.FrameNumber(b - a), unreal.FrameNumber(0), unreal.FrameNumber(a), False)
    ctrl.close_bracket(False)


def bake_stage():
    source = find_asset(SOURCE)
    inline = take(source)
    assert inline and inline.data_model_interface.get_num_bone_tracks() >= 20, 'take not generated yet'
    save(source)
    copy = unreal.load_object(None, FOLDER + '/Soma/AS_Soldier_March.AS_Soldier_March') or \
        TOOLS.duplicate_asset('AS_Soldier_March', FOLDER + '/Soma', inline)
    save(copy)
    score, a, b = best_loop(copy)
    out = {'loop': [a, b], 'seconds': (b - a) / FPS, 'loop_error_deg': round(score, 1)}
    for rtg, mesh, suffix in ((RTG_HERO, HERO_BODY, '_Iven'), (RTG_BG, BG_BODY, '_BridgeGuard')):
        clip = retarget(copy, find_asset(QUINN), find_asset(mesh), find_asset(rtg), suffix)
        crop(clip, a, b)
        clip.set_preview_skeletal_mesh(find_asset(mesh))
        clip.set_editor_property('enable_root_motion', False)
        clip.set_editor_property('force_root_lock', True)
        save(clip)
        out[clip.get_name()] = [clip.get_path_name(), round(clip.get_play_length(), 3)]
    unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
    return out


stage = (ARGS or ['status'])[0]
if stage == 'source':
    result = await source_stage()
elif stage == 'bake':
    result = bake_stage()
else:
    result = status_stage()
json.dumps(result, default=str, indent=1)
