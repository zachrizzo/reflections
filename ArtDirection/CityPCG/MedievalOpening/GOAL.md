# Gray London medieval conversion

The playable Gray London map is the city to improve. Replace ordinary modern
building shells with complete, varied late-medieval buildings on surveyed city
plots, then extend the approach across the playable city. Use reusable kits
and procedural placement where they produce coherent streets; use individually
authored or image-to-3D assets when they improve difficult landmarks. The aim
is an inhabited city with distinct streets and visible enemy strongholds to
reclaim. The separate people workstream owns characters and crowds.

## Completion checks

- The replacement buildings are present in the actual playable Gray London map
  and packaged game, including when their world-partition cells stream in.
- Streets, collision, navigation, quests, landmarks and access to objectives
  remain usable. Existing source city geometry remains recoverable.
- The medieval treatment extends beyond the opening street, with sufficient
  variation and environmental detail to make the city feel lived in.
- Enemy-held areas are visually legible as distinct strongholds.
- Work is visually inspected from the real player spawn and representative
  streets, then checked in gameplay and a refreshed standalone build.
- Verified London changes are committed and pushed to `main` incrementally.

## Current checkpoint

The first West Mark Lane pilot has three complete medieval buildings and a
filtered source tile that removes their three modern shells while retaining
the original road, park, water and landmark geometry. Their assets have been
imported and their geometry and collision settings audited. The pilot still
needs placement, in-editor visual review, streaming/gameplay checks and a
current standalone build; it is not yet the finished city.

Coordinate any editor or PIE session through `Saved/PIE_LOCK.json` and the
shared editor queue. Save only explicitly identified London-owned packages;
never save all packages or a `metahuman_base_skel` asset.
