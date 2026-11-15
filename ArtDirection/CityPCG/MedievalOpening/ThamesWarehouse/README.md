# Thames merchant warehouse

This is a complete exterior for a small warehouse and merchant plot. A segmental goods arch and barred cellar lights anchor a stone ground level. Rough oak planks, a brace and hoist, and shuttered storage doors distinguish the loft. Two pitched clay-tile slopes run between the front and rear gables. The model takes its cues from medieval Thames waterfront archaeology and merchant-house storage. It depicts an original game building. [Historic England, Riverbank House waterfront phases](https://historicengland.org.uk/listing/the-list/list-entry/1484161) · [Historic England, early maritime storage guidance](https://historicengland.org.uk/images-books/publications/dlsg-maritime-naval-buildings/heag114-maritime-and-naval-lsg/)

The nominal rectangular footprint is 800 cm along X by 450 cm along Y, with its pivot at ground level in the center. +X faces the street or quay. The front wall plane is X=+400 cm. Allow 129 cm beyond the front wall for the hoist, 30 cm beyond the rear, and 22 cm at either side for the tiled eaves. The ridge reaches 951 cm. `warehouse_kit.json` records the exact source bounds and material slots. Keep distinct front, rear, and side clearance checks when scaling to measured lots. The shell is enclosed, with decorative doors and windows. There is no interior, hoist rig, or authored gameplay collision.

The mesh uses UV0 and eight existing medieval slots, including the Guildhall rubble and dressed stone materials. A separate background Blender reimport verifies the exported asset. The two preview images show the front and sides and the rear entrance. Unreal import, gameplay collision and placement are the next integration steps.

```powershell
& 'C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe' --background --factory-startup --python-exit-code 1 --python ArtDirection/CityPCG/MedievalOpening/ThamesWarehouse/build_thames_warehouse.py -- ArtDirection/CityPCG/MedievalOpening/ThamesWarehouse/warehouse_preview.png
```
