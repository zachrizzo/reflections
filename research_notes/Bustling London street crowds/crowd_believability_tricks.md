# Crowd believability tricks: making open-world streets feel busy on a budget

Scope: proven design and technical tricks (beyond raw NPC count) for making a UE5.9 open-world London feel busy, ranked by impact versus effort, for a small team about 18 hours from a jam deadline and a later commercial release. Context: story-driven action game with spellcasting, NPCs that already flee, scream and die, and expensive MetaHuman foreground characters.

Source-quality note: GDC Vault slides and videos for the key crowd talks (AC Unity, Hitman: Absolution, Watch Dogs: Legion Census) are behind a membership login. The details below come from session abstracts, a detailed Japanese write-up of the AC Unity talk (GAME Watch), a Game Developer analysis of Hitman's AI, Epic's own documentation, and audio-team write-ups. Where only a headline or search snippet was available, it is flagged.

---

## 1. Density illusions: rings, frustum-aware spawning, hero routes, density by area/time

### Takeaway
No shipped game simulates "a busy city" uniformly. They put a small number of expensive, fully featured NPCs right around the player (AC Unity capped these at 40 within 12 m), surround them with progressively dumber and cheaper tiers, and recycle (pool) agents as the player moves. Density is designer-authored per area. Lesson from AC Syndicate's London: a few dense clusters of "a few dozen" people in the right places beat an evenly spread population, but too sparse reads as "stagnant and empty". Lesson from Cyberpunk 2077: despawning people the player can see, or as soon as they turn around, is noticed immediately.

### Cited Findings
**AC Unity tiered "bulk" crowd (GDC 2015, "Massive Crowd on Assassin's Creed Unity: AI Recycling", Francois Cournoyer)**
- The talk presents "a new technique of AI level of detail" for "thousands of replicated, persistent, interactive NPCs". Press coverage says the core is a pooling system that swaps low-resolution NPCs for high-resolution ones without the player noticing. — [GDC Vault abstract](https://www.gdcvault.com/play/1022141/Massive-Crowd-on-Assassin-s)
- Before this system, AnvilNext was limited to about 100 NPCs at once, about 20 voiced "citizen" NPCs, about 4 citizen-level NPCs near the player, and had no crowd system. — [GAME Watch write-up of the talk (Japanese)](https://game.watch.impress.co.jp/docs/news/20150307_691715.html)
- Three distance tiers (from the GAME Watch write-up of the talk):
  - **Low-res bulk, 40 m and beyond:** about 1,700 to 2,000 polygons, 11 bones. Not autonomous, basic reactions only. Uses a custom fast animation system and hands do not move. Follows navmesh paths without deviating from predefined routes. No Havok physics; pushed aside on contact without reacting. Uses a 2D spatial partition map for queries.
  - **Puppet bulk, 12 to 40 m:** autonomous but with very limited functions.
  - **Autonomous, within 12 m:** up to about 20,000 polygons, about 300 bones, fully featured. Capped at 40 NPCs.
  — [GAME Watch](https://game.watch.impress.co.jp/docs/news/20150307_691715.html)
- CPU cost per NPC: under 25 µs (low-res), under 150 µs (puppet), 500 µs to 5 ms (autonomous). Average cost about 1/100 of the previous system. — [GAME Watch](https://game.watch.impress.co.jp/docs/news/20150307_691715.html)
- "Shepherd" NPCs carry the AI data and lead a group of bulk NPCs. Designers set bulk density, automatic spawn points, placement at specific locations, and Shepherd behaviour scripts in a level-design tool. — [GAME Watch](https://game.watch.impress.co.jp/docs/news/20150307_691715.html)
- Stated lessons: apply LOD to AI logic, not just rendering; concentrate compute on what the player sees and touches up close; stack many simple techniques; give designers density and spawn tools. — [GAME Watch](https://game.watch.impress.co.jp/docs/news/20150307_691715.html)
- One write-up of the talk says AI logic was scaled by distance, but a separate slide deck on crowd interaction says decision and behaviour layers had no LOD, with LOD applied mainly to animation. The two sources conflict. — [GAME Watch](https://game.watch.impress.co.jp/docs/news/20150307_691715.html); contradicted by [SlideShare deck](https://www.slideshare.net/slideshow/assassins-creed-i/253244281) (deck not read in full)
- Headline crowd numbers for Unity conflict between sources: "can support crowds of 30,000" (GameSpot headline), and a reported 5,000 AI in some missions and 10,000 for the King's beheading (team quote via Game Informer, seen only as a search snippet). Treat these as marketing or peak-event numbers, not normal street density. — [GameSpot](https://www.gamespot.com/articles/assassins-creed-unity-can-support-crowds-of-30-000/1100-6421542/); [Game Informer](https://gameinformer.com/b/features/archive/2014/08/25/watch-the-largest-crowd-assembled-in-assassins-creed-unity.aspx)

**AC Syndicate (Victorian London) cut density from Unity**
- Digital Foundry's Face-Off: compared with Unity, Syndicate shows "the culling of hundreds of NPCs, now down to groups of few dozen citizens in various locations across the city." — [Eurogamer / Digital Foundry Face-Off (retrieved via mirror)](https://venvegame.netlify.app/host-https-www.eurogamer.net/digitalfoundry-2015-assassins-creed-syndicate-face-off)
- Ubisoft scaled NPC counts back after Unity's density strained consoles (press interpretation, not an official Ubisoft statement with numbers). — [eTeknix](https://eteknix.com/assassins-creed-unity-syndicate-playstation-4-graphics-compared/amp)
- Reception split: PCWorld called the streets stagnant and empty by comparison; Stevivor said environments were more spread out but still lively. — [PCWorld review](https://www.pcworld.com/article/3008718/assassins-creed-syndicate-review-one-of-the-best-but-its-still-just-assassins-creed.html); [Stevivor](https://stevivor.com/?p=95681)

**Hitman: tight per-zone caps**
- Hitman: Absolution: 1,200 crowd characters per zone, 500 maximum on screen, crowd AI simulated every frame with asynchronous animation, and a "possession" system that upgrades a crowd agent to a full NPC. — [Intel/IOI Hitman 2 presentation PDF (seen via search snippet; file too large to fetch)](https://www.intel.com/content/dam/develop/external/us/en/documents/06-create-a-scalable-and-destructible-world-in-hitman2-807276.pdf)
- Absolution achieved its 1,200-character crowds "while still running at 30fps on current-gen consoles" (PS3/360). — [MCV/Develop](https://www.mcvuk.com/development/gdc-hitman-dev-to-showcase-crowd-technology)
- Hitman (2016) runs "over 1000 crowd NPCs" next to about 300 behaviour-tree NPCs per level. Hitman 2 (2018) raised the crowd to over 2,000 NPCs (Miami racetrack). — [Game Developer, "The AI of Hitman (2016)"](https://gamedeveloper.com/design/the-ai-of-hitman-2016-)

**Matrix Awakens / City Sample (UE5, Mass)**
- 35,000 simulated MetaHuman pedestrians in the demo's stats. — [80.lv](https://80.lv/articles/city-sample-from-the-matrix-demo-released-for-ue5)
- Nearby crowd characters are full rigged, animated MetaHumans. Distant ones are "custom generated, vertex-animated Static Meshes generated from the MetaHumans". Crowd and traffic spawn points are generated along ZoneGraph lanes from Houdini data. An in-game World Settings menu exposes a Crowd density setting. — [Epic City Sample docs](https://dev.epicgames.com/documentation/unreal-engine/city-sample-project-unreal-engine-demonstration)
- Epic forum guidance on City Sample: transition between full actor and static-mesh entities as characters get closer to or further from the screen. — [Unreal forums (via search snippet)](https://forums.unrealengine.com/t/city-sample-crowds-for-ue-5-1/882197)
- Mass LOD: per LOD level you set the distance at which it applies and a maximum entity count, and the LOD system also computes visibility (frustum), not just distance. Representation types per LOD include a high-res Actor and an Instanced Static Mesh. — [Epic, Overview of Mass Gameplay](https://dev.epicgames.com/documentation/unreal-engine/overview-of-mass-gameplay-in-unreal-engine)

**MetaHuman Crowds (Epic, Experimental)**
- Experimental; Epic advises "use caution when shipping with it." Distant characters use the Instanced Skinned Mesh Component, which skips the post-process Anim Blueprint (no correctives). Crowd hair is converted from grooms to card meshes, with no strands and no hair physics. — [Epic, MetaHuman Crowds overview](https://dev.epicgames.com/documentation/metahuman/metahuman-crowds-in-unreal-engine)
- Example LOD caps: 10 full-quality actors up close with hundreds of instanced characters at a distance. Controls: actor-to-instanced switch distance, maximum render distance, maximum count per LOD, and animation "timing variety" for distant characters to avoid lockstep. Spawning uses a MetaHumanMassSpawner with a Count per entity type, an EQS-based spawn generator, and a "Spawning Count Scale" multiplier settable from a scalability CVar. — [Epic, Create MetaHuman Crowds](https://dev.epicgames.com/documentation/metahuman/create-metahuman-crowds-in-unreal-engine)
- The docs page links use application_version=5.8; no introduction version is stated. — [Epic, Create MetaHuman Crowds](https://dev.epicgames.com/documentation/metahuman/create-metahuman-crowds-in-unreal-engine)

**Cyberpunk 2077 (anecdotal, mod and community sources only)**
- A patch 1.3 bug made crowd NPCs "instantly despawn when V turns around, leaving Night City feeling empty", and a separate bug made fleeing or panicking NPCs despawn rapidly. Modders shipped fixes. — [Crowd Despawn Fix mod listing](https://www.gamepressure.com/download/cyberpunk-2077-crowd-despawn-fix-v10-mod/ze13a27); [Nexus Mods](https://nexusmods.com/cyberpunk2077/mods/526)
- One mod's "fast" preset despawns NPCs 5 s after leaving view unless within 15 m, and otherwise after 30 s out of sight. These are mod values, not CDPR's defaults. — [Nexus Mods (via search snippet)](https://nexusmods.com/cyberpunk2077/mods/526)
- Players report that turning away or moving far enough re-rolls the visible NPC set, and that the spawn cap can remove an NPC in front of the camera. — [Steam discussion](https://steamcommunity.com/app/1091500/discussions/0/4635988522932735208)
- Crowd Density is a user setting, moved to the Graphics tab in 2.0. — [Nexus Mods post (via search snippet)](https://www.nexusmods.com/cyberpunk2077/mods/6457?tab=posts)

### Inferences
- The AC Unity numbers give a usable budget shape: fully featured NPCs only within about 12 m and capped at a few dozen; a cheaper puppet ring to about 40 m; beyond that, animation-only filler. For this project, MetaHumans should be the "autonomous within 12 m" tier only, about 10 to 40 of them (Epic's MetaHuman Crowds example uses 10), and everything farther should be cheaper.
- Spawn and despawn should happen only where the player cannot see it: outside the frustum (Mass LOD already computes visibility), behind occluders, at doorways and street corners, or beyond the far tier. Never despawn inside the view or immediately on camera turn (the Cyberpunk 1.3 regression shows players notice).
- Syndicate's London suggests that, on a budget, "clusters on hero streets plus quiet side streets" is the shipped answer. Contrast between busy and quiet also makes the busy street read as busier. The risk is a city that feels empty overall, so the hero route must be dense.
- Density knobs should be a single scalar per area (as in City Sample's Crowd setting and MetaHuman Crowds' Spawning Count Scale), so the jam build can be tuned for performance without re-authoring.

### Gaps
- No primary source found for GTA V's ambient population system (spawn radii, density zones, scenario points). Only community and forum material exists, which I did not treat as reliable.
- No developer source for Cyberpunk 2077's vanilla despawn timers or radii.
- I could not see the AC Unity slides, so the exact handoff mechanism between tiers (how state transfers when a low-res NPC becomes autonomous) is undocumented here.
- No source found on time-of-day crowd density curves in a shipped game.

---

## 2. Ambient behaviours that sell life cheaply (Smart Objects, idles, conversation clusters, vendors, queues, doors, leaning, looking at the player)

### Takeaway
Stationary, designer-placed vignettes (people looking at something, standing in a group shape, waiting at a slot) are the cheapest life you can add: no pathing, little avoidance, and they read as "people doing things". UE5 provides Smart Objects (claim, use, release slots) driven from StateTree, including from Mass, but Epic's own City Sample did not ship Smart Objects in the city, and there are known Mass and Smart Object pitfalls, notably claims leaking when an agent dies, which matters here because NPCs die.

### Cited Findings
- Hitman crowd agents can walk, pause and "acknowledge things nearby", and designers can place groups that look at a point of interest or hold a shape. — [Game Developer, "The AI of Hitman (2016)"](https://gamedeveloper.com/design/the-ai-of-hitman-2016-)
- AC Unity designers could place bulk NPCs at specific locations and script Shepherd behaviours in a level-design tool. — [GAME Watch](https://game.watch.impress.co.jp/docs/news/20150307_691715.html)
- AC Unity had a separate GDC postmortem on "Systemic Crowd Events" covering the difficulty of coordinating crowds of hundreds of NPCs for player-facing events. — [GDC Vault abstract](https://www.gdcvault.com/play/1022211/Postmortem-Developing-Systemic-Crowd-Events)
- Smart Objects flow: an agent queries, calls ClaimSmartObject to reserve a slot (no other agent can claim it until released), uses it on arrival, and releases it. — [Epic, Smart Objects overview](https://dev.epicgames.com/documentation/unreal-engine/smart-objects-in-unreal-engine---overview)
- City Sample: Smart Objects "did not ship in the city"; they can be explored in the MassCrowd test map. Crowd behaviour is a StateTree (`CrowdStateTree` in `Content/AI`). — [Epic City Sample docs](https://dev.epicgames.com/documentation/unreal-engine/city-sample-project-unreal-engine-demonstration)
- Mass agents need the Smart Object Mass Behavior Definition in their behaviour definitions to see Smart Objects. A forum user found Find and Claim must be separate StateTree states with "Try Enter" selection, or Claim runs before Find completes. — [Unreal forums](https://forums.unrealengine.com/t/5-6-mass-ai-smart-object-invalid-claim-handle-id/2561118)
- Disabling a Smart Object may not stop the Mass claim and use tasks (forum report, unresolved). Mass also claims with its own user-data type (FSmartObjectMassEntityUserData), which clashes with actor-based Smart Object components. — [Unreal forums](https://forums.unrealengine.com/t/mass-smart-object-tasks-handling-smart-object-disabled/2651656); [Unreal forums](https://forums.unrealengine.com/t/smartobjectcomponent-expects-fsmartobjectactoruserdata-but-mass-uses-fsmartobjectmassentityuserdata/2651672)
- Claims leak when the AI that claimed a slot dies or aborts without releasing (third-party blog, less authoritative). — [Bugnet blog](https://bugnet.io/blog/fix-unreal-smart-objects-claim-not-released)
- MassCrowd includes a StateTree task `FMassCrowdClaimWaitSlotTask` (wait slots, for example at crossings). I could not confirm its exact semantics. — [Epic API docs](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/MassCrowd/FMassCrowdClaimWaitSlotTask)
- Watch Dogs: Legion's Census system "populates the world" and assigns demographic profiles to characters. Gamesradar's headline (body not retrievable) says it simulates "jobs, work schedules, and ... hiccups and mime". — [Ubisoft News, "The tools that built London"](https://news.ubisoft.com/en-us/article/4po3S9Pwp1YcgBmGPmQxAh/watch-dogs-legion-the-tools-that-built-london); [Gamesradar (headline only)](https://www.gamesradar.com/watch-dogs-legion-simulation)
- Spider-Man's pedestrians and NPCs are fully voice acted, yet one critic still called them "window dressing". — [Game Developer, "Making Insomniac's Spider-Man"](https://gamedeveloper.com/design/making-insomniac-s-i-spider-man-i-do-what-a-spider-can); [Giant Bomb user blog (opinion)](https://giantbomb.com/profile/xanadu/blog/spider-mans-citizens-and-the-complete-super-hero-s/118553/)

### Inferences
- For tonight, hand-placed stationary vignettes on the hero route (2 to 4 people in a conversation ring, a vendor plus customer, a short queue at a door, someone leaning on a wall, a group watching a street performer or a posted notice) give the highest life per hour. They need only an idle loop plus a head look-at, and the existing flee/scream/die reactions can be reused when combat starts.
- Doors as spawn and despawn points ("people entering and exiting buildings") hide population churn and look like purposeful behaviour. This is the same trick AC Unity's automatic spawn points and the City Sample lane spawners use, applied to buildings. It is an inference; I found no primary source describing door despawns specifically.
- If Smart Objects are used, every exit path (death, flee, despawn) must release the claim, or benches and slots silently fill up during combat-heavy play.
- Watch Dogs: Legion's schedules are a commercial-release feature, not a jam feature. They need a persistent population, which is the opposite of a pooled crowd.
- "Looking at the player" is the cheapest acknowledgement and is consistent with Hitman's "acknowledge things nearby". It should be rate-limited (only some NPCs, short durations) to avoid an uncanny "everyone stares" effect. That limit is a judgement call, not sourced.

### Gaps
- No sourced numbers for how many ambient vignettes per street a shipped game used.
- No primary source on GTA's scenario points (benches, smoking, phone-use spots), though they are widely discussed by modders.
- Leaning and other wall-contact idles: no source found on how shipped games author or place them.

---

## 3. Group behaviour: pairs and groups, avoidance and flow on pavements, crossing roads

### Takeaway
Real pedestrians mostly walk in groups. A PLoS ONE field study found up to 70% of people in a commercial street moving in groups, walking side by side at low density and in a V shape as density rises. A crowd of solo walkers therefore reads as artificial. Shipped games handle groups cheaply with a leader and followers (AC Unity's Shepherds) and keep flow with simple speed rules (Hitman's preferred and maximum speeds plus a "pending walk" state for congestion).

### Cited Findings
- Moussaïd et al. (2010), PLoS ONE, about 1,500 pedestrian groups filmed in natural conditions: up to 70% of people move in groups. The per-site figures were 55% and 70%, with the 70% from weekend recordings. — [PLoS ONE via RePEc](https://econpapers.repec.org/RePEc:plo:pone00:0010047); [Big Think summary](https://bigthink.com/?p=38454)
- At low density, group members walk side by side in a line perpendicular to the walking direction. As density increases, the line bends forward into a V. The V helps conversation but reduces flow. — [Moussaïd et al. (arXiv mirror)](https://bohrium.dp.tech/paper/arxiv/1502.01375)
- Simulations based on these observations show groups reduce overall traffic efficiency by about 17% compared with isolated walkers. — [ScienceDaily (CNRS release)](https://sciencedaily.com/releases/2010/04/100413072044.htm)
- AC Unity: a Shepherd NPC holds the AI data and leads a group of bulk NPCs. — [GAME Watch](https://game.watch.impress.co.jp/docs/news/20150307_691715.html)
- Hitman crowd agents run a three-state FSM (idle, walking, "pending walk" when congestion blocks movement) and set preferred and maximum speeds to keep the crowd flowing, especially during panic. — [Game Developer, "The AI of Hitman (2016)"](https://gamedeveloper.com/design/the-ai-of-hitman-2016-)
- AC Unity low-res NPCs follow navmesh paths, never deviate from predefined routes, and are pushed aside on contact without reacting. — [GAME Watch](https://game.watch.impress.co.jp/docs/news/20150307_691715.html)
- City Sample crowds move along ZoneGraph lanes (point-by-point corridors with tags) placed on sidewalks; intersections have their own spawners. — [Epic City Sample docs](https://dev.epicgames.com/documentation/unreal-engine/city-sample-project-unreal-engine-demonstration)

### Inferences
- The cheapest group implementation is a leader that paths normally and 1 to 2 followers that hold a lateral offset (side by side), compress to a V or a single file when the pavement narrows, and match the leader's speed. That is effectively AC Unity's Shepherd pattern.
- Splitting a fixed NPC budget into pairs and trios makes a street look busier and more natural without raising the count, because the study shows groups are the norm.
- Fixed lanes or splines along pavements (City Sample ZoneGraph, AC Unity predefined routes) are cheaper and more readable than free navmesh wandering. They also produce the two-directional flow typical of real pavements.
- Distant NPCs do not need collision response at all. AC Unity simply pushes low-res NPCs aside.
- For road crossings, the cheapest approach is crossing only at authored points. MassCrowd's wait-slot task suggests Epic modelled waiting at crossings in the same way, but this is not confirmed.

### Gaps
- I did not retrieve Epic's Mass Avoidance documentation, so its parameters and costs are not covered here.
- No shipped-game source on how pedestrians cross roads or interact with carriages and traffic in a period setting.
- No source quantifying how much grouping increases perceived density for players (the study measures real pedestrians, not perception).

---

## 4. Audio and VFX tricks (walla beds that scale with density, distant chatter, footsteps, birds, traffic and carriages, steam and smoke, window lights)

### Takeaway
Audio is the highest-leverage, lowest-cost "busy street" trick. Shipped games drive layered crowd beds from a live count of nearby NPCs, with separate small-crowd and large-crowd recordings, because turning up the volume does not make a crowd sound bigger. Walla stands in for distant NPCs, and close pedestrians switch to individual lines. A panic layer replaces the calm layer when violence starts.

### Cited Findings
**Prototype (Radical Entertainment, Scott Morgan, Sound Director)**
- Three tiers: a background quad bed of distant recordings; a midground of grouped pedestrian, vehicle and infected sounds built with a custom "walla generator"; and a foreground of single-object sounds (dialogue, honks, engines) driven by AI state. — [Game Developer, "Dynamic Game Audio Ambience: Bringing Prototype's New York City to Life"](https://www.gamedeveloper.com/audio/dynamic-game-audio-ambience-bringing-i-prototype-i-s-new-york-city-to-life)
- With a few pedestrians, each reacts individually. Around 10 people fades up the first low-density crowd layer, and more people fade in a denser layer. Traffic works the same way: an idle traffic layer fades in once car counts are high, and a traffic panic layer fades in when cars panic. — [Game Developer, Prototype audio](https://www.gamedeveloper.com/audio/dynamic-game-audio-ambience-bringing-i-prototype-i-s-new-york-city-to-life)
- Two crowd sizes were needed because "volume alone does not represent density very well". A 40-person crowd at a quarter of the amplitude still does not sound like 10 people. — [Game Developer, Prototype audio](https://www.gamedeveloper.com/audio/dynamic-game-audio-ambience-bringing-i-prototype-i-s-new-york-city-to-life)
- The walla generator randomises gap timing, pitch and volume within ranges and draws from about 400 reaction files. Per-type voice maximums reserved voices for combat and powers. Crossfades are position-based, not trigger-based. Raycasts stop crowds being heard through walls, and inputs are smoothed because the system reacts instantly. — [Game Developer, Prototype audio](https://www.gamedeveloper.com/audio/dynamic-game-audio-ambience-bringing-i-prototype-i-s-new-york-city-to-life)
- Source material: about 20 hours of raw recordings over about a week and a half in New York. — [Game Developer, Prototype audio](https://www.gamedeveloper.com/audio/dynamic-game-audio-ambience-bringing-i-prototype-i-s-new-york-city-to-life)

**Other implementations**
- CRI tutorial: separate low, medium and high crowd loops for about 2 to 4, 4 to 8, and 10+ people, crossfaded by a parameter (AISAC), with a cue limit to cap voices. — [CRIWARE blog, "Crowd system"](https://blog.criware.com/index.php/2023/05/08/crowd-system/)
- The Outer Worlds (Obsidian): distance-based walla audible at about 40 to 60 m and ambient objects at about 60 to 80 m. Closer than that, animation-synced audio takes over. Voice limiting and virtual voices control the count, and walla tells players where creatures are and roughly how many. (From a search summary of the Audiokinetic blog; page not read in full.) — [Audiokinetic, "The Sound of The Outer Worlds, part 1"](https://audiokinetic.com/the-sound-of-the-outer-worlds-part-1)
- Marvel's Spider-Man 2: distant crowd voices were captured with walla groups that walked in circles while chattering, shoeless to avoid foot noise, in multiple languages to reflect New York. Approaching pedestrians switch from walla to solo lines or simple conversations. Dialogue chunks are blended modularly "like prompt cards" to create new ambient dialogue. Primary source is senior audio designer Jerry Berlongieri's social-media video, relayed by press. — [Gamepur](https://gamepur.com/?p=565268); [Dot Esports](https://vip-develop.dotesports.com/?p=1000019)
- City Sample "Soundscape" (experimental): a Mass processor tracks idling MetaHumans and NPC vehicles, and those positions drive ambient honking and MetaHuman shouts and vocalisations. Most other ambience spawns from ColorPoint data through the World Audio Data System. — [Epic City Sample docs](https://dev.epicgames.com/documentation/unreal-engine/city-sample-project-unreal-engine-demonstration)
- Planet Coaster added extra crowd layers for close-up camera work, where a base crowd texture alone was not enough. — [Audiokinetic, Planet Coaster crowd audio part 3](https://audiokinetic.com/en/planet-coaster-crowd-audio-additional-layers-part-3)

### Inferences
- Tonight's version: count NPCs within a radius of the listener (or per street volume) every half-second or so and crossfade 2 to 3 walla loops (small group, medium crowd, dense crowd), plus a distant city bed that is always on. Swap to a panic or screaming layer when combat starts, and duck back as the street empties. This mirrors Prototype and CRI and needs no new NPCs.
- Walla also "fills" streets with people the player never sees: a dense walla layer at a street mouth implies a crowd around the corner. This is an inference from Spider-Man 2's distant walla and Outer Worlds' 40 to 60 m walla range.
- London-specific layers (inference, unsourced): horse hooves and iron-rimmed carriage wheels on cobbles, distant church bells, street-seller cries, dogs, pigeons and gulls near the river, and rain on awnings. These are cheap one-shot or loop emitters and sell a period London more than extra bodies would.
- VFX (inference, unsourced): chimney and vent steam, coal smoke drifting across street lights, lit and occasionally changing window emissives, and fog that hides the far end of streets (which also hides the cheap far crowd tier). These are standard environment-art tricks, but I found no crowd-specific source quantifying them.

### Gaps
- No primary source on window-light, steam or smoke tricks used specifically to imply population.
- No source on footstep handling at crowd scale (for example, aggregated crowd footstep beds versus per-NPC footsteps).
- The Outer Worlds and Spider-Man 2 details come from search summaries and press relays; the full articles and the original video were not read.

---

## 5. Reaction systems at scale: cheap mass flee, panic propagation, and recovery

### Takeaway
Hitman is the best-documented model. Violence emits "behaviour zones" (a radius and angle around the event) with tiered responses: prone in the line of fire, panic nearby, alert further out. Panic spreads as the player moves. Fleeing uses precomputed per-exit flow fields on a coarse 2D grid instead of per-agent navmesh queries, and agents can switch exits at bottlenecks. Recovery is the weak spot: in Hitman, crowds reportedly never calm down once triggered. In UE5 Mass, the building blocks are signals (including delayed signals for staggering) that wake StateTree only when needed.

### Cited Findings
- Hitman behaviour zones: events emit zones that pulse within a radius and angle of the source. Responses include looking at a point of interest, avoiding the source, being alerted, being scared, or going prone. — [Game Developer, "The AI of Hitman (2016)"](https://gamedeveloper.com/design/the-ai-of-hitman-2016-)
- Example: aiming a gun at a bystander creates three zones; those in the line of fire go prone, those nearby panic, and those further out become alert. When in several zones, an agent takes the response that most affects its mood. Designers tune zones per level (a fight in a fashion-week bar is treated more negatively than trouble in Absolution's Vixen Club). — [Game Developer, "The AI of Hitman (2016)"](https://gamedeveloper.com/design/the-ai-of-hitman-2016-)
- Panic is cumulative: it spreads outward as the player moves, pushing more agents to react. — [Game Developer, "The AI of Hitman (2016)"](https://gamedeveloper.com/design/the-ai-of-hitman-2016-)
- Panic flows: each exit has a flow field built from the shortest path from every grid cell (a Dijkstra variant). In an emergency, agents pick the best exit flow and can switch when a bottleneck forms or the player blocks an exit. A 2D grid over the navmesh marks cells as walkable, avoid, exit, or cordoned off after a panic, so hundreds of agents never query the navmesh repeatedly. — [Game Developer, "The AI of Hitman (2016)"](https://gamedeveloper.com/design/the-ai-of-hitman-2016-)
- Recovery: the article describes no calm-down mechanism, and the author says crowds "never calm down once you set them off". — [Game Developer, "The AI of Hitman (2016)"](https://gamedeveloper.com/design/the-ai-of-hitman-2016-)
- Any Hitman crowd member can be "possessed" by full behaviour-tree AI when the situation needs a fully responsive character. — [Game Developer, "The AI of Hitman (2016)"](https://gamedeveloper.com/design/the-ai-of-hitman-2016-)
- AC Unity low-res NPCs have only "basic reactions" and do not react to collisions; only the inner tiers react richly. — [GAME Watch](https://game.watch.impress.co.jp/docs/news/20150307_691715.html)
- UE5 Mass signals: UMassSignalSubsystem provides SignalEntities (signal many entities) and DelaySignalEntities (signal them after a set number of seconds), with deferred variants for processors. — [Epic API, UMassSignalSubsystem](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/MassSignals/UMassSignalSubsystem); [x157 Mass Signals notes](https://x157.github.io/UE5/Mass/Signals)
- The Mass StateTree only ticks for an entity when the StateTree processor is signalled, so behaviour costs nothing until a signal arrives. — [Unreal forums](https://forums.unrealengine.com/t/statetree-task-only-ticking-once/747998); [Epic API, UMassStateTreeSubsystem](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/MassAIBehavior/UMassStateTreeSubsystem)
- I found no complete, published Mass panic or flee sample; a Mass implementation would be original work. — [Unreal forums, Understanding MassAI & Mass Crowd](https://forums.unrealengine.com/t/understanding-massai-mass-crowd/1623463)
- Cyberpunk 2077 patch 1.3 made fleeing or panicking crowd NPCs despawn rapidly, which modders "fixed" because it emptied the city (community source). — [Gamepressure mod listing](https://www.gamepressure.com/download/cyberpunk-2077-crowd-despawn-fix-v10-mod/ze13a27)
- Prototype's audio: individual panic sounds for a few NPCs, and group panic layers once enough NPCs panic. — [Game Developer, Prototype audio](https://www.gamedeveloper.com/audio/dynamic-game-audio-ambience-bringing-i-prototype-i-s-new-york-city-to-life)

### Inferences
- Cheapest robust design for this project: on a spell impact, kill or scream event, emit 2 to 3 concentric zones (cower or prone, flee, alert or look). Apply the inner zone immediately and delay outer rings by distance (for example 0.1 to 0.3 s per ring), so panic visibly ripples outward instead of every NPC reacting on the same frame. Mass's DelaySignalEntities supports this directly; in actor-land, a staggered timer does the same. Delay values are a suggestion, not sourced.
- Flee toward authored exits that double as despawn points (doorways, alleys, street ends out of view). That gives a readable reaction, frees budget, and creates a natural "street emptied" moment, as long as the despawn happens out of view (the Cyberpunk lesson).
- Recovery is where a story game can beat Hitman: after a cooldown with no new violence, respawn a thinner population from doors and street ends, with cautious idles (looking toward the fight site, gathered in small groups), and ramp walla back up. This recovery loop is an inference; I found no shipped-game source documenting it.
- A coarse grid or flow field per exit (Hitman) is the scalable post-jam version. For the jam, picking the nearest authored exit point that is not in the direction of the threat is probably enough.
- Upgrading a cheap crowd agent to a full MetaHuman or full NPC only when the player targets or engages it (Hitman's possession, AC Unity's tier swap) keeps MetaHuman costs bounded.

### Gaps
- No source on how AC Unity's crowd reacted to violence at scale (the "crowd reaction stimuli" system is mentioned in coverage but not detailed in anything I could read).
- No source on GTA or Spider-Man crowd panic propagation or recovery timings.
- No published cost numbers for Mass-based panic at scale.

---

## 6. How shipped games did it: numbers, techniques, lessons (with London relevance)

### Takeaway
The common pattern across AC Unity, Hitman, the Matrix Awakens and MetaHuman Crowds is a handful of expensive characters near the camera (about 10 to 40), hundreds of cheap animated instances beyond that, distance and visibility LOD on both rendering and AI, designer-placed density, and pooling. The two London-set games are instructive: Syndicate cut Unity's crowds to "groups of a few dozen" for performance and was criticised as emptier, while Watch Dogs: Legion invested in per-person identity (Census) rather than raw density.

### Cited Findings
| Game | Crowd numbers | Key technique | Source |
|---|---|---|---|
| AC Unity (2014, Paris) | Autonomous NPCs capped at 40 within 12 m; puppets at 12 to 40 m; low-res beyond 40 m. Previous engine limit about 100 NPCs. Marketing peaks of 5,000 to 30,000 (conflicting). | 3-tier "bulk" LOD on AI, animation and rendering; Shepherds lead groups; pooling and recycling; designer density tools | [GAME Watch](https://game.watch.impress.co.jp/docs/news/20150307_691715.html); [GDC Vault](https://www.gdcvault.com/play/1022141/Massive-Crowd-on-Assassin-s); [GameSpot](https://www.gamespot.com/articles/assassins-creed-unity-can-support-crowds-of-30-000/1100-6421542/) |
| AC Syndicate (2015, London) | "Groups of few dozen citizens in various locations" instead of hundreds | Clustered density for performance; perceived as emptier | [Digital Foundry Face-Off (mirror)](https://venvegame.netlify.app/host-https-www.eurogamer.net/digitalfoundry-2015-assassins-creed-syndicate-face-off); [PCWorld](https://www.pcworld.com/article/3008718/assassins-creed-syndicate-review-one-of-the-best-but-its-still-just-assassins-creed.html) |
| Hitman: Absolution (2012) | 1,200 per zone, 500 max on screen, 30 fps on PS3/360 | Dummy crowd FSM, behaviour zones, per-exit panic flow fields, possession to full AI | [MCV/Develop](https://www.mcvuk.com/development/gdc-hitman-dev-to-showcase-crowd-technology); [Intel PDF (snippet)](https://www.intel.com/content/dam/develop/external/us/en/documents/06-create-a-scalable-and-destructible-world-in-hitman2-807276.pdf); [Game Developer](https://gamedeveloper.com/design/the-ai-of-hitman-2016-) |
| Hitman (2016) / Hitman 2 (2018) | 1,000+ crowd plus about 300 full NPCs; 2,000+ crowd in Miami | Same architecture, optimised | [Game Developer](https://gamedeveloper.com/design/the-ai-of-hitman-2016-) |
| Matrix Awakens / City Sample (UE5) | 35,000 simulated pedestrians; "hundreds" visible from the drone | Mass + ZoneGraph lanes + StateTree; near full MetaHumans, far vertex-animated static meshes; crowd density setting; Soundscape tied to Mass | [80.lv](https://80.lv/articles/city-sample-from-the-matrix-demo-released-for-ue5); [Epic docs](https://dev.epicgames.com/documentation/unreal-engine/city-sample-project-unreal-engine-demonstration) |
| MetaHuman Crowds (UE 5.8-era docs, Experimental) | Example: 10 full actors up close plus hundreds instanced | Instanced Skinned Mesh far tier; card hair; per-LOD max counts; animation timing variety; Spawning Count Scale CVar | [Epic docs](https://dev.epicgames.com/documentation/metahuman/create-metahuman-crowds-in-unreal-engine); [Epic overview](https://dev.epicgames.com/documentation/metahuman/metahuman-crowds-in-unreal-engine) |
| Watch Dogs: Legion (2020, London) | No crowd counts found | Census: procedural demographic profiles, jobs and schedules | [Ubisoft News](https://news.ubisoft.com/en-us/article/4po3S9Pwp1YcgBmGPmQxAh/watch-dogs-legion-the-tools-that-built-london); [GDC 2021 Census talk listing](https://www.gdcvault.com/play/1027018/contactUs) |
| Marvel's Spider-Man 1 and 2 | No crowd counts found | Houdini-generated asset sets including pedestrians; voiced pedestrians; walla groups for distant crowds | [Game Developer](https://gamedeveloper.com/design/making-insomniac-s-i-spider-man-i-do-what-a-spider-can); [Gamepur](https://gamepur.com/?p=565268) |
| Cyberpunk 2077 | No developer numbers | Crowd Density user setting; out-of-view despawn and respawn (community-observed) | [Steam discussion](https://steamcommunity.com/app/1091500/discussions/0/4635988522932735208); [Nexus Mods](https://nexusmods.com/cyberpunk2077/mods/526) |

- A community developer reported a Mass crowd dropping from about 60 to about 30 fps after spawning about 10 characters (skeletal meshes), and noted City Sample switches to animated static meshes for crowd members. This is anecdotal but shows that full skeletal MetaHumans are the cost driver. — [Unreal forums (via search snippet)](https://forums.unrealengine.com/t/mass-ai-performance-baking/1159579)
- City Sample's crowd setup is not an official engine plugin and broke or needed changes across UE 5.1, 5.2 and 5.4 (forum reports). — [Unreal forums](https://forums.unrealengine.com/t/city-sample-crowds-for-ue-5-1/882197)
- A forum user setting Mass LOD representation to Static Mesh Instance saw black static-mesh instances at distance (unresolved thread). — [Unreal forums](https://forums.unrealengine.com/t/mass-crowd/2006527)

### Inferences
- Across sources, the near tier of expensive characters is consistently small (10 to 40). The perception of a crowd comes from the cheap tiers, grouping, ambient vignettes and audio. For this project, this argues against trying to raise the MetaHuman count.
- For London specifically: Syndicate shows that dense pockets on key routes are acceptable if the player is routed through them. Watch Dogs: Legion shows that character variety and identity sell a city as much as density. On a jam budget, visual variety (outfits, hats, silhouettes per side, consistent with the project's Frostside and Giltside rules) is the affordable form of that.
- Porting City Sample's crowd wholesale is risky under a deadline (version breakage reports). MetaHuman Crowds is Epic-supported but Experimental. Both are post-jam candidates rather than tonight's work.

### Gaps
- No primary GTA V or RDR2 crowd numbers or techniques found.
- No crowd counts for Watch Dogs: Legion, Spider-Man, or Cyberpunk 2077 from developers.
- The Watch Dogs: Legion Census GDC 2021 talk content (Christopher Dragert) was not accessible.
- Insomniac's GDC technical and AI postmortems may cover pedestrians, but the listings do not say so and the content was not accessible.

---

## 7. Ranked by impact versus effort: "tonight" checklist (about 18 hours) and "after the jam" roadmap

### Takeaway
Tonight, spend effort on the things that change perception without adding expensive bodies: a density-driven walla and panic audio layer, hand-placed vignettes and pairs on the player's critical path, out-of-view spawning at doors and street ends with pooling, staggered ring-based panic toward exit and despawn points, and keeping MetaHumans to the near tier. After the jam, move the population onto Mass (ZoneGraph lanes, LOD tiers, signals, Smart Objects) or MetaHuman Crowds, add recovery, time-of-day density and schedules.

### Cited Findings
- Audio density layering is proven and cheap: Prototype used about 10 people as the threshold for the first crowd layer and separate small and large crowd layers; CRI used 2–4 / 4–8 / 10+ crossfades. — [Game Developer, Prototype audio](https://www.gamedeveloper.com/audio/dynamic-game-audio-ambience-bringing-i-prototype-i-s-new-york-city-to-life); [CRIWARE blog](https://blog.criware.com/index.php/2023/05/08/crowd-system/)
- Near-tier caps in shipped and Epic examples: 40 autonomous NPCs within 12 m (AC Unity) and 10 full-quality actors (MetaHuman Crowds example). — [GAME Watch](https://game.watch.impress.co.jp/docs/news/20150307_691715.html); [Epic, Create MetaHuman Crowds](https://dev.epicgames.com/documentation/metahuman/create-metahuman-crowds-in-unreal-engine)
- Designer-placed stationary groups (look at a point of interest, hold a shape) are part of Hitman's crowd toolkit. — [Game Developer, "The AI of Hitman (2016)"](https://gamedeveloper.com/design/the-ai-of-hitman-2016-)
- Up to 70% of real pedestrians walk in groups. — [PLoS ONE via RePEc](https://econpapers.repec.org/RePEc:plo:pone00:0010047)
- Ring-based reaction zones and exit flows are a proven cheap panic model. — [Game Developer, "The AI of Hitman (2016)"](https://gamedeveloper.com/design/the-ai-of-hitman-2016-)
- Visible despawns are noticed and criticised. — [Gamepressure (Cyberpunk mod listing)](https://www.gamepressure.com/download/cyberpunk-2077-crowd-despawn-fix-v10-mod/ze13a27)
- Distant animation lockstep is a known issue that Epic exposes a "timing variety" control for. — [Epic, Create MetaHuman Crowds](https://dev.epicgames.com/documentation/metahuman/create-metahuman-crowds-in-unreal-engine)
- Smart Object claims can leak when agents die. — [Bugnet blog](https://bugnet.io/blog/fix-unreal-smart-objects-claim-not-released)

### Inferences
Impact and effort ratings below are my synthesis of the sources above for this specific project (UE5.9, MetaHuman foreground, existing flee/scream/die reactions, about 18 hours). They are judgements, not sourced measurements.

**Tonight (jam), ranked by impact over effort**

| Rank | Trick | Impact | Effort | Why / source pattern |
|---|---|---|---|---|
| 1 | Density-driven walla: count NPCs near the listener, crossfade 2 to 3 crowd loops, plus an always-on distant city bed and London one-shots (hooves, wheels on cobbles, bells, street cries) | Very high | Low (sound cues plus a small Blueprint or MetaSound parameter) | Prototype, CRI, Spider-Man 2 distant walla |
| 2 | Panic audio swap: on violence, crossfade calm walla to a scream and panic layer, then decay as the street empties | High | Low | Prototype panic layers |
| 3 | Concentrate the population on the critical path ("hero street"); leave side streets quieter for contrast; use fog and occlusion to hide the far end of streets | High | Low (placement only) | Syndicate clusters; AC Unity designer density |
| 4 | Stationary vignettes on the hero route: conversation rings of 2 to 4, vendor plus customer, short queue at a door, leaners, a group watching a performer or notice; an occasional head look-at toward the player | High | Low to medium (idle animations plus placement; reuse existing reactions) | Hitman point-of-interest and shape groups |
| 5 | Pairs and trios: a leader plus 1 to 2 side-by-side followers on fixed pavement splines, two-way flow | Medium to high | Medium | Moussaïd 55–70% groups; AC Unity Shepherds; fixed routes |
| 6 | Out-of-view spawn and despawn with pooling: spawn at doors, alleys and street ends behind occluders or outside the frustum; never despawn visible NPCs | High (prevents "empty" and "popping") | Medium | AC Unity recycling; Mass LOD visibility; Cyberpunk lesson |
| 7 | Keep MetaHumans to the near tier (about 10 to 40 within roughly 12 m); everything farther is cheaper (lower LOD, no groom, simplified animation, or static or instanced) | High (frame-rate headroom) | Medium | AC Unity 40 cap; MetaHuman Crowds 10-actor example |
| 8 | Staggered ring panic: inner ring cowers, middle ring flees, outer ring looks and alerts, outer rings delayed by distance; flee to the nearest exit away from the threat, which doubles as a despawn point | High (sells the combat fantasy) | Medium (builds on existing flee/scream/die) | Hitman behaviour zones and exit flows |
| 9 | Desync idles and walk cycles (random start time and play rate) so groups never animate in lockstep | Medium | Very low | MetaHuman Crowds timing variety |
| 10 | Cheap VFX life: chimney steam and smoke, warm window emissives, lamplight halos in fog | Medium | Low (environment art) | Unsourced (standard environment-art practice) |

Avoid tonight: porting City Sample's crowd stack wholesale (version breakage reports), adopting Experimental MetaHuman Crowds under deadline, and Smart Objects unless claims are released on death, flee and despawn.

**After the jam (commercial roadmap)**
1. Move ambient population to Mass: ZoneGraph pavement lanes, Mass LOD with per-tier distance and count limits, Actor near tier and instanced far tier (City Sample model), and a density scalar per area and scalability level.
2. Evaluate MetaHuman Crowds (Instanced Skinned Mesh far tier, card hair, Spawning Count Scale) once it leaves Experimental, or build an equivalent far tier with baked or vertex animation.
3. Panic at scale: Mass signals with DelaySignalEntities for ripple timing; a coarse grid plus per-exit flow fields (Hitman) for fleeing; upgrade ("possess") crowd agents to full NPCs or MetaHumans when engaged.
4. Recovery loop: cooldown, then thin respawn from doors with cautious idles (onlookers at the fight site, small gossip groups), and a ramp back to normal density. This is a differentiator, since Hitman's crowds reportedly never calm down.
5. Smart Objects for benches, stalls, shop windows, doors and queues via StateTree, with claim release on every exit path.
6. Time-of-day and district density curves, plus schedule and identity layers in the style of Watch Dogs: Legion's Census for named or recruitable citizens.
7. A City Sample-style Soundscape: drive shouts, vendor cries and carriage sounds from live Mass entity positions; distance-tiered walla (about 40 to 60 m, as in The Outer Worlds) with close NPCs switching to individual voiced lines (Spider-Man 2).

### Gaps
- No source measures the relative perceptual impact of these tricks (for example, audio versus NPC count) in player studies; the rankings are judgements.
- Time estimates per item are not sourced and depend on the project's existing NPC and animation setup, which I did not inspect (research-only scope).
