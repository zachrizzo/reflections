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
    # hero-cloak row H (22:3x): plain, tight, one colour per side; probe 22:33: all 16 meshes bone 0 'root', 342 bones.
    'GiltWorkerM': {
        'looks': ['BP_Look_GiltFerryman', 'BP_Look_GiltRamon'], 'donor': 'FerryPilot', 'ident': 'FerryPilotGiltWorker',
        'body': CL + '/Giltside/CivilianWorker/Bodies/SKM_FerryPilot_BodyHidden_Gilt_CivilianWorker_M_FerryPilot',
        'set': {'FerryPilotStripedTunic': CL + '/Giltside/CivilianWorker/SK_Gilt_Worker_M_Upper_FerryPilot',
                'FerryPilotTrousers': CL + '/Giltside/CivilianWorker/SK_Gilt_Worker_M_Lower_FerryPilot',
                'FerryPilotRidingBoots': CL + '/Giltside/CivilianWorker/SK_Gilt_Worker_M_Feet_FerryPilot'}},
    'GiltWorkerF': {
        'looks': ['BP_Look_GiltDrummer', 'BP_Look_GiltPriya'], 'donor': 'FestivalDrummer', 'ident': 'FestivalDrummerGiltWorker',
        'body': CL + '/Giltside/CivilianWorker/Bodies/SKM_FestivalDrummer_BodyHidden_Gilt_CivilianWorker_F_FestivalDrummer',
        'set': {'FestivalDrummer_Blouse': CL + '/Giltside/CivilianWorker/SK_Gilt_Worker_F_Upper_FestivalDrummer',
                'FestivalDrummer_Skirt': CL + '/Giltside/CivilianWorker/SK_Gilt_Worker_F_Lower_FestivalDrummer',
                'FestivalDrummer_Boots': CL + '/Giltside/CivilianWorker/SK_Gilt_Worker_F_Feet_FestivalDrummer'}},
    'FrostSoldierM': {
        'looks': ['Soldiers/FrostSoldier_Iven'], 'donor': 'IvenRook', 'ident': 'IvenRookFrostSoldier',
        'body': CL + '/Frostside/Soldier/Bodies/SKM_IvenRook_BodyHidden_Frost_Soldier_M_IvenRook',
        'set': {'IvenWorkTunic': CL + '/Frostside/Soldier/SK_Frost_Soldier_M_Upper_IvenRook',
                'IvenRagSkirt': CL + '/Frostside/Soldier/SK_Frost_Soldier_M_Lower_IvenRook',
                'IvenSandals': CL + '/Frostside/Soldier/SK_Frost_Soldier_M_Feet_IvenRook'}},
    'GiltSoldierM': {
        # Orchestrator OK 01:24: the Gilt soldier set on a COPY of GiltArchivist (same body, no new face).
        'copy_from': 'BP_Look_GiltArchivist', 'look_id': 'GiltSoldierArchivist', 'role': 'Soldier',
        'looks': ['Soldiers/GiltSoldier_Archivist'], 'donor': 'ArchiveApprentice', 'ident': 'ArchiveApprenticeGiltSoldier',
        'body': CL + '/Giltside/MedievalSoldier/Bodies/SKM_ArchiveApprentice_BodyHidden_Gilt_MedievalSoldier_M_ArchiveApprentice',
        'set': {'ArchiveApprenticeCoat': CL + '/Giltside/MedievalSoldier/SK_Gilt_Soldier_M_Upper_ArchiveApprentice',
                'ArchiveApprenticeTrousers': CL + '/Giltside/MedievalSoldier/SK_Gilt_Soldier_M_Lower_ArchiveApprentice',
                'ArchiveApprenticeBoots': CL + '/Giltside/MedievalSoldier/SK_Gilt_Soldier_M_Feet_ArchiveApprentice'}},
    # hero-cloak row 3a (01:38): BridgeGuard F soldier sets, bone 0 root, 342 bones; hidden bodies hide feet too.
    'GiltSoldierF': {
        'looks': ['Soldiers/GiltSoldier_BridgeGuard', 'Soldiers/GiltSoldier_Rowena'], 'donor': 'BridgeGuard',
        'ident': 'BridgeGuardGiltSoldier',
        'body': CL + '/Giltside/MedievalSoldier/Bodies/SKM_BridgeGuard_BodyHidden_Gilt_Soldier_F_BridgeGuard',
        'set': {'BridgeGuard_Gambeson': CL + '/Giltside/MedievalSoldier/SK_Gilt_Soldier_F_Upper_BridgeGuard',
                'BridgeGuard_Trousers': CL + '/Giltside/MedievalSoldier/SK_Gilt_Soldier_F_Lower_BridgeGuard',
                'BridgeGuard_Boots': CL + '/Giltside/MedievalSoldier/SK_Gilt_Soldier_F_Feet_BridgeGuard'}},
    'FrostSoldierF': {
        'looks': ['Soldiers/FrostSoldier_Amara', 'Soldiers/FrostSoldier_Nia', 'Soldiers/FrostSoldier_Saran'],
        'donor': 'BridgeGuard', 'ident': 'BridgeGuardFrostSoldier',
        'body': CL + '/Frostside/Soldier/Bodies/SKM_BridgeGuard_BodyHidden_Frost_Soldier_F_BridgeGuard',
        'set': {'WhiteGuardWorkTunic': CL + '/Frostside/Soldier/SK_Frost_Soldier_F_Upper_BridgeGuard',
                'WhiteGuardRagSkirt': CL + '/Frostside/Soldier/SK_Frost_Soldier_F_Lower_BridgeGuard',
                'WhiteGuardSandals': CL + '/Frostside/Soldier/SK_Frost_Soldier_F_Feet_BridgeGuard'}},
    # Frost caster: waits for Codex's plain set. Gilt soldier M (ArchiveApprentice): no faces tonight (no new faces).
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
    if '.' not in path.split('/')[-1]:
        path = path + '.' + path.split('/')[-1]  # the tool wants the object path
    r = await call_tool('EditorToolset.SkeletalMeshToolset.GetBoneNames', mesh={'refPath': path})
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
        if globals().get('ONLY') and look not in ONLY:
            continue
        path = '%s/%s' % (LOOKS, look)
        if cfg.get('copy_from') and not eal.does_asset_exist(path):
            eal.duplicate_asset('%s/%s' % (LOOKS, cfg['copy_from']), path)
            cbp = unreal.load_asset(path)
            unreal.BlueprintEditorLibrary.compile_blueprint(cbp)  # templates are empty until the copy compiles
            cdo = unreal.get_default_object(cbp.generated_class())
            tags = [str(t) for t in cdo.get_editor_property('tags') if not str(t).startswith(('Look_Role_', 'Look_Id_'))]
            tags += ['Look_Role_' + cfg['role'], 'Look_Id_' + cfg['look_id']]
            cdo.set_editor_property('tags', [unreal.Name(t) for t in tags])
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
        # The hidden-skin bodies have no skin under the new clothes: every other old part would float, so hide it.
        for comp, o in T.items():
            if comp in ('Body', 'Face') or comp in cfg['set'] or not isinstance(o, unreal.SkeletalMeshComponent):
                continue
            if o.get_editor_property('skeletal_mesh_asset') is not None:
                o.set_editor_property('skeletal_mesh_asset', None)
                o.set_editor_property('visible', False)
                o.set_editor_property('hidden_in_game', True)
                changed.append('-' + comp)
        T['Body'].set_editor_property('skeletal_mesh_asset', body)  # its skin override materials stay
        unreal.BlueprintEditorLibrary.compile_blueprint(bp)
        eal.save_asset(path, only_if_is_dirty=False)
        done[look.split('/')[-1]] = changed
    # Root after, on the walker-named copy, and never save a shared skeleton.
    done['_body_copy_bone0'] = await bone0(body.get_path_name().split('.')[0])
    exec(open(PROJECT + 'Tools/CrowdLooks/skel_guard.py', encoding='utf-8').read(), globals())
    done['_skel_reloaded'] = skel_guard()
    report[key] = done
RESULT = json.dumps(report)
if globals().get('OUT_JSON'):
    open(OUT_JSON, 'w', encoding='utf-8').write(RESULT)
