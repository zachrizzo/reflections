import unreal,json,traceback
from pathlib import Path
out=Path(unreal.Paths.project_saved_dir())/'SampleMapIntegration'/'probe.json';out.parent.mkdir(parents=True,exist_ok=True)
try:
 es=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);w=unreal.EditorLevelLibrary.get_editor_world()
 actors=es.get_all_level_actors();arr=[]
 for a in actors:
  label=a.get_actor_label()
  if any(x in label.lower() for x in ['player','start','crowd','npc','hero','ground','floor']):
   p=a.get_actor_location();arr.append({'label':label,'class':a.get_class().get_path_name(),'loc':[p.x,p.y,p.z]})
 out.write_text(json.dumps({'world':w.get_path_name(),'actor_count':len(actors),'relevant':arr[:80]},indent=2))
except Exception as e:out.write_text(json.dumps({'error':str(e),'trace':traceback.format_exc()}))
