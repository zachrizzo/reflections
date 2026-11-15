# West connector whole-building models

Three closed medieval buildings are modeled for the reviewed west connector
plots: a trading range, workshop and stepped market. Their irregular
footprints, ground pivots and entrance directions follow
`../../west_connector_whole_buildings_candidate.json`; the matching generated
plan is included here. The four/two/two tiled roof ranges have staggered
ridges and inboard masonry chimneys, with different timber and shutter details.

`Source` contains the authored Blender FBXs. `UnrealSource` contains their
triangulated, Y-reflected import copies for the UE legacy FBX importer. The
manifest records source and prepared hashes, transforms, material slots,
footprints, roof profiles and Blender round-trip audits. All meshes passed
closed-solid, winding, UV, material and footprint-edge checks. The three
`*_preview.png` images are Blender renders of the same audited geometry.

These are **offline source models**, not placed or enabled in Gray London.
Fresh in-engine screenshots, import and collision validation, live actor and
route checks, and a cumulative p03_p00 replacement tile are still required.
See `Tools/CityPCG/WHOLE_BUILDING_GENERATOR.md` and
`../../NEXT_WHOLE_BUILDING_BLOCKS.md` for the generation and safety checks.
