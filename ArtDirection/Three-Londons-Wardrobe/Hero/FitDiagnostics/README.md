# Hero clothing fit check

The `original` images and metrics evaluate the existing hero coat, trousers,
boots and coat tails against the MetaHuman body and face in Blender. The
`bodyfitted` image and metrics evaluate an independent trouser prototype, not
the playable character. The `cape` image evaluates the separate V8 cloak
prototype. The stride and crouch poses rotate the thighs, arms and, in the
crouch, calves; they are synthetic static poses, not recorded animation or a
Chaos simulation.

Colors encode nearest skin-surface measurements:

- **Red:** a nearest-surface normal suggests the garment vertex is more than
  2 mm inside skin. Inspect these as potential clipping, not proven collisions.
- **Green:** 0–3 cm from skin.
- **Yellow:** 3–10 cm from skin.
- **Blue:** over 10 cm from skin. This is normal for a loose, flowing cloak.

The original coat mesh's sampled vertices show an estimated 12.69% inside in
the rest pose and 12.05% in the synthetic stride. The loose coat tails show
0% and 3.01%, respectively. The stride image also shows a visible upper-leg
breakthrough. The separate body-derived trouser prototype removes the obvious
crotch seam in Blender and samples 1 cm clearance with no inward flags in these
poses; it remains skin-tight and needs material and boot review. An isolated
Unreal preview moved at 350 cm/s with the sample retarget animation, but the
camera view did not provide a conclusive close-up of the boots. Its
matching topology and weights explain the particularly uniform result.

These percentages count **vertices**, not surface area. Mesh density therefore
affects comparisons. The inside/outside sign uses the closest face normal on
open MetaHuman surfaces, so seams, backfaces, face openings and the eye/mouth
region can yield wrong signs. The check does not measure cloth-to-cloth contact,
animation transitions, face deformation, or Chaos movement. These results guide
inspection; they do not prove the clothing is collision-free.
