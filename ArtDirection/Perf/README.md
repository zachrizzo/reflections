# Performance and stability: packaged Reflections

Owner: the perf session. It works only on the **packaged** game, in `Saved/PerfLab/`: never the shared editor, PIE or packaging's staged folder.

**Status (2026-11-14, 15:10 local): paused.** At the user's request, relayed by the orchestrator at about 15:05, packaged runs stopped, and testing moves to the editor until Sunday morning. On Sunday this suite reruns on the final package; see "Sunday re-run" at the bottom. Everything below comes from the **train #5** package.

## TL;DR

- **Frame rate at Epic, 1080p, on the RTX 5080:** 132 fps in the start area, **75 fps in heavy combat** (23 characters), 85 fps at the finale. No crashes, and no hitches over 50 ms in combat.
- **The game is CPU-bound, not GPU-bound.**
  - In combat the game thread takes 12.4 ms and the render thread 12.3 ms, while the GPU needs only 5.8 ms.
  - The engine's High preset changes almost nothing (77 fps vs 75), because the cost is **per character**: about **0.43 ms of game thread, 0.30 ms of render thread and 0.14 ms of GPU** for every MetaHuman on screen.
- **Cause: each MetaHuman is about 12 skeletal mesh components and 5 groom components.**
  - Combat scene: 272 ticking skeletal meshes, 118 groom components, 2.6 M triangles, 826 draw calls and 23 ms of parallel animation work per frame, in a gray-box map.
  - That's the lever, not Lumen, VSM or Niagara (each under 0.4 ms GPU here).
- **Hitch to chase:** in the calm start area (strolling walkers only), the game thread stalls 40–75 ms waiting on a PrePhysics task, in bursts: 32 frames over 20 ms in 50 s. It doesn't happen in combat. Prime suspect: the walkers' hidden motion-matching driver pawns. Sent to crowd.
- **Hero cloak:** Chaos cloth is **not** a cost in the packaged game. Its game-thread wait is 0.00 ms median and 0.3 ms P99. The 13 ms wait seen in the editor doesn't reproduce here.
- **Ship blockers for a judge's PC:**
  1. Nothing sets graphics quality, so everyone starts at Epic with hardware ray tracing, no frame cap and VSync off. There's also no settings screen. A spec went to game-flow: `GraphicsSettings-Spec.md`.
  2. The zip ships a `Saved/` folder with a checkpoint save in it. Routed to packaging.

## Machine and method

| | |
|---|---|
| CPU | AMD Ryzen 7 9700X (8 cores / 16 threads) |
| GPU | NVIDIA GeForce RTX 5080 16 GB, driver 610.88 |
| RAM | 32 GB DDR5-4800 |
| OS | Windows 11 Home |
| Build | `Saved/JamBuild/Zips/train5_Windows.zip`: Development, Win64, DX12 SM6, git `e9f3c59` plus working tree. Unzipped to `Saved/PerfLab/train5/`. |
| Map | `Lvl_HeroSampleCrowd`, the only cooked map: the sample sandbox plus 6 placed MetaHuman walkers. The Mass city crowd level isn't cooked (`Crowd.Mass.Enable 1` logs "does not exist"), so no Mass numbers yet. |

**Shared machine:** the Unreal Editor was open during every run, with about 6.6 GB VRAM in use. Absolute numbers are slightly pessimistic; A/B deltas are fair.

**How runs are made** (`tools/run_off.ps1`, `tools/batch1.ps1`, `tools/batch2.ps1`):
- `-RenderOffscreen` renders a real 1920×1080 frame with no window. Windowed runs got closed by another desktop agent, and keystroke driving stole focus.
- `-csvGpuStats -csvCaptureFrames=N` records every frame's game thread, render thread, RHI and GPU time plus per-pass GPU timings (`r.GPUCsvStatsEnabled 1`).
- Scenario commands go in `-ExecCmds` and run on frame 1. `-ini:Engine:[ConsoleVariables]:GameFlow.Enabled=0` skips the title.
- Offscreen and windowed agree. Start area windowed: 122 fps, 8.17 ms median, 11.2 ms P95, GPU 3.66 ms. Offscreen: 132 fps.
- **Statistics:** "Steady" is 12 s to the end of a run of about 60–90 s. "Cold" is the first 12 s: load, first-use PSOs, and the scenario's spawns.
- **Tools:**
  - `tools/report.py <runs dir> [prefix]`: the tables below.
  - `tools/csvsum.py`: summarises one CSV.
  - `tools/colstat.py <csv> <stat> [ms]`: distribution of one stat.
- **Raw data:** `Saved/PerfLab/runs/<run>/profile.csv` and `game.log`.

| Scenario | ExecCmds | On screen |
|---|---|---|
| idle | (none) | Hero standing, 6 MetaHuman walkers strolling: 7 characters |
| combat | `Crafting.Dummies 6 900 mixed, Squads.SpawnTest 2, Squads.Engage, Villain.Start, Villain.SpawnTestHosts 4, Crafting.Cast` | 23 characters: 2 engaged squads with casters, villain hosts, dummies |
| finale | `Villain.Finale, Villain.BossHere, Squads.SpawnTest 2, Squads.Engage` | 17 characters, the boss's true form and telegraphs, 2–22 dynamic lights |

## Results (train #5, 1920×1080, steady state)

| Run | FPS (median) | Frame median / P95 / P99 (ms) | Game thread median / P95 | Render thread median / P95 | RHI median | GPU median / P95 | Hitches >50 ms | Cold 0–12 s: worst frame, >50 ms, PSO misses | Characters | RAM (MB) | VRAM (MB) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| idle, Epic | **132** | 7.6 / 11.5 / 24.5 | 5.5 / 10.9 | 7.5 / 9.6 | 4.0 | 3.5 / 3.8 | 3 | 3.7 s, 13, 433 | 7 | 1904 → 1951 | 2660 |
| combat, Epic | **75** | 13.3 / 16.7 / 20.0 | 12.4 / 16.4 | 12.3 / 15.4 | 8.2 | 5.8 / 6.1 | 0 | 3.1 s, 3, 473 | 23 | 2016 → 2206 | 2914 |
| combat, High | 77 | 12.9 / 16.3 / 18.8 | 12.0 / 15.9 | 12.1 / 15.0 | 8.0 | 5.3 / 5.8 | 0 | 2.7 s, 4, 535 | 23 | 2239 → 2404 | 2267 |
| finale, Epic | **85** | 11.8 / 15.1 / 21.4 | 10.2 / 14.1 | 11.5 / 14.4 | 6.9 | 5.3 / 5.9 | 2 | 3.2 s, 3, 467 | 17 | 1968 → 2080 | 2834 |

The 3–4 s worst cold frame is the first frame after map load (asset flush plus the first PSOs). The title screen covers it in the real flow.

**What one frame is made of**, as medians in ms:

| | idle (7 characters) | combat (23) | per extra character |
|---|---|---|---|
| Game thread: Animation (not counting worker anim) | 1.55 | 4.30 | 0.17 |
| Game thread: TickActors | 1.25 | 2.93 | 0.10 |
| Game thread: CharacterMovement | 0.27 | 0.96 | 0.04 |
| Game thread: EndOfFrameUpdates | 0.21 | 1.02 | 0.05 |
| Worker threads: parallel animation (total task time) | 7.1 | 23.5 | 1.0 |
| Render thread: RenderOther + InitViews + RDG collect | 3.5 | 5.6 | 0.13 |
| GPU: HairCardsInterpolation | 0.37 | 1.15 | 0.05 |
| GPU: HairGuideInterpolation | 0.15 | 0.40 | 0.016 |
| GPU: GPUSkinCache | 0.13 | 0.53 | 0.025 |
| GPU: RayTracingDynamicGeometry (skinned BLAS) | 0.08 | 0.29 | 0.013 |
| Ticking skeletal mesh components | 86 | 272 | **≈ 12 per character** |
| Groom components | 42 | 118 | **≈ 5 per character** |
| Draw calls / triangles | 341 / 0.8 M | 826 / 2.6 M | 30 / 0.11 M |

The engine presets cut GPU passes (Epic → High: TSR 0.46 → 0.30 ms, shadows 0.35 → 0.29 ms) but leave every per-character line unchanged.

## Top costs and fixes (sent to owners)

Each line gives the measured cost. Gains are estimates from the per-character slope above, because the A/B toggle runs were cut short by the pause; they are marked "est.". They'll be re-measured on Sunday.

| # | Cost (measured) | Fix | Owner | Expected gain (combat, 23 characters) |
|---|---|---|---|---|
| 1 | About 12 ticking skeletal meshes per MetaHuman (272 in combat) and 2.6 M triangles: MetaHumans render at LOD0 at all distances | Give crowd and NPC MetaHumans a **LODSync with a minimum LOD of 1** (`LODSyncComponent`, or `SkeletalMeshComponent::SetForcedLOD(2)` beyond about 15 m), and set `VisibilityBasedAnimTickOption = OnlyTickPoseWhenRendered` on every leader-posed part (torso, legs, feet, outfit) | crowd-looks (NPC looks) | est. 3–4 ms game thread plus workers, 1.5 ms render thread, 1 M fewer triangles |
| 2 | About 5 GroomComponents per character (118 in combat), many with **no groom asset** (the hero has 5 empty ones of 6, per hero-cloak's notes). They still tick, and HairCards + HairGuide interpolation is 1.55 ms GPU. | At BeginPlay, `DestroyComponent()` (or `SetComponentTickEnabled(false)` + `SetVisibility(false)`) every GroomComponent whose `GroomAsset` is null. Use `LODBias`/cards beyond 10 m for the rest. | crowd-looks (NPCs); hero-cloak (the hero's 5 empty slots). **Hero part done 15:15:** Start With Tick Enabled **and Auto Activate** are off on Beard/Mustache/Eyelashes/Eyebrows/Fuzz in BP_HeroTravelVisual and BP_HeroSampleVisual. Auto Activate alone re-enables tick through `Activate()`. Verified in PIE: only Hair ticks. Lands in the next cook. Sunday check: `Ticks/GroomComponent` drops by 5 for the hero. For NPCs, crowd-looks must turn off both flags too (or destroy the component). | est. 0.5 ms game thread, 0.6 ms GPU |
| 3 | Each walker is a visible MetaHuman plus a **hidden** `BP_SampleCMCClean2` driver running motion matching (1–2.5 ms of worker anim each, per crowd's notes) | Make the driver cheaper **without** dropping its bone refresh: the visible body follows the driver's pose, so `AlwaysTickPose` risks the T-pose / "bone buffers incomplete" bug (crowd's caveat, 15:15). URO (`bEnableUpdateRateOptimizations = true`) plus the same `Crowd.Lod` rates for the driver's pose search are the safe levers. Waits for crowd's PIE trace (row 4). | crowd-react | est. 0.5–1 ms game thread, several ms of worker time |
| 4 | **40–75 ms game-thread stalls** (`EventWait/PrePhysics`) in bursts with only strolling walkers: 32 frames over 20 ms in 50 s idle, 6 in the finale, 0 in combat. Parallel anim tasks are short (max 1–2 ms), so a single long PrePhysics task is blocking. | Capture one Unreal Insights trace in PIE (`-trace=cpu,task -statnamedevents`) of walkers strolling, and find the long PrePhysics task. Suspects: the hidden driver's pose-search full-database search when a stroll target changes, or a stroll/yield query. | crowd-react | Removes the only visible hitches in the build (P99 24 ms → about 12 ms in idle) |
| 4b | **Status 15:45.** Crowd's PIE trace (train #7, 23 s, `Saved/Profiling/20261114_153717_7BBFB0.utrace`) didn't reproduce the stall: TG_PrePhysics peaked at 3.7 ms. **Sync loads are ruled out** for the packaged stalls: in all 68 packaged frames over 20 ms, GT FlushAsyncLoading = 0, AsyncLoading ≤ 0.8 ms, the package queue is 0 and there are no load CSV events. The bursts come in two 8–10 s windows (4.6–12.7 s and 47–57 s), about 40 s apart, so a 23 s PIE window can miss them. The CSV's anim stats cover **evaluation** only, not the parallel **update** where pose search runs, so pose search is still a suspect. | Sunday: a packaged `-trace=cpu,task,loadtime -statnamedevents` run of at least 70 s idle, exported headlessly with `UnrealInsights.exe -OpenTraceFile=… -NoUI -AutoQuit -ExecOnAnalysisCompleteCmd="TimingInsights.ExportTimingEvents …"` | perf | |
| 4c | Crowd's PIE findings in the walker setup (12 drivers): (a) each hidden driver's GameplayCameraComponent evaluates its rig every frame, about 1.1 ms (**fixed for train #8**: `Crowd.Lod.QuietDriverCameras`); (b) driver CharacterMovement plus UpdateChildTransforms of the attached visible MetaHuman, about 3 ms; (c) `BP_AnimNotify_FoleyEvent` fires on the driver meshes, about 1 ms, so footsteps may play twice | (b) and (c), plus URO on the driver mesh (keep bone refresh: T-pose risk), go to npc-unify, which owns the driver setup | npc-unify | about 1.1 ms GT done; (b)+(c) up to about 4 ms GT for 12 walkers. **npc-unify, 15:50:** (1) all camera-like components on walkers are deactivated and tick-off at spawn, train #8 (they'll A/B it in PIE; perf measures it in the package); (2) attach-parent bounds plus no overlaps on leader-posed parts only (outfit, face; never Body, hit capsule or walker), train #9; (3) foley stays until audio decides whether NPC footsteps ship (the walker may be the only source, not a double); (4) URO on the walker mesh is declined before the jam (retarget plus T-pose crash risk). **16:35 update:** in PIE on train #9, all 140 camera-like components on 35 walkers are inactive with tick off. The PIE A/B showed no measurable change (about 32 ms frames, bound elsewhere), so it needs the packaged measurement. Foley-off and lean follower parts are staged behind `Npc.WalkerFoley` and `Npc.LeanFollowerParts`; both are in `batch2.ps1` for Sunday's A/B, with `Crowd.Lod.QuietDriverCameras 0` as the camera A/B. |
| 5 | Ray-traced skinned geometry (0.29 ms GPU plus render-thread gather) and HW Lumen at every preset | In the presets, `r.Lumen.HardwareRayTracing 0` and `r.RayTracing.Geometry.SkeletalMeshes 0` at High and below. Keep both at Epic. See the proposed `DefaultScalability.ini`. | perf (config), after the orchestrator OKs it | est. 0.3 ms GPU, 0.5 ms render thread at High |
| 6 | First use of each spell: the Niagara systems and materials PSO-compile on first cast (cold combat: 3 frames over 50 ms; 470–535 PSO misses in the first 12 s of every run) | At map start, spawn each spell system once, out of view, for one frame (or `PrecachePSOs` on the system assets). Do the same for the villain's telegraph and true-form systems. | spell-combat; villain | Removes the first-cast hitch (not separately measured). **Accepted for train #8** (15:20): `UReflectionsSpellVfxSubsystem::OnWorldBeginPlay` spawns NS_Spell_Projectile/Impact/Heal/Ward plus every system under `/Game/SpellCrafting/VFX` once at Z = -200000, unpooled, then deactivates them after 0.5 s; a log line gives the count. Not covered: the ground-mark decal material still compiles on the first impact. On Sunday, check the first-cast frames for `PSOPrecacheState: Missed` and send the PSO to spell-combat. **Compiled 15:15 local (editor and game targets).** Verify in the package log: `Spell VFX: warmed up N spell systems at map start.` |
| 7 | `DDCvar.*` console variables are looked up by name more than 500 times (engine performance warning): the GASP sample Blueprint reads them every frame | Cache them (low priority) | hero sample owner | Small |

Not a problem, so no action:
- **Chaos cloth** on the hero coat: cloth event wait median 0.00 ms, max 1.9 ms.
- **Niagara** in the finale: 22 lights peak, with no GPU line above 0.2 ms for lights or FX.
- **Lumen and VSM** on this map: under 0.4 ms each.
- **Memory:** about 2.0–2.4 GB RAM and 2.3–2.9 GB VRAM. Combat grows 190 MB over 90 s while spawning and is flat after that.

These may change on the teammate's real map (more geometry and lights). Re-check on Sunday.

## Scalability

- **State today:** there's no `Config/DefaultScalability.ini`, so the engine's Low, Medium, High and Epic presets apply unchanged. They exist and do scale the GPU passes (Lumen off at Low, half-res reflections at High, TSR history and so on).
- **But:**
  1. Nothing in them reduces per-character cost, which is what limits this game.
  2. The game never picks a preset: no `RunHardwareBenchmark`, no `GameUserSettings` code, no settings screen. Every PC runs **Epic + hardware RT**, uncapped, with VSync off, at desktop resolution.
- **Proposal, not applied:** [`proposed/DefaultScalability.ini`](proposed/DefaultScalability.ini). It adds a skeletal LOD bias per view-distance level, turns hardware Lumen and ray-traced skinned meshes off at High and below, and keeps Epic as is. It needs one A/B pass on the final package before it goes into `Config/`. The orchestrator approves the config edit.
- **Settings screen:** specified for game-flow in [`GraphicsSettings-Spec.md`](GraphicsSettings-Spec.md):
  - Rows: preset, resolution, window mode, render scale, VSync, frame cap, ray-traced lighting, auto-detect.
  - On first launch, auto-detect clamped to High, borderless, VSync on.

### 60 fps at 1080p High on a mid-range PC?

This is an estimate from the measurements, not measured on such a PC.
- **GPU:**
  - High is 5.3 ms on the RTX 5080. A mid-range RTX 3060 / RX 6600-class GPU is about 2.5–3× slower, so roughly **14–16 ms**: 60 fps holds on this map, and the proposed High (no hardware RT) adds headroom.
- **CPU, the real risk:**
  - Combat is about 12.4 ms per thread on a Ryzen 7 9700X. A mid-range 6-core CPU (Ryzen 5 5600 / Core i5-12400) is about 1.4–1.6× slower in single-thread terms, giving **17–20 ms**: about **50–58 fps in heavy combat at any preset**.
  - The start area and the finale stay above 60.
  - Getting combat above 60 on mid-range needs fixes 1–3 (about 4–6 ms off each CPU thread), or a cap of about 14 active NPCs in a fight.
- **Epic:** looks right and holds above 60 fps on high-end GPUs. At 4K, use 50 % render scale (TSR). The 4K run didn't finish before the pause.

## Stability

- **Crashes:** none in about 12 minutes of packaged play across 9 launches (idle, combat ×2, finale, plus the windowed and offscreen test runs). `Saved/Crashes` is empty. Three windowed runs ended early because something on the desktop closed the window (`RequestExit … ViewportClosed`), not because of a crash.
- **The 20–30 minute soak was not run:** packaged runs were paused at the user's request. It goes first on Sunday.
- **Log issues (non-fatal):**
  - `LogCollision: Error: RaycastSingle resulted in a NaN/INF in PHit` and `ConvertQueryImpactHit() received NaN/Inf for normal`. These appear 1–6 times per run, including idle at frame 63, so something traces with a zero-length or NaN direction. Probably the GASP sample traversal or foot traces. Low priority, but NaNs can turn into physics crashes.
  - `Crafting.Dummies` asks for `/Game/Characters/WhiteLondon/CrowdPreview/BP_WhiteLook_02_Cap`, which isn't cooked (a dummy is silently missing). Owner: crafting or packaging.
  - The city crowd level `/Game/Crowd/City/Lvl_HeroSampleCrowd_City` isn't cooked. Fine while Mass is off; routed to packaging.

## First-run experience

- **Startup:** about 6 s from launch to the loaded map on this machine (NVMe, warm OS cache). The first frame after load takes 3.1–3.7 s (asset flush plus about 150 PSOs compiled on the render thread). The next 8 s show 3–13 frames over 50 ms in the start area, from PSO misses. `r.PSOPrecaching` is on, but the D3D12 PSO disk cache is off (`r.D3D12.PSO.DiskCache=0`, the engine default), so the driver cache does the work on the second run.
- **The title screen hides most of this**, because the map loads behind it. Keep the title up (or a "Preparing shaders…" line) until `FShaderPipelineCache::NumPrecompilesRemaining() == 0` and 2 s have passed. That's a game-flow change, in the spec's first-launch section.
- **Driver cache:** the true cold first run (empty NVIDIA DX cache) wasn't tested: clearing it would have hit the shared editor. On Sunday, test on a second user account or a clean machine.
- **Recommendation for after the jam:** record a bundled PSO cache (`-logPSO` play-through → `ShaderPipelineCache` `.spc`) so spells and the boss don't compile on first use.

## Sunday re-run (final package)

```bash
powershell -File ArtDirection/Perf/tools/batch1.ps1 -Exe "<PerfLab>\<build>\Windows\reflections\Binaries\Win64\reflections.exe" -Prefix final
```

```bash
powershell -File ArtDirection/Perf/tools/batch2.ps1 -Exe "<same exe>" -Prefix final
```

```bash
python -I ArtDirection/Perf/tools/report.py Saved/PerfLab/runs final_
```

Notes for train #8 and later: the game-flow settings code is in (`GameFlow/ReflectionsGameFlowSettings.{h,cpp}`).
- On first launch it auto-detects and clamps to High. Benchmark runs must therefore pin the preset in `-ExecCmds` (`scalability 3` for the Epic baseline) or numbers won't compare with train #5.
- Hardware RT is stored as a game setting (`ECVF_SetByGameSetting`), so the proposed `DefaultScalability.ini` rows for `r.Lumen.HardwareRayTracing` can't override the player's choice. Console `-ExecCmds` still wins for A/B runs.
- **First-launch test:** delete `<build>\Windows\reflections\Saved\Config\Windows\GameUserSettings.ini`, launch windowed once, and check:
  1. the log shows the benchmark;
  2. the preset is ≤ High, borderless, VSync on;
  3. no hitch reaches the title.

Order on Sunday:
1. Run the 25-minute soak (combat commands every few minutes, via `run_off.ps1` with a large `-Frames`; watch RAM and VRAM growth and `Saved/Crashes`).
2. Run `batch1` (presets, 1440p and 4K, toggles: no hair, no cloth, no VSM, no hardware RT, no Lumen, no crowd LOD).
3. Run `batch2` (LOD bias 1 and 2, no RT skeletal meshes, URO, no grooms).
4. Do an Insights trace of the idle stall.
5. Apply the measured `DefaultScalability.ini`.
