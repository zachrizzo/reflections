# Gray London grouped buildings

This offline review bundle contains nine spatial GLBs for 14 surveyed buildings across West Mark Lane, the West Connector, northwest Leadenhall, and East Royal Mint. The grouped meshes preserve 136,298 triangles in 97 material sections. The individual meshes use 149 material sections.

Open a GLB in a glTF viewer to inspect the shape and material slots. Each cell is local to the `origin_ue_m` recorded in `grouped_buildings.json`. For an ordered GLB position `[x, y, z]`, its world position in Unreal metres is the cell origin plus `[x, z, y]`. The manifest records surveyed plots, source face masks, the authored placement of each building, and its output triangle ranges by material. The GLB material names identify the shared medieval kit materials. Reviewers can apply those materials separately.

## Verify from a checkout

Make the repository's Git LFS objects available. The verifier uses the checked-in canonical and prepared FBXs through project-relative paths. `PreparedWestMarkLane` supplies the three exact prepared bridge files that were previously in an ignored folder. The cumulative masks for this review are in `rollout_mask_evidence.json`. The verification command requires system Python and the standalone decoder from the installed Blender 5.3 FBX add-on.

```powershell
$bundle = 'ArtDirection/CityPCG/MedievalOpening/WholeBuildings/GroupedPrototype'
$decoder = 'C:/Program Files (x86)/Steam/steamapps/common/Blender/5.3/scripts/addons_core/io_scene_fbx'
python Tools/CityPCG/verify_grouped_whole_buildings.py $bundle "$bundle/rollout_mask_evidence.json" --project-root . --fbx-decoder-dir $decoder
```

See [the generation workflow](../../../../../Tools/CityPCG/GROUPED_WHOLE_BUILDING_PROTOTYPE.md) to rebuild the source audit and grouped outputs.

## Unreal integration

The bundle is review-only. Native import and material binding, collision and navigation, cooking, gameplay routes and streaming still require verification. Keep the original tile active until its exact filtered tile and every required group in the manifest are ready. A partial or unloading group must restore the original tile's rendering and collision.
