# North Market massing studies

These four OBJ files are lightweight, closed silhouettes for the two surveyed
North Market blocks on `Tile_p03_p01`. The manifest records each file's hash,
surveyed world pivot and yaw. They are review-only: they have no doors, windows,
textures or gameplay collision, and have not been imported into Unreal. The
full-detail medieval buildings still need to be generated and reviewed.

The inputs and exact footprints are in `FollowOn20261115`. The original
tile's Unreal section mapping, nearby actors, routes and source collision still
need live verification before replacing any geometry.

From the project root, regenerate into a fresh Saved folder:

```powershell
python -B Tools/CityPCG/build_north_market_massing.py --output Saved/CityPCG/NorthMarketMassing_review
python -B -m unittest discover -s Tools/CityPCG -p test_build_north_market_massing.py -v
```

The generator checks plan-to-candidate footprints, pivots, yaw and height,
then checks closed edges, winding and positive volume. The tests independently
read the OBJ vertices, UVs and normals. The source GLB was not reread by this
massing build; this is not an in-game or visual-quality approval.
