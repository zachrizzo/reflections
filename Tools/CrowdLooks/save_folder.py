# Save every dirty package under FOLDER (only my folders).
import json
assert FOLDER.startswith('/Game/Characters/Lanthorne/')
ar = unreal.AssetRegistryHelpers.get_asset_registry()
assets = ar.get_assets_by_path(FOLDER, recursive=True)
saved = 0
names = set(str(a.package_name) for a in assets)
for n in sorted(names):
    if unreal.EditorAssetLibrary.save_asset(n, only_if_is_dirty=True):
        saved += 1
from collections import Counter
RESULT = json.dumps({'assets': len(names), 'classes': dict(Counter(str(a.asset_class_path.asset_name) for a in assets))})
