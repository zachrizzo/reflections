"""Prepare and bake spell-specific Kimodo animation sequences in Unreal 5.9."""
import json
import math
import time
import traceback
from pathlib import Path

import unreal

ROOT = Path(unreal.Paths.project_intermediate_dir()).resolve() / 'DistinctSpellCasts'
ROOT.mkdir(exist_ok=True)
FOLDER = '/Game/Characters/Hero/Animation/SpellCasts'
SOURCE = FOLDER + '/LS_Hero_DistinctSpellCasts_Kimodo'
QUINN = '/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple'
BODY = '/Game/Characters/Hero/Assembled/Hero/Body/SKM_MHC_Hero_BodyMesh'
RETARGET = '/Game/Characters/Hero/Animation/Locomotion/RTG_MannequinToHero'
EA = unreal.EditorAssetLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
FPS = 30

# Display name, C++ enum, seed, duration, release hand, action beat, motion prompt.
CASTS = (
    ('FlameBurst', 'FLAME_BURST', 30601, 102, 'both', .44, 'Keep both feet planted. Pull both fists to the ribs with bent elbows. Forcefully push both palms forward together at chest height. Bend both elbows, draw the hands back to the ribs, and drop both arms to the sides.'),
    ('Fireball', 'FIRESTORM', 30602, 126, 'right', .58, 'Stand with feet apart. Cup both hands near the right hip, roll both hands up to the right shoulder, then send the right palm forcefully forward and up. Let the left hand drop first. Bring the right hand back to the waist and relax. Keep feet planted.'),
    ('IceShard', 'ICE_SHARD', 30603, 96, 'left', .43, 'Stand in place. Lift the bent left elbow with the left hand next to the ear, then make a sharp, straight left-handed overarm throw. Finish with the left hand at chest height, draw it back and lower it. Keep the right hand near the waist.'),
    ('FrostNova', 'FROST_NOVA', 30604, 114, 'both', .51, 'Stand still with soft knees. Cross both forearms tightly over the collarbones, then snap both hands sharply outward and down near hip height with elbows slightly bent. Recover slowly, ending with both arms hanging.'),
    ('TidalSurge', 'TIDAL_SURGE', 30605, 126, 'both', .52, 'Plant both feet. Reach down with cupped hands near the knees, scoop them slowly up together to the waist, then make a broad rising two-handed shove out and up. Draw both hands down along the outside of the ribs, ending at the sides.'),
    ('WaterOrb', 'WATER_ORB', 30606, 126, 'left', .61, 'Stand still. Bring the hands together in front of the belly, then circle both wrists around one another while raising them toward the chest. Gently scoop and send the left palm forward and up like an underhand toss. Follow it with the eyes, then let both arms relax.'),
    ('LightningBurst', 'CHAIN_LIGHTNING', 30607, 108, 'right', .52, 'Stand upright with feet planted. Reach the left hand across the chest and touch the right wrist. Twist the torso right, pulling the right elbow back, then snap the right hand diagonally forward to the left with an open palm. Let both arms drop.'),
    ('LightningBolt', 'LIGHTNING_BOLT', 30608, 102, 'right', .50, 'Keep feet planted. Raise the right hand straight overhead, keeping the left hand by the left hip. Pause briefly. Bring the right hand sharply down and point straight forward from shoulder height. Retract the right hand and return both arms to the sides.'),
    ('ThunderWave', 'THUNDER_WAVE', 30609, 120, 'both', .52, 'Stand with feet apart without stepping. Pull bent elbows up next to the shoulders and raise both fists above the head. Slam both hands down to belly level with a short forward bend of the upper back. Uncurl and return the hands to the sides.'),
    ('StoneShard', 'STONE_SHARD', 30610, 108, 'right', .52, 'Plant both feet. Bend the torso and reach the right hand low across the front of the left thigh. With the left hand braced near the hip, sweep the right arm in a stiff underhand throw up to chest height, then return the right hand down.'),
    ('EarthShock', 'EARTH_SHOCK', 30611, 120, 'both', .53, 'Keep feet planted, right foot forward. Draw the right fist up to the ear while bracing the left palm in front of the chest. Punch the right fist hard down toward the right knee and lean down over it, then straighten the torso and drop both hands to the sides.'),
    ('ForcePush', 'FORCE_PUSH', 30612, 96, 'left', .49, 'Stand in place with planted feet. Keep the right hand back at the right hip. Raise the left palm in front of the sternum and sharply shove the left open hand straight forward at shoulder height. Pull the left elbow back in and drop the hand.'),
    ('ArcaneBolt', 'ARCANE_BOLT', 30613, 108, 'right', .53, 'Stand still. Bring the right hand up slowly in front of the face and circle it clockwise once at eye height with a bent elbow. Straighten the right arm forward, pointing from the shoulder. Bring the hand back in and lower it. The left hand stays on the hip.'),
    ('GreaterHeal', 'GREATER_HEAL', 30614, 132, 'both', .62, 'Stand upright, feet planted. Press both palms together low in front of the waist. Raise the joined hands slowly above the eyes, turn both palms outward, then separate them and lower them in two broad arcs. Finish with both arms relaxed at the sides.'),
    ('HealingPulse', 'HEALING_PULSE', 30615, 108, 'both', .55, 'Stand still. Place the left palm flat on the chest, then the right palm over the left. Press in and briefly bow the head. Open both forearms forward and down at waist height in a small, gentle motion. Relax both arms as the head lifts.'),
    ('ArcaneShield', 'SHIELD', 30616, 114, 'both', .54, 'Stand still. Lift both bent forearms in front of the face and cross them in an X. Then turn both forearms upright, slightly spread them and present the palms forward like blocking a doorway with elbows bent. Lower both arms and straighten.'),
)

# These frames follow the observed retargeted gesture when it differs from the prompt.
REVIEWED_RELEASES = {
    'FlameBurst': (18, 'both'),
    'Fireball': (44, 'right'),
    'IceShard': (62, 'left'),
    'FrostNova': (83, 'both'),
    'TidalSurge': (84, 'both'),
    'WaterOrb': (66, 'left'),
    'LightningBurst': (55, 'right'),
    'LightningBolt': (67, 'right'),
    'ThunderWave': (50, 'both'),
    'StoneShard': (63, 'left'),
    'EarthShock': (40, 'both'),
    'ForcePush': (20, 'left'),
    'ArcaneBolt': (45, 'right'),
    'GreaterHeal': (32, 'both'),
    'HealingPulse': (67, 'both'),
    'ArcaneShield': (78, 'both'),
}

def entries():
    offset = 0
    for name, enum, seed, frames, hand, fraction, prompt in CASTS:
        yield dict(name=name, enum=enum, seed=seed, frames=frames, hand=hand,
                   fraction=fraction, prompt=prompt, offset=offset)
        offset += frames + 12

def create_source():
    source = EA.load_asset(SOURCE) if EA.does_asset_exist(SOURCE) else TOOLS.create_asset(
        SOURCE.rsplit('/', 1)[1], FOLDER, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
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
        binding.set_display_name('Quinn | Distinct spell casts')
        binding.get_object_template().get_editor_property('skeletal_mesh_component').set_skeletal_mesh_asset(EA.load_asset(QUINN))
        mixer = binding.add_track(unreal.MovieSceneAnimationMixerTrack)
    generator = unreal.load_class(None, '/Script/Kimodo.KimodoPoseGenerator')
    state = {'request': None, 'i': 0, 'start': time.monotonic()}
    def attach(delta):
        try:
            if time.monotonic() - state['start'] > 150:
                raise TimeoutError('Kimodo section insertion timed out')
            index = state['i']
            if index == len(definitions):
                assert EA.save_loaded_asset(source, False)
                assert unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(source)
                unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
                (ROOT / 'source-ready.json').write_text(json.dumps(definitions, indent=2))
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

def bake():
    source = EA.load_asset(SOURCE)
    mixer = next(t for t in source.get_bindings()[0].get_tracks() if isinstance(t, unreal.MovieSceneAnimationMixerTrack))
    sections = mixer.get_sections()
    quinn, body, retargeter = (EA.load_asset(path) for path in (QUINN, BODY, RETARGET))
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    opts = unreal.AnimPoseEvaluationOptions()
    opts.set_editor_property('evaluation_type', unreal.AnimDataEvalType.RAW)
    opts.set_editor_property('optional_skeletal_mesh', body)
    report = {}
    for entry, section in zip(entries(), sections):
        name = entry['name']
        inline = unreal.load_object(None, section.get_path_name() + '.AnimSequence_0')
        if not inline or inline.data_model_interface.get_num_bone_tracks() < 20:
            report[name] = {'pending': True}
            continue
        try:
            raw_name = 'AS_Quinn_' + name + '_Kimodo'
            raw_path = FOLDER + '/' + raw_name
            raw = EA.load_asset(raw_path) if EA.does_asset_exist(raw_path) else TOOLS.duplicate_asset(raw_name, FOLDER, inline)
            assert raw and EA.save_loaded_asset(raw, False)
            target = FOLDER + '/AS_Hero_' + name
            if EA.does_asset_exist(target):
                clip = EA.load_asset(target)
            else:
                spec = unreal.IKRetargetBatchOperationInputs(
                    assets_to_retarget=[registry.get_asset_by_object_path(raw.get_path_name())],
                    source_mesh=quinn, target_mesh=body, ik_retarget_asset=retargeter,
                    target_path=FOLDER, use_source_path=False, include_referenced_assets=False,
                    overwrite_existing_files=False, suffix='_HeroRetarget')
                result = unreal.IKRetargetBatchOperation.run_batch_retarget(spec)
                assert len(result) == 1
                assert EA.rename_asset(result[0].get_asset().get_path_name().split('.')[0], target)
                clip = EA.load_asset(target)
            assert clip.get_skeleton() == body.get_editor_property('skeleton')
            clip.set_preview_skeletal_mesh(body)
            clip.set_editor_property('enable_root_motion', False)
            clip.set_editor_property('force_root_lock', True)
            assert EA.save_loaded_asset(clip, False)
            duration = clip.get_play_length()
            poses = []
            tracked_bones = ('pelvis', 'spine_03', 'neck_01', 'head',
                             'clavicle_r', 'upperarm_r', 'lowerarm_r', 'hand_r',
                             'clavicle_l', 'upperarm_l', 'lowerarm_l', 'hand_l')
            for i in range(int(duration * FPS) + 1):
                pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(clip, min(i / FPS, duration), opts)
                assert pose.is_valid()
                poses.append({
                    bone: unreal.AnimPoseExtensions.get_bone_pose(pose, bone, unreal.AnimPoseSpaces.WORLD).translation.to_tuple()
                    for bone in tracked_bones
                })
            hand_travel = {bone: max(math.dist(row[bone], poses[0][bone]) for row in poses) for bone in ('hand_r', 'hand_l')}
            release_bones = ('hand_l', 'hand_r') if entry['hand'] == 'both' else ('hand_' + entry['hand'][0],)
            ideal = entry['fraction'] * len(poses)
            window = range(max(1, round(ideal - .23 * len(poses))), min(len(poses), round(ideal + .23 * len(poses))))
            def movement(i):
                speed = sum(math.dist(poses[i][bone], poses[i - 1][bone]) for bone in release_bones)
                return speed * (1.0 - .4 * abs(i - ideal) / (.23 * len(poses)))
            release = max(window, key=movement) / FPS
            report[name] = dict(clip=clip.get_path_name(), enum=entry['enum'], hand=entry['hand'], duration=duration,
                                hand_travel=hand_travel, release=release, poses=poses)
        except Exception:
            report[name] = {'error': traceback.format_exc()}
    (ROOT / 'bake-report.json').write_text(json.dumps(report, indent=2))

def save_source():
    assert EA.save_loaded_asset(EA.load_asset(SOURCE), False)

def integrate():
    report = json.loads((ROOT / 'bake-report.json').read_text())
    bp = EA.load_asset('/Game/Characters/Hero/Gameplay/BP_HeroPlayer')
    generated = EA.load_blueprint_class(bp.get_path_name())
    defaults = unreal.get_default_object(generated)
    spells = dict(defaults.get_editor_property('spells'))
    for name, (release_frame, hand) in REVIEWED_RELEASES.items():
        result = report[name]
        assert 'clip' in result and max(result['hand_travel'].values()) >= 15, name
        assert 0 < release_frame / FPS < result['duration'], name
        enum = getattr(unreal.HeroSpell, result['enum'])
        socket = {'left': 'hand_l', 'right': 'hand_r'}.get(hand, 'None')
        spells[enum] = unreal.HeroSpellDefinition(
            animation=EA.load_asset(result['clip']), release_time=release_frame / FPS, projectile_socket=socket)
    clips = [spell.animation.get_path_name() for spell in spells.values() if spell.animation]
    assert len(clips) == len(set(clips)) == 20, clips
    defaults.modify()
    defaults.set_editor_property('spells', spells)
    assert EA.save_loaded_asset(bp, False)
    verified = {str(spell): spec.animation.get_path_name() for spell, spec in defaults.get_editor_property('spells').items() if spec.animation}
    (ROOT / 'integrated.json').write_text(json.dumps(verified, indent=2))

