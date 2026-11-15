"""Train #14's NPC changes: sword in the fist, shield on the forearm, the held-ready stance, hits that land with
physics, knockdown and get-up. Any map (written for GrayLondon_Geodata), PIE stopped; everything is placed relative
to where the hero stands when PIE starts. Run through the editor MCP `execute_python` tool (top-level `await`,
`call_tool`), in halves: PART = 'A' (weapons and stance, with close-up pictures), 'B' (physics) or 'C' (the stress run: killed in the middle of
a knockdown, of a get-up and of a shock; RUNS = 6 per call starting at FIRST_RUN, so four calls make 24 runs).

  A1  A Gilt soldier and a Frost soldier, 3 s after spawning: each holds a sword whose handle is at the right hand
      (grip point within 9 cm of the hand bone) and whose blade stands across the forearm (60 to 120 degrees), and
      has a shield on the left forearm (within 14 cm of the forearm line) that is this system's, with the outfit's
      own shield and armour hidden. Close-ups of both hands from the front, the side and above.
  A2  The stance: the left hand is held up (recorded: hand heights with the stance on, and after Npc.ArmedStance 0).
  A3  Walking: the Gilt soldier walks to one of the tarnished; pictured mid-walk.
  B1  Npc.WalkerPhysics 1: a Fire Bolt jolts a soldier's upper body (the head moves against the feet) while the
      visible body is never simulated and stays on its animation blueprint.
  B2  Npc.WalkerPhysics 2: a Fireball knocks a soldier down (pelvis near the ground, alive, body not simulated),
      and it is on its feet again within six seconds. Frame strip pictured.
  B3  Killed while lying there, and killed while getting up: ordinary ragdoll deaths.
Result: Saved/NpcUnified/verify_armed_<PART>.json and G*_ pictures. The console variables are put back afterwards.
"""

import base64
import json
import math
import time
from pathlib import Path

OUT = Path(unreal.Paths.project_saved_dir()) / 'NpcUnified'
OUT.mkdir(parents=True, exist_ok=True)
result = {'checks': {}, 'shots': []}
PART = globals().get('PART', 'A')
result['part'] = PART
LOG_PATH = Path(unreal.Paths.project_log_dir()) / 'reflections.log'
try:
    log_start = LOG_PATH.stat().st_size
except OSError:
    log_start = 0


def check(name, ok, detail=None):
    result['checks'][name] = {'ok': bool(ok), 'detail': detail}


def unwrap(value):
    return value['returnValue'] if isinstance(value, dict) and 'returnValue' in value else value


def console(command, world=None):
    unreal.SystemLibrary.execute_console_command(world or unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world(), command)


async def shot(name):
    try:
        capture = unwrap(await call_tool('SceneCaptureToolset.SceneCaptureToolset.CaptureGameViewport',
                                         world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(),
                                         maxResolution=1600))
        data = capture['image'] if isinstance(capture, dict) else None
        if isinstance(data, dict):
            data = data.get('data') or data.get('base64')
        if data:
            if ',' in data[:64]:
                data = data.split(',', 1)[1]
            path = OUT / (name + '.png')
            path.write_bytes(base64.b64decode(data))
            result['shots'].append(str(path))
    except Exception as error:
        result.setdefault('shot_errors', []).append(name + ': ' + repr(error))


def vec(v):
    return [round(v.x, 1), round(v.y, 1), round(v.z, 1)]


def sub(a, b):
    return unreal.Vector(a.x - b.x, a.y - b.y, a.z - b.z)


def dot(a, b):
    return a.x * b.x + a.y * b.y + a.z * b.z


def length(a):
    return math.sqrt(dot(a, a))


def unit(a):
    n = length(a) or 1.0
    return unreal.Vector(a.x / n, a.y / n, a.z / n)


def angle(a, b):
    return round(math.degrees(math.acos(max(-1.0, min(1.0, dot(unit(a), unit(b)))))), 1)


def distance_to_segment(p, a, b):
    ab = sub(b, a)
    t = max(0.0, min(1.0, dot(sub(p, a), ab) / (dot(ab, ab) or 1.0)))
    return round(length(sub(p, unreal.Vector(a.x + ab.x * t, a.y + ab.y * t, a.z + ab.z * t))), 1)


if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
    result['abort'] = 'PIE is already running (someone else is testing); nothing was started.'
else:
    console('Squads.StartPatrol 0')
    if globals().get('VILLAIN_DELAY') is not None:
        # Before play starts: the villain reads this when play goes live (20 s by default, then he takes a host).
        console('Villain.StartDelay %s' % globals()['VILLAIN_DELAY'])
        result['villain_start_delay'] = globals()['VILLAIN_DELAY']
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
        controller = player.get_controller()
        # Team rule (21:27): until the game puts the hero there itself, go to the start tagged 'Lanthorne' (Great
        # Tower St) first, look the way it looks, and give the streamed city a few seconds to arrive.
        starts = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.PlayerStart)
                  if str(a.get_editor_property('player_start_tag')) == 'Lanthorne']
        result['lanthorne_start'] = bool(starts)
        if starts:
            player.set_actor_location(starts[0].get_actor_location(), False, True)
            player.set_actor_rotation(unreal.Rotator(0.0, 0.0, starts[0].get_actor_rotation().yaw), False)
            controller.set_control_rotation(starts[0].get_actor_rotation())
            await asyncio.sleep(4.0)
            for _ in range(20):
                if abs(player.get_velocity().z) < 5.0:
                    break
                await asyncio.sleep(0.3)
            await asyncio.sleep(0.5)
        npcs = unreal.get_world_subsystem(world, unreal.ReflectionsNpcSubsystem)
        # The hero must outlive the test: hostile soldiers hit back, and a dead hero casts nothing (the first run's
        # later Fireballs never left). This PIE session only; no asset is touched.
        hero_health = player.get_component_by_class(unreal.ReflectionsHealthComponent)
        try:
            hero_health.set_editor_property('max_health', 1000000.0)
            hero_health.reset_health()
        except Exception as error:
            result['hero_health_error'] = repr(error)
        spells = player.get_component_by_class(unreal.ReflectionsSpellCombatComponent)
        HERE = player.get_actor_location()
        GROUND = HERE.z - 90.0
        ahead = player.get_actor_forward_vector()
        ahead = unreal.Vector(ahead.x, ahead.y, 0.0).normal()
        side = unreal.Vector(-ahead.y, ahead.x, 0.0)
        result['start'] = {'at': vec(HERE), 'ahead': [round(ahead.x, 2), round(ahead.y, 2)]}

        def at(forward_cm, right_cm=0.0, up_cm=0.0):
            return unreal.Vector(HERE.x + ahead.x * forward_cm + side.x * right_cm, HERE.y + ahead.y * forward_cm + side.y * right_cm, GROUND + up_cm)

        TOWARD_HERO = unreal.MathLibrary.find_look_at_rotation(at(300), unreal.Vector(HERE.x, HERE.y, GROUND)).yaw

        def brain(actor):
            return actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent)

        def health(actor):
            return round(actor.get_component_by_class(unreal.ReflectionsHealthComponent).get_editor_property('health'), 1)

        def body_of(actor):
            return next(m for m in actor.get_components_by_class(unreal.SkeletalMeshComponent) if m.get_name() == 'Body')

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

        def face(point):
            controller.set_control_rotation(unreal.MathLibrary.find_look_at_rotation(player.get_actor_location(), point))

        def aim_point(actor):
            for capsule in actor.get_components_by_class(unreal.CapsuleComponent):
                if capsule.get_name() == 'RuntimeNpcHitProxy':
                    return capsule.get_world_location()
            return actor.get_actor_location() + unreal.Vector(0, 0, 100)

        def cast(spell, actor):
            point = aim_point(actor)
            face(point)
            origin = unreal.Transform(location=player.get_actor_location() + unreal.Vector(0, 0, 50), rotation=unreal.Rotator(), scale=unreal.Vector(1, 1, 1))
            spells.release_spell_at(spell, origin, point, None)

        def walker_simulating(actor):
            try:
                walker = brain(actor).get_locomotion_driver()
                return bool(walker and walker.get_editor_property('mesh').is_any_simulating_physics())
            except Exception:
                return None

        def pose_empty(actor):
            """True when the visible body has lost its pose buffer: the engine then answers every bone lookup with the
            identity transform, the world's origin exactly (SkinnedMeshComponent.cpp, GetBoneTransform). This is the
            state behind the editor crashes; it is not a body lying at height zero."""
            try:
                where = body_of(actor).get_socket_location('pelvis')
                return where.x == 0.0 and where.y == 0.0 and where.z == 0.0
            except Exception:
                return None

        def pelvis_height(actor):
            try:
                where = body_of(actor).get_socket_location('pelvis')
                if where.x == 0.0 and where.y == 0.0 and where.z == 0.0:
                    return None                              # no pose to read (see pose_empty)
                return round(where.z - GROUND, 1)
            except Exception:
                return None

        # A camera of its own for close-ups (the game view has the hero in the way).
        # (Rendered offscreen by the editor's capture tool from a camera given as numbers: nothing is spawned.)
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
                if not data:
                    raise RuntimeError('no image: ' + repr(capture)[:160])
                if ',' in data[:64]:
                    data = data.split(',', 1)[1]
                (OUT / (name + '.png')).write_bytes(base64.b64decode(data))
                result['shots'].append(str(OUT / (name + '.png')))
            except Exception as error:
                result.setdefault('shot_errors', []).append(name + ': ' + repr(error)[:200])

        def kit(actor):
            body = body_of(actor)
            forearm_r = sub(body.get_socket_location('hand_r'), body.get_socket_location('lowerarm_r'))
            out = {'class': actor.get_class().get_name(), 'props': []}
            for part in actor.get_components_by_class(unreal.StaticMeshComponent):
                mesh = part.get_editor_property('static_mesh')
                if not mesh:
                    continue
                place = part.get_world_location()
                rotation = part.get_world_rotation()
                x_axis = unreal.MathLibrary.get_forward_vector(rotation)
                row = {'mesh': mesh.get_name(), 'bone': str(part.get_attach_socket_name()), 'tags': [str(t) for t in part.component_tags],
                       'material': part.get_material(0).get_name() if part.get_material(0) else None}
                if 'Sword' in row['mesh']:
                    grip = unreal.Vector(place.x - x_axis.x * 5.5, place.y - x_axis.y * 5.5, place.z - x_axis.z * 5.5)
                    row['grip_to_hand_cm'] = round(length(sub(grip, body.get_socket_location('hand_r'))), 1)
                    row['blade_to_forearm_deg'] = angle(x_axis, forearm_r)
                    row['blade_points'] = vec(x_axis)
                if 'Shield' in row['mesh']:
                    row['to_forearm_line_cm'] = distance_to_segment(place, body.get_socket_location('lowerarm_l'), body.get_socket_location('hand_l'))
                    row['face_points'] = vec(x_axis)
                    row['face_vs_actor_forward_deg'] = angle(x_axis, actor.get_actor_forward_vector())
                out['props'].append(row)
            out['look_parts_hidden'] = sorted(part.get_name() for part in actor.get_components_by_class(unreal.SkeletalMeshComponent)
                                              if ('Armor' in part.get_name() or 'Shield' in part.get_name()) and part.get_editor_property('hidden_in_game'))
            out['look_parts_shown'] = sorted(part.get_name() for part in actor.get_components_by_class(unreal.SkeletalMeshComponent)
                                             if ('Armor' in part.get_name() or 'Shield' in part.get_name()) and not part.get_editor_property('hidden_in_game'))
            out['hand_l_height'] = round(body.get_socket_location('hand_l').z - GROUND, 1)
            out['hand_r_height'] = round(body.get_socket_location('hand_r').z - GROUND, 1)
            return out

        async def pictures(prefix, actor):
            body = body_of(actor)
            forward = actor.get_actor_forward_vector()
            right = actor.get_actor_right_vector()
            for label, bone in (('sword_hand', 'hand_r'), ('shield_arm', 'lowerarm_l')):
                p = body.get_socket_location(bone)
                await close_up('%s_%s_front' % (prefix, label), p, unreal.Vector(p.x + forward.x * 75, p.y + forward.y * 75, p.z + 10))
                sign = 1.0 if bone.endswith('_r') else -1.0
                await close_up('%s_%s_side' % (prefix, label), p, unreal.Vector(p.x + right.x * 75 * sign, p.y + right.y * 75 * sign, p.z + 10))
                await close_up('%s_%s_above' % (prefix, label), p, unreal.Vector(p.x + forward.x * 15, p.y + forward.y * 15, p.z + 80))
            chest = actor.get_actor_location() + unreal.Vector(0, 0, 100)
            await close_up('%s_whole_front' % prefix, chest, unreal.Vector(chest.x + forward.x * 330, chest.y + forward.y * 330, chest.z + 20))
            await close_up('%s_whole_side' % prefix, chest, unreal.Vector(chest.x + right.x * 330, chest.y + right.y * 330, chest.z + 20))

        if 'A' in PART:
            # ---- A1: weapons ------------------------------------------------------------------------------
            gilt = npcs.spawn_npc('AlliedSoldier', at(300, -110), TOWARD_HERO, look_class('GiltSoldier_BridgeGuard'))
            frost = npcs.spawn_npc('Soldier', at(300, 110), TOWARD_HERO, look_class('FrostSoldier_Iven'))
            for posed in (gilt, frost):
                if posed:
                    brain(posed).set_externally_steered(True)
            face(at(300, 0, 100))
            await asyncio.sleep(3.2)
            result['A1'] = {}
            for name, actor in (('gilt', gilt), ('frost', frost)):
                if not actor:
                    result['A1'][name] = None
                    continue
                result['A1'][name] = kit(actor)
                await pictures('G_' + name + '_idle', actor)
            ok = True
            for name in ('gilt', 'frost'):
                row = result['A1'].get(name)
                swords = [p for p in (row or {}).get('props', []) if 'Sword' in p['mesh']]
                shields = [p for p in (row or {}).get('props', []) if 'Shield' in p['mesh']]
                good = bool(swords) and swords[0]['grip_to_hand_cm'] <= 9.0 and 60.0 <= swords[0]['blade_to_forearm_deg'] <= 120.0
                good = good and bool(shields) and shields[0]['to_forearm_line_cm'] <= 14.0 and not (row or {}).get('look_parts_shown')
                ok = ok and good
            check('A1_sword_in_the_hand_and_shield_on_the_forearm', ok, result['A1'])
            await shot('G_both_idle_game_view')

            # ---- A2: the stance on and off ---------------------------------------------------------------
            on = {name: [result['A1'][name]['hand_l_height'], result['A1'][name]['hand_r_height']] for name in ('gilt', 'frost') if result['A1'].get(name)}
            console('Npc.ArmedStance 0', world)
            await asyncio.sleep(1.2)
            off = {name: [kit(actor)['hand_l_height'], kit(actor)['hand_r_height']] for name, actor in (('gilt', gilt), ('frost', frost)) if actor}
            console('Npc.ArmedStance 1', world)
            result['A2'] = {'hands_left_right_with_stance': on, 'without': off,
                            'hold_clip_on_disk': unreal.EditorAssetLibrary.does_asset_exist('/Game/NPC/Anim/AS_Npc_ArmedHold_Add_Walker') if False else None}
            check('A2_stance_raises_the_shield_hand', all(on[n][0] - off[n][0] >= 8.0 for n in on), result['A2'])

            # ---- A3: walking --------------------------------------------------------------------------------
            if gilt:
                brain(gilt).set_externally_steered(False)
                foe = npcs.spawn_npc('Civilian', at(1150, -110), TOWARD_HERO, None)
                await asyncio.sleep(1.3)
                npcs.set_infection(foe, unreal.ReflectionsNpcInfection.INFECTED, None)
                moved = 0.0
                start = gilt.get_actor_location()
                for step in range(14):
                    await asyncio.sleep(0.25)
                    moved = length(sub(gilt.get_actor_location(), start))
                    if moved > 150.0:
                        break
                result['A3'] = {'walked_cm': round(moved), 'walking': kit(gilt)}
                await pictures('G_gilt_walking', gilt)
                await shot('G_gilt_walking_game_view')
                check('A3_walks_with_the_shield_hand_still_up', moved > 100.0 and (result['A3']['walking']['hand_l_height'] - off.get('gilt', [0])[0]) >= 5.0, result['A3'])
                for actor in (foe,):
                    unreal.GameplayStatics.apply_damage(actor, 999.0, None, None, unreal.DamageType)

        if 'B' in PART:
            SPOT = at(260)

            async def fresh_soldier():
                actor = npcs.spawn_npc('Soldier', SPOT, TOWARD_HERO, look_class('FrostSoldier_Iven'))
                await asyncio.sleep(1.4)
                return actor

            def head_lean(actor):
                """How far the visible body's head is from the point above its pelvis, flat, in cm."""
                body = body_of(actor)
                h = body.get_socket_location('head')
                p = body.get_socket_location('pelvis')
                return round(math.hypot(h.x - p.x, h.y - p.y), 1)

            # ---- B1: the jolt -------------------------------------------------------------------------------
            leans = {}
            for level in (0, 1):
                console('Npc.WalkerPhysics %d' % level, world)
                soldier = await fresh_soldier()
                rest = head_lean(soldier)
                cast(unreal.HeroSpell.FIRE, soldier)
                peak = rest
                modes = set()
                simulated = False
                began = time.perf_counter()
                while time.perf_counter() - began < 1.1:
                    await asyncio.sleep(0.03)
                    peak = max(peak, head_lean(soldier))
                    modes.add(body_of(soldier).get_editor_property('animation_mode').name)
                    simulated = simulated or body_of(soldier).is_any_simulating_physics()
                leans[level] = {'rest': rest, 'peak': peak, 'health': health(soldier), 'modes': sorted(modes), 'body_simulated': simulated}
                unreal.GameplayStatics.apply_damage(soldier, 999.0, None, None, unreal.DamageType)
                await asyncio.sleep(0.3)
            result['B1'] = leans
            check('B1_a_fire_bolt_jolts_the_upper_body', leans[1]['peak'] - leans[1]['rest'] >= (leans[0]['peak'] - leans[0]['rest']) + 3.0, leans)
            check('B1_the_visible_body_is_never_simulated', not leans[1]['body_simulated'] and all('BLUEPRINT' in m for m in leans[1]['modes']), leans[1])

            # ---- B2: knockdown and get-up ---------------------------------------------------------------------
            console('Npc.WalkerPhysics 2', world)
            soldier = await fresh_soldier()
            cast(unreal.HeroSpell.FIRESTORM, soldier)
            strip = []
            lowest = 999.0
            down_at = None
            up_at = None
            simulated = False
            began = time.perf_counter()
            frame = 0
            while time.perf_counter() - began < 7.5:
                await asyncio.sleep(0.1)
                t = round(time.perf_counter() - began, 1)
                h = pelvis_height(soldier)
                simulated = simulated or (body_of(soldier).is_any_simulating_physics() and brain(soldier).get_editor_property('reaction').name != 'INCAPACITATED')
                if h is not None:
                    lowest = min(lowest, h)
                    if h < 45.0 and down_at is None:
                        down_at = t
                    if down_at is not None and up_at is None and h > 75.0 and t - down_at > 1.0:
                        up_at = t
                strip.append([t, h])
                if frame in (6, 14, 24, 36, 46, 56) :
                    chest = soldier.get_actor_location() + unreal.Vector(0, 0, 60)
                    await close_up('G_knockdown_%02d' % frame, chest, unreal.Vector(chest.x + side.x * 420, chest.y + side.y * 420, chest.z + 120))
                frame += 1
                if up_at is not None and t - up_at > 0.8:
                    break
            result['B2'] = {'pelvis_lowest_cm': lowest, 'down_at_s': down_at, 'up_at_s': up_at, 'health': health(soldier),
                            'reaction': brain(soldier).get_editor_property('reaction').name, 'body_simulated_alive': simulated, 'strip': strip[::4]}
            check('B2_fireball_knocks_it_down', down_at is not None and health(soldier) > 0 and not simulated, result['B2'])
            check('B2_it_gets_up_again', up_at is not None and up_at <= 7.0, result['B2'])
            unreal.GameplayStatics.apply_damage(soldier, 999.0, None, None, unreal.DamageType)
            await asyncio.sleep(0.3)

            # ---- B3: killed while down, and while getting up ---------------------------------------------------
            deaths = {}
            for label, kill_when in (('while_down', 'down'), ('while_rising', 'rising')):
                soldier = await fresh_soldier()
                cast(unreal.HeroSpell.FIRESTORM, soldier)
                began = time.perf_counter()
                was_down = False
                killed_at = None
                while time.perf_counter() - began < 7.0:
                    await asyncio.sleep(0.05)
                    h = pelvis_height(soldier) or 999.0
                    was_down = was_down or h < 45.0
                    t = time.perf_counter() - began
                    if (kill_when == 'down' and was_down and t > 1.6) or (kill_when == 'rising' and was_down and h > 55.0 and t > 2.5):
                        unreal.GameplayStatics.apply_damage(soldier, 999.0, None, player, unreal.DamageType)
                        killed_at = round(t, 2)
                        break
                await asyncio.sleep(1.5)
                body = body_of(soldier)
                deaths[label] = {'was_down': was_down, 'killed_at_s': killed_at, 'reaction': brain(soldier).get_editor_property('reaction').name,
                                 'body_simulating': body.is_any_simulating_physics(), 'walker_simulating': walker_simulating(soldier),
                                 'pelvis': pelvis_height(soldier)}
            result['B3'] = deaths
            check('B3_killed_while_down_or_rising_lies_dead',
                  all(d['killed_at_s'] is not None and d['reaction'] == 'INCAPACITATED' and (d['body_simulating'] or d['walker_simulating'])
                      and (d['pelvis'] or 999.0) < 60.0 for d in deaths.values()), deaths)

        if 'C' in PART:
            # ---- C: killed at the worst moments, over and over (the orchestrator's 20 runs) -------------------
            # RUNS of them per call (default 6, about 35 s of PIE), starting at FIRST_RUN; the results of calls
            # with FIRST_RUN > 0 are added to the file. Kinds in turn: killed in the air or on the ground of a
            # knockdown, killed while getting up, killed while the current runs through it.
            console('Npc.WalkerPhysics 2', world)
            runs = []
            corpses = []
            first_run = int(globals().get('FIRST_RUN', 0))
            for index in range(first_run, first_run + int(globals().get('RUNS', 6))):
                kind = ('mid_knockdown', 'mid_get_up', 'mid_convulse')[index % 3]
                spot = at(260, (index % 6 - 2.5) * 130.0)
                # A Frost soldier in its set look, then a Gilt guard in whatever look the pool gives, in turn.
                if index % 2 == 0:
                    actor = npcs.spawn_npc('Soldier', spot, TOWARD_HERO, look_class('FrostSoldier_Iven'))
                else:
                    actor = npcs.spawn_npc('Guard', spot, TOWARD_HERO, None)
                await asyncio.sleep(1.2)
                before = health(actor)
                cast(unreal.HeroSpell.LIGHTNING_BOLT if kind == 'mid_convulse' else unreal.HeroSpell.FIRESTORM, actor)
                began = time.perf_counter()
                was_down = False
                killed_at = None
                while time.perf_counter() - began < 6.5:
                    await asyncio.sleep(0.05)
                    t = time.perf_counter() - began
                    h = pelvis_height(actor) or 999.0
                    was_down = was_down or h < 45.0
                    if brain(actor).get_editor_property('reaction').name == 'INCAPACITATED':
                        break                                    # the spell itself killed it
                    if ((kind == 'mid_knockdown' and t > 0.5 + 0.1 * (index % 5)) or
                            (kind == 'mid_get_up' and was_down and h > 50.0 and t > 2.2) or
                            (kind == 'mid_convulse' and t > 0.5 + 0.1 * (index % 4))):
                        unreal.GameplayStatics.apply_damage(actor, 999.0, None, player, unreal.DamageType)
                        killed_at = round(t, 2)
                        break
                await asyncio.sleep(0.8)
                runs.append({'run': index, 'kind': kind, 'archetype': 'Soldier' if index % 2 == 0 else 'Guard', 'health_before': before,
                             'was_down': was_down, 'killed_at_s': killed_at, 'reaction': brain(actor).get_editor_property('reaction').name,
                             'body_simulating': body_of(actor).is_any_simulating_physics(), 'walker_simulating': walker_simulating(actor),
                             'pelvis': pelvis_height(actor), 'pose_empty': pose_empty(actor)})
                corpses.append(actor)
            for record, corpse in zip(runs, corpses):
                record['pelvis_at_end'] = pelvis_height(corpse)
                record['pose_empty_at_end'] = pose_empty(corpse)
            result['C_runs'] = runs
    except Exception as error:
        import traceback
        result['error'] = repr(error)
        result['trace'] = traceback.format_exc()[-1500:]
    finally:
        try:
            result['hero_at_end'] = {'health': hero_health.get_editor_property('health'), 'paused': unreal.GameplayStatics.is_game_paused(world),
                                     'same_pawn': unreal.GameplayStatics.get_player_pawn(world, 0) == player}
        except Exception as error:
            result['hero_at_end'] = repr(error)
        try:
            console('Npc.WalkerPhysics %d' % int(globals().get('WALKER_PHYSICS_AFTER', 0)))
            console('Npc.ArmedStance 1')
        except Exception:
            pass
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')
        console('Squads.StartPatrol 1')
        if globals().get('VILLAIN_DELAY') is not None:
            console('Villain.StartDelay 20')

try:
    with open(LOG_PATH, 'rb') as handle:
        handle.seek(log_start)
        tail = handle.read().decode('utf-8', errors='replace')
    result['log'] = {'pose_repairs': tail.count('body bone buffers were incomplete'), 'pose_not_ready': tail.count('body pose not ready'),
                     'bone_out_of_range': tail.count('GetBoneMatrix : BoneIndex'), 'ensures': tail.count('Ensure condition failed'),
                     'accessed_none': tail.count('Accessed None'), 'skinned_asset': tail.count('SkinnedAsset.cpp'),
                     'hosts_taken': tail.count('LogReflectionsGameFlow: Infected:'),
                     'asserts': tail.count('Assertion failed')}
    check('log_no_empty_pose', result['log']['bone_out_of_range'] == 0 and result['log']['pose_not_ready'] == 0
          and result['log']['pose_repairs'] == 0 and result['log']['skinned_asset'] == 0 and result['log']['asserts'] == 0, result['log'])
except Exception as error:
    result['log'] = repr(error)

if 'C_runs' in result:
    # Later calls add their runs (and their log counts) to the earlier ones.
    previous = OUT / 'verify_armed_C.json'
    if int(globals().get('FIRST_RUN', 0)) > 0 and previous.exists():
        try:
            earlier = json.loads(previous.read_text())
            result['C_runs'] = earlier.get('C_runs', []) + result['C_runs']
            if isinstance(result.get('log'), dict) and isinstance(earlier.get('log'), dict):
                result['log'] = {key: value + earlier['log'].get(key, 0) for key, value in result['log'].items()}
        except Exception as error:
            result['merge_error'] = repr(error)
    runs = result['C_runs']
    exercised = [r for r in runs if r['killed_at_s'] is not None]
    result['C_summary'] = {'runs': len(runs), 'killed_by_the_check': len(exercised),
                           'killed_by_the_spell': sum(1 for r in runs if r['killed_at_s'] is None and r['reaction'] == 'INCAPACITATED'),
                           'by_kind': {k: sum(1 for r in exercised if r['kind'] == k) for k in ('mid_knockdown', 'mid_get_up', 'mid_convulse')},
                           'knocked_down': sum(1 for r in runs if r['was_down'])}
    # Dead and limp on the ground either way: as its own ragdoll (an ordinary death), or, from train #20, as the hidden
    # walker's ragdoll when it was killed while down or rising (then the visible body is never simulated).
    wrong = [r for r in exercised if not (r['reaction'] == 'INCAPACITATED' and (r['body_simulating'] or r.get('walker_simulating')))]
    result['C_summary']['lying_as_the_walker'] = sum(1 for r in exercised if r.get('walker_simulating') and not r['body_simulating'])
    check('C_every_one_killed_this_way_lies_dead', bool(exercised) and not wrong, wrong or result['C_summary'])
    result['C_summary']['corpses_without_a_pose'] = sum(1 for r in runs if r.get('pose_empty') or r.get('pose_empty_at_end'))
    check('C_no_corpse_lost_its_pose', result['C_summary']['corpses_without_a_pose'] == 0,
          [r['run'] for r in runs if r.get('pose_empty') or r.get('pose_empty_at_end')])
    if isinstance(result.get('log'), dict):
        check('C_no_asserts_or_pose_warnings',
              all(result['log'].get(k, 0) == 0 for k in ('pose_repairs', 'pose_not_ready', 'bone_out_of_range', 'skinned_asset', 'asserts')), result['log'])

result['passed'] = sum(1 for c in result['checks'].values() if c['ok'])
result['failed'] = sorted(name for name, c in result['checks'].items() if not c['ok'])
(OUT / ('verify_armed_%s.json' % PART)).write_text(json.dumps(result, indent=2, default=str))
json.dumps(result, default=str)
