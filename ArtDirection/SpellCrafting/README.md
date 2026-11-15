# Spell crafting

Players build their own spells from a small grammar. A few parts combine into thousands of spells, and each combination
behaves and looks different. The recipe is the only thing a player authors and the only thing saved; everything else
is derived from it deterministically, so a recipe is the same spell on every machine.

## The grammar

**Spell = Form × Element × 1–3 Behaviours × Trigger × Power (1–5) × Look variant**

| Form | Delivery | Cast gesture (Kimodo) |
|---|---|---|
| Bolt | fast projectile | BoltRight / BoltLeft (alternating hands) |
| Orb | slow, heavy projectile with a blast | Conjure (fallback HeavyPush) |
| Ray | near-instant beam along the reticle | Lance (fallback BoltRight) |
| Nova | burst on the ground where you aim | Slam |
| Wave | cone rolling out from you | Sweep |
| Rain | cloud striking an area over time | SkyCall (fallback HealRaise) |
| Rune | trap on the ground | GroundPlant (fallback Slam) |
| Aura | field around you | Spiral (fallback HealRaise) |

| Element | Effect | Colour family |
|---|---|---|
| Fire | burns over time | orange |
| Ice | slows (time dilation on the target) | pale blue |
| Lightning | stuns briefly, faster, +2 chain jumps with Chain | blue-violet |
| Water | heavy knockback | deep blue |
| Earth | heavy damage, slower | ochre |
| Air | throws targets up and away | pale teal |
| Arcane | pure damage, homes best | violet |
| Life | heals you and allies; weak against enemies | green over gold |

Behaviours change how a form moves or what its payload spawns. The same behaviour means something different on a
projectile and on a field, which is where most of the variety comes from:

| Behaviour | On a projectile (Bolt, Orb, Ray) | On a field (Nova, Wave, Rain, Rune, Aura) |
|---|---|---|
| Split | throws 3–4 shards on impact | throws shards outward each pulse |
| Bounce | ricochets 2–3 times, toward the next enemy when it bounces off one | hops to the next enemy and fires again |
| Pierce | passes through 2–3 enemies | fires a piercing lance at the nearest enemy each pulse |
| Chain | arcs to 2–3 more enemies | arcs from everything each pulse hits |
| Gravity Pull | drags enemies along as it flies | pulls enemies to the centre |
| Delayed Detonation | sticks, waits 1.2 s, detonates 60% harder | telegraphed start, first burst 60% harder |
| Leaves Hazard | lingering pool where it lands | pool where it ends; an Aura lays a trail of pools |
| Heal on Hit | heals you for 35% of damage dealt | same |
| Homing | seeks the nearest enemy | the field drifts toward enemies |
| Orbiting | circles you, then launches at an enemy | the field follows you |
| Echo | recasts itself once at 60% (Cascade: twice) | same |

| Trigger | Meaning |
|---|---|
| On Impact | fires on contact (Runes wait to be stepped on) |
| Airburst | projectiles burst at the aim point, even in mid-air; fields erupt after a short fuse |
| Proximity | projectiles stop at the aim point and arm as a mine; novas wait for an enemy; rain only falls on enemies |
| Pulse | projectiles pulse along their path; a Ray becomes a held beam that follows the reticle; novas and runes repeat |

Who gets hit: sides come from the NPC subsystem (`CanBeHarmedBy`, `IsAllyOf`), the same answer the catalog spells and
aim assist use. It reads each NPC's archetype, so a civilian the villain infects turns hostile without tag edits.
Actors outside that system fall back to the `Friendly` tag.
- Harm: the player's crafted spells hurt anything alive except the player (and anything tagged `Player`). That
  includes civilians; hurting bystanders costs reputation on the NPC side.
- Seeking: homing, ricochets, chain jumps, swarm shards, satellite launches and proximity triggers only pick targets
  that are not allies. A civilian gets hurt only by a direct hit or by being caught in an area; an infected one is fair
  game.
- Healing: Life spells heal you and your allies and never damage them.
The NPC calls are detected at compile time (C++20 concept in `ReflectionsCraftedSpellSubsystem.cpp`). If that API
changes, crafting falls back to the tag rule instead of failing to build.

What a hit does to a body (train #12). Every crafted hit fills the shared reaction fields on `FReflectionsSpellHitData`.
The fields and mapping were agreed with spell-combat so crafted and catalog spells match, and npc-unify plays the
reactions. `Impulse` is unchanged (cm/s) and `Spell` is still the element's proxy spell.

| Element | Reaction | Notes |
|---|---|---|
| Fire | Explosion, or Burn | Explosion for a burst payload 150 cm or wider (orb, nova, rune, fused or delayed blasts): `Origin` is the blast centre. Burn for everything else (bolts, rays, pierce/bounce hits, chains, beams, pools, rain), lasting the burn time (3 s). |
| Lightning | Electrify | Lasts clamp(0.8 + 0.3 × power, 1, 2) s, then the NPC collapses. |
| Water | Push | |
| Earth | Knockdown | |
| Air | Lift | |
| Ice | Freeze | Lasts as long as the slow: 2.5 s, scaled 0.5–1.5× by hit strength. |
| Arcane | Hit | |
| Life (on enemies) | Push | Magnitude capped at 0.35. |
| Gravity modifier, whirlpool | Pull | Sent from the pull itself, about every 0.5 s per caught target, `Origin` = the pull centre. Updraft sends Lift. |

- **Magnitude** (0–1) is clamp(0.5 × damage / 28 + 0.5 × push / 800, 0.05, 1). Inside a burst it falls to 40% at the
  edge. A power-3 fire orb is about 0.64, a water wave about 1.0, a lightning bolt about 0.34.
- **Quiet hits** (beams, rain, swarms, auras, pools, field pulses) still skip the shared event for plain damage. For
  lasting reactions (Electrify, Burn, Freeze, Pull, Lift) they send one at most every 0.5 s per target. `bRepeat` is
  false on the first send after 1.5 s without one, and true after that. Repeats skip hit-stop, so the crafting code
  shows the aim hit marker for them itself.

### Combinations that become something new

Eighteen synergies change the rules instead of adding numbers. A named synergy also renames the spell:

- **Eye of the Storm** (Gravity + Chain): lightning leaps between everything caught in the pull, every 0.35 s.
- **Shatterstorm** (Split + Bounce): the spell splits again on every bounce; shards bounce and split once more.
- **Swarm** (Split + Homing): each shard is handed a different enemy.
- **Implosion** (Gravity + Delayed): pulls 50% harder during the fuse, then detonates at 190%.
- **Sinkhole** (Gravity + Hazard): the pool keeps pulling.
- **Conductor** (Pierce + Chain): every enemy pierced starts its own chain.
- **Satellites** (Orbit + Split on a projectile): several orbiters at once.
- **Escort** (Orbit on a field): the field travels with you (healing rain that follows you).
- **Bloodbath** (Leech + Hazard), **Ricochet** (Homing + Bounce: re-targets after every bounce), **Cascade** (Echo + Delayed).
- Element affinities: **Arc Affinity** (Lightning + Chain), **Permafrost** (Ice + Hazard), **Wildfire** (Fire + Hazard,
  the pool spreads), **Maelstrom** (Water + Gravity), **Cyclone** (Air + Gravity lifts instead of pulling),
  **Boulder** (Earth + Bounce), **Sanctuary** (Life on a field or pool heals allies standing in it).

Count: 8 forms × 8 elements × 231 behaviour sets (any 1–3 of 11) × 4 triggers × 5 power tiers gives 295,680 recipes
that play differently, before look variants.

### Cost, power and names

- **Mana cost** = form base × power curve (0.5, 0.95, 1.5, 2.15, 2.9) × each behaviour's factor (1.1–1.6) × trigger
  factor × 1.08 per synergy, clamped to 4–95. It is paid from the spell core's magic bar through
  `UReflectionsSampleSpellDriver::CastExternal`, which also refuses the cast when the bar is short.
- **Power** raises damage (×0.6 to ×2.0) and size (×0.8 to ×1.3); cost grows faster than damage.
- **Names** are generated from seeded word lists: behaviour adjective + element word + form noun + "of" behaviour noun,
  with named synergies replacing the noun ("Rime Shatterstorm", "Astral Implosion", "Seeking Volt Lance of Chains").
  Power 1 adds "Lesser", power 5 "Grand". Players can type their own name instead.

## Procedural looks

Every recipe hashes (FNV-1a over form, element, behaviours, trigger, power and look variant) into a seed. The seed
drives a three-colour ramp in the element's hue family, a silhouette, density, size and motion. These go to four
parametric Niagara systems through `User.*` parameters (`UReflectionsCraftedSpellSubsystem::ApplyLook`):

| System | Used for |
|---|---|
| `/Game/SpellCrafting/VFX/NS_Crafted_Body` | anything that flies: core, a spinning shell in the recipe's shape, ribbon trail, motes, light |
| `NS_Crafted_Burst` | every payload: the shape thrown outward, flash, shock ring, sparks, haze, light |
| `NS_Crafted_Arc` | rays, chain arcs and storm-eye arcs between `User.Start` and `User.End` |
| `NS_Crafted_Field` | nova/rune/aura circles, rain cloud and drops, gravity vortex or updraft, hazard pools; the shape is laid on the ground |

Parameters: `ColorA/B/C` (main, highlight, shadow), `Shape` (0 sphere, 1 ring, 2 helix, 3 star, 4 shards, 5 spiral;
fractions blend neighbours), `Spikes`, `Density`, `Size`, `Swirl`, `Jitter`, `Turbulence`, `Pulse`, `Glow`,
`Gravity`, `Scale`, `Intensity`. Behaviours bias the silhouette: Orbit draws rings, Homing helices, Split and Pierce stars,
Bounce shards, Gravity and Echo spirals. Gravity spins the shell hard. Lightning and Chain add jitter. Fire and Air add
turbulence, and Fire's motes rise while Water's fall. The **Look** row re-rolls the variant without changing gameplay.
The systems are rebuilt from code by `Tools/SpellCrafting/build_crafted_niagara.py`. They reuse the spell core's
sprite materials, read-only.

## Playing it

- **Keyboard and mouse:** **K** opens the crafting screen. **5–8** select a crafted slot (press again to return to the
  catalog spells). Hold **right mouse** to aim and **left mouse** to cast, the same as every other spell.
- **Controller:** **View** opens the crafting screen and **D-pad Up** cycles crafted slots. Hold **LT** to aim and press
  **RT** to cast. **LB/RB** and the catalog keys return to the catalog spells.
- **Crafting screen:** Up/Down move between rows and Left/Right change the focused row (D-pad, stick, arrows or A/D).
  A/Enter steps forward. LB/RB or Q/E switch slots. X/R re-roll the look. Y/F equip the slot and close. B, Esc, K or
  View close the screen. With the mouse, click any row or its arrows. Every change applies immediately and is saved
  (SaveGame slot `SpellCrafting`) when the screen closes. Empty slots start as four starter spells.
- **Describe your spell:** type a sentence and press Enter or Conjure. Offline, a keyword parser maps it onto the
  grammar; this works in every build, packaged ones included. With the dev relay running, an OpenAI model does the
  mapping instead (see below).

Console (development builds): `Crafting.Preset <slot> <0-3>`, `Crafting.Set <slot> <sentence or JSON>`,
`Crafting.Slot <n>`, `Crafting.Cast [slot]`, `Crafting.Open`, `Crafting.Dump`,
`Crafting.Dummies [count] [distance] [enemy|civilian|mixed]`, `Crafting.ClearDummies`. No crafted slot is active at
start, so give `Crafting.Cast` a slot (`Crafting.Cast 0`) or select one first. Every refused cast logs and shows its
reason: no slot selected, down, mana, still casting, recharging, or the spell core is still recovering.
- The test crowd is made of the team's MetaHuman NPCs, not mannequins: the Red London SimpleRed looks (Bridge Guard,
  Coin Clerk, Archive Apprentice, Festival Drummer) and White London `BP_WhiteLook_01…06`, in turn.
- Each one gets the placed crowd's tags (`NPC_Reactive`, `NPC_HitProxy`, `NPC_SampleLocomotion`) and is enrolled with
  `UReflectionsNpcSubsystem::EnrollActor` as an `Enemy` (the default, hunts on sight) or a `Civilian`.
- So they take hits through their hit capsule, react, flee or fight back, and walk with the sample locomotion.
- A crafted gravity pull drags them by launching the hidden locomotion character that moves them.
- Bare mannequins are only the fallback when none of those Blueprints load.

## Code map

All of it is in `Source/reflections/SpellCrafting/`:

- `ReflectionsSpellCraftingTypes.h`: the grammar enums, `FCraftedSpellRecipe` (saved) and `FCraftedSpellResolved` (derived).
- `ReflectionsSpellCraftingLibrary`: sanitising, stats, cost, synergies, names, descriptions, look seeding, the offline
  sentence parser, JSON, the aim proxies and gesture lookups.
- `ReflectionsCraftedSpell`: one actor class plays every form (projectile, satellite, held beam, mine, fuse, field,
  hazard). Behaviours are written once and shared: Split shards and Hazard pools are themselves crafted spells, which
  is what lets behaviours stack.
- `ReflectionsCraftedSpellSubsystem`: adds the crafting component to the local spell-casting pawn (no Blueprint edits),
  runs burn and slow statuses, shared targeting and hit application, and Niagara spawning.
- `ReflectionsSpellCraftingComponent`: slots, SaveGame, input, and the cast bridge. It casts through the spell core's
  `CastExternal` (windup, layered upper-body montage, follow-through, cancel window, mana) and `PrimaryCastOverride`
  (LMB/RT and held repeat). Aim preview and targeting reuse the spell core's aim component through a per-form proxy spell.
- `ReflectionsSpellCraftingScreen`: the code-built UMG screen and the in-game indicator.
- `ReflectionsSpellRecipeRelay`: the dev-only relay client, compiled out of Shipping.
- `ReflectionsSpellCraftingCommands.cpp`: console commands, compiled out of Shipping.

Hits go through the shared `UReflectionsSpellEventSubsystem::OnSpellHit`, so hit markers, hit-stop, ragdolls, NPC
reactions and reputation all treat crafted spells like catalog spells. Rhythmic payloads (rain, auras, pools, beams)
hit quietly: they skip the event so hit-stop doesn't stutter every tick.

## Cast gestures and Kimodo

Kimodo cannot run in a packaged build. `Kimodo.uplugin` declares one module, `"Type": "Editor"`, and depends on
`AnimGenOffline` and `PythonMLPackages`, both allow-listed to the Editor target. It runs a Python ML model
(transformers, accelerate) inside the editor's Python. So gestures are generated in the editor and baked to ordinary
`AnimSequence` assets, which is what ships.

`Tools/SpellCrafting/author_cast_gestures.py` (stages `source`, `status`, `soma`, `bake`) generates Conjure, Lance,
SkyCall, GroundPlant and Spiral into `/Game/SpellCrafting/Gestures`. It retargets each take to the hero with the
retargeter that matches the take's skeleton: `RTG_MannequinToHero` for takes on the bound Quinn mannequin (what this
run produced), or the spell core's `RTG_SomaToHero` for takes on Kimodo's Soma skeleton. It then finds each release
frame from hand speed and authors a **Spell Release** notify on the clip. Generated 2026-11-14 in about two minutes for
all five; release frames were Conjure 0.67 s, Lance 0.40 s, SkyCall 0.53 s, GroundPlant 0.67 s and Spiral 0.67 s. The component reads that notify at runtime and falls back to a built-in table. Turn off
`AnimGenOffline.RetiredAnimationGC.Enabled` while generating; the script does this for you. Otherwise the plugin's
garbage collector evicts finished takes. Forms without their own gesture yet use the shared combat casts in
`/Game/Characters/Hero/Animation/CombatCasts`.

Kimodo generation is started by re-applying each section's prompt inside an editor transaction while the sequence is
open in Sequencer. The AnimGenOffline editor mode only queues a section for (re)generation when it sees a finished
transaction on it. Setting properties without a transaction, or while PIE is running, leaves the sections empty.

## Aim hold V2: the right hand no longer goes into the body

The spell core's aim layer (`AS_Hero_CombatAimHold`, played by the driver as a looping upper-body montage while Aim is
held) leads with the left hand, extended forward and up with the palm open. The right hand guards at the chest. On the hero
body, though, the right hand sat on the spine plane with the elbow about 20 cm behind the back, so the forearm passed
through the torso. `/Game/SpellCrafting/Gestures/AS_Hero_CombatAimHold_V2` keeps that pose and fixes only the right arm.

How it was chosen (`Tools/SpellCrafting/author_aim_hold.py`, all numbers measured per frame on the retargeted hero):
- Six Kimodo takes, in two rounds of three prompts (`LS_Hero_AimHoldV2_Kimodo`, `..._R2`), each keeping the lead-hand
  wording and placing the right hand in front of the chest, by the left elbow, cradling an orb, or in a guard by the
  cheek. Every take put the right hand or forearm into the torso on some frames (5–13 cm from the spine axis). The
  one take that cleared the body (A) did so by pulling the hand 45 cm behind the back and crouching, which loses
  the pose.
- Take G, which shipped: the original clip with only `upperarm_r`/`lowerarm_r` re-solved by two-bone IK. The hand moves
  ~29 cm forward to sit 24 cm in front of `spine_03`, the elbow points down and out, and the wrist keeps its
  angle to the forearm. The left arm, spine and the clip's breathing are untouched. V2 is original frames 21–66 (1.5 s)
  with the last 12 keys eased into the first, so the montage loops with no seam.

| Per-frame check on the hero | Old (frames 9–81) | V2 (all 46 keys) |
|---|---|---|
| Forearm/hand inside the torso collision bodies (`PHYS_MHC_Hero`, 3 cm arm half-thickness) | 73 of 73 frames, up to 16.3 cm deep (`spine_04`) | 0 frames; at least 6.6 cm clear |
| Right hand distance from the pelvis–neck axis | min 7.1 cm | min 28.2 cm |
| Right elbow relative to the spine plane | 26 cm behind | at or in front (min +1.4 cm) |
| Left lead hand, forward / above `spine_03` | 50 / 39 cm | 51 / 42 cm |
| Loop seam / largest per-frame step | 20 cm / 15 cm | 0 / 0.6 cm |

Re-run: `measure`, `physcheck`, `fixold`, `finalize G 21 66 12` stages of `author_aim_hold.py`.
`Tools/SpellCrafting/compare_aim_hold.py` renders the old and new poses side by side on the full hero look (front and
side) from a spawnable-only LevelSequence, so the shared map is never touched:
`Saved/SpellCraftingShots/AimHoldV2/standing_compare.png`. Its `pie` stage does the A/B in one PIE run while Aim is held,
standing and strafing. It pauses the driver's tick and plays each clip on `DefaultSlot` exactly as the driver does, then
resumes the driver and measures the right hand to confirm which clip the spell core is playing. Its `piecheck` stage
samples the same torso-collision clearance on the live pose, every ~30 ms, while aiming.

The spell core swapped it in as data at ~18:30 UTC: `CombatCasts/AS_Hero_CombatAimHold` now holds V2 (1.5 s). The
original is kept as `CombatCasts/AS_Hero_CombatAimHold_V1`, and from the next train `Spell.AimHoldV1 1` (set before PIE)
loads it instead. Verified in PIE afterwards (`Saved/SpellCraftingShots/AimHoldV2/pie_*_compare.png`):

| While aiming (live pose, layered on GASP locomotion) | Original | V2 (the driver's own aim layer) |
|---|---|---|
| Standing | inside the torso on 68/68 samples, up to 16.3 cm | 0/55 inside, at least 6.6 cm clear |
| Strafing right, 350 cm/s | 66/66 inside | 0/67 inside |
| Strafing left, 350 cm/s | 63/63 inside | 0/58 inside |

The live numbers match the offline per-frame check exactly. The upper body above `spine_01` comes from the clip and
the nearest torso body is `spine_04`, so strafing hips don't change the clearance.

## Describe your spell (dev only)

Type a sentence into the crafting screen's describe box ("a slow storm that follows me and heals friends"). The
crafting screen then fills in a recipe for it.
- **With the dev relay running**, an OpenAI model maps the sentence onto the grammar.
- **Otherwise** the offline keyword parser does it.

The packaged game never needs the network.
- **Key:** `Tools/SpellCrafting/recipe_relay.py` reads the OpenAI key from `%USERPROFILE%\.openai\api_key`
  (or `REFLECTIONS_OPENAI_KEY_FILE`) inside its own process. It never prints, logs or saves the key and sends it
  only to `api.openai.com`. Error output gives just the HTTP status, because OpenAI error bodies can quote part of a
  key. The key is never in the project, the launcher or the Unreal process.
- **Starting it:**
  - `Start-SpellRelay.ps1 -RelayOnly` (or `python recipe_relay.py`) works with an editor that's already open. The relay
    writes a random per-launch token to `Saved/SpellCrafting/relay-token` (git-ignored, deleted on exit), and dev
    builds read it there.
  - `Start-SpellRelay.ps1` with the editor closed launches a fresh editor and hands it the token through the
    environment instead.
  - The game connects to `ws://127.0.0.1:8766` and sends the token plus the sentence; it never sees a key.
- **Model and output:** Responses API structured output. A strict JSON schema of the grammar's enum names is
  enforced: form, element, 1–3 behaviours, trigger, power 1–5 and a name. Minimal reasoning keeps it quick.
  `store: false`, so OpenAI keeps no conversation. The relay clamps the answer to the grammar and balance limits:
  known names only, no repeated behaviours, at most 3, power 1–5, a name of at most 4 words. The game sanitizes it
  again, and power drives the mana cost (4–95).
- **Fallbacks:** Shipping builds compile the client out. Any build where the relay isn't running, refuses the request
  or errors falls back to the offline parser, and the screen says which one interpreted the sentence.
- **Tests that never contact OpenAI:** `python -m unittest -v test_recipe_relay` (9 tests: protocol, token, key
  file, clamping, error redaction).
- **Live check:** `python recipe_relay.py --describe "sentence" ...` prints only the clamped recipes.

AI declaration: when the relay runs, "describe your spell" in development builds uses OpenAI `gpt-5-mini` by default
(`REFLECTIONS_SPELL_MODEL` overrides it). It is not part of the packaged game. Not yet verified: the live call. Running
it with the user's key needs the user's own go-ahead, so the model name above is the configured default, not yet
confirmed against the account.

## Niagara gotcha: systems that compile but never activate

Systems built from scratch through the Niagara toolset can report `UpToDate` with no errors and still never run: the
component is `Inactive` in the very frame it spawns (`fx.Niagara.DumpComponents` shows it), with nothing in the log. On
2026-11-14 this hit `NS_Crafted_Body`, `NS_Crafted_Field` and all four of the spell core's `NS_Spell_*` systems, while
`NS_Crafted_Burst` and `NS_Crafted_Arc`, built the same way, were fine. The cause is in `UNiagaraSystem::IsReadyToRunInternal`:
the system's spawn and update scripts disagree on their dataset attributes, so the system refuses to run. A cooked build
logs it as "failed due to mismatch between System spawn and update script attributes"; the editor fails silently.
Epic's comment calls it "DDC weirdness". Here it comes from building a system through many rapid toolset edits,
which leaves the two scripts compiled from different states. What fixes it: one stack-input edit made after the build
has settled (re-setting any HLSL expression with a no-op change), which forces a full recompile; the fix survives
saving. `Tools/SpellCrafting/fixup_crafted_niagara.py`, run as its own call after `build_crafted_niagara.py`, probes
each system by spawning it and repairs any that stay inactive. Run both in separate MCP calls: a long call times out
client-side and the editor cancels the rest of the script.

## Packaging notes

Crafted assets are loaded by string path, so `/Game/SpellCrafting` must be in `DirectoriesToAlwaysCook`; the packaging
session added it to `Config/DefaultGame.ini`. Audio cues come from `/Game/Audio/Jam`, which is always-cooked too.
Never package `Tools/SpellCrafting`.

## What works and what doesn't

Verified in Play-in-Editor on `Lvl_HeroSampleCrowd` (2026-11-14, 17:05 UTC), casting through the spell core's cast flow
while holding Aim, against six test dummies (`Crafting.Dummies`). Screenshots: `Saved/SpellCraftingShots/`.

| Spell | Recipe | Result |
|---|---|---|
| **Glacial Shatterstorm** (bouncing ice splitter), 15 mana | Bolt · Ice · Bounce + Split · Impact · Power 2 | Works. Ricochets between dummies and splits on every bounce: one cast became ~20 shards within a second; teal trails, frost bursts, slow on hit. |
| **Arcane Implosion** (slow orb that pulls enemies in), 40 mana | Orb · Arcane · Gravity + Delayed · Impact · Power 3 | Works: drifts at ~4 m/s (measured) with a violet body and light, sticks to what it hits, fuses for 1.2 s, then detonates at 190%. Measured pull at 17:4x UTC: walking characters within reach were dragged up to 424 cm and ended up clumped around the orb. |
| **Circling Dawn Deluge** (healing rain that follows you), 33 mana | Rain · Life · Orbit · Pulse · Power 2 | Works. A ring of green light and falling streaks centred on the player that moves with them; drops heal the player and allies they land near, plus a sanctuary tick for everyone inside. |
| Volt Eye of the Storm, 66 mana | Orb · Lightning · Gravity + Chain · Pulse · Power 3 | Starter spell in slot 4; casts, not screenshotted. |

Also verified: names, costs, descriptions and synergy lines are generated deterministically (`Crafting.Dump`); the
crafting screen renders every row, the colour ramp, stats and synergies for each slot; slots save and load; the cast
goes through `CastExternal` (mana spent from the magic bar, layered upper-body cast gesture, aim preview through the
proxy spell); hits drive the shared hit marker and NPC reactions.

Verified after the 17:19 UTC build (train #2): no crafted slot is active at start; choosing one takes the cast button;
picking a catalog spell (here `Driver->SetSelectedSpell`) hands it straight back. The new Kimodo gestures play on the
hero when casting: Conjure (both palms push forward) for the orb, SkyCall (arm raised to the sky) for the rain.
Screenshots `07`–`14` in `Saved/SpellCraftingShots/`. The hand flash at release no longer blooms over the screen
(`NS_Crafted_Burst` now defaults `User.Radius` to 45).

Verified with the MetaHuman test crowd (train #5 build, 20:2x UTC, two locked PIE runs):
- `Crafting.Dummies 6 750 mixed` spawned six team NPCs (White Look 03–06, Bridge Guard, Coin Clerk), all enrolled in
  the NPC system. Enemies have 100 health and civilians 35.
- Arcane Implosion dragged them up to 532 cm through their locomotion drivers, and the blast took each enemy from 100
  to 40.2. Screenshots `11_orb_pull_metahumans.png` and `12_orb_after_metahumans.png`.
- Crafted spells hurt `Friendly` civilians now. In a separate run, an ice splitter cast at three civilians straight
  ahead took the centre one from 35 to 32.3. The two at the sides were untouched, because bounces don't seek civilians.
- Enemy dummies hunt on sight and melee: three of them took the player from 100 to 4 health in a few seconds. Use
  `civilian` dummies for passive targets.

Not done or not verified yet:
- The crafting screen was driven by console commands and screenshots, not by simulated controller or mouse input in
  PIE. Its keyboard, gamepad and mouse handling is implemented but hasn't been exercised end to end.
- Element audio cues are compiled in (train #2) but I haven't listened to them; the cue assets come from the audio
  session.
- Lance, GroundPlant and Spiral gestures haven't been watched in PIE (Ray, Rune and Aura weren't cast).
- The dev relay was tested only against a local stub (`test_recipe_relay.py`); no live OpenAI call was made.
- Spell actors are not replicated; crafted spells are local-only like the rest of the spell core today.
- Many forms × behaviours combinations have only been exercised in code review, not in PIE: Ray (beam and held beam),
  Wave, Rune, Aura, Proximity mines, Satellites, Echo and Hazard pools need a play pass.
