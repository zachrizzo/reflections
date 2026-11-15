# West Mark Lane whole-building pilot

The exported primitive-to-Unreal section mapping remains a live verification
requirement. Several original sections share a material, so the current GLB
primitive count and recorded slot names alone do not prove that correspondence.
Treat the face and road checks below as checks against the recorded mapping
until the original Unreal source sections are compared independently.

Three ordinary p03_p00 source shells share one street block. The workshop and
merchant house meet along a 5.528 m party wall. The old models are flat-topped
and the new houses use pitched roofs inside the measured footprints. Roles,
materials and roof heights are art direction estimates.

| Building | Local depth × width | Maximum source height | Proposed roof |
| --- | ---: | ---: | --- |
| Merchant house | 19.554 × 23.645 m | 14.80 m | Two ranges, 12.75 m ridge |
| Corner workshop | 9.495 × 11.642 m | 12.60 m | One range, 9.25 m ridge |
| Merchant and workshop compound | 43.538 × 39.381 m | 14.80 m | Four ranges, 13.10 m ridge |

`west_mark_lane_whole_building_plan.json` uses the exact street entry normal as
local +X, its counterclockwise turn as +Y, and the source foundation pivot at
Z 0.20 m. The footprint can be concave. Use the supplied plan triangles for
the bottom cap and split them at the roof profile's Y knots for the top cap.
Split wall edges at the same knots and keep the party edges sealed. The nine
door approach profiles reached the exported road. Door recesses are decorative.

## Reproduce the plan

Export the pinned p03_p00 mesh into `Saved/CityPCG/Tile_p03_p00.glb` and run
from the project root.

```powershell
$art = 'ArtDirection/CityPCG/MedievalOpening'
python Tools/CityPCG/plan_whole_building_replacements.py Saved/CityPCG/Tile_p03_p00.glb "$art/west_mark_lane_whole_buildings_candidate.json" "$art/west_mark_lane_whole_building_settings.json" "$art/west_mark_lane_whole_building_plan.json"
```

The planner checks the source hash and all 78 original wall and roof triangle
signatures. The 600 road guards sample the north and south streets and the
joining west street at intervals up to 1 m, across three tracks 0.75 m apart.
All hit the exported road footprint and the nearest guard is 0.695 m from a
source shell. Preserve all road, park, water and authored central facade faces.

## Quest and runtime checks

No mapped story marker envelope intersects the three footprints. The nearest
marker is `Home_agnes_moth`, with 100.56 m outside its configured radius and
78.56 m outside a conservative 25 m radius. The opening objective at Lantern
Row targets a person and marker. The runtime GoTo code tests distance to a
resolved target. Player routes can vary.

A 502.27 m inferred approach from near the opening spawn to the southern
Leadenhall threshold bypasses this block by at least 74.51 m at its sampled
points. The exported p03 road triangles cover all 3,366 guard samples along
that route. The sample polyline and source markers are recorded together in
`Saved/CityPCG/MedievalSurvey/west_mark_lane_quest_route_evidence.json`. The
final passage into the market and navigability still require a live check.

For the visual comparison, retain the original tile collision and use the
index-filtered visual derivative plus the replacement shells. Recheck known
authored actor bounds and run the nine door-approach sweeps and all three local
street guards in the loaded map. Compare rooftop collision and quest movement
before publishing the replacement. Original and derivative are independently
addressable for rollback.

## Find stepped source buildings

Run `inventory_building_geometry.py` on the source export, then inspect the
same export with `group_stacked_roofs.py`.

```powershell
$city = 'Saved/CityPCG'
$survey = "$city/MedievalSurvey"
python Tools/CityPCG/group_stacked_roofs.py "$city/Tile_p03_p00.glb" "$city/Tile_p03_p00.asset.json" "$survey/Tile_p03_p00_building_inventory.json" "$survey/Tile_p03_p00_stacked_roofs.json"
```

The diagnostic compares projected roof triangles and follows upper wall bases
that match the lower roof elevation or the source's 0.20 m foundation offset.
It records actual bearing length and shared wall seams, then reports groups
only where each upper layer has a unique qualifying support. The p03_p00
export has eight candidate stacks, four with a recovered ground shell.
Review the original building ownership and neighboring landmarks, quests and
authored overlays before considering face removal.
