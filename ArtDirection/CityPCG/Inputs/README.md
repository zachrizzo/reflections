# London frontage input

The input uses the existing tile geometry in Unreal. Its walls therefore match
the map's current footprint and height, including past exclusions and cuts. The
source notes credit OpenStreetMap contributors under ODbL 1.0 and describe the
limitations of the map's approximate 1980–2009 reconstruction.

## Mark Lane North pilot

The pilot spans 78 m of the main route north of the four intro shopfronts.
`mark_lane_north_survey.json` records the tile's component origin, the ordinary
facade primitive and a road guide found by live floor and side-wall traces.
`mark_lane_north_frontages.json` contains seven visible wall runs totaling
89.83 m. Three positions at three heights per run were traced against
`OSM Tile_p03_p00`. All 63 hit the intended tile with at most 0.028 cm horizontal
error. Exterior floor samples 0.8 m in front of the walls ranged from 10 to 28 cm
in Z. Individual styles and story counts are inferred by the facade planner.

## Batch 02 survey

`gray_london_batch02_frontages.json` covers 21 additional facing walls in two
nearby cells. All 189 live checks hit the intended ordinary OSM tile, at most
0.005 cm from the extracted wall. Exterior floor samples ranged from 10 to 28 cm.
Actor descriptors were checked against each complete facade envelope, expanded
0.75 m in plan, without finding any unexpected neighboring actor. The large
Anonymous Shops tile actor was checked against its exported geometry separately
so its broad bounds did not mask individual shopfronts. None of its storefront
triangles overlapped the selected wall strips. The source file disables
decorative entrances for this batch to avoid suggesting access where it has
not been designed. The stone and brick variations are a district palette.

The two review boxes in Unreal metres are west `[3052, 322, 3118, 392]` and
east `[3371, 327, 3421, 426]`. From the full-tile road-surface extraction,
the review kept complete spans within either box, at least 4 m wide and at
most 32 m tall. This avoids the initial Mark Lane cell, Fenchurch pre-2008
assets, Leadenhall and Lloyd's. The bake used the ordinary `GL_Facade`
section. The authored `GL_CentralFacade` section was excluded.

To rescreen the reviewed runs against the Anonymous Shops overlay, export that
mesh as an identity-node GLB with material baking disabled, then run
`python Tools/CityPCG/filter_protected_frontages.py ArtDirection/CityPCG/Inputs/gray_london_batch02_frontages.json Saved/CityPCG/AnonymousShops_Tile_p03_p00.glb Saved/CityPCG/gray_london_batch02_protected.json --overlay-origin-m 3000 0 0`.

Run `python Tools/CityPCG/plan_facades.py ArtDirection/CityPCG/Inputs/gray_london_batch02_frontages.json Saved/CityPCG/gray_london_batch02_plan.json --cell-size-m 160 --cell-budget 350 --max-storeys 8`.
This emits 179 instances in `x19_y2` and 229 in `x21_y2`.

## Reproduce and scale

1. In the Gray London editor load the named OSM tile, then execute
   `Tools/CityPCG/export_geodata_tiles_unreal.py` and call
   `export_tiles(["Tile_p03_p00"])`. It exports GLB and source metadata to
   `Saved/CityPCG`. It requires a stopped PIE session and rejects rotated or
   scaled tile components. The source geometry stays in the editor.
2. Run
   `python Tools/CityPCG/extract_tile_frontages.py Saved/CityPCG/Tile_p03_p00.glb ArtDirection/CityPCG/Inputs/mark_lane_north_survey.json ArtDirection/CityPCG/Inputs/mark_lane_north_frontages.json`.
3. In Unreal, call `verify_frontages` from
   `Tools/CityPCG/verify_tile_frontages_unreal.py` with the output path. It
   performs read-only collision checks on up to 50 wall runs per call.

For per-tile batches, replace the manual `road` guide with the `road_primitive`
value recorded by the exporter. The extractor finds nearby road surfaces and
rejects walls facing away from them or blocked by another source wall. A
1 km² test on Tile_p03_p00 produced 802 candidate wall runs totaling 10.88 km
in 2.79 seconds offline. These are candidate runs rather than a building count
or a reviewed city deployment.

Use `bounds` for reviewed district subsets and `exclude_bounds` or
`exclude_ids` for landmarks, hand-placed facades and other protected pieces.
Bounds are `[min_x, min_y, max_x, max_y]` in Unreal local metres. The exporter
records the component origin in the same units. It uses only the ordinary
`GL_Facade` primitive; tiles with unusual section/slot mappings need separate
review. In the full-tile benchmark the separate `GL_CentralFacade` primitive
was excluded. The source tile is a combined mesh, so the extractor cannot
recover cadastral boundaries or historical dates from its triangles.
