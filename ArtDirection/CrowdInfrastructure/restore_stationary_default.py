import unreal, json, traceback
from pathlib import Path
out=Path(unreal.Paths.project_saved_dir())/'CrowdPrototype'/'stationary-default.json'
try:
 asset=unreal.load_asset('/Game/Characters/RedLondon/Crowd/Test/MEC_CrowdPrototype');cfg=asset.get_editor_property('config')
 traits=[x for x in cfg.get_editor_property('traits') if not isinstance(x,unreal.MassVelocityRandomizerTrait)]
 cfg.set_editor_property('traits',traits);asset.set_editor_property('config',cfg)
 unreal.EditorAssetLibrary.save_loaded_asset(asset,only_if_is_dirty=False)
 out.write_text(json.dumps({'stage':'saved','description':'stationary default; explicit synthetic velocity trait removed'}))
except Exception as exc:out.write_text(json.dumps({'error':str(exc),'trace':traceback.format_exc()}));unreal.log_error(traceback.format_exc())
