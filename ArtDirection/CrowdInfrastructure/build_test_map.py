import unreal,json,traceback
from pathlib import Path
OUT=Path(unreal.Paths.project_saved_dir())/'CrowdPrototype'/'map-progress.json'
DIR='/Game/Characters/RedLondon/Crowd/Test'; MAP=DIR+'/Lvl_CrowdPrototype'
def log(stage,**kw):OUT.write_text(json.dumps({'stage':stage,**kw},indent=2))
def main():
 lib=unreal.EditorAssetLibrary
 if lib.does_asset_exist(MAP):raise RuntimeError('Test map already exists; inspect before replacing')
 ls=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
 if not ls.new_level(MAP):raise RuntimeError('Could not create isolated level')
 es=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
 world=unreal.EditorLevelLibrary.get_editor_world()
 world.get_world_settings().set_editor_property('default_game_mode',unreal.GameModeBase)
 floor=es.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(0,0,-50));floor.set_actor_label('Crowd Test Floor')
 floor.static_mesh_component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube.Cube'));floor.set_actor_scale3d(unreal.Vector(100,100,1))
 sun=es.spawn_actor_from_class(unreal.DirectionalLight,unreal.Vector(0,0,500));sun.set_actor_rotation(unreal.Rotator(-45,35,0),False)
 es.spawn_actor_from_class(unreal.SkyLight,unreal.Vector(0,0,600))
 player=es.spawn_actor_from_class(unreal.PlayerStart,unreal.Vector(-1600,0,180));player.set_actor_rotation(unreal.Rotator(0,0,0),False)
 spawner=es.spawn_actor_from_class(unreal.MetaHumanMassSpawner,unreal.Vector(0,0,10));spawner.set_actor_label('Crowd Test Spawner')
 cfg=unreal.load_asset(DIR+'/MEC_CrowdPrototype')
 ent=unreal.MassSpawnedEntityType();ent.set_editor_property('entity_config',cfg);ent.set_editor_property('proportion',1.0)
 spawner.set_editor_property('entity_types',[ent]);spawner.set_editor_property('count',20);spawner.set_editor_property('auto_spawn_on_begin_play',True)
 gen=unreal.ReflectionsCrowdGridGenerator(outer=spawner);gen.set_editor_property('columns',5);gen.set_editor_property('spacing',220.0)
 data=unreal.MassSpawnDataGenerator();data.set_editor_property('generator_instance',gen);data.set_editor_property('proportion',1.0)
 spawner.set_editor_property('spawn_data_generators',[data])
 t=es.spawn_actor_from_class(unreal.ReflectionsCrowdTelemetry,unreal.Vector(0,0,0));t.set_actor_label('Crowd Test Telemetry')
 t.set_editor_property('warmup_seconds',10.0);t.set_editor_property('capture_seconds',30.0)
 if not ls.save_current_level():raise RuntimeError('Test level save failed')
 log('map-saved',map=MAP,spawner=spawner.get_path_name(),count=20)
try:main()
except Exception as exc:log('failed',error=str(exc),trace=traceback.format_exc());unreal.log_error(traceback.format_exc())
