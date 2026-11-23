o = unreal.find_object(None, '/Script/UnrealEd.Default__EditorPerformanceSettings')
was = builtins.__dict__.pop('_AR_THROTTLE_WAS', True)
o.set_editor_property('bThrottleCPUWhenNotForeground', was)
'throttle restored to %s' % was
