assert lock_mine(), 'lock not mine'
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ues.get_game_world(), 'PIE already running: not touching it'
# mark it ours before starting: a StartPIE that times out can still start late, and r_stop must clean that up
builtins.__dict__['_AR_STARTED_PIE'] = True
r = await call_tool('EditorToolset.EditorAppToolset.StartPIE', options={'bSimulate': True, 'warmupSeconds': 2.0})
builtins.__dict__['_AR_P_OVERRIDE'] = {}  # a fresh run starts from the module's own tuning
AR.P.update(importlib.reload(AR).P)
SPOT = globals().get('SPOT', (700.0, 0.0, 8.0)); YAW = globals().get('YAW', 180.0)
# Test Town has another session's "Conversation Test NPC" that walks up to the Hero and stands in the shots.
# Remove its copy from OUR Simulate world only (the editor level is untouched).
_removed = []
for _a in unreal.GameplayStatics.get_all_actors_of_class(ues.get_game_world(), unreal.Character):
    if 'Conversation Test NPC' in _a.get_actor_label():
        _removed.append(_a.get_actor_label()); _a.destroy_actor()
summ = AR.setup(loc=SPOT, yaw=YAW)
summ['removed_from_pie'] = _removed
cam((SPOT[0] - 330.0, SPOT[1] + 260.0, SPOT[2] + 150.0), (SPOT[0], SPOT[1], SPOT[2] + 95.0))
json.dumps({'start': str(r)[:300], 'summary': summ}, default=str)
