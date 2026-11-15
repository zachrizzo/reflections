# Dump a Blueprint's own SCS components with their key properties. Global: BPS (list of BP asset paths)
import json
sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
out = {}
for path in BPS:
    bp = unreal.load_asset(path)
    rows = []
    handles = sds.k2_gather_subobject_data_for_blueprint(bp)
    for h in handles:
        d = unreal.SubobjectDataBlueprintFunctionLibrary.get_data(h)
        o = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(d)
        if o is None:
            continue
        r = {'name': str(unreal.SubobjectDataBlueprintFunctionLibrary.get_variable_name(d)), 'cls': o.get_class().get_name(),
             'inherited': unreal.SubobjectDataBlueprintFunctionLibrary.is_inherited_component(d)}
        for prop in ('skeletal_mesh_asset', 'groom_asset', 'binding_asset', 'leader_pose_component', 'override_materials', 'visible', 'hidden_in_game', 'anim_class', 'tags', 'component_tags'):
            try:
                v = o.get_editor_property(prop)
                if hasattr(v, 'get_path_name'):
                    v = v.get_path_name()
                elif isinstance(v, (list, unreal.Array)):
                    v = [x.get_path_name() if hasattr(x, 'get_path_name') else str(x) for x in v]
                r[prop] = v if isinstance(v, (str, bool, int, float, list)) or v is None else str(v)
            except Exception:
                pass
        rows.append(r)
    cdo = unreal.get_default_object(bp.generated_class())
    out[path] = {'parent': bp.generated_class().get_super_class().get_path_name() if hasattr(bp.generated_class(), 'get_super_class') else '', 'tags': [str(t) for t in cdo.tags], 'comps': rows}
RESULT = json.dumps(out, indent=0)
