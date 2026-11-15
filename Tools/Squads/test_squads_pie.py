"""PIE check for enemy squads on Lvl_HeroSampleCrowd (paste into the editor's execute_python; top-level await).

One PIE run, under 3 minutes, stopped at the end even on failure. Nothing is saved.
  1. spawn two test squads (Squads.SpawnTest 2) with Squads.Passive 1 so they only march
  2. capture the marching formation from an offscreen camera
  3. engage: casters wind up and throw spells, melee soldiers close in; capture a caster mid-cast
  4. hit soldiers with real player spells (the hero's spell component) until they die and ragdoll
Writes Saved/SquadsTest/*.png and Saved/SquadsTest/report.json.
"""
import asyncio
import base64
import json
import math
import os
import time


# ---- Shared PIE lock (team rule): wait for someone else's unexpired lock, hold ours for at most 240 s. ----
LOCK_PATH = os.path.join(unreal.Paths.project_saved_dir(), 'PIE_LOCK.json')
LOCK_OWNER = 'squads (enemy soldier squads side session)'


async def acquire_pie_lock(purpose, seconds=240, wait_limit=600):
    started = time.time()
    while True:
        try:
            with open(LOCK_PATH) as f:
                held = json.load(f)
        except Exception:
            held = None
        if not held or held.get('owner') == LOCK_OWNER or held.get('expires_epoch', 0) <= time.time():
            break
        if time.time() - started > wait_limit:
            raise RuntimeError('PIE lock held by %s' % held.get('owner'))
        await asyncio.sleep(15.0)
    now = time.time()
    with open(LOCK_PATH, 'w') as f:
        json.dump({'owner': LOCK_OWNER, 'purpose': purpose, 'acquired_epoch': int(now),
                   'expires_epoch': int(now + min(seconds, 240))}, f)


def release_pie_lock():
    try:
        with open(LOCK_PATH) as f:
            held = json.load(f)
        if held.get('owner') == LOCK_OWNER:
            os.remove(LOCK_PATH)
    except Exception:
        pass

OUT = os.path.join(unreal.Paths.project_saved_dir(), 'SquadsTest')
os.makedirs(OUT, exist_ok=True)
report = {'steps': []}


def log(step, **kw):
    kw['step'] = step
    kw['t'] = round(time.time() - T0, 1)
    report['steps'].append(kw)


def ename(e):
    return getattr(e, 'name', str(e))


def unwrap(r):
    return r.get('returnValue', r) if isinstance(r, dict) and 'returnValue' in r else r


def game_world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


def cmd(world, text):
    unreal.SystemLibrary.execute_console_command(world, text)


def squads(world):
    return list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ReflectionsSquad))


def members(squad):
    return list(squad.get_editor_property('members'))


def loc(actor):
    v = actor.get_actor_location()
    return [round(v.x), round(v.y), round(v.z)]


async def capture(world, name, cam_loc, look_at, fov=60.0):
    d = unreal.Vector(look_at.x - cam_loc.x, look_at.y - cam_loc.y, look_at.z - cam_loc.z)
    rot = unreal.MathLibrary.make_rot_from_x(d)
    res = await call_tool('SceneCaptureToolset.SceneCaptureToolset.Capture',
                          world={'refPath': world.get_path_name()},
                          camera={'location': {'x': cam_loc.x, 'y': cam_loc.y, 'z': cam_loc.z},
                                  'rotation': {'pitch': rot.pitch, 'yaw': rot.yaw, 'roll': 0.0},
                                  'projectionMode': 'Perspective', 'fOV': fov},
                          mode='Lit', options={'width': 1600, 'height': 900, 'screenPercentage': 1.0})
    res = unwrap(res)
    img = res.get('image') if isinstance(res, dict) else None
    path = os.path.join(OUT, name + '.png')
    if img:
        if not isinstance(img, (str, bytes, bytearray)):
            # The toolset returns {data/mimeType}-style dicts; take the payload field.
            keys = list(img.keys())
            report.setdefault('image_keys', keys)
            img = next((img[k] for k in keys if isinstance(img[k], (str, bytes, bytearray)) and len(img[k]) > 1000), None)
            if img is None:
                return None
        data = img if isinstance(img, (bytes, bytearray)) else base64.b64decode(img.split(',')[-1])
        report.setdefault('images', []).append([name, res.get('width'), res.get('height'), res.get('warnings')])
        with open(path, 'wb') as f:
            f.write(data)
    return path


def heading(squad):
    """Direction of travel: the leader's locomotion pawn velocity (the look actor rides on it)."""
    for m in members(squad):
        if m.actor and m.actor.get_attach_parent_actor():
            v = m.actor.get_attach_parent_actor().get_velocity()
            if v.length() > 10:
                return unreal.Vector(v.x, v.y, 0).normal()
    return unreal.Vector(1, 0, 0)


def centroid(actors):
    pts = [a.get_actor_location() for a in actors]
    n = max(1, len(pts))
    return unreal.Vector(sum(p.x for p in pts) / n, sum(p.y for p in pts) / n, sum(p.z for p in pts) / n)


T0 = time.time()
if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
    raise RuntimeError('PIE already running (another session); not starting')
await acquire_pie_lock('squads: march + cast captures, kills')
unreal.SystemLibrary.execute_console_command(None, 'Squads.StartPatrol 0')  # scripted checks index their own squads
await call_tool('EditorToolset.EditorAppToolset.StartPIE', options={'warmupSeconds': 2.0})
try:
    world = game_world()
    cmd(world, 'Squads.Passive 1')
    cmd(world, 'Squads.SpawnTest 2')
    await asyncio.sleep(9.0)
    sq = squads(world)
    # Builds before the 13:45 train turned the old physics flinch on for soldiers; it crashed the editor. Switch it off.
    for s_ in sq:
        for m in members(s_):
            npc = m.actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent) if m.actor else None
            if npc:
                npc.set_editor_property('enable_physical_hit_reaction', False)
    log('spawned', squads=[(s.get_name(), ename(s.get_editor_property('state')), s.get_alive_count(),
                            [ename(m.state) for m in members(s)]) for s in sq])
    # Marching formation, from a raised three-quarter view beside the column.
    col = sq[0]
    alive = [m.actor for m in members(col) if m.actor]
    c = centroid(alive)
    fwd = heading(col)
    side = unreal.Vector(-fwd.y, fwd.x, 0)
    cam = unreal.Vector(c.x + side.x * 650 + fwd.x * 500, c.y + side.y * 650 + fwd.y * 500, c.z + 330)
    report['march_column'] = await capture(world, '1_march_column', cam, unreal.Vector(c.x, c.y, c.z + 80))
    line = sq[1] if len(sq) > 1 else None
    if line:
        alive = [m.actor for m in members(line) if m.actor]
        c2 = centroid(alive)
        f2 = heading(line)
        cam2 = unreal.Vector(c2.x + f2.x * 900, c2.y + f2.y * 900, c2.z + 380)
        report['march_line'] = await capture(world, '2_march_line', cam2, unreal.Vector(c2.x, c2.y, c2.z + 80))
    log('formation', column=[loc(m.actor) for m in members(col) if m.actor])

    # Engage.
    cmd(world, 'Squads.Passive 0')
    cmd(world, 'Squads.Engage')
    await asyncio.sleep(0.3)
    cmd(world, 'Squads.Cast')
    await asyncio.sleep(0.55)
    caster = None
    for s in sq:
        for m in members(s):
            if ename(m.cast_phase).endswith('WINDUP') and m.actor:
                caster = m.actor
                break
        if caster:
            break
    if caster:
        p = caster.get_actor_location()
        player = unreal.GameplayStatics.get_player_pawn(world, 0)
        to = player.get_actor_location() - p
        to.z = 0
        to = to.normal()
        right = unreal.Vector(-to.y, to.x, 0)
        cam = unreal.Vector(p.x + to.x * 330 + right.x * 260, p.y + to.y * 330 + right.y * 260, p.z + 150)
        report['caster'] = await capture(world, '3_caster_mid_cast', cam, unreal.Vector(p.x, p.y, p.z + 110), 55.0)
    log('engaged', casts=[[m.casts_released for m in members(s)] for s in sq], caster=caster.get_name() if caster else None)
    await asyncio.sleep(6.0)
    log('fight', casts=[[m.casts_released for m in members(s)] for s in sq],
        states=[[ename(m.state) for m in members(s)] for s in sq],
        hero_hp=[c.get_editor_property('health') for c in unreal.GameplayStatics.get_player_pawn(world, 0).get_components_by_class(unreal.ReflectionsHealthComponent)])

    # Player spells kill soldiers: fire real catalog spells from the hero's spell component.
    player = unreal.GameplayStatics.get_player_pawn(world, 0)
    spells = player.get_component_by_class(unreal.ReflectionsSpellCombatComponent)
    hp = player.get_component_by_class(unreal.ReflectionsHealthComponent)
    targets = [m.actor for m in members(sq[0]) if m.actor][:3]
    for target in targets:
        for shot in range(6):
            if hp:
                hp.heal(100.0, player)
            tl = target.get_actor_location()
            pl = player.get_actor_location()
            d = unreal.Vector(tl.x - pl.x, tl.y - pl.y, 0).normal()
            origin = unreal.Transform(unreal.Vector(tl.x - d.x * 250, tl.y - d.y * 250, tl.z + 110), unreal.MathLibrary.make_rot_from_x(d), unreal.Vector(1, 1, 1))
            spells.release_spell_at(unreal.HeroSpell.FIRESTORM if shot % 2 else unreal.HeroSpell.FIRE, origin,
                                    unreal.Vector(tl.x, tl.y, tl.z + 100), target)
            await asyncio.sleep(0.45)
            h = target.get_component_by_class(unreal.ReflectionsHealthComponent)
            if h and h.get_editor_property('health') <= 0:
                break
    await asyncio.sleep(1.2)
    dead = []
    for s in sq:
        for m in members(s):
            if m.actor and ename(m.state).endswith('DEAD'):
                body = None
                for comp in m.actor.get_components_by_class(unreal.SkeletalMeshComponent):
                    if comp.get_name() == 'Body':
                        body = comp
                dead.append({'actor': m.actor.get_name(), 'ragdoll': bool(body and body.is_simulating_physics())})
    log('kills', dead=dead)
    if dead:
        d0 = [m.actor for m in members(sq[0]) if m.actor and ename(m.state).endswith('DEAD')][0]
        body = [c for c in d0.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == 'Body'][0]
        p = body.get_socket_location('pelvis')
        report['ragdoll'] = await capture(world, '4_ragdoll', unreal.Vector(p.x + 350, p.y + 250, p.z + 260), p, 60.0)
    # Stand down: the survivors fall back into formation and march on.
    cmd(world, 'Squads.Reform')
    await asyncio.sleep(7.0)
    log('reform', squads=[(ename(s.get_editor_property('state')), [ename(m.state) for m in members(s)]) for s in sq])
finally:
    try:
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')
        unreal.SystemLibrary.execute_console_command(None, 'Squads.StartPatrol 1')
    except Exception as e:
        report['stop_error'] = str(e)
    release_pie_lock()
    with open(os.path.join(OUT, 'report.json'), 'w') as f:
        json.dump(report, f, indent=1, default=str)
json.dumps(report, default=str)
