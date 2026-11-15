# Project crowd / NPC inventory (Reflections, UE 5.9, as of 2026-11-14 late evening)

All sources are local files in the repo root `C:/Users/zachc/Documents/Unreal Projects/reflections`; link targets below are repo-relative paths. Read-only research. No editor, MCP or git-state changes. Numbers are quoted exactly from the files. Most measured costs are **editor PIE** numbers on a shared, noisy editor (Ryzen 7 9700X, RTX 5080). The packaged numbers come from the train #5 package on `Lvl_HeroSampleCrowd`, a map that has since been deleted.

## Q1. Which crowd systems exist in Source/reflections/Crowd/, what each does, its CVars, target counts and look choice

### Takeaway
The crowd that is live for Gray London is the **actor-based ring crowd**: 12 full MetaHuman civilians spawned through `SpawnNpc("Civilian")` onto ZoneGraph sidewalk lanes, walked by the stroll subsystem and throttled by the LOD subsystem. Yield and chat sit on top of it. The **Mass city crowd** code is intact but dormant: no host map, no crowd level, `Crowd.Mass.Enable 0`. On Gray London today the ring spawns nobody, because the map has no ZoneGraph lanes.

### Cited Findings
**Files present** (21 files, 3,048 lines): `ReflectionsCrowdRingSubsystem`, `ReflectionsCrowdCitySubsystem` (Mass), `ReflectionsCrowdLodSubsystem`, `ReflectionsCrowdStrollSubsystem`, `ReflectionsCrowdYieldSubsystem`, `ReflectionsCrowdChatSubsystem`, `ReflectionsAmbientConversation`, `ReflectionsCrowdLookRow`, `ReflectionsCrowdActorTrait`, `ReflectionsCrowdGridGenerator`, `ReflectionsCrowdTelemetry` — [Source/reflections/Crowd/](Source/reflections/Crowd/)

**Ring crowd (`UReflectionsCrowdRingSubsystem`, tickable world subsystem, Game/PIE only)**
- What it does: keeps a fixed number of civilians around the hero on the ZoneGraph sidewalk lanes of the maps it targets, "so the streets look lived in at a fixed cost". Walkers come from `UReflectionsNpcSubsystem::SpawnNpc` with the Civilian archetype, so they "react, flee, die and talk like every NPC". A calm walker that is far away and unseen is removed and respawned ahead of the hero — [ReflectionsCrowdRingSubsystem.h](Source/reflections/Crowd/ReflectionsCrowdRingSubsystem.h)
- CVars (defaults): `Crowd.Ring.Enable` 1; `Crowd.Ring.Maps` "GrayLondon_Geodata"; `Crowd.Ring.Count` 12, clamped 0–64 in Tick, described as "Each is a full sample-locomotion character"; `Crowd.Ring.MinDistance` 1500 cm; `Crowd.Ring.MaxDistance` 4500 cm; `Crowd.Ring.RecycleDistance` 5500 cm; `Crowd.Ring.RecycleSeconds` 2.0; `Crowd.Ring.Archetype` "Civilian" — [ReflectionsCrowdRingSubsystem.cpp](Source/reflections/Crowd/ReflectionsCrowdRingSubsystem.cpp)
- Mechanics:
  - It checks every 0.5 s (`CheckPeriod`) and spawns at most one walker per check.
  - Spawn points come from `UZoneGraphSubsystem::FindNearestLane` in an 800×800×1000 cm box. It makes 12 tries at yaw ±100° from the hero's heading and rejects any point within 300 cm of another walker.
  - "Seen" means: within 6000 cm of the camera, inside a 65° half-angle cone, and with an unblocked visibility trace. Only the first `Count` spawns may be in view.
  - Each walker is tagged `Crowd_Ring`, `Crowd_LaneWalker`, `Friendly` and `NoVillain`.
  - At BeginPlay it async-preloads the archetype's looks (`RequestAsyncLoad`), so a spawn doesn't stall on a synchronous load.
  - Walkers the villain converts are released from the ring and replaced.
  - With no ZoneGraph data it logs "has no ZoneGraph lanes; no walkers." once and spawns nothing — [ReflectionsCrowdRingSubsystem.cpp](Source/reflections/Crowd/ReflectionsCrowdRingSubsystem.cpp)
- Looks: it passes no look class, so `SpawnNpc` chooses from the Civilian archetype's side-aware pool. "With one side, every walker wears the red (Giltside) looks" on Gray London — [ArtDirection/CrowdInfrastructure/README.md](ArtDirection/CrowdInfrastructure/README.md)

**City crowd (`UReflectionsCrowdCitySubsystem`, Mass / MetaHuman Crowd)**
- What it does: streams a separate crowd level (ZoneGraph shapes and data, a Mass spawner) into a host map at play time. NPC stimuli become ZoneGraph disturbance annotations, which the StateTree flees along. Pedestrians close to a stimulus are "promoted" into full NPC actors through `SpawnNpc("Civilian", …, ResolvePromotedLook(...))` — [ReflectionsCrowdCitySubsystem.h](Source/reflections/Crowd/ReflectionsCrowdCitySubsystem.h)
- CVars (defaults):
  - `Crowd.Mass.Enable` **0**, with the comment "Off by default until the crowd's MetaHuman looks are finished".
  - `Crowd.Mass.HostMap` **""** and `Crowd.Mass.Level` **""**, with the comment: "The Mass crowd is not used for the jam (the ring crowd of actor civilians is): no host map by default, and its old crowd level was removed with the sample maps."
  - `Crowd.Mass.DangerRadius` 1500; `DangerSeconds` 6.0; `PromoteRadius` 700; `MaxPromoted` 6.
  - `Crowd.Mass.LookTable` `/Game/Crowd/City/DT_CrowdLookMap`; `Crowd.Mass.EntityConfig` `/Game/Crowd/City/MEC_CityPedestrian`.
  - `ReleaseDistance` 3000; `ReleaseSeconds` 20.
  - Editor-only console command `Crowd.City.SetupZoneGraph` registers the `CitySidewalk` lane profile (two 150 cm lanes, Forward/Backward, tag mask 1, fixed GUID 5C17E0A1-2B3D4E5F-6A7B8C9D-0E1F2A3B) and turns on build-while-editing — [ReflectionsCrowdCitySubsystem.cpp](Source/reflections/Crowd/ReflectionsCrowdCitySubsystem.cpp)
- Assets on disk now: `Content/Crowd/City/` holds only `MEC_CityPedestrian.uasset` and `ST_CityPedestrian.uasset`. The crowd level `Lvl_HeroSampleCrowd_City` and `DT_CrowdLookMap` are **not present** — [Content/Crowd/City/](Content/Crowd/City/)
- The entity config "keeps the prototype's MetaHuman Crowd visualization (Coin Clerk collection, instanced skinned meshes, baked walk and idle)". It adds movement (140 cm/s ±10%), steering, avoidance, ZoneGraph navigation and the StateTree. `ST_CityPedestrian` runs Wander → Stand 4 s, plus a Flee state on the danger tag at double speed — [ArtDirection/CrowdInfrastructure/README.md](ArtDirection/CrowdInfrastructure/README.md)

**LOD (`UReflectionsCrowdLodSubsystem`)**
- What it does: animation update-rate LOD only. It changes skeletal-mesh tick intervals on actors tagged `NPC_SampleLocomotion` and on their hidden driver pawn. Movement, reactions and damage are untouched. It skips leader-pose followers (garments), because they "never evaluate animation themselves". It rescans every 2.0 s with a `TActorIterator` over all actors and updates tiers every 0.25 s — [ReflectionsCrowdLodSubsystem.cpp](Source/reflections/Crowd/ReflectionsCrowdLodSubsystem.cpp)
- CVars (defaults): `Crowd.Lod.Enable` 1; `NearDistance` 1800; `FarDistance` 4000; `MidHz` 30; `FarHz` 15; `HiddenHz` 6; `WakeRadius` 2500; `WakeSeconds` 9; `QuietDriverCameras` 1 (switches off the GameplayCameraComponent on drivers, "about 0.1 ms" each). Console command `Crowd.LodDump`.
- Tiers:

  | Tier | When | Rate |
  |---|---|---|
  | Full | within 18 m, or woken | every frame |
  | Mid | on screen, 18–40 m | 30 Hz |
  | Far | on screen, beyond 40 m | 15 Hz |
  | Hidden | not rendered in the last 0.3 s | 6 Hz |

  A walker wakes on an NPC stimulus within 25 m, a non-calm reaction, a spell hit, or physics simulation — [ArtDirection/CrowdInfrastructure/README.md](ArtDirection/CrowdInfrastructure/README.md)

**Stroll (`UReflectionsCrowdStrollSubsystem`)**
- What it does: takes over a calm NPC's hidden locomotion pawn through `SetExternallySteered`.
  - It switches the GASP pawn's `CharacterInputState` to WantsToWalk, with strafe, sprint and aim off.
  - Ordinary walkers pick a goal 4–14 m from home, checked with a floor trace and a capsule sweep.
  - `Crowd_LaneWalker` walkers instead walk 10–30 m legs along the nearest ZoneGraph lane, steering at a "carrot" 220 cm ahead and following outgoing links round corners (or turning onto the opposite adjacent lane at dead ends).
  - It idles 1.5–5 s, with a 15% chance of 7–12 s. A walker below 25 cm/s for 1.5 s counts as stuck.
  - It refreshes the candidate list every 1.0 s, and gives the body back on any non-calm reaction — [ReflectionsCrowdStrollSubsystem.cpp](Source/reflections/Crowd/ReflectionsCrowdStrollSubsystem.cpp)
- CVars (defaults): `Crowd.Stroll.Enable` 1; `MinSpeed` 120; `MaxSpeed` 160; `MinRadius` 400; `MaxRadius` 1400; `Debug` 0; `LaneLegMin` 1000; `LaneLegMax` 3000. The lane re-acquire search box is 2000×2000×300 cm.
- Excluded: NPCs tagged `NPC_Soldier` or `NPC_NoStroll`; Enemy, Infected and VillainHost dispositions; archetypes without `Reaction.bRoamsWhenCalm`. Lives adds `NPC_NoStroll` to its named people — [ReflectionsCrowdStrollSubsystem.cpp](Source/reflections/Crowd/ReflectionsCrowdStrollSubsystem.cpp); [ArtDirection/Lives/README.md](ArtDirection/Lives/README.md)

**Yield (`UReflectionsCrowdYieldSubsystem`)**
- What it does: calm civilians step out of the path of moving `NPC_Soldier` actors and of a running player. It adds one extra movement input per frame.
- CVars (defaults): `Crowd.Yield.Enable` 1; `LookAhead` 550; `SoldierHalfWidth` 240; `ToPlayer` 1; `PlayerHalfWidth` 150; `PlayerMinSpeed` 320; `StepSpeed` 240; `Debug` 0 — [ReflectionsCrowdYieldSubsystem.cpp](Source/reflections/Crowd/ReflectionsCrowdYieldSubsystem.cpp)
- The README says: "The walkers' hidden driver capsules don't collide with each other. Without this layer, civilians and soldiers walk through each other." — [ArtDirection/CrowdInfrastructure/README.md](ArtDirection/CrowdInfrastructure/README.md)

**Chat director (`UReflectionsCrowdChatSubsystem`)**
- What it does: plays baked 2–4-person conversations from `DT_AmbientConversations` (generic voices) and `DT_StoryConversations` (named voices) between NPCs the caller has already brought together. The caller is the lives session. The director casts roster voices onto the speakers by sex.
- CVars (defaults): `Crowd.Chat.Enable` 1; `Table` and `StoryTable` (paths above); `MaxActive` 3; `HearDistance` 2500; `MaxSpread` 400; `RepeatSeconds` 300 — [ReflectionsCrowdChatSubsystem.cpp](Source/reflections/Crowd/ReflectionsCrowdChatSubsystem.cpp); [ReflectionsCrowdChatSubsystem.h](Source/reflections/Crowd/ReflectionsCrowdChatSubsystem.h)
- Status: built in train #7, and it loaded 24 conversations. It "has not been verified that a conversation is heard end to end". "Chat spots" (a ChatSpot actor with 2–4 slots, about one per 15 m of sidewalk) are a **proposal, not built** — [ArtDirection/CrowdInfrastructure/README.md](ArtDirection/CrowdInfrastructure/README.md)

**Test-only Mass infrastructure**
- `UReflectionsCrowdGridGenerator`: a flat-grid Mass spawn generator with `MaxTestAgents` 500 (clamp 1–5000). It "does not project to navigation".
- `AReflectionsCrowdTelemetry`: writes frame-interval and MetaHuman Crowd representation counts to `Saved/Profiling/ReflectionsCrowd/`.
- `UReflectionsCrowdActorTrait`: the actor-linkage trait the MetaHuman Crowd visualization requires — [ReflectionsCrowdGridGenerator.h](Source/reflections/Crowd/ReflectionsCrowdGridGenerator.h); [ReflectionsCrowdTelemetry.cpp](Source/reflections/Crowd/ReflectionsCrowdTelemetry.cpp); [ReflectionsCrowdActorTrait.h](Source/reflections/Crowd/ReflectionsCrowdActorTrait.h)

**Verification status**
- The ring was verified only on the now-deleted `Lvl_MockCity`, in a run at 20:23 (`ring_result.json`).
  - 12 walkers filled in 15.6 s.
  - All 12 were "walking on lane" or "idle on lane".
  - 9 of 11 walked 6–13 m in 8 s.
  - After the jump: spawned 39, recycled 12, released to villain 3, failed spawns 3.
  - 0 bone-buffer and 0 SpaceBases warnings — [Saved/CrowdReactions/ring_result.json](Saved/CrowdReactions/ring_result.json)
- `verify_ring.py` was rewritten for Gray London (modified 21:18; header "Ring crowd on Gray London (GrayLondon_Geodata): 12 lane walkers…"). No Gray London result file exists — [Saved/CrowdReactions/verify_ring.py](Saved/CrowdReactions/verify_ring.py)

### Inferences
- Ring, stroll, LOD, yield and chat form one coherent, working actor-crowd stack, reusable as is. Its hard dependency is ZoneGraph lanes (`CitySidewalk`) in the map. Without them, Gray London currently shows **no ring walkers**, only lives' named people (at most 6 spawned at once) and squads.
- The stroll lane-follower and the ring's spawn/recycle logic are independent of the actor representation. They could drive cheaper bodies if those existed.
- The LOD subsystem's 2 s full-world `TActorIterator` rescan is cheap at 12 walkers. It would need replacing with registration if counts grow to hundreds.

### Gaps
- There is no ring or stroll measurement on Gray London, because the map has no lanes.
- No source sets an explicit limit on how many walkers the stroll, yield or chat logic can handle, beyond the ring's clamp of 64.
- No walker-to-walker avoidance (RVO or detour) was found in the actor stack. Only yield (to soldiers and a running player) and stroll's stuck-repick exist.

## Q2. Why the Mass city crowd (MEC_CityPedestrian, ST_CityPedestrian) was switched off, and every measured cost

### Takeaway
Mass was turned off for **looks and pipeline maturity, not CPU cost**. Measured on the game thread it was cheap: about 1.0 ms for 40 pedestrians, against about 0.5 ms *per* actor walker even with LOD. But every pedestrian was the same Coin Clerk with a white bald head, missing brows and lashes, broken groom cards and floating garments. The actor representation path threw null-instance errors, so everything was forced to ISKM. The orchestrator declared Mass a "no-go for the jam" on crowd-looks' recommendation. Its crowd level was then deleted with the sample maps.

### Cited Findings
**Decision**
- "The Mass crowd is **no-go for the jam**, a decision confirmed by the orchestrator on crowd-looks' recommendation." — [ArtDirection/CrowdInfrastructure/README.md](ArtDirection/CrowdInfrastructure/README.md)
- "The Mass prototype collection (`COL_CrowdPrototype_CoinClerk`, white heads, no grooms, floating rags) is off by default since train #6, and Mass is a no-go for the jam (decided with crowd). A smaller crowd of finished actor walkers with the crowd LOD subsystem replaces it." — [ArtDirection/CrowdLooks/README.md](ArtDirection/CrowdLooks/README.md)
- Code comment: "Off by default until the crowd's MetaHuman looks are finished (crowd-looks session)". Also: "The Mass crowd is not used for the jam … its old crowd level was removed with the sample maps." — [ReflectionsCrowdCitySubsystem.cpp](Source/reflections/Crowd/ReflectionsCrowdCitySubsystem.cpp)

**Known problems listed**
- **One look:** every pedestrian is the same Coin Clerk; `MEC_CityPedestrian` lists one Instance.
- **Visual defects:** white untextured bald heads, no brows or lashes, grey garments floating off the body.
- **No crossings:** three separate loops.
- **Swap pop:** a promoted pedestrian turns into a different person until `DT_CrowdLookMap` has rows.
- **Size:** 60 pedestrians is the ceiling until the looks are signed off.
- **Packaging:** the level is loaded by string path, so `/Game/Crowd/City` must be always-cooked — [ArtDirection/CrowdInfrastructure/README.md](ArtDirection/CrowdInfrastructure/README.md)
- **Prototype pipeline defects:**
  - "both groom entries still produced null instanced card meshes".
  - "The high-resolution actor path remains disabled in the prototype because the engine actor template logged null-instance Blueprint errors; all active levels use ISKM as a diagnostic workaround".
  - The clothing conversion needed source LOD0, because the garments have no higher LODs — [ArtDirection/CrowdInfrastructure/README.md](ArtDirection/CrowdInfrastructure/README.md)
- **Tracking:** flee distances could not be measured, because "MetaHuman Crowd instances live on the GPU only (the CPU instance count is 0)" — [ArtDirection/CrowdInfrastructure/README.md](ArtDirection/CrowdInfrastructure/README.md)
- **Planned fix never landed:** "Crowd-looks is building new Red and White collections in `/Game/Characters/Lanthorne/CrowdMass/`". That folder does **not** exist. `Content/Characters/Lanthorne/` contains only `Clothing`, `Grooms`, `Looks` and `People` — [ArtDirection/CrowdInfrastructure/README.md](ArtDirection/CrowdInfrastructure/README.md); [Content/Characters/Lanthorne/](Content/Characters/Lanthorne/)
- **Cook cost:** `/Game/Crowd/City` is always-cooked and "pulls in `COL_CrowdPrototype_CoinClerk`, a 108.8 MB MetaHuman Collection. Estimated 20–80 MB cooked". Packaging asked crowd to drop the always-cook entry — [ArtDirection/Packaging/README.md](ArtDirection/Packaging/README.md). `Config/DefaultGame.ini` line 35 still has `+DirectoriesToAlwaysCook=(Path="/Game/Crowd/City")` — [Config/DefaultGame.ini](Config/DefaultGame.ini)
- **Prototype assets still on disk:** `/Game/Characters/RedLondon/Crowd/Test/` holds `COL_CrowdPrototype_CoinClerk`, `MI_CrowdPrototype_CoinClerk`, `MEC_CrowdPrototype`, `SKEL_CrowdPrototype_Final` and `DA_CrowdPrototype_Animations` (folder `RedLondon/Crowd` is 112 MB) — [Content/Characters/RedLondon/Crowd/Test/](Content/Characters/RedLondon/Crowd/Test/)

**Measured costs: Mass**
- **40 pedestrians on `Lvl_HeroSampleCrowd`** (PIE, 12:57): 40 entities, 0 actors, 40 ISKMs, 16–18 visible.

  | | Crowd on | Crowd off |
  |---|---|---|
  | Game thread median / p95 | 21.6 / 23.4 ms | 20.59 / 23.13 ms |
  | GPU median / p95 | 4.77 / 5.07 ms | 4.34 / 4.51 ms |

  That is about 1.0 ms game thread and 0.4 ms GPU for all 40 — [Saved/CrowdReactions/mass_spike_result.json](Saved/CrowdReactions/mass_spike_result.json); [ArtDirection/CrowdInfrastructure/README.md](ArtDirection/CrowdInfrastructure/README.md)
- **60 pedestrians** (train #7, 15:37, shared editor at a 37 ms baseline): 60 entities, all ISKM, 19–25 visible.

  | | Crowd on | Crowd off |
  |---|---|---|
  | Game thread median / p95 / p99 | 40.98 / 62.21 / 2299.35 ms | 36.97 / 49.27 / 98.25 ms |
  | GPU median | 8.82 ms | 5.9 ms |

  The README says to "treat that as an upper bound until a quiet-editor rerun". A Fireball promoted 1 pedestrian, to `BP_WhiteLook_02_Cap_C` (35/35 HP, FLEEING, 1787 cm from impact) — [Saved/CrowdReactions/city_train_result.json](Saved/CrowdReactions/city_train_result.json)
- `city60_result.json` contains only `{"status": "waiting", "started": "13:09:52"}`: that run never completed — [Saved/CrowdReactions/city60_result.json](Saved/CrowdReactions/city60_result.json)
- **Streaming test** (13:00): 40 entities, 14 visible. Unload gave 0 and reload gave 40 again — [Saved/CrowdReactions/city_stream_result.json](Saved/CrowdReactions/city_stream_result.json)
- **Isolated flat test scene**, unlit, wall-clock frame intervals, test-only straight-line motion:

  | Entities (ISKM) | Median | p95 |
  |---|---|---|
  | 20 | 8.47 ms | 10.25 ms |
  | 100 | 9.01 ms | 12.46 ms |

  The README says this is "**not a shipping or London-scale capacity estimate**". Raw CSVs are in [ArtDirection/CrowdInfrastructure/Measurements/](ArtDirection/CrowdInfrastructure/Measurements/) — [ArtDirection/CrowdInfrastructure/README.md](ArtDirection/CrowdInfrastructure/README.md)

**Measured costs: actor walkers (for comparison)**
- **6 placed walkers:** "about 7 ms of game-thread time: median 27.5 ms with them active, 20.6 ms with all their ticks frozen", plus about 1 ms GPU. Per walker:
  - about 0.3 ms CharacterMovement and 0.2 ms mesh tick on the game thread;
  - "1–2.5 ms of worker-thread motion matching for the hidden driver";
  - 0.3–0.5 ms for the MetaHuman body and 0.15–0.27 ms for the face.

  The same walkers with the crowd LOD gave these game-thread medians: off 19.9 ms, default 17.7 ms, aggressive 16.3 ms — [ArtDirection/CrowdInfrastructure/README.md](ArtDirection/CrowdInfrastructure/README.md)
- **Ring of 12 on the mock city:**

  | | Ring of 12 | Ring off |
  |---|---|---|
  | Game thread median / p95 / max | 30.26 / 41.44 / 228.62 ms | 24.52 / 27.82 / 30.52 ms |
  | GPU median | 8.21 ms | 7.13 ms |

  The README calls this "about 5.7 ms of game thread for 12 … roughly 0.5 ms each with `Crowd.Lod`, plus 1.1 ms GPU. Keep 12 for the jam." One 228 ms frame was seen during replacements — [Saved/CrowdReactions/ring_result.json](Saved/CrowdReactions/ring_result.json); [ArtDirection/CrowdInfrastructure/README.md](ArtDirection/CrowdInfrastructure/README.md)
- **Driver overheads** (12 drivers, PIE hitch dump):
  - camera rig about 1.1 ms in total (now disabled);
  - "character movement plus moving the attached visible body (about 3 ms for 12 drivers in the worst frame)";
  - foley notifies about 1 ms — [ArtDirection/CrowdInfrastructure/README.md](ArtDirection/CrowdInfrastructure/README.md)
- **Walker count on the mock city:** the LOD dump there showed 34 `NPC_SampleLocomotion` walkers (Full 8, Mid 6, Far 9, Hidden 11), counting placed NPCs as well as the ring — [Saved/CrowdReactions/ring_result.json](Saved/CrowdReactions/ring_result.json)

### Inferences
- Per game-thread millisecond, the measured ratio is roughly 40 Mass pedestrians per ~1 ms against roughly 2 actor walkers per ~1 ms. That is about a 20× density advantage for an instanced or GPU-animated background crowd. The comparison is apples-to-oranges, though: Mass had one look and no grooms, and both sets of numbers come from noisy editors.
- The blockers to reviving Mass are content and pipeline problems:
  - a proper MetaHuman Crowd Collection with grooms and fitted garments;
  - a look-mapping table;
  - a host-map crowd level with ZoneGraph data;
  - the actor-representation errors.
- The code (stimulus-to-disturbance, promotion, `PedestrianInstanceIndex` lookup) is reusable once a crowd level exists for Gray London.
- `/Game/Crowd/City` is still always-cooked and still pulls in the 108.8 MB prototype collection, while Mass ships off. That is dead weight against the 1 GB zip limit unless removed or replaced.

### Gaps
- No quiet-editor or packaged measurement of the 60-pedestrian Mass crowd exists. The Mass crowd was never cooked (packaged perf noted it "isn't cooked").
- No measurement exists of Mass with multiple Collections or Instances, grooms, or actor-ISKM transitions.
- No mid-range hardware numbers exist for either crowd.

## Q3. Which crowd-relevant plugins are enabled in reflections.uproject

### Takeaway
Everything needed for Mass plus ZoneGraph, SmartObjects and StateTree crowds is enabled, as is MetaHumanCrowd and the GASP motion-matching stack. **AnimToTexture and AnimationSharing are not enabled.** No vertex-animation or shared-animation crowd path exists in the project.

### Cited Findings
- **Enabled plugin entries** (62, plus the project module):
  - **Crowd / AI:** SmartObjects, GameplayInteractions, MassGameplay, MassCrowd, MassAI, ZoneGraph, ZoneGraphAnnotations, StateTree, GameplayStateTree, MetaHumanCrowd.
  - **Animation:** IKRig, AnimationWarping, PoseSearch, AnimationLocomotionLibrary, MotionWarping, Chooser, AnimationLayering, CurveExpression, ACLPlugin, ControlRig, FullBodyIK.
  - **Movement:** Mover, NetworkPrediction, ChaosMover.
  - **PCG:** PCGPrimitives, PCGBiomeSample, PCGBiomeCore, PCGPrimitives_MeshPartitionInterop, PCGNaniteAssembliesInterop, PCGWaterInterop.
  - **MetaHuman:** MetaHumanCoreML, MetaHumanCharacter, MetaHumanGenerator, MetaHumanCharacterUAF, MetaHumanCalibrationDiagnostics.
  - **Generated animation:** Kimodo, AnimGenOffline, AnimGen.
  - **Editor-only** (`TargetAllowList: Editor`): the toolsets, including NavMeshToolset and PCGToolset, plus NNEDenoiser.
  - `EngineAssociation` is a GUID (`{C694E49A-…}`), so this is a custom or source engine build — [reflections.uproject](reflections.uproject)
- **Not listed** in `reflections.uproject`: `AnimToTexture`, `AnimationSharing`, a bare `PCG` entry and a `MassEntity` entry (a grep for them returns nothing) — [reflections.uproject](reflections.uproject)
- **Module dependencies in `reflections.Build.cs`:** `MassSpawner`, `MassActors`, `MassEntity`, `MassCore`, `MetaHumanCrowd`, `MassCommon`, `MassMovement`, `MassNavigation`, `MassZoneGraphNavigation`, `MassRepresentation`, `MassLOD`, `MassSignals`, `MassCrowd`, `ZoneGraph`, `ZoneGraphAnnotations`, `MassAIBehavior`, `StateTreeModule`, `GameplayStateTreeModule`, `NavigationSystem`, `AIModule`. `bUseUnity = false` — [Source/reflections/reflections.Build.cs](Source/reflections/reflections.Build.cs)
- **Config:** `Config/DefaultEngine.ini` registers the `CitySidewalk` lane profile under `[/Script/ZoneGraph.ZoneGraphSettings]`. It has **no** navigation or Recast settings (a grep for "nav"/"Recast" finds nothing), and no `Crowd.*` CVar overrides. Its `[ConsoleVariables]` sets only `Npc.ElementReactions=1` and `Npc.Heat=1` — [Config/DefaultEngine.ini](Config/DefaultEngine.ini)

### Inferences
- The PCG sub-plugins depend on the core PCG plugin, so PCG is effectively enabled as a dependency (not verified from the engine's .uplugin files).
- MassEntity is used as a module from Build.cs. Whether it is an engine module or an implicitly enabled plugin in this 5.9 build was not checked.
- Using AnimToTexture (vertex-animation crowds) or AnimationSharing would require enabling a new plugin. Both need checking against the engine install, which was out of scope.

### Gaps
- It was not checked whether `AnimToTexture` and `AnimationSharing` exist in this custom engine build's Plugins folder: the engine path is not in the repo.

## Q4. What NPC looks exist, how heavy they are, and whether lighter character meshes exist for background crowds

### Takeaway
The finished cast is **38 look Blueprints**, all full MetaHumans with card grooms and leader-posed garments:
- 20 `BP_Look_*` (12 Giltside, 8 Frostside);
- 12 Pewterside grey `PewLook_*`;
- 6 armour-free soldier looks.

Measured in the package, each MetaHuman is about 12 skeletal-mesh components and 5 groom components, costing about 0.43 ms game thread, 0.30 ms render thread and 0.14 ms GPU, and about 50–60 MB cooked per extra MetaHuman. The only light meshes in the project are Epic mannequins (UEFN, Manny/Quinn Simple, UE5, UE4). Project rules and the side-identity rules exclude them from NPC pools. The legacy SimpleRed and WhiteLook looks are still MetaHumans, and SimpleRed carries a licence problem.

### Cited Findings
**The cast**
- **Giltside (12):** GiltArchivist, GiltBarnaby, GiltBridgeGuard, GiltRowena, GiltCoinClerk, GiltMaren, GiltFerryman, GiltRamon, GiltDrummer, GiltPriya, GiltGlassman, GiltHaruto.
- **Frostside (8):** FrostIven, FrostSilas, FrostTobias, FrostWen, FrostHyeon, FrostSaran, FrostNia, FrostAmara.
- "20 people, 20 distinct faces … 10 women and 10 men; 5 Young, 10 Adult and 5 Old." The machine-readable cast is `Tools/CrowdLooks/cast.json` — [ArtDirection/CrowdLooks/README.md](ArtDirection/CrowdLooks/README.md)
- **On disk:** `Content/Characters/Lanthorne/Looks/` has the 20 `BP_Look_*`. `Looks/Pewterside/` has 12 `PewLook_*`, which are "material-only" grey palette swaps with the same faces, 10 civilians and 2 guards. `Looks/Soldiers/` has 6: `GiltSoldier_BridgeGuard`, `GiltSoldier_Rowena` and `FrostSoldier_{Iven,Saran,Nia,Amara}` — [Content/Characters/Lanthorne/Looks/](Content/Characters/Lanthorne/Looks/); [ArtDirection/CrowdLooks/README.md](ArtDirection/CrowdLooks/README.md)
- **Tags carry metadata:** `NPC_Voice_F|M`, `Look_Age_*`, `Look_Side_Giltside|Frostside`, `Look_Role_Civilian|Guard|Soldier|Caster`, `Look_Id_<Id>` — [ArtDirection/CrowdLooks/README.md](ArtDirection/CrowdLooks/README.md)

**Build and weight**
- How a person is built: an Epic preset, with a "cloud auto-rig (joints only: no blendshapes, a lighter face)" and an "Optimized/Medium build". Only grooms from a MetaHuman build (card LODs) are used. `perf_pass.py` removes empty groom components and sets garments to `OnlyTickPoseWhenRendered`; `cap_textures.py` caps body maps at 1024 and eyes and teeth at 512 — [ArtDirection/CrowdLooks/README.md](ArtDirection/CrowdLooks/README.md)
- Each person's folder holds a body mesh, a face mesh, DNA, and grooms with `CardsMesh_Group0_LOD0…LOD4` (eyebrows, hair). Example: `People/GiltPriya/Built/MHC_GiltPriya/Grooms/` — [Content/Characters/Lanthorne/People/GiltPriya/](Content/Characters/Lanthorne/People/GiltPriya/)
- **Disk sizes (uncooked):**
  - `Characters/Lanthorne` 3.2 GB, nearly all of it `People`; `People/Common` 435 MB; `People/GiltPriya` 233 MB; `People/FrostSilas` 260 MB.
  - Other bodies: `RedLondon/*` 265–404 MB per body; `WhiteLondon/IvenRook` 471 MB (measured with `du`).
  - The README gives "about 1.4 GB for the 13 new people plus 435 MB of shared Common". Packaging gives "the grooms are 461 MB uncooked, strands included" — [ArtDirection/CrowdLooks/README.md](ArtDirection/CrowdLooks/README.md); [ArtDirection/Packaging/README.md](ArtDirection/Packaging/README.md)
- **Packaged runtime weight:**
  - "each MetaHuman is about 12 skeletal mesh components and 5 groom components"; "about **0.43 ms of game thread, 0.30 ms of render thread and 0.14 ms of GPU** for every MetaHuman on screen".
  - Per extra character: 30 draw calls, 0.11 M triangles, 1.0 ms of worker parallel animation.
  - "MetaHumans render at LOD0 at all distances" (perf fix #1: a LODSync minimum LOD of 1, sent to crowd-looks) — [ArtDirection/Perf/README.md](ArtDirection/Perf/README.md)
- Known gaps in the looks: no lip-sync (joints-only face rigs); the White London rag mantle doesn't render; "Groom strand data may still be cooked" — [ArtDirection/CrowdLooks/README.md](ArtDirection/CrowdLooks/README.md)

**Legacy and alternative bodies**
- **SimpleRed** (4 BPs on disk in `Content/Characters/CrowdMotion/SimpleRed/{CoinClerk,ArchiveApprentice,FestivalDrummer,BridgeGuard}/BP_*_SimpleRed`; folder 24 MB): their garments are Hunyuan3D-2 pieces, and "those garments are not licensed for every market". Every look got "one shared maroon tunic". They are excluded from the finished looks, but remain the built-in fallback in `ReflectionsNpcArchetype.cpp` `MakeBuiltIn` and in `TeamLooks()` if fewer than 2 finished looks exist — [ArtDirection/CrowdLooks/README.md](ArtDirection/CrowdLooks/README.md); [ArtDirection/CrowdInfrastructure/README.md](ArtDirection/CrowdInfrastructure/README.md); [Source/reflections/NPC/ReflectionsNpcArchetype.cpp](Source/reflections/NPC/ReflectionsNpcArchetype.cpp); [Source/reflections/NPC/ReflectionsNpcSubsystem.cpp](Source/reflections/NPC/ReflectionsNpcSubsystem.cpp)
- **WhiteLook_01–06** (`Content/Characters/WhiteLondon/CrowdPreview/`, 20 MB folder): MetaHuman outfits on the IvenRook and BridgeGuard faces. Squads still string-load 03–06, and they are listed in `DefaultEditor.ini` — [ArtDirection/CrowdLooks/README.md](ArtDirection/CrowdLooks/README.md); [Config/DefaultEditor.ini](Config/DefaultEditor.ini)
- **`BP_Crowd_01..36`** (36 BPs in `Content/Characters/RedLondon/Crowd/Variants/`): six faces × six palettes, "Not in any pool". Still MetaHumans — [ArtDirection/CrowdLooks/README.md](ArtDirection/CrowdLooks/README.md)
- **Mannequins on disk:**
  - `UEFN_Mannequin`: `Meshes/` 3.4 MB (`SKM_UEFN_Mannequin`, `SK_UEFN_Mannequin`); `Animations/` 2.0 GB (the GASP motion-matching database: Walk, Run, Idle, MotionMatchingData…).
  - `Mannequins`: `SKM_Manny_Simple`, `SKM_Quinn_Simple`; `Meshes/` 31 MB; folder 126 MB.
  - `UE5_Mannequins` 350 MB; `UE4_Mannequin` 17 MB; `Paragon` 751 MB; `Echo` 1.1 GB — [Content/Characters/](Content/Characters/)
- **Cook status of the mannequins:**
  - `UEFN_Mannequin` "is 48 MB" of the hero budget, because it is the hero's motion matching.
  - The villain string-loads `SKM_Manny_Simple` and `SKM_Quinn_Simple`.
  - Paragon, Echo and UE4_Mannequin are in `DirectoriesToNeverCook` as hard guards ("~1.9 GB") — [ArtDirection/Packaging/README.md](ArtDirection/Packaging/README.md)
- **Project rule:** archetype `Looks` doc comment: "Only actor Blueprints of the crowd MetaHumans belong here, never a mannequin". The `SpawnNpc` doc says it exists "so nobody spawns mannequins" — [Source/reflections/NPC/ReflectionsNpcArchetype.h](Source/reflections/NPC/ReflectionsNpcArchetype.h); [Source/reflections/NPC/ReflectionsNpcSubsystem.h](Source/reflections/NPC/ReflectionsNpcSubsystem.h)
- **No lighter crowd body found:** no impostor, vertex-animation (AnimToTexture) or low-poly crowd character set was found in `Content/`. The only instanced crowd body is the broken Mass prototype collection — [Content/Characters/](Content/Characters/); [reflections.uproject](reflections.uproject)

### Inferences
- A background crowd needs a cheaper body than the current looks. Options: MetaHuman Crowd ISKM collections built from the **existing** finished faces and wardrobes (the population contract in the CrowdInfrastructure README); MetaHuman low LODs with grooms disabled; or new low-poly period bodies from Codex art. Mannequins are ruled out by the project's own rule and by the "fitted clothes only" and side-identity requirements.
- The Pewterside looks are material-only copies, so palette variation is cheap. It adds variety without new MetaHumans: no new face or body cook.

### Gaps
- There is no cooked-size measurement of `/Game/Characters/Lanthorne`. Packaging was asked to report it against the 320 MB budget, and no result was found.
- Per-look component and groom counts after `perf_pass.py` were not measured. The 12-mesh / 5-groom figure predates the new cast.
- It is not known whether a LODSync or minimum LOD was actually applied to the new looks. The CrowdLooks README still lists "perf's LODSync minimum LOD 1" as an open item.

## Q5. How NPCs are spawned (SpawnNpc, archetypes) and the walker + leader-pose setup, and the HideUntilPosed rule

### Takeaway
Every crowd member is a MetaHuman look actor spawned by `SpawnNpc` and enrolled in the unified NPC system. At first tick it gets a **hidden GASP `BP_SampleCMCClean2` pawn** (CharacterMovement plus motion matching). The visible look is attached to that pawn's mesh. The look's `Body` runs an `ABP_Crowd_<Identity>` anim BP, and garments and face are leader-pose followers. A just-spawned NPC is hidden until its pose is valid (`Npc.HideUntilPosed` 1, 1.5 s timeout). Each visible person therefore costs two animated skeletons plus about 10 follower meshes.

### Cited Findings
**Spawning**
- Signature: `AActor* SpawnNpc(FName ArchetypeId, FVector Location, float FacingYaw = 0.0f, TSubclassOf<AActor> Look = nullptr)` — [Source/reflections/NPC/ReflectionsNpcSubsystem.h](Source/reflections/NPC/ReflectionsNpcSubsystem.h)
- Look choice, in order:
  1. `GetLooksAt(ArchetypeId, Location)`, which goes through `GetSideAt` and `GetLooksForSide`. Roles fall back within the same side (for example Guard → AlliedSoldier → Soldier → Enemy → Civilian). Pewterside borrows Giltside's looks if it has none.
  2. The least-worn look first (`GetLookUseCount`), with a rotating start index.
  3. `LoadSynchronous()` on the chosen look.
  4. `SpawnActor` with yaw −90 ("These looks face along their own +Y").
  5. The tags `NPC_HitProxy` and `NPC_SampleLocomotion`, then `EnrollActor(Npc, Archetype)`.

  The side of a look is read from its path (`Look_Gilt`/`SimpleRed`/`RedLondon` → Giltside; `Look_Frost`/`WhiteLook`/`WhiteLondon` → Frostside; `/Pewterside/`/`PewLook_` → Pewterside) — [Source/reflections/NPC/ReflectionsNpcSubsystem.cpp](Source/reflections/NPC/ReflectionsNpcSubsystem.cpp)
- `TeamLooks()` probes 20 `/Game/Characters/Lanthorne/Looks/BP_Look_<Id>` packages and falls back to the SimpleRed/WhiteLook list if fewer than 2 exist — [Source/reflections/NPC/ReflectionsNpcSubsystem.cpp](Source/reflections/NPC/ReflectionsNpcSubsystem.cpp)

**Archetypes**
- 12 data assets in `Content/NPC/Archetypes/`: `DA_Npc_AlliedSoldier`, `AlliedSoldierCaster`, `Brave`, `Civilian`, `Enemy`, `Guard`, `Hostile`, `Infected`, `Soldier`, `SoldierCaster`, `Timid`, `VillainHost`. They hold `Looks` (soft class list), `HiddenLookParts`, `Reaction.bRoamsWhenCalm`, voice and barks.
- Built-in Civilian `MaxHealth` is 20.0. The built-ins are overridden by the finished cast when 2 or more looks exist — [Content/NPC/Archetypes/](Content/NPC/Archetypes/); [Source/reflections/NPC/ReflectionsNpcArchetype.h](Source/reflections/NPC/ReflectionsNpcArchetype.h); [Source/reflections/NPC/ReflectionsNpcArchetype.cpp](Source/reflections/NPC/ReflectionsNpcArchetype.cpp)
- The look lists are written from `cast.json` by `Tools/CrowdLooks/apply_look_list.py`, and `/Game/NPC/Archetypes` is always-cooked — [ArtDirection/CrowdLooks/README.md](ArtDirection/CrowdLooks/README.md); [ArtDirection/Packaging/README.md](ArtDirection/Packaging/README.md)

**Walker setup (`UReflectionsNpcReactionComponent::InitializeLocomotion`)**
- Identity and anim BP: the body mesh name must match `SKM_MHC_<Identity>_BodyMesh`. The anim BP is then `/Game/Characters/CrowdMotion/ABP_Crowd_<Identity>`. Only 7 `ABP_Crowd_*` exist: ArchiveApprentice, BridgeGuard, CoinClerk, FerryPilot, FestivalDrummer, GlassArtisan, IvenRook. `IK_Crowd_*` and `RTG_Crowd_*` retargeters sit beside them.
- The driver is `/Game/Characters/Hero/Sample/BP_SampleCMCClean2`. On it:
  - every Camera and SpringArm component is deactivated (comment: "about 0.4 ms of game thread per NPC");
  - the foley bank is emptied unless `Npc.WalkerFoley` = 1;
  - the capsule is `ECC_Vehicle` and blocks only WorldStatic and Pawn;
  - the driver mesh is hidden, `SetForcedLOD(1)`, `AlwaysTickPoseAndRefreshBones`;
  - `bCanWalkOffLedges = false`.
- The visible actor is `AttachToComponent(Driver->GetMesh())`. `Body` gets a tick prerequisite on the driver mesh, `AlwaysTickPoseAndRefreshBones` and `SetAnimInstanceClass(ABP_Crowd_*)`.
- With `Npc.LeanFollowerParts` 1, leader-pose followers attached directly to their leader get `bUseAttachParentBound` and no overlap events — [Source/reflections/NPC/ReflectionsNpcReactionComponent.cpp](Source/reflections/NPC/ReflectionsNpcReactionComponent.cpp); [Content/Characters/CrowdMotion/](Content/Characters/CrowdMotion/)

**HideUntilPosed**
- `Npc.HideUntilPosed` (default 1): "an NPC that has only just been spawned is not shown until its walker's animation has given it a pose (otherwise it stands with its arms out for a moment)". It applies when `GetGameTimeSinceCreation() < 1.0f` and the actor isn't tagged `Lives_Gone`/`NPC_NoLife`, then sets `SetActorHiddenInGame(true)`, `RevealTimeout = 1.5f`, `RevealGoodFrames = 0` — [Source/reflections/NPC/ReflectionsNpcReactionComponent.cpp](Source/reflections/NPC/ReflectionsNpcReactionComponent.cpp)
- Two causes of the arms-out pose were documented:
  - (1) a shared body skeleton (`metahuman_base_skel` under `RedLondon/BridgeGuard/Assembled/Common`) was saved without its `root` bone, to be restored from e9f3c59;
  - (2) the first frames after spawning, before the walker's animation has run. Train #13 added HideUntilPosed for that — [ArtDirection/NPC_Unified/README.md](ArtDirection/NPC_Unified/README.md)
- Related stability history: T-poses with "GetBoneMatrix: BoneIndex out of range of SpaceBases", and two editor crashes. A per-frame watchdog re-registers bodies with incomplete bone buffers. URO on the walker mesh was "declined before the jam (retarget plus T-pose crash risk)" — [ArtDirection/CrowdInfrastructure/README.md](ArtDirection/CrowdInfrastructure/README.md); [ArtDirection/Perf/README.md](ArtDirection/Perf/README.md)

**Other spawners competing for the same budget**
- Lives spawns named people with `SpawnNpc` within 35 m, "At most 6 at once". 42 named people are in `people.json`. They are full-rate within 60 m — [ArtDirection/Lives/README.md](ArtDirection/Lives/README.md)

### Inferences
- The per-walker cost is dominated by the duplicate skeleton (hidden GASP driver running motion matching, plus the visible MetaHuman body with face and garments). Any cheaper background tier should avoid `NPC_SampleLocomotion` drivers altogether, since URO was declined for stability.
- A promote-on-demand pattern already exists (the Mass promotion code calling `SpawnNpc`). It is the natural bridge from a cheap background crowd to the full reactive NPC near the player or near violence. HideUntilPosed covers the pop during the swap. `SpawnNpc` still loads looks synchronously unless they are preloaded (the ring preloads them).

### Gaps
- What `ABP_Crowd_*` does internally (retarget from the driver versus copy pose) was not inspected: they are binary assets.
- Whether every new `People/*` body name resolves to an existing `ABP_Crowd_<Identity>` was not checked. New faces keep the donor body mesh, per the CrowdLooks README, which suggests yes.

## Q6. What world-jump planned for Gray London crowd lanes and navmesh, the current map state, and packaging constraints

### Takeaway
Gray London has **no ZoneGraph lanes, no ZoneGraphData, no navmesh and no HLOD** today. The plan calls for:
- 40–60 `CitySidewalk` ZoneShapes over the Tower district (about 900 × 820 m), generated from OSM highway ways or from floor traces on Jah's `Sidewalk*` meshes;
- a static navmesh bounded to the district (about 1.2 × 1.0 km, 10–20 MB cooked).

Packaging is already tight. The zip must stay under 1 GB; London alone is estimated at 250–470 MB cooked against a 120 MB budget; NPC MetaHumans have a 320 MB budget, and each extra MetaHuman costs about 50–60 MB.

### Cited Findings
**What is in the map now**
- A grep of all 2,151 external actor packages under `Content/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/` found 0 `ZoneShape`, 0 `ZoneGraphData`, 0 `RecastNavMesh`, 0 `NavMeshBoundsVolume`, 0 `MassSpawner`, 0 `NavigationInvoker`, 0 `CitySidewalk` and 0 `WorldPartitionHLOD`. It found 89 `ReflectionsStoryMarker`, 110 `PCGVolume` and 90 `LT_` packages.
- The 4 untracked packages from 21:49 are CityDetailPilot shopfront meshes, not lanes — [Content/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/](Content/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/); [ArtDirection/CityDetailPilot/README.md](ArtDirection/CityDetailPilot/README.md)
- Packaging agrees: "There's no navmesh: no `NavMeshBoundsVolume` and no `RecastNavMesh`. Without one, NPCs, squads and crowd lanes can't path in London"; "The HLODs aren't built: 0 HLOD actors" — [ArtDirection/Packaging/README.md](ArtDirection/Packaging/README.md)
- The crowd README: the ring "waits for world-jump's CitySidewalk lanes along the Tower district's pavements, and logs `no ZoneGraph lanes` once until they exist" — [ArtDirection/CrowdInfrastructure/README.md](ArtDirection/CrowdInfrastructure/README.md)
- Jah's pavement meshes exist: `/Game/GrayLondon/Geodata/Sidewalk{Continuation,Extension,FullWidth,Next,SupportedBatch,SupportedBatch2}/Strand*`, plus `M_OSM_Pavement` — [Content/GrayLondon/Geodata/](Content/GrayLondon/Geodata/)

**District and our actors**
- The play district is Tower Hill, the Tower, Tower Bridge and Leadenhall Market, "about 900 × 820 m and 3.0–3.9 km east of the map origin". "Walking distances are 300–600 m between beats" — [ArtDirection/WorldJump/GrayLondon_Plan.md](ArtDirection/WorldJump/GrayLondon_Plan.md)
- Our actors: `LT_PlayerStart_Intro` at (3292.9, 310.9, 1.1) m on Great Tower Street, and 89 story markers carrying 164 names, all "not spatially loaded". Axes: X = metres east, Y = metres north of 51.5080 N, 0.1281 W — [ArtDirection/WorldJump/GrayLondon_OurActors.md](ArtDirection/WorldJump/GrayLondon_OurActors.md)
- Marker and place coordinates (east_m / north_m) are in `graylondon_markers.json` and `graylondon_places.json`. Quests read the markers file directly: "Keep that file's name/tags format" — [ArtDirection/WorldJump/graylondon_markers.json](ArtDirection/WorldJump/graylondon_markers.json); [ArtDirection/WorldJump/graylondon_places.json](ArtDirection/WorldJump/graylondon_places.json); [ArtDirection/WorldJump/GrayLondon_Plan.md](ArtDirection/WorldJump/GrayLondon_Plan.md)

**Lane plan**
- "Jah's roads are meshes, so there are no centrelines in the map. Plan: generate about 40–60 ZoneShapes for the district's main pavements from the OSM highway ways … offset to the kerb by road width / 2 + 1.5 m, then snap to the navmesh."
- "The shapes must not be spatially loaded, so the lane graph is complete. One `ZoneGraphData` actor." Owner: crowd-react with world-jump.
- Alternative plan: classify pavement by floor traces on a 2 m grid (hit mesh name `Sidewalk*` or height above the carriageway), thin to centrelines, simplify to points at most 10 m apart with traced Z +3 cm — [ArtDirection/WorldJump/GrayLondon_Plan.md](ArtDirection/WorldJump/GrayLondon_Plan.md)
- Crowd-react's lane requirements:
  - the `CitySidewalk` profile;
  - points at least every 10 m;
  - Z from the pavement +3 cm, ±30 cm at worst;
  - pavement only, never across a carriageway;
  - loops round blocks preferred;
  - validated against the navmesh or a floor trace;
  - run `Crowd.City.SetupZoneGraph`, then save new packages only;
  - pedestrian lanes only, because "the ring and follower take any lane near a walker and don't filter by tag" — [ArtDirection/WorldJump/GrayLondon_Plan.md](ArtDirection/WorldJump/GrayLondon_Plan.md)

**Navmesh plan**
- First plan: "`RecastNavMesh` with runtime generation Dynamic + Generate Only Around Navigation Invokers … radius 60–80 m with tile size 32 m. Ledge Slope Filter Mode = None".
- Later plan: "a **static** navmesh bounded to the Tower district only (about 1.2 × 1.0 km with margin; about 10–20 MB cooked)", with dynamic invokers as the fallback. "Never a city-wide navmesh (12.5 km)." Owner: world-jump — [ArtDirection/WorldJump/GrayLondon_Plan.md](ArtDirection/WorldJump/GrayLondon_Plan.md)

**Side and PCG**
- The single side is Red / Giltside: `DA_WorldJumpConfig` DefaultWorld was set to Red — [ArtDirection/WorldJump/GrayLondon_Plan.md](ArtDirection/WorldJump/GrayLondon_Plan.md)
- PCG is baked: "All 110 PCG volumes … are `GenerateOnDemand` … the packaged game shows the saved instances and runs no PCG. Keep it that way. Don't switch them to `GenerateAtRuntime`" — [ArtDirection/Packaging/README.md](ArtDirection/Packaging/README.md)

**Package-size constraints**
- itch.io needs a zip under 1 GB. The train #5 zip was 734 MB.
- "Gray London (landed Sat 21:00) is estimated at 250–470 MB cooked, about 350 MB likely": "well over" its 120 MB budget. The package total is "about **1.0–1.3 GB**. It's likely over 1 GB unless something is cut."
- Crowd/NPC MetaHumans: 301 MB now against a **320 MB** budget, and "Each extra MetaHuman costs ~50–60 MB even with the 2K texture cap".
- Shader code: 134 MB against a 160 MB budget.
- Levers applied or offered: the World texture cap at 1024 (done); dropping SM5 (−65 MB, plus −80 to −110 MB with London); cutting the shipped area — [ArtDirection/Packaging/README.md](ArtDirection/Packaging/README.md)
- Memory: "Expect +1–3 GB for the editor and +1–2 GB for PIE … **not** while crowd-looks builds MetaHumans". The orchestrator at 21:15: "keep memory low. 2.7 GB of virtual memory was free" — [ArtDirection/WorldJump/GrayLondon_Plan.md](ArtDirection/WorldJump/GrayLondon_Plan.md)
- Schedule: "Sunday ~12:00, go/no-go"; the deadline in the plan is Sun 18:00. Packaging names a 4 PM local team target (6 PM ET) — [ArtDirection/WorldJump/GrayLondon_Plan.md](ArtDirection/WorldJump/GrayLondon_Plan.md); [ArtDirection/Packaging/README.md](ArtDirection/Packaging/README.md)

### Inferences
- Lane generation is the critical-path prerequisite for **any** street crowd on Gray London: the ring, a revived Mass crowd, and the Mass StateTree all need ZoneGraph. Navmesh is needed for lives and squads pathing, and for snapping lanes.
- ZoneGraph data (one always-loaded `ZoneGraphData` actor plus non-spatially-loaded shapes) costs little cook size. New MetaHuman faces cost about 50–60 MB each, so bustle should come from more instances of existing people and palettes, not new faces.

### Gaps
- No lane generator script for Gray London was found. `graylondon_places.py`, `london_row_b.py` and `measure_graylondon.py` exist, but none is described as producing ZoneShapes. "Step 0" measurements (frame stats at Tower Hill, editor memory, WP cell size) were not found in a results file.
- The packaged frame rate on Gray London is unmeasured (the plan's estimate: "40–70 fps at 1080p … without the crowd", flagged unmeasured).

## Q7. Performance budgets and perf reports

### Takeaway
The game is **CPU-bound per character**. The only perf report is from the train #5 package on the deleted sandbox map: 132 fps idle and 75 fps in heavy combat with 23 characters. The estimated mid-range CPU result is 50–58 fps in combat, and the report suggests about 14 active NPCs as a cap. There is no explicit "crowd budget" in ms, beyond the crowd README's "Keep 12 for the jam" and perf's per-character slope.

### Cited Findings
**Headline numbers (train #5, 1080p Epic, RTX 5080)**

| Run | FPS | Game thread median | Render thread median | GPU median | Characters |
|---|---|---|---|---|---|
| idle | 132 | 5.5 ms | 7.5 ms | 3.5 ms | 7 |
| combat | 75 | 12.4 ms | 12.3 ms | 5.8 ms | 23 |
| finale | 85 | 10.2 ms | 11.5 ms | 5.3 ms | 17 |

  — [ArtDirection/Perf/README.md](ArtDirection/Perf/README.md)

**Per extra character**
- Game-thread animation 0.17 ms; TickActors 0.10 ms; CharacterMovement 0.04 ms; worker parallel animation 1.0 ms.
- GPU HairCardsInterpolation 0.05 ms.
- About 12 ticking skeletal meshes, about 5 grooms, 30 draws and 0.11 M triangles.
- In combat: 272 ticking skeletal meshes and 118 groom components — [ArtDirection/Perf/README.md](ArtDirection/Perf/README.md)

**Hitch**
- "In the calm start area (strolling walkers only), the game thread stalls 40–75 ms waiting on a PrePhysics task, in bursts: 32 frames over 20 ms in 50 s."
- Prime suspect: the hidden motion-matching drivers. Not reproduced in a 23 s PIE trace (TG_PrePhysics peaked at 3.7 ms). Sync loads are ruled out — [ArtDirection/Perf/README.md](ArtDirection/Perf/README.md)

**Mid-range estimate**
- "about **50–58 fps in heavy combat at any preset**". Getting combat above 60 "needs fixes 1–3 (about 4–6 ms off each CPU thread), or a cap of about 14 active NPCs in a fight" — [ArtDirection/Perf/README.md](ArtDirection/Perf/README.md)

**Proposed fixes**

| # | Fix | Estimated gain |
|---|---|---|
| 1 | LODSync minimum LOD 1, plus `OnlyTickPoseWhenRendered` on leader-posed parts | est. 3–4 ms game thread |
| 2 | Destroy empty grooms | est. 0.5 ms game thread, 0.6 ms GPU |
| 3 | Make the driver cheaper (URO / Crowd.Lod rates) | est. 0.5–1 ms game thread |

  Also proposed: a `proposed/DefaultScalability.ini` with skeletal LOD bias per view distance, not applied — [ArtDirection/Perf/README.md](ArtDirection/Perf/README.md); [ArtDirection/Perf/proposed/DefaultScalability.ini](ArtDirection/Perf/proposed/DefaultScalability.ini)

**Memory**
- "about 2.0–2.4 GB RAM and 2.3–2.9 GB VRAM. Combat grows 190 MB over 90 s while spawning and is flat after that." — [ArtDirection/Perf/README.md](ArtDirection/Perf/README.md)

**Editor PIE crowd costs** (see Q2): ring 12 ≈ 5.7 ms game thread and 1.1 ms GPU; 6 walkers ≈ 7 ms game thread without LOD; Mass 40 ≈ 1.0 ms game thread and 0.4 ms GPU — [ArtDirection/CrowdInfrastructure/README.md](ArtDirection/CrowdInfrastructure/README.md)

**Pending**
- Perf is paused until Sunday's re-run on the final package. `batch2.ps1` includes A/Bs for `Npc.WalkerFoley`, `Npc.LeanFollowerParts` and `Crowd.Lod.QuietDriverCameras 0`. It also needs an Insights trace of the idle stall — [ArtDirection/Perf/README.md](ArtDirection/Perf/README.md); [ArtDirection/Perf/tools/](ArtDirection/Perf/tools/)

### Inferences
- On the measured per-character slope, 12 ring walkers plus up to 6 lives people plus squads already approach the "about 14 active NPCs" guidance for mid-range CPUs in a fight. Adding more *actor* walkers for bustle would push CPU time past 60 fps on mid-range PCs, before Gray London's own geometry cost (unmeasured) is counted.
- More density needs an instanced or cheaper representation for distant pedestrians, with the full actor reserved for those near the player. Simply raising `Crowd.Ring.Count` won't get there.

### Gaps
- No perf data exists for Gray London: no packaged run, and no PIE frame stats at Tower Hill were found.
- Fixes #1–#3 have no post-change measurement.
- There is no documented frame-time budget allocation per system (for example "crowd = X ms").

## Synthesis for the plan: reuse X, finish Y, avoid Z

### Takeaway
Reuse the ring, stroll, LOD, yield and chat stack and the side-aware `SpawnNpc` as the near-player "hero crowd". Finish the Gray London `CitySidewalk` lanes and the bounded navmesh first. Decide on a cheap background representation, either a properly built MetaHuman Crowd ISKM collection from the existing faces and wardrobe, or another instanced approach. Avoid raising actor-walker counts, new MetaHuman faces (cook budget), runtime PCG, city-wide navmesh, and shipping the dead Mass prototype in the cook.

### Cited Findings
- **Reuse:**
  - the ring crowd (lane spawn, out-of-sight recycle, async look preload, villain release);
  - stroll lane-following;
  - the LOD tiers;
  - yield;
  - the chat director;
  - `SpawnNpc` least-worn, side-aware looks;
  - the Mass promotion code path (`PromoteEntityAt` → `SpawnNpc`);
  - ZoneGraph disturbance flee;
  - `CitySidewalk` profile config.

  Sources: [Source/reflections/Crowd/](Source/reflections/Crowd/); [Source/reflections/NPC/ReflectionsNpcSubsystem.cpp](Source/reflections/NPC/ReflectionsNpcSubsystem.cpp); [Config/DefaultEngine.ini](Config/DefaultEngine.ini)
- **Finish:**
  - Gray London lanes (none exist) and a bounded navmesh (none exists) — [ArtDirection/WorldJump/GrayLondon_Plan.md](ArtDirection/WorldJump/GrayLondon_Plan.md); [ArtDirection/Packaging/README.md](ArtDirection/Packaging/README.md)
  - The ring verification on Gray London (script ready, never run) — [Saved/CrowdReactions/verify_ring.py](Saved/CrowdReactions/verify_ring.py)
  - The chat spots (proposal only) — [ArtDirection/CrowdInfrastructure/README.md](ArtDirection/CrowdInfrastructure/README.md)
  - The Mass crowd's missing pieces if it is revived: a Gray London crowd level or in-map spawner; real Collections; `DT_CrowdLookMap` (missing); `Crowd.Mass.HostMap` and `Level` set — [Source/reflections/Crowd/ReflectionsCrowdCitySubsystem.cpp](Source/reflections/Crowd/ReflectionsCrowdCitySubsystem.cpp); [Content/Crowd/City/](Content/Crowd/City/)
  - Perf fixes #1–#3 (LODSync, empty grooms, driver cost) — [ArtDirection/Perf/README.md](ArtDirection/Perf/README.md)
- **Avoid:**
  - Mannequins in NPC pools (project rule) — [Source/reflections/NPC/ReflectionsNpcArchetype.h](Source/reflections/NPC/ReflectionsNpcArchetype.h)
  - SimpleRed garments (licence) — [ArtDirection/CrowdLooks/README.md](ArtDirection/CrowdLooks/README.md)
  - Runtime PCG — [ArtDirection/Packaging/README.md](ArtDirection/Packaging/README.md)
  - A city-wide navmesh — [ArtDirection/WorldJump/GrayLondon_Plan.md](ArtDirection/WorldJump/GrayLondon_Plan.md)
  - URO on walker meshes pre-jam (T-pose risk) — [ArtDirection/Perf/README.md](ArtDirection/Perf/README.md)
  - Non-pedestrian lanes with the `CitySidewalk` profile, because there is no tag filtering — [ArtDirection/WorldJump/GrayLondon_Plan.md](ArtDirection/WorldJump/GrayLondon_Plan.md)
  - Keeping `/Game/Crowd/City` always-cooked while it only drags in the 108.8 MB prototype — [ArtDirection/Packaging/README.md](ArtDirection/Packaging/README.md)

### Inferences
- The cheapest path to "bustling" within the jam window:
  1. lanes;
  2. the ring at 12, verified on Gray London;
  3. then a background tier that costs about 1 ms per several dozen pedestrians (Mass ISKM was measured at about 1.0 ms game thread for 40), promoting to full actors near the player or violence through the existing code.
- The look-quality blocker on Mass (white heads, null groom cards) is the open risk. The plan should budget a look-validation pass, or pick an alternative background representation.
- Every person on Gray London currently wears Giltside (red) looks, because the map is one side (Red). Variety comes from the 12 Giltside faces, plus palette variants such as Pewterside-style material swaps if the user allows grey in Giltside; the side rule says no.

### Gaps
- No feasibility check was made of MetaHuman Crowd in this UE 5.9 build with grooms that work. The prototype's groom cards were null and the actor representation errored. Whether those are engine-version issues or setup issues is unresolved in the notes.
- There is no data on how many pedestrians the stroll/lane logic, or Mass ZoneGraph navigation, can sustain on a 40–60-shape lane graph.
