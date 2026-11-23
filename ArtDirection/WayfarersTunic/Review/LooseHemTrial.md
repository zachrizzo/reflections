# Loose tunic on Barnaby and the Test Town lineup

The trial outfit at `/Game/Characters/Clothing/WayfarerPilot/LooseHem/WI_LooseTunic` uses the shared BridgeGuard reference. The pattern widens by up to 15% laterally and 18% front to back at the hem and adds 6.5 cm of length there. Unreal fits this one outfit to each wearer. A separate simulation mesh drives the visible tunic. Chaos pins fabric above the hem transition and allows up to 5 cm of travel in the weight map. The benchmark verified 76 dynamic particles per fitted tunic. The prototype reuses the existing conservative torso mask.

## Barnaby

The table counts the average number of distinct, fully exposed body triangles intersected by the garment per accepted pose. Hem contacts are the subset involving garment triangles with a vertex in the lowest 12 cm of the reference pose. Clearances use matching surfaces captured during Play in Editor. The physics-disabled reference was checked against the bone-skinned surface at the same pose and agreed within 0.001 mm. The cast uses the source healing animation directly. The turn uses a walk loop and a scripted pivot.

| Motion | Matched poses | Hem contacts off | Hem contacts on | Whole tunic off | Whole tunic on |
| --- | ---: | ---: | ---: | ---: | ---: |
| Step and turn | 49 | 16.0 | 113.3 | 357.7 | 455.6 |
| Healing cast | 36 | 44.0 | 76.4 | 754.3 | 790.4 |

Exposed hem intersections occurred in all 85 paired poses in each mode. The greatest per-pose 95th percentile hem displacement was 46.9 mm during the turn and 49.6 mm during the cast. Upper garment 95th percentile displacement stayed within 5.3 mm in accepted poses. Eleven turn samples were excluded because the CPU render readback and the current pinned upper garment differed by more than 10 mm at the 95th percentile. The first accepted cast sample was 0.15 seconds into the 2.2-second clip. The side-by-side video replays the sampled Unreal geometry with neutral materials and a synchronized camera.

## Performance

Play in Editor on the local Ryzen 7 9700X and RTX 5080 at 2189 × 1251. Each scenario used the same camera, animation loop, wardrobe and LOD 0 in both modes. Three blocks of 120 measured frames per mode were interleaved with the other mode. Frame time is wall time between Slate frame callbacks, with VSync and the FPS cap disabled. The town used temporary test actors at the 24 lineup positions. A preview override retained simulation meshes on the dwarf, elf, orc and holdout so the stress test ran all 24 solvers. These are editor frame timings. Large hitches occurred in both modes.

| Test | Median off | Median on | 95th percentile off | 95th percentile on |
| --- | ---: | ---: | ---: | ---: |
| Barnaby | 13.65 ms | 13.02 ms | 121.56 ms | 120.66 ms |
| 24 wearers | 17.54 ms | 18.78 ms | 107.96 ms | 108.48 ms |

Barnaby's per-block medians overlapped, so this run could not resolve the cost of one hem. The 24-wearer run measured 1.24 ms more at the median with 1,824 dynamic particles active. The hem movement is visible and the observed clipping increased in both motions.

[Per-pose counts and frame timings](LooseHemTrial.json)
