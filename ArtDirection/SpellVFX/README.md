# Spell combat and VFX (rebuild, 14 November)

This replaces the earlier partial VFX pass (kept at the bottom for history). It covers aiming, casting while moving,
new combat casts, and Niagara effects for every attack element plus healing and the ward. **Status of each piece is
stated plainly below; "verified" means seen working in Play-in-Editor on `Lvl_HeroSampleCrowd`.**

## How to play it

| Action | Mouse / keyboard | Gamepad |
|---|---|---|
| Aim (over-the-shoulder rig, zoom, reticle, ground preview) | hold RMB | hold LT |
| Cast the selected spell (hold to repeat) | LMB or Q | RT |
| Next / previous spell | Tab / Shift+Tab | RB / LB |
| Spell page | `[` `]` | D-pad left / right |
| Pick slot on page | 1-4 | — |
| Sprint | Left Shift | L3 (LB now cycles spells) |

The HUD shows the matching prompts for whichever device was used last.

## What was built

**Aiming** (`Hero/ReflectionsSpellAim.*`). RMB/LT is the project's existing `IA_Aim`, which already switches the GASP
camera to its `*_Aim` rig. On top of that: a camera modifier adds a 14° zoom, a small kick on each cast and decaying
shake on impacts; a camera-centre trace finds the aim point; light aim assist picks the most centred enemy inside a 7°
cone (wider and with a stronger camera pull on gamepad) and projectiles home toward it gently; a ground decal previews
the landing (a ring at the blast for orbs/fireballs, a ring where area spells will erupt, an arc in front for cones, a
marker for bolts). The reticle tightens while aiming, opens on each cast, turns red on an assist lock and shows a hit
marker (red on a kill).

**Casting while moving** (`Hero/ReflectionsSampleSpellDriver.*`). The hero body already used
`ABP_HeroSampleCastBlend` (montage slot blended above `spine_01`), but the driver had layering off and froze the pawn.
Layering is now on: legs keep running while the arms cast. Each clip starts late and plays faster so the spell leaves
the hand ~0.28 s after the press for bolts (0.36 s orbs, 0.38 s area, 0.44 s heals); the follow-through is cut after
0.3 s and can be cancelled by the next cast after 0.1 s (holding the button repeats after 0.18 s). Levitation keeps its
original full-body behaviour. Mana, per-spell cooldowns and respawn (added in parallel by another agent) are kept.

**Combat casts** (`/Game/Characters/Hero/Animation/CombatCasts/`, `Tools/SpellVFX/author_combat_casts.py`). Seven new
Kimodo takes — BoltRight, BoltLeft, HeavyPush, Slam, Sweep, HealRaise, AimHold — retargeted to the hero. Kimodo here
generates on its own Soma skeleton, so the script builds `Rigs/IK_Soma_Combat` and `Rigs/RTG_SomaToHero` (a copy of
`RTG_MannequinToHero` with an auto-aligned Soma source pose). Release frames come from the sampled hand-speed peak
(`Intermediate/CombatCasts/bake-report.json`) and are written onto each clip as a `Spell Release` anim notify, which the
driver reads, so release timing can be retuned in the clip without code. Bolts alternate hands on repeat.
Spells map to casts by delivery: bolts → BoltRight/BoltLeft, orbs/fireball/stone/force push → HeavyPush, novas/shocks →
Slam, Tidal Surge → Sweep, heals → HealRaise. Shield and Levitation keep their earlier clips.

**Attack VFX** (`/Game/Characters/Hero/SpellVFX/Systems`, `Tools/SpellVFX/build_spell_niagara.py`). Three parametric
systems driven by `User.*` parameters, so one asset set gives every element (and future crafted spells) its own look:

- `NS_Spell_Projectile` (attached): flickering hot core, coloured halo, world-space ribbon trail (jittered into a
  crackling bolt for lightning), embers/droplets/frost with gravity, drag and curl noise, lightning arcs, an arcane/water
  helix of orbiting motes, and a riding point light. Trails detach and fade when the projectile dies.
- `NS_Spell_Impact` (also the muzzle flash, at 0.3–0.5 scale): flash, ground/surface-aligned shockwave, velocity-aligned
  sparks that bounce off the world (CPU collision), tumbling mesh debris (rock cubes for earth, crystal shards for ice)
  that collides and settles, soft smoke/mist, a fire bloom, lightning arcs, lingering motes, and a light flash.
- Per-element styles live in `SpellVFX/ReflectionsSpellVfxSubsystem.cpp` (`StyleFor`): fire (rising embers, black
  smoke, flame bloom), water (helix, heavy falling spray, mist), ice (frost dust, shards), lightning (jitter + arcs),
  earth (dust, rock chunks), arcane (swirl, violet bloom).
- Feel: camera shake scaled by distance and spell size, and a 60 ms hit-stop when the local player directly hits a
  living target.

**Healing** (`NS_Spell_Heal`, attached at the feet): a rotating hexagram rune circle on the ground, a dense rising
spiral of gold→green motes (≈260/s), curl-noise sparkles, glowing petals thrown out from head height that fall,
bounce and settle on the ground with collision, rising light streaks, energy motes converging into the chest, a
pulse ring and a pulsing warm light. Greater Heal plays at 1.6× scale, Healing Pulse at 1.3× with its ring thrown to
the 400 cm heal radius. Arcane Shield uses `NS_Spell_Ward` (rune ring, rotating sphere of motes, pulse, light).

**Shared materials** (`/Game/Characters/Hero/SpellVFX/Materials`, `Tools/SpellVFX/build_spell_materials.py`): additive
glow, ribbon, rune ring, shockwave, soft depth-faded puff, lit debris with a fresnel rim, and the aim decal.

**Audio** (cues owned by the audio session under `/Game/Audio/Jam/Cues`, referenced only): element cast cue at the hand
on release, element impact cue on hits and area blasts, a projectile loop that stops with the projectile, heal shimmer,
shield up/loop/block (block plays when the shield absorbs damage), and levitation start/loop.

**APIs for other sessions.** Magic bar = the driver's mana: `GetMagic`, `GetMaxMagic`, `SpendMagic`, `TrySpendMana`,
`OnManaChanged` (regen 8/s after a 0.8 s pause). Spell crafting: `CastExternal(FReflectionsExternalCast)` and
`PrimaryCastOverride`. Combat: `UReflectionsSpellCombatComponent::ReleaseSpellAt(Spell, Origin, Target, AimTarget)`.
Events: `OnSpellImpactVisual`, `OnSpellReleaseVisual` on `UReflectionsSpellEventSubsystem`.

## PIE verification (14 Nov, 17:02 UTC, after the 16:40 shared rebuild)

Run with `Tools/SpellVFX/test_spell_combat_pie.py` on `Lvl_HeroSampleCrowd`; captures in `Saved/SpellCombatTest/`.

Verified:
- Holding aim (injected `IA_Aim`) sets the aim component to aiming (alpha 1.0); the reticle, spell label and orange
  ground preview at the practice target are visible (`aim_fireball_preview.png`).
- Fireball, Lightning Bolt, Earth Shock and Greater Heal cast through the driver, play on the upper body, spend mana
  and start their cooldowns.
- `NS_Spell_Projectile` and `NS_Spell_Impact` were active during the attack casts, `NS_Spell_Heal` during the heal;
  `attack_fireball_2.png` shows the impact flash, sparks and ground shockwave, `heal_greater_1.png` the rune circle,
  rising streaks and motes.

Re-checked at 17:11 UTC after the Niagara fix below. All three systems render in game, captured in
`Saved/SpellCombatTest/final/`: `1_aim_reticle_and_preview.png`, `2_fireball_in_flight.png`,
`3_fireball_impact.png` and `4_greater_heal_swirl.png`.

Found and fixed during the test:
- The CPU Vector VM has no `smoothstep`; emitters using it failed to compile and Niagara disabled whole systems at
  spawn (nothing rendered). The builder now expands smoothstep and forces a real compile (opens the asset editor)
  before saving, failing loudly on any VM error.
- The muzzle flash (impact system at small scale) put a huge ring around the camera; its flash and ring now scale
  down with `User.LightScale` (asset fix), and the C++ caps the muzzle at 0.35 scale (17:40 build).
- Multi-target area spells stacked camera shake into heavy blur; hit shake now follows the rate-limited hit-stop and
  the shake is lower and slower (17:40 build).

Re-checked at 17:25 UTC on train #2 (`muzzle`, `heal` and `override` scenarios):
- The muzzle flash is now a small ring at the casting hand: `final/5_muzzle_before_after.png` compares Lightning Bolt
  at 17:01 and 17:25. The Fireball muzzle is a warm glow with no ring. Lightning, Fireball and Greater Heal cast with
  their Niagara systems active.
- After a crafted slot is used, real LMB input casts the catalog spell again. In one case the same catalog key (1) is
  re-picked: Healing cast, and its cooldown restarted. In the other a different slot (2) is picked: Levitation cast.
  In both, the crafted slot was released (active slot -1) before the press.

Not verified yet: the lower camera shake (a still frame can't show it), the aim-hold pose (not visible in the aim
capture), hit-stop feel, projectile homing, the ward and levitation effects, gamepad input on a real pad, and the audio
cues (wired in code, not listened to).

## Known limits

- The bolts' 4 s catalog cooldown (set by the mana/cooldown work) means holding the cast button repeats slowly; lower
  `Cooldown` in `ReflectionsSpellCatalog.cpp` if rapid fire is wanted.
- HealRaise never lifts the hands above ~1.2 m and AimHold has some left-arm motion; both are Kimodo takes that may need
  a re-roll (new seed in `author_combat_casts.py`, then the `soma` and `bake` stages).
- Aim assist only considers pawns and spell practice targets, not Mass crowd entities.
- Visual quality, performance budget and packaged-build inclusion of the new systems are not yet measured.

---

## Earlier pass (superseded, kept for history)

Four Niagara systems were migrated from `action_fighting_UE59` (`NS_GasCanExplosion`, `NS_MissileTrail`,
`NS_BloodImpact`, `NS_GasCanGroundFire`; hashes in `migration.json`) and two candidates were duplicated
(`NS_WaterImpact`, `NS_HealingBurst`). Only the blood impact and `M_BloodSpatter` ground decal are still wired (on
targets tagged `Flesh`); the others are no longer referenced by code. Their PIE captures (`FireImpact_NPCTest.png`,
`Blood_NPCTest.png`, `HealingCandidate_PIE.png`, `WaterCandidate_PIE.png`) document that earlier state.
