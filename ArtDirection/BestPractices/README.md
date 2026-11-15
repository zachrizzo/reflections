# Unreal best-practice audit (UE 5.9)

Read-only audit of `Source/reflections/**`, `Config/*.ini`, `reflections.uproject`, the `*.Target.cs` and `Build.cs` files, and a sample of `/Content`. Done 2026-11-14 at 14:40–14:55 local, before the 15:06 build train. Nothing was edited except this file.

Severity:

- **CRASH**: crash or data-loss risk.
- **BLOCKER**: blocks the jam ship.
- **SALE**: should be fixed before the game is sold.
- **NICE**: nice to have.

Effort:

- **S**: under 15 minutes.
- **M**: under 1 hour.
- **L**: over 1 hour.

Performance is not covered here. The perf-stability session (`local_0825a76a-d9d4-469f-bdc4-00f459f768b9`) owns tick cost, crowd cost and frame budget. Where this doc notes a tick, it is about the pattern, not the cost.

## Headline

The C++ is in better shape than a 19-session sprint usually produces.

- **No GC or crash defects were found.** Every `UObject`/`AActor`/component member in the module is a `UPROPERTY TObjectPtr` or a `TWeakObjectPtr`. Every timer lambda uses `CreateWeakLambda`/`CreateUObject`, and every Slate lambda that outlives its widget captures a weak pointer. All world subsystems limit themselves to Game/PIE worlds with `DoesSupportWorldType`, there's no `FTSTicker`/`AsyncTask`, and there's no static `UObject` state (the static caches hold weak pointers).
- **Every by-name call resolves today.** The 32 named by-name targets were checked against the headers at 14:44, and each `ProcessEvent` call checks the parameter size first. Not checked: the world-jump mana names that come from `DA_WorldJumpConfig`, and the cutscene NPC getter.
- **The ship risks are content and cooking, not code.** Two assets that C++ loads by path don't exist, so a packaged build silently uses fallbacks (J1, J2).
- **The engineering debt is architectural.**
  - Systems in the *same module* call each other through reflection (section 2).
  - About 130 hard-coded `/Game/...` string paths and 18 always-cook folders stand in for an Asset Manager setup (section 3).
  - There are islands of legacy `BindKey` input (section 4).
  - The game UI is raw Slate (section 5).

---

## Fix before the jam submission (small, safe, high value)

| # | Sev | Where | Owner | Problem | Fix | Effort |
|---|---|---|---|---|---|---|
| J1 | BLOCKER | `Lives/ReflectionsPeopleBook.cpp:15,243-246`; `Config/DefaultGame.ini` | npc-lives (asset), packaging (ini) | The editor reads `ArtDirection/Story/people.json` (`#if WITH_EDITOR`). A packaged build reads only `/Game/Lives/DA_PeopleBook`, but **`Content/Lives` does not exist** and `/Game/Lives` isn't always-cooked. The shipped game silently falls back to the "built-in stub" people book. | 1. npc-lives imports the JSON into `/Game/Lives/DA_PeopleBook` and saves it, outside a cook save-freeze. 2. Packaging adds `+DirectoriesToAlwaysCook=(Path="/Game/Lives")`. 3. Check the packaged log for `People book: N named people ... from /Game/Lives/...`, not `built-in stub`. **Status 14:58:** the owner agreed. `UReflectionsPeopleBookAsset` is new in train #7, so the asset can only be made after that train, with `Tools/Lives/import_people_book.py`. The cook line is with packaging. | S |
| J2 | BLOCKER (verify) | `Cinematics/ReflectionsCutsceneSubsystem.cpp:65,305`; callers `Villain/ReflectionsVillainSubsystem.cpp:1004,1073`, `Quests/ReflectionsQuestWorldSubsystem.cpp:1672,1868`, `GameFlow/ReflectionsGameFlowWorldSubsystem.cpp:579` | cutscenes | Cutscenes load `/Game/Cinematics/Data/DA_Cutscene_<Name>`, but **only `Content/Cinematics/Sequences` exists**, with no `Data` folder. In a packaged build `PlayCutscene` returns false for NewGame intro, FirstPage, GiltTower, MirrorWhole and Ending. Every caller carries on safely: when `PlayCutscene` returns false, the villain calls `ShowVictoryNow()` at once (`:1073-1086`), and the 75 s timer is only a backstop for a cutscene that never finishes. | Author and save the `DA_Cutscene_*` assets (the folder is already always-cooked). **Status 14:58:** the owner planned this. `UReflectionsCutsceneAsset` lands in train #7, and right after it `Tools/Cinematics/build_cutscene.py` builds all six, which the owner then checks in PIE. Still to verify: `Cutscene.Play <Name>` in a packaged Development build. | M |
| J3 | BLOCKER (verify) | `Quests/ReflectionsQuestSubsystem.cpp:141,178-188` | quest-system | `/Game/Quests/DA_QuestPack_Story` doesn't exist (no `Content/Quests`), so only the C++ built-in quests run. That may be intended. | Confirm. If the story pack should ship, save it now. `/Game/Quests` is already always-cooked. **Status:** the owner confirmed the pack should ship. `UReflectionsQuestPack` loads with train #7, and right after it `Tools/Quests/import_story.py` builds `/Game/Quests/DA_QuestPack_Story` from `ArtDirection/Story/quests.json` and `people.json`. Until then the built-in quests run, which is harmless. | S |
| J4 | BLOCKER (hygiene) | `Config/DefaultEngine.ini:121-133` (`[/Script/AndroidFileServerEditor.AndroidFileServerRuntimeSettings]`, `SecurityToken=`) | packaging config | The engine's AndroidFileServer plugin is enabled by default. Its editor module writes a fresh `SecurityToken` into `DefaultEngine.ini` whenever the section is missing or empty, which is why it "keeps reappearing". `git log -S SecurityToken` finds no commit, so it's not in history yet. | **Permanent fix:** add `{ "Name": "AndroidFileServer", "Enabled": false }` to `reflections.uproject` (the game is Win64-only) and delete the whole section from `DefaultEngine.ini`. The plugin then never loads and can't regenerate the token. **Belt and braces:** a `pre-commit` hook that rejects staged lines matching `SecurityToken=.` in `Config/`. The editor must restart, which happens at the train anyway. | S |
| J5 | SALE (hitch) | `SpellCrafting/ReflectionsSpellCraftingComponent.cpp:229-239`, called from `:224`, `:273` and `ReflectionsSpellCraftingScreen.cpp:294` | spell-crafting | `UGameplayStatics::SaveGameToSlot` runs **synchronously on the game thread on every crafted-slot change** (each key press). | Replace it with `UGameplayStatics::AsyncSaveGameToSlot`. Game flow already does this at `GameFlow/ReflectionsGameFlowSubsystem.cpp:315`. | S |
| J6 | SALE (latent dangling) | `Hero/ReflectionsSampleSpellDriver.h:25-31` (held in `TOptional<FReflectionsExternalCast> ActiveExternal`, `:223`); `SpellCrafting/ReflectionsSpellCraftingComponent.h:86-90` (`FGesture PendingGesture`, `:135`) | spell-combat; spell-crafting | Plain, unreflected structs hold a raw `UAnimSequenceBase*` across frames. It's safe only while some other `UPROPERTY` keeps the anim alive. | Change the field to `TWeakObjectPtr<UAnimSequenceBase>` and null-check it at use. It's not a `UPROPERTY`, so there's no asset-serialization risk. | S |
| J7 | (rule) | All by-name targets (section 2) | everyone | Renaming or re-signing one of the by-name targets compiles cleanly, then quietly no-ops at runtime. | **Name freeze until submission:** don't rename or change the parameters of any function in the section 2 table. Optional, S per owner: make each by-name helper log a one-time `Warning` when the class or function isn't found, instead of silently returning false. | S |

J5 and J6 are optional for the jam but cost minutes. Everything else waits until after submission.

**Status, checked in the working tree before the 15:06 train:**

- **J5 is done.** `SaveSlots` uses `AsyncSaveGameToSlot`, with one write in flight and one coalesced follow-up (`ReflectionsSpellCraftingComponent.cpp:243-263`).
  - Edge case for later: the synchronous flush in `EndPlay` (`:199-200`) can race a write that is still in flight. If the async write finishes last, it overwrites the newer data. That's teardown only, so it's harmless for the jam. A later fix is to flush only when `!bSaveInFlight`, or to wait for the write.
  - The new failure log uses `LogTemp`.
- **J6 is done** in both places.
  - Crafting: `ReflectionsSpellCraftingComponent.h:88`, with null checks at `.cpp:558,586,596`.
  - Spells: `ReflectionsSampleSpellDriver.h:27`, with a null check at `.cpp:432`. A collected clip falls back to the AimProxy's own clip.
- **J1 cook line is done:** `DefaultGame.ini:40`. The asset itself is made after train #7.
- **J4 is not applied yet** (14:53). The AndroidFileServer section and its token are still at `DefaultEngine.ini:121-133`, and the `.uproject` has no AndroidFileServer entry. The orchestrator has been warned to strip the section before any commit that stages `DefaultEngine.ini`.

---

## Crash and data-loss pass (18:35–19:05, before train #12 at about 20:30)

Second read-only pass. It covered Lives, Quests, Cinematics, the Crowd ring and chat, NPC, Squads, GameFlow, `Voice/` and `Tools/RealtimeVoice`. Six parallel reviewers read the code, and I re-checked every item below in the working tree at 18:40–19:00. Line numbers move: several of these files were saved during the pass.

**Headline.** The pose-path crash is still reachable through squads. Squads play single clips on the visible MetaHuman body, the same state as the 16:16 crash, and the new start patrol puts a marching squad next to the player start. Two packaged-build breaks follow it: New Game opens a map that isn't cooked, and the new weapon props aren't cooked. After that comes a group of New Game bugs that carry the last run into the new one. There's no GC or threading defect.

### Must fix before train #12

| ID | Severity | Where | Owner | Defect and trigger | Fix | Effort |
|---|---|---|---|---|---|---|
| X1 | CRASH | `Squads/ReflectionsSquad.cpp:1038` (march, `Squads.MarchClip` defaults to 1 at `:40`), `:1539,1678,1684,1692` (caster clips), `:744-751` (death drops `SavedAnimClass`) | soldier-squads | Squads call `Body->PlayAnimation` on the visible MetaHuman body, which puts it in single-clip mode, and later swap the AnimBP back. A soldier killed while marching or mid-cast ragdolls in single-clip mode. That is exactly the 16:16 state, and npc-unify hard-disabled the same thing at `NPC/ReflectionsNpcCombatComponent.cpp:142-147`. The 12:16 crash log has `Squad ... Marching -> Engaged` 1.7 s before the `SkinnedAsset.cpp:471` assert on `SKM_MHC_IvenRook_BodyMesh`. Start patrol (on by default) makes this the first fight a judge has. | Default `Squads.MarchClip` to 0. Play the wand channel/flick on the hidden walker through `UReflectionsNpcReactionComponent::PlayOnWalker` with `AS_Melee_Wand_Channel_Walker` / `AS_Melee_Wand_Flick_Walker` (both exist in the always-cooked `/Game/Combat/Melee`), or skip the body clips. | S |
| X2 | CRASH | `Squads/ReflectionsSquad.cpp:1183-1189` → `:1055`; `IsActive` at `:67` checks squad state only | soldier-squads | A one-hit kill on a marching soldier runs `OnOwnerDied` → ragdoll → spell event → `EngageInternal` in the same call stack. The dead soldier still counts as active, so `UpdateMarchAnimation(Member,false)` calls `SetAnimInstanceClass` on a body that just started simulating. | X1 removes it. Also add `if (!ReflectionsSquadNpc::IsAlive(Member.Actor)) { Member.bMarchClipActive = false; Member.SavedAnimClass = nullptr; return; }` at the top of `UpdateMarchAnimation`. | S |
| X3 | PACKAGED-BREAK | `Config/DefaultGame.ini:82` (`NewGameMap=/Game/MockCity/Lvl_MockCity`), `GameFlow/ReflectionsGameFlowSubsystem.cpp:582-593` (`OpenMap`) | packaging (ini, bat); game-flow-ui (guard) | `Lvl_MockCity` is not in `MapsToCook` or the bat's `-map=`, `/Game/MockCity` isn't always-cooked, and no cooked asset references the persistent map. `DA_WorldJumpConfig` names only the three `_Frostside/_Giltside/_Pewterside` sublevels. In a package, Start/New Game fails to load the map and the engine drops back to the default map. | Add `+MapsToCook=(FilePath="/Game/MockCity/Lvl_MockCity")` and add the map to the bat's `-map=`. In `OpenMap`, if `!FPackageName::DoesPackageExist`, log an error and open `CurrentMapPath()` instead. | S |
| X4 | PACKAGED-BREAK | `Squads/ReflectionsSquad.cpp:107-108`; `NPC/ReflectionsNpcArchetype.cpp:164,167` (gated by `DoesPackageExist`) | packaging, or npc-unify (DA) | `SM_Frostside_MirrorSword` and `SM_Pewterside_ReaderWand` live in `/Game/LanthorneAssets/...`. Only C++ string paths name them. They aren't cooked, so packaged soldiers and NPCs are unarmed. | Add both meshes to `Config/DefaultEditor.ini` `[AlwaysCookMaps]`, like the WhiteLook BPs. Or set `WeaponProp` on the DAs (X6). | S |
| X5 | DATA (new run inherits the old one) | Lives: `ForgetEverything` (`Lives/ReflectionsLivesMemory.cpp:85`) has no callers. `StartNewGame` (`GameFlow/ReflectionsGameFlowSubsystem.cpp:620`) only clears the checkpoint. Quests: `Quests/ReflectionsQuestWorldSubsystem.cpp:901` overwrites the `bHadCheckpoint` captured at `:155`, so the reset at `:908` never fires. | game-flow-ui (Lives call); quest-system (`:901`) | Play → return to title (or lose/win → title) → New Game. The new run keeps the old run's dead and tarnished people, story flags, opinions, quests, items and unlocks. After a win the main quest stays Completed. The new run's "Start" checkpoint then writes all of it into `Reflections_Lives`, `Reflections_Quests` and the autosave. | game-flow-ui: in `StartNewGame`, after `ClearCheckpoint()`, add `if (auto* Mem = GetGameInstance()->GetSubsystem<UReflectionsLivesMemory>()) Mem->ForgetEverything();` (same module, direct call). quest-system: delete the `bHadCheckpoint = ...` assignment at `:901`. | S |
| X6 | DATA (features off) | `Content/NPC/Archetypes/DA_Npc_*.uasset` (saved 18:40); `NPC/ReflectionsNpcSubsystem.cpp` `FindArchetype` prefers the DA over the built-in | npc-unify | The DA assets don't contain the new fields (`bCastsAtPlayer`, `WalkerAttackAnimations`, `WalkerCastAnimation`, `WeaponProp`). That leaves tarnished casting, walker strikes and weapon props off in PIE and in the package. | Reset To Built In on each DA from the current build, check the Looks arrays survived, and save outside a cook freeze. The soft refs then also pull the props and walker clips into the cook (covers X4). | S |
| X7 | SECRET / billing | `Tools/RealtimeVoice/api_keys.py:40-44` | npc-dialogue | `load_keys` prefers `GEMINI_API_KEY` from the environment and `~/.gemini/api_key` over the shipped `keys.json`. `CreateProc` passes the game's environment through, so a judge who has their own key set gets billed. | When frozen or when `--keys` is given, read only the keys file. | S |
| X8 | SECRET (repo) | root `.gitignore`; `Content/NpcDialogue/` (untracked, not ignored; `git check-ignore` returns nothing) | npc-dialogue | `PackageJamBuild.bat:35` and `Build-NpcDialogueHelper.ps1` say a `keys.json` may sit in `Content/NpcDialogue/Relay`. A `git add -A` would commit it along with the ~29 MB exe. | Add `/Content/NpcDialogue/Relay/` and `**/keys*.json` to the root `.gitignore`. | S |
| X9 | PACKAGED-BREAK (stale content) | `Content/Lives/DA_PeopleBook.uasset` (15:10) vs `ArtDirection/Story/people.json` (18:46) | npc-lives (re-import); packaging (gate) | A package reads only the DA, so judges get the 15:10 cast and schedules. | Run `Tools/Lives/import_people_book.py` and save before every package. The bat should fail if the DA is older than the JSON. | S |

### Should fix before train #12 if there is time

| ID | Severity | Where | Owner | Defect | Fix | Effort |
|---|---|---|---|---|---|---|
| Y1 | CRASH (medium) | `NPC/ReflectionsNpcReactionComponent.cpp:1292` (`if (!IsIncapacitated()) RepairBodyPose();`), `:1053-1056` (topple sets `bPauseAnims`) | npc-unify | The pose repair stops as soon as the NPC is dead. A body that lost its buffers just before death (first-tick `SetAnimInstanceClass` at `:1162`, a second loss inside the 0.25 s throttle, the 20-repair cap) is refused ragdoll and toppled while still animating, which can reach the same assert. | In `OnOwnerDied`, before choosing ragdoll or topple: if `!BodyPoseReady(Body) && !Body->IsRunningParallelEvaluation() && !Body->LeaderPoseComponent.IsValid()`, call `Body->ReregisterComponent()`. Run the repair for any non-simulating body, dead or alive. Reset the repair count when the pose is good. | S |
| Y2 | DATA | `GameFlow/ReflectionsGameFlowWorldSubsystem.cpp:986-991` (Start/NewGame); `LoadFromSlot` (`Checkpoint = Loaded; WriteSave();`) | game-flow-ui | From the title, New Game (and loading an older slot) overwrites the autosave with no confirm. | Route both through the existing Confirm screen when `HasAnySave()`. | S |
| Y3 | HITCH / memory | `Quests/ReflectionsQuestWorldSubsystem.cpp:1488-1492` (`SpawnPerson`) | quest-system | To pick one look by sex, it `LoadSynchronous`es all 20 `TeamLooks()` MetaHuman BPs. It runs for every absent quest person (from `EnsurePeople` every 2 s, and on quest accept). | Pick by the soft path's asset name and load only the chosen one, or pass `nullptr` and let `SpawnNpc` choose. | S |
| Y4 | CRASH (exit) | `Cinematics/ReflectionsCutsceneSubsystem.cpp:293-298` → Cleanup `NotifyQuests` + `OnCutsceneFinished.Broadcast` | cutscenes | Alt-F4 or travel during a cutscene runs gameplay cleanup on a dying world: quest step completion, villain `AnnounceFinale` (adds a widget) or `ShowVictoryNow`. | In `Deinitialize`, tear down silently: no `NotifyQuests`, no broadcast. | S |
| Y5 | pose-path check | `Cinematics/ReflectionsCutsceneSubsystem.cpp:1264` (`Best->PlayAnimation`), `:1428-1431` (AnimBP restore). Correction: I first wrote that all 6 `DA_Cutscene_*` contain a `bFullBody` take. That came from a name-table hit, not a true value. The owner reports that none of the 15 current takes is full-body, and only the conversion fallback was. | cutscenes | Full-body takes switch the matched mesh to single-clip mode and swap the AnimBP back afterwards. If that mesh is a crowd MetaHuman body, this is the X1 pattern. | For actors with a `UReflectionsNpcReactionComponent`, play full-body takes on the walker (`PlayOnWalker`) rather than the body. At minimum, run all six once and grep the log for `GetBoneMatrix`/empty-pose warnings. | S–M |
| Y6 | SOFT HANG / late audio | `Voice/ReflectionsRealtimeVoiceComponent.cpp:793-797,1159-1171`; `Tools/RealtimeVoice/pipeline.py` (no per-turn deadline) | npc-dialogue | An NPC destroyed mid-reply leaves `bAwaitingReply` stuck (blocks the next NPC). A reply arriving after the 15 s bark timeout cuts the bark and plays the old reply. | Treat `!IsValid(OutputAudio)` as drained. Drop `reply.start` for a turn that already timed out. Wrap each relay turn in `asyncio.timeout(12)`. | M |
| Y7 | PACKAGED (silent) | `relay.py` `serve()` bind failure (uncaught `OSError`); shared `Saved/NpcDialogue/relay.token` deleted by a second instance (`ReflectionsNpcRelayHost.cpp:60-61,84-87`) | npc-dialogue | A taken port or a second game instance silently turns AI dialogue off, with no log line. | Catch and log `OSError`, try 8765–8775, use a per-PID token, and log once when the helper process has died. | S |
| Y8 | PRIVACY | `relay.py:78` (`log_text=True`), `:649-650,742-746`; `ReflectionsRealtimeVoiceComponent.cpp:702-704` | npc-dialogue | Player speech transcripts go to a never-rotated `relay.log` and to the game log (and crash reports) in Development. | Log no text when frozen, use a `RotatingFileHandler`, and make the `UE_LOG` Verbose without the text. | S |
| Y9 | PACKAGED-BREAK (secret staging) | `ArtDirection/Packaging/PackageJamBuild.bat:50-52` (`robocopy ... /XF keys.json *.env *.key`) | packaging | The exclusion matches exact names only, so `keys.json.txt` or `keys - Copy.json` would be staged into the build. | Copy an allowlist (`NpcDialogueRelay.exe`, `_internal\`, `roster.json`, `seed\`, `keys.json.example`) and scan the staged folder for key-shaped strings. | S |

**Status (checked in the working tree):**

- **19:03, X5 Quests part done.**
  - The new-game check now runs before the first start (`Quests/ReflectionsQuestWorldSubsystem.cpp:896-920`), so the first tick can't start the old run's quests before the reset.
  - Still open: a New Game that opens a different map starts that world with the checkpoint already clear. quest-system asked game-flow-ui to also call `ResetAll()` from `StartNewGame`, next to the Lives `ForgetEverything` call.
- **19:03, Y3 done.** `SpawnPerson` walks `TeamLooks()` from the person's hash and stops loading at the first look of the right sex (`:1489-1496`).
- **Cleared:** the 18:35 quest file-time jump was quest-system's own `Copy-Item`, not a foreign re-copy.
- **19:06, Y4 done.** `Deinitialize` sets `bSilentTeardown` around `Cleanup(false)` (`Cinematics/ReflectionsCutsceneSubsystem.cpp:300-302`). The quest notify and the broadcast are skipped (`:1603`).
- **19:06, Y5 done.** NPC roles go through `PlayOnWalker` first (`:1252`). Failing that, a crowd body gets only a slot montage. If no slot fits, the take is logged and skipped. A crowd body is never single-noded or ABP-swapped (`:1264-1278`). Single-node plus restore remains only for the hero and for meshes without an AnimBP (faces).
- **19:06, Cutscene after-jam items done early.** `Elapsed` keeps advancing while the sequence holds its last frame (`:566`). The restore transform targets the driver it was captured from.

### After the jam (latent)

- **`Version` is never written to disk** in `UReflectionsGameFlowSave`, `UReflectionsLivesSave`, `UReflectionsQuestSave` or `UReflectionsSpellCraftingSave`. Delta serialization skips a property equal to its default, so a future `CurrentVersion = 2` reads every old file as version 2.
  - Fix: default `Version = 0`, then set `Save->Version = CurrentVersion` before each save.
  - game-flow-ui should do this now, in the new save system.
- **Game flow saves:** the async autosave isn't waited on at quit, and `.sav` files are written in place. For the new save system, save synchronously on quit and travel, and keep a `.bak` or write via temp-then-rename.
- **Cutscene with `Length` longer than its sequence:** `bPauseAtEnd` freezes `Elapsed`, so the cutscene never ends (`Cinematics/ReflectionsCutsceneSubsystem.cpp:1137,560-563`). All six current assets match their sequence lengths. Restore transform is captured from `DriverOf` (`:1074`) but applied to `RootOf` (`:1492`).
- **Lives:**
  - Ambient ring walkers can create permanent `AutoMarker_Home_gen_*` story markers through `FindStoryMarker` → `PlaceFallback` (`Lives/ReflectionsLivesSubsystem.cpp:1397`).
  - A walker that got a deed (any player spell within 8 m) is kept forever (`:742-746`).
  - Fix: skip marker resolution for `bAmbient` lives, drop their `Places` entry on forget, and cap the retained ambient lives.
- **Lives, `Embody`:** a level-placed townsperson killed in an earlier run is hidden but stays enrolled with its brain running.
- **NPC:**
  - `CastGlow`/`CastLight`/`HitFlash` are not released when an NPC is released mid-cast (cutscene stand-ins).
  - `HasPose` reads false during parallel evaluation, so some deaths topple instead of ragdolling.
  - Rule for the coming element reactions and heat: never touch the body's animation mode, auto-destroy or pool per-hit Niagara, and clear statuses in `OnOwnerDied`/`EndPlay`.
- **Squads:** `SpawnSquad` loops forever if `MarchSpeed <= 0` (`Squads/ReflectionsSquad.cpp:498`; `ClampMin` is editor-only). Start patrol loads 5 looks synchronously 1.5 s into every play.
- **Voice:**
  - Random bark pick on an emptied array (`Voice/ReflectionsRealtimeVoiceComponent.cpp:932-933`; current cues de-duplicate, so it's latent).
  - TTS chunks over 200,000 bytes are dropped without a log line.
  - Bookkeeping `os.replace` failures fail the whole turn.
  - The hosted-relay Dockerfile and .dockerignore disagree.
- **Villain (not reviewed in this pass):** looked at only one spot. `AReflectionsVillainTestHost` sets its mesh and AnimBP once in `BeginPlay` (`Villain/ReflectionsVillainPossession.cpp:870-877`) and ragdolls on death (`:918-921`). It's a test mannequin host with no mid-life swap, so it's not the X1 pattern. `VillainLook` runs the villain body in single-clip mode for its whole life (`ReflectionsVillainLook.cpp:98`) and never ragdolls it.

### Checked and clean

- **Lifetime:** every Slate widget holds weak owners. Timers, WebSocket and save callbacks are weak lambdas. Delegates are removed in `Deinitialize`/`EndPlay`.
- **Threading:** the mic thread touches only atomics and an MPSC queue.
- **Null and bounds:** no `check`/`verify`/`FindChecked` on data in any reviewed folder. Every array index is guarded.
- **Save slots:** six distinct slot names, all with cast-checked loads.
- **Voice robustness:** the relay accepts loopback only, needs the token, and has timeouts on every upstream call. A missing relay never blocks the game thread.
- **Crowd:** the ring and chat are bounded.
- **Keys:** no key-shaped value in any tracked or bundled file.

### Not a code defect, but the biggest data-loss risk

None of the work in these folders is in git:

- **Source:** `Source/reflections/{Lives, Quests, Squads, Cinematics, GameFlow, Villain}`, most of `Crowd`, and the new `Voice` files.
- **Content:** `Content/{Quests, Lives, NPC, Squads, MockCity, NpcDialogue}`.
- **Docs:** `ArtDirection/Story`.

Tracked voice code already includes untracked headers, so a clean clone doesn't build.

A `git clean`, a disk fault or a bad copy would lose the day. Quest file times moved backwards at 18:35–18:38, so something re-copied that folder.

When the orchestrator commits, exclude the `DefaultEngine.ini` AndroidFileServer section (J4) and `Content/NpcDialogue/Relay/`.

---

## 1. C++ correctness and GC safety (after the jam unless marked)

What's already right (keep it):

- `TWeakObjectPtr` containers of actors with `IsValid`/`Get()` checks.
- `CreateWeakLambda` for timers.
- Weak or `Pin()` captures in Slate.
- `DoesSupportWorldType` limited to Game/PIE.
- Versioned `USaveGame` classes written on checkpoint events.
- Shipping-guarded debug draw.

| Sev | Where | Owner | Problem | Fix | Effort |
|---|---|---|---|---|---|
| SALE | `Crowd/ReflectionsCrowdCitySubsystem.cpp:67-68` | crowd-react | `static const UScriptStruct* = FindObject<...>("/Script/MetaHumanCrowd...")` caches a `nullptr` for the rest of the process if the first call is early. | Hold it in a member and look it up again while it's null. | S |
| SALE | `Hero/ReflectionsSpellAim.cpp:133-141,171` | spell-combat | `EndPlay` doesn't remove the camera modifier added with `AddNewCameraModifier`, so a re-added component stacks modifiers. | Call `PlayerCameraManager->RemoveCameraModifier(...)` in `EndPlay`. | S |
| SALE | `Hero/ReflectionsSpellAim.cpp:268-281` | spell-combat | Each cast iterates every `APawn` and does a trace per candidate, so the cost scales with the crowd. | Use `UReflectionsNpcSubsystem::GetNpcActors()` (already used just below) or an overlap sphere. | M |
| NICE | `Lives/ReflectionsLivesSubsystem.cpp:200-207` | npc-lives | `Deinitialize` doesn't remove `OnNpcSpellHit/Died/Infection`/`OnSpellEvent` (bound at `:256-262`), and the debug input component (`:268-274`) is never popped. | Add `RemoveDynamic` and `PopInputComponent`. | S |
| NICE | `Villain/ReflectionsVillainSubsystem.cpp:182-200`; `:155,1013,1070,1077` | villain | `Deinitialize` misses several `RemoveDynamic`s. One-shot timer handles are locals, so a finale restart or loss can't cancel them. | Store the handles as members and clear them in `Deinitialize` and `StopFinale`. | S |
| NICE | `Worlds/ReflectionsWorldJumpSubsystem.cpp:173-183` | world-jump | The repeating `AttachTimer` isn't cleared in `Deinitialize`. | Call `ClearTimer(AttachTimer)`. | S |
| NICE | `NPC/ReflectionsReputationSubsystem.h:27` | npc-unify | `TMap<TWeakObjectPtr<AActor>, float>` is never pruned. | Prune stale keys in `AdjustReputation`. | S |
| NICE | `Lives/ReflectionsLivesSubsystem.cpp:1558-1584` | npc-lives | The by-name call builds a zeroed `TArray<AActor*>` param in a raw buffer and never calls `DestroyValue`, leaking a small allocation per call. | Use `DestroyValue_InContainer` after `ProcessEvent`, or call directly (section 2). | S |
| NICE | `Crowd/ReflectionsCrowdTelemetry.cpp:11-52` | crowd-react | Per-frame CSV capture compiles into shipping. | Wrap it in `#if !UE_BUILD_SHIPPING`. | S |
| NICE | `SpellCrafting/ReflectionsCraftedSpellSubsystem.cpp:555` | spell-crafting | Attached Niagara uses `ENCPoolMethod::None`. The other 5 spawns use `AutoRelease`. | Use `AutoRelease`. | S |
| NICE | 34 `LogTemp` uses. Squads 11, SpellCrafting 6, NPC 5, GameFlowLibrary 3, Crowd 3, others 1 each | squads, crafting, npc-unify, game-flow, crowd | No filtering or verbosity control. | Add one `DECLARE_LOG_CATEGORY_EXTERN(LogReflections<System>, Log, All)` per system in a shared header, then replace. | S |

**Tick that should be an event** (pattern only; perf-stability owns the cost):

- `GameFlow/ReflectionsGameFlowWorldSubsystem.cpp:188-215` polls `EnsureController` every frame.
- `Quests/ReflectionsQuestWorldSubsystem.cpp:856-870` polls `EnsureController`, `BindGame` and `HasCheckpoint` every frame.
- `Lives/ReflectionsLivesSubsystem.cpp:325-350` polls `EnsureInput` and `BindEvents` every frame.
- Fix: bind once in `OnWorldBeginPlay` or `FGameModeEvents::GameModePostLoginEvent`, or use a 0.25 s timer until the controller is found. Add an `OnCheckpointCleared` delegate on game flow.
- Effort: S–M each.

**Synchronous `LoadObject` on gameplay events** causes first-use hitches:

- `Squads/ReflectionsSquad.cpp:114` (BeginPlay, per squad), `:1064,1068` (per bark).
- `NPC/ReflectionsNpcSubsystem.cpp:447,485`.
- `Quests/ReflectionsQuestWorldSubsystem.cpp:707,2050-2065`.
- `Villain/ReflectionsVillainBoss.cpp:49,989`.
- Fix: see section 3. Until then, preload in `OnWorldBeginPlay` into a `UPROPERTY` cache.

## 2. Cross-session coupling by reflection

**Key point:** every one of these classes is in the **same module, `reflections`**. The "no header dependency" reason only held while sessions compiled apart. Now that the classes have landed in a train, a direct `#include` plus `GetWorld()->GetSubsystem<UReflectionsX>()` is free. Typed calls let the compiler catch renames. Today a rename compiles cleanly and the feature quietly does nothing. Use a `UINTERFACE` only where the caller shouldn't know the concrete type. Those cases are marked **I** below.

Verified at 14:44: all targets exist as `UFUNCTION`s or dynamic delegates on the expected class, and the `ProcessEvent` sites check `ParmsSize`/`NumParms` before calling.

| Caller file:line | Caller owner | Target (class::member) | Target owner | After-jam replacement |
|---|---|---|---|---|
| `Cinematics/ReflectionsCutsceneSubsystem.cpp:209-246` | cutscenes | `ReflectionsLivesSubsystem::SpawnPerson` | npc-lives | Direct call |
| `Cinematics/ReflectionsCutsceneSubsystem.cpp:641-703` | cutscenes | `ReflectionsVillainSubsystem::BeginConversion` | villain | Direct call |
| `Cinematics/ReflectionsCutsceneSubsystem.cpp:1567-1590` | cutscenes | `ReflectionsQuestSubsystem::NotifyEvent` | quest-system | Direct call, or a game-wide `OnStoryEvent(FGameplayTag)` delegate |
| `Cinematics/ReflectionsCutsceneSubsystem.cpp:136-152,699,1074,1491` | cutscenes | `NpcReactionComponent::SetExternallySteered` (found by class *name* at `:111-127`) | npc-unify | **I** `IReflectionsSteerable` |
| `Cinematics/ReflectionsCutsceneSubsystem.cpp:159-177` | cutscenes | Getter on NPC, by name | npc-unify | Direct call |
| `Cinematics/ReflectionsCutsceneSubsystem.cpp:864-869` | cutscenes | Actor property read by name (`FindPropertyByName`) | various | Interface getter |
| `GameFlow/ReflectionsGameFlowWorldSubsystem.cpp:51-123` (helpers), `:221` | game-flow-ui | `SpellCraftingComponent::IsCraftingScreenOpen` | spell-crafting | Direct call, or a "UI open" stack in game flow |
| `GameFlow/ReflectionsGameFlowWorldSubsystem.cpp:238,301,807` | game-flow-ui | `QuestSubsystem::OpenJournal`, `IsJournalOpen` | quest-system | Direct call |
| `GameFlow/ReflectionsGameFlowWorldSubsystem.cpp:309,579` | game-flow-ui | `CutsceneSubsystem::IsCutscenePlaying`, `PlayNewGameIntro` | cutscenes | Direct call |
| `GameFlow/ReflectionsGameFlowWorldSubsystem.cpp:953` | game-flow-ui | `SpellAim::IsAiming` | spell-combat | Direct call |
| `GameFlow/ReflectionsGameFlowWorldSubsystem.cpp:958,1171,1299,1312,1322` | game-flow-ui | `SampleSpellDriver::IsDefeated`, `SetRespawnTransform` | spell-combat | **I** `IReflectionsPlayerVitals` |
| `NPC/ReflectionsNpcSubsystem.cpp:797-803` | npc-unify | `GameFlowSubsystem::ReportInfected/ReportCured` | game-flow-ui | Game flow binds `UReflectionsNpcSubsystem::OnNpcInfection` (it already exists) |
| `NPC/ReflectionsNpcSubsystem.cpp:857-873` | npc-unify | `VillainSubsystem::BeginConversion` | villain | Direct call |
| `Villain/ReflectionsVillainSubsystem.cpp:831-860` | villain | `NpcSubsystem::HoldNpc` | npc-unify | Direct call |
| `Villain/ReflectionsVillainSubsystem.cpp:167,1239-1242` (`BindByName`) | villain | `CutsceneSubsystem::OnCutsceneFinished`; `GameFlowSubsystem::OnGameLost` | cutscenes; game-flow-ui | `AddDynamic` on the typed delegate |
| `Villain/ReflectionsVillainSubsystem.cpp:1004,1073,1133,1170-1223` | villain | `CutsceneSubsystem::PlayCutscene`, `IsCutscenePlaying` | cutscenes | Direct call |
| `Villain/ReflectionsVillainSubsystem.cpp:473,481,1095,1342-1381` | villain | `GameFlowSubsystem::ReportInfected/ReportCured/ShowVictory` | game-flow-ui | Direct call. Infection could route through `NpcSubsystem::SetInfection` per `npc-unified.md`. |
| `Villain/ReflectionsVillainConversion.cpp:87-91` | villain | `NpcReactionComponent::EndScriptedHold` | npc-unify | Direct call |
| `Lives/ReflectionsLivesSubsystem.cpp:548-567` | npc-lives | `StoryMarkerSubsystem::Find` | quest-system | Direct call |
| `Lives/ReflectionsLivesSubsystem.cpp:46,1556-1584,1615,1625-1642` (CVar `Lives.ChatDirector` holds a class path) | npc-lives | `CrowdChatSubsystem::PlayConversationBetween`, `IsInConversation`, `StopConversation` | crowd-react | **I** `IReflectionsChatDirector`. Drop the CVar class path. |
| `Lives/ReflectionsLivesSubsystem.cpp:68-70`; `Crowd/ReflectionsCrowdStrollSubsystem.cpp:39-41` | npc-lives; crowd-react | GASP driver `CharacterInputState` struct written by property name | (GASP BP) | Expose a `BlueprintImplementableEvent`/interface on the driver BP, or a C++ base class for it |
| `Lives/ReflectionsLivesSubsystem.cpp:432-454,576-578` | npc-lives | Marker `Radius`, `bAutoPlaced`, name properties read by name | quest-system | Direct access to `AReflectionsStoryMarker` |
| `Quests/ReflectionsQuestSubsystem.cpp:75-111,593,615,848,965` | quest-system | `LivesSubsystem::CompleteQuestFor`, `IsQuestAvailable`, `SetStoryFlag` | npc-lives | Direct call |
| `Quests/ReflectionsQuestSubsystem.cpp:985-995` | quest-system | `SampleSpellDriver::RestoreMana`, tried on every component of the pawn | spell-combat | **I** `IReflectionsManaReceiver` |
| `Quests/ReflectionsQuestWorldSubsystem.cpp:51-65,347-348,1672,1868` | quest-system | `CutsceneSubsystem::PlayCutscene` | cutscenes | Direct call |
| `Quests/ReflectionsQuestWorldSubsystem.cpp:292-293` | quest-system | `VoiceInteractionSubsystem` existence check | npc-dialogue | `GetSubsystem<>() != nullptr` |
| `Voice/ReflectionsVoiceInteractionSubsystem.cpp:45-53,115` | npc-dialogue | `NpcReactionComponent::IsScripted` | npc-unify | Direct call |
| `Voice/ReflectionsRealtimeVoiceComponent.cpp:60-95,180-182` | npc-dialogue | `VoiceProfile`/`VoiceId` struct read by property name on the NPC | npc-unify / crowd-looks | Direct access to the archetype's voice profile |
| `Worlds/ReflectionsWorldJumpComponent.cpp:37-105,389-454` (names come from `DA_WorldJumpConfig` lists `SpendMagicNames` / `MagicGetterNames` / `MaxMagicGetterNames`) | world-jump | Spell driver mana getters and spender, plus a property read (`:418`) | spell-combat | **I** `IReflectionsManaSource` (`GetMana`, `GetMaxMana`, `SpendMana`). Delete the name lists from the data asset. |
| `Crowd/ReflectionsCrowdCitySubsystem.cpp:96-119,201-203` | crowd-react | Engine `UZoneGraphSettings::LaneProfiles` / `bBuildZoneGraphWhileEditing`, `DangerAnnotationTag` written by property name | (engine) | Acceptable: it pokes engine-private config. Keep it, but guard and log a `Warning` if the property is missing after an engine update. |

Suggested interfaces after the jam. They go in one header, `Source/reflections/Core/ReflectionsInterfaces.h`, which the orchestrator or one owner creates:

- `IReflectionsManaSource`
- `IReflectionsManaReceiver`
- `IReflectionsPlayerVitals`
- `IReflectionsSteerable`
- `IReflectionsChatDirector`

Everything else is a plain `#include` with a typed call. Total effort is **L**, about half a day across owners; do it on one branch after submission.

## 3. Asset references and cooking (after the jam)

- **Current state:**
  - About 130 `TEXT("/Game/...")` literals across 27 files. The largest are `Villain/ReflectionsVillainConfig.cpp` (31), `NPC/ReflectionsNpcSubsystem.cpp` (15), `SpellCrafting/ReflectionsSpellCraftingCommands.cpp` (11) and `Squads/ReflectionsSquad.cpp` (10).
  - About 80 `LoadObject`/`TryLoad`/`LoadSynchronous`/`ConstructorHelpers` sites.
  - **Zero** use of `FStreamableManager` or `UAssetManager`.
  - The cooker can't see string paths, so `DefaultGame.ini` always-cooks **18 whole folders**. `DefaultEditor.ini [AlwaysCookMaps]` lists 15 single packages, which is a hack: the section is meant for maps.
  - The result: everything in those folders ships, used or not, and a new path silently breaks the packaged build until someone adds it to the ini. This is the failure mode behind J1 and J2.
- **Good models already in the project:**
  - `UReflectionsWorldJumpConfig` (`Worlds/ReflectionsWorldJumpConfig.h`).
  - `UReflectionsVillainConfig` (`DA_VillainConfig`).
  - `UReflectionsNpcArchetype`.
  - Each is a DataAsset with `TObjectPtr`/soft fields.
- **Target pattern (per system, effort M each, L in total):**
  1. One `UPrimaryDataAsset` per system, for example `UReflectionsCutsceneLibrary`, `UReflectionsPeopleBookAsset` (it exists), `UReflectionsSquadConfig` and `UReflectionsSpellVfxConfig`. Use `TSoftObjectPtr<>`/`TSoftClassPtr<>` fields for anything big (meshes, MetaHuman BPs, Niagara, anim sets). Use hard `TObjectPtr<>` only for small, always-needed assets.
  2. Register the types in `DefaultGame.ini` under `[/Script/Engine.AssetManagerSettings]`, with `+PrimaryAssetTypesToScan=(PrimaryAssetType="ReflectionsConfig",AssetBaseClass=/Script/reflections.ReflectionsConfigBase,Directories=((Path="/Game/Data")),Rules=(CookRule=AlwaysCook))`. The cooker then follows the soft references and ships only what's referenced.
  3. Load with `UAssetManager::GetStreamableManager().RequestAsyncLoad(...)`, or `UAssetManager::Get().LoadPrimaryAsset(...)`, at `OnWorldBeginPlay`. That removes the first-use hitches in section 1.
  4. Delete the `DirectoriesToAlwaysCook` lines and `[AlwaysCookMaps]` entries one system at a time. Run *Audit Assets › Size Map* on the cooked build to confirm.
- **Also:**
  - `Config/DefaultEngine.ini:4` `GlobalDefaultGameMode` is still `/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode`. It's harmless while maps override it. Point it at the real game mode.
  - `Hero/ReflectionsHeroGameMode.cpp:10` hard-loads `/Game/ThirdPerson/...PlayerController` in the constructor. Use a `TSubclassOf` `UPROPERTY` set in a BP subclass or config.

## 4. Gameplay framework and input

- **Framework:**
  - Game state lives in subsystems: game-instance subsystems for game flow, quests and people memory, and world subsystems for the rest. `AGameState`/`APlayerState` are unused.
  - For a single-player game that's a legitimate, clean choice; keep it. Don't add multiplayer assumptions.
  - Do move HUD ownership off the world subsystems onto the `APlayerController`/`AHUD`, or a CommonUI layer (section 5), so local-player UI has one owner.
- **Saves:**
  - `USaveGame` is used everywhere, with a version field on Lives (good).
  - Game flow uses `AsyncSaveGameToSlot`. Quests (`Quests/ReflectionsQuestSubsystem.cpp:1496`) and Lives (`Lives/ReflectionsLivesMemory.cpp:66`) save synchronously, but only on checkpoint. That's fine for the jam; make them async before sale.
  - Crafting is J5.
  - There are four slots. Consider one `UReflectionsSaveGame` with per-system sub-structs, so a checkpoint is atomic across systems (SALE, M).
- **Enhanced Input (SALE, M–L):**
  - Contexts are added at these priorities: base 0 (`reflectionsPlayerController.cpp:48`), spells 1 (`Hero/ReflectionsSampleSpellDriver.cpp:353`), Final Spell 3 (`Villain/ReflectionsFinalSpell.cpp:110`), and world jump from `Config->MappingPriority` (`Worlds/ReflectionsWorldJumpComponent.cpp:277`). Write the priority table down in one place, for example the `Input` README.
  - Legacy `BindKey` islands with no gamepad path and no remapping:
    - `Hero/ReflectionsHeroCharacter.cpp:117-127`: sprint, walk, crouch, coat and spells 1–4. This only matters if `AReflectionsHeroCharacter` / `BP_HeroPlayer` ships.
    - `SpellCrafting/ReflectionsSpellCraftingComponent.cpp:322-351`.
    - `GameFlow/ReflectionsGameFlowWorldSubsystem.cpp:415-417` (pause).
    - `Hero/ReflectionsSpellHud.cpp:321-322`.
    - Fix: move them to `UInputAction` assets plus an IMC, bound with `UEnhancedInputComponent::BindAction`.
  - `Hero/ReflectionsSampleSpellDriver.cpp:371-382` polls 28 keys per tick with `IsInputKeyDown`/`GetInputAnalogKeyState` to detect the input device. `Hero/ReflectionsSpellAim.cpp:162` does the same for aim. Use one `IInputProcessor` (game flow already registers an `InputTracker`; share it) or `UCommonInputSubsystem::OnInputMethodChanged`.
  - Mark the actions *Player Mappable* (`UPlayerMappableKeySettings`) so a key-rebind screen and the controls screen (`GameFlow/ReflectionsGameFlowSlate.cpp:833-843`, which hard-codes key names) read the real bindings.
- **Gameplay Tags (SALE, M):**
  - About 90 `ActorHasTag`/`Tags.Add` sites use FName actor tags (`NPC_Reactive`, `Friendly`, `NPC_Type_<Id>`, `Flesh` and others). The heaviest are `NPC/ReflectionsNpcSubsystem.cpp` (25), `Quests/ReflectionsQuestWorldSubsystem.cpp` (12) and `NPC/ReflectionsNpcReactionComponent.cpp` (10).
  - There are zero `FGameplayTag`s in project code, and `GameplayTags` isn't in `Build.cs`.
  - Fix: a native tag header with `UE_DECLARE_GAMEPLAY_TAG_EXTERN`/`UE_DEFINE_GAMEPLAY_TAG`, under `Reflections.NPC.*`, `Reflections.Disposition.*` and so on, plus an `FGameplayTagContainer` on the NPC component or archetype.
  - `Friendly` currently means both "heal me" and "civilian" (`crowd-findings.md`). Split it into two tags as part of this.
- **StateTree and Mass:** Variant_Combat uses StateTree properly. The Mass crowd is set up, but Lvl_HeroSampleCrowd runs no Mass entities (`crowd-findings.md`), and the 6 walkers are actor BPs with hidden GASP drivers. Perf-stability and crowd own the decision.
- **Niagara:** every spawn is `bAutoDestroy`, and 5 of 6 use `AutoRelease` pooling (good; see the NICE row in section 1).
- **MetaHuman LOD and groom for crowds:** not audited here. That's owned by crowd-looks and perf-stability.

## 5. UI: raw Slate vs UMG/CommonUI

- **Today:**
  - The game flow (title, pause, controls, Tarnish meter), the quest HUD, talk and journal, cutscene overlay, voice overlay and crafting screen are hand-built Slate. They are added with `UGameViewportClient::AddViewportWidgetContent` at z-orders 40–1000.
  - Lifetime handling is correct: each is removed in `Deinitialize`, and the lambdas are weak.
  - The cost: styling lives in C++, so designers can't touch it. Gamepad focus and navigation are hand-rolled per screen. The z-order contracts are implicit. `CommonUI.*` CVars are set in `DefaultGame.ini:59-62`, but CommonUI isn't a dependency and isn't used.
- **Before the jam:** change nothing. It works, and rewriting UI on the last day is the riskiest thing on this list.
- **After the jam (SALE, L, about 2–3 days):**
  1. Enable CommonUI and add `CommonUI`/`CommonInput` to `Build.cs`.
  2. Build one `UCommonActivatableWidgetStack` layer set (Game, GameMenu, Menu, Modal) owned by the player controller.
  3. Port the pause and title menus first, since they gain the most from gamepad focus.
  4. Keep C++ `UCommonActivatableWidget` base classes with `BindWidget`, and put layout and style in WBP_ assets with a `UCommonUIStyle` set.
  5. HUD elements such as the meter and quest tracker can stay as UMG `UUserWidget`s.

## 6. Text and localization

- **Good:**
  - `GameFlow`, `Quests`, `Villain`, `Worlds`, `Cinematics` and `Voice` overlays use `LOCTEXT`/`NSLOCTEXT`. That's about 300 entries.
  - Game flow reads a String Table, `/Game/UI/ST_GameFlowText`, through `GameFlow/ReflectionsGameFlowText.cpp`.
- **Gaps (SALE, M–L):**
  - The player-facing HUD and crafting text is `FText::FromString(FString::Printf(...))`: `Hero/ReflectionsSpellHud.cpp:210-290` (HEALTH, MANA, OPPONENT) and `SpellCrafting/ReflectionsSpellCraftingScreen.cpp:71-456`.
  - Spell names are `const TCHAR*` in `Hero/ReflectionsSpellCatalog.h:11` and are uppercased with `FString::ToUpper`, which isn't locale-safe.
  - Fix: `LOCTEXT` plus `FText::Format` with named arguments, catalog names as `FText`, and `FText::ToUpper`.
  - Player-authored spell names stay `FText::AsCultureInvariant`.
- **Process:**
  - Pick one approach per system. Either use String Tables for anything designers edit, or `LOCTEXT` for code-only strings; both gather fine.
  - Add a Localization Dashboard target that gathers from `Source/` and `/Game`, and run one gather to prove nothing player-facing is missing.

## 7. Project hygiene

- **Redirectors:** none. Asset Registry query for `ObjectRedirector` under `/Game` returned 0 at 14:44.
- **Naming:**
  - Project-owned folders follow the prefixes (`BP_`, `NS_`, `DA_`, `ST_`, `SW_`, `SCue_`, `IA_`, `IMC_`, `MI_`, `M_`, `Lvl_`). Audio uses `ATT_` and `SCON_`, the common style-guide prefixes.
  - MetaHuman-generated names (`SKM_MHC_*`, `Hair_*`) come from the tool; leave them.
  - Small conventions to adopt: `Lvl_` vs the style guide's `L_` (keep `Lvl_`, just be consistent), and the `Content/Characters/Hero/Sample` sandbox-era folder.
- **Bloat (after the jam, before sale):**
  - `Content/Characters` is about 7.9 GB on disk.
  - `AdvancedLocomotionV4` (34 MB), `Characters/Paragon`, `Echo` and `UE4_Mannequin` are guarded by `DirectoriesToNeverCook`, but they still sit in the repo and LFS.
  - Delete the folders that nothing cooked references, after a *Reference Viewer* check. Also delete the `Developers`/`Collections` folders, the template `ThirdPerson`/`Variant_*` content if unused, and the `ThirdPersonCPP` references in `Config/DefaultEditor.ini:1-2,35-36`.
  - A cooked-size check stays with packaging.
- **`Config` vs `Saved/Config`:**
  - `Config/DefaultEditorPerProjectUserSettings.ini` is a per-user file checked into `Config/`. Move it out, or confirm it only holds team-wide defaults.
  - `[ContentBrowser] SelectedPaths` in `DefaultEditor.ini` is per-user state; remove it.
- **Plugins:**
  - Runtime plugins are enabled for every target: `Kimodo`, `AnimGen`, `AnimGenOffline`, `PCGBiomeSample`, `MetaHumanGenerator`, `MetaHumanCharacterUAF` and others.
  - Any that are authoring-only should get `"TargetAllowList": ["Editor"]`, as was done for NNEDenoiser. It cuts package size and startup. Packaging owns this (SALE, S each, verify with a cook).
- **Secrets:**
  - J4 covers the token.
  - The NPC voice relay is done right: `RelayUrl` and `ClientKey` are empty in `DefaultGame.ini:70-72`, the per-run token is generated by `Voice/ReflectionsNpcRelayHost.cpp:56` under `Saved/`, and no key is in source.
  - Keep it that way: any hosted `RelayUrl`/`ClientKey` goes in a non-committed `Saved/Config` override or an environment variable, never in `DefaultGame.ini`.
- **Build:**
  - `reflections.Target.cs` forces `bWithLiveCoding = true; bOverrideBuildEnvironment = true` to work around a machine-wide `BuildConfiguration.xml`.
  - Before sale, fix the machine config instead, and build Shipping with `bUseLoggingInShipping=false`.
  - The `Build.cs` `PublicIncludePaths` for all `Variant_*` folders is template boilerplate. Drop it with the unused variants.
  - `Build.cs` still carries the template comment "Uncomment if you are using Slate UI" while Slate is listed above it; tidy it.

## 8. Performance

Owned by perf-stability (`local_0825a76a-d9d4-469f-bdc4-00f459f768b9`). The patterns above that touch cost, which perf should decide on, are:

- 4 crowd `UTickableWorldSubsystem`s with no tick interval.
- Per-frame tick on every world pickup (`Worlds/ReflectionsWorldPickups.cpp:18,81-87`).
- The per-cast pawn iteration in SpellAim.
- The per-tick input-device polling in the spell driver.
- The first-use `LoadObject` hitches.
