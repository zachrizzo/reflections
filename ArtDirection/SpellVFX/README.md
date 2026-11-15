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
Respawn: `SetRespawnTransform` / `GetRespawnTransform` (game flow sets the checkpoint), and `OnRespawned`, which fires at the
end of `Respawn()`.
Quest rewards: `RestoreMana(Amount)` (train #7; ignored while defeated; clamps and fires `OnManaChanged`).
**Name freeze until submission** (called by name from game flow, quests and world jump): `IsDefeated`,
`SetRespawnTransform`, `RestoreMana`, `IsAiming`, `GetMagic`, `GetMaxMagic`, `SpendMagic`, `TrySpendMana`.
`FReflectionsExternalCast::Animation` is a `TWeakObjectPtr` (train #7): assign as before; a clip that has been unloaded
falls back to the AimProxy's own cast.
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

## Ground stays lit after spells (fixed 14 Nov, ~18:00 UTC)

**Root cause.** `NS_Spell_Projectile`'s riding light was a single particle with a 1000 s lifetime. When a projectile
died, the VFX subsystem detached its system and called `Deactivate()`, which stops spawning but lets live particles
finish. So every spent projectile left a coloured point light where it ended, for about 16 minutes. Its pooled
component never completed and was never reused, so the lights piled up: 7 still lit 5 s after 7 casts, 18 after 20.

**Fix (asset, live now).** The light is now short particles (spawn rate 40, lifetime 0.1 s, each fading over its life).
Overlapping, they sum to the same steady glow; when the projectile dies, spawning stops and the light is gone within
0.1 s. **Backstop (C++, next train).** A detached projectile visual still active 2 s later is hard-stopped.

**Verified.** `Tools/SpellVFX/test_ground_clean_pie.py`; reports in `Saved/SpellCombatTest/ground_before` and
`ground_after`. It attributes every effect to the case that created it, waits for mana and cooldowns before driver
casts, and fails on refused casts, missing projectiles or impacts, and missing captures.

| Case | Before (old asset) | After (rebuilt asset) |
|---|---|---|
| 10 driver casts at the ground (7 projectiles, 2 area, 1 heal) | FAIL: 7 effects active after 5 s | PASS: 0 |
| 5 misses into the sky (range expiry) | FAIL: 5 | PASS: 0 |
| 20 rapid releases (pool reuse) | FAIL: 18 active, 18 distinct components | PASS: 0 active, 6 distinct (reused) |

Image: `Saved/SpellCombatTest/final/6_ground_glow_before_after.png`. Not checked directly: the light *in flight* on
a reused component. Python has no particle counts; it re-lights because the rate spawner runs whenever the system is
active.

**Ground marks (material live; spawning on the next train).** `M_Spell_GroundMark` is one decal material whose
`Kind` parameter picks the look: scorch with cooling embers, frost, wet, lightning burn, dirt, or arcane rune. Its
`DecalLifetimeOpacity` drives the fade. The VFX subsystem projects one onto the surface hit (or the floor under a hit
character) at every non-muzzle impact. Size scales with the spell; each mark holds 1.5 s, fades over 3.5 s and is
destroyed. At most 24 are alive at once (oldest dropped). With Substrate on, lit Translucent decals don't compile,
colored transmittance ignores Opacity, and unlit decals can only add light. So the material is lit **AlphaComposite**
with every output premultiplied by the mask. The render and fade were checked in PIE by spawning the marks from
Python. The C++ that spawns them on impacts compiles but needs the next build train.

**Also on the next train (compiled, not yet in the running editor):** aim assist and targeting for the unified-NPC
actors (`UReflectionsNpcSubsystem::GetNpcActors`, hidden driver pawns skipped, reticle-on-target lock), homing into an
actor-only NPC's hit capsule, `DamageScale` on the combat component, and the spell driver's respawn hooks. The old
`SpellVFX/ReflectionsSpellRagdollSubsystem` is retired (moved to `Saved/RetiredSource/`); lethal ragdoll now lives in
the NPC reaction component.

## Verified on train #8 (14 Nov, 23:42 UTC, `Tools/SpellVFX/test_train3_pie.py`)

- Ground marks on real impacts: 6 of 6 casts accepted, 6 marks spawned, 0 left after 6 s.
- N / F8 (`IA_NextPawn` / `IA_NextVisualOverride`) no longer change the hero. They're blocked in the driver and removed
  from `IMC_Sandbox`.
- Aim lock on actor-only crowd NPCs works, Friendly included (red lock ring). A Fire Bolt homed in and hit 0.8 s after
  release. A slow Fireball at the same NPC hit the practice cube between them (cover works as intended).
- Camera sits 165 cm from the hero's head; the GASP driver mesh (`CharacterMesh0`) is not visible.
- PSO warm-up at map start: "Spell VFX: warmed up 8 spell systems" (4 spell systems + 4 crafted).
- Image: `Saved/SpellCombatTest/final/9_train8_marks_and_npc_aim.png`.

## Tarnish magic: enemy spells for tarnished NPCs (14 Nov, for train #11)

Playtest feedback: tarnished NPCs followed the player and did nothing. They now attack like sorcerers. This folder
owns the spell side; npc-unify owns when the AI casts.

- **API** (`Source/reflections/SpellVFX/ReflectionsTarnishMagic.h`): add a `UReflectionsTarnishCasterComponent` to the
  NPC actor, then call `StartCast(EReflectionsTarnishSpell, Target)`. It runs the wind-up and releases by itself.
  - Also: `CancelCast`, `IsCasting`, `GetWindup`, `GetCastRange`, `ReleaseNow` (no wind-up), and `SetCastBody` (the
    mesh with `hand_r`).
  - Delegates `OnTarnishWindup(Spell, Seconds)` and `OnTarnishReleased(Spell, 0)` are where the AI plays its gesture.
  - Animation and movement stay with the AI.
- **Spells** (all values are UPROPERTYs; the player has 100 HP):
  - **Tarnish Bolt**: 11 damage, 0.8 s wind-up, 1500 cm/s, leads a moving target.
  - **Tarnish Wisp**: 9 damage, 1.1 s wind-up, 620 cm/s, gentle homing (1.4× speed, against 2.2× for the player's
    spells), so the player can dodge it by moving across its path.
  - **Tarnish Burst**: 13 damage within 340 cm of the caster, 420 push, 1.0 s wind-up. A violet ring on the ground
    warns of it and brightens as the release nears.
- **Wind-up telegraph**:
  - Silver motes and dark wisps spiral into the casting hand.
  - A violet point light swells and throbs faster toward the release.
  - Burst also draws the ground ring (decal kind 7).
- **Look**: a black-violet core in a violet rim, sickly silver flickering sparks, and a dark smoke wake. Impacts give
  a dark flash, a violet shock ring, silver sparks, dark smoke and a black-violet stain with glowing veins (decal kind
  6). Assets:
  - `NS_Tarnish_Bolt` (bolt, wisp and wind-up, switched by `User.Gather` / `User.Wisp`);
  - `NS_Tarnish_Burst`;
  - `M_Spell_GroundMark` kinds 6 and 7.

  They're built by `build_spell_niagara.py tarnish_bolt tarnish_burst` and `build_spell_materials.py ground_mark`. If
  the Niagara assets are missing, the shared projectile and impact systems stand in, tinted violet and silver.
- **Gameplay path**: the same as squads' casters.
  - Bolt and wisp are `AReflectionsSpellProjectile` (gameplay spell Arcane Bolt) with `SetLook(TarnishBolt/Wisp)`.
  - Burst uses `ReflectionsSpellCombat::ApplyArea`, the catalog area path.
  - All three pass through `AffectTarget`, so `UReflectionsNpcSubsystem::CanBeHarmedBy` applies: tarnished NPCs don't
    hurt their allies.
  - The caster and its hidden locomotion pawn are never hit by their own magic.
  - The impact sound is the arcane cue pitched down to 0.72.
- **Test**: `Tools/SpellVFX/test_tarnish_pie.py` gives a walker the component, casts all three at the player, checks
  the damage and the stains, and captures the wind-up, flight, impact and burst warning.

## Reactions for everything: explosion, shock, push (14 Nov, trains #11 and #12)

Playtest feedback: "think of this like a fully open world. There needs to be reactions for everything."
- **Stimulus fields** on `FReflectionsSpellHitData` (`Hero/ReflectionsSpellEventSubsystem.h`, additive):
  - `Reaction` (`EReflectionsSpellReaction`): Hit, Explosion, Electrify, Push, Knockdown, Lift, Pull, Freeze, Burn.
  - `Magnitude`: 0–1. 1 is a full-power point-blank hit (ragdoll or knockdown).
  - `Duration`: seconds for Electrify, Freeze, Burn and Pull.
  - `Origin`: blast or pull centre.
  - `bRepeat`: a repeat tick of a beam or field. VFX skips hit-stop, the hit marker and blood for these.
  - `Impulse`: the velocity given to the body, in cm/s.

  npc-unify plays the body reaction; spell crafting fills the same fields for crafted spells.
- **Element mapping** (`ReactionFor` in `ReflectionsSpellCombat.cpp`):
  - Fire with a blast radius → Explosion; Fire Bolt → Burn 2.5 s.
  - Lightning → Electrify: 1.5 s for the bolt, 1.0 s for area lightning.
  - Water → Push. Ice → Freeze 2.5 s. Earth → Knockdown. Air → Lift. Force Push → Push. Arcane and Tarnish → Hit.
- **Fireball explosion** (`ExplodeSpellAt`):
  - 320 cm radius; damage and knock-back fall from 1 to 0.35. The body that was struck directly takes the full blast.
  - Characters launch at up to 1100 cm/s with 40% lift.
  - Loose physics objects get a radial velocity-change impulse, so heavy and light props both fly.
  - The blast VFX is 2.7× scale with a matching scorch and shake.
  - `SCue_Fireball_Explode` (audio session) replaces the fire impact sound when the cue exists.
  - Tarnish Burst uses the same explosion.
- **Water**: Water Bolt push raised from 100 to 450, Water Orb from 380 to 650. Every spell now gives loose props a
  velocity push; NPC bodies are left to npc-unify.
- **Train #12**:
  - A crackle (`NS_Spell_Shock`) on any body that takes an Electrify hit, riding its pelvis (so it follows a ragdoll),
    for the hit's Duration, with `SCue_Shock_Loop`.
  - Chain lightning: a Lightning Bolt's direct hit jumps to up to two living bodies within 7.5 m at 60% damage.

## Earlier queued items (now all in the build)

- HUD target panel: shows health for whatever the reticle is on if it is tagged `NPC_CombatEnemy` or the unified NPC
  system calls it hostile to the player (`IsHostileToPlayer`: enemies, infected, villain hosts, soldiers, anyone
  attacking the player; false when dead). A hit on an NPC's proxy or locomotion pawn counts as the NPC.
- Jam IP rule: the spell driver's input context (priority 1) claims **N** and **F8** with a consuming no-op, so the GASP
  sample's `IA_NextPawn` / `IA_NextVisualOverride` (which cycle the hero into third-party characters) never fire.
  `IMC_Sandbox` maps both on the keyboard only; no gamepad buttons. Removing the two mappings from `IMC_Sandbox` as
  well is pending: it is an asset edit, waiting for the save freeze and editor restart.
- Verification after the train is pending: `Tools/SpellVFX/test_train3_pie.py` covers ground marks on real impacts,
  aim lock and homing on actor NPCs, the aim pose with camera placement, and N/F8 not changing the hero. It follows
  the shared `Saved/PIE_LOCK.json` rule.

## Known limits

- The bolts' 4 s catalog cooldown (set by the mana/cooldown work) means holding the cast button repeats slowly; lower
  `Cooldown` in `ReflectionsSpellCatalog.cpp` if rapid fire is wanted.
- HealRaise never lifts the hands above ~1.2 m; it is a Kimodo take that may need a re-roll (new seed in
  `author_combat_casts.py`, then the `soma` and `bake` stages).
- Aim hold (fixed ~18:30 UTC): the original clip put the right forearm inside the torso on every frame. The spell-crafting
  session re-solved the right arm with IK (V2: 1.5 s, at least 6.6 cm clear on every frame). It now sits at
  `CombatCasts/AS_Hero_CombatAimHold`; the original is `AS_Hero_CombatAimHold_V1`. Checked in PIE (`Tools/SpellVFX/test_aim_pose_pie.py`,
  `Saved/SpellCombatTest/aimpose/`). For A/B, `Spell.AimHoldV1 1` (next train, read at BeginPlay) loads the original.
  The spell-crafting session also measured the live aim layer while standing and strafing left and right at 350 cm/s.
  V2 had 0 of 180 samples with the right forearm or hand inside the torso bodies (at least 6.6 cm clear). The original
  was inside on every sample (up to 16.3 cm). If they regenerate V2, `AS_Hero_CombatAimHold` must be re-copied from
  `/Game/SpellCrafting/Gestures/AS_Hero_CombatAimHold_V2`.
- Aim assist considers pawns, spell practice targets and the unified NPC system's actors (next train). It does not
  consider Mass crowd entities. Civilians (tag `Friendly`) are picked only when the reticle is on them, or within
  1.5°, and never pull the camera.
- Visual quality, performance budget and packaged-build inclusion of the new systems are not yet measured.

---

## Earlier pass (superseded, kept for history)

Four Niagara systems were migrated from `action_fighting_UE59` (`NS_GasCanExplosion`, `NS_MissileTrail`,
`NS_BloodImpact`, `NS_GasCanGroundFire`; hashes in `migration.json`) and two candidates were duplicated
(`NS_WaterImpact`, `NS_HealingBurst`). Only the blood impact and `M_BloodSpatter` ground decal are still wired (on
targets tagged `Flesh`); the others are no longer referenced by code. Their PIE captures (`FireImpact_NPCTest.png`,
`Blood_NPCTest.png`, `HealingCandidate_PIE.png`, `WaterCandidate_PIE.png`) document that earlier state.
