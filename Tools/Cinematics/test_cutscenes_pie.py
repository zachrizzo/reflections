"""PIE proof and contact-sheet frames for the cutscenes. Runs inside the editor via the MCP Python tool (top-level await).
ARGS: run <Name> [skip] [map]
  One PIE session under the shared PIE lock (Saved/PIE_LOCK.json, <= 240 s): plays the cutscene with Cutscene.Play,
  captures the game viewport (UI included: bars, subtitles, cards) at 8 evenly spaced times, then checks that control
  came back: not playing, move/look input not ignored, view target = the hero, hero damageable. With 'skip' it skips
  at 40% through Cutscene.Skip and checks the same. Writes Saved/CinematicsTest/<Name>[_skip]/report.json + frames.
Contact sheets: python Tools/Cinematics/make_contact_sheet.py <Name> (outside the editor).
"""
import asyncio
import base64
import json
import time
from pathlib import Path

import unreal

ME = 'cutscenes-session'
PROJECT = Path(unreal.Paths.project_dir()).resolve()
ROOT = PROJECT / 'Saved' / 'CinematicsTest'
SHEETS = PROJECT / 'ArtDirection' / 'Cinematics'
LOCK = PROJECT / 'Saved' / 'PIE_LOCK.json'
APP = 'EditorToolset.EditorAppToolset.'
LENGTHS = {'Intro': 48.0, 'BurningEyes': 36.0, 'FirstPage': 28.5, 'GiltTower': 35.5, 'MirrorWhole': 29.5, 'Ending': 46.0}


def lock_holder():
    try:
        data = json.loads(LOCK.read_text())
    except Exception:
        return None
    if data.get('owner') != ME and float(data.get('expires_epoch', 0)) > time.time():
        return data.get('owner'), data.get('expires_local')
    return None


def write_lock(purpose, seconds=240):
    now = time.time()
    LOCK.write_text(json.dumps({'owner': ME, 'purpose': purpose, 'acquired_epoch': int(now), 'expires_epoch': int(now + seconds),
                                'expires_local': time.strftime('%H:%M:%S', time.localtime(now + seconds))}, indent=2))


def release_lock():
    try:
        if json.loads(LOCK.read_text()).get('owner') == ME:
            LOCK.unlink()
    except Exception:
        pass


def game_world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


def cutscenes(world):
    return unreal.get_world_subsystem(world, unreal.ReflectionsCutsceneSubsystem)


async def capture(path):
    r = await call_tool('SceneCaptureToolset.SceneCaptureToolset.CaptureGameViewport', world=None, maxResolution=1600)
    data = r['image']
    if data is not None and not isinstance(data, str):
        data = data['data']
    if not data or str(data).startswith('urn:'):
        return None
    path.write_bytes(base64.b64decode(data))
    return str(path)


def control_state(world):
    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    pawn = pc.get_controlled_pawn() if pc else None
    view = pc.get_view_target() if pc else None
    return {
        'playing': cutscenes(world).is_cutscene_playing(),
        'move_ignored': pc.is_move_input_ignored() if pc else None,
        'look_ignored': pc.is_look_input_ignored() if pc else None,
        'view_target_is_hero': bool(view and pawn and view == pawn),
        'view_target': view.get_name() if view else None,
        'hero_can_be_damaged': pawn.get_editor_property('can_be_damaged') if pawn else None,
        'hero': pawn.get_actor_location().to_tuple() if pawn else None,
    }


async def run(name, skip, map_path):
    out = ROOT / (name + ('_skip' if skip else ''))
    out.mkdir(parents=True, exist_ok=True)
    report = {'cutscene': name, 'skip': skip, 'started': time.strftime('%H:%M:%S')}
    waited = 0.0
    while True:
        holder = lock_holder()
        if holder is None and not await call_tool(APP + 'IsPIERunning'):
            write_lock('cutscene %s PIE proof (one run)' % name)
            await call_tool(APP + 'StartPIE')
            break
        await asyncio.sleep(5.0)
        waited += 5.0
        if waited > 90.0:
            return {'error': 'PIE busy or locked: %s' % (holder,)}
    try:
        world = None
        for _ in range(120):
            await asyncio.sleep(0.5)
            world = game_world()
            if world:
                pc = unreal.GameplayStatics.get_player_controller(world, 0)
                if pc and pc.get_controlled_pawn():
                    break
        if map_path and map_path not in world.get_path_name():
            unreal.SystemLibrary.execute_console_command(world, 'open ' + map_path)
            await asyncio.sleep(8.0)
            world = game_world()
        await asyncio.sleep(4.0)  # hero settles, crowd spawns, game flow begins play
        report['map'] = world.get_path_name()
        report['before'] = control_state(world)
        unreal.SystemLibrary.execute_console_command(world, 'Cutscene.Play ' + name)
        await asyncio.sleep(0.2)
        sub = cutscenes(world)
        report['started_ok'] = sub.is_cutscene_playing()
        report['anchor'] = sub.get_anchor_transform().translation.to_tuple()
        length = LENGTHS.get(name, 30.0)
        frames = []
        if skip:
            await asyncio.sleep(length * 0.4)
            frames.append(await capture(out / 'before_skip.png'))
            report['during'] = control_state(world)
            unreal.SystemLibrary.execute_console_command(world, 'Cutscene.Skip')
            await asyncio.sleep(1.6)
        else:
            times = [length * (i + 0.5) / 8.0 for i in range(8)]
            t0 = time.monotonic()
            for i, t in enumerate(times):
                # Sample on the cutscene's own clock (it can hold for a conversion).
                for _ in range(400):
                    if not sub.is_cutscene_playing() or sub.get_cutscene_time() >= t:
                        break
                    await asyncio.sleep(0.1)
                    write_lock('cutscene %s PIE proof (one run)' % name) if time.monotonic() - t0 > 150 else None
                if not sub.is_cutscene_playing():
                    break
                frames.append(await capture(out / ('frame_%d.png' % i)))
                if i == 3:
                    report['during'] = control_state(world)
            for _ in range(300):
                if not sub.is_cutscene_playing():
                    break
                await asyncio.sleep(0.2)
            await asyncio.sleep(2.0)  # hand-off blend
            frames.append(await capture(out / 'after.png'))
        report['after'] = control_state(world)
        report['played'] = sub.has_played(name)
        report['frames'] = [f for f in frames if f]
        report['pass'] = bool(report['started_ok'] and report['played'] and not report['after']['playing']
                              and not report['after']['move_ignored'] and not report['after']['look_ignored']
                              and report['after']['view_target_is_hero'] and report['after']['hero_can_be_damaged'])
    finally:
        if await call_tool(APP + 'IsPIERunning'):
            await call_tool(APP + 'StopPIE')
        release_lock()
    (out / 'report.json').write_text(json.dumps(report, indent=2, default=str))
    return report


async def preview(names):
    """Camera framing check without the cutscene subsystem: in one PIE session, puts a cine camera at each shot's
    first and last key (anchor = the hero's feet and facing) and captures the view -> Saved/CinematicsTest/Preview."""
    import importlib
    import sys
    tools = str(PROJECT / 'Tools' / 'Cinematics')
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import cutscene_defs
    importlib.reload(cutscene_defs)
    out = ROOT / 'Preview'
    out.mkdir(parents=True, exist_ok=True)
    waited = 0.0
    while True:
        holder = lock_holder()
        if holder is None and not await call_tool(APP + 'IsPIERunning'):
            write_lock('cutscene camera preview (one run, no gameplay)')
            await call_tool(APP + 'StartPIE')
            break
        await asyncio.sleep(5.0)
        waited += 5.0
        if waited > 90.0:
            return {'error': 'PIE busy or locked: %s' % (holder,)}
    shots = []
    try:
        world = None
        for _ in range(120):
            await asyncio.sleep(0.5)
            world = game_world()
            pc = unreal.GameplayStatics.get_player_controller(world, 0) if world else None
            if pc and pc.get_controlled_pawn():
                break
        await asyncio.sleep(4.0)
        pawn = pc.get_controlled_pawn()
        capsule = pawn.get_component_by_class(unreal.CapsuleComponent)
        feet = pawn.get_actor_location() - unreal.Vector(0, 0, capsule.get_scaled_capsule_half_height() if capsule else 90.0)
        anchor = unreal.Transform(feet, unreal.Rotator(0.0, 0.0, pawn.get_actor_rotation().yaw), unreal.Vector(1, 1, 1))
        cam = unreal.GameplayStatics.begin_deferred_actor_spawn_from_class(world, unreal.CineCameraActor, anchor)
        cam = unreal.GameplayStatics.finish_spawning_actor(cam, anchor)
        comp = cam.get_cine_camera_component()
        comp.set_editor_property('constrain_aspect_ratio', False)
        pc.set_view_target_with_blend(cam, 0.0)
        for name in names:
            for index, shot in enumerate(cutscene_defs.CUTSCENES[name]['shots']):
                for which, key in (('a', shot['keys'][0]), ('b', shot['keys'][-1])):
                    pos = anchor.transform_location(unreal.Vector(*key['pos']))
                    if 'look' in key:
                        rot = unreal.MathLibrary.find_look_at_rotation(pos, anchor.transform_location(unreal.Vector(*key['look'])))
                    else:
                        r = key['rot']
                        rot = unreal.Rotator(r[0], r[1], r[2] + anchor.rotation.rotator().yaw)
                    cam.set_actor_location_and_rotation(pos, rot, False, True)
                    comp.set_editor_property('current_focal_length', float(shot['focal']))
                    await asyncio.sleep(0.5)
                    shots.append(await capture(out / ('%s_%02d%s.png' % (name, index + 1, which))))
            write_lock('cutscene camera preview (one run, no gameplay)')
        cam.destroy_actor()
    finally:
        if await call_tool(APP + 'IsPIERunning'):
            await call_tool(APP + 'StopPIE')
        release_lock()
    return {'anchor': str(anchor), 'shots': [s for s in shots if s]}


def anchor_for(world, name):
    """Same rules as the subsystem: CutsceneAnchor_<Name> marker (yaw only, snapped to the ground), else None."""
    markers = unreal.get_world_subsystem(world, unreal.ReflectionsStoryMarkerSubsystem)
    marker = markers.find('CutsceneAnchor_' + name, False) if markers else None
    if not marker:
        return None, None
    loc = marker.get_actor_location()
    hit = unreal.SystemLibrary.line_trace_single(world, loc + unreal.Vector(0, 0, 150), loc - unreal.Vector(0, 0, 800),
                                                 unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [marker],
                                                 unreal.DrawDebugTrace.NONE, True)
    if hit:
        loc = hit.to_tuple()[5]
    return unreal.Transform(loc, unreal.Rotator(0.0, 0.0, marker.get_actor_rotation().yaw), unreal.Vector(1, 1, 1)), marker.get_name()


def clear_point(world, cam, target, ignore):
    """Camera inside geometry or its subject hidden: walk from the camera toward the subject until both are fine."""
    def inside(p):
        hits = unreal.SystemLibrary.sphere_overlap_actors(world, p, 25.0, [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1], None, ignore)
        return bool(hits)

    def blocked(p):
        hit = unreal.SystemLibrary.line_trace_single(world, p, target, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, ignore,
                                                     unreal.DrawDebugTrace.NONE, True)
        return hit is not None and bool(hit.to_tuple()[0]) if hasattr(hit, 'to_tuple') else bool(hit)

    if not inside(cam) and not blocked(cam):
        return None
    for i in range(1, 20):
        p = cam + (target - cam) * (i / 20.0)
        if (target - p).length() < 60.0:
            break
        if not inside(p) and not blocked(p):
            return p
    return 'unfixable'


async def geometry(map_path):
    """In one PIE session on map_path: every camera key of every cutscene, placed at that map's anchor, checked for
    being inside a building or losing sight of its subject. Writes Saved/CinematicsTest/geometry.json with suggested
    anchor-space fixes (camera pulled toward its subject until clear)."""
    import importlib
    import sys
    tools = str(PROJECT / 'Tools' / 'Cinematics')
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import cutscene_defs
    importlib.reload(cutscene_defs)
    report = {}
    waited = 0.0
    while True:
        holder = lock_holder()
        if holder is None and not await call_tool(APP + 'IsPIERunning'):
            write_lock('cutscene camera vs geometry check (one run, no gameplay)')
            await call_tool(APP + 'StartPIE')
            break
        await asyncio.sleep(5.0)
        waited += 5.0
        if waited > 90.0:
            return {'error': 'PIE busy or locked: %s' % (holder,)}
    try:
        world = None
        for _ in range(120):
            await asyncio.sleep(0.5)
            world = game_world()
            pc = unreal.GameplayStatics.get_player_controller(world, 0) if world else None
            if pc and pc.get_controlled_pawn():
                break
        if map_path and map_path not in world.get_path_name():
            unreal.SystemLibrary.execute_console_command(world, 'open ' + map_path)
            for _ in range(120):
                await asyncio.sleep(0.5)
                world = game_world()
                pc = unreal.GameplayStatics.get_player_controller(world, 0) if world else None
                if world and map_path in world.get_path_name() and pc and pc.get_controlled_pawn():
                    break
        await asyncio.sleep(3.0)
        pawn = pc.get_controlled_pawn()
        report['map'] = world.get_path_name()
        for name, defn in cutscene_defs.CUTSCENES.items():
            anchor, marker = anchor_for(world, name)
            if anchor is None:
                capsule = pawn.get_component_by_class(unreal.CapsuleComponent)
                feet = pawn.get_actor_location() - unreal.Vector(0, 0, capsule.get_scaled_capsule_half_height() if capsule else 90.0)
                anchor = unreal.Transform(feet, unreal.Rotator(0.0, 0.0, pawn.get_actor_rotation().yaw), unreal.Vector(1, 1, 1))
            entry = {'marker': marker, 'anchor': [round(v) for v in anchor.translation.to_tuple()], 'keys': []}
            for si, shot in enumerate(defn['shots']):
                for ki, key in enumerate(shot['keys']):
                    cam = anchor.transform_location(unreal.Vector(*key['pos']))
                    look = key.get('look') or (0.0, 0.0, 150.0)
                    target = anchor.transform_location(unreal.Vector(*look))
                    fix = clear_point(world, cam, target, [pawn])
                    if fix is None:
                        continue
                    row = {'shot': si, 'label': shot['label'], 'key': ki, 'pos': key['pos']}
                    if fix == 'unfixable':
                        row['fix'] = 'unfixable'
                    else:
                        local = anchor.inverse_transform_location(fix)
                        row['fix'] = [round(local.x), round(local.y), round(local.z)]
                    entry['keys'].append(row)
                await asyncio.sleep(0)
            report[name] = entry
            write_lock('cutscene camera vs geometry check (one run, no gameplay)')
    finally:
        if await call_tool(APP + 'IsPIERunning'):
            await call_tool(APP + 'StopPIE')
        release_lock()
    (ROOT / 'geometry.json').write_text(json.dumps(report, indent=2, default=str))
    return report


_args = list(globals().get('ARGS', []) or [])
if _args and _args[0] == 'geometry':
    RESULT = json.dumps(await geometry(_args[1] if len(_args) > 1 else '/Game/MockCity/Lvl_MockCity'), default=str)
if _args and _args[0] == 'preview':
    RESULT = json.dumps(await preview(_args[1:] or list(LENGTHS)), default=str)
if _args and _args[0] == 'run':
    RESULT = json.dumps(await run(_args[1], 'skip' in _args[2:], next((a for a in _args[2:] if a.startswith('/Game')), None)), default=str)
