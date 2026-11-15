"""Ambient NPC talk only near the player (Source/reflections/Voice/ReflectionsAmbientTalk). Run with
run_pie_locked.py on the open game map, PIE stopped and the local relay running. About 2 minutes.

  1 near   the player stands in the busiest calm group for 40 s: every calm NPC voice that plays is within 20 m
           (18 m fade + 2 m slack), at most 3 calm voices at once; fight lines within 38 m
  2 away   the player jumps 60 m from everyone: after 2 s no calm voice is still playing; for 15 s nothing new starts
  3 talk   back next to a calm NPC, a typed line still gets a reply that finishes (player-started talk is not gated)

Writes Saved/NpcAmbientTalk/report.json and always stops PIE. Free memory under 3 GB stops the run (team rule).
"""
import ctypes
import json
import time
from pathlib import Path

OUT = Path(unreal.Paths.project_saved_dir()) / 'NpcAmbientTalk'
OUT.mkdir(parents=True, exist_ok=True)
APP = 'EditorToolset.EditorAppToolset.'
report = {'checks': {}, 'samples': [], 'voices_seen': {}}


def unwrap(value):
    return value['returnValue'] if isinstance(value, dict) and 'returnValue' in value else value


def check(name, ok, detail=None):
    report['checks'][name] = {'ok': bool(ok), 'detail': detail}


class MemoryStatus(ctypes.Structure):
    _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]


def free_gb():
    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    return round(status.ullAvailPageFile / 1024 ** 3, 1)


def memory_ok(stage):
    report.setdefault('free_gb', []).append((stage, free_gb()))
    if report['free_gb'][-1][1] < 3.0:
        raise RuntimeError('free memory under 3 GB; stopping PIE')


token = Path(unreal.Paths.project_saved_dir()) / 'NpcDialogue' / 'relay.token'
if not token.exists():
    report['abort'] = 'Local relay is not running (no Saved/NpcDialogue/relay.token).'
elif unwrap(await call_tool(APP + 'IsPIERunning')):
    report['abort'] = 'PIE is already running (someone else is testing); nothing was started.'
else:
    unreal.SystemLibrary.execute_console_command(None, 'Cutscene.IntroInPIE 0')
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    try:
        try:
            await call_tool(APP + 'StartPIE', options={'warmupSeconds': 3.0})
        except Exception as error:
            report['start_note'] = repr(error)[:200]  # big World Partition maps outlast the tool's wait
        for _ in range(90):
            if editor.get_game_world():
                break
            await asyncio.sleep(1.0)
        await asyncio.sleep(3.0)
        world = editor.get_game_world()
        player = unreal.GameplayStatics.get_player_pawn(world, 0)
        controller = player.get_controller()
        npcs = unreal.get_world_subsystem(world, unreal.ReflectionsNpcSubsystem)
        dialogue = unreal.get_world_subsystem(world, unreal.ReflectionsVoiceInteractionSubsystem)
        unreal.SystemLibrary.execute_console_command(world, 'Cutscene.Skip')
        unreal.SystemLibrary.execute_console_command(world, 'Squads.Passive 1')
        memory_ok('start')

        def brain(actor):
            return actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent) if actor else None

        def calm(actor):
            b = brain(actor)
            return b is None or b.get_editor_property('reaction').name in ('CALM',)

        def voices():
            """Every NPC voice line playing in PIE: (distance m, calm speaker?, sound name)."""
            here = player.get_actor_location()
            found = []
            for comp in unreal.ObjectIterator(unreal.AudioComponent):
                try:
                    if 'UEDPIE' not in comp.get_path_name() or not comp.is_playing():
                        continue
                    sound = comp.get_editor_property('sound')
                    if sound is None or 'Procedural' in sound.get_class().get_name():
                        continue  # the player's own conversation streams through a procedural wave
                    path = sound.get_path_name()
                    if '/Voice/' not in path and 'SCue_VO' not in path and 'Ambient' not in path:
                        continue
                    owner = comp.get_owner()
                    speaker = owner
                    if brain(owner) is None and owner is not None and owner.get_attach_parent_actor():
                        speaker = owner.get_attach_parent_actor()
                    distance = (comp.get_world_location() - here).length() / 100.0
                    found.append((round(distance, 1), calm(speaker), sound.get_name()))
                except Exception:
                    continue
            return found

        def stand_near(actor):
            target = actor.get_actor_location()
            forward = actor.get_actor_forward_vector()
            spot = target + unreal.Vector(forward.x * 250.0, forward.y * 250.0, 5.0)
            player.set_actor_location(spot, False, True)
            look = unreal.MathLibrary.find_look_at_rotation(spot, target + unreal.Vector(0, 0, 60))
            controller.set_control_rotation(look)

        everyone = [a for a in npcs.get_npc_actors() if a]
        calm_people = [a for a in everyone if calm(a)]
        report['npcs'] = {'all': len(everyone), 'calm': len(calm_people)}

        def neighbours(actor):
            at = actor.get_actor_location()
            return sum(1 for other in calm_people if other != actor and (other.get_actor_location() - at).length() < 1000.0)

        hub = max(calm_people, key=neighbours) if calm_people else None
        check('found_calm_group', hub is not None, hub.get_name() if hub else None)

        # 1 near: listen in the busiest group.
        far_calm, far_fight, most_calm, heard = [], [], 0, 0
        if hub is not None:
            stand_near(hub)
            started = time.time()
            while time.time() - started < 40.0:
                await asyncio.sleep(0.5)
                now = voices()
                calm_now = [v for v in now if v[1]]
                most_calm = max(most_calm, len(calm_now))
                heard += len(now)
                far_calm += [v for v in calm_now if v[0] > 20.0]
                far_fight += [v for v in now if not v[1] and v[0] > 38.0]
                for v in now:
                    report['voices_seen'][v[2]] = max(report['voices_seen'].get(v[2], 0.0), v[0])
                if now:
                    report['samples'].append({'t': round(time.time() - started, 1), 'voices': now})
            memory_ok('near')
        check('1_near_no_calm_voice_beyond_20m', not far_calm, far_calm[:10])
        check('1_near_fight_lines_within_38m', not far_fight, far_fight[:10])
        check('1_near_at_most_3_calm_voices', most_calm <= 3, most_calm)
        report['near_voice_samples'] = heard  # informational: how much ambient talk the group made

        # 2 away: 60 m from everyone (straight up the hub's back direction, on its ground height).
        if hub is not None:
            at = hub.get_actor_location()
            best, best_gap = None, 0.0
            for dx, dy in ((6000, 0), (-6000, 0), (0, 6000), (0, -6000), (4300, 4300), (-4300, -4300)):
                spot = at + unreal.Vector(dx, dy, 5.0)
                gap = min(((a.get_actor_location() - spot).length() for a in everyone), default=1e9)
                if gap > best_gap:
                    best, best_gap = spot, gap
            player.set_actor_location(best, False, True)
            report['away_gap_m'] = round(best_gap / 100.0, 1)
            await asyncio.sleep(2.0)
            lingering = [v for v in voices() if v[1]]
            check('2_away_calm_voices_faded_after_2s', not lingering, lingering)
            started_far = []
            started = time.time()
            while time.time() - started < 15.0:
                await asyncio.sleep(0.5)
                started_far += [v for v in voices() if v[1] and v[0] > 13.0]
            check('2_away_nothing_new_starts_beyond_13m', not started_far, started_far[:10])
            memory_ok('away')

        # 3 talk: player-started conversation still works next to a calm NPC.
        if hub is not None:
            stand_near(hub)
            await asyncio.sleep(1.0)
            before = sum(dialogue.get_reply_count(getattr(unreal.ReflectionsReplySource, s)) for s in ('GENERATED', 'CACHED', 'BARK'))
            sent = dialogue.say_to_npc(hub, "Good day! Busy street today?")
            finished, began = False, time.time()
            while time.time() - began < 30.0:
                await asyncio.sleep(0.25)
                total = sum(dialogue.get_reply_count(getattr(unreal.ReflectionsReplySource, s)) for s in ('GENERATED', 'CACHED', 'BARK'))
                if total > before and not dialogue.is_npc_busy():
                    finished = True
                    break
            report['talk'] = {'sent': sent, 'line': dialogue.get_last_npc_line(), 'seconds': round(time.time() - began, 1),
                              'source': str(dialogue.get_last_reply_source())}
            check('3_player_talk_still_finishes', sent and finished, report['talk'])
            # A far NPC is refused: no live model call for someone the player cannot hear.
            far_one = max(everyone, key=lambda a: (a.get_actor_location() - player.get_actor_location()).length())
            far_m = (far_one.get_actor_location() - player.get_actor_location()).length() / 100.0
            if far_m > 18.0:
                check('3_far_npc_refused', not dialogue.say_to_npc(far_one, "Hello over there!"), round(far_m, 1))
        report['status'] = dialogue.describe_status()
    except Exception as error:
        report['error'] = repr(error)
    finally:
        try:
            if unwrap(await call_tool(APP + 'IsPIERunning')):
                await call_tool(APP + 'StopPIE')
        except Exception as error:
            report['stop_error'] = repr(error)

report['passed'] = sum(1 for c in report['checks'].values() if c['ok'])
report['failed'] = sorted(name for name, c in report['checks'].items() if not c['ok'])
(OUT / 'report.json').write_text(json.dumps(report, indent=2, default=str))
json.dumps({k: report.get(k) for k in ('passed', 'failed', 'npcs', 'near_voice_samples', 'away_gap_m', 'talk', 'abort', 'error', 'free_gb')}, default=str)
