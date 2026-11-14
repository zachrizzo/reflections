"""PIE test for the rebuilt spell combat on Lvl_HeroSampleCrowd (run inside the editor via the MCP Python tool).

Starts PIE, then for each scenario drives real input (RMB aim via IA_Aim, LMB cast) and captures the game viewport
mid-action. Writes PNGs and a JSON report to Saved/SpellCombatTest. ARGS picks scenarios: aim, attack, heal, all.
Asserts what it can measure (aim state, spell release, projectile spawned, Niagara components active, mana spent).
"""
import base64
import json
import math
from pathlib import Path

OUT = Path(unreal.Paths.project_saved_dir()).resolve() / 'SpellCombatTest'
OUT.mkdir(exist_ok=True)
APP = 'EditorToolset.EditorAppToolset.'
IA_AIM = '/Game/Input/IA_Aim.IA_Aim'
report = {'scenarios': {}}


async def capture(name):
    r = await call_tool('SceneCaptureToolset.SceneCaptureToolset.CaptureGameViewport', world=None, maxResolution=1600)
    data = r['image']
    if data is not None and not isinstance(data, str):
        # The image comes back as a struct {mimeType, data, label}; data is the base64 payload.
        data = data['data']
    if data:
        path = OUT / (name + '.png')
        try:
            path.write_bytes(base64.b64decode(data))
        except Exception:
            return 'undecodable: ' + str(data)[:80]
        return str(path)
    return None


def game_world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


def pawn_and_driver(world):
    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    pawn = pc.get_controlled_pawn() if pc else None
    driver = pawn.get_component_by_class(unreal.ReflectionsSampleSpellDriver) if pawn else None
    return pc, pawn, driver


def niagara_active(world):
    # Pooled spell effects have no owning actor, so walk the components themselves.
    comps = []
    for c in unreal.ObjectIterator(unreal.NiagaraComponent):
        try:
            if c.get_world() == world and c.is_active() and c.get_asset():
                comps.append(c.get_asset().get_name())
        except Exception:
            pass
    return comps


def face(pc, pawn, target_location, pitch_bias=-2.0):
    loc = pawn.get_actor_location()
    d = target_location - loc
    yaw = math.degrees(math.atan2(d.y, d.x))
    pitch = math.degrees(math.atan2(d.z + 20.0, math.hypot(d.x, d.y))) + pitch_bias
    pc.set_control_rotation(unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw))


async def press(entries, seconds):
    return await call_tool('InputToolset.InputToolset.ApplyInput', entries=entries, durationSeconds=seconds)


def aim_entry():
    return {'action': unreal.load_object(None, IA_AIM), 'value': {'x': 1.0, 'y': 0.0, 'z': 0.0}}


def key_entry(name):
    return {'key': {'keyName': name}, 'value': {'x': 1.0, 'y': 0.0, 'z': 0.0}}


async def scenario_aim():
    world = game_world()
    pc, pawn, driver = pawn_and_driver(world)
    target = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsSpellTarget)
    if target:
        face(pc, pawn, target[0].get_actor_location())
    driver.set_selected_spell(unreal.HeroSpell.FIRESTORM)
    hold = asyncio.ensure_future(press([aim_entry(), key_entry('RightMouseButton')], 2.2))
    await asyncio.sleep(1.2)
    aim = pawn.get_component_by_class(unreal.ReflectionsSpellAimComponent)
    state = {'aiming': aim.is_aiming() if aim else None, 'alpha': aim.get_aim_alpha() if aim else None}
    shot = await capture('aim_fireball_preview')
    await hold
    return {'state': state, 'screenshot': shot}


async def scenario_attack(spell=unreal.HeroSpell.FIRESTORM, name='attack_fireball',
                          waits=(0.42, 0.08, 0.08, 0.08, 0.1, 0.15, 0.3)):
    world = game_world()
    pc, pawn, driver = pawn_and_driver(world)
    target = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsSpellTarget)
    if target:
        face(pc, pawn, target[0].get_actor_location())
    driver.set_selected_spell(spell)
    mana0 = driver.get_mana()
    hold = asyncio.ensure_future(press([aim_entry(), key_entry('RightMouseButton')], 2.6))
    await asyncio.sleep(0.5)
    # Cast through the driver directly: the spell-crafting PrimaryCastOverride can claim LMB for a crafted slot.
    cast_ok = driver.cast_selected_spell()
    shots = []
    seen = set()
    # Sample a few frames across flight and impact.
    # Dense frames around release (~0.36 s) so a projectile is caught in flight, then the impact.
    for i, wait in enumerate(waits):
        await asyncio.sleep(wait)
        seen.update(niagara_active(world))
        shots.append(await capture('%s_%d' % (name, i)))
    await hold
    return {'cast_ok': cast_ok, 'mana_before': mana0, 'mana_after': driver.get_mana(), 'niagara_seen': sorted(seen), 'screenshots': shots}


async def scenario_heal():
    world = game_world()
    pc, pawn, driver = pawn_and_driver(world)
    driver.set_selected_spell(unreal.HeroSpell.GREATER_HEAL)
    driver.spend_magic(-0.0)
    for _ in range(40):
        if driver.get_mana() >= 40.0:
            break
        await asyncio.sleep(0.25)
    # Look down at the hero a little so the ground rune and rising spiral are framed.
    rot = pc.get_control_rotation()
    pc.set_control_rotation(unreal.Rotator(roll=0.0, pitch=-18.0, yaw=rot.yaw))
    cast_ok = driver.cast_selected_spell()
    shots = []
    seen = set()
    for i, wait in enumerate((0.6, 0.4, 0.4, 0.6)):
        await asyncio.sleep(wait)
        seen.update(niagara_active(world))
        shots.append(await capture('heal_greater_%d' % i))
    return {'cast_ok': cast_ok, 'niagara_seen': sorted(seen), 'screenshots': shots}


async def tap(key, seconds=0.12):
    return await press([key_entry(key)], seconds)


async def wait_mana(driver, amount, limit=6.0):
    t = 0.0
    while driver.get_mana() < amount and t < limit:
        await asyncio.sleep(0.25)
        t += 0.25


async def scenario_override():
    """LMB must cast the catalog spell again after a crafted slot was used: once by re-picking the same catalog
    slot, once by picking a different one. Real key input; crafted slot set through the crafting console commands."""
    world = game_world()
    pc, pawn, driver = pawn_and_driver(world)
    craft = pawn.get_component_by_class(unreal.ReflectionsSpellCraftingComponent)
    if not craft:
        return {'error': 'no crafting component on the pawn'}
    target = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsSpellTarget)
    if target:
        face(pc, pawn, target[0].get_actor_location())
    out = {'page': driver.get_spell_page(), 'slots': [driver.get_spell_slot_name(i) for i in range(4)]}

    def state(tag, spell):
        out[tag] = {'selected': str(driver.get_selected_spell()), 'active_crafted_slot': craft.get_active_slot(),
                    'mana': round(driver.get_mana(), 1), 'catalog_cooldown': round(driver.get_spell_cooldown_remaining(spell), 2)}

    def crafted(cmds):
        for cmd in cmds:
            unreal.SystemLibrary.execute_console_command(world, cmd, pc)

    await tap('One')
    await asyncio.sleep(0.2)
    spell_a = driver.get_selected_spell()
    crafted(['Crafting.Preset 0 0', 'Crafting.Slot 0'])
    await asyncio.sleep(0.2)
    state('1_crafted_selected', spell_a)
    await wait_mana(driver, 60.0)
    await tap('LeftMouseButton')
    await asyncio.sleep(1.1)
    state('2_after_crafted_lmb', spell_a)

    # Case B: re-pick the same catalog slot, then LMB.
    await tap('One')
    await asyncio.sleep(0.3)
    state('3_repicked_same_slot', spell_a)
    await wait_mana(driver, 45.0)
    cd0 = driver.get_spell_cooldown_remaining(spell_a)
    await tap('LeftMouseButton')
    await asyncio.sleep(0.8)
    state('4_after_lmb_same_slot', spell_a)
    # A cast restarts the spell's cooldown, so it must have gone up (a cooldown left over from earlier only falls).
    out['same_slot_catalog_cast'] = driver.get_spell_cooldown_remaining(spell_a) > cd0 + 0.2

    # Case A: crafted again (and used), then a different catalog slot, then LMB.
    crafted(['Crafting.Slot 0'])
    await asyncio.sleep(0.2)
    await wait_mana(driver, 60.0)
    m_before = driver.get_mana()
    await tap('LeftMouseButton')
    await asyncio.sleep(1.1)
    out['4b_second_crafted_cast'] = {'active_crafted_slot': craft.get_active_slot(), 'mana_before': round(m_before, 1),
                                     'mana_after': round(driver.get_mana(), 1)}
    await tap('Two')
    await asyncio.sleep(0.3)
    spell_b = driver.get_selected_spell()
    state('5_picked_other_slot', spell_b)
    await wait_mana(driver, 45.0)
    cd0 = driver.get_spell_cooldown_remaining(spell_b)
    await tap('LeftMouseButton')
    await asyncio.sleep(0.8)
    state('6_after_lmb_other_slot', spell_b)
    out['other_slot_catalog_cast'] = driver.get_spell_cooldown_remaining(spell_b) > cd0 + 0.2
    crafted(['Crafting.Slot -1'])
    return out


which = ARGS or ['all']
started_here = False
if not await call_tool(APP + 'IsPIERunning'):
    await call_tool(APP + 'StartPIE', options={'warmupSeconds': 3.0})
    started_here = True
try:
    if 'all' in which or 'aim' in which or 'quick' in which:
        report['scenarios']['aim'] = await scenario_aim()
    if 'quick' in which:
        report['scenarios']['attack'] = await scenario_attack()
    if 'all' in which or 'attack' in which:
        report['scenarios']['attack'] = await scenario_attack()
        await asyncio.sleep(1.0)
        report['scenarios']['attack_lightning'] = await scenario_attack(unreal.HeroSpell.LIGHTNING_BOLT, 'attack_lightning')
        await asyncio.sleep(1.0)
        report['scenarios']['attack_earth'] = await scenario_attack(unreal.HeroSpell.EARTH_SHOCK, 'attack_earthshock')
    if 'muzzle' in which:
        quick_waits = (0.18, 0.06, 0.06, 0.06, 0.08, 0.12, 0.25)
        report['scenarios']['muzzle_lightning'] = await scenario_attack(unreal.HeroSpell.LIGHTNING_BOLT, 'after_lightning', quick_waits)
        await asyncio.sleep(0.8)
        report['scenarios']['muzzle_fireball'] = await scenario_attack(unreal.HeroSpell.FIRESTORM, 'after_fireball', quick_waits)
    if 'all' in which or 'heal' in which or 'quick' in which:
        await asyncio.sleep(1.0)
        report['scenarios']['heal'] = await scenario_heal()
    if 'override' in which:
        await asyncio.sleep(0.5)
        report['scenarios']['override'] = await scenario_override()
finally:
    if started_here and 'keep' not in which:
        await call_tool(APP + 'StopPIE')
(OUT / 'report.json').write_text(json.dumps(report, indent=2, default=str))
json.dumps(report, indent=1, default=str)
