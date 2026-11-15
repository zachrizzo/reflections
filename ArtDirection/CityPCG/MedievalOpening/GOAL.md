# Gray London medieval conversion

The playable Gray London map is the city to improve. Replace ordinary modern
building shells with complete, varied late-medieval buildings on surveyed city
plots, then extend the approach across the playable city. Use reusable kits
and procedural placement where they produce coherent streets; use individually
authored or image-to-3D assets when they improve difficult landmarks. The aim
is an inhabited city with distinct streets and visible enemy strongholds that
players can reclaim to win back the city. The separate people workstream owns
characters and crowds; integrate the city objectives with the existing game
systems without taking over that work.

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
filtered source tile that removes their three modern shells while retaining
the original road, park, water and landmark geometry. Their assets have been
imported and their geometry and collision settings audited. The pilot still
needs placement, in-editor visual review, streaming/gameplay checks and a
current standalone build; it is not yet the finished city.

The west connector, northwest Leadenhall and east Royal Mint blocks have eleven
more complete source models, checked against their surveyed footprints and
Blender round trips. They have not yet been imported or placed in Unreal.
The east Royal Mint block also needs several neighboring exports before review.

The cumulative rollout preflight covers those 14 proposed buildings across
three of the 117 source tile assets on disk. They remain review-only: the other tiles
need exports and the candidate blocks need live actor and route checks. The
three large modern shells immediately visible from the real spawn overlap
story markers, so replacing them needs a coordinated gameplay and visual review.

At city scale, keep each surveyed outer footprint and use spatially grouped
building geometry and repeated details where feasible. The current individual
models have too many separate material sections to assume they will scale;
measure the result in the playable map before approving it.

Coordinate any editor or PIE session through `Saved/PIE_LOCK.json` and the
shared editor queue. Save only explicitly identified London-owned packages;
never save all packages or a `metahuman_base_skel` asset.
