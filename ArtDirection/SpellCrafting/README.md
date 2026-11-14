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
`Crafting.Slot <n>`, `Crafting.Cast [slot]`, `Crafting.Open`, `Crafting.Dump`, `Crafting.Dummies [count] [distance]`,
`Crafting.ClearDummies`.

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

## Describe your spell (dev only)

`Tools/SpellCrafting/Start-SpellRelay.ps1` (close the editor first) asks for an OpenAI key without echoing it and starts
`recipe_relay.py` on `127.0.0.1:8766` with a random per-launch token, then launches a fresh editor. Add `-WithVoice` to
start the NPC voice relay as well. Only the relay process holds the key; the game sends the token and the sentence,
and the model answers in a strict JSON schema of the grammar's enum names. The relay clamps the answer to the grammar
again before replying. The model defaults to `gpt-5-mini`; override it with `REFLECTIONS_SPELL_MODEL`. Nothing is
logged or saved. Protocol tests, which never contact OpenAI: `python -m unittest -v test_recipe_relay` in that folder.
Packaged and Shipping builds never use the relay. The client is compiled out of Shipping, and without a token the
offline parser handles every sentence.

The generation is started by re-applying each section's prompt inside an editor transaction while the sequence is open
in Sequencer; the AnimGenOffline editor mode only queues a section for (re)generation when it sees a finished transaction
on it. Setting properties without a transaction, or while PIE is running, leaves the sections empty.

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
| **Arcane Implosion** (slow orb that pulls enemies in), 40 mana | Orb · Arcane · Gravity + Delayed · Impact · Power 3 | Works: drifts at ~4 m/s (measured) with a violet body and light, sticks to the dummy it hits, fuses for 1.2 s, then detonates at 190%. The pull itself (LaunchCharacter toward the orb, 10 times a second) is implemented, but how far it drags the test dummies was not measured. |
| **Circling Dawn Deluge** (healing rain that follows you), 33 mana | Rain · Life · Orbit · Pulse · Power 2 | Works. A ring of green light and falling streaks centred on the player that moves with them; drops heal the player and allies they land near, plus a sanctuary tick for everyone inside. |
| Volt Eye of the Storm, 66 mana | Orb · Lightning · Gravity + Chain · Pulse · Power 3 | Starter spell in slot 4; casts, not screenshotted. |

Also verified: names, costs, descriptions and synergy lines are generated deterministically (`Crafting.Dump`); the
crafting screen renders every row, the colour ramp, stats and synergies for each slot; slots save and load; the cast
goes through `CastExternal` (mana spent from the magic bar, layered upper-body cast gesture, aim preview through the
proxy spell); hits drive the shared hit marker and NPC reactions.

Not done or not verified yet:
- The crafting screen was driven by console commands and screenshots, not by simulated controller or mouse input in
  PIE. Its keyboard, gamepad and mouse handling is implemented but hasn't been exercised end to end.
- Until the 17:40 UTC build train, picking a catalog spell does not hand the cast button back from a crafted slot (the
  driver's Enhanced Input swallows the legacy keys crafting listened for). The fix is in Source and compiles; it lands
  with the next editor rebuild, together with the element audio cues.
- The five Kimodo gestures are generated, retargeted and saved, but haven't yet been watched in PIE on the hero (the
  screenshots above used the shared combat casts). They load by path, so Orb, Ray, Rain, Rune and Aura already pick
  them up; falling back to the shared casts happens only if a clip is missing.
- The dev relay was tested only against a local stub (`test_recipe_relay.py`); no live OpenAI call was made.
- Spell actors are not replicated; crafted spells are local-only like the rest of the spell core today.
- Many forms × behaviours combinations have only been exercised in code review, not in PIE: Ray (beam and held beam),
  Wave, Rune, Aura, Proximity mines, Satellites, Echo and Hazard pools need a play pass.
