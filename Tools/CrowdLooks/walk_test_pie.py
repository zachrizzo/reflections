"""PIE: spawn looks as real walking civilians (the unified NPC system's enrolment), let them stroll, then take
close-ups of each one in motion and a wide shot. Nothing is saved.
Globals: LOOKS (class paths), OUT (folder), ARCHETYPE (default 'Civilian'), STAND (seconds before shots)
"""
os.makedirs(OUT, exist_ok=True)
report = {'looks': [], 'errors': []}
T0 = time.time()
await acquire_pie_lock('crowd-looks: walk test of new NPC looks', 240)
STARTED_PIE = False  # 23:02: a lock-free PIE was the USER's own Play; never stop a PIE this script didn't start
try:
    if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
        raise RuntimeError('PIE already running')
    await call_tool('EditorToolset.EditorAppToolset.StartPIE', options={'warmupSeconds': 3.0})
    STARTED_PIE = True
    world = None
    for _ in range(60):
        world = game_world()
        if world:
            break
        await asyncio.sleep(0.25)
    await asyncio.sleep(2.0)
    if globals().get('NO_MASS', True):
        cmd(world, 'Crowd.Mass.Enable 0')
    npcs = unreal.get_world_subsystem(world, unreal.ReflectionsNpcSubsystem) if hasattr(unreal, 'get_world_subsystem') else None
    arch = npcs.find_archetype(globals().get('ARCHETYPE', 'Civilian')) if npcs else None
    pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
    ploc, pfwd = pawn.get_actor_location(), pawn.get_actor_forward_vector()
    right = unreal.Vector(-pfwd.y, pfwd.x, 0)
    spawned = []
    for i, path in enumerate(LOOKS):
        cls = unreal.load_class(None, path)
        if not cls:
            report['errors'].append('no class ' + path)
            continue
        off = (i - (len(LOOKS) - 1) / 2.0) * 220
        sx, sy = ploc.x + pfwd.x * 700 + right.x * off, ploc.y + pfwd.y * 700 + right.y * off
        loc = unreal.Vector(sx, sy, floor_z(world, sx, sy, ploc.z - 90, [pawn]))
        yaw = math.degrees(math.atan2(-pfwd.y, -pfwd.x)) - 90.0
        a = unreal.ReflectionsWorldLibrary.spawn_actor_into_world(world, cls, unreal.Transform(loc, unreal.Rotator(0, 0, yaw), unreal.Vector(1, 1, 1)))
        tags = list(a.tags)
        for t in ('NPC_Reactive', 'NPC_HitProxy', 'NPC_SampleLocomotion'):
            if unreal.Name(t) not in tags:
                tags.append(unreal.Name(t))
        a.tags = tags
        if npcs:
            npcs.enroll_actor(a, arch)
        spawned.append((path, a))
        await asyncio.sleep(0)
    await asyncio.sleep(globals().get('STAND', 6.0))
    await capture_game_viewport(os.path.join(OUT, 'viewport_walk.png'))
    for i, (path, a) in enumerate(spawned):
        name = path.split('.')[-1][:-2] if path.endswith('_C') else path.split('.')[-1]
        row = {'class': path, 'parts': comp_dump(a), 'tags': [str(t) for t in a.tags]}
        try:
            row['shots'] = await shoot_look(world, a, os.path.join(OUT, 'walk_%02d_%s' % (i, name)))
        except Exception as e:
            row['err'] = str(e)
        report['looks'].append(row)
finally:
    try:
        if STARTED_PIE:
            await call_tool('EditorToolset.EditorAppToolset.StopPIE')
    except Exception as e:
        report['errors'].append('stop: %s' % e)
    release_pie_lock()
    report['seconds'] = round(time.time() - T0, 1)
    with open(os.path.join(OUT, 'report.json'), 'w') as f:
        json.dump(report, f, indent=1)
RESULT = json.dumps({'n': len(report['looks']), 'errors': report['errors'], 'seconds': report['seconds']})
