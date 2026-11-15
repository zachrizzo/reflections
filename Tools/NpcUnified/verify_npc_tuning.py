"""Train #13's NPC changes: shorter throws, no arms-out pose on a fresh spawn, Pewterside's own looks, the allied
caster. Any map (written for GrayLondon_Geodata), PIE stopped. Everything is placed relative to where the hero
stands when PIE starts, on the ground at the hero's feet, so it needs a few metres of open ground ahead. One PIE session, about 35 seconds; it always stops PIE. Run through the
editor MCP `execute_python` tool (top-level `await`, `call_tool`). Run it AFTER the archetype assets were re-synced
on the new build (the look pools and the allied caster come from there).

  U0  One look for each of the five bodies that shared the skeleton saved without its root bone at 19:28 (and
      one that never did, as the control): two and a half seconds after the spawn their arms are down, not out.
  U7  Soldiers are armed and unarmoured: a Frost soldier on the IvenRook body holds a sword and has a shield on
      the left forearm; a guard on the BridgeGuard body keeps its own shield, holds a sword, and its armour part
      is hidden. Pictured from the front.
  U1  A townsperson spawned alone: while it is shown, its visible body's hand is never out at reference-pose
      distance (arms held out). Sampled every frame-ish from the spawn.
  U2  Six spawned at once: the same.
  U3  Fireball on a soldier from 2.6 m: thrown between 2 and 6 m (it was 9.7 m).
  U4  Water Orb on a soldier: shoved between 1 and 4 m (it was 6.7 m).
  U5  Look pools: Pewterside townspeople and guards are PewLook_*, Giltside and Frostside pools hold none of them.
  U6  AlliedSoldierCaster spawns, is on the player's side (Guard disposition), and holds the wand.
Result: Saved/NpcUnified/verify_tuning.json and U*_ pictures.
"""

import base64
import json
import time
from pathlib import Path

OUT = Path(unreal.Paths.project_saved_dir()) / 'NpcUnified'
OUT.mkdir(parents=True, exist_ok=True)
result = {'checks': {}, 'shots': []}
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


open_map = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world().get_name()
if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
    result['abort'] = 'PIE is already running (someone else is testing); nothing was started.'
else:
    console('Squads.StartPatrol 0')
    await call_tool('EditorToolset.EditorAppToolset.StartPIE')
    try:
        result['map'] = open_map
        world = None
        player = None
        for _ in range(40):
            # A streamed city takes a while to put the hero down: wait for a pawn that has stopped falling.
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
        spells = player.get_component_by_class(unreal.ReflectionsSpellCombatComponent)
        HERE = player.get_actor_location()
        GROUND = HERE.z - 90.0
        ahead = player.get_actor_forward_vector()
        ahead = unreal.Vector(ahead.x, ahead.y, 0.0).normal()
        side = unreal.Vector(-ahead.y, ahead.x, 0.0)
        result['start'] = {'x': round(HERE.x), 'y': round(HERE.y), 'z': round(HERE.z), 'ahead': [round(ahead.x, 2), round(ahead.y, 2)]}

        def at(forward_cm, right_cm=0.0, up_cm=0.0):
            """A point on the ground relative to where the hero started: so far ahead, so far to its right."""
            return unreal.Vector(HERE.x + ahead.x * forward_cm + side.x * right_cm, HERE.y + ahead.y * forward_cm + side.y * right_cm, GROUND + up_cm)

        TOWARD_HERO = unreal.MathLibrary.find_look_at_rotation(at(300), unreal.Vector(HERE.x, HERE.y, GROUND)).yaw
        SPOT = at(260)

        def brain(actor):
            return actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent)

        def health(actor):
            return round(actor.get_component_by_class(unreal.ReflectionsHealthComponent).get_editor_property('health'), 1)

        def body_of(actor):
            return next(m for m in actor.get_components_by_class(unreal.SkeletalMeshComponent) if m.get_name() == 'Body')

        def hand_out(actor):
            """How far the visible body's right hand is from the actor's upright axis, in cm (arms out: 50 or more)."""
            delta = body_of(actor).get_socket_location('hand_r') - actor.get_actor_location()
            return round(unreal.Vector(delta.x, delta.y, 0).length())

        def aim_point(actor):
            for capsule in actor.get_components_by_class(unreal.CapsuleComponent):
                if capsule.get_name() == 'RuntimeNpcHitProxy':
                    return capsule.get_world_location()
            return actor.get_actor_location() + unreal.Vector(0, 0, 100)

        def cast(spell, actor):
            point = aim_point(actor)
            controller.set_control_rotation(unreal.MathLibrary.find_look_at_rotation(player.get_actor_location(), point))
            origin = unreal.Transform(location=player.get_actor_location() + unreal.Vector(0, 0, 50), rotation=unreal.Rotator(), scale=unreal.Vector(1, 1, 1))
            spells.release_spell_at(spell, origin, point, None)

        def place(actor):
            walker = brain(actor).get_locomotion_driver()
            where = (walker or actor).get_actor_location()
            return where

        async def watch_spawn(actors, seconds):
            """Per actor: [time, hidden, hand distance] several times a second from the spawn on."""
            began = time.perf_counter()
            rows = {actor.get_name(): [] for actor in actors}
            while time.perf_counter() - began < seconds:
                await asyncio.sleep(0.05)
                for actor in actors:
                    try:
                        rows[actor.get_name()].append([round(time.perf_counter() - began, 2), bool(actor.get_editor_property('hidden')), hand_out(actor)])
                    except Exception as error:
                        rows[actor.get_name()].append([round(time.perf_counter() - began, 2), None, repr(error)[:50]])
            return rows

        def judge(rows):
            """Worst hand distance while shown, when it was first shown, and the hand distance at rest at the end."""
            out = {}
            for name, samples in rows.items():
                shown = [s for s in samples if s[1] is False and isinstance(s[2], int)]
                out[name] = {'samples': len(samples), 'first_shown_at': shown[0][0] if shown else None,
                             'worst_hand_while_shown': max((s[2] for s in shown), default=None),
                             'hand_at_end': shown[-1][2] if shown else None,
                             'hidden_samples': sum(1 for s in samples if s[1] is True)}
            return out

        def look_class(look_id):
            path = '/Game/Characters/Lanthorne/Looks/BP_Look_%s.BP_Look_%s_C' % (look_id, look_id)
            try:
                return unreal.load_object(None, path)
            except Exception:
                return None

        def face(point, yaw_offset=0.0):
            rotation = unreal.MathLibrary.find_look_at_rotation(player.get_actor_location(), point)
            rotation.yaw += yaw_offset
            controller.set_control_rotation(rotation)

        # Two halves, so that one editor call never runs longer than about 40 s: PART = 'A', 'B' or 'AB'.
        PART = globals().get('PART', 'AB')
        result['part'] = PART
        if 'A' in PART:
            # ---- U0: the bodies that stood arms-out ---------------------------------------------------------
            face(at(900, 0, 100))
            bodies = [('BridgeGuard', 'GiltBridgeGuard'), ('GlassArtisan', 'GiltGlassman'), ('ArchiveApprentice', 'GiltArchivist'),
                      ('FestivalDrummer', 'GiltDrummer'), ('FerryPilot', 'GiltFerryman'), ('CoinClerk (control)', 'GiltCoinClerk')]
            stood = {}
            for index, (body_name, look_id) in enumerate(bodies):
                cls = look_class(look_id)
                actor = npcs.spawn_npc('Civilian', at(850, (index - 2.5) * 180), TOWARD_HERO, cls) if cls else None
                stood[body_name] = {'look': look_id, 'actor': actor}
            await asyncio.sleep(2.6)
            await shot('U0_the_five_bodies')
            result['U0'] = {}
            for body_name, row in stood.items():
                actor = row['actor']
                if not actor:
                    result['U0'][body_name] = {'look': row['look'], 'spawned': False}
                    continue
                first = hand_out(actor)
                await asyncio.sleep(0.25)
                result['U0'][body_name] = {'look': row['look'], 'spawned': True, 'hand_out_cm': [first, hand_out(actor)],
                                           'walker': bool(brain(actor).get_locomotion_driver())}
            check('U0_the_five_bodies_have_their_arms_down', all(v.get('spawned') and max(v['hand_out_cm']) < 46 for v in result['U0'].values()), result['U0'])
            for row in stood.values():
                if row['actor']:
                    unreal.GameplayStatics.apply_damage(row['actor'], 999.0, None, None, unreal.DamageType)

            # ---- U7: armed and unarmoured -------------------------------------------------------------------

            def kit(actor):
                props = []
                for part in actor.get_components_by_class(unreal.StaticMeshComponent):
                    mesh = part.get_editor_property('static_mesh')
                    if mesh:
                        props.append({'mesh': mesh.get_name(), 'bone': str(part.get_attach_socket_name()),
                                      'material': part.get_material(0).get_name() if part.get_material(0) else None})
                armour = [{'part': part.get_name(), 'hidden': bool(part.get_editor_property('hidden_in_game'))}
                          for part in actor.get_components_by_class(unreal.SkeletalMeshComponent) if 'Armor' in part.get_name()]
                own_shield = [part.get_name() for part in actor.get_components_by_class(unreal.SkeletalMeshComponent) if 'Shield' in part.get_name()]
                return {'class': actor.get_class().get_name(), 'props': props, 'armour_parts': armour, 'shield_part_of_the_look': own_shield}

            soldier = npcs.spawn_npc('Soldier', at(280, -110), TOWARD_HERO, look_class('FrostIven'))
            guard = npcs.spawn_npc('Guard', at(280, 110), TOWARD_HERO, look_class('GiltBridgeGuard'))
            await asyncio.sleep(2.2)
            result['U7'] = {'frost_soldier': kit(soldier) if soldier else None, 'gilt_guard': kit(guard) if guard else None}
            if soldier and guard:
                fs, gg = result['U7']['frost_soldier'], result['U7']['gilt_guard']
                check('U7_frost_soldier_holds_sword_and_shield', any('Sword' in p['mesh'] and p['bone'] in ('hand_r', 'weapon_r') for p in fs['props'])
                      and any('Shield' in p['mesh'] and p['bone'] == 'lowerarm_l' for p in fs['props']), fs)
                check('U7_frost_shield_is_not_red', all('Giltside' not in (p['material'] or '') for p in fs['props'] if 'Shield' in p['mesh']), fs)
                check('U7_gilt_guard_keeps_its_own_shield_and_has_a_sword', bool(gg['shield_part_of_the_look']) and not any('Shield' in p['mesh'] for p in gg['props'])
                      and any('Sword' in p['mesh'] for p in gg['props']), gg)
                check('U7_armour_is_hidden', all(a['hidden'] for a in gg['armour_parts']), gg['armour_parts'])
                face(at(280, 0, 100), 0.0)
                await asyncio.sleep(0.3)
                await shot('U7_soldier_and_guard_armed')
                for actor in (soldier, guard):
                    unreal.GameplayStatics.apply_damage(actor, 999.0, None, None, unreal.DamageType)
                await asyncio.sleep(0.3)
            else:
                check('U7_frost_soldier_holds_sword_and_shield', False, 'could not spawn the two looks')

            controller.set_control_rotation(unreal.MathLibrary.find_look_at_rotation(HERE, SPOT + unreal.Vector(0, 0, 100)))

            # ---- U1: one fresh townsperson -------------------------------------------------------------
            one = npcs.spawn_npc('Civilian', SPOT, TOWARD_HERO, None)
            result['U1'] = judge(await watch_spawn([one], 2.2))
            worst = [v['worst_hand_while_shown'] for v in result['U1'].values()]
            check('U1_fresh_spawn_is_never_shown_with_its_arms_out', all(w is not None and w < 46 for w in worst), result['U1'])
            unreal.GameplayStatics.apply_damage(one, 999.0, None, None, unreal.DamageType)

            # ---- U2: six at once -------------------------------------------------------------------------
            face(at(1050, 0, 100))
            crowd = [npcs.spawn_npc('Civilian', at(1050, (i - 2.5) * 160), TOWARD_HERO, None) for i in range(6)]
            crowd = [actor for actor in crowd if actor]
            await asyncio.sleep(0.15)
            await shot('U2_six_just_spawned')
            result['U2'] = judge(await watch_spawn(crowd, 2.4))
            worst = [v['worst_hand_while_shown'] for v in result['U2'].values()]
            check('U2_six_at_once_are_never_shown_with_their_arms_out', len(worst) == 6 and all(w is not None and w < 46 for w in worst), result['U2'])
            await shot('U2_six_after_two_seconds')
            for actor in crowd:
                unreal.GameplayStatics.apply_damage(actor, 999.0, None, None, unreal.DamageType)

        if 'B' in PART:
            # ---- U3, U4: throws ------------------------------------------------------------------------------
            distances = {}
            for label, spell in (('U3', unreal.HeroSpell.FIRESTORM), ('U4', unreal.HeroSpell.WATER_ORB)):
                soldier = npcs.spawn_npc('Soldier', SPOT, TOWARD_HERO, None)
                await asyncio.sleep(1.3)
                start = place(soldier)
                before = health(soldier)
                cast(spell, soldier)
                far = 0.0
                high = 0.0
                began = time.perf_counter()
                while time.perf_counter() - began < 1.6:
                    await asyncio.sleep(0.05)
                    now = place(soldier)
                    far = max(far, (now.x - start.x) * ahead.x + (now.y - start.y) * ahead.y)
                    high = max(high, now.z - start.z)
                distances[label] = {'thrown_cm': round(far), 'rose_cm': round(high), 'health': [before, health(soldier)],
                                    'simulating': body_of(soldier).is_any_simulating_physics()}
                unreal.GameplayStatics.apply_damage(soldier, 999.0, None, None, unreal.DamageType)
                await asyncio.sleep(0.3)
            result['U3'] = distances['U3']
            result['U4'] = distances['U4']
            check('U3_fireball_throws_2_to_6_m', distances['U3']['health'][1] < distances['U3']['health'][0] and 200 <= distances['U3']['thrown_cm'] <= 600, distances['U3'])
            check('U4_water_orb_shoves_1_to_4_m', distances['U4']['health'][1] < distances['U4']['health'][0] and 100 <= distances['U4']['thrown_cm'] <= 400, distances['U4'])

            # ---- U5: look pools by side --------------------------------------------------------------------------
            def pool(archetype_id, side):
                names = []
                for look in npcs.get_looks_for_side(archetype_id, side):
                    text = str(look.get_path_name()) if hasattr(look, 'get_path_name') else str(look)
                    names.append(text.rsplit('.', 1)[-1].replace("'", '').replace('>', ''))
                return names

            pools = {key: pool(*key.split('@')) for key in ('Civilian@Pewterside', 'Guard@Pewterside', 'Civilian@Giltside', 'Civilian@Frostside', 'Guard@Giltside')}
            result['U5'] = pools
            check('U5_pewterside_wears_its_own_looks', pools['Civilian@Pewterside'] and all('PewLook' in n for n in pools['Civilian@Pewterside'] + pools['Guard@Pewterside']) and pools['Guard@Pewterside'], pools)
            check('U5_no_grey_looks_on_the_other_sides', not any('PewLook' in n for key in ('Civilian@Giltside', 'Civilian@Frostside', 'Guard@Giltside') for n in pools[key]), pools)

            # ---- U6: the allied caster -----------------------------------------------------------------------------
            caster = npcs.spawn_npc('AlliedSoldierCaster', SPOT, TOWARD_HERO, None)
            await asyncio.sleep(1.6)
            if caster:
                props = [part.get_editor_property('static_mesh').get_name() for part in caster.get_components_by_class(unreal.StaticMeshComponent) if part.get_editor_property('static_mesh')]
                result['U6'] = {'class': caster.get_class().get_name(), 'archetype': str(brain(caster).get_active_archetype().get_editor_property('archetype_id')),
                                'hostile_to_player': npcs.is_hostile_to_player(caster), 'props': props, 'health': health(caster)}
                check('U6_allied_caster_is_friendly_and_holds_a_wand', result['U6']['archetype'] == 'AlliedSoldierCaster' and not result['U6']['hostile_to_player']
                      and any('Wand' in p for p in props), result['U6'])
                controller.set_control_rotation(unreal.MathLibrary.find_look_at_rotation(player.get_actor_location(), caster.get_actor_location() + unreal.Vector(0, 0, 105)))
                await asyncio.sleep(0.2)
                await shot('U6_allied_caster')
            else:
                result['U6'] = 'no AlliedSoldierCaster in this build'
                check('U6_allied_caster_is_friendly_and_holds_a_wand', False, result['U6'])
    except Exception as error:
        import traceback
        result['error'] = repr(error)
        result['trace'] = traceback.format_exc()[-1500:]
    finally:
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')
        console('Squads.StartPatrol 1')

try:
    with open(LOG_PATH, 'rb') as handle:
        handle.seek(log_start)
        tail = handle.read().decode('utf-8', errors='replace')
    result['log'] = {'pose_repairs': tail.count('body bone buffers were incomplete'), 'pose_not_ready': tail.count('body pose not ready'),
                     'bone_out_of_range': tail.count('GetBoneMatrix : BoneIndex'), 'ensures': tail.count('Ensure condition failed'),
                     'accessed_none': tail.count('Accessed None')}
    check('log_no_empty_pose', result['log']['bone_out_of_range'] == 0 and result['log']['pose_not_ready'] == 0
          and result['log']['pose_repairs'] == 0, result['log'])
except Exception as error:
    result['log'] = repr(error)

result['passed'] = sum(1 for c in result['checks'].values() if c['ok'])
result['failed'] = sorted(name for name, c in result['checks'].items() if not c['ok'])
(OUT / ('verify_tuning_%s.json' % result.get('part', 'AB'))).write_text(json.dumps(result, indent=2, default=str))
json.dumps(result, default=str)
