# North Market upper-storey and roof review

This is the **unrun v2 hosted review trial**, not an Unreal or gameplay change.
It prepares separate closed-shutter and roof-dormer meshes for the two east
North Market building sources already in the preserved street baseline. The
original building OBJs, FBXs, street scene and seven-shopfront overlay are not
rewritten. The shutters intentionally cover a few existing upper lights and
use subdued existing wood finishes. Three dormer forms use gabled or shed
roofs, projecting clay-tile eaves, bargeboards and exposed timber cheeks in
the existing tile, plaster, oak and leaded-glass palette. The lower edge of each dormer penetrates
the existing tiled roof by 3.5 cm: these are decorative solid additions,
not cut roof openings or interiors.

The geometry follows the **actual source manifest** ridge profiles plus the
0.089 m tile skin, rather than the plan's nominal peaks; its tops remain below
each surveyed height limit. The footprint perimeter and concavities are
checked, party-wall edges receive 1 m clearance, known source chimney positions
are reconstructed and avoided, and shutters are above 3.1 m. The entry edge
is never a party wall. This is a geometric source-art check, not proof of
route, live tile, road, collision or navigation safety.

The reusable geometry functions take a surveyed plan row, a hash-pinned
manifest row, style and protected edge set. This specific trial accepts only
the two eastern building IDs and their `TradingRange` or `DeepWorkshop` styles.
Its roof placement and entry-wall treatment assume a local +X-facing entry;
it refuses other entry directions. It does not claim approval for other tiles,
party walls, roof shapes, or arbitrary city-wide placement. Those need their
own verified source geometry, roof and entry mapping, and route review before
expanding the recipe.

The separate hosted workflow uses a pinned 35,334,942-byte street-scene ZIP
from successful run 43732127254 and verifies both the ZIP and extracted
`.blend` bytes. It rechecks the two original buildings' geometry channels,
poses and material source, writes two separate overlay OBJs with the original
MTL and textures, and compares each overlay's generated and Blender-imported
positions, winding, UVs, normals and materials. It renders a same-camera
before/after pair for each building with brighter consistent lighting, saves
a separate packed Blender scene, and exports a review GLB. A fresh Blender
process verifies the GLB mesh inventory and finite vertices, **not** exact
UVs, normals, material sampling, collision or Unreal rendering. The preserved
baseline's props and ground remain illustrative. Source portraits, roof
intersections and the effect on visual variety still need human review.

The camera isolates the building under comparison, temporarily hiding the
other building for both images so it cannot block the view. Both images use a
camera-fitted high-contrast `ILLUSTRATIVE / ISOLATED / NOT IN GAME` caption.
Original scene visibility is restored before export. The isolated pictures
cannot establish how the whole street reads; visual review is still required.

The workflow runs on GitHub-hosted Ubuntu with read-only contents permissions,
no secrets and no shared editor. Its environment guard prevents accidental
local use, not deliberate spoofing. It retrieves only the pinned baseline LFS
object, downloads the pinned official Blender 4.5.3 archive, and uses bounded
process timeouts. Its output is temporary, review-only and retained three
days; preserving an approved result is a separate step. The v2 artifact is
`north-market-upper-roof-review-v2` and uses the fresh output directory
`ci-north-market-roof-variation-v2`. The earlier trial remains available in
run 43734448268 as artifact 14170380725 until its expiry.

## Making whole-building roofs less uniform

The original `build_whole_buildings_blender.py` and `build_mark_lane.py` use
a single piecewise-linear `(y,z)` roof profile extruded along local X across
each plot. They already lower some ridge heights, but an overlay cannot alter
that underlying roof mass. A bounded next step is to generate a separate
complete building variant with a hash-bound per-range ridge offset, preserving
every valley/eave and remaining inside the surveyed height envelope. The
shell, gable trim, tile skin and chimney placement must all consume the same
adjusted profile; the original full building must remain recoverable. More
ambitious hips, cross roofs and irregular ranges require a zoned roof surface
and junction/collision checks, rather than silently stretching this one-axis
profile. Any candidate with unsupported concavity, seams, party-wall geometry
or unverified source-tile section mapping must stay review-only. Existing
survey footprints alone do not authorize live replacement or route clearance.

Land the two scripts, test and this README first. Then update
`.github/workflows/north-market-roof-variation.yml` in a separate single-parent
workflow-only main commit to trigger the guarded push, or dispatch it on main.
Do not treat the artwork as successful until the hosted render and independent
review complete. Verify real Unreal scale, materials, collision policy,
performance, openings, live party-wall mapping, routes, navigation and tile
restoration before gameplay use.

Lightweight tests (no Blender, output meshes or editor):

```text
python -B Tools/CityPCG/test_north_market_roof_variation.py -v
python -O -B Tools/CityPCG/test_north_market_roof_variation.py -v
```
