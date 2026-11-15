# Reviewed market-prop trial

This isolated draft imports image-to-3D candidates one at a time into
`/Game/GrayLondon/MedievalOpening/MarketDressing/TripoSR` and can author a
separate PCG graph in `/Game/GrayLondon/Maps/MedievalLondon`. It does not run
on Python import, start PIE, replace existing assets, or save unrelated
packages. Live work requires the `codex-gray-london` editor lease whose purpose
is `Dense Medieval London streets and dressing`, that exact map, and no PIE.
The authoring operator must judge available memory for the actual files.

Raw candidates go in `Saved/CityPCG/TripoSRMarketSources/<Name>.glb`. Review
the complete model, its unseen sides and orientation first, and independently
verify its SHA-256. The reviewed TripoSR source is Z-up; passing
`axis_conversion='z_up_to_gltf_y_up'` explicitly opts into a -90 degree X
rotation in a separate normalized GLB. The original is not changed. Other
orientation/layouts fail closed pending review. For example, in the editor:

```python
import import_triposr_market_unreal as market_import
result = market_import.run('BakersTray', '<raw sha256>',
    source_visually_reviewed=True, axis_conversion='z_up_to_gltf_y_up')
```

Interchange imports one static mesh with vertex colors explicitly set to
Replace, no material/texture/animation import and no generated collision.
For sources without normals Unreal is asked to generate them. A new owned
opaque material connects VertexColor's unnamed output to Base Color, uses
roughness 0.8, and is assigned to every mesh slot. Before saving, a fresh UE
GLB export with vertex-color export enabled must match every oriented source
triangle and associated RGB8 value; corner movement is limited to 1e-6 glTF
units. That verifies the color data, not the visual lighting or semantic
quality of the generated unseen surfaces. New imports use the deterministic
local source `Saved/CityPCG/TripoSRMarketSources/Normalized/<Name>_<first 16
raw SHA characters>.glb`. If that local copy is missing, run
`market_import.prepare_normalized_source('<Name>', '<raw sha256>')` to
recreate and verify it from the original. The earlier BakersTray and MarketWell
trials used temporary normalized paths; their existing Unreal import metadata
still needs a separately coordinated update before automatic reimport. The
preserved original and provenance remain the authority.

After the actual asset has been saved, `place_triposr_market_pcg.survey_one`
can read a chosen live stall instance, floor hit, nearby static mesh bounds
and story markers to return a candidate plan. The caller supplies the offset
and visually reviews it; the survey does not create anything. The curved
main-street 2.5 m reserve and marker setbacks are conservative geometry
checks. Only the exact known paving mesh can be treated as cosmetic when its
top is within 12 cm of the traced floor, and any requested cosmetic prop
offset is limited to 12 cm. These checks are not navigation or collision
acceptance for all geometry types.

The separate asynchronous `run(plan, placement_visually_reviewed=True)` creates
a new graph and generates non-colliding PCG instances only after the live
survey is visually reviewed. It rechecks the
source and current mesh/color, anchor, material, floor, story markers, lane,
scene envelopes, lease, and full generated transforms. It explicitly saves
the new graph and the owned non-World-Partition town map only. If it fails,
new objects may remain unsaved in memory and an interrupted async generation
may need coordinated cleanup; no broad Save All or automatic deletion is
performed. The PCG authoring path and actual in-game appearance, persistence,
navigation, and multiplayer/build behavior still require a live trial.

Run the small offline checks with:

```text
python -B Tools/CityPCG/test_triposr_market_geometry.py -v
python -O -B Tools/CityPCG/test_triposr_market_geometry.py -v
```
