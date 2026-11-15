"""Regenerate the hero's aim-hold pose with Kimodo, keeping the old idea and fixing the right hand.

The spell core's AS_Hero_CombatAimHold leads with the left hand (extended forward and up, open palm) and guards with
the right hand at the chest, but on the hero body the right hand sits at the spine plane with the elbow ~20 cm behind
the back: the forearm goes through the torso. This script generates candidate takes that keep the lead hand and move
the guard hand clearly in front of the chest, retargets them to the hero, and measures every frame.

ARGS stage: source [2] | status [2] | retarget [2] | measure | fixold [fwd dx dz] | finalize <Name> <start> <end> [blend]. Runs inside the editor via the MCP Python tool.
Generation only starts once the AnimGenOffline editor mode sees a finished transaction on each section while the
sequence is open; `source` ends by re-applying the prompts inside a transaction for that reason.
"""
import json
import math
import time
import traceback
from pathlib import Path

ROOT = Path(unreal.Paths.project_intermediate_dir()).resolve() / 'SpellCraftingAimHold'
ROOT.mkdir(exist_ok=True)
FOLDER = '/Game/SpellCrafting/Gestures/AimHold'
SOURCE = FOLDER + '/LS_Hero_AimHoldV2_Kimodo'
FINAL = '/Game/SpellCrafting/Gestures/AS_Hero_CombatAimHold_V2'
QUINN = '/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple'
BODY = '/Game/Characters/Hero/Assembled/Hero/Body/SKM_MHC_Hero_BodyMesh'
SOMA_MESH = '/Kimodo/Characters/Soma/soma_neutral'
SOMA_RTG = '/Game/Characters/Hero/Animation/CombatCasts/Rigs/RTG_SomaToHero'
MANNEQUIN_RTG = '/Game/Characters/Hero/Animation/Locomotion/RTG_MannequinToHero'
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
SAVE = unreal.EditorLoadingAndSavingUtils
FPS = 30
FRAMES = 90
holder = []

LEAD = ('Steady aiming stance, perfectly still, feet planted shoulder width apart. The left arm is extended forward and '
        'slightly upward, a little above shoulder height, with the open palm facing forward and the fingers spread, '
        'aiming at a distant target. ')
TAKES = (
    ('A', 71101, LEAD + 'The right hand is a loose fist held in front of the right side of the chest, a forearm\'s length '
     'away from the body, with the right elbow bent and pointing down and slightly outward. Hold this pose steadily the '
     'whole time, breathing slowly.'),
    ('B', 71102, LEAD + 'The right fist is raised in a guard in front of the chin and chest, well clear of the body, with '
     'the right elbow tucked down and out to the side like a boxer. Keep both arms steady the whole time.'),
    ('C', 71103, LEAD + 'The right hand is open with the palm facing forward, held beside and slightly in front of the '
     'right shoulder, ready to cast, with the elbow bent and away from the ribs. Hold perfectly still and breathe slowly.'),
)

# Round 2: take A cleared the torso but drew the right hand back behind the body. These say where the hand goes in
# terms of things the model knows well (the other arm, an object, the face).
TAKES_R2 = (
    ('D', 71201, LEAD + 'The right hand is held up in front of the chest, close to the left elbow, as if steadying the '
     'outstretched arm, with the right elbow pointing down. Stay perfectly still and breathe slowly.'),
    ('E', 71202, LEAD + 'The right hand is held in front of the stomach with the palm facing up, as if cradling a small '
     'glowing orb, with the elbow bent beside the body. Stay perfectly still and breathe slowly.'),
    ('F', 71203, LEAD + 'The right hand is a loose fist raised beside the right cheek, in front of the face, with the '
     'elbow down, like a fighter keeping a guard up. Stay perfectly still and breathe slowly.'),
)
ROUND = ARGS[1] if ARGS and len(ARGS) > 1 and ARGS[0] in ('source', 'status', 'retarget') else 'both'
if ROUND == '2':
    SOURCE = FOLDER + '/LS_Hero_AimHoldV2_Kimodo_R2'
    TAKES = TAKES_R2


def find_asset(path):
    name = path.rsplit('/', 1)[1]
    return unreal.find_object(None, path + '.' + name) or unreal.load_object(None, path + '.' + name)


def save(asset):
    return SAVE.save_packages([asset.get_package()], False)


def load_source():
    unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous([FOLDER], True)
    return unreal.load_object(None, SOURCE + '.' + SOURCE.rsplit('/', 1)[1])


def entries():
    for i, (name, seed, prompt) in enumerate(TAKES):
        yield dict(name=name, seed=seed, prompt=prompt, offset=i * (FRAMES + 12), frames=FRAMES)


def mixer_of(source):
    return next(t for t in source.get_bindings()[0].get_tracks() if isinstance(t, unreal.MovieSceneAnimationMixerTrack))


def create_source():
    unreal.SystemLibrary.execute_console_command(None, 'AnimGenOffline.RetiredAnimationGC.Enabled 0')
    unreal.EditorAssetLibrary.make_directory(FOLDER)
    source = load_source() or TOOLS.create_asset(SOURCE.rsplit('/', 1)[1], FOLDER, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    save(source)
    holder.append(source)
    defs = list(entries())
    end = defs[-1]['offset'] + FRAMES
    source.set_display_rate(unreal.FrameRate(FPS, 1))
    source.set_playback_start(0)
    source.set_playback_end(end)
    source.set_view_range(-.15, end / FPS + .3)
    source.set_work_range(-1., end / FPS + 1.)
    if source.get_bindings():
        mixer = mixer_of(source)
    else:
        binding = source.add_spawnable_from_class(unreal.SkeletalMeshActor)
        binding.set_display_name('Quinn | Aim hold V2')
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
                section.set_range(data['offset'], data['offset'] + FRAMES)
                g = section.get_editor_property('pose_generator')
                g.set_editor_property('RandomSeed', data['seed'])
                g.set_editor_property('movement_source', unreal.AnimGenOfflineMovementSource.GENERATED_ANIMATION)
                state['i'] += 1
                state['request'] = None
                return
            # Arm generation: the editor mode queues a section only on a finished transaction while Sequencer is open.
            if time.monotonic() - state['armed_at'] < 1.0:
                return
            for data, section in zip(defs, mixer.get_sections()):
                with unreal.ScopedEditorTransaction('Generate aim hold V2 ' + data['name']):
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


def retarget():
    body, quinn, soma = find_asset(BODY), find_asset(QUINN), find_asset(SOMA_MESH)
    out = {}
    for data, section in zip(entries(), mixer_of(load_source()).get_sections()):
        inline = section_anim(section)
        if not inline or inline.data_model_interface.get_num_bone_tracks() < 20:
            out[data['name']] = 'pending'
            continue
        on_quinn = inline.get_skeleton() == quinn.get_editor_property('skeleton')
        src_mesh, rtg = (quinn, find_asset(MANNEQUIN_RTG)) if on_quinn else (soma, find_asset(SOMA_RTG))
        name = 'AS_Hero_AimHoldV2_' + data['name']
        src = unreal.load_object(None, FOLDER + '/Source/' + name + '.' + name) or TOOLS.duplicate_asset(name, FOLDER + '/Source', inline)
        save(src)
        spec = unreal.IKRetargetBatchOperationInputs(
            assets_to_retarget=[unreal.AssetRegistryHelpers.create_asset_data(src)], source_mesh=src_mesh, target_mesh=body,
            ik_retarget_asset=rtg, target_path=FOLDER, use_source_path=False, include_referenced_assets=False,
            overwrite_existing_files=True, suffix='')
        clip = unreal.IKRetargetBatchOperation.run_batch_retarget(spec)[0].get_asset()
        clip.set_preview_skeletal_mesh(body)
        clip.set_editor_property('enable_root_motion', False)
        clip.set_editor_property('force_root_lock', True)
        save(clip)
        out[data['name']] = clip.get_path_name()
    return out


def seg_dist(p, a, b):
    ab = [b[i] - a[i] for i in range(3)]
    ap = [p[i] - a[i] for i in range(3)]
    t = max(0.0, min(1.0, sum(ab[i] * ap[i] for i in range(3)) / max(1e-6, sum(x * x for x in ab))))
    return math.dist(p, [a[i] + ab[i] * t for i in range(3)])


def measure_clip(clip):
    """Per-frame clearance on the hero. Torso = capsule from pelvis to neck_01; body mesh space has +Y forward."""
    body = find_asset(BODY)
    opts = unreal.AnimPoseEvaluationOptions()
    opts.set_editor_property('evaluation_type', unreal.AnimDataEvalType.RAW)
    opts.set_editor_property('optional_skeletal_mesh', body)
    names = {str(n) for n in unreal.AnimPoseExtensions.get_bone_names(unreal.AnimPoseExtensions.get_anim_pose_at_time(clip, 0.0, opts))}
    hand_r = [b for b in ('hand_r', 'middle_01_r', 'middle_03_r', 'index_03_r') if b in names]
    hand_l = [b for b in ('hand_l', 'middle_01_l', 'middle_03_l', 'index_03_l') if b in names]
    want = ['pelvis', 'spine_03', 'neck_01', 'lowerarm_r', 'lowerarm_l', 'head'] + hand_r + hand_l
    frames = []
    dur = clip.get_play_length()
    for i in range(int(dur * FPS) + 1):
        pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(clip, min(i / FPS, dur), opts)
        P = {b: unreal.AnimPoseExtensions.get_bone_pose(pose, b, unreal.AnimPoseSpaces.WORLD).translation.to_tuple() for b in want}
        frames.append(dict(
            right=min(seg_dist(P[b], P['pelvis'], P['neck_01']) for b in hand_r),
            left=min(seg_dist(P[b], P['pelvis'], P['neck_01']) for b in hand_l),
            elbow_r=seg_dist(P['lowerarm_r'], P['pelvis'], P['neck_01']),
            elbow_r_fwd=P['lowerarm_r'][1] - P['spine_03'][1],
            hand_r_fwd=P['hand_r'][1] - P['spine_03'][1],
            lead_fwd=P['hand_l'][1] - P['spine_03'][1],
            lead_h=P['hand_l'][2] - P['spine_03'][2],
            pose=[c for b in ('hand_r', 'hand_l', 'lowerarm_r', 'lowerarm_l', 'head') for c in P[b]]))
    return frames


def window_report(frames, start, end):
    w = frames[start:end + 1]
    seam = math.dist(frames[start]['pose'], frames[end]['pose'])
    jitter = max(math.dist(a['pose'], b['pose']) for a, b in zip(w, w[1:])) if len(w) > 1 else 0.0
    return dict(start=start, end=end, seconds=round((end - start) / FPS, 2),
                min_right_clearance=round(min(f['right'] for f in w), 1), min_left_clearance=round(min(f['left'] for f in w), 1),
                min_elbow_r_clearance=round(min(f['elbow_r'] for f in w), 1), min_elbow_r_fwd=round(min(f['elbow_r_fwd'] for f in w), 1),
                min_hand_r_fwd=round(min(f['hand_r_fwd'] for f in w), 1), mean_lead_fwd=round(sum(f['lead_fwd'] for f in w) / len(w), 1),
                mean_lead_h=round(sum(f['lead_h'] for f in w) / len(w), 1), loop_seam=round(seam, 1), max_step=round(jitter, 1))


def best_window(frames, min_len=45):
    """The hold window with the smallest loop seam among windows where every frame clears the torso."""
    best = None
    for s in range(0, len(frames) - min_len):
        for e in range(s + min_len, len(frames)):
            r = window_report(frames, s, e)
            if r['min_right_clearance'] < 24 or r['min_left_clearance'] < 18 or r['min_elbow_r_clearance'] < 16:
                continue
            score = r['loop_seam'] - 0.05 * (e - s)
            if best is None or score < best[0]:
                best = (score, r)
    return best[1] if best else None


def measure():
    out = {'old': window_report(measure_clip(find_asset(OLD)), 9, 81)}
    for data in [dict(name=t[0]) for t in TAKES + TAKES_R2] + [dict(name='G')]:
        clip = unreal.load_object(None, FOLDER + '/AS_Hero_AimHoldV2_%s.AS_Hero_AimHoldV2_%s' % (data['name'], data['name']))
        if not clip:
            out[data['name']] = 'missing'
            continue
        frames = measure_clip(clip)
        out[data['name']] = {'whole': window_report(frames, 0, len(frames) - 1), 'best_hold': best_window(frames)}
    (ROOT / 'measure.json').write_text(json.dumps(out, indent=2))
    return out


OLD = '/Game/Characters/Hero/Animation/CombatCasts/AS_Hero_CombatAimHold_V1'  # the original; the spell core's AS_Hero_CombatAimHold now holds V2
X = unreal.AnimPoseExtensions


def eval_opts():
    opts = unreal.AnimPoseEvaluationOptions()
    opts.set_editor_property('evaluation_type', unreal.AnimDataEvalType.RAW)
    opts.set_editor_property('optional_skeletal_mesh', find_asset(BODY))
    return opts


def local_keys(clip, bones):
    """Local (translation, rotation, scale) of each bone at every key."""
    opts = eval_opts()
    out = {b: [] for b in bones}
    for i in range(clip.data_model_interface.get_number_of_keys()):
        pose = X.get_anim_pose_at_frame(clip, i, opts)
        for b in bones:
            t = X.get_bone_pose(pose, b, unreal.AnimPoseSpaces.LOCAL)
            out[b].append((t.translation, t.rotation, t.scale3d))
    return out


def write_keys(clip, keys, frames=None):
    c = clip.get_editor_property('controller')
    c.open_bracket(unreal.Text('Aim hold V2'), False)
    ok = True
    if frames is not None:
        c.set_number_of_frames(unreal.FrameNumber(frames), False)
    for b, xs in keys.items():
        ok &= bool(c.set_bone_track_keys(b, [x[0] for x in xs], [x[1] for x in xs], [x[2] for x in xs], False))
    c.close_bracket(False)
    return ok


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


def inv(q):
    return unreal.Quat(-q.x, -q.y, -q.z, q.w)


def frame_quat(x, n):
    return unreal.MathLibrary.make_rot_from_xz(x, n).quaternion()


def fix_old(fwd=26.0, dx=-3.0, dz=5.0):
    """Take G: the original clip with only the right arm re-solved (two-bone IK) so the hand sits `fwd` cm in front of
    spine_03 and the elbow points down and out. The left arm, spine and the clip's breathing are untouched; the hand
    keeps its wrist angle relative to the forearm and its frame-to-frame motion (constant offset)."""
    old = find_asset(OLD)
    name = 'AS_Hero_AimHoldV2_G'
    clip = unreal.load_object(None, FOLDER + '/' + name + '.' + name) or TOOLS.duplicate_asset(name, FOLDER, old)
    opts = eval_opts()
    W = unreal.AnimPoseSpaces.WORLD
    rows = []
    for i in range(old.data_model_interface.get_number_of_keys()):
        pose = X.get_anim_pose_at_frame(old, i, opts)
        rows.append({b: X.get_bone_pose(pose, b, W) for b in ('clavicle_r', 'upperarm_r', 'lowerarm_r', 'hand_r', 'spine_03')})
    local = local_keys(old, ['upperarm_r', 'lowerarm_r'])
    mean_fwd = sum(r['hand_r'].translation.y - r['spine_03'].translation.y for r in rows) / len(rows)
    delta = unreal.Vector(dx, fwd - mean_fwd, dz)
    pole = unreal.Vector(-0.5, 0.2, -1.0)
    up_keys, lo_keys, err = [], [], 0.0
    for i, r in enumerate(rows):
        S, E, H = r['upperarm_r'].translation, r['lowerarm_r'].translation, r['hand_r'].translation
        L1, L2 = (E - S).length(), (H - E).length()
        to = H + delta - S
        d = min(to.length(), (L1 + L2) * 0.995)
        u = to.normal()
        T = S + u * d
        a = (L1 * L1 - L2 * L2 + d * d) / (2 * d)
        h = math.sqrt(max(0.0, L1 * L1 - a * a))
        w = (pole - u * pole.dot(u)).normal()
        E2 = S + u * a + w * h
        n_old, n_new = (E - S).cross(H - E), (E2 - S).cross(T - E2)
        up_c = frame_quat(E2 - S, n_new) * inv(frame_quat(E - S, n_old)) * r['upperarm_r'].rotation
        lo_c = frame_quat(T - E2, n_new) * inv(frame_quat(H - E, n_old)) * r['lowerarm_r'].rotation
        # Where the solved chain actually puts the elbow and hand (must match E2 and T).
        e_chk = S + up_c.rotate_vector(local['lowerarm_r'][i][0])
        h_lt = inv(r['lowerarm_r'].rotation).rotate_vector(H - E)
        h_chk = e_chk + lo_c.rotate_vector(h_lt)
        err = max(err, (e_chk - E2).length(), (h_chk - T).length())
        ut, _, us = local['upperarm_r'][i]
        lt, _, ls = local['lowerarm_r'][i]
        up_keys.append((ut, inv(r['clavicle_r'].rotation) * up_c, us))
        lo_keys.append((lt, inv(up_c) * lo_c, ls))
    ok = write_keys(clip, {'upperarm_r': up_keys, 'lowerarm_r': lo_keys})
    clip.set_preview_skeletal_mesh(find_asset(BODY))
    save(clip)
    frames = measure_clip(clip)
    return {'asset': clip.get_path_name(), 'write_ok': ok, 'chain_error_cm': round(err, 3), 'mean_fwd_before': round(mean_fwd, 1),
            'same_skeleton_as_body': clip.get_skeleton() == find_asset(BODY).get_editor_property('skeleton'),
            'whole': window_report(frames, 0, len(frames) - 1), 'window_9_81': window_report(frames, 9, 81),
            'best_hold': best_window(frames)}


def finalize(name, start, end, blend=12):
    """Copies take `name`, cropped to keys [start, end] with the last `blend` keys eased back into the first so the
    montage loop has no seam, to AS_Hero_CombatAimHold_V2, then re-measures it."""
    src = unreal.load_object(None, FOLDER + '/AS_Hero_AimHoldV2_%s.AS_Hero_AimHoldV2_%s' % (name, name))
    final_name = FINAL.rsplit('/', 1)[1]
    final = unreal.load_object(None, FINAL + '.' + final_name) or TOOLS.duplicate_asset(final_name, FINAL.rsplit('/', 1)[0], src)
    bones = [str(b) for b in src.data_model_interface.get_bone_track_names()]
    keys = {b: xs[start:end + 1] for b, xs in local_keys(src, bones).items()}
    n = end - start + 1
    k = max(1, min(blend, n - 1))
    for b, xs in keys.items():
        t0, q0, s0 = xs[0]
        for j in range(k):
            idx = n - k + j
            t = (j + 1) / k
            t = t * t * (3 - 2 * t)
            tt, qq, ss = xs[idx]
            xs[idx] = (tt + (t0 - tt) * t, slerp(qq, q0, t), ss + (s0 - ss) * t)
    ok = write_keys(final, keys, frames=n - 1)
    final.set_preview_skeletal_mesh(find_asset(BODY))
    final.set_editor_property('enable_root_motion', False)
    final.set_editor_property('force_root_lock', True)
    save(final)
    frames = measure_clip(final)
    return {'asset': final.get_path_name(), 'write_ok': ok, 'source': src.get_path_name(),
            'keys': final.data_model_interface.get_number_of_keys(), 'length': round(final.get_play_length(), 3),
            'check': window_report(frames, 0, len(frames) - 1)}


TORSO = ('pelvis', 'spine_01', 'spine_02', 'spine_03', 'spine_04', 'spine_05', 'neck_01', 'neck_02', 'head', 'clavicle_l')


def torso_shapes():
    """The hero physics asset's capsules and spheres on the torso, neck, head and the far clavicle (bone space)."""
    pa = find_asset(BODY).get_editor_property('physics_asset')
    shapes = []
    for bs in [o for o in unreal.ObjectIterator(unreal.BodySetup) if o.get_outer() == pa]:
        bone = str(bs.get_editor_property('bone_name'))
        if bone not in TORSO:
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


def physics_check(path, start=0, end=None, pad=3.0):
    """Per-frame signed clearance (cm) of the right hand, fingers and forearm from the torso collision shapes.
    `pad` is the half-thickness of the hand and forearm; below zero means the arm is inside the body."""
    clip = find_asset(path)
    opts = eval_opts()
    shapes = torso_shapes()
    W = unreal.AnimPoseSpaces.WORLD
    n = clip.data_model_interface.get_number_of_keys()
    end = n - 1 if end is None else end
    worst, worst_frame, worst_shape = 1e9, -1, ''
    per_frame = []
    for i in range(start, end + 1):
        pose = X.get_anim_pose_at_frame(clip, i, opts)
        bones = {b: X.get_bone_pose(pose, b, W) for b in set([s[0] for s in shapes] + ['lowerarm_r', 'hand_r', 'middle_01_r', 'middle_03_r', 'index_03_r', 'thumb_03_r'])}
        e, h = bones['lowerarm_r'].translation, bones['hand_r'].translation
        pts = [e + (h - e) * t for t in (0.2, 0.4, 0.6, 0.8)] + [bones[b].translation for b in ('hand_r', 'middle_01_r', 'middle_03_r', 'index_03_r', 'thumb_03_r')]
        best = 1e9
        for bone, a, b, r in shapes:
            tr = bones[bone]
            A, B = tr.rotation.rotate_vector(a) + tr.translation, tr.rotation.rotate_vector(b) + tr.translation
            for p in pts:
                d = seg_dist(p.to_tuple(), A.to_tuple(), B.to_tuple()) - r - pad
                if d < best:
                    best, best_shape = d, bone
        per_frame.append(round(best, 1))
        if best < worst:
            worst, worst_frame, worst_shape = best, i, best_shape
    return {'clip': path, 'frames': [start, end], 'shapes': len(shapes), 'min_clearance_cm': round(worst, 1),
            'at_frame': worst_frame, 'nearest_body': worst_shape, 'frames_inside': sum(1 for v in per_frame if v < 0)}


stage = (ARGS or ['status'])[0]
if stage == 'finalize':
    result = finalize(ARGS[1], int(ARGS[2]), int(ARGS[3]), *[int(a) for a in ARGS[4:5]])
elif stage == 'physcheck':
    result = [physics_check(OLD, 9, 81), physics_check(FINAL)] + [physics_check(FOLDER + '/AS_Hero_AimHoldV2_' + t) for t in 'ABCDEF']
elif stage == 'fixold':
    result = fix_old(*[float(a) for a in ARGS[1:4]])
else:
    result = {'source': create_source, 'status': status, 'retarget': retarget, 'measure': measure}[stage]()
RESULT = json.dumps(result, default=str, indent=1)
RESULT
