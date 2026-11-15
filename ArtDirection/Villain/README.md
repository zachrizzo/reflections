# The Tarnish: possession, conversion and the finale

Villain side session, 2026-11-14. All player-facing names follow the IP rename (rows V1-V3 of
`ArtDirection/Submission/rename-table.md`): the villain is **the Tarnish**, called "it"; its NPCs are **tarnished**;
the sides are Pewterside, Giltside and Frostside (names read from world jump's config). Every player-visible string
is in one file: `Source/reflections/Villain/ReflectionsVillainText.cpp`.

## What works and what doesn't (read this first)

Verified in PIE on `/Game/Worlds/Test/Lvl_WorldJumpTest` (screenshots in `Screenshots/`, raw runs in
`Saved/VillainTest/`):

| Feature | Status | Evidence |
|---|---|---|
| **A real run with no console (New Game on the mock city to Victory)** | **Works** (20:03-20:05, after the merged #11/#12 build) | `Saved/VillainTest/proof/report.json`: New Game from the title (config map, no cvar) -> possession on by itself, "play is live", first host `BP_Look_GiltFerryman_C_0` 20 s later (`23_proof_first_host_by_itself.png`) -> the 3 pages touched, FirstPage and MirrorWhole cutscenes skipped with the skip button's own UFUNCTION -> true form DORMANT on the Frost crown marker, still DORMANT with the hero inside the tower, MANIFESTING on arrival (`24_proof_crown_true_form.png`) -> 6 Final Spell casts through the F key's `CastFinalSpell`, boss 750 -> 0 in 7.9 s, hero 100 -> 92.8 -> Ending -> game flow "Victory." and the victory screen (`26_proof_victory_no_console.png`). One shortcut: the hero reached the crown by teleport (the nav walk helper is not exposed to editor Python); playtest Run 3 walked the ramps for real. |
| Possession: takes a body, black smoke, violet glow | **Works** | `01_host_taken.png`; game flow meter 1/20 |
| Spread to nearby NPCs (ranged wisp) | **Works** | `02_spread_tarnished.png`; meter 2/20, later 5 |
| Host burns out (dies, ragdolls) and it hops to a fresh NPC | **Works** | `03_burnout_and_hop.png`, `04_new_host.png`; run report: hosts TestHost_5 → TestHost_4 → TestHost_0 |
| Tarnished slip into other sides (rifts) | **Works** | log: "Someone tarnished slipped through into Pewterside / Frostside" |
| Meter reporting through game flow / NPC system | **Works** | TARNISH x/20 on game flow's HUD |
| True form manifests (banner, music, stinger) | **Works** | `05_true_form_manifests.png` ("It rises from the cracked glass of Frostside") |
| Three telegraphed attacks hit the player | **Works** | `06_attack_volley_telegraph.png`, `07_attack_grasp_eruption.png`; hero health 100 → 28 over the test |
| Ordinary spells barely hurt it | **Works** | three Fire Bolts: 0.42 damage total |
| Final Spell (F / X) kills it | **Works** | 5 casts: 125, 125, miss, 125, 125 → 0 health (test ran at 500 health) |
| Death dissolve → game flow victory screen | **Works** | `10_burned_out.png`, `11_victory_game_flow.png` |
| Voice lines (audio's Tarnish VO, from the speaker's head) | Wired; loaded in the next train | |
| Mirror-complete path (world jump `OnBookComplete` → arena) | **Works** (14:50 run) | three `AddPage` calls → book complete → true form manifests and fights → Final Spell 125/hit, 4 hits → "Victory." in the game flow log; `12_bookcomplete_true_form.png`, `13_bookcomplete_final_spell.png`, `14_bookcomplete_victory.png`. Re-run at 15:39: the first page's cutscene (cutscenes' FirstPage) was playing when the book completed, so the finale waited for it as designed; after `Cutscene.Skip`, the true form manifested and fought. Run on `Lvl_HeroSampleCrowd`, the editor's map (an `open` to the test map only takes effect after the Python call returns, and another session restarted PIE in between), so the arena was the no-marker fallback in front of the player, not White's tower |
| **Conversion** (tackle → black wisp → turned) | **Works** on MetaHuman NPCs | `Villain.Convert` on `Lvl_HeroSampleCrowd`: tarnished meter 1 → 2, both get up with violet auras and run; `15_metahuman_tackle.png`, `16_metahuman_wisp.png`, `17_metahuman_risen.png` (far shots); closer, 15:39: `18_metahuman_tackle_close.png`, `19_metahuman_chained_conversion_close.png` (a second conversion chained off the first, meter 4/20). NPC unify also verified it through their hunt (28/28 checks, chained conversions) |
| Black eyes on MetaHumans + black aura | Aura **seen**; black eyes **not confirmed** | the aura shows in `17_metahuman_risen.png` and `19_...`; two close-up attempts didn't catch a face square to the camera |
| Neck twist during conversion | Wired (spell crafting's Kimodo "possessed" clips, 1.25 s wrench), **not yet checked up close on a MetaHuman** | |

True-form look pass (in progress, 14:55). The 'before' shots are `12_bookcomplete_true_form.png` (about 8 m) and `08_true_form_at_range.png`. In train #7: 16 mirror shards instead of 12, about 1.8x larger, on wider and lower orbits; a bigger heart (the aim point); and less smoke (boss shroud 0.3, 0.6 in phase two, was 0.55/0.9). Saved at 15:10: `M_Villain_Mirror` now gives a hard silver glint whenever a spinning shard faces the camera, and has a brighter silver edge (`Tools/Villain/build_villain_materials.py`, `build_mirror`). After (Frost Tower crown, 16:41): `20_tower_true_form_after_close.png`, `21_tower_true_form_after_far.png`, `22_tower_burned_out.png`. Up close the silver shards read against the dark body; at range in Frostside's very bright light he still reads mostly as dark smoke with silver flecks, and the heart (aim point) is hard to see. Second pass (17:15, train #10): attack-time smoke halved (wave 1.4 -> 0.7, phase two 0.6 -> 0.45, base 0.25), shards about 20% larger, a bigger heart, and `M_Villain_Mirror` given a steady silver self-glow so the shards stay bright against the dark core in Frostside's light (saved; the C++ part loads with train #10). Not yet re-shot.

Known look issues: the true form is mostly black robe and smoke, so in bright Giltside daylight it reads as a dark
hooded silhouette with a violet rim, which is clear at 10-20 m. Its eyes are too small to see at range. The black aura
on hosts reads as a dark cloud more than as body-hugging smoke.

## What it is

An all-black, hooded figure in a loose, rippling shroud (black mannequin, a generated robe and hood with
world-position-offset cloth, two eyes, a smoke/wisp/ember Niagara shroud). It has no body of its own until the end:
it lives in NPCs. A **host** has black eyes, a heavy black aura and a violet glow. It burns out after about half a
minute (its eyes start to burn violet in the last 4 s) and the Tarnish streaks, as black smoke, to a fresh NPC.
**Tarnished** NPCs have black eyes and a black aura (same clothes, same person); the NPC system makes them enemies.
When the mirror is whole, its true form rises at the top of Frostside's tower and only the Final Spell can burn it out.

## Conversion (new: how an NPC becomes tarnished)

The NPC system (NPC unify session) hunts with tarnished NPCs. When one reaches a clean NPC (~2.5 m) it calls
`UReflectionsVillainSubsystem::BeginConversion(Attacker, Victim)` (by name), which returns the sequence length and
the NPC system holds both NPCs that long. `AReflectionsVillainConversion` then:

1. **Tackle**: picks the paired tackle (`/Game/Characters/UEFN_Mannequin/Animations/Interactions/Tackle/
   M_relaxed_ragdoll_tackle_run_{F,B,L,R}_{L,R}foot_{A,V}`) whose recorded approach best matches where the attacker
   is, places the attacker at the clip pair's start offset (from the two root tracks; the clips use root motion with
   a ref-pose root lock), and plays `_A` / `_V` on both NPCs' locomotion drivers (`GetMesh()`, the hidden GASP
   mannequin each MetaHuman follows). The clips play as dynamic montages, without the MMI warp and ragdoll notifies.
2. **Pinned**: before the clip's ragdoll hand-off, the victim blends to the first (lying) frame of
   `M_ragdoll_getup_stand_B` (from the front) or `_F` (from behind) and convulses.
3. **Wisp**: black smoke flows from the attacker's `hand_r` into the victim's `spine_05` (1.4 s).
4. **Turned**: `SetInfection(Victim, Infected, Attacker)` (the NPC system makes it an enemy and releases both), black
   eyes + aura, and it gets up.

Abort (either dies, or the victim vanishes): both NPCs are released and the victim stays clean.

Who can be taken (hosts and conversion victims): any NPC with a visible body, including `Friendly` townspeople (the
NPC system lifts the tag while tarnished and restores it on cure). Opt-outs: the `NoVillain` tag, `Villain_BurnedOut`
(set on spent hosts), the player. The NPC system's infection state is the source of truth: an NPC it tarnishes
directly also gets the Tarnish look, and counts as tarnished for conversion.
Test: `Villain.Convert` (the nearest tarnished NPC converts the clean NPC nearest the player).
From train #8, `Villain.RangedSpread` defaults to 0: only tackles convert, through the NPC hunt. Set it to 1 on maps without the hunt, such as the test hosts in `Lvl_WorldJumpTest`; the PIE test does this itself.

## The tarnished as dark sorcerers (train #12, compiled 18:47; not yet seen in PIE)

The tarnished now cast (npc-unify's AI drives spell-combat's `UReflectionsTarnishCasterComponent`), so they should read
as the Tarnish's own at range. The villain side, in `ReflectionsVillainPossession.cpp`:
- **Burning eyes**: on top of the black MetaHuman eyes, a glowing violet-white glint sits on each eye bone
  (`FACIAL_L_Eye` / `FACIAL_R_Eye`), smouldering (glow 2.5, a host 4); mannequins keep the head-bone beads.
- **Cast pulse**: the possession component binds the caster's `OnTarnishWindup` / `OnTarnishReleased` itself. Over the
  wind-up the black-violet aura climbs (0.9 to 2.5), the eyes go to 4x and a violet light gathers at the chest; the
  release flashes all three and they fall away in 0.4 s. A cancelled cast drops after wind-up + 0.5 s. Spell-combat's
  own gather and hand light stay the focus; the body glow only agrees with it.
- **Wisps that trail**: the aura is world-space smoke, and it now thickens with speed (measured from the body's own
  motion, since a MetaHuman is carried by its hidden driver), so a running tarnished leaves a stream behind it.
- **Posture**: npc-unify adds a small forward hunch for the Infected and VillainHost archetypes (their lean, their data).

Soldiers (story canon: Giltside's soldiers fight the tarnished on sight):
- npc-unify's hunters take civilians, guards and Giltside's allied soldiers (a guard-like archetype); the enemy Frost
  squads (Enemy disposition) are left alone on purpose. `BeginConversion` accepts any NPC without a `NoVillain` tag.
- A soldier's (or the player's) spell on a tarnished NPC cures it and the NPC system moves the meter; a Tarnish spell
  from a tarnished caster, or the true form, never cures.
- A tarnished NPC killed by anyone: the NPC system takes it off the meter (`bCuredOnDeath`), and the villain clears the
  corpse's look (a last puff of smoke) through `OnNpcDied`, without calling `SetInfection` again. A killed host makes him
  hop at once, as before.

Pacing (train #13, after crowd-react's ring run took the meter 0 -> 3 in 40 s): ring walkers carry `NoVillain`, so only named or placed people are taken. Tackle conversions are spaced by `Villain.ConvertInterval` (85 s; the first two quicker so the player sees it happen, a little faster with each page), which puts a full meter at about 25 minutes for a player who ignores the Tarnish. If nobody takeable is near the player when he first arrives, he takes any named or placed person on the map, so possession always starts. `Villain.Convert` (tests) ignores the gap.

Scripted beats (cutscenes' BurningEyes): `BeginConversionScripted(Attacker, Victim)` is `BeginConversion` without the pacing gap; it first brings the attacker's walker to arm's length of the victim's and holds both NPCs for the sequence, and it may take a victim tagged `NoVillain` (a story beat turning a named person; the hunt and his own picks still respect the tag). Every refusal names its reason; scripted refusals log at Log level (compiled 03:15). While a cutscene plays, the hunt's `BeginConversion` refuses, so only the scene's scripted conversion runs (compiled 03:33).

Saves (game flow's slots, key `Villain`): every checkpoint, manual and quick save stores the tarnished (by Lives person
id, else level actor name; runtime-spawned crowd bodies are not stored), the host and its seconds left, and the
tallies. A load re-tarnishes them through the usual path (so the meter comes back through `ReportInfected`), retrying
for 10 s while Lives assigns people; a restored host gets no first-host taunt and the meter-band lines do not replay.

## Code (all new, `Source/reflections/Villain/`)

| File | What |
|---|---|
| `ReflectionsVillainConfig.*` | `UReflectionsVillainConfig` data asset (`/Game/Villain/DA_VillainConfig`) hard-referencing every asset, with built-in fallback paths; voice-cue paths; `UReflectionsFinalSpellDamageType`. |
| `ReflectionsVillainFx.*` | Palette, `Villain.*` console variables (tuning), Niagara/sound/voice/damage helpers. |
| `ReflectionsVillainText.*` | Every player-visible villain string. |
| `ReflectionsVillainLook.*` | `UReflectionsVillainLookComponent`: the true form's body, robe, hood, eyes, light and shroud. |
| `ReflectionsVillainPossession.*` | `UReflectionsVillainPossessionComponent` (added at runtime to an NPC: Infected / Host / BurnedOut; visuals only), `AReflectionsVillainWisp` (the hop streak), `AReflectionsVillainTestHost` (wandering test NPC). |
| `ReflectionsVillainConversion.*` | `AReflectionsVillainConversion`: the tackle → wisp → turned sequence. |
| `ReflectionsVillainSubsystem.*` | `UReflectionsVillainSubsystem` (the director: hosts, hops, finale, conversion hook), `AReflectionsVillainArena` (placeable marker), game-flow bridge, console commands. |
| `ReflectionsVillainBoss.*` | `AReflectionsVillainBoss` (true form) and its attacks: `AReflectionsVillainOrb`, `AReflectionsVillainHazard`, `AReflectionsVillainWave`. |
| `ReflectionsFinalSpell.*` | `UReflectionsFinalSpellComponent` (F / gamepad X, cast through the spell driver's `CastExternal`) and `AReflectionsFinalSpellProjectile`. |
| `ReflectionsVillainHud.*` | Boss bar, messages, banner, Final Spell prompt (UMG built in code). |

Nothing outside `Villain/` was edited. Other systems are used through their public APIs:
- world jump: `UReflectionsWorldJumpSubsystem::OnBookComplete`, `OnProgressRestored` (checkpoints), `IsBookComplete`,
  `TranslateBetweenWorlds`, the config's side names;
- NPC system: `UReflectionsNpcSubsystem::SetInfection` (state + meter), `OnNpcSpellHit` (a hit cures a tarnished NPC,
  or makes a host flee early), `GetNpcActors`, `FindNpc(...)->GetMovementCharacter()`; `EndScriptedHold` by name;
- spells: the driver's `CastExternal`;
- game flow: `ShowVictory` (and `ReportInfected` / `ReportCured` only if there is no NPC system), by name.

## Assets (`/Game/Villain/`, always-cooked)

- `DA_VillainConfig`: hard references to everything below plus the mannequin mesh/anims, the two SpellVFX systems
  and the villain cues, so cooking `/Game/Villain` cooks all of it.
- `Materials/`: `M_Villain_Body` (opaque black, violet fresnel rim; `Glow`, `Flash`), `M_Villain_Shroud` (masked,
  two-sided, tattered hem by UV, WPO sway and ripple growing toward the hem), `M_Villain_Eye`,
  `M_Villain_InfectedOverlay` (veins; off by default, `Villain.VeinOverlay 1`), `M_Villain_BurnedOverlay` (ash),
  `M_Villain_Telegraph` (ground circles and rings). Skeletal-mesh usage flags are set (a cooked build would draw the
  default material without them).
- `FX/NS_Villain_Shroud`: CPU, world space, 3 emitters (black smoke, stretched black wisps, violet embers); user
  params `Scale`, `Amount`, `Color`; compiles with 0 errors. Uses the spell team's `M_Spell_SoftPuff` / `M_Spell_Glow`.
  Orbs, streaks and the Final Spell reuse `NS_Spell_Projectile` / `NS_Spell_Impact` with their `User.Color` params.
- `Meshes/SM_Villain_Shroud`, `SM_Villain_Hood`: generated by `Tools/Villain/make_villain_cloth.py` (headless
  Blender), pivot at the feet, front +X, 1:1 (bounds match Blender in cm). Sources: `ArtDirection/Villain/Meshes/`.
- No textures.

Audio (owned by the audio session, referenced only): `SCue_Villain_*` effects, `SCue_VO_Tarnish_*` voice lines
(attached to the speaker's head), `SCue_VO_Tarnish_Taunt_Head` / `_Hop_Head` (2D), `SMX_Jam_StingerDuck`.

Scripts: `Tools/Villain/build_villain_materials.py`, `build_villain_niagara.py`, `make_villain_cloth.py`,
`make_villain_config.py`; PIE test: `test_villain_pie.py` (short steps, honours `Saved/PIE_LOCK.json`).

## Controls

- **Final Spell:** keyboard **F**, gamepad **X / Square** (Face Button Left). It appears when the mirror is whole,
  goes through the spell driver (normal windup, animation, 35 mana, 2 s cooldown; it shares the external-cast
  cooldown with crafting) and homes on the Tarnish. It is ignored while the crafting screen is open.
- Dodging needs only movement and jump, so keyboard and controller both work.

## The fight (about 20 s standing still, longer while dodging: 10 Final Spell hits from train #13)

Every attack now also winds up on his body: rim, cracks, eyes and heart brighten over the telegraph and drop at the strike, so a player learns to dodge on the peak (train #13).

It manifests when the player comes within 32 m of the arena. 1000 health; a Final Spell hit does 125 (8 hits);
anything else does 3% of its damage (and it says so). Three telegraphed attacks:

1. **Shadow volley**: 3 orbs gather over its head (1.25 s), then fly at you one by one, 0.3 s apart. Strafe.
2. **Grasping dark**: violet circles fill on the ground under and around you (1.6 s), then erupt. Step out.
3. **Shroud wave**: it rises, a warning ring pulses at its feet (1.35 s), then a ring of black spikes sweeps
   outward. Jump it (airborne is safe) or be far away.

Under half health: shorter telegraphs, 5 orbs, 5 circles, double waves, and it blinks around the arena.
Defeat: a 3.4 s dissolve, then game flow's `ShowVictory()` 2.5 s later. Checkpoints that restore a whole mirror start
the finale quietly (no banner), and it never starts twice.

## For the map owner

**Gray London (since 21:05, the only map: one side, World Partition, no world anchors).** Possession switches on for game flow's New Game map (from the next train, compiled 21:16), so it no longer needs anchors. Place exactly one **Reflections Villain Arena** at the centre of the finale floor (Tower district) with **Is Spatially Loaded** off; the villain keeps looking for it every 2 s and moves a waiting true form onto it when it loads. With no world jump the banners name no side ("It rises from the cracked glass of the city"). Not yet tested on Gray London. The notes below about Frostside's tower and the mock city describe the earlier three-side maps (deleted 21:05).

Place a **Reflections Villain Arena** actor at the top of Frostside's tower (`ArenaRadius`, default 14 m: leave
open floor to dodge). Without one, the arena is the White-side mirror page's position (cached at map start), then the
White world anchor, and its radius is measured from the nearest walls. The Tarnish runs in any map with a Reflections
World Anchor or an arena (`Villain.AutoStart 2` for every map).

**Self-starting in a real run (train #9, the playtest's blocker #3).** No console command is needed for any of it:
possession switches itself on for any map with world anchors or an arena, including anchors that stream in from
sublevels after the map starts (re-checked every 2 s for the first 2 minutes), and the first host is taken
`Villain.StartDelay` (20 s) after play is live: game flow's `IsRunLive()` (title dismissed or checkpoint restored,
no menu, not game over), no cutscene playing, world not paused. So nothing happens behind the title or during the
intro. Three pages complete the book, the true form waits on the arena (and moves onto the marker if its sublevel
loads late), the Final Spell arrives with the announcement, and the kill ends in game flow's `ShowVictory`. Maps
without anchors (the crowd sample, plain test maps) stay off unless `Villain.Start` is typed. Not yet proven in a
PIE New Game on the mock city: that run needs train #9 (`Tools/Villain/test_villain_pie.py`, stage `proof`).

The mock city (`/Game/MockCity/Lvl_MockCity`, world-jump) puts the arena on the crown of the Frost Tower. What the
fight needs there (sent to world-jump at 15:48):
- one arena actor at the centre of the crown floor, `ArenaRadius` set to the usable flat radius: 10-14 m ideal, 7 m minimum;
- flat, walkable floor with nothing inside the radius (he hovers about 1.5 m up, blinks inside the radius, drops ground
  hazards up to 2.4 m wide and an expanding ring wave);
- a blocking parapet of at least 1.2 m around the edge, so dodging backwards can't drop the hero off the tower;
- nothing for possession: hosts are the map's normal NPCs.

World-jump built it (16:00, loads after train #8): `VillainArena_FrostCrown` in sublevel `Lvl_MockCity_Frostside`, world
(301300, 7000, 2400) cm, ArenaRadius 10 m, on a flat 38 x 26 m crown with a 1.2 m parapet; the ramps come out about
17 m from the centre (inside the 18 m trigger).

**Tested in PIE at 16:41** (`Saved/VillainTest/tower/`): the book completed, the true form spawned on the marker (1.75 m above it, as designed), stayed **dormant while the hero stood inside the tower 23 m below**, rose when the hero reached the crown, fought, and died to 4 Final Spell hits (500 health in the test); the Ending cutscene then started on the crown marker. The Victory screen itself was not reached in this run (my test stopped PIE while the Ending played); it was reached through `ShowVictory` in the 14:50 run, and the no-console proof after train #9 waits for it.

From train #8 he rises when the player is within min(`Villain.ManifestRadius`, arena radius + 8 m) across the ground
**and** within 6 m of the arena's floor height, so a tower-top arena waits for the top of the ramps.

## Tuning (console variables, live)

`Villain.ConvertInterval` 85 (train #13: seconds between tackle conversions; first two at ~40%, each page -10% down to 70%), `Villain.HostLifetime` 28, `Villain.InfectInterval` 16, `Villain.InfectRadius` 2200, `Villain.HopRadius` 4000,
`Villain.RiftDelay` 9, `Villain.RiftChance` 0.6, `Villain.MaxInfected` 30, `Villain.StartDelay` 20,
`Villain.KillHostsOnBurnout` 1, `Villain.RangedSpread` 0 from train #8 (1 = the old ranged wisp), `Villain.VeinOverlay` 0, `Villain.BossHealth` 1250 from train #13 (10 hits; 750 in the merged #11/#12 build was an 8 s fight, 1000 before it was unwinnable),
`Villain.FinalSpellDamage` 125, `Villain.OtherSpellScale` 0.03, `Villain.FinalSpellMana` 20 (was 35),
`Villain.FinalSpellCooldown` 1.2 (was 2), `Villain.ManifestRadius` 3200, `Villain.AttackDamageScale` 0.4 (was 1),
`Villain.TelegraphScale` 1, `Villain.AutoStart` 1.

Debug commands (not in Shipping): `Villain.Start`, `Villain.Stop`, `Villain.Hop`, `Villain.Status`,
`Villain.SpawnTestHosts N`, `Villain.Finale`, `Villain.BossHere`, `Villain.DamageBoss N`, `Villain.CleanseAll`,
`Villain.Convert`.

## AI use

Code, materials, Niagara systems, the robe/hood geometry scripts and this document were written by Claude (Anthropic)
working in the editor through MCP. Voice lines and sound cues are the audio session's (see `ArtDirection/Audio/`).
