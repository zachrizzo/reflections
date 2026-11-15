import json
ar = unreal.AssetRegistryHelpers.get_asset_registry()
out = {}
f = unreal.ARFilter(class_paths=[unreal.TopLevelAssetPath('/Script/MetaHumanCharacter', 'MetaHumanCharacter')], recursive_classes=True)
out['mhc_all'] = sorted(str(a.package_name) for a in ar.get_assets(f))
# any preset-ish data under the plugin
assets = ar.get_assets_by_path('/MetaHumanCharacter', recursive=True)
from collections import Counter
out['plugin_classes'] = dict(Counter(str(a.asset_class_path.asset_name) for a in assets).most_common(40))
out['preset_like'] = sorted(str(a.package_name) for a in assets if 'reset' in str(a.package_name).lower())[:80]
out['enums'] = {}
for e in ['MetaHumanDefaultPipelineType', 'MetaHumanQualityLevel', 'MetaHumanCharacterEyelashesType']:
    try:
        out['enums'][e] = [x for x in dir(getattr(unreal, e)) if x.isupper()]
    except Exception as ex:
        out['enums'][e] = str(ex)
RESULT = json.dumps(out, indent=0)
