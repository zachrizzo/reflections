import json
eal = unreal.EditorAssetLibrary
sub = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
out = {}
pre = unreal.load_asset('/MetaHumanCharacter/Optional/Presets/Vivian')
out['preset_valid_edit'] = sub.try_add_object_to_edit(pre)
try:
    out['preset_is_valid'] = pre.call_method('IsCharacterValid')
except Exception as e:
    out['isvalid_err'] = str(e)[:120]
sub.remove_object_to_edit(pre)
w = unreal.load_asset('/Game/Characters/Lanthorne/People/TestWalter/MHC_TestWalter')
r = unreal.load_asset('/Game/Characters/Lanthorne/People/GiltRowena/MHC_GiltRowena')
for k, a in (('walter', w), ('rowena', r)):
    out[k] = {}
    for p in ('internal_collection', 'face_evaluation_settings', 'skin_settings'):
        try:
            out[k][p] = str(a.get_editor_property(p))[:80]
        except Exception as e:
            out[k][p] = 'ERR'
import os
for k, path in (('walter', 'TestWalter/MHC_TestWalter'), ('rowena', 'GiltRowena/MHC_GiltRowena'), ('ada', 'TestAda/MHC_TestAda')):
    f = unreal.Paths.project_content_dir() + 'Characters/Lanthorne/People/' + path + '.uasset'
    out[k + '_bytes'] = os.path.getsize(f) if os.path.exists(f) else None
pf = unreal.Paths.engine_plugins_dir() + 'MetaHuman/MetaHumanCharacter/Content/Optional/Presets/Vivian.uasset'
out['vivian_src_bytes'] = os.path.getsize(pf) if os.path.exists(pf) else pf
RESULT = json.dumps(out)
