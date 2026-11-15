"""Crowd plan rank 7 (orchestrator, 22:10): LODSync on the look Blueprints. Run with top-level await.

Survey 22:15: 32 of 38 looks had LODSync ForcedLOD = 0, which pins Body, Face and clothes to LOD 0 at EVERY distance
(LODSyncComponent.cpp: ForcedLOD >= 0 wins over the screen-size choice; MinLOD only clamps the automatic choice).
Fix per look: ForcedLOD -1 (automatic) and MinLOD = MIN_LOD (default 1).
Safety: saves ONLY the look's own package. Body bone 0 must be 'root' before and after. Any other package the
compile dirties is reported; shared skeletons are reloaded from disk (skel_guard) and that look is NOT saved.
Measure: summed vertex count of the look's skeletal parts at LOD 0 and LOD MIN_LOD.
Globals: LOOKS (list of package paths; default all), MIN_LOD, DRY_RUN (default False), OUT_JSON (optional path).
"""
import json

eal = unreal.EditorAssetLibrary
sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
SDL = unreal.SubobjectDataBlueprintFunctionLibrary
skm_sub = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
DIRS = ['/Game/Characters/Lanthorne/Looks', '/Game/Characters/Lanthorne/Looks/Pewterside',
        '/Game/Characters/Lanthorne/Looks/Soldiers']
MIN = globals().get('MIN_LOD', 1)
exec(open(PROJECT + 'Tools/CrowdLooks/skel_guard.py', encoding='utf-8').read(), globals())


async def bone0(path):
    if '.' not in path.split('/')[-1]:
        path = path + '.' + path.split('/')[-1]
    r = await call_tool('EditorToolset.SkeletalMeshToolset.GetBoneNames', mesh={'refPath': path})
    bones = r.get('returnValue', r) if isinstance(r, dict) else r
    return bones[0] if bones else None


def verts(mesh, lod):
    try:
        n = mesh.get_num_lods() if hasattr(mesh, 'get_num_lods') else skm_sub.get_lod_count(mesh)
        return skm_sub.get_num_verts(mesh, min(lod, n - 1))
    except Exception:
        return 0


def dirty_set():
    return set(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())


looks = globals().get('LOOKS')
if not looks:
    looks = []
    for d in DIRS:
        for p in eal.list_assets(d, recursive=False):
            path = p.split('.')[0]
            if path.split('/')[-1].startswith(('BP_Look_', 'PewLook_', 'GiltSoldier_', 'FrostSoldier_')):
                looks.append(path)
report = {}
for path in sorted(looks):
    name = path.split('/')[-1]
    row = {}
    before = dirty_set()
    bp = unreal.load_asset(path)
    lodsync, body, v0, v1 = None, None, 0, 0
    seen = set()
    for h in sds.k2_gather_subobject_data_for_blueprint(bp):
        d = SDL.get_data(h)
        o = SDL.get_object(d)
        n = str(SDL.get_variable_name(d))
        if o is None or n in seen:
            continue
        seen.add(n)
        if o.get_class().get_name() == 'LODSyncComponent':
            lodsync = o
        elif isinstance(o, unreal.SkeletalMeshComponent):
            m = o.get_editor_property('skeletal_mesh_asset')
            if m is None or not o.get_editor_property('visible'):
                continue
            if n == 'Body':
                body = m.get_path_name().split('.')[0]
            v0 += verts(m, 0)
            v1 += verts(m, MIN)
    row['verts_lod0'], row['verts_lod%d' % MIN] = v0, v1
    if lodsync is None or body is None:
        report[name] = dict(row, skipped='no LODSync or Body')
        continue
    row['was'] = {'forced': lodsync.get_editor_property('forced_lod'), 'min': lodsync.get_editor_property('min_lod')}
    row['bone0_before'] = await bone0(body)
    if row['bone0_before'] != 'root':
        report[name] = dict(row, skipped='Body bone 0 not root')
        continue
    if globals().get('DRY_RUN', False):
        report[name] = dict(row, dry_run=True)
        continue
    lodsync.set_editor_property('forced_lod', -1)
    lodsync.set_editor_property('min_lod', MIN)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    extra = sorted(p for p in dirty_set() - before if p != path)
    if extra:
        row['extra_dirty'] = extra
        row['skel_reloaded'] = skel_guard()
        if any('/Common/' in p or 'skel' in p.lower() for p in extra):
            # The fix would touch a shared Common asset: leave this look unsaved and reload it from disk.
            unreal.EditorLoadingAndSavingUtils.reload_packages(
                [bp.get_outermost()], unreal.ReloadPackagesInteractionMode.ASSUME_POSITIVE)
            report[name] = dict(row, skipped='compile dirtied a shared Common asset; look reloaded, not saved')
            continue
    eal.save_asset(path, only_if_is_dirty=False)
    row['bone0_after'] = await bone0(body)
    row['now'] = {'forced': -1, 'min': MIN}
    report[name] = row
report['_dirty_after'] = sorted(dirty_set())
RESULT = json.dumps(report)
if globals().get('OUT_JSON'):
    open(OUT_JSON, 'w', encoding='utf-8').write(RESULT)
