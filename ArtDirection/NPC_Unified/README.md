# One NPC system: how every NPC reacts to spells and world events

Status (2026-11-15, 15:24): train #24 is loaded with the tight-street fixes, still **not run in the game** (no PIE turn: memory under the 8 GB gate). Earlier (12:50): the game map is now MedievalLondon (narrow lanes). Two small fixes for tight streets are in Source, compile-clean, **not yet run** (see "MedievalLondon" at the end of section 4); the check for them is `Tools/NpcUnified/verify_npc_medieval.py`. Earlier (05:26): train #23 is loaded. Dead soldiers no longer freeze standing (fixed and confirmed), soldiers wear the dressed looks and hold sword and shield in a guard stance, and physical knockdowns are proven and recommended but still switched off (`Npc.WalkerPhysics` 0) until the user says yes. Earlier (04:20): train #19 is loaded and its guard stance verified; street scenes, panic ripple and fleeing verified; the knockdown crash is understood and its fix, the dressed soldier looks and floor-snapped spawning are in Source for train #20 (compile-clean, not run). Walker physics is still off. Earlier (2026-11-14, 23:47): train #14 is loaded. Soldiers hold sword and shield; the Fireball knockdown works but walker physics stays off after a crash in the lightning path (see "Train #14" below). Before that: train #13 was loaded and verified on Gray London (21:27); **train #14 was in Source and compile-clean but had not run** (weapon grip and stance, physical hits on the walker, street scenes, the panic ripple; see "Train #14" below). Earlier: **loaded and verified in PIE on the 19:32 build (trains #11 and #12 merged)**. On top
of what the 17:43 build already did (spell reactions, lethal hits ragdolling, the tarnished hunting and converting
townspeople, roster voices, passing remarks, the finished looks, lean walkers), these have now run and passed: the
tarnished casting dark magic at the player, sword strikes as montages on the hidden walker with a sword in the hand,
dying in the middle of a strike, look pools by side, the lower health, what each kind of spell does to a living NPC,
crime and heat with guards turning on the player, and a Giltside allied soldier killing one of the tarnished. The
section "Consequences" has the numbers and what the runs turned up (throws too far, tarnished sight too short,
Pewterside still borrowing Giltside's looks). The old strike clips on the visible body stay off: they crashed the
editor (16:16).

## 1. Where things stood (audit, 2026-11-14)

### Paths from a spell to an NPC

| Step | Who | What it does |
|---|---|---|
| Hero catalog spell lands | `Hero/ReflectionsSpellCombat.cpp` `AffectTarget` | Damage (`ApplyPointDamage` or `ICombatDamageable`), push, then `OnSpellHit` |
| Area spell cast / projectile impact | same file, `BroadcastSpell` | `OnSpellEvent(Spell, Location, Caster, Intensity)`: the "loud magic nearby" signal |
| Crafted spell lands | `SpellCrafting/ReflectionsCraftedSpell*.cpp` | Same two events, with a catalog proxy spell per element |
| Health | `UReflectionsHealthComponent` | `OnTakeAnyDamage` → `OnHealthChanged`, `OnDeath` |
| **Subscriber 1** | every `UReflectionsNpcReactionComponent` | Each one listens to both events and filters by owner: fear, flee, investigate, simple attack, hit physics, ragdoll on |
| **Subscriber 2** | `UReflectionsReputationSubsystem` | `OnSpellHit` → −8 reputation if the target has a reaction component |
| **Subscriber 3** | `SpellVFX/UReflectionsSpellRagdollSubsystem` | `OnSpellHit` on a dead `NPC_Ragdoll` actor → the ragdoll kick |
| Subscriber 4 (presentation, stays) | `UReflectionsSpellVfxSubsystem` | Blood on `Flesh`, hit-stop, impact VFX |
| Separate brain | Codex's `UReflectionsNpcCombatComponent` | Polls the player every tick: chase, windup, strike, recover. Never looks at spell events |
| Enrolment | `UReflectionsNpcPopulationSubsystem` | Once, at world begin play: adds health, reaction, combat and hit proxy by tag |
| Not connected at all | `Crowd/*` (Mass), villain possession, game-flow infection meter, world-jump coins | — |

### Actors in `Lvl_HeroSampleCrowd`

The level has 20 actors. Six are NPCs, all actor-only MetaHuman assemblies (not Pawns). There is **no Mass spawner
in this map**: the "walking crowd" here is these six, each moved by a hidden `BP_SampleCMCClean2` character.

| Actor | Tags | Gets at runtime |
|---|---|---|
| Crowd Preview - White 01 | `NPC_Reactive NPC_HitProxy NPC_Timid NPC_Ragdoll Friendly Flesh NPC_SampleLocomotion` | health, reaction (Timid, ragdoll), proxy, driver |
| Crowd Preview - White 02 | `NPC_Reactive NPC_HitProxy NPC_Brave Friendly Flesh NPC_SampleLocomotion` | health, reaction (Brave), proxy, driver |
| BP_BridgeGuard | `NPC_Reactive NPC_HitProxy NPC_Guard NPC_SampleLocomotion` | health, reaction (Guard), proxy, driver |
| Crowd Preview - Red 01 | `NPC_Reactive NPC_HitProxy NPC_Timid Friendly NPC_SampleLocomotion` | health, reaction (Timid), proxy, driver |
| Crowd Preview - Red 02 | `NPC_Reactive NPC_HitProxy Friendly NPC_SampleLocomotion` | health, reaction (Civilian), proxy, driver |
| Crowd Preview - Red 03 | `NPC_Reactive NPC_HitProxy NPC_Brave Friendly NPC_SampleLocomotion` | health, reaction (Brave), proxy, driver |

No enemy is placed (`Tools/NpcCombat/setup_enemy.py` adds one with six tags). A PIE probe on the loaded code
confirmed all six get their components, and a Fire Bolt released straight at the Coin Clerk took it from 100 to 86
health and made it flee while the timid fled and the brave and the guard walked over.

### Why it reads as "spells do nothing", and what is duplicated or in conflict

1. **Death is invisible on five of six NPCs.** Without `NPC_Ragdoll` a dead NPC only stops moving and stands there.
   A Fire Bolt is 14 damage against 100 health, and only `NPC_CombatEnemy` gets a health bar.
2. **Lethal ragdoll has two owners** keyed on the same tag: the reaction component turns physics on at death, the
   ragdoll subsystem adds the kick, and the reaction component adds a second raw impulse to a body that is already down.
3. **Two attack implementations.** The reaction component walks up and applies 8 damage every 1.5 s with no
   animation or line of sight; Codex's component does path-following, a windup clip, 12 damage and interruption.
   A tag check inside the reaction tick picks between them, and Codex's component never sees fear, hits or reputation
   (an enemy hit from beyond 1200 cm does not respond).
4. **One NPC is described by up to six tags** read in four places (disposition, combat, ragdoll, proxy, locomotion, blood).
5. **Reputation** drops 8 for hitting anything with a reaction component, including a hostile enemy.
6. **Enrolment happens once.** Anything spawned later (villain test hosts, crafting dummies, streamed worlds) is never enrolled.
7. **Every NPC subscribes to every spell event** and filters by owner; a hit on the hidden locomotion pawn is lost.
8. **No path at all** for coins, infection, possession, Mass crowd entities or non-spell events.

## 2. Target design

```
 spells (catalog, crafted, villain)        world events (death, infection, alarm, anything)
        │ OnSpellEvent / OnSpellHit                │ ReportStimulus
        ▼                                          ▼
 ┌──────────────────────────── UReflectionsNpcSubsystem (world) ────────────────────────────┐
 │ the ONLY listener for NPC purposes · registry of NPCs · archetype library · tag mapping   │
 │ reputation, coins (world jump), infection (game flow), stimulus feed for the Mass bridge  │
 └───────────────┬──────────────────────────────────────────────┬───────────────────────────┘
                 ▼                                              ▼
   UReflectionsNpcReactionComponent ("the NPC")        crowd bridge (Mass entities)
   Archetype (data asset) + fear/aggression state      reads stimuli, calls the same pure
   movement, hit physics, lethal ragdoll               EvaluateStimulus() per entity
   owns the melee motor (Codex's component)
```

- **`UReflectionsNpcSubsystem`** (`NPC/ReflectionsNpcSubsystem.h`) replaces the population subsystem and is the single
  entry point. It binds `OnSpellEvent` and `OnSpellHit` once and routes them. The reputation subsystem stays as the
  score store but no longer listens to spells. The separate ragdoll subscriber is retired.
- **`UReflectionsNpcReactionComponent`** is the one NPC component (name kept so Voice and the test tools still work).
  It carries a `UReflectionsNpcArchetype` and no longer subscribes to anything itself.
- **`UReflectionsNpcArchetype`** (`NPC/ReflectionsNpcArchetype.h`, a data asset):
  - `Disposition`: Timid, Civilian, Brave, Guard, Enemy, Infected, VillainHost.
  - `Reaction` (plain struct, safe to copy into a Mass fragment): awareness radius, fear gain, flee threshold,
    aggression gain, attack threshold, what loud magic does (flee when afraid / investigate / attack), the reputation
    below which it turns on the player, what a hit does, speeds and timers.
  - `Combat`: can attack, hunt the player on sight, melee tuning (Codex's values: awareness 1200, range 165,
    damage 12, cooldown 1.0, chase input 0.7, interrupt recovery 0.65, impact at 45% of the clip), strike clip,
    and a ranged-caster block (spells, damage scale, min/max range, cooldown, windup, cast clip).
  - `MaxHealth`, `bRagdollOnLethalHit`, `bPhysicalHitReaction`.
  - `HomeWorld` (auto from spawn location, or Gray/Red/White) and `CoinReward` (none / purse via `AwardCoin` / pickup).
  - Reputation deltas (player hit, player kill, per healed point).
  - `bCountsOnInfectionMeter`, `bCuredOnDeath`.
- **Built-in archetypes** exist in code (`Civilian`, `Timid`, `Brave`, `Guard`, `Enemy`, `Hostile`, `Soldier`,
  `SoldierCaster`, `Infected`, `VillainHost`), so nothing breaks if no asset is cooked. A data asset in
  `/Game/NPC/Archetypes` with the same `ArchetypeId` overrides the built-in one; a new id adds a new type.

  | Built-in | Health (Fire Bolts to kill) | On loud magic | When hit | Fights with | Coin |
  |---|---|---|---|---|---|
  | `Civilian` | 35 (3) | flees once afraid | flees | nothing | none |
  | `Timid` | 35 (3) | flees at half the noise | flees | nothing | none |
  | `Brave` | 45 (4) | walks over | fights back | simple strike, 8 | none |
  | `Guard` | 60 (5) | walks over; attacks a player with reputation ≤ −25 | fights back | melee motor, 12 | none |
  | `Enemy` (`NPC_CombatEnemy`) | 100 (8) | attacks | fights back | hunts on sight (1200 cm), melee motor, 12 | purse |
  | `Hostile` | 60 (5) | attacks | fights back | simple strike, 8 | purse |
  | `Soldier` | 70 (5) | ignores (the squad decides) | fights back; flees under 25% health | melee motor, 8 | pickup |
  | `SoldierCaster` | 55 (4) | ignores | flinches away 2.5 s; flees under 25% | ranged spells at 60% damage, cast by the squad | pickup |
  | `Infected` | 45 (4) | attacks | fights back | hunts on sight (900 cm), melee motor, 8 | none |
  | `VillainHost` | 100 (8) | attacks | fights back | hunts on sight (1600 cm), melee motor, 16; no ragdoll | none |

- **Every hit reads**: an upper-body physics flinch blended back into the animation, a stumble away from the impact
  (every hit shoves at least 300 cm/s, blasts 400–1100) and a short flash in the spell's colour on the struck body
  (half strength on bystanders). Blood stays opt-in through the `Flesh` tag the spell VFX reads: the built-in
  `Enemy`, `Hostile`, `Soldier`, `SoldierCaster`, `Infected` and `VillainHost` grant it (an infected civilian bleeds
  only while infected); civilians, the brave and guards do not unless the level tags them. A lethal hit ragdolls with a kick; a body
  that cannot ragdoll freezes and tips over.
- **Tags keep working** by mapping onto archetypes at enrolment:

  | Tag | Meaning now |
  |---|---|
  | `NPC_Reactive` | enrol this actor |
  | `NPC_Timid` / `NPC_Brave` / `NPC_Guard` | archetype of that name (none of them: `Civilian`) |
  | `NPC_CombatEnemy` | archetype `Enemy` (hunts on sight, melee motor) |
  | `NPC_Hostile` (without `NPC_CombatEnemy`) | archetype `Hostile` (attacks when provoked) |
  | `NPC_Infected` / `NPC_VillainHost` | start infected / as his host |
  | `NPC_Type_<Id>` | archetype `<Id>` from a data asset (wins over the tags above) |
  | `NPC_Ragdoll` | per-actor override: ragdoll on a lethal hit |
  | `NPC_HitProxy` | add the query capsule spells can hit |
  | `NPC_SampleLocomotion` | hidden sample-locomotion driver |
  | `Flesh`, `Friendly` | unchanged (blood VFX; aim assist and ally heals). `Friendly` is lifted while infected |

### API (C++; the UFUNCTIONs are also callable from Blueprint and by name)

```cpp
#include "NPC/ReflectionsNpcSubsystem.h"
UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(WorldContext);

// Enrol anything at any time (actors spawned after begin play, crowd actors, test hosts).
UReflectionsNpcReactionComponent* Npc = Npcs->EnrollActor(Actor, /*Archetype or null = from tags*/ nullptr);
Npcs->FindNpc(Actor);                         // also resolves a hidden locomotion pawn to its NPC

// World events. Spells arrive by themselves through the spell event subsystem.
FReflectionsNpcStimulus S;                    // Kind, Location, Intensity, Radius, Instigator, Spell
Npcs->ReportStimulus(S);

// Infection and possession: one call; the subsystem swaps behaviour and reports to the infection meter.
Npcs->SetInfection(Actor, EReflectionsNpcInfection::Infected, Source);   // None / Infected / VillainHost / BurnedOut
Npcs->GetInfection(Actor);

// Whose side is it on? One answer for spells, crafted spells and aim assist.
Npcs->IsHostileToPlayer(Actor);               // Enemy, Infected, VillainHost, or attacking a player right now
Npcs->IsAllyOf(Target, Caster);               // heals reach it, attacks should avoid it
Npcs->CanBeHarmedBy(Target, Caster);          // the player can hurt anyone; NPCs spare their own side

// Spawn with a team MetaHuman look (never a mannequin). Console: Npc.Spawn <Archetype> [Count] [Distance]
Npcs->SpawnNpc(TEXT("Guard"), Location, FacingYaw);   // Look = null: next of the archetype's Looks

// Voice: who it sounds like, and say a line in that voice from its head.
Npcs->GetVoiceProfile(Actor);                 // Sex, Slot 0..2, Character, ArchetypeId, CueSuffix "F1".."M3",
                                              // VoiceId "V001".. and GeminiVoice (both empty without a roster)
Npcs->FindVoiceCue(Actor, TEXT("Remark"));    // the cue of a line group in that NPC's voice, or null
Npcs->PlayBark(Actor, TEXT("Guard_Alert"));   // plays FindVoiceCue's cue from the head, at most every 4 s per NPC
Npcs->FindVoiceRow(TEXT("V017"), Row);        // a roster row: Sex, Side, Characters, Age, Description, GeminiVoice
Npc->SetVoiceOverride(TEXT("V017"));          // cast the NPC as a fixed voice for a scene; ClearVoiceOverride()

// Orders (on the NPC component): squads, set pieces.
Npc->Engage(Target);                          // fight any living actor; nullptr calls it off
Npc->SetExternallySteered(true);              // someone else moves the body (fleeing still overrides)
Npc->BeginScriptedHold(Seconds);              // a set piece owns it: no moving, fighting, fleeing; EndScriptedHold()
Npcs->HoldNpc(Actor, Seconds);  Npcs->ReleaseNpc(Actor);   // the same, by actor
Npc->GetMovementCharacter();  Npc->GetAimPoint();  Npc->IsIncapacitated();

// Listen.
Npcs->OnNpcReaction    (Npc, Reaction, Cause, Location)
Npcs->OnNpcSpellHit    (Npc, Hit)
Npcs->OnNpcDied        (Npc, Killer)
Npcs->OnNpcInfection   (Npc, State, Source)
```

### Crowd bridge (Mass) interface

Mass entities are not actors, so the bridge pulls instead of being pushed per entity:

```cpp
// 1. Every danger the actor NPCs hear, kept for a short time (game thread).
const TArray<FReflectionsNpcStimulus>& UReflectionsNpcSubsystem::GetActiveStimuli() const;
FReflectionsNpcStimulusNative& OnStimulus();            // or be told as each one arrives

// 2. The same decision the actor NPCs use. Pure: no UObject access, callable from a Mass processor.
//    Returns false (nothing changed) when the stimulus is out of range, too weak or ignored.
static bool UReflectionsNpcArchetype::EvaluateStimulus(
    const FReflectionsNpcReactionProfile& Profile, const FReflectionsNpcStimulus& Stimulus,
    const FVector& NpcLocation, float InstigatorReputation, float& InOutFear, float& InOutAggression,
    EReflectionsNpcReaction& OutReaction);
static FVector UReflectionsNpcArchetype::FleeDestination(Profile, NpcLocation, ThreatLocation, FallbackDirection, uint32 Seed);
//    Profile is plain data: Npcs->FindArchetype("Civilian")->Reaction, copied once into a shared fragment.

// 3. When an entity is represented by an actor (close LOD) and should be hittable: enrol it, release it later.
Npcs->EnrollActor(Actor, Npcs->FindArchetype("Civilian"));
Npcs->ReleaseActor(Actor);

// 4. An entity died or was infected without ever being an actor.
Npcs->ReportAnonymousDeath(Location, ArchetypeId, Killer);   // coins, reputation, a Death stimulus for witnesses
```

## 3. Adding a new NPC type with one data asset

1. In the Content Browser, in `/Game/NPC/Archetypes`: right-click → Miscellaneous → Data Asset → pick
   **ReflectionsNpcArchetype**. Name it `DA_Npc_<Something>`.
2. Set **Archetype Id** (for example `Merchant`). To start from an existing type, type that type's id first
   (`Civilian`, `Timid`, `Brave`, `Guard`, `Enemy`, `Hostile`, `Soldier`, `SoldierCaster`, `Infected`, `VillainHost`;
   `AlliedSoldier` from the 19:28 build), press **Reset To Built In**,
   then change the id to your own.
3. Tune it: disposition, the Reaction block (fear and aggression gains and thresholds, what loud magic does, whether
   it fights back), the Combat block (hunt on sight, melee values), health, ragdoll, home world and coin, reputation,
   infection flags.
4. On any actor in a level, add the tags `NPC_Reactive` and `NPC_Type_Merchant`. That is all: at play the system
   gives it health, the NPC component and, if it has no collision spells can hit, a capsule. Add `NPC_SampleLocomotion`
   if it is a MetaHuman crowd body that should walk with the sample locomotion.

Other ways to use the same asset: put a `ReflectionsNpcReactionComponent` on a Blueprint and set its **Archetype**;
or from code, `UReflectionsNpcSubsystem::EnrollActor(Actor, Archetype)` on anything spawned at runtime.

An asset whose id equals a built-in id replaces that built-in everywhere (this is how to retune every civilian at
once). `Tools/NpcUnified/create_archetype_assets.py` writes one asset per built-in type with the built-in numbers.

For a packaged build the folder `/Game/NPC/Archetypes` must be cooked (it is found through the asset registry, not
referenced by a map). If it is not cooked the game still runs on the built-in types.

## 4. What works and what doesn't

### Checked in PIE on the loaded code (2026-11-14, last run 12:38 on the 12:33 build, `Tools/NpcUnified/verify_npc_system.py`: 34 of 34)

Evidence: `Saved/NpcUnified/verify_run6_all_pass.json` and the PNGs beside it (`run2_A`, `run2_D`, `run5_B`, `run6_*`).
The run's log had no empty-pose warning and no watchdog repair.

| Done-means | What happened |
|---|---|
| A fireball near civilians makes them flee | Coin Clerk (Civilian) took 20, 35 → 15, and fled; Archive Apprentice (Timid) took 20 and fled |
| Guards investigate | Bridge Guard went to Investigating and walked toward the blast |
| An enemy fights back | An enemy spawned during play was enrolled a tick later as `Enemy`, stood calm 1403 cm away (outside its 1200 cm sight), took a Fire Bolt (100 → 86, shown on the HUD), came 1200 cm to the player and struck: hero 100 → 88 |
| A lethal hit ragdolls | A Timid villager with no `NPC_Ragdoll` tag died to one bolt at 5 health and lies ragdolled on the ground |
| An infected host counts on the meter | `SetInfection(Infected)`: Tarnish 0 → 1 on game flow's HUD, the host hunted the player, `Friendly` lifted; `SetInfection(None)`: meter back to 0, tag restored |
| Coin through world jump | Killing the enemy paid one coin (`AwardCoin`, 0 → 1) |
| A hit that does not kill | A Brave villager took a bolt (45 → 31), leaned away, was shoved, stood upright again, kept a valid pose and turned on the player |
| Every kind of death ragdolls | A walking villager (Fire Bolt), the placed guard (Fireball) and a spawned soldier (Fire Bolt): body simulating, pelvis 13 cm off the floor, before/after pictures; the soldier dropped its coin |
| One data asset per type | The ten assets in `/Game/NPC/Archetypes` are loaded at play ("NPC archetype 'Guard' from ..." in the log) and override the built-ins |

### Second run (2026-11-14, 14:28 on the 14:17 build, `Tools/NpcUnified/verify_npc_batch2.py`: 28 of 28)

Evidence: `Saved/NpcUnified/verify_run7_batch2_all_pass.json`, `run7_K_hunter_converts_npc.png`, `run7_K_after.png`,
`run7_H_spawned_team_looks.png`. No empty-pose warning and no watchdog repair in the run's log.

| What | What happened |
|---|---|
| Every NPC has a voice | The six placed NPCs: sex from the look (4 women, 2 men), slots spread within each sex, the component's `VoiceSlot` equal to the profile's cue suffix, the same answer twice. No roster table in the project, so every `VoiceId` was None |
| A voice override comes and goes | `SetVoiceOverride("V999")` showed in `GetVoiceProfile`, `ClearVoiceOverride` gave the NPC's own id back |
| The tarnished convert townspeople | A spawned civilian marked `SetInfection(Infected)` went for a placed townsperson; at 12.75 s the NPC system called the villain's `BeginConversion`, both were held for 8.0 s, the victim turned; that victim then tackled and turned a third (8.2 s). Meter 0 → 3. Both victims carried `Friendly`. Holds were released |
| `SpawnNpc` and `Npc.Spawn` | `SpawnNpc("Soldier")`: archetype Soldier, 70 health, a WhiteLook guard body. `Npc.Spawn Guard 2 600`: two Guards. Team looks only, no visible mannequin mesh, all walk and have voices. Both guards wore the same look (the Guard archetype has one) |
| Barks | `PlayBark(Guard, "Guard_Alert")` attached `SCue_VO_Guard_Alert_F1` to an NPC whose voice is F1; a second call inside the cooldown added nothing |
| Scripted hold | A held civilian ignored a spell noise 2 m away (calm, moved 0 cm); released, the same noise made it flee |

### Third run (2026-11-14, 15:11 on the 15:05 build, same script)

Evidence: `Saved/NpcUnified/verify_run8_batch2_train7.json`, `run8_*.png`. 28 checks passed; 2 failed because of the
script itself (it asked the editor asset library for the roster during play, which refuses, and it tried the override
round trip on an NPC that the lives session had already cast as a named person). Both are corrected in the script.

| What | What happened |
|---|---|
| The sight fix | The tarnished civilian went for a clean civilian 3.5 m away at once; hand-over to the villain's conversion at 3.75 s (12.75 s before the fix); three conversions in 25 s; meter 0 → 3; no pose warnings |
| Hostiles ignore one more convert | The tarnished stayed Attacking after each conversion instead of going to Investigating |
| Roster voices | Audio's table was read: the 15 NPCs present at start all carried a named person's voice from the lives session (disabled rows, set with `SetVoiceOverride`), all different |
| Remarks | `SetRemarksMuted` round trip works; there is no Remark cue yet, so nothing played |
| **Not right** | The spawned soldier and both spawned guards (unnamed, all women) each got roster voice V001: see below |

### Runs on the 16:20 and 17:43 builds (trains #9 and #10, `Tools/NpcUnified/verify_npc_melee.py`, strike clips skipped)

Evidence: `Saved/NpcUnified/verify_run9b_train9.json` (11 of 12), `verify_run10b_train10.json` (15 of 16), `run9_*.png`,
`run10_*.png`. No pose warning, watchdog repair or ensure in either log.

| What | What happened (17:57 run unless said) |
|---|---|
| A real spell kills and ragdolls | A soldier left at 5 health, hit by a Fire Bolt: dead, body simulating, pelvis 16 cm off the floor (also on the 16:20 build) |
| Unnamed NPCs sound different | Six spawned NPCs: six different roster voices, each of the look's sex, enabled rows only; civilians got voices of their look's side; each one's Remark and bark cue was its own voice's take |
| Guards sound like guards | Two of three spawned women guards got guard voices with their own alert bark. The third got a civilian voice (generic alert bark): the roster has two free women's guard voices and a new voice beats a repeat. This is the one failed check |
| The finished looks are NPCs | All 20 `BP_Look_*` spawn through `SpawnNpc`, enrol, walk, read their sex from their tag, keep a readable pose; three (three different bodies) ragdolled on a lethal hit |
| Spawns by archetype wear them | `SpawnNpc("Civilian")` and `("Guard")` gave `BP_Look_Gilt*` people |
| Walkers | 41 walkers: no camera component active or ticking; each carries an empty foley bank; 38 outfit and face parts on six NPCs take the body's bounds and raise no overlap events, and everyone still renders whole |
| `Npc.Weaken 5` | Exactly one spawned NPC left at 5 health and held still |
| Walker camera cost | Frame time with the cameras off 37.7 and 34.7 ms, switched back on 36.5 ms: no measurable difference in editor PIE. The performance session's trace is the measurement to trust |

### What went wrong

**The lethal-hit path crashed the shared editor once (11:53).** `KickRagdoll` asked the engine for the closest point
on a body's physics asset. That engine call indexes the body's bone array with no bounds check, and the array was
empty on a squad soldier. The array was empty because of the old nonlethal **physics flinch** (a partial
simulate-and-blend on an arm): on the crowd MetaHuman bodies it leaves the Body without a readable pose afterwards.
Measured in PIE: after a fireball flinch the Coin Clerk's chest bone read as identity for the rest of the run and it
slid about in its reference pose. That flinch predates this work, but ragdolling every NPC made the crash reachable.

What was done about it:
- 12:03 emergency rebuild with a guard on that one engine call.
- 12:14 the data assets were saved with `bPhysicalHitReaction` off, which stopped the flinch in the running editor
  without a rebuild; the check above ran after that.
- 12:16 it crashed a second time the same way: a nonlethal bolt on a squad caster whose own archetype still had the
  flinch on; the engine's animation update asserted on the empty buffer 0.2 s later.
- From the 12:33 build the flinch is refused in code whatever an archetype asks, and replaced by a lean away from
  the impact (a rotation of the walker under its locomotion pawn, restored exactly). Every place the NPC component
  reads body bones first checks both of the body's bone buffers, and a per-frame watchdog re-registers a living
  body whose buffers are incomplete before it animates (it logs each repair; none so far).
- The user's "dead NPCs T-pose" was this same lost pose. On the 12:33 build a walker, a guard and a soldier all
  ragdoll (pictures above).

### Voices

- Every NPC gets a sex from its look (a table of the team looks in `GetLookSex`; the actor tags `NPC_Voice_F` /
  `NPC_Voice_M` override it) and one of three slots per sex, `F1`..`M3`, the least used among the NPCs present.
- Audio's roster table `/Game/Audio/Jam/Voice/DT_NpcVoiceRoster` (132 rows of `FReflectionsNpcVoiceRow`, row name =
  VoiceId) gives each NPC one `VoiceId` for its life, always of its sex and only from enabled rows (the 42 voices of
  named story people are disabled, so they are never handed out at random). How the pick weighs the rest is in the
  last point of this list; the actor's name breaks ties. Without the table nothing changes.
- Named people: whoever owns the person (the lives session) calls `SetVoiceOverride(VoiceId)` on the NPC component.
  A look's sex is the truth for person, look and voice: `GetLookSex(Actor)` (the look Blueprint's `NPC_Voice_F` /
  `NPC_Voice_M` tag, else the table of looks).
- A line group's cue is looked for in `/Game/Audio/Jam/Voice/Cues`, most personal first:
  `<Group>/SCue_VO_<Group>_<VoiceId>`, then `SCue_VO_<Group>_<F1..M3>`, then `SCue_VO_<Group>`. Audio owns all of
  it; the NPC code only references cues and never plays a missing one.
- The archetype names the groups it barks: `BarkOnFear`, `BarkOnAlert`, `BarkOnAttack`.
- Passing remarks: a calm, untarnished, non-hostile NPC with the living player within 4.5 m says its `Remark` cue
  from its head; 60 to 90 s per NPC, one remark at a time across the map. Whoever has an NPC talking (street
  conversations, dialogue, cutscenes) calls `SetRemarksMuted(true)` on its component meanwhile.
- The voice pick, as loaded: different voices first (a voice nobody present has beats a repeat), then the kind of
  character (audio records a voice's lines only for its own kind), then the side (the look's `Look_Side_*` tag, else
  the archetype's home world, else where the NPC stands), then the age (`Look_Age_*` against the roster's Age).

### Who the tarnished go after

- `Infected` and `VillainHost` hunt the player or the nearest NPC they can see, whichever is nearer
  (`Combat.bHuntsNpcs`). Reaching an NPC (250 cm) they ask the villain's `BeginConversion(Attacker, Victim)` by name
  and both are held (`BeginScriptedHold`) for the sequence; the villain ends it with
  `SetInfection(Victim, Infected, Attacker)`. If the villain refuses, the hunter attacks instead.
- Hunters that convert (`Combat.bConvertsNpcs`) leave alone: their own kind, anyone already tarnished or burned out,
  anyone held by a set piece, and actors tagged `NoVillain` or `Villain_BurnedOut`. `Friendly` does not protect
  anyone (agreed with the villain session, which takes Friendly townspeople too). The player is never converted.

**Hunters did not see NPCs standing next to them (found 14:28, fixed in the 15:05 build).** In the second
run the tarnished civilian ignored two clean civilians 3.5 m away, went for one 5 m away, and needed 12.75 s to reach
its first victim. The sight test (`HasLineOfSight`) ran from the hunter's eyes to the target actor's origin. For the
player that is the middle of the capsule; for an NPC actor it is the feet, on the floor, so the floor itself could
end the trace. The same test gates the melee motor's walking on maps with no navmesh and its strike, which fits the
squad session's earlier note that melee only advances with clear sight. The fix aims at the chest (origin + 110 cm
for anything that is not a pawn). Confirmed at 15:11: the hunter took a civilian 3.5 m away and the hand-over came
at 3.75 s.

**Unnamed NPCs of one side shared one roster voice (found 15:11, fixed in the 15:59 build).** The pick
narrowed to the NPC's home side before anything else, and the roster has a single enabled female voice for Pewterside
(the named cast took the rest; a map with no world anchors resolves to Pewterside). The new rule puts different
voices first: a voice nobody present uses always beats a repeat. Confirmed at 16:35 and 17:57: six unnamed NPCs, six
voices. The 15:59 build still ranked side above character (a soldier got a shopkeeper's voice); the 17:43 build
ranks character first.

**The strike clips crashed the shared editor (16:16:19, my test, my PIE slot).** The melee motor could play a strike
clip on the visible body (`PlayAnimation`, then back to the animation blueprint). The test switched the new clips on
in memory only, three enemies struck with the clips playing (picture `M_enemy_strike.png`), the test killed them, and
0.7 s later the engine asserted in `SkinnedAsset.cpp:471`: 342 bones, 0 output transforms, on the Coin Clerk body. It
is the same lost pose as the 12:16 crash; which step empties the buffer is still not proven. Nothing had been saved,
so the assets never listed a clip. Since the 17:43 build the motor refuses clips outright
(`bStrikeClipsOnTheBodyAreSafe` in `StartAttack`), whatever an archetype lists. Excerpt: `crash-1616-npc-strike-clip-death.log`
in the sessions' shared notes.

**A change of mine landed in the middle of a build train (14:55, train #7).** The train had started early; my edit
made its build fail on `ReflectionsNpcCombatComponent.cpp` (new .cpp against the pre-edit headers) and it had to be
rerun from the last checked state. Since then NPC source only changes after the orchestrator says so.

### Consequences: in the 19:32 build, run in PIE 19:51 to 19:57

Written after the user's playtest ("when they get to the player, nothing happens", "they don't even die", "there
needs to be reactions for everything"). Four short PIE runs on `Lvl_HeroSampleCrowd`, no crash, no pose warning in any
of them. Pictures: `ArtDirection/NPC_Unified/images/consequences_1957.png`; results: `Saved/NpcUnified/verify_sorcery.json`,
`verify_reactions.json`, `verify_reactions2.json`, `verify_heat.json`, `diag_tarnish_cast.json`.

| What | Seen |
|---|---|
| Sword strike | montage on the walker, body stays on its animation blueprint; enemy killed mid-swing: ordinary ragdoll |
| Sword prop | `SM_Frostside_MirrorSword` on the guard's `hand_r` |
| Tarnished casting | from 6.3 m it holds its distance; bolt at 1.0 s (player 100 to 89), wisp at 5.5 s (to 80); burst up close |
| Fireball on a soldier | thrown 9.7 m, 1.2 m high, alive (56 to 36), body never simulated |
| Lightning Bolt on that soldier | 36 to 15, ticks to 12 and 9 while it stands convulsing 1.4 s, then drops into the ragdoll |
| Lightning Bolt on a guard, killed 0.6 s in | ordinary ragdoll |
| Water Orb on a soldier | shoved 6.7 m (56 to 44); killed while thrown: ordinary ragdoll |
| Ice Shard on a soldier | walker clock at 0.05 for 2.5 s, then 1.0 again; alive |
| Fire Bolt on a townsperson | 20 to 6, runs |
| Lightning Bolt on a townsperson | dead at once, ragdoll, hands still moving 1 s later |
| Assault in front of a guard | heat 0.34, 7 witnesses, the guard investigates |
| Murder | heat 0.94, the guard is on the player 0.25 s later |
| `ClearPlayerHeat` | heat 0, the guard stands down |
| Allied soldier and one of the tarnished | goes for it at once, kills it, loses 14 health, never turns on the player |
| Six townspeople spawned with no look | six different looks |

What the runs turned up:

- **The tarnished did not cast from 12 m.** With a sight radius of 9 m they never noticed a player further off, and
  with townspeople nearer than the player they went for those instead. The Infected asset now has sight 15 m (data,
  saved 19:56); the built-in gets the same number on train #13.
- **Throws are about twice too far** (9.7 m and 6.7 m). The launch speeds are halved on train #13.
- **The first reactions run could not judge three cases**: its unguided spells missed townspeople and a guard who had
  wandered off. `verify_npc_reactions2.py` repeats them from 2.6 m (6 of 6).
- **"Drops at or under half health" after a shock also applied to the villain's host.** It is exempt from train #13.
- **Pewterside still borrows Giltside's looks.** The crowd-looks session made twelve grey Pewterside looks at 19:49
  (`/Game/Characters/Lanthorne/Looks/Pewterside/PewLook_<X>`), but the side test in the 19:32 build only knows the
  name `Look_Pewter`. Train #13 reads them as Pewterside and adds them to the pools.
- **Bystanders and soldiers standing with their arms out (the user saw it too): two causes.**
  (1) The body skeleton that five bodies share (`RedLondon/BridgeGuard/Assembled/Common/.../metahuman_base_skel`,
  used by BridgeGuard, GlassArtisan, ArchiveApprentice, FestivalDrummer, FerryPilot) was saved at 19:28 without its
  `root` bone: the version in git commit e9f3c59 starts root, pelvis; the saved one starts pelvis and carries the new
  name `Rig_FerryPilot`. Every look on those bodies has stood in the reference pose since (about half the cast); at
  17:57 the same body walked normally (`run10_N_new_looks.png`). The fix is to put the file back from e9f3c59 with the
  editor closed, which the orchestrator does at the train #13 restart; it is not an NPC code change.
  (2) Any NPC shows the reference pose for its first moments after spawning, until the walker's animation has run.
  Train #13 keeps a just-spawned NPC unseen for that moment (`Npc.HideUntilPosed`, default 1).
- **Soldiers (the user at 20:00: no armour, sword and shield in hand).** Train #13: every soldier and caster carries
  the sword (`Combat.WeaponProp`); `Combat.ShieldProp` puts a shield on the left forearm of looks that do not wear
  one already (placed from the body's reference pose, `Combat.ShieldOffset` tunes it, `Combat.ShieldMaterial` gives
  Frostside's a plain wood face); `HiddenLookParts` on the archetype hides parts of the look by name, and the
  fighters go without `Armor`. A guard stance for a standing soldier needs two new walker clips and is train #14.
- The archetype assets were re-synced to the build and saved at 19:56 (eleven; `DA_Npc_AlliedSoldier` is new), which
  is what switched the walker strikes, the props and the casting on outside these checks.
- `Npc.ElementReactions` and `Npc.Heat` are 0 in the 19:32 build's code. `Config/DefaultEngine.ini` sets both to 1
  from the next editor start; train #13 makes 1 the default in code.

**The tarnished are dark sorcerers.** `Infected` and `VillainHost` (`Combat.bCastsAtPlayer`) notice a player inside
their sight radius (15 m and 16 m), then stop anywhere between 4 and 20 m with a clear line, face them, gather for 0.9 s (a glow and a light at the chest, a cast gesture on the
walker), then throw: a dark bolt, 35 % of the time a slower one that follows, a burst inside 3 m. 2.5 to 4 s between
casts. The spell side's `UReflectionsTarnishCasterComponent` does the magic when it is in the build (called by name);
without it the NPC fires `AReflectionsSpellProjectile` itself. They still run townspeople down to turn them.

**Sword strikes play on the hidden walker.** `Combat.WalkerAttackAnimations` (`/Game/Combat/Melee/AS_Melee_<Move>_Walker`,
the crafting session's set) are played with `PlayOnWalker`: a slot montage on the walker's own animation blueprint,
which the visible body follows. The body's animation mode is never changed, which is what the crash was about.
`Combat.WeaponProp` puts a static mesh in the right hand (`weapon_r` socket, else `hand_r` with the crafting session's
grip): a sword for guards, soldiers and enemies, a wand for soldier casters.

**Look pools by side.** `GetLooksForSide(ArchetypeId, Side)`, `GetLooksAt(ArchetypeId, Location)`, `GetSideAt(Location)`.
A look's side is read from its Blueprint path (`Look_Gilt`, `SimpleRed` → Giltside; `Look_Frost`, `WhiteLook` →
Frostside). A side with no look for a role uses its own nearest role (its soldiers for its guards), never the other
side's. Pewterside has no looks yet and borrows Giltside's. `SpawnNpc` with no look uses this, and takes the look the
fewest living NPCs wear (`GetLookUseCount`), so copies of one person appear only when the pool is used up.

**Health** (Fire Bolt 14, Fireball 20, Lightning Bolt 21): Civilian and Timid 20, Brave and Infected 28, Guard,
Hostile and SoldierCaster 42, Soldier and AlliedSoldier 56, Enemy and VillainHost 70.

**What a spell does to a living NPC** (`Npc.ElementReactions 1`). The spell says which reaction it wants
(`FReflectionsSpellHitData::Reaction`, set by the spell code for built-in, crafted and enemy spells):

| Reaction | Spells | What the NPC does |
|---|---|---|
| Explosion | Fireball, Flame Burst, any blast | thrown away from the centre, harder the nearer; a blast of fire also sets it burning |
| Push | Water Bolt, Tidal Surge, Water Orb, Force Push | shoved along the hit |
| Knockdown | Stone Shard, Earth Shock | knocked back |
| Lift | air spells | thrown upward |
| Pull | gravity wells | drawn toward the centre, again on every tick of the spell |
| Freeze | Ice Shard, Frost Nova | held in place 1 to 3 s (the walker's clock is slowed; the body holds its pose) |
| Burn | Fire Bolt | cries out for 2.5 to 5 s; those who do not fight back run |
| Electrify | lightning | stands convulsing 1 to 2 s and takes 6 more damage; then townspeople, and anyone at or under half health, drop into the ragdoll, and the body twitches on the ground. A bolt that kills outright drops it at once and the body twitches |

Thrown always means `LaunchCharacter` on the hidden walker plus a stagger montage on it. A living body is never
simulated (the partial-physics flinch is what lost the pose and crashed the editor twice). Voice groups asked of the
audio session: `React_Hurt`, `React_Knocked`, `React_Burning`, `React_Shocked`, `React_Death`; sounds
`/Game/Audio/Jam/Cues/SCue_Body_Knockback`, `SCue_Burning_Loop`, `SCue_Shock_Loop`, `SCue_Shock_Collapse`. A missing
cue or clip is skipped.

**Crime and heat** (`Npc.Heat 1`). The player's spell hurting an NPC that is not against them is an "Assault",
killing one a "Murder"; other code reports its own with `ReportPlayerCrime(Victim, Crime, Location)`. A witness is a
living, non-hostile NPC within its awareness radius with nothing solid between it and the place (a victim still
standing counts). Witnessed crimes raise heat (0 to 1: +0.34 assault, +0.6 murder, +0.25 other) and one witnessing
townsperson calls for the guards (`Heat_CallGuards`). From 0.5, guards and allied soldiers who can see the player
attack (`Heat_Halt`, `Heat_Alarm`). Heat cools by 0.04 a second, starting 8 s after a crime or 6 s after a pursuer
last saw the player. `OnPlayerCrime(Victim, Crime, Witness, Location, Heat)` fires once per witness (once with a null
witness when nobody saw it); `GetPlayerHeat()`; `ClearPlayerHeat()` wipes the record and stands pursuers down.
Hurting enemies or the tarnished is no crime. NPCs steered by the squad layer are left to that layer.

**Allied soldiers.** New built-in archetype `AlliedSoldier`: Giltside's own, Guard disposition, sword, the Giltside
guard looks. `Combat.bFightsTarnished` (a new archetype field) makes an NPC that is not against the player go for any
Infected NPC it sees inside its sight radius, and never for the player on sight. The villain's host is left to the
player. Guards do not have the flag set.

Checks, each one short PIE run on `Lvl_HeroSampleCrowd`: `Tools/NpcUnified/verify_npc_sorcery.py` (casting, sword,
walker strike and dying mid-swing, side pools), `verify_npc_reactions.py` and `verify_npc_reactions2.py` (every
reaction above, and dying mid-convulsion, mid-throw and at the end of a shock), `verify_npc_heat.py` (assault,
murder, guard turning, record cleared, an allied soldier against one of the tarnished, six different looks),
`diag_tarnish_cast.py` (one tarnished watched from 7 m and 13 m with every other NPC held).

### Train #14 (built 23:31, snapshot `Saved/NpcUnifyWIP/good-2222`): first results, and one crash

Run on Gray London between 23:36 and 23:43 on 2026-11-14.

| What | Result |
|---|---|
| Soldiers' weapons (`verify_npc_armed.py` A) | 4 of 4. Sword on `hand_r`, shield on `lowerarm_l`, the look's own armour and shield hidden, hands raised 18 to 24 cm by the hold and kept up in a charge. Standing, the blade points 45 degrees forward-right and the shield face 45 degrees up: to be tuned in the data assets. |
| Fireball knockdown with `Npc.WalkerPhysics 2` (B) | Works: thrown, flat on the ground from 1.6 s, on its feet again at 4.9 s. The visible body was never simulated while alive. |
| Jolt on a hit (B1) | Not proven: the measure read the same with physics on and off. |
| Killed mid-knockdown and mid-get-up (C, kills 1 and 2) | No crash, ordinary deaths. |
| Killed mid-shock with `Npc.WalkerPhysics 2` (C, kill 3) | **Crashed the editor** (23:42:55): the lost-pose assert, `SkinnedAsset.cpp:471`, on the IvenRook body. First suspected: the walker jolt during a shock; ruled out at 03:46 (see the split below). |
| Street scenes (`verify_npc_street.py` A, 03:43 on train #18) | 7 of 8: begin, one-off clip, pinned (movement None), released, ended by a noise and by death, refused when frightened. The miss is the check's own (its civilian spawned already frightened). |
| Panic ripple (B, 03:44) | Works: the NPC 3 m away reacts at once, those 10 and 13 m away about 0.7 s later; all at once with `Npc.PanicRipple 0`. |
| Fleeing (B) | Works: 12.8 m in 6 s at a steady 2.1 m/s, never stuck (was 7 m and standing). |
| Sword and shield angles by data (`tune_weapon_angles.py`, 03:44) | Not possible with one offset: the turn that puts a standing soldier's shield dead ahead (64 degrees about the forearm) turns a charging one's to the side. Offsets taken off again, nothing saved. Fixed in code for train #19 instead (below). |
| The crash, split (03:46 to 03:50, physics on) | 8 isolated soldiers killed mid-shock: fine. 12 living people shocked to the end: fine. The 24-kill series: 12 kills fine, then the same assert in the third batch (BridgeGuard body), and a non-fatal ensure for the same thing in the first (IvenRook body). So it is not lightning. |

**What is known about the crash.** A visible body ends up with an empty pose buffer; the next pose evaluation asserts on a
worker thread (`USkinnedAsset::FillComponentSpaceTransforms`), and `USkeletalMeshComponent::ExcludeHiddenBones` reports the
same thing as an ensure. In the engine this state comes from a pose task being forced to complete
(`HandleExistingParallelEvaluationTask`) while a physics-blend task of the same component is in flight, followed by a
second buffer swap. Who triggers that here is not known. All three events (23:42, 03:49, 03:50) happened in a PIE that
had killed someone during a knockdown or a get-up seconds earlier, and all three fall within about 2 s of the Tarnish
taking its first host (20 s after play goes live), which is also when the test reaches its third kill. The logs cannot
separate those two. The split still open: the same series with `Villain.StartDelay 9999`.

**The cause, found at 04:10.** The split with the villain switched off settled it: all 24 kills passed, but the engine's
"0 transforms" ensure fired one frame after the first soldier was killed while getting up, on that soldier's own body.
An NPC that dies while knocked down or getting up is left with an empty pose buffer on its visible body; nothing
happens until a later spell wakes that corpse, and then the engine asserts. Deaths during a plain jolt are safe (20 of
them, no ensure), and so are knockdowns and get-ups that death does not interrupt. The villain is not involved.

**The fix (train #20, in Source and compile-clean, not yet run).** For a death while down or rising, nothing is done to
the visible body at all: it is not made a ragdoll and its ticking is not changed. The hidden walker, which already is
a ragdoll on the ground, stays down as the corpse, and the visible body keeps copying it exactly as it does for a
living knocked-down NPC. One killed on the way up drops again from where it is. Hits and lightning twitches on such a
corpse go to the walker's ragdoll. Proof still owed: the 24-kill series twice in a freshly started editor (the ensure
reports only once per session), with no ensure and no assert. `Npc.WalkerPhysics` stays 0 until then.

![Guard stance, before and after](images/soldiers_guard_stance_train19_0406.png)

**Train #19, verified 04:06** (snapshot `good-0401`): standing soldiers measured over a full loop of the stance: blade
0.83 to 0.85 ahead (was 0.76, with 0.62 to the right), shield face 0.73 to 0.76 ahead (was 0.19). Charging: shield
0.92 ahead. What it is: a soldier standing still for 0.35 s takes the
whole-body guard stance; a moving one keeps the additive hold over its legs. Measured before the change: standing,
blade 40 degrees to the right and shield face 75 degrees off ahead; charging, both ahead.

**Train #20 loaded 04:24; first results 04:26.** The 12 archetype assets were re-synced and saved (soldier pools as
below, townspeople back to 28 looks). `lineup_soldiers.py`, 3 of 3: all seven dressed soldier looks spawn, get their
walker, stand in the guard stance, and hold the sword on `hand_r` and the shield on `lowerarm_l`; no armour or second
shield shows (the BridgeGuard-bodied looks still carry those parts, hidden); every one stands 18.0 cm above the height
asked for, on the road sheet, so the floor snap works. The crash fix has not run yet: it needs the 48-kill proof in a
fresh editor.

![The dressed soldiers](images/dressed_soldiers_train20_0426.png)

**Proof of the crash fix, so far 30 of 48 kills (04:38 on train #20, 04:46 on train #21, each in a freshly started
editor, `Npc.WalkerPhysics 2`, villain active).** Ten kills in the middle of a knockdown, ten while getting up, ten
mid-shock: every one lies dead as expected (the twenty knockdown and get-up deaths as the walker's ragdoll), no corpse
lost its pose, and both editor logs hold no ensure and no assert. Before the fix the ensure came at the first get-up
kill of every fresh session. A batch of six costs the editor 4 to 8 GB of free memory, so each fresh start takes two
batches; the last 18 need two more restarts. `Npc.WalkerPhysics` stays 0 until all 48 are in.

**Proof round 2/3 (04:54, train #21): no ensure and no assert, but the proof did not pass.** 41 kills are in across
four fresh sessions with clean logs. One corpse had lost its pose: a soldier killed while lightning was jolting it, an
ordinary ragdoll death. That is a death during a jolt, not during a knockdown, so the train #20 fix does not reach it,
and the 23:42 crash fits it exactly (the failing body was the soldier killed mid-shock 0.7 s before). What the bad
deaths have in common: the visible body was ticking after physics (knockdown, get-up or jolt) and the death ended
that and started the body's own ragdoll in the same moment. The 27 deaths during a knockdown or a get-up since train
#20, which no longer do that, are all clean.

**Train #22 (in Source, compiling 05:00):**

- `Npc.WalkerJolts`, default 0: the jolt has its own switch and is off. `Npc.WalkerPhysics 2` then means knockdowns
  and get-ups only. The jolt was never shown to be visible, and with one on every hit a kill inside it would be common.
- The visible body's own ragdoll is never started during a jolt or in the quarter second after a jolt or a get-up has
  ended. In that window a dying NPC tips over instead (the old fallback for a body that cannot be a ragdoll).

**Train #23, confirmed 05:23 to 05:25 (fresh editor, no ensure, no assert).**

- The frozen-corpse fix, at defaults with nothing set from the test: 8 of 8 Frost soldier deaths kept their pose and
  fell (pelvis from about 120 cm to 43 cm in 2 s, pose within 5 cm of the ragdoll). It was 3 of 8 lost before.
- Sword and shield stay on their bones: 2 s after death the sword is 7 to 8 cm from the right hand and the shield 24 to
  26 cm from the left forearm, as when alive. (With the old behaviour restored from the script, both props lost their
  bone and dropped to the body's origin: that was the "weapons at the feet" of the 05:18 picture.)
- One batch with `Npc.WalkerPhysics 2` on this build: 6 kills (2 mid-knockdown, 2 while getting up, 2 mid-shock), all
  clean, no corpse without a pose.
- Recommendation given to the orchestrator: ship `Npc.WalkerPhysics=2` (one line under `[ConsoleVariables]` in
  `Config/DefaultEngine.ini`), with `Npc.WalkerJolts` left at 0. 39 of 39 deaths during a knockdown or a get-up have
  been clean since train #20. Known limits: about an hour of test time, never run in a packaged build, each
  knocked-down character is simulated until it gets up, and one killed in the quarter second after getting up tips
  over instead of going limp. The decision is the user's; the line is not in the ini yet.

**The frozen-corpse bug in the game as it ships (found 05:06, pinned down 05:11 to 05:19 on train #22, everything at
its defaults, walker physics off).**

- 3 of 8 Frost soldier deaths (FrostSoldier_Iven by a plain kill and as a Guard, FrostSoldier_Amara) had lost their
  pose 0.4 to 2 s after death; 0 of 2 Gilt. It is not about lightning, the archetype or the moment of death.
- What the player sees: the dead soldier stays standing, frozen in its last pose with sword and shield, while its
  ragdoll falls unseen.
- Cause, as far as it is known: a ragdoll body had two writers of its pose every frame, its own animation (the
  retarget from the walker) and the physics blend; the pose buffers get out of step. Why the Frost looks and not the
  Gilt ones is not known.
- Fix (train #23, one line in `StartRagdoll`): once the body simulates, `bNoSkeletonUpdate = true`, so only the
  physics blend writes the corpse's pose. Tried live from the test script before it went into C++: 0 of 8 Frost
  deaths lost their pose, the pose followed the ragdoll to within 5 cm, the bodies fell.
- Can it crash? Three Fireballs and two Lightning Bolts into six such corpses (three without a pose), physics off: no
  ensure, no assert. Both editor crashes were asserts on a body in this state, but with walker physics on. One trial.
- Corpses are clothed (base-colour pictures: the pale Frost clothes read as skin under the red death light), every
  garment follows the ragdoll, the walker is hidden. With the fix the sword and shield lie at the corpse's feet, not
  in its hands; whether that is new is to be checked on train #23.

![Frozen corpses, before](images/frozen_corpses_before_0511.png)
![Corpses with the fix, lit and in base colour](images/soldier_corpses_fix_0518.png)

**A reading I got wrong, corrected 04:44.** Corpses whose pelvis read "8.2 cm under the ground" in the runs before
train #20 were not sunk into the road. A body that has lost its pose buffer answers every bone lookup with the world
origin (`USkinnedMeshComponent::GetBoneTransform` returns the identity), and that zero minus the ground reference was
the number. About a quarter of the corpses in those runs were in that state, ordinary ragdoll deaths among them, and
crowd-react saw it at 04:30 on an ordinary death with walker physics off. So there is a second, older way into the
empty-pose state besides the knockdown deaths fixed in train #20. It has not crashed anything by itself. The stress
check now counts such corpses (`pose_empty`); none in the 30 kills on trains #20 and #21.

**Also in train #20:**

- **Dressed soldiers.** Guards and soldiers wear the seven dressed soldier looks (`/Game/Characters/Lanthorne/Looks/Soldiers/`:
  no armour, plain fitted clothes). Guard, AlliedSoldier and AlliedSoldierCaster: GiltSoldier_BridgeGuard, _Rowena,
  _Archivist (Pewterside's guards stay PewLook_*). Soldier, Enemy and Hostile: FrostSoldier_Amara, _Nia, _Saran, _Iven.
  SoldierCaster keeps FrostTobias and FrostWen. The side of a look is read from its path, so GiltSoldier_ counts as
  Giltside and FrostSoldier_ as Frostside. The archetype assets hold their own copy of the pools: re-sync them after
  the train, then run `apply_extra_looks.py` for the townspeople.
- **Spawned on the real floor.** `SpawnNpc` stands the NPC on the topmost walkable, broad surface within 50 cm above and
  150 cm below the place asked for (`Npc.SpawnOnFloor`, default 1). Gray London's roads are thin sheets 18 cm over the
  city ground; a caller passing the lower height got an NPC with its feet in the road (crowd-react, 04:10).

Look lists outside the pools, for whoever changes the cast: `UReflectionsNpcSubsystem::TeamLooks()` (the 20 older looks;
last fallback of the pools, and used directly by Lives and Quests for named people); `ReflectionsSquad.cpp` 129 to 134
and 576 to 577 (squads' own fallbacks, used only when the pools return nothing).

**`Npc.WalkerPhysics` stays 0** (the C++ default) for the jam unless the cause is found and the 24-kill run passes; the orchestrator agreed (04:00).

![Soldiers with sword and shield](images/soldiers_sword_shield_train14_2339.png)
![Fireball knockdown](images/fireball_knockdown_train14_2340.png)

What the train contains:



**Soldiers hold their weapons.** The sword is placed from the hand's reference pose: gripped in the closed right
fist, blade along the forearm line. The shield sits on the left forearm, face outward (`Combat.ShieldProp`, tag
`NpcShield`; this is the only system that attaches shields). An additive hold clip
(`/Game/NPC/Anim/AS_Npc_ArmedHold_Add_Walker`, made by `Tools/NpcUnified/make_armed_hold.py` from spell crafting's
march-hold clip) lies over whatever the legs do; without it the guard idle plays when the NPC stands still.

**Hits land with physics, on the hidden walker only** (`Npc.WalkerPhysics`, default 0 until proven: 1 = jolts,
2 = knockdowns too). The visible MetaHuman body is never simulated while alive and its animation is never touched;
it only ticks after physics for the length of the effect, so the pose it copies has the physics in it.

| Hit | What the body does |
|---|---|
| Any spell hit | The upper body is jolted along the hit and settles in 0.35 to 0.6 s |
| Strong blast, knockdown or shove (strength 0.6 and up; 0.8 for a shove) | Off its feet as a ragdoll, lies until still for 1.5 s (4 s at most), then gets up from its back or its front |
| Lightning | Jolted again at every flash while the current runs, then drops as before |
| Ice | Held frozen; the ice cracks with a jolt when it ends, and at once when a frozen NPC is struck |
| Killed while down, rising or shocked | The ordinary death: the walker stops where it lies and the visible body goes limp there |

**Street scenes** (for the crowd's scenario spots), on `UReflectionsNpcSubsystem`:

```cpp
bool BeginNpcScene(AActor* Npc, UAnimSequenceBase* Loop, bool bPinned = false, float BlendIn = 0.25f);
bool PlayNpcSceneClip(AActor* Npc, UAnimSequenceBase* Clip, float BlendIn = 0.2f, float BlendOut = 0.2f, bool bThenEnd = false);
void EndNpcScene(AActor* Npc, float BlendOut = 0.25f);
bool IsNpcInScene(const AActor* Npc) const;
FReflectionsNpcSceneEvent OnNpcSceneEnded;   // (AActor* Npc, bool bDisturbed)
```

- `Loop` is a clip for the walker's skeleton (`SK_UEFN_Mannequin`). It plays on the walker's `DefaultSlot`, whole
  body, for as long as the scene lasts. It may be null (pin only).
- `bPinned` stops the walker's movement, so a seated or leaning occupant stays exactly where the caller put it. Move
  the walker there first (`GetLocomotionDriver()`), then begin the scene.
- `PlayNpcSceneClip` plays one clip once over the loop (an idle break, a sit-down). The loop returns by itself.
  With `bThenEnd` the scene ends with the clip (a stand-up).
- Only a calm, free NPC is accepted. One that is reacting, dead, taken, knocked down, shocked, frozen or alight is
  refused, and nothing changes.
- The NPC ends its own scene within a fraction of a second on any reaction but Calm (Alert included), any spell
  hit, death, being taken by the villain, and removal. The clip stops with a 0.15 s blend, movement comes back and
  `OnNpcSceneEnded` fires with `bDisturbed` true. `HoldNpc` does not end a scene.
- In a scene the NPC does not roam by itself. Stroll is not touched: the caller keeps it off.

**Panic spreads and the street empties.**

- Noise, violence, death and a taking reach each NPC later the further away it is: `Npc.PanicRipple` seconds
  (default 0.2) per 5 m ring, 0.9 s at most. Alarm calls and direct hits are not delayed. `Npc.PanicRipple 0` is
  the old behaviour (everyone on the same frame).
- A frightened NPC used to run 7 m in a straight line and stand there. It now takes the clearest run of up to 25 m
  among seven directions away from the threat, prefers one that ends out of the player's sight, and picks again
  when it arrives or is blocked (`Npc.FleeExits`, default 1).
- `GetSecondsSinceViolence(Near, Radius)` says how long a place has been quiet, for the crowd's refill cooldown.
- Fled ring walkers are recycled today: fleeing lasts 7 s, then they are calm and the ring's usual rule applies,
  and a still-frightened one already goes beyond 110 m. Retiring unseen fleeing walkers sooner and holding refills
  while a street is not quiet are changes to the ring, which is crowd-react's.

**Checks, to run in the row after the train** (`run_slot4.py` in the session scratchpad runs them in order under the
PIE lock): `verify_npc_armed.py` PART A (close-ups of both hands, standing and walking, a Gilt and a Frost soldier),
PART B (jolt, knockdown, get-up, killed while down and rising), PART C (24 kills in the middle of a knockdown, a
get-up and a shock, with the log scanned for asserts and pose warnings), and `verify_npc_street.py` PART A (scenes:
begin, one-off clip, pinned, released, ended by a noise, a hit and a death, refused when frightened) and PART B (the
ripple's timing at 3, 8 and 13 m, how far a frightened NPC runs, the quiet timer).

### What still doesn't work

- **The partial-physics flinch stays refused.** `bPhysicalHitReaction` on the archetype does nothing until someone
  proves it safe on a body type and flips the flag at the top of `StartPhysicalHit`.
- **Why that flinch loses the pose is not understood**, only measured (on with it, gone without it). The watchdog is
  there in case something else triggers the same state.
- **More unnamed guards than free guard voices sound like civilians.** The roster keeps most guard voices for named
  people (two free women's guard voices at 17:57). A third unnamed woman guard gets an unused civilian voice, and
  her alert bark is then the generic F1..M3 cue. More enabled guard rows in audio's table fix it; so would letting a
  guard voice repeat once before spilling (one weight in `AssignVoice`).
- **Guards have two looks** (GiltBridgeGuard, GiltRowena), so a third spawned guard repeats one. Civilians have
  twelve, soldiers four, casters two. Squads read the same pools since the 17:43 build (their own WhiteLook paths are
  only a fallback for an empty list; reported by the squads session, not checked by me). The six NPCs placed in
  `Lvl_HeroSampleCrowd` still wear the older Blueprints (level content).
- **The ten assets were last re-synced at 14:27** (`create_archetype_assets(resync=True)`); since then only their
  `Looks` were rewritten (`Tools/NpcUnified/apply_cast_looks.py`, 17:58). A re-sync is needed whenever a build adds an
  archetype field or changes a built-in number, and it is safe again from the 17:43 build on (on the 15:59 and 16:20
  builds it would have switched the strike clips on).
- **The old strike clips on the visible body stay off.** The code that played `/Game/Combat/Melee/AS_Melee_Sword_<Move>_<Body>`
  on the body (`PlayAnimation`, then back to the animation blueprint) crashed the editor (see "What went wrong") and
  is refused in code whatever an archetype lists. Strikes are the walker's montages now (see "Consequences").
  `verify_npc_melee.py` runs the old path only with `RUN_MELEE_CLIPS = True`; do not set it in a shared editor.
- **There is no knockdown and get-up.** A thrown NPC is launched on its feet and staggers; only death is a ragdoll.
  Getting a living body back out of a ragdoll is the kind of step that lost the pose before, so it was left out.
- **The reaction sounds and several voice groups may not exist yet** (`React_*`, `Heat_*`, the four `SCue_*`
  sounds, `AS_React_Stagger_Walker`). The code skips whatever is missing: the reaction still happens, silently.
- **A ragdolled body's bones cannot be read afterwards** (same engine behaviour), so a later direct hit on a body on
  the ground does not kick it; blasts still throw it.
- **A caster on its own does not cast.** `SoldierCaster` keeps its distance; the squad layer performs the casts.
- **Unordered aggression only targets the player** (and, from the 19:28 build, the tarnished for archetypes with
  `Combat.bFightsTarnished`). A guard hit by a soldier's spell runs; it does not fight the soldier. `Engage(Target)`
  can order any fight.
- **Reactions use straight-line movement** except the melee motor, which path-follows when the map has a navmesh
  (`Lvl_HeroSampleCrowd` has none, so it walks straight while it can see its target).
- **The Mass crowd bridge is an interface only.** No map has a Mass spawner; the crowd session builds the bridge if
  one is added.
- **Reputation and NPC state do not persist** across map loads.
- **The data assets hold their own copy of the numbers.** A later change to a built-in in code does not reach an
  asset with the same id; press **Reset To Built In** on the asset (or edit it) to bring it in line.
- **Packaging:** `/Game/NPC/Archetypes` must be in `DirectoriesToAlwaysCook` (asked of the packaging session).

### MedievalLondon (2026-11-15, afternoon)

The game moved from Gray London's broad roads to the MedievalLondon town: lanes of 4 to 7 m, cross alleys of 3.5 to 4 m,
paving pieces laid on one big ground slab. Everything above was proven on Gray London.

In Source for the 14:15 train (each file compile-checked alone on the editor target at 12:48 and 12:50; no header touched;
**not yet run in the game**):

| What | Where | Why |
|---|---|---|
| Fleeing also tries 90 degrees either side | `PickFleeDestination` | With the threat across a lane, "straight away" is the wall behind the NPC; the lane itself was not one of the seven directions tried. |
| A stroll leg ends 70 cm short of a wall | `TickAmbientMovement` | The 2 m stroll triangle has its corners inside the house walls of a 4 m lane; the walker pressed against the wall for the whole leg. |
| Paving on the ground counts as floor | `SpawnNpc` | The floor rule wanted 5 m across both ways. Narrow-lane paving is smaller, so the NPC was stood on the slab under it. A smaller walkable piece now counts when broad floor lies within 30 cm under it (a bench seat, 45 cm up, still does not). `Npc.SpawnOnFloor 2` gives the old rule. |

The check: `Tools/NpcUnified/verify_npc_medieval.py` (one PIE of about 45 s, nothing saved). A census of everyone the
game put on the map (walker present, feet on the floor, posed, shown, not boxed in, not stuck, not standing in
another), then two townspeople, a Frost soldier and a Gilt guard stood in the nearest tight lane: a Fireball, who
flees where, two deaths and where the corpses lie. Result in `Saved/NpcUnified/verify_medieval.json`.

15:24: train #24 carries these. fable-streets' 15:12 repack took the paving strips away again (one ground block), so
the paving rule has nothing to act on there; it stays for maps that have such pieces. Read from the town's scripts and
mesh assets, not measured in play: houses are "complex as simple" with BlockAll and should stop walkers; stalls, crates
and casks have no collision, so everyone walks through them.

Read, not changed: the crowd's strollers steer round each other (`Crowd.Stroll.Avoidance`); walker capsules ignore
each other, so people who are not on the stroll system (fleeing, fighting, on a routine) can pass through one another.

## 5. Files

- Code: `Source/reflections/NPC/ReflectionsNpcSubsystem.*`, `ReflectionsNpcArchetype.*`,
  `ReflectionsNpcReactionComponent.*` (the NPC component), `ReflectionsNpcCombatComponent.*` (melee motor),
  `ReflectionsReputationSubsystem.*` (score store). Removed: `ReflectionsNpcPopulationSubsystem.*`;
  retired by its owner: `SpellVFX/ReflectionsSpellRagdollSubsystem.*`.
- Assets: `/Game/NPC/Archetypes/DA_Npc_<Id>` (ten; `DA_Npc_AlliedSoldier` is added at the re-sync after the 19:28
  build).
- Console (non-shipping): `Npc.Spawn <Archetype> [Count] [Distance]`, `Npc.Weaken [Health=5]` (holds the nearest
  unnamed NPC in front of the player and leaves it one hit from death). Console variables: `Npc.WalkerFoley` (0),
  `Npc.LeanFollowerParts` (1), and from the 19:28 build `Npc.ElementReactions` (0) and `Npc.Heat` (0).
- Tools added for the 19:28 build: `verify_npc_sorcery.py`, `verify_npc_reactions.py`, `verify_npc_heat.py` (one
  short PIE run each), `set_archetype_health.py`.
- Tools: `Tools/NpcUnified/verify_npc_system.py` (PIE check, about 45 s, stops PIE itself),
  `verify_npc_melee.py` (spell kill, voices, walkers, looks; about 45 s), `apply_cast_looks.py` (the finished looks
  into the assets' `Looks`, nothing reset),
  `verify_npc_batch2.py` (second PIE check: voices, spawns, barks, holds, conversion; about 45 s),
  `create_archetype_assets.py`, `create_guard_punch_clip.py`.
