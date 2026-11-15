"""One short PIE run (< 60 s) for pictures of the Lives F7 overlay. Run via execute_python with the PIE lock taken.
Pictures: Saved/Lives/F_overlay_level1.png, F_overlay_level2.png; result text returned."""

import base64
import json
import math
from pathlib import Path

OUT = Path(unreal.Paths.project_saved_dir()) / 'Lives'
OUT.mkdir(parents=True, exist_ok=True)
out = {'shots': []}


def unwrap(value):
    return value['returnValue'] if isinstance(value, dict) and 'returnValue' in value else value


def game_world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


async def shot(name):
    try:
        capture = unwrap(await call_tool('SceneCaptureToolset.SceneCaptureToolset.CaptureGameViewport', world=game_world(), maxResolution=1600))
        data = capture['image'] if isinstance(capture, dict) else None
        if isinstance(data, dict):
            data = data.get('data') or data.get('base64')
        if data:
            if ',' in data[:64]:
                data = data.split(',', 1)[1]
            (OUT / (name + '.png')).write_bytes(base64.b64decode(data))
            out['shots'].append(name)
    except Exception as error:
        out.setdefault('errors', []).append(name + ': ' + repr(error))


async def run():
    if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
        out['abort'] = 'PIE already running'
        return
    await call_tool('EditorToolset.EditorAppToolset.StartPIE')
    try:
        await asyncio.sleep(4.0)
        world = game_world()
        lives = unreal.get_world_subsystem(world, unreal.ReflectionsLivesSubsystem)
        npcs = unreal.get_world_subsystem(world, unreal.ReflectionsNpcSubsystem)
        lives.set_debug_level(1)
        lives.set_time_of_day(12.2)
        await asyncio.sleep(14.0)
        people = [a for a in npcs.get_npc_actors() if a is not None and unreal.SystemLibrary.is_valid(a) and str(lives.get_person_id(a)) != 'None']
        out['people'] = len(people)
        # Stand back from the busiest group so several tags are in view.
        if people:
            cx = sum(a.get_actor_location().x for a in people) / len(people)
            cy = sum(a.get_actor_location().y for a in people) / len(people)
            target = min(people, key=lambda a: math.hypot(a.get_actor_location().x - cx, a.get_actor_location().y - cy))
            player = unreal.GameplayStatics.get_player_pawn(world, 0)
            loc = target.get_actor_location()
            spot = unreal.Vector(loc.x - 900.0, loc.y - 300.0, loc.z + 20.0)
            player.teleport(spot, player.get_actor_rotation())
            yaw = math.degrees(math.atan2(loc.y - spot.y, loc.x - spot.x))
            player.get_controller().set_control_rotation(unreal.Rotator(0.0, -8.0, yaw))
        await asyncio.sleep(1.5)
        await shot('F_overlay_level1')
        lives.set_debug_level(2)
        await asyncio.sleep(1.0)
        await shot('F_overlay_level2')
        out['describe'] = str(lives.describe())[:3000]
        # The overlay is a playtest tool: never leave it on for the next person's Play.
        lives.set_debug_level(0)
        unreal.SystemLibrary.execute_console_command(world, 'Lives.Debug 0')
    except Exception as error:
        out['error'] = repr(error)
    finally:
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')


await run()
(OUT / 'overlay_shot.json').write_text(json.dumps(out, indent=2, default=str))
summary = json.dumps({k: v for k, v in out.items() if k != 'describe'}, default=str)
