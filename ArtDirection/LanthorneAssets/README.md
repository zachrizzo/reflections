# Lanthorne props and wardrobe

Unreal assets are organized under `/Game/LanthorneAssets`, with separate Props and Clothing folders for each district. The [preview sheet](Preview.jpg) shows the textured FBX outputs. The [References](References) folder contains one original ImageGen reference per mesh. [Source](Source) contains the exchange FBXs and the corresponding base-color atlases.

| District | Props | Garment and fitting body |
| --- | --- | --- |
| Pewterside | Archive chair, archive desk, archive shelf, canal bollard, canal crate, canal lamp, hand pump, reader wand | Archivist jacket fitted to the Coin Clerk body |
| Giltside | Archive coffer, archive lantern, closed grimoire, marble urn, mirror pedestal, mirror staff, open spellbook, patrol shield, reading lectern | Apprentice vest fitted to the Archive Apprentice body |
| Frostside | Broken column, iron brazier, lookout helmet, lookout standard, mirror shrine, mirror sword, provision crate, rune waymarker | Lookout tunic fitted to the Iven body |

Hunyuan3D-2 reconstructed the geometry locally from the ImageGen references. Blender reduced the static meshes and fitted the garments using the project's existing MetaHuman wardrobe workflow. The 1024 × 1024 base-color atlases use reference projection. The reverse surfaces of several pieces use a solid material, and projection stretch is visible on some side faces.

The held props use hand-centered pivots with the shaft or blade along +X. The environment meshes use floor-level pivots and simple collision. The library furnishings are individual meshes for level dressing. The garments are skeletal meshes with normalized weights on the matched skeletons.

The [Unreal verification report](Verification/verified_delivery.json) records a successful package and material load for all 28 meshes in Reflections. It also records static-mesh dimensions and collision counts from import, plus the garment skeletons. The [static FBX round-trip](Verification/roundtrip_static.json) and [garment fitting audit](Verification/clothes.json) cover the source exports. In-game placement, attachment, and animated garment fit review are pending.
