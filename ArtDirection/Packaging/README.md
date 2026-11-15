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
     -nocompileeditor -cook -map=/Game/GrayLondon/Maps/GrayLondon_Geodata -stage -pak -iostore -compressed -nodebuginfo
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
| London map / level art (map teammate) | 9 MB | **120 MB** | Not in this map yet. **Gray London (landed Sat 21:00) is estimated at 250–470 MB cooked, about 350 MB likely**: well over this budget. See "Gray London cook plan" in the Sunday plan. |
| Audio | 12 MB | **20 MB** | |
| Spells + VFX, spell crafting, world jump | 3 MB | **15 MB** | |
| NPC dialogue relay (dialogue session): loose `NpcDialogueRelay.exe` + `_internal` | 0 | **15 MB** | **Opt-in, pending the user's decision:** `PackageJamBuild.bat --with-npc-relay`. After staging, it copies the helper from `Content/NpcDialogue/Relay/` (falling back to `Tools/RealtimeVoice/dist/NpcDialogueRelay`) loose to `<stage>/reflections/Content/NpcDialogue/Relay/`. There's deliberately no `DirectoriesToAlwaysStageAsNonUFS` line, so the helper ships only with this flag. Measured 23.9 MB raw, **13.5 MB zipped**, 47 files. Key files (`keys.json`, `*.env`, `*.key`) are excluded from the copy, and the staged folder is checked afterwards. A local `keys.json` for editor testing is fine. The game only starts the helper when the user puts `keys.json` next to the exe after packaging. Risk: PyInstaller executables often trip antivirus or SmartScreen, so scan the final zip with Defender before upload. |
| Villain, possession, finale (villain session) | <1 MB | **10 MB** | Not in the matched build. Requested: `/Game/Villain` (materials, FX, robe mesh) plus a few Mannequin animations. |
| Binaries (fixed) | 187 MB | 187 MB | |
| **Total** | **729 MB** | **947 MB** | ~50 MB of headroom under 1,000 MB. |

If the total runs over: drop SM5 (DX11) shaders, about −65 MB (`DefaultEngine.ini` `D3D11TargetedShaderFormats`, which loses the DX11 fallback), or lower the `Character*` texture cap in `Config/DefaultDeviceProfiles.ini` from 2048 to 1024 (about −100 MB, softer faces up close).

## What changed

### `Config/DefaultGame.ini`, `[/Script/UnrealEd.ProjectPackagingSettings]` (additive)

- `+MapsToCook=/Game/GrayLondon/Maps/GrayLondon_Geodata` (since Sat 21:05; it was `Lvl_HeroSampleCrowd`, then the mock city), so the editor's Package Project cooks only the start map. A World Partition map's actors and streaming cells come with it.
- `+DirectoriesToAlwaysCook` for folders C++ loads by **string path at runtime**, which the cooker can't see:
  - `/Game/Characters/Hero/Gameplay`: `BP_HeroPlayer` (spell defaults) and `BP_HeroAnimation`
  - `/Game/Characters/Hero/Animation/CombatCasts`, `/Game/Characters/Hero/SpellVFX`, `/Game/Input`
  - `/Game/Blueprints/Combat/Blood`
  - `/Game/Characters/WhiteLondon/IvenRook/MetaHuman/Animation/ElementalSpells/FX`
  - `+DirectoriesToAlwaysStageAsUFS=(Path="Crowd/Spots")` (crowd-react, Sat 22:3x): the crowd's street spots are plain JSON, read from `ProjectContentDir()/Crowd/Spots/<MapName>.json`, so the file is staged into the pak. `FFileHelper::LoadFileToString` reads it from there.
  - `+DirectoriesToNeverCook=(Path="/Game/Cinematics/Takes/Source")` (cutscene session, Sun 01:2x): the six editor-only Kimodo source takes. `/Game/Cinematics` itself stays always-cooked, because cutscenes are loaded by path.
    - Checked: nothing outside the folder and no code references them.
    - Their only outside reference is `SKM_Quinn_Simple`, which stays cooked anyway through `[AlwaysCookMaps]` (villain).
    - The saving is small: 13.5 KB in the measurement build. In total, cinematics was ~110 KB compressed in that build.
  - `[AlwaysCookMaps]` `SM_Pewterside_CanalCrate` (crowd-react, Sat 23:0x): the ring walkers' carry prop, string-loaded by `ReflectionsCrowdRingSubsystem` (`Crowd.Ring.CarryProp`). Nothing else references it now that the mock city is gone.
    - Listed as one package rather than the 12.3 MB `Pewterside/Props` folder. Its two materials and its 1.7 MB World-group texture follow as hard refs.
    - About 1 MB cooked at the 1024 cap.
  - `/Game/Characters/UEFN_Mannequin/Animations/Interactions/Bench` and `.../Animations/Idle` (orchestrator for crowd-react, Sat 22:5x): bench and idle clips the crowd spots load by path.
    - On disk they're 47 + 52 MB (24 + 37 clips), but cooked animations are about 44 KB each.
    - All 24 bench clips and 20 of the 37 idle clips were already in the train #5 pak through GASP.
    - Expected cost: about **+1–2 MB**. The eight idle-break clips the code names weren't cooked before.
  - `/Game/Audio/Jam`, `/Game/SpellCrafting` (including `Gestures`), `/Game/Worlds`, `/Game/Villain`, `/Game/UI` (game flow's String Table), `/Game/NPC/Archetypes` (NPC unify; created after train #3), `/Game/Squads` (march cycles, 4.3 MB on disk), `/Game/Quests` (quest packs), `/Game/Cinematics` (cutscene data; size pending), `/Game/Lives` (NPC lives, `DA_PeopleBook`) and `/Game/Combat/Melee` (30 Kimodo melee clips, 30 MB on disk; `Source/` is never-cooked), at their owners' request
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

**Jam package, planned for ~15:45 Sun** (orchestrator, 15:0x). The orchestrator writes "packaging your turn" in `Saved/PIE_QUEUE.md` and closes the editor.
- **Map is now `/Game/GrayLondon/Maps/MedievalLondon`** (Codex). It's set in `GameDefaultMap`, `EditorStartupMap`, `NewGameMap` and `MapsToCook`.
  - It's an ordinary level, not World Partition: one `.umap` (2.2 MB at 12:20), no external actors.
  - Its references reach 89 packages, about 10 MB: `MedievalOpening/MarketDressing`, `Kit`, `Ground`, `WholeBuildings`, `Graphs`, plus a few `LanthorneAssets/Giltside` pieces.
  - Its name table still contains the string `GrayLondon_Geodata` and one Geodata actor path. The asset registry lists no hard or soft dependency on them (20 hard deps, 1 soft), so the old World Partition map and its 1,004 cells won't cook.
  - fable-streets' PCG rebuild may add more before 15:45.
- **`PackageJamBuild.bat` (done 15:2x):**
  - `-map=/Game/GrayLondon/Maps/MedievalLondon`.
  - `-build` is now the default. UAT builds the game target from the frozen code, because `reflections.exe` is from Sat 18:41 while train #24's editor DLL is from 15:05 (B2).
  - `--no-build` skips the build, and is refused while the exe is older than the DLL.
  - Both modes were tested with a dry run.
- **Checks:**
  - `DefaultEngine.ini:124` `SecurityToken=` is still blank.
  - `Crowd/Spots` (UFS) covers the new `MedievalLondon.json` (209 KB).
  - **`DA_PeopleBook` is still stale** (19:45 vs `people.json` 19:57), so the final run stops at the gate until lives re-imports it. `--allow-stale-people` is only for measuring.
  - `THIRD_PARTY_NOTICES.txt` still describes Gray London's assets (Codriver landmarks, the Albert scan, Minimaliano props), most of which no longer ship. The ODbL credit still applies, because MedievalOpening's ground and buildings are built from the OSM tiles. Submission prep should trim the notices to what ships.
- **Size estimate: about 1.25 GB zipped.** Method: today's cook roots (always-cook folders, `[AlwaysCookMaps]`, the map), walked through source name tables and priced at the 01:10 build's compressed sizes. 165 new packages are priced by their folder's ratio.

  | Part | MB |
  |---|---|
  | /Game content, down from 1,183 (−332 MB of Gray London and Geodata, +47 MB of new character work: Lanthorne 13.6, RedLondon 13.4, WhiteLondon 9.8) | ~898 |
  | Engine and plugin content | ~34 |
  | Shaders (London's +9.7 MB goes) | ~130 |
  | Exe and binaries | ~190 |
  | **Zip** | **≈ 1,250** |

  Still about 250 MB over 1 GB. Getting under needs the user's calls: Character cap 1024 (~−100), drop SM5 (~−68), voice at 12 kHz (~−51) or 16 kHz (~−34), and the Common dedupe (~−56, in `redlondon-untangle-plan.md`). Or upload with butler, if the jam allows over 1 GB.
- **Timing:**
  - Game-target build: ~5–20 min, unless it's built ahead now that the code is frozen.
  - Cook: ~8 min with a warm DDC.
  - Stage and pak: ~3 min.
  - Zip: ~2 min.
  - `MeasureJamBuild.ps1`: ~1 min.

0. **Start map switch. Superseded Sat 21:05:** London is the main map, and the mock city and `Lvl_HeroSampleCrowd` are deleted. See "Gray London cook plan" below. History: the real playthrough map is `/Game/MockCity/Lvl_MockCity`, which has the three sides, anchors, towers and pages. `Lvl_HeroSampleCrowd` has no world anchors, so world jump can't run there by design. Once the orchestrator and game flow confirm (game flow's `GameFlow.NewGameMap` lands in train #8), change the three places that name the start map:
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
   - J4: the orchestrator blanked the AndroidFileServer SecurityToken in `DefaultEngine.ini` (19:4x) for the local checkpoint commit.
   - NPC reaction clips and sounds (npc-unify, via the orchestrator, 19:4x): `/Game/Combat/Melee` and `/Game/NPC/Archetypes` were **already** in `DirectoriesToAlwaysCook`, and `/Game/Combat/Melee/Source` (Kimodo takes) is never-cooked. I checked the NPC code's string paths against the cook rules:
     - All 20 `BP_Look_*` built by `BP_Look_%s` are soft-referenced by the `DA_Npc_*` assets.
     - `BP_SampleCMCClean2` (the NPC driver) comes in through the always-cooked `BP_HeroSampleCleanTest`.
     - The `BP_WhiteLook_01/02` and SimpleRed fallbacks are only used when fewer than 2 finished looks exist.
     - No gaps.

   **Also measure the new NPC cast in that cook** (crowd-looks `local_ac448871`, Sat 18:4x):
   - `/Game/Characters/Lanthorne/` replaces the old spawn pools: 20 look Blueprints reached through soft refs in the always-cooked `/Game/NPC/Archetypes/DA_Npc_*`, 13 new MetaHumans plus 7 re-groomed faces. Uncooked it's ~1.4 GB plus 435 MB of `People/Common`; the grooms are 461 MB uncooked, strands included.
   - Report the cooked MB for `/Game/Characters/Lanthorne` against the **320 MB NPC budget** to crowd-looks. If it's over, crowd-looks cuts grooms first (cards-only strands), then the number of new faces.
   - Check these drop out of the pak: `/Game/Characters/CrowdMotion/SimpleRed` (once crowd swaps the 6 placed walkers), `/Game/Characters/WhiteLondon/CrowdPreview` (once squads read the archetype lists), and `RedLondon/Crowd/Variants`.
   - `COL_CrowdPrototype_CoinClerk` (108 MB uncooked): **done Sat 22:3x.** `/Game/Crowd/City` is out of `DirectoriesToAlwaysCook` (orchestrator, crowd plan rank 6; crowd-react agreed).
     - Checked first: `Crowd.Mass.Enable` defaults to 0, `Crowd.Mass.HostMap` and `Crowd.Mass.Level` are empty, and no config sets them. No other asset references the folder.
     - The chain it pulled in was `MEC_CityPedestrian` → `RedLondon/Crowd/Test/MI_CrowdPrototype_CoinClerk` → the collection, and nothing else that's always cooked reaches `Crowd/Test`.
     - Expect about 20–80 MB less in the measurement cook. Turning Mass on again needs the entry back.

   **Gray London cook plan** (orchestrator, Sat 20:5x). Jah's `/Game/GrayLondon/Maps/GrayLondon_Geodata` landed in the working copy at the 21:00 train. It becomes the main map once world-jump's integration passes. This was planned without the editor: from the LFS sizes on `origin/main` (`4aac7d0d`) and from the name tables of the landed files. Licences, trademarks and ODbL are covered in [gray-london-review.md](../Submission/gray-london-review.md).

   - **What's in it.** 3,620 packages, 376 MB:
     - 1,462 assets in `/Game/GrayLondon`;
     - 2,057 actor packages in `__ExternalActors__`: 1,926 static mesh actors, 721 HISM components, 110 PCG volumes, plus the sky, fog, lights and a PlayerStart;
     - 99 `__ExternalObjects__`.

     The placed actors reference essentially every asset in `/Game/GrayLondon`, so nearly all 376 MB cooks.
   - **Estimated cooked size: 250–470 MB, most likely ~350 MB**, against the 120 MB London budget. By part:

     | Part | Source | Cooked estimate | Why |
     |---|---|---|---|
     | Meshes | ~245 MB, ~6.5 M triangles (142 MB is the 117 city tiles, 4.0 M faces) | **150–260 MB** | No Nanite on the tiles. 188 meshes use **complex-as-simple collision**, all 117 tiles included (161 MB of source), so ~4.3 M triangles also cook as collision. Lightmap UVs are generated though static lighting is off. |
     | Textures | 105 assets, 102 MB | **60–100 MB** | `TEXTUREGROUP_World` / `WorldNormalMap`, so the 2048 cap in `DefaultDeviceProfiles.ini` applies. |
     | Shader code | 293 materials, **all base materials, no instances** | **+30–90 MB** | Each one compiles its own SM5 + SM6 shaders. Shader code is 134 MB for the whole game today. |
     | World Partition cells | 19 MB of actors | **10–20 MB** | HISM instance data (4,626 trees, 1,300 shopfronts, props) and the baked PCG instances. |
     | PCG graphs | 4.6 MB | ~0–3 MB | They look editor-only, so they're probably not cooked. That's harmless: see PCG below. |
   - **Package total.** 734 MB at train #5, plus unmeasured growth since then (the new NPC cast, the mock city, the villain), plus London: about **1.0–1.3 GB**. It's likely over 1 GB unless something is cut. Measure it in the first cook.
   - **Levers, biggest safe ones first:**
     1. **World texture cap 2048 → 1024** in `DefaultDeviceProfiles.ini` (`World`, `WorldNormalMap`, `WorldSpecular`). Config only, packaging's. About **−40 to −70 MB** from London. It also softens props up close. **Approved and staged Sat 21:2x.**
     2. **Drop SM5** (B6, the user's call): −65 MB now, plus about half of London's shader cost (**−80 to −110 MB** total).
     3. **Cut the shipped area** to the playable radius. The city plus its park ring is ~12.5 km across. This is the biggest lever; Jah and world-jump decide the radius.
     4. **Turn the 293 materials into instances of a few masters.** That removes most of London's shader cost. Asset work for the map owner, so probably not before Sunday.
     5. **Collision on the city tiles**, likely 40–70 MB of the mesh cost. Changing it affects walking, so not before Sunday.
     6. **The Albert Memorial scan** (19 MB source, 649k triangles) has to go for a sale anyway (provenance). Reverting it saves ~15 MB.
   - **PCG is baked: no runtime generation.**
     - All 110 PCG volumes (Green Park fences, the B01 awnings) are `GenerateOnDemand`.
     - All are `bGenerated`, with their `PCGManagedISMComponent` instances saved in the actor packages.
     - None are partitioned, and none use procedural instances.
     - The engine's `UPCGComponent::BeginPlay` only generates `GenerateOnLoad` components that aren't generated yet, so the packaged game shows the saved instances and runs no PCG.
     - Keep it that way. Don't switch them to `GenerateAtRuntime`: that needs the runtime scheduler, causes hitches near the player, and editor-only graphs wouldn't be in the pak.
   - **World Partition.**
     - The map uses a `WorldPartitionRuntimeHashSet` (a main LH grid partition plus a persistent one) and two HLOD layers, `_HLODLayer_Instanced` and `_HLODLayer_Merged`.
     - The cooker generates the streaming cells from the map and pulls in the actors and their assets itself. So **don't** add `/Game/GrayLondon` or `__ExternalActors__` to `DirectoriesToAlwaysCook`.
     - **The HLODs aren't built: 0 HLOD actors.** The cook doesn't build them, so in a package nothing beyond the loading range shows, and the skyline vanishes at distance. Fix, owned by Jah and world-jump, under a save freeze:
       - Build only the Instanced layer (WorldPartitionBuilderCommandlet, HLODs builder). It's cheap and writes new actor packages into the map.
       - Leave Merged unbuilt: it bakes meshes and textures, +20–80 MB.
       - Or set a few landmarks to not spatially loaded, so they're always present.
     - **There's no navmesh:** no `NavMeshBoundsVolume` and no `RecastNavMesh`. Without one, NPCs, squads and crowd lanes can't path in London, and neither can the playtest walker.
       - Dynamic navmesh around navigation invokers adds nothing to the cook.
       - A bounded volume over the playable area cooks nav data that grows with the area.
       - Owners: world-jump and NPC.
   - **Three Londons (world jump).** A World Partition map can't be a sublevel. So it's either duplicate-in-place (route A) or three maps (route B).
     - Route A: the side step must be about **1.3 M uu**, not 150000, because the city is ~12.5 km across.
     - Both routes share the meshes, so the cook cost is mostly actor packages: **+20–40 MB** for two more copies, more if Red and White get their own dressing.
     - Either way the destination cells have to stream in before the hero lands. The "all three loaded at once" assumption doesn't hold with World Partition.
   - **London is the main map (orchestrator, Sat 21:05).** `Lvl_MockCity` and `Lvl_HeroSampleCrowd` were deleted.
     - The orchestrator set `MapsToCook`, `NewGameMap`, `GameDefaultMap` and `EditorStartupMap` to `GrayLondon_Geodata`.
     - **Done Sat 21:2x (packaging):** `PackageJamBuild.bat` `-map=` is now only `/Game/GrayLondon/Maps/GrayLondon_Geodata`, and no old map name is left in the bat. Dry run checked.
     - Every `[AlwaysCookMaps]` package and `DirectoriesToAlwaysCook` folder still exists. The global game mode is still `ReflectionsSampleGameMode`, whose string-loaded pawn and controller stay always-cooked.
   - **Decisions (orchestrator, Sat 21:2x):**
     1. **World texture cap 1024: done.** `DefaultDeviceProfiles.ini` `[Windows DeviceProfile]` now caps `World`, `WorldNormalMap` and `WorldSpecular` at `MaxLODSize` / `MaxLODSize_VT` 1024. `Character*` stays at 2048, and the editor's own profile is unchanged. Side effect: any clothing, cloak or prop texture in a World group (the default group for imported textures) also cooks at 1K.
     2. **Measurement cook tonight at ~00:30, with the editor closed** (2.7 GB of free virtual memory), after train #14's tests. The orchestrator gives the window and closes the editor.
     3. **Dropping SM5:** the orchestrator is asking the user.
     4. **Instanced-only HLODs and the navmesh:** world-jump owns them (`local_830b60d0`). Numbers sent Sat 21:2x.
     5. **`DA_PeopleBook`:** re-imported in lives' row A.
     6. **Area trimming** waits for the measured size.
   - **Measurement cook runbook** (window ~01:00 Sun, after train #14 and its test rows; the orchestrator closes the editor and messages "cook window open"):
     1. Check: no `UnrealEditor.exe` or UBT is running. `reflections.exe` and `UnrealEditor-reflections.dll` both come from train #14 (B2). Post the freeze in `SAVE-FREEZE-STATUS.md`.
     2. `ArtDirection\Packaging\PackageJamBuild.bat --allow-stale-people`, in the background. The log is `Saved\JamBuild\Logs\uat_package.log`. The flag is only needed while `DA_PeopleBook` is stale, and a build made with it is for measuring only. Without the flag, the gate still stops the run (tested).
     3. `powershell -ExecutionPolicy Bypass -File ArtDirection\Packaging\ZipJamBuild.ps1 -Source Saved\JamBuild\Windows -Dest Saved\JamBuild\Zips\measure_london.zip`. `train5_Windows.zip` stays as the fallback.
     4. `powershell -ExecutionPolicy Bypass -File ArtDirection\Packaging\MeasureJamBuild.ps1 -Zip Saved\JamBuild\Zips\measure_london.zip`. **New, Sat 22:4x.** It reports:
        - the IoStore container by chunk type, with shader code separate;
        - Gray London by part (city tiles, other meshes, textures, materials, PCG graphs, World Partition cells);
        - the top 12 folders and the top 10 packages;
        - whether `Crowd/Spots/*.json` reached the `.pak`;
        - the zip and staged sizes.

        Tested on the train #5 stage: 539 MB container, 128 MB of it shader code, against a 734 MB zip.
     5. Read the cook log for errors and for "missing from cook" or "marked NeverCook" lines. Shader growth over train #5 (128 MB) is mostly London's 293 materials. Report London by part, the zip total and the top 5 contributors to the orchestrator, then end the freeze.
   - **Measurement cook result (Sun 00:59–01:10, editor closed, `--allow-stale-people`).**
     - **Zip: 1,544.9 MB (`Saved/JamBuild/Zips/measure_london.zip`), about 545 MB over 1 GB.** Container 1,355 MB compressed: 1,217 MB of assets plus 137.7 MB of shader code. Staged 1,898 MB.
     - Cook 495 s, stage and pak 185 s, 12,380 packages, **0 errors**. Six warnings, all `SetControlRigClass` deprecations in old `ABP_Clothing_PostProcess`.
     - Not for upload: the people book was stale, and `reflections.exe` (Sat 18:41) doesn't match the 00:32 editor DLL.
     - Everything requested is in: crowd spots JSON (1 file), canal crate plus texture, `M_Relaxed_Stand_Idle_Break_v01–v08`, `Idle_Loop`, the bench clips, and the 1,004 generated World Partition cells. `/Game/Crowd/City` and `COL_CrowdPrototype_CoinClerk` are out. Nothing from the mock city or `Lvl_HeroSampleCrowd`.
     - **Gray London: 335 MB** (estimate was 250–470, ~350 likely), plus only **+9.7 MB** of shader code over train #5. By part:

       | Part | MB | Packages |
       |---|---|---|
       | City tiles | 212.9 | 117 |
       | Other meshes (landmarks, props, markings) | 83.1 | 838 |
       | Textures, at the 1024 cap | 35.2 | 128 |
       | World Partition cells + map | 2.6 | 1,005 |
       | Material assets | 1.2 | 397 |
       | PCG graphs | 0.3 | 128 |

       The single biggest package is `albert_memorial_sequential_35`, 20.7 MB.
     - **Top 5 contributors, compressed MB:**
       1. `/Game/Characters/Lanthorne`, the new NPC cast: **328.6** (`People/Common` 65.4, then ~20–22 per person).
       2. `/Game/GrayLondon`: **335** (`Geodata` 297, `External` 28).
       3. `/Game/Characters/RedLondon`, the **old NPC pools, still cooked**: **206.2** (`BridgeGuard` 72.4, `CoinClerk` 69.5, then `FerryPilot`, `FestivalDrummer`, `GlassArtisan` and `ArchiveApprentice` at ~15–18 each). What pulls them in:
          - 51 always-cooked `/Game/Characters/CrowdMotion/ABP_Crowd_*`;
          - 20 `/Game/Combat/Melee/AS_Melee_*_BridgeGuard`/`_CoinClerk` clips;
          - `/Game/Squads/Animation/AS_Soldier_March_BridgeGuard`;
          - 63 Lanthorne assets, such as `SKM_MHC_FerryPilotGiltWorker_BodyMesh` and the Gilt worker clothing.
       4. `/Game/Audio/Jam`: **113.7**, of which `Voice` is **103.5** in 8,313 packages. It was 12 MB at train #5, against a 20 MB budget.
       5. `/Game/Characters/WhiteLondon`: **63.5** (`IvenRook` 61.8).

       Also: grooms are 121.6 MB across all characters, and `UE5_Mannequins` is new at 24.1 MB, 20 MB of it textures.
   - **Cook time.**
     - The first cook with London is cold: SM5 shaders for 293 materials (the editor only compiled SM6) and 4.3 M triangles of collision. Expect **+15–40 min** on that first cook.
     - So the "~25 min" final estimate doesn't hold for it. Run a measurement cook early, first thing Sunday or tonight if the orchestrator allows it, under a save freeze.
   - **Done Sat 21:1x:** `PackageJamBuild.bat` copies [THIRD_PARTY_NOTICES.txt](../Submission/THIRD_PARTY_NOTICES.txt) next to `reflections.exe`, which puts it in the zip's top folder. It warns while the notices still have `[CONFIRM]` items. Tested with a dry run.
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
