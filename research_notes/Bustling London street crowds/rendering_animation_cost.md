# Rendering and animation techniques for cheap background crowds in UE5 (100-500+ visible pedestrians)

Scope note: Target engine is UE 5.9. Epic doc pages fetched for Animation Budget Allocator, Animation Sharing, Animation Optimization and Nanite were all labelled "Unreal Engine 5.9 Documentation" when fetched (Nov 2026). The MetaHuman Crowds pages carry no version label but link to 5.8 docs and describe 5.8-era features. Reliability is graded inline: **[Official]** = Epic docs or Epic staff in forums; **[Measured-anecdotal]** = a user's own profiling on their hardware; **[Asserted]** = a claim with no measurement behind it.

---

## 1. Vertex Animation Textures (VAT) / AnimToTexture: how it works, workflow, limits, cost, and City Sample usage

### Takeaway
AnimToTexture bakes skeletal animation into textures that a material plays back on (H)ISM static meshes. Epic used it in City Sample for every pedestrian except about 8 full skeletal actors. It moves the crowd cost off the game and render threads, but the cost lands on the GPU vertex work in the base and shadow passes. Its weak points are blending, LOD, motion vectors/TAA, attachments, and Nanite. Epic now (5.8+) recommends Instanced Skinned Mesh (ISKM) + AnimSequenceTransformProvider over VAT for new crowd work, though that path is new and still buggy.

### Cited Findings
- **Origin / version:** AnimToTexture shipped with the UE5 City Sample and became an engine plugin in UE 5.1. In City Sample, "the background characters in crowds are static meshes with vertex animation in the materials." — [Forum: AnimToTexture community tutorial](https://forums.unrealengine.com/t/community-tutorial-animtotexture-plugin-how-to-use-it-to-make-vertex-animation-textures-for-crowds/746648); [Forum: How to use CitySample BP_AnimToTexture](https://forums.unrealengine.com/t/how-to-use-citysample-bp-animtotexture/540208)
- **City Sample split [Official, Epic staff]:** City Sample uses "roughly 8 full actors and vertex animation (VAT) for the rest." The same Epic staffer said skeletal mesh "wasn't designed for 100+ on-screen components" and recommended a few full MetaHuman actors with the rest as Mass entities. — [Forum: MetaHuman skin cache retains LOD0 entries (Epic staff Euan_Carmichael, May 2026)](https://forums.unrealengine.com/t/metahuman-skin-cache-retains-lod0-entries-for-every-npc-regardless-of-camera-distance/2728166)
- **Mass representation tiers [Official]:** Mass representations include a low-resolution Actor, an Instanced Static Mesh (ISM), and none. The ISM is "the cheapest way of representing the Actor and it can be moved and animated using vertex animation," and the docs point to City Sample as the reference. — [Epic: Overview of Mass Gameplay](https://dev.epicgames.com/documentation/en-us/unreal-engine/overview-of-mass-gameplay-in-unreal-engine)
- **Community description of the Mass tiers:** MassRepresentation moves between skeletal mesh (near), static mesh (mid), instanced static mesh (far), and culled (very far). — [StraySpark: Crowd & traffic simulation with Mass AI](https://www.strayspark.studio/blog/crowd-traffic-simulation-ue5-mass-ai) (third-party blog)
- **VAT concept:** VAT stores baked positions per frame in a texture and can be "dramatically cheaper when bone-level detail isn't needed." — [MocapOnline: Open World Game Animation guide](https://mocaponline.com/blogs/mocap-news/open-world-game-animation-guide)
- **Workflow details from the community tutorial (UE 5.1):**
  - An Editor Utility tool drives the bake. A crowd instancer Blueprint scatters the static mesh with its VAT texture and gives each instance a random animation.
  - Per-instance custom data worked only when set in a separate loop after all instances were created. Setting it in the creation loop failed.
  - Choppy, stepped motion was fixed by switching to 16-bit precision and enabling "Force Power of Two" on the texture. The default R8G8B8A8 output was the likely cause; the author thinks non-power-of-two textures fall back to 8-bit.
  - Static meshes have no sockets, so attachments (props, hats) would have to follow a vertex.
  - On mobile, characters showed in T-pose; the thread has no fix.
  - The thread also links a reported TAA ghosting problem on vertex-animated meshes.
  — [Forum: AnimToTexture community tutorial](https://forums.unrealengine.com/t/community-tutorial-animtotexture-plugin-how-to-use-it-to-make-vertex-animation-textures-for-crowds/746648)
- **Version breakage [Measured-anecdotal]:**
  - 5.2: users reported a missing "Param Names" node and that texture generation failed.
  - 5.3: an "Animation To Texture failed" error.
  - 5.5: "some nodes are lost and the material does not work."
  - 5.5: crowd instancing with multiple static meshes didn't apply animation properly (thread title).
  — [Forum: AnimToTexture tutorial replies](https://forums.unrealengine.com/t/community-tutorial-animtotexture-plugin-how-to-use-it-to-make-vertex-animation-textures-for-crowds/746648); [Forum: UE 5.5 AnimToTexture crowd instancing with multiple static meshes](https://forums.unrealengine.com/t/unreal-5-5-animtotexture-crowd-instancing-with-multiple-static-meshes-not-applying-anim-properly/2495702)
- **Community helper assets:** kromond/AnimToTextureHelpers provides an Editor Utility Widget to build VAT assets and a BP_Crowd instancer. It targets 5.2, with contributor updates for 5.3/5.4, and is offered as "a demonstration or example only." — [GitHub: kromond/AnimToTextureHelpers](https://github.com/kromond/AnimToTextureHelpers)
- **GPU cost [Measured-anecdotal, no ms given]:** About 200 AnimToTexture ISM characters in an empty scene could not hold 60 fps on an RTX 3060 Mobile or an RTX 2060 Super. Game and render threads were relieved, but the GPU became the bottleneck in BasePass and ShadowDepths. The poster suspects the vertex-shader animation runs again in every pass, including each shadow pass. — [Forum: AnimToTexture putting pressure on BasePass and ShadowDepths](https://forums.unrealengine.com/t/animtotexute-is-putting-pressure-on-basepass-and-shadowdepths/1145774)
- **LOD limitation [anecdotal]:** "You can't use LODs with VAT in large crowd scenes, because you are changing the vertex count" (no answer in thread). — [Forum: Vertex animation and LODs](https://forums.unrealengine.com/t/vertex-animation-and-lods/233479)
- **Nanite + VAT bug [anecdotal]:** With Nanite enabled on AnimToTexture crowd assets, deformation looks correct on placed static meshes but stretches when driven by Mass. — [Forum: Enabling Nanite on AnimToTexture crowd assets causes stretched VAT animations](https://forums.unrealengine.com/t/enabling-nanite-on-animtotexture-crowd-assets-causes-stretched-vat-animations/2623531)
- **Mutable / runtime-composed characters [Official, Epic staff]:** VAT needs offline-baked bone textures, so Mutable would have to generate merged meshes in the editor first. ISKM transform providers can be generated dynamically. — [Forum: MetaHuman skin cache thread (Epic staff)](https://forums.unrealengine.com/t/metahuman-skin-cache-retains-lod0-entries-for-every-npc-regardless-of-camera-distance/2728166)
- **Epic's current recommendation [Official, Epic staff, June 2026]:**
  - The recommended approach is Mass + ISKM + **AnimSequenceTransformProvider**, which generates GPU-formatted animation data similar to AnimBank, adds per-instance variation, and allows simple retargeting to similar skeletons.
  - Epic considers the ISKM workflow benefits "stronger than VAT's" but warns these are new features and bugs are possible.
  - ISKM inherits from Skinned Mesh Component, so "there's no support for anim blueprint with those components."
  — [Forum: AnimBank and Instanced Skinned Mesh Component](https://forums.unrealengine.com/t/animbank-and-instanced-skinned-mesh-component/2734825)
- **Known ISKM bugs on 5.8 (thread titles only, not read in full):**
  - Mass crowds using SkinnedMeshInstance leak GPU memory; each spawn/kill wave permanently grows the animation track pool (5.8).
  - ISKM permanently renders the reference pose when chunks fall outside the scene-culling cell hierarchy (5.8.1).
  — [Forum: SkinnedMeshInstance GPU memory leak 5.8](https://forums.unrealengine.com/t/mass-crowds-using-skinnedmeshinstance-leak-gpu-memory-every-wave-of-spawned-and-killed-entities-permanently-grows-the-animation-track-pool-5-8/2742508); [Forum: ISKM renders reference pose outside culling hierarchy](https://forums.unrealengine.com/t/instanced-skinned-meshes-permanently-render-reference-pose-when-their-chunks-fall-outside-the-scene-culling-cell-hierarchy-uncullable-range-stale-chunk-attributes/2743519)
- **Earlier Epic stance on ISKM:** An Epic engineer earlier described ISKM as "very much under early development and isn't suitable for use at this moment." This is a pre-5.8 statement, superseded by the June 2026 recommendation above; I could not pin which of the linked threads holds the quote. — [Forum: AnimBank & InstancedSkinnedMeshComponent](https://forums.unrealengine.com/t/animbank-instancedskinnedmeshcomponent/2691277)
- **Third-party VAT crowd tools exist:**
  - JBernardic Vertex Animation Toolkit: bakes skeletal animation to VAT for ISM and adds crowd movement.
  - OverCrowd: auto-converts modular characters to VAT characters.
  - The older "Vertex Anim Toolset" supported only UE 4.22–4.26 and appears discontinued.
  — [Forum: JBernardic VAT Toolkit](https://forums.unrealengine.com/t/jbernardic-vertex-animation-toolkit-crowd-movement/2840895); [Forum: OverCrowd](https://forums.unrealengine.com/t/overcrowd-overcrowd-massive-crowd-simulation/2669477); [Marketplace: Vertex Anim Toolset](https://www.unrealengine.com/marketplace/ja/product/vertex-anim-toolset)
- **Community sentiment [anecdotal]:** One UE 5.1 user found City Sample crowds cost about 10 FPS more than a home-grown crowd of Manny characters. — [Forum: City Sample Crowds for UE 5.1](https://forums.unrealengine.com/t/city-sample-crowds-for-ue-5-1/882197)

### Inferences
- **Bone mode vs vertex mode.** This comes from general engine knowledge and was not re-verified in a fetched doc this session. AnimToTexture has two modes:
  - Vertex mode stores per-vertex offsets and normals per frame. Texture size scales with vertex count × frame count, so it is only practical for low-vertex meshes or short clips.
  - Bone mode stores per-bone transforms per frame. Bone indices and weights are written into extra UV channels of the baked static mesh, and the material skins in the vertex shader. Texture size scales with bone count × frame count, which is tiny.
  - For pedestrians, use **bone mode**.
- **Texture memory, derived arithmetic (assumes RGBA16F at 8 B/texel, two textures for position and rotation; verify against the actual asset):**
  - Bone mode, 70-bone skeleton × 1,000 total baked frames (for example 8 clips of about 4 s at 30 fps): 70 × 1,000 × 8 B × 2 ≈ **1.1 MB**. That is negligible for the 1 GB package.
  - Vertex mode, a 10k-vertex body over the same 1,000 frames: 10,000 × 1,000 × 8 B × 2 ≈ **160 MB**. Not viable.
- **Bone-mode VAT can use mesh LODs.** The "can't use LODs" complaint applies to vertex-mode VAT. Bone-mode textures are indexed by bone, not vertex, so LOD meshes that keep the same bone indices in their UVs should work. This is unverified for AnimToTexture's import path; test it.
- **Blending is the core quality limit.** A VAT instance plays one baked clip at a per-instance time offset. Cross-fading two clips doubles texture fetches in the vertex shader. Walk-to-idle transitions, turning and stopping need either baked transition clips or must hide behind a hand-off to a skeletal or ISKM tier.
- **Background pedestrians that only walk straight or loiter suit VAT well:** about 4–8 clips (walk ×2 speeds, idle ×2, phone/talk idle, look-around), each with random time offsets.
- **Per-instance custom data on HISM/ISM drives variation:** animation index, time offset, play rate, and colour tints. The forum workaround (set it after creation) matters.
- **Motion vectors and TAA/TSR ghosting.** VAT uses World Position Offset (WPO). Unless the material also computes the previous-frame position (Epic's material functions may or may not do this; unverified), TAA/TSR will smear. That matches the reported ghosting. Check "Output velocity" / WPO-velocity project settings.
- **Shadows can dominate GPU cost.** The VAT vertex shader re-runs in every shadow-casting pass, and with Virtual Shadow Maps, WPO meshes invalidate cached pages every frame. Common mitigations, untested here:
  - Disable shadow casting on far VAT LODs, or use a capsule or contact-shadow blob instead.
  - Set "WPO disable distance" so very far instances freeze.
  - Keep far VAT meshes at about 1–4k vertices.
- **Package and memory:** A VAT tier built from a few MetaHuman "Optimized Low" bodies and heads with bone-mode textures adds only megabytes. Each unique baked mesh variant is a small static mesh plus shared textures.
- **For the user's project:** The hidden-walker leader-pose architecture maps cleanly onto a Mass-style hand-off. Near pedestrians use the walker + MetaHuman, mid ones use ISKM or VAT, far ones use impostors or are culled. The walker skeleton's clips are exactly what would be baked or fed to AnimSequenceTransformProvider.

### Gaps
- No measured "ms per 1,000 VAT instances" figure from any reliable source. The only data point is the qualitative 200-instance GPU-bound report on mobile-class RTX GPUs.
- No official Epic doc page for the AnimToTexture plugin was found. Field names (bone vs vertex mode, precision, sample rate) and texture layout are not verified against a 5.9 doc.
- Whether AnimToTexture's material functions output correct previous-frame positions for motion vectors is unconfirmed.
- City Sample's exact LOD distances and VAT mesh triangle counts were not found in any write-up.
- No confirmation that the 5.5 broken-node issues are fixed in 5.8/5.9.

---

## 2. Animation Sharing plugin and Animation Budget Allocator: what they do, setup, savings, caveats with leader pose / MetaHumans

### Takeaway
Both are official, engine-shipped (5.9-documented) game-thread animation savers for crowds that stay skeletal-mesh based.
- **Animation Sharing** evaluates a few animation states once and drives many characters through Leader Pose.
- **Animation Budget Allocator** caps total animation tick time in milliseconds and throttles less significant meshes.

Neither touches render or GPU cost (skinning, grooms, draw calls). Epic says Animation Sharing is "much slower than the ISKM approach." They suit tens of close and mid pedestrians, not hundreds.

### Cited Findings
- **Animation Budget Allocator: what it does [Official, 5.9 doc]:**
  - Limits game-thread animation time by throttling Skeletal Mesh Component ticking.
  - Favours the closest, most significant meshes and lowers the update rate or quality of the rest.
  - Its tools are stopping ticks on individual components "favoring any Leader Pose Component," updating at a lower rate, and optional interpolation between updates.
  — [Epic: Animation Budget Allocator](https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-budget-allocator-in-unreal-engine)
- **Setup [Official]:**
  1. Enable the plugin and restart the editor.
  2. Set the mesh Component Class to `SkeletalMeshComponentBudgeted`, or override the subobject in C++.
  3. Enable **Auto Calculate Significance** and **Auto Register with Budget Allocator**.
  4. Call **Enable Animation Budget** at Begin Play.

  Both the node and the `a.Budget.Enabled` CVar must be on. — [Epic: Animation Budget Allocator](https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-budget-allocator-in-unreal-engine)
- **Defaults [Official]:**

  | CVar | Default | Note |
  |---|---|---|
  | `a.Budget.BudgetMs` | 1.0 | per-frame game-thread budget |
  | `a.Budget.MinQuality` | 0.0 | values above 0 can exceed the budget |
  | `a.Budget.MaxTickRate` | 10 | |
  | `a.Budget.InterpolationMaxRate` | 6 | |
  | `a.Budget.MaxInterpolatedComponents` | 16 | |
  | `a.Budget.MaxTickedOffscreen` | 4 | |
  | `a.Budget.InitialEstimatedWorkUnitTime` | 0.08 ms | |

  The budget can be set per View Distance Quality in `DefaultScalability.ini`; the doc example uses 1.0/1.5/2.0/2.5 ms for levels 0–3. — [Epic: Animation Budget Allocator](https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-budget-allocator-in-unreal-engine)
- **Caveats [Official]:**
  - The C++ `RegisterComponent` call disables the default tick function **and URO** on that component, so the allocator replaces URO rather than stacking with it.
  - Modular characters show debug info per component.
  - Debug with `a.Budget.Debug.Enabled` and Stat > Advanced > AnimationBudgetAllocator.
  — [Epic: Animation Budget Allocator](https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-budget-allocator-in-unreal-engine)
- **Savings figures [Measured-anecdotal, qualitative]:** With 32 MetaHumans (LOD0 forced, groom cards), the allocator at default settings gave a "BIG game thread improvement" (screenshots, no ms in text; UE 5.4 Preview). — [Forum: The new 3.0 MetaHumans, 40% performance gains](https://forums.unrealengine.com/t/the-new-3-0-metahumans-40-performance-gains-tutorial-inside/1777726)
- **Interpolation caveat [anecdotal]:** One user found anim-graph evaluation "very expensive" and that budget interpolation did not appear to run on worker threads in their traces. Others reported `a.budget.Enable`-style commands not working for them. — [Forum: AnimationBudgetAllocator doesn't utilize interpolation](https://forums.unrealengine.com/t/animationbudgetallocator-doesnt-utilize-interpolation-on-registered-components-and-it-feels-like-framerate-drop-what-is-a-proper-way-to-address-it/2663219)
- **Animation Sharing: what it does [Official, 5.9 doc]:**
  - Evaluates a small set of animation states once and shares poses with many characters through the **Leader Pose Component** system.
  - Each state is a bucket of animation instances. Randomised start times and blended transitions add variety, and on-demand additive animations are supported.
  — [Epic: Animation Sharing Plugin](https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-sharing-plugin-in-unreal-engine)
- **Setup [Official]:**
  1. Create an AnimationSharingSetup asset with per-skeleton setups: Skeleton, Skeletal Mesh, and blend and additive AnimBPs.
  2. Create a state Enumeration.
  3. Create an AnimationSharingStateProcessor. The Blueprint version "should only be used for prototyping"; native is faster.
  4. Add states with Num Randomized Instances.
  5. Build the AnimSharingTransitionInstance, AnimSharingAdditiveInstance and AnimSharingStateInstance AnimBPs.
  6. Register each actor with the Animation Sharing Manager at Begin Play.
  — [Epic: Animation Sharing Plugin](https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-sharing-plugin-in-unreal-engine)
- **Scalability knobs [Official]:**
  - Blend Significance Value.
  - Maximum Number Concurrent Blends: excess blends snap to the nearest pose. Each blend spawns an AnimBP at runtime, which adds cost.
  - Tick Significance Value: actors above it are not ticked; tied to the Significance Manager.
  - Per-platform Maximum Number Of Concurrent Instances.
  - "Requires Curves" must be on for curves and morph targets to reach follower components.
  — [Epic: Animation Sharing Plugin](https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-sharing-plugin-in-unreal-engine)
- **Performance claim [Official, qualitative only]:** Going from 100 to 1,000 characters is described as a "minimum increase in performance cost"; no numbers are given. The page never mentions MetaHumans. — [Epic: Animation Sharing Plugin](https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-sharing-plugin-in-unreal-engine)
- **Epic positioning [Official, Epic staff, 2026]:** Animation Sharing is the option when you need pure instancing of skeletal meshes with anim blueprints, but its performance is "going to be much slower than the ISKM approach." — [Forum: AnimBank and ISKM](https://forums.unrealengine.com/t/animbank-and-instanced-skinned-mesh-component/2734825)
- **URO [Official, 5.9 doc]:** Epic recommends "Update Rates that perform at 15Hz and under, at appropriate distances, for most characters," and disabling interpolation. Enable it with **Enable Update Rate Optimizations** on the Skeletal Mesh Component. The page suggests the Budget Allocator as an alternative. — [Epic: Animation Optimization](https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-optimization-in-unreal-engine)

### Inferences
- **Fit with the user's walker + leader-pose MetaHumans:**
  - Animation Sharing removes the per-pedestrian walker AnimBP. N pedestrians follow M shared state actors (for example 3 walk variants + 2 idles, each with a few randomised instances), so animation-graph cost becomes roughly constant.
  - Per-character foot IK, look-at, and turn-in-place are lost unless an additive or on-demand state covers them.
  - Feet will slide if movement speed doesn't match the shared clip's speed.
- **MetaHuman faces are a separate AnimBP/RigLogic evaluation**, not covered by body leader-pose sharing. Background pedestrians should disable face animation and RigLogic entirely, or use a static face LOD. This is inferred from MetaHuman architecture, not from a fetched doc.
- **Budget Allocator as the safety net for the near/mid skeletal tier:** give the 10–30 nearest skeletal pedestrians a hard budget of about 1–2 ms game thread. With the user's measured ~0.5 ms per foreground MetaHuman in PIE, 1 ms buys only about 2 full-rate MetaHumans, so the allocator will aggressively drop tick rates. That reinforces putting most pedestrians on ISKM/VAT. (The PIE figure is the user's; packaged builds are typically cheaper.)
- **Throttled pedestrians at 10 Hz with interpolation look fine past about 15–20 m.** Without interpolation they look choppy, so keep interpolation for mid-distance skeletal pedestrians and accept its main-thread cost.
- **These tools save only game-thread and worker animation time.** Render-thread cost per skeletal component (proxies, skin cache, grooms) is untouched; see section 3.

### Gaps
- No measured ms savings for either plugin from Epic or from a rigorous third-party benchmark.
- No source discusses Animation Sharing with MetaHuman multi-mesh characters (body + face + clothes + grooms) or how it interacts with an existing leader-pose hierarchy.
- No source confirms whether the Budget Allocator correctly budgets follower components in a leader-pose chain. The doc only says Leader Pose Components are favoured.

---

## 3. Skeletal mesh LOD strategies for crowds: LOD counts, URO, visibility-based tick, physics/cloth/groom at distance, MetaHuman LOD sync, optimized MetaHumans, grooms vs cards

### Takeaway
A full MetaHuman is the wrong primitive for a background pedestrian, even at low LOD. Every character carries several skeletal components, a groom with per-component render-thread and VRAM cost that never streams out, skin-cache memory, and correctives. Epic's two answers:
- **"UE Optimized – Low" MetaHumans:** cards only, no correctives, no RBAN, no SSS, max 2K textures.
- **The experimental MetaHuman Crowds pipeline (5.8):** strips LODs, converts grooms to skeletal-mesh cards, and renders distant characters as ISKM.

Merging meshes, rigid groom bindings, disabled hair simulation, forced low LODs, and URO/budgeting are the main levers for whatever skeletal tier remains.

### Cited Findings
- **MetaHuman LOD specification [Official]:**

  | Part | LOD0 | LOD1 | LOD2 | LOD3 | Lower LODs |
  |---|---|---|---|---|---|
  | Head vertices | 24,000 | 12,000 | 6,000 | 2,500 | LOD4 1,300 → LOD7 130 |
  | Head joints | 713 | 529 | 397 | 283 | LOD4 84 → LOD7 26 |
  | Body vertices | 30,500 | 7,600 | 3,350 | 1,507 | body ends at LOD3 |
  | Hair | strands 50,000 / cards 30k verts | strands 25,000 | cards only | cards only | cards to LOD4; mesh hair LOD5–7 (500/250/100 verts) |

  - Head blendshapes exist only at LOD0 (669). Animated maps run only at LOD0–1. Body correctives run only at LOD0–1.
  - Hair physics runs on LOD0–2.
  - On mobile the best LOD is LOD3 with 2048 textures.
  — [Epic: Platform support and LOD specifications for MetaHumans](https://dev.epicgames.com/documentation/en-us/metahuman/platform-support-and-lod-specifications-for-metahumans)
- **UE Optimized assembly tiers [Official]:**
  - "UE Optimized" is for when performance matters more than visual quality. Its highest texture resolution is 2K, and it comes in High, Medium or Low.
  - Medium suits 3–4 characters at a reasonable distance.
  - **Low** suits "crowd shots or background characters": hair cards only, no correctives, no physics (RBAN), SSS disabled, animated maps disabled.
  - Between Cinematic and High, "the most prominent difference is the file size."
  - Further tuning is done through the MetaHuman Component and the LODSync Component.
  — [Epic: MetaHuman Assembly](https://dev.epicgames.com/documentation/metahuman/assembly)
- **MetaHuman Crowds pipeline [Official, Experimental]:**
  - Strand grooms are converted to skeletal meshes with card textures, with no strand detail and no hair physics.
  - Higher-detail LODs are stripped, keeping only those needed for typical crowd distances; this is adjustable in the Collection build settings.
  - Distant characters use the **Instanced Skinned Mesh Component**, which does not run the post-process AnimBP, so correctives are not applied.
  - The feature is marked "Experimental… use caution when shipping with it."
  — [Epic: MetaHuman Crowds](https://dev.epicgames.com/documentation/metahuman/metahuman-crowds-in-unreal-engine)
- **MetaHuman Crowds setup controls [Official]:**
  - Mass Entity framework with a MetaHumanMassSpawner and BP_CrowdPipeline.
  - Per-LOD distance thresholds: full actor → instanced → stop rendering.
  - Max counts per LOD. Example: "10 full-quality actors at close range but hundreds of instanced characters at a distance."
  - Animation scalability: timing variety, number of simultaneous blends, blend duration.
  - Spawning Count Scale per platform.
  - Instance parameters such as hair colour and clothing tint.
  - "The LOD behavior and animation scalability settings are your primary performance controls."
  — [Epic: Create MetaHuman Crowds](https://dev.epicgames.com/documentation/metahuman/create-metahuman-crowds-in-unreal-engine)
- **Scale claim [Asserted, press]:** MetaHuman crowds scale "up to hundreds of characters on mobile and thousands on higher-end platforms." — [GamesBeat: MetaHuman 5.8 crowds](https://gamesbeat.com/?p=326758)
- **Groom render-thread cost [Measured-anecdotal, UE 5.7, Epic staff engaged]:** 50 MetaHumans sharing one cards-only groom, High scalability, 58% screen percentage, average render thread:

  | Configuration | Render thread |
  |---|---|
  | Skinned bindings (default) | ~10.03 ms |
  | Rigid bindings | ~7.12 ms |
  | No bindings (attached component) | ~7.24 ms |
  | No hair at all | ~4.29 ms |

  - That is roughly 6 ms for hair on 50 characters, about 0.12 ms each, even as cards.
  - Epic staff endorsed rigid binding at lower LODs and disabling simulation.
  - Epic staff noted the default MetaHuman hair shader uses dithering and pixel depth offset, which can defeat early-Z, and suggested simplifying the material.
  — [Forum: High render thread cost of groom bindings](https://forums.unrealengine.com/t/high-render-thread-cost-of-groom-bindings-even-on-rigid-mode/2725272)
- **Groom VRAM [Measured-anecdotal + Epic staff]:**
  - About 800 MB of VRAM for grooms on 50 active MetaHuman NPCs (RTX 3070): roughly 400 MB asset data + 400 MB runtime hair buffers, about 25% of the budget.
  - Groom data stays resident regardless of distance or LOD.
  - Epic: "There is no plan for cards to have streaming pool at this time."
  - Guide buffers are allocated only if simulation or RBF interpolation is on. Root buffers are allocated only if any LOD uses skinning binding, so rigid binding avoids them.
  - No crowd-specific groom code exists yet ("working on it, no ETA").
  — [Forum: Groom LOD data remains fully resident in VRAM](https://forums.unrealengine.com/t/groom-lod-data-remains-fully-resident-in-vram-regardless-of-distance-lod-level/2715458)
- **Groom GPU cost [Measured-anecdotal]:** Card interpolation cost over 2 ms GPU for 50+ groom instances. The suggested fix is removing simulation/RBF on card LODs and using rigid binding. — [Forum: Expensive Hair Cards](https://forums.unrealengine.com/t/expensive-hair-cards/2691281)
- **Strands vs cards [Official + anecdotal]:**
  - The groom asset has a "Use Cards" option that forces card/mesh geometry. — [Epic: Groom components and assets](https://dev.epicgames.com/documentation/unreal-engine/groom-components-and-assets-in-unreal-engine)
  - One user reported a stable 45–55 FPS after forcing cards with `r.HairStrand.Strands 0`. — [Forum: Optimizing MetaHumans 5.2.1](https://forums.unrealengine.com/t/optimizing-metahumans-5-2-1/1327489)
  - A university VR wiki says hair has "the largest impact on performance" for MetaHumans. — [RWTH VR wiki: Using MetaHumans in VR](https://git-ce.rwth-aachen.de/vr-vis/unreal-wiki/-/wikis/Unreal/Using-MetaHumans-in-VR)
- **Skin cache memory [Measured-anecdotal, Epic staff replied]:**
  - 50 bald MetaHumans used about 137 MB of GPU skin cache from a far camera and about 142 MB at moderate distance.
  - Forcing LOD3 dropped it to about 31 MB.
  - Epic says the skin cache does evict on LOD change and that editor dumps include other scenes; verify in a packaged build with `r.SkinCache.PrintMemorySummary`.
  — [Forum: MetaHuman skin cache retains LOD0 entries](https://forums.unrealengine.com/t/metahuman-skin-cache-retains-lod0-entries-for-every-npc-regardless-of-camera-distance/2728166)
- **Correctives, mesh merging and bone stripping [Measured-anecdotal, UEFN/UE 5.4]:**
  - Disabling correctives in the MetaHuman 3.0 component gave about 40% higher editor FPS (Ryzen 5800X / RTX 4070 Ti Super). Body correctives were about 90% of that.
  - The Skeletal Mesh Merge plugin gave "ridiculous gains" because the default MetaHuman ticks 5 skeletal meshes per character and a merged mesh ticks 1.
  - Python-stripping finger bones (22 → 8 per finger) cut LOD0 bones by about 60% while keeping about 90% of perceived deformation.
  — [Forum: The new 3.0 MetaHumans, 40% performance gains](https://forums.unrealengine.com/t/the-new-3-0-metahumans-40-performance-gains-tutorial-inside/1777726)
- **Other per-component levers [Official, 5.9 doc]:**
  - Move AnimBP logic to Thread Safe update functions and keep AnimGraph on the Fast Path (no Blueprint VM calls).
  - Enable **Component Use Fixed Skel Bounds** when the Physics Asset isn't needed, which skips per-frame bounds calculation.
  - Avoid updating physics that isn't needed; this is the largest reduction to FParallelAnimationCompletionTask main-thread cost.
  - Interpolation (with URO) and curve blending add main-thread cost.
  — [Epic: Animation Optimization](https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-optimization-in-unreal-engine)
- **City Sample LOD presets [anecdotal]:** One user fixed broken knees on City Sample crowd characters by applying the crowd demo's LOD presets to a new MetaHuman. — search excerpt of [Forum: MetaHuman and CrowdAI broken LODs](https://forums.unrealengine.com/t/metahuman-and-crowdai-broken-lods-imcompatible-new-metahuman/1627023)

### Inferences
- **A practical skeletal tier for pedestrians: 10–30 max at a time, within about 15–25 m.** Each should be:
  - A MetaHuman "UE Optimized – Low" (or a crowd-pipeline build), ideally with body, clothes and head merged into one skeletal mesh (Skeletal Mesh Merge or the Crowd pipeline).
  - Hair as card or mesh hair with **rigid** binding and no simulation or RBF, or baked into the merged mesh as the Crowd pipeline does.
  - Face animation and RigLogic disabled, correctives off.
  - Forced minimum LOD around 2–3.
  - URO or Budget Allocator at 15 Hz or lower beyond about 10 m.
  - Visibility-based anim tick set to only tick when rendered. That is the `VisibilityBasedAnimTickOption` property, `OnlyTickPoseWhenRendered`; general engine knowledge, not re-verified in a fetched 5.9 doc this session.
  - Cloth and physics disabled. Fixed skel bounds.
- **Per-character groom cost scales linearly and never streams.** 0.1–0.2 ms render thread and up to about 16 MB VRAM per character (800 MB / 50) at cards quality means 300 groom-bearing pedestrians would be about 30–60 ms render thread and multiple GB of VRAM. That is impossible, so **background pedestrians must not have Groom components at all.** Bake hair into the skeletal or static mesh as cards or mesh hair, as the Crowd pipeline does.
- **For the user's foreground MetaHumans, keep strands but add groom LOD rules:** cards plus rigid binding at LOD≥2, simulation off at LOD≥2. This frees headroom for the crowd.
- **LODSync:** Make all parts (body, face, clothes, hair) switch LOD together and cap the LOD count for background characters. The assembly doc names LODSync as the tuning point; specific settings were not fetched.
- **Package-size impact:** UE Optimized Low (2K max textures, stripped LODs, no correctives) is the lowest-footprint official MetaHuman variant. Sharing a few body types and texture sets across many pedestrians with tint parameters keeps the cost to tens of MB rather than hundreds; this is an estimate, see Gaps.

### Gaps
- No official per-MetaHuman package-size figure (Cinematic vs High vs Optimized Low). Epic only says file size is the most prominent Cinematic-to-High difference.
- No official ms figures for a single Optimized Low MetaHuman.
- The "platform spawn count limits" table that the Create MetaHuman Crowds page references was not present in the fetched overview content.
- The VisibilityBasedAnimTickOption values and the per-LOD bone-reduction workflow were not on the fetched 5.9 Animation Optimization page, so they were not verified against current docs this session.
- No source quantifies strands vs cards in ms on the same scene.

---

## 4. Nanite skeletal meshes / Nanite for characters (5.5+) and whether it helps crowds

### Takeaway
Nanite Skeletal Mesh exists: Experimental in 5.5 and documented in the 5.9 Nanite overview with "instancing with animation banks." It removes geometry-LOD authoring and gives one draw call per mesh. But it does **not support morph targets**, supports only Opaque/Masked materials, and has reported quality and attachment bugs. It conflicts with MetaHuman faces and correctives, and is a poor fit for VAT. For background pedestrians it is at best a secondary option, used with ISKM/AnimBank on morph-free merged bodies.

### Cited Findings
- **Features [Official, 5.9 doc]:**
  - Nanite Skeletal Mesh offers a Skeletal Mesh API, "one draw call for an entire mesh," shadowing from Virtual Shadow Maps, "instancing with animation banks," and "No geometry LODs. Nanite Skeletal Mesh uses animation LODs."
  - Enable it with **Enable Nanite Support** in the Skeletal Mesh Editor, or in bulk via right-click > Nanite > Enable.
  — [Epic: Nanite Virtualized Geometry](https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine)
- **Limits [Official, 5.9 doc]:**
  - "Deformation with Morph Targets is not supported with Nanite."
  - WPO works but should be clamped, because displaced clusters affect culling.
  - Only Opaque and Masked materials are supported; others fall back to a default material.
  - No forward rendering, MSAA, VR stereo, or lighting channels. Requires DX12 SM6.
  — [Epic: Nanite Virtualized Geometry](https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine)
- **Status by version:** Nanite skeletal mesh was introduced as **Experimental in UE 5.5** per Epic's release communications (summarised by search; the exact release-note line was not read). — [Forum: Unreal Engine 5.5 Released](https://forums.unrealengine.com/t/unreal-engine-5-5-released/2117936); [AWN: Unreal Engine 5.5 now available](https://www.awn.com/print/news/unreal-engine-55-now-available)
- **User reports:**
  - Morph targets break when Nanite is enabled on a skeletal mesh. — [Forum: Nanite Skeletal Mesh in UE 5.5 Main](https://forums.unrealengine.com/t/nanite-skeletal-mesh-in-unreal-engine-5-5-main/1792367)
  - Nanite skeletal mesh shows "extremely low poly from certain angles in UE 5.5+" (thread title). — [Forum: Nanite on Skeletal Mesh shows extremely low poly](https://forums.unrealengine.com/t/nanite-on-skeletal-mesh-shows-extremely-low-poly-from-certain-angles-in-ue-5-5/2573728)
  - Nanite works on individual skeletal meshes but stops once they are merged, and attaching Nanite meshes to a skeletal mesh caused "massive performance issues." — search excerpts of [Forum: Can Nanite skeletal mesh in 5.5 replace LOD?](https://forums.unrealengine.com/t/can-nanite-skeletal-mesh-in-unreal-5-5-replace-lod/2264798)
  - Some Character Creator characters cannot render as Nanite skeletal meshes in UE 5.7 without replacing several eye materials. — [Reallusion Feedback Tracker #12609](https://www.reallusion.com/FeedBackTracker/IssueId/12609)
- **Nanite + VAT [anecdotal]:** Enabling Nanite on AnimToTexture assets caused stretched VAT animation under Mass. — [Forum: Nanite on AnimToTexture crowd assets](https://forums.unrealengine.com/t/enabling-nanite-on-animtotexture-crowd-assets-causes-stretched-vat-animations/2623531)
- **Performance claims [Asserted, low reliability]:** A Medium-style blog says Nanite skeletal meshes give "significant FPS gains with many characters," with no benchmark. — [Medium: Understanding Nanite](https://medium.com/@sarah.hyperdense/understanding-nanite-when-to-use-it-and-when-to-skip-it-b7fcfadc3058)

### Inferences
- **MetaHuman heads rely on 669 blendshapes at LOD0 plus body correctives at LOD0–1** (section 3). With morph targets unsupported, Nanite is incompatible with full-quality MetaHuman faces. It is plausible only for morph-free crowd bodies (correctives already stripped, as in "Optimized Low" and the Crowd pipeline).
- **Where Nanite could help a crowd:**
  - Removing the per-skeletal-mesh draw-call and LOD-pop problem for a merged, morph-free crowd body rendered through ISKM + animation banks.
  - VSM shadows from Nanite skinned geometry may be cheaper than non-Nanite skinned shadows. Unmeasured.
- **Where it doesn't help:** Nanite does not reduce game-thread animation cost or groom cost, which are the dominant per-MetaHuman costs in this project.
- **Version advice:** Treat Nanite skeletal as an experiment in 5.9, not a plan of record. Profile with `stat Nanite` and Insights on target hardware.

### Gaps
- No measured benchmark of Nanite skeletal vs non-Nanite skeletal for crowds was found.
- The 5.9 production/beta status of Nanite skeletal is not stated on the fetched 5.9 Nanite page.
- Whether MetaHuman Crowds' ISKM tier uses Nanite by default in 5.8/5.9 is unknown.

---

## 5. Lightweight non-MetaHuman background people: modular low-poly characters, material variation, consistent look next to MetaHumans

### Takeaway
Little authoritative material exists on this specifically. The established pattern is a small set of low-poly bodies (shared skeleton, a few thousand vertices) varied through per-instance material parameters: tint, texture-atlas index, garment masks. This drives instance count up and draw calls down. For visual consistency next to MetaHumans, Epic's own path is to derive the crowd from MetaHumans: Optimized Low or the Crowd pipeline, with tint parameters. That keeps proportions, skin shading and clothing language matched.

### Cited Findings
- **Epic's crowd variation model [Official]:** The MetaHuman Crowds pipeline varies appearance by slot selection (head/body/garments as MetaHumanCharacter or outfit assets; top/bottom/shoes as ChaosOutfitAsset or SkeletalMesh; hair/brows/beard as GroomBindingAsset) plus instance parameters "such as hair color and clothing tint." — [Epic: Create MetaHuman Crowds](https://dev.epicgames.com/documentation/metahuman/create-metahuman-crowds-in-unreal-engine)
- **Atlases to cut draw calls [anecdotal]:** A developer with an 850-NPC city reported about 20,000 polys per NPC and draw calls already reduced via texture atlases and arrays. They estimated about 70 visible at once (about 35 at LOD0) across 6 neighbourhoods of about 140 NPCs each. No frame times were reported. — [Forum: I have a city with 850 characters](https://forums.unrealengine.com/t/i-have-a-city-with-850-characters-how-to-optimize-it/1457807)
- **Per-LOD bone reduction idea [anecdotal]:** Disable fingers at LOD1 and elbows/knees at LOD2. — [Forum: 850 characters](https://forums.unrealengine.com/t/i-have-a-city-with-850-characters-how-to-optimize-it/1457807)
- **Per-instance VAT variation [anecdotal]:** VAT crowds pick a random animation per instance through per-instance custom data, set after instance creation. — [Forum: AnimToTexture tutorial](https://forums.unrealengine.com/t/community-tutorial-animtotexture-plugin-how-to-use-it-to-make-vertex-animation-textures-for-crowds/746648)
- **Commercial modular-to-VAT tools [vendor claims]:** OverCrowd "automatically converts modular characters into highly performant VAT characters." — [Forum: OverCrowd](https://forums.unrealengine.com/t/overcrowd-overcrowd-massive-crowd-simulation/2669477)
- **Low-tier MetaHuman materials [Official]:** Optimized Low disables subsurface scattering and animated maps, and caps textures at 2K. — [Epic: MetaHuman Assembly](https://dev.epicgames.com/documentation/metahuman/assembly)

### Inferences
- **Recommended for this project (art-consistent and cheap):** Build background pedestrians from MetaHuman Optimized Low, or from the crowd-pipeline output, not from a separate low-poly art style.
  - **Mid tier:** merge to one mesh at about LOD2–3 (about 3.3k body + 6k/2.5k head vertices from the LOD table).
  - **Far tier:** bake to bone-mode VAT or ISKM.
  - Because skin, hair cards and garments come from the same MetaHuman sources as the heroes, colour response and proportions match.
  - A separate modular low-poly cast risks a visible style break next to MetaHumans, especially in faces.
- **Variation budget:** about 4–6 body/garment meshes × 6–10 heads × tint parameters (coat, trousers, hat, skin-tone offset, hair colour) via per-instance custom data. That gives hundreds of perceptually distinct people from a few dozen MB of assets. The project's side identity (rags for Frostside, red for Giltside, fitted clothes) maps well onto per-instance garment-tint and garment-swap parameters.
- **Texture atlases:** Pack the garment variants of one body type into one material and texture array, selected by a per-instance index. Each body type is then one HISM/ISKM draw per LOD per pass.
- **Silhouette props** (top hats, umbrellas, baskets, shawls) do more for period readability at distance than face detail. On VAT they must be baked into the mesh or attached through a bone-driven material path, since static meshes have no sockets.

### Gaps
- No authoritative source or measured data on art-direction techniques for matching low-poly crowds to MetaHumans.
- No measured draw-call figures for atlased vs non-atlased crowd materials in UE5.

---

## 6. Impostor / billboard / sprite crowds for very far distances (octahedral impostors, Niagara crowds, flipbooks): quality and cost

### Takeaway
Impostors are the cheapest far representation: the smallest memory footprint and close to constant cost per instance. But animated impostors multiply texture memory (views × frames), and nothing in UE ships an animated-character impostor workflow. Epic's own crowd systems (City Sample, MetaHuman Crowds) skip impostors and simply **stop rendering** distant characters. For a London street with occlusion from buildings, culling beyond about 80–150 m (or VAT at very low vertex counts) is likely good enough.

### Cited Findings
- **Epic's far tier is "stop rendering" [Official]:** MetaHuman Crowds has a distance threshold "for stopping rendering," and the Mass doc lists "no representation" as a tier. — [Epic: Create MetaHuman Crowds](https://dev.epicgames.com/documentation/metahuman/create-metahuman-crowds-in-unreal-engine); [Epic: Overview of Mass Gameplay](https://dev.epicgames.com/documentation/en-us/unreal-engine/overview-of-mass-gameplay-in-unreal-engine)
- **Perceptual study, 2025 [academic]:**
  - Compared mesh, impostor, NeRF and 3D Gaussian representations at five distances (100% to 20% pixel density) and four LoDs.
  - Meshes were most preferred near the camera. Gaussians became increasingly indistinguishable from the mesh at distance.
  - Impostors had the smallest memory footprint and scaled down most aggressively; they were called the cheapest choice for far or low-detail rendering.
  - Motion did not significantly affect perceived similarity.
  - No runtime ms were measured, and no game engine was used.
  — [arXiv 2510.20558: From Far and Near](https://arxiv.org/html/2510.20558)
- **Impostor speed-up [Measured, Unity, not Unreal]:** Unity's impostor docs show frame time at 800 instances dropping from about 62.5 ms (140k-triangle mesh) to about 4.01 ms with impostors. — [Unity Industry Toolkit: Bake Impostor](https://docs.unity3d.com/Packages/com.unity.industry.toolkit@3.1/manual/Actions/Autogenerated/BakeImpostor.html)
- **Unreal octahedral impostors:** Unreal practitioners use octahedral impostors (ImpostorBaker lineage) for distant static geometry and note acceptable lighting differences at range. No crowd benchmark was found. — search excerpts of [Forum: Octahedral imposters as volumetrics](https://forums.unrealengine.com/t/octahedral-imposters-used-as-volumetrics-experiment/130223/3); [Blog: Octahedral imposters](https://smailikhappy.github.io/posts/Octahedral_imposters/)
- **Niagara VAT crowds exist as an approach:** A zombie horde built with VAT and HLSL in Niagara (portfolio piece; title only). — [ArtStation: Zombie Horde with VAT and HLSL in Niagara](https://isaacoster.artstation.com/projects/kN1ZJA)
- **GPU-driven crowd framework claim (title only):** "6,000 agents on one game thread." — [80.lv: GPU-driven crowd framework](https://80.lv/articles/6-000-agents-on-one-game-thread-novel-high-performance-framework-for-gpu-driven-crowd-systems/)
- **Older hybrid research:** Geopostors switch between impostors and geometry based on pixels per texel. — [Dobbyn et al. 2005, Geopostors](https://ics-websites.science.uu.nl/docs/vakken/mcrws/papers_new/Dobbyn%20et%20al%20-%202005%20-%20Geopostors.pdf)

### Inferences
- **Animated octahedral impostors are expensive in memory.** A walk cycle of about 16 frames × 8×8 views × 256² per view in RGBA8 plus normals gives roughly 16 × 64 × 256 KB × 2 ≈ 0.5 GB per character type before compression (derived arithmetic). Practical animated impostors therefore use few views (4–8 directions), few frames (8–12), and small cells (64–128 px).
  - At 64 px cells, 8 directions × 12 frames ≈ 4.7 MB per type in RGBA8 + normals. That is affordable but low fidelity, and only good where a person covers about 30–60 pixels.
- **A London street with 3–6-storey frontages rarely gives sight lines beyond about 100–200 m** except down long straight streets and across squares. Far impostors matter only for those vistas, so a "VAT-at-very-low-vertex-count then cull" ladder is simpler and avoids a second baking pipeline.
- **Niagara crowds** (sprites, or mesh particles with VAT) can draw thousands of far silhouettes in one system and need no Mass entities. They are good for square-scale ambient fill, like distant market crowds, that never needs hand-off to a nearer tier. The hand-off is the hard part: a Niagara particle can't become an interactive NPC without custom bookkeeping.
- **Fog, haze and atmospheric perspective** (fitting a gray London) hide impostor artefacts and make culling distances shorter and less noticeable.

### Gaps
- No Unreal-specific measured numbers for impostor or Niagara crowds.
- No shipped Epic tool for animated character impostors was found. ImpostorBaker's current status in 5.x was not verified.
- The search could not reach Ryan Brucks' original octahedral impostor write-up in this session.

---

## 7. Reported real numbers: draw calls, ms per N characters, memory, package size per technique

### Takeaway
Hard, reliable numbers are scarce. Epic publishes almost none for crowds, and most figures are single-user forum measurements. The defensible numbers are:
- Groom render thread: about 6 ms per 50 card-groom MetaHumans.
- Groom VRAM: about 800 MB per 50 MetaHumans.
- Skin cache: about 137 MB per 50 MetaHumans (about 31 MB at forced LOD3).
- Correctives: about 40% FPS from disabling them.
- City Sample: about 8 full actors, the rest VAT.
- Budget Allocator default budget: 1 ms.
- URO target: 15 Hz or lower.
- About 200 VAT ISM characters were GPU-bound on mobile-class RTX.

Together they show that hundreds of visible pedestrians are only feasible with an instanced (VAT or ISKM) tier carrying most of the count.

### Cited Findings
- **City Sample:** about 8 full actors, the rest VAT [Official, Epic staff]. — [Forum: MetaHuman skin cache thread](https://forums.unrealengine.com/t/metahuman-skin-cache-retains-lod0-entries-for-every-npc-regardless-of-camera-distance/2728166)
- **Epic: skeletal mesh "wasn't designed for 100+ on-screen components"** [Official, Epic staff]. — [Forum: MetaHuman skin cache thread](https://forums.unrealengine.com/t/metahuman-skin-cache-retains-lod0-entries-for-every-npc-regardless-of-camera-distance/2728166)
- **MetaHuman Crowds example ratio:** 10 full actors close, hundreds instanced [Official]. — [Epic: Create MetaHuman Crowds](https://dev.epicgames.com/documentation/metahuman/create-metahuman-crowds-in-unreal-engine)
- **Groom render thread, 50 MetaHumans, cards only, UE 5.7:** skinned ~10.03 ms, rigid ~7.12 ms, none ~4.29 ms [Measured-anecdotal]. — [Forum: Groom bindings cost](https://forums.unrealengine.com/t/high-render-thread-cost-of-groom-bindings-even-on-rigid-mode/2725272)
- **Groom VRAM, 50 MetaHumans:** about 800 MB (RTX 3070) [Measured-anecdotal]. — [Forum: Groom VRAM resident](https://forums.unrealengine.com/t/groom-lod-data-remains-fully-resident-in-vram-regardless-of-distance-lod-level/2715458)
- **Card interpolation GPU, 50+ grooms:** over 2 ms [Measured-anecdotal]. — [Forum: Expensive Hair Cards](https://forums.unrealengine.com/t/expensive-hair-cards/2691281)
- **Skin cache, 50 MetaHumans:** about 137–142 MB normal, about 31 MB at forced LOD3 [Measured-anecdotal]. — [Forum: Skin cache thread](https://forums.unrealengine.com/t/metahuman-skin-cache-retains-lod0-entries-for-every-npc-regardless-of-camera-distance/2728166)
- **Correctives off:** about 40% editor FPS gain; skeletal mesh merge 5 → 1 ticking meshes per character; finger bones 22 → 8 [Measured-anecdotal, UEFN/5.4]. — [Forum: MetaHuman 3.0 40% gains](https://forums.unrealengine.com/t/the-new-3-0-metahumans-40-performance-gains-tutorial-inside/1777726)
- **VAT:** about 200 AnimToTexture ISM characters could not hold 60 fps on an RTX 3060 Mobile or 2060 Super, GPU-bound in BasePass and ShadowDepths [Measured-anecdotal, no ms]. — [Forum: AnimToTexture BasePass/ShadowDepths](https://forums.unrealengine.com/t/animtotexute-is-putting-pressure-on-basepass-and-shadowdepths/1145774)
- **Budget Allocator default:** 1.0 ms game-thread budget; scalability example 1.0–2.5 ms [Official]. — [Epic: Animation Budget Allocator](https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-budget-allocator-in-unreal-engine)
- **URO target:** 15 Hz or lower at distance [Official]. — [Epic: Animation Optimization](https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-optimization-in-unreal-engine)
- **MetaHuman vertex budgets per LOD** (for draw/skin cost estimates): body LOD0 30.5k → LOD3 1.5k; head LOD0 24k → LOD3 2.5k; 669 blendshapes only at LOD0 [Official]. — [Epic: MetaHuman LOD specifications](https://dev.epicgames.com/documentation/en-us/metahuman/platform-support-and-lod-specifications-for-metahumans)
- **Standard UE5 AI character:** "roughly 0.13–0.41 ms per frame" [Asserted, no method; low reliability]. — [StraySpark: MetaHuman Crowd UE 5.8 guide](https://www.strayspark.studio/blog/metahuman-crowd-ue5-8-guide)
- **City Sample crowds:** about 10 FPS slower than a home-grown Manny crowd, UE 5.1 [anecdotal]. — [Forum: City Sample Crowds for UE 5.1](https://forums.unrealengine.com/t/city-sample-crowds-for-ue-5-1/882197)
- **Impostors, Unity:** 800 instances, 62.5 ms → 4.01 ms [Measured, Unity]. — [Unity: Bake Impostor](https://docs.unity3d.com/Packages/com.unity.industry.toolkit@3.1/manual/Actions/Autogenerated/BakeImpostor.html)
- **Animation Sharing:** 100 → 1,000 characters is a "minimum increase in performance cost" [Official, qualitative]; Epic staff call it "much slower than the ISKM approach." — [Epic: Animation Sharing](https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-sharing-plugin-in-unreal-engine); [Forum: AnimBank and ISKM](https://forums.unrealengine.com/t/animbank-and-instanced-skinned-mesh-component/2734825)

### Inferences

**Budget arithmetic for this project (derived from the user's figure and the numbers above):**
- At ~0.5 ms game thread per full MetaHuman in PIE, 300 visible pedestrians as full MetaHumans would be about 150 ms of game thread. Even a 5–10× cut from URO, budgeting and sharing leaves 15–30 ms. That is not viable, which matches Epic's "not designed for 100+."
- Grooms alone on 300 pedestrians would extrapolate to about 36 ms render thread and about 4.8 GB VRAM. That is fatal, so background pedestrians need **zero groom components**.
- A workable street budget of about 2–3 ms game thread and about 3–5 ms GPU for crowds implies:
  - **0–10 m:** foreground or interactive MetaHumans (the existing walker + leader pose). Max about 5–10, with Budget Allocator.
  - **10–30 m:** 10–30 "Optimized Low" merged skeletal pedestrians (or MetaHuman Crowds full-actor tier). Cards baked in, no groom component, no correctives, no face animation, URO at 10–15 Hz, forced LOD≥2.
  - **30–120 m:** 100–500 instanced pedestrians. Use ISKM + AnimSequenceTransformProvider (Epic's 5.8+ recommendation, experimental and buggy) or bone-mode VAT on HISM (proven in City Sample, version-fragile plugin). Shadows off or cheap beyond about 50 m.
  - **120 m+:** cull, or Niagara/impostor silhouettes for long vistas only.

**Technique comparison matrix** (synthesised from the findings above; costs qualitative unless cited):

| Technique | GT cost / char | RT/GPU cost | Visible count sweet spot | Quality | Setup effort | Package impact | 5.9 status / risk |
|---|---|---|---|---|---|---|---|
| Full MetaHuman (strands, multi-mesh, leader pose) | High (~0.5 ms PIE, user figure) | Very high (groom ~0.12 ms RT and ~16 MB VRAM each even as cards) | <5–10 | Best | Existing | Hundreds of MB per unique MH (unquantified) | Production |
| MH Optimized Low + merge + URO/Budget | Low–medium | Medium (skin cache, per-component RT) | 10–30 | Good at 10–30 m | Medium | Low (2K textures, stripped LODs) | Production |
| Animation Sharing (skeletal, leader pose) | Near-constant total | Unchanged per component | 20–50 | Good, but no per-char IK; synchronized look | Medium–high | Negligible | Production, older plugin; "much slower than ISKM" |
| MetaHuman Crowds (Mass + full actor + ISKM) | Very low for ISKM tier | Low–medium (instanced) | Hundreds+ | Good at range; no correctives or hair physics | Medium (pipeline does the conversion) | Medium (optimised builds; build quality raises memory) | **Experimental (5.8)**; ISKM leak and ref-pose bugs reported 5.8/5.8.1 |
| ISKM + AnimSequenceTransformProvider (custom) | Very low | Low (GPU skinning, instanced) | Hundreds–thousands | Good; no AnimBP, limited blending | High (C++/Mass) | Low | New in 5.8, experimental |
| VAT via AnimToTexture on HISM | ~Zero | GPU vertex cost in every pass incl. shadows | 100–500+ (GPU-bound ~200 on mobile-class RTX) | Medium; no blending, possible TAA ghosting, no sockets | Medium (plugin fragile across versions) | Very low (bone mode ~MB) | Engine plugin since 5.1; nodes broken in 5.2/5.3/5.5 reports |
| Nanite skeletal | n/a (same anim cost) | One draw per mesh, VSM shadows | Untested | No morph targets → no MH faces/correctives | Low (checkbox) | Nanite data size | Experimental 5.5; 5.9 status unclear |
| Impostors / Niagara sprites | ~Zero | Lowest per instance | 1000s at distance | Low; animated impostors memory-heavy | High (custom bake) | Low–medium | No official character workflow |

### Gaps
- No reliable measured ms per N for VAT, ISKM, or MetaHuman Crowds in UE 5.8/5.9 on desktop hardware was found. Epic publishes none, and the "platform spawn count limits" table was not retrievable.
- No measured package-size figures per technique, per MetaHuman quality tier, or for City Sample's crowd content.
- No draw-call counts for any crowd technique in UE5.
- Whether the 5.8 ISKM bugs (GPU memory leak, reference-pose rendering) are fixed in 5.9 is unknown. Check 5.9 release notes and the issue tracker before committing.
