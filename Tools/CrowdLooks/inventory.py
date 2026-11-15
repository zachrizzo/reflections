# Inventory of character assets (read-only).
import json
from collections import Counter
ar = unreal.AssetRegistryHelpers.get_asset_registry()
all_assets = ar.get_assets_by_path('/Game', recursive=True)
c = Counter(str(a.asset_class_path.asset_name) for a in all_assets)
out = {}
out['class_counts'] = {k: v for k, v in c.items() if any(s in k for s in ['MetaHuman', 'Groom', 'Skeletal', 'Collection'])}
out['mh'] = sorted(str(a.package_name) + ' :: ' + str(a.asset_class_path.asset_name) for a in all_assets
                   if 'MetaHuman' in str(a.asset_class_path.asset_name) or 'Collection' in str(a.asset_class_path.asset_name))
out['grooms'] = sorted(str(a.package_name) for a in all_assets if str(a.asset_class_path.asset_name) == 'GroomAsset')
RESULT = json.dumps(out, indent=0)
