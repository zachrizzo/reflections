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

The pinned source export should produce eight patches and 157 floor probes with `trace_status` set to `requires_live_editor_traces`. In Unreal, load the pinned tile and call `collect_street_floor_traces.collect(plan_path, output_path)` outside PIE. Pass the observed output to the planner with `--observations`. The planner requires every probe to agree on the source actor, height within 0.8 cm, and upward normal. The lower layer stays provisional until those observations pass.

```powershell
python ArtDirection/CityPCG/MedievalOpening/Ground/plan_street_patch.py Saved/CityPCG/Tile_p03_p00.glb Saved/CityPCG/medieval_west_ground_verified_plan.json --observations Saved/CityPCG/medieval_west_ground_live_floors.json
python ArtDirection/CityPCG/MedievalOpening/Ground/export_street_patch.py Saved/CityPCG/medieval_west_ground_verified_plan.json ArtDirection/CityPCG/MedievalOpening/Ground/West
```

All 157 editor traces passed for the installed west stretch. It uses the 13-triangle GLB in `West/`, with one UV set, and shares the opening's existing PBR material. To install it, call `apply_west_street_patch.apply(verified_plan_path)` in the Gray London editor outside PIE. It checks the plan and source mesh hashes, repeats all live floor probes before writing, and saves only the mesh and its external actor package. The actor is `GL_1450_West_StreetPaving` at `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/6/LE/5YHYVTTHAU8OXRS48K6MUE`, with collision disabled.

## Leadenhall west approach

`leadenhall_west_section.json` clips an 18.48 × 3.55 m approach strip along three frontage runs. It covers the exposed road outside the arcade and leaves the threshold clear. All 66 editor traces matched the pinned `OSM Tile_p03_p01` road surface at Z=28 cm. The nine-triangle mesh uses the opening cobble material and keeps the existing road collision.

```powershell
$ground = 'ArtDirection/CityPCG/MedievalOpening/Ground'
$tile = 'Saved/CityPCG/MedievalSurvey/Tile_p03_p01.glb'
$survey = 'Saved/CityPCG/medieval_lantern_row_frontages.json'
$plan = 'Saved/CityPCG/leadenhall_west_paving_candidate_plan.json'
$floor = 'Saved/CityPCG/leadenhall_west_paving_live_floors.json'
$verified = 'Saved/CityPCG/leadenhall_west_paving_verified_plan.json'
python Tools/CityPCG/survey_medieval_corridor.py 'Saved/CityPCG/MedievalSurvey/Tile_p03_p01.assets.json' 'ArtDirection/CityPCG/MedievalOpening/lantern_row_corridor.json' $survey
python "$ground/plan_street_patch.py" $tile $plan --section "$ground/leadenhall_west_section.json" --survey $survey
```

With `OSM Tile_p03_p01` loaded in the Gray London editor outside PIE, run `collect_street_floor_traces.collect(plan_path, output_path)` using `$plan` and `$floor`. Then rebuild the source GLB and manifest.

```powershell
python "$ground/plan_street_patch.py" $tile $verified --section "$ground/leadenhall_west_section.json" --survey $survey --observations $floor
python "$ground/export_street_patch.py" $verified "$ground/Leadenhall" --asset SM_GL1450_LeadenhallWestApproachPaving --manifest leadenhall_street_mesh.json
```

Call `apply_west_street_patch.apply_leadenhall(verified_plan_path)` in the Gray London editor outside PIE. It repeats the floor traces and uses the same exact-package write path as the west stretch. The installed `GL_1450_Leadenhall_WestApproachPaving` actor has external package `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/7/TF/15RV4R9DXJFFU22AL3MZRW`.

## Tower Hill approach

`tower_approach_section.json` follows the verified `Tile_p03_p00_9429689c5141` frontage. The 15.30 × 3.05 m strip stays outside the protected landmark footprints and avoids the overlapping source road triangles at the far edge. All 58 floor probes hit `OSM Tile_p03_p00` at Z=28 cm. The 12-triangle mesh reuses the opening cobble material and has collision disabled.

```powershell
$ground = 'ArtDirection/CityPCG/MedievalOpening/Ground'
$tile = 'Saved/CityPCG/Tile_p03_p00.glb'
$survey = 'Saved/CityPCG/medieval_tower_approach_west_frontages.json'
$plan = 'Saved/CityPCG/tower_approach_paving_candidate.json'
$floor = 'Saved/CityPCG/tower_approach_paving_floors.json'
$verified = 'Saved/CityPCG/tower_approach_paving_verified.json'
python Tools/CityPCG/survey_medieval_corridor.py 'Saved/CityPCG/Tile_p03_p00.assets.json' 'ArtDirection/CityPCG/MedievalOpening/tower_approach_west_corridor.json' $survey
python "$ground/plan_street_patch.py" $tile $plan --section "$ground/tower_approach_section.json" --survey $survey
```

Collect `$floor` from `$plan` with `collect_street_floor_traces.collect` in the Gray London editor with `OSM Tile_p03_p00` loaded outside PIE.

```powershell
python "$ground/plan_street_patch.py" $tile $verified --section "$ground/tower_approach_section.json" --survey $survey --observations $floor
python "$ground/export_street_patch.py" $verified "$ground/TowerApproach" --asset SM_GL1450_TowerApproachPaving --manifest tower_approach_mesh.json
```

`apply_west_street_patch.apply_tower_approach(verified_plan_path)` repeats the floor trace checks and installs `GL_1450_TowerApproach_Paving`. The exact actor package is `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/3/A0/4CPCXST74RGMVAB4XQ8TNK`.
