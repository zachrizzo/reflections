out = {}
try:
    AR.teardown(destroy=True)
except Exception as e:
    out['teardown_err'] = str(e)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if ues.get_game_world() and builtins.__dict__.get('_AR_STARTED_PIE') and lock_mine():
    await call_tool('EditorToolset.EditorAppToolset.StopPIE')
    out['stopped'] = True
    builtins.__dict__['_AR_STARTED_PIE'] = False
else:
    out['stopped'] = False
    out['why'] = [bool(ues.get_game_world()), builtins.__dict__.get('_AR_STARTED_PIE'), lock_mine()]
json.dumps(out)
