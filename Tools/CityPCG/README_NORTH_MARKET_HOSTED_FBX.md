# North Market hosted FBX review

This is a **prepared, unrun, review-only** workflow for the four tracked
`NorthMarketDetailedObj` source models. It does not open the shared editor,
place anything in Gray London, or certify the buildings' visual quality. A
clean round trip does not establish Unreal scale or orientation: a conversion
can cancel itself when Blender exports and reimports the same FBX.

The workflow uses an isolated GitHub-hosted `ubuntu-24.04` VM, `contents:
read`, no secrets or self-hosted runners, a 20-minute job timeout and one-day
artifact retention. Checkout and artifact actions are pinned to full commit
SHAs. Only the four OBJs, their MTL, manifest and nine PNGs, plus the four
review scripts and the workflow, are checked out; no Unreal project or LFS
files are required. Blender 4.5.3 is downloaded on the hosted VM from the
[official release](https://download.blender.org/release/Blender4.5/) and
checked against the pinned SHA-256 in the
[official checksum list](https://download.blender.org/release/Blender4.5/blender-4.5.3.sha256).
It downloads about 377 MB; Blender and any render run there, not on the shared
machine. Blender is distributed under the
[GNU GPL](https://www.blender.org/about/license/).

## What is checked

- The pinned source manifest, four OBJ hashes, MTL hash and referenced PNG
  hashes are checked before and after processing. The original source files
  are only read. Source pivots and yaw are copied into the reports.
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
- A bounded, optional CPU render attempts eye-level and three-quarter views
  of one verified building. A render or copy failure is nonfatal; preview files
  are staged in a hidden directory excluded from the upload, checked for PNG
  signatures and a matching FBX hash, then published together by atomic rename.
  These are diagnostic views with artificial lighting, not visual approval or a
  view from the actual game.

Blender's exporter, importer and shader conversion may differ from these
expectations. A failed or ambiguous check stops the job before uploading
the FBX bundle. No FBX or preview has been created by this workflow yet.

## Workflow execution after review

The workflow permits manual `workflow_dispatch` on `main`, or a `main` push
containing exactly one non-merge commit changing **only**
`.github/workflows/north-market-hosted-roundtrip.yml`. The push guard
validates the event and its exact Git diff before downloading Blender.
Because the available connector cannot dispatch Actions, put the scripts,
tests and documentation on `main` first; add the workflow in a later
workflow-only commit to trigger that path. Do not include other files in the
trigger commit. Inspect the Actions run and download the
`north-market-fbx-review` artifact before its one-day expiry.

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
