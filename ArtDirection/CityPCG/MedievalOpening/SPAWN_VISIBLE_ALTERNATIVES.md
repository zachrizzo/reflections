# Opening-visible whole-building alternatives

The saved PIE audit records `LT_PlayerStart_Intro` at (3292.9, 310.9, 1.1) m
and the gameplay camera at (3291.076, 310.977, 1.654) m with yaw 13.5°.
The opening capture shows the east frontage behind the market stall. An
offline sweep from the saved camera hit three nearby source shells. Each
fails the current replacement guards.

| Shell | Horizontal first hits | Guard |
| --- | ---: | --- |
| South return | 7 | `Home_winnie_cobb` projects inside. Six of eight wall triangles and all four matching roof triangles have duplicate source signatures. The roof geometry describes two coincident covers. The two `MedievalOpening_South` façades depend on this frontage. |
| First-view corner | 11 | `CutsceneAnchor_FirstPage` and `Home_frank_dunning` project inside. Its footprint intersects 255.791521 m² of the protected Weigh-House bounds. The stair projection is 0.744 m from the footprint. |
| North return | 5 | `Home_ivy_harker` projects inside. Its footprint intersects 36.511852 m² of the same protected bounds and supports `MedievalOpening_East_04–06` and 11 published Mark Lane PCG placements. |

The scan replays 23 yaw samples from −44° to +44° relative to the camera
heading, at elevations −12°, 0°, 12°, 24°, and 36°. No other building
triangle was the first hit within 70 m. These tests use two-sided
triangles in the shipped p03_p00 export. The saved audit supplies camera
position and yaw. The sampled elevations cover a range around horizontal
and live authored occlusion requires a fresh capture.

```powershell
python -B Tools/CityPCG/verify_spawn_building_review.py
python -B Tools/CityPCG/scan_opening_view_alternatives.py
```

The scan prints JSON and reads the pinned source tile, the existing
first-view review, and `Saved/CityPCG/rebuilt_play_audit.json`. The original
play capture is `Saved/MedievalOpening/gray_london_medieval_spawn_play.png`.

## Live review of the blocked first-view corner

1. Under the active lease, confirm the exact source tile actor and export
   signature. Query saved World Partition descriptors in centimetres from
   (329916.9, 30221.1, −280) to (334355.3, 32728.3, 2300) for the corner and
   its 4 m margin. Survey the adjoining protected Seething Lane and
   Weigh-House bounds as well. Record actor packages, full 3D bounds, and
   data layers. Check the three East bay packages, Wheatsheaf mount, legacy
   shopfronts and fascias, market props, and road and paving assets.
2. For the current story map, record actual transforms and associated
   actor or set-piece bounds for `CutsceneAnchor_FirstPage`,
   `Home_frank_dunning`, `Mk_Pew_Stair_WeighHouse`,
   `Mk_Pew_Square_WeighHouse`, and `Mk_Gilt_Inn_Lamplight`.
   Review the stair, roof, cellar and Home behavior with the quest owner.
   Keep the marker, footprint and route protections until this is resolved.
3. During an authorized gameplay baseline, capture the original spawn and
   record the real camera transform, FOV, and hero capsule dimensions.
   Check floor and sidewall traces, or sweep the current pawn capsule, on
   the spawn-to-Mark Lane and Weigh-House approaches. Sample original
   collision at all three sealed party edges and the roof. Keep the
   FirstPage and Home interactions available through the baseline run.
4. Keep the plot blocked until ownership of the party walls and quest
   volumes is resolved in the loaded map. Any later replacement proposal
   needs the same 3D checks against its geometry and a matched gameplay
   capture. The existing review file lists retained wall triangles and
   exact authored package paths for that comparison.
