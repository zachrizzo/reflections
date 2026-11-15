# Simplified hero outfit — isolated preview

`Hero_SimpleOutfit_Fit.blend` and the four `SK_HeroSimple_*.fbx` files are an
independent Blender fitting prototype: a fitted short-sleeved shirt, tight
trousers, footwear, and a single long cloak. The Unreal preview is
`/Game/Characters/Hero/SimplePreview/BP_HeroSimplePreview`. It has **not**
replaced the playable hero.

The body uses a copied native MetaHuman skin-material chain and a generated UV
opacity mask, rather than hiding the entire body. A Blender UV-sample audit
found all 1,104 sampled hand and 193 forearm vertices visible, with sampled
covered torso, leg, and foot vertices masked. The native face remains a
separate visible component. The FBX round trip checked all four meshes for a
root/pelvis hierarchy, UVs, one material slot, and normalized skin weights.

In an isolated sample play test, the retargeted hero reached 350 cm/s and
jumped. Chaos reported one cloth with 3,094 simulated and 483 pinned vertices.
The original coat and coat tails were hidden only on the preview. These checks
do not establish production quality:

- The hair groom moves off-center during locomotion. Turning off groom
  simulation in the temporary preview reduced but did not remove the problem.
- The single cloak visibly bunches and forms separated-looking folds during
  the jump; collision and cloth tuning need further work.
- The boots show gaps around the ankle in posed Blender views, and the shirt
  neckline and shoulder transitions need refinement.
- The skin mask was checked against the fitting body and sampled UV vertices,
  but needs broader real-animation and camera-angle validation.

`HeroSimple_Standing.png`, `HeroSimple_Running.png`, and `HeroSimple_Jump.png`
show the latest isolated Unreal test. The original hero Blueprint, clothing,
skin materials, and gameplay setup are preserved for rollback.

## Closed-boot candidate

`Candidates/Hero_ClosedBoot_Candidate.blend` and
`Candidates/SK_HeroSimple_ClosedBoot_Candidate.fbx` contain a separate boot
experiment. Ankle connectors and closed shoe shells reduce the gaps in the
Blender rest and crouch poses; detached sole islands were removed after a stride
test exposed them. The FBX has 3,150 vertices, normalized weights, three UV
layers, and one material slot. Unreal contains a separate candidate at
`/Game/Characters/Hero/SimplePreview/BP_HeroSimple_ClosedBootCandidate`.

The candidate followed the pawn at 500 cm/s during a temporary play test;
Chaos reported one active cloth and a 0.45 maximum-distance scale. The sample
camera overrode the diagnostic camera and obscured the shoes, so those images
do not establish boot fit or cloak collision quality in motion. No candidate
has replaced the playable hero. In particular, the groom remains off-center
and the simplified outfit needs further motion and camera-angle review.
