# North Market detailed medieval source meshes

These four unreviewed building source models contain the current procedural
late-medieval timber frames, windows, decorative closed doors, pitched roofs,
and chimneys for the surveyed east and west North Market blocks. The OBJ
files use `NorthMarketDetail.mtl` and the adjacent `Textures` directory.
`detailed_obj_manifest.json` records their source/output hashes, building
pivots, yaw angles, material roles, and geometry counts. Coordinates are
local metres, with +X toward the reviewed entrance and +Z up.

`FlatColorPreviews` shows the models with flat colors and no texture maps. Its
simple face-sorting renderer can display incorrect occlusion where polygons
overlap; the images are orientation aids, not final visual approval.

The OBJ files were built from the real generator with a lightweight Python
vector and ear-clipping substitute. They retain the generator's n-gons and
original winding. Blender's normal recalculation was not run; its roof
triangulation, numerical precision and UV results may differ. These files
are source art: they are not FBX exports, imported Unreal assets, collision,
or approval to replace a live city tile. The source GLB primitive-to-live
Unreal section mapping is unverified.

From the project root, independently re-create the detail geometry in memory
and check positions, n-gon winding, materials, UVs, surveyed transforms and
copied textures against this checked-in bundle:

```powershell
python -B Tools/CityPCG/verify_north_market_detail_obj.py `
  'ArtDirection/CityPCG/MedievalOpening/WholeBuildings/NorthMarketDetailedObj'
```

The verifier and regeneration require the pinned local source tile export
`Saved/CityPCG/MedievalSurvey/Tile_p03_p01.glb`, plus the repository's
reviewed candidates, plans, generator and texture files. `Saved` is not
included in this art bundle. Provenance comparisons allow only LF/CRLF
checkout differences; the bundle's `.gitattributes` keeps the OBJ and MTL
bytes consistent with their recorded hashes.

For production FBXs, use the isolated Blender workflow documented in
`ArtDirection/CityPCG/MedievalOpening/FollowOn20261115/README.md` when the
shared editor/build queue and resource guards permit. Review Blender's
round-trip channels, winding and normals, then verify Unreal materials,
collision, navigation, road and roof access, gameplay and streaming. Pair
with the independently verified complete cumulative mask and grouped meshes
for the tile; keep the original tile available until all replacements are
ready and safe to restore.
