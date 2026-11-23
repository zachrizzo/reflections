# Generated garments: description to Wardrobe Item

One command takes a garment from a description (or a picture, or a textured mesh) to a MetaHuman
Wardrobe Item and tests it on every body. Nothing is edited by hand and nothing is tuned per
garment or per character.

```
C:\Users\zachc\GemXTest\.venv\Scripts\python.exe Tools\ClothingFit\make_wardrobe_item.py FieldTunic top --describe "long-sleeved slate-blue linen field tunic, notched neck, side slits"
```

Other ways in:

```
... make_wardrobe_item.py KneeBreeches bottom --image Saved\ClothingFit\Generated\KneeBreeches\KneeBreeches_Reference.png
... make_wardrobe_item.py MarketJerkin top --mesh <textured.obj> --texture <colour.png>
... make_wardrobe_item.py FieldTunic top --image <png> --over KneeBreeches     (a top fitted and tested over a generated bottom)
```

`--until image|mesh|fit|unreal|test|mask` stops early, `--redo <stage>` repeats from a stage, `--bodies A B`
tests only some bodies. Everything lands in `Saved\ClothingFit\Generated\<Name>\`; the Unreal assets
in `/Game/Characters/Clothing/VillageWardrobe/Generated/<Name>/` (`SM_`, `CA_`, `OA_`, `WI_`, `M_`, `T_`, `T_<Name>_BodyHiddenFaces`).

## Stages

| stage | what happens | script | needs |
|---|---|---|---|
| image | Codex (ChatGPT login, no API key) draws one catalog reference image | `garmentprep/reference_image.py` | Codex app |
| mesh | local TRELLIS.2 (Microsoft, MIT) through ComfyUI: shape at 1536, remeshed to one closed piece, 125,000 triangles, 4096 base colour + metallic + roughness baked from the 3D colour field; converted to OBJ + PNG | `generate_garment_mesh_trellis2.py` | GPU and about 21 GB of free memory: run it while the Unreal editor is closed; about 3 minutes |
| fit | mesh read in Blender, registered on the source body (Barnaby), fit-prepared | `register_garment.py`, `prepare_generated_garment.py` | numpy, scipy; about 2 to 5 minutes |
| unreal | static mesh, cloth asset with skin weights from the source body, resizable outfit, Wardrobe Item | `garmentprep/editor/import_garment.py` | shared editor (MCP port 8019), takes `Saved\PIE_LOCK.json` itself |
| test | item put on each body of `garmentprep/roster.json`, 51 poses captured (standing, 25 walk, 25 reach) and measured | `garmentprep/run_lineup.py`, `audit_capture.py`, `lineup_report.py` | shared editor; about 30 s of editor time and 2 minutes of CPU per body |
| mask | body hidden-face map from the source body's 51 captured poses, imported as `T_<Name>_BodyHiddenFaces` and set on the Wardrobe Item's pipeline (`BodyHiddenFaceMapTexture`) | `garmentprep/hidden_face_map.py`, `emulate_hidden_faces.py`, `editor/import_garment.py` (mask-only mode saves `T_` and `WI_` only) | about 30 s of CPU and a few seconds of editor time |

The fit stage refuses to go on if the prepared garment still crosses the source body.

## Image-to-3D generator (since 2026-11-23: TRELLIS.2)

`generate_garment_mesh_trellis2.py` runs Microsoft TRELLIS.2 4B with ComfyUI's built-in nodes, no window
(install: `C:\Users\zachc\tools\ComfyUI`, ComfyUI 0.46, Python 3.11, torch 2.11 cu128; models from
`Comfy-Org/TRELLIS.2` (bf16, MIT), DINOv3 ViT-L image encoder (Meta DINOv3 licence, commercial use allowed),
BiRefNet background removal (MIT)). No RMBG-2.0 (non-commercial) and no nvdiffrast (non-commercial); the texture is
baked by ComfyUI's own PyTorch code. It replaced Hunyuan3D-2, whose licence does not cover the EU, the UK and South
Korea. Measured on the red tunic and the long-sleeved shirt (same Codex pictures): one closed piece like Hunyuan's,
a 4096 texture with every texel baked from the 3D colour field (Hunyuan: 2048, of which only 27-33 % came from its
six views, the rest was filler), even colour without blotches or streaks, and in Unreal the tunic's long dark flap
lines at both armholes became one small nick. Fit and motion numbers on 8 bodies were about the same (the fit step
decides those). The `udf` remesh variant tears the hems and cuffs; use `solid` (default).
Memory: on this PC every GB of video memory is also charged to the Windows commit limit; a run used 17-19 GB,
so it does not fit next to the open editor. The script refuses to start under 21 GB free and stops ComfyUI by
itself if free memory falls under 2 GB. Ask the orchestrator for an editor-closed window.

## What the fit preparation does (`prepare_generated_garment.py`)

1. Splits triangle edges that are too long to bend. Original vertices, UVs and the texture mapping are kept.
2. Finds cloth buried in the body. Cloth that the spine or neck bone passes through (the flat neck hole
   of a garment made from a front view) is brought out on the side the bone leaves it by: lifted onto
   the shoulder where that is short, otherwise out sideways. All other buried cloth leaves by the nearest wall.
3. For a sleeveless top (detected: cloth at the shoulders, none around the upper arms) keeps the cloth
   off the resting upper arm and close to the trunk where the hanging arm swings. Sleeves and trouser
   legs (cloth all the way round a limb) are pulled in to hug the limb, and a sleeve or leg that runs on
   past the wrist or ankle is shortened below the elbow or knee so it ends 1.5 cm past the wrist joint
   (3 cm above the ankle joint): the hands and feet stay free and the cuffs stop sweeping through the
   trousers (`end_limbs_at_joints`; the first field tunic covered the hands with 15 cm of sleeve).
   Bottoms: registration may not hide a waistband in the belly (no 3% allowance as for a top's flat neck
   hole), and after the legs are turned onto the leg bones the crotch seam is put 1.5 cm under the body's
   crotch (`register.align_crotch`: the rise is stretched, the legs move down and the length rule ends them
   at the ankle again). The neck-hole rule of step 2 only runs for garments that reach the neck.
4. Spreads the correction over the mesh as a smooth displacement with sliding contact, keeps the two
   walls of the cloth stacked, keeps surface relief, and repeats exact triangle tests until nothing
   crosses the skin or the layer underneath.

5. Torn facing: an inner wall (a turned-in waistband or hem facing) that started deep in the body can only
   come out as a long thin fin across the opening; a triangle stretched to more than 3 times its length and
   over 6 cm is dropped (`torn_triangles_dropped` in the report). The exact crossing loop runs up to 10 passes.

`PrepareReport.json` records crossings, skin clearance, hem height, edge-length change (stretch)
and self-crossing pairs before and after.

Known limit (2026-11-23): a slim long-sleeved shirt (FrostShirt) registered with 15 % of its cloth inside the
source body tore at the right underarm: buried underarm cloth leaves partly onto the arm and partly onto the
torso. Dropping the torn triangles leaves a visible hole there, keeping them leaves 17 crossing triangles. The
fix is an underarm exit plan (buried underarm cloth goes down under the arm as one piece); not built yet.

## What the test measures

Per body and pose, on Unreal captures with cloth physics off (`Audit_<tag>.json`, `Lineup_<tag>.md`):
garment triangles crossing skin (arm skin counted separately), depth, crossings of the layer underneath,
stretch, and a floor: the same garment as a 0.6 cm layer glued to the skin, which shows how much of the
contact is the body folding over itself (armpit folds).

## Body hidden-face map (`hidden_face_map.py`, rule in `layer_hide.py`)

The standard way to stop skin showing through clothes: body triangles under the garment are removed when a
character wearing the item is **built** (`MetaHumanDefaultEditorPipelineBase.cpp`, generated-assets path only; the
editor preview masks the same skin per pixel in the body material, so the pose-capture pictures show it).
One rule for every garment, from the source body's 51 captured poses:
1. a body point is hidden only if, standing, no line of sight within 60 degrees of its normal leaves the garment
   (each line is followed until it is out of the garment, up to 80 cm, so skin under loose cloth counts as covered);
2. in every other pose it is still unseen, or it is seen only because it came out *through* the cloth (the garment
   lies within 5 cm straight behind it). That second case is the skin that pokes through in motion, and it is exactly
   what the map should remove; skin seen through a real opening (neck, cuff, hem, slit) is kept;
3. 2.5 cm over the skin is kept from any kept point, and hands, feet and the neck above `neck_01` are never hidden.
The kept band next to the hidden area is painted grey: the engine pushes that skin in by up to
`MaxShrinkDistance` = 1 cm (`MASK_SHRINK` in `make_wardrobe_item.py`) instead of removing it.
The map is painted in the engine's own pixel space (UV0, red channel, `Wrap(uv * 2048, 0, 2047)`; the body UVs sit in
U 1..2) and checked with a port of the engine's `ShouldHideTriangle`. Body UVs come from `Saved\ClothingFit\BodyUV\`
(`editor/dump_body_uvs.py`). `--rule near` gives the first, cautious rule (garment within 4 cm, open sight within 8 cm),
which removed almost nothing that the test counts. `layer_hide.py <capture> <tag> [--shrink 1]` is the EMULATION:
per captured pose, garment triangles crossing the skin with and without the hidden triangles (not a build).
Hiding a garment under another garment is not something the engine does (hidden-face maps act on the body and head
only); for the tunic over the breeches it would not have helped either: those crossings were the over-long cuffs at
the thighs, which the sleeve rule above removes.

## Things to know

- Source body: `Saved\ClothingFit\SourceBody\Barnaby\` (standing surfaces and joints of
  `MHC_GiltBarnaby` wearing the travel trousers). Re-create it with `garmentprep/editor/capture_poses.py`
  if it is lost.
- `MHC_Dwarf`, `MHC_Elf` and `MHC_Orc` (body made from measurements) open in the editor with a default
  body and a default skeleton under their real head, every time, also after a commit and save. Outfits are
  then resized to the wrong body. What works: right after opening the character, re-apply its own body
  measurements and commit the body state (`set_body_constraints` then `commit_body_state`), before anything
  is assembled. That rebuilds the body, the skeleton and the body outfits are resized to. Re-applying the
  measurements without the commit repairs the standing shape only (the skeleton stays default and the
  character animates wrongly).
- The commit marks the character asset as changed, so the test does it only on QA copies
  (`/Game/Characters/Clothing/VillageWardrobe/Generated/QA/MHC_<Name>_BodyCommitted`, made by
  `garmentprep/editor/make_committed_copy.py`; `roster.json` points at them). Anything that builds those
  three characters for the game has to do the same two calls first.
- For any other character the capture still re-applies the body measurements when head and body do not
  meet at the neck, and `lineup_report.py` marks a body "motion not valid" when the skeleton does not
  belong to the body (shoulder joint not a few centimetres under the top of the body mesh).
- The shared editor keeps about 20 GB once many MetaHumans have been opened. `run_lineup.py` stops before
  a capture when less than 7 GB of memory is left to commit; `garmentprep/editor/free_memory.py` unloads
  the character packages the captures loaded.
- Only one of these commands may use the editor at a time (they share one lease owner name).
- GPU: one outside-editor GPU job at a time next to the shared editor; post in `Saved\PIE_QUEUE.md` first.
- Runtime cloth physics stays off for these items.
