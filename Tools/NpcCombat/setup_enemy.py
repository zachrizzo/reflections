"""Create the test-map opponent and a retargeted unarmed strike in Unreal Editor."""
import json
import shutil
import traceback
from pathlib import Path

import unreal

OUT = Path(unreal.Paths.project_intermediate_dir()) / 'NpcCombat'
OUT.mkdir(parents=True, exist_ok=True)
DEST = '/Game/Characters/CrowdMotion/Combat'
EA = unreal.EditorAssetLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
LEVEL = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
EXPECTED = '/Game/Characters/Hero/Sample/Lvl_HeroSampleCrowd'


def loaded(path):
    value = EA.load_asset(path)
    if not value:
        raise RuntimeError('Missing asset: ' + path)
    return value


def setup():
    world = LEVEL.get_editor_world()
    if EXPECTED not in world.get_path_name():
        raise RuntimeError('Open the default crowd map before setting up the opponent')
    if LEVEL.get_game_world():
        raise RuntimeError('Stop Play in Editor before editing the map')
    source_map = Path(unreal.Paths.project_content_dir()) / 'Characters/Hero/Sample/Lvl_HeroSampleCrowd.umap'
    backup = OUT / 'Lvl_HeroSampleCrowd.before-enemy.umap'
    if source_map.exists() and not backup.exists():
        shutil.copy2(source_map, backup)
    if not EA.does_directory_exist(DEST):
        EA.make_directory(DEST)

    target_mesh = loaded('/Game/Characters/RedLondon/BridgeGuard/Assembled/BridgeGuard/Body/SKM_MHC_BridgeGuard_BodyMesh')
    source_mesh = loaded('/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple')
    source_anim = loaded('/Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_Attack_01')
    target_rig = loaded('/Game/Characters/CrowdMotion/IK_Crowd_BridgeGuard')
    retarget_path = DEST + '/RTG_MannequinToGuardCombat'
    retarget = EA.load_asset(retarget_path) if EA.does_asset_exist(retarget_path) else EA.duplicate_asset(
        '/Game/Characters/Hero/Animation/Locomotion/RTG_MannequinToHero', retarget_path)
    if not retarget:
        raise RuntimeError('Could not duplicate the existing humanoid retargeter')
    controller = unreal.IKRetargeterController.get_controller(retarget)
    controller.set_ik_rig(unreal.RetargetSourceOrTarget.TARGET, target_rig)
    controller.set_preview_mesh(unreal.RetargetSourceOrTarget.TARGET, target_mesh)
    EA.save_loaded_asset(retarget, False)

    clip_path = DEST + '/AS_GuardPunch'
    if not EA.does_asset_exist(clip_path):
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
    clip = loaded(clip_path)
    if clip.get_skeleton() != target_mesh.get_editor_property('skeleton'):
        raise RuntimeError('Retargeted strike does not match the guard skeleton')
    clip.set_preview_skeletal_mesh(target_mesh)
    clip.set_editor_property('enable_root_motion', False)
    clip.set_editor_property('force_root_lock', True)
    EA.save_loaded_asset(clip, False)
    options = unreal.AnimPoseEvaluationOptions()
    options.set_editor_property('evaluation_type', unreal.AnimDataEvalType.RAW)
    options.set_editor_property('optional_skeletal_mesh', target_mesh)
    pose_samples = []
    for frame in range(int(clip.get_play_length() * 30) + 1):
        at = min(frame / 30.0, clip.get_play_length())
        pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(clip, at, options)
        points = {}
        for bone in ('spine_03', 'hand_r', 'hand_l'):
            points[bone] = list(unreal.AnimPoseExtensions.get_bone_pose(pose, bone, unreal.AnimPoseSpaces.WORLD).translation.to_tuple())
        pose_samples.append(dict(time=at, **points))

    actors = ACTORS.get_all_level_actors()
    enemies = [actor for actor in actors if actor.actor_has_tag('NPC_CombatEnemy')]
    if len(enemies) > 1:
        raise RuntimeError('Multiple combat test enemies already exist; refusing to duplicate them')
    if enemies:
        enemy = enemies[0]
    else:
        enemy_class = EA.load_blueprint_class('/Game/Characters/CrowdMotion/SimpleRed/BridgeGuard/BP_BridgeGuard_SimpleRed')
        if not enemy_class:
            raise RuntimeError('Could not load the dressed guard Blueprint')
        enemy = ACTORS.spawn_actor_from_class(enemy_class, unreal.Vector(700, 400, 0), unreal.Rotator(0, 180, 0))
        if not enemy:
            raise RuntimeError('Could not spawn combat enemy')
        enemy.set_actor_label('Combat Opponent')
        enemy.set_editor_property('tags', [unreal.Name(x) for x in (
            'NPC_Reactive', 'NPC_Hostile', 'NPC_HitProxy', 'NPC_SampleLocomotion',
            'NPC_Ragdoll', 'NPC_CombatEnemy')])

    nav_volumes = [actor for actor in ACTORS.get_all_level_actors() if actor.actor_has_tag('ReflectionsCombatNavigation')]
    if not nav_volumes:
        volume = ACTORS.spawn_actor_from_class(unreal.NavMeshBoundsVolume, unreal.Vector(500, 0, 200), unreal.Rotator())
        if not volume:
            raise RuntimeError('Could not spawn NavMeshBoundsVolume')
        volume.set_actor_label('Combat Navigation Bounds')
        volume.set_editor_property('tags', [unreal.Name('ReflectionsCombatNavigation')])
        volume.set_actor_scale3d(unreal.Vector(40, 40, 8))
    else:
        volume = nav_volumes[0]
    if not unreal.EditorLevelLibrary.save_current_level():
        raise RuntimeError('Failed to save the crowd map')
    (OUT / 'setup.json').write_text(json.dumps({
        'enemy': enemy.get_actor_label(),
        'enemy_class': enemy.get_class().get_path_name(),
        'enemy_tags': [str(tag) for tag in enemy.get_editor_property('tags')],
        'strike': clip.get_path_name(),
        'strike_duration': clip.get_play_length(),
        'strike_samples': pose_samples,
        'target_skeleton': clip.get_skeleton().get_path_name(),
        'navigation_bounds': volume.get_actor_label(),
        'navigation_scale': list(volume.get_actor_scale3d().to_tuple()),
        'backup': str(backup),
    }, indent=2))


try:
    setup()
except Exception:
    (OUT / 'setup-error.txt').write_text(traceback.format_exc())
    raise
