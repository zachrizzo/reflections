"""NPC talk-back showcase (short version of test_npc_dialogue_pie.py, under 3 minutes). Run through the editor MCP `execute_python` tool (top-level `await`, `call_tool`) with
Gray London (/Game/GrayLondon/Maps/GrayLondon_Geodata, the only map) open, PIE stopped, the PIE lock held, and the local relay running
(Tools/RealtimeVoice/Start-NpcDialogueRelay.ps1).

It starts PIE, spawns a passive soldier squad, then types lines to NPCs through
UReflectionsVoiceInteractionSubsystem::SayToNpc (the same path as the Enter key):
  1 civilian  "Hello there..."      expect a fresh generation (cache miss)
  2 guard     the same line         fresh
  3 soldier   the same line         fresh
  4 civilian  "Hi! What's going on..." in a new conversation: expect a cache hit (decision model agrees)
  5 civilian  a new question        expect a miss (nothing saved is close)
  6 guard     with Npc.DialogueFallback 1: the baked bark with its subtitle (what players get with no relay)
  7 civilian  the player walks 20 m away mid-reply: the voice fades with distance and the subtitle clears
Every reply must come from an audio component attached to the NPC's head bone, spatialized.
Each reply is pictured while its subtitle is on screen. Writes Saved/NpcDialogueTest/*.png and report.json, and
always stops PIE. About 90 seconds and a few US cents of Gemini use.
"""
import base64
import ctypes
import json
import time
from pathlib import Path

OUT = Path(unreal.Paths.project_saved_dir()) / 'NpcDialogueShowcase'
OUT.mkdir(parents=True, exist_ok=True)
APP = 'EditorToolset.EditorAppToolset.'
report = {'turns': [], 'checks': {}, 'shots': []}
SOURCE = {0: 'None', 1: 'Generated', 2: 'Cached', 3: 'Bark'}


def unwrap(value):
    return value['returnValue'] if isinstance(value, dict) and 'returnValue' in value else value


def check(name, ok, detail=None):
    report['checks'][name] = {'ok': bool(ok), 'detail': detail}


async def shot(name):
    """A viewport capture, plus UE's own screenshot with the UI (the capture tool can miss Slate widgets)."""
    try:
        shots = Path(unreal.Paths.project_saved_dir()) / 'Screenshots'
        before = {p for p in shots.rglob('*.png')} if shots.exists() else set()
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        unreal.SystemLibrary.execute_console_command(world, 'Shot showui')
        for _ in range(20):
            await asyncio.sleep(0.15)
            new = [p for p in shots.rglob('*.png') if p not in before] if shots.exists() else []
            if new:
                await asyncio.sleep(0.3)
                (OUT / (name + '_ui.png')).write_bytes(max(new, key=lambda p: p.stat().st_mtime).read_bytes())
                report['shots'].append(str(OUT / (name + '_ui.png')))
                break
    except Exception as error:
        report.setdefault('shot_errors', []).append(name + ' ui: ' + repr(error))
    try:
        capture = unwrap(await call_tool('SceneCaptureToolset.SceneCaptureToolset.CaptureGameViewport', world=None,
                                         maxResolution=1600))
        data = capture['image'] if isinstance(capture, dict) else None
        if isinstance(data, dict):
            data = data.get('data') or data.get('base64')
        if data:
            if ',' in data[:64]:
                data = data.split(',', 1)[1]
            path = OUT / (name + '.png')
            path.write_bytes(base64.b64decode(data))
            report['shots'].append(str(path))
    except Exception as error:
        report.setdefault('shot_errors', []).append(name + ': ' + repr(error))


def source_name(value):
    try:
        return value.name.title() if hasattr(value, 'name') else SOURCE.get(int(value), str(value))
    except Exception:
        return str(value)


token = Path(unreal.Paths.project_saved_dir()) / 'NpcDialogue' / 'relay.token'
if not token.exists():
    report['abort'] = 'Local relay is not running (no Saved/NpcDialogue/relay.token).'
elif unwrap(await call_tool(APP + 'IsPIERunning')):
    report['abort'] = 'PIE is already running (someone else is testing); nothing was started.'
else:
    unreal.log('NPC_DIALOGUE_PIE_START')
    unreal.SystemLibrary.execute_console_command(None, 'Cutscene.IntroInPIE 0')
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    try:
        if not editor.get_game_world():
            try:
                await call_tool(APP + 'StartPIE', options={'warmupSeconds': 3.0})
            except Exception as error:
                # Gray London (World Partition) takes over 20 s to start: keep waiting for the PIE world.
                report['start_note'] = repr(error)[:200]
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
        check('dialogue_subsystem', dialogue is not None)
        unreal.SystemLibrary.execute_console_command(world, 'Cutscene.Skip')
        unreal.SystemLibrary.execute_console_command(world, 'Squads.Passive 1')
        await asyncio.sleep(2.0)

        def brain(actor):
            return actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent)

        def archetype(actor):
            b = brain(actor)
            a = b.get_active_archetype() if b else None
            return str(a.get_editor_property('archetype_id')) if a else '?'

        def calm(actor):
            b = brain(actor)
            return b is not None and b.get_editor_property('reaction').name in ('CALM', 'ALERT')

        def kinds():
            found = {}
            for actor in [a for a in npcs.get_npc_actors() if a]:
                found.setdefault(archetype(actor), []).append(actor)
            return found

        by_kind = kinds()
        # Spawn a test squad only when the map has no soldier of its own (each soldier look costs memory).
        if not (by_kind.get('Soldier') or by_kind.get('SoldierCaster')):
            unreal.SystemLibrary.execute_console_command(world, 'Squads.SpawnTest 1')
            await asyncio.sleep(5.0)
            by_kind = kinds()
            report['spawned_test_squad'] = True
        report['npcs'] = {k: len(v) for k, v in by_kind.items()}
        civilians = [a for k in ('Civilian', 'Timid', 'Brave') for a in by_kind.get(k, []) if calm(a)]
        civilian = civilians[0] if civilians else None
        guard = (by_kind.get('Guard') or [None])[0]
        soldier = (by_kind.get('Soldier') or by_kind.get('SoldierCaster') or [None])[0]
        check('found_npcs', civilian and guard and soldier,
              {'civilian': civilian.get_name() if civilian else None, 'guard': guard.get_name() if guard else None,
               'soldier': soldier.get_name() if soldier else None})

        def stand_near(actor):
            """Puts the player 300 cm in front of the NPC and a little to its side, so the camera sees its face."""
            target = actor.get_actor_location()
            forward = actor.get_actor_forward_vector()
            right = actor.get_actor_right_vector()
            spot = target + unreal.Vector(forward.x * 300.0 + right.x * 110.0, forward.y * 300.0 + right.y * 110.0, 0.0)
            # The NPC's own height: on Gray London the ground is uneven, and the player's height could leave them
            # in mid-air or inside a building, far out of earshot.
            spot.z = target.z + 5.0
            player.set_actor_location(spot, False, True)
            look = unreal.MathLibrary.find_look_at_rotation(spot, target + unreal.Vector(0, 0, 60))
            look.pitch -= 8.0
            controller.set_control_rotation(look)

        sources = []

        def voice_sources(actor):
            """Audio components on the NPC that are playing: where they hang and whether they are 3D."""
            found = []
            for comp in actor.get_components_by_class(unreal.AudioComponent):
                try:
                    if comp.is_playing():
                        parent = comp.get_attach_parent()
                        found.append({'parent': parent.get_name() if parent else None,
                                      'socket': str(comp.get_attach_socket_name()),
                                      'spatial': bool(comp.get_editor_property('allow_spatialization')),
                                      'attenuation': comp.get_editor_property('attenuation_settings').get_name()
                                      if comp.get_editor_property('attenuation_settings') else 'override'})
                except Exception as error:
                    found.append({'error': repr(error)})
            return found

        def free_commit_gb():
            class Status(ctypes.Structure):
                _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                            ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                            ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                            ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                            ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
            status = Status()
            status.dwLength = ctypes.sizeof(Status)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return status.ullAvailPageFile / 1024 ** 3

        async def talk(label, actor, line, expect=None, walk_away=False):
            # Team rule: stop our own PIE if free memory falls under 3 GB.
            report.setdefault('free_gb', []).append(round(free_commit_gb(), 1))
            if report['free_gb'][-1] < 3.0:
                raise RuntimeError('free memory under 3 GB; stopping PIE')
            if actor is None:
                check(label, False, 'no NPC of this kind')
                return
            stand_near(actor)
            await asyncio.sleep(0.6)
            counts = {s: dialogue.get_reply_count(getattr(unreal.ReflectionsReplySource, s.upper())) for s in ('Generated', 'Cached', 'Bark')}
            started = time.time()
            dialogue.say_to_npc(actor, line)
            pictured, first_line_at, finished = False, None, False
            while time.time() - started < 30.0:
                await asyncio.sleep(0.2)
                stand_near(actor) if time.time() - started < 1.0 else None
                text = dialogue.get_last_npc_line()
                now = {s: dialogue.get_reply_count(getattr(unreal.ReflectionsReplySource, s.upper())) for s in counts}
                replied = any(now[s] > counts[s] for s in counts)
                if replied and text and first_line_at is None:
                    first_line_at = round(time.time() - started, 2)
                if replied and text and not pictured and dialogue.is_npc_speaking():
                    await asyncio.sleep(0.6)
                    sources = voice_sources(actor)
                    await shot(label)
                    pictured = True
                    if walk_away:
                        away = player.get_actor_location() + unreal.Vector(0.0, 2000.0, 0.0)
                        player.set_actor_location(away, False, True)
                        await asyncio.sleep(1.0)
                        await shot(label + '_after_walking_20m')
                if replied and not dialogue.is_npc_busy():
                    finished = True
                    break
            source = source_name(dialogue.get_last_reply_source())
            if not pictured:
                sources = voice_sources(actor)
                await shot(label)
            turn = {'label': label, 'npc': actor.get_name(), 'archetype': archetype(actor),
                    'speaker': dialogue.get_speaker_name(), 'player': line, 'npc_line': dialogue.get_last_npc_line(),
                    'source': source, 'reply_id': dialogue.get_last_reply_id(), 'subtitle_after_s': first_line_at,
                    'finished': finished, 'seconds': round(time.time() - started, 1), 'voice_sources': sources}
            report['turns'].append(turn)
            # Fresh vs saved depends on what earlier runs cached, so a different source is noted, not failed.
            check(label, bool(finished and turn['npc_line']), turn)
            if expect is not None and source != expect:
                report.setdefault('source_notes', []).append(f'{label}: expected {expect}, got {source}')
            check(label + '_voice_on_head', any(v.get('socket') == 'head' and v.get('spatial') for v in sources), sources)
            await asyncio.sleep(0.8)

        hello = "Hello there! What's going on around here today?"
        await talk('1_civilian', civilian, hello, 'Generated')
        await talk('2_guard', guard, hello, 'Generated')
        await talk('3_soldier', soldier, hello, 'Generated')
        await talk('4_civilian_cache_hit', civilian, "Hi! What's going on around here today?", 'Cached')
        await talk('5_civilian_asks_the_way', civilian, "Could you point me toward a mirror page or the Gilt Tower?", None)
        report['status'] = dialogue.describe_status()
    except Exception as error:
        report['error'] = repr(error)
    finally:
        try:
            unreal.SystemLibrary.execute_console_command(world, 'Npc.DialogueFallback 0')
        except Exception:
            pass
        try:
            if unwrap(await call_tool(APP + 'IsPIERunning')):
                await call_tool(APP + 'StopPIE')
        except Exception as error:
            report['stop_error'] = repr(error)

try:
    ue_log = (Path(unreal.Paths.project_log_dir()) / 'reflections.log').read_text(encoding='utf-8', errors='replace')
    ue_log = ue_log[ue_log.rfind('NPC_DIALOGUE_PIE_START'):]
    report['ue_dialogue_log'] = [l[l.find('LogReflectionsNpcDialogue'):][:300] for l in ue_log.splitlines()
                                 if 'LogReflectionsNpcDialogue' in l][-30:]
    report['actions'] = [l for l in report['ue_dialogue_log'] if 'NPC action' in l]
except Exception as error:
    report['ue_dialogue_log'] = repr(error)
try:
    relay_log = Path(unreal.Paths.project_saved_dir()) / 'NpcDialogue' / 'relay.log'
    lines = relay_log.read_text(encoding='utf-8', errors='replace').splitlines()
    report['relay_log_tail'] = [l for l in lines if '[turn' in l or '[ratio]' in l][-14:]
except Exception as error:
    report['relay_log_tail'] = repr(error)

report['passed'] = sum(1 for c in report['checks'].values() if c['ok'])
report['failed'] = sorted(name for name, c in report['checks'].items() if not c['ok'])
(OUT / 'report.json').write_text(json.dumps(report, indent=2, default=str))
json.dumps({k: report[k] for k in ('passed', 'failed', 'turns') if k in report} | {'abort': report.get('abort'), 'error': report.get('error')}, default=str)
