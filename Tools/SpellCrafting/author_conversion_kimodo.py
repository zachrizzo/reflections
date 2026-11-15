"""Kimodo takes for the villain's conversion beat: a victim pinned and convulsing as a black wisp enters their chest
(sharp sideways neck wrench, back arching) before rising turned, and an attacker kneeling over them pouring the wisp
in with the right hand. Eerie, not gory (teen rating). Requested for the villain session.

Runs inside the editor via the MCP Python tool (top-level await allowed). ARGS stage [round]:
  source [2]    add the generator sections to the round's LevelSequence in /Game/Villain/Conversion/Source, open it
  arm [2]       with the sequence open: re-apply every prompt in finished transactions (this is what queues Kimodo)
  status [2]    which takes have finished generating
  retarget [2]  build RTG_Mannequin_to_UEFN once, retarget each take to SK_UEFN_Mannequin (the NPC drivers' skeleton)
  clamp [2]     limit neck_01/neck_02/head rotation from the reference pose so the twist never folds a joint
  possess       authored possession overlay (arch, jerks, tremor, sideways neck wrench) on the round-2 convulse takes
                -> AS_Conversion_Victim_Possessed_A/_B, clamped
  review        offscreen captures (unreliable: editor-world meshes do not re-pose offscreen; use draw_pose_sheet.py
                on exported bone positions instead)
Generation only starts when the AnimGenOffline editor mode sees a finished transaction on a section while the sequence
is open, and a PIE start cancels it, so take the shared PIE lock (Saved/PIE_LOCK.json) while arming and generating.
Results 2026-11-14: round 1 victims never got up and convulsed only mildly; round 2 split the beat into convulse and
rise; Kimodo's convulsions stayed calm, so the possession is authored on top. Delivered: Victim_Possessed_A/B,
Victim_Rise_E/F, Attacker_B/C. The superseded retargeted takes (Victim_A/B, Attacker_A, Victim_Convulse_C/D) were
deleted after delivery; to re-run `possess`, run `retarget 2` first (the Kimodo sources stay in Source/).
"""
import base64
import json
import math
import os
import time
import traceback
from pathlib import Path

ROOT = Path(unreal.Paths.project_intermediate_dir()).resolve() / 'VillainConversion'
ROOT.mkdir(exist_ok=True)
FOLDER = '/Game/Villain/Conversion'
SOURCE = FOLDER + '/Source/LS_Conversion_Kimodo'
RTG = FOLDER + '/Rigs/RTG_Mannequin_to_UEFN'
QUINN = '/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple'
UEFN = '/Game/Characters/UEFN_Mannequin/Meshes/SKM_UEFN_Mannequin'
IK_UE5 = '/Game/Characters/UE5_Mannequins/Rigs/IK_UE5_Mannequin_Retarget'
IK_UEFN = '/Game/Characters/UEFN_Mannequin/Rigs/IK_UEFN_Mannequin'
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
FPS = 30
X = unreal.AnimPoseExtensions

VICTIM = ('A person lies flat on their back on the ground. Suddenly the whole body jerks and convulses as if pinned down '
          'by an invisible weight on the chest: the back arches up off the ground, the arms twitch stiffly at the sides, '
          'and the head and neck wrench sharply to one side in an unnatural twist. ')
ATTACKER = 'A person kneels over someone lying on the ground in front of them, leaning forward over the body. '
TAKES = (
    ('Victim_A', 72101, 180, VICTIM + 'The spasms stop abruptly; after a still moment the person rises slowly and stiffly '
     'to their feet and stands upright, the head tilted at an odd angle.'),
    ('Victim_B', 72102, 180, VICTIM + 'The head snaps to the other side, the chest heaves upward twice, then the body goes '
     'limp; the person pushes up off the ground and stands, swaying, unnaturally rigid.'),
    ('Attacker_A', 72201, 150, ATTACKER + 'Kneeling on one knee, the right arm is extended straight out and down over the '
     'body\'s chest, palm down and fingers spread, held steady as if pouring something into it; the left hand rests on '
     'the raised knee. Slow, intense breathing, holding the pose.'),
    ('Attacker_B', 72202, 150, ATTACKER + 'Kneeling on both knees, torso bent low, the right hand reaches out toward the '
     'chest of the body below with the fingers splayed, the arm trembling slightly with effort, the left arm held back '
     'for balance. Stay leaning in, holding the pose.'),
)
# Round 2: round 1's victims never got up and convulsed only mildly, and Attacker_A kept its arm folded. One action per
# take reads better for Kimodo, so the beat is split into a convulse clip and a rise clip the villain can chain.
TAKES_R2 = (
    ('Victim_Convulse_C', 72301, 120, 'A person lies on their back on the ground and convulses violently in sharp jerks: '
     'the back arches high off the ground and drops again, the head whips hard to one side and stays twisted, the arms '
     'and legs spasm stiffly. The body never leaves the ground.'),
    ('Victim_Convulse_D', 72302, 120, 'A person lying on their back is seized by violent spasms: the chest is thrown '
     'upward again and again as if pulled by an invisible hook, the back bends into a high arch, the head jerks and '
     'twists sharply sideways, the fingers claw at the ground.'),
    ('Victim_Rise_E', 72303, 120, 'A person lying flat on their back gets up slowly and stiffly in an unnatural way, '
     'rising to stand upright, then stands completely still with the head tilted to one side and the arms hanging limp.'),
    ('Victim_Rise_F', 72304, 120, 'A person lying on their back sits up rigidly, then rises to their feet in one slow, '
     'stiff motion as if pulled up by strings, and stands still, swaying slightly.'),
    ('Attacker_C', 72305, 150, 'A person kneels on one knee and reaches the right arm fully straight out and down in '
     'front of them, palm open toward the ground about knee height, fingers spread, holding that outstretched arm still '
     'as if pouring something downward; the left hand rests on the knee. Hold this pose, leaning forward.'),
)
ROUND = ARGS[1] if ARGS and len(ARGS) > 1 and ARGS[0] in ('source', 'arm', 'status', 'retarget', 'clamp') else '1'
if ROUND == '2':
    SOURCE = FOLDER + '/Source/LS_Conversion_Kimodo_R2'
    TAKES = TAKES_R2

# Local-rotation limits from the reference pose (degrees): enough for a wrench that reads as wrong, not enough to
# fold the neck skin through the collar.
NECK_LIMITS = {'neck_01': 35.0, 'neck_02': 35.0, 'head': 45.0}
holder = []


def find_asset(path):
    name = path.rsplit('/', 1)[1]
    return unreal.find_object(None, path + '.' + name) or unreal.load_object(None, path + '.' + name)


def save(asset):
    return unreal.EditorLoadingAndSavingUtils.save_packages([asset.get_package()], False)


def entries():
    offset = 0
    for name, seed, frames, prompt in TAKES:
        yield dict(name=name, seed=seed, frames=frames, prompt=prompt, offset=offset)
        offset += frames + 12


def load_source():
    unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous([FOLDER], True)
    return unreal.load_object(None, SOURCE + '.' + SOURCE.rsplit('/', 1)[1])


def mixer_of(source):
    return next(t for t in source.get_bindings()[0].get_tracks() if isinstance(t, unreal.MovieSceneAnimationMixerTrack))


def create_source():
    unreal.SystemLibrary.execute_console_command(None, 'AnimGenOffline.RetiredAnimationGC.Enabled 0')
    for sub in ('', '/Source', '/Rigs'):
        unreal.EditorAssetLibrary.make_directory(FOLDER + sub)
    source = load_source() or TOOLS.create_asset(SOURCE.rsplit('/', 1)[1], FOLDER + '/Source', unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    save(source)
    holder.append(source)
    defs = list(entries())
    end = defs[-1]['offset'] + defs[-1]['frames']
    source.set_display_rate(unreal.FrameRate(FPS, 1))
    source.set_playback_start(0)
    source.set_playback_end(end)
    source.set_view_range(-.15, end / FPS + .3)
    source.set_work_range(-1., end / FPS + 1.)
    if source.get_bindings():
        mixer = mixer_of(source)
    else:
        binding = source.add_spawnable_from_class(unreal.SkeletalMeshActor)
        binding.set_display_name('Quinn | Villain conversion')
        binding.get_object_template().get_editor_property('skeletal_mesh_component').set_editor_property('skeletal_mesh_asset', find_asset(QUINN))
        mixer = binding.add_track(unreal.MovieSceneAnimationMixerTrack)
    generator = unreal.load_class(None, '/Script/Kimodo.KimodoPoseGenerator')
    state = {'request': None, 'i': 0, 'start': time.monotonic(), 'phase': 'add'}

    def tick(delta):
        try:
            if time.monotonic() - state['start'] > 240:
                raise TimeoutError('section insertion timed out')
            if state['phase'] == 'add':
                index = state['i']
                if index == len(defs):
                    save(source)
                    unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(source)
                    state['phase'] = 'arm'
                    state['armed_at'] = time.monotonic()
                    return
                data = defs[index]
                if state['request'] is not None and not state['request'].is_complete:
                    return
                sections = mixer.get_sections()
                if len(sections) <= index:
                    state['request'] = unreal.AnimGenOfflineMixerExtensions.add_generated_animation_section_async(mixer, index, data['offset'], generator)
                    return
                section = sections[index]
                section.set_range(data['offset'], data['offset'] + data['frames'])
                g = section.get_editor_property('pose_generator')
                g.set_editor_property('RandomSeed', data['seed'])
                g.set_editor_property('movement_source', unreal.AnimGenOfflineMovementSource.GENERATED_ANIMATION)
                state['i'] += 1
                state['request'] = None
                return
            if time.monotonic() - state['armed_at'] < 1.0:
                return
            for data, section in zip(defs, mixer.get_sections()):
                with unreal.ScopedEditorTransaction('Generate conversion ' + data['name']):
                    section.modify()
                    section.get_editor_property('pose_generator').set_editor_property('AnimDescriptionOverride', data['prompt'])
            (ROOT / 'source-ready.json').write_text(json.dumps({'takes': defs}, indent=2))
            unreal.unregister_slate_post_tick_callback(state['handle'])
        except Exception:
            (ROOT / 'source-error.txt').write_text(traceback.format_exc())
            unreal.unregister_slate_post_tick_callback(state['handle'])
            raise

    state['handle'] = unreal.register_slate_post_tick_callback(tick)
    return 'source authoring started'


def arm():
    """Re-arm generation when PIE knocked the AnimGenOffline mode out: with the sequence already open in Sequencer
    (open it in an earlier call), re-apply every prompt in its own finished transactions. Synchronous; a slate
    tick callback registered from an MCP call did not fire reliably."""
    unreal.SystemLibrary.execute_console_command(None, 'AnimGenOffline.RetiredAnimationGC.Enabled 0')
    source = load_source()
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() != source:
        unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(source)
        return 'opened; call arm again'
    armed = []
    for data, section in zip(entries(), mixer_of(source).get_sections()):
        with unreal.ScopedEditorTransaction('Generate conversion ' + data['name']):
            section.modify()
            section.get_editor_property('pose_generator').set_editor_property('AnimDescriptionOverride', data['prompt'] + ' ')
        with unreal.ScopedEditorTransaction('Generate conversion ' + data['name'] + ' (prompt)'):
            section.modify()
            section.get_editor_property('pose_generator').set_editor_property('AnimDescriptionOverride', data['prompt'])
        armed.append(data['name'])
    return armed


def section_anim(section):
    prefix = section.get_path_name() + '.AnimSequence_'
    best, best_index = None, -1
    for anim in unreal.ObjectIterator(unreal.AnimSequence):
        path = anim.get_path_name()
        if path.startswith(prefix) and path[len(prefix):].isdigit() and int(path[len(prefix):]) > best_index:
            best, best_index = anim, int(path[len(prefix):])
    return best


def status():
    out = {}
    for data, section in zip(entries(), mixer_of(load_source()).get_sections()):
        inline = section_anim(section)
        out[data['name']] = bool(inline) and inline.data_model_interface.get_num_bone_tracks() >= 20
    return out


def retargeter():
    """UE5 mannequin (Kimodo's Quinn takes) -> UEFN mannequin (the NPC locomotion drivers)."""
    rtg = unreal.load_object(None, RTG + '.' + RTG.rsplit('/', 1)[1])
    if rtg:
        return rtg
    rtg = TOOLS.create_asset(RTG.rsplit('/', 1)[1], RTG.rsplit('/', 1)[0], unreal.IKRetargeter, unreal.IKRetargetFactory())
    c = unreal.IKRetargeterController.get_controller(rtg)
    src, tgt = unreal.RetargetSourceOrTarget.SOURCE, unreal.RetargetSourceOrTarget.TARGET
    c.set_ik_rig(src, find_asset(IK_UE5))
    c.set_ik_rig(tgt, find_asset(IK_UEFN))
    c.set_preview_mesh(src, find_asset(QUINN))
    c.set_preview_mesh(tgt, find_asset(UEFN))
    if c.get_num_retarget_ops() == 0:
        c.add_default_ops()
    c.assign_ik_rig_to_all_ops(tgt, find_asset(IK_UEFN))
    c.auto_map_chains(unreal.AutoMapChainType.EXACT, True)
    save(rtg)
    return rtg


def retarget():
    quinn, uefn = find_asset(QUINN), find_asset(UEFN)
    rtg = retargeter()
    out = {}
    for data, section in zip(entries(), mixer_of(load_source()).get_sections()):
        inline = section_anim(section)
        if not inline or inline.data_model_interface.get_num_bone_tracks() < 20:
            out[data['name']] = 'pending'
            continue
        name = 'AS_Conversion_' + data['name']
        src = unreal.load_object(None, FOLDER + '/Source/' + name + '.' + name) or TOOLS.duplicate_asset(name, FOLDER + '/Source', inline)
        save(src)
        spec = unreal.IKRetargetBatchOperationInputs(
            assets_to_retarget=[unreal.AssetRegistryHelpers.create_asset_data(src)], source_mesh=quinn, target_mesh=uefn,
            ik_retarget_asset=rtg, target_path=FOLDER, use_source_path=False, include_referenced_assets=False,
            overwrite_existing_files=True, suffix='')
        clip = unreal.IKRetargetBatchOperation.run_batch_retarget(spec)[0].get_asset()
        clip.set_preview_skeletal_mesh(uefn)
        save(clip)
        out[data['name']] = {'clip': clip.get_path_name(), 'skeleton': clip.get_skeleton().get_path_name(),
                             'seconds': round(clip.get_play_length(), 2)}
    return out


def quat_angle(q):
    w = max(-1.0, min(1.0, abs(q.w)))
    return math.degrees(2.0 * math.acos(w))


def scale_rotation(q, factor):
    """Slerp from identity to q by factor (q unit, shortest arc)."""
    if q.w < 0:
        q = unreal.Quat(-q.x, -q.y, -q.z, -q.w)
    half = math.acos(max(-1.0, min(1.0, q.w)))
    if half < 1e-6:
        return unreal.Quat(0, 0, 0, 1)
    s = math.sin(half)
    axis = (q.x / s, q.y / s, q.z / s)
    nh = half * factor
    ns = math.sin(nh)
    return unreal.Quat(axis[0] * ns, axis[1] * ns, axis[2] * ns, math.cos(nh))


def inv(q):
    return unreal.Quat(-q.x, -q.y, -q.z, q.w)


def clamp_clip(clip):
    """Clamp neck_01/neck_02/head local rotation away from the reference pose to NECK_LIMITS, keeping direction."""
    uefn = find_asset(UEFN)
    opts = unreal.AnimPoseEvaluationOptions()
    opts.set_editor_property('evaluation_type', unreal.AnimDataEvalType.RAW)
    opts.set_editor_property('optional_skeletal_mesh', uefn)
    ref = X.get_reference_pose(clip.get_skeleton())
    model = clip.data_model_interface
    report, keys, peak = {}, {}, (0.0, 0)
    tracked = {str(n) for n in model.get_bone_track_names()}
    bones = [b for b in NECK_LIMITS if b in tracked]
    ref_rot = {b: X.get_ref_bone_pose(ref, b, unreal.AnimPoseSpaces.LOCAL).rotation for b in bones}
    for b in bones:
        keys[b] = []
        report[b] = {'max_before': 0.0, 'max_after': 0.0, 'frames_clamped': 0}
    for i in range(model.get_number_of_keys()):
        pose = X.get_anim_pose_at_frame(clip, i, opts)
        twist = 0.0
        for b in bones:
            t = X.get_bone_pose(pose, b, unreal.AnimPoseSpaces.LOCAL)
            delta = inv(ref_rot[b]) * t.rotation
            angle = quat_angle(delta)
            twist += angle
            limit = NECK_LIMITS[b]
            r = report[b]
            r['max_before'] = max(r['max_before'], round(angle, 1))
            rot = t.rotation
            if angle > limit:
                rot = ref_rot[b] * scale_rotation(delta, limit / angle)
                r['frames_clamped'] += 1
            r['max_after'] = max(r['max_after'], round(min(angle, limit), 1))
            keys[b].append((t.translation, rot, t.scale3d))
        if twist > peak[0]:
            peak = (twist, i)
    if any(r['frames_clamped'] for r in report.values()):
        c = clip.get_editor_property('controller')
        c.open_bracket(unreal.Text('Clamp neck twist'), False)
        for b, xs in keys.items():
            c.set_bone_track_keys(b, [x[0] for x in xs], [x[1] for x in xs], [x[2] for x in xs], False)
        c.close_bracket(False)
        save(clip)
    return {'bones': report, 'peak_twist_frame': peak[1], 'peak_twist_sum_deg': round(peak[0], 1)}


def clamp():
    out = {}
    for data in entries():
        name = 'AS_Conversion_' + data['name']
        clip = unreal.load_object(None, FOLDER + '/' + name + '.' + name)
        out[data['name']] = clamp_clip(clip) if clip else 'missing'
    (ROOT / 'clamp.json').write_text(json.dumps(out, indent=2))
    return out


def axis_quat(axis, degrees):
    half = math.radians(degrees) * 0.5
    s = math.sin(half)
    return unreal.Quat(axis.x * s, axis.y * s, axis.z * s, math.cos(half))


def smoothstep(a, b, t):
    x = max(0.0, min(1.0, (t - a) / (b - a)))
    return x * x * (3 - 2 * x)


def jerks(t, times, amps):
    """Sum of sharp impulses: 0.06 s rise, 0.18 s decay."""
    total = 0.0
    for t0, amp in zip(times, amps):
        x = t - t0
        if x < 0:
            continue
        total += amp * (x / 0.06 if x < 0.06 else math.exp(-(x - 0.06) / 0.18))
    return min(total, 1.2)


SPINE = ('spine_01', 'spine_02', 'spine_04', 'spine_05')
NECK = ('neck_01', 'neck_02', 'head')
LIMBS = ('upperarm_l', 'upperarm_r', 'lowerarm_l', 'lowerarm_r', 'thigh_l', 'thigh_r', 'calf_l', 'calf_r')


def possess(base_name, out_name, side, seed):
    """Authored possession on a Kimodo lying clip: a back arch (lower spine lifts, upper spine comes down so the chest
    rises while pelvis and head stay down), convulsive jerks with a 10-14 Hz tremor on spine and limbs, and a sharp
    sideways neck wrench at 1.25 s that holds, then eases. Rotations are applied per bone in component space around
    the body's own axes each frame, then the neck limits are enforced by clamp_clip."""
    import random
    rng = random.Random(seed)
    base = unreal.load_object(None, '%s/AS_Conversion_%s.AS_Conversion_%s' % (FOLDER, base_name, base_name))
    clip = unreal.load_object(None, '%s/%s.%s' % (FOLDER, out_name, out_name)) or TOOLS.duplicate_asset(out_name, FOLDER, base)
    opts = unreal.AnimPoseEvaluationOptions()
    opts.set_editor_property('evaluation_type', unreal.AnimDataEvalType.RAW)
    opts.set_editor_property('optional_skeletal_mesh', find_asset(UEFN))
    W, L = unreal.AnimPoseSpaces.WORLD, unreal.AnimPoseSpaces.LOCAL
    edited = SPINE + NECK + LIMBS
    times = sorted(rng.uniform(0.3, 3.1) for _ in range(8))
    amps = [rng.uniform(0.55, 1.0) for _ in times]
    limb_axes = {}
    for b in LIMBS:
        v = unreal.Vector(rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))
        limb_axes[b] = (v.normal(), rng.uniform(0, 6.28))
    keys = {b: [] for b in edited}
    n = clip.data_model_interface.get_number_of_keys()
    for i in range(n):
        t = i / FPS
        pose = X.get_anim_pose_at_frame(base, i, opts)
        comp = {b: X.get_bone_pose(pose, b, W) for b in edited + ('pelvis', 'clavicle_l', 'clavicle_r')}
        lat = (comp['clavicle_l'].translation - comp['clavicle_r'].translation).normal()
        along = (comp['head'].translation - comp['pelvis'].translation).normal()
        front = lat.cross(along).normal()
        lift = 1.0 if front.z >= 0 else -1.0
        j = jerks(t, times, amps)
        arch = min(1.3, smoothstep(0.4, 1.5, t) * (1 - 0.8 * smoothstep(3.2, 3.8, t)) + 0.35 * j)
        wrench = 0.0 if t < 1.25 else min(1.0, (t - 1.25) / 0.12)
        wrench *= 1 - 0.5 * smoothstep(3.4, 4.0, t)
        tremor = math.sin(2 * math.pi * 12.0 * t) * (0.4 + 0.6 * j)
        delta = {}
        for b, sign in zip(SPINE, (1, 1, -1, -1)):
            delta[b] = axis_quat(lat, lift * sign * (14.0 * arch + 1.5 * tremor))
        for b, (twist, tilt) in zip(NECK, ((28.0, 8.0), (28.0, 8.0), (35.0, 10.0))):
            w = wrench * (1 + 0.08 * math.sin(2 * math.pi * 13.0 * t)) if wrench > 0 else 0.0
            delta[b] = axis_quat(along, side * twist * w) * axis_quat(front, side * tilt * w)
        for b in LIMBS:
            axis, phase = limb_axes[b]
            delta[b] = axis_quat(axis, 12.0 * j + 2.5 * math.sin(2 * math.pi * 11.0 * t + phase) * (0.3 + j))
        for b in edited:
            local = X.get_bone_pose(pose, b, L)
            q = comp[b].rotation
            add = inv(q) * delta[b] * q
            keys[b].append((local.translation, local.rotation * add, local.scale3d))
    c = clip.get_editor_property('controller')
    c.open_bracket(unreal.Text('Possession overlay'), False)
    for b, xs in keys.items():
        c.set_bone_track_keys(b, [x[0] for x in xs], [x[1] for x in xs], [x[2] for x in xs], False)
    c.close_bracket(False)
    clip.set_preview_skeletal_mesh(find_asset(UEFN))
    save(clip)
    return {'clip': clip.get_path_name(), 'jerks_at_s': [round(x, 2) for x in times], 'clamp': clamp_clip(clip)}


REVIEW = FOLDER + '/Source/LS_Conversion_Review'
LES = unreal.get_editor_subsystem(unreal.LevelSequenceEditorSubsystem)
SHOTS = os.path.join(unreal.Paths.project_saved_dir(), 'VillainConversion')
BASE = unreal.Vector(-6000.0, 6000.0, 9000.0)


async def review(plan):
    """Renders each clip in plan {name: [seconds]} on the UEFN mannequin (spawnable-only sequence above the level)."""
    os.makedirs(SHOTS, exist_ok=True)
    seq = unreal.load_object(None, REVIEW + '.' + REVIEW.rsplit('/', 1)[1]) or TOOLS.create_asset(
        REVIEW.rsplit('/', 1)[1], REVIEW.rsplit('/', 1)[0], unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    for b in list(seq.get_bindings()):
        b.remove()
    seq.set_display_rate(unreal.FrameRate(FPS, 1))
    seq.set_playback_start(0)
    seq.set_playback_end(200)
    names = list(plan)
    clips = []
    for i, name in enumerate(names):
        clip = unreal.load_object(None, '%s/AS_Conversion_%s.AS_Conversion_%s' % (FOLDER, name, name))
        binding = seq.add_spawnable_from_class(unreal.SkeletalMeshActor)
        binding.set_display_name(name)
        smc = binding.get_object_template().get_editor_property('skeletal_mesh_component')
        smc.set_editor_property('skeletal_mesh_asset', find_asset(UEFN))
        # Offscreen captures do not count as rendered: always tick and refresh bones, or every frame shows one pose.
        smc.set_editor_property('visibility_based_anim_tick_option', unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
        tr = binding.add_track(unreal.MovieScene3DTransformTrack).add_section()
        tr.set_range(0, 200)
        for ch, v in zip(tr.get_all_channels()[:3], (BASE.x + 1500.0 * i, BASE.y, BASE.z)):
            ch.set_default(v)
        clips.append(clip)
    unreal.EditorAssetLibrary.save_loaded_asset(seq, False)
    unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
    unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
    await asyncio.sleep(0.8)  # spawnables appear a frame or two after the sequence opens
    worlds = await call_tool('SceneCaptureToolset.SceneCaptureToolset.ListWorlds')
    worlds = worlds['returnValue'] if isinstance(worlds, dict) else worlds
    world = next(w['world'] for w in worlds if w['worldType'] == 'Editor')
    # Pose the meshes directly (single-node playback, scrubbed per shot): Sequencer's own anim instance does not
    # re-pose spawnables for offscreen captures.
    meshes = []
    for b, clip in zip(seq.get_bindings(), clips):
        smc = LES.get_bound_objects_for_binding(b)[0].get_editor_property('skeletal_mesh_component')
        smc.set_update_animation_in_editor(True)
        smc.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
        smc.set_animation(clip)
        smc.set_play_rate(0.0)
        meshes.append(smc)
    positions = []
    paths = []
    columns = max(len(v) for v in plan.values())
    for c in range(columns):
        for i, name in enumerate(names):
            if c >= len(plan[name]):
                continue
            t = plan[name][c]
            meshes[i].set_position(t, False)
            await asyncio.sleep(0.3)
            positions.append((name, t, round(meshes[i].get_position(), 2)))
            target = BASE + unreal.Vector(1500.0 * i, 0.0, 55.0)
            eye = target + unreal.Vector(-190.0, 250.0, 140.0)
            if 'Possessed' in name:
                actor = LES.get_bound_objects_for_binding(seq.get_bindings()[i])[0]
                head = actor.get_editor_property('skeletal_mesh_component').get_socket_location('head')
                target, eye = head, head + unreal.Vector(-60.0, 90.0, 85.0)
            rot = unreal.MathLibrary.find_look_at_rotation(eye, target)
            cam = {'location': {'x': eye.x, 'y': eye.y, 'z': eye.z}, 'rotation': {'pitch': rot.pitch, 'yaw': rot.yaw, 'roll': 0.0},
                   'projectionMode': 'Perspective', 'fOV': 40.0}
            r = await call_tool('SceneCaptureToolset.SceneCaptureToolset.Capture', world=world, camera=cam, mode='Lit',
                                options={'width': 640, 'height': 640, 'screenPercentage': 1.0, 'visualizationSubMode': ''})
            img = r['image'] if 'image' in r else r['returnValue']['image']
            path = os.path.join(SHOTS, '%s_%03d.png' % (name, int(round(t * FPS))))
            with open(path, 'wb') as f:
                f.write(base64.b64decode(img['data'] if isinstance(img, dict) else img))
            paths.append(path)
    unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
    (ROOT / 'review-positions.json').write_text(json.dumps(positions))
    return paths


stage = (ARGS or ['status'])[0]
if stage == 'review':
    RESULT = json.dumps(await review({
        'Victim_Possessed_A': [0.5, 1.45, 2.4, 3.6], 'Victim_Possessed_B': [0.5, 1.45, 2.4, 3.6],
        'Victim_Rise_E': [0.3, 1.5, 2.6, 3.9], 'Victim_Rise_F': [0.3, 1.5, 2.6, 3.9],
        'Attacker_B': [0.3, 1.5, 3.0, 4.6], 'Attacker_C': [0.3, 1.5, 3.0, 4.6]}))
elif stage == 'possess':
    RESULT = json.dumps([possess('Victim_Convulse_C', 'AS_Conversion_Victim_Possessed_A', 1.0, 9101),
                         possess('Victim_Convulse_D', 'AS_Conversion_Victim_Possessed_B', -1.0, 9102)], indent=1)
else:
    RESULT = json.dumps({'source': create_source, 'arm': arm, 'status': status, 'retarget': retarget, 'clamp': clamp}[stage](), default=str, indent=1)
RESULT
