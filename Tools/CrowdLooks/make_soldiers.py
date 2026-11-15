"""Armour-free soldier looks (the user, 14 Nov ~20:00: "Remove the armor from the soldiers").

GiltSoldier_<X>: copies of the Giltside guard looks with every armour part removed (plates, pauldrons, mail,
bracers, metal helmets), keeping fitted cloth (gambeson, trousers, boots, sash) and the carried shield.
FrostSoldier_<X>: copies of the Frostside soldier looks (already cloth only), with the leftover hidden armour removed too.
Armour parts get no mesh and are hidden, so they cost nothing. Tags: Look_Role_Soldier and Look_Id_<Side>Soldier<X>.
The source looks (named characters may wear them) are unchanged. Global DRY_RUN (default True).
"""
import json

LOOKS = '/Game/Characters/Lanthorne/Looks'
ARMOUR = ('armor', 'armour', 'pauldron', 'plate', 'mail', 'bracer', 'helmet', 'helm', 'gauntlet', 'greave', 'cuirass')
JOBS = [('GiltBridgeGuard', 'GiltSoldier_BridgeGuard', 'GiltSoldierBridgeGuard'),
        ('GiltRowena', 'GiltSoldier_Rowena', 'GiltSoldierRowena'),
        ('FrostIven', 'FrostSoldier_Iven', 'FrostSoldierIven'),
        ('FrostSaran', 'FrostSoldier_Saran', 'FrostSoldierSaran'),
        ('FrostNia', 'FrostSoldier_Nia', 'FrostSoldierNia'),
        ('FrostAmara', 'FrostSoldier_Amara', 'FrostSoldierAmara')]
eal = unreal.EditorAssetLibrary
sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
SDL = unreal.SubobjectDataBlueprintFunctionLibrary


def templates(bp):
    out = {}
    for h in sds.k2_gather_subobject_data_for_blueprint(bp):
        d = SDL.get_data(h)
        o = SDL.get_object(d)
        if o is not None:
            out.setdefault(str(SDL.get_variable_name(d)), o)
    return out


report = {}
for src_id, name, look_id in JOBS:
    src = '%s/BP_Look_%s' % (LOOKS, src_id)
    dst = '%s/Soldiers/%s' % (LOOKS, name)
    T = templates(unreal.load_asset(src))
    armour = [n for n, o in T.items() if isinstance(o, unreal.SkeletalMeshComponent)
              and any(k in (n + ' ' + (o.get_editor_property('skeletal_mesh_asset').get_name() if o.get_editor_property('skeletal_mesh_asset') else '')).lower() for k in ARMOUR)]
    report[name] = {'from': src_id, 'armour_removed': armour}
    if globals().get('DRY_RUN', True):
        continue
    if eal.does_asset_exist(dst):
        eal.delete_asset(dst)
    eal.duplicate_asset(src, dst)
    bp = unreal.load_asset(dst)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    T2 = templates(bp)
    for n in armour:
        o = T2[n]
        o.set_editor_property('skeletal_mesh_asset', None)
        o.set_editor_property('visible', False)
        o.set_editor_property('hidden_in_game', True)
    cdo = unreal.get_default_object(bp.generated_class())
    tags = [str(t) for t in cdo.get_editor_property('tags') if not str(t).startswith(('Look_Role_', 'Look_Id_'))]
    tags += ['Look_Role_Soldier', 'Look_Id_' + look_id]
    cdo.set_editor_property('tags', [unreal.Name(t) for t in tags])
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    eal.save_asset(dst, only_if_is_dirty=False)
    report[name]['tags'] = [t for t in tags if t.startswith(('Look_', 'NPC_Voice'))]
RESULT = json.dumps(report)
