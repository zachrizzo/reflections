"""PIE on the open map (MedievalLondon): close-ups of the grooms on NPCs that spawned BY THEMSELVES, one per NPC type
(ring crowd walker, Lives NPC, quest giver, soldier), for the before/after of groom_fix.py. Nothing is saved.
Per shot NPC: face close-up from the front, and each groom component's asset + forced LOD (what LODSync told it).
Writes report.json after every NPC. Stops shooting after BUDGET s (the MCP call times out near 60 s).
Never stops a PIE it didn't start. Globals: OUT, TAG (file prefix), WAIT (s after the world is up, default 7)."""
exec(open(PROJECT + 'Tools/CrowdLooks/pie_common.py', encoding='utf-8').read(), globals())
os.makedirs(OUT, exist_ok=True)
TAG = globals().get('TAG', 'shot')
BUDGET = globals().get('BUDGET', 44.0)
report = {'errors': [], 'npcs': [], 'counts': {}}
T0 = time.time()
PREFIX = ('BP_Look_', 'PewLook_', 'GiltSoldier_', 'FrostSoldier_')


def dump():
    report['seconds'] = round(time.time() - T0, 1)
    with open(os.path.join(OUT, TAG + '_report.json'), 'w') as f:
        json.dump(report, f, indent=1)


def kind_of(a):
    cls = a.get_class().get_name()
    tags = [str(t) for t in a.tags]
    owner = a.get_owner()
    oc = owner.get_class().get_name() if owner else ''
    low = ' '.join(tags).lower()
    if 'Squad' in oc or cls.startswith(('GiltSoldier_', 'FrostSoldier_')) or 'squad' in low:
        return 'soldier'
    if 'questspawned' in low:  # ReflectionsQuestWorldSubsystem.cpp:1660
        return 'quest_giver'
    if 'lives_person_' in low:  # ReflectionsLivesSubsystem.cpp:67
        return 'lives'
    if 'crowd_ring' in low or 'crowd_' in low:  # ReflectionsCrowdRingSubsystem.cpp:62
        return 'crowd'
    return 'other'


def groom_state(a):
    out = {}
    for c in a.get_components_by_class(unreal.GroomComponent):
        g = c.get_editor_property('groom_asset')
        if g is None:
            continue
        row = {'asset': g.get_name(), 'visible': bool(c.is_visible())}
        for fn in ('get_forced_lod', 'get_force_rendered_lod', 'get_force_streamed_lod'):
            if hasattr(c, fn):
                try:
                    row[fn] = getattr(c, fn)()
                except Exception:
                    pass
        try:  # is hair simulation on? (background NPCs should not simulate)
            phys = g.get_editor_property('hair_groups_physics')
            row['sim_enabled'] = [bool(x.get_editor_property('solver_settings').get_editor_property('enable_simulation'))
                                  for x in phys]
        except Exception as e:
            row['sim_err'] = str(e)[:80]
        out[c.get_name()] = row
    for c in a.get_components_by_class(unreal.LODSyncComponent):
        out['_lodsync'] = [c.get_editor_property('forced_lod'), c.get_editor_property('min_lod')]
    return out


STARTED_PIE = False
await acquire_pie_lock('crowd-looks: groom close-ups on MedievalLondon (%s, ~40 s)' % TAG, 150)
try:
    if unwrap(await call_tool('EditorToolset.EditorAppToolset.IsPIERunning')):
        raise RuntimeError('PIE already running (not ours: leave it)')
    STARTED_PIE = True
    try:
        await call_tool('EditorToolset.EditorAppToolset.StartPIE', options={'warmupSeconds': 2.0})
    except Exception as e:
        report['errors'].append('start (waiting on): %s' % e)
    world = None
    for _ in range(160):
        world = game_world()
        if world:
            break
        await asyncio.sleep(0.25)
    if not world:
        raise RuntimeError('no PIE world')
    report['map'] = world.get_name()
    await asyncio.sleep(globals().get('WAIT', 7.0))
    pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
    report['viewport'] = await capture_game_viewport(os.path.join(OUT, TAG + '_game_view.png'))
    ploc = pawn.get_actor_location()
    found = {}
    for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
        cls = a.get_class().get_name()
        if not cls.startswith(PREFIX):
            continue
        k = kind_of(a)
        d = a.get_actor_location().distance(ploc)
        found.setdefault(k, []).append((d, a))
        report['counts'][k] = report['counts'].get(k, 0) + 1
    report['sample_tags'] = {k: [str(t) for t in sorted(v, key=lambda x: x[0])[0][1].tags][:12] for k, v in found.items()}
    dump()
    order = [k for k in ('crowd', 'lives', 'quest_giver', 'soldier', 'other') if k in found]
    picks = [(k, sorted(found[k], key=lambda x: x[0])[0]) for k in order]
    seen_cls = set(p[1][1].get_class().get_name() for p in picks)
    for k in order:  # more faces of other looks while the time budget lasts
        for d, a in sorted(found[k], key=lambda x: x[0]):
            if a.get_class().get_name() not in seen_cls and len(picks) < globals().get('MAX_SHOTS', 6):
                seen_cls.add(a.get_class().get_name())
                picks.append((k + '_more', (d, a)))
    # a second crowd walker if there is time: different class from the first
    if 'crowd' in found and len(found['crowd']) > 1:
        first = picks[0][1][1].get_class().get_name()
        for d, a in sorted(found['crowd'], key=lambda x: x[0]):
            if a.get_class().get_name() != first:
                picks.append(('crowd2', (d, a)))
                break
    for k, (d, a) in picks:
        if time.time() - T0 > BUDGET:
            report['errors'].append('time budget: skipped %s' % k)
            continue
        row = {'kind': k, 'class': a.get_class().get_name(), 'dist_m': round(d / 100, 1), 'grooms': groom_state(a)}
        try:
            stem = os.path.join(OUT, '%s_%s_%s' % (TAG, k, a.get_class().get_name().replace('_C', '')))
            # Camera on the hero's side of the NPC (16:38: the actor's own facing put the camera in a wall = black),
            # head and shoulders from 1.1 m, plus the head bone height so the shot is aimed at the real head.
            al, pl = a.get_actor_location(), pawn.get_actor_location()
            dv = unreal.Vector(pl.x - al.x, pl.y - al.y, 0.0)
            n = max(1e-3, math.hypot(dv.x, dv.y))
            head = head_point(a)
            cam = unreal.Vector(head.x + dv.x / n * 110, head.y + dv.y / n * 110, head.z + 6)
            row['shots'] = {'face': await capture(world, stem + '_face.png', cam, unreal.Vector(head.x, head.y, head.z - 4),
                                                  fov=32.0, w=640, h=640)}
        except Exception as e:
            row['shot_err'] = str(e)[:200]
        report['npcs'].append(row)
        dump()
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
