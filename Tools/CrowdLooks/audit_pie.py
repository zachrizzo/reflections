"""Crowd-looks audit, one PIE run on the open map (Lvl_HeroSampleCrowd). Nothing is saved.

1. What spawns by itself: every NPC actor (placed walkers, squads, promoted pedestrians) and the Mass city crowd.
   Each gets a face close-up and a body shot, and its components are dumped.
2. A lineup of the looks in a list (LOOKS env/global), spawned in the PIE world in front of the player.
Writes <OUT>/*.png and <OUT>/report.json.  Globals expected: OUT (folder), LOOKS (list of class paths), TAG.
"""
exec(open(os.path.join(PROJECT, 'Tools/CrowdLooks/pie_common.py'), encoding='utf-8').read()) if 'acquire_pie_lock' not in globals() else None

os.makedirs(OUT, exist_ok=True)
report = {'tag': TAG, 'natural': [], 'lineup': [], 'errors': []}
T0 = time.time()

await acquire_pie_lock('crowd-looks audit: capture every NPC look (%s)' % TAG, 240)
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
    await asyncio.sleep(4.0)   # crowd level streams in, NPCs enrol
    cmd(world, 'Crowd.Stroll.Enable 0')
    pc = unreal.GameplayStatics.get_player_pawn(world, 0)
    ploc = pc.get_actor_location() if pc else unreal.Vector(0, 0, 100)
    pfwd = pc.get_actor_forward_vector() if pc else unreal.Vector(1, 0, 0)
    await capture_game_viewport(os.path.join(OUT, 'pie_viewport_start.png'))

    if DO_NATURAL:
        # --- what the map spawns ---
        seen = []
        for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
            cn = a.get_class().get_name()
            if not (a.actor_has_tag('NPC_Reactive') or a.actor_has_tag('NPC_SampleLocomotion') or a.actor_has_tag('Crowd_Promoted')):
                continue
            if 'SampleCMC' in cn:
                continue
            seen.append(a)
        for i, a in enumerate(seen):
            stem = os.path.join(OUT, 'natural_%02d_%s' % (i, a.get_class().get_name()[:-2]))
            row = {'i': i, 'class': a.get_class().get_path_name(), 'label': a.get_name(),
                   'loc': [round(v) for v in (a.get_actor_location().x, a.get_actor_location().y, a.get_actor_location().z)],
                   'tags': [str(t) for t in a.tags], 'parts': comp_dump(a)}
            try:
                row['shots'] = await shoot_look(world, a, stem)
            except Exception as e:
                row['err'] = str(e)
            report['natural'].append(row)
            await asyncio.sleep(0)
        # Mass crowd: entity stats and a few views along the lanes.
        try:
            lib = getattr(unreal, 'MetaHumanCrowdStatsLibrary', None)
            if lib:
                report['mass_stats'] = {m: str(getattr(lib, m)(world)) for m in dir(lib) if m.startswith('get_') and m.count('_') < 6}
        except Exception as e:
            report['mass_stats_err'] = str(e)
        iskm = []
        for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
            for c in a.get_components_by_class(unreal.InstancedSkinnedMeshComponent):
                try:
                    o, e, r = unreal.SystemLibrary.get_component_bounds(c)
                    m = c.get_skinned_asset()
                    iskm.append({'actor': a.get_name(), 'comp': c.get_name(), 'mesh': m.get_path_name() if m else None,
                                 'origin': [round(o.x), round(o.y), round(o.z)], 'extent': [round(e.x), round(e.y), round(e.z)]})
                except Exception as ex:
                    iskm.append({'actor': a.get_name(), 'err': str(ex)})
        report['mass_iskm'] = iskm
        lanes = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor) if 'ZoneGraphShape' in a.get_class().get_name()]
        report['lane_actors'] = len(lanes)
        for i, a in enumerate(lanes[:4]):
            l = a.get_actor_location()
            cam = unreal.Vector(l.x - 350, l.y - 350, l.z + 170)
            await capture(world, os.path.join(OUT, 'mass_view_%d.png' % i), cam, unreal.Vector(l.x, l.y, l.z + 120), fov=60, w=1280, h=720)

    # --- lineup of every look in the list ---
    right = unreal.Vector(-pfwd.y, pfwd.x, 0)
    bx, by = ploc.x + pfwd.x * 600, ploc.y + pfwd.y * 600
    base = unreal.Vector(bx, by, floor_z(world, bx, by, ploc.z - 90, [pc]))
    for i, path in enumerate(LOOKS):
        if time.time() - T0 > 200:
            report['errors'].append('time budget hit at %d' % i)
            break
        row = {'i': i, 'class': path}
        try:
            cls = unreal.load_class(None, path)
            if not cls:
                row['err'] = 'class did not load'
                report['lineup'].append(row)
                continue
            # Facing the player: the looks face their own +Y, so yaw - 90.
            yaw = math.degrees(math.atan2(-pfwd.y, -pfwd.x)) - 90.0
            loc = unreal.Vector(base.x + right.x * (i % 6) * 260 - right.x * 650, base.y + right.y * (i % 6) * 260 - right.y * 650, base.z)
            a = unreal.ReflectionsWorldLibrary.spawn_actor_into_world(world, cls, unreal.Transform(loc, unreal.Rotator(0, 0, yaw), unreal.Vector(1, 1, 1)))
            await asyncio.sleep(0.6)
            a.set_actor_location_and_rotation(loc, unreal.Rotator(0, 0, yaw), False, True)
            row['parts'] = comp_dump(a)
            name = path.split('.')[-1][:-2] if path.endswith('_C') else path.split('.')[-1]
            row['shots'] = await shoot_look(world, a, os.path.join(OUT, 'look_%02d_%s' % (i, name)),
                                            forward=unreal.Vector(-pfwd.x, -pfwd.y, 0))
            a.destroy_actor()
        except Exception as e:
            row['err'] = str(e)
        report['lineup'].append(row)
        await asyncio.sleep(0)
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

RESULT = json.dumps({'natural': len(report['natural']), 'lineup': len(report['lineup']), 'errors': report['errors'],
                     'seconds': report['seconds'], 'mass': report.get('mass_stats'), 'iskm': len(report.get('mass_iskm', []))})
