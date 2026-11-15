# Medieval opening ground

This 15.12 × 12.13 m cosmetic patch replaces the asphalt appearance at the Gray London opening with original rounded cobbles, compacted earth, wheel-worn strips, and a damp drainage seam. The art is a period interpretation. It uses custom base color, normal, and roughness maps, with no photographic texture input.

The new surface fits directly over the existing pavement. The lower layer covers the city ground at Z=10 cm. The upper layer uses clipped triangles from `Tile_p03_p00` at Z=28 cm. The visual mesh is 0.7 cm above both surfaces and has collision disabled. The existing roads and ground supply gameplay collision. All 74 sampled editor traces inside the mesh outline matched its two underlying surface heights.

The level actor is `GL_1450_Opening_PackedEarthAndCobbles` at `(329290, 31090, 0)` cm. Its external package is `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/C/V9/RPMHW11FBF7IBV8LMPS7BA`. Its five supporting asset packages live under `/Game/GrayLondon/MedievalOpening/Ground/SM_GL1450_OpeningGround`. The source GLB round-tripped through Blender with ten upward-facing triangles, a UV set, and three embedded maps.

Rebuild from the repository root with NumPy and Pillow. Use the original `OSM Tile_p03_p00` export with its Unreal axis convention.

```powershell
python ArtDirection/CityPCG/MedievalOpening/Ground/build_opening_ground.py Saved/CityPCG/Tile_p03_p00.glb ArtDirection/CityPCG/MedievalOpening/Ground/Source
```
