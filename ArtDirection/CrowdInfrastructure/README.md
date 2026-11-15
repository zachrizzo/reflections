# MetaHuman Crowd test infrastructure

## The walking crowd in Lvl_HeroSampleCrowd and spells (2026-11-14)

**What the walkers are.** The NPCs walking around `/Game/Characters/Hero/Sample/Lvl_HeroSampleCrowd` are not a Mass/MetaHuman Crowd. The map has no Mass spawner, and the three `MassVisualizer` actors seen in PIE are empty plugin defaults. The walkers are six placed MetaHuman actor Blueprints (plain actors, not pawns):

- four CrowdMotion SimpleRed looks: BridgeGuard, ArchiveApprentice, CoinClerk, FestivalDrummer;
- two White London looks: WhiteLook_01 and WhiteLook_06.

Each is tagged `NPC_Reactive NPC_HitProxy NPC_SampleLocomotion`. At play, the unified NPC system (`NPC/ReflectionsNpcSubsystem`) enrols them. It gives each one health, the NPC component with an archetype, and a query capsule that spells can hit. Each walker is attached to a hidden `BP_SampleCMCClean2` pawn (Game Animation Sample CharacterMovement + motion matching) that drives its position and pose. A walker in this map and a civilian placed anywhere else use the same component and archetypes. There is no separate crowd brain.

**Why spells seemed to do nothing (found 2026-11-14, before the unified NPC system loaded):**

- Catalog spells did land when they connected. A Fire Bolt took a walker from 100 to 86.
- A Fireball aimed at a moving walker flew past it and hurt nobody. Projectiles only home on aim-assist targets, and aim assist never picks a walker: they aren't pawns, five of six are tagged `Friendly`, and the hidden driver pawns fail its line-of-sight test.
- Crafted spells never damage `Friendly` actors, and five of the six walkers are `Friendly`.
- Civilians who only became "alert" froze in place for seven seconds.
- A lethal hit ragdolled only the one walker tagged `NPC_Ragdoll`. The others stood still at 0 HP.

The aim-assist and crafted-spell causes are in the spell and crafting code and were reported to their owners. Reactions, damage, death and ragdoll now belong to the unified NPC system (`ArtDirection/NPC_Unified/README.md`).

**Strolling like city pedestrians.** `Source/reflections/Crowd/ReflectionsCrowdStrollSubsystem` takes over a walker's movement while it is calm, through the NPC system's `SetExternallySteered`. It hands the walker back the moment the NPC system reports any other reaction.

- The hidden sample pawn defaulted to the Run gait with strafing on, which is why walkers jogged and shuffled. While a walker strolls, its pawn is switched to Walk, with strafe and sprint off.
- Each walker picks a goal 4–14 m from home on open floor. A floor trace and a capsule sweep keep goals off blocks and out of walls.
- It walks there at its own speed of 120–160 cm/s and pauses 1.5–5 s, now and then 7–12 s.
- Fleeing is still allowed to run.
- `Crowd.Stroll.Enable 0` turns it off.

**What PIE showed on 2026-11-14 (editor at 12:13 local, with the unified NPC system and the crowd subsystems loaded).** Screenshots are in `Saved/CrowdReactions/`.

| Check | Result |
|---|---|
| Strolling | Works. All six walkers stroll in Walk gait at 150–155 cm/s and pause at their goals (`stroll_city_walk.png`). |
| Fireball scatter | Works. A Fireball landing among them made the two civilians flee (+560 cm and +296 cm away from the blast) and the alert one edge away. The brave and guard walkers walked over to investigate, which is their archetype's choice. Strolling handed every reacting walker back to the NPC system (`scatter_*.png`). |
| Direct hit, lethal hit, ragdoll | Works. Four Fire Bolts took a walker 45 → 31 → 17 → 3 → 0. It went Incapacitated with its body simulating physics (`lethal_ragdoll*.png`). |
| Squad marching through | Partly. Civilians in the lane stepped aside (33 frames of yielding) and kept at least 143 cm from soldiers. Civilians standing still are not pushed. |
| Homing Fireball at a running walker; crafted spell on a civilian | Not verified. Both fixes landed in the spell and crafting code, but in this run their target had fallen off the map (see below). |

**Not working yet:**

- Fleeing civilians could run off the edge of the sandbox floor and fall out of the world. The NPC system's next build sets `bCanWalkOffLedges = false` on every walker's locomotion pawn, so the fix lives there.
- Some walkers sometimes stand or walk in a T-pose with arms out. The log then shows "GetBoneMatrix: BoneIndex out of range of SpaceBases" for their Body mesh, and the same condition crashed the editor twice on 2026-11-14.
  - The warnings are in logs from before any crowd code existed, and they continue with the crowd LOD switched off.
  - The NPC system's owner traced one trigger to the partial-physics hit flinch, which is now off. The squad animation switch is a second suspect.
  - Their next build re-registers any living body whose bone buffers are incomplete, and logs "body bone buffers were incomplete".

**Cost, and the crowd animation LOD.** Measured in editor PIE on this map (Ryzen 7 9700X, RTX 5080), the six walkers cost about 7 ms of game-thread time: median 27.5 ms with them active, 20.6 ms with all their ticks frozen. They also cost about 1 ms of GPU. Per walker:

- about 0.3 ms CharacterMovement and 0.2 ms mesh tick on the game thread;
- 1–2.5 ms of worker-thread motion matching for the hidden driver;
- 0.3–0.5 ms for the MetaHuman body and 0.15–0.27 ms for the face.

These are editor numbers with stats enabled. They show that each walker is a full sample character, so dozens of walkers would not be cheap.

With the crowd LOD, a later run measured these game-thread medians:

| LOD setting | Game thread (median) |
|---|---|
| Off | 19.9 ms |
| Default | 17.7 ms |
| Aggressive (everything beyond 0 m at 15 Hz) | 16.3 ms |

The six walkers were spread around the player, two of them off screen. Those runs were in the same editor session, not a controlled benchmark.

`Source/reflections/Crowd/ReflectionsCrowdLodSubsystem` lowers the animation rate of walkers that are far away or off screen. It changes only skeletal-mesh tick intervals on the walker and its driver: movement, reactions and damage are untouched.

| Tier | When | Animation rate |
|---|---|---|
| Full | within 18 m of the camera, or woken | every frame |
| Mid | on screen, 18–40 m | 30 Hz |
| Far | on screen, beyond 40 m | 15 Hz |
| Hidden | not rendered recently | 6 Hz |

A walker is woken back to every frame immediately when:

- the unified NPC system reports a stimulus within 25 m;
- the walker reacts (anything but calm) or is hit by a spell;
- its body simulates physics (a hit flinch or a ragdoll).

It stays woken for 9 s. Console:

- `Crowd.Lod.Enable 0|1` turns it off or on.
- `Crowd.Lod.NearDistance`, `FarDistance`, `MidHz`, `FarHz`, `HiddenHz`, `WakeRadius` and `WakeSeconds` tune it.
- `Crowd.LodDump` logs each walker's tier.
- **Driver cameras (train #8).** Each walker's hidden locomotion pawn is the sample hero pawn, and it carries the hero's `GameplayCameraComponent`. A PIE hitch dump showed that camera rig being evaluated every frame on all 12 drivers, about 1.1 ms in total, for a camera nobody views through. The LOD subsystem now switches it off on drivers no player controls (`Crowd.Lod.QuietDriverCameras`, default 1). The saving has not been measured yet.
- Other costs on those drivers, from the same dump and owned by the NPC system: character movement plus moving the attached visible body (about 3 ms for 12 drivers in the worst frame), and foley anim notifies firing on the driver meshes (about 1 ms; this may also double NPC footsteps).

**Making way for squads.** `Source/reflections/Crowd/ReflectionsCrowdYieldSubsystem` makes calm or merely alert civilians step out of the path of a marching enemy squad (NPC actors tagged `NPC_Soldier`, from `Source/reflections/Squads/`) and of a running player.

- The lane each moving soldier clears is 240 cm on either side and up to 5.5 m ahead. For the player, the lane is 150 cm on either side, and it applies only above 320 cm/s.
- The unified NPC system decides who takes part: which actors are NPCs, their disposition, whether they are calm, and which character walks for them. Enemy, infected and villain-host NPCs never make way.
- The step aside is one extra movement input per frame on the civilian's own walker, added to whatever the NPC system is already doing. Fleeing, investigating, fighting and downed NPCs are left alone.
- Soldiers are never steered by it, so squad formations are untouched.
- The walkers' hidden driver capsules don't collide with each other. Without this layer, civilians and soldiers walk through each other.
- Lvl_HeroSampleCrowd has no navmesh, so neither crowd nor squads share navigation there.
- `Crowd.Yield.Enable 0|1` turns it off or on, `Crowd.Yield.Debug 1` draws the lanes, and the other `Crowd.Yield.*` variables tune it.

## Gray London (from train #14)

The old maps (`Lvl_HeroSampleCrowd`, `Lvl_MockCity`, the Mass crowd level) were deleted. `/Game/GrayLondon/Maps/GrayLondon_Geodata` is the only map: one London, one side, no world jump.
- The ring crowd below now targets it (`Crowd.Ring.Maps` = `GrayLondon_Geodata`). It waits for world-jump's CitySidewalk lanes along the Tower district's pavements, and logs `no ZoneGraph lanes` once until they exist.
- With one side, every walker wears the red (Giltside) looks.
- The Mass city crowd has no host map by default, so it is dormant everywhere.
- Test: `Saved/CrowdReactions/verify_ring.py`. It travels to Gray London; the walk-away step replaces the world-jump step.

## The ring crowd: actor civilians on the sidewalks (train #10; first tested on the mock city)

The Mass crowd is **no-go for the jam**, a decision confirmed by the orchestrator on crowd-looks' recommendation. The city crowd in `/Game/MockCity/Lvl_MockCity` is therefore made of finished-look actor civilians.

- **Lanes.** World-jump placed 360 sidewalk ZoneShapes in the persistent `Lvl_MockCity`: one closed loop per block on each of the three sides, at final world coordinates, in the outliner folder `CrowdLanes`, and built the ZoneGraph data (saved 16:27). Lane data cannot follow a level-streaming offset, which is why the lanes are not in the side levels.
- **Ring.** `Source/reflections/Crowd/ReflectionsCrowdRingSubsystem` keeps `Crowd.Ring.Count` (12) civilians around the hero, on maps listed in `Crowd.Ring.Maps` (default `Lvl_MockCity` only).
  - They come from `SpawnNpc("Civilian")`, so they wear crowd-looks' finished civilian looks and react like every NPC.
  - **Side rule (the user's).** People in rags belong only to Frostside, people in red only to Giltside; never mix them. The ring crowd and promotion pass no look class, so `SpawnNpc` chooses from the looks of the side at the spawn point (NPC-unify, train #11). Pewterside has no looks of its own yet and gets Giltside's.
  - New walkers appear on lane points 15–45 m away, mostly ahead of the hero. After the first few, they appear only out of sight: outside the view, behind a building, or more than 60 m away.
  - A calm or dead walker more than 55 m away and unseen for 2 s is replaced ahead of the hero. After a world jump the crowd moves to the new side the same way.
  - `Crowd.Ring.Enable 0` removes them.
- **Walking the sidewalks.** Ring walkers are tagged `Crowd_LaneWalker`. The stroll subsystem walks them 10–30 m along the lane (`Crowd.Stroll.LaneLegMin`/`Max`), steering at a point 2.2 m ahead so they follow corners onto the next lane, then idles them like the other strollers. Without a lane nearby they stroll around their spawn point instead.
- **Verified in PIE on Lvl_MockCity** (19:32 build, run by the orchestrator from `Saved/CrowdReactions/verify_ring.py`; results in `ring_result.json`, screenshots `ring_mockcity.png` and `ring_after_jump.png`):
  - 12 walkers within about 10 s of arriving, all on lanes and walking at about 1.5 m/s. 9 of 11 walked 6–13 m in 8 s; the other two were fleeing or down.
  - The side rule holds: Gilt looks on Giltside, and Frost rag looks after jumping to Frostside.
  - After a 1.5 km jump, all 12 old walkers were replaced, and 12 new ones stood 20–44 m from the hero within 12 s.
  - **Cost** in editor PIE: about 5.7 ms of game thread for 12 (median 30.3 vs 24.5 ms), roughly 0.5 ms each with `Crowd.Lod`, plus 1.1 ms GPU. Keep 12 for the jam.
  - No pose warnings, no errors.
- **Playtest run 3** found the walkers standing still. Cause: the lives system of train #10 took every NPC's body, ring walkers included. From the 19:32 build it leaves `Crowd_Ring` actors to stroll.
- **Converted walkers.** A walker the villain converts leaves the ring and stays his. A fresh civilian replaces it.
- **Look preload.** From train #13 the ring loads the Civilian looks in the background at map start, so spawning doesn't stall on a first-time load. One 228 ms frame was seen during replacements in the test.
- **Not the villain's (train #13).** In the test the villain converted 3 ring walkers in about 40 s (Tarnish 3/20). At that rate the meter would hit 20 in 4–5 minutes. The orchestrator decided that ring walkers carry `NoVillain`, so the Tarnish takes only named or placed people. A walker converted before the tag existed still leaves the ring.
- **Back to the sidewalk (train #13).** After a fright, a calm walker now looks for a lane up to 20 m away (6 m before), so it walks back to the sidewalk instead of strolling round its spawn point.
- **Frostside variety.** In the test, every Frostside walker was FrostSilas or FrostHyeon. The look pool per side belongs to npc-unify; a request to add FrostIven, Nia, Saran, Amara, Tobias and Wen (armour-free only) has been sent.

## The city crowd: Mass pedestrians on ZoneGraph lanes (2026-11-14, not used for the jam)

The background crowd of `Lvl_HeroSampleCrowd` is a Mass / MetaHuman Crowd population, separate from the six placed walkers above. The host map file is not changed: everything lives in its own level, which `Source/reflections/Crowd/ReflectionsCrowdCitySubsystem` streams into the host map.

**Off by default.** `Crowd.Mass.Enable` defaults to 0 until the crowd has finished looks. Today every pedestrian has a white bald head, no brows and floating garments (see Known problems). Until then, Play shows only the six actor walkers. Type `Crowd.Mass.Enable 1` to stream the crowd in and `0` to remove it. The setting is shared by the whole editor, so set it back after testing.

**What is in it:**

| Asset or actor | What it is |
|---|---|
| `/Game/Crowd/City/Lvl_HeroSampleCrowd_City` | The crowd level: twelve ZoneShapes forming three sidewalk loops (the outer one at ±13.5 m, plus a north and a south block), one 150 cm lane each way, the ZoneGraph data built from them, and a `MassSpawner` placing 60 pedestrians on the lanes 1.5–4 m apart. The PIE results below were measured with the earlier one-loop, 40-pedestrian version; the 60-pedestrian version has not been run yet. |
| `/Game/Crowd/City/MEC_CityPedestrian` | Entity config. It keeps the prototype's MetaHuman Crowd visualization (Coin Clerk collection, instanced skinned meshes, baked walk and idle). It adds transform and radius fragments, movement (140 cm/s ±10%), steering, obstacle avoidance, ZoneGraph navigation, lane annotations and the StateTree. |
| `/Game/Crowd/City/ST_CityPedestrian` | StateTree: Wander (pick a target along the lane, walk there), then Stand for 4 s, repeat. Flee: when the current lane carries the danger annotation, pick an escape target and walk there at double speed. |
| `CitySidewalk` lane profile | Two 150 cm lanes, tagged Default. Only the editor needs it, to rebuild lanes. `Crowd.City.SetupZoneGraph` registers it in memory until the matching `DefaultEngine.ini` entry is added. |

**Verified in PIE** (shared editor, 2026-11-14):

- The crowd level streams in (it was on by default then): 40 entities, all 40 as instanced meshes, 14–18 on screen.
- The pedestrians walk the loop in both directions with the walk animation and pause at their targets (`Saved/CrowdReactions/mass_spike2_*.png`, `city_stream_west.png`).
- No Mass or StateTree errors in the log.
- `Crowd.Mass.Enable 0` unloads the level, leaving 0 entities; `1` brings all 40 back.
- **Cost:** about 1.0 ms game thread (median 21.6 vs 20.6 ms) and 0.4 ms GPU for all 40. The six placed actor walkers cost about 7 ms.

**Verified in PIE on build train #7** (shared editor, 15:37, crowd turned on for the test with `Crowd.Mass.Enable 1`; screenshots `Saved/CrowdReactions/city60_crowd.png`, `city_flee_*.png`):

- 60 pedestrians across the three loops: 60 entities, all as instanced meshes, 19–25 on screen. `0`/`1` unloads and restores all 60.
- A Fireball cast near them sent one danger area and promoted one pedestrian. In the screenshots the pedestrians break from walking into running and scatter.
- The promoted pedestrian became `BP_WhiteLook_02_Cap` (the random non-SimpleRed fallback) with the `no look mapping` warning logged, carried the `Friendly` tag, was outside the blast (full health) and was fleeing.
- No pose warnings (`bone buffers were incomplete`, `SpaceBases`) and no crowd errors.
- **Not measured:** the flee distances. The test read pedestrian positions from the instanced meshes, but MetaHuman Crowd instances live on the GPU only (the CPU instance count is 0), so nothing could be tracked. Frame cost is also not usable from this run: the shared editor was at a 37 ms game-thread baseline, against 20.6 ms in the earlier 40-pedestrian measurement. Crowd on read 41.0 ms game / 8.8 ms GPU against 37.0 / 5.9 off; treat that as an upper bound until a quiet-editor rerun.

**Spells (built; the flee distances and blast damage on a promoted pedestrian are still unmeasured):**

- **Escape.** Every stimulus the unified NPC system reports becomes a ZoneGraph danger area (at least 15 m, 6 s). The pedestrians' Flee state runs them away along the lanes. The danger annotation is spawned at runtime once the crowd level is in.
- **Promotion.** Up to six pedestrians (`Crowd.Mass.MaxPromoted`) within 7 m of a stimulus, or inside a spell's blast, are swapped for a full NPC actor, spawned as a Civilian through `UReflectionsNpcSubsystem::SpawnNpc`.
  - **Which look:** the actor should be the same person (face, outfit, tint). The crowd reads which MetaHuman Instance the pedestrian wears and looks it up in `/Game/Crowd/City/DT_CrowdLookMap` (rows of `ReflectionsCrowdLookRow`: `CrowdInstance` → `ActorClass`; CVar `Crowd.Mass.LookTable`). The crowd-looks session fills that table.
  - Until a row exists, it picks a random team look and logs `no look mapping for <instance>` once per Instance. The SimpleRed looks are skipped because those garments are not licensed for every market.
  - Each one receives the same stimulus. If it stood inside the blast, it takes the spell's damage and hit, so it flinches, flees, dies and ragdolls exactly like a placed civilian.
  - It then strolls like the six walkers. Calm ones more than 30 m from the player for 20 s are removed, so the crowd thins out after violence.
  - Like placed civilians, it can be hunted and converted by the villain's Tarnish; the `Friendly` tag no longer protects anyone from it.
- Pedestrians far from any spell are never actors, so a projectile cannot hit one directly; it can only catch them in a blast.

**Known problems:**

- **One look.** Every pedestrian is the same Coin Clerk (`MEC_CityPedestrian` lists one Instance). New looks are the crowd-looks session's job; they go into that config's `CharacterInstances`.
- **Visual defects.** The crowd-looks session's PIE check (13:2x) found white, untextured bald heads, no brows or lashes, and grey garments floating off the body (`Saved/CrowdLooks/before_pools/pie_viewport_start.png`). These come from the prototype collection; see "Later diagnostic findings" below. Crowd-looks is building new Red and White collections in `/Game/Characters/Lanthorne/CrowdMass/`; their Instances will replace the prototype in `MEC_CityPedestrian`.
- **No crossings.** Three separate loops; pedestrians do not cross between them yet.
- **Swap pop.** Until `DT_CrowdLookMap` has rows, a promoted pedestrian turns into a different person.
- **Size.** 60 pedestrians is the ceiling until the crowd-looks session signs off on the looks.
- **Packaging.** The crowd level is loaded by string path, so `/Game/Crowd/City` must be in the always-cook list (requested from the packaging session).

The NPC system's own Mass bridge functions (`GetActiveStimuli`, `EvaluateStimulus`) are not used. Escape goes through ZoneGraph annotations, and anything close enough to matter becomes a full NPC through `EnrollActor`.

## Street conversations: the chat director (built, train #7)

`Source/reflections/Crowd/ReflectionsCrowdChatSubsystem` plays audio's baked conversations between NPCs who are already standing together. The caller (the lives session, or later the crowd's own chat spots) brings the people together and keeps them still and facing each other; the director only talks.

- `PlayConversationBetween(Speakers, Spot)`: picks a row from `/Game/Audio/Jam/Voice/Ambient/DT_AmbientConversations` (generic voices) for the place and the number of speakers. `Spot` may be a marker name (`Haunt_Market` → `market`); rows tagged `street` fit anywhere. Rows the speakers already have the voices for come first. Otherwise each role's roster voice goes to a speaker of the same sex for the length of the conversation.
- `PlayConversationById(Speakers, ConvId)`: plays one named row, story table (`DT_StoryConversations`, named people's reserved voices) first. The caller passes the speakers in the row's role order and judges `Band` and `RequiredFlag` itself. Story rows are never picked at random.
- Lines play in turn from each speaker's head. The waves load in the background (train #8). It ends early on any non-calm reaction, a speaker more than 4 m from the group, or `StopConversation`. Each speaker's previous voice is put back at the end (train #8; in train #7 it cleared a lives person's voice).
- It returns false, so the caller can bark instead, while there is no table or no fitting row, a speaker is busy or not calm, the player is more than 25 m away, or three conversations are already playing. CVars: `Crowd.Chat.*`.
- Subtitles come from the waves themselves (engine subtitles set by audio); the director does not draw any.
- In PIE on train #7 it loaded audio's first 24 conversations. The voice check from that run was lost (see the train #7 notes above); it has not been verified that a conversation is heard end to end.

## Chat spots (proposal, not built)

Pedestrians would occasionally stop in pairs or small groups to talk, for audio's "passive talk":

- A `ChatSpot` actor with 2–4 slots facing a centre point, placed at sidewalk corners and plaza edges (about one per 15 m of sidewalk).
- Calm pedestrians claim a free slot now and then, walk to it, face the group and idle 15–40 s, then leave. Actor walkers would do this through the stroll subsystem; Mass pedestrians through a SmartObject state in the same StateTree.
- With two or more present, the crowd raises a conversation event for audio, which plays a baked, spatialised conversation (at most two or three at once, nearest the player first).
- Any NPC stimulus breaks the group up.
- **Voices.** A spot would call the chat director above, which casts the conversation's roster voices onto the gathered NPCs and gives their own voices back afterwards.

## Mass prototype

This is an isolated experiment for the installed UE 5.9 MetaHuman Crowd plugin. It does not construct or modify the city. The current prototype has one Red London Coin Clerk appearance, **not** the 36 conventional actor Blueprint variants and not a White London crowd. Treat each London group as a separate Collection/Instance set and Mass entity config, assigned to independently configurable spawners. The two populations can later be placed in separate streamed regions with different budgets and behavior.

## Artifacts

- `/Game/Characters/RedLondon/Crowd/Test/COL_CrowdPrototype_CoinClerk` is a Crowd Pipeline Collection built from the Coin Clerk source character, hair and eyebrow bindings, coat, trousers and boots.
- `/Game/Characters/RedLondon/Crowd/Test/MI_CrowdPrototype_CoinClerk` is a MetaHuman Instance with those seven slot selections. The target skeleton is `SKEL_CrowdPrototype_Final`; it is a separate saved asset and must stay with the Collection.
- `/Game/Characters/RedLondon/Crowd/Test/MEC_CrowdPrototype` is a Mass entity config using the plugin's MetaHuman Crowd visualization and Crowd Member traits, its Crowd Actor template, an LOD collector and core fragments. Its current test setting forces the instanced skeletal mesh representation at all active LODs, because the engine-provided actor template logged null-instance errors on the actor representation path. It is not a validated actor-to-instance transition.
- `/Game/Characters/RedLondon/Crowd/Test/Lvl_CrowdPrototype` is a separate flat test level with 20 configurable agents, a test grid spawner and telemetry actor. It is not connected to any production level.
- `Source/reflections/Crowd/ReflectionsCrowdGridGenerator.*` supplies a deterministic, configurable flat grid. It is for isolated tests: it does not project onto navmesh, follow streets, or avoid collisions.
- `Source/reflections/Crowd/ReflectionsCrowdTelemetry.*` logs actual plugin entity, visible, actor and instanced-representation counts, plus wall-clock frame intervals, under `Saved/Profiling/ReflectionsCrowd/`. Counts are polled once per second; frame intervals include editor overhead and are not separate CPU/GPU timings.
- The adjacent Python scripts are reproducible editor-side assembly and inspection helpers. A Collection build may take time and creates production build assets; run scripts in the editor only when nobody else is using it. `build_collection.py` deliberately refuses to overwrite an existing Collection. `repair_skeleton.py` was the one-time repair and should not be rerun against an already repaired Collection.

## Verified so far

The Collection build completed and its Instance assembled with seven selections. The first spawn failed template validation until the required actor fragment was added. The next run exposed a missing saved skeleton and null-instance errors in the engine actor template; the Collection was rebuilt using a saved skeleton, and the test entity config was changed to force ISKM. With this temporary setting, Epic's `MetaHumanCrowdStatsLibrary` reported **20 entities, 20 visible, 0 actor representations, 20 instanced skinned mesh representations** in Play In Editor. The editor was hidden and its captured screenshot was black. These numbers confirm representation bookkeeping, not that the crowd looked correct, animated or moved, and do not establish capacity.

Early CSVs were recorded while the editor was background-throttled to roughly 3 Hz; they are unsuitable for performance or capacity conclusions. Profile only after restoring and focusing the viewport, confirming intended frame-rate and vsync settings, verifying real rendered meshes, and allowing warmup. Capture a zero-crowd baseline and multiple densities in the same viewport and hardware conditions; compare median and high-percentile frame times, not just instantaneous FPS. Also inspect game/render/GPU times with Unreal Insights or `stat unit`, and record resolution, hardware, view, rendering quality and exact settings. A city with streamed geometry, AI, real outfits, traffic and other users will have different limits.

## Population contract

Use separate Red and White London Crowd Collections and MetaHuman Instances. The actor Blueprints produced under `/Game/Characters/RedLondon/Crowd/Variants` are independent conventional looks, not Crowd Instances; head/body MHC sources, hair bindings, and compatible garment skeletal meshes must be explicitly added to a Crowd Collection and built. Wardrobe and face combinations must be checked for skeleton/shape compatibility and correct material appearance. A matching asset name or Blueprint alone does not prove that conversion.

The included `add_test_motion.py` adds a simple randomized horizontal velocity for a synthetic stress test; it is unbounded straight-line movement, with no navigation, crowd avoidance, idle/walk state, or guaranteed walking animation. Proper city behavior still requires ZoneGraph or navmesh routing, lane and obstacle avoidance, state/animation logic, streaming and gameplay tests. `bake_test_animations.py` is an unverified helper to try baking idle/walk sequences into this experimental Collection; only a successful rebuild and visible playback can validate it.

Epic references: [Create MetaHuman Crowds](https://dev.epicgames.com/documentation/metahuman/create-metahuman-crowds-in-unreal-engine), [MetaHumanCrowd API](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/MetaHumanCrowd?application_version=5.8). This project uses UE 5.9; inspect its installed plugin headers when APIs differ.

## Later diagnostic findings

The character did render in a visible unlit PIE viewport, but initially appeared without clothing. The clothing conversion used source LODs 1–3 while the custom garment assets have only LOD0. The Collection was rebuilt using source LOD0 for actor/instanced body and clothing, and the three garments now appear in the instance's assembly output and in PIE. The visual result remains a prototype: the unlit diagnostic shows white-looking heads, missing groom cards, and apparent clothing/boot misalignment. The groom build log says its cards material could not load. Unlit visualization cannot establish whether the head's lit skin material works. Near actor representation still has the null-instance problem noted above.

The pipeline successfully baked `Idle` and `Walk` from the hero sequences into the Collection, and the isolated entity config was given a horizontal test velocity. Separate screenshots show agents changing position, but that is not proof of walking animation, natural navigation or avoidance.

One diagnostic capture after foregrounding the editor yielded 1,227 frames at a median 8.47 ms and 95th percentile 10.25 ms with 20 instanced entities in the flat test scene. It ended before the intended full duration. The viewport was unlit and the crowd had the visual defects above; this is not a dressed, fully animated crowd benchmark, nor a city-scale capacity measurement. Prior hidden-editor files are background-throttled and should be ignored.

## Foreground diagnostic: 20 and 100 entities

On this machine (Ryzen 7 9700X, RTX 5080 16 GB, UE 5.9 editor), the isolated flat scene was run with unlit rendering and the camera facing the spawn grid. The 20-entity capture was stopped early after about 10.8 seconds of sampled frames; the 100-entity capture ran the full 30 seconds after a 10-second warmup. The crowd has no valid groom cards yet, and clothes show apparent misalignment. The scripts use test-only straight-line movement, not pathfinding. Different numbers of agents remained in view as they moved.

| Entities / ISKM representations | Visible during sampling | Frames | Median frame interval | 95th percentile |
|---|---:|---:|---:|---:|
| 20 / 20 | 18–20 | 1,227 | 8.47 ms | 10.25 ms |
| 100 / 100 | 55–92 | 3,153 | 9.01 ms | 12.46 ms |

The raw frame samples and unlit diagnostic images are in `Measurements/`. The conditions are approximate rather than a controlled performance comparison (different capture duration, moving agents, and a groom-pipeline change between runs). These wall-clock frame intervals do not isolate game-thread/render-thread/GPU timing and are **not a shipping or London-scale capacity estimate**. The full city, diverse completed outfits and hair, collision avoidance, gameplay, and actor/ISKM transitions remain untested.

The groom pipeline was configured with Epic's cards/helmet materials. Although this removed the prior missing-material build error, both groom entries still produced null instanced card meshes; this has not repaired the hair. Earlier confirmed clothing conversion required both the canonical `Outfits` selections and source LOD0 because the custom garments provide no higher source LODs. The generated LOD0 output needs fit and animation alignment work.

## Safe test defaults

The grid's exposed `MaxTestAgents` setting defaults to 500 per test spawner, and may be set from 1 through 5,000. Requests over the chosen limit are capped and logged. These are guardrails for this isolated test generator, not recommended city targets. The saved test entity config is stationary; the temporary randomized-velocity trait used for measurements was removed after testing. `add_test_motion.py` is retained for supervised reproduction only and must not be enabled as production movement: it does not bound travel. A real crowd should use controlled navigation and despawning within streamed areas.

The two groom items now have an assigned Crowd Groom pipeline with cards and helmet parent materials, removing the prior missing-material error. The generated `instanced_grooms` entries still contain null cards meshes, so hair remains broken and needs compatible source hair cards and LOD mapping. The unlit white head appearance has not been diagnosed in a properly lit test. The high-resolution actor path remains disabled in the prototype because the engine actor template logged null-instance Blueprint errors; all active levels use ISKM as a diagnostic workaround.
