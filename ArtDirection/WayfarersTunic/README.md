# Wayfarer’s Tunic

The same Wardrobe Item fits the Test Town lineup and new MetaHumans. Select `WI_WayfarersTunic` in the character’s **Outfits** slot and assemble the preview. Unreal picks a reference size, resizes the garment to the current body and transfers skin weights. The four reference sizes are BridgeGuard, Dwarf, Elf and Orc. The new character, `MHC_TunicFieldTest`, has a 170 cm height target and was held out of garment authoring.

[All 24 standing fits](Review/Standing24.jpg) · [Five characters in four poses](Review/MotionReview.jpg) · [New MetaHuman in motion](Review/NewMetaHumanMotion.gif) · [Measurements by character](FitReview.json)

## Sizing and motion in Test Town

The original pattern carried the deepest chest measurement down to the hem. The revised front smooths across each horizontal section and slopes gradually from chest to waist. A shared neckline, sleeve openings and skin coverage maps apply to every character. The orc’s median front-waist clearance on the authoring mesh went from 93.5 mm to 17.0 mm.

| Authoring mesh | Median front chest gap (mm) | Median front waist gap (mm) |
| --- | ---: | ---: |
| BridgeGuard | 20.6 | 14.8 |
| Dwarf | 13.7 | 14.8 |
| Elf | 19.4 | 20.9 |
| Orc | 19.4 | 17.0 |

Unreal resized the garment separately onto 24 bodies from that one item. Across the resized outputs, neutral median front-waist clearance ranged from 12.4 to 20.9 mm. The new MetaHuman measured 13.8 mm. Each character was sampled at rest and at 22%, 50% and 78% of a walk, crouch walk and healing cast. The actual tunic vertices moved in all 216 animated samples. For cloth vertices initially within 40 mm of the skin, the largest per-pose 95th-percentile change in distance to the same point on the skin was 1.0 mm.

The test uses LOD 0 render geometry, including underlying body and face triangles. It measures bone-driven deformation. Movement of loose fabric under gravity or wind requires a Chaos simulation mesh. The manual editor actors followed the body at the neck during motion sampling and returned to their original face driver afterward. The worst sample had 9.2% of garment triangles intersect the underlying skin (GiltBarnaby, cast 50). That includes skin covered by wardrobe masks. Inspect the open edges around the collar and underarms in the captures. Cooked gameplay and additional LODs remain unverified.

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
blender --background --python-exit-code 2 --python Tools/ClothingFit/audit_posed_surfaces.py -- Intermediate/WayfarerReview/surfaces FitSamples.json
```

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
