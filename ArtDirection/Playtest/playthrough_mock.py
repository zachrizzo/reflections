"""Playtest lead: full playthrough of the mock city in PIE, in short steps (one execute_python call each).

    src = open(r'C:/Users/zachc/Documents/Unreal Projects/reflections/ArtDirection/Playtest/playthrough_mock.py').read()
    ns = dict(globals()); exec(compile(src, 'playthrough_mock.py', 'exec'), ns); result = await ns['step'](0)

Steps (each renews the PIE lock; 'stop' always stops PIE, resets the cvars and frees the lock):
  0  preflight (lock, no PIE, no open sequence), TitleInPIE/IntroInPIE on, Play, title -> New Game (keys)
  1  mock city loaded, intro playing -> skip, control back, start state, ring crowd
  2  Bell Lane shards (walk), Ilse on Lantern Row (walk, E, talk lines)
  3  Fire Bolt spell-kill of a spawned Guard, ring crowd check
  4  burning eyes in Bell Square: villain host, cure with spells
  5  step down to Pewterside (hold key), Weigh-House roof page 1 + Giltside shard
  6  step up to Giltside, Lantern Gate (tarnished), Gilt Tower key
  7  Gilt Tower door -> page 2 + Frostside shard
  8  step up inside the tower -> Frost Tower page 3, book complete, Final Spell, boss
  9  climb the ramps to the crown (walk), boss rises
  10 Final Spell (F) until the boss burns out, Ending, Victory, stop
Walking is the player's own move input (IA_Move forward) steered along a navmesh path. When a leg does not
arrive in time the hero is teleported the rest of the way and the leg is reported as a FAIL (stuck / no path).
Every jump, pickup, door, talk and cast goes through the real game path (keys, overlaps, the talk card).
"""
import asyncio
import base64
import json
import math
import time
from pathlib import Path

APP = 'EditorToolset.EditorAppToolset.'
PROJ = Path(unreal.Paths.project_dir()).resolve()
OUT = PROJ / 'ArtDirection' / 'Playtest' / 'run3'
SHOTS = PROJ / 'ArtDirection' / 'Playtest' / 'shots'
LOCK = Path(unreal.Paths.project_saved_dir()).resolve() / 'PIE_LOCK.json'
ME = 'playtest-lead (packaging session local_51169275)'
GRAY, RED, WHITE = unreal.ReflectionsWorld.GRAY, unreal.ReflectionsWorld.RED, unreal.ReflectionsWorld.WHITE
SIDE_X = {GRAY: 0.0, RED: 150000.0, WHITE: 300000.0}
CROWN = unreal.Vector(301300.0, 7000.0, 2400.0)
RAMP_EXIT = unreal.Vector(300800.0, 7800.0, 2500.0)


# ------------------------------------------------------------------------------------------------ lock + basics
def lock_data():
    try:
        return json.loads(LOCK.read_text())
    except Exception:
        return None


def lock_busy():
    d = lock_data()
    if d and d.get('owner') != ME and float(d.get('expires_epoch', d.get('expires', 0))) > time.time():
        return d.get('owner')
    return None


def write_lock(purpose):
    now = time.time()
    LOCK.write_text(json.dumps({'owner': ME, 'purpose': purpose, 'acquired_epoch': int(now), 'expires_epoch': int(now + 240),
                                'expires_local': time.strftime('%H:%M:%S', time.localtime(now + 240))}, indent=2))


def renew_lock():
    d = lock_data()
    if d and d.get('owner') == ME:
        d['expires_epoch'] = int(time.time() + 240)
        d['expires_local'] = time.strftime('%H:%M:%S', time.localtime(time.time() + 240))
        LOCK.write_text(json.dumps(d, indent=2))


def release_lock():
    d = lock_data()
    if d and d.get('owner') == ME:
        LOCK.unlink()


def game_world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


def player(world):
    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    return pc, (pc.get_controlled_pawn() if pc else None)


def cmd(world, text):
    unreal.SystemLibrary.execute_console_command(world, text)


def gi_sub(world, cls):
    return unreal.get_game_instance_subsystem(unreal.GameplayStatics.get_game_instance(world), cls)


def flow_of(world):
    return gi_sub(world, unreal.ReflectionsGameFlowSubsystem)


def jumps_of(world):
    return gi_sub(world, unreal.ReflectionsWorldJumpSubsystem)


def quests_of(world):
    return unreal.get_world_subsystem(world, unreal.ReflectionsQuestWorldSubsystem)


def cutscenes_of(world):
    return unreal.get_world_subsystem(world, unreal.ReflectionsCutsceneSubsystem)


def villain_of(world):
    return unreal.get_world_subsystem(world, unreal.ReflectionsVillainSubsystem)


def vec(v):
    return [round(v.x), round(v.y), round(v.z)]


def dist(a, b):
    return (a - b).length()


def safe(fn, default=None):
    try:
        return fn()
    except Exception as e:
        return 'err: %s' % str(e)[:120]


def health_of(pawn):
    c = pawn.get_component_by_class(unreal.ReflectionsHealthComponent) if pawn else None
    if not c:
        return None
    return safe(lambda: round(c.get_editor_property('health'), 1))


def tracker(world):
    q = quests_of(world)
    if not q:
        return None
    text = safe(lambda: q.describe_ui()) or ''
    return text if len(text) < 900 else text[:900] + '...'


def state(world):
    pc, pawn = player(world)
    s = {'t': round(unreal.GameplayStatics.get_time_seconds(world), 1)}
    if pawn:
        s['loc'] = vec(pawn.get_actor_location())
        s['health'] = health_of(pawn)
        d = pawn.get_component_by_class(unreal.ReflectionsSampleSpellDriver)
        if d:
            s['mana'] = round(d.get_mana(), 1)
        j = pawn.get_component_by_class(unreal.ReflectionsWorldJumpComponent)
        s['jump_component'] = bool(j)
        if j:
            s['side'] = str(j.get_current_world()).split('.')[-1]
    js = jumps_of(world)
    if js:
        s['coins'] = {n: js.get_coins(w) for n, w in (('gray', GRAY), ('red', RED), ('white', WHITE))}
        s['pages'] = [str(p) for p in js.get_pages()]
        s['keys'] = [str(k) for k in js.get_keys()]
        s['book'] = js.is_book_complete()
    f = flow_of(world)
    if f:
        s['screen'] = str(f.get_screen()).split('.')[-1]
        s['run_live'] = f.is_run_live()
        s['tarnish'] = '%s/%s' % (f.get_infection_count(), f.get_infection_cap())
    cs = cutscenes_of(world)
    if cs and cs.is_cutscene_playing():
        s['cutscene'] = str(cs.get_current_cutscene())
    if pc:
        s['move_ignored'] = pc.is_move_input_ignored()
    return s


def ring(world):
    pc, pawn = player(world)
    walkers = [a for a in unreal.GameplayStatics.get_all_actors_with_tag(world, 'Crowd_LaneWalker')]
    out = {'count': len(walkers)}
    if pawn and walkers:
        here = pawn.get_actor_location()
        ds = sorted(round(dist(a.get_actor_location(), here) / 100.0) for a in walkers)
        out['dist_m'] = ds
        out['moving'] = sum(1 for a in walkers if a.get_velocity().length() > 20.0)
    return out


# ------------------------------------------------------------------------------------------------ report + shots
class Run:
    def __init__(self):
        OUT.mkdir(parents=True, exist_ok=True)
        SHOTS.mkdir(parents=True, exist_ok=True)
        self.path = OUT / 'report.json'
        self.report = json.loads(self.path.read_text()) if self.path.exists() else {}

    def save(self):
        self.path.write_text(json.dumps(self.report, indent=2, default=str))

    def put(self, step, key, value):
        self.report.setdefault('step%s' % step, {})[key] = value

    async def shot(self, step, name):
        try:
            r = await call_tool('SceneCaptureToolset.SceneCaptureToolset.CaptureGameViewport', world=None, maxResolution=1280)
            data = r['image']
            if data is not None and not isinstance(data, str):
                data = data['data']
            if not data or str(data).startswith('urn:'):
                return None
            path = SHOTS / ('r3-%s.png' % name)
            path.write_bytes(base64.b64decode(data))
            self.report.setdefault('step%s' % step, {}).setdefault('shots', []).append(path.name)
            return path.name
        except Exception as e:
            self.put(step, 'shot_error_' + name, str(e)[:200])
            return None


# ------------------------------------------------------------------------------------------------ player actions
async def key(name, seconds=0.12):
    await call_tool('InputToolset.InputToolset.ApplyInput', entries=[{'key': {'keyName': name}, 'value': {'x': 1, 'y': 0, 'z': 0}}],
                    durationSeconds=seconds)


def face(pc, pawn, target, pitch_bias=-2.0):
    d = target - pawn.get_actor_location()
    yaw = math.degrees(math.atan2(d.y, d.x))
    pitch = math.degrees(math.atan2(d.z + 30.0, math.hypot(d.x, d.y))) + pitch_bias
    pc.set_control_rotation(unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw))


MOVE_ACTIONS = ['/Game/Input/IA_Move.IA_Move', '/Game/Input/Actions/IA_Move.IA_Move']


async def push_forward(seconds):
    """The player's own move input (stick / WASD forward), on both IA_Move assets the hero setups use."""
    await call_tool('InputToolset.InputToolset.ApplyInput', durationSeconds=seconds,
                    entries=[{'action': {'refPath': a}, 'value': {'x': 0, 'y': 1, 'z': 0}} for a in MOVE_ACTIONS])


def flat_dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def nav_path(world, a, b):
    try:
        p = unreal.NavigationSystemV1.find_path_to_location_synchronously(world, a, b)
    except Exception as e:
        return None, 'err %s' % str(e)[:100]
    if not p:
        return None, None
    pts = list(p.get_editor_property('path_points'))
    return pts, safe(lambda: p.is_partial())


async def walk_to(world, target, timeout=25.0, tol=180.0, label=''):
    """Walks with the real move input, steering along a navmesh path (the camera turns with it).
    Returns a leg report; teleports the rest of the way if it can't arrive."""
    pc, pawn = player(world)
    start = pawn.get_actor_location()
    pts, partial = nav_path(world, start, target)
    leg = {'leg': label, 'from': vec(start), 'to': vec(target), 'straight_m': round(dist(start, target) / 100.0, 1),
           'nav_points': len(pts) if pts else 0, 'nav_partial': partial}
    if not pts:
        pts = [start, target]
        leg['no_nav_path'] = True
    i = 1 if len(pts) > 1 else 0
    t0 = unreal.GameplayStatics.get_time_seconds(world)
    last, last_t, stuck_for = start, t0, 0.0
    wall0 = time.time()
    while True:
        now = unreal.GameplayStatics.get_time_seconds(world)
        here = pawn.get_actor_location()
        if flat_dist(here, target) < tol and abs(here.z - target.z) < 260.0:
            leg.update(result='arrived', game_s=round(now - t0, 1))
            break
        while i < len(pts) - 1 and flat_dist(here, pts[i]) < 120.0:
            i += 1
        if i == len(pts) - 1 and flat_dist(here, pts[i]) < 100.0:
            leg.update(result='PATH_END_SHORT', game_s=round(now - t0, 1), at=vec(here), left_m=round(dist(here, target) / 100.0, 1))
            break
        wp = pts[i]
        pc.set_control_rotation(unreal.Rotator(roll=0.0, pitch=-10.0, yaw=math.degrees(math.atan2(wp.y - here.y, wp.x - here.x))))
        await push_forward(0.35)
        now = unreal.GameplayStatics.get_time_seconds(world)
        here = pawn.get_actor_location()
        if now - last_t >= 1.5:
            moved = dist(here, last)
            stuck_for = stuck_for + (now - last_t) if moved < 40.0 else 0.0
            last, last_t = here, now
            if stuck_for >= 3.0:
                leg.update(result='STUCK', game_s=round(now - t0, 1), stuck_at=vec(here), left_m=round(dist(here, target) / 100.0, 1))
                break
        if now - t0 > timeout or time.time() - wall0 > timeout + 15.0:
            leg.update(result='TIMEOUT', game_s=round(now - t0, 1), at=vec(here), left_m=round(dist(here, target) / 100.0, 1))
            break
    if leg['result'] != 'arrived':
        pawn.teleport(target + unreal.Vector(0.0, 0.0, 60.0), pawn.get_actor_rotation())
        leg['teleported_rest'] = True
        await asyncio.sleep(0.6)
    return leg


async def skip_cutscene(world, run, step, label):
    for _ in range(3):
        cs = cutscenes_of(world)
        if not cs or not cs.is_cutscene_playing():
            return
        run.report.setdefault('cutscenes', []).append('%s @%s' % (cs.get_current_cutscene(), label))
        cs.skip_cutscene()
        await asyncio.sleep(1.0)


async def wait_cutscene_or(world, seconds):
    for _ in range(int(seconds / 0.25)):
        cs = cutscenes_of(world)
        if cs and cs.is_cutscene_playing():
            return True
        await asyncio.sleep(0.25)
    return False


async def hold_jump(world, run, step, up):
    pc, pawn = player(world)
    j = pawn.get_component_by_class(unreal.ReflectionsWorldJumpComponent)
    if not j:
        run.put(step, 'jump', 'FAIL: no jump component on the pawn')
        return False
    direction = unreal.ReflectionsJumpDirection.UP if up else unreal.ReflectionsJumpDirection.DOWN
    before = state(world)
    can = safe(lambda: str(j.can_jump(direction)))
    keys = ['X', 'Z'] if up else ['Z', 'X']
    side0 = str(j.get_current_world())
    used = None
    for k in keys[:1]:
        await key(k, 0.45)
        for _ in range(16):
            await asyncio.sleep(0.25)
            if str(j.get_current_world()) != side0 and not j.is_jumping():
                used = k
                break
        if used:
            break
    await asyncio.sleep(0.8)
    after = state(world)
    run.put(step, 'jump_%s' % ('up' if up else 'down'), {'can_jump_before': can, 'key': keys[0], 'changed_side': used is not None,
                                                          'before': before, 'after': after})
    return used is not None


def pickups(world, cls):
    return [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, cls) if unreal.SystemLibrary.is_valid(a)]


def side_of_x(x):
    return GRAY if x < 75000.0 else (RED if x < 225000.0 else WHITE)


def coins_on(world, side, near=None, radius=None):
    out = []
    for c in pickups(world, unreal.ReflectionsCoinPickup):
        loc = c.get_actor_location()
        if str(c.get_editor_property('coin_world')) != str(side):  # the shard's colour, not where it lies
            continue
        if near is not None and radius is not None and dist(loc, near) > radius:
            continue
        out.append(c)
    return out


def page_on(world, side):
    for p in pickups(world, unreal.ReflectionsBookPagePickup):
        if side_of_x(p.get_actor_location().x) == side:
            return p
    return None


async def cast_at(world, target, casts=5, gap=1.0, until=None):
    pc, pawn = player(world)
    done = 0
    for _ in range(casts):
        if until and until():
            break
        if not unreal.SystemLibrary.is_valid(target):
            break
        face(pc, pawn, target.get_actor_location(), pitch_bias=-1.0)
        await key('LeftMouseButton', 0.25)
        done += 1
        await asyncio.sleep(gap)
    return done


def npcs(world):
    out = []
    for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
        c = a.get_component_by_class(unreal.ReflectionsNpcReactionComponent)
        if c:
            out.append((a, c))
    return out


# ------------------------------------------------------------------------------------------------ steps
async def s0(run):
    busy = lock_busy()
    if busy:
        raise RuntimeError('PIE lock held by %s' % busy)
    if await call_tool(APP + 'IsPIERunning'):
        raise RuntimeError('PIE is already running (someone else?)')
    seq = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
    run.report = {'open_sequence_at_play': seq.get_path_name() if seq else None}
    if seq and not globals().get('ALLOW_SEQ'):
        raise RuntimeError('A level sequence is open in Sequencer: %s (ask its owner to close it)' % seq.get_path_name())
    write_lock('Row 5: FULL playthrough on the mock city via New Game (title > shards > jumps > 3 pages > finale > Victory), short steps')
    for c in ('GameFlow.TitleInPIE 1', 'Cutscene.IntroInPIE 1'):
        unreal.SystemLibrary.execute_console_command(None, c)
    run.report['started_local'] = time.strftime('%H:%M:%S')
    await call_tool(APP + 'StartPIE')
    world = None
    for _ in range(40):
        world = game_world()
        if world and player(world)[0]:
            break
        await asyncio.sleep(0.5)
    await asyncio.sleep(2.0)
    world = game_world()
    f = flow_of(world)
    run.put(0, 'start_map', world.get_path_name())
    run.put(0, 'screen_at_play', str(f.get_screen()))
    run.put(0, 'has_checkpoint', safe(lambda: f.has_checkpoint()))
    await run.shot(0, '01-title')
    # The title menu: with a checkpoint the cursor starts on Continue, so New Game is one Down.
    if safe(lambda: f.has_checkpoint()) is True:
        cmd(world, 'GameFlow.Key Down')
        await asyncio.sleep(0.4)
    cmd(world, 'GameFlow.Key Enter')
    await asyncio.sleep(1.5)
    w2 = game_world()
    run.put(0, 'after_enter_world', w2.get_path_name() if w2 else None)
    run.put(0, 'after_enter_screen', safe(lambda: str(flow_of(w2).get_screen())))


async def s1(run):
    world = None
    for _ in range(50):
        world = game_world()
        if world and 'Lvl_MockCity' in world.get_path_name() and player(world)[1]:
            break
        await asyncio.sleep(0.5)
    run.put(1, 'map', world.get_path_name() if world else None)
    if not world or 'Lvl_MockCity' not in world.get_path_name():
        run.put(1, 'result', 'FAIL: New Game did not open Lvl_MockCity')
        return
    intro = await wait_cutscene_or(world, 6.0)
    run.put(1, 'intro_playing', intro)
    if intro:
        await asyncio.sleep(3.0)
        await run.shot(1, '02-intro')
        await skip_cutscene(world, run, 1, 'intro')
        await asyncio.sleep(2.0)
    pc, pawn = player(world)
    cam = unreal.GameplayStatics.get_player_camera_manager(world, 0)
    run.put(1, 'camera_above_hero_cm', round(cam.get_camera_location().z - pawn.get_actor_location().z))
    run.put(1, 'camera_dist_cm', round(dist(cam.get_camera_location(), pawn.get_actor_location())))
    run.put(1, 'state', state(world))
    run.put(1, 'tracker', tracker(world))
    run.put(1, 'villain', {'possession_running': safe(lambda: villain_of(world).is_possession_running())})
    run.put(1, 'pickups', {'coins': len(pickups(world, unreal.ReflectionsCoinPickup)), 'pages': len(pickups(world, unreal.ReflectionsBookPagePickup)),
                           'keys': len(pickups(world, unreal.ReflectionsKeyPickup)), 'doors': len(pickups(world, unreal.ReflectionsSealedDoor))})
    await asyncio.sleep(2.0)
    run.put(1, 'ring', ring(world))
    await run.shot(1, '03-giltside-start')


async def s2(run):
    world = game_world()
    pc, pawn = player(world)
    here = pawn.get_actor_location()
    legs = []
    for c in sorted(coins_on(world, GRAY, here, 4500.0), key=lambda c: dist(c.get_actor_location(), here))[:2]:
        legs.append(await walk_to(world, c.get_actor_location(), timeout=12.0, tol=90.0, label='Bell Lane shard'))
        await asyncio.sleep(0.5)
    run.put(2, 'shard_legs', legs)
    run.put(2, 'after_shards', state(world))
    q = quests_of(world)
    ilse = safe(lambda: q.find_person_actor('ilse_varrow'))
    if not ilse or isinstance(ilse, str):
        run.put(2, 'ilse', 'FAIL: FindPersonActor(ilse_varrow) found nobody (%s)' % ilse)
        return
    run.put(2, 'ilse_at', vec(ilse.get_actor_location()))
    pawn = player(world)[1]
    to = ilse.get_actor_location()
    toward = pawn.get_actor_location() - to
    toward.z = 0.0
    spot = to + toward * (220.0 / max(toward.length(), 1.0))
    run.put(2, 'walk_ilse', await walk_to(world, spot, timeout=28.0, tol=200.0, label='to Ilse on Lantern Row'))
    face(pc, pawn, ilse.get_actor_location(), pitch_bias=-6.0)
    await asyncio.sleep(0.3)
    run.put(2, 'dist_to_ilse_cm', round(dist(pawn.get_actor_location(), ilse.get_actor_location())))
    await key('E', 0.15)
    await asyncio.sleep(1.0)
    opened = q.is_talk_open()
    run.put(2, 'talk_open_after_E', opened)
    lines = [tracker(world)]
    if opened:
        await run.shot(2, '04-talk-ilse')
        for _ in range(10):
            if not q.is_talk_open():
                break
            if not q.advance_talk():
                q.choose_talk_option(0)
            await asyncio.sleep(0.7)
            lines.append(tracker(world))
    run.put(2, 'talk_ui', lines)
    run.put(2, 'talk_open_end', q.is_talk_open())
    if q.is_talk_open():
        q.close_talk()
    run.put(2, 'after_talk', state(world))


async def s3(run):
    world = game_world()
    pc, pawn = player(world)
    before = {a.get_name() for a, c in npcs(world)}
    cmd(world, 'Npc.Spawn Guard 1 400')
    await asyncio.sleep(1.5)
    new = [(a, c) for a, c in npcs(world) if a.get_name() not in before]
    run.put(3, 'spawned', [a.get_name() for a, c in new])
    if not new:
        run.put(3, 'result', 'FAIL: Npc.Spawn Guard made no NPC')
    else:
        guard, rc = new[0]
        mana0 = player(world)[1].get_component_by_class(unreal.ReflectionsSampleSpellDriver).get_mana()
        n = await cast_at(world, guard, casts=8, gap=1.1, until=lambda: rc.is_incapacitated())
        await asyncio.sleep(1.0)
        run.put(3, 'casts', n)
        run.put(3, 'mana_start', round(mana0, 1))
        run.put(3, 'guard_down', safe(lambda: rc.is_incapacitated()))
        await run.shot(3, '05-guard-spell-kill')
    run.put(3, 'tracker', tracker(world))
    r1 = ring(world)
    await asyncio.sleep(3.0)
    r2 = ring(world)
    run.put(3, 'ring', [r1, r2])
    run.put(3, 'state', state(world))


async def s4(run):
    world = game_world()
    pc, pawn = player(world)
    v = villain_of(world)
    host = safe(lambda: v.get_host())
    run.put(4, 'host_at_start', host.get_name() if host and not isinstance(host, str) else host)
    sq = unreal.Vector(SIDE_X[RED] - 6500.0, 1000.0, pawn.get_actor_location().z)
    run.put(4, 'walk_bell_square', await walk_to(world, sq, timeout=22.0, tol=400.0, label='to Bell Square (burning eyes)'))
    if await wait_cutscene_or(world, 3.0):
        await asyncio.sleep(1.5)
        await run.shot(4, '06-burning-eyes')
        await skip_cutscene(world, run, 4, 'burning eyes')
    host = safe(lambda: v.get_host())
    infected = [(a, c) for a, c in npcs(world) if a.get_component_by_class(unreal.ReflectionsVillainPossessionComponent)]
    run.put(4, 'host', host.get_name() if host and not isinstance(host, str) else host)
    run.put(4, 'possessed_npcs', [a.get_name() for a, c in infected])
    target = host if host and not isinstance(host, str) else (infected[0][0] if infected else None)
    if target:
        run.put(4, 'casts_at_host', await cast_at(world, target, casts=4, gap=1.2))
        await asyncio.sleep(1.0)
        if await wait_cutscene_or(world, 2.0):
            await skip_cutscene(world, run, 4, 'after cure')
    run.put(4, 'tarnish', state(world).get('tarnish'))
    run.put(4, 'tracker', tracker(world))


async def s5(run):
    world = game_world()
    pawn = player(world)[1]
    here = pawn.get_actor_location()
    gray = [c for c in coins_on(world, GRAY) if side_of_x(c.get_actor_location().x) == RED]
    run.put(5, 'gray_shards_in_giltside', [vec(c.get_actor_location()) for c in gray])
    legs = []
    for c in sorted(gray, key=lambda c: dist(c.get_actor_location(), here))[:2]:
        legs.append(await walk_to(world, c.get_actor_location(), timeout=12.0, tol=90.0, label='Pewterside shard in Giltside'))
        await asyncio.sleep(0.4)
    run.put(5, 'shard_legs', legs)
    run.put(5, 'coins_before_jump', state(world).get('coins'))
    ok = await hold_jump(world, run, 5, up=False)
    await run.shot(5, '07-pewterside')
    if not ok:
        return
    p = page_on(world, GRAY)
    run.put(5, 'page1_at', vec(p.get_actor_location()) if p else None)
    if p:
        run.put(5, 'walk_page1', await walk_to(world, p.get_actor_location(), timeout=32.0, tol=90.0, label='Weigh-House stair to roof page'))
        await asyncio.sleep(1.2)
        if await wait_cutscene_or(world, 1.5):
            await skip_cutscene(world, run, 5, 'page 1')
        pawn = player(world)[1]
        for c in coins_on(world, RED, pawn.get_actor_location(), 1500.0)[:1]:
            run.put(5, 'walk_roof_shard', await walk_to(world, c.get_actor_location(), timeout=8.0, tol=90.0, label='roof Giltside shard'))
        await run.shot(5, '08-weighhouse-roof')
    run.put(5, 'state', state(world))
    run.put(5, 'tracker', tracker(world))


async def s6(run):
    world = game_world()
    ok = await hold_jump(world, run, 6, up=True)
    if not ok:
        return
    pc, pawn = player(world)
    gate = unreal.Vector(SIDE_X[RED] + 14000.0, 3500.0, 100.0)
    k = pickups(world, unreal.ReflectionsKeyPickup)
    run.put(6, 'key_pickups', [vec(a.get_actor_location()) for a in k])
    target = k[0].get_actor_location() if k else gate
    run.put(6, 'walk_down_and_to_key', await walk_to(world, target, timeout=34.0, tol=90.0, label='Weigh-House roof -> Lantern Gate key'))
    await asyncio.sleep(1.0)
    infected = [a.get_name() for a, c in npcs(world) if a.get_component_by_class(unreal.ReflectionsVillainPossessionComponent)
                and dist(a.get_actor_location(), pawn.get_actor_location()) < 3000.0]
    run.put(6, 'tarnished_near_gate', infected)
    run.put(6, 'state', state(world))
    run.put(6, 'tracker', tracker(world))
    await run.shot(6, '09-lantern-gate-key')


async def s7(run):
    world = game_world()
    door = [d for d in pickups(world, unreal.ReflectionsSealedDoor) if side_of_x(d.get_actor_location().x) == RED]
    if not door:
        run.put(7, 'result', 'FAIL: no sealed door in Giltside')
        return
    d = door[0]
    run.put(7, 'door_at', vec(d.get_actor_location()))
    run.put(7, 'walk_door', await walk_to(world, d.get_actor_location(), timeout=30.0, tol=150.0, label='to the Gilt Tower door'))
    await asyncio.sleep(1.5)
    run.put(7, 'door_open', d.is_open())
    if await wait_cutscene_or(world, 1.5):
        await asyncio.sleep(1.0)
        await run.shot(7, '10-gilt-tower-cutscene')
        await skip_cutscene(world, run, 7, 'gilt tower')
    p = page_on(world, RED)
    if p:
        run.put(7, 'walk_page2', await walk_to(world, p.get_actor_location(), timeout=14.0, tol=90.0, label='inside the Gilt Tower to page 2'))
        await asyncio.sleep(1.2)
        if await wait_cutscene_or(world, 1.5):
            await skip_cutscene(world, run, 7, 'page 2')
    pawn = player(world)[1]
    for c in coins_on(world, WHITE, pawn.get_actor_location(), 1500.0)[:1]:
        run.put(7, 'walk_frost_shard', await walk_to(world, c.get_actor_location(), timeout=8.0, tol=90.0, label='Frostside shard in the tower'))
    run.put(7, 'state', state(world))
    run.put(7, 'tracker', tracker(world))
    await run.shot(7, '11-inside-gilt-tower')


async def s8(run):
    world = game_world()
    ok = await hold_jump(world, run, 8, up=True)
    await asyncio.sleep(0.5)
    await run.shot(8, '12-frost-tower-inside')
    if not ok:
        return
    p = page_on(world, WHITE)
    if p:
        run.put(8, 'walk_page3', await walk_to(world, p.get_actor_location(), timeout=12.0, tol=90.0, label='inside the Frost Tower to page 3'))
    await asyncio.sleep(1.5)
    if await wait_cutscene_or(world, 2.0):
        await asyncio.sleep(1.5)
        await run.shot(8, '13-mirror-whole')
        await skip_cutscene(world, run, 8, 'mirror whole')
    await asyncio.sleep(1.0)
    pawn = player(world)[1]
    bosses = pickups(world, unreal.ReflectionsVillainBoss)
    run.put(8, 'final_spell_given', bool(pawn.get_component_by_class(unreal.ReflectionsFinalSpellComponent)))
    run.put(8, 'boss', [(b.get_name(), vec(b.get_actor_location()), str(b.get_boss_state())) for b in bosses])
    run.put(8, 'state', state(world))
    run.put(8, 'tracker', tracker(world))


async def s9(run):
    world = game_world()
    run.put(9, 'walk_ramps', await walk_to(world, RAMP_EXIT, timeout=40.0, tol=250.0, label='Frost Tower ramps to the crown'))
    await asyncio.sleep(2.5)
    pc, pawn = player(world)
    bosses = pickups(world, unreal.ReflectionsVillainBoss)
    if bosses:
        face(pc, pawn, bosses[0].get_actor_location(), pitch_bias=2.0)
        run.put(9, 'boss_state', str(bosses[0].get_boss_state()))
        run.put(9, 'boss_health', bosses[0].get_health())
    await asyncio.sleep(0.5)
    await run.shot(9, '14-crown-boss')
    run.put(9, 'state', state(world))
    run.put(9, 'tracker', tracker(world))


async def s10(run):
    world = game_world()
    pc, pawn = player(world)
    bosses = pickups(world, unreal.ReflectionsVillainBoss)
    flow = flow_of(world)
    if bosses:
        b = bosses[0]
        presses, t0, hp = 0, time.time(), []
        while unreal.SystemLibrary.is_valid(b) and b.get_health() > 0.0 and time.time() - t0 < 38.0:
            face(pc, pawn, b.get_actor_location())
            await key('F', 0.12)
            presses += 1
            await asyncio.sleep(0.9)
            hp.append(round(b.get_health()) if unreal.SystemLibrary.is_valid(b) else 0)
            if presses == 2:
                await run.shot(10, '15-final-spell')
            if health_of(player(world)[1]) == 0:
                break
        run.put(10, 'f_presses', presses)
        run.put(10, 'boss_health_trace', hp)
        run.put(10, 'hero_health', health_of(player(world)[1]))
    for _ in range(30):
        await asyncio.sleep(0.5)
        cs = cutscenes_of(world)
        if (cs and cs.is_cutscene_playing()) or flow.is_victory():
            break
    await asyncio.sleep(1.0)
    await run.shot(10, '16-ending')
    await skip_cutscene(world, run, 10, 'ending')
    for _ in range(16):
        if flow.is_victory():
            break
        await asyncio.sleep(0.5)
    run.put(10, 'victory', flow.is_victory())
    run.put(10, 'screen', str(flow.get_screen()))
    run.put(10, 'tracker', tracker(world))
    await run.shot(10, '17-victory')


async def stop(run):
    if await call_tool(APP + 'IsPIERunning'):
        d = lock_data()
        if d and d.get('owner') == ME:
            await call_tool(APP + 'StopPIE')
            run.report['stopped_local'] = time.strftime('%H:%M:%S')
    for c in ('GameFlow.TitleInPIE 0', 'Cutscene.IntroInPIE 0'):
        unreal.SystemLibrary.execute_console_command(None, c)
    release_lock()


async def f0(run):
    """Finale re-run: Play -> title -> Continue (the last checkpoint, page 3 inside the Frost Tower)."""
    busy = lock_busy()
    if busy:
        raise RuntimeError('PIE lock held by %s' % busy)
    if await call_tool(APP + 'IsPIERunning'):
        raise RuntimeError('PIE is already running (someone else?)')
    write_lock('Row 5 (part 2): finale re-run from the page-3 checkpoint via Continue (<3 min)')
    unreal.SystemLibrary.execute_console_command(None, 'GameFlow.TitleInPIE 1')
    unreal.SystemLibrary.execute_console_command(None, 'Cutscene.IntroInPIE 0')
    run.report['finale_started_local'] = time.strftime('%H:%M:%S')
    await call_tool(APP + 'StartPIE')
    world = None
    for _ in range(40):
        world = game_world()
        if world and player(world)[0]:
            break
        await asyncio.sleep(0.5)
    await asyncio.sleep(2.0)
    world = game_world()
    f = flow_of(world)
    run.put('f0', 'screen', str(f.get_screen()))
    run.put('f0', 'has_checkpoint', safe(lambda: f.has_checkpoint()))
    cmd(world, 'GameFlow.Key Enter')   # Continue is the first item when a checkpoint exists
    await asyncio.sleep(1.5)
    w2 = game_world()
    run.put('f0', 'after_enter_world', w2.get_path_name() if w2 else None)


async def f1(run):
    world = None
    for _ in range(50):
        world = game_world()
        if world and 'Lvl_MockCity' in world.get_path_name() and player(world)[1]:
            break
        await asyncio.sleep(0.5)
    run.put('f1', 'map', world.get_path_name() if world else None)
    if not world or 'Lvl_MockCity' not in world.get_path_name():
        return
    await asyncio.sleep(1.5)
    await skip_cutscene(world, run, 'f1', 'continue')
    run.put('f1', 'restored', state(world))
    pc, pawn = player(world)
    # Heal up the way a player would: spell 1 (Healing), cast, then back to Fire Bolt.
    await key('One', 0.1)
    heals = []
    for _ in range(3):
        await key('LeftMouseButton', 0.25)
        await asyncio.sleep(1.3)
        heals.append(health_of(player(world)[1]))
    await key('Four', 0.1)
    run.put('f1', 'health_after_heals', heals)
    run.put('f1', 'walk_ramps', await walk_to(world, RAMP_EXIT, timeout=40.0, tol=250.0, label='Frost Tower ramps to the crown (re-run)'))
    await asyncio.sleep(2.0)
    bosses = pickups(world, unreal.ReflectionsVillainBoss)
    run.put('f1', 'boss', [(b.get_name(), str(b.get_boss_state()), round(b.get_health())) for b in bosses])
    run.put('f1', 'state', state(world))


async def f2(run):
    if 'step10' in run.report and 'step10_run1' not in run.report:
        run.report['step10_run1'] = run.report.pop('step10')
    await s10(run)
    run.report['finale_step'] = run.report.pop('step10', None)
    await stop(run)


STEPS = [s0, s1, s2, s3, s4, s5, s6, s7, s8, s9, s10]
FINALE = {'f0': f0, 'f1': f1, 'f2': f2}


async def step(n):
    run = Run()
    if n != 0:
        renew_lock()
    try:
        if n == 'stop':
            await stop(run)
        elif n in FINALE:
            if n != 'f0':
                d = lock_data()
                if not d or d.get('owner') != ME:
                    raise RuntimeError('I do not hold the PIE lock; not touching PIE')
            await FINALE[n](run)
        else:
            if n != 0:
                d = lock_data()
                if not d or d.get('owner') != ME:
                    raise RuntimeError('I do not hold the PIE lock; not touching PIE')
            await STEPS[n](run)
            if n == len(STEPS) - 1:
                await stop(run)
    except Exception:
        import traceback
        run.report['error_step%s' % n] = traceback.format_exc()[-1500:]
    run.save()
    out = run.report.get('finale_step' if n == 'f2' else ('step%s' % n), {})
    if 'error_step%s' % n in run.report:
        out = dict(out, error=run.report['error_step%s' % n])
    return out
