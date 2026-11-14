"""Add simple unbounded test motion; NOT city navigation, collision avoidance, or walking animation."""
import unreal, json, traceback
from pathlib import Path
out=Path(unreal.Paths.project_saved_dir())/'CrowdPrototype'/'test-motion.json'
try:
 asset=unreal.load_asset('/Game/Characters/RedLondon/Crowd/Test/MEC_CrowdPrototype')
 cfg=asset.get_editor_property('config'); traits=list(cfg.get_editor_property('traits'))
 randomizer=next((x for x in traits if isinstance(x,unreal.MassVelocityRandomizerTrait)),None)
 if not randomizer: randomizer=unreal.MassVelocityRandomizerTrait(outer=asset);traits.append(randomizer)
 randomizer.set_editor_property('min_speed',45.0);randomizer.set_editor_property('max_speed',80.0);randomizer.set_editor_property('set_z_component',False)
 cfg.set_editor_property('traits',traits);asset.set_editor_property('config',cfg)
 unreal.EditorAssetLibrary.save_loaded_asset(asset,only_if_is_dirty=False)
 out.write_text(json.dumps({'stage':'saved','description':'horizontal test velocity 45-80 cm/s; no pathing, avoidance or animation'}))
except Exception as exc:out.write_text(json.dumps({'error':str(exc),'trace':traceback.format_exc()}));unreal.log_error(traceback.format_exc())
