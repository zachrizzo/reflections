# Grouped whole-building geometry

Use this offline prototype to measure section consolidation while keeping the original building placements, collision footprints and cumulative tile masks traceable. It consumes all buildings named by a rollout audit, so an omitted or duplicate mesh aborts the bundle.

## Prepare ignored inputs

The four candidate files and canonical model kits are in `ArtDirection/CityPCG/MedievalOpening`. Restore the exact original Gray London GLBs and their sidecars into `Saved/CityPCG` first. They contain the source triangle ordinals that the checked masks refer to.

| Tile | Expected SHA-256 | How to request the matching export |
| --- | --- | --- |
| `Tile_p03_p00` | `5c946436fce01c086598966fcca3c379381b29776e1e03df2b37ada9fb4b08f4` | `export_geodata_tiles_unreal.export_tiles(["Tile_p03_p00"])` |
| `Tile_p03_p01` | `411a895aedeb642f0250cdd4c3e4725a1d04b73035ea4a75335f60193ca7102c` | `export_geodata_tiles_unreal.export_tiles(["Tile_p03_p01"])` |
| `Tile_p04_p00` | `5dab26bfe0ce4107b20721fac0998db646d68f22dade557ece0ab8f003aa3943` | `export_medieval_tile_inputs.export_inputs("Tile_p04_p00")` |

Run those functions in Unreal Python on the matching Gray London map revision with `Tools/CityPCG` on `sys.path`, outside PIE and in the assigned editor window. The first exporter reads the loaded `OSM Tile_…` actor and writes `.asset.json` next to its GLB. The second uses the tile and anonymous-shop actor descriptors and writes `.assets.json` under `Saved/CityPCG/MedievalSurvey`. The shop overlay export can remain there, though the grouping prototype only reads the canonical tile and metadata. Neither exporter needs a map save. If the export digest differs, obtain the original pinned export and sidecar from the survey owner or regenerate and re-review the candidate on the new source.

From the checkout root, reproduce the cumulative report and the older West Mark Lane preparation. Choose a fresh report name if the report already exists. Use an available build window for the preparation Blender process.

```powershell
$art = 'ArtDirection/CityPCG/MedievalOpening'
$survey = 'Saved/CityPCG/MedievalSurvey/whole_building_rollout_preflight_v2.json'
python Tools/CityPCG/audit_whole_building_rollout.py $survey --candidate "$art/west_mark_lane_whole_buildings_candidate.json" --candidate "$art/west_connector_whole_buildings_candidate.json" --candidate "$art/leadenhall_northwest_whole_buildings_candidate.json" --candidate "$art/east_tower_whole_buildings_candidate.json"
$blender = 'C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe'
& $blender --background --threads 2 --factory-startup --python-exit-code 1 --python "$art/WholeBuildings/prepare_mark_lane_ue_fbx.py"
```

The latter regenerates the three prepared FBXs and `prepared_fbx_audit.json` in `Saved/MedievalOpening/WestMarkLaneImport` from the checked-in West Mark Lane source FBXs. The other three kits already include prepared copies. Regenerate the grouped bundle after regenerating any prepared FBX. Fresh exports may have identical geometry with different raw FBX bytes.

## Build and verify a bundle

```powershell
$survey = 'Saved/CityPCG/MedievalSurvey/whole_building_rollout_preflight_v2.json'
$kit = 'ArtDirection/CityPCG/MedievalOpening/WholeBuildings'
$decoder = 'C:/Program Files (x86)/Steam/steamapps/common/Blender/5.3/scripts/addons_core/io_scene_fbx'
$bundle = 'Saved/CityPCG/WholeBuildings/GroupedPrototype'
python Tools/CityPCG/group_whole_buildings.py $survey $bundle --kit "$kit/whole_buildings_kit.json" --kit "$kit/WestConnector/whole_buildings_kit.json" --kit "$kit/LeadenhallNorthwest/whole_buildings_kit.json" --kit "$kit/EastRoyalMint/whole_buildings_kit.json" --legacy-bridge-audit 'Saved/MedievalOpening/WestMarkLaneImport/prepared_fbx_audit.json' --fbx-decoder-dir $decoder
python Tools/CityPCG/verify_grouped_whole_buildings.py $bundle $survey --fbx-decoder-dir $decoder
python -m unittest discover -s Tools/CityPCG -p 'test_group_whole_buildings.py' -v
```

The command uses the installed Blender add-on's stand-alone FBX decoder in system Python. It does not launch Blender. Supply a fresh output directory. Default grid cells are 64 m, anchored at each source tile's recorded origin. Each building goes wholly into the cell containing the mean of its footprint vertices. Actual group spans are capped at twice the cell width and each group is capped at 100,000 triangles by default. Buildings and materials are emitted in stable order.

Schema 2 records kit and FBX paths relative to the checkout with forward slashes. To verify in a relocated checkout, keep the same layout and exact referenced bytes, including West Mark Lane's three prepared FBXs in `Saved/MedievalOpening/WestMarkLaneImport/Source`. Copy the grouped bundle and cumulative report, then pass the new checkout via `--project-root` when running the verifier from elsewhere. The verifier rejects absolute paths, traversal and links outside that root. The legacy audit is needed to generate the bundle. The grouped manifest already contains the source hashes needed to verify it.

When sharing a bundle for offline review, its compact `rollout_mask_evidence.json` can serve as the verifier's rollout argument. It retains the exact checked masks and source pins. The reviewed candidate files in the repository remain the regeneration inputs.

Each GLB has one primitive per material and retains triangle order within each building and material. The manifest carries the source mask hash, original face ordinals and footprint, authored pivot and yaw, prepared FBX hash and exact material triangle ranges. The verifier compares the emitted ordered world-space positions, normals and UVs with the prepared source geometry using the source kit's signed axes. This checks winding independently of the GLB totals and digest. Material fingerprints compare the authored material properties, texture inputs and embedded image bytes. Export paths and an ambient color multiplied by zero are normalized.

The four reviewed kits yielded **14 buildings in nine cells and 97 material sections**, down from **149 sections** in the individual assets. They contain **136,298 triangles**. Independent readback checked all **408,894 corners**. These figures count sections and geometry on disk.

## Unreal integration remains pending

The GLBs contain material slot names. A future native import must bind the exact listed kit material assets and recheck section identities, signed bounds, normals, UVs, collision and navigation. The prototype retains geometry density and does not author LODs, lightmap UVs or a simplified collision proxy.

Keep the loaded original tile until the exact cumulative filtered tile and **every** listed group for that source tile are registered and verified. A missing or unloading group restores that tile's original rendering and collision. This preserves the existing roads and protected geometry under the same mask. Treat the group manifest as offline evidence for an eventual activation gate. Native cooking, stream-in/out, route/capsule checks and roof traversal still require in-engine proof.
