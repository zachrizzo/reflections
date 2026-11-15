# Medieval opening ground

This 15.12 × 12.13 m cosmetic patch replaces the asphalt appearance at the Gray London opening with original rounded cobbles, compacted earth, wheel-worn strips, and a damp drainage seam. The art is a period interpretation. It uses custom base color, normal, and roughness maps, with no photographic texture input.

The new surface fits directly over the existing pavement. The lower layer covers the city ground at Z=10 cm. The upper layer uses clipped triangles from `Tile_p03_p00` at Z=28 cm. The visual mesh is 0.7 cm above both surfaces and has collision disabled. The existing roads and ground supply gameplay collision. All 74 sampled editor traces inside the mesh outline matched its two underlying surface heights.

The level actor is `GL_1450_Opening_PackedEarthAndCobbles` at `(329290, 31090, 0)` cm. Its external package is `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/C/V9/RPMHW11FBF7IBV8LMPS7BA`. Its five supporting asset packages live under `/Game/GrayLondon/MedievalOpening/Ground/SM_GL1450_OpeningGround`. The source GLB round-tripped through Blender with ten upward-facing triangles, a UV set, and three embedded maps.

Rebuild from the repository root with NumPy and Pillow. Use the original `OSM Tile_p03_p00` export with its Unreal axis convention.

```powershell
python ArtDirection/CityPCG/MedievalOpening/Ground/build_opening_ground.py Saved/CityPCG/Tile_p03_p00.glb ArtDirection/CityPCG/MedievalOpening/Ground/Source
```

## West district street section

`west_street_section.json` selects a 17.57 × 10.55 m street stretch along four northeast-facing `x20_y1` frontages. `plan_street_patch.py` follows the source road triangles for its upper mesh, proposes a lower City ground layer, and maps both to the opening's cobble material with the drainage seam running along the street. The plan keeps the visual mesh 0.7 cm above the proposed surfaces and specifies `NoCollision`.

```powershell
python ArtDirection/CityPCG/MedievalOpening/Ground/plan_street_patch.py Saved/CityPCG/Tile_p03_p00.glb Saved/CityPCG/medieval_west_ground_plan.json
```

The pinned source export should produce eight patches and 157 floor probes with `trace_status` set to `requires_live_editor_traces`. In Unreal, load the pinned tile and call `collect_street_floor_traces.collect(plan_path, output_path)` outside PIE. Pass the observed output to the planner with `--observations`. The planner then requires every probe to agree on the source actor, height within 0.8 cm, and upward normal. The lower layer stays provisional until those observations pass. This stage writes only geometry and checks for review.
