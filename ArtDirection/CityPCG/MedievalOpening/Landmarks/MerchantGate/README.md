# Merchant hall gateway reference

`References/merchant_gate_imagegen_v1.png` is an original built-in ImageGen
reference for a possible late-medieval London guildhall gateway. It is not an
in-game screenshot, a 3D mesh, or a one-for-one historical reconstruction.
The City of London's [medieval walk](https://www.cityoflondon.gov.uk/assets/Things-to-do/medieval-city-self-guided-walk.pdf)
describes merchant halls with shops on the street and gateways to courtyards.

Use this as a source for a distinctive image-to-3D landmark or a hand-built
mesh, after finding a suitable plot. The arch must stay truly open: inspect the
generated mesh for filled-in passages, repair it if needed, and validate the
player capsule, ground, collision and navigation in the actual map. Survey
adjacent roads and story actors before deciding where it belongs. Plot selection
and in-map validation are pending.

## MIT-licensed local alternative

The official [TripoSR code](https://github.com/VAST-AI-Research/TripoSR) and
[pretrained model](https://huggingface.co/stabilityai/TripoSR) are MIT-licensed.
The upstream project lists about 6 GB of GPU memory for its default single
image run. This is a candidate for regions where the installed Hunyuan model's
output terms below are unsuitable. Two remote TripoSR trials from the original
reference and a [transparent square cutout](References/ImageTo3D_Cutouts/README.md)
produced warped, fragmented gate meshes with slab-like surfaces; one also
showed a likely blocked arch. Neither is suitable for game placement. They are
not tests of the separate pinned local runner, which still needs its first real
generation and Windows, UV and Unreal import checks.

For a reproducible local setup, use a fresh directory under this project's
`Saved/CityPCG/ImageTo3D` and the following pinned revisions:

```powershell
$base = 'Saved/CityPCG/ImageTo3D'
$source = "$base/TripoSR-upstream"
$model = "$base/TripoSR-model"
git clone --filter=blob:none --no-checkout https://github.com/VAST-AI-Research/TripoSR.git $source
git -C $source checkout --detach 107cefdc244c39106fa830359024f6a2f1c78871
New-Item -ItemType Directory -Path $model
Invoke-WebRequest -Uri 'https://huggingface.co/stabilityai/TripoSR/resolve/5b521936b01fbe1890f6f9baed0254ab6351c04a/config.yaml' -OutFile "$model/config.yaml"
Invoke-WebRequest -Uri 'https://huggingface.co/facebook/dino-vitb16/resolve/f205d5d8e640a89a2b8ef0369670dfc37cc07fc2/config.json' -OutFile "$model/dino_config.json"
python -B Tools/CityPCG/fetch_triposr_weights.py
```

The 1,677,246,742-byte checkpoint is pinned to SHA-256
`429e2c6b22a0923967459de24d67f05962b235f79cde6b032aa7ed2ffcd970ee`.
The fetcher keeps a partial file and resumes in short sessions, publishing
the completed checkpoint only after checking that hash. It defers during an
editor lease or build, a closed editor, or low memory. Re-run it in an idle
window until verification completes. The fetcher's resume, lock and hash checks
pass small offline tests; the full network transfer has not run yet. The
[isolated inference runner](../../../../../Tools/CityPCG/README_MERCHANT_GATE_TRIPOSR.md)
has passed guard and synthetic geometry tests, but its first real generation
is still needed; fetching files alone produces no 3D asset.

## Prepare a local trial

The gray opening in the reference shows the intended rear exit. The stone jambs, dark interior and visible floor make it a useful single view for geometry conditioning. Its rear elevation, actual arch depth and covered ceiling still need review because the image only shows one side. The street paving in the foreground is reference context and can be removed from the mesh. Keep the original PNG and its hash in `source_metadata.json`.

The installed Local3D CLI has the Hunyuan3D-2.0 geometry weights, Python environment and background-removal model. Start when the shared Unreal Editor is idle and there is enough free GPU memory and system RAM for the geometry pass. Run one pass in a fresh scratch folder. Keep the generated `_input.png` to check whether background removal left the opening intact, and retain the model's JSON sidecar. The GPU run and any texture pass are still pending.

```powershell
$local = 'C:/Users/zachc/tools/Local3D'
$landmark = 'ArtDirection/CityPCG/MedievalOpening/Landmarks/MerchantGate'
$ref = (Resolve-Path "$landmark/References/merchant_gate_imagegen_v1.png").Path
$out = 'Saved/CityPCG/MerchantGate/hunyuan_geometry_seed1450'
if (Test-Path $out) { throw 'Choose a fresh run folder' }
& "$local/.venv/Scripts/python.exe" "$local/generate_mesh.py" --image $ref --output "$out/MerchantGate_raw.glb" --steps 30 --resolution 384 --seed 1450
```

The Hunyuan 3D 2.0 community license prohibits using, reproducing, modifying, distributing or displaying the model's outputs in the EU, UK, and South Korea. Record the model, checkpoint and seed for generated meshes, and carry that provenance through mesh repairs and baked textures. For release in those territories, a separately authored mesh can use the original ImageGen reference. [Pinned Tencent license, §1(l) and §5](https://raw.githubusercontent.com/Tencent-Hunyuan/Hunyuan3D-2/f8db63096c8282cb27354314d896feba5ba6ff8a/LICENSE)

## Normalize and check the passage

1. Import the raw GLB into a separate Blender scene. Remove floating fragments and detached background or street slabs. Orient the visible entrance toward local +X with +Z up. Work in metres. Use a uniform fit to approximately 13 m wide, 8 m tall, and 7 m deep. Center the pivot on the ground between the two piers and bake object transforms into the vertices. If the proportions cannot fit the tolerances in `source_metadata.json` without distorting the gate, use a different candidate or rebuild the shell.
2. Inspect both ends and an interior section of the arch. If the generator has put a skin across either end or filled the interior, keep the stone jambs and roof and rebuild the opening as one through-cut. Fit a pointed arch cutter along local X from beyond the entry to past the rear wall. Repair the newly exposed jambs and the vaulted surface, review winding and normals, and repeat the check after simplification. If the scan is unsuitable for a clean cut, make the traversable arch and walls with clean authored topology, then use allowed generated pieces only for ornament.
3. Export one selected mesh to a Y-up glTF 2 binary with a baked identity node and no collision helpers. Check it with regular Python:

```powershell
python Tools/CityPCG/audit_merchant_gate.py Saved/CityPCG/MerchantGate/MerchantGate_baked.glb --report Saved/CityPCG/MerchantGate/geometry_audit.json
python -m unittest discover -s Tools/CityPCG -p test_merchant_gate_audit.py
```

The audit checks metre dimensions and ground pivot. It tests every triangle against a continuous 2.5 m wide by 2.7 m high corridor through the entire mesh depth, above a 6 cm floor band, and checks that the opening is clear centrally at 3.05 m. Separate samples require both piers and a header with deep bearing. A nonzero exit means aperture, scale or export repair is needed. This check covers the mesh, so viewport review, capsule sweeps and navigation are still needed later.

Optional Local3D paint runs only after the passage passes. Its `texture_mesh.py` performs a new UV unwrap and creates a 2K base-color atlas from projected views. Use a separate output folder and rerun the baked mesh check with `--require-uv0` after any paint or texture transfer. Inspect the arch interior, back, timber color and roof tiles for projection errors. Record which tool produced every derivative.

## Eventual Unreal import

Use the project's Blender-to-Unreal static mesh workflow when the shared editor is idle. Check `Saved/PIE_LOCK.json` before starting Play-In-Editor. Import the reviewed candidate as a new asset under `/Game/GrayLondon/MedievalOpening/Landmarks/MerchantGate`, with no auto-generated convex hull. Preserve UV0, normals and the ordered material slots. Check approximate bounds of 700 × 1,300 × 800 cm, the ground pivot and visible +X orientation. Preview with no collision. For a placed gate, author separate simple hulls around each pier and the overhead masonry and confirm a player capsule can pass in both directions. Check the street surface and navigation, inspect both ends from the player's view, and save only the explicit package after those checks and a plot review.

## ImageGen prompt

Use case: historical-scene. Asset type: single-object image-to-3D reference
for a medieval London game landmark. Create a believable late-15th-century
London merchant guildhall gatehouse as one complete freestanding structure: a
stout pale ragstone ground floor with a broad OPEN pointed-arch cart passage
through the center and two small timber-shuttered shop bays either side; above
it a richly weathered dark-oak timber frame and warm lime plaster, a modest
first-floor jetty supported by carved oak brackets, small leaded windows, steep
uneven red-clay tiled roof and a pair of modest chimneys. The structure is
approximately 13 meters wide, 8 meters high, and 7 meters deep. Single coherent
building and roof; show the entire asset including both roof and ground, from
a slightly elevated front three-quarter view that shows the arch opening and
one side. Photorealistic game-asset reference, aged but inhabited, overcast
soft studio illumination, neutral light gray seamless background. No people,
vehicles, separate props, vegetation, text, signs, border, watermark, multiple
views, modern materials or fantasy ornament. This is a historically informed
original design, not an exact reconstruction.
