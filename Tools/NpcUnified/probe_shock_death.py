"""Why does a Frost soldier killed while lightning runs through it end up without a pose?

Found in the crash-fix proof (train #22, 05:06): two of two FrostSoldier_Iven soldiers killed mid-shock read an empty
pose (every bone lookup answers the world origin), with no walker-physics code involved; Gilt guards killed the same
way never did. This probe runs with everything at its DEFAULTS (Npc.WalkerPhysics 0, the game as it ships) and varies
one thing at a time:

  A  Soldier archetype, FrostSoldier_Iven, shocked, killed 0.6 s into the shock        (the failing case)
  B  Soldier archetype, FrostSoldier_Iven, NOT shocked, killed                         (is it the shock?)
  C  Guard archetype,   FrostSoldier_Iven, shocked, killed                             (is it the archetype?)
  D  Soldier archetype, GiltSoldier_BridgeGuard, shocked, killed                       (is it the look?)
  E  Soldier archetype, FrostSoldier_Amara, shocked, killed                            (another Frost body)

Two of each, one at a time. For each corpse at 0.1, 0.4, 0.9 and 2.0 s after the kill: the pelvis socket (the pose),
the physics pelvis (the ragdoll), where the Body component is, whether it simulates, is registered, follows a leader,
ticks, and how many bones its mesh has. A picture of the first corpse found without a pose. The shock is a hit injected
on that NPC alone (no projectile, no chain). PIE of about 45 s; always stopped; nothing saved.
Result: Saved/NpcUnified/probe_shock_death.json and S_* pictures.
"""

import base64
import json
import time
from pathlib import Path

OUT = Path(unreal.Paths.project_saved_dir()) / 'NpcUnified'
OUT.mkdir(parents=True, exist_ok=True)
CASES = globals().get('CASES', 'ABCDE')
PLAN = {'A': ('Soldier', 'FrostSoldier_Iven', True), 'B': ('Soldier', 'FrostSoldier_Iven', False), 'C': ('Guard', 'FrostSoldier_Iven', True),
        'D': ('Soldier', 'GiltSoldier_BridgeGuard', True), 'E': ('Soldier', 'FrostSoldier_Amara', True)}
result = {'cases': {}, 'defaults': {}, 'mitigate': bool(globals().get('MITIGATE', False)), 'started': time.strftime('%H:%M:%S')}


def unwrap(value):
    return value['returnValue'] if isinstance(value, dict) and 'returnValue' in value else value


def console(command, world=None):
    unreal.SystemLibrary.execute_console_command(world or unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world(), command)


def save():
    (OUT / 'probe_shock_death.json').write_text(json.dumps(result, indent=1, default=str))


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

        TOWARD_HERO = unreal.MathLibrary.find_look_at_rotation(at(320), unreal.Vector(HERE.x, HERE.y, GROUND)).yaw

        def brain(actor):
            return actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent)

        def body_of(actor):
            return next(m for m in actor.get_components_by_class(unreal.SkeletalMeshComponent) if m.get_name() == 'Body')

        def look_class(look_id):
            try:
                return unreal.load_object(None, '/Game/Characters/Lanthorne/Looks/Soldiers/%s.%s_C' % (look_id, look_id))
            except Exception:
                return None

        def vec(v):
            return [round(v.x, 1), round(v.y, 1), round(v.z, 1)]

        def state(actor):
            body = body_of(actor)
            row = {}
            for key, read in (('pose_pelvis', lambda: vec(body.get_socket_location('pelvis'))),
                              ('pose_head', lambda: vec(body.get_socket_location('head'))),
                              ('physics_pelvis', lambda: vec(body.get_center_of_mass('pelvis'))),
                              ('component_at', lambda: vec(body.get_world_location())),
                              ('simulating', lambda: body.is_any_simulating_physics()),
                              ('registered', lambda: body.is_registered()),
                              ('leader', lambda: str(body.get_editor_property('leader_pose_component'))[:40]),
                              ('attached_to', lambda: body.get_attach_parent().get_name() if body.get_attach_parent() else None),
                              ('tick_on', lambda: body.is_component_tick_enabled()),
                              ('tick_interval', lambda: round(body.get_component_tick_interval(), 3)),
                              ('pause_anims', lambda: body.get_editor_property('pause_anims')),
                              ('anim_mode', lambda: body.get_editor_property('animation_mode').name),
                              ('visible', lambda: body.is_visible()),
                              ('mesh_bones', lambda: body.get_num_bones())):
                try:
                    row[key] = read()
                except Exception as error:
                    row[key] = 'ERR ' + repr(error)[:50]
            row['pose_empty'] = row.get('pose_pelvis') == [0.0, 0.0, 0.0] and row.get('pose_head') == [0.0, 0.0, 0.0]
            # The sword and the shield: how far each is from the bone it hangs on, and from the ragdoll's pelvis.
            try:
                held = []
                pelvis = body.get_center_of_mass('pelvis')
                for part in actor.get_components_by_class(unreal.StaticMeshComponent):
                    mesh = part.get_editor_property('static_mesh')
                    if not mesh:
                        continue
                    bone = str(part.get_attach_socket_name())
                    where = part.get_world_location()
                    held.append([mesh.get_name().replace('SM_', '')[:22], bone, round((where - body.get_socket_location(bone)).length()),
                                 round((where - pelvis).length()), part.get_attach_parent().get_name() if part.get_attach_parent() else None])
                row['held'] = held
            except Exception as error:
                row['held'] = 'ERR ' + repr(error)[:60]
            row['no_skeleton_update'] = None
            try:
                row['no_skeleton_update'] = body.get_editor_property('no_skeleton_update')
            except Exception as error:
                row['no_skeleton_update'] = 'ERR ' + repr(error)[:40]
            return row

        def shock(actor):
            hit = unreal.ReflectionsSpellHitData()
            hit.set_editor_property('spell', unreal.HeroSpell.LIGHTNING_BOLT)
            hit.set_editor_property('location', brain(actor).get_aim_point())
            hit.set_editor_property('impulse', unreal.Vector(ahead.x * 260.0, ahead.y * 260.0, 0.0))
            hit.set_editor_property('caster', player)
            hit.set_editor_property('target', actor)
            hit.set_editor_property('reaction', unreal.ReflectionsSpellReaction.ELECTRIFY)
            hit.set_editor_property('magnitude', 0.7)
            hit.set_editor_property('duration', 1.5)
            hit.set_editor_property('origin', player.get_actor_location())
            npcs.report_spell_hit(hit)

        async def picture(name, look_at, from_point):
            try:
                aim = unreal.MathLibrary.find_look_at_rotation(from_point, look_at)
                capture = unwrap(await call_tool('SceneCaptureToolset.SceneCaptureToolset.Capture', world=world,
                                                 camera={'location': {'x': from_point.x, 'y': from_point.y, 'z': from_point.z},
                                                         'rotation': {'pitch': aim.pitch, 'yaw': aim.yaw, 'roll': 0.0},
                                                         'projectionMode': 'Perspective', 'fOV': 50.0},
                                                 mode='Lit', options={'width': 900, 'height': 900, 'screenPercentage': 1.0, 'visualizationSubMode': ''}))
                data = capture.get('image') if isinstance(capture, dict) else None
                if isinstance(data, dict):
                    data = data.get('data') or data.get('base64')
                if data:
                    if ',' in data[:64]:
                        data = data.split(',', 1)[1]
                    (OUT / (name + '.png')).write_bytes(base64.b64decode(data))
            except Exception as error:
                result.setdefault('shot_errors', []).append(name + ': ' + repr(error)[:160])

        for name in ('Npc.WalkerPhysics', 'Npc.WalkerJolts', 'Npc.ElementReactions', 'Crowd.Lod.Enable'):
            try:
                result['defaults'][name] = unreal.SystemLibrary.get_console_variable_string_value(name)
            except Exception as error:
                result['defaults'][name] = repr(error)[:40]

        pictured = False
        slot = 0
        blast_targets = []
        for case in CASES:
            archetype, look_id, shocked = PLAN[case]
            for repeat in range(int(globals().get('REPEATS', 2))):
                spot = at(420, (slot % 8 - 3.5) * (90.0 if globals().get('BLAST_AFTER', False) else 150.0))
                slot += 1
                actor = npcs.spawn_npc(archetype, spot, TOWARD_HERO, look_class(look_id))
                await asyncio.sleep(1.3)
                brain(actor).set_externally_steered(True)
                record = {'archetype': archetype, 'look': look_id, 'shocked': shocked, 'alive': state(actor), 'after': {}}
                if shocked:
                    shock(actor)
                    await asyncio.sleep(0.6)
                    record['reaction_before_kill'] = brain(actor).get_editor_property('reaction').name
                unreal.GameplayStatics.apply_damage(actor, 999.0, None, player, unreal.DamageType)
                if globals().get('UNFIX', False):
                    # The old behaviour on a build that has the fix in C++: the body goes on evaluating its own animation.
                    try:
                        body_of(actor).set_editor_property('no_skeleton_update', False)
                        record['unfixed'] = True
                    except Exception as error:
                        record['unfixed'] = repr(error)[:80]
                if globals().get('MITIGATE', False):
                    # The candidate fix, tried from here before it goes into C++: once the body is a ragdoll, its own
                    # animation is no longer evaluated (only the physics blend writes its pose).
                    try:
                        body_of(actor).set_editor_property('no_skeleton_update', True)
                        record['mitigated'] = True
                    except Exception as error:
                        record['mitigated'] = repr(error)[:80]
                began = time.perf_counter()
                for moment in (0.1, 0.4, 0.9, 2.0):
                    await asyncio.sleep(max(0.0, moment - (time.perf_counter() - began)))
                    record['after'][str(moment)] = state(actor)
                record['empty_at'] = [m for m, s in record['after'].items() if s.get('pose_empty')]
                last = record['after']['2.0']
                try:
                    record['pose_to_physics_cm_at_2s'] = round(sum((a - b) ** 2 for a, b in zip(last['pose_pelvis'], last['physics_pelvis'])) ** 0.5, 1)
                except Exception:
                    record['pose_to_physics_cm_at_2s'] = None
                result['cases'].setdefault(case, []).append(record)
                blast_targets.append((case, len(result['cases'][case]) - 1, actor))
                save()
                if record['empty_at'] and not pictured:
                    pictured = True
                    where = body_of(actor).get_center_of_mass('pelvis')
                    await picture('S_first_empty_corpse_%s' % case, where, unreal.Vector(where.x - ahead.x * 320.0 + side.x * 120.0, where.y - ahead.y * 320.0 + side.y * 120.0, where.z + 150.0))
                    record['pictured'] = True
        if globals().get('BLAST_AFTER', False):
            # Can a later spell near such a corpse take the game down? Three Fireballs and two Lightning Bolts into the
            # corpses of this run, the ones without a pose among them. (The two editor crashes were asserts on a body in
            # this state.) Progress is saved before each cast: a crash leaves the record of how far it got.
            spells = player.get_component_by_class(unreal.ReflectionsSpellCombatComponent)
            controller = player.get_controller()
            corpses = [(case, index, npcs_actor) for case, index, npcs_actor in blast_targets]
            empties = [(c, i) for c, i, a in corpses if state(a).get('pose_empty')]
            result['blast'] = {'corpses': len(corpses), 'without_a_pose_before': empties, 'casts': []}
            save()
            order = [a for c, i, a in corpses if (c, i) in empties] + [a for c, i, a in corpses if (c, i) not in empties]
            for shot, spell in enumerate((unreal.HeroSpell.FIRESTORM, unreal.HeroSpell.LIGHTNING_BOLT, unreal.HeroSpell.FIRESTORM,
                                          unreal.HeroSpell.LIGHTNING_BOLT, unreal.HeroSpell.FIRESTORM)):
                target = order[shot % len(order)]
                aim = body_of(target).get_center_of_mass('pelvis')
                controller.set_control_rotation(unreal.MathLibrary.find_look_at_rotation(player.get_actor_location(), aim))
                origin = unreal.Transform(location=player.get_actor_location() + unreal.Vector(0, 0, 50), rotation=unreal.Rotator(), scale=unreal.Vector(1, 1, 1))
                result['blast']['casts'].append({'spell': spell.name, 'at': time.strftime('%H:%M:%S'), 'landed': False})
                save()
                spells.release_spell_at(spell, origin, aim, None)
                await asyncio.sleep(1.4)
                result['blast']['casts'][-1]['landed'] = True
                save()
            await asyncio.sleep(1.5)
            result['blast']['without_a_pose_after'] = [(c, i) for c, i, a in corpses if state(a).get('pose_empty')]
            result['blast']['survived'] = True
            save()
        result['summary'] = {case: {'what': '%s / %s / %s' % (PLAN[case][0], PLAN[case][1], 'shocked' if PLAN[case][2] else 'not shocked'),
                                    'empty': sum(1 for r in rows if r['empty_at']), 'of': len(rows)} for case, rows in result['cases'].items()}
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

result['ended'] = time.strftime('%H:%M:%S')
save()
json.dumps({'finished': result.get('finished'), 'summary': result.get('summary'), 'error': result.get('error')}, default=str)
