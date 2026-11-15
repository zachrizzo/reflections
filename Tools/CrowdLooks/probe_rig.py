import json
eal = unreal.EditorAssetLibrary
sub = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
out = {}
dst = '/Game/Characters/Lanthorne/People/TestAda/MHC_TestAda'
if not eal.does_asset_exist(dst):
    eal.duplicate_asset('/MetaHumanCharacter/Optional/Presets/Ada', dst)
ada = unreal.load_asset(dst)
sub.try_add_object_to_edit(ada)
out['ada_can_build'] = sub.can_build_meta_human(ada, True)
w = unreal.load_asset('/Game/Characters/Lanthorne/People/TestWalter/MHC_TestWalter')
sub.try_add_object_to_edit(w)
p = unreal.MetaHumanCharacterAutoRiggingRequestParams()
out['rig_params'] = str(p)
try:
    p.set_editor_property('rig_type', unreal.MetaHumanRigType.JOINTS_ONLY)
except Exception as e:
    out['rig_type_err'] = str(e)
try:
    sub.request_auto_rigging(w, p)
    out['rig_requested'] = True
except Exception as e:
    out['rig_err'] = str(e)
RESULT = json.dumps(out)
