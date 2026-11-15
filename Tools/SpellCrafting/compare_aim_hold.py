"""Old vs new aim hold on the full hero look (coat, face, hair), front and side views, offscreen.

Runs in the editor via the MCP Python tool with top-level await allowed. Uses a LevelSequence with two spawned
BP_HeroSampleVisual actors high above the level, so the shared map is never edited or dirtied.
ARGS stage: build | shots | close | pie (one PIE run: old and new while aiming, standing and strafing).
"""
import base64
import json
import os

SEQ_DIR = '/Game/SpellCrafting/Gestures/AimHold'
SEQ_NAME = 'LS_AimHoldV2_Compare'
VISUAL = '/Game/Characters/Hero/Sample/BP_HeroSampleVisual.BP_HeroSampleVisual_C'
CLIPS = {'Old': '/Game/Characters/Hero/Animation/CombatCasts/AS_Hero_CombatAimHold_V1.AS_Hero_CombatAimHold_V1',
         'New': '/Game/SpellCrafting/Gestures/AS_Hero_CombatAimHold_V2.AS_Hero_CombatAimHold_V2'}
# The same source frame of the original clip (frame 36): V2 starts at original frame 21.
SHOT_TIME = {'Old': 36, 'New': 15}
BASE = unreal.Vector(-4000.0, -4000.0, 3000.0)
SPACING = 1500.0
OUT = os.path.join(unreal.Paths.project_saved_dir(), 'SpellCraftingShots', 'AimHoldV2')
FPS = 30
LES = unreal.get_editor_subsystem(unreal.LevelSequenceEditorSubsystem)


def seq_asset():
    unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous([SEQ_DIR], True)
    return unreal.load_object(None, '%s/%s.%s' % (SEQ_DIR, SEQ_NAME, SEQ_NAME))


def location(i):
    return BASE + unreal.Vector(SPACING * i, 0.0, 0.0)


def build():
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    seq = seq_asset() or tools.create_asset(SEQ_NAME, SEQ_DIR, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    for b in list(seq.get_bindings()):
        b.remove()
    seq.set_display_rate(unreal.FrameRate(FPS, 1))
    seq.set_playback_start(0)
    seq.set_playback_end(90)
    cls = unreal.load_object(None, VISUAL)
    actors = []
    for i, (tag, clip_path) in enumerate(CLIPS.items()):
        binding = seq.add_spawnable_from_class(cls)
        binding.set_display_name('Hero | ' + tag)
        tr = binding.add_track(unreal.MovieScene3DTransformTrack)
        sec = tr.add_section()
        sec.set_range(0, 90)
        loc = location(i)
        chans = sec.get_all_channels()
        for ch, v in zip(chans[:3], (loc.x, loc.y, loc.z)):
            ch.set_default(v)
        actors.append((tag, binding, clip_path))
    unreal.EditorAssetLibrary.save_loaded_asset(seq, False)
    unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
    unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
    report = {}
    for tag, binding, clip_path in actors:
        bound = LES.get_bound_objects_for_binding(binding)
        actor = bound[0] if bound else None
        body = None
        if actor:
            body = next(c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name().startswith('Body'))
        report[tag] = {'actor': actor.get_name() if actor else None, 'body': body.get_name() if body else None}
        if not body:
            continue
        comp_binding = seq.add_possessable(body)
        comp_binding.set_parent(binding)
        anim = comp_binding.add_track(unreal.MovieSceneSkeletalAnimationTrack)
        sec = anim.add_section()
        sec.set_range(0, 90)
        params = sec.get_editor_property('params')
        params.set_editor_property('animation', unreal.load_object(None, clip_path))
        sec.set_editor_property('params', params)
        sec.set_editor_property('section_range', sec.get_editor_property('section_range'))
    unreal.EditorAssetLibrary.save_loaded_asset(seq, False)
    unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()
    return report


async def capture(tag, view, loc):
    if view == 'front':
        cam = {'location': {'x': loc.x, 'y': loc.y + 330.0, 'z': loc.z + 115.0}, 'rotation': {'pitch': -3.0, 'yaw': -90.0, 'roll': 0.0}}
    else:  # the character's right side (body +X is its left)
        cam = {'location': {'x': loc.x - 330.0, 'y': loc.y + 10.0, 'z': loc.z + 115.0}, 'rotation': {'pitch': -3.0, 'yaw': 0.0, 'roll': 0.0}}
    cam.update({'projectionMode': 'Perspective', 'fOV': 38.0})
    worlds = await call_tool('SceneCaptureToolset.SceneCaptureToolset.ListWorlds')
    worlds = worlds['returnValue'] if isinstance(worlds, dict) else worlds
    world = next(w['world'] for w in worlds if w['worldType'] == 'Editor')
    r = await call_tool('SceneCaptureToolset.SceneCaptureToolset.Capture', world=world, camera=cam,
                        mode='Lit', options={'width': 900, 'height': 1100, 'screenPercentage': 1.0, 'visualizationSubMode': ''})
    img = r['image'] if isinstance(r, dict) and 'image' in r else r['returnValue']['image']
    data = img['data'] if isinstance(img, dict) else img
    path = os.path.join(OUT, 'standing_%s_%s.png' % (view, tag.lower()))
    with open(path, 'wb') as f:
        f.write(base64.b64decode(data))
    return path


async def shots():
    os.makedirs(OUT, exist_ok=True)
    paths = []
    for i, tag in enumerate(CLIPS):
        unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(SHOT_TIME[tag])
        await asyncio.sleep(0.4)
        for view in ('front', 'side'):
            paths.append(await capture(tag, view, location(i)))
    return paths


AIM = '/Game/Input/IA_Aim.IA_Aim'
MOVE = '/Game/Input/IA_Move.IA_Move'
DRIVER = '/Script/reflections.ReflectionsSampleSpellDriver'


async def pie_capture(world, body, prefix, view, tag):
    feet, fwd = body.get_world_location(), body.get_right_vector()  # mesh +Y is the character's forward
    side = body.get_forward_vector() * -1.0  # mesh +X is the character's left
    d = fwd if view == 'front' else side
    loc = feet + d * 330.0 + unreal.Vector(0, 0, 115.0)
    rot = unreal.MathLibrary.make_rot_from_x(d * -1.0)
    cam = {'location': {'x': loc.x, 'y': loc.y, 'z': loc.z}, 'rotation': {'pitch': -3.0, 'yaw': rot.yaw, 'roll': 0.0},
           'projectionMode': 'Perspective', 'fOV': 38.0}
    r = await call_tool('SceneCaptureToolset.SceneCaptureToolset.Capture', world=world, camera=cam, mode='Lit',
                        options={'width': 900, 'height': 1100, 'screenPercentage': 1.0, 'visualizationSubMode': ''})
    img = r['image'] if isinstance(r, dict) and 'image' in r else r['returnValue']['image']
    path = os.path.join(OUT, '%s_%s_%s.png' % (prefix, view, tag))
    with open(path, 'wb') as f:
        f.write(base64.b64decode(img['data'] if isinstance(img, dict) else img))
    return path


def hand_forward(body):
    """Right hand ahead of spine_03 in the body's mesh space (cm): about -5 for the old clip, +24 for V2."""
    h = body.get_socket_transform('hand_r', unreal.RelativeTransformSpace.RTS_COMPONENT).translation
    s = body.get_socket_transform('spine_03', unreal.RelativeTransformSpace.RTS_COMPONENT).translation
    return round(h.y - s.y, 1)


async def pie():
    """One PIE run. Old and new are played the same way the driver plays its aim layer (looping DefaultSlot montage)
    while Aim is held, standing and strafing right, with the driver's tick paused so it can't swap its own clip back
    in. Then the driver is resumed to confirm which clip the spell core itself plays. PIE is always stopped."""
    if await call_tool('EditorToolset.EditorAppToolset.IsPIERunning'):
        raise RuntimeError('PIE already running; not touching it.')
    os.makedirs(OUT, exist_ok=True)
    log, paths = {}, []
    await call_tool('EditorToolset.EditorAppToolset.StartPIE')
    try:
        driver_cls = unreal.load_class(None, DRIVER)
        pawn = driver = None
        for _ in range(60):
            await asyncio.sleep(0.25)
            w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
            pc = unreal.GameplayStatics.get_player_controller(w, 0) if w else None
            pawn = pc.get_controlled_pawn() if pc else None
            driver = pawn.get_component_by_class(driver_cls) if pawn else None
            if driver:
                break
        visual = next(c for c in pawn.get_components_by_class(unreal.ChildActorComponent) if c.get_name().startswith('HeroVisual')).get_editor_property('child_actor')
        body = next(c for c in visual.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name().startswith('Body'))
        anim = body.get_anim_instance()
        worlds = await call_tool('SceneCaptureToolset.SceneCaptureToolset.ListWorlds')
        worlds = worlds['returnValue'] if isinstance(worlds, dict) else worlds
        world = next(x['world'] for x in worlds if x['worldType'] == 'PIE')
        await asyncio.sleep(1.0)
        aim = {'action': {'refPath': AIM}, 'value': {'x': 1, 'y': 0, 'z': 0}}
        strafe = {'action': {'refPath': MOVE}, 'value': {'x': 1, 'y': 0, 'z': 0}}
        driver.set_component_tick_enabled(False)
        for tag in ('old', 'new'):
            clip = unreal.load_object(None, CLIPS[tag.capitalize()])
            for prefix, entries in (('pie_standing', [aim]), ('pie_strafing', [aim, strafe])):
                held = asyncio.ensure_future(call_tool('InputToolset.InputToolset.ApplyInput', entries=entries, durationSeconds=3.2))
                await asyncio.sleep(0.3)
                anim.play_slot_animation_as_dynamic_montage(clip, 'DefaultSlot', 0.18, 0.2, 1.0, 1000, -1.0, 0.3)
                await asyncio.sleep(1.2)
                log['%s_%s_hand_fwd' % (prefix, tag)] = hand_forward(body)
                log['%s_%s_speed' % (prefix, tag)] = round(pawn.get_velocity().length())
                for view in ('front', 'side'):
                    paths.append(await pie_capture(world, body, prefix, view, tag))
                await held
                anim.montage_stop(0.1, None)
                await asyncio.sleep(0.4)
        # The real path: the driver chooses and plays its own aim clip.
        driver.set_component_tick_enabled(True)
        held = asyncio.ensure_future(call_tool('InputToolset.InputToolset.ApplyInput', entries=[aim, strafe], durationSeconds=3.0))
        await asyncio.sleep(1.5)
        log['driver_aim_hand_fwd'] = hand_forward(body)
        for view in ('front', 'side'):
            paths.append(await pie_capture(world, body, 'pie_driver', view, 'live'))
        await held
    finally:
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')
    return {'log': log, 'shots': paths}


TORSO = ('pelvis', 'spine_01', 'spine_02', 'spine_03', 'spine_04', 'spine_05', 'neck_01', 'neck_02', 'head', 'clavicle_l')
ARM = ('lowerarm_r', 'hand_r', 'middle_01_r', 'middle_03_r', 'index_03_r', 'thumb_03_r')


def torso_shapes(mesh):
    """Bone-space capsules and spheres of the mesh's physics asset on the torso, neck, head and far clavicle."""
    pa = mesh.get_editor_property('physics_asset')
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


def seg_dist(p, a, b):
    ab, ap = b - a, p - a
    t = max(0.0, min(1.0, ab.dot(ap) / max(1e-6, ab.dot(ab))))
    return (p - (a + ab * t)).length()


def arm_clearance(body, shapes, pad=3.0):
    """Signed clearance (cm) of the right forearm, hand and fingers from the torso shapes on the live pose."""
    space = unreal.RelativeTransformSpace.RTS_COMPONENT
    T = {b: body.get_socket_transform(b, space) for b in set(s[0] for s in shapes) | set(ARM)}
    e, h = T['lowerarm_r'].translation, T['hand_r'].translation
    pts = [e + (h - e) * t for t in (0.2, 0.4, 0.6, 0.8)] + [T[b].translation for b in ARM[1:]]
    best, where = 1e9, ''
    for bone, a, b, r in shapes:
        tr = T[bone]
        A, B = tr.rotation.rotate_vector(a) + tr.translation, tr.rotation.rotate_vector(b) + tr.translation
        for p in pts:
            d = seg_dist(p, A, B) - r - pad
            if d < best:
                best, where = d, bone
    return best, where


async def pie_check():
    """One PIE run: per-frame right-arm clearance from the torso collision bodies while Aim is held, standing and
    strafing right and left. 'old' plays the original with the driver paused; 'live' is the driver's own aim layer."""
    if await call_tool('EditorToolset.EditorAppToolset.IsPIERunning'):
        raise RuntimeError('PIE already running; not touching it.')
    out = {}
    await call_tool('EditorToolset.EditorAppToolset.StartPIE')
    try:
        driver_cls = unreal.load_class(None, DRIVER)
        pawn = driver = None
        for _ in range(60):
            await asyncio.sleep(0.25)
            w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
            pc = unreal.GameplayStatics.get_player_controller(w, 0) if w else None
            pawn = pc.get_controlled_pawn() if pc else None
            driver = pawn.get_component_by_class(driver_cls) if pawn else None
            if driver:
                break
        visual = next(c for c in pawn.get_components_by_class(unreal.ChildActorComponent) if c.get_name().startswith('HeroVisual')).get_editor_property('child_actor')
        body = next(c for c in visual.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name().startswith('Body'))
        anim = body.get_anim_instance()
        shapes = torso_shapes(body.get_skeletal_mesh_asset())
        await asyncio.sleep(1.0)
        aim = {'action': {'refPath': AIM}, 'value': {'x': 1, 'y': 0, 'z': 0}}
        phases = (('standing', [aim]),
                  ('strafe_right', [aim, {'action': {'refPath': MOVE}, 'value': {'x': 1, 'y': 0, 'z': 0}}]),
                  ('strafe_left', [aim, {'action': {'refPath': MOVE}, 'value': {'x': -1, 'y': 0, 'z': 0}}]))
        for tag in ('old', 'live'):
            driver.set_component_tick_enabled(tag == 'live')
            for name, entries in phases:
                held = asyncio.ensure_future(call_tool('InputToolset.InputToolset.ApplyInput', entries=entries, durationSeconds=3.0))
                await asyncio.sleep(0.2)
                if tag == 'old':
                    anim.play_slot_animation_as_dynamic_montage(unreal.load_object(None, CLIPS['Old']), 'DefaultSlot', 0.18, 0.2, 1.0, 1000, -1.0, 0.3)
                await asyncio.sleep(0.6)  # past the blend-in
                values, worst_bone, speeds = [], '', []
                while not held.done():
                    v, bone = arm_clearance(body, shapes)
                    if not values or v < min(values):
                        worst_bone = bone
                    values.append(v)
                    speeds.append(pawn.get_velocity().length())
                    await asyncio.sleep(0.03)
                await held
                if tag == 'old':
                    anim.montage_stop(0.1, None)
                await asyncio.sleep(0.4)
                out['%s_%s' % (tag, name)] = {'samples': len(values), 'min_clearance_cm': round(min(values), 1) if values else None,
                                              'samples_inside': sum(1 for v in values if v < 0), 'nearest_body': worst_bone,
                                              'mean_speed': round(sum(speeds) / max(1, len(speeds)))}
    finally:
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')
    return out


def close():
    unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
    return [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]


stage = (ARGS or ['build'])[0]
if stage == 'shots':
    RESULT = json.dumps(await shots())
elif stage == 'pie':
    RESULT = json.dumps(await pie())
elif stage == 'piecheck':
    RESULT = json.dumps(await pie_check())
else:
    RESULT = json.dumps({'build': build, 'close': close}[stage](), default=str)
RESULT
