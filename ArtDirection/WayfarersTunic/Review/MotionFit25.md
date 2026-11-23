# Wayfarer tunic moving-hem fit test

One Wardrobe Item fitted all 24 lineup MetaHumans and the new MotionFitHoldout. The shared BridgeGuard pattern adds ease around the hips and shortens the loose-hem trial by up to 3.3 cm. The new body was created after the source was set, with requested measurements of 184 cm height, 107 cm chest, and 92 cm waist. It had no role in the garment source.

The saved item is `/Game/Characters/Clothing/WayfarerPilot/MotionFit/WI_LooseTunic`. The Play in Editor test generated a skinned triangle collider from each wearer's LOD 2 body and used the same Chaos graph and 4 cm maximum travel setting. All 25 had 114 dynamic particles in every capture. The collider construction ran in the editor test harness. Normal wardrobe assembly uses the collider authored on the shared asset.

## Results

| Motion | Sampled poses | Mean exposed hem contacts, physics off | Mean exposed hem contacts, physics on | Poses with exposed hem contact, physics on |
| --- | ---: | ---: | ---: | ---: |
| Step and turn | 425 | <0.1 | 1.3 | 58 |
| Healing cast | 625 | 104.2 | 93.1 | 481 |

The moving hem cleared all body triangles on 10 of 25 wearers through the turn. Fourteen had confirmed exposed hem intersections and one had only intersections in a mask transition. Every wearer had an exposed hem intersection at some point in the cast. The biggest per-wearer 95th-percentile hem displacement during the turn ranged from 32.0 to 40.0 mm. Across cast poses the same measurement ranged from 40.0 to 60.1 mm, which includes distortion of the render mesh under the cast pose.

The new holdout's hem moved 35.2 mm in the turn and cleared all 17 poses, even with all body triangles counted. It crossed exposed skin in 17 of 25 cast poses, with a peak of 337 intersected triangles. Barnaby averaged 0.9 exposed hem contacts during the turn. The earlier loose-hem trial averaged 113.3 in a separately sampled turn. The whole tunic still crossed exposed skin in every motion sample. 

## How the counts work

Each wearer was sampled at rest, at 17 poses during a step and scripted 60° turn, and at 25 poses through the 2.2-second healing animation clip. Chaos advanced while the poses changed. The paired comparison uses the same body pose with the bone-skinned tunic and the simulated render surface. The test used the source clips in Play in Editor, with the cast driven directly from the animation sequence.

Three early Barnaby cast samples had more than 10 mm of displacement at the 95th percentile of the upper garment. Barnaby's capture was repeated after warm-up. Across the final 25-wearer data set the maximum of that check was 6.7 mm.

A contact is a distinct body triangle intersecting cloth. The hem count tests garment triangles in the bottom 12 cm. The whole-tunic count includes the sleeves and torso. Confirmed exposed counts exclude areas verified hidden by the wardrobe mask. The existing TunicFieldTest and the new MotionFitHoldout used body materials that did not declare the mask parameter. The report keeps any contacts in their uncertain mask regions and includes all geometric contacts for both.

[Numbers for all 25 wearers](MotionFit25.csv) · [Per-pose measurements](MotionFit25.json) · [Capture script](../../../Tools/ClothingFit/run_motion_fit.py)

## Runtime cost

The revised tunic was timed in Test Town Play in Editor on a Ryzen 7 9700X and RTX 5080 at 2189 × 794. Each scenario used its own fixed camera and the same looping animation, costume, and render LOD 0 in all three modes. The test interleaved three 90-frame blocks per mode with VSync and the FPS cap disabled. Measurements are wall-clock frame intervals. Both simulation modes had 114 dynamic cloth particles per wearer. Body-shaped collision used each wearer's body LOD 2.

| Wearers | Physics off, median | Capsules, median | Body-shaped collision, median |
| --- | ---: | ---: | ---: |
| Barnaby | 19.50 ms | 20.55 ms | 20.78 ms |
| 24 | 23.68 ms | 30.20 ms | 28.96 ms |

The observed cost of physics with body-shaped collision was 1.28 ms for Barnaby and 5.28 ms for the lineup. The capsule and triangle timing blocks overlapped, so this run did not resolve an additional cost for the body-shaped collider. The lineup's 95th-percentile times were 30.73 ms with physics off, 42.22 ms with capsules, and 41.40 ms with body-shaped collision.

[Raw runtime timings](MotionFit25Runtime.json)
