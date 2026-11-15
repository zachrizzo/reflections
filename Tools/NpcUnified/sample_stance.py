"""How steady the standing guard stance is: where the blade and the shield's face point, sampled over one loop.

One PIE of about 25 s. A Gilt and a Frost soldier stand facing the hero; from 2 s after they appear, the direction of
the sword's blade and of the shield's face is read four times a second for 3.5 s, in the body's own frame
(ahead, to its right, up). Also which clip plays on the walker. Nothing is changed or saved.
Run in the editor's Python (top-level await, `call_tool`), map open, PIE stopped, PIE lock held.
Result: Saved/NpcUnified/sample_stance.json
"""

import json
from pathlib import Path

OUT = Path(unreal.Paths.project_saved_dir()) / 'NpcUnified'
result = {'checks': {}}


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

        def at(forward_cm, right_cm=0.0):
            return unreal.Vector(HERE.x + ahead.x * forward_cm + side.x * right_cm, HERE.y + ahead.y * forward_cm + side.y * right_cm, GROUND)

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

        def sample(actor):
            walker = brain(actor).get_locomotion_driver() or actor
            forward, right = walker.get_actor_forward_vector(), walker.get_actor_right_vector()
            row = {'speed': round(walker.get_velocity().length())}
            try:
                montage = walker.get_editor_property('mesh').get_anim_instance().get_current_active_montage()
                row['clip'] = montage.get_name()[:40] if montage else None
            except Exception as error:
                row['clip'] = repr(error)[:30]
            for part in actor.get_components_by_class(unreal.StaticMeshComponent):
                mesh = part.get_editor_property('static_mesh')
                kind = None
                if mesh:
                    kind = 'sword' if 'Sword' in mesh.get_name() else ('shield' if 'Shield' in mesh.get_name() else None)
                if kind:
                    x = unreal.MathLibrary.get_forward_vector(part.get_world_rotation())
                    row[kind] = [round(x.x * forward.x + x.y * forward.y, 2), round(x.x * right.x + x.y * right.y, 2), round(x.z, 2)]
            return row

        gilt = npcs.spawn_npc('AlliedSoldier', at(300, -110), TOWARD_HERO, look_class('GiltSoldier_BridgeGuard'))
        frost = npcs.spawn_npc('Soldier', at(300, 110), TOWARD_HERO, look_class('FrostSoldier_Iven'))
        for posed in (gilt, frost):
            brain(posed).set_externally_steered(True)
        await asyncio.sleep(2.0)
        rows = {'gilt': [], 'frost': []}
        for _ in range(14):
            rows['gilt'].append(sample(gilt))
            rows['frost'].append(sample(frost))
            await asyncio.sleep(0.25)
        result['samples'] = rows
        summary = {}
        for name, series in rows.items():
            for kind in ('sword', 'shield'):
                ahead_values = [r[kind][0] for r in series if kind in r]
                up_values = [r[kind][2] for r in series if kind in r]
                if ahead_values:
                    summary['%s_%s' % (name, kind)] = {'ahead_min': min(ahead_values), 'ahead_max': max(ahead_values),
                                                       'up_min': min(up_values), 'up_max': max(up_values)}
            summary[name + '_clips'] = sorted({str(r.get('clip')) for r in series})
            summary[name + '_max_speed'] = max(r['speed'] for r in series)
        result['summary'] = summary
        result['checks']['shield_faces_ahead_all_through'] = {'ok': all(summary[n + '_shield']['ahead_min'] >= 0.6 for n in rows if n + '_shield' in summary), 'detail': summary}
        result['checks']['blade_ahead_all_through'] = {'ok': all(summary[n + '_sword']['ahead_min'] >= 0.6 for n in rows if n + '_sword' in summary), 'detail': None}
    except Exception as error:
        import traceback
        result['error'] = repr(error)
        result['trace'] = traceback.format_exc()[-1200:]
    finally:
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')
        console('Squads.StartPatrol 1')

result['passed'] = sum(1 for c in result['checks'].values() if c['ok'])
result['failed'] = sorted(name for name, c in result['checks'].items() if not c['ok'])
(OUT / 'sample_stance.json').write_text(json.dumps(result, indent=1, default=str))
json.dumps({'passed': result['passed'], 'failed': result['failed'], 'error': result.get('error'), 'summary': result.get('summary')}, default=str)[:2500]
