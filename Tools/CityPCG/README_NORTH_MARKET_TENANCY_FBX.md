# North Market tenancy FBX trial

This prepares two **review-only** outputs from the tenancy source trial:

- `overlay/SM_NorthMarket_0a_TenancyOverlay.fbx` contains only the closed
  decorative frontage additions at the original building's local pivot.
  It can be reviewed alongside the unchanged baseline building.
- `complete/SM_NorthMarket_0a_TenancyFull.fbx` contains the original building
  and those additions together. Use it *instead of* the baseline building,
  never on top of it.

The script rechecks the pinned surveyed plan, original OBJ/MTL/textures and
fresh generator report; regenerates the overlay hash; and proves that the
complete OBJ's per-face positions, winding, UVs, normals and materials are the
ordered union of the original and overlay. It also binds the independently
verified baseline FBX hash. Both generated OBJ hashes are pinned to the
source shown in hosted preview run `43731156271`, artifact `14167854997`.
The hashes were independently recomputed from the ZIP members after the ZIP
itself was verified. This records provenance, not visual approval. Each OBJ is
then imported in Blender, compared to
its source, exported to a fresh folder, reimported in a **separate Blender
process**, and compared again. Material slots, their assignments and the
portable base-color/texture graph are checked; the original asset is untouched.

If Blender averages compatible authored flat normals, the existing validated
normal-restoration procedure may add sharp edges before export. It rejects
ambiguous source matches and runs the same strict full-channel comparison
before export and after fresh reimport; it never weakens the tolerances.

Run the small offline checks without Blender:

```text
python -B Tools/CityPCG/test_north_market_tenancy_fbx.py -v
python -O -B Tools/CityPCG/test_north_market_tenancy_fbx.py -v
```

For a future **reviewed** integration into the existing `north-market-hosted-
roundtrip.yml` job, add `north_market_tenancy_fbx.py` and its test to sparse
checkout. Only after the original east-0a FBX has been verified and the tenancy
generator and before/after preview have succeeded, run on the east-0a matrix
row:

```bash
python3 -B Tools/CityPCG/test_north_market_tenancy_fbx.py -v
python3 -O -B Tools/CityPCG/test_north_market_tenancy_fbx.py -v
blender="$RUNNER_TEMP/blender-4.5.3-linux-x64/blender"
script="$GITHUB_WORKSPACE/Tools/CityPCG/north_market_tenancy_fbx.py"
for kind in overlay complete; do
  timeout --signal=TERM --kill-after=10s 180s "$blender" --background --threads 2 \
    --factory-startup --python-exit-code 1 --python "$script" -- export "$kind"
  timeout --signal=TERM --kill-after=10s 180s "$blender" --background --threads 2 \
    --factory-startup --python-exit-code 1 --python "$script" -- verify "$kind"
done
```

Upload `ci-north-market-tenancy-fbx/` as a separate, short-retention artifact
only if both clean-process verifications succeed. Each fresh subdirectory holds
its FBX, copied texture dependencies and export/verify reports with SHA-256s,
source placement metadata and comparison facts. The original FBX artifact and
tenancy source/preview artifact remain separate and available as the baseline.

This workflow has not yet been integrated or run. The checks are intentionally
strict and may stop on real Blender import/export differences. A successful
Blender-to-Blender round-trip does not prove Unreal dimensions, orientation,
tangents, materials, collision, placement, navigation, or visual quality.
The motifs remain closed; this does not create functional doors, change the
people system, or approve any live map replacement.
