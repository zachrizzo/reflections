# White London outfit previews

Six isolated actor Blueprint previews are saved under
`/Game/Characters/WhiteLondon/CrowdPreview`:

- `BP_WhiteLook_01_Plain` through `BP_WhiteLook_04_CapMantle` use Iven's
  existing MetaHuman face, hair, rags, sandals, and tattoos, with optional
  Blender-built cap and short mantle pieces. These are four combinations on
  one identity, not four new people. The new accessories have normalized FBX
  weights and UVs, but their fit has not been verified in Unreal; the mantle
  looked stiff at the shoulders in Blender. They are prototypes.
- `BP_WhiteLook_05_GuardRags` uses the existing BridgeGuard MetaHuman face
  and body, with Iven's rag tunic, skirt, sandals, and tattoos refitted to that
  body in Blender. This is a second White London face, but it also appears in
  the Red London looks, so it is not a second globally unique identity.
- `BP_WhiteLook_06_GuardBoldRunes` uses the same refitted outfit and identity
  with 22 larger runic markings projected onto that body's skin in Blender.
  The dedicated FBX passed a hierarchy and normalized-weight round trip.
  `WhiteGuard_BoldRunes_Walk.png` shows an Unreal retargeted walk pose; the
  markings follow the body, but have not been validated over a full animation
  set or as a baked skin texture.

`WhiteLondon_BridgeGuard_RagFit_Prototype.blend` is the editable fit source;
the four `SK_WhiteGuard_*.fbx` exports are retained alongside it. The exported
meshes were reimported into Blender to check root hierarchy and normalized
weights; the three clothing pieces retain UVs. The solid-color tattoo mesh
does not require a UV map. `white_guard_pose.json` records synthetic rest,
stride, and crouch nearest-normal estimates; the method is not a collision
guarantee, especially on open body surfaces.

`WhiteGuard_Fit_QA.png` shows the two identities in Unreal. The retargeted
walk pose in `WhiteGuard_Walk_QA.png` confirms the body and clothing animate
together, but the neckline and moving skirt still show sharp dark artifacts.
Neither the accessory variants nor the cross-body outfit is a finished Crowd
Collection appearance or has passed full animation and cloth collision review.
Iven's preview body scale uses an estimate from the exported fitting meshes
to approach the project's 183.199 cm reference height. BridgeGuard retains its
existing normalized body scale.
