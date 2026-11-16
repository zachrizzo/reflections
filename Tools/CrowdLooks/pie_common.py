# Shared helpers for the crowd-looks PIE scripts. Exec'd into the script namespace by run_file().
import asyncio
import base64
import json
import math
import os
import time

PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
LOCK_PATH = os.path.join(unreal.Paths.project_saved_dir(), 'PIE_LOCK.json')
LOCK_OWNER = 'crowd-looks (NPC appearance side session)'


async def acquire_pie_lock(purpose, seconds=240, wait_limit=900):
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
        await asyncio.sleep(10.0)
    now = time.time()
    exp = now + min(seconds, 240)
    with open(LOCK_PATH, 'w') as f:
        json.dump({'owner': LOCK_OWNER, 'purpose': purpose, 'acquired_epoch': int(now),
                   'expires_epoch': int(exp), 'expires_local': time.strftime('%H:%M:%S', time.localtime(exp))}, f)


def release_pie_lock():
    try:
        with open(LOCK_PATH) as f:
            held = json.load(f)
        if held.get('owner') == LOCK_OWNER:
            os.remove(LOCK_PATH)
    except Exception:
        pass


def unwrap(r):
    return r.get('returnValue', r) if isinstance(r, dict) and 'returnValue' in r else r


def game_world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


def cmd(world, text):
    unreal.SystemLibrary.execute_console_command(world, text)


def _save_image(res, path):
    res = unwrap(res)
    img = res.get('image') if isinstance(res, dict) else None
    if img and not isinstance(img, (str, bytes, bytearray)):
        img = next((img[k] for k in img if isinstance(img[k], (str, bytes, bytearray)) and len(img[k]) > 1000), None)
    if not img:
        return None
    data = img if isinstance(img, (bytes, bytearray)) else base64.b64decode(img.split(',')[-1])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(data)
    return path


async def capture(world, path, cam_loc, look_at, fov=40.0, w=640, h=640):
    d = unreal.Vector(look_at.x - cam_loc.x, look_at.y - cam_loc.y, look_at.z - cam_loc.z)
    rot = unreal.MathLibrary.make_rot_from_x(d)
    res = await call_tool('SceneCaptureToolset.SceneCaptureToolset.Capture',
                          world={'refPath': world.get_path_name()},
                          camera={'location': {'x': cam_loc.x, 'y': cam_loc.y, 'z': cam_loc.z},
                                  'rotation': {'pitch': rot.pitch, 'yaw': rot.yaw, 'roll': 0.0},
                                  'projectionMode': 'Perspective', 'fOV': fov},
                          mode=globals().get('CAPTURE_MODE', 'Lit'), options={'width': w, 'height': h, 'screenPercentage': 1.0})
    return _save_image(res, path)


async def capture_game_viewport(path):
    res = await call_tool('SceneCaptureToolset.SceneCaptureToolset.CaptureGameViewport', world={'refPath': game_world().get_path_name()}, maxResolution=1600)
    return _save_image(res, path)


def comp_dump(actor):
    """Every visible part of a look: skeletal meshes, grooms, their assets and materials."""
    rows = []
    for c in actor.get_components_by_class(unreal.SceneComponent):
        row = {'name': c.get_name(), 'class': c.get_class().get_name()}
        try:
            row['visible'] = bool(c.is_visible()) and not bool(c.get_editor_property('hidden_in_game'))
        except Exception:
            pass
        if isinstance(c, unreal.SkinnedMeshComponent):
            m = c.get_skinned_asset() if hasattr(c, 'get_skinned_asset') else None
            if m is None and isinstance(c, unreal.SkeletalMeshComponent):
                m = c.get_skeletal_mesh_asset()
            row['mesh'] = m.get_path_name() if m else None
            try:
                row['mats'] = [(mi.get_path_name() if mi else None) for mi in c.get_materials()]
            except Exception:
                pass
        elif c.get_class().get_name() == 'GroomComponent':
            try:
                ga = c.get_editor_property('groom_asset')
                gb = c.get_editor_property('binding_asset')
                row['groom'] = ga.get_path_name() if ga else None
                row['binding'] = gb.get_path_name() if gb else None
            except Exception as e:
                row['err'] = str(e)
        else:
            continue
        rows.append(row)
    return rows


def face_comp(actor):
    best = None
    for c in actor.get_components_by_class(unreal.SkeletalMeshComponent):
        n = c.get_name().lower()
        if n == 'face' or 'face' in n:
            return c
        if n == 'body':
            best = c
    return best


def head_point(actor):
    """World location of the head, and the direction the look faces (+Y of the actor for team looks)."""
    fc = face_comp(actor)
    loc = None
    for sock in ('FACIAL_C_FacialRoot', 'head', 'Head'):
        try:
            if fc and fc.does_socket_exist(sock):
                loc = fc.get_socket_location(sock)
                break
        except Exception:
            pass
    if loc is None:
        o, e = actor.get_actor_bounds(True)
        loc = unreal.Vector(o.x, o.y, o.z + e.z * 0.82)
    return loc


async def shoot_look(world, actor, stem, forward=None, face=True, body=True):
    """Face close-up and full body, three-quarter from the front."""
    if forward is None:
        forward = actor.get_actor_right_vector()
    fwd = unreal.Vector(forward.x, forward.y, 0.0)
    n = max(1e-3, math.sqrt(fwd.x * fwd.x + fwd.y * fwd.y))
    fwd = unreal.Vector(fwd.x / n, fwd.y / n, 0.0)
    side = unreal.Vector(-fwd.y, fwd.x, 0.0)
    head = head_point(actor)
    out = {}
    if face:
        cam = unreal.Vector(head.x + fwd.x * 62 + side.x * 22, head.y + fwd.y * 62 + side.y * 22, head.z + 3)
        out['face'] = await capture(world, stem + '_face.png', cam, unreal.Vector(head.x, head.y, head.z - 2), fov=30.0, w=560, h=560)
    if body:
        o, e = actor.get_actor_bounds(True)
        mid = unreal.Vector(head.x, head.y, head.z - 78)
        cam = unreal.Vector(head.x + fwd.x * 300 + side.x * 90, head.y + fwd.y * 300 + side.y * 90, head.z - 55)
        out['body'] = await capture(world, stem + '_body.png', cam, mid, fov=40.0, w=480, h=720)
    return out


def floor_z(world, x, y, guess_z, ignore=()):
    """Top floor under (x, y): trace from guess_z + 50 down to guess_z - 150 and take the first hit (crowd-react,
    04:0x: spawning at player z - 90 put NPCs under Gray London's 28 cm road sheet, and they stood on the city ground
    below, so planted boots looked buried). Falls back to guess_z."""
    try:
        hit = unreal.SystemLibrary.line_trace_single(
            world, unreal.Vector(x, y, guess_z + 50), unreal.Vector(x, y, guess_z - 150),
            unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, list(ignore), unreal.DrawDebugTrace.NONE, True)
        t = hit.to_tuple() if hit is not None and hasattr(hit, 'to_tuple') else None
        if t and t[0]:
            return t[4].z
    except Exception:
        pass
    return guess_z
