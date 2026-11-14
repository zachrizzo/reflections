import unreal,json,traceback
from pathlib import Path
out=Path(unreal.Paths.project_saved_dir())/'CrowdPrototype'/'animation-config.json'
try:
 d='/Game/Characters/RedLondon/Crowd/Test';name='DA_CrowdPrototype_Animations'
 fac=unreal.DataAssetFactory();fac.set_editor_property('data_asset_class',unreal.MetaHumanCrowdAnimationConfig)
 asset=unreal.load_asset(d+'/'+name) or unreal.AssetToolsHelpers.get_asset_tools().create_asset(name,d,unreal.MetaHumanCrowdAnimationConfig,fac)
 idle=unreal.load_asset('/Game/Characters/Hero/Animation/Locomotion/AS_Hero_Idle')
 walk=unreal.load_asset('/Game/Characters/Hero/Animation/Locomotion/AS_Hero_Walk')
 if not asset or not idle or not walk:raise RuntimeError('Missing animation config or source sequences')
 items=[]
 for name,seq in [('Idle',idle),('Walk',walk)]:
  entry=unreal.MetaHumanCrowdBakeAnimationData();entry.set_editor_property('name',name);entry.set_editor_property('body_anim_sequence',seq);entry.set_editor_property('loop',True);entry.set_editor_property('root_motion',False);items.append(entry)
 asset.set_editor_property('animations_to_bake',items);unreal.EditorAssetLibrary.save_loaded_asset(asset,only_if_is_dirty=False)
 col=unreal.load_asset(d+'/COL_CrowdPrototype_CoinClerk');sub=unreal.get_editor_subsystem(unreal.MetaHumanCollectionEditingSubsystem)
 h=sub.open_collection_session(col,'Reflections crowd animation bake');p=h.get_staged_pipeline().get_editor_property('editor_pipeline');p.set_editor_property('animation_config',asset)
 out.write_text(json.dumps({'stage':'building'}))
 if not h.apply_changes():raise RuntimeError('Failed building collection with animation config')
 unreal.EditorAssetLibrary.save_loaded_asset(col,only_if_is_dirty=False)
 out.write_text(json.dumps({'stage':'complete','config':asset.get_path_name(),'animations':[s.get_path_name() for s in [idle,walk]]}))
except Exception as exc:out.write_text(json.dumps({'stage':'failed','error':str(exc),'trace':traceback.format_exc()}));unreal.log_error(traceback.format_exc())
