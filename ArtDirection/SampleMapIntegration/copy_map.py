import unreal,json,traceback
from pathlib import Path
out=Path(unreal.Paths.project_saved_dir())/'SampleMapIntegration'/'copy.json'
try:
 w=unreal.EditorLevelLibrary.get_editor_world()
 if w.get_path_name()!='/Game/Characters/Hero/Sample/Lvl_HeroSampleSandbox.Lvl_HeroSampleSandbox':raise RuntimeError('Current map differs from expected sample sandbox')
 if unreal.EditorLevelLibrary.get_game_world():raise RuntimeError('PIE is active; refusing to change levels')
 dest='/Game/Characters/Hero/Sample/Lvl_HeroSampleCrowd'
 if unreal.EditorAssetLibrary.does_asset_exist(dest):raise RuntimeError('Destination already exists; refusing overwrite')
 before=[str(x) for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
 ok=unreal.EditorLoadingAndSavingUtils.save_map(w,dest)
 after=unreal.EditorLevelLibrary.get_editor_world().get_path_name()
 out.write_text(json.dumps({'saved':ok,'original_world':'/Game/Characters/Hero/Sample/Lvl_HeroSampleSandbox','current_world_after':after,'copy':dest,'dirty_before':before,'dirty_after':[str(x) for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]},indent=2))
except Exception as e:out.write_text(json.dumps({'error':str(e),'trace':traceback.format_exc()},indent=2));unreal.log_error(traceback.format_exc())
