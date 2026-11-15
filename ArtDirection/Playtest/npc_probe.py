# PIE probe: NPC count / incapacitated (dead) count / nearest NPC to the hero, plus the camera height.
# Run through PythonScriptingTools.execute_python:  exec(open(<this file>).read()); r
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
r = {}
if not w:
    r['pie'] = False
else:
    p = unreal.GameplayStatics.get_player_pawn(w, 0)
    cam = unreal.GameplayStatics.get_player_camera_manager(w, 0)
    r['map'] = w.get_name()
    r['t'] = round(unreal.GameplayStatics.get_time_seconds(w), 1)
    if p and cam:
        pl = p.get_actor_location()
        cl = cam.get_camera_location()
        r['cam_minus_pawn_z'] = round(cl.z - pl.z)
        r['cam_dist'] = round((cl - pl).length())
    npcs = []
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
        c = a.get_component_by_class(unreal.ReflectionsNpcReactionComponent)
        if c:
            npcs.append((a, c))
    r['npcs'] = len(npcs)
    r['incapacitated'] = sum(1 for a, c in npcs if c.is_incapacitated())
    if p and npcs:
        pl = p.get_actor_location()
        a, c = min(npcs, key=lambda ac: (ac[0].get_actor_location() - pl).length())
        r['nearest'] = [a.get_name(), round((a.get_actor_location() - pl).length()), c.is_incapacitated()]
r
