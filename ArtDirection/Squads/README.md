# Enemy soldier squads

Status (2026-11-14, 13:05): **working in PIE on `Lvl_HeroSampleCrowd`** (11:45/12:03/12:33 builds). Later changes
(shared Soldier archetypes, archetype caster tuning, battle-order barks, melee fan-out, casters circling for a shot)
are compiled and queued for the 13:45 train but not yet re-tested in game. The "What works / what doesn't" section lists only what a PIE run showed.

## What it is

Squads of 4–6 White London raiders patrol a route in formation at a marching pace. When they spot the player, hear
the player's magic land nearby, or get hit, they break formation: melee soldiers close in through the NPC system's
melee motor, casters keep their distance and throw real catalog spells (Fire Bolt, Ice Shard, Arcane Bolt) with the
same projectile, muzzle, impact and sound as the player's. When the player is gone for a few seconds they stand down,
reform on the nearest route point and march on.

Soldiers are ordinary NPCs of the unified NPC system (`UReflectionsNpcSubsystem`), enrolled with that system's own
`Soldier` / `SoldierCaster` archetypes (data assets `DA_Npc_Soldier` / `DA_Npc_SoldierCaster` in
`/Game/NPC/Archetypes`; a private copy only when a spawner overrides health or melee damage). The NPC system owns their health, hit
reactions, fear and fleeing, death, ragdoll, coin drop and infection. The squad only decides where each soldier stands
while marching (and where a caster stands while fighting) and tells the melee motor whom to fight.

## Placing a squad (map owner)

1. Place a **Reflections Squad Route** (`AReflectionsSquadRoute`). Drag its spline points along the street.
   - `bLoop`: on for a closed patrol, off to walk to the end and back.
   - `HaltSeconds`: how long the squad stands at each point (0 = keep marching).
2. Place a **Reflections Squad Spawner** (`AReflectionsSquad`) and set `Route` to that route.
   - `SquadSize` (1–8, default 5), `CasterCount` (default 2; casters march at the rear).
   - `Formation`: `Column` (single file), `ColumnOfTwos`, or `Line` (shoulder to shoulder, wheels at corners).
   - `MarchSpeed` (150 cm/s), `RankSpacing` (170 cm), `FileSpacing` (125 cm), `TurnRate` (45°/s).
   - Looks: from the next train, soldiers take their looks from the NPC system's `Soldier` / `SoldierCaster`
     archetype `Looks` lists. The crowd looks owner fills those, and npc-unify owns the assets. `MeleeLooks` /
     `CasterLooks` (BP_WhiteLook_03–06) are only the fallback when a list is empty or `bUseArchetypeLooks` is off.
     Each squad uses its list in turn from its own starting index, so no face repeats inside a squad while the
     list has at least as many looks as the squad has soldiers of that role.
     Defaults: melee `BP_WhiteLook_06_GuardBoldRunes`, `BP_WhiteLook_05_GuardRags`; casters
     `BP_WhiteLook_04_CapMantle`, `BP_WhiteLook_03_Mantle`.
   - `CasterSpells`: the spell each caster throws (caster N uses entry N).
   - Combat tuning under *Squad|Combat*: sight 22 m in a 140° cone, alert 7 m all round, give up at 34 m, aim lead
     45 %, at most one cast start per 1.1 s per squad. `SoldierHealth` / `MeleeDamage` 0 = the archetype's
     (70 melee / 55 caster health, 8 melee damage). With `bUseArchetypeCasterTuning` (default on) the caster
     spells, damage scale (×0.6), range band (5–14 m), cooldown (3–5 s), windup (0.7 s) and cast clip come from
     the `SoldierCaster` archetype, so they are tuned in one place.
   - `bBarkOrders`: soldiers shout battle orders (audio's `SCue_VO_Soldier_Command_<voice>`, 3D from the head,
     each soldier in the voice the NPC system gave it) on engaging and every 6–10 s in combat.
   - `RespawnDelay`: respawn a fresh squad this long after the last soldier dies (0 = never).
   - `CastAnimations` / `MarchAnimations`: clips played on the soldier body; each soldier uses the first clip whose
     skeleton matches its body. Defaults: the hero's Kimodo cast `AS_Hero_CombatBoltRight` (fits the IvenRook-bodied
     caster looks) and the Kimodo march cycle in `/Game/Squads/Animation` (one copy per soldier skeleton).
     `MarchAnimationSpeed` (155 cm/s) is the ground speed the march cycle was authored at.
3. Give the level a navmesh (a Nav Mesh Bounds Volume over the streets the squad uses). Squads path between route
   points on it, and the NPC system's melee motor needs it to chase around obstacles. Without one the squad marches
   straight legs between points (fine on open ground, walks into walls otherwise) and melee soldiers only advance on
   a target they can see. **No map in Content has a navmesh yet** (checked 12:53), so navmesh pathing is untested.

Nothing else is needed: no Blueprint, no tags, no level script.

**Weapons (train #11):** each melee soldier carries Codex's `SM_Frostside_MirrorSword` (98 cm), and each caster
`SM_Pewterside_ReaderWand` (34 cm), in the right hand. The props pivot at the grip with the blade along +X. They go on
the body's `weapon_r` socket, or on `hand_r` with spell crafting's grip (`WeaponGrip`) when the body lacks that socket.
They have no collision and stay in the hand through ragdoll. The NPC system now puts the same props in Soldier /
SoldierCaster hands from the archetype's `Combat.WeaponProp`, and it owns soldier weapons. The squad attaches its own
(`MeleeWeapon` / `CasterWeapon`) only when the archetype names no weapon, so each hand holds one prop. Not yet checked in PIE: grip and scale on the moving hand. Known gap: the fingers stay open.

**Start patrol (train #11):** `Squads.StartPatrol` (default 1) raises one squad on `Lvl_HeroSampleCrowd` and
`Lvl_MockCity`, so a player who presses Play sees soldiers. It's a column of 5 on a 14 × 8 m loop, 8–16 m from the
player start. The loop is ahead if there's room, otherwise to the right, left or behind, and is checked for clear
ground, line of sight and navmesh. It isn't raised when a squad already patrols within 40 m of the start. It fights
only up close (sight 7 m), or when hit or cast at. Scripted checks that need an empty start set
`Squads.StartPatrol 0` before StartPIE; `Squads.Clear` removes it.

**Crash safety (merged 19:30 build):** by default no squad code switches a visible MetaHuman body into single-clip
mode. Ragdolling a body in that mode crashed the editor at 16:16 (best-practices review X1/X2). So:
- `Squads.MarchClip` defaults to 0: soldiers march with the NPC locomotion walk, not the Kimodo march loop.
- The cast channel and flick play on the hidden walker as montages (`AS_Melee_Wand_Channel_Walker` /
  `_Flick_Walker` via npc-unify's `PlayOnWalker`; `Squads.BodyClips 1` restores the old body clips).
- Dead soldiers are never animated.

**Fighting back (merged 19:30 build, not yet seen in PIE):** any hit or kill on a soldier turns the whole squad on
the attacker at once:
- The formation breaks and the leader calls the charge.
- Casters cast from range.
- The squad runs its melee soldiers down to the target, along the navmesh path where there is one. The NPC melee
  motor strikes once they're within 6.5 m (`MeleeHandOverRange`).
- Squads of the same faction with a soldier within 40 m join (`AlarmRadius`, one hop only).
- The fight goes on until no soldier has seen the target for 8 s (`LoseSightTime`; sight up to `LoseRadius` 60 m).
  Then the squad calls a retreat, reforms and resumes its patrol.

**Factions (merged 19:30 build, not yet seen in PIE):** `Faction` comes from the side level (`bFactionFromSide`):
- **Frost** raiders in rags, on Frostside: hostile to the player.
- **Gilt** guards in red, on Giltside (Captain Brask's men): allied. They fight the tarnished and Frost soldiers on
  sight, and turn on the player only if the player hits or kills one of them, or commits a crime (npc-unify's
  `OnPlayerCrime`) that a soldier witnesses or that happens within 25 m.

Gilt soldiers use the NPC types `AlliedSoldier` / `AlliedSoldierCaster` (falling back to `Guard`). They wear only
Giltside looks: GiltBridgeGuard / GiltRowena until the medieval outfits arrive. Both Gilt looks already wear a skinned round shield (`BridgeGuard_RoundShield`), so the squad's
`SM_Giltside_PatrolShield` only goes on a Gilt melee soldier whose look has no shield part. It goes on `hand_l`,
fitted per soldier from the live hand pose (face out, upright; `ShieldGrip` overrides this). Once ordered onto
the player, Gilt soldiers' strikes and projectiles do hurt the player (npc-unify: NPCs attacking the player count as
hostile to it). The user's rule is enforced: a squad never wears another side's looks.

Battle lines use npc-unify's `PlayBark` with audio's per-voice groups: `Soldier_Charge` (or `Heat_Alarm`),
`Soldier_AllyDown`, `Soldier_EnemyDown`, `Soldier_Victory` and `Soldier_Retreat`.

Test commands: `Squads.SpawnGilt` spawns an allied test squad. `UReflectionsSquadSubsystem::RaiseAlarm(Offender,
Location, Radius)` lets any system set nearby squads on someone.

**Streamed levels:** put the spawner and its route in the same streamed level. Soldiers are spawned into the
persistent level, so from train #8 the spawner despawns them when its level streams out and raises a fresh squad when
it streams back in. Each spawner has exactly one route, set by reference; squads never search for routes by name or
tag. A patrol that shouldn't attack on sight gets SightRadius and AlertRadius 0. It should then fight only when
provoked: hit, or the player casting within 11 m. Untested: the NPC system's own aggravation could still start a
fight.

## Testing (PIE only, nothing saved)

Console (non-shipping builds):

| Command | Does |
|---|---|
| `Squads.SpawnTest [n]` | spawns test squads around the player: a column of five and a line of five |
| `Squads.Clear` | removes them |
| `Squads.Engage [i]` / `Squads.Reform` | break formation / stand down |
| `Squads.Cast` | first ready caster of each squad casts now |
| `Squads.KillAll` | kills every soldier through the normal damage path |
| `Squads.Dump` | logs squad and member states |
| `Squads.Passive 1` | squads ignore the player (for filming the march) |
| `Squads.MarchClip 0` | march with the NPC system's locomotion walk instead of the march cycle |
| `Squads.PauseDriverAnim 1` | pause the locomotion pawn's animation while the march loop plays (off: no measured gain) |
| `Squads.Debug 1` / `2` | draws route, anchor, slots (and member states) |
| `Squads.AutoTest 1` | set before PIE: spawns the two test squads when `Lvl_HeroSampleCrowd` begins play |

Scripted checks (each one PIE run under a minute, stopped at the end, and each takes the team's
`Saved/PIE_LOCK.json` first; write `Saved/SquadsTest/`):
`Tools/Squads/retest_squads_pie.py` (all of it in one run of about 60–80 s: the build's archetypes and flinch flag, march
captures and frame cost, one squad engaged with the cast-clip sequence, melee motor, barks, three kills with ragdoll
and coins, reform; use this one on a new build), `test_squads_pie.py` (march and cast captures),
`test_squads_combat_pie.py` (one squad: melee, a spell in flight, reform), `test_squads_kill_pie.py` (kills, ragdoll,
coins, caster flee, frame cost), `probe_melee_pie.py`. The MCP call times out at about 60 s and stops the script
there; the `finally` block still stops PIE, frees the lock and writes the report. They use top-level `await`; run them in the editor's `execute_python` through
`compile(src, path, 'exec', flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)` and `await eval(...)`.
March cycle authoring: `Tools/Squads/author_march.py` (Kimodo; stages `source`, `status`, `bake`).

## How it works

- **Formation.** A virtual anchor walks the route at `MarchSpeed` and leaves a breadcrumb trail. Column slots sit on
  the trail one rank apart, so followers walk in the leader's footsteps and turn where the leader turned; line slots
  sit beside the anchor and the line slows while it wheels. The anchor waits when any soldier falls more than ~1.6 m
  behind its slot, so the formation never stretches. Each soldier steers its NPC locomotion pawn toward its slot with
  the formation's own velocity plus a correction, capped at 1.7× march speed (2.2× while reforming).
- **Cost.** One squad actor ticks for all its soldiers; only the anchor queries the navmesh (once per route leg);
  sight checks run at 4 Hz and only trace when the player is inside the cone. Fine grooms (peach fuzz, eyelashes)
  are hidden on soldiers (`bStripFineGrooms`).
- **March animation.** `Tools/Squads/author_march.py` asked Kimodo for a 4 s soldier march (upright, chin up, firm
  heel-to-toe steps, straight-arm swing), took the bound Quinn take, retargeted it with the existing
  `RTG_MannequinToHero` (IvenRook skeleton, casters) and `RTG_Crowd_BridgeGuard` (BridgeGuard skeleton, melee),
  and cut the best-matching cycle: frames 88–117, 0.97 s for two steps (≈124 steps a minute), 80 cm steps, ≈157 cm/s
  on the ground. The root is locked, so it plays in place on the body while the NPC locomotion pawn carries the
  soldier; its play rate follows each soldier's real speed. Standing still (halts, reform) and fighting switch the
  body back to the NPC system's animation.
- **Casting.** A caster stops, faces the player and channels: it plays spell crafting's Kimodo
  `AS_Melee_Wand_Channel_<Body>` loop (both arms forward, leaning in; `ArtDirection/CombatMelee/README.md`) while
  the telegraph grows, then cuts to `AS_Melee_Wand_Flick_<Body>` timed so the flick's strike (0.27 s in) lands
  exactly when the spell leaves. The channel loop starts at the point whose pose best matches the flick's first frame
  (worked out once per clip at spawn from the arm and upper-spine bones), so the cut barely shows. Every clip is
  listed in its three body variants and `ClipFor` picks the one matching each caster's skeleton. If no flick matches,
  the caster plays the hero's `AS_Hero_CombatBoltRight` instead, the earlier gesture. The spawner fields are
  `ChannelAnimations`, `ReleaseAnimations`, `ReleaseAnimationStrike` and `CastAnimations`. During the windup the spell
  gathers in its right hand (the shared `NS_Spell_Projectile` system, tinted to the element, plus a growing point
  light). At the release frame it spawns a real `AReflectionsSpellProjectile` (so the spell VFX subsystem dresses it
  exactly like the player's), broadcasts the usual release visual (muzzle + cast sound), and its own squad is
  ignored by the projectile (no friendly fire inside the squad).
- **Melee.** When the squad breaks formation, melee soldiers first fan out around the player (±45° apart, ~1.2 s) so
  the back rank isn't stuck behind the front; then the squad calls the NPC component's `Engage(player)` and stops
  steering that soldier (`SetExternallySteered(false)`), and the NPC system's melee motor chases and strikes.
  Reforming calls `Engage(nullptr)` and takes the soldier back. The strike, hit-react and death clips belong to the
  NPC combat component, not the squad. The NPC session is wiring spell crafting's Kimodo sword set
  (`/Game/Combat/Melee`, `_BridgeGuard` variants for these melee looks) into it. No sword or wand prop is attached yet
  (Codex is making them), and the hands stay open (no grip pose).
- **Hooks used** (NPC component, found at compile time by `requires` checks in `ReflectionsSquadNpcBridge.cpp`):
  `SetExternallySteered(bool)` while in formation or keeping casting range, `Engage(AActor*)` for melee. Fleeing is
  the NPC system's call: when a soldier's reaction turns to Fleeing the squad lets go of it and takes it back once it
  calms down. With these archetypes casters flee briefly (2.5 s) whenever hit and melee soldiers fight back.
  Soldiers never use the NPC system's old physics flinch (`bPhysicalHitReaction` off), which crashed the editor.

## What works / what doesn't

Checked in PIE on `Lvl_HeroSampleCrowd` between 11:52 and 12:48 on the 11:45, 12:03 and 12:33 builds
(`Tools/Squads/test_squads_pie.py`, `test_squads_combat_pie.py`, `test_squads_kill_pie.py`; images and reports in
`ArtDirection/Squads/images/`).

**Mock city (Lanthorne), train #10, PIE runs at 17:52 and 17:56.** The script travels to `/Game/MockCity/Lvl_MockCity`
inside PIE, so the editor's open map isn't switched (`Tools/Squads/test_squads_mockcity_pie.py`,
`test_squads_mockcity_unload_pie.py`; reports `Saved/SquadsTest/mockcity*-report.json`).
- **The world-jump session's three placed squads work from their side levels.** Gilt Lamp Company (Column 5), Frost Wall
  Company (Line 5) and Pew Constables (Column of twos 4) all spawned. All three logged
  `route points, navmesh paths`, so the mock city's navmesh is used. They marched 9–11.5 m in about 7 s.
- **Provoked-only patrols stay calm:** Gilt (SightRadius / AlertRadius 0) kept marching in formation with the player
  3.6–5.9 m away. The hostile Frost line engaged (all five Fighting) within 3 s of the player standing 12 m in
  front of it.
- **Streaming despawn (train #8 fix) works.** A dynamic copy of Pewterside was loaded 4.5 km out. It raised a fresh
  4-soldier squad (straight legs, being off the navmesh). Unloading it despawned that squad: the log shows
  `Marching -> Inactive` at the unload, and its soldier actors were destroyed. The check tripped on one destroyed actor;
  `gone()` now handles that.
- **Frame cost with all three squads running:** game thread 24.6 and 33.0 ms in two runs (frame 25.4 / 29.1 ms, GPU 5.9 /
  6.4 ms). The squad-free baseline wasn't measured: crowd-looks' MetaHuman builds then blocked the editor. The editor's
  background throttle couldn't be turned off from Python: UE 5.9 doesn't expose `throttle_cpu_when_not_foreground`.
  These numbers don't look throttled, while the 85 ms of the train #7 run probably was.
- Not checked: which archetype looks the soldiers wore.

**Re-test: train #7 build (editor DLL 15:05), one PIE run at 15:09–15:10, nothing overridden.**
Report `images/retest-report-train7.json`, images `images/train7_*.png`.
- **The build gives every soldier the right setup:** all 10 soldiers enrolled with the shared archetypes
  `DA_Npc_Soldier` (melee) / `DA_Npc_SoldierCaster` (casters). The physics flinch is off in both the archetype and the
  component, and ragdoll on death is on. Casters picked up the archetype's Ranged tuning: range 5–14 m, cooldown
  3–5 s, windup 0.7 s, damage ×0.6. The looks are the team MetaHumans listed below.
- **Two squads march** (`train7_march_column.png`). While squad 0 fought, squad 1 kept marching its line route,
  halted at the end and marched back.
- **Casters cast with the new wand gesture.** Logged per cast: Channel loop → Flick → spell released → back to the
  NPC animation (`ABP_Crowd_IvenRook`). Each cast took about 0.5–0.65 s of channel and 0.2–0.5 s of flick. The two
  casters released 3 spells each in 18 s with no forcing. Images: `train7_caster_mid_cast.png` (the channel pose,
  element glow in the hand) and `train7_spell_in_flight.png`.
- **Melee closes in:** the three melee soldiers fanned out around the player (about 40° apart) and closed to 1.5–2.3 m.
  The NPC melee motor started 6 attacks for each of them and landed 6, 5 and 5 hits (`train7_melee_closing_in.png`).
- **Barks:** two soldiers played `SCue_VO_Soldier_Command_F1` / `_F3` during the fight.
- **Deaths:** player spells killed the three melee soldiers. All three went to ragdoll (pelvis on the ground) and
  dropped 3 coins (`train7_ragdoll.png`). **No crash** with the flinch off from the build itself; this closes the
  11:53/12:16 crash item below.
- Not covered this run: the run was cut at 61 s by the MCP timeout just after `Squads.Reform` began (squad 0 went to
  Reforming). Reform completing was verified in the earlier runs below.

**Works (seen in PIE, earlier builds):**
- Two test squads spawn from `Squads.SpawnTest 2`, are enrolled in the NPC system (each gets its locomotion pawn) and
  march their routes: the column keeps exact 170 cm ranks in single file, the line marches five abreast, both with
  the Kimodo march cycle on every body (`squad_march_column.png`, `squad_march_line.png`).
- `Squads.Engage` breaks both squads out of formation at once (all members go to Fighting).
- Casters wind up with the hero's BoltRight cast and the element glow in the hand (`squad_caster_mid_cast.png`), then
  release real projectiles: 5 casts from 4 casters in the first 6 s of the fight.
- Second PIE run (12:12, one squad, player placed where the squad can see it): the lead melee soldier closed in
  and landed 4 of 4 strikes through the NPC melee motor; casters released 3 spells, one shown in flight with the
  player's own projectile VFX (`squad_spell_in_flight.png`) and an Ice Shard hitting the hero
  (`squad_fight_ice_hit.png`); hero 100 → 51 in 10 s standing still. `Squads.Passive 1` + `Squads.Reform` then put
  all five back in formation and the squad marched on (Marching, all In Formation, 9 s later).
- Third PIE run (12:47, 12:33 build, soldiers' physics flinch switched off at runtime): player spells killed 3 of
  3 targeted soldiers; all three went to **ragdoll** on the ground through the NPC system
  (`squad_soldier_ragdoll.png`) and **each dropped a coin** (0 → 3 coin pickups). A caster hit once by a Fire Bolt
  **fled** (NPC reaction Fleeing, squad released it) and was back in the fight about 4 s later. The squad stayed
  engaged with its 2 survivors. Report: `images/kill-report.json`.
- **Every soldier is a team MetaHuman look:** melee `BP_WhiteLook_06_GuardBoldRunes` and `BP_WhiteLook_05_GuardRags`
  (BridgeGuard MetaHuman body), casters `BP_WhiteLook_04_CapMantle` and `BP_WhiteLook_03_Mantle` (IvenRook MetaHuman
  body). No mannequin is ever spawned; the Kimodo take was only an intermediate on the Quinn rig and the clips the
  soldiers play are retargeted to the two MetaHuman skeletons. The white mannequin visible near the player start in
  some captures is a level prop (`SKM_Quinn_Simple` on the PlayerStart), not a soldier; distant soldiers can look
  grey in the offscreen captures because their textures had not streamed in.
- Fourth PIE run (12:52, line squad, player in front of it): **all three melee soldiers closed in** from 6–8 m to
  arm's length and landed 10 of 11 strikes (`squad_line_melee_charge.png`), casters cast 3 times (one Arcane
  Bolt in flight), and the squad reformed and marched on. Report: `images/combat-report-line.json`.
- **Cost:** in editor PIE, two marching squads (10 soldiers) raised the game thread from 20.0 to 26.9 ms
  (frame 20.5 → 26.6 ms, GPU 4.2 → 5.6 ms). Most of that is each soldier's NPC locomotion pawn running the sample's
  motion matching plus a MetaHuman body; the squad logic itself is one tick per squad. A second measurement (12:50)
  gave +3.1 ms game thread (26.7 → 29.8 ms) and +1.2 ms GPU for the same ten soldiers; editor numbers are noisy.
  Pausing the locomotion pawns' animation while they march made no measurable difference, so that option
  (`Squads.PauseDriverAnim`) ships off.
- The fight is dangerous: standing still against **both** squads at once, the hero went from 100 to 50 health in
  6 s (melee plus spells, at the earlier 8 melee / ×0.6 spell tuning). Damage is now 6 / ×0.5.

**Doesn't work / not verified:**
- **Two editor crashes while testing (11:53 lethal hit, 12:16 non-lethal hit).** Both were NPC Body meshes left
  with no bone pose by the NPC system's old partial-physics hit flinch (`bPhysicalHitReaction`); placed level NPCs
  showed the same state in runs without squads. Root cause found by the NPC session; logs in the shared notes folder
  (`crash-1153-npc-lethal-hit.log`, `crash-1216-iven-body-empty-transforms.log`). Fix: the NPC system guards every
  bone read and replaces the flinch, and the soldier archetype turns the flinch off (in the code for the 12:45 train;
  the 12:47 run switched it off at runtime and had no crash). Re-run on train #7 with the fix compiled in and no
  runtime override: 3 kills, no crash.
- **Frame cost on train #7 is unexplained.** That run measured 85 ms game thread with two squads marching. Earlier
  builds measured 27–30 ms (+3 to +7 ms for the squads). This run had no squad-free baseline. The machine was short on
  memory (the asset compiler reported 405 MiB free), and another session ran editor Python during the run. So this
  number says nothing yet about the squads' own cost. It needs a baseline run with and without squads.
- The flinch itself is gone for soldiers: a hit shows the NPC system's shove/lean, not a physics arm.
- `Lvl_HeroSampleCrowd` has no navmesh, so squads there walk straight legs; navmesh path-following is untested.
  Without a navmesh the NPC melee motor only steps toward a target it can see, so melee soldiers stand still when
  level geometry or a comrade blocks their sight line (seen in PIE: the two rear melee soldiers never advanced).
  Reported to the NPC session; the squad now fans its melee out around the player before handing them over.
- Reforming after the player leaves (34 m) cannot happen on this 35 m test floor; `Squads.Reform` is the only test.
- Aim assist does not target actor NPCs (crowd session's finding), so the player must aim at soldiers by hand.
- With the player behind level geometry, casters found no shot for 25 s (0 casts) in the 12:47 run; from the 13:45
  train a caster without a sight line circles the player to find a gap. Not verified yet: the train #7 run put the
  player in clear sight.
- `/Game/Combat/Melee` (wand clips) is loaded by path, so packaging must cook that folder. Without it, casters fall
  back to `AS_Hero_CombatBoltRight`.
