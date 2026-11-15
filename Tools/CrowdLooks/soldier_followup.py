"""Soldier follow-ups (20:05):
1. GiltSoldier_*: hide the built-in round shield (squads give every soldier its own sword and shield).
2. Template for the male Giltside soldier from hero-cloak's fitted outfit: copy Preview/BP_Preview_GiltSoldier_M to
   Looks/Templates/BP_Template_GiltSoldier_M with the rigid helmet hidden (the user: no armour, metal helmets included)
   and the hair shown. make_look.py dresses GiltCorwin / GiltOsric from it once their faces are built.
"""
import json

eal = unreal.EditorAssetLibrary
sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
SDL = unreal.SubobjectDataBlueprintFunctionLibrary
out = {}


def templates(bp):
    t = {}
    for h in sds.k2_gather_subobject_data_for_blueprint(bp):
        d = SDL.get_data(h)
        o = SDL.get_object(d)
        if o is not None:
            t.setdefault(str(SDL.get_variable_name(d)), o)
    return t


def hide(o):
    o.set_editor_property('skeletal_mesh_asset', None)
    o.set_editor_property('visible', False)
    o.set_editor_property('hidden_in_game', True)


for name in ('GiltSoldier_BridgeGuard', 'GiltSoldier_Rowena'):
    p = '/Game/Characters/Lanthorne/Looks/Soldiers/' + name
    bp = unreal.load_asset(p)
    T = templates(bp)
    hidden = [n for n in T if 'shield' in n.lower()]
    for n in hidden:
        hide(T[n])
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    eal.save_asset(p, only_if_is_dirty=False)
    out[name] = hidden

src = '/Game/Characters/Lanthorne/Clothing/Giltside/MedievalSoldier/Preview/BP_Preview_GiltSoldier_M'
dst = '/Game/Characters/Lanthorne/Looks/Templates/BP_Template_GiltSoldier_M'
if eal.does_asset_exist(src):
    if eal.does_asset_exist(dst):
        eal.delete_asset(dst)
    eal.duplicate_asset(src, dst)
    bp = unreal.load_asset(dst)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    T = templates(bp)
    helm = []
    for n, o in T.items():
        if isinstance(o, unreal.SkeletalMeshComponent):
            m = o.get_editor_property('skeletal_mesh_asset')
            if m and 'helmet' in m.get_name().lower():
                hide(o)
                helm.append(n)
    if 'Hair' in T:
        T['Hair'].set_editor_property('visible', True)
        T['Hair'].set_editor_property('hidden_in_game', False)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    eal.save_asset(dst, only_if_is_dirty=False)
    out['template'] = {'path': dst, 'helmet_hidden_on': helm}
else:
    out['template'] = 'preview missing: ' + src
RESULT = json.dumps(out)
