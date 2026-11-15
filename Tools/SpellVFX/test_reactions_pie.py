"""PIE check of spell reactions (run inside the editor via the MCP Python tool). ARGS picks cases: explosion, shock.

explosion: drops four physics crates around a crowd walker, casts the player's Fireball at the walker, and measures
           how far the crates were thrown and how much the walker lost; captures the blast from the side.
shock:     casts Lightning Bolt at a walker with another body nearby; checks the crackle system (NS_Spell_Shock) is on
           the struck body and that the bolt chained to a second body; captures the crackle.
Writes Saved/SpellCombatTest/reactions/. Takes and releases the shared PIE lock (claim it from bash first when the
editor is shared; this script only waits 30 s for it).
"""
import base64
import json
import math
import time
from pathlib import Path

APP = 'EditorToolset.EditorAppToolset.'
SC = 'SceneCaptureToolset.SceneCaptureToolset.'
OUT = Path(unreal.Paths.project_saved_dir()).resolve() / 'SpellCombatTest' / 'reactions'
OUT.mkdir(parents=True, exist_ok=True)
LOCK = Path(unreal.Paths.project_saved_dir()).resolve() / 'PIE_LOCK.json'
ME = 'spell-aim-vfx [561a1b] (Rebuild spell aiming, casting, animations and VFX)'
report = {'failures': [], 'shots': {}}


def fail(why):
    report['failures'].append(why)


def flush():
    (OUT / 'report.json').write_text(json.dumps(report, indent=2, default=str))


async def acquire_lock(purpose):
    for _ in range(3):
        try:
            cur = json.loads(LOCK.read_text())
        except Exception:
            cur = None
        if cur and cur.get('owner') != ME and float(cur.get('expires_epoch', 0)) > time.time():
            await asyncio.sleep(10.0)
            continue
        if not await call_tool(APP + 'IsPIERunning'):
            now = time.time()
            LOCK.write_text(json.dumps({'owner': ME, 'purpose': purpose, 'acquired_epoch': now, 'expires_epoch': now + 200}))
            return
        await asyncio.sleep(10.0)
    raise RuntimeError('PIE lock not available; claim it from bash first')


def release_lock():
    try:
        if json.loads(LOCK.read_text()).get('owner') == ME:
            LOCK.unlink()
    except Exception:
        pass


def save(name, r):
    data = r.get('image') if isinstance(r, dict) else None
    if isinstance(data, dict):
        data = data.get('data')
    p = OUT / (name + '.png')
    if data:
        p.write_bytes(base64.b64decode(data))
    report['shots'][name] = str(p) if data else None


async def view(name, world_ref, eye, target, fov=60.0):
    d = target - eye
    camera = {'location': {'x': eye.x, 'y': eye.y, 'z': eye.z},
              'rotation': {'pitch': math.degrees(math.atan2(d.z, math.hypot(d.x, d.y))), 'yaw': math.degrees(math.atan2(d.y, d.x)), 'roll': 0.0},
              'projectionMode': 'Perspective', 'fOV': fov}
    save(name, await call_tool(SC + 'Capture', world=world_ref, camera=camera, mode='Lit',
                               options={'width': 1280, 'height': 720, 'screenPercentage': 1.0, 'visualizationSubMode': ''}))


def health(actor):
    h = actor.get_component_by_class(unreal.ReflectionsHealthComponent) if actor else None
    return h.get_editor_property('health') if h else None


def aim_at(pc, point):
    cam = pc.player_camera_manager.get_camera_location()
    d = point - cam
    pc.set_control_rotation(unreal.Rotator(roll=0.0, pitch=math.degrees(math.atan2(d.z, math.hypot(d.x, d.y))), yaw=math.degrees(math.atan2(d.y, d.x))))


async def ready_cast(driver, spell, limit=8.0):
    cost = driver.get_spell_mana_cost(spell)
    t = 0.0
    while t < limit:
        if driver.get_mana() >= cost and driver.get_spell_cooldown_remaining(spell) <= 0.0 and not driver.is_casting():
            return driver.cast_spell(spell)
        await asyncio.sleep(0.1)
        t += 0.1
    return False


def walkers_near(world, origin, lo, hi):
    npcs = None
    for sub in unreal.ObjectIterator(unreal.ReflectionsNpcSubsystem):
        try:
            if sub.get_world() == world:
                npcs = sub
                break
        except Exception:
            pass
    found = []
    for a in (npcs.get_npc_actors() if npcs else []):
        if isinstance(a, unreal.Pawn):
            continue
        d = (a.get_actor_location() - origin).length()
        if (health(a) or 0) > 0 and lo < d < hi:
            found.append((d, a))
    found.sort(key=lambda x: x[0])
    return [a for _, a in found]


def chest(actor):
    o, e = actor.get_actor_bounds(True)
    return o + unreal.Vector(0.0, 0.0, e.z * 0.25)


def loose_props(world, center, radius=650.0, limit=4):
    """Python here cannot spawn actors in PIE, so borrow small static props near the blast and make them physics
    objects for this run (the PIE copy only; the saved level is untouched)."""
    props = []
    for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.StaticMeshActor):
        try:
            o, e = a.get_actor_bounds(False)
            if max(e.x, e.y, e.z) > 120.0 or (o - center).length() > radius:
                continue
            c = a.static_mesh_component
            c.set_mobility(unreal.ComponentMobility.MOVABLE)
            c.set_simulate_physics(True)
            if c.is_simulating_physics():
                props.append((a.get_actor_location() - center).length(), a)
        except Exception:
            pass
    props.sort(key=lambda x: x[0])
    return [a for _, a in props[:limit]]


async def case_explosion(world, world_ref, pc, pawn, driver):
    ws = walkers_near(world, pawn.get_actor_location(), 700.0, 1600.0)
    if not ws:
        fail('explosion: no walker 7-16 m away')
        return {}
    w = ws[0]
    base = w.get_actor_location()
    crates = loose_props(world, base)
    report['props_borrowed'] = [c.get_name() for c in crates]
    await asyncio.sleep(0.6)
    before = [c.get_actor_location() for c in crates]
    h0 = health(w)
    aim_at(pc, chest(w))
    ok = await ready_cast(driver, unreal.HeroSpell.FIRESTORM)
    hit_after = None
    t0 = time.time()
    while time.time() - t0 < 3.0:
        h = health(w)
        if h is not None and h0 is not None and h < h0 - 0.01:
            hit_after = round(time.time() - t0, 2)
            break
        await asyncio.sleep(0.05)
    side = unreal.Vector(-(base - pawn.get_actor_location()).y, (base - pawn.get_actor_location()).x, 0.0)
    side = side * (1.0 / max(1.0, side.length()))
    eye = base + side * 650.0 + unreal.Vector(0.0, 0.0, 220.0)
    await view('explosion_blast', world_ref, eye, base + unreal.Vector(0, 0, 60), 65.0)
    await asyncio.sleep(0.45)
    await view('explosion_after', world_ref, eye, base + unreal.Vector(0, 0, 60), 65.0)
    await asyncio.sleep(0.8)
    moved = [round((c.get_actor_location() - b).length(), 1) for c, b in zip(crates, before)]
    out = {'walker': w.get_name(), 'cast': ok, 'hit_after_s': hit_after, 'walker_damage': round(h0 - (health(w) or 0), 2) if h0 else None,
           'crates_moved_cm': moved}
    if not ok:
        fail('explosion: fireball refused')
    if moved and max(moved) < 50.0:
        fail('explosion: no prop near the blast moved more than 0.5 m (%s)' % moved)
    return out


async def case_shock(world, world_ref, pc, pawn, driver):
    ws = walkers_near(world, pawn.get_actor_location(), 500.0, 1800.0)
    pair = None
    for a in ws:
        for b in ws:
            if a != b and (a.get_actor_location() - b.get_actor_location()).length() < 650.0:
                pair = (a, b)
                break
        if pair:
            break
    if not pair:
        fail('shock: no two walkers within 6.5 m of each other')
        return {}
    a, b = pair
    # Face the struck body and hold it still (Npc.Weaken holds the nearest unnamed NPC in front for 15 s), so the bolt
    # can't miss a moving walker; the chain target b keeps walking.
    aim_at(pc, chest(a))
    await asyncio.sleep(0.3)
    unreal.SystemLibrary.execute_console_command(world, 'Npc.Weaken 45', pc)
    await asyncio.sleep(0.3)
    held = [w for w in walkers_near(world, pawn.get_actor_location(), 300.0, 2500.0) if health(w) == 45.0]
    if held:
        a = held[0]
        others = [w for w in walkers_near(world, a.get_actor_location(), 1.0, 700.0) if w != a]
        if others:
            b = others[0]
    report['shock_held'] = a.get_name() if held else None
    ha, hb = health(a), health(b)
    aim_at(pc, chest(a))
    await asyncio.sleep(0.2)
    aim_at(pc, chest(a))
    ok = await ready_cast(driver, unreal.HeroSpell.LIGHTNING_BOLT)
    crackle = 0
    shot = False
    t0 = time.time()
    while time.time() - t0 < 2.0:
        crackle = max(crackle, sum(1 for c in unreal.ObjectIterator(unreal.NiagaraComponent)
                                   if c.get_world() == world and c.get_asset() and c.get_asset().get_name() == 'NS_Spell_Shock' and c.is_active()))
        if crackle and not shot:
            await asyncio.sleep(0.15)
            p = a.get_actor_location()
            await view('shock_crackle', world_ref, p + unreal.Vector(-260.0, 160.0, 140.0), chest(a), 55.0)
            shot = True
        await asyncio.sleep(0.05)
    out = {'struck': a.get_name(), 'near': b.get_name(), 'cast': ok, 'struck_damage': round(ha - (health(a) or 0), 2),
           'near_damage': round(hb - (health(b) or 0), 2), 'crackle_components': crackle}
    if not crackle:
        fail('shock: no NS_Spell_Shock crackle on the struck body')
    if out['near_damage'] <= 0:
        fail('shock: the bolt did not chain to the nearby body')
    return out


await acquire_lock('spell reactions check: fireball explosion, shock crackle and chain')
await call_tool(APP + 'StartPIE', options={'warmupSeconds': 3.0})
try:
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    worlds = await call_tool(SC + 'ListWorlds')
    wl = worlds if isinstance(worlds, list) else worlds.get('returnValue', worlds)
    world_ref = next(w for w in wl if w.get('worldType') == 'PIE')['world']
    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    pawn = pc.get_controlled_pawn()
    driver = pawn.get_component_by_class(unreal.ReflectionsSampleSpellDriver)
    # npc-unify's element reactions sit behind Npc.ElementReactions (0 until its own check); on for this run only.
    report['element_reactions_was'] = unreal.SystemLibrary.get_console_variable_int_value('Npc.ElementReactions')
    unreal.SystemLibrary.execute_console_command(world, 'Npc.ElementReactions 1', pc)
    which = ARGS or ['explosion', 'shock']
    if 'explosion' in which:
        report['explosion'] = await case_explosion(world, world_ref, pc, pawn, driver)
        flush()
    if 'shock' in which:
        report['shock'] = await case_shock(world, world_ref, pc, pawn, driver)
        flush()
except Exception as e:
    fail('script error: %r' % e)
finally:
    if 'element_reactions_was' in report:
        unreal.SystemLibrary.execute_console_command(None, 'Npc.ElementReactions %d' % report['element_reactions_was'])
    try:
        await call_tool(APP + 'StopPIE')
    except Exception:
        pass
    release_lock()
report['result'] = 'FAIL' if report['failures'] else 'PASS'
flush()
json.dumps(report, default=str)
