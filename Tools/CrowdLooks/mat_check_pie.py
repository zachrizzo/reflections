"""PIE: one Gilt and one Frost dressed soldier in the REAL game view (orchestrator 04:30: judge the flat-colour garments
in-game, not from a brightened offscreen capture). Spawns both 4.5 m ahead of the player on the traced floor, 1.2 m
apart, facing the player; waits; captures the game viewport plus one close offscreen shot each. Nothing is saved.
Never stops a PIE it didn't start. Globals: OUT."""
exec(open(PROJECT + 'Tools/CrowdLooks/pie_common.py', encoding='utf-8').read(), globals())
L = '/Game/Characters/Lanthorne/Looks/Soldiers/'
PAIR = [('GiltSoldier_BridgeGuard', L + 'GiltSoldier_BridgeGuard.GiltSoldier_BridgeGuard_C'),
        ('FrostSoldier_Amara', L + 'FrostSoldier_Amara.FrostSoldier_Amara_C'),
        ('GiltFerryman', '/Game/Characters/Lanthorne/Looks/BP_Look_GiltFerryman.BP_Look_GiltFerryman_C')]
os.makedirs(OUT, exist_ok=True)
report = {'errors': []}
STARTED_PIE = False
await acquire_pie_lock('crowd-looks: in-game look of the dressed soldiers (2 looks, ~20 s)', 120)
try:
    if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
        raise RuntimeError('PIE already running (not ours: leave it)')
    STARTED_PIE = True
    try:
        await call_tool('EditorToolset.EditorAppToolset.StartPIE', options={'warmupSeconds': 3.0})
    except Exception as e:
        report['errors'].append('start (waiting on): %s' % e)
    world = None
    for _ in range(240):
        world = game_world()
        if world:
            break
        await asyncio.sleep(0.25)
    if not world:
        raise RuntimeError('no PIE world')
    await asyncio.sleep(2.0)
    pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
    ploc, pfwd = pawn.get_actor_location(), pawn.get_actor_forward_vector()
    right = unreal.Vector(-pfwd.y, pfwd.x, 0)
    actors = []
    for i, (name, path) in enumerate(PAIR):
        off = (i - (len(PAIR) - 1) / 2.0) * 120
        sx, sy = ploc.x + pfwd.x * 450 + right.x * off, ploc.y + pfwd.y * 450 + right.y * off
        loc = unreal.Vector(sx, sy, floor_z(world, sx, sy, ploc.z - 90, [pawn]))
        yaw = math.degrees(math.atan2(-pfwd.y, -pfwd.x)) - 90.0
        a = unreal.ReflectionsWorldLibrary.spawn_actor_into_world(
            world, unreal.load_class(None, path), unreal.Transform(loc, unreal.Rotator(0, 0, yaw), unreal.Vector(1, 1, 1)))
        actors.append((name, a))  # not enrolled: they stand still for the shot
    await asyncio.sleep(3.0)
    report['viewport'] = await capture_game_viewport(os.path.join(OUT, 'soldiers_game_view.png'))
    for name, a in actors:
        pl, al = pawn.get_actor_location(), a.get_actor_location()
        try:
            report[name] = await shoot_look(world, a, os.path.join(OUT, 'soldier_' + name),
                                            forward=unreal.Vector(pl.x - al.x, pl.y - al.y, 0.0), face=False)
        except Exception as e:
            report['errors'].append('%s shot: %s' % (name, e))
        try:
            body =[c for c in a.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == 'Body'][0]
            f1, f2 = body.get_socket_location('foot_l'), body.get_socket_location('foot_r')
            mid = unreal.Vector((f1.x + f2.x) / 2, (f1.y + f2.y) / 2, (f1.z + f2.z) / 2)
            d = unreal.Vector(pl.x - al.x, pl.y - al.y, 0.0)
            n = max(1e-3, math.hypot(d.x, d.y))
            cam = unreal.Vector(mid.x + d.x / n * 120, mid.y + d.y / n * 120, mid.z + 40)
            report[name + '_feet'] = await capture(world, os.path.join(OUT, 'soldier_%s_feet.png' % name), cam, mid,
                                                   fov=45.0, w=560, h=420)
        except Exception as e:
            report['errors'].append('%s feet: %s' % (name, e))
        a.destroy_actor()
except Exception as e:
    report['errors'].append('run: %s' % e)
finally:
    try:
        if STARTED_PIE:
            await call_tool('EditorToolset.EditorAppToolset.StopPIE')
    except Exception as e:
        report['errors'].append('stop: %s' % e)
    release_pie_lock()
    with open(os.path.join(OUT, 'report.json'), 'w') as f:
        json.dump(report, f, indent=1)
