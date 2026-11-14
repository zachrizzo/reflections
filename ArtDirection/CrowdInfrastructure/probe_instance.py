import unreal,json,traceback
from pathlib import Path
out=Path(unreal.Paths.project_saved_dir())/'CrowdPrototype'/'probe.json'
try:
 col=unreal.load_asset('/Game/Characters/RedLondon/Crowd/Test/COL_CrowdPrototype_CoinClerk')
 inst=unreal.load_asset('/Game/Characters/RedLondon/Crowd/Test/MI_CrowdPrototype_CoinClerk')
 d=col.get_default_instance()
 subs=unreal.get_editor_subsystem(unreal.MetaHumanCollectionEditingSubsystem)
 h=subs.open_instance_session(inst,'Crowd prototype instance setup')
 for sel in d.get_slot_selections():
  if not h.set_slot_selection(sel): raise RuntimeError('Could not copy slot selection '+str(sel))
 applied=h.apply_changes()
 unreal.EditorAssetLibrary.save_loaded_asset(inst,only_if_is_dirty=False)
 inst.get_assembly_output()
 obj={'collection_built':col.is_built(),'default_count':len(d.get_slot_selections()),'instance_count':len(inst.get_slot_selections()),'applied':applied,'instance_assembled':inst.is_assembled(),'classes':[x for x in dir(unreal) if 'Mass' in x and ('Trait' in x or 'Spawn' in x or 'EntityConfig' in x)],'massconfig_api':list(x for x in dir(unreal.MassEntityConfigAsset) if 'trait' in x or 'config' in x),'massspawner_api':list(x for x in dir(unreal.MassSpawner) if 'spawn' in x or 'count' in x)}
 out.write_text(json.dumps(obj,indent=2))
except Exception as e:out.write_text(json.dumps({'error':str(e),'trace':traceback.format_exc()},indent=2))
