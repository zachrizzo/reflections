"""Re-import hidden-skin bodies IN PLACE (editor Python, no PIE, inside your queue slot).

Use after a re-fit changed only which skin is hidden (2026-11-15: whole feet hidden under boots). Every target asset keeps
its path, so the looks that use it need no rewiring. That covers both the outfit's own Bodies/SKM_<Body>_BodyHidden_<id>
and crowd-looks' walker-named copies in /Game/Characters/Lanthorne/Bodies.

Globals in: TARGETS = [(fbx_rel_path, [asset_path, ...]), ...]
1. Proof: the first FBX is imported with NO skeleton into /Game/Developers/ClothingFitRootTest. Bone 0 must be "root" and
   the bone count must match the first target's skeleton, or nothing is touched. The test folder is deleted.
2. Per target: record skeleton, slot materials, physics/shadow physics asset and post-process ABP; re-import the FBX over
   it (legacy FBX, replace_existing, onto the recorded skeleton); put every recorded property back; save that package
   by path. A target whose bounds before reach above 130 cm (a full body, not a hidden-skin body) is skipped.
3. Skeleton guard: a dirtied metahuman_base_skel is reloaded from disk, never saved. Then skinned-asset compiles are
   finished, so nobody's PIE animates a half-built mesh.
RESULT: per target, bounds z before/after, bone 0, slot check, saved.
"""
import json
import os

import unreal

A = unreal.EditorAssetLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
TEST = '/Game/Developers/ClothingFitRootTest'
CV = 'Interchange.FeatureFlags.Import.FBX'
PROPS = ('physics_asset', 'shadow_physics_asset', 'post_process_anim_blueprint')
RESULT = {'targets': []}


def zrange(mesh):
    b = mesh.get_bounds()
    return [round(b.origin.z - b.box_extent.z, 1), round(b.origin.z + b.box_extent.z, 1)]


def bone_names(skel):
    return [str(n) for n in unreal.AnimPoseExtensions.get_bone_names(skel.get_reference_pose())]


def import_fbx(fbx, dest, name, skeleton, replace):
    s = unreal.FbxImportUI()
    s.automated_import_should_detect_type = False
    s.mesh_type_to_import = unreal.FBXImportType.FBXIT_SKELETAL_MESH
    s.import_as_skeletal = True
    s.import_mesh = True
    s.import_materials = False
    s.import_textures = False
    s.import_animations = False
    s.create_physics_asset = False
    if skeleton is not None:
        s.skeleton = skeleton
    d = s.skeletal_mesh_import_data
    d.normal_import_method = unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
    d.set_editor_property('import_morph_targets', False)
    d.set_editor_property('import_uniform_scale', 1.0)
    d.set_editor_property('convert_scene', True)
    d.set_editor_property('convert_scene_unit', True)
    t = unreal.AssetImportTask()
    t.filename = fbx
    t.destination_path = dest
    t.destination_name = name
    t.automated = True
    t.replace_existing = replace
    t.save = False
    t.options = s
    prev = unreal.SystemLibrary.get_console_variable_bool_value(CV)
    try:
        unreal.SystemLibrary.execute_console_command(None, CV + ' 0')
        TOOLS.import_asset_tasks([t])
    finally:
        unreal.SystemLibrary.execute_console_command(None, CV + (' 1' if prev else ' 0'))
    return unreal.load_asset(dest + '/' + name)


def refresh(fbx, path):
    out = {'asset': path}
    mesh = unreal.load_asset(path)
    if mesh is None:
        out['error'] = 'asset missing'
        return out
    out['z_before'] = zrange(mesh)
    if out['z_before'][1] > 130:
        out['error'] = 'skipped: bounds reach %.0f cm, not a hidden-skin body' % out['z_before'][1]
        return out
    skel = mesh.get_editor_property('skeleton')
    mats = [(str(sl.get_editor_property('material_slot_name')), sl.material_interface) for sl in mesh.get_editor_property('materials')]
    keep = {p: mesh.get_editor_property(p) for p in PROPS}
    dest, name = path.rsplit('/', 1)
    mesh = import_fbx(fbx, dest, name, skel, True)
    if mesh is None:
        out['error'] = 'import failed'
        return out
    slots = mesh.get_editor_property('materials')
    out['slots'] = [len(mats), len(slots)]
    for i in range(min(len(mats), len(slots))):
        sl = slots[i]
        sl.material_interface = mats[i][1]
        slots[i] = sl
    mesh.set_editor_property('materials', slots)
    for p, v in keep.items():
        mesh.set_editor_property(p, v)
    out['skeleton_same'] = mesh.get_editor_property('skeleton') == skel
    out['bone0'] = str(mesh.get_bone_parent('pelvis'))
    out['z_after'] = zrange(mesh)
    out['props_kept'] = all(mesh.get_editor_property(p) == v for p, v in keep.items())
    out['saved'] = unreal.EditorLoadingAndSavingUtils.save_packages([mesh.get_package()], False)
    return out


if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world():
    RESULT = 'PIE running: nothing touched'
else:
    fbx0 = os.path.join(PROJ, TARGETS[0][0])
    tm = import_fbx(fbx0, TEST, 'SK_RootTest', None, True)
    proof, count = None, None
    if tm:
        names = bone_names(tm.get_editor_property('skeleton'))
        proof, count = names[0], len(names)
    A.delete_directory(TEST)
    tcount = len(bone_names(unreal.load_asset(TARGETS[0][1][0]).get_editor_property('skeleton')))
    RESULT['proof'] = [proof, count, tcount]
    if proof != 'root' or count != tcount:
        RESULT['stopped'] = 'proof failed: nothing touched'
    else:
        for rel, paths in TARGETS:
            for p in paths:
                try:
                    RESULT['targets'].append(refresh(os.path.join(PROJ, rel), p))
                except Exception as e:
                    RESULT['targets'].append({'asset': p, 'error': repr(e)})
    dirty = [p for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
             if str(p.get_name()).endswith('metahuman_base_skel')]
    if dirty:
        unreal.EditorLoadingAndSavingUtils.reload_packages(dirty)
    RESULT['reloaded_dirty_skeletons'] = [str(p.get_name()) for p in dirty]
    sk0 = {}
    for _, paths in TARGETS:
        m = unreal.load_asset(paths[0])
        if m:
            sk = m.get_editor_property('skeleton')
            sk0[sk.get_path_name().split('.')[0]] = bone_names(sk)[0]
    RESULT['skeleton_bone0'] = sk0
    unreal.SystemLibrary.execute_console_command(None, 'Editor.AsyncSkinnedAssetCompilationFinishAll')
