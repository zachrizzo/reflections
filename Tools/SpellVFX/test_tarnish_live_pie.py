"""PIE check of tarnish magic through the real AI path (run inside the editor via MCP Python; claim PIE_LOCK first).

Infects the nearest crowd walker 5-14 m away (UReflectionsNpcSubsystem::SetInfection), lets npc-unify's AI fight the
player for ~14 s, and records every tarnish cast: the caster component (added by npc-unify by name), wind-ups seen,
projectiles in flight, player damage, tarnish stains. Captures the wind-up, a bolt in flight and the hit.
Writes Saved/SpellCombatTest/tarnish_live/.
"""
import base64
import json
import math
import time
from pathlib import Path

APP = 'EditorToolset.EditorAppToolset.'
SC = 'SceneCaptureToolset.SceneCaptureToolset.'
OUT = Path(unreal.Paths.project_saved_dir()).resolve() / 'SpellCombatTest' / 'tarnish_live'
OUT.mkdir(parents=True, exist_ok=True)
LOCK = Path(unreal.Paths.project_saved_dir()).resolve() / 'PIE_LOCK.json'
ME = 'spell-aim-vfx [561a1b] (Rebuild spell aiming, casting, animations and VFX)'
report = {'failures': [], 'shots': {}, 'events': []}


def flush():
    (OUT / 'report.json').write_text(json.dumps(report, indent=2, default=str))


def save(name, r):
    data = r.get('image') if isinstance(r, dict) else None
    if isinstance(data, dict):
        data = data.get('data')
    p = OUT / (name + '.png')
    if data:
        p.write_bytes(base64.b64decode(data))
    report['shots'][name] = str(p) if data else None


async def view(name, world_ref, eye, target, fov=55.0):
    d = target - eye
    camera = {'location': {'x': eye.x, 'y': eye.y, 'z': eye.z},
              'rotation': {'pitch': math.degrees(math.atan2(d.z, math.hypot(d.x, d.y))), 'yaw': math.degrees(math.atan2(d.y, d.x)), 'roll': 0.0},
              'projectionMode': 'Perspective', 'fOV': fov}
    save(name, await call_tool(SC + 'Capture', world=world_ref, camera=camera, mode='Lit',
                               options={'width': 1280, 'height': 720, 'screenPercentage': 1.0, 'visualizationSubMode': ''}))


def health(a):
    h = a.get_component_by_class(unreal.ReflectionsHealthComponent) if a else None
    return round(h.get_editor_property('health'), 2) if h else None


def tarnish_marks(world):
    n = 0
    for c in unreal.ObjectIterator(unreal.DecalComponent):
        try:
            m = c.get_decal_material()
            if c.get_world() == world and isinstance(m, unreal.MaterialInstanceDynamic) and m.get_scalar_parameter_value('Kind') >= 5.5:
                n += 1
        except Exception:
            pass
    return n


async def run():
    await call_tool(APP + 'StartPIE', options={'warmupSeconds': 3.0})
    try:
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        worlds = await call_tool(SC + 'ListWorlds')
        wl = worlds if isinstance(worlds, list) else worlds.get('returnValue', worlds)
        world_ref = next(w for w in wl if w.get('worldType') == 'PIE')['world']
        pc = unreal.GameplayStatics.get_player_controller(world, 0)
        pawn = pc.get_controlled_pawn()
        npcs = next((s for s in unreal.ObjectIterator(unreal.ReflectionsNpcSubsystem) if s.get_world() == world), None)
        loc = pawn.get_actor_location()
        cands = sorted(((a.get_actor_location() - loc).length(), a) for a in npcs.get_npc_actors()
                       if not isinstance(a, unreal.Pawn) and (health(a) or 0) > 0 and 500 < (a.get_actor_location() - loc).length() < 1400)
        if not cands:
            report['failures'].append('no walker 5-14 m away')
            return
        npc = cands[0][1]
        report['caster'] = npc.get_name()
        report['infected'] = npcs.set_infection(npc, unreal.ReflectionsNpcInfection.INFECTED, None)
        h0 = health(pawn)
        report['player_health_start'] = h0
        marks0 = tarnish_marks(world)
        t0 = time.time()
        comp = None
        casting_seen = 0
        shot_windup = shot_flight = shot_hit = False
        last_h = h0
        while time.time() - t0 < 14.0:
            if comp is None:
                comp = npc.get_component_by_class(unreal.ReflectionsTarnishCasterComponent)
                if comp:
                    report['events'].append('component added at %.1f s' % (time.time() - t0))
            c = npc.get_actor_location()
            p = pawn.get_actor_location()
            if comp and comp.is_casting():
                casting_seen += 1
                if not shot_windup:
                    f = c + (p - c) * (170.0 / max(1.0, (p - c).length()))
                    await view('1_windup', world_ref, f + unreal.Vector(0, 0, 70), c + unreal.Vector(0, 0, 90), 60.0)
                    shot_windup = True
                    report['events'].append('wind-up %s at %.1f s' % (comp.get_current_spell(), time.time() - t0))
            flying = [x for x in unreal.ObjectIterator(unreal.ReflectionsSpellProjectile) if x.get_world() == world and x.get_owner() == npc]
            if flying and not shot_flight:
                mid = (c + p) * 0.5
                d = p - c
                side = unreal.Vector(-d.y, d.x, 0.0) * (1.0 / max(1.0, math.hypot(d.x, d.y)))
                await view('2_flight', world_ref, mid + side * 480.0 + unreal.Vector(0, 0, 160), mid + unreal.Vector(0, 0, 90), 62.0)
                shot_flight = True
            h = health(pawn)
            if h is not None and last_h is not None and h < last_h - 0.01:
                report['events'].append('player hit %.1f -> %.1f at %.1f s' % (last_h, h, time.time() - t0))
                if not shot_hit:
                    await asyncio.sleep(0.1)
                    await view('3_hit', world_ref, p + unreal.Vector(-280, 200, 160), p + unreal.Vector(0, 0, 60), 65.0)
                    shot_hit = True
            last_h = h
            flush()
            await asyncio.sleep(0.05)
        report['component'] = bool(comp)
        report['casting_frames'] = casting_seen
        report['player_health_end'] = health(pawn)
        report['tarnish_marks_added'] = tarnish_marks(world) - marks0
        if not comp:
            report['failures'].append('npc-unify never added the tarnish caster component')
        if not casting_seen:
            report['failures'].append('no tarnish wind-up seen in 14 s')
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
json.dumps({k: report.get(k) for k in ('result', 'failures', 'events')}, default=str)
