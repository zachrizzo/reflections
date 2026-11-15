# Make Gray London Bustle Without More MetaHumans

Gray London will not reach GTA density tonight by adding people. It will feel busy if the people it can afford **do visible things, in the right places, alongside a crowd the player hears more than sees**. Today the map spawns **zero** ring walkers. A grep of its 2,151 external actor packages finds no ZoneShape, no ZoneGraphData and no navmesh, and the ring can only spawn onto ZoneGraph lanes. That makes scripted `CitySidewalk` lanes along the hero route the single critical-path item ([external actors](../Content/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/); [ring source](../Source/reflections/Crowd/ReflectionsCrowdRingSubsystem.cpp)). The cost ceiling is hard. In the package, each MetaHuman costs **about 0.43 ms of game thread, 0.30 ms of render thread and 0.14 ms of GPU**, and perf already advises **about 14 active NPCs** in a fight to hold 60 fps on a mid-range PC ([Perf README](../ArtDirection/Perf/README.md)). Every new face adds **50–60 MB** to a package that is probably already over the 1 GB itch.io limit ([Packaging README](../ArtDirection/Packaging/README.md)). In practice that caps a calm street at roughly **24 MetaHuman actors**: 12 ring walkers, about 6 people pinned in street scenes, and up to 6 of Lives' named people. Three cheap additions multiply what those 24 can sell:
- a lightweight "scenario spot" layer that plays looping clips on the hidden walker skeleton, which already holds the Game Animation Sample's bench-sit set and 13 standing idle breaks;
- a crowd-murmur bed whose loudness follows how many people are nearby, mixed from the **3,312 crowd voice lines already recorded**, since no ambience bed exists;
- a panic loop that spreads outward from violence, empties the street through exits the player can't see, then refills it.

Mass with MetaHuman Crowd is the right far tier for the commercial game: 40 Mass pedestrians cost about **1 ms of game thread**, while each actor walker costs about 0.5 ms. But it is experimental, has no usable look and no crowd level, and still drags a 108.8 MB prototype collection into the cook. Defer it, and strip its always-cook entry tonight.

## Gray London has a working crowd stack but nowhere for it to walk

The crowd that would fill Gray London is already written and was verified once. `UReflectionsCrowdRingSubsystem` keeps `Crowd.Ring.Count` civilians around the hero (default **12**, clamped to 64). It spawns them through `SpawnNpc("Civilian")`, so they "react, flee, die and talk like every NPC". It adds at most one walker per 0.5 s check, **between 15 m and 45 m** from the hero. After the initial fill, it spawns only where the player can't see: anything within 60 m, inside a 65° half-angle cone, with a clear line of sight counts as seen. It recycles calm, unseen walkers beyond **55 m** after 2 s ([ring header](../Source/reflections/Crowd/ReflectionsCrowdRingSubsystem.h); [ring source](../Source/reflections/Crowd/ReflectionsCrowdRingSubsystem.cpp)). Four more subsystems sit on top:
- **Stroll** walks the civilians in 10–30 m legs along the nearest lane, steering at a point 220 cm ahead ([stroll source](../Source/reflections/Crowd/ReflectionsCrowdStrollSubsystem.cpp)).
- **LOD** drops their animation to 30 Hz beyond 18 m, 15 Hz beyond 40 m and 6 Hz when hidden.
- **Yield** steps them out of soldiers' paths.
- **The chat director** plays baked 2–4-person conversations ([CrowdInfrastructure README](../ArtDirection/CrowdInfrastructure/README.md)).

On the now-deleted mock city, the ring filled all 12 walkers in **15.6 s** with zero bone-buffer warnings ([ring_result.json](../Saved/CrowdReactions/ring_result.json)). Its verification script has been rewritten for Gray London, but no Gray London result exists yet ([verify_ring.py](../Saved/CrowdReactions/verify_ring.py)).

The dependency is ZoneGraph. The ring finds spawn points with `FindNearestLane`, and with no lane data it logs "has no ZoneGraph lanes; no walkers." once and stops. Gray London has **0 ZoneShape, 0 ZoneGraphData, 0 RecastNavMesh and 0 NavMeshBoundsVolume** packages. So today its streets hold only Lives' named people (at most 6 at once) and squads ([CrowdInfrastructure README](../ArtDirection/CrowdInfrastructure/README.md); [Lives README](../ArtDirection/Lives/README.md)). World-jump's plan is about 40–60 `CitySidewalk` ZoneShapes over the Tower district. They would be cut from OSM highway ways and offset to the kerb by road width / 2 + 1.5 m, or traced from Jah's `Sidewalk*` meshes on a 2 m grid. The shapes stay non-spatially-loaded under one `ZoneGraphData` actor ([GrayLondon plan](../ArtDirection/WorldJump/GrayLondon_Plan.md)). No generator script exists yet.

The engine cooperates:
- `UZoneShapeComponent` exposes `Points`, `LaneProfile` and `Tags` as BlueprintReadWrite, so an editor script can fill them ([ZoneShapeComponent.h](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/Runtime/ZoneGraph/Source/ZoneGraph/Public/ZoneShapeComponent.h)).
- In 5.9, both `AZoneShape` and `AZoneGraphData` default to not spatially loaded, so the whole lane graph stays resident under World Partition ([ZoneShapeActor.cpp](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/Runtime/ZoneGraph/Source/ZoneGraph/Private/ZoneShapeActor.cpp); [ZoneGraphData.cpp](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/Runtime/ZoneGraph/Source/ZoneGraph/Private/ZoneGraphData.cpp)).
- Building while editing is **off by default**, so someone must run Build ZoneGraph by hand ([ZoneGraphSettings.h](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/Runtime/ZoneGraph/Source/ZoneGraph/Public/ZoneGraphSettings.h)).

Python access to the `FZoneShapePoint` fields is still untested. That alone justifies a two-block pilot before scripting the whole route. One rule matters more than lane geometry: lay pavement lanes only. The ring and stroll follower take any lane near a walker and do not filter by tag, so a carriageway lane would march civilians into traffic ([GrayLondon plan](../ArtDirection/WorldJump/GrayLondon_Plan.md)).

Two facts make a fallback possible. First, stroll's ordinary mode needs neither ZoneGraph nor a navmesh. It picks a goal 4–14 m from home and checks it with a floor trace and a capsule sweep ([stroll source](../Source/reflections/Crowd/ReflectionsCrowdStrollSubsystem.cpp)). Hand-placed street scenes that spawn their own occupants can therefore still mill about if lanes slip. Second, the ring searches for lanes only near the hero. The "density dilution" trap therefore doesn't apply to it. That trap belongs to Mass spawners, which spread their `Count` uniformly over every matching lane in the world ([MassEntityZoneGraphSpawnPointsGenerator.cpp](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/Runtime/MassGameplay/Source/MassSpawner/Private/MassEntityZoneGraphSpawnPointsGenerator.cpp)). It matters only when Mass returns. The navmesh is world-jump's item for Lives and squads, not a crowd prerequisite.

The dormant Mass crowd was switched off for **looks and pipeline maturity, not CPU**:
- every pedestrian was the same Coin Clerk with a white bald head and floating grey garments;
- the groom entries produced null card meshes;
- the actor representation threw null-instance errors;
- a promoted pedestrian turned into a different person, because `DT_CrowdLookMap` had no rows.

The orchestrator declared it "no-go for the jam" ([CrowdInfrastructure README](../ArtDirection/CrowdInfrastructure/README.md)). Its crowd level was deleted with the sample maps, `DT_CrowdLookMap` is missing, and the planned `/Game/Characters/Lanthorne/CrowdMass/` collections were never created ([CrowdLooks README](../ArtDirection/CrowdLooks/README.md)). Yet `DefaultGame.ini` still always-cooks `/Game/Crowd/City`, which pulls in the **108.8 MB** prototype collection, estimated at 20–80 MB cooked ([DefaultGame.ini](../Config/DefaultGame.ini); [Packaging README](../ArtDirection/Packaging/README.md)).

## About two dozen MetaHumans is the ceiling, so the bustle must be implied

The packaged numbers bound everything. In the train #5 package, each MetaHuman was about 12 skeletal mesh components and 5 groom components. Each extra character added 30 draw calls, 0.11 M triangles and 1.0 ms of worker-thread animation, and MetaHumans rendered at LOD0 at every distance. The build ran 132 fps idle with 7 characters and 75 fps in combat with 23 on the RTX 5080 dev box. Perf estimates **50–58 fps in heavy combat on a mid-range PC**, and suggests a cap of about 14 active NPCs in a fight unless its fixes land ([Perf README](../ArtDirection/Perf/README.md)).

In PIE, the hidden GASP driver behind each walker adds 1–2.5 ms of worker-thread motion matching, about 0.3 ms of CharacterMovement and 0.2 ms of mesh tick. The ring of 12 cost **about 5.7 ms of game thread and 1.1 ms of GPU even with LOD**. During replacements it produced one 228 ms frame ([CrowdInfrastructure README](../ArtDirection/CrowdInfrastructure/README.md); [ring_result.json](../Saved/CrowdReactions/ring_result.json)). Perf also logged unexplained 40–75 ms PrePhysics stalls in calm areas where only strolling walkers were present, and the hidden drivers are its prime suspect ([Perf README](../ArtDirection/Perf/README.md)).

From that per-character slope, 24 MetaHumans cost about **10 ms of game thread and 7 ms of render thread for characters alone**, before Gray London's own geometry, which nobody has measured. That keeps the dev box comfortable but leaves a mid-range PC near 50 fps. London's frontages help: most of the ring sits behind buildings at any moment, and hidden walkers drop to 6 Hz. So the working rule is **24 actors in a calm street, falling toward 14 active in a fight** as civilians flee out of view and street scenes stop refilling.

The outside evidence says scaling actors further is a dead end. Epic staff state that skeletal mesh "wasn't designed for 100+ on-screen components". They add that City Sample uses "roughly 8 full actors and vertex animation (VAT) for the rest" ([Epic forum](https://forums.unrealengine.com/t/metahuman-skin-cache-retains-lod0-entries-for-every-npc-regardless-of-camera-distance/2728166)). Grooms alone rule out mass MetaHumans: 50 characters with card grooms spent about **6 ms of render thread on hair** ([Epic forum](https://forums.unrealengine.com/t/high-render-thread-cost-of-groom-bindings-even-on-rigid-mode/2725272)). They also held about **800 MB of groom VRAM** that stays resident at every LOD ([Epic forum](https://forums.unrealengine.com/t/groom-lod-data-remains-fully-resident-in-vram-regardless-of-distance-lod-level/2715458)). Assassin's Creed Unity's tiers draw the same line. It ran fully featured NPCs only within 12 m, capped at 40. Beyond that came "puppets" out to 40 m, and past 40 m bulk NPCs costing **under 25 µs each** ([GAME Watch](https://game.watch.impress.co.jp/docs/news/20150307_691715.html)).

The project's own Mass spike fits this. It measured 40 pedestrians at about **1.0 ms of game thread and 0.4 ms of GPU**: roughly twenty times the actor walkers' density per millisecond ([mass_spike_result.json](../Saved/CrowdReactions/mass_spike_result.json)). The comparison is loose, though: Mass had one look, no grooms, and ran in a noisy editor.

Package size and memory close off the remaining routes:
- The zip must stay under 1 GB. Train #5 zipped to 734 MB.
- Gray London alone is estimated at 250–470 MB cooked against a 120 MB budget, which puts the package at "about 1.0–1.3 GB … likely over 1 GB unless something is cut".
- The crowd and NPC MetaHumans already use **301 MB of their 320 MB** budget, and each extra MetaHuman costs about 50–60 MB ([Packaging README](../ArtDirection/Packaging/README.md)).

Tonight's crowd work must therefore be net-negative on size: no new faces, small props, tiny clips, and the always-cook removal. On the 31 GB machine, the plan budgets +1–3 GB for the editor and +1–2 GB for PIE, "not while crowd-looks builds MetaHumans". At 21:15 the orchestrator saw only 2.7 GB of free virtual memory ([GrayLondon plan](../ArtDirection/WorldJump/GrayLondon_Plan.md)). Any MetaHuman Crowd collection build belongs after the jam; City Sample's Big City recommends 64 GB of RAM ([Epic City Sample](https://dev.epicgames.com/documentation/unreal-engine/city-sample-project-unreal-engine-demonstration)). Variety stays inside the cast. Gray London is single-sided Giltside, so every walker draws from the 12 Giltside faces ([CrowdInfrastructure README](../ArtDirection/CrowdInfrastructure/README.md)). The twelve grey Pewterside palette swaps exist. Whether grey belongs on a Giltside street is a side-identity call for the user ([CrowdLooks README](../ArtDirection/CrowdLooks/README.md)).

## Scenario spots turn the same bodies into a working street

Stationary scenes are the cheapest life a street can buy. They need no pathing and little avoidance, and they read instantly as "people doing things". Hitman's crowd tools let designers place groups that look at a point of interest or hold a shape ([Game Developer](https://gamedeveloper.com/design/the-ai-of-hitman-2016-)). AC Unity's level-design tool placed bulk NPCs and scripted "Shepherd" NPCs, who carry the AI for a group of cheap ones ([GAME Watch](https://game.watch.impress.co.jp/docs/news/20150307_691715.html)). GTA's scenario points are the model the user has in mind, but the research found no primary source on them. The design below follows the documented Hitman and AC Unity equivalents instead.

The project's architecture fits this well. Combat clips are played as DefaultSlot montages on each NPC's hidden walker pawn (`BP_SampleCMCClean2`, skeleton `SK_UEFN_Mannequin`), because playing them directly on the visible MetaHuman crashed the shared editor. The visible body then follows through its retarget ([CombatMelee README](../ArtDirection/CombatMelee/README.md)). One clip on that skeleton therefore animates every look in the cast. The skeleton already owns much of what street scenes need:
- the Game Animation Sample bench set: ten sit-down approaches (front, back-left, back-right, 90° left and right, each off either foot), a seated idle loop and a stand-up, each with a montage ([Bench folder](../Content/Characters/UEFN_Mannequin/Animations/Interactions/Bench/));
- thirteen standing idle-break variants with their idle loops ([Idle folder](../Content/Characters/UEFN_Mannequin/Animations/Idle/));
- relaxed head-turn poses for window-shopping and onlookers ([Poses folder](../Content/Characters/UEFN_Mannequin/Animations/Poses/)).

New loops come from the existing Kimodo route. `author_melee_kimodo.py walker` retargets Kimodo takes straight to the walker. Kimodo keeps the pelvis pinned, which suits idles. It does not animate fingers, but the tool's `fist` stage bakes in a grip. `AS_Melee_Shield_March_Hold_Walker` is already a 2 s seamless upper-body loop "while walking or marching", which is exactly the shape of a carrying-goods layer ([CombatMelee README](../ArtDirection/CombatMelee/README.md)). Props can attach the way `Combat.ShieldProp` places shields from the body's reference pose ([NPC_Unified README](../ArtDirection/NPC_Unified/README.md)).

The proposed design is one small runtime subsystem owned by crowd-react. It reads a scenario list written in the same east_m/north_m convention as the markers file, and spawns spot actors at play time, so nobody edits Jah's World Partition map ([GrayLondon OurActors](../ArtDirection/WorldJump/GrayLondon_OurActors.md)). Spots work in two modes:
- **Claimable.** A ring walker whose stroll leg passes a free spot takes it for a while, then walks on. This costs no extra bodies.
- **Pinned.** Vendors and queue heads spawn their own occupant through `SpawnNpc` when the hero is near and the spot is out of view.

Each slot holds a weak reference that is re-checked every tick, and an invalid, dead or panicking occupant simply stops counting. Spots should sit against shopfronts or the kerb, off the lane centreline. Walker capsules don't collide with each other, and the actor stack has no walker-to-walker avoidance, so a walker on the lane would stroll straight through a seated group ([CrowdInfrastructure README](../ArtDirection/CrowdInfrastructure/README.md)). The unbuilt "chat spot" proposal (2–4 slots, about one per 15 m of pavement) folds into this design as one spot type ([CrowdInfrastructure README](../ArtDirection/CrowdInfrastructure/README.md)).

| Scenario | Animation on the walker skeleton | Prop or dressing | Existing system reused | Tonight? |
|---|---|---|---|---|
| Chatting group (2–4) | Relaxed idle loop, idle breaks, head turns | None | Chat director (`MaxActive` 3, `HearDistance` 25 m, `MaxSpread` 4 m); Lives street chats | Yes |
| Window-shopping | Relaxed idle loop and head-turn poses | CityDetailPilot shopfronts ([README](../ArtDirection/CityDetailPilot/README.md)) | Stroll hand-off | Yes |
| Bench sitting | GASP bench approach, idle and stand-up montages | Bench mesh from the map or Codex | None (needs the walker capsule's movement and collision paused while seated) | Yes, if a bench exists |
| Vendor and customer | Idle breaks plus a Kimodo "calling out" loop | Barrow or stall (Codex) | Lives `Remark`/`Talk` barks ([Lives README](../ArtDirection/Lives/README.md)) | Yes, pinned |
| Queue at a door | Idle loop, step forward on a timer | Door or notice | None | Stretch |
| Smoking or leaning | Kimodo hand-to-mouth or wall-lean loop | Clay pipe; tiny smoke wisp | SpellVFX for the wisp | Stretch |
| Carrying goods | Kimodo upper-body hold loop, like Shield March Hold | Basket, crate, sack | Ring and stroll walkers | Stretch (confirm the walker's upper-body slot) |

Who walks matters too. In a field study of about 1,500 pedestrian groups, **up to 70% of people on a commercial street moved in groups** ([PLoS ONE via RePEc](https://econpapers.repec.org/RePEc:plo:pone00:0010047)). Twelve lone walkers therefore read as artificial. Pairs of a leader and a side-by-side follower would fix that, but they are a stretch goal tonight. Where the crowd stands matters as much as its size. AC Syndicate's London cut Unity's crowds down to "groups of few dozen citizens in various locations" ([Digital Foundry via mirror](https://venvegame.netlify.app/host-https-www.eurogamer.net/digitalfoundry-2015-assassins-creed-syndicate-face-off)), and reviewers called the result stagnant and empty ([PCWorld](https://www.pcworld.com/article/3008718/assassins-creed-syndicate-review-one-of-the-best-but-its-still-just-assassins-creed.html)). The lesson is to concentrate people on the route the player actually walks. That route runs from `LT_PlayerStart_Intro` on Great Tower Street toward Tower Hill and Leadenhall, with beats 300–600 m apart ([GrayLondon plan](../ArtDirection/WorldJump/GrayLondon_Plan.md)). Two more rules:
- **Pre-warm the ring before the intro fade.** The initial fill may spawn in view, so without a pre-warm the street fills in front of the player over about 15 seconds.
- **Never despawn anyone in view.** Cyberpunk 2077's patch 1.3 made crowds "instantly despawn when V turns around", and modders rushed out fixes ([Gamepressure](https://www.gamepressure.com/download/cyberpunk-2077-crowd-despawn-fix-v10-mod/ze13a27)).

Sound is the highest-leverage piece, and the project has the raw material but no bed. Audio's README records **137 designed crowd voices and 3,312 generated lines**. It also states plainly that "no ambience beds … were requested or made" ([Audio README](../ArtDirection/Audio/README.md)). Prototype's New York faded in its first crowd layer at **around 10 nearby people**. It needed separate small-crowd and large-crowd recordings, because "volume alone does not represent density very well". Its "walla" (background crowd murmur) generator randomised gap, pitch and volume across about 400 reaction files, and raycasts stopped crowds being heard through walls ([Game Developer](https://www.gamedeveloper.com/audio/dynamic-game-audio-ambience-bringing-i-prototype-i-s-new-york-city-to-life)). CRI's equivalent crossfades loops for 2–4, 4–8 and 10+ people ([CRIWARE](https://blog.criware.com/index.php/2023/05/08/crowd-system/)). The Outer Worlds keeps walla audible at about 40–60 m, so players can hear crowds they cannot see ([Audiokinetic](https://audiokinetic.com/the-sound-of-the-outer-worlds-part-1)). A MetaSound or SoundCue generator can follow the same pattern:
- mix the existing lines at low gain;
- drive it by a count of NPCs within about 30 m;
- add an always-on distant city bed and a panic layer drawn from the fear and flee barks.

That adds near-zero package size and makes a street sound twice as full as it looks.

## Violence should ripple outward, empty the street, then refill it

Reactions already exist, so the job is to keep the new layers from fighting them. Ring walkers are full Civilian NPCs that flee, scream and die. Stroll hands the body back on any non-calm reaction. The LOD subsystem wakes a walker to full rate for any NPC stimulus within 25 m. The ring releases walkers the villain converts ([CrowdInfrastructure README](../ArtDirection/CrowdInfrastructure/README.md)). The scenario layer has to follow the same discipline. On a non-calm reaction, death, recycle or conversion, it must stop the montage within a fraction of a second, free the slot, and hand the body to the reaction component.

This is where Smart Objects would hurt tonight. A Smart Object claim reserves a slot until it is explicitly released ([Epic](https://dev.epicgames.com/documentation/unreal-engine/smart-objects-in-unreal-engine---overview)), and claims leak when the claimant dies or aborts first ([Bugnet](https://bugnet.io/blog/fix-unreal-smart-objects-claim-not-released)). Mass adds two traps of its own:
- the Find and Claim tasks must be separate StateTree states, or the claim runs before the find completes ([Epic forum](https://forums.unrealengine.com/t/5-6-mass-ai-smart-object-invalid-claim-handle-id/2561118));
- Mass claims with its own user-data type, which clashes with actor-based Smart Object components ([Epic forum](https://forums.unrealengine.com/t/smartobjectcomponent-expects-fsmartobjectactoruserdata-but-mass-uses-fsmartobjectmassentityuserdata/2651672)).

Even City Sample did not ship Smart Objects in its city ([Epic City Sample](https://dev.epicgames.com/documentation/unreal-engine/city-sample-project-unreal-engine-demonstration)). In a game where combat kills street NPCs regularly, weak-reference slots that are re-checked every tick make the leak structurally impossible. Smart Objects, which are not experimental in 5.9, can come back after the jam behind a release-on-every-exit rule and a sweeper.

Hitman offers the best-documented panic model. Violence emits "behaviour zones" around the event: people in the line of fire go prone, those nearby panic, those further out become alert. Panic accumulates as the player moves, and fleeing agents follow precomputed per-exit flow fields on a coarse 2D grid instead of querying the navmesh ([Game Developer](https://gamedeveloper.com/design/the-ai-of-hitman-2016-)). The same article names Hitman's weak spot: its crowds "never calm down once you set them off". A story game can do better with three cheap moves:
- **Delay outer rings.** Hold each ring's reaction by distance (a suggested 0.1–0.3 s per ring) so the panic visibly spreads instead of firing on one frame.
- **Flee to hidden exits.** Send fleeing civilians toward exits out of view, where the ring can quietly retire them.
- **Refill after a lull.** After a quiet cooldown, refill the street out of view, with a few onlookers facing the fight site and the murmur ramping back up.

That refill loop is an inference; no shipped-game source documents one. One code fact needs checking before trusting it: the ring recycles only *calm* walkers, so civilians that never return to calm could leave the street stuck empty or stuck fleeing ([ring header](../Source/reflections/Crowd/ReflectionsCrowdRingSubsystem.h)). For the commercial version, the dormant Mass subsystem already turns NPC stimuli into ZoneGraph disturbance annotations that pedestrians flee along. It also promotes pedestrians within 7 m of a stimulus into full NPCs, up to 6 at a time, which is Hitman's "possession" by another name ([city subsystem source](../Source/reflections/Crowd/ReflectionsCrowdCitySubsystem.cpp)). Mass's `DelaySignalEntities` gives the delayed ripple for free ([Epic API](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/MassSignals/UMassSignalSubsystem)).

## The ranked plan: lanes tonight, scenes by noon, Mass after the jam

Times below count from now (T, about 18 hours before the 6 PM ET team target). Packaging lists the hard deadline as **8:59 PM ET**, which gives about three hours of buffer ([Packaging README](../ArtDirection/Packaging/README.md)). The world-jump plan sets a **Sunday ~12:00 go/no-go**, roughly T+12h ([GrayLondon plan](../ArtDirection/WorldJump/GrayLondon_Plan.md)). C++ must land in a build-train window, and every PIE test goes through the PIE lock.

### Build before the deadline, in priority order

| Rank | Piece | Owner | Depends on | Time-box | Cut rule |
|---|---|---|---|---|---|
| 1 | Scripted `CitySidewalk` lanes. Pilot 2–3 blocks around `LT_PlayerStart_Intro`, then the hero route to Tower Hill and Leadenhall. Pavement only, a point at least every 10 m, Z +3 cm, then `Crowd.City.SetupZoneGraph`, Build ZoneGraph, and save new packages only. | world-jump with crowd-react; Jah approves anything touching the map. This is the hardest single piece. | Nothing | Pilot by T+3h, route by T+8h | If the pilot fails by T+5h, switch to the fallback below |
| 2 | Walla generator: three density layers mixed from existing lines, a distant city bed, a panic layer, wall occlusion | audio | Nothing (starts now, in parallel) | T+8h | Ship the city bed and one walla layer at minimum |
| 3 | Run `verify_ring.py` on Gray London; pre-warm the ring before the intro fade; keep `Crowd.Ring.Count` at 12 | crowd-react | Rank 1 | T+9h | Raise to 16 only if the packaged run shows headroom |
| 4 | Scenario spot subsystem: weak-reference slots, claimable and pinned modes, montage on the walker, exit on reaction, death or recycle | crowd-react (subsystem); npc-unify (montage and reaction hooks) | A train window | Code by T+9h | Pinned mode alone ships if claiming isn't stable |
| 5 | Spot content: 15–25 spots on the hero route (chat rings, window-shopping at shopfronts, benches, two vendors), from a JSON list | crowd-react, with world-jump and Jah for positions | Rank 4 | T+10h | Chat rings and window-shopping first |
| 6 | Remove `/Game/Crowd/City` from `DirectoriesToAlwaysCook` | packaging, with crowd-react's agreement | Nothing (config only) | Before the final cook | None: est. 20–80 MB saved |
| 7 | Perf fixes #1 and #2: LODSync minimum LOD 1 plus `OnlyTickPoseWhenRendered`, and destroying empty grooms | crowd-looks with perf | The editor closed for asset edits | T+9h | Skip if any shared Common asset would be re-saved |
| 8 | Kimodo loops (vendor call, smoking, carry hold, lean) and props (basket, crate, barrow, pipe) | combat-melee's Kimodo tool owner; Codex for props | Rank 4 | T+10h | Cut first if late |
| 9 | Delayed panic rings and a refill cooldown; confirm that fled walkers get recycled | npc-unify with crowd-react | Ranks 3–4 | T+10h | Keep today's flee if risky |
| 10 | Gate: packaged perf and size run on Gray London, crowd on and off | perf, packaging | All of the above | T+10h to T+11.5h | Decides 12 vs 16 walkers and the pinned-spot cap |

If lanes are not in by T+5h, ship the **lane-free fallback**: pinned spots spawn their occupants on the hero route, nearby occupants mill using stroll's lane-free 4–14 m mode, and the walla bed implies the rest. The street then reads as stationary scenes plus sound rather than flowing traffic. That is weaker, but needs no ZoneGraph and no navmesh ([stroll source](../Source/reflections/Crowd/ReflectionsCrowdStrollSubsystem.cpp)).

### Tier ladder

| Tier | Jam representation | Distance | Count cap | Animation rate | Commercial target |
|---|---|---|---|---|---|
| Near / engaged | Any NPC actor, full rate | 0–18 m, or woken by a stimulus within 25 m | ≈14 active in combat | Every frame | Full MetaHuman actor, 0–12/15 m, 10–16 at once, with the Animation Budget Allocator at about 1–2 ms ([Epic](https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-budget-allocator-in-unreal-engine)) |
| Ring walkers | MetaHuman walkers on `CitySidewalk` lanes | Spawn 15–45 m from the hero; recycle beyond 55 m when unseen for 2 s | 12 (16 with measured headroom) | 30 Hz at 18–40 m, 15 Hz beyond 40 m, 6 Hz hidden | Mid tier: "UE Optimized – Low" MetaHumans with merged meshes, no groom components and no face animation, 15–40 m, 20–30 at once, ≤15 Hz ([Epic](https://dev.epicgames.com/documentation/metahuman/assembly)) |
| Scene occupants | Pinned occupants plus ring walkers in claimed spots | Activate within ~60 m; retire beyond ~80 m when unseen (proposal) | 6 pinned | Same as the ring | Smart Object slots with claim hygiene |
| Lives people | Named MetaHumans | Spawn within 35 m; full rate within 60 m | 6 | Full | Lives schedules that drive spot use |
| Implied | Walla, fog, window light | 40–150 m | n/a | n/a | Far tier: Mass entities as MetaHuman Crowd instanced skinned meshes (or bone-mode VAT), 40–120 m, 300–500 at once, shadows off beyond ~50 m |
| Off | Nothing | Beyond ~150 m | n/a | n/a | Mass simulation only, 1,000–3,000 entities, culled |
| **Calm total** | **≤24 MetaHuman actors** | | | | Promote an instanced pedestrian to a full NPC within 7 m of violence, carrying its look through `DT_CrowdLookMap` |

The commercial ladder sits close to Mass's stock crowd defaults:

| Mass tier | Representation | Starts at | Max entities |
|---|---|---|---|
| High | Full actor | 0 m | 10 |
| Medium | Low-res actor | 10 m | 20 |
| Low | Instanced mesh | 50 m | 500 |
| Off | Nothing rendered | 100 m | — |

Those caps come from `MassCrowdVisualizationTrait.cpp` ([UE 5.9 source](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/AI/MassCrowd/Source/MassCrowd/Private/MassCrowdVisualizationTrait.cpp)). A density target of 1,000–3,000 simulated agents, with about 500 instanced and about 30 actors, is the research's conservative starting point.

### Defer to after the jam

Ten items wait for the commercial build:
- Reviving the Mass city crowd on Gray London: a crowd level or in-map spawner, entity configs, and `Crowd.Mass.HostMap`.
- Building real MetaHuman Crowd collections from the 20 finished faces, plus the missing look map. The collection builds are memory-heavy, and look quality was the original blocker.
- A packaged spike comparing instanced skinned meshes with bone-mode VAT for the far tier. Epic now recommends the former, but 5.8 users report an animation-pool GPU memory leak and stuck reference poses ([Epic forum](https://forums.unrealengine.com/t/animbank-and-instanced-skinned-mesh-component/2734825); [leak report](https://forums.unrealengine.com/t/mass-crowds-using-skinnedmeshinstance-leak-gpu-memory-every-wave-of-spawned-and-killed-entities-permanently-grows-the-animation-track-pool-5-8/2742508); [reference-pose report](https://forums.unrealengine.com/t/instanced-skinned-meshes-permanently-render-reference-pose-when-their-chunks-fall-outside-the-scene-culling-cell-hierarchy-uncullable-range-stale-chunk-attributes/2743519)). VAT, meanwhile, went GPU-bound at about 200 characters on an RTX 3060 Mobile and an RTX 2060 Super ([Epic forum](https://forums.unrealengine.com/t/animtotexute-is-putting-pressure-on-basepass-and-shadowdepths/1145774)).
- Smart Objects for spots, so Mass entities can use them too.
- A merged, groom-free mid tier with the Budget Allocator. URO (skeletal-mesh update-rate optimisation) on walkers was declined before the jam for T-pose risk.
- Removing the duplicate driver skeleton from background actors.
- Crossings and intersections.
- Flow-field panic.
- Time-of-day and district density.
- A Soundscape-style mix driven by live entity positions.
- Walking pairs, if they don't make it tonight.

### Key risks

| Risk | Evidence | Mitigation |
|---|---|---|
| MetaHuman cost | About 0.43 ms game thread per packaged MetaHuman; about 14 active NPCs is the mid-range cap; 40–75 ms calm-area stalls blamed on drivers | Hold 24 calm; LODSync min LOD 1; destroy empty grooms; no new faces; measure packaged before raising counts |
| Package size | Likely 1.0–1.3 GB against a 1 GB zip limit; NPC MetaHumans at 301 of 320 MB | Zero new faces; props ≤5 MB total with 512–1K textures; remove the `/Game/Crowd/City` always-cook; the SM5 drop is the next lever ([Packaging README](../ArtDirection/Packaging/README.md)) |
| Mass experimental status | MassGameplay, MassAI and MassCrowd are 0.4; ZoneGraph is 0.5; MetaHumanCrowd and AnimToTexture are experimental ([UE 5.9 plugins](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/)); City Sample crowds broke on 5.7 ([Epic forum](https://forums.unrealengine.com/t/ue-5-7-city-sample-broken/2701997)); stale ZoneGraph data after an engine version round trip dropped one project to 6 fps ([Epic forum](https://forums.unrealengine.com/t/ue-5-6-mass-ai-severe-fps-drop-after-5-8-1-downgrade-invalid-lane-location-fixed-by-recreating-zonegraph-data/2742990)) | Ship no Mass in the jam. Keep the lane generator scripted, so ZoneGraph data is rebuilt on every engine bump. The jam ring already depends on experimental ZoneGraph, but only for lane queries. These plugin versions were read from the launcher install, while the project uses a custom engine build, so recheck them there |
| Smart Object slot leaks on NPC death | Claims persist until released; death skips the release ([Bugnet](https://bugnet.io/blog/fix-unreal-smart-objects-claim-not-released)) | Tonight: weak-reference slots re-checked every tick. After the jam: release in the death, flee, recycle, conversion and unload paths, plus a sweeper, with one claimant type per object |
| Shared-skeleton breakage from MetaHuman builds | `metahuman_base_skel`, which five bodies share, was saved at 19:28 without its `root` bone, and about half the cast stood in reference pose until restored from commit e9f3c59 ([NPC_Unified README](../ArtDirection/NPC_Unified/README.md)) | Freeze crowd-looks builds before the final train. Run a pre-train check that every shared skeleton still starts with `root` and that `SK_UEFN_Mannequin` is byte-identical: the hero's motion matching and every driver use it, and Kimodo clips target it. Put prop sockets on meshes, never on shared skeletons. `HideUntilPosed` only hides spawn frames, not a broken skeleton |
| Memory on 31 GB | 2.7 GB of free virtual memory at 21:15 | One PIE at a time under the lock; no MetaHuman builds during crowd tests; short PIE scripts |
| Spawn hitches and pops | A 228 ms frame during ring replacements; walker capsules ignore each other | Keep one spawn per 0.5 s with async preload; place spots off the lanes; pre-warm before the fade |
| Commercial cleanliness | SimpleRed's Hunyuan3D-2 garments "are not licensed for every market" ([CrowdLooks README](../ArtDirection/CrowdLooks/README.md)) | Make Codex props only with a commercially cleared image-to-3D model, and record its licence beside each asset |

### How to measure success

The targets below are proposals, set against the measured baselines. The tools already exist: `verify_ring.py`, `Crowd.LodDump`, the crowd telemetry actor, perf's `batch2.ps1`, `stat unit` and Insights ([Perf README](../ArtDirection/Perf/README.md)).

| Metric | Target | How |
|---|---|---|
| Visible life at the start | ≥15 people in view on Great Tower Street within 10 s of gaining control; ≥3 scene types within a 60 s walk | `verify_ring.py` extended with spot counts; a screenshot |
| Variety | No identical face within 20 m | `Look_Id` tags across `Crowd.LodDump` |
| Calm performance (packaged, 1080p Epic, dev box) | Game thread median ≤12 ms; ring-on minus ring-off ≤6 ms; p99 ≤33 ms over a 5-minute walk | `batch2.ps1` A/B with `Crowd.Ring.Enable` |
| Combat performance | ≥60 fps on the dev box; mid-range estimate ≥50 fps | Perf's combat run |
| Stability | 0 SpaceBases warnings, 0 arms-out frames, 0 crashes in a 15-minute soak | Log scan; HideUntilPosed reveal timeouts |
| Reaction | 100% of scene occupants within 15 m of a Fireball leave their slot within 0.5 s; 0 leaked slots after 20 kills; ≥70% of slots refilled within 90 s of the last stimulus | A spot-occupancy dump before and after |
| Audio | Walla rises with ≥10 people within 30 m; switches to panic within 1 s of the first flee | Listening test plus cue-parameter log |
| Size and memory | Zip under 1 GB; crowd content ≤ +10 MB net; packaged RAM ≤3 GB and VRAM ≤3.5 GB (baselines 2.0–2.4 GB and 2.3–2.9 GB) | Packaging zip script; perf memory run |

## Conclusion

The bottleneck is not the crowd code, which already spawns, strolls, throttles, yields, chats and flees. It is map data and the cost of each body. Each person on the street is two animated skeletons: a hidden motion-matched driver plus a retargeted MetaHuman with about ten follower meshes. That is why bodies are expensive, and also why scenes are cheap. A single Kimodo take or bench montage on `SK_UEFN_Mannequin` instantly works on every face in the cast, so a jam-night investment in clips and spots pays out across all 24 people the budget allows. The same logic reorders the commercial roadmap. Mass's promotion, disturbance-flee and look-swap code is written, so reviving it is mostly a content problem: a real MetaHuman Crowd collection built from the finished faces, a look map, and a lane graph. All three can be scripted.

The 1 GB ceiling is an itch.io jam rule, not a property of the game. After the jam, the far tier's cost becomes a frame-time question, not a zip-size question, and that is the right moment to spend the memory a proper crowd collection needs.
