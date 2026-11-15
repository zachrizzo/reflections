"""A line-up of the dressed soldiers, for a contact sheet: every soldier look standing guard with sword and shield.

One PIE of about 30 s. Seven soldiers stand in a row facing the hero, 1.6 m apart: the three Giltside looks as
AlliedSoldier and the four Frostside looks as Soldier (each look is passed by class, so the side-aware pool does not
change who wears what). After three seconds: one wide picture from the front, one from the side, and a close picture
of each. Also written down for each: its body mesh, what it holds and on which bone, which parts of the look are
hidden, and whether its walker exists (a look without its crowd animation blueprint would stand as a statue).
Nothing is changed or saved. Run in the editor's Python (top-level await, `call_tool`), PIE stopped, PIE lock held.
Result: Saved/NpcUnified/lineup_soldiers.json and L_* pictures.
"""

import base64
import json
from pathlib import Path

OUT = Path(unreal.Paths.project_saved_dir()) / 'NpcUnified'
OUT.mkdir(parents=True, exist_ok=True)
LINE = (('AlliedSoldier', 'GiltSoldier_BridgeGuard'), ('AlliedSoldier', 'GiltSoldier_Rowena'), ('AlliedSoldier', 'GiltSoldier_Archivist'),
        ('Soldier', 'FrostSoldier_Amara'), ('Soldier', 'FrostSoldier_Nia'), ('Soldier', 'FrostSoldier_Saran'), ('Soldier', 'FrostSoldier_Iven'))
result = {'checks': {}, 'soldiers': {}}


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
        await asyncio.sleep(1.5)
        console('Squads.Clear', world)
        npcs = unreal.get_world_subsystem(world, unreal.ReflectionsNpcSubsystem)
        hero_health = player.get_component_by_class(unreal.ReflectionsHealthComponent)
        hero_health.set_editor_property('max_health', 1000000.0)
        hero_health.reset_health()
        HERE = player.get_actor_location()
        GROUND = HERE.z - 90.0
        ahead = player.get_actor_forward_vector()
        ahead = unreal.Vector(ahead.x, ahead.y, 0.0).normal()
        side = unreal.Vector(-ahead.y, ahead.x, 0.0)

        def at(forward_cm, right_cm=0.0, up_cm=0.0):
            return unreal.Vector(HERE.x + ahead.x * forward_cm + side.x * right_cm, HERE.y + ahead.y * forward_cm + side.y * right_cm, GROUND + up_cm)

        TOWARD_HERO = unreal.MathLibrary.find_look_at_rotation(at(450), unreal.Vector(HERE.x, HERE.y, GROUND)).yaw

        def brain(actor):
            return actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent)

        def look_class(look_id):
            try:
                return unreal.load_object(None, '/Game/Characters/Lanthorne/Looks/Soldiers/%s.%s_C' % (look_id, look_id))
            except Exception:
                return None

        async def picture(name, look_at, from_point, size=900, fov=38.0):
            try:
                aim = unreal.MathLibrary.find_look_at_rotation(from_point, look_at)
                capture = unwrap(await call_tool('SceneCaptureToolset.SceneCaptureToolset.Capture', world=world,
                                                 camera={'location': {'x': from_point.x, 'y': from_point.y, 'z': from_point.z},
                                                         'rotation': {'pitch': aim.pitch, 'yaw': aim.yaw, 'roll': 0.0},
                                                         'projectionMode': 'Perspective', 'fOV': fov},
                                                 mode='Lit', options={'width': size, 'height': size, 'screenPercentage': 1.0, 'visualizationSubMode': ''}))
                data = capture.get('image') if isinstance(capture, dict) else None
                if isinstance(data, dict):
                    data = data.get('data') or data.get('base64')
                if data:
                    if ',' in data[:64]:
                        data = data.split(',', 1)[1]
                    (OUT / (name + '.png')).write_bytes(base64.b64decode(data))
            except Exception as error:
                result.setdefault('shot_errors', []).append(name + ': ' + repr(error)[:160])

        row = []
        for index, (archetype, look_id) in enumerate(LINE):
            cls = look_class(look_id)
            spot = at(450, (index - 3) * 160.0)
            actor = npcs.spawn_npc(archetype, spot, TOWARD_HERO, cls) if cls else None
            if actor:
                brain(actor).set_externally_steered(True)
            row.append((look_id, archetype, actor, spot))
            result['soldiers'][look_id] = {'archetype': archetype, 'class_loaded': bool(cls), 'spawned': bool(actor)}
            await asyncio.sleep(0.6)                      # one look at a time (memory rule of 01:23)
        await asyncio.sleep(3.0)

        for look_id, archetype, actor, spot in row:
            if not actor:
                continue
            info = result['soldiers'][look_id]
            walker = brain(actor).get_locomotion_driver()
            info['walker'] = bool(walker)
            info['class'] = actor.get_class().get_name()
            info['feet_z_minus_spawn_z'] = round(((walker.get_actor_location().z - 90.0) if walker else actor.get_actor_location().z) - spot.z, 1)
            for mesh in actor.get_components_by_class(unreal.SkeletalMeshComponent):
                if mesh.get_name() == 'Body':
                    asset = mesh.get_skeletal_mesh_asset()
                    info['body'] = asset.get_name() if asset else None
                    info['hands_above_ground'] = [round(mesh.get_socket_location(b).z - (walker.get_actor_location().z - 90.0 if walker else spot.z)) for b in ('hand_l', 'hand_r')]
            info['holds'] = [[part.get_editor_property('static_mesh').get_name(), str(part.get_attach_socket_name())]
                             for part in actor.get_components_by_class(unreal.StaticMeshComponent) if part.get_editor_property('static_mesh')]
            info['hidden_parts'] = sorted(part.get_name() for part in actor.get_components_by_class(unreal.SkeletalMeshComponent)
                                          if ('Armor' in part.get_name() or 'Shield' in part.get_name()) and part.get_editor_property('hidden_in_game'))
            info['shown_armour_or_shield_parts'] = sorted(part.get_name() for part in actor.get_components_by_class(unreal.SkeletalMeshComponent)
                                                          if ('Armor' in part.get_name() or 'Shield' in part.get_name()) and not part.get_editor_property('hidden_in_game'))

        middle = at(450, 0.0, 100.0)
        await picture('L_line_front', middle, at(-330, 0.0, 150.0), 1400, 60.0)
        await picture('L_line_left', middle, at(120, -820.0, 160.0), 1400, 50.0)
        for look_id, archetype, actor, spot in row:
            if actor:
                walker = brain(actor).get_locomotion_driver() or actor
                forward = walker.get_actor_forward_vector()
                chest = walker.get_actor_location() + unreal.Vector(0, 0, 10)
                await picture('L_' + look_id, chest, unreal.Vector(chest.x + forward.x * 300, chest.y + forward.y * 300, chest.z + 25))

        armed = [s for s in result['soldiers'].values() if s.get('spawned')]
        result['checks']['all_seven_spawned_and_walk'] = {'ok': len(armed) == len(LINE) and all(s.get('walker') for s in armed), 'detail': {k: [v.get('spawned'), v.get('walker')] for k, v in result['soldiers'].items()}}
        result['checks']['each_holds_sword_and_shield'] = {'ok': bool(armed) and all(any('Sword' in h[0] for h in s.get('holds', [])) and any('Shield' in h[0] for h in s.get('holds', [])) for s in armed), 'detail': None}
        result['checks']['no_armour_or_second_shield_shown'] = {'ok': bool(armed) and all(not s.get('shown_armour_or_shield_parts') for s in armed), 'detail': None}
    except Exception as error:
        import traceback
        result['error'] = repr(error)
        result['trace'] = traceback.format_exc()[-1200:]
    finally:
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')
        console('Squads.StartPatrol 1')

result['passed'] = sum(1 for c in result['checks'].values() if c['ok'])
result['failed'] = sorted(name for name, c in result['checks'].items() if not c['ok'])
(OUT / 'lineup_soldiers.json').write_text(json.dumps(result, indent=1, default=str))
json.dumps({'passed': result['passed'], 'failed': result['failed'], 'error': result.get('error')}, default=str)
