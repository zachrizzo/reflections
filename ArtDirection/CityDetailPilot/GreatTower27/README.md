# 27 Great Tower Street

This exterior study reconstructs the 1914 building from its mapped outline and street photographs. No. 27 is at the Byward Street end of Great Tower Street. Its street elevation has five upper bays, two storeys of brick pilasters with Ionic caps, a Portland stone entablature, and a swept parapet with a central segmental pediment. The model also includes the tiled mansard, dormers, side return, rusticated ground storey, and a shallow exterior passage. The source height of 14.34 m and secondary elevations are estimates. The passage models only the exterior portal and a short recess.

- [Historic England list entry 1064672](https://historicengland.org.uk/listing/the-list/list-entry/1064672) identifies the date, materials, bay count, main entrance, west passage, and return.
- [Planning Data outline 42136285](https://www.planning.data.gov.uk/entity/42136285), City of London Corporation and the Ministry of Housing, Communities and Local Government. Contains public sector information licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). The source coordinates were translated, approximated in metres, and rotated to the frontage axis.
- [2008 corner photograph by Ewan Munro](https://commons.wikimedia.org/wiki/File:The_Hung_Drawn_and_Quartered_(HDQ),_Great_Tower_Street,_London_EC3.jpg), CC BY-SA 2.0. The mesh uses it as a visual reference for the two street walls and roof silhouette.
- [2012 north photo](https://commons.wikimedia.org/wiki/File:The_Hung,_Drawn_and_Quartered_on_Great_Tower_Street_-_geograph.org.uk_-_3335747.jpg) and [2012 east photo](https://commons.wikimedia.org/wiki/File:The_Hung,_Drawn_and_Quartered_on_Great_Tower_Street_-_geograph.org.uk_-_3335751.jpg), both Steve Daniels via Geograph and CC BY-SA 2.0, provide a second check on the fenestration and return.

The exported mesh and its three 512 px textures were built procedurally from measured geometry and visual reference. The exported textures contain no source photo pixels. The Hunyuan image-to-3D trial was deferred while the shared Unreal editor was open and system memory was limited.

## Files and validation

- `GreatTowerStreet_27.blend` contains the original building, packed textures, and the studio camera and lights.
- `GreatTowerStreet_27.glb` contains only the textured building mesh. A clean Blender reimport verified 14,920 triangles, 8 material slots, one UV set, a ground pivot at the centre of the Great Tower Street frontage, and bounds of 26.77 × 20.17 × 14.34 m.
- `GreatTowerStreet_27_preview.png` is the studio render of the north and east elevations.
- `/Game/GrayLondon/CityDetailPilot/GreatTower27/GreatTowerStreet_27/StaticMeshes/SM_GreatTowerStreet_27_Exterior` is the standalone Unreal draft. Its mesh description matches the 14,920 source triangles and has one UV set, eight material slots, and zero simple collision shapes. Nanite is enabled and the fallback render mesh has 4,290 triangles. Unreal Interchange created eight materials and four textures, including two imports of the shared brick image. All 13 draft asset packages were saved and persisted by explicit path.

## Placement seed

The public footprint gives a centre of **51.509615° N, 0.0807545° W** at the street edge. It is halfway between the west frontage endpoint at `(51.509651, -0.080846)` and the east endpoint at `(51.509579, -0.080663)`. The outward normal is **032.30° true** or **030.73° on British National Grid**. The existing Gray London projection script, combined with the map's +X east and +Y north convention, gives an approximate actor position of `(328038, 26467)` cm and an initial outward yaw of **+59.27°**.

Use the position as a starting point for tracing, because the existing OSM wall was hit around `(328073.77, 26528.90)` cm with horizontal outward normal `(.4537, .8912)`, and its flat roof is at approximately `Z=1280` cm. That existing mass can fill the portal and intersect the mansard. Fit the street edge and return, verify ground height at both ends, and isolate the affected building volume before placement.

The Blender file uses +X toward the street and +Y toward the west passage. Unreal's glTF import mirrors source Y, so the imported asset's +Y points toward the east return. Correct that handedness before applying the geographic yaw, then verify both building corners against traces. Use a mirrored import variant or bake the correction into a copy of the draft mesh. Placement, collision, and streaming have not been tested.

## Rebuild

From the repository root, with Blender 5.3 and a Python installation containing Pillow and NumPy:

```powershell
$out = 'Saved/CityDetailPilot/GreatTower27'
python ArtDirection/CityDetailPilot/GreatTower27/build_material_textures.py "$out/textures"
blender -b --factory-startup -t 4 --python ArtDirection/CityDetailPilot/GreatTower27/build_great_tower_27.py -- $out
```
