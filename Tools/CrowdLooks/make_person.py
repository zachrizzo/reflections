"""Make one Lanthorne NPC MetaHuman from an Epic preset face, on an existing wardrobe body, and build it.

Globals in: PERSON (dict, see people.json), BUILD (bool), QUALITY ('CINEMATIC'|'OPTIMIZED').
The new character lives in /Game/Characters/Lanthorne/People/<Id>/MHC_<Id>; the build unpacks next to it and shares
/Game/Characters/Lanthorne/People/Common. The face keeps the preset's DNA rig; only the body is replaced by the donor
body so the donor's fitted garments fit.
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
eal = unreal.EditorAssetLibrary
sub = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
log = {'id': PERSON['id'], 't': {}}
T0 = time.time()

pid = PERSON['id']
dst = '%s/%s/MHC_%s' % (ROOT, pid, pid)
if not eal.does_asset_exist(dst):
    eal.duplicate_asset('/MetaHumanCharacter/Optional/Presets/' + PERSON['preset'], dst)
mhc = unreal.load_asset(dst)
donor = unreal.load_asset(DONORS[PERSON['body']])
log['t']['dup'] = round(time.time() - T0, 1)
sub.try_add_object_to_edit(mhc)
sub.try_add_object_to_edit(donor)

# Body: the donor's parametric constraints, so the donor's garments fit.
cons = sub.get_body_constraints(donor)
sub.set_body_constraints(mhc, cons)
sub.commit_body_state(mhc)
log['body_same'] = sub.compare_body_state(mhc, donor, 0.5)
log['t']['body'] = round(time.time() - T0, 1)

# Skin tone / texture variation (optional per person).
if 'skin' in PERSON:
    ss = mhc.get_editor_property('skin_settings')
    sk = ss.get_editor_property('skin')
    for k, v in PERSON['skin'].items():
        sk.set_editor_property(k, v)
    ss.set_editor_property('skin', sk)
    sub.commit_skin_settings(mhc, ss)

log['can_build'] = sub.can_build_meta_human(mhc, True)
if BUILD and log['can_build']:
    p = unreal.MetaHumanCharacterEditorBuildParameters()
    p.set_editor_property('pipeline_type', getattr(unreal.MetaHumanDefaultPipelineType, QUALITY if QUALITY in ('CINEMATIC', 'OPTIMIZED') else 'CINEMATIC'))
    if QUALITY == 'OPTIMIZED':
        p.set_editor_property('pipeline_quality', unreal.MetaHumanQualityLevel.MEDIUM)
    p.set_editor_property('common_folder_path', ROOT + '/Common')
    p.set_editor_property('absolute_build_path', '%s/%s/Assembled' % (ROOT, pid))
    sub.build_meta_human(mhc, p)
    log['t']['build'] = round(time.time() - T0, 1)
sub.remove_object_to_edit(donor)
eal.save_asset(dst, only_if_is_dirty=False)
RESULT = json.dumps(log)
