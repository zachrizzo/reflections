import unreal,json,traceback
from pathlib import Path
OUT=Path(unreal.Paths.project_saved_dir())/'CrowdPrototype'/'repair.json'
def report(stage,**kw):OUT.write_text(json.dumps({'stage':stage,**kw},indent=2))
def main():
 lib=unreal.EditorAssetLibrary; d='/Game/Characters/RedLondon/Crowd/Test'; col=unreal.load_asset(d+'/COL_CrowdPrototype_CoinClerk')
 sub=unreal.get_editor_subsystem(unreal.MetaHumanCollectionEditingSubsystem);h=sub.open_collection_session(col,'Reflections crowd skeleton repair')
 p=h.get_staged_pipeline(); editor=p.get_editor_property('editor_pipeline')
 skel=editor.create_target_skeleton_from_template(d,'SKEL_CrowdPrototype_Final')
 if not skel:raise RuntimeError('Cannot create target skeleton')
 if not editor.add_compatible_skeletons_from_collection(h.get_staged_collection()):raise RuntimeError('Skeleton compatibility failed')
 if not lib.save_loaded_asset(skel,only_if_is_dirty=False):raise RuntimeError('Cannot save generated skeleton')
 report('building',skeleton=skel.get_path_name())
 if not h.apply_changes():raise RuntimeError('Rebuilding Collection failed')
 lib.save_loaded_asset(col,only_if_is_dirty=False)
 instance=unreal.load_asset(d+'/MI_CrowdPrototype_CoinClerk');instance.get_assembly_output()
 report('complete',collection_built=col.is_built(),instance_assembled=instance.is_assembled(),skeleton=skel.get_path_name())
try:main()
except Exception as e:report('failed',error=str(e),trace=traceback.format_exc());unreal.log_error(traceback.format_exc())


