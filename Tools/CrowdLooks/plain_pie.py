"""PIE check of the re-dressed looks, ONE AT A TIME (orchestrator 01:24, after the 01:17 crash). Nothing is saved.
Top-level await. Per look, inside one PIE: spawn as an enrolled civilian 7 m in front of the player, wait STAND s,
measure moved distance (walker found its ABP), hand_r vs pelvis/upperarm (arms down, not T-pose), take shots,
then ragdoll (Body simulates; pelvis drop), shot, destroy. The report is written after EVERY look, so a crash keeps
what came before. FerryPilotGiltWorker body (01:17 crash) goes last. Globals: OUT, ONLY (optional ids),
ADOPT_OWN_PIE (only when the log proves the running PIE is ours).
Never stops a PIE it didn't start (23:02 lesson)."""
exec(open(PROJECT + 'Tools/CrowdLooks/pie_common.py', encoding='utf-8').read(), globals())
L = '/Game/Characters/Lanthorne/Looks/'
ORDER = ['Soldiers/FrostSoldier_Iven', 'BP_Look_GiltDrummer', 'BP_Look_GiltPriya', 'Soldiers/GiltSoldier_BridgeGuard',
         'Soldiers/FrostSoldier_Amara', 'Soldiers/GiltSoldier_Archivist', 'BP_Look_GiltFerryman', 'BP_Look_GiltRamon',
         'BP_Look_FrostIven', 'BP_Look_FrostSilas', 'BP_Look_FrostTobias', 'BP_Look_FrostWen',
         'BP_Look_GiltBridgeGuard', 'BP_Look_GiltRowena']
LOOKS = [(p.split('/')[-1], L + p + '.' + p.split('/')[-1] + '_C') for p in ORDER
         if not globals().get('ONLY') or p.split('/')[-1] in ONLY]
STAND = globals().get('STAND', 5.0)
os.makedirs(OUT, exist_ok=True)
report = {'looks': {}, 'errors': [], 'order': [n for n, _ in LOOKS]}
T0 = time.time()
REPORT = os.path.join(OUT, 'plain_report.json')


def dump():
    report['seconds'] = round(time.time() - T0, 1)
    with open(REPORT, 'w') as f:
        json.dump(report, f, indent=1)


def body_of(a):
    for c in a.get_components_by_class(unreal.SkeletalMeshComponent):
        if c.get_name() == 'Body':
            return c
    return None


def pose(b):
    hz, pz, sz = (b.get_socket_location(s).z for s in ('hand_r', 'pelvis', 'upperarm_r'))
    out = {'hand_above_pelvis_cm': round(hz - pz, 1), 'hand_below_shoulder_cm': round(sz - hz, 1),
           'mesh': b.get_editor_property('skeletal_mesh_asset').get_name()}
    # hero-cloak 03:2x: a folded foot (retarget) hides the boot sole. ball - foot should be ~13 cm FORWARD and
    # roughly level; up, back or ~0 means the walker's retarget collapses the foot/toe chain.
    try:
        fwd = b.get_owner().get_actor_right_vector()  # team looks face +Y
        for side in ('l', 'r'):
            f, k = b.get_socket_location('foot_' + side), b.get_socket_location('ball_' + side)
            d = unreal.Vector(k.x - f.x, k.y - f.y, k.z - f.z)
            out['ball_minus_foot_' + side] = {'len_cm': round(math.sqrt(d.x * d.x + d.y * d.y + d.z * d.z), 1),
                                              'fwd_cm': round(d.x * fwd.x + d.y * fwd.y, 1), 'up_cm': round(d.z, 1)}
    except Exception as e:
        out['foot_err'] = str(e)
    return out


STARTED_PIE = False
await acquire_pie_lock('crowd-looks: plain-clothes PIE check, one look at a time (%d looks)' % len(LOOKS), 240)
try:
    running = unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning'))
    if running and not globals().get('ADOPT_OWN_PIE'):
        raise RuntimeError('PIE already running (not ours: leave it)')
    STARTED_PIE = True
    if not running:
        try:
            await call_tool('EditorToolset.EditorAppToolset.StartPIE', options={'warmupSeconds': 3.0})
        except Exception as e:
            report['errors'].append('start (waiting on): %s' % e)  # 01:16: a 29 s first start timed out the call
    world = None
    for _ in range(240):
        world = game_world()
        if world:
            break
        await asyncio.sleep(0.25)
    if not world:
        raise RuntimeError('no PIE world')
    await asyncio.sleep(2.0)
    npcs = unreal.get_world_subsystem(world, unreal.ReflectionsNpcSubsystem)
    arch = npcs.find_archetype('Civilian') if npcs else None
    for i, (name, path) in enumerate(LOOKS):
        row = report['looks'].setdefault(name, {})
        report['current'] = name
        dump()
        pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
        ploc, pfwd = pawn.get_actor_location(), pawn.get_actor_forward_vector()
        cls = unreal.load_class(None, path)
        if not cls:
            row['err'] = 'no class'
            continue
        sx, sy = ploc.x + pfwd.x * 700, ploc.y + pfwd.y * 700
        loc = unreal.Vector(sx, sy, floor_z(world, sx, sy, ploc.z - 90, [pawn]))
        yaw = math.degrees(math.atan2(-pfwd.y, -pfwd.x)) - 90.0
        a = unreal.ReflectionsWorldLibrary.spawn_actor_into_world(
            world, cls, unreal.Transform(loc, unreal.Rotator(0, 0, yaw), unreal.Vector(1, 1, 1)))
        tags = list(a.tags)
        for t in ('NPC_Reactive', 'NPC_HitProxy', 'NPC_SampleLocomotion'):
            if unreal.Name(t) not in tags:
                tags.append(unreal.Name(t))
        a.tags = tags
        if npcs:
            npcs.enroll_actor(a, arch)
        if globals().get('FORCE_LOD') is not None:
            # Runtime only (nothing saved): test whether LOD 1 drops garment geometry (03:20 footless boot).
            for c in a.get_components_by_class(unreal.LODSyncComponent):
                c.set_editor_property('forced_lod', FORCE_LOD)
            row['forced_lod_runtime'] = FORCE_LOD
        start = a.get_actor_location()
        await asyncio.sleep(STAND)
        b = body_of(a)
        p = a.get_actor_location()
        row['moved_cm'] = round(math.dist((p.x, p.y), (start.x, start.y)), 1)
        row['pose'] = pose(b) if b else None
        row['parts'] = comp_dump(a)
        # 04:20: guards on the old looks didn't fall; record which parts collide (a hidden shield or armour could prop the body up).
        row['colliding_parts'] = []
        for c in a.get_components_by_class(unreal.PrimitiveComponent):
            try:
                ce = c.get_collision_enabled()
                if ce != unreal.CollisionEnabled.NO_COLLISION:
                    row['colliding_parts'].append([c.get_name(), str(ce), bool(c.is_visible()), c.get_collision_profile_name() if hasattr(c, 'get_collision_profile_name') else ''])
            except Exception:
                pass
        dump()
        # Camera on the player's side (the NPC spawned 7 m in front of the player): the actor's own facing can put
        # the camera inside a Gray London wall (03:01 blank shot).
        pl, al = pawn.get_actor_location(), a.get_actor_location()
        to_player = unreal.Vector(pl.x - al.x, pl.y - al.y, 0.0)
        try:
            row['shots'] = await shoot_look(world, a, os.path.join(OUT, 'one_%02d_%s' % (i, name)), forward=to_player,
                                            face=globals().get('FACE', True))
        except Exception as e:
            row['shot_err'] = str(e)
        try:
            fl, fr = b.get_socket_location('foot_l'), b.get_socket_location('foot_r')
            mid = unreal.Vector((fl.x + fr.x) / 2, (fl.y + fr.y) / 2, (fl.z + fr.z) / 2)
            n = max(1e-3, math.hypot(to_player.x, to_player.y))
            cam = unreal.Vector(mid.x + to_player.x / n * 150, mid.y + to_player.y / n * 150, mid.z + 45)
            row['feet_shot'] = await capture(world, os.path.join(OUT, 'one_%02d_%s_feet.png' % (i, name)), cam, mid,
                                             fov=45.0, w=560, h=420)
            row['feet_z_cm'] = [round(fl.z, 1), round(fr.z, 1)]
            # 03:30: a flat foot showed only the boot cuff. Is the street surface above the walker's sole?
            gz = []
            for fp in (fl, fr):
                try:
                    hit = unreal.SystemLibrary.line_trace_single(
                        world, unreal.Vector(fp.x, fp.y, fp.z + 80), unreal.Vector(fp.x, fp.y, fp.z - 80),
                        unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [a, pawn], unreal.DrawDebugTrace.NONE, True)
                    t = hit.to_tuple() if hit is not None and hasattr(hit, 'to_tuple') else None
                    gz.append(round(t[4].z, 1) if t and t[0] else None)
                    if t and t[0] and t[9] is not None:
                        row.setdefault('ground_actor', t[9].get_name() if hasattr(t[9], 'get_name') else str(t[9]))
                except Exception as e:
                    gz.append('err %s' % e)
            row['ground_z_under_feet_cm'] = gz
            try:
                row['actor_z_cm'] = round(a.get_actor_location().z, 1)
                row['ball_z_cm'] = [round(b.get_socket_location('ball_l').z, 1), round(b.get_socket_location('ball_r').z, 1)]
            except Exception:
                pass
        except Exception as e:
            row['feet_shot_err'] = str(e)
        row['pelvis_before_ragdoll'] = round(b.get_socket_location('pelvis').z, 1)
        b.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
        b.set_simulate_physics(True)
        await asyncio.sleep(2.0)
        row['ragdoll_drop_cm'] = round(row['pelvis_before_ragdoll'] - b.get_socket_location('pelvis').z, 1)
        row['simulating'] = b.is_simulating_physics('pelvis')
        try:
            row['ragdoll_shot'] = await shoot_look(world, a, os.path.join(OUT, 'one_%02d_%s_ragdoll' % (i, name)),
                                                   face=False)
        except Exception as e:
            row['ragdoll_shot_err'] = str(e)
        a.destroy_actor()
        row['done'] = True
        dump()
        await asyncio.sleep(0.5)
    report.pop('current', None)
except Exception as e:
    report['errors'].append('run: %s' % e)
finally:
    try:
        if STARTED_PIE:
            await call_tool('EditorToolset.EditorAppToolset.StopPIE')
    except Exception as e:
        report['errors'].append('stop: %s' % e)
    release_pie_lock()
    dump()
