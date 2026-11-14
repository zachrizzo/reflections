"""Build one isolated Crowd Collection with one existing MetaHuman and its garments.
Run only in the project's UE 5.9 editor after coordinating ownership. Does not create a city.
"""
import unreal, json, traceback
from pathlib import Path
OUT=Path(unreal.Paths.project_saved_dir())/'CrowdPrototype'; OUT.mkdir(parents=True,exist_ok=True)
DIR='/Game/Characters/RedLondon/Crowd/Test'
NAME='COL_CrowdPrototype_CoinClerk'
BASE='/Game/Characters/RedLondon/CoinClerk'
SLOTS={
 'Head': BASE+'/MHC_CoinClerk',
 'Body': BASE+'/MHC_CoinClerk',
 'Hair': BASE+'/Assembled/CoinClerk/Grooms/Hair_M_BobCurly_Binding',
 'Eyebrows': BASE+'/Assembled/CoinClerk/Grooms/Eyebrows_M_Dense_Binding',
 'Top Garment': BASE+'/Outfit/SK_CoinClerk_Coat',
 'Bottom Garment': BASE+'/Outfit/SK_CoinClerk_Trousers',
 'Shoes': BASE+'/Outfit/SK_CoinClerk_Boots',
}
def report(stage,**kwargs):
 (OUT/'collection-progress.json').write_text(json.dumps({'stage':stage,**kwargs},indent=2))
def run():
 report('starting')
 lib=unreal.EditorAssetLibrary; tools=unreal.AssetToolsHelpers.get_asset_tools()
 path=DIR+'/'+NAME
 if lib.does_asset_exist(path):
  raise RuntimeError('Prototype collection already exists; inspect it before another build')
 for slot,p in SLOTS.items():
  if not lib.does_asset_exist(p): raise RuntimeError('Missing '+slot+' input '+p)
 asset=tools.create_asset(NAME,DIR,unreal.MetaHumanCollection,unreal.MetaHumanCollectionFactory())
 if not asset: raise RuntimeError('Collection factory returned None')
 subsystem=unreal.get_editor_subsystem(unreal.MetaHumanCollectionEditingSubsystem)
 handle=subsystem.open_collection_session(asset,'Reflections crowd prototype')
 pipeline_class=unreal.load_class(None,'/MetaHumanCrowd/BP_CrowdPipeline.BP_CrowdPipeline_C')
 if not handle or not pipeline_class: raise RuntimeError('Collection editing session or Crowd pipeline unavailable')
 handle.set_pipeline_from_class(pipeline_class)
 keys={}
 for slot,p in SLOTS.items():
  keys[slot]=handle.add_principal_asset(unreal.Name(slot),unreal.SoftObjectPath(p+'.'+p.rsplit('/',1)[-1]))
  selection=unreal.MetaHumanPipelineSlotSelection()
  selection.set_editor_property('slot_name',unreal.Name(slot))
  selection.set_editor_property('selected_item',keys[slot])
  if not handle.set_slot_selection(selection): raise RuntimeError('Cannot select '+slot)
 report('staged',slots=list(keys))
 pipeline=handle.get_staged_pipeline(); editor_pipeline=pipeline.get_editor_property('editor_pipeline')
 if not editor_pipeline: raise RuntimeError('Crowd editor pipeline not available')
 skeleton=editor_pipeline.create_target_skeleton_from_template(DIR,'SKEL_CrowdPrototype')
 if not skeleton: raise RuntimeError('Could not create target crowd skeleton')
 if not editor_pipeline.add_compatible_skeletons_from_collection(handle.get_staged_collection()): raise RuntimeError('Failed to add compatible skeletons')
 if not lib.save_loaded_asset(skeleton,only_if_is_dirty=False): raise RuntimeError('Failed to save target skeleton')
 report('building',slots=list(keys),skeleton=skeleton.get_path_name())
 if not handle.apply_changes(): raise RuntimeError('Collection build/apply failed; review Output Log')
 lib.save_loaded_asset(asset,only_if_is_dirty=False)
 if not asset.is_built(): raise RuntimeError('Collection apply completed but has no valid build')
 factory=unreal.MetaHumanInstanceFactory();factory.set_editor_property('collection',asset)
 instance=tools.create_asset('MI_CrowdPrototype_CoinClerk',DIR,unreal.MetaHumanInstance,factory)
 if not instance: raise RuntimeError('Instance factory failed')
 lib.save_loaded_asset(instance,only_if_is_dirty=False)
 report('complete',collection=asset.get_path_name(),instance=instance.get_path_name(),skeleton=skeleton.get_path_name(),slots=SLOTS)
try:run()
except Exception as exc:
 report('failed',error=str(exc),traceback=traceback.format_exc()); unreal.log_error(traceback.format_exc())

