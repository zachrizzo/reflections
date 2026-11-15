"""Creates only the melee strike clip the NPC archetypes look for: /Game/Characters/CrowdMotion/Combat/AS_GuardPunch
(plus the retargeter it is made with). This is the animation half of Tools/NpcCombat/setup_enemy.py; it places no
actor, adds no nav volume and never touches or saves a level.

Run in the editor's Python, not during PIE and not during a SAVE FREEZE:
    exec(open(r'<project>/Tools/NpcUnified/create_guard_punch_clip.py').read())
"""

import unreal

DEST = '/Game/Characters/CrowdMotion/Combat'
EA = unreal.EditorAssetLibrary


def _loaded(path):
    value = EA.load_asset(path)
    if not value:
        raise RuntimeError('Missing asset: ' + path)
    return value


def create_guard_punch_clip():
    clip_path = DEST + '/AS_GuardPunch'
    if EA.does_asset_exist(clip_path):
        return clip_path + ' (already there)'
    if not EA.does_directory_exist(DEST):
        EA.make_directory(DEST)
    target_mesh = _loaded('/Game/Characters/RedLondon/BridgeGuard/Assembled/BridgeGuard/Body/SKM_MHC_BridgeGuard_BodyMesh')
    source_mesh = _loaded('/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple')
    source_anim = _loaded('/Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_Attack_01')
    target_rig = _loaded('/Game/Characters/CrowdMotion/IK_Crowd_BridgeGuard')
    retarget_path = DEST + '/RTG_MannequinToGuardCombat'
    retarget = EA.load_asset(retarget_path) if EA.does_asset_exist(retarget_path) else EA.duplicate_asset(
        '/Game/Characters/Hero/Animation/Locomotion/RTG_MannequinToHero', retarget_path)
    if not retarget:
        raise RuntimeError('Could not duplicate the existing humanoid retargeter')
    controller = unreal.IKRetargeterController.get_controller(retarget)
    controller.set_ik_rig(unreal.RetargetSourceOrTarget.TARGET, target_rig)
    controller.set_preview_mesh(unreal.RetargetSourceOrTarget.TARGET, target_mesh)
    EA.save_loaded_asset(retarget, False)

    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    inputs = unreal.IKRetargetBatchOperationInputs(
        assets_to_retarget=[registry.get_asset_by_object_path(source_anim.get_path_name())],
        source_mesh=source_mesh, target_mesh=target_mesh, ik_retarget_asset=retarget,
        target_path=DEST, use_source_path=False, include_referenced_assets=False,
        overwrite_existing_files=False, suffix='_GuardCombat')
    results = unreal.IKRetargetBatchOperation.run_batch_retarget(inputs)
    if len(results) != 1:
        raise RuntimeError('Expected one retargeted strike, got ' + str(results))
    if not EA.rename_asset(results[0].get_asset().get_path_name().split('.')[0], clip_path):
        raise RuntimeError('Could not name the strike asset')
    clip = _loaded(clip_path)
    if clip.get_skeleton() != target_mesh.get_editor_property('skeleton'):
        raise RuntimeError('Retargeted strike does not match the guard skeleton')
    clip.set_preview_skeletal_mesh(target_mesh)
    clip.set_editor_property('enable_root_motion', False)
    clip.set_editor_property('force_root_lock', True)
    EA.save_loaded_asset(clip, False)
    return clip_path


if __name__ == '__main__':
    print(create_guard_punch_clip())
