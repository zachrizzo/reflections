"""Turn a story marker towards open space on Gray London and save ONLY its package. ARGS: [marker name].
Horizontal traces at 1.6 m every 15 degrees out to 40 m; picks the most open direction, preferring the one closest to
the Bell Square marker (the open churchyard square) among directions clear for at least 15 m."""
import json
import math
import unreal

NAME = ARGS[0] if ARGS else 'CutsceneAnchor_BurningEyes'
res = {'marker': NAME}
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def free_dist(origin, yaw_deg, max_cm=4000.0):
    d = unreal.Vector(math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg)), 0.0)
    end = origin + d * max_cm
    h = unreal.SystemLibrary.line_trace_single(w, origin, end, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [],
                                               unreal.DrawDebugTrace.NONE, True)
    hs = [v for v in (h if isinstance(h, tuple) else (h,)) if isinstance(v, unreal.HitResult)]
    t = hs[0].to_tuple() if hs else None
    return (t[3] if t and t[0] else max_cm)   # distance


if unreal.EditorLevelLibrary.get_game_world() is not None:
    res['abort'] = 'PIE running'
else:
    markers = {str(a.get_editor_property('marker_name')): a for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.ReflectionsStoryMarker)}
    a = markers.get(NAME)
    if a is None:
        res['abort'] = 'marker not found'
    else:
        loc = a.get_actor_location()
        origin = unreal.Vector(loc.x, loc.y, loc.z + 160.0)
        old_yaw = a.get_actor_rotation().yaw
        res['old'] = {'yaw': round(old_yaw, 1), 'free_m': round(free_dist(origin, old_yaw) / 100.0, 1)}
        scan = {y: free_dist(origin, float(y)) for y in range(0, 360, 15)}
        sq = markers.get('Mk_Gilt_Square_BellSquare')
        want = None
        if sq is not None:
            s = sq.get_actor_location()
            if (s - loc).length() > 300.0:
                want = math.degrees(math.atan2(s.y - loc.y, s.x - loc.x))
        clear = [y for y, dist in scan.items() if dist >= 1500.0]
        if clear and want is not None:
            best = min(clear, key=lambda y: abs((y - want + 180.0) % 360.0 - 180.0))
        else:
            best = max(scan, key=scan.get)
        a.set_actor_rotation(unreal.Rotator(0.0, 0.0, float(best)), False)
        res['new'] = {'yaw': float(best), 'free_m': round(scan[best] / 100.0, 1), 'towards_square_yaw': round(want, 1) if want is not None else None}
        res['scan_m'] = {y: round(d / 100.0) for y, d in scan.items()}
        pkg = a.get_outermost()
        res['saved'] = unreal.EditorLoadingAndSavingUtils.save_packages([pkg], True)
        res['package'] = pkg.get_name()
json.dumps(res)
