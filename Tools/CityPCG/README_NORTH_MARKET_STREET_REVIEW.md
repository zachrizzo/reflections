# North Market illustrative street review

This hosted-only scene places two previously round-tripped North Market FBXs
in their surveyed relative transforms, adds the independently regenerated
closed-tenancy overlay to the first building, and composes a market stall,
goods, handcart and small props around them. It creates actual review geometry and
rendered views without accessing the shared Unreal editor. Prop positions,
the cobble/earth ground plane, lighting and cameras are **illustrative**;
they are not a live map, safe placements, gameplay collision, navigation or
visual approval. The ale-stake is a speculative tavern cue, not evidence for
an actual historic tenancy. No people are included.

The two pinned source FBX ZIPs are in `NorthMarketDetailedObj/HostedFBXReview`.
The stall, crates and cask are regenerated from the pinned original Blender
source in a fresh runner scratch tree. The separately tracked quay handcart
and cargo GLBs have Blender round-trip reports, but no authored collision.
The trestle, bowl and ale-stake use the draft MarketDressingKit's pure geometry
functions, with flat colors; its Windows local resource guard is unchanged.
The illustrative plane uses the opening ground's original color, normal and
roughness images. It does not reuse the geographically different ground mesh
or claim that the opening ground's floor survey applies here.

On success the hosted artifact `north-market-street-illustrative-review`
contains a packed `.blend`, `north_market_street_review.glb`, two labeled
street-level PNGs, reusable individual prop GLB/OBJ/MTL sources, a build
report and `manifest.json`. The manifest records input/output hashes, source
commit, model and prop details, illustrative poses and independent GLB
reimport. The reimport verifies mesh inventory and finite geometry; it is
not a proof of exact topology, UVs, material sampling or Unreal appearance.

The entrypoint verifies the two archive hashes and bounded extracted FBX
hashes against the earlier successful hosted FBX runs. It rechecks the FBX
geometry/material channels against the pinned OBJ source before adding the
building to the scene. A separate Blender process reimports the resulting
GLB. No result should be consumed if `manifest.json` is absent.
The surveyed plan is pinned using LF-canonical SHA-256 (accepting LF or CRLF
only); binary sources are checked byte-for-byte. The build report records
both the plan's canonical and actual raw digest.

The tenancy overlay is regenerated from the pinned source and checked against
the overlay SHA-256 from successful hosted trial 43731156271. A full
position/winding/UV/normal/material comparison checks its Blender import;
it uses exactly the 0a FBX's local transform. Its combined-building OBJ is
not layered over the original shell. The overlay remains closed visual detail.

Before gameplay use, separately verify Unreal scale/orientation, each prop's
material binding and collision policy, real floor support, entry and street
clearance, navigation, quests, streaming and original-tile restoration. The
scene's 0a doorway is closed decorative geometry. The source surveys do not
approve the props' artistic offsets.

## Review and execution

The draft workflow uses only a GitHub-hosted `ubuntu-24.04` runner and
`contents: read`, with no editor access or repository write. A sparse
checkout retrieves two LFS FBX bundles and two LFS quay props. It downloads
the approximately 377 MB official Blender 4.5.3 archive and checks the same
SHA-256 used by the existing North Market round-trip. Hosted environment
checks prevent accidental local execution; they are not a security boundary
against a deliberately spoofed environment.

Land the two scripts and tests on main first. Then add the workflow in a
separate single-parent main commit changing only
`.github/workflows/north-market-street-review.yml` to trigger its guarded
push path, or dispatch it on main when available. The workflow also runs the
small tests normally and with `-O`. Inspect the hosted run before treating
the artifact as available. Its output is temporary and expires after three
days; preserving approved assets needs a separate authorized action.

Local lightweight checks, which do not run Blender or generate assets:

```text
python -B Tools/CityPCG/test_north_market_street_review.py -v
python -O -B Tools/CityPCG/test_north_market_street_review.py -v
```
