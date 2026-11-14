import unreal,json,traceback
from pathlib import Path
out=Path(unreal.Paths.project_saved_dir())/'CrowdPrototype'/'lod-repair.json'
try:
 col=unreal.load_asset('/Game/Characters/RedLondon/Crowd/Test/COL_CrowdPrototype_CoinClerk');sub=unreal.get_editor_subsystem(unreal.MetaHumanCollectionEditingSubsystem)
 h=sub.open_collection_session(col,'Reflections inspect LOD');e=h.get_staged_pipeline().get_editor_property('editor_pipeline')
 actor=list(e.get_editor_property('actor_body_lo_ds'))[:1];instanced=list(e.get_editor_property('instanced_body_lo_ds'))[:1]
 for lod in actor+instanced:lod.set_editor_property('source_lod',0)
 e.set_editor_property('actor_body_lo_ds',actor);e.set_editor_property('instanced_body_lo_ds',instanced)
 out.write_text(json.dumps({'stage':'building'}))
 if not h.apply_changes():raise RuntimeError('Failed to rebuild with LOD0 clothing')
 unreal.EditorAssetLibrary.save_loaded_asset(col,only_if_is_dirty=False)
 i=unreal.load_asset('/Game/Characters/RedLondon/Crowd/Test/MI_CrowdPrototype_CoinClerk');v=i.get_assembly_output().get_value()
 out.write_text(json.dumps({'stage':'complete','clothing':str(v.get_editor_property('instanced_clothing'))},indent=2))
except Exception as exc:out.write_text(json.dumps({'stage':'failed','error':str(exc),'trace':traceback.format_exc()}));unreal.log_error(traceback.format_exc())
