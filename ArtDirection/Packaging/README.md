# Test packaging: Win64 Development jam build

Status as of **2026-11-14 ~10:35 local (Sat)**. Deadline is Sun Nov 15, 8:59 PM ET (team target 6 PM ET = 4 PM local). itch.io needs a zip under 1 GB.

**Bottom line:** the packaged build **works**.

- **Build:** made from train #2's matched editor DLL and game exe (10:19). The cook had **0 errors**.
- **Test run:** `Lvl_HeroSampleCrowd` loads in 0.6 s. The hero spawns in the new drape coat, the crowd animates, the spell HUD and health/mana work, and the game log has 0 errors.
- **Zipped size: 729 MB** (baseline 1,756 MB). Staged: 1,062 MB.
- **Screenshot:** `Saved/JamBuild/Logs/launch_matched.png`. Package: `Saved/JamBuild/Windows/`. Zip: `Saved/JamBuild/Zips/matched_Windows.zip`.

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
   It copies `NeverCookList.txt` to `%TEMP%` first, because the cooker's command line can't take a path with spaces. Use `--dry-run` to print the command without running it. The cook takes ~1–3 min with a warm DDC; staging takes ~2 min. The log goes to `Saved/JamBuild/Logs/uat_package.log`.
4. **End the freeze** once the log shows `COOK COMMAND COMPLETED`.
5. **Launch-test:** run `Saved/JamBuild/Windows/reflections.exe -windowed`, then check `Saved/JamBuild/Windows/reflections/Saved/Logs/reflections.log` for `Error:` and `Fatal`.
6. **Zip** the `Windows` folder with Explorer's "Compressed (zipped) folder" or .NET `ZipFile` (deflate). Don't use `tar -a -cf x.zip`: it stored the files uncompressed here.

To list what's in the pak: `"C:\Program Files\Epic Games\UE_5.9\Engine\Binaries\Win64\UnrealPak.exe" -ListContainer="<stage>\Windows\reflections\Content\Paks\reflections-Windows.utoc" -csv=out.csv`

## Sizes

| Build | Cooked packages | Content paks | Staged | **Zip** |
|---|---|---|---|---|
| Baseline: no packaging settings (09:00) | 1,563 | 1,461 MB | 2,330 MB | **1,756 MB** |
| Packaging settings only (09:13) | 3,166 | 554 MB\* | 1,465 MB | 892 MB |
| + editor-only toolsets, no `/Game/Worlds` (verification, 10:06) | 3,313 | 649 MB | 1,156 MB | 823 MB |
| **+ NNEDenoiser out, matched train #2 build (10:26)** | 3,306 | 554 MB | 1,062 MB | **729 MB** |

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
| Crowd / NPC MetaHumans (user, Codex NPC combat) | 301 MB | **320 MB** | `RedLondon` 199, `WhiteLondon` 82. **Each extra MetaHuman costs ~50–60 MB** even with the 2K texture cap. |
| Shader code (all materials, SM5 + SM6) | 134 MB | **160 MB** | Grows with every new material, especially the London map's. |
| Hero body, cloak, GASP locomotion (hero-cloak, spell-combat) | 89 MB | **100 MB** | `UEFN_Mannequin` (motion-matching animations) is 48 MB of it. |
| Engine + plugin content | 13 MB | **15 MB** | |
| London map / level art (map teammate) | 9 MB | **120 MB** | Not in this map yet. |
| Audio | 12 MB | **20 MB** | |
| Spells + VFX, spell crafting, world jump | 3 MB | **15 MB** | |
| Binaries (fixed) | 187 MB | 187 MB | |
| **Total** | **729 MB** | **937 MB** | ~60 MB of headroom under 1,000 MB. |

If the total runs over: drop SM5 (DX11) shaders, about −65 MB (`DefaultEngine.ini` `D3D11TargetedShaderFormats`, which loses the DX11 fallback), or lower the `Character*` texture cap in `Config/DefaultDeviceProfiles.ini` from 2048 to 1024 (about −100 MB, softer faces up close).

## What changed

### `Config/DefaultGame.ini`, `[/Script/UnrealEd.ProjectPackagingSettings]` (additive)

- `+MapsToCook=Lvl_HeroSampleCrowd`, so the editor's Package Project cooks only the start map.
- `+DirectoriesToAlwaysCook` for folders C++ loads by **string path at runtime**, which the cooker can't see:
  - `/Game/Characters/Hero/Gameplay`: `BP_HeroPlayer` (spell defaults) and `BP_HeroAnimation`
  - `/Game/Characters/Hero/Animation/CombatCasts`, `/Game/Characters/Hero/SpellVFX`, `/Game/Input`
  - `/Game/Blueprints/Combat/Blood`
  - `/Game/Characters/WhiteLondon/IvenRook/MetaHuman/Animation/ElementalSpells/FX`
  - `/Game/Audio/Jam`, `/Game/SpellCrafting` and `/Game/Worlds`, at their owners' request
  - `/Game/Characters/CrowdMotion` was already listed.
  
  Every folder was checked: none references the broken `action_fighting` chain.
- `+DirectoriesToNeverCook`:
  - `/MetaHuman/GenericTracker` and `/MetaHumanCoreTech/GenericTracker`: ~580 MB of face-tracking ML models that no cooked package references.
  - `/Game/Worlds/Test`, `CombatCasts/Rigs` and `CombatCasts/Soma`: their owners confirmed they aren't used at runtime, and nothing references them.
- Compression: `PackageCompressionMethod=Leviathan`, levels `DebugDevelopment=7`, `TestShipping=7` (engine default: Kraken 4).

### `Config/DefaultEditor.ini`, new `[AlwaysCookMaps]` section

`+Map=/Game/Characters/Hero/Sample/BP_HeroSampleCleanTest` and `+Map=.../BP_SampleControllerClean`. `ReflectionsSampleGameMode::InitGame` loads the map's real pawn and controller by string path. The cooker requests any package listed there on every cook (`CookOnTheFlyServer.cpp`, `GCookRequestUsageMessage`). Their folder can't be always-cooked as a whole: `GM_HeroSample` there pulls in the broken chain.
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
| B9 | Save freezes around every packaging cook | Packaging announces; all sessions honour | In place |
| B10 | Disk: ~41 GB free on C:. Each package needs ~1.1 GB staged + ~0.75 GB zipped. My test copy and intermediate zips are already deleted; `Saved/JamBuild/Zips` keeps only the baseline and matched zips. | Packaging | OK |

## Sunday plan

1. **Rehearsal:** after any build train Sunday morning, run steps 1–6 above end to end and check the zip against the budget.
2. **Final:** at the last build train before the 4 PM local target (6 PM ET), freeze content and source, then run steps 1–6. That's ~25 min including the train.
   - Zip as `TeamName_GameName.zip`, then upload.
   - Leave at least 2 hours before 4 PM local for a second attempt.
3. If the zip is over 1,000 MB, apply the fallbacks under the budget table, then re-run steps 3–6.
