"""Points the soldiers' blade forward and turns the shield's face to the front, by data only (no C++).

The sword and the shield are placed from the hand's reference pose; where they point in the game depends on the
armed-hold clip. Measured on train #14: standing, the blade pointed 45 degrees to the right of the body and the
shield's face 45 degrees up. This script measures that on a Gilt and a Frost soldier in PIE and turns each prop
about the one axis that keeps it physically in place:
  sword   about the palm's normal, through the grip (the handle slants across the palm; 30 degrees at most)
  shield  about the forearm, through the forearm's line (it turns on the arm like a bracelet; 70 degrees at most)
It sets Combat.WeaponOffset / Combat.ShieldOffset on every archetype that carries one, in memory, re-spawns the two
soldiers, measures again standing and in a charge, and takes pictures.

Run in the editor's Python (top-level await, `call_tool`), map open, PIE stopped, PIE lock held:
  MODE = 'tune'  (default)  one PIE of about 40 s; nothing is saved
  MODE = 'save'             no PIE: saves the archetype assets that carry an offset, by path
  MODE = 'clear'            no PIE: sets both offsets back to none on every archetype (not saved)
Result: Saved/NpcUnified/tune_weapon_angles.json and W_* pictures.
"""

import base64
import json
import math
import time
from pathlib import Path

OUT = Path(unreal.Paths.project_saved_dir()) / 'NpcUnified'
OUT.mkdir(parents=True, exist_ok=True)
MODE = globals().get('MODE', 'tune')
NAMES = ('Civilian', 'Timid', 'Brave', 'Guard', 'Enemy', 'Hostile', 'Soldier', 'SoldierCaster', 'Infected', 'VillainHost', 'AlliedSoldier', 'AlliedSoldierCaster')
GRIP = unreal.Vector(-5.5, 0.0, 0.0)          # the grip on the sword, in its own space (Combat.WeaponGrip)
ARM = unreal.Vector(-6.0, 0.0, 0.0)           # the forearm's line, seen from the shield's middle
result = {'mode': MODE, 'checks': {}}


def unwrap(value):
    return value['returnValue'] if isinstance(value, dict) and 'returnValue' in value else value


def console(command, world=None):
    unreal.SystemLibrary.execute_console_command(world or unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world(), command)


def turned(pivot, degrees):
    """A turn of `degrees` about the prop's own Z axis through `pivot` (a point in the prop's space)."""
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    moved = unreal.Vector(pivot.x * c - pivot.y * s, pivot.x * s + pivot.y * c, pivot.z)
    return unreal.Transform(location=unreal.Vector(pivot.x - moved.x, pivot.y - moved.y, 0.0),
                            rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=degrees), scale=unreal.Vector(1.0, 1.0, 1.0))


def assets():
    found = []
    for name in NAMES:
        asset = unreal.load_asset('/Game/NPC/Archetypes/DA_Npc_' + name)
        if asset:
            found.append((name, asset))
    return found


def set_offsets(sword_degrees, shield_degrees):
    changed = []
    for name, asset in assets():
        combat = asset.get_editor_property('combat')
        touched = False
        if sword_degrees is not None and combat.get_editor_property('weapon_prop'):
            combat.set_editor_property('weapon_offset', turned(GRIP, sword_degrees))
            touched = True
        if shield_degrees is not None and combat.get_editor_property('shield_prop'):
            combat.set_editor_property('shield_offset', turned(ARM, shield_degrees))
            touched = True
        if touched:
            asset.set_editor_property('combat', combat)
            changed.append(name)
    return changed


if MODE == 'save':
    saved = []
    for name, asset in assets():
        combat = asset.get_editor_property('combat')
        yaw = [round(combat.get_editor_property(p).rotation.rotator().yaw, 1) for p in ('weapon_offset', 'shield_offset')]
        if any(abs(v) > 0.05 for v in yaw):
            path = '/Game/NPC/Archetypes/DA_Npc_' + name
            saved.append([name, yaw, unreal.EditorAssetLibrary.save_asset(path, False)])
    result['saved'] = saved
elif MODE == 'clear':
    result['cleared'] = set_offsets(0.0, 0.0)
elif unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
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

        TOWARD_HERO = unreal.MathLibrary.find_look_at_rotation(at(300), unreal.Vector(HERE.x, HERE.y, GROUND)).yaw

        def brain(actor):
            return actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent)

        def look_class(look_id):
            """The look's class: a dressed soldier look (Looks/Soldiers/<id>) or one of the older cast (Looks/BP_Look_<id>)."""
            for path in ('/Game/Characters/Lanthorne/Looks/Soldiers/%s.%s_C' % (look_id, look_id),
                         '/Game/Characters/Lanthorne/Looks/BP_Look_%s.BP_Look_%s_C' % (look_id, look_id)):
                try:
                    found = unreal.load_object(None, path)
                    if found:
                        return found
                except Exception:
                    pass
            return None

        def dot(a, b):
            return a.x * b.x + a.y * b.y + a.z * b.z

        def props(actor):
            """Each held prop with its own X and Z axes in the world, and the body's frame (the walker's)."""
            walker = brain(actor).get_locomotion_driver() or actor
            forward = walker.get_actor_forward_vector()
            right = walker.get_actor_right_vector()
            out = {'forward': forward, 'right': right}
            for part in actor.get_components_by_class(unreal.StaticMeshComponent):
                mesh = part.get_editor_property('static_mesh')
                if not mesh:
                    continue
                kind = 'sword' if 'Sword' in mesh.get_name() else ('shield' if 'Shield' in mesh.get_name() else None)
                if kind:
                    rotation = part.get_world_rotation()
                    out[kind] = {'x': unreal.MathLibrary.get_forward_vector(rotation), 'z': unreal.MathLibrary.get_up_vector(rotation)}
            return out

        def split(vector, frame):
            return [round(dot(vector, frame['forward']), 2), round(dot(vector, frame['right']), 2), round(vector.z, 2)]

        def report(actor):
            frame = props(actor)
            return {kind: split(frame[kind]['x'], frame) for kind in ('sword', 'shield') if kind in frame}

        def wanted(frame, forward, right, up):
            v = unreal.Vector(frame['forward'].x * forward + frame['right'].x * right, frame['forward'].y * forward + frame['right'].y * right, up)
            return v.normal()

        def best_turn(frame, kind, target, limit):
            """The turn about the prop's own Z (degrees, within the limit) that brings its X closest to the target."""
            best = (dot(frame[kind]['x'], target), 0.0)
            for step in range(-int(limit), int(limit) + 1, 2):
                turned_x = unreal.MathLibrary.rotate_angle_axis(frame[kind]['x'], float(step), frame[kind]['z'])
                score = dot(turned_x, target)
                if score > best[0] + 1e-4:
                    best = (score, float(step))
            return best

        async def close_up(name, look_at, from_point, size=700):
            try:
                aim = unreal.MathLibrary.find_look_at_rotation(from_point, look_at)
                capture = unwrap(await call_tool('SceneCaptureToolset.SceneCaptureToolset.Capture', world=world,
                                                 camera={'location': {'x': from_point.x, 'y': from_point.y, 'z': from_point.z},
                                                         'rotation': {'pitch': aim.pitch, 'yaw': aim.yaw, 'roll': 0.0},
                                                         'projectionMode': 'Perspective', 'fOV': 38.0},
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

        async def pictures(prefix, actor):
            walker = brain(actor).get_locomotion_driver() or actor
            forward, right = walker.get_actor_forward_vector(), walker.get_actor_right_vector()
            chest = walker.get_actor_location() + unreal.Vector(0, 0, 10)
            await close_up(prefix + '_front', chest, unreal.Vector(chest.x + forward.x * 330, chest.y + forward.y * 330, chest.z + 20))
            await close_up(prefix + '_side', chest, unreal.Vector(chest.x + right.x * 330, chest.y + right.y * 330, chest.z + 20))

        async def pair():
            gilt = npcs.spawn_npc('AlliedSoldier', at(300, -110), TOWARD_HERO, look_class('GiltSoldier_BridgeGuard'))
            frost = npcs.spawn_npc('Soldier', at(300, 110), TOWARD_HERO, look_class('FrostSoldier_Iven'))
            for posed in (gilt, frost):
                if posed:
                    brain(posed).set_externally_steered(True)
            await asyncio.sleep(3.0)
            return gilt, frost

        def remove(*actors):
            # (Destroying the look actor takes its hidden walker with it, the way the street crowd retires people.)
            for actor in actors:
                try:
                    if actor:
                        actor.destroy_actor()
                except Exception as error:
                    result.setdefault('remove_errors', []).append(repr(error)[:120])

        # ---- as it is now (whatever offsets the assets carry are taken off first) --------------------------
        set_offsets(0.0, 0.0)
        gilt, frost = await pair()
        result['before'] = {'gilt': report(gilt), 'frost': report(frost)}
        frame = props(gilt)
        # The blade: ahead, a little out to the sword side and a little up. The shield's face: ahead, a little up.
        sword_turn = best_turn(frame, 'sword', wanted(frame, 0.96, 0.15, 0.22), 30)
        shield_turn = best_turn(frame, 'shield', wanted(frame, 0.95, 0.10, 0.28), 70)
        if not globals().get('APPLY_TURNS', True):
            # Measuring only (the stance check after train #19): what the best turns would be is still reported.
            result['turns_not_applied'] = {'sword_deg': sword_turn[1], 'shield_deg': shield_turn[1]}
            sword_turn = (sword_turn[0], 0.0)
            shield_turn = (shield_turn[0], 0.0)
        result['turns'] = {'sword_deg': sword_turn[1], 'sword_alignment': round(sword_turn[0], 2), 'shield_deg': shield_turn[1], 'shield_alignment': round(shield_turn[0], 2)}
        remove(gilt, frost)
        await asyncio.sleep(0.3)

        # ---- with the turns -----------------------------------------------------------------------------------
        result['archetypes_changed'] = set_offsets(sword_turn[1], shield_turn[1])
        gilt, frost = await pair()
        result['after'] = {'gilt': report(gilt), 'frost': report(frost)}
        await pictures('W_gilt_standing', gilt)
        await pictures('W_frost_standing', frost)

        # ---- in a charge -----------------------------------------------------------------------------------------
        brain(gilt).set_externally_steered(False)
        foe = npcs.spawn_npc('Civilian', at(1150, -110), TOWARD_HERO, None)
        await asyncio.sleep(1.3)
        npcs.set_infection(foe, unreal.ReflectionsNpcInfection.INFECTED, None)
        start = gilt.get_actor_location()
        for _ in range(14):
            await asyncio.sleep(0.25)
            if (gilt.get_actor_location() - start).length() > 150.0:
                break
        result['after']['gilt_charging'] = report(gilt)
        await pictures('W_gilt_charging', gilt)
        unreal.GameplayStatics.apply_damage(foe, 999.0, None, None, unreal.DamageType)

        before, after = result['before']['gilt'], result['after']['gilt']
        result['checks']['blade_points_ahead_standing'] = {'ok': after['sword'][0] >= 0.85, 'detail': [before['sword'], after['sword']]}
        result['checks']['shield_faces_ahead_standing'] = {'ok': after['shield'][0] >= 0.75, 'detail': [before['shield'], after['shield']]}
        result['checks']['still_ahead_in_a_charge'] = {'ok': result['after']['gilt_charging']['sword'][0] >= 0.7 and result['after']['gilt_charging'].get('shield', [0])[0] >= 0.6,
                                                       'detail': result['after']['gilt_charging']}
    except Exception as error:
        import traceback
        result['error'] = repr(error)
        result['trace'] = traceback.format_exc()[-1500:]
    finally:
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')
        console('Squads.StartPatrol 1')

result['passed'] = sum(1 for c in result['checks'].values() if c['ok'])
result['failed'] = sorted(name for name, c in result['checks'].items() if not c['ok'])
(OUT / 'tune_weapon_angles.json').write_text(json.dumps(result, indent=2, default=str))
json.dumps(result, default=str)[:3000]
