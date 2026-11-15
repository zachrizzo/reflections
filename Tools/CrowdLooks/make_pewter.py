"""Pewterside looks (orchestrator, 19:15): grey-palette variants of the finished Giltside outfits, material changes only.
No rags (Frostside), no red (Giltside), nothing new or baggy.

For each Giltside look BP_Look_Gilt<X>: copy to /Game/Characters/Lanthorne/Looks/Pewterside/PewLook_<X>, and put a
"Pewter" tint (slate grey, MI_Crowd_<Char>_Pewter, a child of the outfit's own M_CrowdTint_<Char>) on every slot that
wears the outfit's tinted fabric (its original material or any MI_Crowd_<Char>_* palette). Tags: Look_Side_Pewterside,
Look_Id_Pew<X>; the rest are kept. Same faces as Giltside: the city is mirrored, and SpawnNpc never mixes sides.
Global DRY_RUN (default True), IDS (optional subset).
"""
import json

LOOKS = '/Game/Characters/Lanthorne/Looks'
DST = LOOKS + '/Pewterside'
MATS = '/Game/Characters/RedLondon/Crowd/Materials'
PEWTER = unreal.LinearColor(0.30, 0.32, 0.35, 1.0)
eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
SDL = unreal.SubobjectDataBlueprintFunctionLibrary
variants = json.load(open(PROJECT + 'ArtDirection/Three-Londons-Wardrobe/CrowdLooks/variants.json'))['variants']
ORIGINAL = {}
for v in variants:
    ORIGINAL.setdefault(v['base_identity'], v['original_material'].split('.')[0])
cast = [L for L in json.load(open(PROJECT + 'Tools/CrowdLooks/cast.json'))['looks'] if L['side'] == 'Giltside']
if globals().get('IDS'):
    cast = [L for L in cast if L['id'] in IDS]


def templates(bp):
    out = {}
    for h in sds.k2_gather_subobject_data_for_blueprint(bp):
        d = SDL.get_data(h)
        o = SDL.get_object(d)
        if o is not None:
            out.setdefault(str(SDL.get_variable_name(d)), o)
    return out


def pewter_mi(char):
    path = '%s/MI_Crowd_%s_Pewter' % (MATS, char)
    if not eal.does_asset_exist(path):
        if globals().get('DRY_RUN', True):
            return path
        src = '%s/MI_Crowd_%s_Ash' % (MATS, char)
        eal.duplicate_asset(src, path)
        mi = unreal.load_asset(path)
        mel.set_material_instance_vector_parameter_value(mi, 'CrowdTint', PEWTER)
        eal.save_asset(path, only_if_is_dirty=False)
    return path


report = {}
for L in cast:
    lid = L['id']
    src = '%s/BP_Look_%s' % (LOOKS, lid)
    bp_src = unreal.load_asset(src)
    if bp_src is None:
        report[lid] = 'no source look'
        continue
    pid = lid.replace('Gilt', '', 1)
    dst = '%s/PewLook_%s' % (DST, pid)
    T = templates(bp_src)
    body = T['Body'].get_editor_property('skeletal_mesh_asset').get_name()  # SKM_MHC_<Char>_BodyMesh
    char = body.replace('SKM_MHC_', '').replace('_BodyMesh', '')
    targets = []
    for name, o in T.items():
        if not isinstance(o, unreal.SkeletalMeshComponent) or name in ('Body', 'Face'):
            continue
        mesh = o.get_editor_property('skeletal_mesh_asset')
        if mesh is None:
            continue
        slots = [m.get_editor_property('material_interface') for m in mesh.get_editor_property('materials')]
        over = list(o.get_editor_property('override_materials'))
        for i, base in enumerate(slots):
            cur = over[i] if i < len(over) and over[i] else base
            p = cur.get_path_name().split('.')[0] if cur else ''
            if p == ORIGINAL.get(char) or p.startswith('%s/MI_Crowd_%s_' % (MATS, char)):
                targets.append((name, i))
    report[lid] = {'to': dst, 'char': char, 'tinted_slots': targets}
    if globals().get('DRY_RUN', True):
        continue
    mi = unreal.load_asset(pewter_mi(char))
    if eal.does_asset_exist(dst):
        eal.delete_asset(dst)
    eal.duplicate_asset(src, dst)
    bp = unreal.load_asset(dst)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    T2 = templates(bp)
    missing = [n for n, _ in targets if n not in T2]
    if missing:
        report[lid]['err'] = 'components not found after copy: %s (have %s)' % (missing, sorted(T2)[:12])
        continue
    for name, i in targets:
        o = T2[name]
        n = len(o.get_editor_property('skeletal_mesh_asset').get_editor_property('materials'))
        over = list(o.get_editor_property('override_materials'))
        over += [None] * (n - len(over))
        over[i] = mi
        o.set_editor_property('override_materials', over)
    cdo = unreal.get_default_object(bp.generated_class())
    tags = [str(t) for t in cdo.get_editor_property('tags') if not str(t).startswith(('Look_Side_', 'Look_Id_'))]
    tags += ['Look_Side_Pewterside', 'Look_Id_Pew' + pid]
    cdo.set_editor_property('tags', [unreal.Name(t) for t in tags])
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    eal.save_asset(dst, only_if_is_dirty=False)
RESULT = json.dumps(report, indent=0)
