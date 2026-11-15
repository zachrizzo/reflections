# East of Royal Mint Court whole-building survey

The conservative p04_p00 interior scan recovered 45 candidate shells. Eight
road-connected groups contain 34 of them. The preferred next block is
`block_7113aff9ea1e`, four ordinary shells east of Royal Mint Court with
771.084 m² of combined footprint. It clears the nearest conservative story
marker buffer by 79.503 m. The geometry plan passed 225 road samples along
50.542 m of links. The nearest sampled point is 0.475 m from a source shell.
The exported road is Z 0.28 m.

`east_tower_whole_buildings_candidate.json` pins the exact geometry and
anonymous shop export. The scratch derivative removed 80 wall triangles
and 32 roof triangles and preserved every road, park, water, and authored
central facade triangle. The plan and mask are review-only.

## Coverage and limits

The preferred region is inside the wider survey bounds, which reserve at
least 150 m from the nominal p04_p00 tile edges. The nominated candidates
also avoid the recorded Tower and St Katharine protection areas, the
existing Tower and St Katharine PCG, the published St Katharine route, and
the additional Royal Mint Court and dock reservations.

The source tile and matching Anonymous Shops geometry are available. The
p03_p00 and p03_p01 neighbor roof exports were checked. Their shop overlays
are wholly west of the screening area, with eastern extents at X 3335.285 m
and X 3477.428 m. The p03_p00 protected central façade ends at X 3462.227 m.
No external roof overlapped the preferred block in the available exports.

p04_p01, p04_m01 and p05_p00 have project packages and no local paired
roof and overlay exports for this survey. p03_m01, p05_m01 and p05_p01
are also absent as exports. Asset descriptors and visual checks still need
to confirm any geometry extending across those seams and any site-specific
authored actors. Live tool use must verify the door strips, road floor and
capsule clearance, quest paths and rooftop traversal before authorizing any
replacement or tile swap.

## Reproduce

Use the p04_p00 GLB under `Saved/CityPCG/MedievalSurvey`. The similarly named
export one level up has different GLB bytes. Its ordered world-space
triangle coordinates match all six sections, but it does not match the file
hash in the inventory. Keep the exact export pinned.

```powershell
$city = 'Saved/CityPCG'
$survey = "$city/MedievalSurvey"
$art = 'ArtDirection/CityPCG/MedievalOpening'
$inputArgs = @(
    "$survey/Tile_p04_p00.glb",
    "$survey/Tile_p04_p00.assets.json",
    "$survey/Tile_p04_p00_building_inventory.json",
    "$survey/AnonymousShops_Tile_p04_p00.glb"
)
$neighbors = @(
    '--neighbor', "$city/Tile_p03_p00.glb", "$city/Tile_p03_p00.asset.json",
    '--neighbor', "$survey/Tile_p03_p01.glb", "$survey/Tile_p03_p01.assets.json"
)

python Tools/CityPCG/select_whole_building_blocks.py @inputArgs "$art/east_tower_whole_building_blocks_settings.json" "$survey/Tile_p04_p00_next_building_blocks.json" @neighbors

$focus = Get-Content "$art/east_tower_whole_building_blocks_settings.json" -Raw | ConvertFrom-Json
$focus.tile_bounds_m.Tile_p04_p00 = @(4008, 245, 4081, 305)
$focus | ConvertTo-Json -Depth 10 | Set-Content "$survey/east_tower_priority_settings.json" -Encoding utf8
python Tools/CityPCG/select_whole_building_blocks.py @inputArgs "$survey/east_tower_priority_settings.json" "$survey/Tile_p04_p00_east_tower_priority.json" @neighbors --candidate block_7113aff9ea1e "$art/east_tower_whole_buildings_candidate.json"
python Tools/CityPCG/plan_replacement_block.py "$survey/Tile_p04_p00.glb" "$art/east_tower_whole_buildings_candidate.json" "$survey/east_tower_whole_building_plan.json"
```
