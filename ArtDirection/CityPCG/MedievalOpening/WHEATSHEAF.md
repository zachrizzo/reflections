# Wheatsheaf hanging sign

The sign uses an original built-in ImageGen reference of a clipped oak plaque
with worn ochre wheat and an iron eye, designed as a c. 1450 trade sign. The
source image is `Textures/T_GLMedieval_Wheatsheaf.png`. The front texture and
raised grain follow that image. The rear, iron eye and bent hanger are modeled
to complete the prop from oblique views.

Rebuild from the repository root with Python, NumPy and Pillow, then Blender.

```powershell
python ArtDirection/CityPCG/MedievalOpening/build_wheatsheaf_relief.py Saved/MedievalOpening/WheatsheafSign
blender --background --factory-startup --python ArtDirection/CityPCG/MedievalOpening/build_wheatsheaf_fbx.py -- Saved/MedievalOpening/WheatsheafSign/wheatsheaf_relief.glb
```

The FBX has an eye-centered pivot, +X face and +Z up. Its width is 30 cm,
height 49.47 cm including the hook, and depth 10.84 cm including the hook.
The painted face uses UV0, with the kit oak and lead materials for the back
and iron. The opening bay's local mount is +48 cm in front, +54 cm across and
+247.8 cm above the bay base. Run `place_wheatsheaf.py`'s `run()` in the
Gray London editor to import and place the sign at that mount.
