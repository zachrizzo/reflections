import unreal,json,traceback
from pathlib import Path
out=Path(unreal.Paths.project_saved_dir())/'CrowdPrototype'/'groom-probe.json'
try:
 col=unreal.load_asset('/Game/Characters/RedLondon/Crowd/Test/COL_CrowdPrototype_CoinClerk')
 sub=unreal.get_editor_subsystem(unreal.MetaHumanCollectionEditingSubsystem);h=sub.open_collection_session(col,'Reflections groom probe')
 data=[]
 for item in h.get_staged_collection().get_items():
  slot=str(item.get_editor_property('slot_name'))
  if slot not in ('Hair','Eyebrows'):continue
  wi=item.get_editor_property('wardrobe_item');p=wi.get_pipeline();ep=p.get_editor_property('editor_pipeline') if p else None
  v={'slot':slot,'wardrobe':str(wi),'pipeline':str(p),'editor':str(ep)}
  if ep:
   for prop in ('cards_material','helmets_material','compatible_heads'):
    try:v[prop]=str(ep.get_editor_property(prop))
    except Exception as e:v[prop]='error '+str(e)
  data.append(v)
 out.write_text(json.dumps(data,indent=2));h.close()
except Exception as exc:out.write_text(json.dumps({'error':str(exc),'trace':traceback.format_exc()}));unreal.log_error(traceback.format_exc())
