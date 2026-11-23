# Read-only: names of the packages the editor holds with unsaved changes.
sorted(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + ["MAPS:"] + sorted(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
