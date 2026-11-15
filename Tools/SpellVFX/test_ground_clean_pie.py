"""PIE check that spells leave nothing lit or alive on the ground (run inside the editor via the MCP Python tool).

Cases (pick with ARGS; add 'tag=<name>' to name the report, e.g. ['ground10', 'miss', 'stress', 'tag=after']):
- ground10: ten real driver casts at the ground ahead (waits, bounded, for mana / cooldown / cast readiness).
- miss:     five releases aimed at the sky, so projectiles expire at max range instead of hitting.
- stress:   twenty rapid releases at the ground through the combat component (exercises Niagara pool reuse).

Each case records a baseline of active NS_Spell_* components and a baseline capture, casts, waits 5 s, then checks:
- every cast-attributed NS_Spell_* component has finished (a lingering light particle keeps its component active);
- no spell projectile actor is still alive;
- captures exist (baseline / during / after). Ground brightness vs the baseline is compared afterwards from the PNGs.
A refused cast, a missing projectile on a projectile spell, a missing impact or a missing capture is a FAILURE.
Writes Saved/SpellCombatTest/ground_<tag>/report.json and PNGs.
"""
import base64
import json
import math
from pathlib import Path

APP = 'EditorToolset.EditorAppToolset.'
args = list(ARGS or ['ground10', 'miss', 'stress'])
tag = next((a.split('=', 1)[1] for a in args if a.startswith('tag=')), 'run')
OUT = Path(unreal.Paths.project_saved_dir()).resolve() / 'SpellCombatTest' / ('ground_' + tag)
OUT.mkdir(parents=True, exist_ok=True)
report = {'tag': tag, 'cases': {}, 'failures': []}

PROJECTILE_SPELLS = {'FIRE', 'WATER', 'ICE_SHARD', 'LIGHTNING_BOLT', 'ARCANE_BOLT', 'STONE_SHARD', 'FIRESTORM', 'WATER_ORB',
                     'CHAIN_LIGHTNING', 'FORCE_PUSH'}
GROUND10 = ['FIRE', 'WATER', 'ICE_SHARD', 'LIGHTNING_BOLT', 'ARCANE_BOLT', 'STONE_SHARD', 'FIRESTORM', 'FROST_NOVA',
            'EARTH_SHOCK', 'GREATER_HEAL']
STRESS = ['FIRESTORM', 'LIGHTNING_BOLT', 'ARCANE_BOLT', 'ICE_SHARD', 'WATER', 'FIRE', 'STONE_SHARD', 'WATER_ORB',
          'CHAIN_LIGHTNING', 'EARTH_SHOCK']


def fail(case, why):
    report['failures'].append('%s: %s' % (case, why))


async def capture(name):
    r = await call_tool('SceneCaptureToolset.SceneCaptureToolset.CaptureGameViewport', world=None, maxResolution=1600)
    data = r.get('image') if isinstance(r, dict) else None
    if data is not None and not isinstance(data, str):
        data = data['data']
    if not data:
        return None
    path = OUT / (name + '.png')
    path.write_bytes(base64.b64decode(data))
    return str(path)


def game_world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


def spell_fx(world):
    """Active NS_Spell_* components by identity (pooled components keep their object path)."""
    out = {}
    for c in unreal.ObjectIterator(unreal.NiagaraComponent):
        try:
            asset = c.get_asset()
            if c.get_world() == world and c.is_active() and asset and asset.get_name().startswith('NS_Spell_'):
                out[c.get_path_name()] = asset.get_name()
        except Exception:
            pass
    return out


def projectiles(world):
    return {a.get_path_name() for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsSpellProjectile)}


class Tracker:
    """Samples effects after each cast so everything a case creates is attributed to it."""

    def __init__(self, world):
        self.world = world
        self.baseline_fx = spell_fx(world)
        self.baseline_proj = projectiles(world)
        self.fx = {}
        self.proj = set()

    def sample(self):
        for k, v in spell_fx(self.world).items():
            if k not in self.baseline_fx:
                self.fx[k] = v
        self.proj |= projectiles(self.world) - self.baseline_proj

    def summary(self):
        names = {}
        for v in self.fx.values():
            names[v] = names.get(v, 0) + 1
        return names


def setup_view(pc, pawn, pitch):
    rot = pc.get_control_rotation()
    pc.set_control_rotation(unreal.Rotator(roll=0.0, pitch=pitch, yaw=rot.yaw))


async def finish_case(case, world, tracker, expect_impacts=True):
    tracker.sample()
    during = await capture(case + '_during')
    # Keep sampling while things play out so short-lived effects are attributed too.
    for _ in range(10):
        await asyncio.sleep(0.5)
        tracker.sample()
    alive_fx = {k: v for k, v in spell_fx(world).items() if k in tracker.fx}
    alive_proj = projectiles(world) & tracker.proj
    after = await capture(case + '_after5s')
    result = {'fx_created': tracker.summary(), 'fx_alive_after_5s': sorted(alive_fx.values()),
              'projectiles_created': len(tracker.proj), 'projectiles_alive_after_5s': len(alive_proj),
              'captures': {'during': during, 'after5s': after}}
    if alive_fx:
        fail(case, '%d spell effect(s) still active 5 s after the last cast: %s' % (len(alive_fx), sorted(alive_fx.values())))
    if alive_proj:
        fail(case, '%d projectile actor(s) still alive after 5 s' % len(alive_proj))
    if expect_impacts and 'NS_Spell_Impact' not in result['fx_created']:
        fail(case, 'no impact effect was seen')
    for k, v in result['captures'].items():
        if not v:
            fail(case, 'missing %s capture' % k)
    return result


async def ready_cast(driver, spell, limit=8.0):
    cost = driver.get_spell_mana_cost(spell)
    waited = 0.0
    while waited < limit:
        if driver.get_mana() >= cost and driver.get_spell_cooldown_remaining(spell) <= 0.0 and not driver.is_casting():
            return driver.cast_spell(spell), round(waited, 2)
        await asyncio.sleep(0.1)
        waited += 0.1
    return False, round(waited, 2)


async def case_ground10(world, pc, pawn, driver):
    setup_view(pc, pawn, -16.0)
    await asyncio.sleep(0.4)
    base = await capture('ground10_baseline')
    tracker = Tracker(world)
    casts = []
    for name in GROUND10:
        before = projectiles(world)
        ok, waited = await ready_cast(driver, getattr(unreal.HeroSpell, name))
        spawned = False
        for _ in range(12):
            await asyncio.sleep(0.1)
            tracker.sample()
            if projectiles(world) - before:
                spawned = True
        casts.append({'spell': name, 'cast': ok, 'waited_s': waited, 'projectile': spawned})
        if not ok:
            fail('ground10', '%s was refused (mana %.0f, cooldown %.1f)' % (name, driver.get_mana(),
                 driver.get_spell_cooldown_remaining(getattr(unreal.HeroSpell, name))))
        elif name in PROJECTILE_SPELLS and not spawned:
            fail('ground10', '%s cast but no projectile appeared' % name)
    result = await finish_case('ground10', world, tracker)
    result['casts'] = casts
    result['captures']['baseline'] = base
    if not base:
        fail('ground10', 'missing baseline capture')
    return result


async def release_series(world, pc, pawn, case, spells, count, interval, target_fn, expect_impacts):
    combat = pawn.get_component_by_class(unreal.ReflectionsSpellCombatComponent)
    if not combat:
        fail(case, 'pawn has no ReflectionsSpellCombatComponent')
        return {}
    setup_view(pc, pawn, -16.0)
    await asyncio.sleep(0.4)
    base = await capture(case + '_baseline')
    tracker = Tracker(world)
    loc = pawn.get_actor_location()
    fwd = pawn.get_actor_forward_vector()
    right = pawn.get_actor_right_vector()
    origin = unreal.Transform(location=loc + fwd * 60.0 + unreal.Vector(0.0, 0.0, 50.0))
    projectile_comps = set()
    for i in range(count):
        name = spells[i % len(spells)]
        before = projectiles(world)
        seen_before = {k for k, v in tracker.fx.items() if v == 'NS_Spell_Projectile'}
        combat.release_spell_at(getattr(unreal.HeroSpell, name), origin, target_fn(i, loc, fwd, right), None)
        await asyncio.sleep(interval)
        tracker.sample()
        projectile_comps |= {k for k, v in tracker.fx.items() if v == 'NS_Spell_Projectile'}
        new_fx = {k for k, v in tracker.fx.items() if v == 'NS_Spell_Projectile'} - seen_before
        if name in PROJECTILE_SPELLS and not (projectiles(world) - before) and not (tracker.proj - before) and not new_fx:
            fail(case, 'release %d (%s) produced no projectile' % (i, name))
    result = await finish_case(case, world, tracker, expect_impacts)
    result['captures']['baseline'] = base
    result['distinct_projectile_components'] = len(projectile_comps)
    if not base:
        fail(case, 'missing baseline capture')
    return result


def ground_target(i, loc, fwd, right):
    return loc + fwd * (900.0 + 150.0 * (i % 4)) + right * (-300.0 + 150.0 * (i % 5)) - unreal.Vector(0.0, 0.0, 90.0)


def sky_target(i, loc, fwd, right):
    return loc + fwd * 2000.0 + right * (-400.0 + 200.0 * i) + unreal.Vector(0.0, 0.0, 6000.0)


async def case_marks(world, pc, pawn):
    """Material check for M_Spell_GroundMark: one mark per Kind in front of the hero, held 1.5 s then faded over
    3.5 s (as the VFX subsystem does), captured across the fade; all marks must be gone after it."""
    setup_view(pc, pawn, -22.0)
    await asyncio.sleep(0.3)
    mat = unreal.load_asset('/Game/Characters/Hero/SpellVFX/Materials/M_Spell_GroundMark')
    loc = pawn.get_actor_location()
    fwd = pawn.get_actor_forward_vector()
    right = pawn.get_actor_right_vector()
    colors = [unreal.LinearColor(1.0, 0.28, 0.04, 1.0), unreal.LinearColor(0.45, 0.8, 1.0, 1.0), unreal.LinearColor(0.08, 0.42, 1.0, 1.0),
              unreal.LinearColor(0.42, 0.5, 1.0, 1.0), unreal.LinearColor(0.85, 0.52, 0.22, 1.0), unreal.LinearColor(0.7, 0.3, 1.0, 1.0)]
    marks = []
    for k in range(6):
        # 3 x 2 grid clear of the practice cube (straight ahead at ~7 m) and of the hero (bottom centre).
        p = loc + fwd * (380.0 if k < 3 else 560.0) + right * (-430.0 + 430.0 * (k % 3)) * (1.0 if k % 3 != 1 else 0.0)             + right * (0.0 if k % 3 != 1 else 0.0) - unreal.Vector(0.0, 0.0, 88.0)
        d = unreal.GameplayStatics.spawn_decal_at_location(world, mat, unreal.Vector(30.0, 95.0, 95.0), p,
                                                           unreal.Rotator(roll=0.0, pitch=-90.0, yaw=0.0), 0.0)
        mid = d.create_dynamic_material_instance()
        mid.set_scalar_parameter_value('Kind', float(k))
        mid.set_scalar_parameter_value('Seed', 13.0 * k + 1.0)
        mid.set_vector_parameter_value('Color', colors[k])
        d.set_fade_out(1.5, 3.5, False)
        marks.append(d)
    shots = {}
    for label, wait in (('0.3s', 0.3), ('2.5s', 2.2), ('4.5s', 2.0), ('5.5s', 1.0)):
        await asyncio.sleep(wait)
        shots[label] = await capture('marks_' + label)
    alive = 0
    for d in marks:
        try:
            if d.is_registered():
                alive += 1
        except Exception:
            pass
    if alive:
        fail('marks', '%d of 6 marks still exist 5.5 s after spawning' % alive)
    for k, v in shots.items():
        if not v:
            fail('marks', 'missing %s capture' % k)
    return {'captures': shots, 'marks_alive_after_5_5s': alive}


if await call_tool(APP + 'IsPIERunning'):
    raise RuntimeError('PIE is already running (someone else is testing); try again when it is free.')
await call_tool(APP + 'StartPIE', options={'warmupSeconds': 3.0})
try:
    world = game_world()
    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    pawn = pc.get_controlled_pawn()
    driver = pawn.get_component_by_class(unreal.ReflectionsSampleSpellDriver)
    if 'marks' in args:
        report['cases']['marks'] = await case_marks(world, pc, pawn)
    if 'ground10' in args:
        report['cases']['ground10'] = await case_ground10(world, pc, pawn, driver)
    if 'miss' in args:
        report['cases']['miss'] = await release_series(world, pc, pawn, 'miss', ['FIRE', 'ARCANE_BOLT', 'LIGHTNING_BOLT', 'ICE_SHARD', 'WATER'],
                                                       5, 0.3, sky_target, expect_impacts=False)
    if 'stress' in args:
        report['cases']['stress'] = await release_series(world, pc, pawn, 'stress', STRESS, 20, 0.25, ground_target, expect_impacts=True)
finally:
    await call_tool(APP + 'StopPIE')
report['result'] = 'FAIL' if report['failures'] else 'PASS'
(OUT / 'report.json').write_text(json.dumps(report, indent=2, default=str))
json.dumps(report, indent=1, default=str)
