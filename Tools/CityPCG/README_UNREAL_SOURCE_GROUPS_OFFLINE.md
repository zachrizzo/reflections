# West Mark Lane offline source geometry comparison

This check compares the saved `Tile_p03_p00.uasset` source MeshDescription to
the original, filtered, and named-import GLBs without Unreal Editor. For the
currently pinned files, all six source polygon groups match one distinct GLB
primitive by exact signed triangle geometry. The source group whose
`ImportedMaterialSlotName` is `GL_Road` contains 18,340 triangles and maps to
primitive 2; all of those triangles occur in both the filtered and named
import GLBs. This is **offline source-geometry evidence**, not authorization
to activate the pilot.

Unreal's `SectionInfoMap` can assign a different runtime material slot to a
source section. The actual live section-to-slot binding, actor identity and
transform, current filtered Unreal asset, collision, navigation, streaming,
visual quality, and gameplay must still be checked during an allocated editor
handoff. Keep the replacement disabled until those checks pass.

## Inputs and reproduction

The reproducible decompressor is
`Tools/CityPCG/decompress_west_mark_lane_source.py`. It reads the pinned source asset and
the `oo2core.dll` already installed with Unreal 5.9, without copying or
distributing that DLL. It requires the separately installed local `blake3`
module under `Saved/CityPCG/OfflineGeometryDeps`. Its compressed-buffer header
and block table are CRC-checked; each Oodle output size, the full decompressed
length, the full 32-byte BLAKE3 and the original asset hash before/after are
checked. It writes only the fresh payload path below and refuses to overwrite.
If the default payload does not already exist, run:

```powershell
python Tools/CityPCG/decompress_west_mark_lane_source.py
python Tools/CityPCG/test_decompress_west_mark_lane_source.py -v
```

The decoder refuses to overwrite any output. To repeat the check when the
default file already exists, specify a **fresh** file under `Saved` with
`--output Saved/CityPCG/MedievalSurvey/Tile_p03_p00_mesh_payload_repro.bin`.
If the external Python package is missing, it can be installed into an
isolated local folder without changing the shared environment:

```powershell
python -m pip install --target Saved/CityPCG/OfflineGeometryDeps blake3==1.0.11
```

The verified payload is
`Saved/CityPCG/MedievalSurvey/Tile_p03_p00_mesh_payload.bin` with SHA-256
`147621d39e17a2288a7559e8fa846ed07e3090e384d4855b266891d29953f83c` and
BLAKE3 `894085384a512d1de43b1f6ced6c5b491153308e264e0ec3bc2e35a60c782a07`.
Its source asset SHA-256 is
`fad42a2a33c47b14298e5206fbbd3f3e60b3124ea8316f4f35077539824673f1`.
The clean comparator checks both SHA-256 values independently; the preceding
decompression is what establishes their relationship.

The comparator requires Node.js and the external MIT-licensed
`@threenative/raw-unreal` **0.1.13** `dist/index.js`; it checks the exact
SHA-256 `bff54c6adf1958211246cbd571ad55d70628c14bfaf74deb572d31fc4eec0d70`.
It does not vendor the package or require its three.js renderer. In this
checkout the independently downloaded, registry-integrity-checked package is
under `Saved/CityPCG/UAssetResearch/raw-unreal-0.1.13/package`. With that
external parser and the verified payload present, run:

```powershell
python Tools/CityPCG/verify_unreal_source_groups_offline.py --parser-js Saved/CityPCG/UAssetResearch/raw-unreal-0.1.13/package/dist/index.js
python Tools/CityPCG/test_verify_unreal_source_groups_offline.py -v
```

For a fresh checkout, obtain the parser separately into a fresh Saved folder;
the comparator verifies the extracted `dist/index.js` hash before using it:

```powershell
New-Item -ItemType Directory -Path Saved/CityPCG/RawUnrealParser -ErrorAction Stop
npm pack @threenative/raw-unreal@0.1.13 --pack-destination Saved/CityPCG/RawUnrealParser
tar -xzf Saved/CityPCG/RawUnrealParser/raw-unreal-0.1.13.tgz -C Saved/CityPCG/RawUnrealParser
python Tools/CityPCG/verify_unreal_source_groups_offline.py --parser-js Saved/CityPCG/RawUnrealParser/package/dist/index.js
```

The pinned parser does not support UE 5.9's FName-array unique-name table.
`extract_unreal_source_groups.mjs` checks the original parser hash, applies a
small in-memory adapter based on the installed UE 5.9
`MeshAttributeArray.h` serialization, and rejects duplicate attribute and
element names. It uses in-memory rendering stubs only to satisfy imports;
no three.js rendering functionality is called. Parser changes or a different
asset or payload fail closed rather than selecting another format.

The extractor requires the payload to be fully consumed, validates dense
element IDs, attribute types and lengths, polygon/triangle group links,
vertex-instance and vertex indices, finite positions, nondegenerate faces,
unique nonempty imported slot names, and no signed triangle shared between
source groups. Each source vertex is converted from UE centimetres to glTF
metres with UE's float32 `0.01` scale and `(X,Z,Y)` axis order. Triangle
winding is preserved, with only cyclic rotations treated as identical. The
comparison counts multiplicities and requires a unique bijection between the
source groups and GLB primitives, then checks the exact pinned filtered and
named-import GLB hashes and the retained road geometry. It never infers a
source match from material names or triangle counts alone.
