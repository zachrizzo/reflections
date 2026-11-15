# Test packaging: Win64 Development jam build

Status as of **2026-11-14 ~10:35 local (Sat)**. Deadline is Sun Nov 15, 8:59 PM ET (team target 6 PM ET = 4 PM local). itch.io needs a zip under 1 GB.

**Bottom line:** the packaged build **works**.

- **Build:** made from train #2's matched editor DLL and game exe (10:19). The cook had **0 errors**.
- **Test run:** `Lvl_HeroSampleCrowd` loads in 0.6 s. The hero spawns in the new drape coat, the crowd animates, the spell HUD and health/mana work, and the game log has 0 errors.
- **Zipped size: 729 MB** (baseline 1,756 MB). Staged: 1,062 MB.
- **Screenshot:** `Saved/JamBuild/Logs/launch_matched.png`. (Its zip has since been deleted; `train5_Windows.zip` is the kept fallback.)
- **Latest (12:50):** the train #5 matched pair, cooked under a save freeze; the staged exe was verified byte-for-byte against the train #5 exe. **734 MB zipped**, 0 cook errors. Package: `Saved/JamBuild/Windows/`. Zip: `Saved/JamBuild/Zips/train5_Windows.zip`. Screenshot: `Saved/JamBuild/Logs/launch_train5.png`. The NPC spell-kill path still needs a manual play test (see the pak audit section).
- **Runtime log of the latest build** (3 errors, none fatal; the game kept running):
  - `ConvertQueryImpactHit() received NaN/Inf for normal` and `RaycastSingle resulted in a NaN/INF in PHit!`, twice, with the hero idle. Some code is issuing a raycast with a NaN direction, probably NPC or crowd movement.
  - Warning: `City crowd: level /Game/Crowd/City/Lvl_HeroSampleCrowd_City does not exist; no pedestrians`. That level isn't created yet; `/Game/Crowd/City` is already always-cooked for when it is.

## How to package

1. **Build the editor and game targets together, from the same source,** while nobody is editing source. The orchestrator's :40 build train does this. The editor must be closed, because its DLL is locked while it runs.
   ```bat
   "C:\Program Files\Epic Games\UE_5.9\Engine\Build\BatchFiles\Build.bat" -Target="reflectionsEditor Win64 Development -Project=\"C:\Users\zachc\Documents\Unreal Projects\reflections\reflections.uproject\"" -Target="reflections Win64 Development -Project=\"C:\Users\zachc\Documents\Unreal Projects\reflections\reflections.uproject\"" -WaitMutex
   ```
2. **Announce a SAVE FREEZE** to every session: no asset saves under `Content/` until "end". Wait until `Content/` has been quiet for 60 s. Two cooks today raced live saves (audio at 10:02, spell VFX at 10:04).
3. **Cook and stage.** The open editor can stay open, since the cook runs in its own process:
   ```bat
   ArtDirection\Packaging\PackageJamBuild.bat
   ```
   The script runs:
   ```
   RunUAT.bat BuildCookRun -project=<reflections.uproject> -noP4 -platform=Win64 -clientconfig=Development -target=reflections
     -nocompileeditor -cook -map=/Game/Characters/Hero/Sample/Lvl_HeroSampleCrowd -stage -pak -iostore -compressed -nodebuginfo
     -stagingdirectory=<project>\Saved\JamBuild -unattended -utf8output
     -AdditionalCookerOptions=-NeverCookListFile=%TEMP%\ReflectionsJamNeverCook.txt
   ```
   It copies `NeverCookList.txt` to `%TEMP%` first, because the cooker's command line can't take a path with spaces. Use `--dry-run` to print the command without running it. Add `--with-npc-relay` to also stage the NPC dialogue helper (see the budget table); it's off by default. The cook takes ~1–3 min with a warm DDC; staging takes ~2 min. The log goes to `Saved/JamBuild/Logs/uat_package.log`.
4. **End the freeze** once the log shows `COOK COMMAND COMPLETED`.
5. **Launch-test:** run `Saved/JamBuild/Windows/reflections.exe -windowed`, then check `Saved/JamBuild/Windows/reflections/Saved/Logs/reflections.log` for `Error:` and `Fatal`.
6. **Zip** with `powershell -ExecutionPolicy Bypass -File ArtDirection\Packaging\ZipJamBuild.ps1 -Source Saved\JamBuild\Windows -Dest <TeamName>_Reflections.zip`.
   - **Don't zip the folder by hand.** Running the staged game (step 5) writes `reflections/Saved/` into it: logs, `SaveGames/Reflections_Checkpoint.sav` (judges would see "Continue" on our save) and crash-reporter config. The script excludes every `Saved/` folder, `*.sav`, `*.log` and `keys.json`. Perf-stability found these in `train5_Windows.zip` (14:5x); that zip has since been rebuilt clean.
   - Don't use `tar -a -cf x.zip` either: it stored the files uncompressed here.

> **Packaging is paused until Sunday** (user, ~15:00 Sat): the team is testing in the editor. `Saved/JamBuild/Zips/train5_Windows.zip` (734.0 MB, clean) is the fallback. The cook rules in this README stay in force for the final package.

To list what's in the pak: `"C:\Program Files\Epic Games\UE_5.9\Engine\Binaries\Win64\UnrealPak.exe" -ListContainer="<stage>\Windows\reflections\Content\Paks\reflections-Windows.utoc" -csv=out.csv`

## Sizes

| Build | Cooked packages | Content paks | Staged | **Zip** |
|---|---|---|---|---|
| Baseline: no packaging settings (09:00) | 1,563 | 1,461 MB | 2,330 MB | **1,756 MB** |
| Packaging settings only (09:13) | 3,166 | 554 MB\* | 1,465 MB | 892 MB |
| + editor-only toolsets, no `/Game/Worlds` (verification, 10:06) | 3,313 | 649 MB | 1,156 MB | 823 MB |
| **+ NNEDenoiser out, matched train #2 build (10:26)** | 3,306 | 554 MB | 1,062 MB | **729 MB** |
| Train #3 cook (11:46 DLL) + hotfix exe (11:58), new villain/UI/squad rules (12:02). Throwaway: mismatched pair | 3,376 | 562 MB | 1,064 MB | 731 MB |
| Matched 12:04 rebuild (KickRagdoll fix), + voice lines, NPC archetypes (12:17) | 3,474 | 564 MB | 1,066 MB | 732 MB |
| **Train #5 matched pair (12:33 DLL, 12:34 exe), + 78 NPC voice lines (12:50)** | — | 566 MB | 1,068 MB | **734 MB** |

\* The 09:13 build was missing NNEDenoiser and later content. All builds after the baseline also include the hero pawn, spells, audio and spell crafting, which the baseline had silently left out (root cause A).

### Zip by part (matched build)

| Part | Zipped |
|---|---|
| Content paks | 542 MB |
| `reflections.exe` (monolithic, 337 plugins) | 137 MB |
| Other binaries (engine/plugin DLLs, Vulkan layers, DirectML, D3D12) | 50 MB |

### Content by owner (matched build; compressed in the pak ≈ zipped size)

| Owner | Now | **Budget** | Notes |
|---|---|---|---|
| Crowd / NPC MetaHumans (user, Codex NPC combat, crowd session) | 301 MB | **320 MB** | `RedLondon` 199, `WhiteLondon` 82. **Each extra MetaHuman costs ~50–60 MB** even with the 2K texture cap. Pending: the crowd session's city level `/Game/Crowd/City` (always-cooked since 12:51) pulls in `COL_CrowdPrototype_CoinClerk`, a 108.8 MB MetaHuman Collection. Estimated 20–80 MB cooked (`MHC_*` and control rigs are editor-only); measure at the next cook. If it's over ~60 MB, the crowd owner should slim the collection or the budget must move. |
| Shader code (all materials, SM5 + SM6) | 134 MB | **160 MB** | Grows with every new material, especially the London map's. |
| Hero body, cloak, GASP locomotion (hero-cloak, spell-combat) | 89 MB | **100 MB** | `UEFN_Mannequin` (motion-matching animations) is 48 MB of it. |
| Engine + plugin content | 13 MB | **15 MB** | |
| London map / level art (map teammate) | 9 MB | **120 MB** | Not in this map yet. |
| Audio | 12 MB | **20 MB** | |
| Spells + VFX, spell crafting, world jump | 3 MB | **15 MB** | |
| NPC dialogue relay (dialogue session): loose `NpcDialogueRelay.exe` + `_internal` | 0 | **15 MB** | **Opt-in, pending the user's decision:** `PackageJamBuild.bat --with-npc-relay`. After staging, it copies the helper from `Content/NpcDialogue/Relay/` (falling back to `Tools/RealtimeVoice/dist/NpcDialogueRelay`) loose to `<stage>/reflections/Content/NpcDialogue/Relay/`. There's deliberately no `DirectoriesToAlwaysStageAsNonUFS` line, so the helper ships only with this flag. Measured 23.9 MB raw, **13.5 MB zipped**, 47 files. Key files (`keys.json`, `*.env`, `*.key`) are excluded from the copy, and the staged folder is checked afterwards. A local `keys.json` for editor testing is fine. The game only starts the helper when the user puts `keys.json` next to the exe after packaging. Risk: PyInstaller executables often trip antivirus or SmartScreen, so scan the final zip with Defender before upload. |
| Villain, possession, finale (villain session) | <1 MB | **10 MB** | Not in the matched build. Requested: `/Game/Villain` (materials, FX, robe mesh) plus a few Mannequin animations. |
| Binaries (fixed) | 187 MB | 187 MB | |
| **Total** | **729 MB** | **947 MB** | ~50 MB of headroom under 1,000 MB. |

If the total runs over: drop SM5 (DX11) shaders, about −65 MB (`DefaultEngine.ini` `D3D11TargetedShaderFormats`, which loses the DX11 fallback), or lower the `Character*` texture cap in `Config/DefaultDeviceProfiles.ini` from 2048 to 1024 (about −100 MB, softer faces up close).

## What changed

### `Config/DefaultGame.ini`, `[/Script/UnrealEd.ProjectPackagingSettings]` (additive)

- `+MapsToCook=Lvl_HeroSampleCrowd`, so the editor's Package Project cooks only the start map.
- `+DirectoriesToAlwaysCook` for folders C++ loads by **string path at runtime**, which the cooker can't see:
  - `/Game/Characters/Hero/Gameplay`: `BP_HeroPlayer` (spell defaults) and `BP_HeroAnimation`
  - `/Game/Characters/Hero/Animation/CombatCasts`, `/Game/Characters/Hero/SpellVFX`, `/Game/Input`
  - `/Game/Blueprints/Combat/Blood`
  - `/Game/Characters/WhiteLondon/IvenRook/MetaHuman/Animation/ElementalSpells/FX`
  - `/Game/Audio/Jam`, `/Game/SpellCrafting` (including `Gestures`), `/Game/Worlds`, `/Game/Villain`, `/Game/UI` (game flow's String Table), `/Game/NPC/Archetypes` (NPC unify; created after train #3), `/Game/Squads` (march cycles, 4.3 MB on disk), `/Game/Crowd/City` (the crowd's runtime city level), `/Game/Quests` (quest packs), `/Game/Cinematics` (cutscene data; size pending), `/Game/Lives` (NPC lives, `DA_PeopleBook`) and `/Game/Combat/Melee` (30 Kimodo melee clips, 30 MB on disk; `Source/` is never-cooked), at their owners' request
  - `/Game/Characters/CrowdMotion` was already listed.
  
  Every folder was checked: none references the broken `action_fighting` chain.
- `+DirectoriesToNeverCook`:
  - `/MetaHuman/GenericTracker` and `/MetaHumanCoreTech/GenericTracker`: ~580 MB of face-tracking ML models that no cooked package references.
  - `/Game/Worlds/Test`, `CombatCasts/Rigs` and `CombatCasts/Soma`: their owners confirmed they aren't used at runtime, and nothing references them.
- Compression: `PackageCompressionMethod=Leviathan`, levels `DebugDevelopment=7`, `TestShipping=7` (engine default: Kraken 4).

### `Config/DefaultEditor.ini`, new `[AlwaysCookMaps]` section

`+Map=/Game/Characters/Hero/Sample/BP_HeroSampleCleanTest` and `+Map=.../BP_SampleControllerClean`. `ReflectionsSampleGameMode::InitGame` loads the map's real pawn and controller by string path.
The section also lists 9 Mannequin packages that the villain session's code string-loads: `MM_Idle`, `MM_Fall_Loop`, `MM_Dash`, `MM_Attack_02`, `MM_Attack_03`, `MM_ChargedAttack`, `SKM_Manny_Simple`, `SKM_Quinn_Simple` and `ABP_Unarmed`. They stay until its `DA_VillainConfig` hard-references them; I listed packages rather than the whole 126 MB Mannequins folder.
It also lists the squads' White London looks, `BP_WhiteLook_03_Mantle`, `_04_CapMantle`, `_05_GuardRags` and `_06_GuardBoldRunes`, which squads spawn by string path. They share IvenRook's body and face, which are already cooked, so the expected cost is only their clothing meshes: about 1–5 MB. The scan's 85 MB "upper bound" is mostly editor-only MetaHuman control rigs, which the cooker already excludes. The cooker requests any package listed there on every cook (`CookOnTheFlyServer.cpp`, `GCookRequestUsageMessage`). Their folder can't be always-cooked as a whole: `GM_HeroSample` there pulls in the broken chain.
An Asset Manager `PrimaryAssetTypesToScan` rule was tried first and reverted: it logs `LogAssetManager: Error` on every save of those Blueprints.

### `Config/DefaultDeviceProfiles.ini` (new): texture caps, cooked build only

`[Windows DeviceProfile]` sets `MaxLODSize` and `MaxLODSize_VT` to 2048 for the World* and Character* texture groups (including their normal-map and specular variants) and to 4096 for Skybox. The cooker strips mips above the cap for the Windows target (`TextureDerivedData.cpp`, `SerializeCooked`). MetaHuman baked maps are virtual textures and read only `MaxLODSize_VT`. Result: the 8K body maps went from ~70 MB to ~4.5 MB each, and Texture2D overall from 562 MB to 274 MB. `[WindowsEditor DeviceProfile]` restores 16384, so editor visuals are unchanged.

### `reflections.uproject` (at the orchestrator's request)

- `"TargetAllowList": ["Editor"]` on 20 editor-assistant plugins: the `*Toolset(s)` entries plus `MCPClientToolset`, `AgentPluginToolset`, `DataflowAgent`, `UnrealCanvasBridge` and `UnrealCanvasAnnotations`. Result: the game target went from 415 to 338 plugins, CEF3 web-browser DLLs are no longer staged (163 MB zipped), and the exe shrank.
- `NNEDenoiser` with `"TargetAllowList": ["Editor"]`. The plugin's own `Config/Game.ini` still always-cooks `/NNEDenoiser`, so its content is excluded through `ArtDirection/Packaging/NeverCookList.txt` (passed by `PackageJamBuild.bat`). Saves 100 MB.
  - Why not `DirectoriesToNeverCook`: never-cooking a plugin's root path trips an `AssetReferenceRestrictions` ensure in every cook and editor start.
  - Optional cleanup: set NNEDenoiser to `"Enabled": false` (path-tracer denoising in the editor goes away). The list file then becomes unnecessary.
- Before each change I checked that no game source, Build.cs or cooked asset depends on these plugins.

### `Source/reflections.Target.cs` (applied by the orchestrator, game target only)

`bWithLiveCoding = true; bOverrideBuildEnvironment = true;`. See root cause B.

### Not changed, and why

- **MetaHuman skeletal-mesh LODs.** Skeletal meshes are 23 MB cooked; cook-time LOD stripping needs per-asset MinLOD (an asset edit). Textures were the real cost.
- **`/Game` folders weren't never-cooked beyond the confirmed ones.** `-map`/`MapsToCook` already leaves unreferenced content out. A broad never-cook would silently drop content someone references tomorrow.

## Root causes found today

**A. String-path loads were missing from the package.** `LoadObject`, `TryLoadClass` and `FSoftClassPath` literals are invisible to the cooker. The baseline package had no hero pawn or controller, spell defaults, spell clips, VFX, input actions or blood VFX. Fixed with the always-cook entries. **Every new string path must point into an always-cook folder.**

**B. The packaged exe crashed during C++ static init** (exit code 777006, `CrashDuringStaticInit`, before any log). Symbolized with the game PDB, it was a null write in `TDeferredRegistry<UScriptStruct>::AddRegistration` (`InInfo.ReloadVersionInfo`), from the static initializer of `CombatStateTreeUtility.gen.cpp`. That file isn't at fault: it's just the first USTRUCT to register.
Cause: `%APPDATA%\Unreal Engine\UnrealBuildTool\BuildConfiguration.xml` (dated 2026-02-11, machine-wide) sets `<bWithLiveCoding>false</bWithLiveCoding>`. So our module compiled with `WITH_LIVE_CODING=0` against Epic's precompiled game libraries built with 1, and in a monolithic exe the UObject registration structs then differ. The editor is unaffected because hot reload keeps `WITH_RELOAD=1`. The UBT `-LiveCoding` switch does **not** override the XML (tested).
**Fixed** by the two `Target.cs` lines. Verified: the train #2 exe gets through static init and runs.

**C. Cooked data must match the exe.** Cooked packages use unversioned property serialization, so **even an added UPROPERTY** breaks loading of assets cooked before it. Seen today: a fatal `ObjectSerializationError ... DA_WorldJumpConfig: Serial size mismatch` four seconds after map load, in a mixed build. Hence build first, then cook, every time.

## The `action_fighting` question

`BP_Player`, `AC_Hostility`, `AIC_Human`, `AC_Weapons`, `SandboxCharacter_Mover_ABP` and `GM_Sandbox` are **not cooked** in any build: the cook log has no `action_fighting` mention, and none of them is in the pak listings. The only path to them runs through `/Game/Characters/Hero/Sample/GM_HeroSample` → `/Game/Blueprints/PC_Sandbox` / `SandboxCharacter_Mover` → `SandboxCharacter_Mover_ABP` → `AC_Weapons`, `BP_Player` → `AIC_Human`, `AC_Hostility`. Nothing the map or the always-cook rules reference reaches `GM_HeroSample`. **Don't always-cook `Hero/Sample` or `/Game/Blueprints` as a whole.**

## Cook errors and warnings

- The matched cook (and every good cook): **0 errors**. The same 5 warnings each time:
  - `LevelBlock` construction script: `Attempted to access index 0 from array 'CallFunc_GetAllActorsOfClass_OutActors' of length 0` (from `LevelBlock_Traversable_C_0` in the map).
  - `ABP_Clothing_PostProcess` (BridgeGuard, CoinClerk, IvenRook): deprecated `SetControlRigClass`.
- Packaged-game log (matched build): 0 errors. The only warnings are `LogConsoleManager` performance notices from the GASP locomotion Blueprints polling cvars (`DDCvar.*`), which are harmless.
  - The earlier `NS_Spell_Impact` missing warning (a save race) and the `NS_Crafted_Body/Field` attribute mismatch (fixed by spell crafting at 10:07–10:10) are both gone.
- Failed cooks today, all explained:
  - 31 errors: my two reverted config experiments.
  - 18 errors: the audio save race at 10:02.
  - 18 errors: NNEDenoiser assets failing to cook once their module was editor-only, before the never-cook list was added.
- Game-target compiles broke twice from mid-edit source (08:50 `ReflectionsSpellCombat.cpp`, where C4456 variable shadowing is a compile error in this project; 09:07 SpellCrafting). Both were fixed by their owners within minutes.

## Blockers and owners

| # | Item | Owner | State |
|---|---|---|---|
| B1 | Static-init crash | Orchestrator | **Fixed** (`Target.cs`), verified |
| B2 | Build the editor and game together, then cook (root cause C) | Orchestrator (build train) + packaging | Process in place |
| B3 | Source must compile for the Game target at packaging time | Each C++ owner | OK at 10:19 |
| B4 | New string-path loads must land in always-cook folders | All C++ owners (spells, crafting, NPC/Codex, world jump, audio) | Ongoing |
| B5 | `/Game/Characters/CrowdMotion/Combat/AS_GuardPunch` is loaded by code but doesn't exist | NPC combat (Codex), routed via the user | Open |
| B6 | Size headroom: NNEDenoiser removed (**done**). SM5 shaders (−65 MB) are optional if the budget tightens. | `DefaultEngine.ini` owner (user) | Optional |
| B7 | `GM_HeroSample`, `PC_Sandbox`, `SandboxCharacter_Mover` still reference the broken `action_fighting` Blueprints. Harmless while nothing cooked references them. | Sample-integration owner (spell-combat-rebuild / user) | Watch |
| B8 | The user-level `BuildConfiguration.xml` `bWithLiveCoding=false` also disables Live Coding in the editor for every project on this machine. `Target.cs` no longer depends on it. | User | Decision |
| B9 | Save freezes around every packaging cook. Send "start" and "end" to every asset-saving session: spells `local_07d1c5bc…`, world jump `local_830b60d0…`, spell crafting `local_f926586a…`, audio `local_8ac9a603…`, villain `local_dd0eeffa…`, game flow `local_0b912c4f…`, NPC unify `local_c650e0ab…`, crowd `local_3627acc6…`, squads `local_cf45fc1d…`, hero cloak `local_18d00117…`. The full IDs are in the shared notes. PIE checks during a cook are fine (PIE doesn't save). The app caps automated cross-session messages (~20 per user message), so the freeze status is also kept in `SAVE-FREEZE-STATUS.md` in the shared notes folder. Also: the cook only starts after `Content/` has been quiet for 60 s, and it caught a save landing mid-cook at 12:15 (the archetypes made it in). | Packaging announces; all sessions honour | In place |
| B10 | Disk: ~166 GB free on C: (the user cleared space). Each package needs ~1.1 GB staged + ~0.75 GB zipped. `Saved/JamBuild/Zips` keeps only `train5_Windows.zip`, the last known-good fallback; older zips were recycled at the user's request. | Packaging | OK |

## Sunday plan

0. **Start map switch (pending the orchestrator's go):** the real playthrough map is `/Game/MockCity/Lvl_MockCity`, which has the three sides, anchors, towers and pages. `Lvl_HeroSampleCrowd` has no world anchors, so world jump can't run there by design. Once the orchestrator and game flow confirm (game flow's `GameFlow.NewGameMap` lands in train #8), change the three places that name the start map:
   - `DefaultEngine.ini` `GameDefaultMap`: the orchestrator switches it, along with game flow's `NewGameMap`, once world jump confirms the mock city plays. `EditorStartupMap` stays the sample so editor restarts stay light.
   - `DefaultGame.ini` `+MapsToCook`: add `Lvl_MockCity` and the side maps `Lvl_MockCity_Giltside` / `_Pewterside` / `_Frostside` if they're streamed by name.
   - `PackageJamBuild.bat` `-map=`: list each map, separated by `+`.

   Then do a dry-run cook and re-measure the zip, because the new map's content changes the size budget. `/Game/Worlds/Test` stays never-cooked.

   **Done Sat 19:03–19:20, from the best-practices crash review (X3, X4, Y9, X9).** Not cooked yet; check the cook log Sunday.
   - `DefaultGame.ini`: `+MapsToCook=(FilePath="/Game/MockCity/Lvl_MockCity")`, because `NewGameMap` is opened by string. The bat's `-map=` is now `Lvl_HeroSampleCrowd+/Game/MockCity/Lvl_MockCity`. `GameDefaultMap` / `EditorStartupMap` are unchanged (orchestrator).
   - `DefaultEditor.ini` `[AlwaysCookMaps]`: `SM_Frostside_MirrorSword` and `SM_Pewterside_ReaderWand`, which are string-loaded by Squads and the NPC archetypes. Without them, soldiers are unarmed in a package.
   - `PackageJamBuild.bat --with-npc-relay`:
     - The relay is copied by **allowlist**: `NpcDialogueRelay.exe`, `roster.json`, `keys.json.example`, `_internal\` and `seed\`; `*key*.json`, `*.env` and `*.key` are excluded inside the two folders.
     - Then the staged folder is scanned for key-named files and for key-shaped strings (`AIza…`, `sk-…`) in text files. On a hit, it deletes the staged relay and exits 9.
     - Tested on a scratch copy with `keys - Copy.json`, `keys.json.txt` and `.env` decoys, which stayed behind, and a planted `AIza…` string, which was caught. (findstr couldn't do it: it silently gives up on search strings over 127 bytes.)
   - `PackageJamBuild.bat` now **fails** when `Content/Lives/DA_PeopleBook` is older than `ArtDirection/Story/people.json`; a dry run only warns. At 19:20 it's stale (15:10 vs 19:04), and npc-lives was asked to re-import.
   - Still open: J4. The AndroidFileServer section and its SecurityToken in `DefaultEngine.ini` belong to the orchestrator (plugin off in the uproject, section deleted).

   **Also measure the new NPC cast in that cook** (crowd-looks `local_ac448871`, Sat 18:4x):
   - `/Game/Characters/Lanthorne/` replaces the old spawn pools: 20 look Blueprints reached through soft refs in the always-cooked `/Game/NPC/Archetypes/DA_Npc_*`, 13 new MetaHumans plus 7 re-groomed faces. Uncooked it's ~1.4 GB plus 435 MB of `People/Common`; the grooms are 461 MB uncooked, strands included.
   - Report the cooked MB for `/Game/Characters/Lanthorne` against the **320 MB NPC budget** to crowd-looks. If it's over, crowd-looks cuts grooms first (cards-only strands), then the number of new faces.
   - Check these drop out of the pak: `/Game/Characters/CrowdMotion/SimpleRed` (once crowd swaps the 6 placed walkers), `/Game/Characters/WhiteLondon/CrowdPreview` (once squads read the archetype lists), and `RedLondon/Crowd/Variants`.
   - `COL_CrowdPrototype_CoinClerk` (108 MB uncooked) still comes in because `/Game/Crowd/City` is always-cooked, though Mass is a no-go for the jam. Ask crowd (`local_3627acc6`) to drop that always-cook entry before the rehearsal.
1. **Rehearsal:** after any build train Sunday morning, run steps 1–6 above end to end and check the zip against the budget.
2. **Final:** at the last build train before the 4 PM local target (6 PM ET), freeze content and source, then run steps 1–6. That's ~25 min including the train.
   - Zip as **`[TeamName]_Reflections.zip`** (jam rule `TeamName_GameName.zip`; the team name is still the user's decision), then upload. `reflections.exe` and the pak and folder names stay as they are.
   - The window title comes from `ProjectDisplayedTitle=INVTEXT("Reflections")` in `DefaultGame.ini`. Verified in the 12:02 package: the window reads "Reflections (64-bit Development PCD3D_SM6)" and game flow's title screen shows. `CompanyName` is still pending the team name.

### Pak audit (12:02 package)

`/Game/AdvancedLocomotionV4`, `/Game/Characters/Paragon`, `/Game/Characters/Echo` and `/Game/Characters/UE4_Mannequin` each have **0 cooked packages**.
- ALS (35 MB on disk) is referenced only by the old `/Game/Blueprints/Data/Weapons/WD_*` data, which is never cooked. It's now in `DirectoriesToNeverCook` as a guard.
- Paragon (786 MB), Echo (1,121 MB) and UE4_Mannequin (17 MB) are referenced only by GASP's visual-override retarget set, `/Game/Blueprints/RetargetedCharacters/ABP_GenericRetarget` and `BP_UE4_Mannequin`. That set isn't cooked because nothing the map uses reaches `GM_HeroSample`. All three are now in `DirectoriesToNeverCook` as hard guards (approved by the orchestrator): if anything cooked ever references them, the cook fails loudly with "Content is missing from cook ... marked NeverCook" instead of silently adding ~1.9 GB.
- `NNEDenoiser` has 0 packages.

The 12:17 matched package confirms this audit. It also contains the 50 voice lines (`SCue_VO_Narrator_Intro` included, so that warning is gone) and all 10 NPC archetypes. Its game log has 0 errors and no warnings apart from GASP's cvar-polling performance notices.

**Not yet tested: killing an NPC with a spell** (the 11:53 `KickRagdoll` crash path, fixed in the 12:04 build). The automated test reaches the title screen and gameplay, but synthetic mouse and key input doesn't reach gameplay casting (mana stays 100). Someone must play the packaged build for a minute and kill an NPC with Fire Bolt. Observed during the idle test: the hero's health fell from 100 to 36 in about 45 s with no player input, so NPCs or the Tarnish damage an idle hero. Worth checking that this is intended.
   - Leave at least 2 hours before 4 PM local for a second attempt.
3. If the zip is over 1,000 MB, apply the fallbacks under the budget table, then re-run steps 3–6.
