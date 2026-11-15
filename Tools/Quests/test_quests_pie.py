"""PIE proof for the quest system, in short steps (each MCP call stays under its timeout; state goes through a JSON file).

    ns = dict(globals()); exec(compile(src, 'test_quests_pie.py', 'exec'), ns); result = await ns['step']('side', 1)

Stages:
  side 1   take the PIE lock, open Lvl_WorldJumpTest, show test quests, the giver appears; talk card offer; accept (pad A)
  side 2   tracked objective + pointer; pick up the ledger; light the brazier with a real Fire cast
  side 3   back to the giver: delivery, choice, turn in, reward banner; journal (L); stop PIE
  main 1   take the lock, open the map: main quest tracked; a shard; step through; pages one by one
  main 2   the finale: go to the arena, beat the Tarnish (Villain.DamageBoss), victory; stop PIE
  story 1  take the lock, open the map, list the story quests and screenshot each giver's offer card; stop PIE
Each stage writes Saved/QuestsTest/<stage>/report.json and PNGs (copied to ArtDirection/Quests/Screenshots by `publish`).
`step(stage, 'stop')` always stops PIE and releases the lock.
"""
import base64
import json
import math
import shutil
import time
from pathlib import Path

APP = 'EditorToolset.EditorAppToolset.'
TEST_MAP = globals().get('QUEST_TEST_MAP', '/Game/MockCity/Lvl_MockCity')   # New Game's map; the side proof ran on Lvl_WorldJumpTest
MAP_TAG = TEST_MAP.rsplit('/', 1)[-1]
ROOT = Path(unreal.Paths.project_saved_dir()).resolve() / 'QuestsTest'
SHOTS = Path(unreal.Paths.project_dir()).resolve() / 'ArtDirection' / 'Quests' / 'Screenshots'
LOCK = Path(unreal.Paths.project_saved_dir()).resolve() / 'PIE_LOCK.json'
ME = 'quests-session'


def lock_holder():
    try:
        data = json.loads(LOCK.read_text())
    except Exception:
        return None
    if data.get('owner') != ME and float(data.get('expires_epoch', 0)) > time.time():
        return data.get('owner'), data.get('expires_local')
    return None


def write_lock(purpose):
    now = time.time()
    LOCK.write_text(json.dumps({'owner': ME, 'purpose': purpose, 'acquired_epoch': int(now), 'expires_epoch': int(now + 240),
                                'expires_local': time.strftime('%H:%M:%S', time.localtime(now + 240))}, indent=2))


def refresh_lock():
    try:
        data = json.loads(LOCK.read_text())
        if data.get('owner') == ME:
            data['expires_epoch'] = int(time.time() + 240)
            data['expires_local'] = time.strftime('%H:%M:%S', time.localtime(time.time() + 240))
            LOCK.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


def release_lock():
    try:
        if json.loads(LOCK.read_text()).get('owner') == ME:
            LOCK.unlink()
    except Exception:
        pass


def game_world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


def cmd(world, text):
    unreal.SystemLibrary.execute_console_command(world, text)


def player(world):
    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    return pc, (pc.get_controlled_pawn() if pc else None)


def quests(world):
    return unreal.get_game_instance_subsystem(unreal.GameplayStatics.get_game_instance(world), unreal.ReflectionsQuestSubsystem)


def qworld(world):
    return unreal.get_world_subsystem(world, unreal.ReflectionsQuestWorldSubsystem)


def markers(world):
    return unreal.get_world_subsystem(world, unreal.ReflectionsStoryMarkerSubsystem)


def face(pc, pawn, target, pitch_bias=-4.0):
    d = target - pawn.get_actor_location()
    yaw = math.degrees(math.atan2(d.y, d.x))
    pitch = math.degrees(math.atan2(d.z, math.hypot(d.x, d.y))) + pitch_bias
    pc.set_control_rotation(unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw))


def teleport(pawn, loc, toward=None):
    pawn.teleport(loc + unreal.Vector(0, 0, 100), pawn.get_actor_rotation())


def ui(world):
    return qworld(world).describe_ui()


def skip_cutscenes(world):
    """Tests do not sit through scenes: skip whatever plays (the intro starts with the main quest)."""
    cls = getattr(unreal, 'ReflectionsCutsceneSubsystem', None)
    sub = unreal.get_world_subsystem(world, cls) if cls else None
    if sub and sub.is_cutscene_playing():
        sub.skip_cutscene()
        return True
    return False


class Run:
    def __init__(self, stage):
        self.stage = stage
        self.out = ROOT / stage
        self.out.mkdir(parents=True, exist_ok=True)
        self.path = self.out / 'report.json'
        self.report = json.loads(self.path.read_text()) if self.path.exists() else {}

    def save(self):
        self.path.write_text(json.dumps(self.report, indent=2, default=str))

    def note(self, key, value):
        self.report[key] = value

    async def shot(self, name):
        await asyncio.sleep(0.35)
        r = await call_tool('SceneCaptureToolset.SceneCaptureToolset.CaptureGameViewport', world=None, maxResolution=1600)
        data = r['image']
        if data is not None and not isinstance(data, str):
            data = data['data']
        if not data or str(data).startswith('urn:'):
            return None
        path = self.out / (name + '.png')
        path.write_bytes(base64.b64decode(data))
        self.report.setdefault('screenshots', [])
        if str(path) not in self.report['screenshots']:
            self.report['screenshots'].append(str(path))
        return str(path)


async def start(run, purpose):
    waited = 0.0
    while True:
        holder = lock_holder()
        if holder is None and not await call_tool(APP + 'IsPIERunning'):
            write_lock(purpose)
            try:
                await call_tool(APP + 'StartPIE')
                break
            except Exception:
                release_lock()
        await asyncio.sleep(5.0)
        waited += 5.0
        if waited > 60.0:
            raise RuntimeError('PIE busy or locked (%s); run this step again later.' % (holder,))
    cmd(game_world(), 'open ' + TEST_MAP)
    for _ in range(80):
        await asyncio.sleep(0.5)
        world = game_world()
        if world and MAP_TAG in world.get_path_name():
            pc, pawn = player(world)
            if pawn:
                break
    await asyncio.sleep(3.0)
    world = game_world()
    cmd(world, 'Quest.Reset')
    await asyncio.sleep(0.5)
    for _ in range(6):
        skip_cutscenes(world)
        await asyncio.sleep(0.5)
    run.report = {'map': world.get_path_name(), 'started': time.strftime('%H:%M:%S')}
    return world


def auto_placed(world):
    """Marker names the story marker subsystem had to auto-place (should be none on a finished map)."""
    try:
        return [str(n) for n in markers(world).get_auto_placed_names()]
    except Exception as ex:
        return 'n/a: %s' % ex


async def stop(run):
    if await call_tool(APP + 'IsPIERunning'):
        world = game_world()
        if world and MAP_TAG in world.get_path_name():
            cmd(world, 'Quest.Status')
            await call_tool(APP + 'StopPIE')
            run.report['stopped'] = True
        else:
            run.report['stopped'] = 'not my PIE world: %s' % (world.get_path_name() if world else None)
    release_lock()


def mine(world):
    if not world or MAP_TAG not in world.get_path_name():
        raise RuntimeError('The running PIE is not this test (world %s).' % (world.get_path_name() if world else None))


def option_index(world, prefix):
    """Index of the talk card button whose action starts with prefix (from Quest.Ui's '  > label [action]' lines)."""
    opts = [l for l in ui(world).splitlines() if l.startswith('  > ')]
    for i, l in enumerate(opts):
        if l.rsplit('[', 1)[-1].startswith(prefix):
            return i
    return -1


async def pick(world, prefix, wait=0.5):
    """Skips to the buttons and presses the one for this action. True if it was there."""
    qw = qworld(world)
    for _ in range(8):
        if not qw.advance_talk():
            break
    i = option_index(world, prefix)
    if i >= 0:
        qw.choose_talk_option(i)
    await asyncio.sleep(wait)
    return i >= 0


async def press(world, key, wait=0.35):
    qworld(world).simulate_key(key)
    await asyncio.sleep(wait)


# ------------------------------------------------------------------------------------------------------- side quest

async def side(run, n):
    if n == 1:
        world = await start(run, 'quest system PIE proof: test side quest (one run, 3 steps)')
        cmd(world, 'Quest.ShowTestQuests 1')
        q = quests(world)
        q.refresh_availability() if hasattr(q, 'refresh_availability') else None
        cmd(world, 'Quest.Reload')
        await asyncio.sleep(4.5)  # people check runs 3 s after start
        qw = qworld(world)
        giver = qw.find_person_actor('QuestTester')
        run.note('giver', giver.get_name() if giver else None)
        if not giver:
            raise RuntimeError('quest giver did not appear')
        pc, pawn = player(world)
        gl = giver.get_actor_location()
        teleport(pawn, gl + unreal.Vector(-220, 0, 0))
        await asyncio.sleep(0.6)
        face(pc, pawn, gl, pitch_bias=-8.0)
        await asyncio.sleep(1.2)
        await run.shot('01_giver_mark_prompt')
        run.note('ui_before_talk', ui(world))
        qw.open_talk(giver, False) if hasattr(qw, 'open_talk') else cmd(world, 'Quest.Talk QuestTester')
        await asyncio.sleep(0.6)
        run.note('ui_offer', ui(world))
        await run.shot('02_offer_card')
        await press(world, 'Gamepad_FaceButton_Bottom')   # Continue (pad A)
        run.note('ui_offer_2', ui(world))
        await run.shot('03_offer_buttons')
        await pick(world, 'accept:')                      # I'll do it
        run.note('ui_accepted', ui(world))
        await run.shot('04_accepted')
        await pick(world, 'goodbye')
        await asyncio.sleep(1.0)
        run.note('status_after_accept', str(q.get_status('test_ledger')))
        await run.shot('05_tracked_banner')
    elif n == 2:
        world = game_world()
        mine(world)
        q = quests(world)
        qw = qworld(world)
        pc, pawn = player(world)
        items = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsQuestItem)
        run.note('items', [i.get_name() for i in items])
        if items:
            il = items[0].get_actor_location()
            teleport(pawn, il + unreal.Vector(-900, -300, 0))
            await asyncio.sleep(0.5)
            face(pc, pawn, il)
            await asyncio.sleep(1.0)
            await run.shot('06_pointer_to_item')
            run.note('ui_pointer', ui(world))
            teleport(pawn, il - unreal.Vector(0, 0, 70))
            await asyncio.sleep(1.5)
        run.note('ledger_count', q.get_item_count('TestLedger'))
        run.note('ui_after_pickup', ui(world))
        await run.shot('07_after_pickup')
        brazier = markers(world).find('Spot_TestBrazier', True)
        if brazier:
            bl = brazier.get_actor_location()
            teleport(pawn, bl + unreal.Vector(-200, 0, 0))
            await asyncio.sleep(0.8)
            face(pc, pawn, bl + unreal.Vector(0, 0, 40), pitch_bias=0.0)
            await asyncio.sleep(0.5)
            driver = pawn.get_component_by_class(unreal.ReflectionsSampleSpellDriver)
            cast_ok = False
            for _ in range(4):
                if driver:
                    face(pc, pawn, bl + unreal.Vector(0, 0, 40), pitch_bias=0.0)
                    cast_ok = driver.cast_spell(unreal.HeroSpell.FIRE) or cast_ok
                await asyncio.sleep(1.6)
                if 'Light the brazier' not in ui(world):
                    break
            run.note('fire_cast', cast_ok)
            await run.shot('08_brazier_lit')
        run.note('ui_after_fire', ui(world))
    elif n == 3:
        world = game_world()
        mine(world)
        q = quests(world)
        qw = qworld(world)
        pc, pawn = player(world)
        giver = qw.find_person_actor('QuestTester')
        gl = giver.get_actor_location()
        teleport(pawn, gl + unreal.Vector(-220, 0, 0))
        await asyncio.sleep(0.6)
        face(pc, pawn, gl, pitch_bias=-8.0)
        await asyncio.sleep(0.8)
        await run.shot('09_return_mark')
        cmd(world, 'Quest.Talk QuestTester')
        await asyncio.sleep(0.6)
        run.note('ui_deliver', ui(world))
        await run.shot('10_delivery_lines')
        run.note('ui_choice', ui(world))
        await run.shot('11_choice')
        await pick(world, 'choose:test_ledger.keep_secret')
        run.note('ui_after_choice', ui(world))
        await run.shot('12_choice_reply')
        await pick(world, 'turn_in:')
        run.note('ui_reward', ui(world))
        await run.shot('13_turned_in')
        await pick(world, 'goodbye')
        await asyncio.sleep(1.2)
        await run.shot('14_complete_banner')
        run.note('status_end', str(q.get_status('test_ledger')))
        run.note('standing', q.get_standing('QuestTester'))
        run.note('unlock', q.has_unlock('Test_LedgerReturned'))
        qw.open_journal()
        await asyncio.sleep(0.8)
        await run.shot('15_journal_main')
        await press(world, 'Down')
        await asyncio.sleep(0.4)
        await run.shot('16_journal_side')
        run.note('ui_journal', ui(world))
        await press(world, 'L')
        await stop(run)


# ------------------------------------------------------------------------------------------------------- main quest

def main_step(q):
    """The main quest's current step id ('' when it is not active)."""
    r = q.get_quest_state('main')
    st = r[1] if isinstance(r, tuple) else r
    if not st or st.status != unreal.ReflectionsQuestStatus.ACTIVE:
        return ''   # a finished quest keeps its last step id
    return str(st.step_id)


async def main_try(run, world, q, sid):
    """Does the real thing for one main-quest step where the test map has it. Returns what it did."""
    qw = qworld(world)
    pc, pawn = player(world)
    mk = markers(world)
    goto = {'first_face': 'Spot_BellSquare', 'dull_as_ever': 'Spot_WeighHouseCorner', 'gilt_tower': 'Tower_Giltside'}
    if sid == 'intro':
        for _ in range(10):
            skip_cutscenes(world)
            await asyncio.sleep(0.5)
            if main_step(q) != 'intro':
                return 'intro: cutscene or 4 s fallback'
        return 'intro: waited'
    if sid == 'lantern_row':
        a = qw.find_person_actor('ilse_varrow')
        if not a:
            return 'no ilse'
        teleport(pawn, a.get_actor_location() + unreal.Vector(-220, 0, 0))
        await asyncio.sleep(0.6)
        face(pc, pawn, a.get_actor_location(), pitch_bias=-8.0)
        await asyncio.sleep(0.4)
        qw.open_talk(a, False)
        await asyncio.sleep(0.6)
        await run.shot('21_main_talk_ilse')
        for _ in range(10):
            if not qw.advance_talk():
                break
            await asyncio.sleep(0.2)
        await press(world, 'Escape')
        return 'talked to ilse'
    if sid == 'through_glass':
        for side in (unreal.ReflectionsWorld.WHITE, unreal.ReflectionsWorld.RED, unreal.ReflectionsWorld.GRAY):
            unreal.ReflectionsWorldLibrary.award_coin(world, side, 3)
        await asyncio.sleep(0.6)
        jumped = unreal.ReflectionsWorldLibrary.request_world_jump(world, unreal.ReflectionsJumpDirection.UP)
        await asyncio.sleep(2.5)
        return 'shards + world jump (%s)' % jumped
    if sid in ('hold_line', 'cracked_crown'):
        jumped = unreal.ReflectionsWorldLibrary.request_world_jump(world, unreal.ReflectionsJumpDirection.UP)
        await asyncio.sleep(2.5)
        return 'world jump (%s)' % jumped
    if sid in goto:
        m = mk.find(goto[sid], True)
        if m:
            teleport(pawn, m.get_actor_location())
            await asyncio.sleep(1.2)
        pages = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsBookPagePickup))
        used = run.report.setdefault('used_pages', [])
        pages = [p for p in pages if p.get_name() not in used]
        if pages and sid != 'first_face':
            used.append(pages[0].get_name())
            pl = pages[0].get_actor_location()
            teleport(pawn, pl - unreal.Vector(0, 0, 80))
            await asyncio.sleep(1.4)
            return 'went to %s + page %s' % (goto[sid], pages[0].get_name())
        return 'went to %s (%s)' % (goto[sid], m.get_name() if m else None)
    if sid == 'let_the_light_through':
        villain = unreal.get_world_subsystem(world, unreal.ReflectionsVillainSubsystem)
        bosses = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsVillainBoss)
        if bosses:
            bl = bosses[0].get_actor_location()
            teleport(pawn, bl + unreal.Vector(-900, 0, 0))
            await asyncio.sleep(1.0)
            face(pc, pawn, bl)
            await asyncio.sleep(0.8)
            await run.shot('27_main_boss')
        cmd(world, 'Villain.DamageBoss 100000')
        await asyncio.sleep(5.0)
        return 'boss damaged (finale %s, bosses %d)' % (villain.is_finale() if villain else None, len(bosses))
    return 'no real action on the test map'


async def main_walk(run, world, q, stop_at):
    """Walks the main quest step by step: the real action, else Quest.CompleteStep (recorded as forced)."""
    walk = run.report.setdefault('walk', [])
    for _ in range(14):
        sid = main_step(q)
        if not sid or sid == stop_at:
            break
        did = await main_try(run, world, q, sid)
        await asyncio.sleep(0.8)
        forced = main_step(q) == sid
        if forced:
            q.complete_step('main')
            await asyncio.sleep(0.8)
            skip_cutscenes(world)
        walk.append({'step': sid, 'did': did, 'forced': forced, 'next': main_step(q)})
        refresh_lock()
        await run.shot('22_main_%02d_%s' % (len(walk), sid))


async def main(run, n):
    if n == 1:
        world = await start(run, 'quest system PIE proof: main quest (one run, 2 steps)')
        q = quests(world)
        await asyncio.sleep(0.5)
        run.report['walk'] = []
        run.note('ui_start', ui(world))
        await run.shot('20_main_start')
        await main_walk(run, world, q, 'through_glass')
    elif n == 2:
        world = game_world()
        mine(world)
        q = quests(world)
        await main_walk(run, world, q, '')
        run.note('auto_placed', auto_placed(world))
        run.note('main_status', str(q.get_status('main')))
        run.note('victory_unlock', q.has_unlock('Quest_main'))
        run.note('ui_victory', ui(world))
        await asyncio.sleep(1.0)
        await run.shot('29_victory')
        await stop(run)


async def story(run, n):
    """Story pack: list the quests, then SQ9 'Unsigned' end to end through the talk card (pad A / Enter)."""
    if n == 1:
        world = await start(run, 'quest system PIE: story quests (one run, 2 steps)')
        if not unreal.EditorAssetLibrary.does_asset_exist('/Game/Quests/DA_QuestPack_Story'):
            cmd(world, 'Quest.LoadJson ArtDirection/Story/quests.json ArtDirection/Story/people.json')
            await asyncio.sleep(0.5)
        q = quests(world)
        qw = qworld(world)
        await asyncio.sleep(4.5)
        run.note('status_start', q.describe_status())
        run.note('ui_start', ui(world))
        await run.shot('30_story_start')
        # Skip the main quest to Lantern Row's end so SQ9 (requires Quest_main.lantern_row) opens.
        for _ in range(3):
            if q.has_unlock('Quest_main.lantern_row'):
                break
            q.complete_step('main')
            await asyncio.sleep(0.5)
            skip_cutscenes(world)
        run.note('sq9_status', str(q.get_status('sq9_unsigned')))
        pc, pawn = player(world)
        await asyncio.sleep(2.5)  # people check
        for person, shot in (('barnaby_thrale', '31_sq9_offer'),):
            a = qw.find_person_actor(person)
            run.note('found_' + person, a.get_name() if a else None)
            if not a:
                continue
            teleport(pawn, a.get_actor_location() + unreal.Vector(-220, 0, 0))
            await asyncio.sleep(0.6)
            face(pc, pawn, a.get_actor_location(), pitch_bias=-8.0)
            await asyncio.sleep(0.8)
            qw.open_talk(a, False)
            await asyncio.sleep(0.6)
            await run.shot(shot)
            for _ in range(6):
                if 'accept:' in ui(world):
                    break
                await press(world, 'Gamepad_FaceButton_Bottom')
            await press(world, 'Gamepad_FaceButton_Bottom')   # accept
            run.note('ui_sq9_accepted', ui(world))
            await press(world, 'Escape')
            await asyncio.sleep(1.0)
            await run.shot('32_sq9_tracked')
    elif n == 2:
        world = game_world()
        mine(world)
        q = quests(world)
        qw = qworld(world)
        pc, pawn = player(world)
        for i, person in enumerate(('odette_vane', 'barnaby_thrale', 'odette_vane')):
            a = qw.find_person_actor(person)
            if not a:
                run.note('missing_' + person, True)
                continue
            teleport(pawn, a.get_actor_location() + unreal.Vector(-220, 0, 0))
            await asyncio.sleep(0.6)
            face(pc, pawn, a.get_actor_location(), pitch_bias=-8.0)
            await asyncio.sleep(0.6)
            qw.open_talk(a, False)
            await asyncio.sleep(0.6)
            await run.shot('33_sq9_talk_%d' % i)
            run.note('ui_sq9_talk_%d' % i, ui(world))
            await press(world, 'Escape')
            await press(world, 'Escape')
            await asyncio.sleep(0.8)
        run.note('sq9_end', str(q.get_status('sq9_unsigned')))
        run.note('seam_held', q.has_unlock('Seam_Held'))
        await asyncio.sleep(1.0)
        await run.shot('34_sq9_complete')
        qw.open_journal()
        await asyncio.sleep(0.8)
        await run.shot('35_journal_story')
        await press(world, 'L')
        run.note('status_end', q.describe_status())
        run.note('auto_placed', auto_placed(world))
        await stop(run)


def publish():
    """Copies the PNGs to ArtDirection/Quests/Screenshots."""
    SHOTS.mkdir(parents=True, exist_ok=True)
    copied = []
    for stage in ('side', 'main', 'story'):
        for png in sorted((ROOT / stage).glob('*.png')):
            shutil.copy2(png, SHOTS / png.name)
            copied.append(png.name)
    return copied


async def step(stage, n):
    run = Run(stage)
    refresh_lock()
    try:
        if n == 'stop':
            await stop(run)
        elif stage == 'side':
            await side(run, n)
        elif stage == 'main':
            await main(run, n)
        elif stage == 'story':
            await story(run, n)
    except Exception:
        import traceback
        run.report['error_step_%s' % n] = traceback.format_exc()
        try:
            await stop(run)
        except Exception as ex:
            run.report['stop_error'] = str(ex)
    run.save()
    return {k: v for k, v in run.report.items() if k != 'screenshots'}
