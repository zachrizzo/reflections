"""Dress one built Lanthorne person in an existing fitted wardrobe Blueprint.

Globals in: LOOK = {id, person, built_bp, outfit_bp, sex, age, side, role, mats: {component: material path}}
  - built_bp: the BP the MetaHuman build produced (face, grooms, skin source)
  - outfit_bp: a wardrobe Blueprint on the donor body (garments with leader pose on Body)
Result: /Game/Characters/Lanthorne/Looks/BP_Look_<id>. The donor body mesh is kept (its garments, its ABP_Crowd_*
walk), with the new person's body skin material; face, grooms and eyelashes come from the new person.
"""
import json

LOOKS = '/Game/Characters/Lanthorne/Looks'
eal = unreal.EditorAssetLibrary
sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
SDL = unreal.SubobjectDataBlueprintFunctionLibrary
GROOMS = ('Hair', 'Eyebrows', 'Eyelashes', 'Fuzz', 'Mustache', 'Beard')


def templates(bp):
    out = {}
    for h in sds.k2_gather_subobject_data_for_blueprint(bp):
        d = SDL.get_data(h)
        o = SDL.get_object(d)
        if o is not None:
            out.setdefault(str(SDL.get_variable_name(d)), o)
    return out


dst = '%s/BP_Look_%s' % (LOOKS, LOOK['id'])
if eal.does_asset_exist(dst):
    eal.delete_asset(dst)
eal.duplicate_asset(LOOK['outfit_bp'], dst)
bp = unreal.load_asset(dst)
src = unreal.load_asset(LOOK['built_bp'])
T = templates(bp)
S = templates(src)
log = {'id': LOOK['id'], 'set': []}

# Face: the new person's face mesh and its own face anim BP.
T['Face'].set_editor_property('skeletal_mesh_asset', S['Face'].get_editor_property('skeletal_mesh_asset'))
T['Face'].set_editor_property('override_materials', [])
log['set'].append('Face')
# Body: keep the donor mesh (garment fit + crowd walk ABP); wear the new skin.
new_body = S['Body'].get_editor_property('skeletal_mesh_asset')
skin = [m.get_editor_property('material_interface') for m in new_body.get_editor_property('materials')]
T['Body'].set_editor_property('override_materials', skin)
log['skin'] = [m.get_path_name() if m else None for m in skin]
# Grooms, including the ones the donor lacked (eyebrows, eyelashes).
for g in GROOMS:
    if g not in T:
        continue
    s = S.get(g)
    ga = s.get_editor_property('groom_asset') if s else None
    gb = s.get_editor_property('binding_asset') if s else None
    gm = list(s.get_editor_property('override_materials')) if s else []
    T[g].set_editor_property('groom_asset', ga)
    T[g].set_editor_property('binding_asset', gb)
    T[g].set_editor_property('override_materials', gm)
    # The look rides a moving locomotion pawn: tick the groom after everything moved, or hair trails the head
    # (same cause as the hero's hair fix, ArtDirection/Clothing-Fit-Audit/HeroHair-Detach-Fix.md).
    try:
        tf = T[g].get_editor_property('primary_component_tick')
        tf.set_editor_property('tick_group', unreal.TickingGroup.TG_POST_UPDATE_WORK)
        T[g].set_editor_property('primary_component_tick', tf)
    except Exception as e:
        log.setdefault('tick_err', str(e))
    log['set'].append('%s=%s' % (g, ga.get_name() if ga else None))
# Outfit colour per person.
for comp, mat in (LOOK.get('mats') or {}).items():
    if comp in T:
        T[comp].set_editor_property('override_materials', [unreal.load_asset(mat)])
# Tags that travel with the look: voice, age, side, role.
cdo = unreal.get_default_object(bp.generated_class())
tags = [t for t in cdo.get_editor_property('tags') if not str(t).startswith(('NPC_Voice_', 'Look_'))]
tags += ['NPC_Voice_' + LOOK['sex'], 'Look_Age_' + LOOK['age'], 'Look_Side_' + LOOK['side'], 'Look_Role_' + LOOK['role'],
         'Look_Id_' + LOOK['id']]
cdo.set_editor_property('tags', [unreal.Name(t) for t in tags])
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
eal.save_asset(dst, only_if_is_dirty=False)
log['bp'] = dst
log['tags'] = tags
RESULT = json.dumps(log)
