# Wayfarer’s Tunic

One Wardrobe Item assembles the tunic on the Test Town lineup and new MetaHumans. Select `WI_WayfarersTunic` in the character’s **Outfits** slot and assemble the preview. Unreal picks a reference size, resizes the garment to the current body and transfers skin weights. The four reference sizes are BridgeGuard, Dwarf, Elf and Orc. The new character, `MHC_TunicFieldTest`, has a 170 cm height target and was held out of garment authoring.

[Numeric fit scorecard](Review/FitScorecard.md) · [All 24 standing previews](Review/Standing24.jpg) · [Five characters in four poses](Review/MotionReview.jpg) · [New MetaHuman in motion](Review/NewMetaHumanMotion.gif) · [Measurements by character](FitReview.json)

## Sizing and motion in Test Town

The original pattern carried the deepest chest measurement down to the hem. The revised front smooths across each horizontal section and slopes gradually from chest to waist. A shared neckline, sleeve openings and skin coverage maps apply to every character. The orc’s median front-waist clearance on the authoring mesh went from 93.5 mm to 11.8 mm.

| Authoring mesh | Median front chest gap (mm) | Median front waist gap (mm) |
| --- | ---: | ---: |
| BridgeGuard | 18.4 | 9.1 |
| Dwarf | 12.6 | 6.3 |
| Elf | 18.5 | 13.6 |
| Orc | 18.1 | 11.8 |

Unreal resized the garment on all 24 targets. The earlier panel bridged across the widest point of an entire chest or waist section. Bounding the fabric depth at individual columns reduced the orc’s maximum front chest gap from 76.4 to 32.9 mm and its maximum front waist gap from 59.2 to 14.8 mm. A separate clearance limit on top of the shoulder addresses excess height after smoothing. The pattern measures the full 128-ray waist ring against each reference body and adjusts the garment toward 55 mm of extra circumference. The same rule runs for all four sizes. Across the final lineup, the largest sampled front chest, front waist and shoulder gaps were 34.3, 20.9 and 24.8 mm, respectively.

Each character was sampled at rest and at 22%, 50% and 78% of a walk, crouch walk and healing cast. The body-following test passed on 24 of 24. Independent fabric swing would require a simulation mesh. The full numeric fit verdict is **0 of 24 passing**. The scorecard identifies remaining contacts with unmasked body triangles and separately reports bare-body self-intersections in the same poses. The gray preview material on the new character does not declare the coverage parameter in its material interface, so the audit conservatively treats its black-mask contacts as unresolved. Facial skin and mask transitions also remain unclassified. The face temporarily followed the body during motion sampling. Cooked gameplay and additional LODs remain unverified.

Across the full lineup, extra waist circumference ranged from 3.9 to 5.9 cm. At the waist of the new character, the 128-ray horizontal section measured 91.7 cm around the body and 96.7 cm around the tunic. The extra circumference was 4.9 cm.

## Reproduce the checks

1. Build the project’s editor target and open Test Town. In Unreal’s **Python** console, run the following to restore the temporary lineup and reapply the saved Wardrobe Item. Repeat after reopening the editor.
2. Run the capture script in the same console with the lineup in its neutral pose. It records posed body, face and garment vertices and triangle indices under `Intermediate/WayfarerReview/surfaces`.
3. Run the Blender audit from the project root to measure all captured poses. It reports body intersections, changes in distance to tracked skin points, edge stretch and neutral chest and waist clearance.

```python
from pathlib import Path
import runpy, unreal
tools = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())) / "Tools/ClothingFit"
runpy.run_path(str(tools / "show_tunic_lineup.py"), run_name="__main__")
runpy.run_path(str(tools / "capture_lineup_motion.py"), run_name="__main__")
```

```powershell
blender --background --python-exit-code 2 --python Tools/ClothingFit/audit_posed_surfaces.py -- Intermediate/WayfarerReview/surfaces FitSamples.json --body-mask ArtDirection/WayfarersTunic/Source/T_WayfarersTunic_BodyMask.png
python Tools/ClothingFit/score_tunic_fit.py FitSamples.json FitScorecard.json --markdown FitScorecard.md
```

The score command returns exit status 1 when any wearer fails the numeric checks. The defaults are working limits for this tailored tunic. Pass the limit arguments to evaluate a different fit specification.

## Rebuild the shared garment

1. Export the four combined skeletal fitting bodies from `/Game/Characters/Clothing/OA_WayfarersTunic/Source` as LOD 0 FBXs and name them `<Size>_FullBody.fbx`. Run these commands on that directory. The pattern generates all four sizes and the UV coverage used for the body and head masks. The mask script uses Pillow.

```powershell
blender --background --python-exit-code 2 --python Tools/ClothingFit/build_wayfarers_tunic.py -- <fitting-directory> BridgeGuard Dwarf Elf Orc
python Tools/ClothingFit/bake_tunic_coverage.py <fitting-directory> BridgeGuard Dwarf Elf Orc
```

2. Copy the generated FBXs and PNGs into [Source](Source). Reimport the four static meshes and two coverage textures. Re-evaluate and save each matching `CA_WayfarersTunic_*` Dataflow, then re-evaluate and save `OA_WayfarersTunic` with all four size entries. Each entry pairs the garment with its matching combined body. Use the [source clearance audit](../../Tools/ClothingFit/audit_torso_clearance.py) for matched FBXs, then run the resized-output checks above. [Epic’s FBX workflow](https://dev.epicgames.com/documentation/metahuman/building-a-metahuman-parametric-outfit-with-an-fbx-export) · [Epic’s sizing workflow](https://dev.epicgames.com/documentation/metahuman/create-a-metahuman-parametric-outfit-asset)
3. The tunic’s Wardrobe Item uses the project’s `AnimatedOutfitEditorPipeline`. In UE 5.9, the stock character preview can bind the garment to the root while face rig data is pending. This project setting keeps weight transfer enabled for a valid multi-bone fitting body during preview and delegates resizing to Unreal. Reuse that editor pipeline on new garment items to support motion on newly created characters. The two wardrobe skin masks share conservative coverage across references. [Epic’s fit and masking guide](https://dev.epicgames.com/documentation/metahuman/testing-and-configuring-your-parametric-outfit-asset)

## Wardrobe and source art

Runtime selection across prepared garments uses shared MetaHuman Collection slots and MetaHuman Instances. Runtime swapping and layered garment combinations still need gameplay tests. [MetaHuman Collections](https://dev.epicgames.com/documentation/metahuman/metahuman-collections-in-unreal-engine) · [MetaHuman Instances](https://dev.epicgames.com/documentation/metahuman/metahuman-instances-in-unreal-engine)

[Editable Blender source](WayfarersTunic_Source.blend) · [Original generated concept](WayfarersTunic_Concept.png)

<details>
<summary>Concept image prompt</summary>

Game asset concept art of exactly one original fantasy garment, front and back orthographic views of the same garment next to each other on a neutral parchment studio backdrop. Show ONLY an empty wearable short-sleeve tunic, no person, no mannequin, no accessories, no weapons, no writing, no annotations. Design: a practical forest wayfarer's fitted woven linen tunic, muted deep teal / spruce fabric, sleeves ending mid upper arm, hem ends at the hips, subtly flared at hem, clean collar opening and a small V notch finished with narrow antique gold edge binding. Slim antique gold narrow woven braid at sleeve cuffs and hem. A small stitched gold diamond at mid upper chest. Slight vertical tailoring seams, minimally wrinkled. No belt, no cape, no armor. Front and back clearly readable, entire silhouette fits with margins, consistent dimensions for modeling. Realistic understated high-quality fantasy RPG prop visualization, soft diffuse light, three-dimensional but strictly orthographic, no heavy shadows.

</details>
