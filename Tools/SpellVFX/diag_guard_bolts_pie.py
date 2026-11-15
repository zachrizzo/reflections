"""Diagnostic (playtest run 3, item 4): why point-blank Fire Bolts don't hurt a spawned Gilt guard.

Spawns `Npc.Spawn Guard 1 400`, puts the hero at ARGS distances (default 110 and 450 cm) in front of it, casts Fire
Bolts at its chest and tracks every projectile each frame: where it spawned, how far that is inside the guard's hit
capsule, where it ended, and whether the guard's health dropped. Writes Saved/SpellCombatTest/guard_diag/report.json.
Claim Saved/PIE_LOCK.json from bash first.
"""
import json
import math
import time
from pathlib import Path

APP = 'EditorToolset.EditorAppToolset.'
OUT = Path(unreal.Paths.project_saved_dir()).resolve() / 'SpellCombatTest' / 'guard_diag'
OUT.mkdir(parents=True, exist_ok=True)
LOCK = Path(unreal.Paths.project_saved_dir()).resolve() / 'PIE_LOCK.json'
ME = 'spell-aim-vfx [561a1b] (Rebuild spell aiming, casting, animations and VFX)'
report = {'failures': []}


def flush():
    (OUT / 'report.json').write_text(json.dumps(report, indent=2, default=str))


def health(a):
    h = a.get_component_by_class(unreal.ReflectionsHealthComponent) if a else None
    return round(h.get_editor_property('health'), 2) if h else None


def capsules(a):
    out = []
    for c in a.get_components_by_class(unreal.CapsuleComponent):
        out.append({'name': c.get_name(), 'r': round(c.get_scaled_capsule_radius(), 1), 'hh': round(c.get_scaled_capsule_half_height(), 1),
                    'loc': c.get_world_location(), 'enabled': str(c.get_collision_enabled()), 'type': str(c.get_collision_object_type()),
                    'tags': [str(t) for t in c.component_tags]})
    return out


def inside(p, caps):
    best = None
    for c in caps:
        d = p - c['loc']
        z = max(0.0, abs(d.z) - (c['hh'] - c['r']))
        dist = math.sqrt(d.x * d.x + d.y * d.y + z * z) - c['r']
        best = dist if best is None else min(best, dist)
    return round(best, 1) if best is not None else None


async def bolt_at(world, pc, driver, guard, tag):
    o, e = guard.get_actor_bounds(True)
    aim = o + unreal.Vector(0, 0, e.z * 0.25)
    cam = pc.player_camera_manager.get_camera_location()
    d = aim - cam
    pc.set_control_rotation(unreal.Rotator(roll=0.0, pitch=math.degrees(math.atan2(d.z, math.hypot(d.x, d.y))), yaw=math.degrees(math.atan2(d.y, d.x))))
    known = set(p.get_name() for p in unreal.ObjectIterator(unreal.ReflectionsSpellProjectile) if p.get_world() == world)
    h0 = health(guard)
    t = 0.0
    while t < 6.0 and not (driver.get_mana() >= 10 and driver.get_spell_cooldown_remaining(unreal.HeroSpell.FIRE) <= 0 and not driver.is_casting()):
        await asyncio.sleep(0.1)
        t += 0.1
    ok = driver.cast_spell(unreal.HeroSpell.FIRE)
    tracks = {}
    t0 = time.time()
    while time.time() - t0 < 2.0:
        for p in unreal.ObjectIterator(unreal.ReflectionsSpellProjectile):
            try:
                if p.get_world() != world or p.get_name() in known:
                    continue
                loc = p.get_actor_location()
                caps = [c for c in capsules(guard) if 'NO_COLLISION' not in c['enabled']]
                tr = tracks.setdefault(p.get_name(), {'first': loc, 'first_t': round(time.time() - t0, 3),
                                                      'first_gap_to_capsule_cm': inside(loc, caps), 'frames': 0})
                tr['last'] = loc
                tr['frames'] += 1
                tr['min_gap_cm'] = min(tr.get('min_gap_cm', 1e9), inside(loc, caps) or 1e9)
            except Exception:
                pass
        await asyncio.sleep(0.0)
    return {'tag': tag, 'cast': ok, 'hero_to_guard_cm': round((pc.get_controlled_pawn().get_actor_location() - guard.get_actor_location()).length(), 1),
            'guard_health_before': h0, 'guard_health_after': health(guard), 'projectiles': tracks}


async def run():
    await call_tool(APP + 'StartPIE', options={'warmupSeconds': 3.0})
    try:
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        pc = unreal.GameplayStatics.get_player_controller(world, 0)
        pawn = pc.get_controlled_pawn()
        driver = pawn.get_component_by_class(unreal.ReflectionsSampleSpellDriver)
        before = set(a.get_name() for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))
        unreal.SystemLibrary.execute_console_command(world, 'Npc.Spawn Guard 1 400', pc)
        await asyncio.sleep(1.5)
        guard = None
        for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
            if a.get_name() not in before and 'Guard' in a.get_class().get_name():
                guard = a
        if not guard:
            report['failures'].append('no spawned guard found')
            return
        report['guard'] = guard.get_class().get_name()
        report['health_at_spawn'] = health(guard)
        # Hold it still (and at a known health) so point-blank distances are real: Npc.Weaken [Health].
        unreal.SystemLibrary.execute_console_command(world, 'Npc.Weaken 30', pc)
        await asyncio.sleep(0.3)
        report['health_after_weaken'] = health(guard)
        report['guard_capsules'] = capsules(guard)
        report['guard_bounds'] = guard.get_actor_bounds(True)
        report['runs'] = []
        for dist in [float(x) for x in (ARGS or ['110', '450'])]:
            g = guard.get_actor_location()
            fwd = guard.get_actor_forward_vector()
            spot = g + fwd * dist
            pawn.set_actor_location(unreal.Vector(spot.x, spot.y, pawn.get_actor_location().z), False, True)
            pc.set_control_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=guard.get_actor_rotation().yaw + 180.0))
            await asyncio.sleep(0.4)
            for i in range(2):
                report['runs'].append(await bolt_at(world, pc, driver, guard, 'd%d_%d' % (dist, i)))
                flush()
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
        flush()


await run()
json.dumps(report, default=str)[:6000]
