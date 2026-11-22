# Reflections: how hard is a world we can dig in?

Feasibility report for Unreal Engine 5.9. Research only: nothing was prototyped, installed, compiled or changed in the project or editor.
Written 2026-11-21. Prices, versions and licence terms were checked on that date and can change.

## 1. The short answer

**A world you can dig anywhere is hard. A few places you can dig is not.**

- **UE 5.9 has no built-in way to dig.** Landscape cannot be edited at runtime in a shipped game, and Epic's new Mesh Terrain (5.8, experimental) is an editor-and-cook tool only. Anything diggable means a chunked mesh terrain that you write yourself or buy.
- **Digging itself is the easy part.** Cutting a hole in a mesh takes days. The cost is everything that stands on the ground: navmesh, crowds, props, lighting, collision, save files. Dynamic meshes are not Nanite, have no distance field, and are weak under Lumen. Mass/ZoneGraph lanes cannot be rebuilt at runtime in a shipped game.
- **No third-party voxel plugin supports UE 5.9 yet.** Voxel Plugin 2 (the best known) lists UE 5.6 and 5.7 and calls itself buggy. Its licence is cheap and clean ($349 once, no royalty) but has a budget cap you must confirm.
- **The project is a good place to start.** The ground today is scaled engine cubes, there is no navmesh, no Mass/PCG content and no save system, and the game is single-player. Little exists that digging could break.

Rough effort, in working days of a Claude session building with you testing in the editor. These are my estimates; the research found no UE5 benchmarks or postmortems to calibrate against.

| Scope | First usable version | Likely | Range | Verdict |
|---|---|---|---|---|
| 1. Faked digging (authored dig spots) | one site, saved | **4–6 days**, then 0.5–1 day per site | 3–10 | Easy, safe, no licence issues |
| 2. Heightfield-only deformation | ground that lowers and rises | **~15 days** | 8–28 | Medium; no engine support, still pays most knock-on costs |
| 3. Full volumetric, whole world | tunnels and caves anywhere | **~60 days in-house**, or **~16 days with Voxel Plugin 2** if it runs on 5.9 | 35–120+ in-house; 8–30 with the plugin | Hard; product-scale in-house, third-party blocked by 5.9 support |
| 4. Diggable zones only | one cellar or dig site with real tunnels | **~20 days**, plus a 2–3 day spike first | 10–39 | Medium; contains every knock-on to one place |

**Recommendation (details in section 7).** You said on 2026-11-21 that you want full digging. The route is section 7.1: build it in-house in five gated stages (a dig-spot actor and versioned save, a 3–5 day spike on one patch under the real renderer settings, the voxel core, the swap of the town ground, then polish), about 60 working days in all, stopping at any gate that fails. If digging stays limited to a few places, build scope 4 instead (section 7.2). Either way, do not buy a plugin for UE 5.9 yet.

## 2. What is in the project and engine today

Everything in this section was read from files on disk. The editor was not opened and nothing was compiled.

### 2.1 The Test Town map

`Content/Maps/TestTown/L_TestTown.umap` (172 KB) is the only level. I read its package name table and string data directly, because the file is binary.

| Question | Finding |
|---|---|
| What is the ground? | Plain **static-mesh blockout**. The file contains about 180 occurrences of the `StaticMeshActor` class name, which I read as roughly that many actors. The only static meshes it references are `/Engine/BasicShapes/Cube` and `/Engine/BasicShapes/Cylinder` (the only other asset is the mannequin skeletal mesh for the NPC), skinned with ten `M_Blockout_*` materials (Field, Path, Paving, Stone, Plaster, Slate, Canvas, Clay, Timber, Water). Ground-related actors are labelled `Town Ground`, `South Road`, `North Road`, `Market Square`, `Market Lane West` and `Market Lane East`, in folders `Town/Ground`, `Town/Buildings`, `Town/Boundary`, `Town/Market Stalls` and `Town/Market Well`. |
| Landscape actor? | **No.** The string `Landscape` appears nowhere in the file. |
| World Partition? | **No.** No `WorldPartition` reference, and `Content/__ExternalActors__` holds zero files (it only has an empty `GrayLondon` folder tree left over from the old map). All actors live in the one persistent level. |
| Navmesh? | **None saved.** No `RecastNavMesh`, `NavMeshBoundsVolume` or `NavModifierVolume`. The level only carries the default `NavigationSystemV1` config. |
| Mass, ZoneGraph, PCG, SmartObjects? | **None placed in the map.** No spawner, `ZoneShape`, `PCGVolume`/`PCGComponent` or SmartObject actors, and no foliage or instanced meshes. |
| Lighting | Directional light, SkyAtmosphere, SkyLight, ExponentialHeightFog and post-process volumes. `r.AllowStaticLighting=False`, so lighting is fully dynamic: there is no baked lighting that digging could invalidate. |

So today the ground is a handful of scaled cubes. Nothing in the world can be dug, but equally nothing sculpted needs to be preserved.

### 2.2 Plugins and settings that matter

From `reflections.uproject` and `Config/DefaultEngine.ini`:

- **Enabled:** MassGameplay, MassCrowd, MassAI, ZoneGraph, ZoneGraphAnnotations, SmartObjects, GameplayInteractions, StateTree, the PCG family (PCGPrimitives, PCGBiomeCore, PCGBiomeSample, PCGPrimitives_MeshPartitionInterop, PCGNaniteAssembliesInterop, PCGWaterInterop, plus the editor-only PCGToolset), NavMeshToolset (editor only), Mover, ChaosMover, NetworkPrediction, MetaHumanCrowd, ModelingToolsEditorMode (editor only) and MultiUserClient.
- **Pulled in indirectly:** `PCGPrimitives` depends on `PCGGeometryScriptInterop`, which depends on the runtime **GeometryScripting** plugin, so Geometry Script is already loaded in this project without being listed. `PCGPrimitives_MeshPartitionInterop` depends on **MeshPartition**, **MeshTerrainMode** and `PCGMeshPartitionInterop`, so Epic's experimental Mesh Partition terrain plugins are loaded too (read from the `.uplugin` dependency lists). Relying on transitive enabling is fragile: a digging feature should list GeometryScripting explicitly in `reflections.uproject` and add `GeometryScriptingCore`, `GeometryFramework` and `DynamicMesh` to `reflections.Build.cs`. Neither is listed there today.
- **Not referenced:** the project does not reference the Landscape Patch plugin (installed with the engine) or any third-party voxel plugin.
- **Rendering:** Lumen GI (`r.DynamicGlobalIlluminationMethod=1`) and Lumen reflections (`r.ReflectionMethod=1`); `r.GenerateMeshDistanceFields=True`; `r.Lumen.TraceMeshSDFs=0`; Virtual Shadow Maps on; hardware ray tracing support compiled in (`r.RayTracing=True`, ray-tracing proxies enabled); Substrate on; DX12 with SM6; desktop, maximum-quality target class. These matter because moving geometry interacts with Lumen, VSM and ray-tracing acceleration structures (section 4).
- **Content reality check:** there are no Mass, ZoneGraph, PCG or Landscape assets in `Content/`. The only SmartObject and StateTree assets are the Epic Game Animation Sample ones (`Content/Blueprints/SmartObjects`, `Content/Blueprints/AI`). Before the 2026-11-21 reset (commit `7e3f44ee`) the project had a Mass-based crowd system under `Source/reflections/Crowd/` and old save classes (`ReflectionsGameFlowSave.h`, `ReflectionsQuestSave.h`); the reset deleted them. They remain in git history as reference, but today none of it is in the working tree.

### 2.3 Single-player or networked?

**Single-player, in practice.** Evidence:

- `Source/reflections` has almost no networking code. The only hit is `UReflectionsSpellVfxSubsystem::OnWorldBeginPlay`, which returns early on a dedicated server (`ReflectionsSpellVfxSubsystem.cpp:243`). There is no `UPROPERTY(Replicated)`, no RPC, no `GetLifetimeReplicatedProps`.
- `reflections.Build.cs` has no `OnlineSubsystem` or session dependency, and `Config/*.ini` has no `NetDriver`, session or Steam settings.
- The Mover, ChaosMover and NetworkPrediction plugins are enabled, but I found no project code that uses their networking. My inference is that they come with Epic's movement sandbox content.
- The "relay host" and realtime voice code use WebSockets to talk to an AI service, not to other players.

Consequence: dig state can be a local-only, deterministic list of edits. Keeping each edit as a small record `{time, tool, position, radius, material}` costs almost nothing now and keeps a later multiplayer option open.

### 2.4 Save and load today

There is **no `USaveGame` code** in the working tree. Persisting a dug world means adding a save system first (or reviving the deleted ones from git history as a pattern). It is a prerequisite for every scope except the faked one, and even there it is needed to remember which dig spots were opened.

### 2.5 How the player, spells and NPCs would meet a dig

Current code (all under `Source/reflections/`):

- The hero is `AReflectionsHeroCharacter : AreflectionsCharacter : ACharacter`, so it uses the classic Character Movement Component, with the player hotbar defined in `ReflectionsSpellCatalog::PlayerSpells` (Levitation, Firestorm, Healing, Freeze). `EHeroSpell` already contains earth spells (`StoneShard`, `EarthShock`) whose catalog entries have `Element = Earth`, a delivery type, a `Radius`, `Impulse` and `ManaCost`. The enum is "deliberately stable for existing assets", so new spells must be appended just before `MAX`.
- Every spell lands through a few shared choke points:
  - `AReflectionsSpellProjectile::OnProjectileHit` gives the hit location and surface.
  - `ReflectionsSpellCombat::ApplyArea(World, Caster, Spell, Center, Radius, Damage, Push, Ignore)` handles radial effects such as explosions.
  - `UReflectionsSpellCombatComponent::ReleaseSpellAt(Spell, Origin, Target, AimTarget)` is the aimed release.
  - `UReflectionsSpellEventSubsystem` (a world subsystem) broadcasts `OnSpellHit` with `FReflectionsSpellHitData` (location, impact normal, physical surface, impulse, reaction), plus `OnSpellImpactVisual`.
- Aiming already finds the ground: `UReflectionsSpellAimComponent` traces from the camera on `ECC_Visibility` (`ReflectionsSpellAim.cpp:211`) and `GroundBelow()` traces down from the aim point (`:313`). It exposes `AimPoint` and `AimNormal`, and draws a ground decal preview (`EReflectionsAimPreview::GroundArea`) that could show a dig radius. Any diggable surface must therefore **block `ECC_Visibility`**.
- NPCs react to Earth spells with a `Knockdown` reaction (`ReflectionsSpellCombat.cpp:65`). Existing NPC pathing only appears in `ReflectionsNpcCombatComponent.cpp:134` (`FindPathToLocationSynchronously`). `ArtDirection/NpcBehavior/Plan.md` says the NPC code will be rebuilt from scratch, so nothing there needs to be protected from digging; the rebuild should simply be told about it.

**Where a dig tool or dig spell hooks in:** a new `UReflectionsTerrainSubsystem : UWorldSubsystem` that owns the dig state and exposes `Dig(Center, Radius, Strength)` / `Fill(...)`. A new `EHeroSpell::Dig` (or reuse of `EarthShock`) calls it from `ReleaseSpellAt`/`ApplyArea` at the aimed point, and the subsystem also listens to `OnSpellHit` so existing Earth spells can scar the ground too. The spell code already has the radius, impulse and mana fields a dig needs; only the terrain side is new.

## 3. The four scopes

"Working days" below means days of a Claude session doing the build while you test and review in the editor. Elapsed time is longer, because compiles and builds have to wait for editor-closed windows. Every effort figure is my estimate.

### Scope 1 — Faked digging (pre-authored dig spots)

**How it works.** The ground stays a normal static world. A `DigSpot` actor (a small C++ class plus a data asset) is placed wherever the story wants a dig. When the player digs there, with a shovel interaction or an Earth spell landing inside the spot's radius, the actor plays a short timeline:

1. A burst of dirt (Niagara, the project already ships spell VFX infrastructure in `SpellVFX/`), a sound, and a camera kick (the spell camera modifier already exists).
2. A swap from the "intact" mesh to a "dug" mesh. The dug mesh is a pre-modelled pit or trench with the same rim as the ground it replaces. Two or three stages (mound, shallow pit, deep pit) read as progress.
3. A reveal: a buried item or quest pickup, a skeleton, a hatch to a cellar level, or a trigger for a story beat.
4. A saved flag so it stays dug.

Surface scars away from any spot (scorch, churned earth) are covered by decals, which cost almost nothing and need no collision.

Because the ground is currently scaled engine cubes, the "dug" state needs real geometry: either a ground tile modelled in two states and swapped, or a hole cut through the cube ground under a lid mesh. Both are a few hours of Blender work per site, and the project already has Blender scripting and a build-from-scripts pipeline (`Tools/`, `ArtDirection/CityPCG`).

**Effort (Claude session + user).**

| Piece | Low | Likely | High |
|---|---|---|---|
| `DigSpot` actor, data asset, stage swap, Niagara/sound, hook to the existing spell and interact paths | 2 days | 3 days | 5 days |
| Per-site art (pit meshes, matching rims, materials, placement) | 0.5 day each | 1 day each | 2 days each |
| Save flags (needs a small save system, which the project does not have today) | 1 day | 1–2 days | 3 days |

A convincing first slice (one dig site, three stages, a reveal, saved) is about **4–6 working days**. Each extra site is then **0.5–1 day**.

**Risks.**
- It reads as canned. Players who expect "I can dig anywhere" will test the edges, and a flat ground cube cannot be dented away from a prepared spot. The fix is design, not code: make spots obvious (disturbed earth, a marker, an NPC hint) and keep the dig verb tied to them.
- Pit meshes have to match the ground's height and material exactly or the seam shows. A short dust cloud hides the swap.
- A reveal that spawns a physics prop inside a pit needs the pit collision to be simple and generous.

**What breaks or needs changing in the project.** Almost nothing. Navmesh, NPC pathing, Mass lanes and PCG all stay on a static world, so a pre-authored pit is baked into the nav data once and never rebuilt at runtime. The pit area needs a navigation modifier or a nav link only if NPCs should avoid or use it. The ground meshes where spots sit need to be tiled or cut; that is a map edit, not a code change. Save and load is the one missing prerequisite (section 2.4).

**Licence and cost.** None. This uses only engine features (Niagara, static meshes, decals) and original art.

### Scope 2 — Heightfield-only deformation

**What UE 5.9 offers.** None of the engine's heightfield routes can lower or raise ground in a shipped game. I checked the Landscape Patch and Mesh Partition source myself. The research agents checked the rest against Epic's docs and forum posts.

| Route | Maturity in 5.9 | Digs at runtime? |
|---|---|---|
| Stock Landscape actor | Production for authoring | **No.** Epic's source says runtime Landscape editing is not supported. Edit layers, the Landscape Patch plugin and "import heightmap from render target" are editor-only (the Landscape Patch header marks them "editor-only (and don't work at runtime)"). Collision rebuild is editor-only and the collision height data is stripped from cooked builds. |
| Virtual Heightfield Mesh | Experimental, v0.1, off by default | Visual only. No collision, navigation or physics, no Nanite or Lumen path. |
| Mesh Partition / Mesh Terrain (Epic, 5.8) | Experimental | **Authoring and cook only.** Its runtime sections are "built during the cook process" (`ACompiledSection` in the source), it is built around World Partition, and Epic has not documented any runtime editing. Epic's docs say to "use caution when shipping". 5.9 Preview adds nothing for runtime use. |
| Nanite Displaced Mesh | Beta | Baked in the editor. |
| Render target plus World Position Offset | Production technique | Visual only (footprints, dents). No collision. |
| Render target plus Nanite tessellation | Unlabelled; open bugs in 5.7–5.8 | Visual only. |
| Chunked dynamic-mesh heightfield (`UDynamicMeshComponent` or similar) | Supported | **Yes**, with real collision. Not Nanite, weak under Lumen. This is the only workable route. |

**How the workable route works.** The ground becomes a grid of chunks, each a dynamic mesh built from a height array. A dig lowers heights inside the brush radius and rebuilds only the chunks it touches. Collision is cooked asynchronously per chunk, and a vertex-colour splat drives the material. It is simpler than volumetric digging: no marching cubes, chunk seams are just shared border rows, a town-sized ground needs no LOD, and a save file is just height deltas.

**Limits.** No tunnels, caves or overhangs. A "hole" is a pit with sloped walls, because a heightfield stores one height per column.

**What breaks or must change here.**
- `Town Ground`, `South Road`, `North Road`, `Market Square` and the lanes are scaled engine cubes. They must be replaced by chunk meshes (or cut out of) so the ground can change.
- Buildings, roads, the well and the stalls need a **"do not dig" mask**, or their footings float over lowered ground.
- Everything in section 4 applies in full: navmesh, hero and NPC floors, props, lighting, save.

**Third-party and open source.** TerraDyne is an MIT-licensed GitHub project (v0.8.0, 2026-11-13) that does chunked dynamic-mesh heightfield sculpting. The author claims it works on UE 5.5–5.8 including cooked builds, with off-thread collision. Those are the author's claims and I tested nothing. MIT permits commercial use, but a stale or one-person project is a risk to carry. Orbdale Terrain (custom heightfield, no Nanite) and Shader World ($249.99–$1,024.99 on Fab, UE 5.0–5.8, runtime editing, Fab Standard License) also exist. None lists UE 5.9.

**Effort (Claude session + user).**

| Piece | Low | Likely | High |
|---|---|---|---|
| Chunk grid, height-array mesher, async collision | 3 | 6 | 10 |
| Dig and raise brush, aim and preview | 1 | 2 | 4 |
| Materials (splat, paving mask) | 1 | 2 | 4 |
| Save and load of height deltas | 1 | 2 | 3 |
| Nav, hero and NPC floors, props after a dig | 2 | 3 | 7 |
| **Total (working days)** | **8** | **15** | **28** |

**Risks.** Collision hitches (the default is a synchronous cook on the game thread), mismatch between visible and collidable ground, chunk seams, ground that looks like a mud pit with no tunnels, and no Nanite plus weak Lumen on all the ground. I found no postmortem of a shipped UE5 game that ships runtime terraforming.

**Licence and cost.** In-house: none beyond Unreal's own terms.

### Scope 3 — Full volumetric digging (tunnels, caves, overhangs)

Two ways to get there. Neither is a feature you add in a sprint.

#### 3a. In-house on Geometry Script and `UDynamicMeshComponent`

**What the engine gives you.** The runtime-safe pieces are mesh booleans, plane cuts, Solidify and Morphology (voxel wrap and offset), and `FMarchingCubes` (header-only, in the `GeometryCore` runtime module). `UDynamicMeshComponent` renders a mesh and cooks its collision asynchronously. Geometry Script is already loaded in this project through the PCG plugins (section 2.2). The research agent read the module build files and headers to confirm what ships at runtime.

**What it does not give you.**
- No node that meshes a density grid. Solidify and Morphology take a mesh in. `FMarchingCubes` takes a per-sample function, uses a locked hash map, and emits only positions and triangles: fine for a prototype, too slow and too bare to ship.
- No dual contouring, no surface nets, no Transvoxel (seam-stitching between levels of detail) anywhere in the engine source searched.
- No Nanite, no LODs, no distance field (section 4).

**What you write in C++.** A density-plus-material grid with chunk addressing; a purpose-built mesher with normals and material weights; brush stamps; a dirty-chunk scheduler with a per-frame commit budget; a worker-thread pipeline; chunk streaming; a collision policy; navmesh hookup; a triplanar material; save and load; and soak tests.

**The mesh-boolean shortcut.** Boolean-cutting a big mesh is the quickest demo. Forum reports call it slow and fragile on dense meshes ("wasn't designed to work at runtime on objects with many vertices"). Treat it as a prototype, not the architecture.

**Effort.** The research agent's estimate (mine for the totals) for a *bounded* dig volume of about 100–250 m, one resolution, no LOD, single-player, 1–3 materials:

| Package | Low | Likely | High |
|---|---|---|---|
| SDF volume, meshing, collision, navmesh hookup | 5 | 10 | 20 |
| Digging tool and brush | 2 | 4 | 8 |
| Materials | 2 | 4 | 8 |
| Save and load | 2 | 3 | 6 |
| Polish and performance | 4 | 8 | 15 |
| **Total (working days)** | **15** | **29** | **57** |

A rough demo (dig a hole, see it update, collide with it) is 3–5 days. That is why demos mislead.

For a **whole-town** diggable world I add streaming in and out, view-distance and LOD or seam work, and prop, navmesh and crowd integration at scale. My extrapolation is **about 60 working days (35–120+)**, and it is the part I trust least. Reference classes: Astroneer (UE4) rewrote its terrain once and the studio said the game took about twice as long to make; Voxel Plugin 2 was announced in September 2024 for "early 2025" and is still a preview that calls itself buggy.

**Risks.** Game-thread stalls when a dig crosses many chunks (proxy rebuild, ray-tracing geometry rebuild, physics-state recreate), Lumen quality inside caves, Virtual Shadow Map invalidation near lights, navmesh churn, and a reported 5.9 Preview collision-key bug (section 4.5).

**Licence and cost.** None beyond Unreal's own terms.

#### 3b. Buying a plugin

All prices and terms below were seen on 2026-11-21. The Voxel Plugin licence page I re-fetched myself; the rest comes from the research agent's notes.

**Voxel Plugin 2** (vendor: Voxel Plugin; the open `VoxelCore` library carries "Voxel Plugin SAS")
- **Status:** a preview series (2.0p8), not a final 2.0. The docs say it "can be buggy at times", target UE 5.6 and 5.7, and call runtime sculpting "experimental, first iteration". **5.9 is not listed**; 5.8 support for VP2 itself is unconfirmed.
- **Price:** **$349 one-time**, excluding VAT. "This isn't subscription licensing." The licence gives perpetual access, one year of feature updates, three years of bug fixes and three years of Unreal upgrades. Licences are shareable "within reason, rather than being per-seat".
- **Royalty or revenue share:** none stated.
- **Cap:** a **game-budget cap, not a revenue cap**. Above $100k USD budget the $349 licence is not available and you contact the vendor for separate terms. If the first release that uses the plugin had a budget under $100k, you keep the $349 licence even if earnings later pass $100k. **Conflict:** the vendor homepage says $200k and the docs say $100k, and the docs page is undated. Get the figure in writing from the vendor before relying on it.
- **Source and EULA:** the VP2 source repo is private; access comes from linking GitHub after purchase. I could not find the EULA text, so whether you may modify the source is unconfirmed. Fab's Standard License permits modification, but the legacy Fab listing did not show its licence label when I re-checked.
- **Features:** async sculpt calls, collision and a dynamic navmesh around "invokers", save and load of edits (`Get Save`, `Load from Save`), and an experimental Nanite path (2.0p8). Edits are not replicated automatically. There is no voxel physics (floating pieces falling), which Legacy had. I found no Lumen documentation and no independent benchmarks.
- **Engine lag:** for Legacy, build fixes for 5.7 came 18 days after 5.7 released, and for 5.8 seven days after. There are no 5.9 commits. UE 5.9 is a Preview and the final is described as next year, so a 5.9 port may mean patching the plugin yourself.

**Other options** (research agent's notes; mostly vendor claims; none verified by me):

| Option | Price | Licence | UE versions listed | Notes |
|---|---|---|---|---|
| Voxel Plugin Pro Legacy (1.x) | $349.99 on Fab | Vendor; end-of-life, bug fixes only | patched for 5.8 in June 2026 | Has voxel physics. Its free GitHub repo has **no LICENSE file**. One forum user reports Pro 1.2 crashing on 5.7.3/5.7.4. |
| TerraVox | $159.99–324.99 | Fab Standard | 5.6–5.8 | New (Aug–Nov 2026), no track record. |
| VoxelTerrain (Brahoule) | $274.99–524.99 | Fab Standard | 5.4–5.8 | |
| SuperVoxel, Voxelith | $49.99–99.99, $20.99–41.99 | Fab Standard | 5.8 only | Voxelith is block-style. |
| PorismDIMs | $239.99–799.99 | Fab Standard | 5.7–5.8 | Tagged "Generated with AI: Yes". |
| Realtime Mesh Component Pro | see Fab | Fab Standard | 5.5–5.8 | Claims runtime Nanite (vendor claim). |
| Voxel Farm | $295/yr indie, $995/yr pro, per seat | Proprietary | UE4-era pages | No evidence of UE5 support. |
| UnrealSandboxTerrain | free | **GPL-3.0, non-commercial** | — | Unusable in a sold game without a separate licence from the author. |
| VoxelWorlds, GeoField, VoxelWorld, VoxelPluginFreeLegacy | free | **No licence file** | — | Not usable commercially without the owner's permission. |
| InstantOrganicCaves, TerraDyne, DC4UE | free | MIT | 5.7 / 5.5–5.8 / stale | Caves only (its runtime carving API is paid), heightfield only, and stale respectively. |

I found no maintained, permissively licensed, full 3D voxel terrain with runtime digging.

**Baseline terms.**
- **Fab EULA:** shipping a game with a purchased plugin compiled in is allowed, and so is modifying it; standalone resale or redistribution is not. Plugins are licensed per seat. Fab content cannot be combined with GPL, LGPL or CC-BY-SA code. Section 5(b) has an ambiguous "Engine Tools" clause worth a lawyer's read before shipping.
- **Epic royalty:** 5% of lifetime gross revenue above $1M per product, with Epic Games Store sales exempt.
- **This project:** `ArtDirection/Submission/THIRD_PARTY_NOTICES.txt` and the Credits screen already track third-party licences, so any plugin adds a notice line.

**Effort with Voxel Plugin 2.** My estimate: **about 16 working days (8–30)** if it runs on 5.9, made of engine compatibility 1–10 days, world setup and materials 3–5, dig tool 2–3, navmesh/crowd/prop/NPC handling 3–6, save 1–2 and tests 1–3. If it does not run on 5.9, the effort moves toward the in-house numbers above.

**Main risks.** The 5.9 gap; a preview-quality plugin; a budget cap that could bite if the game's budget passes $100k; and reliance on one vendor.

### Scope 4 — Diggable zones only

**How it works.** The world stays static and Nanite. A few chosen places (a dig site, a cellar, an old mine) are bounded volumes with real tunnels. Each volume holds one fixed-resolution density grid (plus a material id), meshed in roughly 16 m chunks as non-Nanite `UDynamicMeshComponent`s. The opening is framed by static geometry (a quarry rim, a hatch, a stair) so no seam shows. Brush stamps subtract from or add to the grid, and a worker thread re-meshes only the dirty chunks.

**Why it is the sweet spot.** A bounded zone removes most of the hard parts: no LOD or Transvoxel, no streaming, one resolution. Grids are small. A 32×32×16 m cellar at 0.25 m cells is about a million cells (roughly 2 MB as 16-bit values). A 128×128×64 m zone at 0.5 m cells is 8.4 million cells (16.8 MB, plus 8.4 MB for materials) before compression. Every knock-on in section 4 is confined to the zone:
- **Navmesh:** only tiles under the zone rebuild.
- **Crowds:** ZoneGraph lanes are baked and static, so keep them out of the zone; crowds never go there.
- **Props:** PCG never places anything in the zone.
- **Rendering:** weak Lumen and no Nanite apply only to the zone's interior, which is a dark space lit by local lights anyway.
- **Save:** one grid snapshot per zone, or an edit log.

**Effort (Claude session + user).** My estimate, scaling the bounded-zone table above down for small zones:

| Package | Low | Likely | High |
|---|---|---|---|
| SDF volume, meshing, async collision | 4 | 8 | 15 |
| Digging tool and brush | 2 | 3 | 6 |
| Materials (triplanar rock and soil, cave look) | 1 | 3 | 6 |
| Save and load | 1 | 2 | 4 |
| Polish, performance, navmesh throttling | 2 | 4 | 8 |
| **Total (working days)** | **10** | **20** | **39** |

Run a **2–3 day spike first**: one 32 m zone, dynamic-mesh chunks, async collision, with Lumen, hardware ray tracing, Virtual Shadow Maps and a dynamic navmesh all on. It answers the biggest unknowns (commit hitching, cave lighting) before the full cost is committed. No public benchmark exists for this stack.

**Risks.**
- Cave lighting under Lumen: the dynamic mesh has only bounding-box mesh cards and no distance field, so interiors may look flat or leak light. Plan local lights and test early.
- Commit hitches when a dig crosses chunk borders.
- The 5.9 Preview collision-key bug (keep each chunk's collision mesh under 16,384 vertices).
- Player expectation: "why only here?" This is a design problem as much as a technical one, and it is why zones should be story places.
- Preview-engine churn.

**What breaks or must change.** The aim traces (`ReflectionsSpellAim.cpp:211`, `:313`) must hit the zone's collision on `ECC_Visibility`. The ground cubes around each zone need a hole or rim. The NPC rebuild should treat zones as no-go for crowds. `reflections.uproject` should list GeometryScripting and the Build.cs should add `GeometryScriptingCore`, `GeometryFramework` and `DynamicMesh`. A save system is needed (section 2.4).

**Licence and cost.** None beyond Unreal's own terms. A plugin is not needed at this size, so there is no third-party licence to carry.

## 4. Knock-on effects of ground that changes

These apply to scopes 2, 3 and 4 (and in a contained way to scope 1's authored pits). Findings marked **(source)** were read from the UE 5.9 install at `C:\Program Files\Epic Games\UE_5.9\Engine` by me or a research agent. Nothing here was measured; no public figure exists for most of these costs, so budget a profiling pass.

### 4.1 Navmesh at runtime

- **Dynamic generation is required.** Only `RuntimeGeneration = Dynamic` re-gathers geometry, so only it can create or remove walkable floor. `DynamicModifiersOnly`, dynamic obstacles and Nav Modifier Volumes only cut or mark the existing surface; they are far cheaper but cannot create a pit floor or a tunnel floor **(source)**.
- **How a rebuild works.** A component update or a dirty-area box queues work that flushes up to 60 times a second. Every tile the box touches (after growing by the agent size) is rebuilt. Geometry is gathered on the game thread; rasterising runs on worker tasks; finished tiles are applied on the game thread **(source)**.
- **Time slicing is compiled out** in this build (`RECAST_ASYNC_REBUILDING 1`, `ALLOW_TIME_SLICE_NAV_REGEN 0` in `RecastNavMesh.h`, which I confirmed), so the time-slice budget settings do nothing. The 5.9 release notes mention progressive tile building "with control over how many tiles build per tick"; I did not verify how it is exposed. Epic's tip is to wrap bulk edits in navigation build locks and throttle how often you commit.
- **Tile size.** The engine default is 1000 uu tiles at about 52 cells a side; Epic's dev doc recommends 32–128 cells per side. A 500 m town is about 2,500 tile columns. There is no ms-per-tile figure anywhere I looked; use `stat Navigation`.
- **A dynamic mesh does not feed the navmesh by default.** `UDynamicMeshComponent` and `UProceduralMeshComponent` are navigation-relevant, but the navmesh reads their collision body and exports a triangle mesh only when the trace flag is `CTF_UseComplexAsSimple`. The dynamic mesh component defaults to `CTF_UseSimpleAsComplex`, so by default it exports nothing. Neither component notifies navigation after rebuilding collision; you must call `FNavigationSystem::UpdateComponentData` yourself **(source)**.
- **The project has no navmesh today** (section 2.1), so a `NavMeshBoundsVolume` is needed regardless. World Partition navmesh is called "very experimental" by an Epic reply, which is another reason to stay in the current non-World-Partition level.

### 4.2 Characters and AI walking into holes

- Path following repaths when tiles change (about every 0.5 s) or aborts the move. `ANavLinkProxy` smart links can be toggled at runtime **(source)**.
- **Hero (Character Movement):** defaults are fall-friendly (`bAlwaysCheckFloor = true`), so the floor vanishing makes the hero fall. KillZ is the fallback.
- **Mover** (used by the sandbox content): walking mode defaults to `FloorCheckPolicy = OnDynamicBaseOnly`, so a stationary character on static ground that disappears does **not** re-check its floor unless the policy is `Always`. The enum's own comment says so **(source)**. I did not read ChaosMover's behaviour.
- A plain `MOVE_NavWalking` character follows navmesh height and can hover over a stale navmesh.
- There is no engine "fill kill-volume"; fall recovery would be custom.

### 4.3 Mass crowds and ZoneGraph

- **ZoneGraph lanes are baked.** They come from `UZoneShapeComponent` shapes and are serialised in `AZoneGraphData`. The build code is `WITH_EDITOR` (I confirmed the guard in `ZoneGraphData.cpp`). `UMassCrowdSubsystem::RebuildLaneData` is also editor-only and refuses to run in a game world (confirmed in `MassCrowdSubsystem.cpp`). A ZoneGraph Quick Start forum post (dated November 2025 on the page) says ZoneGraph "does not support runtime generation or modification in its current state". Public build helpers exist, but I found no sample, so a custom runtime rebuild is unproven.
- **Lanes are not terrain-following and Mass agents do no ground trace.** `UMassNavigationSmoothHeightProcessor` smooths each agent's height toward the lane or navmesh point's height, so dug ground leaves agents at the old height.
- **Mass navmesh path-following calls `FindPath` once** and has no observer, so tile invalidation does not re-plan.
- **What does work at runtime:** `UMassCrowdSubsystem::SetLaneState` (open and close lanes), annotation components, and actor representation with Character Movement.
- **Consequence:** with any digging, crowds either avoid the diggable area (scope 4), close lanes that cross a dug place, or stay on static ground (scope 1). The old crowd system was removed in the 2026-11-21 reset, so nothing needs to be unpicked today.

### 4.4 SmartObjects and PCG

- **SmartObjects** keep their registered transform. After a dig you must call `UpdateSmartObjectTransform`, `SetSlotEnabled` or unregister them yourself. Entrance validity is recomputed at request time with a ground trace and a navmesh projection **(source)**.
- **PCG:** change tracking, `Refresh` and `DirtyGenerated` are editor-only. At runtime, generation reacts only to generation-source position and radii. You can force regeneration with `GenerateLocal(bForce)`. I found no runtime "dirty region" API. The Landscape cache is not serialised by default and Epic plans to deprecate it. GPU PCG behaviour with changing ground was not covered by any source.
- **Props standing on dug ground:** the standard pattern is a custom pass after each dig. Overlap-query props inside the dig's bounding box, re-trace each one down, then drop it, destroy it or let it ragdoll. This works for every scope. The project has no PCG content yet, so this is a constraint on future work, not a regression.

### 4.5 Chaos collision

- **Dynamic mesh collision** defaults to a synchronous cook on the game thread. `bUseAsyncCooking` (off by default) keeps the old collision until the new cook finishes, then swaps it and recreates the physics state on the game thread. Epic's own code comment gives 9–13 ms to cook a 10–18k-vertex trimesh on one core of a Threadripper 3970X.
- **The default cap** is `geometry.DynamicMesh.MaxComplexCollisionTriCount = 250000` triangles.
- **Collision-key bug (5.9 Preview 1, UE-380849).** A forum report dated 2026-11-17, with no Epic reply, says runtime procedural meshes over 16,384 vertices share one cooked collision key and so collide wrongly. `UDynamicMeshComponent` does not override `GetMeshId`, so it may be affected in the editor and PIE. The DDC path is compiled out of packaged builds. Keep each chunk's collision mesh under 16,384 vertices and check in PIE.
- Landscape collision is a 2.5D heightfield and cannot hold caves.
- An Epic forum reply says Chaos flushes a large batch of pending body changes (over about 10,000) in one stall that cannot be time-sliced, and recommends fewer, merged bodies. Avoid creating and destroying many bodies in a frame.

### 4.6 Nanite, Lumen, shadows, ray tracing

- **Nanite does not support runtime-modified meshes.** `UDynamicMeshComponent` and `UProceduralMeshComponent` always use the non-Nanite path, and the `GeometryFramework` module has no Nanite code (confirmed). Runtime Nanite exists only through third-party plugins that write Nanite data themselves, which is a version-fragility risk. In a mostly Nanite scene, dug terrain becomes the expensive non-Nanite part, and Epic's Virtual Shadow Map docs say non-Nanite casters cost more.
- **Lumen.** Dynamic-mesh distance fields were deprecated in 5.6 and the proxy sets `bSupportsDistanceFieldRepresentation = false` (confirmed). Under **software** Lumen the terrain is not in the Lumen scene at all. Under **hardware** ray tracing it is traced through its own acceleration structure, but gets only bounding-box "mesh cards" (a TODO in Epic's code), a poor fit for caves and overhangs. Each buffer upload recreates the chunk's whole acceleration structure (no refit). This project has Lumen on with `r.Lumen.TraceMeshSDFs=0`, hardware ray tracing support compiled in, `r.GenerateMeshDistanceFields=True` and Virtual Shadow Maps on. On a GPU without DXR support Lumen falls back to software and the terrain drops out of Lumen GI. That last step combines verified code with Epic's hardware requirements and is my inference.
- **Virtual Shadow Maps** invalidate cached pages that overlap a changed primitive's bounds. Lighting is fully dynamic (`r.AllowStaticLighting=False`), so nothing baked goes stale.
- **Ray tracing per chunk** is on by default (`bEnableRaytracing`). Turning it off saves cost but also removes the chunk from hardware Lumen.

### 4.7 Saving and loading dug ground

- **Two patterns.** Modified-chunk snapshots, or an edit log (brush stamps) replayed over a deterministic base. A snapshot of modified chunks plus a recent log is the common hybrid. Dense voxel data compresses well: one benchmark (engine unnamed) reports about a billion non-empty voxels as 38–73 MB on disk against 2.97 GB in memory.
- **Version the format on day one.** The strongest migration evidence is Astroneer: the original terrain was "hard to update without totally breaking peoples' save games".
- **The project has no save system** (section 2.4). A dug-ground save is a good reason to build one properly rather than as a one-off.
- **Edit-log size and replay-time figures** (a few dozen bytes per stamp) are my inference; I found no published replay times.

### 4.8 Networking

The game is single-player in practice (section 2.3). Making dug terrain multiplayer-safe later is expensive: Astroneer's own blog calls its terrain replication "novel" and shipped with known issues, and Voxel Plugin 2 does not replicate edits automatically. The cheap hygiene to build in now is to route every dig through one function that appends a small deterministic record. The research notes include a five-point checklist for deciding a game is single-player only: planned modes, shared state, AI dependence on terrain, competitive use and headless testing.

### 4.9 Performance on the RTX 5080 and a minimum spec

- **No UE5 benchmark exists** for diggable terrain, so every budget below is a heuristic.
- **On the dev RTX 5080** the GPU is not the limit. The stalls are CPU and game-thread: the proxy rebuild, the physics-state recreate and the navmesh apply. Mesh generation runs on workers; collision cooking is CPU. The acceleration-structure rebuild is GPU.
- **Memory:** the research agent's rough figure is 2–3 MB per 10k-triangle chunk including the ray-tracing structure and cooked collision, or about 200–300 MB for 100 occupied chunks in a worst case. Unmeasured.
- **Sourced anchors:** Epic's Lumen budgets (4 ms at 60 fps on console), and ray-tracing guidance of at most about 100k instances and 10k–30k dynamic triangles per frame.
- **Minimum spec.** I did not find a minimum spec defined in the project files I read. The Steam survey for October 2026 (read through a fetch tool, not cross-checked) puts the GTX 1660 family at about 2.6%, RTX 2060 at 1.55%, 16 GB RAM at 41.4%, six cores at 27.3% and 8 GB VRAM at 26.9%. The project already needs Lumen, Virtual Shadow Maps and DX12 SM6, so a GTX 1660-class card is a stretch regardless. Digging adds CPU load and, without DXR, removes the terrain from Lumen. Zones (scope 4) keep that cost bounded; a world-wide dig does not.

## 5. What changes in the project, by scope

| Item | 1 Faked | 2 Heightfield | 3 Volumetric world | 4 Zones |
|---|---|---|---|---|
| Replace the cube ground (`Town Ground`, roads, square) | Cut or tile at each site | Replace entirely | Replace entirely | Cut a hole and frame it per zone |
| Navmesh bounds volume added to the map | Yes (needed anyway) | Yes, set to Dynamic | Yes, set to Dynamic | Yes, set to Dynamic |
| Mass lanes / ZoneGraph | No change | Close lanes or keep crowds off dug areas | Same, everywhere | Keep lanes out of zones |
| PCG props | No change | Re-validation pass after each dig | Same | Not placed in zones |
| Save system (none today) | Small flags | Height deltas | Chunks or edit log | One grid per zone |
| `reflections.uproject` / `Build.cs` | None | Add GeometryScripting, `DynamicMesh`, `GeometryFramework` | Same, or the plugin | Same |
| Aim traces on `ECC_Visibility` | None | Ground must block it | Same | Zone must block it |
| NPC rebuild (`NpcBehavior/Plan.md`) | Optional | Must handle falls and no-go areas | Same | Must treat zones as no-go |
| Third-party licence line | None | None (or TerraDyne MIT) | Plugin terms | None |

## 6. What I could not verify

- **Nothing was measured.** I did not open the editor, compile, prototype or profile. The map findings come from reading the binary `.umap` for class and asset names. I did not decode each actor's scale or mesh, and "no navmesh, Mass or PCG actors" is based on those class names being absent from the file.
- **UE 5.9 may change.** The install reports 5.9.0 (changelist 60738873), but Epic's online 5.9 release notes were still titled "Preview" when read, and the README says the project runs 5.9.0 Preview. Behaviours and bugs reported on 5.9 Preview 1 may change before the final.
- **Several Epic pages could not be read** (HTTP 403 or empty): the 5.8 release notes, the Virtual Heightfield Mesh docs page, "Introduction to Mesh Terrain", the roadmap card and Epic's 5.8 announcement posts. Mesh Terrain conclusions rest on the plugin source and forum posts.
- **Voxel Plugin 2:** the EULA text, the $100k versus $200k cap, and 5.8 or 5.9 compatibility need the vendor. On re-check, the legacy Fab listing did not show its licence label or supported engine versions. Other plugin prices and versions come from the research agent's notes and were not re-verified by me.
- **Engine behaviour not confirmed:** how the 5.9 "progressive navmesh build" option is exposed; ChaosMover's floor handling; whether `UpdateComponentData` is reachable from Blueprint; GPU PCG with changing ground; whether the dynamic-mesh acceleration structures count against the per-frame ray-tracing update cap; the default `bCanEverAffectNavigation` on `UDynamicMeshComponent`; and how Lumen actually lights dug interiors in 5.9.
- **Effort numbers are my estimates**, not sourced. The research found no benchmark or postmortem to calibrate them against.
- **The Steam hardware survey figures** were read through a fetch tool and not cross-checked.

## 7. Recommendation

### 7.1 Updated 2026-11-21: full digging is the goal

You asked for full digging. This is scope 3 built in-house (section 3a), cut into stages that each end at a gate so a failure costs days, not weeks. The task-level plan for stages 1 and 2 is the doc "Reflections full digging plan": https://claude.ai/artifact/Kco5jg6MqxCsjaiYE2XVrr Everything here is my design reasoning and arithmetic. Nothing was measured or prototyped.

**What "full" means here (my assumption, change it if wrong).** Anywhere you can walk on the ground, you can dig down, tunnel sideways, make caves and overhangs, and pile dirt back up. Buildings, roads and the square stay authored Nanite geometry that sits on protected ground, so you cannot undermine a house. Destructible or collapsing buildings, falling debris, fluids and multiplayer are a different and much larger project and are not covered.

**The design that makes it tractable**
- **Data covers the whole town, meshes cover only what is near.** The 500 m town as one grid is about 1000 × 1000 × 46 cells at 0.5 m (20 m of depth, 3 m of height), roughly 46 million cells, or about 92 MB dense at 16 bits before collapsing the many all-air and all-rock chunks. Meshes exist only for surface chunks inside a ring of about 150 m around the hero: roughly 275 chunks of 16 m, each a non-Nanite `UDynamicMeshComponent`. Outside the ring the ground is a cheap coarse proxy rebuilt from the data. The ring moves with the hero, and the hero can only dig within arm's reach, so the ring edge is never where the digging is. Dug chunks that fall out of the ring keep their data and re-mesh on a worker thread when the ring returns.
- **One dig function.** Every dig, from a tool, a spell or a story beat, goes through one function that edits the grid and appends a small record. That is the whole networking and save hygiene (sections 4.7, 4.8).
- **A bedrock floor and an edge wall** bound the grid, so there is no infinite void to fall into.
- **Our own mesher.** Write a surface-nets or similar mesher in C++ with normals and material weights, because the engine's `FMarchingCubes` is a prototype-grade tool (section 3a). Keep each chunk's collision mesh under 16,384 vertices (section 4.5).

**Stages, with gates** (working days of a Claude session plus you testing in the editor; my estimates)

| Stage | What | Likely days | Gate to continue |
|---|---|---|---|
| 0 | You decide the questions below | 0.5 (you) | Answers written down |
| 1 | Scope 1 dig-spot actor, plus a small versioned save system that chunks can later use | 5 | Buried finds work and survive a save |
| 2 | **Spike** on one 32–64 m patch of the real ground: chunk meshes, async collision, a 3×3 ring that streams, the seam against the old cube ground, hero walking and digging, Lumen with hardware ray tracing, Virtual Shadow Maps, dynamic navmesh, packaged build | 3–5 | Pass marks below |
| 3 | **Voxel core:** grid and chunk store, mesher, brush, worker pipeline with a per-frame commit budget, async collision, material weights, chunk save and load, navmesh hookup | 18 | A 150 m ring holds frame time while digging |
| 4 | **Town swap:** replace the cube ground, no-dig masks under buildings and roads, ring streaming plus the far proxy, hero and AI fall handling, prop re-validation, spell aim, one NPC rule for holes | 13 | Whole town playable and saved |
| 5 | **Polish and soak:** cave lighting, performance, minimum-spec pass, long soak tests, save-format migration test | 20 | Packaged build stable for hours |
| | **Total** | **about 60** | Range 35–120+ (the same total as section 3a; polish is the number I trust least) |

**Spike pass marks (mine, adjust them).** Digging never costs more than about 4 ms of game-thread time in a frame once commits are budgeted; a cave interior looks acceptable with local lights; navmesh updates stay within budget; the packaged build behaves like PIE; no collision gaps across chunk seams.

**Plugin gate at the start of stage 2.** Check whether Voxel Plugin 2 now lists UE 5.9, and get the budget cap and EULA in writing. If all three come back clean, spike the plugin instead. The likely total drops to about 16 days (section 3b) for $349, and stage 3 largely disappears. If not, carry on in-house.

**Decisions I need from you (my defaults in brackets)**
1. Are buildings and roads protected from digging? [Yes.]
2. How deep, and how many materials? [Bedrock 20 m down; topsoil, clay and rubble, stone, plus undiggable bedrock.]
3. Do you require a ray-tracing-capable GPU for cave lighting, or accept flat caves on others? [Require it, with software Lumen as a documented fallback.]
4. What is digging for: finds, tunnels and mines, ambush and hiding, a spell? [Open. It affects stages 4 and 5, not stage 3.]
5. Single-player only? [Yes, as the code is today (section 2.3).]

**Who builds what.** Claude builds everything except art generation, which Codex owns. Stage 3 is the one hard sub-task, so it is the one that would go on the strongest model. Stages 1 to 5 all edit `Source/`, and stages 2 to 5 need compiles and PIE time, so they have to be queued around the shared editor, the PIE lock and the build-train windows.

**What you give up by going full.** Dug ground is not Nanite, so it is the expensive part of every frame; Lumen is weak on it without hardware ray tracing; Mass crowds and PCG props have to be steered around dug ground (sections 4.3 and 4.4); and the project carries a bespoke terrain engine through every future UE upgrade.

### 7.2 If digging stays limited to a few places (the earlier recommendation)

These arguments were written before the goal became full digging. They still stand as the case for zones if the scope shrinks later.

**Build diggable zones (scope 4) in-house on Geometry Script and `UDynamicMeshComponent`, in this order, and stop at any gate that fails.**

1. **Build the dig-spot actor and a small save system first (scope 1, about 4–6 days).** It gives the game a dig verb, buried finds and story reveals right away. It is also the content layer for later zones and the fallback if the spike fails.
2. **Run a 2–3 day spike** on one 32 m zone with dynamic-mesh chunks, async collision, Lumen with hardware ray tracing, Virtual Shadow Maps and a dynamic navmesh all on, in a packaged build. Suggested pass marks (mine, to adjust): digging never costs more than about 4 ms of game-thread time in a frame once commits are budgeted; the cave interior looks acceptable with local lights; navmesh updates stay under budget; nothing differs in the packaged build.
3. **Then build one real zone (about 20 working days, 10–39).** A cellar, dig site or mine that the story actually wants.

**Why this and not the others**
- **Unreal 5.9 gives no way to dig the open ground.** Landscape editing, Landscape Patch and Mesh Terrain are editor-only, so every open-ground route means writing the terrain yourself.
- **A whole diggable world makes every knock-on global.** Navmesh, crowds, props and lighting all become your problem everywhere, and the research found no public benchmark or postmortem for UE5. Zones put those costs in one place you can test.
- **No plugin fits today.** Voxel Plugin 2 targets 5.6 and 5.7, is a preview, and has a budget cap and an EULA I could not confirm. Nothing else is both mature and licensed for a sold game on 5.9. An in-house zone adds no third-party licence to track, which suits a game you may sell.
- **The project is cheap to change right now.** The ground is cubes, there is no navmesh, crowd, PCG or save content to protect, and the NPC code is about to be rebuilt anyway. This is the least expensive moment to decide.

**Before any of this, settle what digging is for.** The answer picks the scope: finding buried things and making holes needs only scope 1; terraforming to hide or ambush needs scope 2; tunnels and mines need scope 4.

**Reconsider if:** the spike shows commits and cave lighting are fine and you still want digging across the whole town (the next step up is scope 2, a heightfield, at about 15 days, not scope 3); or the Voxel Plugin vendor publishes UE 5.9 support and confirms the budget cap and EULA in writing, in which case buying it for zone work becomes a fair comparison with the in-house route.

## 8. Sources

Raw research notes, with the verified-versus-inferred split for every claim: `C:\Users\zachc\AppData\Roaming\Claude\side-session-notes\local_cca9c984-ac0d-432b-a2bf-94457bab8cc7\research_notes\Digging feasibility\` (`heightfield.md`, `voxel_plugins.md`, `volumetric_inhouse.md`, `knockon_nav_mass_pcg.md`, `rendering_physics_save_perf.md`).

**This project (read from disk)**
- `reflections.uproject`, `Config/DefaultEngine.ini`, `Source/reflections/reflections.Build.cs`
- `Content/Maps/TestTown/L_TestTown.umap` (string and class-name scan)
- `Source/reflections/Hero/ReflectionsSpellAim.cpp`, `ReflectionsSpellCombat.h`, `ReflectionsSpellCatalog.h`, `ReflectionsSpellEventSubsystem.h`, `ReflectionsHeroCharacter.h`, `NPC/ReflectionsNpcCombatComponent.cpp`, `SpellVFX/ReflectionsSpellVfxSubsystem.cpp`
- `ArtDirection/NpcBehavior/Plan.md`, `ArtDirection/Submission/THIRD_PARTY_NOTICES.txt`, `README.md`
- Git history: commit `7e3f44ee` (the 2026-11-21 reset)

**UE 5.9 engine source and plugin descriptors** (`C:\Program Files\Epic Games\UE_5.9\Engine`)
- `Plugins/Experimental/MeshPartition/` (`MeshPartition.uplugin`, `Source/MeshPartition/Public/MeshPartitionCompiledSection.h`), `Plugins/Experimental/MeshTerrainMode/`, `PCGPrimitives_MeshPartitionInterop`, `PCGPrimitives`, `Plugins/Editor/LandscapePatch/Source/LandscapePatch/Public/LandscapePatchComponent.h`
- `Plugins/Runtime/GeometryScripting/`, `Plugins/Runtime/GeometryProcessing/`, `Source/Runtime/GeometryFramework/Public/Components/DynamicMeshComponent.h` and `BaseDynamicMeshComponent.h`, `Source/Runtime/GeometryCore/Public/Generators/MarchingCubes.h`
- `Source/Runtime/NavigationSystem/Public/NavMesh/RecastNavMesh.h`
- `Plugins/Runtime/ZoneGraph/Source/ZoneGraph/Private/ZoneGraphData.cpp`, `Plugins/AI/MassCrowd/Source/MassCrowd/Private/MassCrowdSubsystem.cpp`
- `Source/Runtime/Engine/Private/PhysicsEngine/BodySetup.cpp`

**Epic documentation and posts**
- [UE 5.9 release notes (Preview)](https://dev.epicgames.com/documentation/unreal-engine/unreal-engine-5-9-release-notes)
- [Geometry Scripting user's guide](https://dev.epicgames.com/documentation/en-us/unreal-engine/geometry-scripting-users-guide-in-unreal-engine)
- [Lumen technical details](https://dev.epicgames.com/documentation/en-us/unreal-engine/lumen-technical-details-in-unreal-engine) and [Lumen performance guide](https://dev.epicgames.com/documentation/en-us/unreal-engine/lumen-performance-guide-for-unreal-engine)
- [Nanite virtualized geometry](https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine), [Nanite with landscapes](https://dev.epicgames.com/documentation/en-us/unreal-engine/using-nanite-with-landscapes-in-unreal-engine), [Nanite tessellation and displacement](https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-tessellation-and-displacement-in-unreal-engine)
- [Virtual Shadow Maps](https://dev.epicgames.com/documentation/en-us/unreal-engine/virtual-shadow-maps-in-unreal-engine), [Ray tracing performance guide](https://dev.epicgames.com/documentation/en-us/unreal-engine/ray-tracing-performance-guide-in-unreal-engine)
- [Optimizing navigation mesh generation speed](https://dev.epicgames.com/documentation/unreal-engine/optimizing-navigation-mesh-generation-speed-in-unreal-engine), [PCG generation modes](https://dev.epicgames.com/documentation/en-us/unreal-engine/using-pcg-generation-modes-in-unreal-engine)
- [Landscape Patch system](https://dev.epicgames.com/documentation/unreal-engine/landscape-patch-system?lang=en-US), [Mesh Terrain in Unreal Engine](https://dev.epicgames.com/documentation/unreal-engine/mesh-terrain-in-unreal-engine?lang=en-US)
- [Epic Unreal Engine licence and royalty terms](https://www.unrealengine.com/license), [Fab EULA](https://www.fab.com/eula)

**Forum threads (anecdotal unless stated)**
- [Runtime landscape editing in a shipping build](https://forums.unrealengine.com/t/is-it-possible-to-edit-the-landscape-in-the-shipping-version/2663539)
- [Does 5.8 Mesh Terrain support runtime terrain in a packaged build?](https://forums.unrealengine.com/t/does-5-8-mesh-terrain-support-creation-of-a-terrain-at-runtime-in-a-packaged-build/2730244) and [Introduction to Mesh Terrain](https://forums.unrealengine.com/t/knowledge-base-introduction-to-mesh-terrain/2707493)
- [UE-380849: wrong collision in 5.9 Preview 1](https://forums.unrealengine.com/t/5-9-preview-1-ue-380849-now-causes-wrong-collision-not-only-non-deterministic-cooks/2857211)
- [Lumen support for dynamic meshes](https://forums.unrealengine.com/t/looks-like-lumen-support-for-dynamic-meshes-is-coming-possibly-in-ue-5-5/1951349), [Nanite and Lumen on dynamic meshes](https://forums.unrealengine.com/t/will-dynamic-mesh-support-luman-nanite/2638551)
- [Dynamic navmesh with procedural mesh components](https://forums.unrealengine.com/t/dynamic-navmesh-not-updating-properly-with-changing-procedural-mesh-component/1900877), [ZoneGraph quick-start guide](https://forums.unrealengine.com/t/tutorial-zonegraph-quick-start-guide/573924)
- [Chaos async acceleration-queue flush hitch](https://forums.unrealengine.com/t/hitch-in-flushasyncaccelerationqueue-by-numerous-calls-to-applyparticlependingdata/2737440)
- [Geometry Script boolean performance](https://forums.unrealengine.com/t/geometry-script-boolean-operation-performance/2684577), [dynamic mesh chunk test](https://forums.unrealengine.com/t/instanced-static-mesh-performance-issues/1769521)

**Voxel plugins, licences and open source** (all seen 2026-11-21)
- [Voxel Plugin docs](https://docs.voxelplugin.com/), [licensing page](https://docs.voxelplugin.com/resources/licensing.html), [runtime edits and sculpting](https://docs.voxelplugin.com/knowledgebase/blueprints/runtime-edits-and-sculpting.html), [collision, navmesh and invokers](https://docs.voxelplugin.com/knowledgebase/blueprints/collision-navmesh-and-invokers.html), [multiplayer](https://docs.voxelplugin.com/knowledgebase/blueprints/multiplayer-support.html), [vendor site](https://voxelplugin.com/)
- [Voxel Plugin Pro Legacy on Fab](https://www.fab.com/listings/5c85f2f0-cf03-4860-b22e-e4f470af4133), [Voxel Plugin 2 announcement](https://80.lv/articles/voxel-plugin-2-for-unreal-engine-5-announced/), [runtime Nanite geometry article](https://80.lv/articles/a-cool-setup-for-generating-nanite-geometry-in-ue5-at-runtime)
- [Realtime Mesh Component Pro on Fab](https://www.fab.com/listings/c04e6977-a3bd-4e24-b0a2-0b696bee90da), [Voxel Farm](https://voxelfarm.com/gaming.html)
- GitHub: [UnrealSandboxTerrain (GPL-3.0)](https://github.com/bw2012/UnrealSandboxTerrain), [VoxelPluginFreeLegacy](https://github.com/VoxelPlugin/VoxelPluginFreeLegacy), [VoxelCore (MIT)](https://github.com/VoxelPlugin/VoxelCore), [TerraDyne (MIT)](https://github.com/gregorik/TerraDyne), [InstantOrganicCaves (MIT)](https://github.com/gregorik/InstantOrganicCaves), [ue5-voxel (MIT)](https://github.com/1polygon/ue5-voxel)
- [TerraDyne thread](https://forums.unrealengine.com/t/gregorigin-terradyne-unified-runtime-terrain-sculpting-with-real-time-physics/2699018), [Orbdale Terrain thread](https://forums.unrealengine.com/t/orbdale-orbdale-terrain/2857059)

**Reference class and technique**
- [Astroneer postmortem (Game Developer)](https://www.gamedeveloper.com/design/what-i-astroneer-i-s-devs-learned-while-leaving-early-access), [Astroneer multiplayer blog](https://blog.astroneer.space/p/day-1-multiplayer-and-beyond/)
- [Deep Rock Galactic cave generation (Ghost Ship devlog)](https://devtrackers.gg/deep-rock-galactic/p/8cd5ca9c-below-decks-at-ghost-ship-cave-generation-in-deep-rock-galactic)
- [Transvoxel](https://transvoxel.org/), [Smooth voxel terrain, part 2](https://0fps.net/2012/07/12/smooth-voxel-terrain-part-2/), [Godot Voxel Tools performance](https://voxel-tools.readthedocs.io/en/latest/performance/)
- [Steam hardware survey](https://store.steampowered.com/hwsurvey/)
