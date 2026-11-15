"""Before/after close-ups of one NPC look in PIE: the look as it is, and the same look wearing fitted garments.

Run in the editor (Python, top-level await) while holding Saved/PIE_LOCK.json. Globals in:
    LOOK  = '/Game/Characters/Lanthorne/Looks/BP_Look_GiltFerryman'
    NEW   = ['/Game/Characters/Lanthorne/Clothing/Giltside/CivilianWorker/SK_..._Upper_FerryPilot', ...]
    BODY_HIDDEN = '/Game/.../SKM_FerryPilot_BodyHidden_<outfit>'   # optional: the outfit's hidden-skin body
    OUT_DIR, TAG
Nothing is saved and the editor level is not touched: both actors are spawned in the PIE world only.
The "after" actor hides every garment component on the look (anything that is not Body, Face or a groom) and adds
the new meshes as SkeletalMeshComponents under Body, leader-posed to Body, the way the look Blueprints wear clothes.
"""
import base64
import math
import os

import unreal

ED = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
KEEP = ('Body', 'Face')
RESULT = {'shots': []}


def garment_components(actor):
    out = []
    for c in actor.get_components_by_class(unreal.SkeletalMeshComponent):
        if c.get_name() in KEEP or isinstance(c, unreal.GroomComponent):
            continue
        out.append(c)
    return out


def body_of(actor):
    for c in actor.get_components_by_class(unreal.SkeletalMeshComponent):
        if c.get_name() == 'Body':
            return c
    return None


async def capture(world, target, name, yaw_off, dist, height, look_z, fov=32.0):
    loc = target.get_actor_location()
    yaw = target.get_actor_rotation().yaw + yaw_off
    sun = next(iter(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.DirectionalLight)), None)
    if sun is not None:
        sd = sun.get_actor_forward_vector()          # direction the light travels
        f0 = unreal.Vector(math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), 0)
        if f0.x * sd.x + f0.y * sd.y > 0:            # camera would look into the sun: shoot from the other side
            yaw += 180.0
    f = unreal.Vector(math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), 0)
    cam = loc + f * dist + unreal.Vector(0, 0, height)
    aim = loc + unreal.Vector(0, 0, look_z)
    rot = unreal.MathLibrary.find_look_at_rotation(cam, aim)
    res = await call_tool('SceneCaptureToolset.SceneCaptureToolset.Capture', world=world,
                          camera={'location': {'x': cam.x, 'y': cam.y, 'z': cam.z},
                                  'rotation': {'pitch': rot.pitch, 'yaw': rot.yaw, 'roll': 0.0},
                                  'projectionMode': 'Perspective', 'fOV': fov},
                          mode='Lit', options={'width': 900, 'height': 1200, 'screenPercentage': 1.0})
    img = res['image']
    data = img.get('data') if isinstance(img, dict) else img
    path = os.path.join(OUT_DIR, '%s_%s.png' % (TAG, name))
    with open(path, 'wb') as fh:
        fh.write(base64.b64decode(data))
    RESULT['shots'].append(path)
    return path


started = False
hidden = []
try:
    if not ED.get_game_world():
        await call_tool('EditorToolset.EditorAppToolset.StartPIE', options={'warmupSeconds': 2.0})
        started = True
    world = ED.get_game_world()
    pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
    base = pawn.get_actor_location() if pawn else unreal.Vector(0, 0, 100)
    cls = unreal.load_asset(LOOK).generated_class()
    cls_after = unreal.load_asset(LOOK_AFTER).generated_class() if globals().get('LOOK_AFTER') else cls
    # Face both copies toward the sun so the front camera is on the lit side.
    sun = next(iter(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.DirectionalLight)), None)
    yaw = 0.0
    if sun is not None:
        sd = sun.get_actor_forward_vector()
        yaw = math.degrees(math.atan2(-sd.y, -sd.x))
    # Two copies of the look, 2.5 m apart, both facing the same way, on the floor next to the player start.
    fw = unreal.Vector(math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), 0)
    rt = unreal.Vector(-fw.y, fw.x, 0)
    spots = [base + fw * 400 - rt * 125, base + fw * 400 + rt * 125]
    actors = []
    for k, p in enumerate(spots):
        hit = unreal.SystemLibrary.line_trace_single(world, p + unreal.Vector(0, 0, 200), p - unreal.Vector(0, 0, 500),
                                                     unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [],
                                                     unreal.DrawDebugTrace.NONE, True)
        t = hit.to_tuple() if hit else None
        floor = t[4] if t and t[0] else p
        # Python can't spawn into a PIE world directly; the NPC system's SpawnNpc can (and gives the look its walker).
        try:
            npc = unreal.get_world_subsystem(world, unreal.ReflectionsNpcSubsystem)
        except TypeError:
            npc = unreal.get_world_subsystem(unreal.ReflectionsNpcSubsystem, world)
        a = npc.spawn_npc('Civilian', floor, yaw, cls if k == 0 else cls_after)
        if a is not None and body_of(a) is None:
            for c in a.get_attached_actors(True, True) if hasattr(a, 'get_attached_actors') else []:
                if body_of(c) is not None:
                    a = c
                    break
        actors.append(a)
    before, after = actors
    RESULT['look_class'] = cls.get_name()
    if not globals().get('LOOK_AFTER'):
        RESULT['old_garments'] = [c.get_name() for c in garment_components(after)]
        for c in garment_components(after):
            c.set_visibility(False, True)
        body = body_of(after)
        if globals().get('BODY_HIDDEN'):
            # The outfit's body copy without the covered skin; the look's skin override materials stay on the component.
            body.set_skinned_asset_and_update(unreal.load_asset(BODY_HIDDEN), False)
            RESULT['body'] = BODY_HIDDEN
        # Python can't add components at runtime: reuse the look's own garment components (already leader-posed to the
        # body, as crowd-looks will wire it), one new mesh per component; the leftover old parts stay hidden.
        added = []
        old = garment_components(after)
        for comp, path in zip(old, NEW):
            comp.set_skinned_asset_and_update(unreal.load_asset(path), False)
            try:
                comp.set_editor_property('override_materials', [])
            except Exception:
                pass
            comp.set_visibility(True, False)
            added.append(comp.get_name() + '=' + path.rsplit('/', 1)[1])
        RESULT['added'] = added
        if globals().get('HIDE_HAIR'):
            # A helmet hides the hair: switch the Hair groom off on the "after" copy only.
            for c in after.get_components_by_class(unreal.GroomComponent):
                if c.get_name() == 'Hair':
                    c.set_visibility(False, False)
    # Keep everything else out of frame for the instant of each capture.
    for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Character):
        if a not in actors and not a.get_editor_property('hidden'):
            hidden.append(a)
    await asyncio.sleep(1.5)
    unreal.GameplayStatics.set_game_paused(world, True)
    for a in hidden:
        a.set_actor_hidden_in_game(True)
    for tag, act in (('before', before), ('after', after)):
        act2 = after if act is before else before
        act2.set_actor_hidden_in_game(True)
        await capture(world, act, tag + '_front', 15.0, 190.0, 150.0, 120.0)
        await capture(world, act, tag + '_side', 75.0, 190.0, 150.0, 120.0)
        await capture(world, act, tag + '_back', 170.0, 190.0, 150.0, 120.0)
        await capture(world, act, tag + '_full', 20.0, 330.0, 120.0, 95.0, fov=34.0)
        act2.set_actor_hidden_in_game(False)
finally:
    w = ED.get_game_world()
    if w:
        for a in hidden:
            try:
                a.set_actor_hidden_in_game(False)
            except Exception:
                pass
        unreal.GameplayStatics.set_game_paused(w, False)
    if started and ED.get_game_world():
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')
