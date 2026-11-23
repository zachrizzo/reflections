# GiltBarnaby tunic pilot

**Result: failed.** Unreal resized one four-panel tunic authored on BridgeGuard for GiltBarnaby. Barnaby received no pattern, mesh or weight edits. The prototype exceeded the waist allowance and crossed exposed skin in every sampled gameplay cast pose. It remains a separate pilot Wardrobe Item at `/Game/Characters/Clothing/WayfarerPilot/WI_PanelTunic`.

| Measurement | Current Wayfarer | Epic stock shirt | Panel prototype |
| --- | ---: | ---: | ---: |
| Extra waist circumference at neutral stance | 44.8 mm | 78.1 mm | **96.4 mm** |
| Median gap at front waist | 5.9 mm | 2.6 mm | 12.1 mm |
| Median gap at back waist | 4.3 mm | 21.0 mm | 27.1 mm |
| Body triangles crossed at neutral stance on skin exposed in all three outfits | 3 | 36 | 0 |
| Active gameplay cast samples crossing that skin | 25/25 | 25/25 | **25/25** |
| Peak body triangles crossed there in a gameplay cast sample | 693 | 956 | 694 |
| Largest sampled local inward distance there | 12.8 mm | 16.0 mm | 14.0 mm |
| Worst gameplay 95th-percentile edge extension | 25.4% | 20.9% | 17.8% |

The project sets 30–80 mm of extra waist circumference and a 20% edge-extension limit for this tunic. The prototype exceeded the waist limit by 16.4 mm. The back waist had more than twice the gap measured at the front. In neutral stance the prototype also crossed 218 body triangles on its own unmasked body and 73 triangles on the separate head mesh. Head-mask visibility was unverified. The zero in the comparison table applies only to the skin exposed by all three items. [Project fit criteria](FitScorecard.md)

## Motion and fit evidence

- **Reference construction.** Independent front, back and two sleeve panels were joined at their edges, leaving openings for the neck, hem and two cuffs. The 3,170-vertex reference garment underwent 25 Blender frames of gravity drape on BridgeGuard before export. Median vertex displacement during that drape was 21.9 mm. Unreal transferred the reference weights, built a single-source resizable outfit, and resized it for Barnaby. [Pattern generator](../../../Tools/ClothingFit/build_panel_pilot.py)
- **Direct clip.** The three outfits were captured separately at rest and at 67 evenly spaced times including both endpoints of the 2.2-second healing cast. Body and head topology matched across outfits and their coordinates matched within 0.1 mm at every corresponding sample. All three garments crossed common exposed body skin in all 67 moving poses. Epic's shorts were separated from its shirt by mesh connectivity.
- **Gameplay.** In a temporary Play in Editor session in Test Town, Barnaby’s body used the player’s layered animation Blueprint. The player's spell driver cast Healing Pulse. Three pre-fitted garments followed the same Barnaby skeleton simultaneously. The driver ended the cast at 1.00 seconds and Barnaby's left hand moved 33.1 cm from idle. The capture had 34 samples including idle and follow-through, with 25 while the driver reported an active cast. Actual timestamps are in the data. The longest interval was 91 ms. Metrics use LOD 0 bone-skinned surfaces. Runtime cloth physics was outside this test.
- **Where the garments crossed.** In the active gameplay samples, 746 body-triangle contacts occurred at the same place and time for all three shirts, counting recurring contacts once per sample. Dominant skin weights assigned 364 of those contacts to upper arms and 349 to forearms, or 95.6% combined. This localizes the shared failure. A comparison that changes only the arm motion can test how much the cast contributes.
- **Measurement definitions.** Circumference is the length difference between two closed 128-ray waist rings. The cast comparison counts distinct triangles on the same body mesh whose skin is confirmed exposed in all three outfits. Skin and shirt triangles were tested for actual geometric intersection. Inward distance samples vertices of crossing cloth triangles whose nearest body triangle also crosses the cloth, so it can underestimate continuous penetration. Stretch is the 95th percentile increase in shirt-edge length relative to the neutral pose, taking the worst observed gameplay sample while casting. The raw results also separate each outfit's own body mask, uncertain mask boundaries and head contacts. [Per-sample measurements](BarnabyPanelPilot.json) · [Measurement code](../../../Tools/ClothingFit/compare_panel_pilot.py)

**Next experiment.** Bring the shared pattern’s back waist into the project allowance and remeasure Barnaby at rest. Separately, hold that garment fixed and compare the same gameplay cast with and without an arm-clearance adjustment. Check both the forearm-to-garment distance and the casting hand’s trajectory at matched release times before trying more bodies.
