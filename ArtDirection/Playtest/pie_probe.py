w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
r = {}
if not w:
    r['pie'] = False
else:
    p = unreal.GameplayStatics.get_player_pawn(w, 0)
    pc = unreal.GameplayStatics.get_player_controller(w, 0)
    r['paused'] = unreal.GameplayStatics.is_game_paused(w)
    r['t'] = round(unreal.GameplayStatics.get_time_seconds(w), 1)
    if pc:
        r['moveIgnored'] = pc.is_move_input_ignored()
        r['lookIgnored'] = pc.is_look_input_ignored()
    if p:
        r['pawn'] = p.get_name()
        l = p.get_actor_location()
        r['loc'] = [round(l.x), round(l.y), round(l.z)]
        r['speed'] = round(p.get_velocity().length())
        d = p.get_component_by_class(unreal.ReflectionsSampleSpellDriver)
        if d:
            r['mana'] = round(d.get_mana(), 1)
            r['casting'] = d.is_casting()
            r['spell'] = str(d.get_selected_spell())
            r['defeated'] = d.is_defeated()
        j = p.get_component_by_class(unreal.ReflectionsWorldJumpComponent)
        if j:
            r['world'] = str(j.get_current_world())
            for name in ('UP', 'DOWN'):
                try:
                    r['can_' + name] = str(j.can_jump(getattr(unreal.ReflectionsJumpDirection, name)))
                except Exception as e:
                    r['can_' + name] = 'err ' + str(e)[:100]
r
