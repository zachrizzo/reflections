import unreal,json,traceback
from pathlib import Path
out=Path(unreal.Paths.project_saved_dir())/'CrowdPrototype'/'benchmark-setup.json'
try:
 e=unreal.get_editor_subsystem(unreal.EditorActorSubsystem); sp=[a for a in e.get_all_level_actors() if isinstance(a,unreal.MetaHumanMassSpawner)]
 if len(sp)!=1:raise RuntimeError('Expected exactly one CrowdPrototype spawner; found '+str(len(sp)))
 s=sp[0];s.set_editor_property('count',100)
 gs=s.get_editor_property('spawn_data_generators');gs[0].get_editor_property('generator_instance').set_editor_property('columns',10)
 out.write_text(json.dumps({'stage':'ready','count':s.get_editor_property('count'),'generator_count':len(gs)}))
except Exception as exc:out.write_text(json.dumps({'stage':'failed','error':str(exc),'trace':traceback.format_exc()}));unreal.log_error(traceback.format_exc())
