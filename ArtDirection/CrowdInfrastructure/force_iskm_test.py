import unreal,json,traceback
from pathlib import Path
out=Path(unreal.Paths.project_saved_dir())/'CrowdPrototype'/'iskm.json'
try:
 a=unreal.load_asset('/Game/Characters/RedLondon/Crowd/Test/MEC_CrowdPrototype');c=a.get_editor_property('config');v=c.get_editor_property('traits')[0];p=v.get_editor_property('params')
 i=unreal.MassRepresentationType.SKINNED_MESH_INSTANCE;n=unreal.MassRepresentationType.NONE
 p.set_editor_property('lod_representation',[i,i,i,n]);v.set_editor_property('params',p)
 unreal.EditorAssetLibrary.save_loaded_asset(a,only_if_is_dirty=False)
 out.write_text(json.dumps({'stage':'saved','params':str(p.get_editor_property('lod_representation'))}))
except Exception as e:out.write_text(json.dumps({'error':str(e),'trace':traceback.format_exc()}))
