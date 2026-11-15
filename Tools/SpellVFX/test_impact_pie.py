"""PIE checks for trains #13/#14 (run in the editor via MCP Python; claim Saved/PIE_LOCK.json from bash first).

ARGS picks cases (default all) plus an optional tag=<name> for the strip file names:
  regen      - damage the hero by 30, check health holds for 6 s, then climbs (train #13 regen: 3/s after 6 s).
  pointblank - spawn a Guard, hold it (Npc.Weaken), stand 90 cm in front and cast a Fire Bolt (train #13 sweep).
  strip      - frame strips of a Fireball direct hit and a Lightning Bolt hit on a held walker, from a side camera:
               frames just before impact and at about +0, +0.12, +0.3, +0.6 and +1.2 s.
Writes Saved/SpellCombatTest/impact/ (PNGs, strips and report.json).
"""
import base64
import json
import math
import time
from pathlib import Path

APP = 'EditorToolset.EditorAppToolset.'
SC = 'SceneCaptureToolset.SceneCaptureToolset.'
OUT = Path(unreal.Paths.project_saved_dir()).resolve() / 'SpellCombatTest' / 'impact'
OUT.mkdir(parents=True, exist_ok=True)
LOCK = Path(unreal.Paths.project_saved_dir()).resolve() / 'PIE_LOCK.json'
ME = 'spell-aim-vfx [561a1b] (Rebuild spell aiming, casting, animations and VFX)'
args = list(ARGS or [])
TAG = next((a.split('=', 1)[1] for a in args if a.startswith('tag=')), 'now')
CASES = [a for a in args if '=' not in a] or ['regen', 'pointblank', 'strip']
report = {'failures': [], 'tag': TAG}


def fail(why):
    report['failures'].append(why)


def flush():
    (OUT / ('report_%s.json' % TAG)).write_text(json.dumps(report, indent=2, default=str))


def health(a):
    h = a.get_component_by_class(unreal.ReflectionsHealthComponent) if a else None
    return round(h.get_editor_property('health'), 2) if h else None


async def capture(name, world_ref, eye, target, fov=50.0):
    d = target - eye
    camera = {'location': {'x': eye.x, 'y': eye.y, 'z': eye.z},
              'rotation': {'pitch': math.degrees(math.atan2(d.z, math.hypot(d.x, d.y))), 'yaw': math.degrees(math.atan2(d.y, d.x)), 'roll': 0.0},
              'projectionMode': 'Perspective', 'fOV': fov}
    r = await call_tool(SC + 'Capture', world=world_ref, camera=camera, mode='Lit',
                        options={'width': 960, 'height': 540, 'screenPercentage': 1.0, 'visualizationSubMode': ''})
    data = r.get('image') if isinstance(r, dict) else None
    if isinstance(data, dict):
        data = data.get('data')
    if not data:
        return None
    p = OUT / (name + '.png')
    p.write_bytes(base64.b64decode(data))
    return str(p)


def aim_at(pc, point):
    cam = pc.player_camera_manager.get_camera_location()
    d = point - cam
    pc.set_control_rotation(unreal.Rotator(roll=0.0, pitch=math.degrees(math.atan2(d.z, math.hypot(d.x, d.y))), yaw=math.degrees(math.atan2(d.y, d.x))))


def chest(actor):
    o, e = actor.get_actor_bounds(True)
    return o + unreal.Vector(0.0, 0.0, e.z * 0.3)


async def ready_cast(driver, spell, limit=8.0):
    t = 0.0
    while t < limit:
        if driver.get_mana() >= driver.get_spell_mana_cost(spell) and driver.get_spell_cooldown_remaining(spell) <= 0 and not driver.is_casting():
            return driver.cast_spell(spell)
        await asyncio.sleep(0.1)
        t += 0.1
    return False


def npc_actors(world):
    npcs = next((s for s in unreal.ObjectIterator(unreal.ReflectionsNpcSubsystem) if s.get_world() == world), None)
    return [a for a in (npcs.get_npc_actors() if npcs else []) if not isinstance(a, unreal.Pawn)]


async def hold_walker(world, pc, pawn, hp):
    """Face the nearest walker 6-12 m away and hold it still at hp health (Npc.Weaken)."""
    loc = pawn.get_actor_location()
    cands = sorted(((a.get_actor_location() - loc).length(), a) for a in npc_actors(world)
                   if (health(a) or 0) > 0 and 600 < (a.get_actor_location() - loc).length() < 1200)
    if not cands:
        # Gray London has no crowd at the start: spawn one 9 m in front of the hero.
        before = set(a.get_name() for a in npc_actors(world))
        unreal.SystemLibrary.execute_console_command(world, 'Npc.Spawn Civilian 1 900', pc)
        await asyncio.sleep(1.5)
        fresh = [a for a in npc_actors(world) if a.get_name() not in before and (health(a) or 0) > 0]
        if not fresh:
            return None
        cands = [((fresh[0].get_actor_location() - loc).length(), fresh[0])]
    target = cands[0][1]
    aim_at(pc, chest(target))
    await asyncio.sleep(0.3)
    unreal.SystemLibrary.execute_console_command(world, 'Npc.Weaken %d' % hp, pc)
    await asyncio.sleep(0.4)
    return target


async def case_regen(world, pawn):
    h = pawn.get_component_by_class(unreal.ReflectionsHealthComponent)
    start = health(pawn)
    unreal.GameplayStatics.apply_damage(pawn, 30.0, None, None, unreal.DamageType)
    t0 = time.time()
    samples = []
    while time.time() - t0 < 10.0:
        samples.append((round(time.time() - t0, 1), health(pawn)))
        await asyncio.sleep(0.5)
    after_hit = samples[0][1]
    at5 = next(v for t, v in samples if t >= 5.0)
    at10 = samples[-1][1]
    out = {'start': start, 'after_hit': after_hit, 'at_5s': at5, 'at_10s': at10, 'samples': samples}
    if at5 > after_hit + 0.01:
        fail('regen: health rose within 5 s of damage (%s -> %s)' % (after_hit, at5))
    if at10 < after_hit + 6.0:
        fail('regen: health did not climb after the 6 s wait (%s -> %s at 10 s)' % (after_hit, at10))
    return out


async def case_pointblank(world, pc, pawn, driver):
    before = set(a.get_name() for a in npc_actors(world))
    unreal.SystemLibrary.execute_console_command(world, 'Npc.Spawn Guard 1 400', pc)
    await asyncio.sleep(1.2)
    guard = next((a for a in npc_actors(world) if a.get_name() not in before and 'Guard' in a.get_class().get_name()), None)
    if not guard:
        fail('pointblank: no Guard spawned')
        return {}
    aim_at(pc, chest(guard))
    await asyncio.sleep(0.2)
    unreal.SystemLibrary.execute_console_command(world, 'Npc.Weaken 40', pc)
    await asyncio.sleep(0.3)
    g = guard.get_actor_location()
    to_hero = pawn.get_actor_location() - g
    to_hero.z = 0.0
    to_hero = to_hero * (90.0 / max(1.0, to_hero.length()))
    pawn.set_actor_location(unreal.Vector(g.x + to_hero.x, g.y + to_hero.y, pawn.get_actor_location().z), False, True)
    await asyncio.sleep(1.2)  # let the camera settle before aiming
    aim_at(pc, chest(guard))
    await asyncio.sleep(0.1)
    h0 = health(guard)
    unreal.SystemLibrary.execute_console_command(world, 'Spell.LogHits 1', pc)
    ok = await ready_cast(driver, unreal.HeroSpell.FIRE)
    await asyncio.sleep(1.0)
    unreal.SystemLibrary.execute_console_command(world, 'Spell.LogHits 0', pc)
    out = {'guard': guard.get_name(), 'cast': ok, 'hero_to_guard_cm': round((pawn.get_actor_location() - guard.get_actor_location()).length(), 1),
           'health_before': h0, 'health_after': health(guard)}
    if ok and (out['health_after'] is None or out['health_after'] >= (h0 or 0)):
        fail('pointblank: Fire Bolt from %s cm did no damage' % out['hero_to_guard_cm'])
    return out


async def strip(world, world_ref, pc, pawn, driver, spell, name):
    walker = await hold_walker(world, pc, pawn, 90)
    if not walker:
        fail('strip %s: no walker 6-12 m away' % name)
        return {}
    w = walker.get_actor_location()
    p = pawn.get_actor_location()
    d = w - p
    side = unreal.Vector(-d.y, d.x, 0.0) * (1.0 / max(1.0, math.hypot(d.x, d.y)))
    eye = w - d * 0.28 + side * 430.0 + unreal.Vector(0.0, 0.0, 120.0)
    look = w - d * 0.12 + unreal.Vector(0.0, 0.0, 60.0)
    aim_at(pc, chest(walker))
    await asyncio.sleep(0.15)
    h0 = health(walker)
    known = set(x.get_name() for x in unreal.ObjectIterator(unreal.ReflectionsSpellProjectile) if x.get_world() == world)
    ok = await ready_cast(driver, spell)
    frames = []
    t_cast = time.time()
    pre_done = False
    t_hit = None
    while time.time() - t_cast < 3.0 and t_hit is None:
        try:
            fly = [x for x in unreal.ObjectIterator(unreal.ReflectionsSpellProjectile) if x.get_world() == world and x.get_name() not in known]
            gap = (fly[0].get_actor_location() - w).length() if fly else 1e9
        except Exception:
            gap = 1e9
        if not pre_done and gap < 520.0:
            frames.append(('-0.1s', await capture('%s_%s_0' % (TAG, name), world_ref, eye, look)))
            pre_done = True
        h = health(walker)
        if h is not None and h0 is not None and h < h0 - 0.01:
            t_hit = time.time()
        await asyncio.sleep(0.0)
    if t_hit is None:
        fail('strip %s: no hit within 3 s' % name)
        return {'walker': walker.get_name(), 'cast': ok}
    for i, (label, at) in enumerate((('+0', 0.0), ('+0.12s', 0.12), ('+0.3s', 0.3), ('+0.6s', 0.6), ('+1.2s', 1.2))):
        while time.time() - t_hit < at:
            await asyncio.sleep(0.01)
        frames.append((label, await capture('%s_%s_%d' % (TAG, name, i + 1), world_ref, eye, look)))
    return {'walker': walker.get_name(), 'cast': ok, 'damage': round(h0 - (health(walker) or 0), 1), 'frames': frames}


def compose(name, title, frames):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return None
    shots = [(l, p) for l, p in frames if p]
    if not shots:
        return None
    W, H = 480, 270
    out = Image.new('RGB', (W * len(shots), H + 40), 'black')
    try:
        font = ImageFont.truetype('arial.ttf', 22)
    except Exception:
        font = ImageFont.load_default()
    d = ImageDraw.Draw(out)
    d.text((10, 8), title, fill=(255, 255, 255), font=font)
    for i, (label, path) in enumerate(shots):
        im = Image.open(path).convert('RGB').resize((W, H))
        ImageDraw.Draw(im).text((10, H - 32), label, fill=(255, 255, 255), font=font)
        out.paste(im, (i * W, 40))
    path = OUT / ('strip_%s_%s.png' % (TAG, name))
    out.save(path)
    return str(path)


async def run():
    await call_tool(APP + 'StartPIE', options={'warmupSeconds': 3.0})
    try:
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        worlds = await call_tool(SC + 'ListWorlds')
        wl = worlds if isinstance(worlds, list) else worlds.get('returnValue', worlds)
        world_ref = next(w for w in wl if w.get('worldType') == 'PIE')['world']
        pc = unreal.GameplayStatics.get_player_controller(world, 0)
        pawn = pc.get_controlled_pawn()
        driver = pawn.get_component_by_class(unreal.ReflectionsSampleSpellDriver)
        report['map'] = world.get_name()
        # Until the Lanthorne start fix (train #14) is in, the hero spawns at Gray London's dark origin: move it to the
        # PlayerStart tagged Lanthorne and give streaming a few seconds.
        start = next((s for s in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.PlayerStart)
                      if str(s.get_editor_property('player_start_tag')) == 'Lanthorne'), None)
        if start and (pawn.get_actor_location() - start.get_actor_location()).length() > 300.0:
            pawn.set_actor_location(start.get_actor_location(), False, True)
            pc.set_control_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=start.get_actor_rotation().yaw))
            await asyncio.sleep(4.0)
        report['hero_start'] = pawn.get_actor_location()
        if 'strip' in CASES:
            fb = await strip(world, world_ref, pc, pawn, driver, unreal.HeroSpell.FIRESTORM, 'fireball')
            report['strip_fireball'] = fb
            report['strip_fireball_png'] = compose('fireball', 'Fireball direct hit (%s)' % TAG, fb.get('frames', []))
            flush()
            await asyncio.sleep(1.0)
            lb = await strip(world, world_ref, pc, pawn, driver, unreal.HeroSpell.LIGHTNING_BOLT, 'lightning')
            report['strip_lightning'] = lb
            report['strip_lightning_png'] = compose('lightning', 'Lightning Bolt hit (%s)' % TAG, lb.get('frames', []))
            flush()
        if 'regen' in CASES:
            report['regen'] = await case_regen(world, pawn)
            flush()
        if 'pointblank' in CASES:
            report['pointblank'] = await case_pointblank(world, pc, pawn, driver)
            flush()
    except Exception as e:
        fail('script error: %r' % e)
    finally:
        try:
            await call_tool(APP + 'StopPIE')
        except Exception:
            pass
        try:
            if json.loads(LOCK.read_text()).get('owner') == ME:
                LOCK.unlink()
        except Exception:
            pass
        report['result'] = 'FAIL' if report['failures'] else 'PASS'
        flush()


await run()
json.dumps({k: report.get(k) for k in ('result', 'failures')}, default=str)
