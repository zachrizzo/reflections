# Follow-on whole-building blocks

The district selector found 22 complete shells that passed the offline screens
on `Tile_p03_p00` and `Tile_p03_p01`. Eleven form four road-connected groups.
These two groups have portable, review-only masks.

| Group | Source tile | Shells | Area | Wall and roof faces | Road samples |
| --- | --- | ---: | ---: | ---: | ---: |
| West connector | p03_p00 | 3 | 1,344.941 m² | 72 and 30 | 198 |
| Northwest of Leadenhall | p03_p01 | 4 | 1,321.489 m² | 94 and 41 | 261 |

The selector checks known landmark bounds, published PCG facades, the anonymous
shop overlay, central facade geometry, story marker zones, the inferred
opening-to-market road guide, and other roof geometry on the source and
neighboring exports. Each selected shell has a 1.5 m entrance approach
sampled at three offsets. Links between shells have three road sample tracks
and reject source wall crossings. The output identifies original face ordinals
and requires unique coordinate signatures before it writes the candidate.

Use the original export, inventories, and the matching overlays from
`Saved/CityPCG`. Run from the project root.

```powershell
$city = 'Saved/CityPCG'
$survey = "$city/MedievalSurvey"
$art = 'ArtDirection/CityPCG/MedievalOpening'

python Tools/CityPCG/select_whole_building_blocks.py "$city/Tile_p03_p00.glb" "$city/Tile_p03_p00.asset.json" "$survey/Tile_p03_p00_building_inventory.json" "$city/AnonymousShops_Tile_p03_p00.glb" "$art/next_whole_building_blocks_settings.json" "$survey/Tile_p03_p00_next_building_blocks.json" --neighbor "$survey/Tile_p03_p01.glb" "$survey/Tile_p03_p01.assets.json" --neighbor "$survey/Tile_p04_p00.glb" "$survey/Tile_p04_p00.assets.json" --candidate block_45eb3584ef2e "$art/west_connector_whole_buildings_candidate.json"

python Tools/CityPCG/select_whole_building_blocks.py "$survey/Tile_p03_p01.glb" "$survey/Tile_p03_p01.assets.json" "$survey/Tile_p03_p01_building_inventory.json" "$survey/AnonymousShops_Tile_p03_p01.glb" "$art/next_whole_building_blocks_settings.json" "$survey/Tile_p03_p01_next_building_blocks.json" --neighbor "$city/Tile_p03_p00.glb" "$city/Tile_p03_p00.asset.json" --neighbor "$survey/Tile_p04_p00.glb" "$survey/Tile_p04_p00.assets.json" --candidate block_c4997573ed77 "$art/leadenhall_northwest_whole_buildings_candidate.json"
```

Generate bounded starting proportions and recheck each complete road link
against every footprint in its block:

```powershell
python Tools/CityPCG/plan_replacement_block.py "$city/Tile_p03_p00.glb" "$art/west_connector_whole_buildings_candidate.json" "$survey/west_connector_whole_building_plan.json"
python Tools/CityPCG/plan_replacement_block.py "$survey/Tile_p03_p01.glb" "$art/leadenhall_northwest_whole_buildings_candidate.json" "$survey/leadenhall_northwest_whole_building_plan.json"
```

The planner validates all shared party edges and proposes reproducible roof
proportions that stay under the source height. These are starting styles for
art review, not evidence that a generated mesh or runtime placement is safe.

## Before swapping either tile

Check the loaded tile and live actor bounds. Validate the existing door and
street profiles with floor traces and capsule sweeps, inspect roof traversal,
and check the opening-to-market gameplay path and authored neighbors.

Build each derivative from the canonical source with the **cumulative mask
for that tile**. West Mark Lane and the west connector are both on p03_p00.
Once both groups are accepted, their union removes 128 wall and 52 roof faces
from six source shells. A derivative based on the connector alone would
restore the first three old shells. Keep the original source and each
approved derivative addressable for rollback.

After both groups have passed live review, produce their cumulative offline
mask from the same original tile export. Use a fresh output path:

```powershell
python Tools/CityPCG/combine_replacement_candidates.py "$city/Tile_p03_p00.glb" "$survey/p03_p00_six_shell_candidate.json" "$art/west_mark_lane_whole_buildings_candidate.json" "$art/west_connector_whole_buildings_candidate.json"
python Tools/CityPCG/subtract_building_shells.py "$city/Tile_p03_p00.glb" "$city/Tile_p03_p00.asset.json" "$survey/p03_p00_six_shell_candidate.json" "$survey/p03_p00_without_six_shells.glb" "$survey/p03_p00_without_six_shells.audit.json"
```

The combiner rejects different source hashes, duplicate buildings and repeated
face signatures. It does not approve any unreviewed gameplay replacement.
