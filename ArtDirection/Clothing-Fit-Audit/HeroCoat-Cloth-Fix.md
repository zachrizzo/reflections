# Hero coat cloth fix: 14 November 2026

The playable hero's cloak is the `TravelDrape` component on `/Game/Characters/Hero/TravelCloak/BP_HeroTravelVisual`. That Blueprint is the `HeroVisual` child of `BP_HeroSampleCleanTest` on `Lvl_HeroSampleCrowd`. The cloak is simulated by **Chaos Cloth**, not Niagara: a legacy `ClothingAssetCommon` named `HeroCoatTails`, built by `UReflectionsHeroClothTools::BuildCoatTailSimulation`, which collides with `PHYS_MHC_Hero` (20 capsules and 4 boxes). `HeroCoat` and `HeroTails` on that Blueprint are empty and hidden.

Images: `HeroCoat_PIE_BeforeAfter.png`, `HeroCoat_PIE_Motion.png`, `HeroCoat_RestMesh_BeforeAfter.png`.

## What was wrong

- **The rest mesh was already broken before simulation.** `fit_travel_cloak.py` added a per-vertex radius "variation" sampled from the image-to-3D reconstruction. It also measured body clearance with rays cast from outside inward, and those rays switched between arm and torso hits at a hard `|x| < 0.215` cutoff. The result was zig-zag pleats down the side edges and a stepped notch at the shoulder. The radial second difference between neighbouring vertices reached 15–17 cm (95th percentile 3.8 cm), and edge lengths within one row ranged from 0.6 cm to 6.5 cm. Chaos keeps those rest lengths, so the simulated cloak kept the "flopped" vertices: a jagged hem and spiky shoulder flaps.
- **Every vertex down to the ankle hem was skinned 100% to `spine_05`.** The animated target of a 1.4 m panel therefore swung rigidly with the upper chest.
- **The simulation was very light and ran 1 iteration with 1 substep.** At walking speed the old drape lifted to horizontal behind the hero like a scarf; settled, it hung short and bunched. It travelled about a metre from its skinned position even though its painted limit was about 17 cm (48 cm × 0.35 component scale). I didn't chase that further because the asset was replaced.
- Import scale and axis were fine. The old asset's bounds match Blender ×100 with the usual Y flip. Normals all faced outward.

## What changed

- New generator: `ArtDirection/Three-Londons-Wardrobe/Hero/TravelCloak/fit_heavy_coat.py`. It writes `Hero_TravelCloak_Coat.blend` and `Intermediate/TravelCloak/SK_HeroTravel_Drape_Coat.fbx`, and leaves the source `.blend` unmodified.
  - **Geometry:** a smooth flared 65 × 51 grid (3,315 vertices). The radial second difference is now at most 1.6 cm across and 2.7 cm down (95th percentile under 1.2 cm), with at least 2 cm torso clearance.
  - **Clearance:** pushes run along the torso surface normal, and arms are ignored below the shoulder top.
  - **Skin weights:** blend from `spine_05`/clavicles at the collar down the spine to the pelvis, with up to 25% `thigh_l`/`thigh_r` at the hem.
- New asset: `/Game/Characters/Hero/TravelCloak/Clothing/SK_HeroTravel_Drape_Coat`, imported on `metahuman_base_skel`. Bounds are x ±40.8, y −33.6 to 8.7 and z 13.5 to 157.6 cm, matching Blender. The cloth was rebuilt with the existing C++ tool, giving 472 pinned and 2,843 free particles.
- Cloth settings:
  - **Mass and stiffness:** density 0.6, bending 0.9, tethers 1.0.
  - **Solver:** 4 iterations × 2 substeps.
  - **Collision:** CCD on, collision thickness 3 cm, friction 0.4.
  - **Damping:** 0.08, local damping 0.15.
  - **Pull back toward the skinned pose:** animDrive stiffness 0.06, damping 0.15.
  - **Air:** drag 0.08, lift 0.04.
  - **Momentum carried over from the character:** linear 0.4, angular 0.55, fictitious angular 0.8.
- `BP_HeroTravelVisual`: only `TravelDrape` changed. Its mesh is now `SK_HeroTravel_Drape_Coat` and its cloth max-distance scale is 0.85 (was `SK_HeroTravel_Drape_Mantle` at 0.35). Nothing else in the Blueprint, level, materials or C++ changed. To revert, set those two values back. The old mantle asset is still there.
- Verified in PIE on `Lvl_HeroSampleCrowd`: idle, walk (200 cm/s), jog (500), sprint (700), hard stop, turning while running, and settling afterwards. There were no broken vertices in any of them.

## What still looks off

- On a hard stop from a sprint, the far coat panel can still swing forward past the front shin for a moment, showing its lining. This is much reduced in the final settings and recovers within about a second.
- There is no backstop: the C++ tool only paints max distance. Leg protection comes from capsule collision plus CCD. Backpedalling with GASP strafe on, jumps, crouch, levitation and spell casts were not tested. With raised arms the upper arm can pass through the pinned mantle, because pinned particles don't collide.
- Coat, shirt and trousers are all near-black, so the coat's silhouette gets lost against the body from the side. The drape material (`M_Travel_Drape_Refit`) is all constants with no tint parameter.
- The burgundy lining flashes at the hem when the coat swings. That's intended by the two-sided material, but it reads as red flicker.
- Test setup note: someone parked a `SKM_Quinn_Simple` SkeletalMeshActor on the PlayerStart of `Lvl_HeroSampleCrowd`, so the hero spawns inside it. I left it alone and tested 3.5 m away.
