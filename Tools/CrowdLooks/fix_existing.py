"""Finished looks for the seven existing faces: same fitted outfit Blueprint, plus the grooms they were missing.

Global FIXES: list of {id, outfit_bp, sex, age, side, role, grooms: {Component: plugin groom name}, mats: {...}}
Grooms come from the MetaHuman Creator wardrobe (/MetaHumanCharacter/Optional/Grooms) and get a binding to this
face mesh, saved in /Game/Characters/Lanthorne/Grooms/<id>/. Output: /Game/Characters/Lanthorne/Looks/BP_Look_<id>.
"""
import json

LOOKS = '/Game/Characters/Lanthorne/Looks'
GROOM_DIR = '/Game/Characters/Lanthorne/Grooms'
PLUGIN = '/MetaHumanCharacter/Optional/Grooms/GroomAssets'
KIND = {'Hair': 'Hair', 'Eyebrows': 'Eyebrows', 'Eyelashes': 'Eyelashes', 'Beard': 'Beards', 'Mustache': 'Mustaches', 'Fuzz': 'Peachfuzz'}
eal = unreal.EditorAssetLibrary
sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
SDL = unreal.SubobjectDataBlueprintFunctionLibrary
# The head mesh the wardrobe grooms are authored on (read from a binding the MetaHuman build made).
ref_binding = unreal.load_asset('/Game/Characters/Lanthorne/People/GiltRowena/Built/MHC_GiltRowena/Grooms/Eyebrows_M_SlightArch_Binding')
SOURCE_HEAD = ref_binding.get_editor_property('source_skeletal_mesh') if ref_binding else None


def templates(bp):
    out = {}
    for h in sds.k2_gather_subobject_data_for_blueprint(bp):
        d = SDL.get_data(h)
        o = SDL.get_object(d)
        if o is not None:
            out.setdefault(str(SDL.get_variable_name(d)), o)
    return out


def binding_for(groom_name, comp, face, pid):
    path = '%s/%s/%s/%s' % (PLUGIN, KIND[comp], groom_name, groom_name)
    groom = unreal.load_asset(path)
    if groom is None:
        raise RuntimeError('no groom ' + path)
    pkg = '%s/%s/%s_Binding' % (GROOM_DIR, pid, groom_name)
    if eal.does_asset_exist(pkg):
        return groom, unreal.load_asset(pkg)
    b = unreal.GroomLibrary.create_new_groom_binding_asset_with_path(pkg, groom, face, 100, SOURCE_HEAD, 0)
    return groom, b


results = []
for F in FIXES:
    log = {'id': F['id'], 'set': []}
    dst = '%s/BP_Look_%s' % (LOOKS, F['id'])
    if eal.does_asset_exist(dst):
        eal.delete_asset(dst)
    eal.duplicate_asset(F['outfit_bp'], dst)
    bp = unreal.load_asset(dst)
    T = templates(bp)
    face = T['Face'].get_editor_property('skeletal_mesh_asset')
    for comp, gname in (F.get('grooms') or {}).items():
        if gname is None:
            T[comp].set_editor_property('groom_asset', None)
            T[comp].set_editor_property('binding_asset', None)
            continue
        if gname.startswith('/Game/'):
            # "<built BP path>" : take this component's groom (card LODs from a MetaHuman build) and its materials
            # from a built person, with a new binding to this face.
            S = templates(unreal.load_asset(gname))
            groom = S[comp].get_editor_property('groom_asset')
            mats = list(S[comp].get_editor_property('override_materials'))
            pkg = '%s/%s/%s_Binding' % (GROOM_DIR, F['id'], groom.get_name())
            b = unreal.load_asset(pkg) if eal.does_asset_exist(pkg) else \
                unreal.GroomLibrary.create_new_groom_binding_asset_with_path(pkg, groom, face, 100, SOURCE_HEAD, 0)
            T[comp].set_editor_property('groom_asset', groom)
            T[comp].set_editor_property('binding_asset', b)
            T[comp].set_editor_property('override_materials', mats)
            log['set'].append('%s=%s (from %s)' % (comp, groom.get_name(), gname.split('/')[-1]))
            continue
        groom, b = binding_for(gname, comp, face, F['id'])
        T[comp].set_editor_property('groom_asset', groom)
        T[comp].set_editor_property('binding_asset', b)
        hair_mi = (F.get('groom_mats') or {}).get(comp)
        T[comp].set_editor_property('override_materials', [unreal.load_asset(hair_mi)] if hair_mi else [])
        log['set'].append('%s=%s' % (comp, gname))
    for comp in ('Hair', 'Eyebrows', 'Eyelashes', 'Fuzz', 'Mustache', 'Beard'):
        if comp in T:
            try:
                tf = T[comp].get_editor_property('primary_component_tick')
                tf.set_editor_property('tick_group', unreal.TickingGroup.TG_POST_UPDATE_WORK)
                T[comp].set_editor_property('primary_component_tick', tf)
            except Exception as e:
                log['tick_err'] = str(e)
    for comp, mat in (F.get('mats') or {}).items():
        if comp in T:
            T[comp].set_editor_property('override_materials', [unreal.load_asset(mat)])
    cdo = unreal.get_default_object(bp.generated_class())
    tags = [str(t) for t in cdo.get_editor_property('tags') if not str(t).startswith(('NPC_Voice_', 'Look_'))]
    tags += ['NPC_Voice_' + F['sex'], 'Look_Age_' + F['age'], 'Look_Side_' + F['side'], 'Look_Role_' + F['role'], 'Look_Id_' + F['id']]
    cdo.set_editor_property('tags', [unreal.Name(t) for t in tags])
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    eal.save_asset(dst, only_if_is_dirty=False)
    for p in unreal.AssetRegistryHelpers.get_asset_registry().get_assets_by_path('%s/%s' % (GROOM_DIR, F['id']), recursive=True):
        eal.save_asset(str(p.package_name), only_if_is_dirty=True)
    log['bp'] = dst
    results.append(log)
RESULT = json.dumps(results)
