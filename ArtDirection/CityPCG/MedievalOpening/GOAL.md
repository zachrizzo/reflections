# Goal: rebuild Gray London as a medieval city

Rebuild Gray London as the game's only playable city: a lived-in,
late-medieval London. Prioritize removing unsuitable modern building shells
and replacing them with newly built, complete medieval buildings. Extend that
replacement across the actual playable city, not just the opening street.

Create varied, reusable building kits and use surveyed footprints, stable
procedural placement and parallel generation to build whole streets and
neighborhoods efficiently. Give buildings distinct silhouettes, rooflines,
materials and street-level doors or shopfronts, with details appropriate to
their districts. Use individually authored or image-to-3D assets where they
improve difficult landmarks or distinctive buildings. Add environmental
details that make the city feel occupied, and turn parts of it into enemy
strongholds that players can reclaim to win back the city. The separate people
workstream owns characters and crowds; integrate city objectives with the
existing game systems without taking over that work.

Replace buildings in verified sections, preserving the street network,
essential landmarks and gameplay routes. Keep the original source geometry
recoverable while replacements are tested. Work on `main` and push verified
progress incrementally, coordinating shared editor access with the other
workstreams.

## Completion checks

- Unsuitable modern building shells throughout the playable city have been
  replaced with varied, complete medieval buildings in the actual Gray London
  map and packaged game, including when their world-partition cells stream in.
- Streets, collision, navigation, quests, landmarks and access to objectives
  remain usable. Existing source city geometry remains recoverable.
- The medieval treatment extends beyond the opening street. Representative
  neighborhoods have visually reviewed silhouettes, materials, street-level
  details and sufficient variation to make the city feel lived in.
- Enemy-held areas are visually legible as distinct strongholds. Players can
  clear defenders and reclaim the bases to win back the city, with progress
  saved and synchronized for a LAN host and guests.
- The real game entry path reaches Gray London as the only playable location.
  Work is visually inspected from the real player spawn and representative
  streets, then checked for movement, streaming and playable performance. A
  refreshed game-target build and cook are tested in standalone and with the
  same build on a LAN host and guest.
- Verified London changes are committed and pushed to `main` incrementally.

## Current checkpoint

A GitHub-hosted merchant-gate source export and independent source review
passed. The review checked 5,973 triangles, material references and a clear
2.5 m by 2.7 m passage through the full depth above a 6 cm floor band. Two
flat-color previews were produced but have not yet been visually reviewed.
The gate has not been imported into Unreal or placed in the playable map;
collision, navigation and in-game appearance remain unverified.

The first West Mark Lane pilot has three complete medieval buildings and a
filtered source tile that removes their three surveyed shells while retaining
the other exported primitives. An offline comparison now matches all six
original source mesh groups to their exported primitives by exact signed
geometry. The source group named `GL_Road` has 18,340 triangles, all retained
in the filtered and import files. The saved source and replacement assets also
both have six matching LOD0 section-to-material indices and expected material
slot names; the replacement's material references match the previously
recorded effective source-actor materials. The saved source actor references
the expected tile and five matching material overrides, with relative location
`(300000, 0, 0)` cm. These are saved-file checks: the loaded actor, its world
transform and Unreal's live section-to-material binding still need verification
before runtime road, park, water and landmark preservation can be claimed. The saved
Unreal replacement asset also needs an independent geometry check. The building
assets have been imported and their geometry and collision settings audited.
The pilot still needs placement, in-editor visual review, streaming/gameplay
checks and a current standalone build; it is not yet the finished city. Its
runtime module was linked into shared editor build #15, with the replacement
disabled by default until the pilot is verified.

The west connector, northwest Leadenhall and east Royal Mint blocks have eleven
more complete source models, checked against their surveyed footprints and
Blender round trips. They have not yet been imported or placed in Unreal.
The east Royal Mint block also needs several neighboring exports before review.

The cumulative rollout preflight covers 18 proposed buildings across three of
the 117 source tile assets on disk. Four of those North Market buildings
now have detailed OBJ source meshes with timber, roofs, windows and doors.
All four passed hosted Blender-to-FBX round trips after a targeted repair
preserved the fourth model's authored face normals. Their review-only bundles
and two diagnostic previews are preserved on `main`; they have not been
imported into Unreal. The first preview is repetitive and needs more
street-level detail. A subsequent east-0a variant adds seven closed,
decorative shop/house bays; its overlay, before/after previews and a complete
FBX variant passed hosted Blender source and clean-reimport checks. The FBX
bundle is preserved on `main` with a verified LFS readback. An illustrative
street scene combines the variant with market stalls, goods and a handcart;
its archive and two previews are also preserved on `main`. Visual review found
that its lighting is dark and the upper facades and rooflines remain too regular.
The scene's ground and prop positions are illustrative, and none of these
variants has been imported or placed in Unreal. The buildings still need visual
and Unreal checks, approved collision and a matching cumulative tile filter.
The repaired model's sharp-edge count and resulting Unreal performance need
measurement. All proposals remain review-only: the
other tiles need exports, the original section mapping needs verification, and
candidate blocks need live actor and route checks. The
three large modern shells immediately visible from the real spawn overlap
story markers, so replacing them needs a coordinated gameplay and visual review.

A reproducible historical survey worklist identifies 52 additional screened
shells across those same three exported tiles. It records eight connected
groups and 22 singletons, with split groups and route access flagged for fresh
review. These are candidates, not generated or approved replacements; the
original tile and overlay exports, current protections and live actor evidence
must be rechecked before use. The remaining tiles still need surveying.

At city scale, use surveyed footprints and bounds to guide placement, with
spatially grouped building geometry and repeated details where feasible. New
medieval footprints may differ from the modern shells when they preserve
validated routes, gameplay spaces and access. The current individual models
have too many separate material sections to assume they will scale; measure
the result in the playable map before approving it. Nine review-only grouped
meshes now contain the 14 models in 97 sections instead of 149; material
binding, collision and streaming have not yet been tested in Unreal.

An offline watch-gate kit provides occupied and reclaimed pennant variants.
A hosted source-art review adds palisade wings, supplies, a sconce and claim
markers, with separate occupied and reclaimed scene GLBs. Its source surfaces
leave the measured central box clear, and both scenes passed a fresh GLB
reimport; the review bundle and labeled previews are preserved on `main`.
The result is a simple isolated entrance, not a finished base, and it has not
been imported or placed in Unreal. Collision, navigation, routes and capture
gameplay remain unverified. Its quest example, LAN visual controller and
separate campaign rules are prototypes. A revised defender-clear capture mode and checkpoint adapter passed
standalone C++17 checks on a hosted Linux runner, with Unreal-shaped test
doubles for the adapter. They have not been compiled against Unreal or connected
to the game. No reclaimable stronghold has been placed or verified in the
playable level. GameFlow needs a save preflight before those rules can be
integrated without risking loss of stronghold progress.

The active tracked goal remains in progress. The current game and standalone
have not yet received a verified full-building replacement; the first priority
is to prove the source section mapping and safely review the pilot in the real
playable map. Subsequent neighborhoods, reclaim gameplay, streaming and a
refreshed standalone remain completion work.

The current staged standalone predates the four West Mark Lane pilot assets,
and the game executable predates the replacement runtime source. After the
pilot is placed and verified, rebuild the game target as well as cooking the
map; then check the staged files and test the same build on the LAN host and
guest. `Tools/CityPCG/audit_london_package.py` reports known stale indicators
without treating timestamps as proof of a fresh or playable build.

Coordinate any editor or PIE session through `Saved/PIE_LOCK.json` and the
shared editor queue. Save only explicitly identified London-owned packages;
never save all packages or a `metahuman_base_skel` asset.
