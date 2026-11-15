"""PIE check of the aim-hold pose (run inside the editor via the MCP Python tool).

Holds aim (injected IA_Aim) so the driver plays CombatCasts/AS_Hero_CombatAimHold on the upper body, then captures the
game view plus two offscreen views of the hero (right side, front-right) where the right hand and torso are visible.
Then plays AS_Hero_CombatAimHold_V1 (the original clip) on the same slot and captures the same views, for an A/B.
Writes PNGs to Saved/SpellCombatTest/aimpose/.
"""
import base64
import json
import math
from pathlib import Path

APP = 'EditorToolset.EditorAppToolset.'
SC = 'SceneCaptureToolset.SceneCaptureToolset.'
OUT = Path(unreal.Paths.project_saved_dir()).resolve() / 'SpellCombatTest' / 'aimpose'
OUT.mkdir(parents=True, exist_ok=True)
report = {'shots': {}}


def save(name, r):
    data = r.get('image') if isinstance(r, dict) else None
    if isinstance(data, dict):
        data = data.get('data')
    if not data:
        report['shots'][name] = None
        return
    p = OUT / (name + '.png')
    p.write_bytes(base64.b64decode(data))
    report['shots'][name] = str(p)


async def game_shot(name):
    save(name, await call_tool(SC + 'CaptureGameViewport', world=None, maxResolution=1600))


async def side_shots(prefix, world_ref, pawn, mode):
    loc = pawn.get_actor_location()
    fwd = pawn.get_actor_forward_vector()
    right = pawn.get_actor_right_vector()
    yaw = pawn.get_actor_rotation().yaw
    views = {
        'right': (loc + right * 230.0 + fwd * 20.0 + unreal.Vector(0, 0, 45.0), yaw - 90.0 - 180.0 + 180.0 + 180.0),
        'front_right': (loc + fwd * 190.0 + right * 150.0 + unreal.Vector(0, 0, 55.0), yaw + 180.0 - 38.0),
    }
    for key, (cam, cam_yaw) in views.items():
        target = loc + unreal.Vector(0, 0, 45.0)
        d = target - cam
        cam_yaw = math.degrees(math.atan2(d.y, d.x))
        pitch = math.degrees(math.atan2(d.z, math.hypot(d.x, d.y)))
        camera = {'location': {'x': cam.x, 'y': cam.y, 'z': cam.z}, 'rotation': {'pitch': pitch, 'yaw': cam_yaw, 'roll': 0.0},
                  'projectionMode': 'Perspective', 'fOV': 55.0}
        r = await call_tool(SC + 'Capture', world=world_ref, camera=camera, mode=mode,
                            options={'width': 900, 'height': 900, 'screenPercentage': 1.0, 'visualizationSubMode': ''})
        save('%s_%s' % (prefix, key), r)


if await call_tool(APP + 'IsPIERunning'):
    raise RuntimeError('PIE is already running (someone else is testing); try again when it is free.')
await call_tool(APP + 'StartPIE', options={'warmupSeconds': 3.0})
try:
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    pawn = pc.get_controlled_pawn()
    worlds = await call_tool(SC + 'ListWorlds')
    wl = worlds if isinstance(worlds, list) else worlds.get('returnValue', worlds)
    pie = next(w for w in wl if w.get('worldType') == 'PIE')
    world_ref = pie['world']
    modes = await call_tool(SC + 'ListModes', bIncludeUnavailable=False)
    ml = modes if isinstance(modes, list) else modes.get('returnValue', modes)
    names = [m.get('name') if isinstance(m, dict) else str(m) for m in ml]
    report['modes'] = names[:12]
    mode = next((n for n in names if n in ('Lit', 'FinalColor', 'SceneColor')), names[0])
    report['mode'] = mode
    aim = {'action': unreal.load_object(None, '/Game/Input/IA_Aim.IA_Aim'), 'value': {'x': 1.0, 'y': 0.0, 'z': 0.0}}
    hold = asyncio.ensure_future(call_tool('InputToolset.InputToolset.ApplyInput', entries=[aim, {'key': {'keyName': 'RightMouseButton'}, 'value': {'x': 1.0, 'y': 0.0, 'z': 0.0}}], durationSeconds=3.2))
    await asyncio.sleep(1.4)
    comp = pawn.get_component_by_class(unreal.ReflectionsSpellAimComponent)
    report['aiming'] = comp.is_aiming() if comp else None
    await game_shot('v2_game')
    await side_shots('v2', world_ref, pawn, mode)
    await hold
    await asyncio.sleep(0.4)
    # A/B: the original clip on the same upper-body slot, at the same 0.3 s start offset the driver uses.
    v1 = unreal.load_asset('/Game/Characters/Hero/Animation/CombatCasts/AS_Hero_CombatAimHold_V1')
    played = []
    skel = v1.get_editor_property('skeleton')
    report['anim_instances'] = []
    for mesh in pawn.get_components_by_class(unreal.SkeletalMeshComponent):
        inst = mesh.get_anim_instance()
        asset = mesh.get_skinned_asset() if hasattr(mesh, 'get_skinned_asset') else None
        report['anim_instances'].append('%s:%s' % (mesh.get_name(), inst.get_class().get_name() if inst else None))
        if inst and asset and asset.get_editor_property('skeleton') == skel:
            inst.play_slot_animation_as_dynamic_montage(v1, 'DefaultSlot', 0.1, 0.2, 1.0, 1000, -1.0, 0.3)
            played.append(mesh.get_name())
    report['v1_played_on'] = played
    await asyncio.sleep(0.8)
    await side_shots('v1', world_ref, pawn, mode)
    await game_shot('v1_game')
finally:
    await call_tool(APP + 'StopPIE')
(OUT / 'report.json').write_text(json.dumps(report, indent=2, default=str))
json.dumps(report, default=str)
