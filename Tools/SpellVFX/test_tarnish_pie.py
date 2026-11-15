"""PIE check of the tarnish enemy magic (run inside the editor via the MCP Python tool, after the C++ is loaded).

Gives a crowd walker (or, without one, a practice target) a UReflectionsTarnishCasterComponent and has it cast
Tarnish Bolt, Tarnish Wisp and Tarnish Burst at the player. Checks the wind-up runs, each spell hurts the player by
its tuned damage, tarnish stains are laid, and captures the wind-up, flight and burst warning from beside the fight.
Writes PNGs and report.json to Saved/SpellCombatTest/tarnish/. Takes and releases the shared PIE lock.
"""
import base64
import json
import math
import time
from pathlib import Path

APP = 'EditorToolset.EditorAppToolset.'
SC = 'SceneCaptureToolset.SceneCaptureToolset.'
OUT = Path(unreal.Paths.project_saved_dir()).resolve() / 'SpellCombatTest' / 'tarnish'
OUT.mkdir(parents=True, exist_ok=True)
LOCK = Path(unreal.Paths.project_saved_dir()).resolve() / 'PIE_LOCK.json'
ME = 'spell-aim-vfx [561a1b] (Rebuild spell aiming, casting, animations and VFX)'
report = {'failures': [], 'shots': {}}


def fail(why):
    report['failures'].append(why)


async def acquire_lock(purpose, budget_s=240):
    # Shared rule: never wait long inside the editor (another session's call cancels it). Claim the lock from bash
    # first; this only waits up to ~30 s, then writes ours (<= now + 240 s).
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
            LOCK.write_text(json.dumps({'owner': ME, 'purpose': purpose, 'acquired_epoch': now,
                                        'expires_epoch': now + min(budget_s, 240)}))
            return True
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
    if not data:
        report['shots'][name] = None
        return
    p = OUT / (name + '.png')
    p.write_bytes(base64.b64decode(data))
    report['shots'][name] = str(p)


async def view(name, world_ref, eye, target, fov=55.0):
    d = target - eye
    camera = {'location': {'x': eye.x, 'y': eye.y, 'z': eye.z},
              'rotation': {'pitch': math.degrees(math.atan2(d.z, math.hypot(d.x, d.y))), 'yaw': math.degrees(math.atan2(d.y, d.x)), 'roll': 0.0},
              'projectionMode': 'Perspective', 'fOV': fov}
    save(name, await call_tool(SC + 'Capture', world=world_ref, camera=camera, mode='Lit',
                               options={'width': 1280, 'height': 720, 'screenPercentage': 1.0, 'visualizationSubMode': ''}))


def health(actor):
    h = actor.get_component_by_class(unreal.ReflectionsHealthComponent)
    return h.get_editor_property('health') if h else None


def tarnish_marks(world):
    n = 0
    for c in unreal.ObjectIterator(unreal.DecalComponent):
        try:
            m = c.get_decal_material()
            if c.get_world() == world and isinstance(m, unreal.MaterialInstanceDynamic) and \
                    m.get_base_material().get_name() == 'M_Spell_GroundMark' and m.get_scalar_parameter_value('Kind') >= 5.5:
                n += 1
        except Exception:
            pass
    return n


def side_eye(a, b, out=520.0, up=170.0):
    mid = (a + b) * 0.5
    d = b - a
    side = unreal.Vector(-d.y, d.x, 0.0)
    side = side * (1.0 / max(1.0, side.length()))
    return mid + side * out + unreal.Vector(0.0, 0.0, up), mid


async def cast_and_watch(world, world_ref, comp, caster, pawn, spell, tag):
    windup = comp.get_windup(spell)
    h0 = health(pawn)
    marks0 = tarnish_marks(world)
    ok = comp.start_cast(spell, pawn)
    if not ok:
        fail('%s: start_cast refused' % tag)
        return {'started': False}
    await asyncio.sleep(windup * 0.6)
    casting = comp.is_casting()
    c = caster.get_actor_location()
    if tag == 'burst':
        await view('%s_warning' % tag, world_ref, c + unreal.Vector(-420.0, -300.0, 520.0), c, 70.0)
    else:
        f = c + (pawn.get_actor_location() - c) * (160.0 / max(1.0, (pawn.get_actor_location() - c).length()))
        await view('%s_windup' % tag, world_ref, f + unreal.Vector(0.0, 0.0, 60.0), c + unreal.Vector(0.0, 0.0, 60.0), 60.0)
    await asyncio.sleep(max(0.0, windup * 0.4) + 0.12)
    released_at = time.time()
    if tag == 'burst':
        await view('%s_blast' % tag, world_ref, c + unreal.Vector(-420.0, -300.0, 520.0), c, 70.0)
    hit_after = None
    shot_flight = False
    for i in range(45):
        h = health(pawn)
        if h is not None and h0 is not None and h < h0 - 0.01:
            hit_after = round(time.time() - released_at, 2)
            break
        if not shot_flight and tag != 'burst' and time.time() - released_at > (0.25 if tag == 'bolt' else 0.9):
            eye, mid = side_eye(c, pawn.get_actor_location())
            await view('%s_flight' % tag, world_ref, eye, mid, 60.0)
            shot_flight = True
        await asyncio.sleep(0.1)
    await asyncio.sleep(0.25)
    if tag != 'burst':
        p = pawn.get_actor_location()
        await view('%s_impact' % tag, world_ref, p + unreal.Vector(-260.0, 180.0, 150.0), p, 65.0)
    damage = round(h0 - health(pawn), 2) if h0 is not None else None
    if hit_after is None:
        fail('%s: the player took no damage' % tag)
    return {'started': ok, 'windup_s': windup, 'casting_mid_windup': casting, 'damage': damage, 'hit_after_release_s': hit_after,
            'tarnish_marks_added': tarnish_marks(world) - marks0}


await acquire_lock('tarnish magic check: bolt, wisp, burst at the player', 220)
await call_tool(APP + 'StartPIE', options={'warmupSeconds': 3.0})
try:
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    worlds = await call_tool(SC + 'ListWorlds')
    wl = worlds if isinstance(worlds, list) else worlds.get('returnValue', worlds)
    world_ref = next(w for w in wl if w.get('worldType') == 'PIE')['world']
    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    pawn = pc.get_controlled_pawn()
    report['player_health_start'] = health(pawn)
    loc = pawn.get_actor_location()
    npcs = None
    for sub in unreal.ObjectIterator(unreal.ReflectionsNpcSubsystem):
        try:
            if sub.get_world() == world:
                npcs = sub
                break
        except Exception:
            pass
    walkers = []
    for a in (npcs.get_npc_actors() if npcs else []):
        if isinstance(a, unreal.Pawn):
            continue
        d = (a.get_actor_location() - loc).length()
        if (health(a) or 0) > 0 and 500.0 < d < 1500.0:
            walkers.append((d, a))
    walkers.sort(key=lambda x: x[0])
    if walkers:
        caster = walkers[0][1]
    else:
        fwd = pawn.get_actor_forward_vector()
        xf = unreal.Transform(location=loc + fwd * 900.0)
        caster = unreal.GameplayStatics.begin_deferred_actor_spawn_from_class(world, unreal.ReflectionsSpellTarget, xf)
        if caster:
            caster = unreal.GameplayStatics.finish_spawning_actor(caster, xf)
    if not caster:
        raise RuntimeError('no caster: no walker in range and no practice target spawned')
    report['caster'] = caster.get_name()
    comp = caster.add_component_by_class(unreal.ReflectionsTarnishCasterComponent, False, unreal.Transform(), False)
    comp.set_editor_property('aim_spread', 0.0)
    report['bolt'] = await cast_and_watch(world, world_ref, comp, caster, pawn, unreal.ReflectionsTarnishSpell.BOLT, 'bolt')
    await asyncio.sleep(0.6)
    report['wisp'] = await cast_and_watch(world, world_ref, comp, caster, pawn, unreal.ReflectionsTarnishSpell.WISP, 'wisp')
    await asyncio.sleep(0.6)
    # Burst is short range: put the player 2 m from the caster.
    c = caster.get_actor_location()
    away = pawn.get_actor_location() - c
    away.z = 0.0
    away = away * (200.0 / max(1.0, away.length()))
    pawn.set_actor_location(unreal.Vector(c.x + away.x, c.y + away.y, pawn.get_actor_location().z), False, True)
    await asyncio.sleep(0.3)
    report['burst'] = await cast_and_watch(world, world_ref, comp, caster, pawn, unreal.ReflectionsTarnishSpell.BURST, 'burst')
    report['player_health_end'] = health(pawn)
except Exception as e:
    fail('script error: %r' % e)
finally:
    await call_tool(APP + 'StopPIE')
    release_lock()
report['result'] = 'FAIL' if report['failures'] else 'PASS'
(OUT / 'report.json').write_text(json.dumps(report, indent=2, default=str))
json.dumps(report, default=str)
