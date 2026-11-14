import unreal,json,traceback
from pathlib import Path
out=Path(unreal.Paths.project_saved_dir())/'SampleMapIntegration'/'crowd.json'
items=[('Red 01','/Game/Characters/RedLondon/Crowd/Variants/BP_Crowd_03',700,-700),('Red 02','/Game/Characters/RedLondon/Crowd/Variants/BP_Crowd_16',1000,-350),('Red 03','/Game/Characters/RedLondon/Crowd/Variants/BP_Crowd_29',800,0),('White 01','/Game/Characters/WhiteLondon/CrowdPreview/BP_WhiteLook_01_Plain',1000,400),('White 02','/Game/Characters/WhiteLondon/CrowdPreview/BP_WhiteLook_06_GuardBoldRunes',700,800)]
try:
 world=unreal.EditorLevelLibrary.get_editor_world();target='/Game/Characters/Hero/Sample/Lvl_HeroSampleCrowd'
 if not world.get_path_name().startswith(target+'.'):raise RuntimeError('Not in copied crowd test map')
 es=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);existing=es.get_all_level_actors()
 if any(a.get_actor_label().startswith('Crowd Preview - ') for a in existing):raise RuntimeError('Crowd preview actors already exist')
 classes=[]
 for label,path,x,y in items:
  cls=unreal.load_class(None,path+'.'+path.rsplit('/',1)[-1]+'_C')
  if not cls:raise RuntimeError('Missing '+path)
  classes.append((label,path,x,y,cls))
 result=[]
 for label,path,x,y,cls in classes:
  a=es.spawn_actor_from_class(cls,unreal.Vector(x,y,0),unreal.Rotator(0,0,180));a.set_actor_label('Crowd Preview - '+label);a.set_folder_path('Crowd Preview')
  center,extent=a.get_actor_bounds(False)
  result.append({'label':label,'path':path,'location':[x,y,0],'bounds_center':[center.x,center.y,center.z],'bounds_extent':[extent.x,extent.y,extent.z]})
 if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():raise RuntimeError('Could not save copy')
 out.write_text(json.dumps({'map':target,'count':len(result),'actors':result},indent=2))
except Exception as exc:out.write_text(json.dumps({'error':str(exc),'trace':traceback.format_exc()},indent=2));unreal.log_error(traceback.format_exc())

