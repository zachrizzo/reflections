import unreal,json,traceback
from pathlib import Path
O=Path(unreal.Paths.project_saved_dir())/'CrowdPrototype'/'api.json'
classes=['MassEntityConfig','MassEntityConfigAsset','InstancedStruct','MassActorFragment','TransformFragment','MassViewerInfoFragment','MassSpawnedEntityType','MassSpawnDataGenerator','MetaHumanMassCrowdVisualizationTrait','ReflectionsCrowdGridGenerator']
d={}
for n in classes:
 c=getattr(unreal,n,None)
 d[n]={'found':bool(c),'doc':str(c.__doc__)[:2000] if c else '', 'methods':dir(c) if c else []}
O.write_text(json.dumps(d,indent=2))
