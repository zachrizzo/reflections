"""PLAN B for the NPC grooms (only if the slot is too short for groom_fix.py): every look back to LODSync ForcedLOD 0
(the 14 Nov 18:30 state: cards on 3-LOD looks, mesh LOD 5 hair on 2-LOD looks; loses the body LOD saving).
Saves only each look's own package. Globals: DRY_RUN (default True), OUT_JSON."""
import json
eal = unreal.EditorAssetLibrary
sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
SDL = unreal.SubobjectDataBlueprintFunctionLibrary
out = {}
for d in ['/Game/Characters/Lanthorne/Looks', '/Game/Characters/Lanthorne/Looks/Pewterside', '/Game/Characters/Lanthorne/Looks/Soldiers']:
    for p in eal.list_assets(d, recursive=False):
        path = p.split('.')[0]
        if not path.split('/')[-1].startswith(('BP_Look_', 'PewLook_', 'GiltSoldier_', 'FrostSoldier_')):
            continue
        bp = unreal.load_asset(path)
        for h in sds.k2_gather_subobject_data_for_blueprint(bp):
            o = SDL.get_object(SDL.get_data(h))
            if o is not None and o.get_class().get_name() == 'LODSyncComponent':
                out[path.split('/')[-1]] = [o.get_editor_property('forced_lod'), o.get_editor_property('min_lod')]
                if not globals().get('DRY_RUN', True):
                    o.set_editor_property('forced_lod', 0)
                    o.set_editor_property('min_lod', 0)
                    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
                    eal.save_asset(path, only_if_is_dirty=False)
                break
out['_dirty_after'] = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
if globals().get('OUT_JSON'):
    open(OUT_JSON, 'w', encoding='utf-8').write(json.dumps(out, indent=1))
