"""NPCs on the new game map, /Game/GrayLondon/Maps/MedievalLondon: one PIE of about 45 s, nothing saved.

The user's ask (2026-11-15, 12:55): "make the crowds and stuff work well ... and the NPCs work well". Everything the NPC
system proved before was on GrayLondon_Geodata. This run looks at the new town in one go:

  1  CENSUS of everyone the game itself put there, about ten seconds into play: who (archetype, look), does it have
     its walker, do its feet stand on the floor (capsule bottom against the floor under it), is it posed (not in the
     reference pose with the arms out, not without a pose), is it shown, is it boxed in by walls. Then again 2.5 s
     later: who is trying to move and is not getting anywhere.
  2  A TIGHT LANE: the nearest lane to the start is found by measuring (3 to 5.2 m between the walls). Two
     townspeople, a Frost soldier and a Gilt guard are stood in it (spawned through SpawnNpc, so on the floor snap).
     Checked: on the floor, posed, not in a wall, soldiers holding sword and shield.
  3  A FIREBALL into them: how far each is thrown, whether anyone ends up in a wall or stuck, whether the frightened
     run along the lane.
  4  DEATHS there: one townsperson and the soldier are killed; the corpses must keep their pose, lie low, and not be
     inside a wall.
Two pictures of the lane (before the Fireball, after the deaths).

Run in the editor's Python (top-level await, `call_tool`), MedievalLondon open, PIE stopped, PIE lock held.
WALKER_PHYSICS = 0 (default) leaves the game as it ships; 2 turns the knockdowns on for the run.
Result: Saved/NpcUnified/verify_medieval.json and V_* pictures.
"""

import base64
import json
import math
import time
from pathlib import Path

OUT = Path(unreal.Paths.project_saved_dir()) / 'NpcUnified'
OUT.mkdir(parents=True, exist_ok=True)
result = {'checks': {}, 'started': time.strftime('%H:%M:%S'), 'walker_physics': int(globals().get('WALKER_PHYSICS', 0))}
LOG_PATH = Path(unreal.Paths.project_log_dir()) / 'reflections.log'
try:
    log_start = LOG_PATH.stat().st_size
except OSError:
    log_start = 0


def check(name, ok, detail=None):
    result['checks'][name] = {'ok': bool(ok), 'detail': detail}


def save():
    (OUT / 'verify_medieval.json').write_text(json.dumps(result, indent=1, default=str))


def unwrap(value):
    return value['returnValue'] if isinstance(value, dict) and 'returnValue' in value else value


def console(command, world=None):
    unreal.SystemLibrary.execute_console_command(world or unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world(), command)


result['map'] = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world().get_name()
if 'MedievalLondon' not in result['map'] and not globals().get('ANY_MAP'):
    result['abort'] = 'the editor has %s open, not MedievalLondon; nothing was started.' % result['map']
elif unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
    result['abort'] = 'PIE is already running (someone else is testing); nothing was started.'
else:
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
        began = time.perf_counter()
        npcs = unreal.get_world_subsystem(world, unreal.ReflectionsNpcSubsystem)
        controller = player.get_controller()
        spells = player.get_component_by_class(unreal.ReflectionsSpellCombatComponent)
        hero_health = player.get_component_by_class(unreal.ReflectionsHealthComponent)
        hero_health.set_editor_property('max_health', 1000000.0)
        hero_health.reset_health()
        console('Npc.Heat 0', world)
        HERO_START = player.get_actor_location()
        result['hero_start'] = [round(HERO_START.x), round(HERO_START.y), round(HERO_START.z, 1)]
        WORLD_STATIC = [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1]

        def trace(start, end, ignore=()):
            hit = unreal.SystemLibrary.line_trace_single_for_objects(world, start, end, WORLD_STATIC, False, list(ignore), unreal.DrawDebugTrace.NONE, True)
            if not hit:
                return None
            parts = unreal.GameplayStatics.break_hit_result(hit)
            if not parts[0]:
                return None
            return {'distance': parts[3], 'point': parts[5], 'actor': parts[9], 'component': parts[10]}

        def floor_under(point, ignore=()):
            hit = trace(unreal.Vector(point.x, point.y, point.z + 120.0), unreal.Vector(point.x, point.y, point.z - 400.0), ignore)
            return hit['point'].z if hit else None

        def free_width(point, axis):
            """Room between the walls across a lane at chest height, and the two distances (cm)."""
            chest = unreal.Vector(point.x, point.y, point.z + 110.0)
            sides = []
            for sign in (1.0, -1.0):
                hit = trace(chest, unreal.Vector(chest.x + axis[0] * sign * 900.0, chest.y + axis[1] * sign * 900.0, chest.z))
                sides.append(round(hit['distance']) if hit else 900)
            return sides[0] + sides[1], sides

        def brain(actor):
            return actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent)

        def body_of(actor):
            return next((m for m in actor.get_components_by_class(unreal.SkeletalMeshComponent) if m.get_name() == 'Body'), None)

        def look_at(actor):
            """One NPC, measured."""
            row = {'look': actor.get_class().get_name().replace('BP_Look_', '').replace('_C', '')}
            mind = brain(actor)
            try:
                archetype = mind.get_active_archetype()
                row['archetype'] = archetype.get_name().replace('DA_Npc_', '') if archetype else None
                row['reaction'] = mind.get_editor_property('reaction').name
            except Exception as error:
                row['archetype'] = 'ERR ' + repr(error)[:40]
            walker = mind.get_locomotion_driver() if mind else None
            row['walker'] = bool(walker)
            where = (walker or actor).get_actor_location()
            row['at'] = [round(where.x), round(where.y), round(where.z, 1)]
            if walker:
                capsule = walker.get_component_by_class(unreal.CapsuleComponent)
                bottom = where.z - capsule.get_scaled_capsule_half_height()
                floor = floor_under(unreal.Vector(where.x, where.y, bottom), [walker, actor])
                row['feet_above_floor_cm'] = round(bottom - floor, 1) if floor is not None else None
                row['speed'] = round(walker.get_velocity().length())
                try:
                    row['pushing'] = round(walker.get_component_by_class(unreal.CharacterMovementComponent).get_current_acceleration().length())
                except Exception:
                    row['pushing'] = None
                # Boxed in: walls closer than 30 cm on three or four sides of the chest.
                chest = unreal.Vector(where.x, where.y, where.z + 20.0)
                near = 0
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    hit = trace(chest, unreal.Vector(chest.x + dx * 60.0, chest.y + dy * 60.0, chest.z), [walker, actor])
                    near += 1 if hit and hit['distance'] < 30.0 else 0
                row['walls_within_30cm'] = near
            body = body_of(actor)
            if body:
                pelvis, left, right = (body.get_socket_location(b) for b in ('pelvis', 'hand_l', 'hand_r'))
                row['pose_empty'] = pelvis.x == 0.0 and pelvis.y == 0.0 and pelvis.z == 0.0
                row['hands_above_pelvis_cm'] = [round(left.z - pelvis.z), round(right.z - pelvis.z)]
                row['hands_apart_cm'] = round((left - right).length())
                row['pelvis_above_floor_cm'] = None
                floor = floor_under(pelvis, [actor] + ([walker] if walker else []))
                if floor is not None and not row['pose_empty']:
                    row['pelvis_above_floor_cm'] = round(pelvis.z - floor, 1)
                row['simulating'] = body.is_any_simulating_physics()
            row['hidden'] = actor.is_hidden_ed() if False else bool(actor.get_editor_property('hidden'))
            row['holds'] = sorted(part.get_editor_property('static_mesh').get_name().replace('SM_', '')[:20]
                                  for part in actor.get_components_by_class(unreal.StaticMeshComponent) if part.get_editor_property('static_mesh'))
            # Arms out like the reference pose: both hands at or above the pelvis on someone who holds nothing.
            row['arms_out'] = bool(body and not row.get('pose_empty') and not row['holds'] and min(row['hands_above_pelvis_cm']) > -2)
            return row

        async def picture(name, target, from_point):
            try:
                aim = unreal.MathLibrary.find_look_at_rotation(from_point, target)
                capture = unwrap(await call_tool('SceneCaptureToolset.SceneCaptureToolset.Capture', world=world,
                                                 camera={'location': {'x': from_point.x, 'y': from_point.y, 'z': from_point.z},
                                                         'rotation': {'pitch': aim.pitch, 'yaw': aim.yaw, 'roll': 0.0},
                                                         'projectionMode': 'Perspective', 'fOV': 70.0},
                                                 mode='Lit', options={'width': 1100, 'height': 700, 'screenPercentage': 1.0, 'visualizationSubMode': ''}))
                data = capture.get('image') if isinstance(capture, dict) else None
                if isinstance(data, dict):
                    data = data.get('data') or data.get('base64')
                if data:
                    if ',' in data[:64]:
                        data = data.split(',', 1)[1]
                    (OUT / (name + '.png')).write_bytes(base64.b64decode(data))
            except Exception as error:
                result.setdefault('shot_errors', []).append(name + ': ' + repr(error)[:160])

        # ---- 1: the census -------------------------------------------------------------------------------
        await asyncio.sleep(max(0.0, 9.0 - (time.perf_counter() - began)))
        people = [a for a in npcs.get_npc_actors() if a]
        first = {a: look_at(a) for a in people}
        await asyncio.sleep(2.5)
        census = []
        for actor, row in first.items():
            try:
                later = look_at(actor)
            except Exception:
                continue
            row['moved_cm_in_2.5s'] = round(math.hypot(later['at'][0] - row['at'][0], later['at'][1] - row['at'][1]))
            row['stuck'] = bool((row.get('pushing') or 0) > 50 and (later.get('pushing') or 0) > 50 and row['moved_cm_in_2.5s'] < 10)
            row['arms_out_later'] = later.get('arms_out')
            census.append(row)
        by_type = {}
        for row in census:
            by_type[row.get('archetype')] = by_type.get(row.get('archetype'), 0) + 1
        bad_feet = [r for r in census if r.get('walker') and r.get('feet_above_floor_cm') is not None and not -6.0 <= r['feet_above_floor_cm'] <= 12.0 and r.get('reaction') != 'INCAPACITATED']
        result['census'] = {'count': len(census), 'by_archetype': by_type, 'looks': sorted({r['look'] for r in census}),
                            'without_walker': [r['look'] for r in census if not r.get('walker')],
                            'feet_off_the_floor': [[r['look'], r['feet_above_floor_cm'], r['at']] for r in bad_feet],
                            'no_floor_found': [[r['look'], r['at']] for r in census if r.get('walker') and r.get('feet_above_floor_cm') is None],
                            'arms_out': [[r['look'], r['hands_above_pelvis_cm']] for r in census if r.get('arms_out') and r.get('arms_out_later') and not r.get('hidden')],
                            'without_a_pose': [r['look'] for r in census if r.get('pose_empty')],
                            'hidden': [r['look'] for r in census if r.get('hidden')],
                            'boxed_in': [[r['look'], r['at']] for r in census if (r.get('walls_within_30cm') or 0) >= 3],
                            'stuck': [[r['look'], r['at'], r.get('reaction')] for r in census if r.get('stuck')],
                            'armed': [[r['look'], r['archetype'], r['holds']] for r in census if r.get('holds')],
                            'feet_cm': sorted(r['feet_above_floor_cm'] for r in census if r.get('feet_above_floor_cm') is not None)}
        result['census_rows'] = census
        # Two live, shown NPCs within 40 cm of each other: one is standing in the other.
        shown = [r for r in census if r.get('walker') and r.get('reaction') != 'INCAPACITATED' and not r.get('hidden')]
        inside = []
        for i, one in enumerate(shown):
            for other in shown[i + 1:]:
                apart = math.hypot(one['at'][0] - other['at'][0], one['at'][1] - other['at'][1])
                if apart < 40.0 and abs(one['at'][2] - other['at'][2]) < 120.0:
                    inside.append([one['look'], other['look'], round(apart), one['at']])
        result['census']['standing_in_each_other'] = inside
        c = result['census']
        check('1_people_are_there', c['count'] >= 5, {'count': c['count'], 'by_archetype': by_type})
        check('1_everyone_has_a_walker_and_stands_on_the_floor', not c['without_walker'] and not c['feet_off_the_floor'] and not c['no_floor_found'],
              {k: c[k] for k in ('without_walker', 'feet_off_the_floor', 'no_floor_found')})
        check('1_nobody_in_the_reference_pose_or_without_a_pose', not c['arms_out'] and not c['without_a_pose'], {k: c[k] for k in ('arms_out', 'without_a_pose')})
        check('1_nobody_boxed_in_or_stuck', not c['boxed_in'] and not c['stuck'], {k: c[k] for k in ('boxed_in', 'stuck')})
        check('1_nobody_standing_in_another', not c['standing_in_each_other'], c['standing_in_each_other'])
        save()

        # ---- 2: a tight lane ---------------------------------------------------------------------------------
        # Found by measuring, not from the layout's numbers (the streets are being moved): points on a 4 m grid around
        # the hero's start, nearest first, for at most 5 s; a lane is 3 to 5.2 m between the walls one way and at least
        # 14 m free the other way.
        lanes = []
        hero_floor = floor_under(HERO_START)
        base_z = (hero_floor if hero_floor is not None else 0.0) + 5.0
        grid = sorted(((dx, dy) for dx in range(-30, 31) for dy in range(-30, 31)), key=lambda d: d[0] * d[0] + d[1] * d[1])
        scan_began = time.perf_counter()
        scanned = 0
        for dx, dy in grid:
            if time.perf_counter() - scan_began > 5.0 or len(lanes) >= 4:
                break
            if dx * dx + dy * dy < 9:
                continue                                            # not on the hero's own doorstep
            point = unreal.Vector(HERO_START.x + dx * 400.0, HERO_START.y + dy * 400.0, base_z)
            floor = floor_under(point)
            scanned += 1
            if floor is None or abs(floor - (base_z - 5.0)) > 60.0:
                continue                                            # a roof or a hole, not the street
            point = unreal.Vector(point.x, point.y, floor)
            for across, along_axis in (((1.0, 0.0), (0.0, 1.0)), ((0.0, 1.0), (1.0, 0.0))):
                width, sides = free_width(point, across)
                if not 300 <= width <= 520:
                    continue
                along, along_sides = free_width(point, along_axis)
                if along >= 1400 and min(along_sides) >= 450:
                    lanes.append((width, math.hypot(dx, dy), point, sides, across, along_axis))
                    break
        result['lane_scan'] = {'points': scanned, 'seconds': round(time.perf_counter() - scan_began, 1)}
        result['lanes_found'] = [[round(l[2].x), round(l[2].y), l[0]] for l in lanes[:8]]
        if lanes:
            width, _, spot, sides, across, along_axis = lanes[0]
            # Stand in the middle of the lane, looking along it.
            shift = (sides[0] - sides[1]) * 0.5
            spot = unreal.Vector(spot.x + across[0] * shift, spot.y + across[1] * shift, spot.z)
            ahead, side = unreal.Vector(along_axis[0], along_axis[1], 0.0), unreal.Vector(across[0], across[1], 0.0)
        else:
            width, spot = None, unreal.Vector(HERO_START.x, HERO_START.y, hero_floor if hero_floor is not None else HERO_START.z - 90.0)
            forward = player.get_actor_forward_vector()
            ahead = unreal.Vector(forward.x, forward.y, 0.0).normal()
            side = unreal.Vector(-ahead.y, ahead.x, 0.0)
        result['lane'] = {'found': bool(lanes), 'width_cm': width, 'at': [round(spot.x), round(spot.y), round(spot.z, 1)]}
        player.set_actor_location(unreal.Vector(spot.x - ahead.x * 250.0, spot.y - ahead.y * 250.0, spot.z + 100.0), False, True)
        controller.set_control_rotation(unreal.MathLibrary.find_look_at_rotation(unreal.Vector(0, 0, 0), ahead))
        for other in people:
            try:
                if (other.get_actor_location() - spot).length() < 2500.0:
                    npcs.hold_npc(other, 40.0)              # the lane's own people stand still for the test
            except Exception:
                pass
        await asyncio.sleep(1.0)

        def lane_point(forward_cm, right_cm=0.0):
            return unreal.Vector(spot.x + ahead.x * forward_cm + side.x * right_cm, spot.y + ahead.y * forward_cm + side.y * right_cm, spot.z)

        facing = unreal.MathLibrary.find_look_at_rotation(lane_point(300), lane_point(-250)).yaw

        def soldier_look(name):
            try:
                return unreal.load_object(None, '/Game/Characters/Lanthorne/Looks/Soldiers/%s.%s_C' % (name, name))
            except Exception:
                return None

        cast_of = (('Civilian', None, 150, -45), ('Civilian', None, 250, 45), ('Soldier', soldier_look('FrostSoldier_Iven'), 370, -40),
                   ('Guard', None, 480, 40))
        group = []
        for archetype, look, forward_cm, right_cm in cast_of:
            actor = npcs.spawn_npc(archetype, lane_point(forward_cm, right_cm), facing, look)
            if actor:
                brain(actor).set_externally_steered(archetype != 'Civilian')
                group.append((archetype, actor))
            await asyncio.sleep(0.5)
        await asyncio.sleep(1.8)
        standing = {'%s_%d' % (kind, i): look_at(actor) for i, (kind, actor) in enumerate(group)}
        result['lane_group'] = standing
        feet = [s.get('feet_above_floor_cm') for s in standing.values()]
        check('2_lane_group_stands_on_the_floor', len(group) == len(cast_of) and all(f is not None and -6.0 <= f <= 12.0 for f in feet), feet)
        check('2_lane_group_is_posed_and_not_in_a_wall', all(not s.get('pose_empty') and not s.get('arms_out') and (s.get('walls_within_30cm') or 0) < 3 and s.get('walker')
                                                              for s in standing.values()),
              {k: [s.get('arms_out'), s.get('pose_empty'), s.get('walls_within_30cm')] for k, s in standing.items()})
        check('2_soldier_and_guard_hold_sword_and_shield', all(any('Sword' in h for h in s['holds']) and any('Shield' in h for h in s['holds'])
                                                              for k, s in standing.items() if not k.startswith('Civilian')),
              {k: s['holds'] for k, s in standing.items()})
        await picture('V_lane_before', lane_point(300, 0), unreal.Vector(lane_point(-330).x, lane_point(-330).y, spot.z + 230.0))
        save()

        # ---- 3: a Fireball into them ---------------------------------------------------------------------------
        console('Npc.WalkerPhysics %d' % result['walker_physics'], world)
        before = {actor: (brain(actor).get_locomotion_driver() or actor).get_actor_location() for _, actor in group}
        target = lane_point(300, 0)
        target = unreal.Vector(target.x, target.y, spot.z + 90.0)
        origin = unreal.Transform(location=player.get_actor_location() + unreal.Vector(0, 0, 50), rotation=unreal.Rotator(), scale=unreal.Vector(1, 1, 1))
        controller.set_control_rotation(unreal.MathLibrary.find_look_at_rotation(player.get_actor_location(), target))
        spells.release_spell_at(unreal.HeroSpell.FIRESTORM, origin, target, None)
        track = {i: [] for i in range(len(group))}
        blast_began = time.perf_counter()
        while time.perf_counter() - blast_began < 3.2:
            await asyncio.sleep(0.4)
            for i, (kind, actor) in enumerate(group):
                walker = brain(actor).get_locomotion_driver() or actor
                track[i].append(round(walker.get_velocity().length()))
        after = {}
        for i, (kind, actor) in enumerate(group):
            row = look_at(actor)
            start = before[actor]
            row['thrown_or_ran_cm'] = round(math.hypot(row['at'][0] - start.x, row['at'][1] - start.y))
            row['speeds'] = track[i]
            row['health'] = round(actor.get_component_by_class(unreal.ReflectionsHealthComponent).get_editor_property('health'), 1)
            after['%s_%d' % (kind, i)] = row
        result['after_fireball'] = after
        check('3_the_blast_reached_them', sum(1 for r in after.values() if r['reaction'] != 'CALM') >= 3, {k: [r['reaction'], r['health'], r['thrown_or_ran_cm']] for k, r in after.items()})
        check('3_nobody_in_a_wall_or_under_the_floor_after_it', all((r.get('walls_within_30cm') or 0) < 3 and r.get('feet_above_floor_cm') is not None and r['feet_above_floor_cm'] >= -6.0
                                                                      for r in after.values() if r['reaction'] != 'INCAPACITATED'),
              {k: [r.get('walls_within_30cm'), r.get('feet_above_floor_cm')] for k, r in after.items()})
        runners = {k: r for k, r in after.items() if r['reaction'] == 'FLEEING'}
        check('3_the_frightened_get_away_along_the_lane', all(r['thrown_or_ran_cm'] >= 250 for r in runners.values()) if runners else True,
              {k: [r['thrown_or_ran_cm'], r['speeds']] for k, r in runners.items()} or 'nobody fled')
        save()

        # ---- 4: deaths there ---------------------------------------------------------------------------------------
        victims = [(kind, actor) for kind, actor in group if kind in ('Civilian', 'Soldier')][:3]
        for kind, actor in victims:
            unreal.GameplayStatics.apply_damage(actor, 999.0, None, player, unreal.DamageType)
            await asyncio.sleep(0.3)
        await asyncio.sleep(2.6)
        corpses = {}
        for i, (kind, actor) in enumerate(victims):
            row = look_at(actor)
            body = body_of(actor)
            try:
                physics = body.get_center_of_mass('pelvis')
                floor = floor_under(physics, [actor])
                row['ragdoll_pelvis_above_floor_cm'] = round(physics.z - floor, 1) if floor is not None else None
                near = 0
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    hit = trace(physics, unreal.Vector(physics.x + dx * 60.0, physics.y + dy * 60.0, physics.z), [actor])
                    near += 1 if hit and hit['distance'] < 12.0 else 0
                row['ragdoll_walls_within_12cm'] = near
            except Exception as error:
                row['ragdoll_error'] = repr(error)[:60]
            corpses['%s_%d' % (kind, i)] = row
        result['corpses'] = corpses
        check('4_corpses_keep_their_pose_and_lie_low', all(not r.get('pose_empty') and r.get('reaction') == 'INCAPACITATED' and
                                                           (r.get('ragdoll_pelvis_above_floor_cm') is not None and -10.0 <= r['ragdoll_pelvis_above_floor_cm'] <= 75.0)
                                                           for r in corpses.values()),
              {k: [r.get('pose_empty'), r.get('reaction'), r.get('ragdoll_pelvis_above_floor_cm'), r.get('pelvis_above_floor_cm')] for k, r in corpses.items()})
        check('4_corpses_are_not_inside_a_wall', all((r.get('ragdoll_walls_within_12cm') or 0) < 3 for r in corpses.values()),
              {k: r.get('ragdoll_walls_within_12cm') for k, r in corpses.items()})
        await picture('V_lane_after', lane_point(300, 0), unreal.Vector(lane_point(-330).x, lane_point(-330).y, spot.z + 230.0))
        result['seconds'] = round(time.perf_counter() - began, 1)
    except Exception as error:
        import traceback
        result['error'] = repr(error)
        result['trace'] = traceback.format_exc()[-1800:]
    finally:
        try:
            console('Npc.WalkerPhysics 0')
            console('Npc.Heat 1')
        except Exception:
            pass
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')

try:
    with open(LOG_PATH, 'rb') as handle:
        handle.seek(log_start)
        tail = handle.read().decode('utf-8', errors='replace')
    result['log'] = {'ensures': tail.count('Ensure condition failed'), 'asserts': tail.count('Assertion failed'), 'skinned_asset': tail.count('SkinnedAsset.cpp'),
                     'pose_repairs': tail.count('body bone buffers were incomplete'), 'missing_bones': tail.count('is missing bones'),
                     'locomotion_missing': tail.count('Sample locomotion assets missing'), 'no_look': tail.count('no team look could be loaded'),
                     'accessed_none': tail.count('Accessed None')}
    check('log_clean', all(result['log'][k] == 0 for k in ('ensures', 'asserts', 'skinned_asset', 'missing_bones', 'locomotion_missing', 'no_look')), result['log'])
except Exception as error:
    result['log'] = repr(error)

result['passed'] = sum(1 for c in result['checks'].values() if c['ok'])
result['failed'] = sorted(name for name, c in result['checks'].items() if not c['ok'])
result['ended'] = time.strftime('%H:%M:%S')
save()
json.dumps({'passed': result['passed'], 'failed': result['failed'], 'error': result.get('error'), 'abort': result.get('abort'), 'map': result.get('map')}, default=str)
