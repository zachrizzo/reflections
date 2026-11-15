# West Mark Lane whole buildings

These three late medieval exteriors fit the exact surveyed outlines west of Mark Lane. Each has an underside, rear and side walls, closed doors, and a tiled roof with solid gables. The shared 5.528 m party wall stays sealed. Outside corners and recesses in the source outlines remain open for access. The plan does not identify a verified interior courtyard, so the trading compound uses a closed cart gate and keeps its source exterior boundary.

| Building | Footprint | Roof | Street detail |
| --- | ---: | --- | --- |
| Workshop | 74.579 m² | One steep gable over an L plan | Green shutters and a low timber door |
| Merchants' houses | 352.576 m² | Two adjoining tiled ranges | Stone base, leaded windows and timber jetty brackets |
| Trading compound | 1,277.621 m² | Four staggered tiled ranges | A wide stone cart arch with a closed door |

`whole_buildings_kit.json` gives the exact placement transform and roof-to-ground dimensions for each FBX in `Source`. Use the recorded pivot, yaw and unit scale. The ground pivot is the recovered source shell origin, which can be at a footprint corner. Local +X faces the designated exterior entry and +Z points up. The FBX uses Blender metres and exports with Unreal centimetre units. The build checks the footprint and source height before export.

The FBXs use UV0 and the shared `M_GLMedieval_*` material slots. Assign existing Unreal materials by slot name. The FBXs embed the shared image textures from `../Textures` and `../Guildhall/Textures`. Blender may unpack audit copies in `.fbm` folders during reimport. The two `MarkLane` previews show the three meshes from opposite approaches using their recorded transforms.

Use LOD0 for the street pilot. For distant versions, strip fine glazing bars and door ironwork first while keeping the tile slopes and framing. Use only the shell and roof at skyline distance. The importer uses LOD0 geometry as ComplexAsSimple collision for each building. Replacement components inherit the source tile's collision settings. Verify the entry strips, party wall, pavement and roof access during the tile swap.

To rebuild the FBXs and previews with Blender 5.3 from the repository root:

```powershell
& 'C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe' --background --factory-startup --python-exit-code 1 --python 'ArtDirection/CityPCG/MedievalOpening/WholeBuildings/build_mark_lane.py' -- --preview
```

Prepare the three Unreal import copies with Blender, then validate the input hashes and surveyed transforms with regular Python:

```powershell
& 'C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe' --background --factory-startup --python-exit-code 1 --python 'ArtDirection/CityPCG/MedievalOpening/WholeBuildings/prepare_mark_lane_ue_fbx.py'
python 'ArtDirection/CityPCG/MedievalOpening/WholeBuildings/import_west_mark_lane.py' --preflight
```

This writes the triangulated copies and `prepared_fbx_audit.json` under `Saved/MedievalOpening/WestMarkLaneImport`. The copies account for Unreal's FBX Y reflection. The audit records each original and prepared file hash and a separate geometry hash that excludes FBX metadata. The original FBXs remain the authoritative Blender source.

With the editor idle, invoke the importer in Unreal Python:

```python
from pathlib import Path
import runpy
import unreal

script = Path(unreal.Paths.project_dir()).resolve() / 'ArtDirection/CityPCG/MedievalOpening/WholeBuildings/import_west_mark_lane.py'
report = runpy.run_path(str(script))['run']()
```

The importer writes only the three mesh packages under `/Game/GrayLondon/MedievalOpening/WholeBuildings/WestMarkLane`. Before saving, it checks signed bounds, footprint vertices, clockwise winding, ordered materials, LOD0 triangles, UV0 and collision. Every LOD0 section provides collision, with zero generated simple or convex shapes. The report includes the hard material references read back from the saved packages. Set `verify_only=True` when checking an existing import. The project report is `Saved/MedievalOpening/WestMarkLaneImport/ue_import_report.json`.
