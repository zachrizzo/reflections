"""One new person end to end, synchronously (async scripts stop when the MCP call times out).
Global PID. The caller holds the PIE lock (lock.sh) because the build's Interchange import fails during PIE.
create (preset -> donor body -> cloud rig -> cloud textures) -> build Optimized/Medium -> save -> dress (make_look).
Progress: Saved/CrowdLooks/pipeline.json
"""
import ast
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
row = progress[PID] = {}
t0 = time.time()


def run(script, **kw):
    g = {'unreal': unreal, '__name__': 'crowdlooks', 'PROJECT': PROJECT}
    g.update(kw)
    exec(compile(open(TOOLS + script, encoding='utf-8').read(), TOOLS + script, 'exec'), g)
    return json.loads(g['RESULT'])


try:
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world():
        raise RuntimeError('PIE is running; retry later')
    mhc_path = '%s/%s/MHC_%s' % (ROOT, PID, PID)
    built_bp = '%s/%s/Built/MHC_%s/BP_MHC_%s' % (ROOT, PID, PID, PID)
    built_face = '%s/%s/Built/MHC_%s/Face/SKM_MHC_%s_FaceMesh' % (ROOT, PID, PID, PID)
    mhc = unreal.load_asset(mhc_path)
    if mhc is not None and not sub.is_object_added_for_editing(mhc):
        sub.try_add_object_to_edit(mhc)
    if mhc is None or not sub.can_build_meta_human(mhc, False):
        # make_people.py without its await (one id)
        src = open(TOOLS + 'make_people.py', encoding='utf-8').read().replace('    await asyncio.sleep(0)\n', '')
        g = {'unreal': unreal, '__name__': 'crowdlooks', 'PROJECT': PROJECT, 'IDS': [PID]}
        exec(compile(src, TOOLS + 'make_people.py', 'exec'), g)
        row['make'] = json.loads(g['RESULT'])
        mhc = unreal.load_asset(mhc_path)
    row['t_make'] = round(time.time() - t0, 1)
    if not eal.does_asset_exist(built_face):
        if eal.does_directory_exist('%s/%s/Built' % (ROOT, PID)):
            eal.delete_directory('%s/%s/Built' % (ROOT, PID))
        p = unreal.MetaHumanCharacterEditorBuildParameters()
        p.set_editor_property('pipeline_type', unreal.MetaHumanDefaultPipelineType.OPTIMIZED)
        p.set_editor_property('pipeline_quality', getattr(unreal.MetaHumanQualityLevel, globals().get('QUALITY', 'MEDIUM')))
        p.set_editor_property('common_folder_path', ROOT + '/Common')
        p.set_editor_property('absolute_build_path', '%s/%s/Built' % (ROOT, PID))
        sub.build_meta_human(mhc, p)
        if not eal.does_asset_exist(built_face):
            raise RuntimeError('build failed (see LogMetaHumanCharacterEditor)')
        # Save the person AND the shared Common folder: the build copies each groom's textures and card meshes into
        # Common, and unsaved Common copies are lost on the next editor restart (bald "helmet" hair).
        for folder in ('%s/%s' % (ROOT, PID), ROOT + '/Common'):
            for a in ar.get_assets_by_path(folder, recursive=True):
                eal.save_asset(str(a.package_name), only_if_is_dirty=True)
    row['t_build'] = round(time.time() - t0, 1)
    L = dict(cast[PID])
    L['built_bp'] = built_bp
    row['look'] = run('make_look.py', LOOK=L)
    row['ok'] = True
except Exception as e:
    row['err'] = str(e)[:300]
row['secs'] = round(time.time() - t0, 1)
with open(PROGRESS, 'w') as f:
    json.dump(progress, f, indent=1)
RESULT = json.dumps(row)
