# Reviewed whole-building source batches

`build_reviewed_group_batch.py` is an offline, bounded batch runner for the
historical screened worklist. It derives each footprint from the pinned source
survey and verifies source face signatures; it does not invent placements or
modify Unreal assets. The script has synthetic selection tests but has **not**
yet completed a real source batch.

The current worklist contains 52 additional screened shells. Six complete,
fully unused road-connected groups contain 15 shells and can be nominated in
one- to four-model batches. Mixed groups, singletons, disconnected subsets and
groups larger than four require fresh connectivity and route evidence before
they can enter this runner. All screening is historical review evidence, not
approval of current actor, overlay, road or story conditions.

After the shared queue releases an unreserved window, the editor is running,
and no lease exists, the guard requires at least 4 GiB physical and 10 GiB
system commit headroom. It rechecks the lease, train and available memory at
stage boundaries and during source hashing. Individual model generation and
OBJ readback run synchronously between those checks, so they cannot stop
instantly if a new lease appears. Coordinate with other large offline jobs
before starting.
For the two-building East Interior group, from the project root:

```powershell
python -B Tools/CityPCG/build_reviewed_group_batch.py `
  --tile Tile_p04_p00 --group block_269eb22dac5f --batch EastInteriorReview001
```

The default worklist is `Saved/CityPCG/MedievalSurvey/screened_worklist_from_snapshot_20261115_codex_v2.json`.
If it is absent, create it using the tracked snapshot and
`python -B Tools/CityPCG/build_screened_worklist.py`; an existing worklist is
never overwritten. `--worklist` may select another identical regenerated copy.
Use `--group` more than once only when the combined group size is at most four.

The runner writes a fresh directory under
`Saved/CityPCG/ReviewedWholeBuildingBatches`. It retains any incomplete
directory for review and refuses to reuse its name. A completed batch contains
candidate/plan evidence, detailed OBJ/MTL/texture source art, independent
geometry/UV readback, a cumulative tile mask and `next_rollout_baseline.json`.
The final manifest pins the inputs, outputs and baseline. For a later batch,
pass the preceding completed batch's `next_rollout_baseline.json` with
`--baseline`; the runner checks its sibling completion manifest and hash,
then preserves the original 18-building baseline and prior cumulative masks.

The Python vector/tessellation shim does not replace Blender FBX round trips.
The models have not been imported, placed or tested in Gray London. Source
GLB primitive-to-live-Unreal section and material binding, authored actors,
collision, navigation, story and roof routes, LAN and streaming still require
independent validation. The new cumulative mask does **not** match the
previous grouped meshes; build and verify the exact complete group set, retain
the original tile and collision until everything is ready, and restore it if
any required cell unloads or fails.

Run the lightweight selection tests without launching Blender or Unreal:

```powershell
python -B -m unittest discover -s Tools/CityPCG -p test_build_reviewed_group_batch.py -v
```
