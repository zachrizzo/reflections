"""Create Lanthorne people from Epic MetaHuman presets, ready to build. Globals: IDS (person ids from people.json).

Per person (blocking cloud calls, ~15 s each): duplicate the preset, give it the donor's body, auto-rig the face
(joints only: no blendshapes, a lighter face), download texture sources. Build with build_one.py afterwards.
"""
import json
import time

ROOT = '/Game/Characters/Lanthorne/People'
DONORS = {
    'CoinClerk': '/Game/Characters/RedLondon/CoinClerk/MHC_CoinClerk',
    'BridgeGuard': '/Game/Characters/RedLondon/BridgeGuard/MHC_BridgeGuard',
    'FestivalDrummer': '/Game/Characters/RedLondon/FestivalDrummer/MHC_FestivalDrummer',
    'ArchiveApprentice': '/Game/Characters/RedLondon/ArchiveApprentice/MHC_ArchiveApprentice',
    'FerryPilot': '/Game/Characters/RedLondon/FerryPilot/MHC_FerryPilot',
    'GlassArtisan': '/Game/Characters/RedLondon/GlassArtisan/MHC_GlassArtisan',
    'IvenRook': '/Game/Characters/WhiteLondon/IvenRook/MetaHuman/MHC_IvenRook',
}
cast = {p['id']: p for p in json.load(open(PROJECT + 'Tools/CrowdLooks/people.json'))['new']}
eal = unreal.EditorAssetLibrary
sub = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
out = []
for pid in IDS:
    P = cast[pid]
    row = {'id': pid}
    t0 = time.time()
    dst = '%s/%s/MHC_%s' % (ROOT, pid, pid)
    if not eal.does_asset_exist(dst):
        # Load the preset first: duplicating an unloaded preset silently fails.
        pre = unreal.load_asset('/MetaHumanCharacter/Optional/Presets/' + P['preset'])
        if not eal.duplicate_loaded_asset(pre, dst):
            unreal.AssetToolsHelpers.get_asset_tools().duplicate_asset('MHC_' + pid, '%s/%s' % (ROOT, pid), pre)
    mhc = unreal.load_asset(dst)
    if mhc is None:
        out.append({'id': pid, 'err': 'duplicate failed'})
        continue
    donor = unreal.load_asset(DONORS[P['body']])
    if not sub.is_object_added_for_editing(mhc):
        sub.try_add_object_to_edit(mhc)
    if not sub.is_object_added_for_editing(donor):
        sub.try_add_object_to_edit(donor)
    sub.set_body_constraints(mhc, sub.get_body_constraints(donor))
    sub.commit_body_state(mhc)
    rp = unreal.MetaHumanCharacterAutoRiggingRequestParams()
    rp.set_editor_property('rig_type', unreal.MetaHumanRigType.JOINTS_ONLY)
    rp.set_editor_property('blocking', True)
    rp.set_editor_property('report_progress', False)
    sub.request_auto_rigging(mhc, rp)
    tp = unreal.MetaHumanCharacterTextureRequestParams()
    tp.set_editor_property('blocking', True)
    tp.set_editor_property('report_progress', False)
    sub.request_texture_sources(mhc, tp)
    row['can_build'] = sub.can_build_meta_human(mhc, True)
    eal.save_asset(dst, only_if_is_dirty=False)
    row['secs'] = round(time.time() - t0, 1)
    out.append(row)
    await asyncio.sleep(0)
RESULT = json.dumps(out)
