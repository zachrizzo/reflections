# Plan: Gray London (Jah's World Partition map) as the game's map

Written by world-jump on Nov 14 at 21:00, editor-free, from `git show origin/main` (4aac7d0d) and our source. The
numbers marked **measure** come from step 0, run in my editor row after train #13. `NewGameMap` stays on the mock city
until a London playthrough passes.

**Recommendation.**
- **Option A, the one London.** A world jump swaps the side in place, using World Partition **runtime Data
  Layers**: one per side, holding that side's set pieces, pickups, lights, fog and colour grade. Nothing moves,
  and nothing is copied.
- **A compact play district round the Tower.** Tower Hill, the Tower, Tower Bridge and Leadenhall Market, about
  900 × 820 m and 3.0–3.9 km east of the map origin. The rest of London is scenery.
- **Option B (three streamed copies) is technically possible with World Partition but wrong for us.** See
  section 1.

## What we're taking in

| Fact | Value | Source |
|---|---|---|
| Map | `/Game/GrayLondon/Maps/GrayLondon_Geodata`, World Partition with PCG | README |
| Packages | 2,057 external actor packages and 99 external object packages for this map, plus about 1,250 content assets (landmarks, tiles, materials). 394 MB in LFS. | `git ls-tree` |
| Geometry | 121 geodata tiles, about 4.0 M source faces for the whole city, 133k building IDs; landmark models (Tower, Tower Bridge, St Paul's, Westminster…) from Codriver | period audit, data sources |
| Coordinates | British National Grid, origin at 51.5080 N, 0.1281 W (Charing Cross), clipped to a 5,650 m radius | data sources |
| Collision | Hidden Thames collision with openings at bridges. Foliage, signals and kiosks have none. Routes are "not exhaustively tested". | data sources |
| Period | Aims at about 1980–2009; post-2009 towers removed by hand | period audit |

## 1. Three sides on one World Partition London

**Option B, three streamed copies at offsets.** World Partition has no streaming sublevels, so B would mean
duplicating all 2,057 actors twice inside the same World Partition map, at offsets of at least 12 km.
- What works: streaming by distance would keep memory to about one copy, if we also add streaming sources at the
  hero's mirrored positions so a jump doesn't wait on a load.
- Why not:
  - Every edit Jah makes to London would have to be made three times. The user calls this map "the main map we
    use", so it will keep changing.
  - PCG, HLOD, navmesh and lanes would all triple.
  - About 4,100 new actor packages.
  - The packaged build grows.
- **No.**

**Option A, one London where the side changes in place.** This is close to what players see already (the hero
"keeps the exact spot"):

| Layer | What's in it |
|---|---|
| Base London (no data layer) | Jah's city, the navmesh, crowd lanes, and all story markers (each with an explicit `Side`; the property exists today). |
| `DL_Pewterside`, `DL_Giltside`, `DL_Frostside` (runtime data layers) | That side's set pieces (the mirror tower variants, the Weigh-House roof and stair, the key pedestal, the sealed door, the arena, the ramps), pickups (shards, pages, key), lamps and braziers, props, an **unbound** post-process volume with the side's grade, a local fog volume, and its squad routes and spawners. |

- **The jump:**
  1. Set the destination layer to *Activated*; the other two stay *Loaded*, so the switch is a visibility and
     collision flip with no disk load.
  2. Wait for streaming to complete near the hero.
  3. Run the safe-landing sweep at the same spot.
  4. Set the source layer to *Loaded*.
- **Mood comes free:** each side's grade and fog live in its layer and switch with it. Codex's per-side props and
  lamps come along too.
- **The real London stays one look.** It gets per-side grade, fog, sky and lights, which is what the mock does
  minus the per-side facade colours. Later, Jah's master materials could read a material parameter collection
  holding the side index, for a tint or frost overlay.

**Code changes (one train), with owners:**

| Change | Owner |
|---|---|
| `EReflectionsWorldLayout::InPlace`. Per side in `FReflectionsWorldInfo`, a `UDataLayerAsset`. The jump path above. `GetWorldAtLocation()` returns the current side in InPlace. A new `GetActorSide(Actor)` reads data-layer membership, falling back to the current side. `TranslateBetweenWorlds` returns the same spot. | world-jump (me) |
| NPC home side: `NpcSubsystem` lines 355, 535 and 1083 use the location today. They need an explicit side from the person, the spawner or the actor's data layer. NPCs not on the current side get hidden and paused on a jump (schedules keep running). | npc-unify / npc-lives |
| Possession target side (`VillainPossession.cpp:646`); voice side (`RealtimeVoiceComponent.cpp:407`) | villain / npc-dialogue |
| Quest goTo side (`QuestWorldSubsystem.cpp:1054`): use the marker's side | quests |
| Ring crowd: respawn from the destination side's look pool on a jump | crowd-react |
| Pickups (`WorldPickups.cpp:254`): side from data layer | world-jump |

Everything else keeps working through markers (by name, with an explicit side).

## 2. Story markers on real London spots

There are 138 names: 89 marker actors (Giltside 50, Pewterside 22, Frostside 17) plus extra names as tags; see
`ArtDirection/MockCity/MARKERS.md`. They hang off **35 places**. `graylondon_places.py` maps each place to a real spot
and projects it to map metres. Its output is `graylondon_places.json`.

| Mock place | Real spot | E, N (m from origin) |
|---|---|---|
| Intro, Lamplight inn | Great Tower St / Mark Lane corner | 3283–3300, 311–319 |
| Bell Lane (3 failing lamps) | Byward Street | 3342, 292 |
| Bell Square, dry fountain / Cistern | All Hallows by the Tower churchyard | 3364–3374, 276–286 |
| Weigh-House (Pewterside page), stair, roof | **Set piece** in Seething Lane Garden | 3321–3339, 303–314 |
| Tower plaza, mirror tower (Gilt sealed / Frost ramps + crown / Pew stump) | **Set pieces** on Trinity Square Gardens, Tower Hill | 3519–3523, 275–297 |
| Archive and steps (Ice Stairs) | Trinity House steps | 3505–3508, 325–330 |
| Ice Wall | Roman London Wall, Tower Hill | 3605, 355 |
| Lantern Row (Bone Market), shops | Leadenhall Market, Lime St, Gracechurch St | 3019–3131, 565–637 |
| Lantern Gate, gate bridge, watch post (key) | Tower Bridge north tower, deck, approach | 3660–3702, −183 to −38 |
| Drifter camp (under the gate) | St Katharine's Way, under the approach | 3766, −91 |
| River edge (canal), Fish Steps | Tower Wharf; Old Billingsgate river stairs | 3487, −54; 3078, 169 |
| Muster Yard, Wall Company barracks | Royal Mint Court | 3867–3916, 258–267 |
| Watch barracks | 10 Trinity Square frontage | 3429, 300 |
| Coal Lane stop, Hester, laundry | Fenchurch Street station, Crutched Friars, Cooper's Row | 3431–3573, 382–478 |
| Wick Street (infirmary) | Mark Lane north | 3280, 408 |
| Sorrel's yard and shed | Cooper's Row wall courtyard | 3586–3593, 394–399 |

Walking distances are 300–600 m between beats (1–2 min at run speed), against 50–150 m in the mock. That's fine
for a jam slice; quests may want to tighten some steps.

**Script (`tools/place_london_markers.py`, to write in step 0):**
1. Open the map in the editor (World Partition maps can't be built off-screen the way I build the mock).
2. **Calibrate:** find the Tower of London landmark actor through the World Partition actor descriptions, compare its
   bounds centre with the projected Tower spot, and solve the axis mapping (signs; the ~1.5° grid convergence is
   already in the projection). Check with a second landmark (Tower Bridge).
3. For each mock marker, take its place's London spot plus the marker's mock offset from that place (scaled down if
   needed so it stays on the street). Trace down to the ground, project onto the navmesh, and spawn a
   `ReflectionsStoryMarker` with the same name, tags, `Side`, radius and facing.
4. Set pieces and pickups go into their side's data layer, reusing the mock generator's tower, Weigh-House, stall and
   lamp functions, rotated to the street grid.
5. **Save only the new actor packages, by path.** Never save all; other sessions' dirty assets must not be written.
6. Check in PIE: `Story.Markers` shows 0 auto-placed, and the path checks from `fix_driver.py` pass.

## 3. Navmesh, crowd lanes and PCG

- **Navmesh.**
  - Bounds over the play district only, about 1.0 × 0.9 km. A city-wide 100 km² navmesh is out.
  - Recommended: `RecastNavMesh` with **runtime generation Dynamic + Generate Only Around Navigation Invokers**. The
    invokers are the hero, the named NPCs and the squads, at radius 60–80 m with tile size 32 m. *Ledge Slope Filter
    Mode = None*, as in the mock, or stairs never join the navmesh.
  - Alternative if invoker cost is too high: a World-Partitioned static navmesh (navigation data chunk actors) built
    for the district only.
  - **Measure:** tile build time around the hero.
- **Crowd lanes (ZoneGraph, `CitySidewalk`).** Jah's roads are meshes, so there are no centrelines in the map.
  - Plan: generate about 40–60 ZoneShapes for the district's main pavements from the OSM highway ways. Use the same
    Geofabrik extract Jah used (ODbL), offset to the kerb by road width / 2 + 1.5 m, then snap to the navmesh.
  - The shapes must not be spatially loaded, so the lane graph is complete. One `ZoneGraphData` actor.
  - Owner: crowd-react with me; I can write the generator.
- **Crowd-react's lane requirements (21:15).**
  1. Profile: `CitySidewalk`, two 150 cm lanes, one each way.
  2. Points at least every 10 m. Z sampled from the pavement +3 cm, ±30 cm at worst: the ring spawns walkers on the
     lane point, and the follower searches ±3 m in height.
  3. Pavement only, never across a carriageway, with the centreline mid-pavement.
  4. Loops round each block are best; dead ends are fine; ends within a few cm link automatically.
  5. Validate every point against the navmesh or with a floor trace.
  6. Run `Crowd.City.SetupZoneGraph` once with the map open, place the shapes, check the `ZoneGraphData` actor
     exists, then save (new packages only).
  7. The map short name is `GrayLondon_Geodata`. Crowd-react already targets it from train #14 (`Crowd.Ring.Maps`).
  8. (21:25) Every lane uses the **CitySidewalk** profile (ID 5C17E0A1-2B3D4E5F-6A7B8C9D-0E1F2A3B, tag bit 0
     Default). Pedestrian lanes only, no road or vehicle lanes: the ring and follower take any lane near a walker and
     don't filter by tag. Road lanes would need their own profile and tag, cleared with crowd-react and the
     orchestrator first.

  Plan:
  - Classify pavement by floor traces on a 2 m grid over the district, using the hit mesh name (Jah's
    `Sidewalk*` meshes) or its height above the carriageway.
  - Thin each pavement region to a centreline.
  - Simplify to points no more than 10 m apart, with traced Z +3 cm.
  - Build one ZoneShape per centreline.
- **PCG.**
  - **Measure:** count the `PCGComponent`s and their *Generation Trigger*. If any are generate-at-runtime
    (partitioned), that costs CPU at load; switch them to generate-on-load in the editor and save the results.
  - The awnings and pilots (Green Park, the B01 batch) look editor-generated.

## 4. Load time, memory and performance

- **Disk:** 394 MB for the London content.
  - Packaging: our jam build target is **under 1 GB** (the test-package session). Cooking all of London could take
    most of that. If it's tight, cook only the cells inside a play boundary. World Partition can't easily cook a
    subset, so alternatively drop far tiles, or accept a bigger build.
- **Editor memory:** opening a World Partition map loads only the always-loaded actors plus the regions you load.
  PIE streams cells by loading range. Expect +1–3 GB for the editor and +1–2 GB for PIE. With about 17 GB free that's
  OK, but **not** while crowd-looks builds MetaHumans.
- **Measure in step 0:**
  - map open time;
  - editor working set before/after;
  - the actor count by class;
  - World Partition grid cell size and loading range;
  - HLOD present or not (without HLOD, far buildings vanish beyond the loading range: no skyline);
  - PCG triggers;
  - triangles in view at Tower Hill;
  - PIE start time.
- **Perf estimate (unmeasured):** about 4 M faces for the whole city is light, but the landmark models
  (Codriver, combined meshes) and Lumen + VSM over a dense city are the risks. Guess: 40–70 fps at 1080p on this
  machine at Tower Hill without the crowd. MetaHuman NPCs and the ring crowd cost the same as on the mock. Editor PIE
  numbers are throttled when the editor is in the background, so we need a standalone check.

## 5. Risks to decide on

1. **IP (High, in `ArtDirection/Submission/rules.md` #1 and `originality.md`).** The jam rules tell us to keep
   "London" out of everything a player sees, because three stacked Londons with Gray/Red/White naming follows
   V.E. Schwab. A recognisable real London (Tower Bridge, the Tower) makes the premise more literal. In-game names
   stay Lanthorne / Pewterside / Giltside / Frostside, and we must not show the map's name. **The user should
   confirm they accept this.**
2. **Trademarks (`rules.md` 15(d)):**
   - The map has a **Waterstone's** sign (a real brand) at Trafalgar Square: outside our district, but it ships if
     the whole map cooks. Remove it.
   - Check the `BusStops` / `TransitMarkers` for TfL roundels.
3. **Attribution we'd owe:** "© OpenStreetMap contributors" (ODbL) and Codriver landmark models (CC BY 4.0) in the
   credits and on the itch page, plus Cosmo Tree Gen (MIT), the Noto Serif licence (OFL) and the London Street Props
   postbox (CC BY 4.0).
4. **Schedule (deadline Sun 18:00):**

   | When | What |
   |---|---|
   | Tonight, my post-#13 row (~10 min) | Step 0: measure |
   | Train #14 | InPlace code |
   | Then (~2 h editor work) | Set pieces, markers, navmesh and lanes |
   | Sunday morning | Playthrough |
   | **Sunday ~12:00, go/no-go** | Otherwise ship the mock city as it is (verified today), with London as a post-jam goal |

## Asks received after the plan (Nov 14, 21:15), not yet answered (messaging paused)

- **Villain.**
  - Exactly one `ReflectionsVillainArena` at the centre of the finale floor, `ArenaRadius` equal to the usable flat
    radius (10–14 m ideal, at least 7 m), **not spatially loaded**.
  - The floor is flat and clear, with a parapet of at least 1.2 m if raised.
  - Send the spot.
- **Jam-submission** (option (a): texture or material swaps, the least touch).
  - Find the actor instances in the editor:
    - the TextRender "Waterstone's - Trafalgar Square - sign prototype" (`__ExternalActors__/.../1/FE/1PYCSCAM3NLP2FIMCXRQJY`);
    - the "Tate Britain identification sign" TateSignText (`.../E/67/J4M2QI9H1W13WMI61US781`).
  - Also: Twinings (TwiningsStrandFrontage), the four Cecil Court shop names, and the 104 Underground roundel
    TransitMarkers plus `T_BusStopFlag`, which are the worst items.
  - Check: OXO face, BT Tower logo, Selfridges sign, Cenotaph RAF flag, Buckingham Palace flag (Royal Standard →
    Union flag).
  - Generic replacement words: BOOKSELLERS, TEA MERCHANTS, PROVISIONERS, DRAPERS, EMPORIUM, THEATRE, GALLERY, and
    THE LAMP & KEY for the Garrick Arms; never "London".
  - Tell the orchestrator before saving any of Jah's textures, then report the changes to jam-submission.
- **Packaging (21:20), with the orchestrator's go: world-jump owns HLOD and the navmesh.** Neither exists in Gray
  London.
  - **Navmesh.**
    - Next editor row: a **static** navmesh bounded to the Tower district only (about 1.2 × 1.0 km with margin;
      about 10–20 MB cooked), built in the editor with only the district loaded. Our own `LT_RecastNavMesh` is spawned
      **before** the bounds volume, so the editor doesn't auto-create one. It is not spatially loaded, with ledge
      filter None.
    - Fallback if memory or cook size won't allow it: Dynamic + "Generate Navigation Only Around Navigation
      Invokers". That needs a project setting plus invoker components on the hero and NPCs (code in my world-jump
      module, a train).
    - Never a city-wide navmesh (12.5 km).
  - **HLOD.** Instanced layer only, Merged left unbuilt; the orchestrator decides.
    - The run: `UnrealEditor-Cmd.exe <proj> /Game/GrayLondon/Maps/GrayLondon_Geodata -run=WorldPartitionBuilderCommandlet -Builder=WorldPartitionHLODsBuilder`.
    - It writes new HLOD actor packages into Jah's map.
    - **Only with the editor closed** (memory) and under a save freeze. It must finish before packaging's measurement
      cook at about 00:30, so it needs a slot in a train window.
    - Keeping Merged out means either changing Jah's Merged HLOD layer asset or the partition's HLOD setup in the
      .umap. Both touch Jah's files, so that's the orchestrator's call.
    - Cheaper skyline fallback: 10–15 landmark actors set not spatially loaded. That costs memory, not cook size,
      and also touches Jah's actors.
- **The single side is Red / Giltside (fixed 21:25).** `DA_WorldJumpConfig` > DefaultWorld was **Gray**, while Auto
  markers resolve to Red (hard-coded when world jump is inactive). I had told the side-lookup owners "Red"; it is now
  set to Red and saved, so `GetWorldAtLocation` and the markers agree. `GetCurrentWorld()` returned the stored value,
  Gray, unless a jump set it. From train #14 it falls back to DefaultWorld (`ReflectionsWorldJumpSubsystem.cpp`,
  same UFUNCTION signature). Until then, the callers of `GetCurrentWorld` still see Gray: cutscenes, the game-flow
  checkpoint, quests, story markers and voice.
- **Row B probe (21:16–21:19, 20 s PIE):** world time advanced and the game wasn't paused. The hero
  (`BP_HeroSampleCleanTest`) spawned at our start on Great Tower St, (3292.9, 310.9, 1.0) m, standing on the ground,
  with no Lumen warnings. The engine chooses randomly between our start and Jah's Trafalgar Square start; our start
  has PlayerStartTag `Lanthorne` so the game mode can prefer it (a code change for the game mode's owner).
- **Quest-system (train #14):** with `IsWorldJumpActive()` false, world-jump objectives auto-complete, side filters
  match everywhere, the PageFound sides map to the 1st/2nd/3rd page, shards from any side count, and goTo radius is at
  least 25 m. All 54 quest marker names resolve in `graylondon_markers.json`. **Keep that file's name/tags format:
  quests' checker reads it directly.**
- **Crowd-react:** the map short name is `GrayLondon_Geodata`. See the lane requirements in section 3.
- **Orchestrator (21:15):** don't touch mock maps (none were touched) and keep memory low. 2.7 GB of virtual memory
  was free at the time, so load only the district and build neither HLOD nor full-map nav.

## Step 0, my next editor row (~10 min, no saves)

1. Open `GrayLondon_Geodata`, timing it and recording the editor working set.
2. Dump the World Partition actor descriptions: classes, data layers, landmark labels and bounds.
3. Calibrate the axes with the Tower landmark.
4. Load the district region, timing it and recording memory.
5. Short PIE at Tower Hill:
   - frame stats;
   - can the hero walk Tower Hill → Tower Bridge;
   - is there roof collision;
   - is there a navmesh at all.
6. Switch the editor back, **saving nothing**.

I'll report the numbers and an updated go/no-go.
