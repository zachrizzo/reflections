# First-view building verification

Run from the project root with the pinned `Saved/CityPCG/Tile_p03_p00.glb`
export and its `Tile_p03_p00.asset.json` metadata.

```powershell
python -B Tools/CityPCG/verify_spawn_building_review.py
```

The verifier reads `spawn_first_view_whole_building_review.json` and prints
its results to standard output. It requires `blocked_review_only` status,
the pinned source hash, and the unique recorded wall and roof face
signatures. It rechecks the closed cap, eight retained party-wall
triangles, all 23 spawn-eye rays, and the current quest-marker and
Weigh-House footprint intersections.

Thirteen rays hit the shell. Its footprint overlaps 255.791521 m² of
the protected Weigh-House bounds. The FirstPage and Frank Dunning marker
projections are inside. This check cannot establish their current 3D
positions, live camera occlusion, or authored overlay state. A successful
run confirms the blocked review and writes no files or replacement mask.
