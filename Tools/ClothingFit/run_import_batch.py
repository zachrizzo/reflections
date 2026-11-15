"""Import a batch of fitted outfits into UE, safely (editor Python, no PIE, inside your queue slot).

Globals in: OUTFITS = [(fit_id, body_mesh_path, dest_folder), ...]
1. Proof: the first outfit's first FBX is imported with NO skeleton into /Game/Developers/ClothingFitRootTest. Its new
   throwaway skeleton's bone 0 must be "root" (the armature was exported as "Armature"). If not, stop: nothing else
   is imported. The throwaway assets are deleted either way.
2. Every piece and the hidden-skin body of each outfit is imported with import_fitted_garments.py (which ends with the
   skeleton guard: dirtied metahuman_base_skel packages are reloaded from disk, never saved).
3. RESULT: per asset, its bone 0 (must be "root"), plus the guard report.
"""
import json
import os

import unreal

A = unreal.EditorAssetLibrary
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
OUT = 'Intermediate/ClothingFit2026_11_14/Out/'
TEST = '/Game/Developers/ClothingFitRootTest'
RESULT = {}


def bone0_of_mesh(path):
    m = unreal.load_asset(path)
    if m is None:
        return None
    return str(m.get_bone_parent('pelvis'))


if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world():
    RESULT = 'PIE running: nothing imported'
else:
    first_id = OUTFITS[0][0]
    rep0 = json.load(open(os.path.join(PROJ, OUT + first_id + '/' + first_id + '_report.json')))
    first_fbx = os.path.join(PROJ, rep0['fbx'][0]) if not os.path.isabs(rep0['fbx'][0]) else rep0['fbx'][0]
    s = unreal.FbxImportUI()
    s.automated_import_should_detect_type = False
    s.mesh_type_to_import = unreal.FBXImportType.FBXIT_SKELETAL_MESH
    s.import_as_skeletal = True
    s.import_mesh = True
    s.import_materials = False
    s.import_textures = False
    s.import_animations = False
    s.create_physics_asset = False
    s.skeletal_mesh_import_data.set_editor_property('convert_scene', True)
    t = unreal.AssetImportTask()
    t.filename = first_fbx
    t.destination_path = TEST
    t.destination_name = 'SK_RootTest'
    t.automated = True
    t.replace_existing = True
    t.save = False
    t.options = s
    cv = 'Interchange.FeatureFlags.Import.FBX'
    prev = unreal.SystemLibrary.get_console_variable_bool_value(cv)
    try:
        unreal.SystemLibrary.execute_console_command(None, cv + ' 0')
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t])
    finally:
        unreal.SystemLibrary.execute_console_command(None, cv + (' 1' if prev else ' 0'))
    tm = unreal.load_asset(TEST + '/SK_RootTest')
    proof, count = None, None
    if tm:
        tsk = tm.get_editor_property('skeleton')
        tnames = [str(n) for n in unreal.AnimPoseExtensions.get_bone_names(tsk.get_reference_pose())]
        proof, count = tnames[0], len(tnames)
    A.delete_directory(TEST)
    target = unreal.load_asset(OUTFITS[0][1]).get_editor_property('skeleton')
    tcount = len(unreal.AnimPoseExtensions.get_bone_names(target.get_reference_pose()))
    RESULT['proof_bone0'] = proof
    RESULT['proof_bones'] = [count, tcount]
    if proof != 'root' or count != tcount:
        RESULT['stopped'] = 'throwaway skeleton bone 0 %r with %s bones (target "root", %s): nothing imported' % (proof, count, tcount)
    else:
        src = open(os.path.join(PROJ, 'Tools/ClothingFit/import_fitted_garments.py'), encoding='utf-8').read()
        RESULT['outfits'] = {}
        for oid, body, dest in OUTFITS:
            rep = json.load(open(os.path.join(PROJ, OUT + oid + '/' + oid + '_report.json')))
            items = [{'fbx': OUT + oid + '/' + n + '.fbx', 'dest': dest, 'body': body, 'slot_info': p.get('slots') or {}}
                     for n, p in rep['pieces'].items() if p.get('kind') != 'helmet']
            items.append({'fbx': OUT + oid + '/' + rep['body_hide']['name'] + '.fbx', 'dest': dest + '/Bodies',
                          'body': body, 'body_copy': True})
            g = {'unreal': unreal, 'ITEMS': items, 'REPLACE': False, '__name__': 'import_fitted'}
            exec(compile(src, 'import_fitted_garments.py', 'exec'), g)
            RESULT['outfits'][oid] = {
                'assets': [{'asset': (i.get('asset') or '').rsplit('/', 1)[-1], 'pelvis_parent': bone0_of_mesh(i['asset']) if i.get('asset') else None,
                            'saved': i.get('saved'), 'err': i.get('error')} for i in g['RESULT']['items']],
                'guard': g['RESULT'].get('skeleton_guard')}
