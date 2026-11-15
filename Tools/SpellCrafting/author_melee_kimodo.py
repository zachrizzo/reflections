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
    before = settings.get_editor_property('bThrottleCPUWhenNotForeground')
    if enabled is None:
        saved = ROOT / 'throttle.json'
        enabled = json.loads(saved.read_text())['before'] if saved.exists() else True
        saved.unlink(missing_ok=True)
    elif not enabled and not (ROOT / 'throttle.json').exists():
        (ROOT / 'throttle.json').write_text(json.dumps({'before': before}))
    settings.set_editor_property('bThrottleCPUWhenNotForeground', enabled)
    return {'before': before, 'now': settings.get_editor_property('bThrottleCPUWhenNotForeground')}


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


def smooth01(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def leg_ik(S0, E, H, S, front, q_thigh, q_calf):
    """Two-bone leg IK: the hip moved from S0 to S; keep the foot at H with the knee bending forward. Returns the new
    component rotations of thigh and calf (the bend plane always contains `front`, so the leg never flips)."""
    L1, L2 = (E - S0).length(), (H - E).length()
    to = H - S
    dist = min(to.length(), (L1 + L2) * 0.999)
    u = to.normal()
    a = (L1 * L1 - L2 * L2 + dist * dist) / (2 * dist)
    h = math.sqrt(max(0.0, L1 * L1 - a * a))
    w = (front - u * front.dot(u)).normal()
    E2 = S + u * a + w * h
    T2 = S + u * dist
    n_old, n_new = (E - S0).cross(front).normal(), (E2 - S).cross(front).normal()
    thigh = frame_quat(E2 - S, n_new) * qinv(frame_quat(E - S0, n_old)) * q_thigh
    calf = frame_quat(T2 - E2, n_new) * qinv(frame_quat(H - E, n_old)) * q_calf
    return thigh, calf


def stagger_overlay(base_path='/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Neutral_Stand_Idle_Loop', seconds=0.8,
                    out_name='AS_React_Stagger_Walker', buckle_side='l'):
    """Authored blast stagger for the walker (option b, no steps: the capsule launch carries the body). From a held
    standing idle frame: the hit snaps the spine back and the head after it, the arms fling forward and up with the
    elbows bent, the fingers spread, and one knee buckles (pelvis drops ~13 cm and tilts to that side) with both feet kept
    planted by two-bone leg IK; then everything eases back to the stance by the end, so the montage blends out clean."""
    mesh = find_asset(WALKER)
    base = find_asset(base_path)
    clip = unreal.load_object(None, '%s/%s.%s' % (FOLDER, out_name, out_name)) or TOOLS.duplicate_asset(out_name, FOLDER, base)
    opts = eval_opts(mesh)
    W, L = unreal.AnimPoseSpaces.WORLD, unreal.AnimPoseSpaces.LOCAL
    pose = X.get_anim_pose_at_frame(base, 0, opts)
    bones = [str(b) for b in clip.data_model_interface.get_bone_track_names()]
    comp = {b: X.get_bone_pose(pose, b, W) for b in bones}
    local = {b: X.get_bone_pose(pose, b, L) for b in bones}
    P = lambda b: comp[b].translation
    up = unreal.Vector(0, 0, 1)
    down = up * -1.0
    lat = (P('clavicle_l') - P('clavicle_r')).normal()
    front = up.cross(lat).normal()
    if ((P('ball_l') - P('foot_l')) + (P('ball_r') - P('foot_r'))).dot(front) < 0:
        front = front * -1.0
    back = front * -1.0
    ext = signed_for(lat, 1.0, P('spine_03'), P('head'), back)
    tilt = signed_for(front, 1.0, P('pelvis'), P('thigh_' + buckle_side), down)
    sides = {s: {'reach': signed_for(lat, 1.0, P('upperarm_' + s), P('hand_' + s), front),
                 'abduct': signed_for(front, 1.0, P('upperarm_' + s), P('hand_' + s), up),
                 'elbow': signed_for(lat, 1.0, P('lowerarm_' + s), P('hand_' + s), front),
                 'shrug': signed_for(front, 1.0, P('clavicle_' + s), P('upperarm_' + s), up)} for s in 'lr'}
    ref = X.get_reference_pose(clip.get_editor_property('skeleton'))
    finger_ref = {b: X.get_ref_bone_pose(ref, b, L).rotation for b in SHOCK_FINGERS if b in comp}
    root_q = comp['root'].rotation if 'root' in comp else unreal.Quat(0, 0, 0, 1)
    n = int(round(seconds * FPS))

    def hit(t):
        return smooth01(t / 0.07) * (1 - smooth01((t - 0.25) / 0.55))

    def buckle(t):
        return smooth01((t - 0.10) / 0.20) * (1 - smooth01((t - 0.42) / 0.38))

    spine = [b for b in ('spine_01', 'spine_02', 'spine_03', 'spine_04', 'spine_05') if b in comp]
    neck = [b for b in ('neck_01', 'neck_02', 'head') if b in comp]
    keys = {b: [] for b in bones}
    report = {'pelvis_drop_cm': 0.0, 'head_back_cm': 0.0, 'hands_fwd_cm': 0.0}
    for i in range(n + 1):
        t = i / FPS
        k, kb = hit(t), buckle(t)
        lag = lambda d: hit(max(0.0, t - d))
        delta = {}
        for b in spine:
            delta[b] = axis_quat(lat, ext * 5.0 * k)
        for b in neck:
            delta[b] = axis_quat(lat, ext * 7.0 * lag(0.05))
        for s, d in sides.items():
            a = lag(0.04)
            delta['clavicle_' + s] = axis_quat(front, d['shrug'] * 8.0 * lag(0.03))
            delta['upperarm_' + s] = axis_quat(front, d['abduct'] * 18.0 * a) * axis_quat(lat, d['reach'] * 60.0 * a)
            delta['lowerarm_' + s] = axis_quat(lat, d['elbow'] * 30.0 * lag(0.06))
            delta['hand_' + s] = axis_quat(lat, d['elbow'] * -20.0 * lag(0.06))
        # Pelvis: drops and tilts toward the buckling knee.
        dp = axis_quat(front, tilt * 7.0 * kb)
        drop = down * (13.0 * kb)
        qp = comp['pelvis'].rotation
        Rp = dp * qp
        tp = P('pelvis') + drop
        for b in bones:
            lt = local[b]
            if b == 'pelvis':
                keys[b].append((lt.translation + qinv(root_q).rotate_vector(drop), lt.rotation * (qinv(qp) * dp * qp), lt.scale3d))
            elif b in finger_ref:
                keys[b].append((lt.translation, slerp(lt.rotation, finger_ref[b], 0.6 * lag(0.05)), lt.scale3d))
            elif b in delta:
                q = comp[b].rotation
                keys[b].append((lt.translation, lt.rotation * (qinv(q) * delta[b] * q), lt.scale3d))
            elif b.startswith(('thigh_', 'calf_', 'foot_')) and b[-1] in 'lr' and b.count('_') == 1:
                continue  # legs below
            else:
                keys[b].append((lt.translation, lt.rotation, lt.scale3d))
        for s in 'lr':
            S = tp + Rp.rotate_vector(local['thigh_' + s].translation)
            th, ca = leg_ik(P('thigh_' + s), P('calf_' + s), P('foot_' + s), S, front,
                            comp['thigh_' + s].rotation, comp['calf_' + s].rotation)
            for b, rot in (('thigh_' + s, qinv(Rp) * th), ('calf_' + s, qinv(th) * ca),
                           ('foot_' + s, qinv(ca) * comp['foot_' + s].rotation)):
                if b in keys:
                    keys[b].append((local[b].translation, rot, local[b].scale3d))
        report['pelvis_drop_cm'] = max(report['pelvis_drop_cm'], round(13.0 * kb, 1))
    c = clip.get_editor_property('controller')
    c.open_bracket(unreal.Text('Stagger overlay'), False)
    c.set_number_of_frames(unreal.FrameNumber(n), False)
    for b, xs in keys.items():
        if len(xs) == n + 1:
            c.set_bone_track_keys(b, [x[0] for x in xs], [x[1] for x in xs], [x[2] for x in xs], False)
    c.close_bracket(False)
    clip.set_preview_skeletal_mesh(mesh)
    clip.set_editor_property('enable_root_motion', False)
    save(clip)
    peak = X.get_anim_pose_at_frame(clip, int(round(0.2 * FPS)), opts)
    G = lambda p, b: X.get_bone_pose(p, b, W).translation
    feet = max((G(X.get_anim_pose_at_frame(clip, i, opts), f) - P(f)).length() for i in range(n + 1) for f in ('foot_l', 'foot_r'))
    end = X.get_anim_pose_at_frame(clip, n, opts)
    report.update({
        'clip': clip.get_path_name(), 'frames': clip.data_model_interface.get_number_of_keys(),
        'seconds': round(clip.get_play_length(), 2), 'skeleton': clip.get_editor_property('skeleton').get_path_name(),
        'root_motion': clip.get_editor_property('enable_root_motion'), 'feet_drift_cm': round(feet, 2),
        'head_back_cm': round((G(peak, 'head') - P('head')).dot(back), 1),
        'hands_fwd_cm': {s: round((G(peak, 'hand_' + s) - P('hand_' + s)).dot(front), 1) for s in 'lr'},
        'end_vs_stance_cm': round(max((G(end, b) - P(b)).length() for b in ('head', 'hand_l', 'hand_r', 'pelvis')), 2),
        'right': clearance(clip, mesh, 'r'), 'left': clearance(clip, mesh, 'l')})
    return report


# ---- sword-and-shield soldiers (user: "need to be holding sword and shield"; npc-unify plays these on the walker).
# Sections follow the stagger section in LS_Melee_Kimodo, in this order. Kimodo pins the pelvis and leaves the fingers
# at the reference pose, so holds and idles come out in place; the fists are closed afterwards by grip_fingers.
SHIELD = (
    dict(name='Shield_Guard_Idle', seed=73112, frames=90, prompt=(
        'A soldier holding a sword in the right hand and a shield on the left forearm stands in a guard stance: feet '
        'apart, knees slightly bent, the left forearm raised across the front of the chest as if holding a shield up, '
        'the right hand holding the sword low beside the right hip pointing forward. Alert and steady, breathing, '
        'shifting weight slightly, holding this pose.')),
    dict(name='Shield_March_Hold', seed=73113, frames=60, prompt=(
        'A soldier stands upright holding a sword in the right hand down at the right side, the blade pointing down and '
        'slightly forward, and the left forearm held in front of the stomach, bent at a right angle, as if carrying a '
        'shield. Steady, holding this pose.')),
)
LOOPS = LOOPS + tuple(d['name'] for d in SHIELD)


def shield_index(name):
    return len(TAKES) + 1 + [d['name'] for d in SHIELD].index(name)


def shield_section(source, name):
    sections = mixer_of(source).get_sections()
    index = shield_index(name)
    return sections[index] if len(sections) > index else None


def shield_offset(name):
    offset = 750 + STAGGER['frames'] + 12  # after the stagger section (750..810)
    for d in SHIELD:
        if d['name'] == name:
            return offset
        offset += d['frames'] + 12


def add_shield():
    """Adds the missing sword-and-shield generator sections (async, one after another, polled from a slate tick). Does
    not open the sequence: arm_shield does that, and build_shield closes it."""
    source = load_source()
    mixer = mixer_of(source)
    if not stagger_section(source):
        return 'add the stagger section first (sections must stay in order)'
    todo = [d for d in SHIELD if not shield_section(source, d['name'])]
    if not todo:
        return 'already added'
    last = SHIELD[-1]
    source.set_playback_end(shield_offset(last['name']) + last['frames'])
    generator = unreal.load_class(None, '/Script/Kimodo.KimodoPoseGenerator')
    state = {'request': None, 'todo': list(todo), 'start': time.monotonic()}
    (ROOT / 'shield-ready.json').unlink(missing_ok=True)

    def tick(delta):
        try:
            if time.monotonic() - state['start'] > 180:
                raise TimeoutError('shield section insertion timed out')
            if state['request'] is not None and not state['request'].is_complete:
                return
            if state['request'] is not None:
                d = state['todo'].pop(0)
                section = shield_section(source, d['name'])
                offset = shield_offset(d['name'])
                section.set_range(offset, offset + d['frames'])
                g = section.get_editor_property('pose_generator')
                g.set_editor_property('RandomSeed', d['seed'])
                g.set_editor_property('movement_source', unreal.AnimGenOfflineMovementSource.GENERATED_ANIMATION)
                state['request'] = None
            if not state['todo']:
                hide_spawnables(source)
                save(source)
                (ROOT / 'shield-ready.json').write_text(json.dumps([d['name'] for d in todo]))
                unreal.unregister_slate_post_tick_callback(state['handle'])
                return
            d = state['todo'][0]
            state['request'] = unreal.AnimGenOfflineMixerExtensions.add_generated_animation_section_async(
                mixer, shield_index(d['name']), shield_offset(d['name']), generator)
        except Exception as error:
            (ROOT / 'shield-error.txt').write_text(repr(error))
            unreal.unregister_slate_post_tick_callback(state['handle'])
            raise

    state['handle'] = unreal.register_slate_post_tick_callback(tick)
    return 'adding %s' % [d['name'] for d in todo]


def arm_shield(names=None):
    """Queues Kimodo for the named sword-and-shield sections only (background throttle off in memory first)."""
    unreal.SystemLibrary.execute_console_command(None, 'AnimGenOffline.RetiredAnimationGC.Enabled 0')
    throttle(False)
    source = load_source()
    if hide_spawnables(source):
        save(source)
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() != source:
        unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(source)
        return 'opened; call arm_shield again'
    armed = []
    for d in SHIELD:
        if names and d['name'] not in names:
            continue
        section = shield_section(source, d['name'])
        for text in (d['prompt'] + ' ', d['prompt']):
            with unreal.ScopedEditorTransaction('Generate melee ' + d['name']):
                section.modify()
                section.get_editor_property('pose_generator').set_editor_property('AnimDescriptionOverride', text)
        armed.append(d['name'])
    return armed


def shield_status():
    source = load_source()
    out = {}
    for d in SHIELD:
        section = shield_section(source, d['name'])
        anim = section_anim(section) if section else None
        out[d['name']] = bool(anim and anim.data_model_interface.get_num_bone_tracks() >= 20)
    return out


def scale_rotation(q, factor):
    """q^factor: the same axis, `factor` times the angle (shortest arc)."""
    if q.w < 0:
        q = unreal.Quat(-q.x, -q.y, -q.z, -q.w)
    half = math.acos(max(-1.0, min(1.0, q.w)))
    if half < 1e-6:
        return unreal.Quat(0, 0, 0, 1)
    s = math.sin(half)
    nh = min(half * factor, math.pi * 0.49)
    ns = math.sin(nh)
    return unreal.Quat(q.x / s * ns, q.y / s * ns, q.z / s * ns, math.cos(nh))


GRIP_FINGERS = tuple('%s_%02d_' % (f, k) for f in ('index', 'middle', 'ring', 'pinky') for k in (1, 2, 3))
GRIP_THUMB = tuple('thumb_%02d_' % k for k in (1, 2, 3))


# Grip: fingers wrap a round handle (sword grip, shield strap) of HANDLE_RADIUS cm. The finger bones' joint centres sit
# FINGER_HALF cm inside the skin, so the joints ride on a circle of radius HANDLE_RADIUS + FINGER_HALF around it.
HANDLE_RADIUS = 1.5
FINGER_HALF = 0.9
TIP_FRACTION = 0.8  # the fingertip segment has no bone; its length is this fraction of the middle segment


def hand_frame(T, s):
    """(along, across, palm) unit vectors of one hand on the reference pose: along = from the middle knuckle toward
    the fingers, across = index to pinky knuckles, palm = the palm side (the side the thumb sits on)."""
    m1, m2 = T('middle_01_' + s).translation, T('middle_02_' + s).translation
    along = (m2 - m1).normal()
    across = T('pinky_01_' + s).translation - T('index_01_' + s).translation
    across = (across - along * across.dot(along)).normal()
    palm = along.cross(across).normal()
    if (T('thumb_02_' + s).translation - m1).dot(palm) < 0:
        palm = palm * -1.0
    return along, across, palm


def wrap_angles(lengths, radius):
    """Joint bends (degrees) that lay finger segments of these lengths tangent to a circle of `radius` (each segment's
    bone line touches it at the segment's middle, the way a hook grip lies on a handle): segment k spans a central angle
    of 2 atan(L / 2R); the bend at joint k is the mean of the spans on either side (the knuckle turns half of the
    first span off the hand's line)."""
    th = [2.0 * math.degrees(math.atan(L / (2.0 * radius))) for L in lengths]
    return (th[0] * 0.5, (th[0] + th[1]) * 0.5, (th[1] + th[2]) * 0.5)


def fist_adds(skeleton, sides='lr'):
    """Per finger joint, the local rotation that closes the hand around a ~3 cm handle. Worked out once on the
    reference pose in component space: fingers bend toward the palm about (bone direction x palm normal), by the
    wrap_angles of their own segment lengths; the thumb closes over the top of the handle on the wrist side (THUMB_POLAR). Expressed in
    each joint's own frame, so it holds however the hand moves."""
    ref = X.get_reference_pose(skeleton)
    W = unreal.AnimPoseSpaces.WORLD
    T = lambda b: X.get_ref_bone_pose(ref, b, W)
    adds, angles = {}, {}
    for s in sides:
        along, across, palm = hand_frame(T, s)
        for f in ('index', 'middle', 'ring', 'pinky', 'thumb'):
            names = ['%s_%02d_%s' % (f, k, s) for k in (1, 2, 3)]
            pts = [T(b).translation for b in names]
            tip = pts[2] + (pts[2] - pts[1]) * TIP_FRACTION
            seg = [pts[1] - pts[0], pts[2] - pts[1], tip - pts[2]]
            if f == 'thumb':
                continue  # after the fingers: it closes over the handle they define
            # Fingers: absolute target direction per segment, measured from the metacarpal line in the plane of
            # (metacarpal, palm). The reference pose's own slight curl is absorbed, not added on top.
            meta = T('%s_metacarpal_%s' % (f, s)).translation
            base_dir = (pts[0] - meta).normal()
            palm_f = (palm - base_dir * palm.dot(base_dir)).normal()
            degs = wrap_angles([v.length() for v in seg], HANDLE_RADIUS + FINGER_HALF)
            angles[f + '_' + s] = [round(x, 1) for x in degs]
            wants, total = [], 0.0
            for k in range(3):
                total += degs[k]
                a = math.radians(total)
                wants.append(base_dir * math.cos(a) + palm_f * math.sin(a))
            adds.update(aim_chain(T, names, seg, wants))
            if f == 'middle':
                # The handle axis (along `across`): R toward the palm from the middle of the first segment.
                a1 = math.radians(degs[0])
                n1 = palm_f * math.cos(a1) - base_dir * math.sin(a1)
                centre = pts[0] + wants[0] * (seg[0].length() * 0.5) + n1 * (HANDLE_RADIUS + FINGER_HALF)
        # Thumb: over the top of the handle on the wrist side, where the fingertips leave it open. Its last joint sits
        # at THUMB_POLAR deg round the handle (last joint, tip) (0 = knuckle side, 90 = fingertip side, 180 = palm side),
        # level with the index finger; the middle joint bends outward (two-bone IK).
        names = ['thumb_%02d_%s' % (k, s) for k in (1, 2, 3)]
        pts = [T(b).translation for b in names]
        seg = [pts[1] - pts[0], pts[2] - pts[1], (pts[2] - pts[1]) * TIP_FRACTION]
        level = across * (T('index_01_' + s).translation - centre).dot(across)
        rt = HANDLE_RADIUS + THUMB_HALF
        polar = lambda deg: (palm * -1.0) * math.cos(math.radians(deg)) + along * math.sin(math.radians(deg))
        j3 = centre + level + polar(THUMB_POLAR[0]) * rt
        tip = centre + level + polar(THUMB_POLAR[1]) * rt
        S, L1, L2 = pts[0], seg[0].length(), seg[1].length()
        to = j3 - S
        dist = min(to.length(), (L1 + L2) * 0.999)
        u = to.normal()
        a = (L1 * L1 - L2 * L2 + dist * dist) / (2 * dist)
        h = math.sqrt(max(0.0, L1 * L1 - a * a))
        out = (S + j3) * 0.5 - centre
        out = out - across * out.dot(across)
        w = (out - u * out.dot(u)).normal()
        E = S + u * a + w * h
        J3 = S + u * dist
        wants = [(E - S).normal(), (J3 - E).normal(), (tip - J3).normal()]
        adds.update(aim_chain(T, names, seg, wants))
        angles['thumb_' + s] = {'reach_ok': to.length() <= L1 + L2, 'joint3_polar': THUMB_POLAR[0], 'tip_polar': THUMB_POLAR[1]}
    fist_adds.angles = angles
    return adds


THUMB_HALF = 1.0
THUMB_POLAR = (238.0, 180.0)


def aim_chain(T, names, seg, wants):
    """Local rotations that point a bone chain's segments along `wants` (absolute component-space directions), each
    joint turning its own segment after its parents have moved (shortest arc)."""
    adds, cum = {}, unreal.Quat(0, 0, 0, 1)
    for k, b in enumerate(names):
        want = wants[k]
        have = cum.rotate_vector(seg[k].normal())  # where this segment points after its parents moved
        axis = have.cross(want)
        if axis.length() < 1e-6:
            delta = unreal.Quat(0, 0, 0, 1)
        else:
            delta = axis_quat(axis.normal(), math.degrees(math.acos(max(-1.0, min(1.0, have.dot(want))))))
        # delta acts after the parents' rotation; in the base frame it is cum^-1 * delta * cum
        own = qinv(cum) * delta * cum
        q = T(b).rotation
        adds[b] = qinv(q) * own * q
        cum = cum * own
    return adds


def grip_check(skeleton, sides='lr'):
    """The grip on the reference hand, posed by forward kinematics (no asset touched): for each finger, its joints'
    and segment midpoints' distance from the handle surface (the handle axis runs along `across`, HANDLE_RADIUS +
    FINGER_HALF palm-side of each knuckle) and how far round the handle it wraps; for the thumb, how close its tip comes
    to the index finger. Also returns hand-frame coordinates for draw_grip_sheet.py."""
    ref = X.get_reference_pose(skeleton)
    W = unreal.AnimPoseSpaces.WORLD
    T = lambda b: X.get_ref_bone_pose(ref, b, W)
    adds = fist_adds(skeleton, sides)
    R = HANDLE_RADIUS + FINGER_HALF
    out = {'handle_diameter_cm': HANDLE_RADIUS * 2, 'angles': fist_adds.angles, 'fingers': {}, 'draw': {}}
    for s in sides:
        along, across, palm = hand_frame(T, s)
        origin = T('middle_01_' + s).translation
        to_hand = lambda p: [round((p - origin).dot(v), 2) for v in (along, across, palm)]
        posed, centres = {}, {}
        for f in ('index', 'middle', 'ring', 'pinky', 'thumb'):
            names = ['%s_%02d_%s' % (f, k, s) for k in (1, 2, 3)]
            pts = [T(b).translation for b in names]
            tip = pts[2] + (pts[2] - pts[1]) * TIP_FRACTION
            seg = [pts[1] - pts[0], pts[2] - pts[1], tip - pts[2]]
            cum, p, chain = unreal.Quat(0, 0, 0, 1), pts[0], [pts[0]]
            for k, b in enumerate(names):
                q = T(b).rotation
                cum = cum * (q * adds[b] * qinv(q))
                p = p + cum.rotate_vector(seg[k])
                chain.append(p)
            posed[f] = chain
            if f != 'thumb':
                # The handle axis (along `across`) sits R from the first segment's middle, toward the palm.
                d1 = (chain[1] - chain[0]).normal()
                n1 = (palm - d1 * palm.dot(d1)).normal()
                centre = (chain[0] + chain[1]) * 0.5 + n1 * R
                centres[f] = centre
                samples = chain + [(a + b) * 0.5 for a, b in zip(chain, chain[1:])]
                # skin gap: bone-line distance from the handle axis, minus handle radius and finger half-thickness
                gaps = [((q - centre) - across * (q - centre).dot(across)).length() - R for q in samples]
                # Angle round the handle: 0 at the knuckle side, 90 toward the fingertips, 180 on the palm side, ...
                polar, prev = [], None
                for q in chain:
                    v = q - centre
                    a = math.degrees(math.atan2(v.dot(along), v.dot(palm * -1.0)))
                    if prev is not None:
                        while a < prev - 180.0:
                            a += 360.0
                    polar.append(a)
                    prev = a
                wrap = polar[-1] - polar[0]
                out['fingers'][f + '_' + s] = {'min_skin_gap_cm': round(min(gaps), 2),
                                               'max_skin_gap_cm': round(max(gaps[1:]), 2),
                                               'wrap_deg': round(wrap, 0)}
        tip_t = posed['thumb'][-1]
        idx = posed['index']
        mid_centre = centres['middle']
        # spread of the four fingers' handle axes (they should all wrap one straight handle)
        spread = max(((c - mid_centre) - across * (c - mid_centre).dot(across)).length() for c in centres.values())
        out['fingers']['thumb_' + s] = {
            'tip_to_index_middle_cm': round(min((tip_t - q).length() for q in idx[1:3]), 1),
            'tip_skin_gap_cm': round(((tip_t - mid_centre) - across * (tip_t - mid_centre).dot(across)).length() - R, 2)}
        out['fingers']['handle_axes_spread_' + s] = round(spread, 2)
        out['draw'][s] = {'handle_centre': to_hand(mid_centre), 'radius': HANDLE_RADIUS,
                          'ref': {f: [to_hand(T('%s_%02d_%s' % (f, k, s)).translation) for k in (1, 2, 3)]
                                  for f in ('index', 'middle', 'ring', 'pinky', 'thumb')},
                          'grip': {f: [to_hand(q) for q in chain] for f, chain in posed.items()},
                          'wrist': to_hand(T('hand_' + s).translation)}
    return out


def grip_fingers(clip, sides='lr'):
    """Closes the hands into a fist (around a sword grip or shield handle) on every frame of a walker clip. Kimodo
    leaves the fingers at the reference pose, so the fist is the reference finger pose times fist_adds."""
    mesh = find_asset(WALKER)
    opts = eval_opts(mesh)
    L, W = unreal.AnimPoseSpaces.LOCAL, unreal.AnimPoseSpaces.WORLD
    adds = fist_adds(clip.get_editor_property('skeleton'), sides)
    tracks = [str(b) for b in clip.data_model_interface.get_bone_track_names()]
    n = clip.data_model_interface.get_number_of_keys()
    poses = [X.get_anim_pose_at_frame(clip, i, opts) for i in range(n)]
    tip_gap = lambda p, s: round((X.get_bone_pose(p, 'middle_03_' + s, W).translation - X.get_bone_pose(p, 'hand_' + s, W).translation).length(), 1)
    angles = {'tip_to_wrist_before_cm': {s: tip_gap(poses[0], s) for s in sides}}
    ref = X.get_reference_pose(clip.get_editor_property('skeleton'))
    keys = {}
    for b, add in adds.items():
        if b in tracks:
            # From the reference rotation, not the clip's, so running it twice doesn't curl twice.
            fist = X.get_ref_bone_pose(ref, b, L).rotation * add
            keys[b] = [(t.translation, fist, t.scale3d) for t in (X.get_bone_pose(p, b, L) for p in poses)]
    c = clip.get_editor_property('controller')
    c.open_bracket(unreal.Text('Grip'), False)
    for b, xs in keys.items():
        c.set_bone_track_keys(b, [x[0] for x in xs], [x[1] for x in xs], [x[2] for x in xs], False)
    c.close_bracket(False)
    save(clip)
    after = X.get_anim_pose_at_frame(clip, 0, opts)
    angles['tip_to_wrist_after_cm'] = {s: tip_gap(after, s) for s in sides}
    angles['fingers_keyed'] = len(keys)
    return angles


IDLE0 = '/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Neutral_Stand_Idle_Loop'
LOWER_PREFIXES = ('root', 'pelvis', 'spine_01', 'spine_02', 'thigh_', 'calf_', 'foot_', 'ball_')
# Where the sword's blade should point (component space, from body axes): guard = ahead and a little up, at the enemy;
# march = down and a little forward, carried.
SWORD_AIM = {'Shield_Guard_Idle': (1.0, 0.0, 0.25), 'Shield_March_Hold': (0.45, 0.0, -0.9)}  # (front, lat, up)
BLADE_TILT = 15.0  # degrees the blade leans back toward the forearm from square across the palm (npc-unify's prop setup)


def body_axes(pose):
    W = unreal.AnimPoseSpaces.WORLD
    P = lambda b: X.get_bone_pose(pose, b, W).translation
    up = unreal.Vector(0, 0, 1)
    lat = P('clavicle_l') - P('clavicle_r')
    lat = (lat - up * lat.dot(up)).normal()
    front = up.cross(lat).normal()
    if ((P('ball_l') - P('foot_l')) + (P('ball_r') - P('foot_r'))).dot(front) < 0:
        front = front * -1.0
    return front, lat, up


def hand_axes_local(skeleton, s):
    """The hand's (along, across, palm) as vectors in hand_<s>'s own frame, from the reference pose (fixed per hand)."""
    ref = X.get_reference_pose(skeleton)
    W = unreal.AnimPoseSpaces.WORLD
    T = lambda b: X.get_ref_bone_pose(ref, b, W)
    along, across, palm = hand_frame(T, s)
    q = T('hand_' + s).rotation
    return [qinv(q).rotate_vector(v) for v in (along, across, palm)]


def match_idle_lower(clip):
    """Lower body, pelvis and lower spine set to the neutral idle's frame 0 on every frame (npc-unify adds the clip on top
    of the walk as a local-space additive over exactly that frame, so anything different there would ride every step)."""
    mesh = find_asset(WALKER)
    opts = eval_opts(mesh)
    L = unreal.AnimPoseSpaces.LOCAL
    idle = X.get_anim_pose_at_frame(find_asset(IDLE0), 0, opts)
    tracks = [str(b) for b in clip.data_model_interface.get_bone_track_names()]
    lower = [b for b in tracks if b.startswith(LOWER_PREFIXES)]
    n = clip.data_model_interface.get_number_of_keys()
    c = clip.get_editor_property('controller')
    c.open_bracket(unreal.Text('Lower body = idle frame 0'), False)
    for b in lower:
        t = X.get_bone_pose(idle, b, L)
        c.set_bone_track_keys(b, [t.translation] * n, [t.rotation] * n, [t.scale3d] * n, False)
    c.close_bracket(False)
    save(clip)
    return lower


def signed_angle(a, b, axis):
    """Angle (degrees) turning a onto b about axis, both projected onto the plane normal to axis."""
    a = (a - axis * a.dot(axis)).normal()
    b = (b - axis * b.dot(axis)).normal()
    ang = math.degrees(math.acos(max(-1.0, min(1.0, a.dot(b)))))
    return ang if a.cross(b).dot(axis) >= 0 else -ang


def aim_sword_shield(clip, name):
    """Per frame: the left forearm rolls (about its own axis, so the hand stays put) until the back of the hand and
    forearm faces forward, where the shield is strapped; the right forearm rolls and the wrist turns until the blade
    (out of the index side of the fist, BLADE_TILT back toward the forearm) points along SWORD_AIM. Returns how well
    each lands (dot products) and the largest wrist turn."""
    mesh = find_asset(WALKER)
    opts = eval_opts(mesh)
    W, L = unreal.AnimPoseSpaces.WORLD, unreal.AnimPoseSpaces.LOCAL
    skel = clip.get_editor_property('skeleton')
    axes = {s: hand_axes_local(skel, s) for s in 'lr'}
    n = clip.data_model_interface.get_number_of_keys()
    edit = ('lowerarm_l', 'lowerarm_r', 'hand_r')
    keys = {b: [] for b in edit}
    report = {'shield_back_facing_front_min': 1.0, 'blade_on_aim_min': 1.0, 'max_wrist_turn_deg': 0.0, 'max_roll_deg': 0.0}
    for i in range(n):
        pose = X.get_anim_pose_at_frame(clip, i, opts)
        front, lat, up = body_axes(pose)
        C = lambda b: X.get_bone_pose(pose, b, W)
        local = {b: X.get_bone_pose(pose, b, L) for b in edit}
        # Left: roll the forearm so the back of the hand (minus palm) faces front.
        el, hl = C('lowerarm_l'), C('hand_l')
        axis = (hl.translation - el.translation).normal()
        back = hl.rotation.rotate_vector(axes['l'][2]) * -1.0
        roll = signed_angle(back, front, axis)
        R = axis_quat(axis, roll)
        q = el.rotation
        keys['lowerarm_l'].append((local['lowerarm_l'].translation, local['lowerarm_l'].rotation * (qinv(q) * R * q), local['lowerarm_l'].scale3d))
        back2 = R.rotate_vector(back)
        report['shield_back_facing_front_min'] = min(report['shield_back_facing_front_min'], round(back2.dot(front), 3))
        report['max_roll_deg'] = max(report['max_roll_deg'], round(abs(roll), 1))
        # Right: blade direction in component space.
        f_, l_, u_ = SWORD_AIM[name]
        aim = (front * f_ + lat * l_ + up * u_).normal()
        er, hr = C('lowerarm_r'), C('hand_r')
        axis = (hr.translation - er.translation).normal()
        a_al, a_ac = hr.rotation.rotate_vector(axes['r'][0]), hr.rotation.rotate_vector(axes['r'][1])
        t = math.radians(BLADE_TILT)
        blade = (a_ac * (-math.cos(t)) + a_al * (-math.sin(t))).normal()
        roll = max(-80.0, min(80.0, signed_angle(blade, aim, axis)))
        R = axis_quat(axis, roll)
        q = er.rotation
        keys['lowerarm_r'].append((local['lowerarm_r'].translation, local['lowerarm_r'].rotation * (qinv(q) * R * q), local['lowerarm_r'].scale3d))
        blade = R.rotate_vector(blade)
        # then the wrist takes the rest (shortest arc, at most 55 degrees)
        rest = blade.cross(aim)
        turn = math.degrees(math.acos(max(-1.0, min(1.0, blade.dot(aim)))))
        turn_c = min(turn, 55.0)
        Rw = axis_quat(rest.normal(), turn_c) if rest.length() > 1e-6 else unreal.Quat(0, 0, 0, 1)
        qh = R * hr.rotation  # the hand's comp rotation after the forearm roll
        # hand local = local * (qh^-1 Rw qh) relative to its (rolled) parent: the parent's roll is inherited already
        keys['hand_r'].append((local['hand_r'].translation, local['hand_r'].rotation * (qinv(qh) * Rw * qh), local['hand_r'].scale3d))
        report['blade_on_aim_min'] = min(report['blade_on_aim_min'], round(Rw.rotate_vector(blade).dot(aim), 3))
        report['max_wrist_turn_deg'] = max(report['max_wrist_turn_deg'], round(turn_c, 1))
        report['max_roll_deg'] = max(report['max_roll_deg'], round(abs(roll), 1))
    c = clip.get_editor_property('controller')
    c.open_bracket(unreal.Text('Sword and shield arms'), False)
    for b, xs in keys.items():
        c.set_bone_track_keys(b, [x[0] for x in xs], [x[1] for x in xs], [x[2] for x in xs], False)
    c.close_bracket(False)
    save(clip)
    return report


def build_shield(names=None):
    """For each finished take: the whole take baked on the Kimodo skeleton, AS_Melee_<Name>_Walker made by walker()
    (retarget, hand anticlip, seamless loop), then both fists closed. Restores the throttle and closes Sequencer."""
    source = load_source()
    quinn = find_asset(QUINN)
    out = {}
    for d in SHIELD:
        if names and d['name'] not in names:
            continue
        section = shield_section(source, d['name'])
        inline = section_anim(section) if section else None
        if not inline or inline.data_model_interface.get_num_bone_tracks() < 20:
            out[d['name']] = 'pending'
            continue
        bake(inline, 'AS_Melee_%s_Kimodo' % d['name'], 0.0, inline.get_play_length(), 1.0)
        made = walker([d['name']])
        clip = unreal.load_object(None, '%s/AS_Melee_%s_Walker.AS_Melee_%s_Walker' % (FOLDER, d['name'], d['name']))
        if d['name'] == 'Shield_March_Hold':
            made['lower_body_from_idle'] = len(match_idle_lower(clip))
        made['arms'] = aim_sword_shield(clip, d['name'])
        made['grip'] = grip_fingers(clip)
        mesh = find_asset(WALKER)
        made['final_right'] = clearance(clip, mesh, 'r')
        made['final_left'] = clearance(clip, mesh, 'l')
        out[d['name']] = made
    if all(v != 'pending' for v in out.values()):
        out['throttle_restored'] = throttle(None)
        out['sequence_closed'] = close_source(source)
    return out


# ---- get-ups after a physics knockdown (npc-unify ragdolls the hidden walker, then plays one of these on it).
# Cut from the Game Animation Sample's mocap get-ups (same skeleton): only the active part, a little faster, the root's
# travel taken out so the body rises in place over the capsule, ending in the sample's standing idle pose.
GETUP_SRC = '/Game/Characters/UEFN_Mannequin/Animations/Ragdoll/'
GETUPS = (
    # out name, source, start s, end s, speed: back stands at 2.33 s, face-down moves from 0.6 s and stands at 2.67 s
    ('AS_GetUp_Back_Walker', 'M_ragdoll_getup_stand_B', 0.0, 2.5, 1.25),
    ('AS_GetUp_Front_Walker', 'M_ragdoll_getup_stand_F', 0.5, 2.83, 1.15),
)


def getups():
    mesh = find_asset(WALKER)
    opts = eval_opts(mesh)
    W, L = unreal.AnimPoseSpaces.WORLD, unreal.AnimPoseSpaces.LOCAL
    out = {}
    for name, src_name, start, end, speed in GETUPS:
        src = find_asset(GETUP_SRC + src_name)
        clip = unreal.load_object(None, '%s/%s.%s' % (FOLDER, name, name)) or TOOLS.duplicate_asset(name, FOLDER, src)
        bones = [str(b) for b in src.data_model_interface.get_bone_track_names()]
        times, t = [], start
        while t < end - 1e-4:
            times.append(t)
            t += speed / FPS
        times.append(end)
        keys = {b: [] for b in bones}
        for t in times:
            pose = X.get_anim_pose_at_time(src, t, opts)
            for b in bones:
                tr = X.get_bone_pose(pose, b, L)
                if b == 'root':
                    # in place: the root stays at the origin (its rotation kept)
                    keys[b].append((unreal.Vector(0, 0, 0), tr.rotation, tr.scale3d))
                else:
                    keys[b].append((tr.translation, tr.rotation, tr.scale3d))
        c = clip.get_editor_property('controller')
        c.open_bracket(unreal.Text('Get-up cut'), False)
        c.set_number_of_frames(unreal.FrameNumber(len(times) - 1), False)
        for b, xs in keys.items():
            c.set_bone_track_keys(b, [x[0] for x in xs], [x[1] for x in xs], [x[2] for x in xs], False)
        c.close_bracket(False)
        clip.set_preview_skeletal_mesh(mesh)
        clip.set_editor_property('enable_root_motion', False)
        save(clip)
        n = clip.data_model_interface.get_number_of_keys()
        p0, p1 = X.get_anim_pose_at_frame(clip, 0, opts), X.get_anim_pose_at_frame(clip, n - 1, opts)
        G = lambda p, b: X.get_bone_pose(p, b, W).translation
        idle = X.get_anim_pose_at_frame(find_asset('/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Neutral_Stand_Idle_Loop'), 0, opts)
        lie = G(p0, 'head') - G(p0, 'pelvis')
        out[name] = {
            'source': src_name, 'seconds': round(clip.get_play_length(), 2), 'frames': n,
            'skeleton': clip.get_editor_property('skeleton').get_path_name(),
            'root_motion': clip.get_editor_property('enable_root_motion'),
            'start_pelvis_cm': [round(v) for v in G(p0, 'pelvis').to_tuple()],
            'start_head_from_pelvis_cm': [round(v) for v in lie.to_tuple()],
            'end_pelvis_cm': [round(v) for v in G(p1, 'pelvis').to_tuple()],
            'end_vs_idle_cm': round(max((G(p1, b) - G(idle, b)).length() for b in ('pelvis', 'head', 'hand_l', 'hand_r', 'foot_l', 'foot_r')), 1),
        }
    return out


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
elif stage == 'stagger_overlay':
    RESULT = json.dumps(stagger_overlay(), default=str, indent=1)
elif stage == 'add_shield':
    RESULT = json.dumps(add_shield(), default=str)
elif stage == 'arm_shield':
    RESULT = json.dumps(arm_shield(ARGS[1:] or None), default=str)
elif stage == 'shield_status':
    RESULT = json.dumps(shield_status())
elif stage == 'build_shield':
    RESULT = json.dumps(build_shield(ARGS[1:] or None), default=str, indent=1)
elif stage == 'getups':
    RESULT = json.dumps(getups(), default=str, indent=1)
elif stage == 'grip_check':
    _check = grip_check(find_asset(WALKER).get_editor_property('skeleton'))
    (ROOT / 'grip_check.json').write_text(json.dumps(_check))
    RESULT = json.dumps({k: _check[k] for k in ('handle_diameter_cm', 'angles', 'fingers')}, indent=1)
elif stage == 'fist':
    RESULT = json.dumps({n: grip_fingers(unreal.load_object(None, '%s/%s.%s' % (FOLDER, n, n))) for n in ARGS[1:]}, default=str)
else:
    RESULT = json.dumps({'source': create_source, 'arm': arm, 'status': status, 'skeletons': skeletons,
                         'check': check, 'grip': grip}[stage](), default=str, indent=1)
RESULT
