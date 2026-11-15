# Clothing fit: Codex garments onto MetaHuman bodies (14 November 2026)

Codex generates the garments (image, then image-to-3D; request `ArtDirection/CodexRequests/2026-11-14_clothing.md`). This folder only fits them to our bodies. Nothing here models or reshapes a garment.

## Bodies

`Intermediate/ClothingFit2026_11_14/Bodies/<Body>_Body.fbx` and `<Body>_Face.fbx` are FBX exports of the live UE meshes the looks wear. Each body is 3,328 vertices on the 341-bone `metahuman_base_skel`, in an A-pose with the arms 52.6° below horizontal, facing -Y in Blender. Exporting them saved nothing in UE.

| Body | Looks |
|---|---|
| FerryPilot | GiltFerryman, GiltRamon (Giltside worker, M) |
| FestivalDrummer | GiltDrummer, GiltPriya (Giltside worker, F) |
| CoinClerk | GiltCoinClerk, GiltMaren |
| ArchiveApprentice | GiltArchivist, GiltBarnaby |
| GlassArtisan | GiltGlassman, GiltHaruto |
| BridgeGuard | GiltBridgeGuard, GiltRowena, FrostHyeon, FrostSaran, FrostNia, FrostAmara |
| IvenRook | FrostIven, FrostSilas, FrostTobias, FrostWen |

A garment fits the body it was fitted on. Wearing it on another body needs a second fit run with that body's config.

## Fit (Blender 5.3, headless, about 10 s per outfit)

```
blender -b --factory-startup --python Tools/ClothingFit/fit_codex_garments.py -- Tools/ClothingFit/configs/<outfit>.json
```

Pieces are fitted inner layer first (feet, lower, upper, then a helmet). Fits are tight, per the user (18:50): the innermost sheet sits 3 mm off the skin (4 mm for skirts, 2 mm for gloves), and each later piece sits 3 mm outside the earlier ones.

Piece kinds:
- `upper`, `lower` and `feet` are conformed to the skin.
- `skirt` is conformed at the waist and hips only; below that it is just pushed out where it would clip.
- `gloves` are conformed, and adding them lets the hands be hidden too.
- `helmet` is rigid: centred over the scalp, kept at Codex's size if it seats (otherwise grown in 2 % steps), lowered until it rests on the crown, and weighted 100 % to `head`.

1. **Align to the bind pose.** Trimmed per-axis ICP gives scale and offset, with the scale clamped to 0.85–1.15. Sleeves are rotated about the shoulder joint to the arm's direction. Boots are sized about the heel (length and width) until the foot fits inside, and lowered so the insole sits under the bare foot (`boot_drop_cm`: `"auto"` or a number).
2. **Trim caps.** Image-to-3D shells are closed at the neck, cuffs, waist and ankles. A face is removed only if it is more than 1.5 cm inside the body and runs across the limb, as a cap does.
3. **Conform.** On every skin point, the height of the garment's innermost sheet is measured by a ray. The correction (target 4–8 mm off the skin) is smoothed over the skin at about 8 cm. Every garment sheet above that point moves by the same amount, so thickness, seams, lapels, buttons and a waistcoat over a shirt keep their shape. Further rounds push out only what is still too close. A final per-vertex step handles anything deeper than a ray can see. Below the crotch a skirt is only pushed out, and shirt tails keep half their hang.
4. **Weights.** Transferred from the body (nearest face, interpolated), then smoothed over 2 passes, limited to 8 bones and normalised. Hems below the pelvis are blended toward pelvis and both thighs so they don't split.
5. **Body hiding.** The outfit gets its own copy of the body with the covered skin deleted, `SKM_<Body>_BodyHidden_<outfit>`. Covered means a garment sheet lies within 6 cm along the skin normal, or the skin is inside a garment's volume (legs inside a skirt). One edge ring (about 3.5 cm) of skin is kept under every cuff, collar and hem. Hands, neck and face are never hidden, unless the outfit has gloves, in which case the hands can be. The looks that wear the outfit swap their Body mesh to this copy, so skin can't poke through in motion.
6. **Pose checks.** walk, run, cast, crouch, arms up and arms across, posed on the body's own rig. Two counts per pose:
   - garment vertices more than 5 mm inside visible skin;
   - hidden skin that the posed garments no longer cover (a hole someone could see).
   On the test outfit, garments clip into visible skin in 0 vertices except 0.5 % with arms up, and 0.06–0.45 % of hidden faces end up uncovered.
7. **Export.** Writes `<out_dir>/<piece>.fbx`, the hidden body FBX (mesh plus the body's armature, the same settings as the hero coat), `<id>_Fit.blend`, `<id>_report.json` and front/side/back previews.

## Import (UE editor, PIE-free moment, no SAVE FREEZE)

`import_fitted_garments.py` uses the legacy FBX importer, as the hero coat did, and imports onto the body mesh's own skeleton. It brings in textures at 2K or less (normal map and ORM linear) and makes one `MI_<piece>` of `/Game/Characters/Lanthorne/Clothing/Materials/M_LanthorneGarment` per piece. That material is BaseColor × `Tint`, Normal, and ORM as AO/Roughness/Metallic, two-sided. It checks the bounds and skeleton, then saves. An item with `body_copy: True` is the hidden-skin body: it gets the original body's materials, physics asset and post-process anim BP instead of a garment material. It does not change any Blueprint or level.

`pie_before_after.py` makes before/after close-ups in PIE: one copy of the look as it is, and one with the old garments hidden and the new ones leader-posed to Body.

## Known limits

- Boots lowered onto the insole put the outsole 1–2 cm under the ground plane. A small upward offset on the look's Body may be wanted.
- Arms raised overhead is the hardest pose. With hidden skin it comes down to about 0.5 % of an upper garment's vertices.
- Helmets don't hide hair grooms: a helmeted look needs its Hair groom off.
- A look's NPC systems use its Body component. After a look swaps to a hidden body, spawn it once to check walk and ragdoll.
- A fitted ankle skirt can't follow a long running stride without cloth. Expect some leg clipping at full run.
