# Cumulative filtered tiles for grouped buildings

`build_grouped_tile_derivatives.py` builds review-only GLB copies of the
original geodata tiles with exactly the surveyed building faces removed. It
never changes the source GLB, Unreal assets, or the map. The default masks
match the nine grouped-building GLBs currently checked into `GroupedPrototype`:

| Tile | Removed building shells | Required grouped meshes |
| --- | ---: | ---: |
| `Tile_p03_p00` | 6 | 5 |
| `Tile_p03_p01` | 4 | 2 |
| `Tile_p04_p00` | 4 | 2 |

The builder requires the exact source GLB hashes and metadata named in the
grouped masks. The two `p04_p00` exports on this machine have different hashes;
the default source is `Saved/CityPCG/MedievalSurvey/Tile_p04_p00.glb`, the
revision pinned by the east Royal Mint candidate. `--source TILE GLB METADATA`
can select an equivalent exact copy and can be repeated for other tiles.

Before touching the tile GLBs, and again before each tile and publication,
the builder checks for an active shared-editor lease and the first explicit
train status in `Saved/PIE_QUEUE.md`. It refuses a train marked `BUILDING` or
an unreadable, missing or unrecognized queue status; older train entries do
not override the leading status. These are snapshot checks, so coordinate with
the orchestrator before starting: they do not prevent a train starting midway
through a tile. The builder also requires at least 4 GiB of free physical
memory and 10 GiB of available system commit headroom. It processes tiles
sequentially. Choose a fresh output folder under this project's `Saved`:

```powershell
$out = 'Saved/CityPCG/GroupedImport/Filtered6_4_4'
python -B Tools/CityPCG/build_grouped_tile_derivatives.py --output $out
python -B -m unittest discover -s Tools/CityPCG -p test_build_grouped_tile_derivatives.py -v
```

Each tile receives its exact cumulative mask, normalized original metadata,
filtered GLB, audit, and a second GLB whose material names match the original
Unreal slots. `tile_derivatives.json` records SHA-256 hashes, the exact grouped
cells needed with each mask, and per-section triangle counts. The original GLB
binary prefix containing vertices, UVs, normals and embedded images is retained;
the independent readback checks every retained index, source material property
and each primitive designated protected by the export metadata. The GLB
primitives labelled road, park, water and authored central façade remain
unchanged in the file. **Their mapping to the original Unreal sections has
not yet been independently verified.** Several GLB primitives share the same
material, so names and section counts alone do not prove source-section order.
A partial or failed run does not publish its final folder.
Its uniquely named `grouped_tile_filters_*` scratch directory is left intact
for inspection; the builder never recursively deletes it. After successful
publication, it removes only the verified, empty scratch directory. The
builder checks the original resolved `Saved`, output-parent, staging and
destination paths again immediately before publishing. These checks do not
make concurrent filesystem redirects atomic: do not move or redirect `Saved`
or the output parent while a run is in progress.

## Separate eight-shell north-market variant

The two additional north-market candidates belong to `Tile_p03_p01`. This
command builds a **separate** eight-shell mask and filter, checked against the
18-building offline rollout evidence:

```powershell
$out = 'Saved/CityPCG/GroupedImport/FilteredP03P01_8_Unmatched'
$follow = 'ArtDirection/CityPCG/MedievalOpening/FollowOn20261115'
python -B Tools/CityPCG/build_grouped_tile_derivatives.py --output $out --tile Tile_p03_p01 `
  --additional-candidate "$follow/north_market_east_candidate_20261115.json" `
  --additional-candidate "$follow/north_market_west_candidate_20261115.json" `
  --extended-evidence 'Saved/CityPCG/MedievalSurvey/rollout_18_buildings_20261115.json'
```

The resulting manifest explicitly records that the eight-shell filter **does
not match** the current four-shell `p03_p01` grouped meshes. Generate and
review matching eight-shell building groups before considering the variant.

## Live integration is still required

These are offline mesh derivatives, not imported Unreal packages. The existing
West Mark Lane tile importer is hard-coded to the older three-shell pilot; do
not use it for these cumulative filters. Before accepting any mask, independently
verify its GLB primitive-to-live-Unreal section mapping for the exact pinned
export. A later importer must check each live source actor, bind the source's
exact section materials and collision settings,
round-trip the imported tile, and save only the explicitly owned packages.

World Partition and runtime PCG can load or clean up their cells on different
schedules. Keep the original tile and its collision active until the exact
matching cumulative filter **and every required grouped cell for that tile**
are registered and ready; restore the original if any part unloads or fails.
Check live street and story actors, capsule clearance, navigation, roof access,
stream-out/in, real-spawn visuals, LAN play and a refreshed standalone cook
before making the replacement visible to players.
