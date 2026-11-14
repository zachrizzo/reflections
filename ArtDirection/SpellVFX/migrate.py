from pathlib import Path
import shutil,json,hashlib
src=Path(r'C:/Users/zachc/Documents/Unreal Projects/action_fighting_UE59/Content');dst=Path('Content')
files=['Blueprints/Combat/Blood/NS_BloodImpact.uasset','Blueprints/Combat/Blood/M_BloodParticle.uasset','Blueprints/Combat/Explosives/NS_GasCanExplosion.uasset','Blueprints/Combat/Explosives/NS_MissileTrail.uasset','Blueprints/Combat/Explosives/NS_GasCanGroundFire.uasset','Blueprints/Combat/Explosives/M_ExplosionFire.uasset','Blueprints/Combat/Explosives/M_ExplosionSmoke.uasset','Blueprints/Combat/Explosives/M_ExplosionSpark.uasset','Blueprints/Combat/Explosives/T_Explosion_Fire_SubUV.uasset','Blueprints/Combat/Explosives/T_Explosion_Smoke_SubUV.uasset']
r=[]
for rel in files:
 s=src/rel;d=dst/rel
 if not s.is_file():raise RuntimeError('Missing '+str(s))
 h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
 if d.exists():
  if h(s)!=h(d):raise RuntimeError('Refusing overwrite of existing different asset '+str(d))
  status='already identical'
 else:
  d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(s,d);status='copied'
 r.append({'path':rel,'status':status,'sha256':h(d)})
Path('ArtDirection/SpellVFX/migration.json').write_text(json.dumps({'source':str(src),'assets':r},indent=2))
