# Game flow: title, pause, Tarnish meter, checkpoints, victory

Owner: the game-flow side session.
- **Code:** only in `Source/reflections/GameFlow/`.
- **Widgets:** Slate built in code.
- **Asset:** one, the String Table `/Game/UI/ST_GameFlowText`. It holds every player-facing name. Packaging always-cooks `/Game/UI`.

## Status update (2026-11-14, 18:50 local)

- **Save system (new, merged train #11/#12 at 19:30):**
  - What's in it: Save Game and Load Game screens, 3 manual slots plus a quick save and the autosave, F5 / F9, hold Start on the pad, a death screen, and Continue loading the newest save.
  - **Verified in PIE on the 19:32 build** (`test_save_system_pie.py`, 19:39, 21/21 checks in 19 s; `Screenshots/save_*.png`, `save_report.json`):
    - **Saving:** Save screen → Slot 1, saved with health at 70. The status reads "Saved to Slot 1", and the checkpoint becomes "Slot 1". F5 quick-saved 600 cm away, with 2 Tarnish.
    - **Loading:** the Load screen lists Quick save, Autosave and Slots 1-3. Slot 1 asked to confirm, then reloaded at Slot 1's spot with health 70 (not 100) and Tarnish 0, as saved.
    - **Death:** `GameFlow.Kill` showed the death screen with "Respawn at last save" as the default. Enter got the hero up at once through the driver's `RespawnNow`, at Slot 1's spot with full health.
    - **Quick load:** F9 put the hero back at the quick-save spot with health 70 and Tarnish 2 (the restore placeholders).
    - **Weak check:** Slot 1 was saved at the spawn point, so its position checks prove less than the quick-load one, which was 600 cm away.
  - **Fixed for train #13** (compiled 19:42):
    - The death screen's long date cut "Respawn at last save" off; its rows now show only the time and side.
    - The Load screen drew the newest slot as a primary button while focus was on the first; now only the first row is primary.
    - Tip cards stay up while the new narrator voice's longer lines play (Cast 8.4 s, Crafting 9.5 s, StepThrough 13.5 s).
  - **Not tried yet:**
    - The pad's hold-Start quick save.
    - X / Y in pause.
    - The title's Continue and Load Game.
    - The villain's possession restore and quests coming back with a real quest state (the test map has no quests or hosts).
    - Mouse clicks on the slot rows.
- **Settings Back fix (train #10):** verified in PIE at 18:42 (`test_credits_settings_pie.py`, 11/11). From a Custom quality mix, Back put every scalability group back exactly.
- **Credits:** the 9-line Gemini credits fit on the Credits and Victory screens even in a 1920×794 PIE window (`Screenshots/13`, `14`).
- **Map credits (21:24, for train #14):** the new key `Credits.Map` holds 5 lines for the map's licences: OpenStreetMap ODbL, Codriver 3D CC BY, artfletch CC BY, Minimaliano, Poly Haven / Cosmo Tree Gen / Noto Serif, and the notices file. They sit in BUILT ON, between Epic's line and "Made with Unreal Engine 5.9", which stays last. `Credits.Tools` is unchanged.
  - The table is saved (103 keys), and the C++ fallback has the same five lines. The train #13 DLL doesn't read the key yet, so in the editor the lines appear from train #14. A packaged build compiles them in from source.
  - **Layout checked in PIE** (`test_credits_map_pie.py`, 21:23): for that run only, the same seven BUILT ON lines were put in `Credits.Thanks`, then put back. Nothing is cut off (`Screenshots/15_credits_map.png`, `16_victory_credits_map.png`). The Victory panel used 87% of the screen height, and the standalone Credits panel 93%.
  - So the panels are wider for train #14 (both targets compile at 21:24): the Credits screen goes from 820 to 1040, and the Victory credits from 660 to 760 (the row stays under 1440, so it still fits 4:3). That leaves room for the team names.
  - If the Fab props turn out not to be CC BY, delete "· Street props by Minimaliano (Fab), CC BY 4.0" from line 3. That's a table edit only (and the fallback, for tidiness).

## Status (2026-11-14, 12:50 local, build train #5)

The whole loop runs in PIE in `Lvl_HeroSampleCrowd`, on both keyboard and gamepad:
- Path: title → controls → play → pause → death and respawn at the checkpoint → lose at the cap → try again → victory → title.
- Result: all 19 keyboard and gamepad checks pass in one 38-second run; screenshots are in `Screenshots/`.
- Train #5 fixes: the clipping is gone, and the narrator hooks and rule-neutral text are in.
- Mouse: automation can't drive it in PIE; see below.

## What the player gets

| Screen | How it opens | Buttons |
|---|---|---|
| Title | At launch (packaged and `-game` builds), after "Quit to title", and after victory | Continue (the newest save), Load Game, Start / New Game, Controls, Settings, Credits, Quit |
| Pause | Esc, P, or Start (on release; holding Start quick-saves) while playing | Resume, Save Game, Load Game, Journal, Controls, Settings, Restart from checkpoint, Quit to title. X / F5 quick-saves, Y / F9 quick-loads |
| Save Game | Pause > Save Game | Slot 1-3 (time, side, pages, or Empty), Back. Overwriting asks first |
| Load Game | Title, pause, death or lose screen > Load Game | Quick save, Autosave, Slot 1-3, Back. In play, loading asks first |
| Death | ~1.2 s after the hero falls | Respawn at last save / checkpoint (default), Load last save, Load Game, Quit to title. Y / F9 quick-loads |
| Controls | From the title or pause | Action, keyboard & mouse and controller columns; Back |
| Credits | From the title; also shown beside the victory text | Back |
| Confirm | Restart or Quit to title from pause | Restart / Quit to title, Cancel |
| Lose | The Tarnish count reaches the cap | Try again from checkpoint, Load Game (with a save), Quit to title |
| Victory | `ShowVictory()` (the villain session calls it) | Return to title, Quit game |

The title screen shows **REFLECTIONS** with the three side marks (Pewterside, Giltside, Frostside). Directly under the title it shows the jam-theme line (Director's Cut, rule 7(g)), in italic, for as long as the title is up. A short tagline follows.

Every menu pauses the game, shows the mouse cursor and puts focus on its first button.
- **Mouse:** hovering a button, or moving the mouse over it, gives it focus, so the mouse and the gamepad share one highlight. Clicking a button presses it.
- **Keyboard:** the arrow keys or Tab move, Enter or Space selects, Esc goes back. P or Esc also closes pause.
- **Gamepad:** the D-pad or the left stick moves, A selects, B goes back. Start also closes pause.
- **Held keys:** a held Start, B or Esc counts once; auto-repeat is ignored.
- **Focus:** it wraps top to bottom and never leaves the menu, so the gamepad can't wander into the spell HUD's buttons. If a click lands on empty space, focus returns to the last button on the next frame.
- **Prompts:** the footer and the tutorial tips switch between key names and button names, following the last device used.

Layers (all viewport content, the same layer `AddToViewport` uses):
- **Z 40, the meter layer:** above the spell HUD (20), crafting and world jump (30) and the villain HUD (35).
- **Z 1000, the menus:** above everything.
- **Tarnish meter, top right:** shows "TARNISH 7 / 20" with a bar that fades from green to red. It pulses when the count changes and warns from 75% of the cap. The world-jump panel is top left and the spell HUD bottom centre, so the meter doesn't cover them.
- **Toast under the meter:** "Checkpoint saved" or "Back at your last checkpoint".
- **Tip card under the meter:** one-time tutorial prompts.
- **Visibility:** the meter layer hides while the spell-crafting screen is open and during the title, lose and victory screens.

PIE note: so the title doesn't freeze other sessions' automated PIE tests, it shows in PIE only after `GameFlow.TitleInPIE 1`, or on demand with `GameFlow.Title`. Everything else runs in PIE. Esc stops PIE in the editor, so use P or Start there to pause.

## Loading screen, saves and quitting (11-15, menus-polish)

- **Loading screen:** a full-screen dark screen with the title, the theme line, a gold spinner and "Loading..." (`SReflectionsLoadingScreen`). Load, Continue, New Game, Restart, Try again and Quit to title used to open the map on the same frame as the click. The screen froze on the menu for the whole MedievalLondon load (7.2 s in PIE). Now `OpenMap` shows the screen and opens the map 3 frames later. The new map keeps the screen up until it is ready, holds it 0.6 s more, then fades it out in 0.35 s. It times out after 30 s.
  - **Packaged builds:** the movie player paints a copy while `LoadMap` blocks, so the spinner keeps turning. This needs the `MoviePlayer` module, added in `reflections.Build.cs`. The first load at launch shows it too.
  - **PIE:** the movie player is off in the editor, so the in-game copy stays on screen during the load (the spinner stops). Menus take no input while the screen is up.
- **Saves are async.** Every save file this code writes (the autosave and the quick and manual slots) is serialized on the game thread, a few KB, and written on one background pipe, in order. `FlushSaveWrites()` runs before a slot is read, before a map opens and before quitting. The slot list is cached: it is read once at startup, and each save or load updates its own entry. The title, pause and save menus never touch the disk.
  - Quests and Lives still write their own files synchronously in their `OnCheckpointSaved` handlers, which game flow then mirrors. They are under 13 KB.
- **"Saving..." indicator:** a small spinner and "Saving..." at the bottom right for about 1 s after each checkpoint, quick or manual save.
- **Quit:** Pause > **Quit to desktop** is new. It asks first, then quits without the title's map reload. Quit (title, victory, and Pause after the confirm) shows the screen, waits for the save writes, then quits. Packaged builds also mute the sound and hide the window, so the engine's teardown happens out of sight.

## Renaming things: the String Table

All names and story text are entries in `/Game/UI/ST_GameFlowText`.
- **To rename:** open the asset in the editor and edit the value. No rebuild is needed.
- **Fallback:** if the table or a key is missing, the built-in default (the same text) is used, so the menus never show a missing-string marker.
- **CSV mirror:** `ArtDirection/GameFlow/ST_GameFlowText.csv` mirrors the table. `make_string_table_csv.py` regenerates it from the C++ defaults, and `EditorToolset.StringTableToolset.ImportFile` imports it back, with `bReplaceExisting`.

| Key | Used for |
|---|---|
| `Game.Title`, `Game.Opening`, `Game.Summary` | Title screen (and the loading screen: title and the opening line). `Game.Opening` is the opening card (11-15 16:45): the Tarnish spreads through Lanthorne and fills people with dark magic. It is a new key on purpose: the old `Game.Theme` / `Game.Tagline` rows still in the asset (with the "three reflections" text) are no longer read. The title no longer shows the three side names. |
| `World.Gray`, `World.Red`, `World.White` | The three side marks (title, victory) |
| `Meter.Label`, `Meter.None`, `Meter.Some`, `Meter.Danger`, `Pause.Count` | Tarnish meter and the pause-screen count |
| `Lose.Title`, `Lose.Body` (`{0}` count, `{1}` cap), `Victory.Title`, `Victory.Body` | Lose and victory screens |
| `Tip.<Aim,Cast,Craft>.<Title,Keys,Pad>`, `Tip.Shard(.Title)`, `Tip.Step.<Title,Keys,Pad>` | Tutorial tips (`Keys` = keyboard wording, `Pad` = controller wording) |
| `Controls.StepUp`, `Controls.StepDown`, `Controls.Note` | Controls screen |
| `Title.Saved` | "Last checkpoint: ..." under the title buttons |
| `Credits.LeadRole`, `Credits.Lead` | The lead credit, first and largest: "CREATED BY" / "Jah Markabowi" |
| `Credits.Crew` | Anyone else, one per line under the lead (empty: not in the table) |
| `Credits.NoticesHead`, `Credits.Notices` | The small licence block at the end (multi-line, one notice per line) |
| `Settings.VoicePrivacy` | The privacy line on the Settings screen (voice chat sends speech to Google) |

**11-15 16:46 (menus-polish): one city, no stepping through here.** The game plays one map, MedievalLondon. Checked in the level data: no world anchors, no mirror shard or page pickups, and `DA_WorldJumpConfig` lists only the MockCity maps. So stepping through into another side is not possible on this map, and the text no longer promises it.
- The title has no side marks. The tagline reads "Wren Hale, the Silverer, is the only one who can burn the Tarnish out of Lanthorne." (`Game.Summary`).
- Save slots name the place, "Lanthorne", not a side (`Save.Place`). The Death and Save names use the same text.
- The lose and victory screens lost their side and reflection wording (`Lose.Body2`, `Victory.Body2`). The victory screen has no side marks.
- The Controls table no longer lists the step-up and step-down keys, and its note no longer mentions stepping (`Controls.Note2`). The Save note says "at every checkpoint" (`Save.LoadNote2`).
- The mirror shard tip uses `Tip.Shard2`. The coin and stepping-through tips (`GameFlow` tips) only fire when `UReflectionsWorldJumpWorldSubsystem::IsWorldJumpActive()`, which is false here, so they never show on this map. Their texts stay in code for a world-jump build.
- `Narrator_Tip_StepThrough` is not re-voiced: its tip can't fire on this map, so no audio plays for it. The old clip stays unused.

**11-15 16:20 (menus-polish): commercial credits.** The game reads as a normal commercial release: no jam or AI-made wording on the title, credits or loading screen. The credits moved to **new keys** on purpose. The old rows (`Game.JamLine`, `Credits.Game`, `Credits.Team`, `Credits.Tools`, `Credits.Thanks`, `Credits.Map`) still sit in the `.uasset` with the jam-era text, but no code reads them any more. They can be deleted from the asset at any time. The CSV no longer lists them.

The licence block keeps only what licences and terms ask for, from `ArtDirection/Submission/THIRD_PARTY_NOTICES.txt` (what ships with MedievalLondon):
- the Unreal Engine notice (Epic's EULA);
- OpenStreetMap's ODbL attribution;
- Kimodo's NVIDIA Open Model License line, "Powered by Tencent Hunyuan", and the ElevenLabs attribution;
- TripoSR (MIT), Poly Haven (CC0), and FreeType;
- one neutral line saying the character voices are synthesized, not human actors. OpenAI's usage policies require that disclosure for its TTS voices, and the in-game dialogue no longer shows one.

The Gray London map credits (Codriver, the Albert scan, Minimaliano, Cosmo Tree Gen, Noto Serif) are gone: they don't ship with MedievalLondon. Add a line to `Credits.Notices` if a new third-party asset ships.

- **11-14 18:25:** the table and `ST_GameFlowText.csv` hold the 9-line Gemini version, which names Google Gemini first in the voice line and adds the "Live NPC replies" line.
- The C++ fallback in `ReflectionsGameFlowSlate.cpp` (used only if the table fails to load) has the same 9 lines from train #11, so `make_string_table_csv.py` regenerates them.
- The CSV now has 98 keys, including the `Save.*` and `Death.*` text of the save system.

## Tarnish (infection) API, for NPC, enemy and villain code

`UReflectionsGameFlowSubsystem` is a game-instance subsystem, class path `/Script/reflections.ReflectionsGameFlowSubsystem`. Callers today:
- `UReflectionsNpcSubsystem`, by name: it reports NPCs that become tarnished, including the villain's hosts.
- The villain session, by name: `ShowVictory` after the Final Spell.

```cpp
#include "GameFlow/ReflectionsGameFlowLibrary.h"
UReflectionsGameFlowLibrary::ReportInfected(this, Npc);   // +1, once per actor
UReflectionsGameFlowLibrary::ReportCured(this, Npc);      // -1 if it was counted
UReflectionsGameFlowLibrary::ShowVictory(this);           // the Tarnish is burned out

// or the subsystem itself
if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this))
{
    Flow->ReportInfected(Npc);
    Flow->OnInfectionChanged.AddDynamic(this, &UMyThing::HandleInfection);  // (int32 Count, int32 Cap)
}
```

With no compile dependency, call it by name: find the subsystem on the game instance by that class path, then `FindFunction("ReportInfected")` and `ProcessEvent` with `{ AActor* Host; }`. `ShowVictory` takes no parameters. **These names and signatures are stable**: the NPC subsystem checks for exactly one `AActor*` parameter.

| Function | Meaning |
|---|---|
| `ReportInfected(AActor* Host)` | The count means "currently tarnished". It's deduped per actor, so calling twice for one host is safe. A null `Host` adds one anonymous infection. |
| `ReportCured(AActor* Host)` | -1 if `Host` was counted. A null `Host` removes one anonymous infection. It never goes below 0. |
| `GetInfectionCount()`, `GetInfectionCap()`, `GetInfectionFraction()`, `IsInfected(Host)` | Read the state. |
| `SetInfectionCap(int32)` | Set the cap for this run; 0 restores the default. |
| `OnInfectionChanged(Count, Cap)` | Fires on every change of the count or the cap. |
| `OnGameLost`, `OnVictory`, `IsGameOver()`, `IsVictory()` | Win and lose state. |
| `IsRunLive()` | True only while the player is actually playing: play has begun in this map, no game-flow menu is open, not game over. The villain's auto-start gates on it, because `GetScreen() == None` alone is also true for the first frame or two of every map load. |
| `ShowVictory()` | Pauses the game and shows the victory screen with the credits. |

- **Cap:** the default is **20**, from `DefaultInfectionCap`. Override it in `DefaultGame.ini` under `[/Script/reflections.ReflectionsGameFlowSubsystem]`, per run with `SetInfectionCap`, or from the console with `GameFlow.InfectionCap N`.
- **Reaching the cap** shows the lose screen and pauses the game.
- **Destroyed hosts** stay counted until `ReportCured`. The NPC subsystem cures on death. A host destroyed by a map change is dropped when the next map starts.
- **Restores keep the count** (from the 19:30 build; playtest run 3 found Continue reset it). Continue, Load, Try again and Restart put the meter back to the checkpoint's saved count at once, as placeholders. When the villain re-tarnishes its saved hosts (`OnCheckpointRestored`), each one replaces a placeholder, so the count neither drops nor doubles. Hosts it can't identify stay as placeholders. **New Game** resets the count to 0.

## Checkpoints

- **Auto-saved** on every step through (`OnWorldChanged`) and every mirror page (`OnPagesChanged`), two frames later so the hero has landed. A start checkpoint is also saved when play begins in a map. With SeparateMaps it waits for the arrival teleport. `SaveCheckpoint(Reason)` saves one by hand.
- **Contents:** the map, the side, the pawn location and yaw, the camera rotation, mirror shards per side, mirror pages, keys, and which level-placed pickups were taken.
- **Storage:** one save slot, `Reflections_Checkpoint` (user 0), written asynchronously. It also records which tips were seen.
- **Restore** (Try again, Restart, Continue):
  1. It reloads the checkpoint's map.
  2. It calls world jump's quiet `RestoreProgress(shards, pages, keys)`. That fires no pickup, page, book-complete or key events, so there are no pickup sounds and no second finale; world jump's `OnProgressRestored` resyncs its HUD.
  3. It sets the saved side (a broadcast, so the coat tint and music follow) and removes the level-placed pickups that were already taken.
  4. It teleports the hero with a camera cut and a cloth reset.

  The world-jump side confirmation in the first second after a restore doesn't autosave.
- **Death:** `UReflectionsSampleSpellDriver` owns defeat and respawn. After every save, game flow calls the driver's `SetRespawnTransform` so the hero respawns at the checkpoint. On every respawn at a same-map checkpoint, game flow also applies the saved camera rotation and a camera cut. If an older driver has no `SetRespawnTransform`, game flow moves the hero itself on the respawn frame.
- **Leaving a menu:** a map opened from a menu (Try again, Restart, Continue) gets GameOnly input back when play starts. `FInputModeUIOnly` sets IgnoreInput on the viewport client, and that setting outlives a map load.

## Saving and loading

The user's playtest asked for this: "There needs to be like saving game mode so I can save and then respawn."

**Slots** (`ReflectionsSaveSlots`, user 0):

| Slot | File | Written by |
|---|---|---|
| 0 Autosave | `Reflections_Checkpoint` | Every checkpoint (step through, mirror page, start of play), every save, and every load |
| 1 Quick save | `Reflections_QuickSave` | F5, holding Start (0.8 s), or X in the pause menu |
| 2-4 Slot 1-3 | `Reflections_Save_1..3` | Pause > Save Game |

**Behaviour:**
- **A save is also a checkpoint.** Saving runs the normal checkpoint path, so `OnCheckpointSaved` fires and every system stores its state. Then the checkpoint is copied into the slot. So "save, then respawn" works directly: if you fall, you get up where you saved.
- **What a save holds:**
  - Everything a checkpoint has: map, side, position and camera, shards per side, pages, keys, and the pickups already taken.
  - Hero health (`UReflectionsHealthComponent::Health`) and mana (the driver's `GetMagic`).
  - Reputation (`UReflectionsReputationSubsystem`, keyed by the pawn).
  - The Tarnish count and cap.
  - Other systems' data, in two forms:
    - Copies of the files quests and lives write on every checkpoint (`Reflections_Quests`, `Reflections_Lives`).
    - Data blobs any system stores with `SetSaveData`.
- **Loading a slot:**
  1. The loaded state becomes the checkpoint (and the autosave).
  2. The quest and lives files are written back.
  3. The Tarnish count clears and the slot's map reloads. On restore, the meter goes back to the saved count (placeholders, which the villain's re-tarnished hosts replace).
  4. The checkpoint is restored as for Try again.
  5. Saved health and mana are put back (only on a load: Try again, Restart and the death respawn give full health).
  6. Saved reputation is put back (on every restore).
  7. `OnCheckpointRestored` fires.
- **Continue** on the title loads the newest of all five slots.
- **New Game** clears the autosave only (and asks first when there is one). Manual and quick saves stay. It also makes Lives forget everything (`ForgetEverything`) and resets quests (`ResetAll`).
- **Newest** sorts on `UsedAt`: the time a state was last saved or loaded. Loading an older slot stamps it (`SavedAt` stays, because quests match on it), so saves from the run the player loaded away from don't count as newest for Continue, the death screen or Load last save.
- **During a load's map change** (`bTravelPending`), no checkpoint can save, so nothing from the old world overwrites the loaded state.
- **Death screen:** about 1.2 s after the driver reports `IsDefeated`, the game pauses on "YOU FELL". The default is the newer of the last checkpoint and the last manual or quick save; since a save is also a checkpoint, that's normally "Respawn at last save / checkpoint".
  - **Respawn:** closes the screen, and the driver gets the hero up at the checkpoint (`SetRespawnTransform`). Its timer waited while the screen paused the game, so the rest of its 5 s delay runs. The driver's `RespawnNow()` (added by the spell session for this build) is called by name, so the hero gets up at once.
  - **Load last save:** reloads the newest manual or quick save.
  - **Load Game:** opens the Load screen.
  - **Quit to title.**
  - `GameFlow.DeathScreen 0` brings back the old timed respawn.

**Hooks for other systems** (on `UReflectionsGameFlowSubsystem`; the names are fixed):
- `SetSaveData(FName System, const TArray<uint8>& Data)`: call it in your `OnCheckpointSaved` handler. The data rides with that checkpoint and any slot saved from it. For a `USaveGame`, `UGameplayStatics::SaveGameToMemory` gives the bytes.
- `bool GetSaveData(FName System, TArray<uint8>& Data) const`: the data stored with the checkpoint being restored.
- `OnCheckpointRestored(const FReflectionsCheckpoint&)`: fires after the hero is placed on a restoring map load (Load, Continue, Try again, Restart), after world jump's `OnProgressRestored`. It doesn't fire on a death respawn, because the world keeps going there.
- `SaveToSlot(int32)`, `LoadFromSlot(int32)`, `QuickSave()`, `QuickLoad()`, `GetSaveSlotInfo(int32)`, `GetNewestSaveSlot(bool bExcludeAutosave)`, `HasAnySave()`.

**Other sessions' parts:**
- **Quests:** done for this build. `HandleProgressRestored` re-reads `Reflections_Quests` once when its snapshot's `SavedAt` doesn't match, then applies it. The snapshot also carries the dead-people list.
- **Lives:** confirmed, no change needed. `SyncWithCheckpoint` → `LoadSnapshot` at map start replaces the in-memory people, flags and clock from the restored `Reflections_Lives` file.
- **Villain:** wired for train #12 (villain session, 18:55).
  - **Save:** `SetSaveData("Villain")` stores the tarnished NPCs (Lives `Person_<id>` tags, or level actor names), the host and its time left, and its tallies.
  - **Restore:** in `OnCheckpointRestored`, retried for up to 10 s while Lives assigns people, it re-tarnishes them. The NPC system's `ReportInfected` calls then bring the Tarnish meter back. Runtime-spawned crowd bodies aren't saved.
  - **Finale and true form:** these come back through pages.
- **Spell crafting:** keeps its own save across runs, unchanged.

**Controls:** F5 quick save, F9 quick load (both free; F7 is the lives debug key and F8 the block). Every pad button is taken in play:
- **Quick save:** hold Start for 0.8 s. A short press still pauses, now on release.
- **In the pause menu:** X quick-saves and Y quick-loads. Y quick-loads on the death screen too.
- **No clash:** menus take UI-only input, so X and Y can't trigger game actions there.

## Intro cutscene (the cutscene session's subsystem, called by name)

- **Fresh runs only:** on Start / New Game (and on a PIE start without the title), game flow calls `ReflectionsCutsceneSubsystem::PlayNewGameIntro()` once play begins. It doesn't call it for Restore, Continue or Try again.
- **Narrator line:** if the cutscene starts, it voices the theme line itself. If it doesn't (in PIE it needs `Cutscene.IntroInPIE 1`), game flow plays `SCue_VO_Narrator_Intro` instead. While that class exists, the title screen shows the theme line without voicing it.
- **While `IsCutscenePlaying()`:** no pause key, the tips wait (their clock starts after the cutscene), and no "Checkpoint saved" toast.
- **Status:** compiled; lands on the next train. It isn't tested in PIE yet, because the cutscene subsystem lands on train #7.

## Graphics settings (perf session's spec: `ArtDirection/Perf/GraphicsSettings-Spec.md`)

- **First launch** (packaged and `-game` only, never PIE; it runs when `GetLastCPUBenchmarkResult() < 0`):
  1. `RunHardwareBenchmark` and `ApplyHardwareBenchmarkResults`, clamped to **High**.
  2. **Borderless** at the desktop resolution, VSync on, frame cap Unlimited, render scale 100 % (50 % from 4K up).
  3. `ApplySettings`, `ConfirmVideoMode` and `SaveSettings`, then `r.Lumen.HardwareRayTracing` off.

  This runs before the title is built. Later launches re-apply the stored ray-tracing choice.
- **The screen:** **Settings** sits on the title (after Controls) and on pause (after Controls).
  - Rows: quality preset, resolution, window mode, render scale, VSync, frame cap and ray-traced lighting.
  - Buttons: Apply, Auto-detect and Back.
  - Left/right on a row (D-pad, stick or arrow keys) changes its value; a click cycles forward.
  - The preset previews live. Everything else applies on **Apply**; **Back** drops unapplied changes.
  - A resolution or window-mode change opens "Keep these settings?", which reverts after 15 s (B or Esc reverts).
  - In PIE, resolution and window mode are left alone, and the screen says so.
- **Storage:** the ray-tracing choice is stored in `GameUserSettings.ini` under `[/Script/reflections.ReflectionsGameFlow] bHardwareRayTracing`. It's set with game-setting priority after `ApplySettings`, so the preset can't flip it back.
- **Code:** `GameFlow/ReflectionsGameFlowSettings.{h,cpp}`. Strings are the `Settings.*` keys in the String Table.
- **Status (PIE, 16:21, `test_mockcity_settings_pie.py`):**
  - Settings opens from the title, every row renders (`Screenshots/mockcity_1_settings.png`), and changing the preset previews live.
  - **Bug:** Back didn't undo the preview when the starting quality was "Custom", as it is in the editor, because the preset number can't express that. Fixed for train #10: Settings records every scalability group when it opens (and after Apply, Keep or Revert), and Back restores them exactly. It compiles but isn't re-tested in PIE yet.
  - The first-launch auto-detect hasn't been run yet; it needs a packaged build.

## New Game map

- **Current setting:** the orchestrator set `NewGameMap=/Game/MockCity/Lvl_MockCity.Lvl_MockCity` in `DefaultGame.ini` (16:2x). It takes effect at the next editor start, and in packaged builds.
- **Default when unset:** `UReflectionsGameFlowSubsystem::NewGameMap` (Config, `FSoftObjectPath`) is empty, and Start / New Game plays the map that's loaded. That's today's behaviour; the title is an overlay on `GameDefaultMap`.
- **To switch** (for example to the mock city, once world-jump confirms it plays), add this to `DefaultGame.ini` and put the map in packaging's `MapsToCook`:
  ```
  [/Script/reflections.ReflectionsGameFlowSubsystem]
  NewGameMap=/Game/MockCity/Lvl_MockCity.Lvl_MockCity
  ```
- **Console override for testing:** `GameFlow.NewGameMap /Game/MockCity/Lvl_MockCity`.
- **Continue and Try again** always go to the checkpoint's map.
- **Verified in PIE (16:21):** with `GameFlow.NewGameMap /Game/MockCity/Lvl_MockCity`, title → Start opened the mock city as a fresh run.
  - The hero spawned at the Giltside PlayerStart (146200, 1100, 88).
  - A "Start" checkpoint was saved for `/Game/MockCity/Lvl_MockCity` in Giltside (world Red).
  - Screenshot: `Screenshots/mockcity_3_arrived.png`.
  - The `DefaultGame.ini` line and the MapsToCook entry are packaging's to add.

## Quest journal (the quest session's subsystem, called by name)

- **The button:** the pause menu shows **Journal** (between Resume and Controls) only when `/Script/reflections.ReflectionsQuestSubsystem` has both `OpenJournal()` and `IsJournalOpen()`.
- **While the journal is open:** pressing Journal opens it and hides the pause menu (its Z 990 sits under the menus at 1000). The game stays paused.
- **When it closes:** pause comes back with focus, and it re-asserts the pause and UI-only input.
- **Controls screen:** it lists Journal (L / Start > Journal; the quest session moved it off J, which the sample uses for teleport-to-target) and Speak with quest people (E / D-pad down).
- **Status:** compiled for train #7. It's untested, because the quest subsystem isn't in the tree yet.

## Tutorial tips

Each tip shows once per save, one at a time for about 7 seconds, in the tip card under the meter. The run starts in Giltside, so they appear there.

| Tip | Shows when |
|---|---|
| Aim | 2.5 s into play, once the spell driver is on the pawn. It ends early once you aim. |
| Cast | After the aim tip, once you aim (or 14 s later) |
| Mirror shards | A shard pickup is within 25 m, or you hold any shard |
| Step through | `UReflectionsWorldJumpComponent::CanJump` is true, up or down: you have the shard and the magic |
| Spell crafting | 20 s after the cast tip, once the crafting component is on the pawn |

`GameFlow.Tips 0` hides them; `GameFlow.ResetTips` forgets which were seen.

## Bindings on the Controls screen (from the code and the owning sessions, not guessed)

| Action | Keyboard & mouse | Controller | Source |
|---|---|---|---|
| Move / Look | WASD / Mouse | Left / right stick | `/Game/Input/IMC_Sandbox` |
| Jump | Space | A | IMC_Sandbox |
| Sprint | Left Shift | L3 | IMC_Sandbox; the spell driver moves pad sprint to L3 |
| Walk / Crouch / Strafe | Left Ctrl / C / Middle mouse | stick partway / B / – | IMC_Sandbox (the spell driver takes RB) |
| Aim | Right mouse (hold) | LT (hold) | `UReflectionsSampleSpellDriver` |
| Cast selected spell | Left mouse or Q | RT | spell driver |
| Select spell 1-4 / page | 1-4 / `]` `[` | – / D-pad right-left | spell driver |
| Next / previous spell | Tab / Shift+Tab | RB / LB | spell driver |
| Open spell crafting / crafted spells | K / 5-8 | View / D-pad up | `UReflectionsSpellCraftingComponent` |
| Step up / down a side | X (hold) / Z (hold) | Y (hold) / R3 (hold) | `/Game/Worlds/Input/IMC_WorldJump` |
| Free the mouse cursor | Right Alt (hold) | – | spell HUD |
| Pause / menu | Esc or P | Start | game flow |
| Quick save / quick load | F5 / F9 | Hold Start / Start > Y (X saves in pause) | game flow |

`IA_WarMap` in IMC_Sandbox also lists Start and View, but nothing handles it, so game flow uses Start for pause.

## Debug console (not in Shipping)

`GameFlow.Title`, `GameFlow.Pause`, `GameFlow.Resume`, `GameFlow.Controls`, `GameFlow.Credits`, `GameFlow.Infect [N]`, `GameFlow.Cure [N]`, `GameFlow.Cap N`, `GameFlow.Lose`, `GameFlow.Victory`, `GameFlow.Checkpoint`, `GameFlow.Restart`, `GameFlow.Kill` (kills the hero to test the respawn), `GameFlow.Tip Aim|Cast|Coin|Cross|Craft`, `GameFlow.ResetTips`, `GameFlow.DeleteSave`, `GameFlow.Key <KeyName>` (presses a key through Slate), `GameFlow.Dump`, `GameFlow.Save [1-3|q]`, `GameFlow.Load [1-3|q|a]` (no argument: the newest), `GameFlow.SaveMenu`, `GameFlow.LoadMenu`.

CVars:
- `GameFlow.DeathScreen 0|1`
- `GameFlow.TitleInPIE 0|1`
- `GameFlow.Tips 0|1`
- `GameFlow.Enabled 0|1`: 0 turns the whole layer off in maps started afterwards.
- `GameFlow.InfectionCap N`

## Test

`ArtDirection/GameFlow/test_game_flow_pie.py` runs the whole loop in PIE with real key events through Slate, for both keyboard and gamepad. The usage line is at the top of the file. It writes `Saved/GameFlowTest/*.png` and `report.json`.

The other test scripts take the PIE lock from outside the editor first:
- `test_credits_settings_pie.py`: Settings Back from a Custom quality mix, plus the Credits and Victory layout.
- `test_credits_map_pie.py`: the Credits and Victory layout with the map lines, using the loaded DLL (it puts them in `Credits.Thanks` for the run, then back), then writes `Credits.Map` and saves the table.
- `test_save_system_pie.py`: Save screen → Slot 1, quick save, Load screen → Slot 1 (with the confirm), the death screen and respawn, then quick load. It moves any real saves aside first and puts them back after.

## Packaging notes

- **`/Game/UI`** (the String Table) is in `DirectoriesToAlwaysCook`; packaging added it.
- **UI sounds** load by path from `/Game/Audio/Jam/Cues/` (`SCue_UI_Click`, `_Hover`, `_Confirm`, `SCue_MUS_Victory_Sting`, `SCue_Villain_Manifest`), which is always-cooked. A missing cue only means silence.
- **No startup map change:** the title is an overlay on whatever `GameDefaultMap` loads.

## What works and what doesn't

**Verified in PIE** (train #3 build, 12:10 local). The run used `test_game_flow_pie.py` with real key events sent through Slate (`SlateInspectorToolset.PressKey`). Gamepad keys went in as controller input; there was no physical pad. Result: 19/19 checks passed, `Screenshots/report.json`.
- **Title:** shows at PIE start with `GameFlow.TitleInPIE 1`. The arrow keys move focus, Enter opens Controls, and Esc comes back without stopping PIE. The D-pad moves focus, and A on Start begins play (`01`, `02`).
- **Tips and meter:** the Aim tip appears about 2.5 s into play. The Tarnish meter reads 0/20 at the top right, and the "Checkpoint saved" toast follows the start checkpoint (`03`).
- **Pause:** Start opens it. D-pad + A opens Controls, B goes back to pause and B again resumes. P opens and closes pause too, and the arrow keys move focus there (`04`, `05`).
- **Respawn:**
  - The checkpoint was saved away from the spawn point while looking at yaw 35. The hero then moved elsewhere, turned to yaw 175 and was killed (`GameFlow.Kill`).
  - The driver respawned the hero at the checkpoint (600, 300) rather than the spawn point (0, 0), and the camera came back to yaw 35. The toast said "Back at your last checkpoint" (`06`, `07`).
- **Lose:** `GameFlow.Cap 5` plus 5 infections showed "THE TARNISH HAS TAKEN LANTHORNE" with the count, the game paused, and focus sat on "Try again" (`08`, `09`).
- **Try again:** A reloaded the map. The hero came back at the checkpoint, not the spawn, the count went back to 0, and input worked (the next tip appeared) (`10`).
- **Victory:** `GameFlow.Victory` showed the victory screen and credits. A on "Return to title" reloaded the map onto the title, now with Continue / New Game (`11`, `12`).
- **Compile:** all 6 sources pass `Build.bat reflectionsEditor -SingleFile`, including the later fixes below.

**Re-run on train #5** (12:50): the same 19 checks pass in 38 s. The layout fixes are visible in `Screenshots/01`, `02`, `09` and `11`:
- Buttons are 440 wide with tighter letter spacing, so "Restart from checkpoint" and "Try again from checkpoint" fit.
- The Controls action column is wider, so its long names no longer run into the key column.
- Credits lines wrap.
- The title's dark band now spans the title.

The narrator hooks (`SCue_VO_Narrator_*`) and the rule-neutral text are in this build too. The voice lines exist, but nobody has listened to them in game yet.

**Not tested yet:**
- **Mouse:** hover → focus and click are untested. Automation can't reach them in PIE, because `SlateInspectorToolset` snapshots only see editor windows, not the game viewport's layers. Its "Credits" match was an editor widget under the Message Log window. The test's mouse step now skips with a note. The buttons are standard `SButton`s (click = `OnClicked`), and hover only adds a focus change. **A 30-second manual check is still needed**: in PIE with `GameFlow.TitleInPIE 1`, hover the buttons (the highlight should follow) and click Controls → Back.
- **Packaged build:** Esc pausing and the title at launch haven't been tried there. In the editor, Esc stops PIE before the game sees it; P and Start were tested instead. Launch uses the same code path as `GameFlow.TitleInPIE 1`.
- **Real world jumps and mirror-page pickups:** the test map has no world-jump anchors and no pickups. So the autosave on `OnWorldChanged` / `OnPagesChanged` and the quiet `RestoreProgress` with shards and pages are untested in PIE. The test checkpoint was saved from the console, and the start checkpoint is the automatic one.
- **Shard, Step through and Crafting tips:** the test map has no shards or world jumps, and the run was shorter than the crafting tip's delay.
- **Real infections:** those from the NPC subsystem and the villain weren't seen; the test used `GameFlow.Infect`. A real `ShowVictory` from the finale also isn't tested.
- **Credits team names:** still a placeholder (`Credits.Team` in the String Table).

**Known limits:**
- **Title audio:** the title pauses the world, so the side's music pauses under it; only UI sounds play there.
- **Cap override:** `GameFlow.Cap` / `SetInfectionCap` stays for the whole session, restarts included.
