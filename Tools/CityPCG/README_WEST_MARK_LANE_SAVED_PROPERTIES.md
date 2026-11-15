# West Mark Lane saved section properties

This read-only check verifies the serialized section and material metadata of
two **exact, SHA-256-pinned files**: the original `Tile_p03_p00.uasset` and
the imported `SM_GLMedieval_WestBlockTile.uasset`. It writes no files, uses
only Python's standard library, and does not start or communicate with Unreal.

```powershell
python Tools/CityPCG/verify_west_mark_lane_saved_sections.py
python Tools/CityPCG/test_verify_west_mark_lane_saved_sections.py -v
python -O Tools/CityPCG/test_verify_west_mark_lane_saved_sections.py -v
```

For both saved assets, `SectionInfoMap` contains six distinct keys, 0–5, with
matching material indices and collision flags enabled. Unreal 5.9's
`Engine/Source/Runtime/Engine/Private/StaticMesh.cpp:6795` encodes a key as
`((LODIndex & 0xffff) << 16) | (SectionIndex & 0xffff)`, so these serialized
keys describe LOD 0 sections 0–5. Their saved and imported slot names are, in
order, `GL_Facade`, `GL_Roof`, `GL_Road`, `GL_Park`, `GL_Water`, and
`GL_CentralFacade`.

The replacement's six saved material imports resolve respectively to
`/Game/GrayLondon/Geodata/Materials/M_ResidentialFacadeTrial`, `M_OSM_Roof`,
`M_OSM_Road`, `M_OSM_Park`, `M_WaterBroadTrial`, and
`/Game/GrayLondon/Geodata/Materials/CentralSelective/M_CentralStoneWindows`
(the unqualified names share the first material directory). The original's
first five saved material references point to the engine's WorldGridMaterial;
its sixth points to the same central material.

The parser is deliberately limited to the pinned UE package layouts. It
checks the package versions, names and their terminators, complete tagged
type trees and bounds, duplicate keys and properties, section-map and nested
struct terminators, slot and imported-slot names, and each material's import
class, outer package, and object name. The unrelated native `ExtendedBounds`
value is bounded but not decoded. The command refuses changed package bytes;
`parse_structure` alone is a test helper and is not authenticated evidence.

These findings describe saved bytes only. The actual live post-load section
and render mapping, component material overrides, actor and transform, and
the replacement mesh's geometry, UVs, collision behavior, navigation,
streaming, visuals and gameplay remain separate checks. Keep the pilot off
until the required allocated editor handoff and verification. The complementary
source-mesh/GLB geometry evidence is documented in
`README_UNREAL_SOURCE_GROUPS_OFFLINE.md`.
