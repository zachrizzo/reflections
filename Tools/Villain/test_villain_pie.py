"""PIE test for the villain, in short steps (each MCP call stays well under its timeout; state goes through a JSON file).

    ns = dict(globals()); exec(compile(src, 'test_villain_pie.py', 'exec'), ns); result = await ns['step']('possession', 1)

Stages and steps:
  possession 1  wait for a free PIE, open Lvl_WorldJumpTest, spawn test hosts, he takes a first host
  possession 2  he spreads (infected veins), is forced out (burnout) and hops to a second host
  possession 3  a natural burnout and a third host; stop PIE
  finale 1      wait for a free PIE, open the map, raise his true form (Villain.BossHere), manifest shots
  finale 2      watch the attacks (telegraphs, orbs, circles, wave)
  finale 3      ordinary spells barely hurt him; Final Spell until he dies; death + victory; stop PIE
  arena 1..3    same as finale but through Villain.Finale (the mirror-complete path and its arena fallback)
Each step writes Saved/VillainTest/<stage>/report.json (merged) and PNGs. `step(stage, 'stop')` always stops PIE.
"""
import base64
import json
import math
from pathlib import Path

APP = 'EditorToolset.EditorAppToolset.'
TEST_MAP = '/Game/Worlds/Test/Lvl_WorldJumpTest'
ROOT = Path(unreal.Paths.project_saved_dir()).resolve() / 'VillainTest'

LOCK = Path(unreal.Paths.project_saved_dir()).resolve() / 'PIE_LOCK.json'
ME = 'villain-finale-391eac'


def lock_holder():
    """(owner, expires) of a live lock held by someone else, else None."""
    import time
    try:
        data = json.loads(LOCK.read_text())
    except Exception:
        return None
    if data.get('owner') != ME and float(data.get('expires_epoch', 0)) > time.time():
        return data.get('owner'), data.get('expires_local')
    return None


def write_lock(purpose):
    import time
    now = time.time()
    LOCK.write_text(json.dumps({'owner': ME, 'purpose': purpose, 'acquired_epoch': int(now),
                                'expires_epoch': int(now + 240), 'expires_local': time.strftime('%H:%M:%S', time.localtime(now + 240))}, indent=2))


def refresh_lock():
    """Keeps my lock alive across the steps of one run (never more than now + 240 s)."""
    import time
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


def villain(world):
    return unreal.get_world_subsystem(world, unreal.ReflectionsVillainSubsystem)


def player(world):
    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    return pc, (pc.get_controlled_pawn() if pc else None)


def face(pc, pawn, target, pitch_bias=-4.0, yaw_offset=0.0):
    d = target - pawn.get_actor_location()
    yaw = math.degrees(math.atan2(d.y, d.x)) + yaw_offset
    pitch = math.degrees(math.atan2(d.z + 30.0, math.hypot(d.x, d.y))) + pitch_bias
    pc.set_control_rotation(unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw))


def host_name(world):
    h = villain(world).get_host()
    return h.get_name() if h else None


def boss(world):
    found = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsVillainBoss)
    return found[0] if found else None


class Run:
    def __init__(self, stage):
        self.out = ROOT / stage
        self.out.mkdir(parents=True, exist_ok=True)
        self.path = self.out / 'report.json'
        self.report = json.loads(self.path.read_text()) if self.path.exists() else {}

    def save(self):
        self.path.write_text(json.dumps(self.report, indent=2, default=str))

    async def shot(self, name):
        r = await call_tool('SceneCaptureToolset.SceneCaptureToolset.CaptureGameViewport', world=None, maxResolution=1600)
        data = r['image']
        if data is not None and not isinstance(data, str):
            data = data['data']
        if not data or str(data).startswith('urn:'):
            return None
        path = self.out / (name + '.png')
        path.write_bytes(base64.b64decode(data))
        self.report.setdefault('screenshots', []).append(str(path))
        return str(path)


async def start(run, max_wait=45.0):
    """Shared PIE etiquette: honour Saved/PIE_LOCK.json, take it (240 s), and only then start PIE."""
    waited = 0.0
    while True:
        holder = lock_holder()
        if holder is None and not await call_tool(APP + 'IsPIERunning'):
            write_lock('villain possession + finale test (one run)')
            try:
                await call_tool(APP + 'StartPIE')
                break
            except Exception:
                release_lock()
        await asyncio.sleep(5.0)
        waited += 5.0
        if waited > max_wait:
            raise RuntimeError('PIE busy or locked (%s); run this step again later.' % (holder,))
    # The PIE world only exists a few frames after StartPIE returns: wait for it (and its pawn) before 'open',
    # or the command goes nowhere and the test runs on the editor's map.
    for _ in range(40):
        world = game_world()
        if world and player(world)[1]:
            break
        await asyncio.sleep(0.5)
    for attempt in range(2):
        cmd(game_world(), 'open ' + TEST_MAP)
        for _ in range(40):
            await asyncio.sleep(0.5)
            world = game_world()
            if world and 'Lvl_WorldJumpTest' in world.get_path_name() and player(world)[1]:
                break
        if world and 'Lvl_WorldJumpTest' in world.get_path_name():
            break
    await asyncio.sleep(2.5)
    world = game_world()
    pc, pawn = player(world)
    run.report = {'map': world.get_path_name(), 'pawn': pawn.get_class().get_name() if pawn else None}
    return world


async def stop(run):
    # Never stop a PIE that runs under someone else's live lock (a failed start must not end another session's run).
    holder = lock_holder()
    if holder is not None:
        run.report['stopped'] = 'not mine: %s holds the lock' % (holder,)
        return
    if await call_tool(APP + 'IsPIERunning'):
        world = game_world()
        if world and any(m in world.get_path_name() for m in ('Lvl_WorldJumpTest', 'Lvl_HeroSampleCrowd', 'Lvl_MockCity')):
            cmd(world, 'Villain.Status')
            await call_tool(APP + 'StopPIE')
            run.report['stopped'] = True
        else:
            run.report['stopped'] = 'not my PIE world: %s' % (world.get_path_name() if world else None)
    release_lock()


def mine(world):
    if not world or 'Lvl_WorldJumpTest' not in world.get_path_name():
        raise RuntimeError('The running PIE is not this test (world %s).' % (world.get_path_name() if world else None))


# ----------------------------------------------------------------------------------------------- possession

async def possession(run, n):
    if n == 1:
        world = await start(run)
        pc, pawn = player(world)
        cmd(world, 'Villain.InfectInterval 5')
        cmd(world, 'Villain.HostLifetime 14')
        cmd(world, 'Villain.RangedSpread 1')  # test hosts have no NPC hunt, so let hosts spread at range
        cmd(world, 'Villain.SpawnTestHosts 8')
        await asyncio.sleep(1.0)
        run.report['test_hosts'] = len(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsVillainTestHost))
        cmd(world, 'Villain.Hop')
        await asyncio.sleep(1.0)
        wisps = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsVillainWisp)
        if wisps:
            face(pc, pawn, wisps[0].get_actor_location())
        await run.shot('1_arrival_wisp')
        for _ in range(24):
            await asyncio.sleep(0.25)
            if villain(world).get_host():
                break
        run.report['hosts_seen'] = [host_name(world)]
        if villain(world).get_host():
            face(pc, pawn, villain(world).get_host().get_actor_location())
            await asyncio.sleep(0.4)
            await run.shot('2_host_tell')
        return
    world = game_world()
    mine(world)
    pc, pawn = player(world)
    v = villain(world)
    if n == 2:
        await asyncio.sleep(3.0)
        run.report['infected_after_spread'] = v.get_infected_count()
        for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsVillainTestHost):
            c = a.get_component_by_class(unreal.ReflectionsVillainPossessionComponent)
            if c and c.get_state() == unreal.ReflectionsVillainInfection.INFECTED:
                face(pc, pawn, a.get_actor_location())
                await asyncio.sleep(0.3)
                await run.shot('3_infected_veins')
                break
        old = v.get_host()
        cmd(world, 'Villain.Hop')
        await asyncio.sleep(0.35)
        if old:
            face(pc, pawn, old.get_actor_location())
        await run.shot('4_burnout')
        await asyncio.sleep(0.5)
        wisps = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsVillainWisp)
        if wisps:
            face(pc, pawn, wisps[0].get_actor_location())
            await run.shot('5_hop_wisp')
        first = run.report.get('hosts_seen', [None])[0]
        for _ in range(24):
            await asyncio.sleep(0.25)
            if host_name(world) and host_name(world) != first:
                break
        run.report['hosts_seen'].append(host_name(world))
        if v.get_host():
            face(pc, pawn, v.get_host().get_actor_location())
            await asyncio.sleep(0.4)
            await run.shot('6_new_host')
    elif n == 3:
        seen = run.report.get('hosts_seen', [])
        for _ in range(50):
            await asyncio.sleep(0.5)
            if host_name(world) and host_name(world) not in seen:
                seen.append(host_name(world))
                break
        run.report['hosts_seen'] = seen
        run.report['hopped_between_hosts'] = len(set(s for s in seen if s)) >= 2
        run.report['infected_final'] = v.get_infected_count()
        if v.get_host():
            face(pc, pawn, v.get_host().get_actor_location())
            await asyncio.sleep(0.4)
            await run.shot('7_third_host')


async def conversion(run):
    """Villain.Convert on the test hosts: tackle, pinned + wisp, turned. Runs inside the possession PIE session."""
    world = game_world()
    mine(world)
    pc, pawn = player(world)
    cmd(world, 'Villain.Stop')
    cmd(world, 'Villain.Convert')
    await asyncio.sleep(0.2)
    convs = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsVillainConversion)
    run.report['conversion_started'] = bool(convs)
    if not convs:
        return
    c = convs[0]
    attacker, victim = c.get_owner(), None
    for label, wait in (('8_tackle', 0.5), ('9_tackle_hit', 0.7), ('10_pinned_wisp', 0.9), ('11_wisp_enters', 0.6), ('12_turned_rising', 1.4), ('13_turned', 2.0)):
        await asyncio.sleep(wait)
        if unreal.SystemLibrary.is_valid(c):
            face(pc, pawn, c.get_actor_location(), pitch_bias=-8.0)
        await run.shot(label)
    hosts = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsVillainTestHost)
    run.report['infected_after_conversion'] = villain(world).get_infected_count()
    run.report['conversion_states'] = [str(h.get_component_by_class(unreal.ReflectionsVillainPossessionComponent).get_state())
                                       for h in hosts if h.get_component_by_class(unreal.ReflectionsVillainPossessionComponent)]


async def crowd_conversion(run, n):
    """Real NPCs: open the crowd map, convert the clean NPC nearest the player, capture each step."""
    if n == 1:
        world = game_world()
        if not world or 'Lvl_' not in world.get_path_name():
            world = await start(run)
        cmd(world, 'open /Game/Characters/Hero/Sample/Lvl_HeroSampleCrowd')
        for _ in range(60):
            await asyncio.sleep(0.5)
            w = game_world()
            if w and 'Lvl_HeroSampleCrowd' in w.get_path_name():
                pc, pawn = player(w)
                if pawn:
                    break
        await asyncio.sleep(3.0)
        world = game_world()
        run.report['crowd_map'] = world.get_path_name()
        return
    world = game_world()
    pc, pawn = player(world)
    cmd(world, 'Villain.RangedSpread 0')
    cmd(world, 'Villain.Convert')
    await asyncio.sleep(0.15)
    convs = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsVillainConversion)
    run.report['conversion_started'] = bool(convs)
    if not convs:
        await stop(run)
        return
    c = convs[0]
    vic = c.get_editor_property('root_component')
    for label, wait in (('1_tackle_start', 0.3), ('2_tackle_contact', 0.7), ('3_pinned_kneel', 0.6), ('4_wisp', 0.5), ('5_wisp_enters_wrench', 0.6),
                        ('6_turned_convulsing', 1.2), ('7_rising', 1.3), ('8_risen_tarnished', 2.6)):
        await asyncio.sleep(wait)
        if unreal.SystemLibrary.is_valid(c):
            face(pc, pawn, c.get_actor_location(), pitch_bias=-10.0, yaw_offset=10.0)
        await run.shot(label)
    run.report['infected_after'] = villain(world).get_infected_count()
    await stop(run)


# ----------------------------------------------------------------------------------------------- finale

async def finale(run, n, via_arena):
    if n == 1:
        world = game_world()
        if world and 'Lvl_WorldJumpTest' in world.get_path_name():
            run.report = {'map': world.get_path_name(), 'reused_pie': True}
            cmd(world, 'Villain.CleanseAll')
            cmd(world, 'Villain.Stop')
        else:
            world = await start(run)
        pc, pawn = player(world)
        cmd(world, 'Villain.BossHealth 500')
        cmd(world, 'Villain.FinalSpellMana 8')
        cmd(world, 'Villain.FinalSpellCooldown 1.0')
        cmd(world, 'Villain.AttackDamageScale 0.25')
        if via_arena:
            jump = unreal.get_game_instance_subsystem(unreal.GameplayStatics.get_game_instance(world), unreal.ReflectionsWorldJumpSubsystem)
            for page in ('GrayHighSpotPage', 'RedTowerPage', 'WhiteTowerPage'):
                jump.add_page(page)
            run.report['book_complete'] = jump.is_book_complete()
        else:
            cmd(world, 'Villain.BossHere')
        await asyncio.sleep(0.8)
        b = boss(world)
        run.report['boss_spawned'] = bool(b)
        if not b:
            return
        run.report['boss_spawn_location'] = str(b.get_actor_location())
        if via_arena:
            # Put the hero where the last page was (the test is the fight, not the climb).
            pawn.teleport(b.get_actor_location() + unreal.Vector(-150.0, 0.0, -40.0), unreal.Rotator(0.0, 0.0, 0.0))
            await asyncio.sleep(0.5)
        face(pc, pawn, b.get_actor_location())
        await asyncio.sleep(1.4)
        face(pc, pawn, b.get_actor_location(), yaw_offset=12.0)
        await run.shot('1_manifest')
        await asyncio.sleep(3.2)
        face(pc, pawn, b.get_actor_location(), yaw_offset=12.0)
        await run.shot('2_true_form')
        run.report['state_after_manifest'] = str(b.get_boss_state())
        run.report['boss_location'] = str(b.get_actor_location())
        run.report['player_to_boss_cm'] = round((pawn.get_actor_location() - b.get_actor_location()).length())
        run.report['finale'] = villain(world).is_finale()
        cmd(world, 'Villain.Status')
        return
    world = game_world()
    mine(world)
    pc, pawn = player(world)
    b = boss(world)
    if not b:
        run.report['error_step_%d' % n] = 'no boss'
        await stop(run)
        return
    if n == 2:
        for i in range(10):
            await asyncio.sleep(1.1)
            face(pc, pawn, b.get_actor_location(), pitch_bias=-16.0, yaw_offset=12.0)
            await run.shot('3_attack_%d' % i)
        run.report['hero_health_component'] = str(pawn.get_component_by_class(unreal.ReflectionsHealthComponent).get_editor_property('health')) \
            if pawn.get_component_by_class(unreal.ReflectionsHealthComponent) else None
    elif n == 3:
        driver = pawn.get_component_by_class(unreal.ReflectionsSampleSpellDriver)
        h0 = b.get_health()
        if driver:
            driver.set_selected_spell(unreal.HeroSpell.FIRE)
            for _ in range(3):
                face(pc, pawn, b.get_actor_location())
                driver.cast_selected_spell()
                await asyncio.sleep(1.1)
        run.report['ordinary_spell_damage'] = h0 - b.get_health()
        final = pawn.get_component_by_class(unreal.ReflectionsFinalSpellComponent)
        run.report['final_spell_component'] = bool(final)
        casts, hits, t = 0, [], 0.0
        while final and b.get_health() > 0.0 and t < 30.0:
            face(pc, pawn, b.get_actor_location())
            before = b.get_health()
            if final.cast_final_spell():
                casts += 1
                await asyncio.sleep(0.45)
                if casts <= 2:
                    await run.shot('4_final_spell_%d' % casts)
                await asyncio.sleep(0.6)
                hits.append(before - b.get_health())
                t += 1.05
            else:
                await asyncio.sleep(0.4)
                t += 0.4
        run.report['final_casts'] = casts
        run.report['final_hits'] = hits
        run.report['boss_health_end'] = b.get_health()
        await asyncio.sleep(1.2)
        if unreal.SystemLibrary.is_valid(b):
            face(pc, pawn, b.get_actor_location())
        await run.shot('5_death')
        await asyncio.sleep(3.8)
        await run.shot('6_victory')
        run.report['boss_state_end'] = str(b.get_boss_state()) if unreal.SystemLibrary.is_valid(b) else 'destroyed'
        run.report['victory'] = villain(world).is_finale()
        if not via_arena:
            await stop(run)


# ----------------------------------------------------------------------------------------------- last slot (look pass)

async def start_here(run, purpose):
    """Start PIE on whatever map the editor has open (no 'open': it only lands after the Python call returns)."""
    holder = lock_holder()
    if holder is not None or await call_tool(APP + 'IsPIERunning'):
        raise RuntimeError('PIE busy or locked (%s)' % (holder,))
    write_lock(purpose)
    await call_tool(APP + 'StartPIE')
    world = None
    for _ in range(30):
        world = game_world()
        if world and player(world)[1]:
            break
        await asyncio.sleep(0.5)
    run.report = {'map': world.get_path_name()}
    # The intro cutscene plays even with Cutscene.IntroInPIE 0: skip it (twice, per packaging's playtest notes).
    await asyncio.sleep(0.8)
    cmd(world, 'Cutscene.Skip')
    await asyncio.sleep(0.6)
    cmd(world, 'Cutscene.Skip')
    return world


def tarnished_near(world, where, radius=1500.0):
    out = []
    for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
        c = a.get_component_by_class(unreal.ReflectionsVillainPossessionComponent)
        if c and (a.get_actor_location() - where).length() < radius:
            out.append(a)
    return out


def stand_beside(pawn, target, distance, side=1.0, anchor=None):
    """Teleport the hero `distance` cm from target, back along the line towards `anchor` (default: where the hero
    stands now) and slightly to one side, but only onto ground a downward trace finds (the crowd map is a platform
    with a sheer edge: an unchecked spot drops the hero into the void)."""
    origin = anchor if anchor is not None else pawn.get_actor_location()
    d = origin - target
    d.z = 0.0
    span = d.length()
    d = d.normal() if span > 1.0 else unreal.Vector(-1.0, 0.0, 0.0)
    perp = unreal.Vector(-d.y * side, d.x * side, 0.0)
    world = pawn.get_world()
    for dist in (distance, distance * 0.75, distance * 0.5, 350.0):
        if span > 300.0:
            dist = min(dist, max(span - 50.0, 250.0))
        spot = target + (d + perp * 0.25).normal() * dist
        start = unreal.Vector(spot.x, spot.y, target.z + 400.0)
        end = unreal.Vector(spot.x, spot.y, target.z - 600.0)
        hit = unreal.SystemLibrary.line_trace_single(world, start, end, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [pawn],
                                                     unreal.DrawDebugTrace.NONE, True)
        if hit:
            t = hit.to_tuple()
            if t[0]:
                ground = t[4]
                pawn.teleport(unreal.Vector(spot.x, spot.y, ground.z + 100.0), unreal.Rotator(0.0, 0.0, 0.0))
                return dist
    return None


async def last_slot(run, n):
    if n == 1:  # close conversion on MetaHumans
        world = await start_here(run, 'villain look-pass + close conversion shots (one run)')
        pc, pawn = player(world)
        await asyncio.sleep(2.0)
        cmd(world, 'Villain.RangedSpread 0')
        cmd(world, 'Villain.Convert')
        await asyncio.sleep(0.1)
        convs = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsVillainConversion)
        run.report['conversion_started'] = bool(convs)
        if not convs:
            return
        c = convs[0]
        where = c.get_actor_location()
        run.report['conversion_at'] = str(where)
        stand_beside(pawn, where, 430.0)
        for label, wait in (('c1_tackle', 0.35), ('c2_contact', 0.7), ('c3_pinned', 0.6), ('c4_wisp', 0.5), ('c5_wrench', 0.6),
                            ('c6_turned', 1.2), ('c7_rising', 1.3), ('c8_risen', 1.6)):
            await asyncio.sleep(wait)
            if unreal.SystemLibrary.is_valid(c):
                where = c.get_actor_location()
            face(pc, pawn, where, pitch_bias=-14.0, yaw_offset=8.0)
            await run.shot(label)
        run.report['conversion_end_at'] = str(where)
        run.report['infected_after'] = villain(world).get_infected_count()
        return
    if n == 3 and not await call_tool(APP + 'IsPIERunning'):
        await start_here(run, 'villain slot 15: after-look true form + Final Spell kill (one run)')
        await asyncio.sleep(1.0)
    world = game_world()
    pc, pawn = player(world)
    if n == 2:  # black eyes close-up on a freshly tarnished MetaHuman
        import ast
        where = run.report.get('conversion_end_at')
        near = tarnished_near(world, pawn.get_actor_location(), 3000.0)
        run.report['tarnished_near'] = [a.get_name() for a in near]
        if not near:
            return
        t = min(near, key=lambda a: (a.get_actor_location() - pawn.get_actor_location()).length())
        for i in range(2):
            stand_beside(pawn, t.get_actor_location(), 200.0, side=-1.0)
            await asyncio.sleep(0.15)
            face(pc, pawn, t.get_actor_location() + unreal.Vector(0.0, 0.0, 70.0), pitch_bias=0.0, yaw_offset=4.0)
            await run.shot('e%d_eyes_close' % (i + 1))
            await asyncio.sleep(0.8)
        return
    if n == 3:  # the after-pass true form, close and far
        for c in ('Villain.BossHealth 500', 'Villain.FinalSpellMana 8', 'Villain.FinalSpellCooldown 1.0', 'Villain.AttackDamageScale 0.1'):
            cmd(world, c)
        jump = unreal.get_game_instance_subsystem(unreal.GameplayStatics.get_game_instance(world), unreal.ReflectionsWorldJumpSubsystem)
        for page in ('GrayHighSpotPage', 'RedTowerPage', 'WhiteTowerPage'):
            jump.add_page(page)
        run.report['book_complete'] = jump.is_book_complete()
        await asyncio.sleep(1.5)
        run.report['mirror_cutscene_seen'] = True
        await run.shot('t0_mirror_whole_cutscene')
        cmd(world, 'Cutscene.Skip')
        await asyncio.sleep(0.6)
        cmd(world, 'Cutscene.Skip')
        await asyncio.sleep(0.8)
        b = boss(world)
        run.report['boss'] = bool(b)
        if not b:
            return
        home = pawn.get_actor_location()
        run.report['home'] = [home.x, home.y, home.z]
        stand_beside(pawn, b.get_actor_location(), 600.0, anchor=home)
        await asyncio.sleep(3.2)
        placed = {}
        for label, dist in (('t1_after_close', 520.0), ('t2_after_mid', 900.0), ('t3_after_far', 1300.0)):
            placed[label] = stand_beside(pawn, b.get_actor_location(), dist, anchor=home)
            await asyncio.sleep(0.25)
            face(pc, pawn, b.get_actor_location(), pitch_bias=4.0, yaw_offset=9.0)
            await run.shot(label)
            await asyncio.sleep(0.9)
        run.report['placed'] = placed
        run.report['boss_state'] = str(b.get_boss_state())
        stand_beside(pawn, b.get_actor_location(), 700.0, anchor=home)
        return
    if n == 4:  # Final Spell to death and victory, then stop PIE
        b = boss(world)
        final = pawn.get_component_by_class(unreal.ReflectionsFinalSpellComponent)
        casts, t = 0, 0.0
        while final and b and unreal.SystemLibrary.is_valid(b) and b.get_health() > 0.0 and t < 14.0:
            face(pc, pawn, b.get_actor_location())
            if final.cast_final_spell():
                casts += 1
                await asyncio.sleep(0.45)
                if casts == 1:
                    await run.shot('t4_final_spell_hit')
                await asyncio.sleep(0.6)
                t += 1.05
            else:
                await asyncio.sleep(0.4)
                t += 0.4
        run.report['final_casts'] = casts
        run.report['boss_health_end'] = b.get_health() if b and unreal.SystemLibrary.is_valid(b) else 0.0
        run.report['boss_state_end'] = str(b.get_boss_state()) if b and unreal.SystemLibrary.is_valid(b) else 'destroyed'
        await asyncio.sleep(3.5)
        await run.shot('t5_ending_cutscene')
        cmd(world, 'Cutscene.Skip')
        await asyncio.sleep(0.6)
        cmd(world, 'Cutscene.Skip')
        await asyncio.sleep(2.5)
        await run.shot('t6_victory')
        run.report['finale_flag'] = villain(world).is_finale()
        await stop(run)


# ----------------------------------------------------------------------------------------------- Frost Tower crown (mock city)

MOCK_CITY = '/Game/MockCity/Lvl_MockCity'
CROWN = unreal.Vector(301300.0, 7000.0, 2400.0)         # VillainArena_FrostCrown (world-jump, Lvl_MockCity_Frostside)
RAMP_EXIT = unreal.Vector(300800.0, 7800.0, 2500.0)   # on the crown, ~9.4 m from centre (world-jump's tested spot)
TOWER_INSIDE = unreal.Vector(300000.0, 7000.0, 100.0)  # inside the Frost Tower, 23 m below the crown


async def skip_cutscenes(world):
    cmd(world, 'Cutscene.Skip')
    await asyncio.sleep(0.6)
    cmd(world, 'Cutscene.Skip')


async def tower(run, n):
    if n == 0:  # start PIE and travel (the travel only lands after this call returns)
        world = await start_here(run, 'villain slot 6: Frost Tower crown finale (one run)')
        cmd(world, 'open ' + MOCK_CITY)
        run.report['open_sent'] = True
        return
    world = game_world()
    if n == 1:
        for _ in range(40):
            world = game_world()
            if world and 'Lvl_MockCity' in world.get_path_name() and player(world)[1]:
                break
            await asyncio.sleep(0.5)
        run.report['map'] = world.get_path_name() if world else None
        if not world or 'Lvl_MockCity' not in world.get_path_name():
            return
        await asyncio.sleep(1.5)
        await skip_cutscenes(world)
        pc, pawn = player(world)
        for c in ('Villain.BossHealth 500', 'Villain.FinalSpellMana 8', 'Villain.FinalSpellCooldown 1.0', 'Villain.AttackDamageScale 0.1'):
            cmd(world, c)
        markers = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsVillainArena)
        run.report['arena_markers'] = [(m.get_name(), str(m.get_actor_location())) for m in markers]
        jump = unreal.get_game_instance_subsystem(unreal.GameplayStatics.get_game_instance(world), unreal.ReflectionsWorldJumpSubsystem)
        for page in ('GrayHighSpotPage', 'RedTowerPage', 'WhiteTowerPage'):
            jump.add_page(page)
        run.report['book_complete'] = jump.is_book_complete()
        if not run.report['book_complete']:
            cmd(world, 'Villain.Finale')
            run.report['used_villain_finale'] = True
        await asyncio.sleep(1.5)
        await skip_cutscenes(world)
        await asyncio.sleep(0.8)
        b = boss(world)
        run.report['boss'] = bool(b)
        if not b:
            return
        run.report['boss_at'] = str(b.get_actor_location())
        run.report['boss_from_crown_cm'] = round((b.get_actor_location() - CROWN).length())
        # Inside the tower, 23 m below: he must stay dormant.
        pawn.teleport(TOWER_INSIDE, unreal.Rotator(0.0, 0.0, 0.0))
        await asyncio.sleep(1.2)
        run.report['state_inside_tower'] = str(b.get_boss_state())
        # Arrive the way a player does: at the top of the ramps.
        pawn.teleport(RAMP_EXIT, unreal.Rotator(0.0, 0.0, 0.0))
        await asyncio.sleep(0.4)
        run.report['state_on_arrival'] = str(b.get_boss_state())
        face(pc, pawn, b.get_actor_location(), pitch_bias=2.0, yaw_offset=9.0)
        await run.shot('k1_arrival')
        await asyncio.sleep(2.6)
        home = pawn.get_actor_location()
        placed = {}
        for label, dist in (('k2_after_close', 520.0), ('k3_after_mid', 900.0), ('k4_after_far', 1500.0)):
            placed[label] = stand_beside(pawn, b.get_actor_location(), dist, anchor=home)
            await asyncio.sleep(0.25)
            face(pc, pawn, b.get_actor_location(), pitch_bias=4.0, yaw_offset=9.0)
            await run.shot(label)
            await asyncio.sleep(0.9)
        run.report['placed'] = placed
        run.report['boss_state'] = str(b.get_boss_state())
        stand_beside(pawn, b.get_actor_location(), 700.0, anchor=home)
        return
    if n == 2:
        pc, pawn = player(world)
        b = boss(world)
        final = pawn.get_component_by_class(unreal.ReflectionsFinalSpellComponent)
        casts, t = 0, 0.0
        while final and b and unreal.SystemLibrary.is_valid(b) and b.get_health() > 0.0 and t < 14.0:
            face(pc, pawn, b.get_actor_location())
            if final.cast_final_spell():
                casts += 1
                await asyncio.sleep(0.45)
                if casts == 1:
                    await run.shot('k5_final_spell_hit')
                await asyncio.sleep(0.6)
                t += 1.05
            else:
                await asyncio.sleep(0.4)
                t += 0.4
        run.report['final_casts'] = casts
        run.report['boss_health_end'] = b.get_health() if b and unreal.SystemLibrary.is_valid(b) else 0.0
        run.report['boss_state_end'] = str(b.get_boss_state()) if b and unreal.SystemLibrary.is_valid(b) else 'destroyed'
        await asyncio.sleep(3.5)
        await run.shot('k6_ending_cutscene')
        await skip_cutscenes(world)
        await asyncio.sleep(2.5)
        await run.shot('k7_victory')
        cmd(world, 'Villain.Status')
        if lock_holder() is None and await call_tool(APP + 'IsPIERunning'):
            await call_tool(APP + 'StopPIE')
            run.report['stopped'] = True
        release_lock()


# ----------------------------------------------------------------------------------------------- no-console proof (train #9+)
# A real run with zero console commands: the title's New Game button (StartNewGame), cutscenes skipped with the skip
# button's own UFUNCTION (SkipCutscene), the hero walked onto pages by teleport (the overlap pickup does the rest),
# the Final Spell cast through the F key's handler (CastFinalSpell). Possession must start by itself.

def flow_of(world):
    return unreal.get_game_instance_subsystem(unreal.GameplayStatics.get_game_instance(world), unreal.ReflectionsGameFlowSubsystem)


def cutscenes_of(world):
    return unreal.get_world_subsystem(world, unreal.ReflectionsCutsceneSubsystem)


async def skip_button(world, run=None, label=None):
    """Press skip while a cutscene plays (up to three in a row)."""
    for _ in range(3):
        cs = cutscenes_of(world)
        if not cs or not cs.is_cutscene_playing():
            return
        if run is not None:
            run.report.setdefault('cutscenes', []).append('%s @%s' % (cs.get_current_cutscene(), label))
        cs.skip_cutscene()
        await asyncio.sleep(0.8)


async def proof(run, n):
    if n == 0:
        holder = lock_holder()
        if holder is not None or await call_tool(APP + 'IsPIERunning'):
            raise RuntimeError('PIE busy or locked (%s)' % (holder,))
        write_lock('villain: no-console New Game -> pages -> Tarnish -> Victory (one run)')
        await call_tool(APP + 'StartPIE')
        world = None
        for _ in range(30):
            world = game_world()
            if world and player(world)[1]:
                break
            await asyncio.sleep(0.5)
        await asyncio.sleep(1.5)
        flow = flow_of(world)
        run.report = {'start_map': world.get_path_name(), 'screen_at_start': str(flow.get_screen())}
        # New Game's map comes from DefaultGame.ini (NewGameMap = the mock city) since train #10: no console at all.
        flow.start_new_game()          # the title's New Game button
        run.report['new_game_pressed'] = True
        return
    world = game_world()
    if n == 1:
        for _ in range(40):
            world = game_world()
            if world and 'Lvl_MockCity' in world.get_path_name() and player(world)[1]:
                break
            await asyncio.sleep(0.5)
        run.report['map'] = world.get_path_name() if world else None
        if not world or 'Lvl_MockCity' not in world.get_path_name():
            return
        await asyncio.sleep(2.0)
        await skip_button(world, run, 'intro')
        await asyncio.sleep(1.0)
        flow = flow_of(world)
        v = villain(world)
        run.report['run_live'] = flow.is_run_live()
        run.report['possession_running'] = v.is_possession_running()
        run.report['arena_markers'] = [m.get_name() for m in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsVillainArena)]
        await run.shot('p1_live')
        return
    if n == 2:  # wait out StartDelay: the Tarnish should take a host on its own
        v = villain(world)
        pc, pawn = player(world)
        host = None
        for _ in range(26):
            await asyncio.sleep(1.0)
            await skip_button(world, run, 'wait')
            host = v.get_host()
            if host:
                break
        run.report['first_host'] = host.get_name() if host else None
        run.report['infected'] = v.get_infected_count()
        if host:
            face(pc, pawn, host.get_actor_location(), pitch_bias=-8.0)
            await run.shot('p2_first_host')
        return
    if n == 3:  # collect the three pages the way the hero would: by touching them
        pc, pawn = player(world)
        pages = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsBookPagePickup))
        run.report['pages_found'] = [(str(pg.get_editor_property('page_id')), [round(c) for c in (pg.get_actor_location().x, pg.get_actor_location().y, pg.get_actor_location().z)]) for pg in pages]
        jump = unreal.get_game_instance_subsystem(unreal.GameplayStatics.get_game_instance(world), unreal.ReflectionsWorldJumpSubsystem)
        for pg in pages:
            if jump.is_book_complete():
                break
            if not unreal.SystemLibrary.is_valid(pg):
                continue
            pawn.teleport(pg.get_actor_location() + unreal.Vector(0.0, 0.0, 20.0), unreal.Rotator(0.0, 0.0, 0.0))
            await asyncio.sleep(1.2)
            await skip_button(world, run, 'page')
            run.report.setdefault('page_count_after', []).append(jump.get_page_count())
        run.report['book_complete'] = jump.is_book_complete()
        await asyncio.sleep(1.0)
        await skip_button(world, run, 'book')
        await asyncio.sleep(1.0)
        b = boss(world)
        run.report['boss'] = bool(b)
        if b:
            run.report['boss_from_crown_cm'] = round((b.get_actor_location() - CROWN).length())
            run.report['boss_state_before_climb'] = str(b.get_boss_state())
        final = pawn.get_component_by_class(unreal.ReflectionsFinalSpellComponent)
        run.report['final_spell_given'] = bool(final)
        return
    if n == 4:  # climb (teleport to the ramp top), he rises; after-look shots
        pc, pawn = player(world)
        b = boss(world)
        if not b:
            return
        pawn.teleport(TOWER_INSIDE, unreal.Rotator(0.0, 0.0, 0.0))
        await asyncio.sleep(1.2)
        run.report['state_inside_tower'] = str(b.get_boss_state())
        # Walk up the Frost Tower ramps on the navmesh (path following moves the hero like held input).
        walked = False
        try:
            unreal.AIBlueprintHelperLibrary.simple_move_to_location(pc, RAMP_EXIT)
            start = pawn.get_actor_location()
            for i in range(56):
                await asyncio.sleep(0.5)
                loc = pawn.get_actor_location()
                if i == 6 and (loc - start).length() < 50.0:
                    break                                   # no path: not moving at all
                if loc.z > CROWN.z - 50.0 and (loc - RAMP_EXIT).length() < 900.0:
                    walked = True
                    break
            run.report['walk_end'] = [round(c) for c in (pawn.get_actor_location().x, pawn.get_actor_location().y, pawn.get_actor_location().z)]
        except Exception as ex:
            run.report['walk_error'] = str(ex)
        run.report['walked_up_ramps'] = walked
        if not walked:
            pawn.teleport(RAMP_EXIT, unreal.Rotator(0.0, 0.0, 0.0))   # fallback, reported as such
        await asyncio.sleep(0.5)
        run.report['state_on_arrival'] = str(b.get_boss_state())
        face(pc, pawn, b.get_actor_location(), pitch_bias=2.0, yaw_offset=9.0)
        await run.shot('p3_arrival')
        await asyncio.sleep(2.8)
        home = pawn.get_actor_location()
        for label, dist in (('p4_after_close', 520.0), ('p5_after_mid', 900.0), ('p6_after_far', 1500.0)):
            stand_beside(pawn, b.get_actor_location(), dist, anchor=home)
            await asyncio.sleep(0.25)
            face(pc, pawn, b.get_actor_location(), pitch_bias=4.0, yaw_offset=9.0)
            await run.shot(label)
            await asyncio.sleep(0.8)
        stand_beside(pawn, b.get_actor_location(), 700.0, anchor=home)
        run.report['state_after_shots'] = str(b.get_boss_state())
        return
    if n == 5:  # Final Spell (F) until he burns out; Ending; Victory; stop
        pc, pawn = player(world)
        b = boss(world)
        final = pawn.get_component_by_class(unreal.ReflectionsFinalSpellComponent)

        def hero_health():
            hc = pawn.get_component_by_class(unreal.ReflectionsHealthComponent) if unreal.SystemLibrary.is_valid(pawn) else None
            try:
                return round(hc.get_editor_property('health'), 1) if hc else None
            except Exception:
                return None

        run.report['hero_health_fight_start'] = hero_health()
        run.report['boss_health_fight_start'] = b.get_health() if b else None
        casts, t = 0, 0.0
        while final and b and unreal.SystemLibrary.is_valid(b) and b.get_health() > 0.0 and t < 22.0:
            face(pc, pawn, b.get_actor_location())
            if final.cast_final_spell():
                casts += 1
                await asyncio.sleep(0.45)
                if casts == 1:
                    await run.shot('p7_final_spell')
                await asyncio.sleep(0.6)
                t += 1.05
            else:
                await asyncio.sleep(0.4)
                t += 0.4
        run.report['final_casts'] = casts
        run.report['boss_health_end'] = b.get_health() if b and unreal.SystemLibrary.is_valid(b) else 0.0
        run.report['hero_health_fight_end'] = hero_health()
        run.report['fight_seconds'] = round(t, 1)
        # Death (2 s) then 2.5 s later the Ending cutscene; wait for it, skip it, then wait for game flow's Victory.
        flow = flow_of(world)
        for _ in range(24):
            await asyncio.sleep(0.5)
            cs = cutscenes_of(world)
            if (cs and cs.is_cutscene_playing()) or flow.is_victory():
                break
        await asyncio.sleep(1.0)
        await run.shot('p8_ending')
        await skip_button(world, run, 'ending')
        for _ in range(16):
            if flow.is_victory():
                break
            await asyncio.sleep(0.5)
        await asyncio.sleep(1.0)
        run.report['victory'] = flow.is_victory()
        run.report['screen_end'] = str(flow.get_screen())
        await run.shot('p9_victory')
        if lock_holder() is None and await call_tool(APP + 'IsPIERunning'):
            await call_tool(APP + 'StopPIE')
            run.report['stopped'] = True
        release_lock()


async def step(stage, n):
    run = Run(stage)
    refresh_lock()
    try:
        if n == 'stop':
            await stop(run)
        elif stage == 'possession' and n == 4:
            await conversion(run)
        elif stage == 'possession':
            await possession(run, n)
        elif stage == 'proof':
            await proof(run, n)
        elif stage == 'tower':
            await tower(run, n)
        elif stage == 'slot':
            await last_slot(run, n)
        elif stage == 'crowd':
            await crowd_conversion(run, n)
        elif stage in ('finale', 'arena'):
            await finale(run, n, stage == 'arena')
    except Exception:
        import traceback
        run.report['error_step_%s' % n] = traceback.format_exc()
        try:
            await stop(run)
        except Exception as ex:
            run.report['stop_error'] = str(ex)
    run.save()
    return {k: v for k, v in run.report.items() if k != 'screenshots'}
