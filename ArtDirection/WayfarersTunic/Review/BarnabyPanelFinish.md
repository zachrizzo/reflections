# Barnaby’s tunic surface and skin mask

Barnaby wore the Wardrobe Item at `/Game/Characters/Clothing/WayfarerPilot/Smoothed/WI_PanelTunic`. Unreal resized it from BridgeGuard. The shared pattern has smoother folds, a continuous UV chart for each fabric panel, and extra clearance at the upper torso and sleeves. Gameplay clipping remains on this wearer.

| Standing on Barnaby | Previous panel tunic | Revised panel tunic |
| --- | ---: | ---: |
| Render triangles | 6,192 | 6,192 |
| Adjacent edges bent over 45° | 1,112 | 255 |
| 95th-percentile bend | 90.6° | 25.2° |
| Extra waist circumference | 96.4 mm | 77.7 mm |
| Intersected body triangles before masking | 218 | 202 |
| Intersected head triangles | 73 | 0 |

**What hiding skin accomplished.** The item's Body Hidden Face Map fully covers 4,525 triangles on the torso and covered upper arms. The bake protects the neck, forearms and hands and reserves clearance around the collar, cuffs and hem. The closest conservative bound from a garment opening to any body triangle potentially affected by the mask was 5.3 mm across the neutral pose, 67 direct-clip poses, and 28 fresh gameplay samples. This includes partially covered triangles and texture-filter margins. The installed texture matched the measured image pixel for pixel. [Epic’s outfit masking workflow](https://dev.epicgames.com/documentation/metahuman/testing-and-configuring-your-parametric-outfit-asset)

In neutral stance all 202 remaining body intersections were on fully exposed skin. Dominant skin weights placed 130 on the upper arms. During the 20 samples with an active gameplay healing cast, the mask fully covered up to 34 intersected triangles in a single sample. All 20 samples still had exposed intersections. The next fit test should isolate the sleeve opening and its weights, then compare arm clearance on the same cast. One wearer and one gameplay action were tested. The motion measurements use bone-skinned geometry.

[Per-pose measurements](BarnabyPanelFinish.json) · [Original pilot](BarnabyPanelPilot.md) · [Shared pattern](../../../Tools/ClothingFit/build_panel_pilot.py)
