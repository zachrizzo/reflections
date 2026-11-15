"""Restore Common packages a MetaHuman build referenced but that were never saved (lost on an editor crash).

The build copies plugin content (/MetaHumanCharacter/...) into <Common>/... with the same relative path. For every
package under SCAN folders, any missing dependency under a Common folder is re-copied from the plugin and saved.
Globals: SCAN (list of /Game folders), COMMONS (list of Common roots), DRY_RUN.
"""
import json

eal = unreal.EditorAssetLibrary
ar = unreal.AssetRegistryHelpers.get_asset_registry()
opts = unreal.AssetRegistryDependencyOptions(include_soft_package_references=True, include_hard_package_references=True)
missing = set()
for folder in SCAN:
    for a in ar.get_assets_by_path(folder, recursive=True):
        for dep in ar.get_dependencies(a.package_name, opts) or []:
            d = str(dep)
            for c in COMMONS:
                if d.startswith(c + '/') and not eal.does_asset_exist(d):
                    missing.add((c, d))
fixed, failed = [], []
for c, d in sorted(missing):
    src = '/MetaHumanCharacter' + d[len(c):]
    if not eal.does_asset_exist(src):
        failed.append([d, 'no plugin source ' + src])
        continue
    if globals().get('DRY_RUN'):
        fixed.append(d)
        continue
    obj = eal.duplicate_asset(src, d)
    if obj:
        eal.save_asset(d, only_if_is_dirty=False)
        fixed.append(d)
    else:
        failed.append([d, 'duplicate failed'])
RESULT = json.dumps({'missing': len(missing), 'fixed': len(fixed), 'failed': failed[:20], 'sample': fixed[:10]})
