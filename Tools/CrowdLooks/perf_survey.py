"""READ-ONLY survey for crowd plan rank 7 (no saves). Run with top-level await.
Per look BP (Looks, Looks/Pewterside, Looks/Soldiers): Body mesh + its skeleton, Body bone 0, LODSync present/min LOD,
empty groom components, non-Body/Face skeletal parts not on OnlyTickPoseWhenRendered. Also lists dirty packages."""
import json

eal = unreal.EditorAssetLibrary
sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
SDL = unreal.SubobjectDataBlueprintFunctionLibrary
DIRS = ['/Game/Characters/Lanthorne/Looks', '/Game/Characters/Lanthorne/Looks/Pewterside',
        '/Game/Characters/Lanthorne/Looks/Soldiers']
OTP = unreal.VisibilityBasedAnimTickOption.ONLY_TICK_POSE_WHEN_RENDERED


async def bone0(path):
    if '.' not in path.split('/')[-1]:
        path = path + '.' + path.split('/')[-1]  # the tool wants the object path
    r = await call_tool('EditorToolset.SkeletalMeshToolset.GetBoneNames', mesh={'refPath': path})
    bones = r.get('returnValue', r) if isinstance(r, dict) else r
    return bones[0] if bones else None


looks = []
for d in DIRS:
    for p in eal.list_assets(d, recursive=False):
        path = p.split('.')[0]
        if path.split('/')[-1].startswith(('BP_Look_', 'PewLook_', 'GiltSoldier_', 'FrostSoldier_')):
            looks.append(path)
out = {}
b0cache = {}
for path in sorted(looks):
    bp = unreal.load_asset(path)
    row = {'lodsync': None, 'empty_grooms': [], 'not_otp': [], 'parts': 0}
    seen = set()
    for h in sds.k2_gather_subobject_data_for_blueprint(bp):
        d = SDL.get_data(h)
        o = SDL.get_object(d)
        n = str(SDL.get_variable_name(d))
        if o is None or n in seen:
            continue
        seen.add(n)
        cls = o.get_class().get_name()
        if cls == 'LODSyncComponent':
            row['lodsync'] = {'min_lod': o.get_editor_property('min_lod'),
                              'forced_lod': o.get_editor_property('forced_lod')}
        elif cls == 'GroomComponent' and o.get_editor_property('groom_asset') is None:
            row['empty_grooms'].append(n)
        elif isinstance(o, unreal.SkeletalMeshComponent):
            m = o.get_editor_property('skeletal_mesh_asset')
            if n == 'Body':
                row['body'] = m.get_path_name().split('.')[0] if m else None
                row['skel'] = m.get_editor_property('skeleton').get_path_name().split('.')[0] if m else None
            elif n != 'Face' and m is not None:
                row['parts'] += 1
                if o.get_editor_property('visibility_based_anim_tick_option') != OTP:
                    row['not_otp'].append(n)
    b = row.get('body')
    if b:
        if b not in b0cache:
            b0cache[b] = await bone0(b)
        row['body_bone0'] = b0cache[b]
    out[path.split('/')[-1]] = row
dirty = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
RESULT = json.dumps({'n': len(out), 'looks': out, 'dirty': dirty})
