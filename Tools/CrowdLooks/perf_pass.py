"""Perf pass on the look Blueprints (perf session's asks, ArtDirection/Perf/README.md):
- leader-posed parts (garments, props) only tick their pose when rendered,
- groom components with no groom asset are removed (empty grooms still tick and cost render-thread time),
- optional LODSync min LOD (global MIN_LOD, default None = leave as is).
Global IDS (look ids) or all BP_Look_* in /Game/Characters/Lanthorne/Looks.
"""
import json

LOOKS = '/Game/Characters/Lanthorne/Looks'
eal = unreal.EditorAssetLibrary
sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
SDL = unreal.SubobjectDataBlueprintFunctionLibrary
ids = globals().get('IDS') or [p.split('BP_Look_')[-1].split('.')[0] for p in eal.list_assets(LOOKS, recursive=False) if 'BP_Look_' in p]
out = {}
for lid in ids:
    path = '%s/BP_Look_%s' % (LOOKS, lid)
    bp = unreal.load_asset(path)
    if bp is None:
        out[lid] = 'missing'
        continue
    handles = sds.k2_gather_subobject_data_for_blueprint(bp)
    root = handles[0]
    removed, ticked = [], 0
    to_remove = []
    seen = set()
    for h in handles:
        d = SDL.get_data(h)
        o = SDL.get_object(d)
        if o is None:
            continue
        name = str(SDL.get_variable_name(d))
        if name in seen:
            continue
        seen.add(name)
        cls = o.get_class().get_name()
        if cls == 'GroomComponent' and o.get_editor_property('groom_asset') is None:
            to_remove.append(h)
            removed.append(name)
        elif isinstance(o, unreal.SkeletalMeshComponent) and name not in ('Body', 'Face'):
            o.set_editor_property('visibility_based_anim_tick_option', unreal.VisibilityBasedAnimTickOption.ONLY_TICK_POSE_WHEN_RENDERED)
            ticked += 1
        elif cls == 'LODSyncComponent' and globals().get('MIN_LOD') is not None:
            o.set_editor_property('min_lod', MIN_LOD)
    if to_remove:
        try:
            sds.delete_subobjects(root, to_remove, bp)
        except Exception as e:
            out.setdefault('errors', []).append('%s: %s' % (lid, e))
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    eal.save_asset(path, only_if_is_dirty=False)
    out[lid] = {'removed': removed, 'pose_on_render': ticked}
RESULT = json.dumps(out)
