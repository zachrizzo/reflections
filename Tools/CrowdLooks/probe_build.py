import json
sub = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
out = {}
mhc = unreal.load_asset('/Game/Characters/RedLondon/CoinClerk/MHC_CoinClerk')
out['props'] = {}
for p in ['template_type', 'skin_settings', 'eyes_settings', 'head_model_settings', 'makeup_settings', 'has_face_dna', 'has_body_dna',
          'internal_collection', 'body_constraints']:
    try:
        v = mhc.get_editor_property(p)
        out['props'][p] = str(v)[:300]
    except Exception as e:
        out['props'][p] = 'ERR ' + str(e)[:80]
out['bp'] = str(unreal.MetaHumanCharacterEditorBuildParameters())[:600]
try:
    out['bp_doc'] = unreal.MetaHumanCharacterEditorBuildParameters.__doc__[:1500]
except Exception as e:
    out['bp_doc'] = str(e)
out['added'] = sub.try_add_object_to_edit(mhc)
out['can_build'] = sub.can_build_meta_human(mhc, True)
out['coeffs'] = len(sub.get_face_model_coefficients(mhc))
sub.remove_object_to_edit(mhc)
RESULT = json.dumps(out, indent=0)
