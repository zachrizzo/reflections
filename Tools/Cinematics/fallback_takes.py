"""Retargets the project's existing Kimodo hand wave (Quinn) for the cutscene fallback takes:
  /Game/Cinematics/Takes/Fallback/AS_Fallback_Wave_UEFN  (NPC drivers, RTG_Mannequin_to_UEFN)
  /Game/Cinematics/Takes/Fallback/AS_Fallback_Wave_Hero  (Wren's MetaHuman body, RTG_MannequinToHero)
Runs in the editor via the MCP Python tool. No PIE needed."""
import json

import unreal

FOLDER = '/Game/Cinematics/Takes/Fallback'
SOURCE = '/Game/Animations/KimodoTests/AS_Quinn_RightHandWave_Kimodo'
QUINN = '/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple'
UEFN = '/Game/Characters/UEFN_Mannequin/Meshes/SKM_UEFN_Mannequin'
TARGETS = (
    ('AS_Fallback_Wave_UEFN', '/Game/Villain/Conversion/Rigs/RTG_Mannequin_to_UEFN', UEFN),
    ('AS_Fallback_Wave_Hero', '/Game/Characters/Hero/Animation/Locomotion/RTG_MannequinToHero', None),
)


def load(path):
    return unreal.load_asset(path)


def save(asset):
    unreal.EditorAssetLibrary.save_loaded_asset(asset, False)


def run():
    unreal.EditorAssetLibrary.make_directory(FOLDER)
    src = load(SOURCE)
    out = {}
    for name, rtg_path, mesh_path in TARGETS:
        rtg = load(rtg_path)
        target_mesh = load(mesh_path) if mesh_path else \
            unreal.IKRetargeterController.get_controller(rtg).get_preview_mesh(unreal.RetargetSourceOrTarget.TARGET)
        spec = unreal.IKRetargetBatchOperationInputs(
            assets_to_retarget=[unreal.AssetRegistryHelpers.create_asset_data(src)], source_mesh=load(QUINN),
            target_mesh=target_mesh, ik_retarget_asset=rtg, target_path=FOLDER, use_source_path=False,
            include_referenced_assets=False, overwrite_existing_files=True, suffix='_' + name)
        clip = unreal.IKRetargetBatchOperation.run_batch_retarget(spec)[0].get_asset()
        final = FOLDER + '/' + name
        if clip.get_path_name().split('.')[0] != final:
            if unreal.EditorAssetLibrary.does_asset_exist(final):
                unreal.EditorAssetLibrary.delete_asset(final)
            unreal.EditorAssetLibrary.rename_asset(clip.get_path_name().split('.')[0], final)
            clip = load(final)
        clip.set_editor_property('enable_root_motion', False)
        save(clip)
        out[name] = {'skeleton': clip.get_skeleton().get_path_name(), 'seconds': round(clip.get_play_length(), 2),
                     'target_mesh': target_mesh.get_path_name() if target_mesh else None}
    return out


RESULT = json.dumps(run(), indent=1)
