# Surveyed whole-building roof massing trial

This opt-in trial changes the **complete procedural building** roof profile.
It is unrun and review-only: it does not update Gray London or establish
Unreal/gameplay readiness. The original generator behavior is unchanged when
`--roof-variation` is omitted, and existing source OBJs, FBXs, tile meshes,
street scene and overlays are not overwritten or combined with the variants.

For each supported alternating roof range,
`--roof-variation asymmetric-ridges-v1` deterministically moves its ridge
within the existing pair of valleys. Ridge height, eave/valley locations,
surveyed footprint, source origin, yaw and entry are retained. The building
generator passes the same varied profile to the closed shell, tiled roof,
gable trim and chimney placement; it then runs its existing FBX reimport,
footprint, UV-layer, material-slot, manifold-edge and positive-volume audits.
This changes the roof mass itself rather than putting another roof on top.

The mode supports only sufficiently wide, initially symmetric, equal-eave
pitched ranges and rejects plans with shared party-wall edges. It does not
infer unrecorded party walls, cut gameplay doors or certify routes. The four
North Market candidate buildings are the trial inputs; their recorded Gray
London tile and source-export hash are evidence for these candidate footprints,
not approval for live replacement. The retained height is an envelope from the
survey, not proof of an exact historic roof. Hips, cross-gables, segmented roof
depths, party-wall pairs and narrow or already asymmetric ranges require a more
capable roof representation and separate validation.

The separate, read-only GitHub-hosted workflow runs east and west as independent
matrix jobs. It checks pinned LF-canonical generator, candidate and plan bytes,
copies the nine source-manifest-pinned textures into an isolated scratch tree,
and generates a baseline and a varied complete-building FBX for each of two
buildings on that side, using the original plan-pinned east style override.
The baseline style and roof profile are checked against the prior source
manifest, but complete face-for-face equivalence to the earlier OBJ is not
claimed. Both FBXs are reimported by the original generator. A second
fresh Blender process compares pre-export and reimported mesh counts, bounds,
UV layers and ordered material slots, and checks every textured material's
packed or scratch-resolved image bytes against the source texture manifest.
It also checks the exact reported profiles, footprints, pivots,
entries and party-edge status, requires actual FBX vertices at each reported
tiled ridge, and compares faces wholly below `eave - 0.10 m` by
position, UV, winding and material. It renders labeled before/after diagnostic
views and publishes the source trees and an output-hash manifest. The compared
lower-face signature excludes faces crossing that cutoff and does not prove
identical normals, exact connectivity, or
an exact Unreal FBX import. Exact source PNGs are included in the bundle, but
automatic texture path resolution outside it still needs verification. No live
map, Unreal editor or shared PC is used.

Each matrix job downloads the pinned Blender 4.5.3 archive (approximately
377 MB) independently; parallel jobs may transfer roughly 754 MB in total.
The official download is tried first, then Blender's official mirror service
on transfer failure; both paths require HTTPS and the exact same SHA-256.
The environment guard prevents accidental local execution, not deliberate
spoofing. Artifacts are temporary, retained for three days, and are not
published into the game. A failed job uploads no bundle for that side.

Land the generator, helper, hosted review script, tests and this README on
main first. Add `.github/workflows/whole-building-roof-review.yml` in a
separate single-parent workflow-only commit, or dispatch the workflow on
main. Inspect both job results, per-building FBX audits and visual comparisons
before deciding whether to preserve any result.

Before use on the playable map, independently prove the pinned GLB primitive
to Unreal source section mapping, preserve protected roads and landmarks, and
maintain the tile-level all-cells-ready/restore barrier. Then check Unreal
scale, pivot, material binding, normals, collision, route clearance, navigation,
streaming and visual quality under a genuine shared-editor handoff. The
survey and this hosted test do not establish those conditions.

Lightweight source tests only:

```text
python -B Tools/CityPCG/test_whole_building_ridge_variation.py -v
python -O -B Tools/CityPCG/test_whole_building_ridge_variation.py -v
```
