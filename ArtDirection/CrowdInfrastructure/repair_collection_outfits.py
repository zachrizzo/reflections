import unreal,json,traceback
from pathlib import Path
out=Path(unreal.Paths.project_saved_dir())/'CrowdPrototype'/'collection-outfits.json'
def report(stage,**kw):out.write_text(json.dumps({'stage':stage,**kw},indent=2))
try:
 lib=unreal.EditorAssetLibrary; d='/Game/Characters/RedLondon/Crowd/Test';col=unreal.load_asset(d+'/COL_CrowdPrototype_CoinClerk');inst=unreal.load_asset(d+'/MI_CrowdPrototype_CoinClerk')
 subsystem=unreal.get_editor_subsystem(unreal.MetaHumanCollectionEditingSubsystem)
 old=subsystem.find_instance_session(inst)
 if old:pass
 h=subsystem.open_collection_session(col,'Reflections outfit slot fix')
 sources={str(s.get_editor_property('slot_name')):s.get_editor_property('selected_item') for s in col.get_default_instance().get_slot_selections()}
 for slot in ('Top Garment','Bottom Garment','Shoes'):
  if slot in sources:h.remove_item(sources[slot])
 paths=['/Game/Characters/RedLondon/CoinClerk/Outfit/SK_CoinClerk_Coat','/Game/Characters/RedLondon/CoinClerk/Outfit/SK_CoinClerk_Trousers','/Game/Characters/RedLondon/CoinClerk/Outfit/SK_CoinClerk_Boots']
 keys=[]
 for path in paths:
  key=h.add_principal_asset('Outfits',unreal.SoftObjectPath(path+'.'+path.rsplit('/',1)[-1]));keys.append(key)
  sel=unreal.MetaHumanPipelineSlotSelection();sel.set_editor_property('slot_name','Outfits');sel.set_editor_property('selected_item',key)
  if not h.add_slot_selection(sel):raise RuntimeError('Failed Outfits selection '+path)
 report('building')
 if not h.apply_changes():raise RuntimeError('Collection rebuild failed')
 lib.save_loaded_asset(col,only_if_is_dirty=False)
 ih=subsystem.open_instance_session(inst,'Reflections outfit slot fix')
 for sel in col.get_default_instance().get_slot_selections():
  if str(sel.get_editor_property('slot_name'))=='Outfits':
   if not ih.add_slot_selection(sel):raise RuntimeError('Failed to copy Outfits selection')
 if not ih.apply_changes():raise RuntimeError('Instance apply failed')
 lib.save_loaded_asset(inst,only_if_is_dirty=False)
 v=inst.get_assembly_output().get_value()
 report('complete',clothing=str(v.get_editor_property('instanced_clothing')))
except Exception as exc:report('failed',error=str(exc),trace=traceback.format_exc());unreal.log_error(traceback.format_exc())
