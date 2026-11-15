"""What a soldier's corpse looks like: do its clothes follow the ragdoll, is anything else showing?

One PIE of about 30 s at default settings. Three soldiers (FrostSoldier_Iven, FrostSoldier_Amara,
GiltSoldier_BridgeGuard) are killed plainly, one at a time, with the candidate ragdoll fix applied from here
(bNoSkeletonUpdate on the body right after the kill, as train #23 does in C++). Three seconds later, for each corpse:
  * a close picture in the game's lighting and one in base colour (no lighting: the red death light does not hide
    what is cloth and what is skin);
  * every skeletal mesh part of the look: shown or hidden, which part it follows, and how far its bounds lie from the
    ragdoll's pelvis (a part that did not follow the body is metres away);
  * the hidden walker: is it hidden, and where is it.
Nothing is changed or saved. Result: Saved/NpcUnified/probe_corpse_look.json and K_* pictures.
"""

import base64
import json
from pathlib import Path

OUT = Path(unreal.Paths.project_saved_dir()) / 'NpcUnified'
OUT.mkdir(parents=True, exist_ok=True)
LOOKS = ('FrostSoldier_Iven', 'FrostSoldier_Amara', 'GiltSoldier_BridgeGuard')
result = {'corpses': {}}


def unwrap(value):
    return value['returnValue'] if isinstance(value, dict) and 'returnValue' in value else value


def console(command, world=None):
    unreal.SystemLibrary.execute_console_command(world or unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world(), command)


if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
    result['abort'] = 'PIE is already running (someone else is testing); nothing was started.'
else:
    console('Squads.StartPatrol 0')
    await call_tool('EditorToolset.EditorAppToolset.StartPIE')
    try:
        world = None
        player = None
        for _ in range(40):
            await asyncio.sleep(0.5)
            world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
            player = unreal.GameplayStatics.get_player_pawn(world, 0) if world else None
            if player and abs(player.get_velocity().z) < 5.0:
                break
        await asyncio.sleep(2.0)
        console('Squads.Clear', world)
        console('Npc.Heat 0', world)
        npcs = unreal.get_world_subsystem(world, unreal.ReflectionsNpcSubsystem)
        HERE = player.get_actor_location()
        GROUND = HERE.z - 90.0
        ahead = player.get_actor_forward_vector()
        ahead = unreal.Vector(ahead.x, ahead.y, 0.0).normal()
        side = unreal.Vector(-ahead.y, ahead.x, 0.0)

        def at(forward_cm, right_cm=0.0, up_cm=0.0):
            return unreal.Vector(HERE.x + ahead.x * forward_cm + side.x * right_cm, HERE.y + ahead.y * forward_cm + side.y * right_cm, GROUND + up_cm)

        TOWARD_HERO = unreal.MathLibrary.find_look_at_rotation(at(420), unreal.Vector(HERE.x, HERE.y, GROUND)).yaw

        def brain(actor):
            return actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent)

        def body_of(actor):
            return next(m for m in actor.get_components_by_class(unreal.SkeletalMeshComponent) if m.get_name() == 'Body')

        async def picture(name, look_at, from_point, mode):
            try:
                aim = unreal.MathLibrary.find_look_at_rotation(from_point, look_at)
                capture = unwrap(await call_tool('SceneCaptureToolset.SceneCaptureToolset.Capture', world=world,
                                                 camera={'location': {'x': from_point.x, 'y': from_point.y, 'z': from_point.z},
                                                         'rotation': {'pitch': aim.pitch, 'yaw': aim.yaw, 'roll': 0.0},
                                                         'projectionMode': 'Perspective', 'fOV': 50.0},
                                                 mode=mode, options={'width': 800, 'height': 800, 'screenPercentage': 1.0, 'visualizationSubMode': ''}))
                data = capture.get('image') if isinstance(capture, dict) else None
                if isinstance(data, dict):
                    data = data.get('data') or data.get('base64')
                if data:
                    if ',' in data[:64]:
                        data = data.split(',', 1)[1]
                    (OUT / (name + '.png')).write_bytes(base64.b64decode(data))
            except Exception as error:
                result.setdefault('shot_errors', []).append(name + ': ' + repr(error)[:160])

        made = []
        for index, look_id in enumerate(LOOKS):
            cls = unreal.load_object(None, '/Game/Characters/Lanthorne/Looks/Soldiers/%s.%s_C' % (look_id, look_id))
            actor = npcs.spawn_npc('Soldier', at(420, (index - 1) * 260.0), TOWARD_HERO, cls)
            await asyncio.sleep(1.5)
            brain(actor).set_externally_steered(True)
            unreal.GameplayStatics.apply_damage(actor, 999.0, None, player, unreal.DamageType)
            try:
                body_of(actor).set_editor_property('no_skeleton_update', True)
            except Exception as error:
                result.setdefault('flag_errors', []).append(repr(error)[:80])
            made.append((look_id, actor))
            await asyncio.sleep(0.8)
        await asyncio.sleep(3.0)

        for look_id, actor in made:
            body = body_of(actor)
            pelvis = body.get_center_of_mass('pelvis')
            info = {'pelvis_physics': [round(pelvis.x), round(pelvis.y), round(pelvis.z, 1)],
                    'pose_pelvis_z': round(body.get_socket_location('pelvis').z, 1), 'parts': []}
            for part in actor.get_components_by_class(unreal.SkeletalMeshComponent):
                try:
                    centre = unreal.SystemLibrary.get_component_bounds(part)[0]
                except Exception:
                    centre = None
                asset = None
                try:
                    asset = part.get_skeletal_mesh_asset()
                except Exception:
                    pass
                leader = None
                try:
                    leader_component = part.get_editor_property('leader_pose_component')
                    leader = leader_component.get_name() if leader_component else None
                except Exception as error:
                    leader = 'ERR ' + repr(error)[:30]
                info['parts'].append({'part': part.get_name(), 'mesh': asset.get_name() if asset else None, 'visible': part.is_visible(),
                                      'hidden_in_game': part.get_editor_property('hidden_in_game'), 'follows': leader,
                                      'cm_from_ragdoll_pelvis': round((centre - pelvis).length()) if centre else None})
            walker = brain(actor).get_locomotion_driver()
            if walker:
                mesh = walker.get_editor_property('mesh')
                info['walker'] = {'hidden_in_game_flag': walker.get_editor_property('hidden'),
                                  'mesh_visible': mesh.is_visible(), 'cm_from_ragdoll_pelvis': round((walker.get_actor_location() - pelvis).length())}
            info['held'] = [[part.get_editor_property('static_mesh').get_name(), part.is_visible(),
                             round((part.get_world_location() - pelvis).length())]
                            for part in actor.get_components_by_class(unreal.StaticMeshComponent) if part.get_editor_property('static_mesh')]
            result['corpses'][look_id] = info
            above = unreal.Vector(pelvis.x - ahead.x * 170.0, pelvis.y - ahead.y * 170.0, pelvis.z + 230.0)
            await picture('K_%s_lit' % look_id, pelvis, above, 'Lit')
            await picture('K_%s_colour' % look_id, pelvis, above, 'BaseColor')
        result['finished'] = True
    except Exception as error:
        import traceback
        result['error'] = repr(error)
        result['trace'] = traceback.format_exc()[-1500:]
    finally:
        try:
            console('Npc.Heat 1')
        except Exception:
            pass
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')
        console('Squads.StartPatrol 1')

(OUT / 'probe_corpse_look.json').write_text(json.dumps(result, indent=1, default=str))
json.dumps({'finished': result.get('finished'), 'error': result.get('error')}, default=str)
