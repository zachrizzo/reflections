"""Look check of the tarnish Niagara systems and decal kinds without the tarnish C++ (run in the editor via MCP Python).

Starts PIE and spawns NS_Tarnish_Bolt as a wind-up gather, as a flying bolt and as a wisp, plus NS_Tarnish_Burst and
M_Spell_GroundMark kinds 6 (stain) and 7 (burst warning) in front of the player, and captures them from a side
camera. Writes Saved/SpellCombatTest/tarnish_look/. Takes and releases the shared PIE lock.
"""
import base64
import json
import math
import time
from pathlib import Path

APP = 'EditorToolset.EditorAppToolset.'
SC = 'SceneCaptureToolset.SceneCaptureToolset.'
OUT = Path(unreal.Paths.project_saved_dir()).resolve() / 'SpellCombatTest' / 'tarnish_look'
OUT.mkdir(parents=True, exist_ok=True)
LOCK = Path(unreal.Paths.project_saved_dir()).resolve() / 'PIE_LOCK.json'
ME = 'spell-aim-vfx [561a1b] (Rebuild spell aiming, casting, animations and VFX)'
SYS = '/Game/Characters/Hero/SpellVFX/Systems/'
report = {'shots': {}}
VIOLET = unreal.LinearColor(0.30, 0.03, 0.55, 1.0)
SILVER = unreal.LinearColor(0.66, 0.70, 0.74, 1.0)
SMOKE = unreal.LinearColor(0.025, 0.01, 0.04, 0.82)


async def acquire_lock(purpose, budget_s=240):
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


def save(name, r):
    data = r.get('image') if isinstance(r, dict) else None
    if isinstance(data, dict):
        data = data.get('data')
    p = OUT / (name + '.png')
    if data:
        p.write_bytes(base64.b64decode(data))
    report['shots'][name] = str(p) if data else None


async def view(name, world_ref, eye, target, fov=50.0):
    d = target - eye
    camera = {'location': {'x': eye.x, 'y': eye.y, 'z': eye.z},
              'rotation': {'pitch': math.degrees(math.atan2(d.z, math.hypot(d.x, d.y))), 'yaw': math.degrees(math.atan2(d.y, d.x)), 'roll': 0.0},
              'projectionMode': 'Perspective', 'fOV': fov}
    save(name, await call_tool(SC + 'Capture', world=world_ref, camera=camera, mode='Lit',
                               options={'width': 1280, 'height': 720, 'screenPercentage': 1.0, 'visualizationSubMode': ''}))


def styled(world, system, loc, rot=None, **floats):
    c = unreal.NiagaraFunctionLibrary.spawn_system_at_location(world, system, loc, rot or unreal.Rotator(), unreal.Vector(1, 1, 1),
                                                               True, False, unreal.NCPoolMethod.NONE, True)
    c.set_variable_linear_color('User.Color', VIOLET)
    c.set_variable_linear_color('User.Color2', SILVER)
    c.set_variable_linear_color('User.SmokeColor', SMOKE)
    for k, v in floats.items():
        c.set_variable_float('User.' + k, float(v))
    c.activate(True)
    return c


def decal(world, mat, loc, radius, kind, strength):
    d = unreal.GameplayStatics.spawn_decal_at_location(world, mat, unreal.Vector(30.0, radius, radius), loc,
                                                       unreal.Rotator(roll=0.0, pitch=-90.0, yaw=0.0), 0.0)
    m = d.create_dynamic_material_instance()
    m.set_scalar_parameter_value('Kind', kind)
    m.set_scalar_parameter_value('Seed', 17.0)
    m.set_scalar_parameter_value('Strength', strength)
    m.set_vector_parameter_value('Color', VIOLET)
    return d


await acquire_lock('tarnish look check (Niagara + decals only, no casts)', 150)
await call_tool(APP + 'StartPIE', options={'warmupSeconds': 3.0})
try:
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    worlds = await call_tool(SC + 'ListWorlds')
    wl = worlds if isinstance(worlds, list) else worlds.get('returnValue', worlds)
    world_ref = next(w for w in wl if w.get('worldType') == 'PIE')['world']
    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    pawn = pc.get_controlled_pawn()
    bolt = unreal.load_asset(SYS + 'NS_Tarnish_Bolt')
    burst = unreal.load_asset(SYS + 'NS_Tarnish_Burst')
    mark = unreal.load_asset('/Game/Characters/Hero/SpellVFX/Materials/M_Spell_GroundMark')
    p = pawn.get_actor_location()
    fwd = pawn.get_actor_forward_vector()
    fwd.z = 0.0
    fwd = fwd * (1.0 / max(0.001, fwd.length()))
    right = unreal.Vector(-fwd.y, fwd.x, 0.0)
    # Ground under the player.
    hit = unreal.SystemLibrary.line_trace_single(world, p, p - unreal.Vector(0, 0, 400), unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
                                                 False, [pawn], unreal.DrawDebugTrace.NONE, True)
    ground = hit.to_tuple()[4] if hit else p - unreal.Vector(0, 0, 90)
    report['ground_z'] = ground.z
    base = ground + fwd * 600.0
    # 1. Wind-up gather at "hand" height, 2. flying bolt and 3. wisp moved by script, 4. burst, 5. decals.
    gather = styled(world, bolt, base + right * -160.0 + unreal.Vector(0, 0, 130), Scale=0.6, Gather=1.0, Wisp=0.0)
    flyer = styled(world, bolt, base + right * 380.0 + unreal.Vector(0, 0, 120), Scale=1.0, Gather=0.0, Wisp=0.0)
    wisp = styled(world, bolt, base + right * 380.0 + unreal.Vector(0, 0, 220), Scale=1.3, Gather=0.0, Wisp=1.0)
    stain = decal(world, mark, base + right * 120.0, 110.0, 6.0, 1.0)
    warning = decal(world, mark, base + fwd * 420.0, 340.0, 7.0, 0.6)
    t0 = time.time()
    while time.time() - t0 < 1.1:
        a = (time.time() - t0) / 1.1
        flyer.set_world_location(base + right * (380.0 - 700.0 * a) + unreal.Vector(0, 0, 120), False, False)
        wisp.set_world_location(base + right * (380.0 - 300.0 * a) + unreal.Vector(0, 0, 220), False, False)
        await asyncio.sleep(0.03)
    eye = base - fwd * 520.0 + right * 60.0 + unreal.Vector(0, 0, 210)
    await view('1_windup_bolt_wisp_stain', world_ref, eye, base + unreal.Vector(0, 0, 90), 62.0)
    styled(world, burst, base + right * 120.0 + unreal.Vector(0, 0, 20), unreal.Rotator(pitch=90.0, yaw=0.0, roll=0.0),
           Scale=1.0, Amount=1.0, LightScale=1.0)
    await asyncio.sleep(0.12)
    await view('2_bolt_impact_burst', world_ref, base + right * 120.0 - fwd * 330.0 + unreal.Vector(0, 0, 150),
               base + right * 120.0 + unreal.Vector(0, 0, 40), 60.0)
    big = styled(world, burst, base + fwd * 420.0 + unreal.Vector(0, 0, 20), unreal.Rotator(pitch=90.0, yaw=0.0, roll=0.0),
                 Scale=4.0, Amount=1.0, LightScale=1.0)
    await view('3_burst_warning_ring', world_ref, base + fwd * 420.0 - fwd * 520.0 + unreal.Vector(0, 0, 520),
               base + fwd * 420.0, 70.0)
    await asyncio.sleep(0.15)
    await view('4_burst_blast', world_ref, base + fwd * 420.0 - fwd * 620.0 + unreal.Vector(0, 0, 330),
               base + fwd * 420.0 + unreal.Vector(0, 0, 60), 68.0)
    await asyncio.sleep(0.9)
    await view('5_burst_smoke_after', world_ref, base + fwd * 420.0 - fwd * 620.0 + unreal.Vector(0, 0, 330),
               base + fwd * 420.0 + unreal.Vector(0, 0, 60), 68.0)
finally:
    await call_tool(APP + 'StopPIE')
    release_lock()
(OUT / 'report.json').write_text(json.dumps(report, indent=2, default=str))
json.dumps(report, default=str)
