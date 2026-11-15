import json
ar = unreal.AssetRegistryHelpers.get_asset_registry()
out = {}
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w = ues.get_editor_world()
out['editor_world'] = w.get_path_name() if w else None
out['pie'] = bool(ues.get_game_world())
# grooms and wardrobe items outside /Game
f = unreal.ARFilter(class_paths=[unreal.TopLevelAssetPath('/Script/HairStrandsCore', 'GroomAsset')], recursive_classes=True)
g = ar.get_assets(f)
out['grooms_all'] = sorted(set(str(a.package_name) for a in g if not str(a.package_name).startswith('/Game')))[:400]
f2 = unreal.ARFilter(class_paths=[unreal.TopLevelAssetPath('/Script/MetaHumanCharacterPalette', 'MetaHumanWardrobeItem')], recursive_classes=True)
wi = ar.get_assets(f2)
out['wardrobe_items_count'] = len(wi)
out['wardrobe_items'] = sorted(str(a.package_name) for a in wi)[:300]
RESULT = json.dumps(out, indent=0)
