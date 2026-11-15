# Mass Entity / MassCrowd / ZoneGraph pedestrian crowds for a large World Partition city (City Sample approach)

Scope note for the report writer: web documentation on this topic is thin and much of Epic's tutorial content is JS-rendered (unfetchable). To compensate, several of the most load-bearing facts below were read directly from the **UE 5.9 engine plugin source installed on this machine** (`C:\Program Files\Epic Games\UE_5.9\Engine\Plugins\...`). These are authoritative for 5.9 and are cited as `file:///` links. Web-sourced numbers are marked by confidence. Unreal distances are in centimetres (cm) unless stated.

## 1. How City Sample's crowd pipeline works end to end

### Takeaway
City Sample spawns pedestrians with **Mass Spawner** actors whose **Spawn Data Generators** scatter points along **ZoneGraph** lanes (lane data generated procedurally from Houdini). Each agent is defined by a **Mass Entity Config** (a stack of Traits: movement, steering, avoidance, ZoneGraph navigation, LOD, visualization, StateTree). Behavior is a **StateTree** (`CrowdStateTree`), and rendering switches between full MetaHuman actors near the camera and vertex-animated static meshes farther away. The same building blocks are available in the stock engine plugins (MassGameplay, MassAI, MassCrowd, ZoneGraph, StateTree, SmartObjects).

### Cited Findings
**City Sample architecture (Epic docs)**
- City Sample uses several Mass Spawners, one each for crowds, intersections, traffic and parked vehicles. Each spawner specifies an **Entity Type** (what to spawn) and **Spawn Data Generators** (where to spawn it). — [Epic: City Sample Project](https://dev.epicgames.com/documentation/unreal-engine/city-sample-project-unreal-engine-demonstration)
- A **Mass Entity Definition/Config** data asset sets the Traits of spawned entities (visuals, LOD, behaviors). — [Epic: City Sample Project](https://dev.epicgames.com/documentation/unreal-engine/city-sample-project-unreal-engine-demonstration)
- Crowd and traffic spawn points are distributed along a ZoneGraph built from procedural Houdini data. Parked cars spawn from a point cloud generated along the streets. — [Epic: City Sample Project](https://dev.epicgames.com/documentation/unreal-engine/city-sample-project-unreal-engine-demonstration)
- Crowd behavior is driven by StateTree. The `CrowdStateTree` asset lives in `Content/AI` and is linked from the crowd's Mass Entity Definition. Traffic does **not** use StateTree. — [Epic: City Sample Project](https://dev.epicgames.com/documentation/unreal-engine/city-sample-project-unreal-engine-demonstration)
- Epic describes ZoneGraph as a "lightweight design-driven flow for AI": a point-by-point corridor structure that can store static and dynamic tags. Zone Shape components come from the Place Actors panel, and the Big City outliner has a "Zone Shapes" folder. — [Epic: City Sample Project](https://dev.epicgames.com/documentation/unreal-engine/city-sample-project-unreal-engine-demonstration)
- Mass also feeds idling MetaHuman and vehicle locations to Soundscape for ambient shouts and honks. — [Epic: City Sample Project](https://dev.epicgames.com/documentation/unreal-engine/city-sample-project-unreal-engine-demonstration)
- City Sample ships a standalone `MassCrowd` test map under the AI folder. Forum users report that this map keeps working even when the Big City crowd breaks. — [Forum: UE 5.7 City Sample broken](https://forums.unrealengine.com/t/ue-5-7-city-sample-broken/2701997)
- The smaller City Sample PCG map variant does **not** include the Mass AI setup for traffic and pedestrians. — [Epic: City Sample PCG](https://dev.epicgames.com/documentation/unreal-engine/city-sample-pcg-for-unreal-engine) (via search snippet)

**Generic trait stack (Epic "Your First 60 Minutes with Mass", UE 5.2, via mirror)**
- **Plugins:** MassEntity, MassGameplay, MassAI, MassCrowd, ZoneGraph, StateTree. A forum commenter notes MassCrowd was missing from the tutorial's plugin list. — [Mirror of Epic tutorial](https://teletype.in/@hardway/60minwithmass); [Forum thread](https://forums.unrealengine.com/t/tutorial-your-first-60-minutes-with-mass/794314/38)
- **Movement and navigation traits:**
  - Movement, with a "Default" movement style.
  - Steering.
  - Smooth Orientation.
  - Avoidance, which needs an Agent Radius fragment.
  - ZoneGraph Navigation, with Any Tags = Default and **Query Radius 5000 cm**.
  - Navigation Obstacle.
  — [Mirror of Epic tutorial](https://teletype.in/@hardway/60minwithmass)
- **StateTree (Mass Behavior schema):**
  - Wander state: `ZG Find Wander Target`, then `ZG Path Follow`, with the target bound to the wander target. On completion it transitions to Idle.
  - Idle state: `ZG Stand` with Duration 1.5 s, then back to root.
  — [Mirror of Epic tutorial](https://teletype.in/@hardway/60minwithmass)
- **Player awareness:** give the player character a **MassAgent component** with a config containing Navigation Obstacle and Agent Capsule Collision Sync (Actor→Mass). NPCs then avoid the player. — [Mirror of Epic tutorial](https://teletype.in/@hardway/60minwithmass)
- **High-res actor sync:** the high-res actor gets a MassAgent component (MassPuppetEntityConfig) with Agent Movement Sync = Mass→Actor and Agent Feet Location Sync = Actor→Mass. — [Mirror of Epic tutorial](https://teletype.in/@hardway/60minwithmass)

**UE 5.9 MassCrowd plugin contents (local source)**
- MassCrowd ships crowd-specific classes:
  - Representation: `MassCrowdVisualizationTrait`, `MassCrowdVisualizationLODProcessor`, `MassCrowdRepresentationSubsystem`.
  - Spawning, navigation and members: `MassCrowdSpawnerSubsystem`, `MassCrowdNavigationProcessor`, `MassCrowdMemberTrait`.
  - Lanes and networking: `ZoneGraphCrowdLaneAnnotations` (lane open/close, crossings, wait areas), `MassCrowdLaneClosingTest`, plus replication classes.
  — [UE 5.9 MassCrowd Public headers](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/AI/MassCrowd/Source/MassCrowd/Public/)
- **Project Settings > Mass Crowd** (`UMassCrowdSettings`) exposes:
  - Lane tags: `CrowdTag` and `CrossingTag` (FZoneGraphTag).
  - Lane densities: `LaneDensities` (Tag + Weight).
  - Wait areas: `SlotSize` = 50, `SlotOffset` = 75.
  - Obstacles: `ObstacleEffectRadius` = 1000 cm, `ObstacleTimeToStop` = 0.3 s.
  - Movement: `MoveDistance` = 500 cm ± 100.
  - Lane debug-render colours.
  No engine `.ini` sets a default CrowdTag, so the project must define it. — [UE 5.9 MassCrowdSettings.h](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/AI/MassCrowd/Source/MassCrowd/Public/MassCrowdSettings.h); grep of all UE 5.9 plugin `.ini` files found no CrowdTag default.
- In 5.9 the MassAI plugin includes **MassZoneGraphNavigation**, **MassNavMeshNavigation** and **NavCorridor** modules. Mass agents are therefore no longer ZoneGraph-only: they can also navigate on a NavMesh. — [UE 5.9 MassAI.uplugin](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/AI/MassAI/MassAI.uplugin)
- Smart Objects: MassGameplay depends on SmartObjects and contains a `MassSmartObjects` module. A forum thread on `FindSmartObjectTask` failing points to missing **SmartObject ZoneGraph annotations** in the level as a common cause. — [UE 5.9 MassGameplay.uplugin](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/Runtime/MassGameplay/MassGameplay.uplugin); [Forum: FindSmartObjectTask](https://forums.unrealengine.com/t/findsmartobjecttask-on-a-state-tree-does-not-find-smartobject/2667828)

**Plugin maturity in UE 5.9 (local source)**
- Still **experimental**: MassGameplay 0.4, MassAI 0.4, MassCrowd 0.4 ("Spline based AI crowd system"), ZoneGraph 0.5, ZoneGraphAnnotations 0.5, AnimToTexture, MassCharacters, MetaHumanCrowd 1.0.0, UAFMass.
- Not flagged experimental: StateTree and SmartObjects.
- MassInsights is beta.
— [UE 5.9 plugin descriptors](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/)

### Inferences
- City Sample's crowd is not a single "crowd system" asset. It is a configuration of stock Mass plugins plus City-Sample-specific content (entity configs, StateTree, MetaHuman crowd characters, Houdini-generated ZoneShapes). A small team can rebuild it from stock plugins without migrating City Sample, using City Sample only as a reference.
- Because 5.9 has `MassNavMeshNavigation`, a navmesh is an option later. ZoneGraph remains the cheapest path for sidewalk-following pedestrians and needs no navmesh, which suits this project (none exists yet).

### Gaps
- Exact City Sample crowd asset names, trait values and ZoneGraph tag names could not be verified. Epic's tutorial pages are JS-rendered, and the City Sample docs don't list them. From memory (unverified), City Sample also ships project plugins such as CitySampleCrowd and MassTraffic. Check by opening City Sample locally.
- No fetchable recording or transcript of the Unreal Fest / State of Unreal Mass talks with pipeline details. "Large Numbers of Entities with Mass in UE5" (Mario Palmero, State of Unreal 2022, about 29 minutes) covers fragments, processors and entities from scratch, not City Sample crowds. — [Forum listing](https://forums.unrealengine.com/t/610520)

## 2. Mass representation LOD: actor / low-res actor / ISM (vertex animation) / off — thresholds and counts

### Takeaway
The stock `MassCrowdVisualizationTrait` (UE 5.9) hard-codes four tiers:

| LOD | Representation | Starts at (in frustum) | Max entities |
|---|---|---|---|
| High | High-res spawned actor | 0 cm | 10 |
| Medium | Low-res spawned actor | 1,000 cm (10 m) | 20 |
| Low | Static mesh instance (ISM) | 5,000 cm (50 m) | 500 |
| Off | Nothing rendered | 10,000 cm (100 m) | unlimited |

Out-of-view distances are 0, 5, 10 and 50 m, with 20% hysteresis. In City Sample, near characters are fully rigged MetaHumans and distant ones are vertex-animated static meshes baked from MetaHumans. **UE 5.8+ adds an Epic-recommended alternative: Instanced Skinned Mesh (ISKM) with AnimSequenceTransformProvider and the MetaHumanCrowd plugin.**

### Cited Findings
**Defaults in `UMassCrowdVisualizationTrait` (UE 5.9 source)**
- Representation per tier: High = `HighResSpawnedActor`, Medium = `LowResSpawnedActor`, Low = `StaticMeshInstance`, Off = `None`. — [UE 5.9 MassCrowdVisualizationTrait.cpp](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/AI/MassCrowd/Source/MassCrowd/Private/MassCrowdVisualizationTrait.cpp)
- `BaseLODDistance`: High 0, Medium 500, Low 1000, Off 5000 (cm). — same file
- `VisibleLODDistance`: High 0, Medium 1000, Low 5000, Off 10000 (cm). — same file
- `LODMaxCount`: High 10, Medium 20, Low 500, Off = INT_MAX. — same file
- Hysteresis and frustum: `BufferHysteresisOnDistancePercentage` = 20, `DistanceToFrustum` = 0, `DistanceToFrustumHysteresis` = 0. — same file
- Other flags:
  - `bKeepLowResActors` = true, commented as "a spawning optimization, this will keep the low-res actor if available while showing the static mesh instance".
  - `bKeepActorExtraFrame` = true.
  - `NotVisibleUpdateRate` = 0.5.
  - `LODParams.FilterTag` = `FMassCrowdTag`.
  — same file
- The UE 5.9 **MetaHumanCrowd** plugin's `MetaHumanMassCrowdVisualizationTrait` uses the same distances, max counts and hysteresis. — [UE 5.9 MetaHumanMassCrowdVisualizationTrait.cpp](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/MetaHuman/MetaHumanCrowd/Source/MetaHumanCrowd/Private/Mass/MetaHumanMassCrowdVisualizationTrait.cpp)
- The crowd's server-side representation LOD (for dedicated servers) uses High 0, Medium/Low/Off 5000 cm, with max counts High 50, Medium/Low 0. — [UE 5.9 MassCrowdServerRepresentationLODProcessor.cpp](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/AI/MassCrowd/Source/MassCrowd/Private/MassCrowdServerRepresentationLODProcessor.cpp)

**What the LOD parameters mean**
- `FMassVisualizationLODParameters` has:
  - `BaseLODDistance` ("Distances where each LOD becomes relevant").
  - `VisibleLODDistance`.
  - `DistanceToFrustum` (entities within that distance of the frustum count as visible).
  - Per-LOD `LODMaxCount`.
  - A hysteresis buffer.
  The API docs list no defaults. — [Epic API: FMassVisualizationLODParameters](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/MassRepresentation/FMassVisualizationLODParameters)
- **Simulation LOD is separate from representation LOD.**
  - `UMassSimulationLODTrait` and `UMassSimulationLODProcessor` add `FMassOffLODTag` and similar tags, with optional variable ticking per LOD (`TickRates`, in seconds per LOD).
  - Count-based LOD reduction is on by default.
  - Use either the distance collector trait or the visibility (frustum) collector trait, "DO NOT add both traits to a single Entity".
  - World Partition streaming sources can act as LOD viewers.
  — [x157 Dev Notes: Mass LOD](https://x157.github.io/UE5/Mass/LOD)

**Tutorial settings (UE 5.2)**
- High LOD Max Count set to 10.
- Medium LOD uses a low-res BP actor.
- ISM description uses `Shape_NarrowCapsule` with Min LODSignificance 3.0.
- A LOD Collector trait is required.
- Crowd entities need `MassCrowdLODCollectorProcessor`, `MassCrowdVisualizationProcessor` and `MassCrowdVisualizationLODProcessor`. In 5.2 these had to be auto-registered with processing phases (DefaultMass.ini `bAutoRegisterWithProcessingPhases=True`).
— [Mirror of Epic tutorial](https://teletype.in/@hardway/60minwithmass)

**City Sample visuals**
- City Sample: "thousands of unique digital human characters" from a subset of MetaHumans. Nearby characters are fully rigged and animated MetaHumans. Distant ones are "custom generated, vertex-animated Static Meshes" made from MetaHumans. Drone mode shows "hundreds" of crowd characters at once. — [Epic: City Sample Project](https://dev.epicgames.com/documentation/unreal-engine/city-sample-project-unreal-engine-demonstration)
- **AnimToTexture** (bakes skeletal animation into textures for vertex-animated static meshes) ships in UE 5.9 as an experimental plugin at `Engine/Plugins/Experimental/AnimToTexture`. — [UE 5.9 plugin folder](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/Experimental/AnimToTexture/)

**5.8+ alternative: ISKM**
- Epic staff (June 2026 thread) recommend **Mass + Instanced Skinned Mesh Component (ISKM) + AnimSequenceTransformProvider** for crowds from 5.8. They say it "provides greater flexibility for handling variation within instances and for simple retargeting".
- ISKM inherits from Skinned Mesh Component, not Skeletal Mesh Component, so it **does not support anim blueprints**.
- Epic acknowledges "there's always a possibility for bugs/issues compared to the VAT + Mass pipeline".
- A MetaHuman crowd demo on Fab was planned around 5.8, moving from dehydrated ISKM entities to hydrated skeletal actors with anim blueprints.
- A linked thread reports "Mass crowds using SkinnedMeshInstance leak GPU memory (5.8)" (unverified).
— [Forum: AnimBank and Instanced Skinned Mesh Component](https://forums.unrealengine.com/t/animbank-and-instanced-skinned-mesh-component/2734825)
- UE 5.9 includes `MetaHuman/MetaHumanCrowd`: experimental, "Support for crowds of MetaHumans". It depends on MassAI, MassCrowd, MassGameplay, SmartObjects, Mover, MetaHumanCharacter, HairStrands, ChaosClothAsset and ChaosOutfitAsset. Its content includes `BP_CrowdActor`, `BP_CrowdPipeline`, baked-groom crowd materials and `_Instanced` material variants. — [UE 5.9 MetaHumanCrowd.uplugin](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/MetaHuman/MetaHumanCrowd/MetaHumanCrowd.uplugin)

**Third-party LOD guidance (low confidence)**
- StraySpark (Mar 2026, not benchmarked) recommends roughly skeletal 0–25/30 m, mid-tier to about 75–80 m, ISM to about 190–200 m, then cull. It also suggests 10–30 simultaneously visible skeletal agents and staggering each agent's switch distance by ±2 m to hide pops. The article gives three mutually inconsistent distance schemes. — [StraySpark blog](https://www.strayspark.studio/blog/crowd-traffic-simulation-ue5-mass-ai)

### Inferences
- With stock crowd defaults, at most about **530 agents render at any moment**: 10 full actors, 20 low-res actors and 500 ISM. Nothing renders beyond 100 m in view. Sim-only agents further out still exist and walk. For a "bustling" look on a dense London street, raise `LODMaxCount[Low]` and `VisibleLODDistance[Off]` first; that's the cheap ISM tier. Keep High/Medium caps low because each one is a spawned actor.
- Inference from the parameter names and the `DistanceToFrustum` doc: `VisibleLODDistance` applies to entities in or near the view frustum, while `BaseLODDistance` applies to those outside it, which is why its values are tighter.
- **Jam shortcut:** the ISM tier can use a non-animated or crudely animated static mesh at 50–100 m, where motion along the lane sells the effect. AnimToTexture baking is a good post-jam upgrade. For commercial, evaluate the 5.8+ ISKM / MetaHumanCrowd path against AnimToTexture, given Epic's "possibility for bugs" caveat and the reported GPU memory leak.
- This project uses non-MetaHuman characters (medieval soldiers, rags), so MetaHumanCrowd's MetaHuman-specific pipeline (grooms, outfits) may not apply directly. Its trait defaults and the ISKM approach still do.

### Gaps
- City Sample's actual per-tier distances and counts (its entity config overrides) were not verifiable online.
- No authoritative AnimToTexture settings (texture size, frame rate, bone vs vertex mode) were found in this pass.

## 3. Authoring and generating ZoneGraph lanes for a city, and World Partition behaviour

### Takeaway
ZoneGraph lanes come from **ZoneShape components** (spline or polygon/intersection shapes), each with a **Lane Profile** (lane count, widths, directions) and **Tags**, defined in Project Settings > ZoneGraph. **Build ZoneGraph** bakes them into a **ZoneGraphData** actor per level. In UE 5.9 both `AZoneShape` actors and `AZoneGraphData` default to **not spatially loaded**, so under World Partition they are always loaded and the whole lane network is resident. City Sample generated its shapes procedurally (Houdini). Practical procedural routes for an OSM/PCG city are a Python/C++ editor script that writes ZoneShape points, the third-party PCGEx "Cluster to Zone Graph" node, or a road plugin such as UnrealDrive.

### Cited Findings
**Authoring and building**
- Project Settings > ZoneGraph (`UZoneGraphSettings`) has:
  - `LaneProfiles` (array).
  - `Tags` (fixed array of up to `EZoneGraphTags::MaxTags`).
  - `VisualizedTags`.
  - `ShapeMaxDrawDistance` = 20000.
  - `BuildSettings`.
  - `bBuildZoneGraphWhileEditing` = **false** by default, so you must build manually.
  — [UE 5.9 ZoneGraphSettings.h](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/Runtime/ZoneGraph/Source/ZoneGraph/Public/ZoneGraphSettings.h)
- **Scriptable ZoneShape properties:** `UZoneShapeComponent` exposes `Points` (`TArray<FZoneShapePoint>`), `LaneProfile`, `Tags`, `ShapeType` (Spline/Polygon), `bReverseLaneProfile` and `PolygonRoutingType` as **BlueprintReadWrite**. Setters include `SetShapeType`, `SetTags` and `SetReverseLaneProfile`. ZoneShapes can therefore be created and filled from editor scripting. — [UE 5.9 ZoneShapeComponent.h](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/Runtime/ZoneGraph/Source/ZoneGraph/Public/ZoneShapeComponent.h)
- **Minimal tutorial setup:** add a lane profile with 2 lanes (one forward, one backward) using the Default tag. Place ZoneShapes in a closed loop, **Build ZoneGraph**, and save. — [Mirror of Epic tutorial](https://teletype.in/@hardway/60minwithmass)
- ZoneGraphData is built via Build > Build ZoneGraph, which generates **one ZoneGraphData actor per level**. — [UnrealDrive docs: Zone Graph](https://unrealdrive.readthedocs.io/en/stable/ZoneGraph.html)
- **Spawn generator lane filtering:** `UMassEntityZoneGraphSpawnPointsGenerator` walks every lane of every registered ZoneGraphData that matches its `TagFilter`, places candidate points every `MinGap` = 100 to `MaxGap` = 300 cm, shuffles them, and keeps `Count`. It logs "No locations found on zone graphs" if none match. — [UE 5.9 MassEntityZoneGraphSpawnPointsGenerator.cpp](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/Runtime/MassGameplay/Source/MassSpawner/Private/MassEntityZoneGraphSpawnPointsGenerator.cpp)
- **Crowd lane data:** MassCrowd builds its lane data for all existing lanes in the zone graph, with a per-lane array sized to the ZoneGraph storage. — [Epic API: UMassCrowdSubsystem::BuildLaneData](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/MassCrowd/UMassCrowdSubsystem/BuildLaneData)

**World Partition behaviour**
- In UE 5.9 the constructors of both `AZoneShape` (`ZoneShapeActor.cpp`) and `AZoneGraphData` (`ZoneGraphData.cpp`) set `bIsSpatiallyLoaded = false`, so both are always loaded under World Partition. — [UE 5.9 ZoneShapeActor.cpp](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/Runtime/ZoneGraph/Source/ZoneGraph/Private/ZoneShapeActor.cpp); [UE 5.9 ZoneGraphData.cpp](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/Runtime/ZoneGraph/Source/ZoneGraph/Private/ZoneGraphData.cpp)
- ZoneGraphData also exposes an "Is Main World Only" option: it loads only in the persistent level, not through Level Instances. — [Epic Python API: ZoneGraphData](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/ZoneGraphData)
- `AMassSpawner` does **not** override `bIsSpatiallyLoaded`, so it keeps the AActor default (spatially loaded). Its `EndPlay` calls `DoDespawning()`: when a World Partition cell holding a spawner unloads, all of that spawner's entities are destroyed. `bAutoSpawnOnBeginPlay` defaults to true. — [UE 5.9 MassSpawner.cpp](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/Runtime/MassGameplay/Source/MassSpawner/Private/MassSpawner.cpp)
- The source also carries a "temp fix for streaming levels async loading MassSpawners after `UMassSpawnerSubsystem::OnPostWorldInit`", which applies to network clients. — [UE 5.9 MassSpawner.cpp](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/Runtime/MassGameplay/Source/MassSpawner/Private/MassSpawner.cpp)
- The crowd visualization trait has a `WorldPartitionGridNameContainingCollision` parameter (`NAME_None` by default). — [UE 5.9 MassCrowdVisualizationTrait.cpp](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/AI/MassCrowd/Source/MassCrowd/Private/MassCrowdVisualizationTrait.cpp)
- City Sample Big City (about 4×4 km) loads no cells at open, and World Partition streams cells at runtime. — [Epic: City Sample Project](https://dev.epicgames.com/documentation/unreal-engine/city-sample-project-unreal-engine-demonstration)

**Procedural generation options**
- City Sample: Houdini-generated city data includes metadata that drives the traffic and crowd AI. — [Epic: City Sample Project](https://dev.epicgames.com/documentation/unreal-engine/city-sample-project-unreal-engine-demonstration)
- **PCGEx (third-party PCG extension, "Pro" tier):**
  - The **"Cluster to Zone Graph"** node turns a PCGEx cluster into ZoneGraph shapes. Vertices with 3 or more edges become **polygon intersections**, edge chains between them become **spline roads**, and leaf vertices become road ends.
  - Lane profile is resolved per road from an edge attribute, and intersection size can derive from lane widths.
  - Upstream nodes include "Path : To Clusters", "Cluster : Connect Points", "Cluster : Delaunay 2D" and "Mesh to Clusters".
  - Unfused overlapping spline endpoints create separate leaf nodes instead of junctions.
  — [PCGEx: Zone Graph](https://pcgex.gitbook.io/pcgex/zone-graph); [PCGEx search snippet](https://pcgex.gitbook.io/pcgex/zone-graph/working-with-zonegraph)
- **UnrealDrive** (third-party road plugin): builds ZoneGraph from road lane data. ZoneGraphData is built only for actors with a `URoadGraphDataComponent`, produced at bake time. — [UnrealDrive docs](https://unrealdrive.readthedocs.io/en/stable/ZoneGraph.html)
- A forum question on converting a regular spline to a ZoneShape has no answer in search results. — [Forum: Spline to Zone Shape](https://forums.unrealengine.com/t/spline-to-zone-shape/1207729)
- Third-party advice (StraySpark, unbenchmarked): use 2–3 lanes per sidewalk for bidirectional flow, and split zone graphs per district rather than one map-wide graph. — [StraySpark blog](https://www.strayspark.studio/blog/crowd-traffic-simulation-ue5-mass-ai)

### Inferences
- **Map-scale density trap (important).** The ZoneGraph generator spreads `Count` uniformly at random over all matching lanes in the whole world. A 3.5-mile-radius map covers about 100 km², so tagging every OSM footway would dilute even thousands of agents into near-empty streets. For comparison, Matrix Awakens had 35k pedestrians over a 4×5 km world with 260 km of roads (see Q4). Building one candidate point per 1–3 m over the whole network at spawn time is also a one-off cost proportional to total lane length. Mitigations:
  - Only build or tag crowd lanes in the playable core districts.
  - Use a distinct ZoneGraph tag per district with a spawner per district (spawner `TagFilter`).
  - Or write a custom spawn data generator that only accepts points near the player.
- Because spawners are spatially loaded and despawn on unload, there are two workable WP patterns:
  - (a) A few spawners with **Is Spatially Loaded unchecked** (always loaded) for a persistent population.
  - (b) Per-district spawners left spatially loaded, so crowds appear and vanish with streaming. Streaming distances must hide the pop.
- **Fastest OSM route for this team:** they already have OSM data and Python tooling. An editor Python script that spawns `ZoneShape` actors per OSM `highway=footway`/`sidewalk` polyline (setting `points`, `lane_profile`, `tags` through `set_editor_property`), followed by Build ZoneGraph, is likely the quickest path. Crossings and intersections can be skipped for a jam: unconnected spline lanes simply dead-end, and wanderers turn around or pick new targets. This is unverified: Python access to `FZoneShapePoint` fields and lane-profile refs should be tested on a tiny sample first.
- All ZoneShapes are always loaded, so a very large lane network costs memory and editor load time permanently. Keep lane density reasonable (sidewalks in core areas, not every alley).

### Gaps
- No primary source on ZoneGraph Build behaviour when World Partition cells are unloaded in the editor. Because ZoneShape actors are non-spatial by default, it probably isn't an issue, but shapes placed as components on spatially loaded actors (for example PCG-spawned) may be skipped if their cell isn't loaded at build time. Verify.
- No measured ZoneGraph memory cost per km of lanes was found.
- PCGEx's required UE version, runtime vs editor-only behaviour and World Partition handling were not stated on the fetched page.

## 4. Measured or reported performance

### Takeaway
Epic has not published per-100 or per-1,000-agent millisecond costs for MassCrowd. The headline evidence is Matrix Awakens: about **35,000 simulated pedestrians**, 18k simulated vehicles and about 40k parked cars on PS5/XSX, with only a few hundred visible at once. Community and third-party numbers suggest Mass simulation is cheap (low single-digit ms for thousands of agents). The costs that bite are **spawned skeletal actors** (animation and skinning on CPU) and **actor spawning hitches**, which is why the high-res tiers are capped at 10/20 actors by default.

### Cited Findings
- **Matrix Awakens (Epic):** about 35,000 simulated MetaHuman pedestrians in a world roughly 4×5 km with 260 km of roads and 7,000 buildings. Jeff Farris (Epic) described 35,000 crowd members, 18,000 simulated vehicles and 40,000 parked cars. Crowds persist when the player leaves and returns. — [Search summary of press coverage incl. AOL/Variety "Inside The Matrix Awakens"](https://www.aol.com/news/inside-matrix-awakens-epic-games-040021751.html); [GamesBeat](https://gamesbeat.com/?p=206063) (secondary sources quoting Epic stats)
- **City Sample (Epic):** hundreds of crowd characters visible in Drone mode. Recommended specs for Big City: 12-core 3.4 GHz CPU, 64 GB RAM, RTX 2080 / RX 6000-class GPU with 8 GB+ VRAM, SSD. — [Epic: City Sample Project](https://dev.epicgames.com/documentation/unreal-engine/city-sample-project-unreal-engine-demonstration)
- **Stock caps (UE 5.9 source):** spawned actors are capped at 10 high-res + 20 low-res and ISMs at 500. With `bKeepLowResActors` = true, the low-res actor is kept while the ISM shows, as a spawning optimization. This implies actor spawn and despawn is a known cost. — [UE 5.9 MassCrowdVisualizationTrait.cpp](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/AI/MassCrowd/Source/MassCrowd/Private/MassCrowdVisualizationTrait.cpp)
- **Anecdotal (forum, UE 5.6.1):** about 2,000 Mass units (Mass Entity, MassCrowd, ZoneGraph, StateTree) ran stably above 60 FPS. Hardware and representation are not stated. — [Forum: 5.6 Mass AI FPS drop](https://forums.unrealengine.com/t/ue-5-6-mass-ai-severe-fps-drop-after-5-8-1-downgrade-invalid-lane-location-fixed-by-recreating-zonegraph-data/2742990)
- **Third-party "benchmark" (StraySpark, low confidence):** one urban scene at 1080p with Nanite and Lumen and a 3-LOD representation. No game-thread/render split or methodology.

  | Agents | RTX 4080 | RTX 4060 | PS5/XSX |
  |---|---|---|---|
  | 1,000 | 1.2 ms | 1.8 ms | 2.1 ms |
  | 5,000 | 2.8 ms | 4.5 ms | 5.2 ms |
  | 10,000 | 4.6 ms | 7.8 ms | 9.1 ms |
  | 20,000 | 8.2 ms | 14.1 ms | 16.5 ms |

  The article also asserts, without data, that a standard UE AI character costs about 0.13–0.41 ms per agent per frame (animation 0.05–0.15 ms), that VAT costs about 0.002 ms per agent, and that rendering dominates below about 5,000 agents. — [StraySpark blog](https://www.strayspark.studio/blog/crowd-traffic-simulation-ue5-mass-ai)
- **Forum consensus:** skeletal meshes are CPU-skinned or animated per instance and don't instance like static meshes. VAT on ISM is the usual answer for big crowds. Animation Sharing (leader pose) is a mid-way option. — [Search summary of forum threads incl. Vertex Animation Toolset](https://forums.unrealengine.com/t/vertex-animation-toolset-crowd-rendering/132246/15); [Forum: Mass 5.5 thousands of units](https://forums.unrealengine.com/t/mass-5-5-mass-entity-thousands-of-units/2487745)
- Epic says the Animation Sharing approach will be "much slower than the ISKM approach" (5.8+). — [Forum: AnimBank and ISKM](https://forums.unrealengine.com/t/animbank-and-instanced-skinned-mesh-component/2734825)
- **Profiling:** UE 5.9 ships a **MassInsights** plugin (beta), "Plugin to gather insights into Mass execution". — [UE 5.9 plugins folder](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/MassInsights/)

### Inferences
- Budget order for this project, from biggest to smallest:
  1. Full skeletal actors with anim blueprints (High tier). Keep to about 10–30.
  2. Low-res actors.
  3. ISM draw cost, which is small with instancing; AnimToTexture adds vertex-shader cost.
  4. Mass simulation (movement, avoidance, StateTree), cheap per agent.
- For a jam, 1,000–3,000 simulated agents with about 500 ISM visible and about 30 actors is a conservative target. Validate with `stat game`, `stat unit` and Unreal Insights or MassInsights on the target machine.

### Gaps
- No Epic-authored ms or memory breakdown (game thread vs render vs GPU) for MassCrowd at 100 or 1,000 agents was found.
- No reliable memory-per-entity figure was found.
- The StraySpark numbers are unverifiable.

## 5. Common pitfalls and gotchas

### Takeaway
Most "crowd doesn't appear" reports come down to the same handful of causes: missing plugins, no or empty ZoneGraph data, tag mismatches, processors not registered (5.2), spawners in unloaded cells, and stale data after engine version changes. Mass plugins remain experimental in 5.9, and version upgrades (including City Sample on 5.7) have broken setups.

### Cited Findings
**Spawning failures**
- **"No locations found on zone graphs" / 0 entities:** the ZoneGraph generator errors when no registered ZoneGraphData exists ("No zone graphs found") or when no lane passes the TagFilter ("No locations found on zone graphs"). — [UE 5.9 MassEntityZoneGraphSpawnPointsGenerator.cpp](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/Runtime/MassGameplay/Source/MassSpawner/Private/MassEntityZoneGraphSpawnPointsGenerator.cpp)
  - Setting both MinGap and MaxGap to 0 is rejected with an error.
- **City Sample on 5.7:** traffic and crowd don't spawn, with "LogMassSpawner: Error: No locations found on zone graphs". The workaround was to manually run **Build** on the `CityTrafficBuilder_BP` actor, a step that "never happened before". — [Forum: UE 5.7 City Sample broken](https://forums.unrealengine.com/t/ue-5-7-city-sample-broken/2701997)
- **City Sample on 5.2 / 5.2.1:**
  - Crowds not showing (only sound audible) in the MassCrowd map.
  - Tutorial followers seeing 0 entities in the debugger, even with the HairStrands, MassAI, MassCrowd and MassEntity plugins enabled.
  — [Forum: City Sample Crowds still not working in 5.2.1](https://forums.unrealengine.com/t/city-sample-crowds-still-not-working-in-5-2-1/1265776); [Forum: City Sample in 5.2 crowd doesn't show](https://forums.unrealengine.com/t/city-sample-in-ue-5-2-ai-map-masscrowd-level-crowd-doesnt-show-only-sound-can-be-heard/1190310)
- **UE 5.2 processor bug:** processor execution flags were set incorrectly (fixed in 5.2.1). The workaround was to set the Editor flag on processor CDOs (DebugVisLocationProcessor, MassUpdateISMProcessor, MassVisualizationLODProcessor) in Project Settings > Mass. Crowd visualization processors also needed auto-registration. — [Mirror of Epic tutorial](https://teletype.in/@hardway/60minwithmass)
- **Missing plugin:** the tutorial's plugin list omitted MassCrowd. — [Forum: Your First 60 Minutes with Mass](https://forums.unrealengine.com/t/tutorial-your-first-60-minutes-with-mass/794314/38)

**Phantom agents**
- **Extra agents stuck at 0,0,0:** every actor with a MassAgent component (added to make actors "Mass-aware" for avoidance) generated an extra crowd agent at the origin. A spawner Count of 40 gave 43 agents. Removing MassAgent from those actors fixed it (UE 5.2.1). — [Forum: City Crowd Samples, MassSpawner & Spawn Count](https://forums.unrealengine.com/t/city-crowd-samples-massspawner-spawn-count/1282266)

**Version and data issues**
- **Stale data after a version round trip:** going 5.6.1 → 5.8.1 → back to 5.6.1 dropped about 2,000 agents at 60+ FPS to 6 FPS at about 1,000 agents, with log spam "[MassZoneGraphFindWanderTarget] Invalid lane location". Fixed by deleting and rebuilding the ZoneGraph Data, then recreating Mass Entity Config assets under new package names. — [Forum: 5.6 Mass AI FPS drop](https://forums.unrealengine.com/t/ue-5-6-mass-ai-severe-fps-drop-after-5-8-1-downgrade-invalid-lane-location-fixed-by-recreating-zonegraph-data/2742990)
- **ZoneGraph not auto-building:** `bBuildZoneGraphWhileEditing` defaults to false. — [UE 5.9 ZoneGraphSettings.h](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/Runtime/ZoneGraph/Source/ZoneGraph/Public/ZoneGraphSettings.h)
- **Editing City Sample's ZoneGraph:** a user reports lanes only became visible after pressing **P**. — [Forum: How to modify City Sample's ZoneGraph?](https://forums.unrealengine.com/t/how-to-modify-city-samples-zonegraph/652645)

**Behaviour and integration issues**
- **Traffic stopping at zone connection points** and **crowd zonegraph tolerances**: agents drift after collisions. Both are reported, with no accepted fix found. — [Forum: zone graph stopping traffic](https://forums.unrealengine.com/t/massentity-zone-graph-are-stopping-traffic-on-their-connection-points/794222); [Forum: City Sample Crowd Zonegraph tolerances](https://forums.unrealengine.com/t/city-sample-crowd-zonegraph-tolerances/1757039)
- **Sequencer / Movie Render Queue:** a reported failure to get Mass crowds to work in Level Sequencer renders. — [Forum: Mass crowd AI with video renders](https://forums.unrealengine.com/t/cant-get-mass-cowd-ai-to-work-with-video-renders-in-level-sequencer/1735964)
- **High-res actors not following entities:** a reported issue where spawned actors don't move with their Mass agents. The tutorial's answer is a MassAgent component with Agent Movement Sync = Mass→Actor. It also says to use the same BP for the low-res template, because movement sync needs the Character Movement Component wrapper. — [Forum: spawned actor not moving](https://forums.unrealengine.com/t/mass-entity-spawned-actor-not-moving-with-the-simulated-mass-agents/1197697); [Mirror of Epic tutorial](https://teletype.in/@hardway/60minwithmass)
- **Smart Objects:** a `FindSmartObject` StateTree task found nothing when the SmartObject ZoneGraph annotations weren't set up. — [Forum: FindSmartObjectTask](https://forums.unrealengine.com/t/findsmartobjecttask-on-a-state-tree-does-not-find-smartobject/2667828)

**World Partition**
- A spawner in a streamed cell despawns all its agents on cell unload (EndPlay → DoDespawning). — [UE 5.9 MassSpawner.cpp](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/Runtime/MassGameplay/Source/MassSpawner/Private/MassSpawner.cpp)
- The editor loads cells for editing, which can mask streaming problems, so test in Standalone or a packaged build. — [bugnet blog (third-party)](https://bugnet.io/blog/fix-unreal-world-partition-streaming-not-loading)

**MetaHumans and skeletal meshes**
- 5.8+ ISKM has no anim BP support, and a GPU memory leak is reported with SkinnedMeshInstance crowds in 5.8 (unverified). — [Forum: AnimBank and ISKM](https://forums.unrealengine.com/t/animbank-and-instanced-skinned-mesh-component/2734825)
- MetaHumanCrowd in 5.9 pulls in Mover, HairStrands, Chaos Cloth/Outfit and MetaHumanCharacter as dependencies. — [UE 5.9 MetaHumanCrowd.uplugin](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/MetaHuman/MetaHumanCrowd/MetaHumanCrowd.uplugin)

**Debug console commands (UE 5.9 source)**
- `ai.mass.ForceSpawn`, `ai.mass.ForceDespawn` and `ai.mass.ResetSpawning` (respawn all spawners).
- `ai.mass.scalability.SpawnDensityMultiplier`, a scalability CVar that must be set **before** Mass spawn init. Final count = `Count × SpawningCountScale × SpawnDensityMultiplier`.
— [UE 5.9 MassSpawner.cpp](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/Runtime/MassGameplay/Source/MassSpawner/Private/MassSpawner.cpp)
- The Gameplay Debugger (apostrophe key in PIE) shows Mass entity transforms and steering. — [Mirror of Epic tutorial](https://teletype.in/@hardway/60minwithmass)

### Inferences
- Before any engine bump (5.9 → 5.x), back up and plan to **rebuild ZoneGraph data**. If "Invalid lane location" appears, recreate the entity configs.
- Don't put MassAgent components on random props for avoidance. Use them only on the player and other deliberately Mass-aware actors, and watch for phantom agents at the origin.
- The PIE lock and train-window rules for this project still apply: testing crowds needs PIE, so keep test scripts short.

### Gaps
- No primary source on **packaged vs editor** differences specific to MassCrowd (for example, processors that only run in the editor once the 5.2 flags issue is fixed). Test a packaged build early.
- No confirmed 5.4 → 5.6 API breakages for MassCrowd were found in this pass. Release notes were not fetched.

## 6. Minimum viable MassCrowd setup on an existing map (a few hours)

### Takeaway
A wandering-pedestrian crowd on ZoneGraph sidewalks needs about 10 steps:

1. Enable the plugins.
2. Define ZoneGraph tags and a lane profile.
3. Set the Mass Crowd Crowd tag.
4. Place or script ZoneShapes.
5. Build ZoneGraph.
6. Make an entity config with movement, ZoneGraph navigation, crowd visualization and StateTree traits.
7. Make a small StateTree.
8. Place an always-loaded MassSpawner with the ZoneGraph generator.
9. PIE and debug.
10. Tune the LOD caps.

No navmesh is required.

### Cited Findings
Step list assembled from the sources below. Each step cites where it came from.
1. **Plugins:** MassEntity (core), MassGameplay, MassAI, **MassCrowd**, ZoneGraph, ZoneGraphAnnotations (MassCrowd depends on it), StateTree. Restart once. Add AnimToTexture later if baking VATs. — [Mirror of Epic tutorial](https://teletype.in/@hardway/60minwithmass); [Forum note on MassCrowd](https://forums.unrealengine.com/t/tutorial-your-first-60-minutes-with-mass/794314/38); [UE 5.9 MassCrowd.uplugin](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/AI/MassCrowd/MassCrowd.uplugin)
2. **Project Settings > ZoneGraph:** add tags (for example a sidewalk/crowd tag) and a lane profile with 2 lanes (forward and backward) carrying that tag. — [Mirror of Epic tutorial](https://teletype.in/@hardway/60minwithmass); [UE 5.9 ZoneGraphSettings.h](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/Runtime/ZoneGraph/Source/ZoneGraph/Public/ZoneGraphSettings.h)
3. **Project Settings > Mass Crowd:** set `CrowdTag` (and optionally `CrossingTag` and `LaneDensities`). It has no engine default. — [UE 5.9 MassCrowdSettings.h](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/AI/MassCrowd/Source/MassCrowd/Public/MassCrowdSettings.h)
4. **ZoneShapes:** place ZoneShape actors along sidewalks, or script them by setting `Points`, `LaneProfile`, `Tags` and `ShapeType`. Use closed loops or connected networks so wanderers don't dead-end. They are always loaded under World Partition by default. — [Mirror of Epic tutorial](https://teletype.in/@hardway/60minwithmass); [UE 5.9 ZoneShapeComponent.h](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/Runtime/ZoneGraph/Source/ZoneGraph/Public/ZoneShapeComponent.h); [UE 5.9 ZoneShapeActor.cpp](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/Runtime/ZoneGraph/Source/ZoneGraph/Private/ZoneShapeActor.cpp)
5. **Build > Build ZoneGraph**, then save. Auto-build is off by default. — [Mirror of Epic tutorial](https://teletype.in/@hardway/60minwithmass); [UnrealDrive docs](https://unrealdrive.readthedocs.io/en/stable/ZoneGraph.html)
6. **Mass Entity Config asset** with these traits:
   - Movement, with a movement style.
   - Steering.
   - Smooth Orientation.
   - Avoidance, plus an Agent Radius fragment.
   - ZoneGraph Navigation, with the crowd tag and Query Radius 5000.
   - Navigation Obstacle.
   - A LOD Collector.
   - Crowd Member.
   - Crowd Visualization: High-res actor template, Low-res actor template, and a static mesh instance desc for the ISM tier.
   - StateTree.
   — [Mirror of Epic tutorial](https://teletype.in/@hardway/60minwithmass); [UE 5.9 MassCrowd headers](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/AI/MassCrowd/Source/MassCrowd/Public/)
7. **StateTree (Mass Behavior schema):** Wander = `ZG Find Wander Target`, then `ZG Path Follow`, transitioning to Idle. Idle = `ZG Stand` for 1.5 s, then back to root. — [Mirror of Epic tutorial](https://teletype.in/@hardway/60minwithmass)
8. **High-res actor:**
   - A character BP with a looping walk animation BP.
   - A MassAgent component with Movement Sync = Mass→Actor and Feet Location Sync = Actor→Mass.
   - The same BP as the low-res template if movement sync is needed.
   - Mesh offset Z −90 and Yaw 270 for the mannequin case.
   — [Mirror of Epic tutorial](https://teletype.in/@hardway/60minwithmass)
9. **MassSpawner:**
   - Entity Types = the config.
   - Spawn Data Generator = **ZoneGraph Spawn Points Generator** with TagFilter = the crowd tag. MinGap/MaxGap default to 100/300 cm.
   - Set Count.
   - `bAutoSpawnOnBeginPlay` = true (default).
   - Uncheck **Is Spatially Loaded** if the spawner sits in a World Partition map and the crowd should persist.
   — [UE 5.9 MassEntityZoneGraphSpawnPointsGenerator.h](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/Runtime/MassGameplay/Source/MassSpawner/Public/MassEntityZoneGraphSpawnPointsGenerator.h); [UE 5.9 MassSpawner.cpp](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/Runtime/MassGameplay/Source/MassSpawner/Private/MassSpawner.cpp)
10. **Player:** add a MassAgent component with a config containing Navigation Obstacle and Agent Capsule Collision Sync (Actor→Mass), so pedestrians avoid the player. — [Mirror of Epic tutorial](https://teletype.in/@hardway/60minwithmass)
11. **Debug:**
    - Gameplay Debugger in PIE.
    - Check the Output Log for `LogMassSpawner` errors.
    - Use `ai.mass.ResetSpawning` after edits and `ai.mass.scalability.SpawnDensityMultiplier` for density.
    — [Mirror of Epic tutorial](https://teletype.in/@hardway/60minwithmass); [UE 5.9 MassSpawner.cpp](file:///C:/Program%20Files/Epic%20Games/UE_5.9/Engine/Plugins/Runtime/MassGameplay/Source/MassSpawner/Private/MassSpawner.cpp)
12. **Sanity test first:** the tutorial's EQS donut spawn (Inner 1000, Outer 3000, 5 rings × 12 points) with the Debug Visualization trait (cone mesh, far cull 25000) proves the spawner works before ZoneGraph is involved. — [Mirror of Epic tutorial](https://teletype.in/@hardway/60minwithmass)

### Inferences
- **Jam plan (about 18 h):**
  - Prove the pipeline on a 2–3 block pilot area with hand-placed or scripted ZoneShapes before scripting the whole OSM footway network. Tag only the playable core to avoid the density-dilution trap from Q3.
  - Use the existing Frostside/Giltside character actors as the High-res and Low-res templates, honouring the side-specific outfit rules.
  - Use a single static mesh for the ISM tier.
  - Raise `LODMaxCount[Low]` and `VisibleLODDistance[Off]` for density.
- **Commercial follow-ups:**
  - Bake AnimToTexture VATs, or evaluate 5.8+ ISKM.
  - Add crossings/intersections (polygon ZoneShapes, CrossingTag, lane annotations).
  - Add Smart Objects (benches, market stalls) via ZoneGraph annotations.
  - Write a custom player-proximity spawn generator.
  - Use per-district streaming spawners.
  - Run a packaged-build soak test.
- Avoid migrating City Sample wholesale: it is heavy (64 GB RAM recommended), MetaHuman-centric, and has broken on version bumps (5.2, 5.7).

### Gaps
- No primary source gives exact recommended lane widths for sidewalk lane profiles. A 2-lane profile of about 1–1.5 m per lane is a reasonable guess, not sourced.
- Python editor scripting access to `FZoneShapePoint` and `FZoneLaneProfileRef` is implied by BlueprintReadWrite but was not tested.
- The Epic "Designing Scalable Crowds with Mass AI" community tutorial (Dec 2025, by ICVR, covers ZoneGraph/NavMesh, StateTree, Smart Objects, LOD and AnimToTexture) could not be fetched because the page is JS-rendered. It is worth reading manually: [Epic community tutorial](https://dev.epicgames.com/community/learning/tutorials/zqZZ/unreal-engine-epic-for-indies-designing-scalable-crowds-with-mass-ai-a-comprehensive-ue-guide); [Forum summary](https://forums.unrealengine.com/t/community-tutorial-designing-scalable-crowds-with-mass-ai-a-comprehensive-ue-guide/2686225)
