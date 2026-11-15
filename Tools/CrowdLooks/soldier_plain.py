"""The user (~20:10): "you are getting too fancy with the clothes they need to just be tight clothes".
Strip decoration from the armour-free soldier looks until Codex's plain fitted shirt/trousers/boots land:
hide sashes, tattoos, runes, glyphs, capes and mantles, satchels and ledgers. Fitted cloth and footwear stay."""
import json

eal = unreal.EditorAssetLibrary
sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
SDL = unreal.SubobjectDataBlueprintFunctionLibrary
DECOR = ('sash', 'tattoo', 'rune', 'glyph', 'mantle', 'cape', 'capelet', 'satchel', 'ledger', 'neckerchief', 'cap')
out = {}
for p in eal.list_assets('/Game/Characters/Lanthorne/Looks/Soldiers', recursive=False):
    path = p.split('.')[0]
    bp = unreal.load_asset(path)
    hidden = []
    seen = set()
    for h in sds.k2_gather_subobject_data_for_blueprint(bp):
        d = SDL.get_data(h)
        o = SDL.get_object(d)
        n = str(SDL.get_variable_name(d))
        if n in seen or not isinstance(o, unreal.SkeletalMeshComponent) or n in ('Body', 'Face'):
            continue
        seen.add(n)
        m = o.get_editor_property('skeletal_mesh_asset')
        key = (n + ' ' + (m.get_name() if m else '')).lower()
        if m and any(k in key for k in DECOR):
            o.set_editor_property('skeletal_mesh_asset', None)
            o.set_editor_property('visible', False)
            o.set_editor_property('hidden_in_game', True)
            hidden.append(n)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    eal.save_asset(path, only_if_is_dirty=False)
    out[path.split('/')[-1]] = hidden
RESULT = json.dumps(out)
