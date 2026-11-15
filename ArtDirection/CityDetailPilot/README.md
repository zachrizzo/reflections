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
