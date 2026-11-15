"""Cap texture sizes on built people (size budget + memory). Global PIDS.
Body baked maps -> 1024 (only hands, neck and forearms show under the outfits); eye and teeth maps -> 512;
face maps stay (the packaging device profile caps Character textures at 2048 in the cook)."""
import json

eal = unreal.EditorAssetLibrary
ar = unreal.AssetRegistryHelpers.get_asset_registry()
out = {}
for pid in PIDS:
    n = 0
    for a in ar.get_assets_by_path('/Game/Characters/Lanthorne/People/%s/Built' % pid, recursive=True):
        if str(a.asset_class_path.asset_name) != 'Texture2D':
            continue
        path = str(a.package_name)
        name = path.split('/')[-1]
        cap = 1024 if '/Body/' in path else (512 if name.startswith(('T_Eye', 'T_Teeth')) else None)
        if cap is None:
            continue
        t = unreal.load_asset(path)
        if t.get_editor_property('max_texture_size') != cap:
            t.set_editor_property('max_texture_size', cap)
            eal.save_asset(path, only_if_is_dirty=False)
            n += 1
    out[pid] = n
RESULT = json.dumps(out)
