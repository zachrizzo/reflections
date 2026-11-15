# North Market hosted FBX review

This is a **review-only** workflow for the four tracked
`NorthMarketDetailedObj` source models. It does not open the shared editor,
place anything in Gray London, or certify the buildings' visual quality. A
clean round trip does not establish Unreal scale or orientation: a conversion
can cancel itself when Blender exports and reimports the same FBX.

The first hosted attempt passed both east models but stopped on the first
west model before the combined artifact upload, so it retained no FBX bundle.
The parallel [matrix run 43723954546](https://github.com/zachrizzo/reflections/actions/runs/43723954546)
then passed both east models and `west_d08bbb3b`, retaining a separate bundle
for each. `west_736fd5c6` failed before FBX export: one imported face normal
differed from the source by 0.0041 in one component, exceeding the 0.001
tolerance. Its position, UV, material and winding matched. The cause and a
safe correction are still under investigation.

Each job uses an isolated GitHub-hosted `ubuntu-24.04` VM, `contents: read`,
no secrets or self-hosted runners, a 20-minute timeout and one-day artifact
retention. Checkout and artifact actions are pinned to full commit
SHAs. Only the four OBJs, their MTL, manifest and nine PNGs, plus the four
review scripts and the workflow, are checked out; no Unreal project or LFS
files are required. Blender 4.5.3 is downloaded on the hosted VM from the
[official release](https://download.blender.org/release/Blender4.5/) and
checked against the pinned SHA-256 in the
[official checksum list](https://download.blender.org/release/Blender4.5/blender-4.5.3.sha256).
Each VM downloads about 377 MB: up to roughly 1.5 GB across the four jobs,
subject to GitHub scheduling. The extra downloads permit independent parallel
results and do not use the shared machine's Blender or GPU. Blender is distributed under the
[GNU GPL](https://www.blender.org/about/license/).

## What is checked

- Each job checks the pinned source manifest, its own OBJ hash, the MTL hash
  and referenced PNG hashes before and after processing. The original source
  files are only read. Source pivots and yaw are copied into the reports.
- Each source OBJ is imported with local metres and its existing +X entrance
  and +Z up coordinates. OBJ has no slot order, so the contract is the MTL's
  declaration order filtered to materials actually used by that building.
  Slot reordering retains each face's named assignment.
- Before FBX export and after reimport in a **separate clean Blender
  process**, a fail-closed comparison checks object identity transform and
  pivot; vertex, edge, polygon and UV-corner counts; ordered slot names; and
  every polygon's signed cyclic corner positions, UVs, normals and named
  material. Position tolerance is 0.00003 m, UV tolerance 0.00003 and normal
  component tolerance 0.001. Similar ambiguous polygon matches are rejected.
  These face checks do not prove watertightness or exact vertex connectivity.
- Each textured material must connect its expected, hash-matched external
  image directly to Principled Base Color using the active UV channel, with
  sRGB, repeat, linear filtering and flat projection, and matching sampling
  properties after FBX reimport. Solid materials'
  Base Colors must match MTL `Kd`; shader alpha must be unlinked and opaque.
  Non-finite transforms and material values are rejected. The verification requires reimported
  textures to resolve inside the exported model's artifact directory; it
  does not fall back to source textures elsewhere.
- Only the matching `east_0a73564b` job attempts the bounded, optional CPU
  render of eye-level and three-quarter views. A render or copy failure is nonfatal; preview files
  are staged in a hidden directory excluded from the upload, checked for PNG
  signatures and a matching FBX hash, then published together by atomic rename.
  These are diagnostic views with artificial lighting, not visual approval or a
  view from the actual game.

Blender's exporter, importer and shader conversion may differ from these
expectations. A failed or ambiguous check stops that model's job before
upload; other model jobs can still upload their verified bundles.

## Workflow execution after review

The workflow permits manual `workflow_dispatch` on `main`, or a `main` push
containing exactly one non-merge commit changing **only**
`.github/workflows/north-market-hosted-roundtrip.yml`. The push guard
validates the event and its exact Git diff before downloading Blender.
Because the available connector cannot dispatch Actions, put the scripts,
tests and documentation on `main` first; add the workflow in a later
workflow-only commit to trigger that path. Do not include other files in the
trigger commit. Inspect the Actions run and download the successful individual
artifacts before their one-day expiry:

- `north-market-fbx-review-east-0a73564b`
- `north-market-fbx-review-east-31c9ff1a`
- `north-market-fbx-review-west-736fd5c6`
- `north-market-fbx-review-west-d08bbb3b`

Local tests do not require Blender or modify assets:

```text
python -B Tools/CityPCG/test_north_market_roundtrip.py -v
python -O -B Tools/CityPCG/test_north_market_roundtrip.py -v
```

After the hosted checks pass, a human still needs to inspect all four models
and their material appearance; any preview covers only one. Before playable
use, verify imported dimensions, +X facing, pivot, UV/material sections,
collision, navigation, replacement-tile alignment, streaming and gameplay
inside Unreal, with the original city geometry recoverable. None of those
steps is authorized by or implied from a passing hosted round trip.
