# Surveyed whole-building generation

The Blender generator consumes a reviewed candidate and the matching plan from `plan_replacement_block.py`. It uses surveyed ground pivots, entry directions and footprint boundaries. It builds closed walls and floors below pitched roof ranges and places decorative doors at the reviewed entry. Footprint width and planned role choose the material palette, framing and shutters. Roof heights vary by range. Chimneys fit inside the survey boundary and stay below the highest planned ridge.

Generate the west connector pilot from the repository root:

```powershell
$city = 'Saved/CityPCG'
$art = 'ArtDirection/CityPCG/MedievalOpening'
python Tools/CityPCG/plan_replacement_block.py "$city/Tile_p03_p00.glb" "$art/west_connector_whole_buildings_candidate.json" "$city/MedievalSurvey/west_connector_whole_building_plan.json"
& 'C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe' --background --factory-startup --python-exit-code 1 --python 'Tools/CityPCG/build_whole_buildings_blender.py' -- --output "$city/WholeBuildings/WestConnectorRefined" --prepare-unreal
```

`Source` contains the Blender source FBXs. `UnrealSource` contains triangulated copies that compensate for the legacy FBX importer's Y-axis conversion. `whole_buildings_kit.json` records both file hashes, placement transforms, material slots, roof and chimney coordinates, and audit results. Add `--preview` to render the three meshes in Blender. Use `--candidate`, `--plan`, `--output`, and `--prefix` to generate another reviewed block. The output directory must be new, so reruns cannot overwrite an earlier audit or artist's files. Narrower or lower plots may need a different kit.

Every mesh is reimported into a clean Blender scene. The audit checks UV0, material order, resolved textures, identity transforms, triangle counts, closed edges and winding. It checks projected triangle edges throughout each footprint, including concave recesses. The result is ready for a separate Unreal import and route review. Road access, collisions, quest paths, and preservation of nearby actors still require the live map.
