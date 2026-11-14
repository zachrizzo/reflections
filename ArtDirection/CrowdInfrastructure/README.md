# MetaHuman Crowd test infrastructure

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
