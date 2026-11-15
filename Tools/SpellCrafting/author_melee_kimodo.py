"""Kimodo melee set for NPCs and soldiers: sword idle, three slashes, a lunge stab, a block, an armed hit react, an armed
death lead-in, a wand flick and a two-handed wand channel. Fast and weighty: each take is trimmed around its strike
(peak hand speed) to a short wind-up and recovery, then baked faster.

NPC combat (UReflectionsNpcCombatComponent) and squads (AReflectionsSquad::ClipFor) play clips directly on the
MetaHuman body and only when the clip's skeleton matches the body's, so every clip is retargeted to each distinct body
skeleton in BODIES.

Runs inside the editor via the MCP Python tool (top-level await allowed). ARGS stage:
  source     add the generator sections to /Game/Combat/Melee/Source/LS_Melee_Kimodo and open it
  arm        with the sequence open: re-apply every prompt in finished transactions (this is what queues Kimodo)
  status     which takes have finished generating
  skeletons  the distinct skeletons of the NPC/soldier MetaHuman bodies
  build      trim + speed up each take on the Kimodo skeleton, retarget to every body skeleton, save
  anticlip   push hands/forearms that come within 2 cm of the torso back out (two-bone IK, smoothed)
  loopblend  ease the idle/channel loops' last 12 keys into the first (seamless loops)
  check      per-frame hand/forearm clearance from each body's torso collision, plus strike timing
  grip       weapon_r socket offset/rotation on hand_r for a hammer grip, per body mesh
  shock      [base idle path] AS_Shock_Convulse_Walker: a standing 1 s electrocution loop (authored overlay)
  add_stagger / arm_stagger / build_stagger   the AS_React_Stagger_Walker take (a blast stumble, in place)
  walker     [moves] the walker-pawn set (AS_Melee_<Move>_Walker on SK_UEFN_Mannequin, the hidden locomotion pawn
             BP_SampleCMCClean2 that the visible body follows): retarget the trimmed takes, anticlip against
             PA_UEFN_Mannequin, loop-blend the channel, and report timing and clearance
Hold the shared PIE lock (Saved/PIE_LOCK.json) while arming/generating and while saving: PIE cancels generation and
makes saves fail.
"""
import json
import math
import os
import time
from pathlib import Path

ROOT = Path(unreal.Paths.project_intermediate_dir()).resolve() / 'CombatMelee'
ROOT.mkdir(exist_ok=True)
FOLDER = '/Game/Combat/Melee'
SOURCE = FOLDER + '/Source/LS_Melee_Kimodo'
QUINN = '/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple'
RTG = '/Game/Characters/Hero/Animation/Locomotion/RTG_MannequinToHero'
# The NPCs' hidden locomotion pawn (BP_SampleCMCClean2): clips played on it as DefaultSlot montages drive the visible body.
WALKER = '/Game/Characters/UEFN_Mannequin/Meshes/SKM_UEFN_Mannequin'
WALKER_RTG = '/Game/Villain/Conversion/Rigs/RTG_Mannequin_to_UEFN'
WALKER_MOVES = ('Sword_Slash_LR', 'Sword_Slash_RL', 'Sword_Stab', 'Sword_Overhead', 'Wand_Flick', 'Sword_HitReact',
                'Wand_Channel')
LOOPS = ('Sword_Idle', 'Wand_Channel')
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
FPS = 30
X = unreal.AnimPoseExtensions
# NPC and soldier MetaHuman bodies (crowd looks and the squad identities).
BODIES = (
    '/Game/Characters/WhiteLondon/IvenRook/MetaHuman/Assembled/IvenRook/Body/SKM_MHC_IvenRook_BodyMesh',
    '/Game/Characters/RedLondon/BridgeGuard/Assembled/BridgeGuard/Body/SKM_MHC_BridgeGuard_BodyMesh',
    '/Game/Characters/RedLondon/CoinClerk/Assembled/CoinClerk/Body/SKM_MHC_CoinClerk_BodyMesh',
    '/Game/Characters/RedLondon/ArchiveApprentice/Assembled/ArchiveApprentice/Body/SKM_MHC_ArchiveApprentice_BodyMesh',
    '/Game/Characters/RedLondon/FestivalDrummer/Assembled/FestivalDrummer/Body/SKM_MHC_FestivalDrummer_BodyMesh',
)

SWORD = 'A swordsman holding a one-handed sword in the right hand, '
WAND = 'A wizard holding a short wand in the right hand, '
# name, seed, frames, kind (idle/strike/hold), speed, prompt
TAKES = (
    ('Sword_Idle', 73101, 90, 'idle', 1.0, SWORD + 'stands in a low ready fighting stance, knees bent, the sword held out in '
     'front of the body with the blade angled forward and up, the left hand raised for balance; alert, shifting weight '
     'slightly from foot to foot.'),
    ('Sword_Slash_LR', 73102, 60, 'strike', 1.2, SWORD + 'in a fighting stance, pulls the sword back across the left side '
     'of the body and swings it in one fast, powerful horizontal backhand slash from left to right at chest height, '
     'then snaps back into the stance.'),
    ('Sword_Slash_RL', 73103, 60, 'strike', 1.2, SWORD + 'in a fighting stance, draws the sword back to the right side and '
     'swings it in one fast, powerful horizontal forehand slash from right to left across the body at chest height, '
     'then snaps back into the stance.'),
    ('Sword_Overhead', 73104, 60, 'strike', 1.15, SWORD + 'in a fighting stance, raises the sword high above the head and '
     'chops it straight down hard in front of the body with full force, bending forward into the blow, then recovers.'),
    ('Sword_Stab', 73105, 60, 'strike', 1.2, SWORD + 'in a fighting stance, lunges forward one big step with the right '
     'foot and thrusts the sword straight ahead in a fast, hard stab, the right arm fully extended, then pulls back into '
     'the stance.'),
    ('Sword_Block', 73106, 45, 'strike', 1.1, SWORD + 'in a fighting stance, quickly raises the sword horizontally in front '
     'of the face to block a blow from above, bracing as the impact hits, then lowers back into the stance.'),
    ('Sword_HitReact', 73107, 45, 'strike', 1.1, SWORD + 'in a fighting stance, is struck hard in the chest, the upper body '
     'jolts backward and they stagger back one step, then regain the stance.'),
    ('Sword_Death', 73108, 75, 'death', 1.0, SWORD + 'is fatally struck in the chest, stumbles backward, the sword drops '
     'from the hand, the knees buckle and they collapse onto the ground.'),
    ('Wand_Flick', 73109, 45, 'strike', 1.2, WAND + 'standing ready, snaps the wand sharply forward at a target in a quick '
     'flick of the wrist and forearm, casting a spell, then relaxes back.'),
    ('Wand_Channel', 73110, 90, 'idle', 1.0, 'A wizard holding a wand with both hands, arms extended straight forward, '
     'channels a powerful spell into a target, leaning into it, body tense and trembling slightly, holding the pose.'),
)


def find_asset(path):
    name = path.rsplit('/', 1)[1]
    return unreal.find_object(None, path + '.' + name) or unreal.load_object(None, path + '.' + name)


def save(asset):
    return unreal.EditorLoadingAndSavingUtils.save_packages([asset.get_package()], False)


def entries():
    offset = 0
    for name, seed, frames, kind, speed, prompt in TAKES:
        yield dict(name=name, seed=seed, frames=frames, kind=kind, speed=speed, prompt=prompt, offset=offset)
        offset += frames + 12


def load_source():
    unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous([FOLDER], True)
    return unreal.load_object(None, SOURCE + '.' + SOURCE.rsplit('/', 1)[1])


def mixer_of(source):
    return next(t for t in source.get_bindings()[0].get_tracks() if isinstance(t, unreal.MovieSceneAnimationMixerTrack))


def create_source():
    """Adds one generator section per take (async requests, polled from a slate tick) and opens the sequence."""
    unreal.SystemLibrary.execute_console_command(None, 'AnimGenOffline.RetiredAnimationGC.Enabled 0')
    for sub in ('', '/Source'):
        unreal.EditorAssetLibrary.make_directory(FOLDER + sub)
    source = load_source() or TOOLS.create_asset(SOURCE.rsplit('/', 1)[1], FOLDER + '/Source', unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    defs = list(entries())
    end = defs[-1]['offset'] + defs[-1]['frames']
    source.set_display_rate(unreal.FrameRate(FPS, 1))
    source.set_playback_start(0)
    source.set_playback_end(end)
    if source.get_bindings():
        mixer = mixer_of(source)
    else:
        binding = source.add_spawnable_from_class(unreal.SkeletalMeshActor)
        binding.set_display_name('Quinn | Melee')
        binding.get_object_template().get_editor_property('skeletal_mesh_component').set_editor_property('skeletal_mesh_asset', find_asset(QUINN))
        mixer = binding.add_track(unreal.MovieSceneAnimationMixerTrack)
    save(source)
    generator = unreal.load_class(None, '/Script/Kimodo.KimodoPoseGenerator')
    state = {'request': None, 'i': 0, 'start': time.monotonic()}

    def tick(delta):
        try:
            if time.monotonic() - state['start'] > 240:
                raise TimeoutError('section insertion timed out')
            index = state['i']
            if index == len(defs):
                save(source)
                unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(source)
                (ROOT / 'sections-ready.json').write_text(json.dumps({'takes': [d['name'] for d in defs]}))
                unreal.unregister_slate_post_tick_callback(state['handle'])
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
        except Exception as error:
            (ROOT / 'source-error.txt').write_text(repr(error))
            unreal.unregister_slate_post_tick_callback(state['handle'])
            raise

    state['handle'] = unreal.register_slate_post_tick_callback(tick)
    return 'adding sections'


def arm():
    unreal.SystemLibrary.execute_console_command(None, 'AnimGenOffline.RetiredAnimationGC.Enabled 0')
    source = load_source()
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() != source:
        unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(source)
        return 'opened; call arm again'
    armed = []
    for data, section in zip(entries(), mixer_of(source).get_sections()):
        with unreal.ScopedEditorTransaction('Generate melee ' + data['name']):
            section.modify()
            section.get_editor_property('pose_generator').set_editor_property('AnimDescriptionOverride', data['prompt'] + ' ')
        with unreal.ScopedEditorTransaction('Generate melee ' + data['name'] + ' (prompt)'):
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


def skeletons():
    groups = {}
    for path in BODIES:
        mesh = find_asset(path)
        if mesh:
            groups.setdefault(mesh.get_editor_property('skeleton').get_path_name(), []).append(path)
    return groups


def eval_opts(mesh):
    opts = unreal.AnimPoseEvaluationOptions()
    opts.set_editor_property('evaluation_type', unreal.AnimDataEvalType.RAW)
    opts.set_editor_property('optional_skeletal_mesh', mesh)
    return opts


def strike_frame(clip, mesh):
    """Frame of peak right-hand speed (component space), ignoring the first and last few frames."""
    opts = eval_opts(mesh)
    n = clip.data_model_interface.get_number_of_keys()
    prev, best, best_i = None, -1.0, 0
    for i in range(n):
        p = X.get_bone_pose(X.get_anim_pose_at_frame(clip, i, opts), 'hand_r', unreal.AnimPoseSpaces.WORLD).translation
        if prev is not None and 3 <= i < n - 3:
            v = (p - prev).length() * FPS
            if v > best:
                best, best_i = v, i
        prev = p
    return best_i, round(best)


# Extra speed at the strike (added to the base speed in a 0.12 s Gaussian around the peak hand speed).
SNAP = {'Sword_Slash_LR': 0.9, 'Sword_Slash_RL': 0.9, 'Sword_Overhead': 0.7, 'Sword_Stab': 0.9, 'Sword_Block': 0.5,
        'Sword_HitReact': 0.4, 'Wand_Flick': 0.8}


def bake(src, dst_name, start_s, end_s, speed, peak_s=None, snap=0.0):
    """New clip on src's skeleton: src between start_s and end_s, resampled `speed` times faster, plus `snap` extra
    speed around peak_s. Returns the clip and where the peak lands in it (seconds)."""
    dst = unreal.load_object(None, '%s/Source/%s.%s' % (FOLDER, dst_name, dst_name)) or TOOLS.duplicate_asset(dst_name, FOLDER + '/Source', src)
    mesh = find_asset(QUINN)
    opts = eval_opts(mesh)
    bones = [str(b) for b in src.data_model_interface.get_bone_track_names()]
    times, t, peak_out = [], start_s, None
    while t < end_s - 1e-4:
        times.append(t)
        rate = speed + (snap * math.exp(-((t - peak_s) / 0.12) ** 2) if peak_s is not None else 0.0)
        if peak_s is not None and peak_out is None and t + rate / FPS >= peak_s:
            peak_out = len(times) / FPS
        t += rate / FPS
    times.append(end_s)
    keys = {b: [] for b in bones}
    for t in times:
        pose = X.get_anim_pose_at_time(src, t, opts)
        for b in bones:
            tr = X.get_bone_pose(pose, b, unreal.AnimPoseSpaces.LOCAL)
            keys[b].append((tr.translation, tr.rotation, tr.scale3d))
    c = dst.get_editor_property('controller')
    c.open_bracket(unreal.Text('Melee trim'), False)
    c.set_number_of_frames(unreal.FrameNumber(len(times) - 1), False)
    for b, xs in keys.items():
        c.set_bone_track_keys(b, [x[0] for x in xs], [x[1] for x in xs], [x[2] for x in xs], False)
    c.close_bracket(False)
    save(dst)
    return dst, peak_out


def drop_time(clip, mesh, below=55.0):
    """First time the pelvis is lower than `below` cm (the body is going down): where a ragdoll should take over."""
    opts = eval_opts(mesh)
    for i in range(clip.data_model_interface.get_number_of_keys()):
        z = X.get_bone_pose(X.get_anim_pose_at_frame(clip, i, opts), 'pelvis', unreal.AnimPoseSpaces.WORLD).translation.z
        if z < below:
            return i / FPS
    return clip.get_play_length()


def build(only=None):
    quinn = find_asset(QUINN)
    rtg = find_asset(RTG)
    targets = {skel: paths[0] for skel, paths in skeletons().items()}
    out = {}
    for data, section in zip(entries(), mixer_of(load_source()).get_sections()):
        if only and data['name'] not in only:
            continue
        inline = section_anim(section)
        if not inline or inline.data_model_interface.get_num_bone_tracks() < 20:
            out[data['name']] = 'pending'
            continue
        length = inline.get_play_length()
        peak = None
        if data['kind'] == 'strike':
            frame, speed = strike_frame(inline, quinn)
            peak = frame / FPS
            start, end = max(0.0, peak - 0.35), min(length, peak + 0.40)
        elif data['kind'] == 'death':
            frame, speed = 0, 0
            start, end = 0.0, min(length, drop_time(inline, quinn) + 0.15)
        else:
            frame, speed = 0, 0
            start, end = 0.0, length
        trimmed, strike_s = bake(inline, 'AS_Melee_%s_Kimodo' % data['name'], start, end, data['speed'], peak, SNAP.get(data['name'], 0.0))
        made = []
        for skel, mesh_path in targets.items():
            identity = mesh_path.rsplit('/', 1)[1].replace('SKM_MHC_', '').replace('_BodyMesh', '')
            spec = unreal.IKRetargetBatchOperationInputs(
                assets_to_retarget=[unreal.AssetRegistryHelpers.create_asset_data(trimmed)], source_mesh=quinn,
                target_mesh=find_asset(mesh_path), ik_retarget_asset=rtg, target_path=FOLDER, use_source_path=False,
                include_referenced_assets=False, overwrite_existing_files=True, suffix='')
            clip = unreal.IKRetargetBatchOperation.run_batch_retarget(spec)[0].get_asset()
            final_name = 'AS_Melee_%s_%s' % (data['name'], identity)
            if clip.get_name() != final_name:
                if unreal.EditorAssetLibrary.does_asset_exist(FOLDER + '/' + final_name):
                    unreal.EditorAssetLibrary.delete_asset(FOLDER + '/' + final_name)
                unreal.EditorAssetLibrary.rename_asset(clip.get_path_name().split('.')[0], FOLDER + '/' + final_name)
                clip = unreal.load_object(None, '%s/%s.%s' % (FOLDER, final_name, final_name))
            clip.set_preview_skeletal_mesh(find_asset(mesh_path))
            clip.set_editor_property('enable_root_motion', False)
            save(clip)
            made.append(clip.get_path_name())
        seconds = trimmed.get_play_length()
        out[data['name']] = {'clips': made, 'seconds': round(seconds, 2),
                             'strike_at_s': round(strike_s, 2) if strike_s is not None else None,
                             'strike_fraction': round(strike_s / seconds, 2) if strike_s is not None else None,
                             'source_peak_hand_speed_cm_s': speed}
    previous = json.loads((ROOT / 'build.json').read_text()) if (ROOT / 'build.json').exists() else {}
    previous.update(out)
    (ROOT / 'build.json').write_text(json.dumps(previous, indent=2))
    return out


TORSO = ('pelvis', 'spine_01', 'spine_02', 'spine_03', 'spine_04', 'spine_05', 'neck_01', 'neck_02', 'head')


def torso_shapes(mesh, skip_side):
    pa = mesh.get_editor_property('physics_asset')
    shapes = []
    for bs in [o for o in unreal.ObjectIterator(unreal.BodySetup) if o.get_outer() == pa]:
        bone = str(bs.get_editor_property('bone_name'))
        if bone not in TORSO and bone != 'clavicle_' + skip_side:
            continue
        geom = bs.get_editor_property('agg_geom')
        for e in geom.get_editor_property('sphyl_elems'):
            axis = e.get_editor_property('rotation').quaternion().rotate_vector(unreal.Vector(0, 0, 1))
            c, half = e.get_editor_property('center'), e.get_editor_property('length') * 0.5
            shapes.append((bone, c - axis * half, c + axis * half, e.get_editor_property('radius')))
        for e in geom.get_editor_property('sphere_elems'):
            c = e.get_editor_property('center')
            shapes.append((bone, c, c, e.get_editor_property('radius')))
    return shapes


def seg_dist(p, a, b):
    ab, ap = b - a, p - a
    t = max(0.0, min(1.0, ab.dot(ap) / max(1e-6, ab.dot(ab))))
    return (p - (a + ab * t)).length()


def clearance(clip, mesh, side, pad=3.0):
    """Min signed clearance (cm) of one forearm, hand and fingers from the torso bodies, over every frame."""
    other = 'l' if side == 'r' else 'r'
    shapes = torso_shapes(mesh, other)
    opts = eval_opts(mesh)
    W = unreal.AnimPoseSpaces.WORLD
    worst, worst_i, inside = 1e9, -1, 0
    arm = ['lowerarm_' + side, 'hand_' + side, 'middle_01_' + side, 'middle_03_' + side, 'index_03_' + side, 'thumb_03_' + side]
    for i in range(clip.data_model_interface.get_number_of_keys()):
        pose = X.get_anim_pose_at_frame(clip, i, opts)
        T = {b: X.get_bone_pose(pose, b, W) for b in set(s[0] for s in shapes) | set(arm)}
        e, h = T[arm[0]].translation, T[arm[1]].translation
        pts = [e + (h - e) * t for t in (0.25, 0.5, 0.75)] + [T[b].translation for b in arm[1:]]
        best = 1e9
        for bone, a, b, r in shapes:
            tr = T[bone]
            A, B = tr.rotation.rotate_vector(a) + tr.translation, tr.rotation.rotate_vector(b) + tr.translation
            for p in pts:
                best = min(best, seg_dist(p, A, B) - r - pad)
        inside += best < 0
        if best < worst:
            worst, worst_i = best, i
    return {'min_cm': round(worst, 1), 'at_frame': worst_i, 'frames_inside': int(inside)}


MARGIN = 2.0


def frame_quat(x, n):
    return unreal.MathLibrary.make_rot_from_xz(x, n).quaternion()


def qinv(q):
    return unreal.Quat(-q.x, -q.y, -q.z, q.w)


def worst_push(T, shapes, side, pad=3.0):
    """(clearance, push direction) of the arm sample closest to the torso in one pose."""
    e, h = T['lowerarm_' + side].translation, T['hand_' + side].translation
    pts = [e + (h - e) * t for t in (0.25, 0.5, 0.75)] + [T[b].translation for b in (
        'hand_' + side, 'middle_01_' + side, 'middle_03_' + side, 'index_03_' + side, 'thumb_03_' + side)]
    best, direction = 1e9, unreal.Vector(0, 0, 0)
    for bone, a, b, r in shapes:
        tr = T[bone]
        A, B = tr.rotation.rotate_vector(a) + tr.translation, tr.rotation.rotate_vector(b) + tr.translation
        ab = B - A
        for p in pts:
            t = max(0.0, min(1.0, ab.dot(p - A) / max(1e-6, ab.dot(ab))))
            q = A + ab * t
            d = (p - q).length() - r - pad
            if d < best:
                best, direction = d, (p - q).normal()
    return best, direction


def anticlip_clip(clip, mesh, side, passes=4):
    """Keeps one arm at least MARGIN cm clear of the torso: per frame the hand is moved out along the push direction by
    the shortfall (max-filtered and smoothed over +-3 frames), the elbow re-solved with two-bone IK keeping its swivel."""
    other = 'l' if side == 'r' else 'r'
    shapes = torso_shapes(mesh, other)
    opts = eval_opts(mesh)
    W, L = unreal.AnimPoseSpaces.WORLD, unreal.AnimPoseSpaces.LOCAL
    need = set(sh[0] for sh in shapes) | {'clavicle_' + side, 'upperarm_' + side, 'lowerarm_' + side, 'hand_' + side,
                                          'middle_01_' + side, 'middle_03_' + side, 'index_03_' + side, 'thumb_03_' + side}
    n = clip.data_model_interface.get_number_of_keys()
    moved = 0
    for _ in range(passes):
        rows, shortfall = [], []
        for i in range(n):
            pose = X.get_anim_pose_at_frame(clip, i, opts)
            T = {b: X.get_bone_pose(pose, b, W) for b in need}
            lt = {b: X.get_bone_pose(pose, b, L) for b in ('upperarm_' + side, 'lowerarm_' + side)}
            c, d = worst_push(T, shapes, side)
            rows.append((T, lt, d))
            shortfall.append(max(0.0, MARGIN - c))
        if max(shortfall) <= 0.05:
            break
        held = [max(shortfall[max(0, i - 2):i + 3]) for i in range(n)]
        smooth = [sum(held[max(0, i - 3):i + 4]) / len(held[max(0, i - 3):i + 4]) for i in range(n)]
        up_keys, lo_keys = [], []
        for i, (T, lt, d) in enumerate(rows):
            S, E, H = T['upperarm_' + side].translation, T['lowerarm_' + side].translation, T['hand_' + side].translation
            ul, ll = lt['upperarm_' + side], lt['lowerarm_' + side]
            push = smooth[i] * 1.4
            n_old = (E - S).cross(H - E)
            if n_old.length() < 1e-3:  # straight arm: bend plane from the push direction instead
                n_old = (E - S).cross(d)
            if push <= 0.01 or n_old.length() < 1e-3:
                up_keys.append((ul.translation, ul.rotation, ul.scale3d))
                lo_keys.append((ll.translation, ll.rotation, ll.scale3d))
                continue
            L1, L2 = (E - S).length(), (H - E).length()
            to = H + d * push - S
            dist = min(to.length(), (L1 + L2) * 0.995)
            u = to.normal()
            T2 = S + u * dist
            a = (L1 * L1 - L2 * L2 + dist * dist) / (2 * dist)
            h = math.sqrt(max(0.0, L1 * L1 - a * a))
            pole = E + d * push - S  # the elbow moves out with the hand
            w = (pole - u * pole.dot(u)).normal()
            E2 = S + u * a + w * h
            n_new = (E2 - S).cross(T2 - E2)
            if n_new.length() < 1e-3:
                up_keys.append((ul.translation, ul.rotation, ul.scale3d))
                lo_keys.append((ll.translation, ll.rotation, ll.scale3d))
                continue
            up_c = frame_quat(E2 - S, n_new) * qinv(frame_quat(E - S, n_old)) * T['upperarm_' + side].rotation
            lo_c = frame_quat(T2 - E2, n_new) * qinv(frame_quat(H - E, n_old)) * T['lowerarm_' + side].rotation
            up_keys.append((ul.translation, qinv(T['clavicle_' + side].rotation) * up_c, ul.scale3d))
            lo_keys.append((ll.translation, qinv(up_c) * lo_c, ll.scale3d))
            moved += 1
        c = clip.get_editor_property('controller')
        c.open_bracket(unreal.Text('Melee anticlip'), False)
        for b, xs in (('upperarm_' + side, up_keys), ('lowerarm_' + side, lo_keys)):
            c.set_bone_track_keys(b, [x[0] for x in xs], [x[1] for x in xs], [x[2] for x in xs], False)
        c.close_bracket(False)
    save(clip)
    return moved


def anticlip(only=None):
    out = {}
    for skel, paths in skeletons().items():
        mesh = find_asset(paths[0])
        identity = paths[0].rsplit('/', 1)[1].replace('SKM_MHC_', '').replace('_BodyMesh', '')
        for data in entries():
            if only and data['name'] not in only:
                continue
            name = 'AS_Melee_%s_%s' % (data['name'], identity)
            clip = unreal.load_object(None, '%s/%s.%s' % (FOLDER, name, name))
            if not clip:
                continue
            fixed = {side: anticlip_clip(clip, mesh, side) for side in ('r', 'l')}
            out[name] = {'frames_moved': fixed, 'right': clearance(clip, mesh, 'r'), 'left': clearance(clip, mesh, 'l')}
    return out


def slerp(a, b, t):
    qa, qb = (a.x, a.y, a.z, a.w), (b.x, b.y, b.z, b.w)
    dot = sum(x * y for x, y in zip(qa, qb))
    if dot < 0:
        qb, dot = tuple(-x for x in qb), -dot
    if dot > 0.9995:
        q = [x + (y - x) * t for x, y in zip(qa, qb)]
    else:
        th = math.acos(dot)
        sa, sb = math.sin((1 - t) * th) / math.sin(th), math.sin(t * th) / math.sin(th)
        q = [x * sa + y * sb for x, y in zip(qa, qb)]
    n = math.sqrt(sum(x * x for x in q))
    return unreal.Quat(q[0] / n, q[1] / n, q[2] / n, q[3] / n)


def blend_loop(clip, mesh, blend=12):
    """Eases the last `blend` keys of a looping clip into its first key so it loops without a seam. Returns the seam
    (largest hand/head/pelvis gap between the first and last frame, cm)."""
    opts = eval_opts(mesh)
    bones = [str(b) for b in clip.data_model_interface.get_bone_track_names()]
    n = clip.data_model_interface.get_number_of_keys()
    keys = {b: [] for b in bones}
    for i in range(n):
        pose = X.get_anim_pose_at_frame(clip, i, opts)
        for b in bones:
            tr = X.get_bone_pose(pose, b, unreal.AnimPoseSpaces.LOCAL)
            keys[b].append((tr.translation, tr.rotation, tr.scale3d))
    for b, xs in keys.items():
        t0, q0, s0 = xs[0]
        for j in range(blend):
            idx = n - blend + j
            t = (j + 1) / blend
            t = t * t * (3 - 2 * t)
            tt, qq, ss = xs[idx]
            xs[idx] = (tt + (t0 - tt) * t, slerp(qq, q0, t), ss + (s0 - ss) * t)
    c = clip.get_editor_property('controller')
    c.open_bracket(unreal.Text('Melee loop blend'), False)
    for b, xs in keys.items():
        c.set_bone_track_keys(b, [x[0] for x in xs], [x[1] for x in xs], [x[2] for x in xs], False)
    c.close_bracket(False)
    save(clip)
    a, z = X.get_anim_pose_at_frame(clip, 0, opts), X.get_anim_pose_at_frame(clip, n - 1, opts)
    return round(max((X.get_bone_pose(a, bn, unreal.AnimPoseSpaces.WORLD).translation
                      - X.get_bone_pose(z, bn, unreal.AnimPoseSpaces.WORLD).translation).length()
                     for bn in ('hand_r', 'hand_l', 'head', 'pelvis')), 2)


def loopblend(names=LOOPS, blend=12):
    out = {}
    for skel, paths in skeletons().items():
        mesh = find_asset(paths[0])
        identity = paths[0].rsplit('/', 1)[1].replace('SKM_MHC_', '').replace('_BodyMesh', '')
        for name in names:
            asset = 'AS_Melee_%s_%s' % (name, identity)
            out[asset] = blend_loop(unreal.load_object(None, '%s/%s.%s' % (FOLDER, asset, asset)), mesh, blend)
    return out


def walker(only=None):
    """AS_Melee_<Move>_Walker on the walker pawn's skeleton, from the same trimmed Kimodo takes as the body clips."""
    quinn, mesh, rtg = find_asset(QUINN), find_asset(WALKER), find_asset(WALKER_RTG)
    out = {}
    for name in (only or WALKER_MOVES):
        src = 'AS_Melee_%s_Kimodo' % name
        trimmed = unreal.load_object(None, '%s/Source/%s.%s' % (FOLDER, src, src))
        if not trimmed:
            out[name] = 'no trimmed take'
            continue
        spec = unreal.IKRetargetBatchOperationInputs(
            assets_to_retarget=[unreal.AssetRegistryHelpers.create_asset_data(trimmed)], source_mesh=quinn,
            target_mesh=mesh, ik_retarget_asset=rtg, target_path=FOLDER, use_source_path=False,
            include_referenced_assets=False, overwrite_existing_files=True, suffix='')
        clip = unreal.IKRetargetBatchOperation.run_batch_retarget(spec)[0].get_asset()
        final_name = ('AS_%s_Walker' if name.startswith('React_') else 'AS_Melee_%s_Walker') % name
        if clip.get_name() != final_name:
            if unreal.EditorAssetLibrary.does_asset_exist(FOLDER + '/' + final_name):
                unreal.EditorAssetLibrary.delete_asset(FOLDER + '/' + final_name)
            unreal.EditorAssetLibrary.rename_asset(clip.get_path_name().split('.')[0], FOLDER + '/' + final_name)
            clip = unreal.load_object(None, '%s/%s.%s' % (FOLDER, final_name, final_name))
        clip.set_preview_skeletal_mesh(mesh)
        clip.set_editor_property('enable_root_motion', False)
        save(clip)
        before = {'right': clearance(clip, mesh, 'r'), 'left': clearance(clip, mesh, 'l')}
        moved = {side: anticlip_clip(clip, mesh, side) for side in ('r', 'l')}
        seam = blend_loop(clip, mesh) if name in LOOPS else None
        seconds = clip.get_play_length()
        frame, speed = strike_frame(clip, mesh) if name not in LOOPS else (None, None)
        out[final_name] = {
            'skeleton': clip.get_editor_property('skeleton').get_path_name(), 'seconds': round(seconds, 2),
            'frames': clip.data_model_interface.get_number_of_keys(),
            'strike_at_s': round(frame / FPS, 2) if frame is not None else None,
            'strike_fraction': round(frame / FPS / seconds, 2) if frame is not None else None,
            'peak_hand_speed_cm_s': speed, 'root_motion': clip.get_editor_property('enable_root_motion'),
            'loop_seam_cm': seam, 'before': before, 'frames_moved': moved,
            'right': clearance(clip, mesh, 'r'), 'left': clearance(clip, mesh, 'l')}
    previous = json.loads((ROOT / 'walker.json').read_text()) if (ROOT / 'walker.json').exists() else {}
    previous.update(out)
    (ROOT / 'walker.json').write_text(json.dumps(previous, indent=2))
    return out


def check():
    out = {}
    for skel, paths in skeletons().items():
        mesh = find_asset(paths[0])
        identity = paths[0].rsplit('/', 1)[1].replace('SKM_MHC_', '').replace('_BodyMesh', '')
        for data in entries():
            name = 'AS_Melee_%s_%s' % (data['name'], identity)
            clip = unreal.load_object(None, '%s/%s.%s' % (FOLDER, name, name))
            if not clip:
                continue
            out[name] = {'right': clearance(clip, mesh, 'r'), 'left': clearance(clip, mesh, 'l'),
                         'frames': clip.data_model_interface.get_number_of_keys()}
    (ROOT / 'check.json').write_text(json.dumps(out, indent=2))
    return out


def grip():
    """A weapon_r socket on hand_r for a hammer grip: centred in the closed fist, +X along the blade (out of the top of
    the fist, toward the thumb), +Z out of the back of the hand. Measured on each body's reference pose."""
    out = {}
    for skel, paths in skeletons().items():
        mesh = find_asset(paths[0])
        ref = X.get_reference_pose(mesh.get_editor_property('skeleton'))
        W = unreal.AnimPoseSpaces.WORLD
        P = {b: X.get_ref_bone_pose(ref, b, W) for b in ('hand_r', 'index_metacarpal_r', 'pinky_metacarpal_r', 'middle_01_r', 'index_01_r', 'pinky_01_r')
             if b in [str(n) for n in X.get_bone_names(ref)]}
        hand = P['hand_r']
        inv = unreal.Quat(-hand.rotation.x, -hand.rotation.y, -hand.rotation.z, hand.rotation.w)
        local = lambda v: inv.rotate_vector(v - hand.translation)
        knuckles = P['middle_01_r'].translation
        palm_mid = (hand.translation + knuckles) * 0.5
        blade = (P['index_01_r'].translation - P['pinky_01_r'].translation).normal()
        centre = local(palm_mid)
        axis = inv.rotate_vector(blade)
        rot = unreal.MathLibrary.make_rot_from_x(axis)
        out[paths[0].rsplit('/', 1)[1]] = {'socket': 'weapon_r', 'bone': 'hand_r',
                                           'location': [round(c, 1) for c in centre.to_tuple()],
                                           'rotation_pyr': [round(rot.pitch, 1), round(rot.yaw, 1), round(rot.roll, 1)],
                                           'blade_axis_local': [round(c, 3) for c in axis.to_tuple()]}
    (ROOT / 'grip.json').write_text(json.dumps(out, indent=2))
    return out


STAGGER = dict(name='React_Stagger', seed=73111, frames=60, prompt=(
    'A person standing relaxed is suddenly hit hard in the chest by a blast: the upper body snaps backward and they '
    'stumble two quick steps back, arms flung forward and out for balance, then catch themselves and stand upright '
    'again.'))


def stagger_section(source):
    """The stagger take's section: the one after the TAKES sections, or None before it is added."""
    sections = mixer_of(source).get_sections()
    return sections[len(TAKES)] if len(sections) > len(TAKES) else None


def add_stagger():
    """Adds the stagger generator section after the TAKES sections (async, polled from a slate tick). Arm it with
    arm_stagger in a later call, with the sequence open and PIE idle."""
    source = load_source()
    mixer = mixer_of(source)
    if stagger_section(source):
        return 'already added'
    last = list(entries())[-1]
    offset = last['offset'] + last['frames'] + 12
    source.set_playback_end(offset + STAGGER['frames'])
    generator = unreal.load_class(None, '/Script/Kimodo.KimodoPoseGenerator')
    state = {'request': unreal.AnimGenOfflineMixerExtensions.add_generated_animation_section_async(mixer, len(TAKES), offset, generator),
             'start': time.monotonic()}

    def tick(delta):
        try:
            if time.monotonic() - state['start'] > 120:
                raise TimeoutError('stagger section insertion timed out')
            if not state['request'].is_complete:
                return
            section = stagger_section(source)
            section.set_range(offset, offset + STAGGER['frames'])
            g = section.get_editor_property('pose_generator')
            g.set_editor_property('RandomSeed', STAGGER['seed'])
            g.set_editor_property('movement_source', unreal.AnimGenOfflineMovementSource.GENERATED_ANIMATION)
            save(source)
            unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(source)
            (ROOT / 'stagger-ready.json').write_text(json.dumps({'offset': offset}))
            unreal.unregister_slate_post_tick_callback(state['handle'])
        except Exception as error:
            (ROOT / 'stagger-error.txt').write_text(repr(error))
            unreal.unregister_slate_post_tick_callback(state['handle'])
            raise

    state['handle'] = unreal.register_slate_post_tick_callback(tick)
    return 'adding the stagger section'


def hide_spawnables(source):
    """The Kimodo spawnable (Quinn) sits at the origin, which is the hero's spawn point in Lvl_HeroSampleCrowd: while
    the sequence is open every PIE copies it in. Hidden in game, it stays visible in Sequencer only."""
    hidden = 0
    for binding in source.get_spawnables():
        template = binding.get_object_template()
        if not template:
            continue
        try:
            already = bool(template.get_editor_property('hidden'))
        except Exception:
            already = False
        if not already:
            template.set_actor_hidden_in_game(True)
            hidden += 1
    return hidden


def close_source(source=None):
    """Closes Sequencer if it shows the Kimodo sequence (see hide_spawnables)."""
    source = source or load_source()
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() == source:
        unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
        return True
    return False


def perf_settings():
    return unreal.find_object(None, '/Script/UnrealEd.Default__EditorPerformanceSettings')


def throttle(enabled):
    """Sets "Use Less CPU when in Background" on the in-memory settings object only (never saved). Kimodo's queue is
    flushed from a level-viewport tick, which never runs while a background editor is throttled to about 3 fps."""
    settings = perf_settings()
    if not settings:
        return 'no settings object'
    before = settings.get_editor_property('throttle_cpu_when_not_foreground')
    if enabled is None:
        saved = ROOT / 'throttle.json'
        enabled = json.loads(saved.read_text())['before'] if saved.exists() else True
        saved.unlink(missing_ok=True)
    elif not enabled and not (ROOT / 'throttle.json').exists():
        (ROOT / 'throttle.json').write_text(json.dumps({'before': before}))
    settings.set_editor_property('throttle_cpu_when_not_foreground', enabled)
    return {'before': before, 'now': settings.get_editor_property('throttle_cpu_when_not_foreground')}


def arm_stagger():
    """Queues Kimodo for the stagger section only (the other takes are not re-generated). Turns the background throttle
    off in memory first; build_stagger (or the restore_throttle stage) turns it back on."""
    unreal.SystemLibrary.execute_console_command(None, 'AnimGenOffline.RetiredAnimationGC.Enabled 0')
    throttle(False)
    source = load_source()
    if hide_spawnables(source):
        save(source)
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() != source:
        unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(source)
        return 'opened; call arm_stagger again'
    section = stagger_section(source)
    for text in (STAGGER['prompt'] + ' ', STAGGER['prompt']):
        with unreal.ScopedEditorTransaction('Generate melee ' + STAGGER['name']):
            section.modify()
            section.get_editor_property('pose_generator').set_editor_property('AnimDescriptionOverride', text)
    return 'armed'


def build_stagger():
    """Trims the stagger take around the hit (peak backward chest speed) to the moment the body settles, bakes it 1.1x
    faster with a little snap at the hit, takes the travel out of the pelvis so it plays in place (the caller moves the
    capsule), then makes the walker clip AS_React_Stagger_Walker."""
    source = load_source()
    inline = section_anim(stagger_section(source))
    if not inline or inline.data_model_interface.get_num_bone_tracks() < 20:
        return 'pending'
    restored = throttle(None)
    closed = close_source(source)
    quinn = find_asset(QUINN)
    opts = eval_opts(quinn)
    n = inline.data_model_interface.get_number_of_keys()
    W = unreal.AnimPoseSpaces.WORLD
    chest = [X.get_bone_pose(X.get_anim_pose_at_frame(inline, i, opts), 'spine_05', W).translation for i in range(n)]
    pelvis = [X.get_bone_pose(X.get_anim_pose_at_frame(inline, i, opts), 'pelvis', W).translation for i in range(n)]
    # "Backward" is opposite the facing at the start: the toes point forward of the feet.
    p0 = X.get_anim_pose_at_frame(inline, 0, opts)
    fwd = X.get_bone_pose(p0, 'ball_l', W).translation - X.get_bone_pose(p0, 'foot_l', W).translation
    fwd = unreal.Vector(fwd.x, fwd.y, 0).normal()
    speed = [0.0] + [-(chest[i] - chest[i - 1]).dot(fwd) * FPS for i in range(1, n)]
    peak = max(range(3, n - 3), key=lambda i: speed[i])
    settle = next((i for i in range(peak + 6, n - 2) if all(
        ((pelvis[k] - pelvis[k - 1]) * unreal.Vector(1, 1, 0)).length() * FPS < 25.0 for k in (i, i + 1, i + 2))), n - 1)
    start, end = max(0.0, (peak - 4) / FPS), min((n - 1) / FPS, (settle + 3) / FPS, (peak + 24) / FPS)
    trimmed, strike_s = bake(inline, 'AS_Melee_React_Stagger_Kimodo', start, end, 1.1, peak / FPS, 0.4)
    travel = in_place(trimmed, quinn)
    out = walker(['React_Stagger'])
    out['travel_back_cm'] = travel
    out['hit_at_s'] = round(strike_s, 2) if strike_s is not None else None
    out['source_peak_chest_speed_cm_s'] = round(speed[peak])
    out['throttle_restored'] = restored
    out['sequence_closed'] = closed
    return out


def in_place(clip, mesh):
    """Removes the horizontal travel of the pelvis (the root stays at the origin) so the clip plays in place; returns
    how far the body travelled backward overall (cm), for the caller's capsule launch."""
    opts = eval_opts(mesh)
    W, L = unreal.AnimPoseSpaces.WORLD, unreal.AnimPoseSpaces.LOCAL
    n = clip.data_model_interface.get_number_of_keys()
    root = [X.get_bone_pose(X.get_anim_pose_at_frame(clip, i, opts), 'root', W) for i in range(n)]
    world = [X.get_bone_pose(X.get_anim_pose_at_frame(clip, i, opts), 'pelvis', W).translation for i in range(n)]
    local = [X.get_bone_pose(X.get_anim_pose_at_frame(clip, i, opts), 'pelvis', L) for i in range(n)]
    flat = unreal.Vector(1, 1, 0)
    drift = [(w - world[0]) * flat for w in world]
    keys = []
    for i in range(n):
        lo, hi = max(0, i - 3), min(n, i + 4)
        smooth = sum((drift[k] for k in range(lo, hi)), unreal.Vector(0, 0, 0)) * (1.0 / (hi - lo))
        # The pelvis is a child of the root: bring the world-space offset into the root's frame.
        offset = qinv(root[i].rotation).rotate_vector(smooth)
        keys.append((local[i].translation - offset, local[i].rotation, local[i].scale3d))
    c = clip.get_editor_property('controller')
    c.open_bracket(unreal.Text('Stagger in place'), False)
    c.set_bone_track_keys('pelvis', [k[0] for k in keys], [k[1] for k in keys], [k[2] for k in keys], False)
    c.close_bracket(False)
    save(clip)
    total = drift[-1]
    return round(total.length(), 1)


def walker_idle(contains=('Idle',)):
    """Standing idle clips on the walker skeleton, shortest name first (the shock loop's base pose)."""
    skel = find_asset(WALKER).get_editor_property('skeleton').get_path_name()
    ar = unreal.AssetRegistryHelpers.get_asset_registry()
    found = []
    for a in ar.get_assets_by_class(unreal.TopLevelAssetPath('/Script/Engine', 'AnimSequence'), True):
        name = str(a.asset_name)
        if all(c.lower() in name.lower() for c in contains) and skel.split('.')[0] in str(a.get_tag_value('Skeleton')):
            found.append(str(a.package_name))
    return sorted(found, key=lambda p: (len(p.rsplit('/', 1)[1]), p))


def axis_quat(axis, degrees):
    half = math.radians(degrees) * 0.5
    s = math.sin(half)
    return unreal.Quat(axis.x * s, axis.y * s, axis.z * s, math.cos(half))


def signed_for(axis, degrees, pivot, tip, want):
    """+degrees or -degrees about axis, whichever moves tip (rotating about pivot) along `want`."""
    v = tip - pivot
    plus = axis_quat(axis, degrees).rotate_vector(v) - v
    return degrees if plus.dot(want) >= 0 else -degrees


SHOCK_FINGERS = tuple('%s_%02d_%s' % (f, k, s) for f in ('index', 'middle', 'ring', 'pinky') for k in (1, 2, 3) for s in 'lr')


def shock(base_path=None, frame=0, seconds=1.0, out_name='AS_Shock_Convulse_Walker'):
    """Standing electrocution loop on the walker skeleton: one frame of a standing idle held, with an authored overlay
    in component space around the body's own axes: the back arches and the head goes back, the shoulders shrug, the
    arms jerk out from the sides with the forearms bent up and the fingers splayed, plus a 14-16 Hz tremor and three
    sharp jerks a second. Every frequency is a whole number of cycles over the clip, so it loops seamlessly. The legs and
    pelvis are left alone so the feet stay planted."""
    mesh = find_asset(WALKER)
    base_path = base_path or walker_idle()[0]
    base = find_asset(base_path)
    # Re-key an existing clip in place: deleting it makes the editor scan referencers, which froze the shared editor
    # for 3 minutes once.
    clip = unreal.load_object(None, '%s/%s.%s' % (FOLDER, out_name, out_name)) or TOOLS.duplicate_asset(out_name, FOLDER, base)
    opts = eval_opts(mesh)
    W, L = unreal.AnimPoseSpaces.WORLD, unreal.AnimPoseSpaces.LOCAL
    pose = X.get_anim_pose_at_frame(base, frame, opts)
    bones = [str(b) for b in base.data_model_interface.get_bone_track_names()]
    comp = {b: X.get_bone_pose(pose, b, W) for b in bones}
    local = {b: X.get_bone_pose(pose, b, L) for b in bones}
    lat = (comp['clavicle_l'].translation - comp['clavicle_r'].translation).normal()
    up = unreal.Vector(0, 0, 1)
    front = up.cross(lat).normal()
    # Which way is "forward": each foot's toes point forward of its own ankle. (Read from the full pose: an idle may
    # not key every bone, and comparing the right toes with the left ankle once flipped this.)
    P = lambda b: X.get_bone_pose(pose, b, W).translation
    toes = (P('ball_l') - P('foot_l')) + (P('ball_r') - P('foot_r'))
    if toes.dot(front) < 0:
        front = front * -1.0
    head, pelvis = comp['head'].translation, comp['pelvis'].translation
    # Never "-front": unary minus on an unreal.Vector negated front itself here (back and front became one vector).
    back = front * -1.0
    arch = signed_for(lat, 1.0, comp['spine_03'].translation if 'spine_03' in comp else pelvis, head, back)
    sides = {}
    for s in 'lr':
        sides[s] = {
            'abduct': signed_for(front, 1.0, comp['upperarm_' + s].translation, comp['hand_' + s].translation, up),
            # Shoulder and elbow flexion: the arm and forearm come forward (about the body's left-right axis). The back
            # arch tilts the shoulders back, so the arms have to come forward more than they look.
            'reach': signed_for(lat, 1.0, comp['upperarm_' + s].translation, comp['hand_' + s].translation, front),
            'elbow': signed_for(lat, 1.0, comp['lowerarm_' + s].translation, comp['hand_' + s].translation, front),
            'shrug': signed_for(front, 1.0, comp['clavicle_' + s].translation, comp['upperarm_' + s].translation, up)}
    # Fingers splay by easing them toward the reference pose (straight, spread fingers on this skeleton).
    ref = X.get_reference_pose(clip.get_editor_property('skeleton'))
    finger_ref = {b: X.get_ref_bone_pose(ref, b, L).rotation for b in SHOCK_FINGERS if b in comp}
    n = int(round(seconds * FPS))
    period = n / FPS

    def wave(t, hz, phase=0.0):
        cycles = max(1, round(hz * period))
        return math.sin(2 * math.pi * cycles * t / period + phase)

    def jolt(t):
        # Three sharp jerks per loop second: fast rise, quick decay, wrapping round the loop.
        total = 0.0
        for k in range(3):
            x = (t - (k + 0.15) * period / 3.0) % period
            total += x / 0.05 if x < 0.05 else math.exp(-(x - 0.05) / 0.12)
        return min(total, 1.2)

    spine = [b for b in ('spine_01', 'spine_02', 'spine_03', 'spine_04', 'spine_05') if b in comp]
    neck = [b for b in ('neck_01', 'neck_02', 'head') if b in comp]
    keys = {b: [] for b in bones}
    for i in range(n + 1):
        t = (i % n) / FPS
        j = jolt(t)
        trem = 0.45 + 0.55 * j
        delta = {}
        for k, b in enumerate(spine):
            delta[b] = axis_quat(lat, arch * (2.2 + 1.2 * j + 0.8 * trem * wave(t, 15, k)))
        for k, b in enumerate(neck):
            delta[b] = axis_quat(lat, arch * (4.0 + 2.0 * j + 1.8 * trem * wave(t, 14, 1.3 + k))) * \
                       axis_quat(up, 3.0 * trem * wave(t, 16, 0.4 * k))
        for s, d in sides.items():
            ph = 0.0 if s == 'l' else 1.9
            delta['clavicle_' + s] = axis_quat(front, d['shrug'] * (9.0 + 5.0 * j + 2.5 * trem * wave(t, 15, ph)))
            # Rigid arms held a little out from the sides, elbows locked half bent with the forearms forward, wrists
            # cocked back: the seizing pose, not a T-pose.
            delta['upperarm_' + s] = axis_quat(front, d['abduct'] * (18.0 + 10.0 * j + 5.0 * trem * wave(t, 14, ph))) * \
                                     axis_quat(lat, d['reach'] * (26.0 + 6.0 * j + 5.0 * trem * wave(t, 16, ph + 0.7)))
            delta['lowerarm_' + s] = axis_quat(lat, d['elbow'] * (58.0 + 14.0 * j + 7.0 * trem * wave(t, 16, ph + 2.1)))
            delta['hand_' + s] = axis_quat(lat, -d['elbow'] * (22.0 + 10.0 * trem * wave(t, 15, ph + 1.1)))
        splay = min(1.0, 0.65 + 0.25 * j + 0.08 * wave(t, 15, 0.6))
        for b in bones:
            lt = local[b]
            if b in finger_ref:
                keys[b].append((lt.translation, slerp(lt.rotation, finger_ref[b], splay), lt.scale3d))
            elif b in delta:
                q = comp[b].rotation
                keys[b].append((lt.translation, lt.rotation * (qinv(q) * delta[b] * q), lt.scale3d))
            else:
                keys[b].append((lt.translation, lt.rotation, lt.scale3d))
    c = clip.get_editor_property('controller')
    c.open_bracket(unreal.Text('Shock overlay'), False)
    c.set_number_of_frames(unreal.FrameNumber(n), False)
    for b, xs in keys.items():
        c.set_bone_track_keys(b, [x[0] for x in xs], [x[1] for x in xs], [x[2] for x in xs], False)
    c.close_bracket(False)
    clip.set_preview_skeletal_mesh(mesh)
    clip.set_editor_property('enable_root_motion', False)
    save(clip)
    # Report: the loop seam, how far the hands move and stay clear of the body, and that the feet stay put.
    first, last = X.get_anim_pose_at_frame(clip, 0, opts), X.get_anim_pose_at_frame(clip, n, opts)
    seam = max((X.get_bone_pose(first, b, W).translation - X.get_bone_pose(last, b, W).translation).length()
               for b in ('hand_l', 'hand_r', 'head'))
    feet = max((X.get_bone_pose(X.get_anim_pose_at_frame(clip, i, opts), f, W).translation - comp[f].translation).length()
               for i in range(0, n + 1, 3) for f in ('foot_l', 'foot_r'))
    hands_up = {s: round(X.get_bone_pose(X.get_anim_pose_at_frame(clip, n // 6, opts), 'hand_' + s, W).translation.z - comp['hand_' + s].translation.z, 1) for s in 'lr'}
    head_back = round((X.get_bone_pose(X.get_anim_pose_at_frame(clip, n // 6, opts), 'head', W).translation - head).dot(back), 1)
    return {'toes': [round(x, 2) for x in toes.to_tuple()], 'up_x_lat': [round(x, 2) for x in up.cross(lat).to_tuple()],
            'signs': sides, 'arch': arch, 'lat': [round(x, 2) for x in lat.to_tuple()],
            'front': [round(x, 2) for x in front.to_tuple()],
            'clip': clip.get_path_name(), 'base': base_path, 'frames': clip.data_model_interface.get_number_of_keys(),
            'seconds': round(clip.get_play_length(), 2), 'skeleton': clip.get_editor_property('skeleton').get_path_name(),
            'seam_cm': round(seam, 2), 'feet_drift_cm': round(feet, 2), 'hands_raised_cm': hands_up,
            'head_back_cm': head_back, 'right': clearance(clip, mesh, 'r'), 'left': clearance(clip, mesh, 'l')}


stage = (ARGS or ['status'])[0]
if stage == 'build':
    RESULT = json.dumps(build(ARGS[1:] or None), default=str, indent=1)
elif stage == 'loopblend':
    RESULT = json.dumps(loopblend(), indent=1)
elif stage == 'anticlip':
    RESULT = json.dumps(anticlip(ARGS[1:] or None), default=str, indent=1)
elif stage == 'walker':
    RESULT = json.dumps(walker(ARGS[1:] or None), default=str, indent=1)
elif stage == 'shock':
    RESULT = json.dumps(shock(*(ARGS[1:2] or [None])), default=str, indent=1)
elif stage == 'idles':
    RESULT = json.dumps(walker_idle(), indent=1)
elif stage in ('add_stagger', 'arm_stagger', 'build_stagger'):
    RESULT = json.dumps({'add_stagger': add_stagger, 'arm_stagger': arm_stagger, 'build_stagger': build_stagger}[stage](),
                        default=str, indent=1)
elif stage == 'restore_throttle':
    RESULT = json.dumps(throttle(None), default=str)
elif stage == 'close':
    RESULT = json.dumps({'closed': close_source()})
else:
    RESULT = json.dumps({'source': create_source, 'arm': arm, 'status': status, 'skeletons': skeletons,
                         'check': check, 'grip': grip}[stage](), default=str, indent=1)
RESULT
