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
- **Regrounding (train #18).** Walkers sank 10–18 cm into Gray London roads.
  - Cause: each OSM tile's road section (GL_Road) is a one-sided triangle sheet at 28 cm over the city ground at 10 cm, with no kerb face. The collision is fine: tiles are complex-as-simple, BlockAll (WorldStatic), and the driver capsule (ECC_Vehicle) blocks WorldStatic. But a capsule stepping off the pavement meets the sheet's edge from below and slides under it.
  - Fix, without touching the map: the LOD subsystem traces down (complex, WorldStatic) from each walking driver's capsule centre. When a walkable surface (normal Z > 0.7) is 3–45 cm above the capsule bottom, it lifts the driver onto it.
  - Timing: near walkers (Full and Mid tiers) are checked every frame; the rest every 0.25 s.
  - Skipped: the player, falling or pinned drivers, and seated drivers (collision off).
  - `Crowd.Lod.Reground 0|1` (default 1). `Crowd.LodDump` shows the lift count.
  - **Measured on train #18** (`Saved/CrowdReactions/verify_road_edge.py`, R1 03:57): a walker driven across a kerb, both up and down, stayed 2.1–2.2 cm above the floor, with the reground on or off (0 lifts). The CMC steps up the 18 cm sheet edge normally. In a survey of 25 walkers, 0 capsules were buried.
  - **So the train #17 "10–18 cm sink" came from spawning, not walking.** `SpawnNpc` places the NPC exactly where it is asked (no floor snap). The test scripts (`plain_pie.py`, `verify_npc_armed.py`) spawn at hero z − 90, about 8 cm. At the Lanthorne start, 3–7 m ahead of the hero is road, so those NPCs started under the 28 cm sheet. The ring's lane spawns could do the same where a lane cuts a road corner (0.6% of lane length; 23 of 2,530 points).
  - **Ring lane spawns (train #20)** now stand on the top floor found from 25 cm above the lane point: high enough to reach a road, too low to reach a bench seat.
  - **Corpses (train #20, `Crowd.Lod.RegroundCorpses`, default 1).** Ragdoll bodies have no step-up. A body that slides under a road sheet at a kerb, or starts under one, rests on the ground below it.
    - For 8 s after a walker dies into a ragdoll (whole body simulating, driver capsule off), every 0.1 s, each torso physics body (pelvis, spine_*) is traced down from 50 cm above its centre.
    - If a broad walkable surface lies 1–45 cm above a torso body's centre, all simulating bodies are lifted (teleported) by that amount plus 14 cm, with any downward speed removed. At most 4 lifts per corpse.
    - Why torso only (train #24): the first version tested every body. In the train #23 test (`corpse_kerb_result_c0/c1.json`) it made 9 lifts on 4 corpses but did not reduce the parts under (c0: 5, c1: 6). Those were nearly all feet sinking 3–10 cm into every floor, road middle and pavement alike. The lifts also threw corpses that were already at rest 10–15 cm up at 3–4 s. No torso ended under a sheet in either run, including the body spawned under the road.
    - A collapsed ragdoll (all bodies within 1 cm of one height) is left alone; lifting it would only bounce it. The first corpse test (train #20, 04:30) showed one corpse with all 13 bones at exactly z 0.0, the same as three of npc-unify's. That is npc-unify's ragdoll start, not a sheet problem.
    - "Broad" means what was hit spans more than 5 m both ways (a whole OSM tile), so benches and tables never count. For instanced components, the hit instance's own bounds are used. Gray London's benches, bins and bollards are ISM instances, and their component bounds cover every instance. The walker reground uses the same test.
    - `Crowd.LodDump` shows "corpses 1 (N lifts)". Check: `Saved/CrowdReactions/verify_corpse_kerb.py`.
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

## MedievalLondon: routes and street scenes from the town layout (2026-11-15)

The game map is `/Game/GrayLondon/Maps/MedievalLondon`, a 500 m PCG town. Nothing in its crowd is hand-placed: `Tools/Crowd/build_medieval_crowd.py` reads the town's layout and writes `Content/Crowd/Spots/MedievalLondon.json`. It runs offline in about 3 s and also draws `Saved/CrowdReactions/MedievalLondon_crowd_plan*.png`.

- **Layout source.** It prefers fable-streets' narrowed town, `Saved/MedievalLondon_Narrow_streets.json`: street and alley centre lines with a clear 2.5 m strip, stalls, crates, casks, house boxes, and the lantern posts on the alley mouths.
  - Walls, gates, story markers and the well come from `Saved/FableStreets_measure_before.json`.
  - Without the narrow file it uses the measured instances (`--measure PATH`), or with `--layout` the town script's own `layout()`.
  - Re-run it whenever the town is repacked.
  - On the narrowed town the routes follow those centre lines, resampled every 3 m. Where something stands on a line (a lantern post), the route steps sideways round it in a straight run.
- **Editor check (no PIE, read-only).** `Saved/CrowdReactions/verify_medieval_routes_editor.py` sweeps a walker capsule along every route edge and tests every spot against the town's real collision. Output: `medieval_routes_editor_check.json`.
- **Routes** (`"routes": {"nodes", "edges", "offset_cm"}`): a walking graph along the clear middle of every street, built from the town's street lines (the curved main street, the east-west streets, the cross streets).
  - At every 3 m it finds the free span between houses, stalls, crates, casks, walls and the well, with 45 cm walker clearance. On a narrow street it takes the middle; on open ground it keeps to the street's own line.
  - Two rows cross the market square in front of the stall rows, and a ring goes round the well. Crossing lines are joined once, at their mutually nearest nodes.
  - It keeps the largest connected part, and checks every edge against every obstacle. The first build had 2,101 nodes, 6.3 km, and 0 edges touching an obstacle.
- **Walkers on routes** (`ReflectionsCrowdStrollSubsystem`, train after 12:45):
  - Ring walkers (`Crowd_LaneWalker`) on a map with routes walk legs of 25–65 m along the graph (`Crowd.Stroll.LaneLegMin/Max`). At a junction they mostly go straight on, turn now and then, and are drawn towards their trip's street activity; at a dead end they turn round.
  - They keep `offset_cm` (±30%) to the left of the line, so head-on passes never cross; the local avoidance also passes on the left.
  - The ring spawns them on a route 15–45 m from the hero, unseen and not crowded (`UReflectionsCrowdStrollSubsystem::FindRouteSpawn`). Lanes, then open floor, remain the fallback.
  - Maps without routes (Gray London) are unchanged. The stroll subsystem's `Describe()` and `GetRouteNodeCount()` (Python: `unreal.get_world_subsystem(world, unreal.ReflectionsCrowdStrollSubsystem)`) show the route nodes and who is on a route.
- **Spots** (189 on the first build, all scripted):
  - Each market stall gets a vendor (pinned) behind the counter, or beside it when a house is behind, and two customers in front, facing it.
  - A chat by the well; chats, smokers and a leaner on open ground in the market square.
  - People leaning, smoking or chatting at house fronts, one try about every 20 m of street, at least 18 m apart. A chat at every other cross-street corner, a smoker at the rest.
  - Standing people keep at least 1.1 m (customers 0.8 m) from a route line, and 2.6 m from any story marker.
- **Density pass (15:20; config and data only, the code is frozen after train #24).** The aim is busy near the camera, without many more full MetaHumans.
  - **Pinned spots:** one spot in three of each kind spawns its own people (`PIN_EVERY = 3` in the generator). Pinned chats are pairs and pinned shoppers come alone. On the saved town that's 55 of 159 spots.
  - **Kept clear of npc-lives:** the 159 spots keep 2.5 m from npc-lives' 1,092 points (doors, stalls, gathering places with their radius).
  - **Config (`Config/DefaultEngine.ini` `[ConsoleVariables]`):**
    - `Crowd.Ring.Count=20`; walkers spawn 9–30 m from the player (`MinDistance 900`, `MaxDistance 3000`) and are recycled 40 m behind (`RecycleDistance 4000`);
    - spot scenes switch on within 30 m (`Crowd.Spots.ActivateDistance 3000`, `DeactivateDistance 4000`), with `MaxPinned=8`;
    - walking speeds 115–205 cm/s, so a few hurry; `PairShare=0.4`;
    - LOD: full rate within 12 m, 20 Hz to 28 m, 10 Hz beyond, 4 Hz when not seen.
  - **Budget:** about 28 people near the player instead of 18. Most are past 12 m or out of sight in the narrow streets, at reduced animation rates.
  - **PIE check:** `Saved/CrowdReactions/verify_medieval_crowd.py` applies these lines at runtime, so it shows the tuning without an editor restart. It also takes a "busy lane" picture.
- **Only when the hero is near:**
  - Spots activate within 60 m (`Crowd.Spots.ActivateDistance`). Pinned occupants are capped at 6 (`Crowd.Spots.MaxPinned`).
  - The chat director starts a conversation only near the hero, and fades it out when the hero walks away. npc-dialogue's 12:40 hooks in `ReflectionsCrowdChatSubsystem.cpp` (CanStart, Tick, PlayLine) start it within 13 m, end it past 18 m, and play at most 3 ambient lines at once. Keep those hooks when editing that file.
  - Out of earshot, a chat group still shows its ring and gestures, without voices.
- **Shared with npc-lives:**
  - npc-lives owns the stall vendors (named NPCs at work), homes' door points and its gathering place, and publishes them in `Content/Crowd/Spots/MedievalLondon_Lives.json`.
  - The generator keeps every street scene 2.5 m clear of those points. The exception is stall customers, who face a Lives vendor across the counter.
  - It places no vendor spots unless run with `--stall-vendors`.

## Gray London (from train #14)

The old maps (`Lvl_HeroSampleCrowd`, `Lvl_MockCity`, the Mass crowd level) were deleted. `/Game/GrayLondon/Maps/GrayLondon_Geodata` is the only map: one London, one side, no world jump.
- The ring crowd below now targets it (`Crowd.Ring.Maps` = `GrayLondon_Geodata`). It waits for world-jump's CitySidewalk lanes along the Tower district's pavements, and logs `no ZoneGraph lanes` once until they exist.
- With one side, every walker wears the red (Giltside) looks.
- The Mass city crowd has no host map by default, so it is dormant everywhere.
- Test: `Saved/CrowdReactions/verify_ring.py`. It travels to Gray London; the walk-away step replaces the world-jump step.

## Bustling Gray London (train #14)

The plan, by the orchestrator: `reports/Bustling London street crowds.md`. Crowd-react leads it.

- **Walkers without lanes.** Gray London has no ZoneGraph lanes yet and no navmesh. Without lanes, the ring places walkers on open street floor 15–45 m from the hero. A spot must pass three checks: the floor is within ±4 m of the hero's level; it is outdoors (the first hit from 30 m up is that same floor); and a standing person fits. The walkers stroll 4–14 m around their spawn point. Lanes are used whenever they exist; `Crowd.Ring.LaneFree 0` turns this off.
- **Pre-warm.** The initial fill spawns 4 walkers per 0.5 s (`Crowd.Ring.PrewarmPerCheck`), so the street is full about 3 s after map start, behind the intro. Count stays 12.
- **Street scenes ("scenario spots"), v1.** `Source/reflections/Crowd/ReflectionsCrowdSpotSubsystem`. The list per map is `Content/Crowd/Spots/<map>.json`. Gray London has 22 spots on the hero route: chat rings, shop windows, and two pinned vendors.
  - **Claimable spots** (chat, window). A calm ring walker within 12 m may stop. It leaves stroll through `NPC_NoStroll`, walks to the slot, faces in, and stands 20–45 s with relaxed idle-break clips on the hidden walker (DefaultSlot), then walks on.
  - **Pinned spots** (vendors). They spawn their own occupant out of sight while the hero is within 60 m. The occupant is tagged `NoVillain` and removed beyond 80 m once unseen; at most `Crowd.Spots.MaxPinned` (6) are alive.
  - **Chat rings.** With two or more people, the chat director plays a conversation for the spot's place.
  - **Slot safety.** Slots are weak references re-checked every 0.25 s. Any reaction, death, conversion or recycle frees the slot and gives the body back to the NPC system.
  - **Placement.** Spots snap to open outdoor street floor within 4 m at runtime, or are skipped (logged). JSON fields: `name`, `kind` (chat / window / vendor), `slots`, `x`, `y`, `z` (UE cm; x = east_m × 100, y = north_m × 100), `yaw`, `place`, `pinned`.
  - **Packaging** must stage `Content/Crowd/Spots` (`+DirectoriesToAlwaysStageAsUFS`).
  - **v2 (train #15): sitting and street activities**, built on npc-unify's scene API (`BeginNpcScene`, `PlayNpcSceneClip`, `EndNpcScene`, `OnNpcSceneEnded`). There are 39 spots on Gray London: 13 chat, 7 window, 2 vendor, 7 bench, 6 lean and 4 smoke.
    - **bench:** seats 1–2 people on the map's own bench (`GrayLondonBench` or a shelter bench), found within 15 m of the spot. They face away from the backrest (the higher side), and their capsule collision is off while seated. They sit with the Game Animation Sample bench idle and leave through its stand-up clip. `Crowd.Spots.SeatForward` tunes how far forward they sit.
    - **lean:** finds a wall within 2.5 m at shoulder height and stands 40 cm off it, wall on the left, with `AS_Street_Wall_Lean_Walker`.
    - **smoke:** `AS_Street_Pipe_Smoke_Walker`, with the right hand closed round a bowl. There is no pipe prop yet (Codex).
    - Chat-ring people gesture (`AS_Street_Chat_Gesture_Walker`), vendors wave and call (`AS_Street_Vendor_Call_Walker`), and the rest play relaxed idle breaks.
    - Six pinned spots (two vendors, two benches, a leaner and a smoker by the inn) keep someone there; at most 6 such people are alive at once. The target is at least 30% of visible people doing something other than walking.
  - **Carriers (ring, train #15).** `Crowd.Ring.CarryChance` (30%) of new walkers carry goods: `AS_Street_Carry_Hold_Walker`, additive over the walk, plus a prop held at waist height. Carrying starts only when `Crowd.Ring.CarryProp` names a mesh; no Codex basket or crate exists yet. The pose and prop are dropped while frightened.
  - **Not built yet:** sitting on steps and low walls; the pipe and basket props.
- **Not verified yet** on Gray London. `Saved/CrowdReactions/verify_ring.py` now also reports the spots.
- **Lanes for Gray London, computed offline (01:20).** A trace survey in the editor found no pavement, because Gray London's OSM tiles were not loaded there (World Partition), so every trace hit the always-loaded `City ground` cylinder at 10 cm. The map's layers:
  - roads are each tile's `GL_Road` triangles (flat, 28 cm);
  - pavement is the city ground (10 cm) between a road and the building footprints (`GL_Roof`);
  - facades and roofs collide.
  `Tools/Crowd/lanes_from_tile.py` reads an exported tile GLB (Codex's reader, verified axes). It takes the band 1–3 m outside every road edge, at least 1 m clear of buildings, thins it to centrelines, joins the pieces, and puts points every 6 m at 13 cm. For `Tile_p03_p00` round the intro the result is 87 lanes (about 3.2 km): `Tools/Crowd/graylondon_lanes.json`, previewed in `graylondon_lanes_preview.png`. **Placed (01:37):** `Tools/Crowd/build_route_lanes.py` merges the route boxes over tiles `p03_p00`, `p04_p00` and `p03_p01` into 270 shapes (2,530 points). The ZoneGraph build gives 540 lanes and 22.3 km; within 50 m there are 33 lanes at the intro, 36 at Tower Hill and 15 at Leadenhall. Not yet checked in PIE on the full set. `Tools/Crowd/crowd_lanes.py` stage `json` spawns them, `build` builds the ZoneGraph, and `save` saves only our packages. Tower Hill east of 3500 m and Leadenhall need tiles `p04_p00` and `p03_p01` exported first.
- **Partial lanes.** The ring uses a lane point near the hero where it can, and open street floor anywhere else.

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
