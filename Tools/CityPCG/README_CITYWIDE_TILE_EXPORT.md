# Gray London citywide source export

`batch_export_geodata_unreal.py` prepares source GLBs for offline review in
small, resumable batches. It is read-only with respect to Unreal actors,
maps and asset packages; it never saves a package. It has been exercised with
fake Unreal objects, but it has **not** yet been run in the shared editor.

**All exports are provisional.** The existing exporter checks the number of
primitives and total triangles, but does not independently establish which
source Unreal section corresponds to each GLB primitive. A material name,
even a unique one, is not a section-geometry proof. This tool writes only
`.unverified.json` metadata, never `.asset.json` or `.assets.json` consumed by
the existing rollout audit. Before using any result to replace a tile, match
every source section to its GLB primitive by signed triangle geometry, resolve
ambiguities, and independently verify preservation of road geometry. Confirm
each source component's actual transform in the editor as well. An unloaded
actor's bounds can suggest a translation but cannot establish rotation or
scale; suggested values are explicitly labelled as unverified hypotheses.

## Short run in an allocated editor turn

The shared editor queue and explicit handoff govern access. After receiving
an allocated turn in `Saved/PIE_QUEUE.md`, acquire the owner's current
`Saved/PIE_LOCK.json` lease and use the already-running editor with Gray
London Geodata open, outside PIE. The script also requires at least 120
seconds remaining on that exact lease, 4 GiB free physical memory, and 10 GiB
free commit headroom. It checks the world, lock, and PIE state again during
export and stops if they change. It does not restart the editor or take a
lease.

In Unreal Python, for one existing tile:

```python
from pathlib import Path
import sys
import unreal

project = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(project / 'Tools/CityPCG'))
import batch_export_geodata_unreal as city_export

report = city_export.run_batch('codex-gray-london', batch_size=1,
                               names=['Tile_p03_p00'])
print(report)
```

For a citywide pass, omit `names` and use `batch_size=2` (the allowed range is
1–8). Repeated calls resume by checking source identity and export hashes;
to advance efficiently pass the returned `next_start_after` as `start_after`
on the next call. Failed tiles are recorded and skipped on later calls so
they do not block others. Review the failure before retrying it explicitly
with `names=[...]` and `retry_failed=True`. A retained completed attempt is
never overwritten; changed or ambiguous evidence requires manual review.

The on-disk snapshot used during preparation had 117 tile meshes, 78 matching
anonymous-commercial overlays, 39 tiles without one, and three overlay assets
without a matching tile. Inventory is checked afresh against the Asset
Registry each time; the summary reports actual counts and orphan names. Missing
overlays are valid only if no matching saved or loaded overlay actor exists.
The exporter records exact actor descriptors, hard dependencies, source and
actor package hashes, live component transforms where present, and per-GLB
hashes. It refuses ambiguous actors/dependencies and source changes. Completed
attempts have unique directories under `Saved/CityPCG/CitywideTileExports`;
incomplete staging stays outside that search tree under
`Saved/CityPCGBatchStaging`.

Offline test without Unreal or Blender, from the project root:

```text
python Tools/CityPCG/test_batch_export_geodata_unreal.py -v
```

Passing those tests does not validate the live Unreal Python API, real GLB
geometry, retained roads, or a packaged build.
