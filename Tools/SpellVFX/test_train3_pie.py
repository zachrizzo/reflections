"""Post-train PIE check (run inside the editor via the MCP Python tool): ground marks on real impacts, aim lock and
homing on the unified-NPC walkers, the V2 aim-hold pose and camera placement. Writes Saved/SpellCombatTest/train3/.
"""
import base64
import json
import math
from pathlib import Path

APP = 'EditorToolset.EditorAppToolset.'
SC = 'SceneCaptureToolset.SceneCaptureToolset.'
OUT = Path(unreal.Paths.project_saved_dir()).resolve() / 'SpellCombatTest' / 'train3'
OUT.mkdir(parents=True, exist_ok=True)
report = {'failures': []}


def fail(why):
    report['failures'].append(why)


async def shot(name):
    r = await call_tool(SC + 'CaptureGameViewport', world=None, maxResolution=1600)
    data = r.get('image') if isinstance(r, dict) else None
    if isinstance(data, dict):
        data = data.get('data')
    if not data:
        fail('missing capture ' + name)
        return None
    p = OUT / (name + '.png')
    p.write_bytes(base64.b64decode(data))
    return str(p)


def marks(world):
    n = 0
    for c in unreal.ObjectIterator(unreal.DecalComponent):
        try:
            m = c.get_decal_material()
            if c.get_world() == world and m and m.get_base_material().get_name() == 'M_Spell_GroundMark':
                n += 1
        except Exception:
            pass
    return n


def health_of(actor):
    h = actor.get_component_by_class(unreal.ReflectionsHealthComponent)
    return h.get_editor_property('health') if h else None


def aim_at(pc, point, offset_yaw=0.0):
    cam = pc.player_camera_manager.get_camera_location()
    d = point - cam
    pc.set_control_rotation(unreal.Rotator(roll=0.0, pitch=math.degrees(math.atan2(d.z, math.hypot(d.x, d.y))),
                                           yaw=math.degrees(math.atan2(d.y, d.x)) + offset_yaw))


def aim_entries():
    return [{'action': unreal.load_object(None, '/Game/Input/IA_Aim.IA_Aim'), 'value': {'x': 1.0, 'y': 0.0, 'z': 0.0}},
            {'key': {'keyName': 'RightMouseButton'}, 'value': {'x': 1.0, 'y': 0.0, 'z': 0.0}}]


async def ready_cast(driver, spell, limit=8.0):
    cost = driver.get_spell_mana_cost(spell)
    t = 0.0
    while t < limit:
        if driver.get_mana() >= cost and driver.get_spell_cooldown_remaining(spell) <= 0.0 and not driver.is_casting():
            return driver.cast_spell(spell)
        await asyncio.sleep(0.1)
        t += 0.1
    return False


def chest(actor):
    origin, extent = actor.get_actor_bounds(True)
    return origin + unreal.Vector(0.0, 0.0, extent.z * 0.25)


async def case_marks(world, pc, driver):
    rot = pc.get_control_rotation()
    pc.set_control_rotation(unreal.Rotator(roll=0.0, pitch=-16.0, yaw=rot.yaw + 25.0))
    await asyncio.sleep(0.3)
    peak = 0
    casts = []
    for name in ('FIRE', 'ICE_SHARD', 'WATER', 'LIGHTNING_BOLT', 'ARCANE_BOLT', 'EARTH_SHOCK'):
        ok = await ready_cast(driver, getattr(unreal.HeroSpell, name))
        casts.append((name, ok))
        if not ok:
            fail('marks: %s refused' % name)
        for _ in range(8):
            await asyncio.sleep(0.1)
            peak = max(peak, marks(world))
    await asyncio.sleep(0.2)
    right_after = marks(world)
    s1 = await shot('marks_after_impacts')
    await asyncio.sleep(5.8)
    later = marks(world)
    s2 = await shot('marks_6s_later')
    if peak == 0:
        fail('marks: no ground mark was spawned by real impacts')
    return {'casts': casts, 'peak_marks': peak, 'marks_right_after': right_after, 'marks_6s_later': later, 'shots': [s1, s2]}


async def fire_at(world, pc, driver, walker, spell, tag):
    aim_at(pc, chest(walker))
    hold = asyncio.ensure_future(call_tool('InputToolset.InputToolset.ApplyInput', entries=aim_entries(), durationSeconds=3.0))
    await asyncio.sleep(0.5)
    aim_at(pc, chest(walker))
    await asyncio.sleep(0.15)
    lock_shot = await shot('%s_reticle' % tag)
    h0 = health_of(walker)
    driver.set_selected_spell(spell)
    ok = await ready_cast(driver, spell, 6.0)
    # Hold the camera still after release: any hit on a moving walker now comes from aim lock + homing.
    flight = []
    hit_at = None
    for i in range(22):
        await asyncio.sleep(0.1)
        h = health_of(walker)
        if h is not None and h0 is not None and h < h0 and hit_at is None:
            hit_at = round(0.1 * (i + 1), 1)
        if i in (3, 6):
            flight.append(await shot('%s_flight_%d' % (tag, i)))
    await hold
    return {'walker': walker.get_name(), 'friendly': walker.actor_has_tag('Friendly'), 'cast': ok,
            'health_before': h0, 'health_after': health_of(walker), 'hit_after_s': hit_at,
            'shots': [lock_shot] + flight}


async def case_walkers(world, pc, pawn, driver):
    npcs = None
    for sub in unreal.ObjectIterator(unreal.ReflectionsNpcSubsystem):
        try:
            if sub.get_world() == world:
                npcs = sub
                break
        except Exception:
            pass
    loc = pawn.get_actor_location()
    walkers = []
    for a in (npcs.get_npc_actors() if npcs else []):
        if isinstance(a, unreal.Pawn):
            continue
        h = health_of(a)
        d = (a.get_actor_location() - loc).length()
        if h and h > 0 and 500.0 < d < 2600.0:
            walkers.append((d, a))
    walkers.sort(key=lambda x: x[0])
    out = {'npc_actors': len(npcs.get_npc_actors()) if npcs else 0, 'walkers_in_range': len(walkers)}
    if not walkers:
        fail('walkers: no live actor NPC between 5 and 26 m')
        return out
    out['fireball'] = await fire_at(world, pc, driver, walkers[0][1], unreal.HeroSpell.FIRESTORM, 'walker_fireball')
    await asyncio.sleep(0.6)
    alive = [w for d, w in walkers if (health_of(w) or 0) > 0]
    if alive:
        out['firebolt'] = await fire_at(world, pc, driver, alive[0], unreal.HeroSpell.FIRE, 'walker_firebolt')
    for k in ('fireball', 'firebolt'):
        r = out.get(k)
        if r and r['cast'] and r['hit_after_s'] is None:
            fail('walkers: %s cast at %s but it took no damage' % (k, r['walker']))
        if r and not r['cast']:
            fail('walkers: %s refused' % k)
    return out


async def case_pose(world, pc, pawn):
    aim_at(pc, pawn.get_actor_location() + pawn.get_actor_forward_vector() * 800.0)
    hold = asyncio.ensure_future(call_tool('InputToolset.InputToolset.ApplyInput', entries=aim_entries(), durationSeconds=2.4))
    await asyncio.sleep(1.3)
    game = await shot('pose_game')
    cam = pc.player_camera_manager.get_camera_location()
    head = pawn.get_actor_location() + unreal.Vector(0, 0, 70.0)
    inside = (cam - head).length()
    meshes = {}
    for m in pawn.get_components_by_class(unreal.SkeletalMeshComponent):
        asset = m.get_skinned_asset()
        meshes[m.get_name()] = {'asset': asset.get_name() if asset else None, 'visible': m.is_visible(),
                                'hidden_in_game': m.get_editor_property('hidden_in_game')}
    driver_mesh = meshes.get('CharacterMesh0', {})
    if driver_mesh and driver_mesh.get('visible') and not driver_mesh.get('hidden_in_game'):
        fail('pose: the GASP driver mesh CharacterMesh0 (%s) is visible on the hero' % driver_mesh.get('asset'))
    await hold
    return {'game_shot': game, 'camera_to_head_cm': round(inside, 1), 'meshes': meshes}


import time
LOCK = Path(unreal.Paths.project_saved_dir()).resolve() / 'PIE_LOCK.json'
ME = 'spell-aim-vfx [561a1b] (Rebuild spell aiming, casting, animations and VFX)'


async def acquire_lock(purpose, budget_s=240):
    # Shared rule: wait while another owner's unexpired lock exists (poll 15 s), then write ours (<= now + 240 s).
    for _ in range(80):
        try:
            cur = json.loads(LOCK.read_text())
        except Exception:
            cur = None
        if cur and cur.get('owner') != ME and float(cur.get('expires_epoch', 0)) > time.time():
            await asyncio.sleep(15.0)
            continue
        if not await call_tool(APP + 'IsPIERunning'):
            now = time.time()
            LOCK.write_text(json.dumps({'owner': ME, 'purpose': purpose, 'acquired_epoch': now,
                                        'expires_epoch': now + min(budget_s, 240)}))
            return True
        await asyncio.sleep(15.0)
    raise RuntimeError('PIE lock not available')


def release_lock():
    try:
        if json.loads(LOCK.read_text()).get('owner') == ME:
            LOCK.unlink()
    except Exception:
        pass


async def case_ip_keys(world, pc):
    # N (IA_NextPawn) and F8 (IA_NextVisualOverride) must not change the hero.
    pawn0 = pc.get_controlled_pawn()
    def look(p):
        meshes = sorted('%s=%s' % (m.get_name(), m.get_skinned_asset().get_name() if m.get_skinned_asset() else None)
                        for m in p.get_components_by_class(unreal.SkeletalMeshComponent))
        return p.get_name(), p.get_class().get_name(), meshes
    before = look(pawn0)
    for key in ('N', 'F8', 'N', 'F8'):
        await call_tool('InputToolset.InputToolset.ApplyInput', entries=[{'key': {'keyName': key}, 'value': {'x': 1.0, 'y': 0.0, 'z': 0.0}}], durationSeconds=0.15)
        await asyncio.sleep(0.35)
    after = look(pc.get_controlled_pawn())
    if before != after:
        fail('ip_keys: N/F8 changed the hero: %s -> %s' % (before[:2], after[:2]))
    return {'before': before[:2], 'after': after[:2], 'meshes_unchanged': before[2] == after[2]}


await acquire_lock('train3 check: marks, NPC aim/homing, aim pose, N/F8 block', 200)
await call_tool(APP + 'StartPIE', options={'warmupSeconds': 3.0})
try:
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    pawn = pc.get_controlled_pawn()
    driver = pawn.get_component_by_class(unreal.ReflectionsSampleSpellDriver)
    which = ARGS or ['pose', 'marks', 'walkers', 'ip']
    if 'ip' in which:
        report['ip_keys'] = await case_ip_keys(world, pc)
        pawn = pc.get_controlled_pawn()
        driver = pawn.get_component_by_class(unreal.ReflectionsSampleSpellDriver)
    if 'pose' in which:
        report['pose'] = await case_pose(world, pc, pawn)
    if 'marks' in which:
        report['marks'] = await case_marks(world, pc, driver)
    if 'walkers' in which:
        report['walkers'] = await case_walkers(world, pc, pawn, driver)
except Exception as e:
    fail('script error: %r' % e)
finally:
    await call_tool(APP + 'StopPIE')
    release_lock()
report['result'] = 'FAIL' if report['failures'] else 'PASS'
(OUT / 'report.json').write_text(json.dumps(report, indent=2, default=str))
json.dumps(report, default=str)
