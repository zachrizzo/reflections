# Gray London medieval conversion

The playable Gray London map is the city to rebuild. Remove the ordinary modern
building shells from surveyed plots and replace them with complete, varied
late-medieval buildings, extending the approach across the playable city. Build
whole streets and neighborhoods with reusable kits and procedural placement;
use individually authored or image-to-3D assets when they improve difficult
landmarks. The aim is a lived-in city with distinct streets and enemy
strongholds that players can reclaim to win back the city. The separate people
workstream owns characters and crowds; integrate city objectives with the
existing game systems without taking over that work.

Replace buildings in verified sections, preserving the street network,
essential landmarks and gameplay routes. Keep the original source geometry
recoverable while replacements are tested. Work on `main` and push verified
progress incrementally, coordinating shared editor access with the other
workstreams.

## Completion checks

- The replacement buildings are present in the actual playable Gray London map
  and packaged game, including when their world-partition cells stream in.
- Streets, collision, navigation, quests, landmarks and access to objectives
  remain usable. Existing source city geometry remains recoverable.
- The medieval treatment extends beyond the opening street, with sufficient
  variation and environmental detail to make the city feel lived in.
- Enemy-held areas are visually legible as distinct strongholds, and the
  player can reclaim them as part of winning back the city.
- Work is visually inspected from the real player spawn and representative
  streets, then checked for movement, streaming and playable performance in
  gameplay and a refreshed standalone build.
- Verified London changes are committed and pushed to `main` incrementally.

## Current checkpoint

The first West Mark Lane pilot has three complete medieval buildings and a
filtered source tile that removes their three surveyed shells while retaining
the other exported primitives. The original Unreal section-to-export mapping
still needs independent verification before road, park, water and landmark
preservation can be claimed. In the offline source, filtered and import
files, the primitive labelled as road in the import copy retains all 18,340
signed triangles; its identity as the actual Unreal road section remains
unproven. The saved Unreal replacement asset also needs an independent
geometry check. The building assets have been imported and their geometry and
collision settings audited. The pilot still
needs placement, in-editor visual review, streaming/gameplay checks and a
current standalone build; it is not yet the finished city. Its runtime module
was linked into shared editor build #15, with the replacement disabled by
default until the pilot is verified.

The west connector, northwest Leadenhall and east Royal Mint blocks have eleven
more complete source models, checked against their surveyed footprints and
Blender round trips. They have not yet been imported or placed in Unreal.
The east Royal Mint block also needs several neighboring exports before review.

The cumulative rollout preflight covers 18 proposed buildings across three of
the 117 source tile assets on disk; four of those have rough massing studies
but no detailed building meshes yet.
They remain review-only: the other tiles need exports, the original section
mapping needs verification, and candidate blocks need live actor and route checks. The
three large modern shells immediately visible from the real spawn overlap
story markers, so replacing them needs a coordinated gameplay and visual review.

At city scale, keep each surveyed outer footprint and use spatially grouped
building geometry and repeated details where feasible. The current individual
models have too many separate material sections to assume they will scale;
measure the result in the playable map before approving it. Nine review-only
grouped meshes now contain the 14 models in 97 sections instead of 149;
material binding, collision and streaming have not yet been tested in Unreal.

An offline watch-gate kit provides occupied and reclaimed pennant variants.
Its quest example, LAN visual controller and separate campaign rules are
prototypes; no reclaimable stronghold has been placed or verified in the
playable level yet. GameFlow needs a save preflight before those rules can be
integrated without risking loss of stronghold progress.

The active tracked goal remains in progress. The current game and standalone
have not yet received a verified full-building replacement; the first priority
is to prove the source section mapping and safely review the pilot in the real
playable map. Subsequent neighborhoods, reclaim gameplay, streaming and a
refreshed standalone remain completion work.

Coordinate any editor or PIE session through `Saved/PIE_LOCK.json` and the
shared editor queue. Save only explicitly identified London-owned packages;
never save all packages or a `metahuman_base_skel` asset.
