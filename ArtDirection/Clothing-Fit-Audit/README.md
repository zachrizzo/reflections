# Clothing fit audit — 13 November 2026

These are measurements of **the Blender source fitting scenes**, not certified measurements of the meshes currently rendered by Unreal. The audit renders ten color views (eight rest poses and two synthetic Coin Clerk poses), and `fit-audit.json` contains the full per-object counts. The corresponding Blender source paths are embedded in that JSON. The hero's separate Chaos cloak is not included in `Hero_Wardrobe.blend`; see the separate hero-cloak work for that mesh and physics. The 14 November cloak fix (broken rest mesh, skinning and simulation settings) is written up in `HeroCoat-Cloth-Fix.md` in this folder. The fix for the hero's hair trailing behind the head while running is in `HeroHair-Detach-Fix.md`.

## Reading the maps

The camera faces the characters at a slight angle. Grey is a fitting body, head, or prop. Color shows each garment vertex's distance to the nearest fitting-body triangle (and, in the rest pose, the separately imported head/neck triangle):

- Blue: less than 5 mm.
- Green: 5–30 mm.
- Amber: 30–60 mm.
- Red: over 60 mm. A loose coat, hanging skirt, shoe, or layer over another garment can reasonably be this far from skin.
- Magenta: more than 2 mm on the inward-facing side of the nearest triangle according to its normal; this is a **candidate requiring visual inspection**, not proof of intersection. This overrides the distance color. Gray accessories are measured in the JSON but hidden as color to keep the picture legible.

The metric uses evaluated mesh vertices in Blender world space (one Blender unit interpreted as one meter). Median and 95th percentile are vertex-weighted, not fabric-area-weighted. Garment hems, overlapping internal layers, intentionally open designs, and absent body surfaces can dominate their scores. Missing garment coverage (such as an open neckline) cannot be diagnosed just by measuring garment vertices. Body proxy meshes are open and the head and body are separate; nearest triangle normals can point the wrong way for an inside/outside decision. Some fitting bodies are 3,328 vertices and some are 7,622. Face proxies are non-watertight and cannot establish reliable solid collisions. Hair and actual UE LODs are not included.

For the Coin Clerk's `reach` and `stride` images, small scripted rotations are applied to upper arm and thigh bones. These are synthetic checks, not actual sample locomotion or full animation playback. The head proxy in the scenes has no armature, so it is omitted from the proximity calculation in posed checks; its apparent position in the render is only a static reference. No full movement collision-free claim follows from these tests.

## Source/Unreal correspondence

Matching filenames and prior import scripts were checked, but no mesh hash/equality comparison with the current Unreal assets was performed. Therefore each row is a source-scene measurement and **asset correspondence is indicative, not verified**. The live Blueprint's current component choices were not verified for all characters. Timestamps are local system times and can change due to unrelated saves.

| Source character | Matching Unreal assets observed | Status and caveat |
|---|---|---|
| Coin Clerk | `/Game/Characters/RedLondon/CoinClerk/Outfit/SK_CoinClerk_*` | Merchant scene objects use `SK_Merchant_*` source names. Separate `SK_CoinClerk_FittedCollar` is an isolated preview candidate and is not included in these metrics or the original production character. |
| Ferry Pilot | `/Game/Characters/RedLondon/FerryPilot/Clothing/SK_FerryPilot_*` | Scene last saved 19:28, striped tunic asset 19:15: source can be newer; do not assume rendered geometry matches. |
| Bridge Guard | `/Game/Characters/RedLondon/BridgeGuard/Wardrobe/SK_BridgeGuard_*` | Matching asset names exist; exact imported mesh and active components not independently verified. |
| Festival Drummer | `/Game/Characters/RedLondon/FestivalDrummer/Wardrobe/SK_FestivalDrummer_*` | Matching asset names exist; exact imported mesh and active components not independently verified. |
| Archive Apprentice | `/Game/Characters/RedLondon/ArchiveApprentice/Outfit/SK_ArchiveApprentice_*` | Source objects retain `SK_Merchant_*` names. Refit import script targets the coat; waistcoat asset predates the source scene save. Exact equivalence unverified. |
| Glass Artisan | `/Game/Characters/RedLondon/GlassArtisan/Outfit/SK_GlassArtisan_*` | Source objects retain `SK_Merchant_*` names. Refit import script targets the coat, apron and glass; waistcoat asset predates the source scene save. Exact equivalence unverified. |
| Iven | `/Game/Characters/WhiteLondon/IvenRook/MetaHuman/Clothing/SK_Iven_*` | Matching asset names exist. Scene measures work tunic, rag skirt, sandals, tattoo and glyph; it does not measure the separate legacy linen-wrap asset. |
| Hero | Hero wardrobe source, `SK_HeroCoat` and `SK_HeroTails` | Wardrobe scene only; no separate simulated cloak mesh. Hero outfit and cloak are being checked independently; the current assembled sample-character components are not independently verified here. |

## Representative measurements

| Source | Object | Median distance | 95th percentile distance | Nearest-normal candidate count |
|---|---|---:|---:|---:|
| Coin Clerk | Coat | 42.27 mm | 126.84 mm | 815 / 6,838 vertices |
| Coin Clerk | Waistcoat | 20.68 mm | 55.79 mm | 885 / 6,550 vertices |
| Ferry Pilot | Striped tunic | 21.27 mm | 79.88 mm | 560 / 6,174 vertices |
| Bridge Guard | Gambeson | 24.48 mm | 80.82 mm | 1,231 / 17,856 vertices |
| Festival Drummer | Blouse | 18.60 mm | 43.35 mm | 443 / 7,786 vertices |
| Archive Apprentice | Coat | 39.54 mm | 78.58 mm | 559 / 6,602 vertices |
| Glass Artisan | Coat | 32.07 mm | 55.82 mm | 778 / 6,602 vertices |
| Iven | Work tunic | 26.50 mm | 46.87 mm | 702 / 17,368 vertices |
| Hero | Coat | 28.96 mm | 67.17 mm | 2,057 / 16,214 vertices |

These are not collision counts and must not be compared as pass/fail scores: the objects have different layers, topology, and intentional silhouettes. In the Coin Clerk preview, a replacement collar was tested separately, but it did not resolve the existing upper-chest coverage and shoulder gaps. It was not applied to the production Blueprint. A garment rebuild and testing through actual animation in Unreal remain necessary before claiming a production fix.

Run the audit again from the project root using Blender 5.3: `blender -b --python ArtDirection/Clothing-Fit-Audit/audit.py`. The script opens source scenes in memory and writes only audit outputs; it does not save or modify those scenes.
