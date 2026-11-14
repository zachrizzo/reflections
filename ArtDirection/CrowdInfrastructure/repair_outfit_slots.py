import unreal,json,traceback
from pathlib import Path
out=Path(unreal.Paths.project_saved_dir())/'CrowdPrototype'/'outfit-selections.json'
try:
 p='/Game/Characters/RedLondon/Crowd/Test/MI_CrowdPrototype_CoinClerk';a=unreal.load_asset(p)
 subsystem=unreal.get_editor_subsystem(unreal.MetaHumanCollectionEditingSubsystem);h=subsystem.open_instance_session(a,'Reflections crowd outfit repair')
 for sel in a.get_slot_selections():
  name=str(sel.get_editor_property('slot_name'))
  if name in ('Top Garment','Bottom Garment','Shoes'):
   sel.set_editor_property('slot_name','Outfits')
   if not h.add_slot_selection(sel):raise RuntimeError('Unable to add Outfits selection for '+name)
 if not h.apply_changes():raise RuntimeError('Could not apply outfit selections')
 unreal.EditorAssetLibrary.save_loaded_asset(a,only_if_is_dirty=False)
 v=a.get_assembly_output().get_value()
 out.write_text(json.dumps({'stage':'complete','selections':str(a.get_slot_selections()),'actor_clothing':str(v.get_editor_property('actor_clothing')),'instanced_clothing':str(v.get_editor_property('instanced_clothing'))},indent=2))
except Exception as exc:out.write_text(json.dumps({'stage':'failed','error':str(exc),'trace':traceback.format_exc()}));unreal.log_error(traceback.format_exc())
