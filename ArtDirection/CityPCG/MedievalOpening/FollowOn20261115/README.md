# Two follow-on blocks on tile p03_p01

These are review-only inputs for four complete medieval replacement buildings
on two more road-connected blocks. East and west describe their positions in
the project's local coordinate frame, not a claim about historical addresses.
The candidates pin the original tile and anonymous-shop export hashes, record
their surveyed footprints, and retain the source road and landmark sections.
Both blocks were screened again against the current story, corridor, overlay
and neighboring-tile inputs on 15 November 2026.

The two plans cover four shells and 171 road samples. An offline cumulative
preflight combining these blocks with the earlier Leadenhall, West Mark Lane,
West Connector and Royal Mint candidates checked 18 buildings across three
tiles. On p03_p01 its combined mask contains eight buildings, 200 ordinary
wall triangles and 86 roof triangles; the protected sections remain intact.
This is not a live approval, an imported mesh, or proof of navigation.

## Generate the source meshes

From the project root, use an idle build window with sufficient memory. Each
output directory must be new. The east recipe intentionally gives its workshop
a different palette from its neighboring trading range. Both workflows run
the generator's Blender round-trip and prepared-FBX audits.

```powershell
$art = 'ArtDirection/CityPCG/MedievalOpening/FollowOn20261115'
$out = 'Saved/CityPCG/WholeBuildings'
$blender = 'C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe'
& $blender --background --threads 2 --factory-startup --python-exit-code 1 --python 'Tools/CityPCG/build_whole_buildings_blender.py' -- --candidate "$art/north_market_east_candidate_20261115.json" --plan "$art/north_market_east_plan_20261115.json" --style-overrides "$art/north_market_east_style_override_20261115.json" --output "$out/NorthMarketEast" --prefix NorthMarketEast --prepare-unreal
& $blender --background --threads 2 --factory-startup --python-exit-code 1 --python 'Tools/CityPCG/build_whole_buildings_blender.py' -- --candidate "$art/north_market_west_candidate_20261115.json" --plan "$art/north_market_west_plan_20261115.json" --output "$out/NorthMarketWest" --prefix NorthMarketWest --prepare-unreal
```

Before replacing anything, review live actor descriptors and overlapping
authored structures, then test the entry approaches, streets, roofs, collision,
navigation and quest routes in Gray London. Build the filtered source tile
from the **complete accepted mask** for p03_p01 rather than from either new
block alone. Keep the original tile available for rollback.
