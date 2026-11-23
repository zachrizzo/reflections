"""Fit the shared moving-hem tunic and sample each MetaHuman in Test Town PIE."""
import asyncio
import json
from pathlib import Path

import unreal

from capture_lineup_motion import JOINTS, MOTIONS, capture_body_mask


PROJECT = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
OUTPUT = PROJECT / 'Intermediate/WayfarerReview/MotionFit'
WARDROBE = '/Game/Characters/Clothing/WayfarerPilot/MotionFit/WI_LooseTunic'
SIMULATION_TRIAL = WARDROBE + '_SimulationTrial'
HOLDOUT = 'MotionFitHoldout'
HOLDOUT_ASSET = '/Game/Characters/Clothing/WayfarerPilot/MotionFit/MHC_' + HOLDOUT


def components(actor):
    meshes = {c.get_name(): c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent)}
    return meshes['Body'], meshes['Face'], actor.get_component_by_class(unreal.ChaosClothComponent)


async def assemble(names=None, wardrobe_path=SIMULATION_TRIAL):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    assert world and world.get_path_name().startswith('/Game/Maps/TestTown/L_TestTown.')
    subsystem = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
    dataflow = unreal.get_editor_subsystem(unreal.DataflowScriptingSubsystem)
    tabs = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
    assets = unreal.EditorAssetLibrary
    roster = json.loads((PROJECT/'ArtDirection/WayfarersTunic/Lineup.json').read_text())
    roster.append({'label': HOLDOUT, 'character': HOLDOUT_ASSET, 'folder': 'Preview/Wardrobe Holdout',
                   'location_cm': [-1050, 675, 8], 'yaw': 90})
    lookup = {(a.get_actor_label(),str(a.get_folder_path())): a
              for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor)}
    wardrobe = unreal.load_asset(wardrobe_path)
    assert wardrobe
    result = {}
    for slot in roster:
        name = slot['label'].split(' ',1)[-1]
        if names is not None and name not in names:
            continue
        path = slot['character']
        fresh = path == HOLDOUT_ASSET and not assets.does_asset_exist(path)
        if fresh:
            package, asset_name = path.rsplit('/',1)
            character = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                asset_name,package,unreal.MetaHumanCharacter,unreal.MetaHumanCharacterFactoryNew())
        else:
            character = unreal.load_asset(path)
        assert character
        if not subsystem.is_object_added_for_editing(character):
            assert subsystem.try_add_object_to_edit(character), name
        if fresh:
            targets = {'Height':184.,'Across Shoulder':43.,'Chest':107.,'Waist':92.,'Inseam':86.}
            measures = list(subsystem.get_body_constraints(character))
            for measure in measures:
                key = str(measure.name)
                measure.is_active = key in targets
                if measure.is_active:
                    measure.target_measurement = targets[key]
            subsystem.set_body_constraints(character,measures)
            subsystem.commit_body_state(character)
            assert assets.save_loaded_asset(character,False)
            (OUTPUT/'holdout.json').write_text(json.dumps({'character':path,
                'requested_cm':targets, 'garment_source':'BridgeGuard'}))
        actor = lookup.get((slot['label'],slot['folder']))
        if not actor:
            actor = subsystem.spawn_meta_human_actor(character,keep_transient=True)
            assert actor,name
            actor.set_actor_label(slot['label'],mark_dirty=False)
            actor.set_folder_path(unreal.Name(slot['folder']))
            actor.set_actor_location(unreal.Vector(*slot['location_cm']),False,True)
            actor.set_actor_rotation(unreal.Rotator(yaw=slot['yaw']),True)
        collection = subsystem.get_preview_collection(character)
        keys = collection.get_item_keys_for_wardrobe_item(wardrobe)
        key = keys[0] if keys else collection.try_add_item_from_wardrobe_item('Outfits',wardrobe)
        assert key and collection.get_default_instance().set_single_slot_selection('Outfits',key) is not False
        subsystem.assemble_for_preview(character)
        _,_,cloth = components(actor)
        assert cloth and cloth.get_material(0), name
        fitted = cloth.get_asset()
        overrides = {str(p.name):p.value for p in dataflow.get_dataflow_instance_info(fitted).variable_overrides}
        if wardrobe_path == SIMULATION_TRIAL and overrides.get('StripSimMesh') == 'True':
            assert tabs.open_editor_for_assets([fitted]), name
            dataflow.set_variable_override(fitted,'StripSimMesh','False')
            await asyncio.sleep(.7)
            tabs.close_all_editors_for_asset(fitted)
        result[name] = actor
        if len(result) % 4 == 0:
            await asyncio.sleep(.1)
    assert set(result) == set(names) if names is not None else len(result) == 25 and HOLDOUT in result
    return result


def add_component(actor, cls, parent=None):
    component = actor.call_method('AddComponentByClass',
        (cls.static_class(),parent is not None,unreal.Transform(),False))
    if parent:
        rule = unreal.AttachmentRule.SNAP_TO_TARGET
        component.attach_to_component(parent,'',rule,rule,rule,False)
    return component


def spawn(library, hero, preview, placement):
    source_body,source_face,source_cloth = components(preview)
    actor = library.spawn_bench_actor(hero,placement,unreal.Rotator())
    root = add_component(actor,unreal.SceneComponent)
    actor.set_actor_location(placement,False,True)
    body = add_component(actor,unreal.SkeletalMeshComponent,root)
    body.set_skinned_asset_and_update(source_body.get_skinned_asset())
    body.set_forced_lod(1)
    body.visibility_based_anim_tick_option = unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES
    for index in range(source_body.get_num_materials()):
        body.set_material(index,source_body.get_material(index))
    face = add_component(actor,unreal.SkeletalMeshComponent,body)
    face.set_skinned_asset_and_update(source_face.get_skinned_asset())
    face.set_leader_pose_component(body,True)
    face.set_forced_lod(1)
    cloth = add_component(actor,unreal.ChaosClothComponent,body)
    cloth.set_asset(source_cloth.get_asset())
    cloth.set_leader_pose_component(body,True)
    collider_lod = library.fit_triangle_collider(cloth,body)
    if collider_lod < 0:
        actor.destroy_actor()
        raise RuntimeError(f'Triangle collider failed on {preview.get_actor_label()}')
    cloth.set_forced_lod(1)
    cloth.set_leader_pose_component(body,True)
    return actor,body,face,cloth,collider_lod


def write_frame(library, folder, label, parts):
    _,body,face,cloth,_ = parts
    count = library.get_dynamic_cloth_particle_count(cloth)
    assert count > 0, (folder.name,label)
    for key,mesh in [('body',body),('face',face),('off',cloth)]:
        assert library.write_posed_surface(mesh,str(folder/f'{label}_{key}.bin')), (folder.name,label,key)
    assert library.write_cloth_frame(cloth,str(folder/f'{label}_on.bin')), (folder.name,label,'on')
    return count


async def sample_group(library, live, output):
    frames = {name:{} for name in live}
    # Freeze each pose for at least an engine frame so body and simulation data
    # refer to the same sample. Fabric advances continuously between poses.
    await asyncio.sleep(.7)
    for name,parts in live.items():
        actor,body,_,_,lod = parts
        folder = output/name
        folder.mkdir(parents=True,exist_ok=True)
        library.refresh_sample_pose(body)
        count = write_frame(library,folder,'rest',parts)
        capture_body_mask(body,folder)
        inverse = actor.get_actor_transform().inverse_transform_location
        frames[name]['rest'] = {'collider_lod':lod, 'particles':count,
            'bones_cm':{j:list(inverse(body.get_socket_location(j)).to_tuple()) for j in JOINTS}}

    for action,points in [('walk',17),('cast',25)]:
        clip = unreal.load_asset(MOTIONS[action])
        end = min(clip.get_play_length(),1.6) if action=='walk' else clip.get_play_length()
        for _,body,_,cloth,_ in live.values():
            body.play_animation(clip,False)
            body.stop()
            cloth.force_next_update_teleport_and_reset()
        for i in range(points):
            t = end*i/(points-1)
            fraction = min(1.,max(0.,(t-.20)/.55))
            yaw = 60*fraction*fraction*(3-2*fraction) if action=='walk' else 0
            for actor,body,_,_,_ in live.values():
                body.set_position(t,False)
                actor.set_actor_rotation(unreal.Rotator(yaw=yaw),True)
                library.refresh_sample_pose(body)
            await asyncio.sleep(.052 if i else .25)
            label = f'{action}_{i:02d}'
            for name,parts in live.items():
                count = write_frame(library,output/name,label,parts)
                frames[name][label] = {'time_s':round(t,4),'yaw_deg':yaw,'particles':count}
    for name,rows in frames.items():
        (output/name/'frames.json').write_text(json.dumps(rows))


async def run(models, names):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    play = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    library = unreal.ClothingFitLibrary
    assert not play.is_in_play_in_editor()
    play.editor_request_begin_play()
    try:
        for _ in range(200):
            await asyncio.sleep(.08)
            game = editor.get_game_world()
            hero = unreal.GameplayStatics.get_player_character(game,0) if game else None
            if hero:
                break
        assert hero
        player = unreal.GameplayStatics.get_player_controller(game,0)
        camera = library.spawn_bench_actor(hero,unreal.Vector(-1530,-235,210),unreal.Rotator())
        add_component(camera,unreal.CameraComponent)
        camera.set_actor_location(unreal.Vector(-1530,-235,210),False,True)
        camera.set_actor_rotation(unreal.Rotator(pitch=-9),True)
        player.set_view_target_with_blend(camera,0)
        for start in range(0,len(names),5):
            group = names[start:start+5]
            live = {}
            try:
                for i,name in enumerate(group):
                    live[name] = spawn(library,hero,models[name],unreal.Vector(-1060,-500+130*i,8))
                    await asyncio.sleep(.04)
                await sample_group(library,live,OUTPUT/'surfaces')
            finally:
                for actor,_,_,_,_ in live.values():
                    actor.destroy_actor()
        return names
    finally:
        play.editor_request_end_play()
        await asyncio.sleep(.4)
