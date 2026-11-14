import unreal,json,traceback
from pathlib import Path
OUT=Path(unreal.Paths.project_saved_dir())/'CrowdPrototype'/'mass-progress.json'
DIR='/Game/Characters/RedLondon/Crowd/Test'; NAME='MEC_CrowdPrototype'
def log(stage,**kw):OUT.write_text(json.dumps({'stage':stage,**kw},indent=2))
def main():
 lib=unreal.EditorAssetLibrary; tools=unreal.AssetToolsHelpers.get_asset_tools(); path=DIR+'/'+NAME
 asset=unreal.load_asset(path)
 if not asset:
  factory=unreal.DataAssetFactory(); factory.set_editor_property('data_asset_class',unreal.MassEntityConfigAsset)
  asset=tools.create_asset(NAME,DIR,unreal.MassEntityConfigAsset,factory)
 if not asset:raise RuntimeError('Could not create Mass entity config asset')
 instance=unreal.load_asset(DIR+'/MI_CrowdPrototype_CoinClerk')
 actor=unreal.load_class(None,'/MetaHumanCrowd/BP_CrowdActor.BP_CrowdActor_C')
 if not instance or not actor:raise RuntimeError('Missing crowd instance or actor class')
 instance.get_assembly_output()
 if not instance.is_assembled():raise RuntimeError('Crowd instance failed to assemble')
 visual=unreal.MetaHumanMassCrowdVisualizationTrait(outer=asset)
 visual.set_editor_property('character_instances',[instance]);visual.set_editor_property('high_res_template_actor',actor);visual.set_editor_property('low_res_template_actor',actor)
 core=unreal.ReflectionsCrowdActorTrait(outer=asset)
 member=unreal.MassCrowdMemberTrait(outer=asset)
 collector=unreal.MassLODCollectorTrait(outer=asset)
 movement=unreal.MassSimpleMovementTrait(outer=asset)
 config=asset.get_editor_property('config'); config.set_editor_property('traits',[visual,member,collector,movement,core]);asset.set_editor_property('config',config)
 lib.save_loaded_asset(asset,only_if_is_dirty=False)
 log('config-saved',asset=asset.get_path_name(),actor=actor.get_path_name(),traits=[str(t.get_class().get_name()) for t in config.get_editor_property('traits')])
main_guard=None
try:main()
except Exception as exc:log('failed',error=str(exc),trace=traceback.format_exc());unreal.log_error(traceback.format_exc())


