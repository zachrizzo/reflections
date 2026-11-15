# North Market tenancy source review

These images and reports come from the east-0a job in hosted run
[43731156271](https://github.com/zachrizzo/reflections/actions/runs/43731156271).
The east job generated seven closed, decorative shop and house bays, compared
the imported overlay against its authored geometry, winding, UVs, normals and
material assignments, and rendered before/after views with matching cameras.
They are Blender source previews, not screenshots from the game.

The generated [overlay OBJ](../tenancies_overlay_east_0a73564b.obj) is kept
beside the original OBJ, material library and texture folder so its material
references resolve. The original source building and verified baseline FBX
bundles are unchanged. The complete variant can be regenerated from the
committed tenancy generator; it is the original OBJ followed by the overlay.

The doors and hatches are visual details backed by the original closed shell.
The upper facade remains repetitive and the grey background is not the
playable street. This source-art trial has not been FBX-round-tripped as a
complete variant, imported into Unreal, placed in Gray London or validated
for collision, navigation, streaming, gameplay or performance.
