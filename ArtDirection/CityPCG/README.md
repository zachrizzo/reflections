# Gray London building generation

Use the shapes and locations of the shipped Gray London blocks as the first
placement source. Add visible architectural detail with a small number of shared
meshes. Each point carries its mesh, rotation, scale, seed, and source wall ID.
The Unreal bridge places the points through native PCG and groups instances by
mesh in a spatially loaded World Partition cell.

## Mark Lane North pilot

The input contains seven verified runs of ordinary city wall along a 78 m
corridor. The walls came from the shipped `Tile_p03_p00` mesh. The frontage
survey records the source section, road exposure, and trace checks. The style
override file assigns brick offices, pale stone arches, and postwar glazing
as an art pass. These assignments are estimates for the pilot.

```powershell
python Tools/CityPCG/plan_facades.py ArtDirection/CityPCG/Inputs/mark_lane_north_frontages.json ArtDirection/CityPCG/Inputs/mark_lane_north_pcg.json --overrides ArtDirection/CityPCG/Inputs/mark_lane_north_style.json --max-storeys 12
```

This produces 125 instances in cell `x20_y2`. The planner uses the measured wall
length and height to fit bays and storeys. Ground modules have selected entrance
bays. The existing city geometry supplies the massing, roof, and gameplay
collision. The local authority for kit dimensions and materials is
`Kit/kit_manifest.json`.

The pilot is generated and saved in `GrayLondon_Geodata`. Its spatial actor is
`PCG_GL_Facades_x20_y2`. Unreal reported 125 instances across seven ISM
components, and all instance transforms matched the plan. The components use
`NoCollision` and do not affect navigation. Lit editor screenshots at the same
camera position are in `Saved/Screenshots/WindowsEditor/mark_lane_north_pcg.png`
and `mark_lane_north_before_pcg.png`. Play and streaming checks are still due.

The next reviewed batch added 179 modules in `x19_y2` and 229 in `x21_y2`.
Gray London now has 533 saved modules across these three cells. Those two
cells use a district palette from the source survey and omit entrance bays.
The [input guide](Inputs/README.md) records the repeatable plan, wall and actor
checks, and protection mask. A lit Unreal view of the east cell is at
`Saved/Screenshots/WindowsEditor/gray_london_pcg_east_cell.png`.

### Generate another cell

1. Use `Tools/CityPCG/extract_tile_frontages.py` with a source-model GLB of the
   tile currently assigned to its map actor. Pass its transform and verify the
   source sections. Run automatic road exposure for candidates, then apply
   exclusions and validate a sample of the walls against the editor.
2. Run `Tools/CityPCG/plan_facades.py` on the reviewed input. Use the optional
   style overrides for reference-backed materials and entrance positions that
   can be identified.
3. In Editor Python, use `Tools/CityPCG/import_facade_kit.py` to import the shared
   kit when needed. Call `await run(plan_path)` in `apply_facade_pcg.py` for a
   read-only summary. Call `await run(plan_path, mode='save', cell_id='x20_y2')`
   with the new cell ID when ready. The bridge validates the instance counts
   and saves that graph and actor by exact package. It rejects existing cells.
   For a reviewed selection, call `await save_reviewed_cells(plan_path, cell_ids)`.
   The batch verifies its selections and kit paths before saving, then commits
   each cell separately so an interruption leaves a known list of saved cells.

Automatic road exposure found 802 wall candidates covering 10.88 km of facade
span in the 1 km² `Tile_p03_p00`. Extracting and filtering that mesh took about
three seconds offline. Planning four storeys per wall produced 10,331 points
across 49 cells, with a peak of 656 in one cell. These counts are a planning
benchmark. The full tile still needs protected-building masks and an Unreal
performance test before being generated.

## From a city model to a street view

- **Measure the envelope.** Keep a stable building ID, footprint, street-facing
  sections, ground level, eaves, and roof form. The project uses local coordinates
  derived from British National Grid, with Unreal X east, Y north, and centimetres
  in engine. Recover placement from the live tile variant and its actor transform.
  The raw asset name alone can point to a superseded version of a tile.
- **Use a basis that matches the period.** The current city is based on
  OpenStreetMap and has documented 2009-era exclusions. Ordnance Survey building
  parts can supply measured height and roof attributes where available. Environment
  Agency LiDAR surface and terrain models can help check heights. Check the survey
  dates against the game's period before applying measurements. [OS NGD building
  attributes](https://docs.os.uk/osngd/using-os-ngd-data/os-ngd-buildings/building-attribution)
  · [Environment Agency surface model](https://www.data.gov.uk/dataset/cf3f1137-c12b-44a1-a835-e80fe4a60b92/lidar-composite-dsm-2022-1m)
- **Add detail where there is evidence.** Follow the surveyed form and archived
  elevation for recognisable buildings. Use period photos to select materials and
  window patterns for ordinary blocks. Have an artist approve reference sets by
  district and keep uncertainties in the data. The CityGML approach is a useful
  reference for matching the level of detail to available evidence, from simple
  solids to architectural geometry. [OGC CityGML users guide](https://docs.ogc.org/guides/20-066.html)
- **Generate by cell.** Use selected block and street inputs in parallel. Keep
  background roofs and skylines separate from street-level facade modules, then
  profile the instance counts, effects of streaming, and HLOD before raising the
  citywide coverage. Place base, upper, and entrance modules deterministically.
  An instance cap fails a cell early so the author can revise density. [Unreal PCG
  generation modes](https://dev.epicgames.com/documentation/unreal-engine/using-pcg-generation-modes-in-unreal-engine)
- **Put exact buildings on their own pipeline.** Keep known landmarks and previous
  handcrafted changes in the exclusion set. For a unique building, image-to-3D
  can propose a shell or generate ornament from clean views. Verify all visible
  elevations, passage clearance, and roof silhouette against the footprint and
  photographs before replacing any existing geometry. The No. 27 study shows this
  workflow and the need to isolate the old building inside a combined tile.

Base city geometry © OpenStreetMap contributors, ODbL 1.0. See the project's
Gray London data-source notes for the existing tile and asset provenance.
