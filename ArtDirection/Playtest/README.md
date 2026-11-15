# Editor playtest: full playthrough checklist

Owner: playtest and integration lead (the former packaging session). Playing in **PIE**, the way a player would, after each build train.
PIE lock: runs of 4 minutes or less, batched, one slot after every train. Packaging is paused until Sunday (see `ArtDirection/Packaging/README.md`).

**How to read this:** each step is PASS, FAIL or BLOCKED (can't reach it), with a screenshot path, what broke, exact repro steps, and the owner.
The top 5 "can't play past here" blockers from each run go to the orchestrator.

## Owners (session IDs)

| Area | Session |
|---|---|
| Orchestrator, build trains | `local_6f701af5` |
| Spells, aiming, magic bar | `local_07d1c5bc` |
| World jump, coins, pages, towers | `local_830b60d0` |
| Spell crafting, melee set | `local_f926586a` |
| Audio, voice | `local_8ac9a603` |
| Villain, possession, finale | `local_dd0eeffa` |
| Game flow: title, pause, Tarnish meter, checkpoints, lives | `local_0b912c4f` |
| NPC unify: archetypes, reactions | `local_c650e0ab` |
| Crowd | `local_3627acc6` |
| Squads | `local_cf45fc1d` |
| NPC dialogue / talk-back | `local_7ede22ac` |
| Hero cloak | `local_18d00117` |
| Perf / stability | `local_0825a76a` |
| Cutscenes | `local_4511e14c` |
| Quests, journal | `local_00d6efaf` |
| NPC lives | `local_74e1e1dc` |
| Story bible, people book | `local_729a66f4` |

## Playthrough: Lvl_HeroSampleCrowd

| # | Step | Expected | Run 1 (after train #7) | Screenshot | Blocker / repro | Owner |
|---|---|---|---|---|---|---|
| 1 | Press Play | Title screen: REFLECTIONS, Start / Controls / Credits / Quit | NOT TESTED (by design) | `shots/r1-01-title.png` (that's the intro card, not the title) | Game flow confirmed this is intended: in PIE the title only shows with `GameFlow.TitleInPIE 1` set before Play, so automated PIE tests don't stall on a paused menu. Packaged and `-game` builds always show it. Next run: set `GameFlow.TitleInPIE 1`, Play, then check Start / Controls / Settings / Credits / Quit (plus Continue when a save exists), and that Start begins a fresh run. | game flow |
| 2 | Start | Intro cutscene plays and can be skipped | FAIL | `r1-02-intro.png`, `r1-02b-intro-mannequin-visible.png`, `r1-03a/b-camera-floor-run1.png` | (a) The intro plays even with `Cutscene.IntroInPIE 0`, although the log says "New-game intro skipped in PIE". (b) In batch 2 it took two `Cutscene.Skip`; in batch 4 one skip ended it at 9.7 s. (c) The subtitle shows twice (large centred and tiny at the bottom), and the tiny one stays on screen after the skip. (d) With `Cutscene.IntroInPIE 1`, GameplayCameras logged `Invalid input P=0 Y=-nan R=0 to FRotator::Quaternion` once (22:18:25 UTC, with a long callstack, not every frame), and after the skip the camera sits at floor level. (e) Each Play logs "Sequence did not contain any bindings with the tag 'Hero' / 'Jory' / 'Goldie'".<br>**Cutscenes' fixes (land with the next train):**<br>(a) The quest's intro step also called PlayCutscene("Intro"); Intro is now gated in PIE for every caller.<br>(b) Skip fades for 0.45 s of real time (about 1.5 s with PIE in the background), so the second Skip was a no-op; that's not a bug.<br>(c) The tiny subtitle was the voice wave's engine subtitle; it's now suppressed.<br>(d) The floor camera came from SetViewTarget(pawn); the cutscene now restores the previous view target.<br>(e) Bindings are set only for tags the sequence has.<br>Recheck after the next train. | cutscenes `local_4511e14c` |
| 3 | Giltside start | Hero spawns in Giltside with cloak; HUD shows health, mana, spells, Tarnish meter | FAIL | `r1-03-spawn-mannequin-visible.png`, `r1-08-talk-odette.png` | The white mannequin driver mesh shows through the hero (head, arms, hands), in the cutscene and in play. The HUD shows Tarnish 0/20 and the spell bar 1–4 (Healing 20, Levitation 15, Water Bolt 8, Fire Bolt 10); no health or mana bar was visible. The start area is the grey plaza, not Giltside art. **Cause (found by hero-cloak-fix):** it's not the hero at all. The pawn's own mannequin mesh stays hidden. The visible one is the Quinn spawnable ("Quinn \| Intro", SKM_Quinn_Simple) from the Kimodo take sequence `/Game/Cinematics/Takes/Source/LS_Takes_Intro`, which was left open in Sequencer. Sequencer spawns it into the editor world at (0, 0, 0), PIE copies it in, and the hero spawns at the origin right on top of it. The saved `Lvl_HeroSampleCrowd.umap` has no Quinn or SkeletalMeshActor (checked), so **packaged builds aren't affected; this is editor-only**. Fix: `Tools/Cinematics/kimodo_takes.py` should close the sequence when it's done. | cutscenes `local_4511e14c` (take tooling) |
| 4 | Move, jump, sprint | GASP locomotion, camera follows | PASS (move) | – | Batch 4 (intro skipped): 2 s of `IA_Move` forward moved the hero 4.2 m, and move and look input were not ignored. In batch 2, just after the cutscene, 1.5 s moved only about 1 m. Jump and sprint not checked. | spells (pawn) |
| 5 | Cast each spell 1–4 at nothing | Cast animation and VFX play; mana drains and regenerates | PASS (Fire Bolt) | `r1-05-cast-lmb-no-projectile.png` (batch 3) | Batch 4: a 0.6 s LeftMouseButton press cast Fire Bolt; mana read 100, then 92.7 about 6 s later (cost 10, then regen). Earlier, `IA_Shoot` did nothing, because the cast action is the driver's runtime `IA_SpellCast` (LMB / Q / RT). Casts write no log line. Slots 1–3 not checked. | spells |
| 6 | Hit and kill an NPC with a spell | Reaction, ragdoll, no crash (the 11:53 KickRagdoll path) | PASS (verified by NPC unify, 16:35) | `Saved/NpcUnified/run9_S_spell_kill_ragdoll.png` | A spawned Soldier left at 5 health died to a real Fire Bolt and ragdolled to the floor with no crash. Three NPCs in the new looks were also killed and ragdolled. I checked the screenshot (body on the floor at the impact) and the editor log (no fatal or assert). **Don't enable the sword strike clips in any test**: they crashed the editor at 16:16 and are off in the saved assets. | NPC unify |
| 7 | Crowd and squads | Pedestrians walk and react; squads march | PASS (crowd) | `r1-03-spawn-mannequin-visible.png` | Pedestrians walk, and Lives names 42 people at start. Squads not checked yet. Story markers (Spot_BellSquare, Home_*) are auto-placed because the map has none. | crowd / squads / NPC lives |
| 8 | Talk to a quest giver (hold T) | Dialogue appears, quest starts | PASS, with issues | `r1-08-talk-odette.png` | E (not T) talks to Odette Vane: "Clean line, good finish. Nothing else matters." / Goodbye. The world pauses during the talk. The quest log shows `Quest main: Accepted` and `StepStarted intro` twice at Play; after the skip it moves to `lantern_row`. Quests confirmed the double start (PIE's new-game reset started `main` again). A fix is staged for the next train: quests start on the first tick after game flow reports IsPlaying(). | dialogue / quests |
| 9 | Spell crafting (K) | Crafting screen opens, a crafted spell casts | RECHECK after train #8 | – | `Crafting.Cast` printed `Crafting.Cast: ` with no reason. Cause (from spell crafting): no crafted slot was active, because slots start inactive until you pick one with 5–8 or D-pad Up, so a bare `Crafting.Cast` has nothing to cast. Fixed for train #8: every refusal now gives a reason in the log and on the crafting hint. Next run: `Crafting.Cast 0`, then open the K screen. | spell crafting |
| 10 | World jump | Jump to Pewterside or Frostside and back | BLOCKED (wrong map) | – | On Lvl_HeroSampleCrowd no actor has a `ReflectionsWorldJumpComponent`, so `IA_WorldJumpUp` does nothing. **By design** (world jump's reply): the jump component is only attached when the map has `Reflections World Anchor`s, and this single-side sample map has none. The playthrough map is `/Game/MockCity/Lvl_MockCity` (three sides, Weigh-House / Gilt Tower / Frost Tower, pages, key, shards). Test world jump now on `/Game/Worlds/Test/Lvl_WorldJumpTest`; run 2 moves to Lvl_MockCity once world jump says it's ready (after train #8). | orchestrator + game flow (start map) |
| 11 | Pages and towers | Collect the mirror pages: the Gilt Tower, the Frost Tower, Pewterside's high spot | BLOCKED | – | Needs step 10. | world jump |
| 12 | Tarnish and lives | The meter rises with tarnished NPCs; lives and checkpoints work | PARTIAL | `r1-08-talk-odette.png` | The meter shows `TARNISH 0/20` and `GameFlow.Dump` says infection=0/20 and that a Start checkpoint is saved. Rising Tarnish and death/respawn not checked yet (`GameFlow.Infect`, `GameFlow.Kill`). | game flow / NPC lives |
| 13 | Finale | The villain manifests, the possession fight works | NOT TESTED | – | Handed to the villain session's own run (it had the next PIE slot). The log says "possession off (Villain.Start to run it here)", so the finale doesn't start on its own on this map. | villain |
| 14 | Ending | Ending and credits; quit works | PASS (screen only) | – | `GameFlow.Victory` gives screen=Victory, gameover=1, victory=1. It was reached by console, not by beating the villain. Credits and Quit buttons not clicked (UI capture doesn't include menus). | game flow |
| 15 | Pause menu | Esc pauses; resume and quit work | PASS | – | `GameFlow.Pause`: screen=Pause, game paused, mouse freed. `GameFlow.Resume`: unpaused, mouse captured again. Esc itself not pressed. | game flow |

## Playthrough: world-jump test levels (`/Game/Worlds/Test`, editor only)

| # | Step | Expected | Run 1 | Screenshot | Blocker / repro | Owner |
|---|---|---|---|---|---|---|
| W1 | Open each test level and Play | Spawns, world-jump anchors work | NEXT RUN | | Start with `/Game/Worlds/Test/Lvl_WorldJumpTest` (it has anchors), until Lvl_MockCity is ready. | world jump |

## Runs

(Each run gets a dated section here: the build train, PIE lock slot, results, and the top 5 blockers.)

### Run 3: Sat 14 Nov, build #10 (editor restarted 18:52), Lvl_MockCity via New Game (queue row 5)

Run A, the full route: PIE 19:05:50 to 19:08:40. Run B, the finale re-run via Continue: 19:09:40 to 19:11:09. Driver: [`playthrough_mock.py`](playthrough_mock.py); step data in [`run3/report.json`](run3/report.json); shots `shots/r3-*.png` (the run-A finale shots are `*-run1.png`).

**How it was played.** Keys and actions went through InputToolset: Enter/Down on the title, E to talk, LMB Fire Bolt, Z/X held 0.45 s to step, F for the Final Spell, 1 for Healing.
- Walking was real move input (`/Game/Input/IA_Move`), steered along a navmesh path. When a leg stalled or had no path, the hero was teleported the rest of the way, and that leg is marked **TP** below.
- `LS_Melee_Kimodo` was open in Sequencer. That's harmless here, because New Game travels away from the start map, but it should be closed (owner of `/Game/Combat/Melee`).

| Step | Result | Evidence / notes | Owner |
|---|---|---|---|
| Title → New Game (Down, Enter) | PASS | Title screen with a checkpoint; New Game opened `Lvl_MockCity` from config (no cvar). `r3-01-title.png` | game flow |
| Intro → skip → control | PASS | The intro played (IntroInPIE 1) and the skip button ended it. Camera 89 cm up and 196 cm back; move input live. `r3-02-intro.png` | cutscenes |
| Giltside start, HUD | PASS | Spawned at the Lamplight PlayerStart in Giltside. The HUD shows health, mana, shards per side, pages 0/3, magic and the step prompts, Tarnish 0/20 and the quest tracker. The city kit facades and lamps stand upright, and NPCs wear finished looks. `r3-03-giltside-start.png` | world jump / HUD |
| Talk to Ilse (E) | PASS | E within 1.7 m opened her card. Four lines (Ilse / Wren) played, then the quest moved to "Cast a spell". From 6 m there's no prompt, as designed. `r3-04-talk-ilse.png` | quests / dialogue |
| Cast a spell | PASS | A Fire Bolt advanced the quest to "Find the burning eyes". | spells / quests |
| Spell-kill a spawned Guard | **FAIL** | `Npc.Spawn Guard 1 400` gave `BP_Look_GiltBridgeGuard_C_1` (with a shield). Eight Fire Bolts point-blank, and it never went down; it hit the hero from 100 down to 40, then 16. `r3-05-guard-spell-kill.png`. Sparks show at the hero's hand, so bolts may be hitting the shield or spawning inside it. | npc-unify / spells |
| Hero health regen | FAIL? | Health stayed at 16 from game time 160 s to 264 s, with no regeneration or pickups. Only the Healing spell restores it. Check this is intended. | game flow / spells |
| Ring crowd | **FAIL** (walking) | 12 `Crowd_LaneWalker`s spawned 15–51 m away, but **0 were moving** in three samples. Later, 2 of 12 were about 1.5 km away (other sides). | crowd-react |
| Burning eyes (Bell Square) | **FAIL** | A host existed (`BP_Look_GiltGlassman_C_0`) and 8 NPCs were tarnished. Walking toward Bell Square got about 100 m in 22 s (good), then the TP failed about 40 m short (the spot was likely blocked). The step never completed. | quests / villain |
| Bell Lane Pewterside shards | PASS | Two picked up. The first leg stalled after about 10 m (STUCK, TP); the second leg walked. | world jump |
| Step down to Pewterside (hold Z) | PASS | Side changed RED → GRAY, magic 100 → 24, 1 shard spent, checkpoint "World jump". `r3-07-pewterside.png` | world jump |
| Weigh-House roof, page 1 | PASS with TP | Page 1 and the Giltside shard were picked up, with checkpoint "Page" and the FirstPage cutscene. **No nav path up the stair** (partial path; it ends at the foot, 12 m short), so the climb was TP. A human should check that the stair can actually be climbed. `r3-08-weighhouse-roof.png` | world jump |
| Step up on the roof (hold X) | PASS | Side changed GRAY → RED and the hero landed on the Giltside roof at the same height. | world jump |
| Down from the Giltside roof → Lantern Gate | TP | **No nav path from the Giltside corner roof** (0 points). It walked about 9 m, then stuck. A player who steps up there may be stranded. | world jump |
| Gilt Tower key | PASS | `GiltTowerKey` picked up at the Watch post (163950, 3700). `r3-09-lantern-gate-key.png` | world jump |
| Gate → Gilt Tower door | TP | No nav path (0 points) from the key spot. Straight-line steering got stuck after 34 m. | world jump |
| Door opens with the key | PASS | The door opened on overlap and the GiltTower cutscene played. `r3-10-gilt-tower-cutscene.png` | world jump / cutscenes |
| Page 2 + Frostside shard (inside) | PASS | Both walked to, with checkpoint "Page". `r3-11-inside-gilt-tower.png` | world jump |
| Step up inside the tower → Frost Tower | PASS | The hero landed inside the sealed Frost Tower. `r3-12-frost-tower-inside.png` | world jump |
| Page 3 → book whole | PASS | Book complete, MirrorWhole cutscene, Final Spell given; the boss spawned DORMANT at the crown. `r3-13-mirror-whole.png` | world jump / villain |
| Ramps to the crown | **PASS** (walked) | Nav path of 22 points, not partial; walked in 20 s with no TP, in both runs. The boss went DORMANT → FIGHTING on arrival. `r3-14-crown-boss.png` | world jump / villain |
| Final Spell (F) | PASS (input) | F casts, and each hit takes 125. `r3-15-final-spell.png` | villain |
| Beat the boss → Ending → Victory | **FAIL** | Run A: the hero arrived with 16 health and died after 1 hit (boss 1000 → 875). Run B: the hero arrived with 86 health (Continue gave 100), and 15 F presses landed 5 hits (boss → 375) before the hero died, about 15 s in. Standing still, with no dodging. The Final Spell is mana-bound (35 of 100, regen about 8/s), which makes about 8 hits a roughly 30 s fight; the boss kills a full-health hero in about 15 s. Victory was not reached. | villain |
| Death → respawn | PASS | "Respawned at the checkpoint" (page 3, inside the Frost Tower), both times. `r3-17-victory*.png` show the respawn. | game flow |
| Continue from the title | PASS, with a note | Enter on Continue restored page 3 with all pages, key and shards. **The Tarnish meter reset to 0/20** (it was 12/20). | game flow |
| Quest tracker vs progress | **FAIL** | The tracker stayed on "Find the burning eyes" through all 3 pages, the key, the door, the book and the boss. The quest only follows its own step order, so a player who doesn't trigger the burning-eyes beat gets no guidance for the rest of the game. | quests |
| Tarnish pacing | Watch | 3/20 at 1.3 game-min, 8 at 2.5, 10 at 2.7, then 12–13 from 3.7 min on. Possession runs from the start. | villain / game flow |

Also seen:
- The talk prompt shows a generated name, "E Speak with Gen Bc058f90" (owner: npc-lives / quests).
- Two talk hints show at once: "E Speak with …" and "Hold T or D-pad Down to talk · Enter to type" (owner: quests / dialogue).
- An editor `Ensure condition failed: !HasAnyFlags(RF_ClassDefaultObject)` in NavigationSystem.h:294 at 19:03:55, before my run.
- Viewport captures **now include the HUD (UMG)**.

**Top 5 after run 3**
1. **The finale can't be won standing still.** The boss kills a full-health hero in about 15 s, while 8 mana-bound Final Spell hits take about 30 s. Victory was not reached in two tries. Owner: villain `local_dd0eeffa`. Tune the boss (health, damage) or the Final Spell (mana, cooldown), or confirm a dodging player wins.
2. **The main quest stalls at "Find the burning eyes".** The tracker never moves past MQ02, though pages, door, book and boss all happen. The burning-eyes beat didn't fire near Bell Square, with a host present. Owner: quests `local_00d6efaf` (+ villain for the host beat). **Fix in the 19:30 merged build (quests):** the quest now catches up, skipping earlier steps once a later step's progress has happened. Burning eyes is a goTo of `Spot_BellSquare` with a 12 m radius, and I was about 40 m away; the host/conversion part is the villain's cutscene. **Recheck on the next mock city run.**
3. **Navmesh gaps on the win path:** no nav path up the Weigh-House stair, none down from the Giltside corner roof after stepping up, and none from the Lantern Gate key to the Gilt Tower door; Bell Lane walks stalled twice. Real movement may still manage the stair, so a human should check it. Owner: world jump `local_830b60d0`.
4. **Spell-kill on the mock city fails, and hero health never regenerates.** A shielded Gilt guard survived 8 point-blank Fire Bolts and took the hero to 16 health, which stayed there. Owners: npc-unify `local_c650e0ab` / spells `local_07d1c5bc` / game flow.
5. **Ring crowd walkers stand still** (0 of 12 moving) and some end up about 1.5 km away. Owner: crowd-react `local_3627acc6`.

Fixed since run 2 and verified: start map → mock city (no cvar), title → New Game, world jump, all 3 pages, key and door, book complete, Final Spell, the boss rising at the crown, death and respawn, and Continue.

### Run 2: Sat 14 Nov, after train #8, Lvl_HeroSampleCrowd (slot 10)

PIE 16:06:47 to 16:09:32 local, after the PIE-lock queue and about 90 s waiting on an editor slow task (world jump saving the mock city maps). No level sequence was open before Play. Cvars were set for the run, then reset to `GameFlow.TitleInPIE 0` and `Cutscene.IntroInPIE 0`.

| Check | Result | Evidence |
|---|---|---|
| Title in PIE (`GameFlow.TitleInPIE 1`) | PASS | `GameFlow.Dump`: screen=Title, playing=0. |
| Title → Continue | PASS | With a save, Enter lands on Continue: "Restored checkpoint (Start)". No intro, as designed. |
| Title → New Game (Down, Enter) | PASS | "Cutscene Intro started (48.0 s)", "New-game intro cutscene: playing"; Jory spawned through Lives. |
| Intro gate with `IntroInPIE 0` | PASS (fix landed) | "New-game intro cutscene: did not start" on plain Play. |
| Intro → skip → control and camera | PASS (fix landed) | "Cutscene Intro finished; control returned." Move and look input not ignored; camera 89 cm above the hero and 196 cm back (normal play camera, no floor camera). No `FRotator::Quaternion` NaN and no "did not contain any bindings" warnings. |
| Doubled subtitle | NOT VERIFIED | Viewport capture leaves out UMG. Needs a human look or a capture that includes UI. |
| Quest `main` starts once | FAIL (known) | `Accepted` / `StepStarted intro` still logged twice per start. Quests' fix is staged for a later train. |
| Fire Bolt cast | PASS | Mana 100 → 90 right after LMB, `casting=true`, regen to 96.6 within 1.5 s. |
| Kill an NPC with a spell (KickRagdoll path) | NOT VERIFIED | `Npc.Spawn Civilian 1 350` logged no warning, but no NPC was in front by cast time (NPCs flee from spell noise), and 0 of 15 NPCs went down. Every NPC near the spawn is a named Lives person whose state goes into the Lives snapshot save, so I didn't target one blind. Cause (per NPC unify): civilians flee spell noise by design. Next: `Npc.Spawn Guard 1 400` and five Fire Bolts (see "How to drive PIE"). NPC unify is also running this exact check (a real Fire Bolt kill on a soldier) in its queue slot on train #8. |

Gotcha: `unreal.SystemLibrary.execute_console_command(None, ...)` from Python runs in the **editor** world, not PIE. Use the `RunConsoleCommand` tool for PIE commands such as `Cutscene.Skip`.

**Top 5 after run 2**
1. Start map → `Lvl_MockCity`, waiting on world jump's confirmation. Owners: orchestrator + game flow.
2. Finale only reachable by console. Owner: villain, train #9.
3. ~~Killing an NPC with a spell~~: **verified** by NPC unify at 16:35 (Soldier, one Fire Bolt, ragdoll, no crash; screenshot checked). Its replacement here is any new break found in the next run.
4. World jump, pages and towers have never been played in PIE (no anchors on the sample map). The next slot goes to `GameFlow.NewGameMap /Game/Worlds/Test/Lvl_WorldJumpTest`, or the mock city once confirmed. Owner: world jump.
5. Quest `main` starts twice (fix staged). Owner: quests.

Fixed since run 1 and verified: the intro gate, the camera after the intro, the binding warnings, and the title flow in PIE.

Also seen in NPC unify's 16:35 screenshot: the hero without the mannequin, Health and Mana bars on the HUD, the quest tracker ("The Mirror Made Whole: Find Ilse Varrow on Lantern Row, 5 m away"), and spawned NPCs in crowd-looks' finished looks (since 16:36:59).

### Run 1: Sat 14 Nov, after train #7, Lvl_HeroSampleCrowd

Four batches in PIE: 15:13 to 15:24 (batches 1 to 3) and 15:29:39 to 15:30:39 (batch 4). Input went in through the editor's InputToolset, and state was read with [`pie_probe.py`](pie_probe.py): pawn location, speed, mana, paused, move-input-ignored, world jump. Run it through `PythonScriptingTools.execute_python` with `exec(open(<path>).read())`, then return `r`.
Batch 3 ran past my 4-minute lock, and npc-lives waited for it; I stopped at 15:24. Later runs renew the lock before each batch.

**Top 5 "can't play past here" blockers**

1. **The start map should be `Lvl_MockCity`** (step 10). Lvl_HeroSampleCrowd is a single-side sample with no world anchors, so world jump, pages and towers can't happen there, by design. New Game, `GameDefaultMap` and packaging's `-map` / `MapsToCook` all still point at the sample. Owners: orchestrator `local_6f701af5` + game flow `local_0b912c4f` (`GameFlow.NewGameMap /Game/MockCity/Lvl_MockCity` from train #8). Packaging follows once they confirm.
2. ~~Mannequin visible through the hero~~ (step 3). **Editor-only, not a ship bug.** It was the Quinn spawnable from a take sequence left open in Sequencer, which PIE copies in at the hero's spawn point. Owner: cutscenes `local_4511e14c` (close the sequence after generating takes). The playtest now checks for an open sequence before Play.
3. **Intro cutscene control** (step 2). It plays with `Cutscene.IntroInPIE 0`, the subtitle shows twice and stays after the skip, the Sequence has no 'Hero' / 'Jory' / 'Goldie' bindings, and with IntroInPIE 1 the camera ends at floor level (one NaN). Owner: cutscenes `local_4511e14c`. All five causes are found and fixed in source; recheck after the next train.
4. **Finale isn't reachable in play.** Possession is off unless `Villain.Start` is run, and Victory was only reached by console. Owner: villain `local_dd0eeffa` / game flow `local_0b912c4f`.
5. **Killing an NPC with a spell is still unverified** (step 6), and it's the old KickRagdoll crash path. Next run first. Owner: NPC unify `local_c650e0ab` / spells.

(Dropped from the list: the silent crafted-cast refusal. It was a test-method issue, since no crafted slot was selected, and the missing reason is fixed for train #8.)

Also seen: the quest log starts `main`/`intro` twice (quests). The missing title menu in PIE turned out to be by design (step 1).
Works: moving, casting Fire Bolt with mana drain and regen, the Tarnish meter display, talking to Odette, pause and resume, the Victory screen, and the crowd with 42 named Lives people.

**How to drive PIE from a session (learned this run)**

- Cast with the key `LeftMouseButton` or `Q`, not `IA_Shoot`. The spell inputs are built at runtime, so InputToolset can't target them by asset path.
- **NPC spell-kill test (safe target, from NPC unify):**
  - Use `Npc.Spawn Guard 1 400`: 60 health, so five Fire Bolts (14 each). It doesn't flee from spell noise; it walks over and fights back, so it stays in front. Expect a ragdoll on the fifth bolt.
  - Other options: `Npc.Spawn Soldier 1 400` (70 health; it runs below 25%) or `Npc.Spawn Enemy 1 600` (100 health, hostile).
  - Spawned Guards, Soldiers and Enemies are unnamed throwaways, so Lives never touches them and a kill leaves nothing in the Lives snapshot.
  - Don't use a Civilian: they flee from spell noise and roam.
  - From train #9: `Npc.Weaken [Health=5]` leaves the nearest unnamed NPC in front with that much health and holds it still for 15 s, so one bolt does it.
- Crafted spells: slots start unselected. Use `Crafting.Cast <0-3>` (it selects and casts) or `Crafting.Slot <n>` first; in play, 5–8 or D-pad Up.
- Move with `/Game/Input/IA_Move.IA_Move` (y=1 is forward). World jump uses `/Game/Worlds/Input/IA_WorldJumpUp.IA_WorldJumpUp`.
- **Before Play:** make sure no level sequence is open in Sequencer (`unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()` should be `None`). An open sequence's spawnables get copied into PIE; that's how a Quinn mannequin ended up inside the hero in run 1. Don't close another session's sequence yourself; ask its owner.
- Full flow from the title: set `GameFlow.TitleInPIE 1` (and `Cutscene.IntroInPIE 1` for the intro) before Play. Without them, PIE starts mid-run. See `ArtDirection/GameFlow/README.md`.
- Menus: `GameFlow.Pause`, `GameFlow.Resume`, `GameFlow.Key <Key>` (sends a key through Slate, so it reaches UMG menus and dialogue), and `GameFlow.Dump` (logs the state).
- `CaptureGameViewport` now includes the HUD (it didn't in run 1). Menus can still be checked with `GameFlow.Dump`.
- Walk with `/Game/Input/IA_Move.IA_Move` (5 m/s). `/Game/Input/Actions/IA_Move` doesn't move the hero. `Quest.Ui` / `DescribeUi()` prints the tracker, prompt and talk card.
- While no tool call is running, PIE ticks at about 3 fps (the editor is in the background). Measure over game time, not wall time.

## Known from packaged-build testing (Sat morning)

- With no input, the hero's health drained from 100 to about 40 in under a minute (Tarnish or NPC damage?). Check whether that's intended. Owner: game flow / NPC unify.
- `RaycastSingle resulted in a NaN/INF in PHit!` and `ConvertQueryImpactHit() received NaN/Inf for normal`, twice while idle. Owner: NPC / crowd movement code.
- Killing an NPC with a spell has not been verified since the 12:04 KickRagdoll fix. Owner: NPC unify / spells.
