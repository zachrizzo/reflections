"""PIE on the open (default) map: the real crowd on Play, at close range. Nothing is saved.
Starts PIE, lets the walkers spread for a few seconds, moves the player pawn ~4 m from the densest group of NPCs
facing them, and captures the game viewport (what the player sees) plus an eye-level offscreen shot.
Also writes which look each nearby NPC wears. Globals: OUT."""
os.makedirs(OUT, exist_ok=True)
rep = {'npcs': []}
T0 = time.time()
await acquire_pie_lock('crowd-looks: PIE screenshot of the crowd on Play (~30 s)', 120)
try:
    await call_tool('EditorToolset.EditorAppToolset.StartPIE', options={'warmupSeconds': 3.0})
    world = None
    for _ in range(60):
        world = game_world()
        if world:
            break
        await asyncio.sleep(0.25)
    await asyncio.sleep(5.0)
    await capture_game_viewport(os.path.join(OUT, 'play_view_start.png'))
    npcs = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
            if a.actor_has_tag('NPC_Reactive') and 'SampleCMC' not in a.get_class().get_name()]
    pts = [(a, a.get_actor_location()) for a in npcs]
    best, bestn = None, -1
    for a, p in pts:
        n = sum(1 for b, q in pts if (p.x - q.x) ** 2 + (p.y - q.y) ** 2 < 600 ** 2)
        if n > bestn:
            best, bestn = p, n
    near = [(a, p) for a, p in pts if (best.x - p.x) ** 2 + (best.y - p.y) ** 2 < 1600 ** 2]
    cx = sum(p.x for _, p in near) / len(near)
    cy = sum(p.y for _, p in near) / len(near)
    # Camera with the sun behind it, ~4.5 m from the group, at eye height (the player can't be teleported reliably).
    sun = next((a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.DirectionalLight)), None)
    sd = sun.get_actor_forward_vector() if sun else unreal.Vector(1, 0, -1)
    hx, hy = -sd.x, -sd.y
    hn = max(1e-3, math.sqrt(hx * hx + hy * hy))
    gz = near[0][1].z
    for k, (off, fov, tag) in enumerate([(700, 60, 'group'), (420, 45, 'group_tight')]):
        cam = unreal.Vector(cx + hx / hn * off, cy + hy / hn * off, gz + 160)
        await capture(world, os.path.join(OUT, 'play_%s.png' % tag), cam, unreal.Vector(cx, cy, gz + 120), fov=fov, w=1600, h=900)
    stand = unreal.Vector(cx + hx / hn * 450, cy + hy / hn * 450, gz)
    for i, (a, p) in enumerate(near):
        try:
            await shoot_look(world, a, os.path.join(OUT, 'walker_%02d_%s' % (i, a.get_class().get_name()[:-2])), forward=unreal.Vector(hx / hn, hy / hn, 0))
        except Exception as e:
            rep.setdefault('errs', []).append(str(e))
    for a, p in near:
        rep['npcs'].append({'class': a.get_class().get_name(), 'dist_m': round(math.sqrt((p.x - stand.x) ** 2 + (p.y - stand.y) ** 2) / 100, 1),
                            'tags': [str(t) for t in a.tags if str(t).startswith(('Look_', 'NPC_Voice'))]})
    rep['all_classes'] = sorted(a.get_class().get_name() for a in npcs)
finally:
    try:
        await call_tool('EditorToolset.EditorAppToolset.StopPIE')
    except Exception as e:
        rep['stop_err'] = str(e)
    release_pie_lock()
    rep['seconds'] = round(time.time() - T0, 1)
    with open(os.path.join(OUT, 'play_report.json'), 'w') as f:
        json.dump(rep, f, indent=1)
RESULT = json.dumps({'near': len(rep['npcs']), 'all': rep.get('all_classes'), 'seconds': rep['seconds']})
