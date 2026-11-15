"""Duplicate the locally migrated source Niagara systems into dedicated game VFX assets."""
import unreal,json,traceback
from pathlib import Path
out=Path(unreal.Paths.project_saved_dir())/'SpellVFX'/'duplicate.json';out.parent.mkdir(parents=True,exist_ok=True)
source={'NS_SpellFireImpact':'/Game/Blueprints/Combat/Explosives/NS_GasCanExplosion','NS_SpellFireTrail':'/Game/Blueprints/Combat/Explosives/NS_MissileTrail','NS_SpellBloodImpact':'/Game/Blueprints/Combat/Blood/NS_BloodImpact'}
try:
 lib=unreal.EditorAssetLibrary;unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous(['/Game/Blueprints/Combat'])
 result=[]
 for name,src in source.items():
  dest='/Game/Effects/Spells/'+name
  a=unreal.load_asset(dest) if lib.does_asset_exist(dest) else lib.duplicate_asset(src,dest)
  if not a:raise RuntimeError('Failed duplicate '+src)
  if not isinstance(a,unreal.NiagaraSystem):raise RuntimeError('Not a Niagara System: '+dest)
  if not lib.save_loaded_asset(a,only_if_is_dirty=False):raise RuntimeError('Save failed '+dest)
  result.append({'source':src,'system':a.get_path_name()})
 out.write_text(json.dumps({'status':'complete','systems':result},indent=2))
except Exception as exc:out.write_text(json.dumps({'status':'failed','error':str(exc),'trace':traceback.format_exc()},indent=2));unreal.log_error(traceback.format_exc())
