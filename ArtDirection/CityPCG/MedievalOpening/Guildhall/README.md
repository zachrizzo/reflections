# Medieval merchant hall frontage

This original merchant hall uses the squared masonry and ashlar dressings documented for London's early fifteenth-century Guildhall, plus pointed window openings and leaded glazing. The relief shield is original. The three-bay street frontage is an architectural variation for the game. [Historic England](https://historicengland.org.uk/listing/the-list/list-entry/1064675) · [City of London medieval walk](https://www.cityoflondon.gov.uk/assets/Things-to-do/medieval-city-self-guided-walk.pdf) · [Historic England medieval glazing](https://historicengland.org.uk/whats-new/research/back-issues/the-origins-and-use-of-medieval-glazing-in-england/)

| Mesh ending | Width | Height | Triangles |
| --- | ---: | ---: | ---: |
| `WestWing` | 450 cm | 1318.77 cm | 5,396 |
| `Portal` | 450 cm | 1460.57 cm | 5,364 |
| `EastWing` | 450 cm | 1267.28 cm | 5,384 |
| `Frontage` | 1350 cm | 1460.57 cm | 16,144 |

All four use the existing roof and wall cladding convention. +X faces the street, Y spans the facade, and +Z is up. The origin is the wall plane at the lower center seam. Keep the existing shell for collision. Set the actor and imported mesh collision profile to `NoCollision`, with automatic collision off. The portal's doors are decorative. The maximum outward projection is 71 cm, and most of the field stone wall projects 22 cm. The roof return goes about 18 cm behind the wall plane. Check the underlying roof and adjoining facade edges from an oblique view before placing a module.

The kit manifest lists each FBX and its ordered slots. Reuse existing medieval oak, glass, lead, and clay tile materials. For the three new slots, build `M_GLMedieval_GuildRubble` and `M_GLMedieval_GuildAshlar` from the supplied UV0 base color tiles, and use the solid `GuildDressed` material for the carved stone trim. Share the materials across modules. Import with material and texture generation disabled if binding existing or explicitly authored materials.

The south Leadenhall approach has an offline candidate in `Saved/MedievalOpening/lantern_release_check.json`, `Tile_p03_p01_82cc326dcbcd.0`. Its wall is 4.656 m long and 14.8 m tall. The saved point is at `(306787.375, 57652.058, 19.65)` cm, with yaw `-18.18671` and scale `(0.56, 0.976789, 0.997305)`. It sits south of the protected Leadenhall and Lloyd's bounds. Recheck wall continuity, roadway clearance, and backdrop height live before swapping its planned timber mesh for the portal.

All four FBXs reimported in Blender with identity transforms, exact manifest bounds and material order, one UV channel and no degenerate polygons. The preview is a Blender render of the exported geometry. Verify UE dimensions, slot bindings and placement in the map after import.

```powershell
python ArtDirection/CityPCG/MedievalOpening/Guildhall/build_guildhall_textures.py
& 'C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe' --background --factory-startup --python-exit-code 1 --python ArtDirection/CityPCG/MedievalOpening/Guildhall/build_guildhall.py -- ArtDirection/CityPCG/MedievalOpening/Guildhall/guildhall_preview.png
```
