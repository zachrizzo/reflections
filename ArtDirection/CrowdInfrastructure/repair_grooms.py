import unreal,json,traceback
from pathlib import Path
out=Path(unreal.Paths.project_saved_dir())/'CrowdPrototype'/'groom-repair.json'
def report(stage,**kw):out.write_text(json.dumps({'stage':stage,**kw},indent=2))
try:
 lib=unreal.EditorAssetLibrary;col=unreal.load_asset('/Game/Characters/RedLondon/Crowd/Test/COL_CrowdPrototype_CoinClerk')
 sub=unreal.get_editor_subsystem(unreal.MetaHumanCollectionEditingSubsystem);h=sub.open_collection_session(col,'Reflections groom pipeline fix')
 cls=unreal.load_class(None,'/MetaHumanCrowd/BP_CrowdGroomPipeline.BP_CrowdGroomPipeline_C')
 if not cls:raise RuntimeError('Crowd groom pipeline class missing')
 head=unreal.load_asset('/Game/Characters/RedLondon/CoinClerk/MHC_CoinClerk')
 cards=unreal.load_asset('/MetaHumanCrowd/Materials/MI_Hair_Cards_Actor');helmet=unreal.load_asset('/MetaHumanCrowd/Materials/MI_Hair_Helmets_Actor')
 if not head or not cards or not helmet:raise RuntimeError('Required groom head or materials missing')
 fixed=[]
 for item in h.get_staged_collection().get_items():
  slot=str(item.get_editor_property('slot_name'))
  if slot not in ('Hair','Eyebrows'):continue
  wi=item.get_editor_property('wardrobe_item');wi.set_pipeline_from_class(cls)
  ep=wi.get_pipeline().get_editor_property('editor_pipeline')
  if not ep:raise RuntimeError('Groom editor pipeline missing for '+slot)
  ep.set_editor_property('cards_material',cards);ep.set_editor_property('helmets_material',helmet);ep.set_editor_property('compatible_heads',[head]);fixed.append(slot)
 if len(fixed)!=2:raise RuntimeError('Missing hair or eyebrows item')
 report('building',slots=fixed)
 if not h.apply_changes():raise RuntimeError('Collection groom rebuild failed')
 lib.save_loaded_asset(col,only_if_is_dirty=False)
 i=unreal.load_asset('/Game/Characters/RedLondon/Crowd/Test/MI_CrowdPrototype_CoinClerk');v=i.get_assembly_output().get_value()
 report('complete',grooms=str(v.get_editor_property('instanced_grooms')))
except Exception as exc:report('failed',error=str(exc),trace=traceback.format_exc());unreal.log_error(traceback.format_exc())
