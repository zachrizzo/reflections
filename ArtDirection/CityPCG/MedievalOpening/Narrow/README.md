# Narrow Cellarer frontage

The Cellarer has an exact 300 cm width and the existing 1484 cm opening-kit height. Its base-centered pivot and +X street face match the 450 cm merchant modules. The offset door retains a normal width, while a storage hatch, stone plinth, and a projecting leaded oriel distinguish the bay. The shadowed clay backing masks the flat host wall above the gable. Maximum +X street projection is 90.6 cm, before the usual depth scaling in the PCG plan.

Use two narrow bays on verified 5.5–6.6 m runs with enough clearance. Fit them to the usable width after applying the planner's frontage margins. Keep the host shell for collision and use `NoCollision` on generated components.

The mesh has 2,540 triangles, one UV layer, and nine existing medieval material slots. The Blender FBX round trip preserved the identity transform, material assignments, and texture references. The Unreal importer only creates a new mesh and binds shared materials. It supports retries without resaving existing assets. [Import helper](../../../../Tools/CityPCG/import_narrow_medieval.py)

```powershell
& 'C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe' --background --factory-startup --python-exit-code 1 --python ArtDirection/CityPCG/MedievalOpening/Narrow/build_cellarer.py -- ArtDirection/CityPCG/MedievalOpening/Narrow/cellarer_preview.png
```
