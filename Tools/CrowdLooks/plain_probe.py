"""READ-ONLY probe before the plain-clothes re-swap (hero-cloak row H, 22:3x). Top-level await.
For each new mesh: exists, bone 0, skeleton, LOD count. For each target look: its skeletal parts, with mesh and
visibility, so the swap maps onto the right components. Writes OUT_JSON."""
import json

eal = unreal.EditorAssetLibrary
sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
SDL = unreal.SubobjectDataBlueprintFunctionLibrary
GW = '/Game/Characters/Lanthorne/Clothing/Giltside/CivilianWorker/'
GS = '/Game/Characters/Lanthorne/Clothing/Giltside/MedievalSoldier/'
FS = '/Game/Characters/Lanthorne/Clothing/Frostside/Soldier/'
MESHES = [GS + 'SK_Gilt_Soldier_M_Upper_ArchiveApprentice', GS + 'SK_Gilt_Soldier_M_Lower_ArchiveApprentice',
          GS + 'SK_Gilt_Soldier_M_Feet_ArchiveApprentice',
          GS + 'Bodies/SKM_ArchiveApprentice_BodyHidden_Gilt_MedievalSoldier_M_ArchiveApprentice',
          GW + 'SK_Gilt_Worker_M_Upper_FerryPilot', GW + 'SK_Gilt_Worker_M_Lower_FerryPilot',
          GW + 'SK_Gilt_Worker_M_Feet_FerryPilot', GW + 'Bodies/SKM_FerryPilot_BodyHidden_Gilt_CivilianWorker_M_FerryPilot',
          GW + 'SK_Gilt_Worker_F_Upper_FestivalDrummer', GW + 'SK_Gilt_Worker_F_Lower_FestivalDrummer',
          GW + 'SK_Gilt_Worker_F_Feet_FestivalDrummer',
          GW + 'Bodies/SKM_FestivalDrummer_BodyHidden_Gilt_CivilianWorker_F_FestivalDrummer',
          FS + 'SK_Frost_Soldier_M_Upper_IvenRook', FS + 'SK_Frost_Soldier_M_Lower_IvenRook',
          FS + 'SK_Frost_Soldier_M_Feet_IvenRook', FS + 'Bodies/SKM_IvenRook_BodyHidden_Frost_Soldier_M_IvenRook']
LOOKS = ['BP_Look_GiltFerryman', 'BP_Look_GiltRamon', 'BP_Look_GiltDrummer', 'BP_Look_GiltPriya',
         'BP_Look_FrostIven', 'Soldiers/FrostSoldier_Iven', 'Templates/BP_Template_GiltSoldier_M']


async def bone0(path):
    if '.' not in path.split('/')[-1]:
        path = path + '.' + path.split('/')[-1]
    r = await call_tool('EditorToolset.SkeletalMeshToolset.GetBoneNames', mesh={'refPath': path})
    bones = r.get('returnValue', r) if isinstance(r, dict) else r
    return (bones[0] if bones else None), len(bones or [])


out = {'meshes': {}, 'looks': {}}
for m in MESHES:
    k = m.split('/')[-1]
    if not eal.does_asset_exist(m):
        out['meshes'][k] = 'MISSING'
        continue
    a = unreal.load_asset(m)
    b0, nb = await bone0(m)
    out['meshes'][k] = {'bone0': b0, 'bones': nb, 'skel': a.get_editor_property('skeleton').get_path_name().split('.')[0]}
for lk in LOOKS:
    p = '/Game/Characters/Lanthorne/Looks/' + lk
    bp = unreal.load_asset(p)
    if bp is None:
        out['looks'][lk] = 'MISSING'
        continue
    parts = {}
    seen = set()
    for h in sds.k2_gather_subobject_data_for_blueprint(bp):
        d = SDL.get_data(h)
        o = SDL.get_object(d)
        n = str(SDL.get_variable_name(d))
        if o is None or n in seen or not isinstance(o, unreal.SkeletalMeshComponent):
            continue
        seen.add(n)
        mm = o.get_editor_property('skeletal_mesh_asset')
        parts[n] = [mm.get_name() if mm else None, bool(o.get_editor_property('visible')),
                    (mm.get_editor_property('skeleton').get_path_name().split('/')[-1] if mm else None)]
    out['looks'][lk] = parts
out['dirty'] = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
open(OUT_JSON, 'w', encoding='utf-8').write(json.dumps(out, indent=1))
