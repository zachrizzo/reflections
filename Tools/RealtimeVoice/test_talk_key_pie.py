"""One talk key (E / D-pad Down): quest dialogue for a person with quest business, live voice for anyone else; the
listening display; NPCs face the player and stop walking while they talk. Run with run_pie_locked.py on the open game
map (MedievalLondon), PIE stopped, the local relay running. About 2 minutes.

Uses the voice system's test hooks (PressTalkKey = pressing / letting go of E, GetTalkPromptText, IsListeningShown,
IsThinkingShown) and the quest system's IsTalkOpen / CloseTalk.

  1 prompts   near a quest person the prompt is "E   Talk to <name>"; near anyone else "Hold E to speak"; never "AI"
  3 voice     E on an ordinary NPC: the listening display (not the quest card); let go: thinking, then a reply ends;
              the NPC faces the player (within 30 degrees) and does not walk off (under 40 cm in 2 s)
  2 quest     E on a quest person: the quest card opens and no listening; the person faces the player and stays put;
              closing the card gives it back to its routine (NPC_NoStroll removed)

Writes Saved/NpcTalkKey/report.json and *_ui.png captures, and always stops PIE.
"""
import base64
import ctypes
import json
import math
import time
from pathlib import Path

OUT = Path(unreal.Paths.project_saved_dir()) / 'NpcTalkKey'
OUT.mkdir(parents=True, exist_ok=True)
APP = 'EditorToolset.EditorAppToolset.'
report = {'checks': {}, 'shots': [], 'prompts': []}


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


async def shot(name):
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
                return
    except Exception as error:
        report.setdefault('shot_errors', []).append(name + ': ' + repr(error))


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
        quests = unreal.get_world_subsystem(world, unreal.ReflectionsQuestWorldSubsystem)
        unreal.SystemLibrary.execute_console_command(world, 'Cutscene.Skip')
        unreal.SystemLibrary.execute_console_command(world, 'Squads.Passive 1')
        memory_ok('start')

        def brain(actor):
            return actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent) if actor else None

        def calm(actor):
            b = brain(actor)
            return b is not None and b.get_editor_property('reaction').name == 'CALM'

        squad_members = set()
        for squad in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsSquad):
            try:
                for member in squad.get_editor_property('members'):
                    actor = member.get_editor_property('actor')
                    if actor:
                        squad_members.add(actor.get_name())
            except Exception as error:
                report.setdefault('squad_errors', []).append(repr(error)[:120])

        def soldier(actor):
            # Squads steer their members (guards included), so voice talk leaves those bodies alone unless the squad
            # is halted: not an ordinary facing test.
            b = brain(actor)
            a = b.get_active_archetype() if b else None
            return actor.get_name() in squad_members or (a is not None and 'Soldier' in str(a.get_editor_property('archetype_id')))

        def stand_near(actor):
            target = actor.get_actor_location()
            forward = actor.get_actor_forward_vector()
            right = actor.get_actor_right_vector()
            # To its side, so "faces the player" has to be a real turn.
            spot = target + unreal.Vector(right.x * 230.0 + forward.x * 60.0, right.y * 230.0 + forward.y * 60.0, 5.0)
            player.set_actor_location(spot, False, True)
            look = unreal.MathLibrary.find_look_at_rotation(spot, target + unreal.Vector(0, 0, 60))
            look.pitch -= 8.0
            controller.set_control_rotation(look)

        def facing_error(actor):
            to = player.get_actor_location() - actor.get_actor_location()
            want = math.degrees(math.atan2(to.y, to.x))
            have = actor.get_actor_rotation().yaw
            return round(abs((want - have + 180.0) % 360.0 - 180.0), 1)

        here = player.get_actor_location()
        people = sorted([a for a in npcs.get_npc_actors() if a and calm(a)], key=lambda a: (a.get_actor_location() - here).length())
        report['calm_npcs'] = len(people)

        # 1 prompts: find a quest person and an ordinary person.
        quest_npc, voice_npc = None, None
        for actor in people[:40]:
            stand_near(actor)
            await asyncio.sleep(0.5)
            if dialogue.get_talk_target() != actor and not dialogue.get_talk_prompt_text():
                continue
            prompt = str(dialogue.get_talk_prompt_text())
            report['prompts'].append({'npc': actor.get_name(), 'prompt': prompt})
            if prompt.startswith(('E   Talk to', 'D-pad')) and quest_npc is None:
                quest_npc = actor
            elif prompt.startswith(('Hold E', 'Hold D-pad')) and voice_npc is None and dialogue.get_talk_target() == actor and not soldier(actor):
                voice_npc = actor
            if quest_npc and voice_npc:
                break
        check('1_prompt_hold_e_for_ordinary_npc', voice_npc is not None, report['prompts'][-6:])
        check('1_prompt_e_talk_for_quest_person', quest_npc is not None, report['prompts'][-6:])
        check('1_no_ai_or_gemini_in_prompts', not any('AI' in p['prompt'].split() or 'Gemini' in p['prompt'] for p in report['prompts']),
              report['prompts'])

        # 2 quest (first): E opens the quest card for a quest person; it faces the player; closing hands it back.
        if quest_npc is not None:
            await asyncio.sleep(1.0)
            stand_near(quest_npc)
            await asyncio.sleep(0.6)
            before_error = facing_error(quest_npc)
            start_at = quest_npc.get_actor_location()
            dialogue.press_talk_key(True)
            await asyncio.sleep(0.3)
            opened = quests.is_talk_open()
            listening = dialogue.is_listening_shown()
            dialogue.press_talk_key(False)
            await asyncio.sleep(1.7)
            await shot('3_quest_card')
            after_error = facing_error(quest_npc)
            moved = round((quest_npc.get_actor_location() - start_at).length(), 1)
            tagged = quest_npc.actor_has_tag('NPC_NoStroll')
            check('3_quest_e_opens_card_not_voice', opened and not listening, {'card': opened, 'listening': listening})
            check('3_quest_npc_faces_player', after_error <= 30.0, {'before_deg': before_error, 'after_deg': after_error})
            check('3_quest_npc_stays_put', moved < 40.0, {'moved_cm': moved, 'no_stroll_tag': tagged})
            quests.close_talk()
            await asyncio.sleep(0.5)
            check('3_quest_close_returns_routine', not quests.is_talk_open() and not quest_npc.actor_has_tag('QuestTalk_NoStroll'),
                  {'still_tagged': quest_npc.actor_has_tag('NPC_NoStroll')})
        # 3 voice: hold E, let go, a reply; the NPC faces the player and stays put.
        if voice_npc is not None:
            stand_near(voice_npc)
            await asyncio.sleep(0.6)
            before_error = facing_error(voice_npc)
            start_at = voice_npc.get_actor_location()
            dialogue.press_talk_key(True)
            await asyncio.sleep(1.2)
            listening = dialogue.is_listening_shown()
            await shot('2_voice_listening')
            check('2_voice_e_opens_listening_not_quest', listening and not quests.is_talk_open(),
                  {'listening': listening, 'quest_open': quests.is_talk_open()})
            await asyncio.sleep(0.8)
            after_error = facing_error(voice_npc)
            moved = round((voice_npc.get_actor_location() - start_at).length(), 1)
            dialogue.press_talk_key(False)
            thinking, began = False, time.time()
            while time.time() - began < 4.0 and not thinking:
                await asyncio.sleep(0.1)
                thinking = dialogue.is_thinking_shown()
            if thinking:
                await shot('2_voice_thinking')
            finished = False
            while time.time() - began < 25.0:
                await asyncio.sleep(0.25)
                if not dialogue.is_npc_busy() and not dialogue.is_listening_shown() and not dialogue.is_thinking_shown():
                    finished = True
                    break
            check('2_voice_thinking_shown', thinking)
            check('2_voice_turn_ends', finished, {'line': dialogue.get_last_npc_line(), 'source': str(dialogue.get_last_reply_source())})
            check('2_voice_npc_faces_player', after_error <= 30.0, {'before_deg': before_error, 'after_deg': after_error})
            check('2_voice_npc_stays_put', moved < 40.0, {'moved_cm': moved})
            memory_ok('voice')


        # 4 spot: a person at a bench or stall (Crowd_Spot) is let go to face the player; no copy left, no extra spawn.
        spot_npc = next((a for a in people if a.actor_has_tag('Crowd_Spot') and not soldier(a)), None)
        if spot_npc is not None:
            await asyncio.sleep(0.5)
            count_before = len([a for a in npcs.get_npc_actors() if a])
            spot_at = spot_npc.get_actor_location()
            stand_near(spot_npc)
            await asyncio.sleep(0.6)
            before_error = facing_error(spot_npc)
            dialogue.press_talk_key(True)
            await asyncio.sleep(2.5)
            after_error = facing_error(spot_npc)
            released = not spot_npc.actor_has_tag('Crowd_Spot')
            await shot('4_spot_person')
            dialogue.press_talk_key(False)
            if quests.is_talk_open():
                quests.close_talk()
            await asyncio.sleep(1.0)
            others = [a for a in npcs.get_npc_actors() if a]
            near_old = [a.get_name() for a in others if a != spot_npc and (a.get_actor_location() - spot_at).length() < 60.0]
            check('4_spot_person_released_and_faces', released and after_error <= 30.0,
                  {'npc': spot_npc.get_name(), 'released': released, 'before_deg': before_error, 'after_deg': after_error})
            check('4_spot_no_copy_no_extra_spawn', not near_old and len(others) <= count_before,
                  {'npcs_before': count_before, 'npcs_after': len(others), 'left_at_spot': near_old})
            began = time.time()
            while time.time() - began < 12.0 and (dialogue.is_npc_busy() or dialogue.is_thinking_shown()):
                await asyncio.sleep(0.25)
        else:
            report['spot_note'] = 'no calm person at a bench or stall'

        # 5 soldier: in a halted (or inactive) squad, turns in place to face the player.
        halted = []
        for squad in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsSquad):
            try:
                state = str(squad.get_editor_property('state').name)
                if state not in ('HALTED', 'INACTIVE'):
                    continue
                for member in squad.get_editor_property('members'):
                    actor = member.get_editor_property('actor')
                    if actor and calm(actor):
                        halted.append((actor, state))
            except Exception as error:
                report.setdefault('squad_errors', []).append(repr(error)[:120])
        here = player.get_actor_location()
        halted.sort(key=lambda e: (e[0].get_actor_location() - here).length())
        if halted:
            trooper, state = halted[0]
            await asyncio.sleep(0.5)
            stand_near(trooper)
            await asyncio.sleep(0.6)
            start_at = trooper.get_actor_location()
            before_error = facing_error(trooper)
            dialogue.press_talk_key(True)
            await asyncio.sleep(2.0)
            after_error = facing_error(trooper)
            moved = round((trooper.get_actor_location() - start_at).length(), 1)
            await shot('5_halted_soldier')
            dialogue.press_talk_key(False)
            check('5_halted_soldier_turns_in_place', after_error <= 30.0 and moved < 60.0,
                  {'npc': trooper.get_name(), 'squad': state, 'before_deg': before_error, 'after_deg': after_error, 'moved_cm': moved})
        else:
            report['soldier_note'] = 'no calm soldier in a halted or inactive squad'
        memory_ok('end')
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
json.dumps({k: report.get(k) for k in ('passed', 'failed', 'prompts', 'abort', 'error', 'free_gb')}, default=str)
