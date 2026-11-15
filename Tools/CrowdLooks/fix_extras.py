"""Per-look finishing touches found in the after lineup (14 Nov, 18:25).

- FrostSilas: the White London cloth cap is fitted to Iven Rook's head and sits as a band on Silas's larger head, with
  his hair hidden under it. Hide the cap, show the hair.
- FrostHyeon: her preset had no hair groom (bald). Give her Priya's built low ponytail with a silver-grey colouring
  (new material instances), bound to her face.
"""
import json

eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
SDL = unreal.SubobjectDataBlueprintFunctionLibrary
LOOKS = '/Game/Characters/Lanthorne/Looks'
GROOM_DIR = '/Game/Characters/Lanthorne/Grooms'
ref_binding = unreal.load_asset('/Game/Characters/Lanthorne/People/GiltRowena/Built/MHC_GiltRowena/Grooms/Eyebrows_M_SlightArch_Binding')
SOURCE_HEAD = ref_binding.get_editor_property('source_skeletal_mesh')


def templates(bp):
    out = {}
    for h in sds.k2_gather_subobject_data_for_blueprint(bp):
        d = SDL.get_data(h)
        o = SDL.get_object(d)
        if o is not None:
            out.setdefault(str(SDL.get_variable_name(d)), o)
    return out


def finish(path, bp):
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    eal.save_asset(path, only_if_is_dirty=False)


log = {}
# Silas
p = LOOKS + '/BP_Look_FrostSilas'
bp = unreal.load_asset(p)
T = templates(bp)
for name, o in T.items():
    if 'Cap' in name:
        o.set_editor_property('visible', False)
        o.set_editor_property('hidden_in_game', True)
T['Hair'].set_editor_property('visible', True)
T['Hair'].set_editor_property('hidden_in_game', False)
finish(p, bp)
log['FrostSilas'] = 'cap hidden, hair shown'

# Hyeon
p = LOOKS + '/BP_Look_FrostHyeon'
bp = unreal.load_asset(p)
T = templates(bp)
S = templates(unreal.load_asset('/Game/Characters/Lanthorne/People/GiltPriya/Built/MHC_GiltPriya/BP_MHC_GiltPriya'))
groom = S['Hair'].get_editor_property('groom_asset')
face = T['Face'].get_editor_property('skeletal_mesh_asset')
mats = []
for mi in S['Hair'].get_editor_property('override_materials'):
    dst = '%s/FrostHyeon/%s_Silver' % (GROOM_DIR, mi.get_name())
    if not eal.does_asset_exist(dst):
        eal.duplicate_asset(mi.get_path_name(), dst)
    m = unreal.load_asset(dst)
    mel.set_material_instance_scalar_parameter_value(m, 'hairMelanin', 0.45)
    mel.set_material_instance_scalar_parameter_value(m, 'WhiteAmount', 0.82)
    eal.save_asset(dst, only_if_is_dirty=False)
    mats.append(m)
bpath = '%s/FrostHyeon/%s_Binding' % (GROOM_DIR, groom.get_name())
binding = unreal.load_asset(bpath) if eal.does_asset_exist(bpath) else \
    unreal.GroomLibrary.create_new_groom_binding_asset_with_path(bpath, groom, face, 100, SOURCE_HEAD, 0)
eal.save_asset(bpath, only_if_is_dirty=False)
T['Hair'].set_editor_property('groom_asset', groom)
T['Hair'].set_editor_property('binding_asset', binding)
T['Hair'].set_editor_property('override_materials', mats)
T['Hair'].set_editor_property('visible', True)
T['Hair'].set_editor_property('hidden_in_game', False)
finish(p, bp)
log['FrostHyeon'] = 'silver low ponytail'
RESULT = json.dumps(log)
