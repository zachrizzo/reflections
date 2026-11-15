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

## Review a style variation

Use `--style-overrides` to select an existing style for specific building IDs. The recipe's `plan_lf_sha256` hashes the plan bytes after replacing CRLF line endings with LF. Other bytes stay significant. The same recipe therefore works with either checkout line ending. Generated manifests still record the raw plan file hash as `plan_sha256` and the raw recipe file hash as `style_overrides_sha256`. The generator uses the same footprint, entry, roof and shared wall checks. Running without a recipe preserves the original style selection.

The northwest Leadenhall recipe gives the merchant house stone, lime render, dark oak and red shutters beside the warm plaster workshop. Run this variation in a fresh output folder:

```powershell
$city = 'Saved/CityPCG'
$art = 'ArtDirection/CityPCG/MedievalOpening'
& 'C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe' --background --threads 2 --factory-startup --python-exit-code 1 --python 'Tools/CityPCG/build_whole_buildings_blender.py' -- --candidate "$art/leadenhall_northwest_whole_buildings_candidate.json" --plan "$art/WholeBuildings/LeadenhallNorthwest/leadenhall_northwest_whole_building_plan.json" --style-overrides "$art/leadenhall_northwest_style_variation.json" --output "$city/WholeBuildings/LeadenhallNorthwestMerchantVariant" --prefix LeadenhallNorthwestVariant --prepare-unreal --preview
```

Review the merchant and workshop together from the street and above their four shared walls. Check that the lighter merchant palette reads distinctly, the roof joins leave no visible openings, and window or shutter details stay clear of the door approaches. The variant remains a source-art review until its collision and route checks pass in Unreal.

Run the recipe tests without Blender using `python -m unittest discover -s Tools/CityPCG -p test_whole_building_styles.py`.
