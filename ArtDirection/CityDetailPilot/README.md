# Gray London street-detail pilot

Three original, modular 4 m shopfront overlays add modeled doors, display
windows, pilasters, cornices, and striped awnings to the introduction street
near Great Tower Street / Mark Lane. The fascia panels are intentionally blank.
They are shallow visual additions over the existing city geometry; their actors
have collision disabled so the existing wall and road remain authoritative.

The Unreal assets are in `/Game/GrayLondon/CityDetailPilot/`. Four separate
World Partition actors, labeled `CityDetailPilot_1` through `CityDetailPilot_4`,
form the trial. Their positions were derived from wall and ground traces, and
the imported meshes have UVs, assigned materials, base-center pivots and
approximately 4.07 m × 3.20 m face dimensions. The FBX files and reproducible
Blender scripts are in this folder. `shopfront_preview.png` is a Blender studio
render; `unreal_base_color.png` is an Unreal base-color pass, not a lit render.

This is a small placement and geometry pilot, not a finished city art pass.
The flat-color materials need surface texture, weathering and more local
variation. The overlays have not been visually checked in the main lit editor
viewport, play-tested, or tested after a World Partition unload and reload.
Decorative doors do not open. Check lighting, navigation, ground contact, and
streaming before copying the modules to other streets.

## Next production passes

1. Validate this four-bay sample from the actual gameplay camera, in a lit
   viewport and on foot. Adjust the height, orientation and colors against
   the underlying building; compare with the rest of the street before any
   bulk placement.
2. Build out the player route from the intro corner to Byward Street, Tower
   Hill and Leadenhall. Give each block a few different entrances and shop
   windows, plus curb, pavement, signs and street furniture. Keep 1.5 m of
   walkable clearance and verify it against the actual player capsule.
3. Replace the flat fills with a small shared library of tileable stone,
   painted wood, metal, glass and canvas materials; add restrained dirt and
   wear. Keep color and roughness consistent with the existing district.
4. Use custom landmark treatments for the places players approach or see in
   close shots; keep the geographic massing for the distant skyline. For
   irregular hero props, image-to-3D is an option, followed by mesh cleanup,
   UV/material checks, simple collision and a deliberate pivot. Straight
   facade modules and repeated details are better controlled as modular
   geometry.
5. Profile the completed street with real lighting and World Partition
   streaming. Consolidate repeated meshes or use instances where appropriate;
   verify collision, pathfinding and HLODs before spreading the kit citywide.

Independent source modeling, reference gathering and material work can run
concurrently. Editor imports, placement and saves should be coordinated in the
shared editor. The previous local Hunyuan3D-2 workflow has geographic licence
restrictions that require review before its outputs are selected for release.
