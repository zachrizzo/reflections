# West Mark Lane saved source actor

`verify_west_mark_lane_saved_actor.py` reads the exact pinned external actor
package and verifies its package version and name/import tables, the saved
`StaticMesh` reference, its five serialized material overrides, a native
`RelativeLocation` vector, and the component's property terminator. It uses
the nearby saved-section verifier's narrow UE parsing helpers; neither script
starts or communicates with Unreal or writes to the project.

```powershell
python Tools/CityPCG/verify_west_mark_lane_saved_actor.py
python Tools/CityPCG/test_verify_west_mark_lane_saved_actor.py -v
python -O Tools/CityPCG/test_verify_west_mark_lane_saved_actor.py -v
```

The saved mesh reference is `/Game/GrayLondon/Geodata/Tiles/Tile_p03_p00`.
Its five material overrides match the first five saved replacement material
paths. The serialized relative location is `(300000, 0, 0)` centimetres; the
override array has no sixth entry. This describes only that specific actor's
saved bytes. It does not establish the current live actor, its resulting
world transform, loaded component overrides, or current asset geometry. It
does not infer rotation or scale. The pilot remains disabled pending the
allocated editor verification, visual checks, collision and gameplay checks.
