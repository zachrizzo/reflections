"""Whole pipeline for new people: create (make_people) -> build (Optimized/Medium, shared Common) -> save -> dress
(make_look). Globals: IDS. Progress: Saved/CrowdLooks/pipeline.json. Yields 15 s between people for other sessions."""
import json
import time

ROOT = '/Game/Characters/Lanthorne/People'
TOOLS = PROJECT + 'Tools/CrowdLooks/'
PROGRESS = PROJECT + 'Saved/CrowdLooks/pipeline.json'
cast = {L['id']: L for L in json.load(open(TOOLS + 'cast.json'))['looks']}
eal = unreal.EditorAssetLibrary
sub = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
ar = unreal.AssetRegistryHelpers.get_asset_registry()
try:
    progress = json.load(open(PROGRESS))
except Exception:
    progress = {}


def run(script, **kw):
    g = {'unreal': unreal, 'call_tool': call_tool, 'asyncio': asyncio, '__name__': 'crowdlooks', 'PROJECT': PROJECT}
    g.update(kw)
    exec(compile(open(TOOLS + script, encoding='utf-8').read(), TOOLS + script, 'exec'), g)
    return json.loads(g['RESULT'])


def save_progress():
    with open(PROGRESS, 'w') as f:
        json.dump(progress, f, indent=1)


for pid in IDS:
    row = progress.setdefault(pid, {})
    t0 = time.time()
    try:
        mhc_path = '%s/%s/MHC_%s' % (ROOT, pid, pid)
        built_bp = '%s/%s/Built/MHC_%s/BP_MHC_%s' % (ROOT, pid, pid, pid)
        built_face = '%s/%s/Built/MHC_%s/Face/SKM_MHC_%s_FaceMesh' % (ROOT, pid, pid, pid)
        mhc = unreal.load_asset(mhc_path)
        if mhc is not None and not sub.is_object_added_for_editing(mhc):
            sub.try_add_object_to_edit(mhc)
        if mhc is None or not sub.can_build_meta_human(mhc, False):
            row['make'] = await_result = None
            # make_people is async (awaits between people); run its body synchronously for one id
            g = {'unreal': unreal, 'call_tool': call_tool, 'asyncio': asyncio, '__name__': 'crowdlooks', 'PROJECT': PROJECT, 'IDS': [pid]}
            import ast
            code = compile(open(TOOLS + 'make_people.py', encoding='utf-8').read(), TOOLS + 'make_people.py', 'exec', flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
            r = eval(code, g)
            if r is not None:
                await r
            row['make'] = json.loads(g['RESULT'])
            mhc = unreal.load_asset(mhc_path)
        save_progress()
        await asyncio.sleep(2)
        if not eal.does_asset_exist(built_face):
            if eal.does_directory_exist('%s/%s/Built' % (ROOT, pid)):
                eal.delete_directory('%s/%s/Built' % (ROOT, pid))  # leftovers of a failed build
            # The build imports the face through Interchange, which refuses while any PIE world exists:
            # hold the PIE lock (nobody starts PIE) and wait out a running PIE.
            await acquire_pie_lock('crowd-looks: MetaHuman build of %s (no PIE please, ~2 min)' % pid, 200)
            for _ in range(120):
                if not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world():
                    break
                await asyncio.sleep(2)
            p = unreal.MetaHumanCharacterEditorBuildParameters()
            p.set_editor_property('pipeline_type', unreal.MetaHumanDefaultPipelineType.OPTIMIZED)
            p.set_editor_property('pipeline_quality', unreal.MetaHumanQualityLevel.MEDIUM)
            p.set_editor_property('common_folder_path', ROOT + '/Common')
            p.set_editor_property('absolute_build_path', '%s/%s/Built' % (ROOT, pid))
            try:
                sub.build_meta_human(mhc, p)
            finally:
                release_pie_lock()
            row['built'] = eal.does_asset_exist(built_face)
            if not row['built']:
                raise RuntimeError('build failed (see LogMetaHumanCharacterEditor)')
            for a in ar.get_assets_by_path('%s/%s/Built' % (ROOT, pid), recursive=True):
                eal.save_asset(str(a.package_name), only_if_is_dirty=True)
            save_progress()
            await asyncio.sleep(5)
        L = dict(cast[pid])
        L['built_bp'] = built_bp
        row['look'] = run('make_look.py', LOOK=L)
        row['secs'] = round(time.time() - t0, 1)
        row['ok'] = True
    except Exception as e:
        row['err'] = str(e)[:300]
    save_progress()
    await asyncio.sleep(15)
RESULT = json.dumps({k: {'ok': v.get('ok'), 'err': v.get('err'), 'secs': v.get('secs')} for k, v in progress.items() if k in IDS})
