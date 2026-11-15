# Gray London facade kit

Three architecture families provide a brick Edwardian frontage, a Portland stone office arcade, and a late twentieth-century stone and glass office. Each has a ground bay, a distinct entrance, an upper bay, and a crown. The windows and doors are shallow visual overlays for existing building shells. The family designs take their cues from the mixed office architecture documented in the [Gray London photo references](../../CityDetailPilot/PHOTO_REFERENCES.md).

Use `kit_manifest.json` for the engine mesh names, ordered shared material slots, source texture paths, and base colors. Bays and entrances measure 400 cm along Y and 320 cm along Z, with the pivot at the bottom center of the existing facade plane and +X facing the street. Cornices are 55 cm high. Street projection is 28–39.4 cm for bays and 46 cm at the cornice. The rear extends 2.5 cm behind the plane. Keep the original building collision and disable any automatic collision for the overlays. All three texture tiles are original and baked into the FBX exports, with separate PNGs for sharing one texture and material per slot across the kit.

Use at most one entrance on a selected street-facing run, and group neighboring bays by actual building and facade style. Fit authored bays and upper floors to the wall length and story height. Keep cornices off runs with incompatible roof height or insufficient clearance. Archetypes provide a district-level starting point for the PCG rules. Characteristic corner forms and protected landmarks need explicit models and exclusions.

Regenerate the source and the preview with the following commands.

```powershell
python ArtDirection/CityPCG/Kit/build_kit_textures.py
& 'C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe' --background --factory-startup --python-exit-code 1 --python ArtDirection/CityPCG/Kit/build_facade_kit.py -- ArtDirection/CityPCG/Kit/facade_kit_preview.png
```

All 12 FBXs round-tripped through Blender with one UV layer, identity transforms, the expected material order and resolved image references. The set totals 5,832 triangles. The preview shows each family's entrance, upper story and cornice ordered left to right. Verify Unreal import scale, facing, UVs and slots before placement.
