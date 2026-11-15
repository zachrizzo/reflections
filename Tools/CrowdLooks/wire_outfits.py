"""(Run with top-level await: it checks every mesh's bone 0 is root before wiring.)
Swap hero-cloak's fitted Codex outfits (plain, tight) into the finished looks.

Per outfit: the look's garment components get the new meshes (no material overrides: per-slot materials live on the
meshes), parts the outfit replaces or the user ruled out ("too fancy") are hidden, and the Body swaps to the outfit's
hidden-skin body. The NPC walker finds its animation from the Body mesh NAME (SKM_MHC_<Id>_BodyMesh ->
/Game/Characters/CrowdMotion/ABP_Crowd_<Id>), so each hidden body is copied to
/Game/Characters/Lanthorne/Bodies/SKM_MHC_<Id>_BodyMesh and gets ABP_Crowd_<Id> (a copy of its donor's).
The look keeps its own skin materials on the Body. Global DRY_RUN (default True), OUTFITS (keys to run).
"""
import json

eal = unreal.EditorAssetLibrary
sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
SDL = unreal.SubobjectDataBlueprintFunctionLibrary
CL = '/Game/Characters/Lanthorne/Clothing'
LOOKS = '/Game/Characters/Lanthorne/Looks'
BODIES = '/Game/Characters/Lanthorne/Bodies'
CM = '/Game/Characters/CrowdMotion'

CFG = {
    'GiltWorkerM': {
        'looks': ['BP_Look_GiltFerryman', 'BP_Look_GiltRamon'], 'donor': 'FerryPilot', 'ident': 'FerryPilotGiltWorker',
        'body': CL + '/Giltside/CivilianWorker/Bodies/SKM_FerryPilot_BodyHidden_Gilt_CivilianWorker_M_FerryPilot',
        'set': {'FerryPilotStripedTunic': CL + '/Giltside/CivilianWorker/SK_Gilt_Worker_M_Upper_FerryPilot',
                'FerryPilotTrousers': CL + '/Giltside/CivilianWorker/SK_Gilt_Worker_M_Lower_FerryPilot'},
        'hide': ['FerryPilotLeatherCapelet', 'FerryPilotNeckerchief', 'FerryPilotRopeBelt', 'FerryPilotHandCoil']},
    'GiltWorkerF': {
        'looks': ['BP_Look_GiltDrummer', 'BP_Look_GiltPriya'], 'donor': 'FestivalDrummer', 'ident': 'FestivalDrummerGiltWorker',
        'body': CL + '/Giltside/CivilianWorker/Bodies/SKM_FestivalDrummer_BodyHidden_Gilt_CivilianWorker_F_FestivalDrummer',
        'set': {'FestivalDrummer_Blouse': CL + '/Giltside/CivilianWorker/SK_Gilt_Worker_F_Upper_FestivalDrummer',
                'FestivalDrummer_Skirt': CL + '/Giltside/CivilianWorker/SK_Gilt_Worker_F_Lower_FestivalDrummer'},
        'hide': ['FestivalDrummer_Capelet', 'FestivalDrummer_Trousers', 'FestivalDrummer_Sash', 'FestivalDrummer_Belt',
                 'FestivalDrummer_RopeDrum', 'FestivalDrummer_DrumHarness', 'FestivalDrummer_Beaters']},
    'FrostCasterM': {
        'looks': ['BP_Look_FrostTobias', 'BP_Look_FrostWen'], 'donor': 'IvenRook', 'ident': 'IvenRookFrostCaster',
        'body': CL + '/Frostside/Caster/Bodies/SKM_IvenRook_BodyHidden_Frost_Caster_M_IvenRook',
        'set': {'IvenWorkTunic': CL + '/Frostside/Caster/SK_Frost_Caster_M_Upper_IvenRook',
                'IvenRagSkirt': CL + '/Frostside/Caster/SK_Frost_Caster_M_Lower_IvenRook',
                'IvenSandals': CL + '/Frostside/Caster/SK_Frost_Caster_M_Feet_IvenRook'},
        'hide': ['WhiteRagMantle', 'WhiteClothCap', 'IvenChestGlyph']},
    'FrostSoldierM': {
        'looks': ['Soldiers/FrostSoldier_Iven'], 'donor': 'IvenRook', 'ident': 'IvenRookFrostSoldier',
        'body': CL + '/Frostside/Soldier/Bodies/SKM_IvenRook_BodyHidden_Frost_Soldier_M_IvenRook',
        'set': {'IvenWorkTunic': CL + '/Frostside/Soldier/SK_Frost_Soldier_M_Upper_IvenRook',
                'IvenRagSkirt': CL + '/Frostside/Soldier/SK_Frost_Soldier_M_Lower_IvenRook',
                'IvenSandals': CL + '/Frostside/Soldier/SK_Frost_Soldier_M_Feet_IvenRook'},
        'hide': ['IvenChestGlyph', 'IvenTattoos']},
}


def templates(bp):
    out = {}
    for h in sds.k2_gather_subobject_data_for_blueprint(bp):
        d = SDL.get_data(h)
        o = SDL.get_object(d)
        if o is not None:
            out.setdefault(str(SDL.get_variable_name(d)), o)
    return out


def ensure_body(cfg):
    body = '%s/SKM_MHC_%s_BodyMesh' % (BODIES, cfg['ident'])
    abp = '%s/ABP_Crowd_%s' % (CM, cfg['ident'])
    if not eal.does_asset_exist(body):
        eal.duplicate_asset(cfg['body'], body)
        eal.save_asset(body, only_if_is_dirty=False)
    if not eal.does_asset_exist(abp):
        eal.duplicate_asset('%s/ABP_Crowd_%s' % (CM, cfg['donor']), abp)
        eal.save_asset(abp, only_if_is_dirty=False)
    return unreal.load_asset(body)


async def bone0(path):
    # The mesh's own bone list (hierarchy order): bone 0 must be 'root', or the body T-poses and can damage the
    # shared skeleton (14 Nov 20:16: hero-cloak's first fitted bodies had a bad root bone).
    r = await call_tool('EditorToolset.SkeletalMeshToolset.GetBoneNames', skeletalMesh={'refPath': path})
    bones = r.get('returnValue', r) if isinstance(r, dict) else r
    return bones[0] if bones else None


report = {}
for key in (globals().get('OUTFITS') or list(CFG)):
    cfg = CFG[key]
    missing = [p for p in [cfg['body']] + list(cfg['set'].values()) if not eal.does_asset_exist(p)]
    if missing:
        report[key] = {'missing': missing}
        continue
    bad = {}
    for p in [cfg['body']] + list(cfg['set'].values()):
        b = await bone0(p)
        if b != 'root':
            bad[p.split('/')[-1]] = b
    if bad:
        report[key] = {'REFUSED_bad_root_bone': bad}
        continue
    if globals().get('DRY_RUN', True):
        report[key] = 'ok (dry run)'
        continue
    body = ensure_body(cfg)
    done = {}
    for look in cfg['looks']:
        path = '%s/%s' % (LOOKS, look)
        bp = unreal.load_asset(path)
        T = templates(bp)
        changed = []
        for comp, mesh in cfg['set'].items():
            if comp in T:
                T[comp].set_editor_property('skeletal_mesh_asset', unreal.load_asset(mesh))
                T[comp].set_editor_property('override_materials', [])
                T[comp].set_editor_property('visible', True)
                T[comp].set_editor_property('hidden_in_game', False)
                changed.append(comp)
        for comp in cfg['hide']:
            if comp in T:
                T[comp].set_editor_property('skeletal_mesh_asset', None)
                T[comp].set_editor_property('visible', False)
                T[comp].set_editor_property('hidden_in_game', True)
                changed.append('-' + comp)
        T['Body'].set_editor_property('skeletal_mesh_asset', body)  # its skin override materials stay
        unreal.BlueprintEditorLibrary.compile_blueprint(bp)
        eal.save_asset(path, only_if_is_dirty=False)
        done[look.split('/')[-1]] = changed
    report[key] = done
RESULT = json.dumps(report)
