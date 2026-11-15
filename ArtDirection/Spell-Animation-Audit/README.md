# Spell animation audit

The first sections below record the original 13 November inspection. See the
14 November update at the end for subsequently generated takes and tests.

The active sample spell driver reads spell definitions from `/Game/Characters/Hero/Gameplay/BP_HeroPlayer`. The build report records four separate Kimodo-derived sequences retargeted to the hero. Each is one take; this record does not claim multiple alternate takes exist.

| Spell | Hero sequence under `/Game/Characters/Hero/Animation/Locomotion/` | Duration | Effect release | Release hand |
|---|---|---:|---:|---|
| Healing | `AS_Hero_Healing` | 4.00 s | 0.80 s (frame 24 at 30 fps) | centered on character |
| Levitation | `AS_Hero_Levitation` | 4.20 s | 1.367 s (frame 41) | centered on character |
| Water | `AS_Hero_Water` | 4.00 s | 2.50 s (frame 75) | left hand |
| Fire | `AS_Hero_Fire` | 3.80 s | 0.60 s (frame 18) | right hand |

Source: `Intermediate/HeroLocomotion/result.json`, `Intermediate/HeroLocomotion/build_gameplay.py`, and `Source/reflections/Hero/ReflectionsSampleSpellDriver.cpp`. The four generated prompts used different gestures: healing opens both arms, levitation raises both arms, water sweeps across the torso, and fire thrusts the right hand. `Intermediate/IvenElemental/source-ready.json` records their prompts and generation seeds. Existing Iven showcase stills (`Saved/Screenshots/WindowsEditor/Iven_Spell_*.png`) depict distinct sampled poses and illustrative visuals; they are not tests of the current hero's gameplay rendering or of the full animation. A previous PIE test reported the sample hero playing fire and selecting water, plus healing and projectile damage behavior; this audit did not independently re-run PIE because the editor was in use.

## Timing caveat

Release frames are authored per spell in the existing definitions, not inferred automatically from a gesture. Every new take needs its own visually checked release time. For context only, the independently retargeted Iven clip's sampled left hand was still moving at the existing water release frame 75, with its greatest sampled speed at frame 92; this does not prove either frame is a better visual release, nor does it measure the hero's retarget. Sampled positions come from `Intermediate/IvenElemental/bake-report.json` (30 fps). Fire's corresponding right-hand sample peaked at frame 14 and releases at frame 18. The Iven evidence cannot establish collision, timing, or quality on the hero.

## Runtime visual limitations

The Iven screenshots are cinematic showcase images with staged meshes and must not be presented as the real-time spell effects. In the sample driver, healing and levitation show a single temporary preview mesh; fire and water use moving static-mesh projectiles. The present levitation raises the visual child by up to 65 cm while leaving the player collision capsule in place. Casting is blocked while airborne or crouched, stops movement, and restores walking after the montage; it is a prototype rather than a fully integrated traversal/combat implementation. Timed release, transitions, clothing/hair, player control, VFX readability, and cast interruption must be verified on each new take in actual gameplay.

## Explosion candidates — 14 November

Two new Kimodo takes were generated independently from different prompts and
seeds, then retargeted to the hero's body skeleton. The source sequences, raw
Quinn clips, and hero clips are in `/Game/Characters/Hero/Animation/SpellExplosion/`.

| Candidate | Seed | Hero clip | Result |
|---|---:|---|---|
| Explosion | 92117 | `AS_Hero_Explosion` | Hands rose together but did not spread outward; not selected for gameplay. |
| Explosion V2 | 49813 | `AS_Hero_ExplosionV2` | Hands spread from about 63 cm to 142 cm, but the pose held with raised arms through the end. |

V2 was played as a temporary dynamic montage on the existing sample hero while
moving. The montage played and then stopped, with locomotion resuming. Visual
review showed a prolonged stiff T-shaped pose and the hero's pre-existing hair
groom visibly detaching. The pawn also ran off the edge of the test floor before
the recovery capture, so the result does not validate normal blend-out on level
ground. `ExplosionV2_Cast.png` and `ExplosionV2_BlendOut.png` show the sampled
play test. These are **isolated candidates**, not integrated spell animations.

The previously generated `HealingV2`, `LevitationV2`, `WaterV2`, and `FireV3`
have distinct prompts, seeds, and sampled hand trajectories; see
`Intermediate/SpellVariants/source-ready.json`, `bake-report.json`, and the
corresponding `SpellVariantsFireReroll` records. Spell gameplay currently shares
animation families among many spell types; distinct named spells should not be
counted as distinct animations unless they actually reference separate takes.

## Twenty gameplay casts

The default crowd map now uses a separate animation sequence per spell. The first
four use the existing hero sequences, and the other sixteen were generated with
Kimodo using separate prompts and seeds, then retargeted to the hero. The source
sequence is `/Game/Characters/Hero/Animation/SpellCasts/LS_Hero_DistinctSpellCasts_Kimodo`.
The matching raw and retargeted animation assets live in the same folder. The
authoring script in `Tools/SpellVFX/author_distinct_casts.py` records the prompts
and review timings. Timing was chosen from sampled retargeted poses, with
projectile sockets set to the observed leading hand where appropriate. Some
generated gestures only approximate their prompts.

Play in Editor on `Lvl_HeroSampleCrowd` verified that twenty Tab presses cycle
through all twenty spells and wrap back to Healing. Shift+Tab cycles backward.
Bracket page changes, number selection, and pressing Q to cast were also tested
through Unreal's local player input. Each of the twenty spell casts then played
a separate animation sequence with measurable upper-body motion and returned to
locomotion. The test does not assess bespoke visual-effect quality or every cast
while running and jumping. Machine evidence is in
`Intermediate/DistinctSpellCasts/default-map-spell-pie.json`.
