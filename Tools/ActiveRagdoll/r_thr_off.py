o = unreal.find_object(None, '/Script/UnrealEd.Default__EditorPerformanceSettings')
if '_AR_THROTTLE_WAS' not in builtins.__dict__:
    builtins.__dict__['_AR_THROTTLE_WAS'] = o.get_editor_property('bThrottleCPUWhenNotForeground')
o.set_editor_property('bThrottleCPUWhenNotForeground', False)
'throttle off (was %s)' % builtins.__dict__['_AR_THROTTLE_WAS']
