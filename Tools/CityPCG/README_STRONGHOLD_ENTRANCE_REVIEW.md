# Stronghold entrance source-art review

This is a **review-only, illustrative** gate scene. It uses the existing pinned
watch-gate frame and occupied/reclaimed pennants, regenerates the palisade wing
from its source, and adds reusable guard-rack, supply-stack, watch-sconce and
two claim-marker GLBs. The markers and pennants show two visual states; no
capture, enemies, crowds or game logic are created. Existing assets are not
overwritten.

The hosted result contains three labeled same-camera images: the bare gate,
the dressed occupied entrance, and the same dressing with reclaimed markers.
Its two separately exported scene GLBs are mutually exclusive alternatives;
lighting, ground and caption are illustrative and excluded from those GLBs.
`ReusableAssets/` holds each independently reusable prop. Build and fresh-process
reimport reports record source hashes, triangle counts, bounds, material counts,
and output hashes. This is not a full UV, per-corner normal, topology, FBX or
Unreal import audit.

The original gate, each flag state, and all placed props are checked against a
central source-surface box 2.5 m deep by 2.2 m wide by 2.34 m tall, beginning
6 cm above the floor. A conservative triangle-box test checks the box before
export and after clean GLB reimport for both states. It does **not** establish
solid-masonry continuity, imported collision, navigation, road clearance in
the actual map, or a passable gameplay route. The placement is illustrative;
the Trinity watch-gate recipe is a survey hint, not authorization or proof of
live placement.

Small geometry/source checks, including pinned original gate triangle data,
run without Blender or Unreal:

```text
python -B Tools/CityPCG/test_stronghold_entrance_review.py -v
python -O -B Tools/CityPCG/test_stronghold_entrance_review.py -v
```

The isolated `stronghold-entrance-review.yml` workflow runs only on a standard
GitHub-hosted Ubuntu runner with `contents: read`. It pins the Blender release,
the original GLBs, watch-gate generator and recipe, then builds and reimports
the review assets in separate Blender processes. For a push-triggered run, the
script requires a single-parent main commit changing only this workflow file.
Commit source and tests first, then the workflow file separately. No hosted
run, live editor operation or main push is implied by this document.

Before any map use, review the actual art, materials and silhouette, then
independently verify Unreal units, orientation, placement, collision, nav,
both approaches, sightlines, streaming and gameplay. The occupied and reclaimed
visuals still need a separately reviewed game-state binding.
