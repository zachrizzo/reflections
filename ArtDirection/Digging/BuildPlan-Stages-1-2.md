# Full Digging, Stages 1 and 2: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Reflections a dig action with saved dig spots (stage 1) and a 48 x 48 m diggable voxel patch that proves or kills full digging (stage 2).

**Architecture:** A versioned save file holds dig state. Stage 1 is an authored dig-spot actor driven by a dig component on the player pawn. Stage 2 is one grid of ground data (density and material per cell); a dig edits the grid, worker tasks re-mesh the touched chunks with surface nets, and a per-frame budget commits the results to `UDynamicMeshComponent` chunks with their own collision.

**Tech Stack:** Unreal Engine 5.9 C++ (module `reflections`), Enhanced Input, `UDynamicMeshComponent` (GeometryFramework), Unreal automation tests, Unreal Python for the test map.

**Spec:** the Claude Doc "Reflections full digging plan" (https://claude.ai/artifact/Kco5jg6MqxCsjaiYE2XVrr), which follows `ArtDirection/Digging/Feasibility.md` section 7.1 in the main checkout. This file is the buildable form of that doc's stage 1 and stage 2 tasks. Where it differs from the doc, the difference is a recorded ruling in the ledger (`.superpowers/sdd/BuildPlan-Stages-1-2/progress.md`).

## Global Constraints

- **Where you work:** only inside the worktree `C:\Users\zachc\Documents\Unreal Projects\reflections\.worktrees\digging`, branch `claude/digging-stages-1-2`. Never read-modify anything in the main checkout above it. Never use the running Unreal editor, `unreal-mcp` tools, or PIE: the editor on this machine belongs to other sessions.
- **The worktree is sparse.** It holds `Source/`, `Config/`, `ArtDirection/Digging/`, `Tools/Digging/` and `Content/Maps/DigSpike/` only. The rest of `Content/` is absent, so game Blueprints and the Test Town map do not exist here. Use engine content (`/Engine/BasicShapes/...`) in tests and in the map.
- **Build:** only with `powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\zachc\Documents\Unreal Projects\reflections\.worktrees\digging\.superpowers\bin\build.ps1"`. A pass prints `BUILD OK`.
- **Editor-context tests:** only with `powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\zachc\Documents\Unreal Projects\reflections\.worktrees\digging\.superpowers\bin\test.ps1" -Filter <prefix>`. A pass prints `TESTS: N ran, N passed, 0 failed` with N > 0 and `automation warnings/errors logged: 0`.
- **Game-context tests** (tasks 2.4 onward): the same script with `-Game -Map /Game/Maps/DigSpike/L_DigSpike`. Add `-Render` only where a task says so. The wrapper caps a game-context run at 60 frames a second (`t.MaxFPS 60`); without the cap a game process with no renderer runs at about 1000, and a test counted in frames means nothing.
- **Editor Python** (the map script): only with `...\.superpowers\bin\editor-python.ps1 -Script <path>`.
- **If any wrapper prints `REFUSED` or `ABORTED` (exit 75), stop and report BLOCKED.** That means a project build train is running. Never call `Build.bat`, UnrealBuildTool, `UnrealEditor.exe` or `UnrealEditor-Cmd.exe` directly.
- **Engine:** UE 5.9 at `C:\Program Files\Epic Games\UE_5.9`. Engine source is readable there. Check real headers before using an engine API; names and flags changed between versions.
- **Module rules:** `reflections` has `bUseUnity = false` and explicit PCHs. Every `.cpp` includes its own header first and then everything it uses. Types used across files carry `REFLECTIONS_API`.
- **Names:** classes are `AReflections...`, `UReflections...`, `FReflections...`; namespaces are `ReflectionsSave`, `ReflectionsDig`, `ReflectionsDigMesher`.
- **Files:** new code goes under `Source/reflections/Save/` and `Source/reflections/Digging/`, tests in a `Tests/` folder beside the code, tools under `Tools/Digging/`, assets under `Content/Maps/DigSpike/`. Existing files are edited only where a task lists them.
- **Tests:** Unreal automation tests named `Reflections.*`, inside `#if WITH_DEV_AUTOMATION_TESTS`. Output must be clean: a deliberate warning or error is declared with `AddExpectedError`.
- **Save slots in tests:** tests never touch the real slot `Reflections`. They use slot `ReflectionsTest` and delete it before and after.
- **Fixed numbers:** cell 50 cm; chunk 32 cells (16 m); density is `int8`, positive is solid, range -127 to 127; `DensityPerCell = 64`; `SampleBorder = 2`; topsoil material 0; bedrock material 255; dig radius 100 cm; reach 250 cm; commit budget default 2 per frame; mesh radius 2400 cm; a chunk piece holds at most 12,000 vertices.
- **Scope limits:** single-player only, no replication. No third-party code, no new plugins, no `.uproject` change.
- **Git:** one commit per task (a fix round adds a commit). Stage only the task's files by path, never `git add -A`. Never stash, reset, rebase, switch branches or push. Commit messages are one plain sentence in the imperative ("Add a versioned save with a checked file format") and end with a `Co-Authored-By:` line naming the model that wrote the commit (for an Opus subagent: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`).

## Review Focus

1. **The ground is dug out from under the hero.** They land on the new surface or on bedrock, never outside the world. Pinned by `Reflections.Digging.Grid.BedrockCannotBeRemoved` (2.1) and `Reflections.DigSpike.DigDownToBedrock` (2.4).
2. **The dig key is held down.** Work stays bounded and the newest state wins. Pinned by the queue tests and `Reflections.Digging.Terrain.HeldDigStaysBounded` (2.3).
3. **A dig overlaps the edge of the patch.** The stamp is clipped and the side walls stay closed. Pinned by `StampHalfOutsideIsClipped` and `SideWallsAreBedrock` (2.1).
4. **The save file is corrupt, cut short, or from a newer build.** It is refused and left untouched, and later digs do not overwrite it. Pinned by `RefusesNewerVersion`, `CorruptFileIsRefused`, `TruncatedFileIsRefused`, `UpdateLeavesBadFileAlone` (1.1) and `BadSaveDoesNotBlockDigging` (1.3).
5. **A chunk is dug while its collision is still cooking.** The old floor stays until the new one is ready. Pinned by `Reflections.DigSpike.FloorStaysWhileCollisionRecooks` (2.4).

---

### Task 1.1: Versioned save

**Files:**
- Create: `Source/reflections/Save/ReflectionsSaveGame.h`, `Source/reflections/Save/ReflectionsSaveGame.cpp`
- Test: `Source/reflections/Save/Tests/ReflectionsSaveTests.cpp`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces:
  - `UCLASS() class REFLECTIONS_API UReflectionsSaveGame : public USaveGame` with `UPROPERTY() int32 SaveVersion` (defaults to 1), `UPROPERTY() TMap<FName, uint8> DigSpotStages`, `UPROPERTY() TArray<uint8> DigTerrainBlob` (unused until stage 3).
  - `enum class EReflectionsLoadResult : uint8 { Loaded, NoFile, NewerVersion, Corrupt }`.
  - `namespace ReflectionsSave`:
    - `inline constexpr int32 LatestVersion = 1;`
    - `REFLECTIONS_API extern const FString DefaultSlot;` with value `"Reflections"`
    - `REFLECTIONS_API const FString& ActiveSlot();` returns `DefaultSlot` unless an override is alive
    - `REFLECTIONS_API bool Write(const UReflectionsSaveGame& Data, const FString& Slot);`
    - `REFLECTIONS_API EReflectionsLoadResult Read(const FString& Slot, UReflectionsSaveGame*& OutData);`
    - `REFLECTIONS_API bool Update(TFunctionRef<void(UReflectionsSaveGame&)> Mutate);`
    - `struct REFLECTIONS_API FScopedSlotOverride` with `explicit FScopedSlotOverride(const FString& Slot)` and a destructor that restores the previous slot; not copyable.

**File format (exact).** The slot holds raw bytes written with `UGameplayStatics::SaveDataToSlot(Bytes, Slot, 0)`: four little-endian `uint32` values, then the payload.

| Offset | Value |
|---|---|
| 0 | magic `0x52464C53` |
| 4 | save version, taken from `Data.SaveVersion` |
| 8 | payload length in bytes |
| 12 | `FCrc::MemCrc32` of the payload |
| 16 | payload: the bytes from `UGameplayStatics::SaveGameToMemory` |

**Read rules.**
- Slot does not exist: return `NoFile`; `OutData` is a new empty save at version 1. Nothing is written.
- Fewer than 16 bytes, or wrong magic: `Corrupt`, `OutData = nullptr`.
- Header version greater than `LatestVersion`: `NewerVersion`, `OutData = nullptr`. This is checked before length and CRC.
- Length does not match the bytes present, CRC mismatch, or the payload does not load as a `UReflectionsSaveGame`: `Corrupt`, `OutData = nullptr`.
- Otherwise `Loaded`, and `OutData->SaveVersion` is the header version.
- `Read` never writes, deletes or renames the file.

**Update rules.** `Update` reads `ActiveSlot()`. On `Loaded` or `NoFile` it calls `Mutate`, writes the result to `ActiveSlot()` and returns the write result. On `NewerVersion` or `Corrupt` it does not call `Mutate`, does not write, logs one `LogReflectionsSave` warning on every such call and returns false. (No once-per-run limit: other tests in the same process expect the same warning.)

- [ ] **Step 1: Write seven failing tests** in `ReflectionsSaveTests.cpp`, all on slot `ReflectionsTest`, each deleting the slot before and after:
  - `Reflections.Save.RoundTrip`: write `DigSpotStages = {Well: 2}`; `Read` returns `Loaded`, the value is 2 and `SaveVersion` is 1.
  - `Reflections.Save.NoFileStartsEmpty`: `Read` returns `NoFile`; `OutData` is non-null, version 1, both containers empty; the slot still does not exist afterwards.
  - `Reflections.Save.RefusesNewerVersion`: `Write` a save with `SaveVersion = 2`; `Read` returns `NewerVersion` with null `OutData`; the slot's raw bytes are identical before and after.
  - `Reflections.Save.CorruptFileIsRefused`: store 256 bytes from `FRandomStream(1234)`; `Read` returns `Corrupt` with null `OutData`; bytes unchanged.
  - `Reflections.Save.TruncatedFileIsRefused`: write a valid save with 50 entries, cut its raw bytes to half, store them; `Read` returns `Corrupt`.
  - `Reflections.Save.UpdateWritesThroughActiveSlot`: inside `FScopedSlotOverride("ReflectionsTest")`, `Update` adding `Pump: 1` returns true; a second `Update` adding `Well: 2` returns true and a `Read` shows both entries; after the override leaves scope `ActiveSlot()` equals `DefaultSlot`.
  - `Reflections.Save.UpdateLeavesBadFileAlone`: with the override alive, once with the 256 random bytes and once with a version 2 file: `Update` returns false, `Mutate` is not called, bytes unchanged. Declare the expected warning with an exact count of 2.
- [ ] **Step 2: Build and run** `test.ps1 -Filter Reflections.Save`. Expected: the build fails on the missing symbols, or the tests fail. Record that output as the RED evidence.
- [ ] **Step 3: Implement** `ReflectionsSaveGame.h/.cpp` to the interface, format and rules above.
- [ ] **Step 4: Build and run** `test.ps1 -Filter Reflections.Save`. Expected: `TESTS: 7 ran, 7 passed, 0 failed`. (A later review pass added an eighth test, `Reflections.Save.VersionZeroIsCorrupt`.)
- [ ] **Step 5: Commit** the three files.

---

### Task 1.2: Dig-spot actor

**Files:**
- Create: `Source/reflections/Digging/ReflectionsDigSpot.h`, `Source/reflections/Digging/ReflectionsDigSpot.cpp`
- Create: `Source/reflections/Digging/Tests/ReflectionsDigTestWorld.h` (test helper, header only, inside `#if WITH_DEV_AUTOMATION_TESTS`)
- Test: `Source/reflections/Digging/Tests/ReflectionsDigSpotTests.cpp`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces:
  - `UCLASS() class REFLECTIONS_API AReflectionsDigSpot : public AActor` with
    - `UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Digging") FName SpotId;`
    - `UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Digging") TArray<TObjectPtr<UStaticMesh>> StageMeshes;` index 0 is untouched ground, the last is fully dug
    - `UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Digging") TSubclassOf<AActor> BuriedFindClass;`
    - `UFUNCTION(BlueprintCallable, Category = "Digging") bool DigOnce();`
    - `UFUNCTION(BlueprintPure, Category = "Digging") int32 GetStage() const;`
    - `UFUNCTION(BlueprintCallable, Category = "Digging") void SetStage(int32 NewStage);`
    - `UStaticMeshComponent* GetMeshComponent() const;` the root component, collision profile `BlockAll`
  - `struct FReflectionsDigTestWorld` (not copyable): the constructor creates a game-type `UWorld` with a physics scene, registers it with `GEngine` and begins play; the destructor destroys it. Members: `UWorld* World`, `void Tick(int32 Frames = 1, float DeltaSeconds = 1.0f / 60.0f)`, `template <typename T> T* Spawn(const FVector& Location = FVector::ZeroVector, const FRotator& Rotation = FRotator::ZeroRotator)`, and `template <typename T> T* SpawnDeferred(...)` with a matching `FinishSpawning`.

**Behaviour.** The last stage is `max(0, StageMeshes.Num() - 1)`.
- `DigOnce`: at the last stage, or with no meshes, it returns false and changes nothing. Otherwise it adds one to the stage, shows `StageMeshes[Stage]`, and returns true. On reaching the last stage it spawns one `BuriedFindClass` actor at the spot's transform, if the class is set. It never spawns a second one.
- `SetStage`: clamps to 0..last, shows that mesh, and never spawns the find (landing on the last stage uses it up). Whether a spot restored from a save gives its find again is decided by the restore in task 1.4, not by `SetStage`.
- `MarkFindCollected` (`UFUNCTION(BlueprintCallable, Category = "Digging")`): records the spot's id in `UReflectionsSaveGame::DigSpotFindsCollected` (`UPROPERTY() TSet<FName>`, no version bump) through `ReflectionsSave::Update` and remembers it locally; a no-op for a spot without an id. Whatever takes the find calls it.
- A placed or spawned spot shows `StageMeshes[0]` (`OnConstruction` and `BeginPlay`).

- [ ] **Step 1: Write five failing tests**, each in an `FReflectionsDigTestWorld`, with the three stage meshes `/Engine/BasicShapes/Cube.Cube`, `/Engine/BasicShapes/Cone.Cone`, `/Engine/BasicShapes/Cylinder.Cylinder`:
  - `Reflections.DigSpot.AdvancesOneStagePerDig`: starts at stage 0 showing mesh 0; each `DigOnce` returns true and moves to stage 1 then 2, showing mesh 1 then 2.
  - `Reflections.DigSpot.StopsAtLastStage`: after two digs, a third returns false and the stage stays 2.
  - `Reflections.DigSpot.SetStageClamps`: `SetStage(9)` gives 2; `SetStage(-1)` gives 0.
  - `Reflections.DigSpot.SpawnsBuriedFindOnce`: with `BuriedFindClass = ATargetPoint::StaticClass()`, the world holds 0 target points after the first dig, 1 after the second, still 1 after a third; a second spot taken to stage 2 with `SetStage` spawns none.
  - `Reflections.DigSpot.NoMeshesMeansNothingToDig`: with empty `StageMeshes`, `DigOnce` returns false and `GetStage` is 0.
- [ ] **Step 2: Build and run** `test.ps1 -Filter Reflections.DigSpot`. Record the failure as RED evidence.
- [ ] **Step 3: Implement** the actor and the test-world helper.
- [ ] **Step 4: Build and run** `test.ps1 -Filter Reflections.DigSpot`. Expected: 5 ran, 5 passed.
- [ ] **Step 5: Commit** the four files.

---

### Task 1.3: Hero dig input

**Files:**
- Create: `Source/reflections/Digging/ReflectionsDigComponent.h`, `Source/reflections/Digging/ReflectionsDigComponent.cpp`
- Modify: `Source/reflections/Hero/ReflectionsHeroCharacter.h` and `.cpp`: create the component in the constructor, beside `HeroVisual` and `SpellPreview`
- Modify: `Source/reflections/Hero/ReflectionsSampleGameMode.h` and `.cpp`: override `SetPlayerDefaults(APawn* PlayerPawn)`, call `Super`, then `UReflectionsDigComponent::EnsureOnPawn(PlayerPawn)`
- Test: `Source/reflections/Digging/Tests/ReflectionsDigComponentTests.cpp`

**Why two attach points.** The live player pawn is the Blueprint `BP_HeroSampleCleanTest`, spawned by `AReflectionsSampleGameMode` (the project's default game mode). It is not an `AReflectionsHeroCharacter`, and its Blueprint cannot be edited from this worktree. The game mode therefore adds the component at runtime.

**Interfaces:**
- Consumes: `AReflectionsDigSpot::DigOnce`, `GetStage`, `SpotId` (task 1.2); `ReflectionsSave::Update` (task 1.1); `FReflectionsDigTestWorld` (task 1.2).
- Produces: `UCLASS(ClassGroup = (Digging), meta = (BlueprintSpawnableComponent)) class REFLECTIONS_API UReflectionsDigComponent : public UActorComponent` with
  - `UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Digging", meta = (ClampMin = "0", Units = "cm")) float ReachCm = 250.0f;`
  - `UFUNCTION(BlueprintCallable, Category = "Digging") bool TryDig();`
  - `static UReflectionsDigComponent* EnsureOnPawn(APawn* Pawn);` null pawn returns null; an existing component is returned as is; otherwise one is created, registered and returned.

**`TryDig` rules.**
- The view point is the pawn controller's `GetPlayerViewPoint`, or the pawn's `GetActorEyesViewPoint` when it has no controller.
- Trace `ECC_Visibility` along the view direction, ignoring the pawn and every actor attached to it (`GetAttachedActors`, recursive), the way `UReflectionsSpellAimComponent` does (`Source/reflections/Hero/ReflectionsSpellAim.cpp`, around line 189).
- The trace starts level with the pawn, not at the camera: `Start = ViewLocation + ViewDirection * max(0, dot(PawnLocation - ViewLocation, ViewDirection))`, and `End = Start + ViewDirection * ReachCm`. Nothing between a third-person camera and the pawn can be hit. This geometry lives in `static void UReflectionsDigComponent::ComputeReachTrace(const FVector& ViewLocation, const FVector& ViewDirection, const FVector& PawnLocation, float ReachCm, FVector& OutStart, FVector& OutEnd)` so it can be tested without a camera.
- A hit counts only if the impact point is within `ReachCm` of the pawn's actor location.
- On an `AReflectionsDigSpot`: call `DigOnce`. If it returned true and `SpotId` is not `NAME_None`, call `ReflectionsSave::Update` to set `DigSpotStages[SpotId]` to the new stage. Return what `DigOnce` returned; a failed save does not change the return value.
- Anything else: return false.

**Input.** Build an `IA_Dig` boolean action and an `IMC_Digging` mapping context in code with `NewObject`, the way `UReflectionsSampleSpellDriver::BindControls` does (`Source/reflections/Hero/ReflectionsSampleSpellDriver.cpp`, lines 277 to 330): key `EKeys::G`, `bConsumeInput` true, mapping context priority 1, `ETriggerEvent::Started` calls `TryDig`. Bind only for a locally controlled pawn with a player controller: try in `BeginPlay`, and if there is no controller yet, bind when the pawn's controller changes. Remove the mapping context in `EndPlay`. The component does not tick.

- [ ] **Step 1: Write the failing tests** (six at first, nine after review), each in an `FReflectionsDigTestWorld`, inside `FScopedSlotOverride("ReflectionsTest")`, deleting that slot before and after. The spot sits at the origin with the three engine stage meshes; the pawn is an `ADefaultPawn` with `BaseEyeHeight = 0` unless stated, with the component added by `EnsureOnPawn`, facing +X:
  - `Reflections.DigInput.DigsSpotInReach`: pawn at (-150, 0, 0); `TryDig` returns true, the spot is at stage 1, and the save holds the spot's id with value 1.
  - `Reflections.DigInput.IgnoresSpotOutOfReach`: pawn at (-400, 0, 0); `TryDig` returns false, stage 0, and no save file exists.
  - `Reflections.DigInput.NothingHitReturnsFalse`: pawn at (-150, 0, 0) facing -X; false.
  - `Reflections.DigInput.SpotWithoutIdDigsButIsNotSaved`: `SpotId` is `NAME_None`; `TryDig` returns true, stage 1, no save file.
  - `Reflections.DigInput.EnsureOnPawnAddsExactlyOne`: two calls return the same pointer and the pawn has one such component; a null pawn gives null.
  - `Reflections.DigInput.BadSaveDoesNotBlockDigging`: the slot holds 256 random bytes; `TryDig` returns true, stage 1, and the bytes are unchanged. Declare the expected warning (exact count 1, matching the refusal text).
  - `Reflections.DigInput.ReachIsMeasuredFromThePawn` (added in review): with `BaseEyeHeight = 300` and the pawn at (-150, 0, -300), `TryDig` returns false (the cube face is about 316 cm from the pawn). With `BaseEyeHeight = 100` and the pawn at (-150, 0, -100) it returns true.
  - `Reflections.DigInput.TraceStartsLevelWithThePawn` (added in review): `ComputeReachTrace` with the view at (-565, 0, 100), direction +X, pawn at (-150, 0, 0), reach 250 gives start (-150, 0, 100) and end (100, 0, 100). With the view at (50, 0, 0), ahead of the pawn, the start is the view location itself.
  - `Reflections.DigInput.IgnoresActorsAttachedToThePawn` (added in review): a blocking cube actor (scale 0.2) attached to the pawn 60 cm in front of it, between the pawn and the spot; `TryDig` still returns true and the spot is at stage 1.
- [ ] **Step 2: Build and run** `test.ps1 -Filter Reflections.DigInput`. Record RED.
- [ ] **Step 3: Implement** the component, the hero constructor line and the game mode override.
- [ ] **Step 4: Build and run** `test.ps1 -Filter Reflections`. Expected: all tests from tasks 1.1 to 1.3 pass (22).
- [ ] **Step 5: Commit** the listed files. In the report, say plainly that the `G` key binding itself is not covered by a test and needs a manual check in the real editor.

---

### Task 1.4: One dig site that survives a save

**Files:**
- Modify: `Source/reflections/Digging/ReflectionsDigSpot.cpp` (and `.h` if needed): `BeginPlay` restores the stage from the save
- Modify: `Source/reflections/Digging/Tests/ReflectionsDigSpotTests.cpp`: two more tests
- Create: `Tools/Digging/build_dig_spike_map.py`
- Create by running the script: `Content/Maps/DigSpike/L_DigSpike.umap`
- Test: `Source/reflections/Digging/Tests/ReflectionsDigSpikeMapTests.cpp`

**Interfaces:**
- Consumes: `ReflectionsSave::Read`, `ActiveSlot`, `FScopedSlotOverride` (1.1); `UReflectionsDigComponent::TryDig`, `EnsureOnPawn` (1.3).
- Produces: the map `/Game/Maps/DigSpike/L_DigSpike`, and a script that rebuilds it from nothing. Tasks 2.4 and 2.5 extend both.

**`BeginPlay` rule.** If `SpotId` is not `NAME_None`, call `ReflectionsSave::Read(ReflectionsSave::ActiveSlot(), Data)`. On `Loaded` with an entry for `SpotId`, call `SetStage` with it; in every other case the spot stays at stage 0. If the restored stage is the last stage, `BuriedFindClass` is set and `SpotId` is not in `DigSpotFindsCollected`, the find was uncovered but never taken: spawn it once, at the spot's location and rotation with unit scale, through the same code a live dig uses. If the id is in that set, spawn nothing. `BeginPlay` never writes.

**Map contents (exact).** The script always builds a new level and overwrites the map file.

| Actor label | Class | Placement and settings |
|---|---|---|
| `DigSpike_Ground` | `StaticMeshActor` | mesh `/Engine/BasicShapes/Cube`, location (0, 0, -50), scale (100, 100, 1), so the top is at Z = 0 |
| `DigSpike_Sun` | `DirectionalLight` | rotation pitch -45, yaw 30; movable |
| `DigSpike_Sky` | `SkyAtmosphere` | defaults |
| `DigSpike_SkyLight` | `SkyLight` | movable, real-time capture on |
| `DigSpike_Start` | `PlayerStart` | location (-600, 0, 100), facing +X |
| `DigSpike_SpotA` | `AReflectionsDigSpot` | location (0, -300, 50), `SpotId = DigSpike_A`, stage meshes Cube, Cone, Cylinder from `/Engine/BasicShapes/` |
| `DigSpike_SpotB` | `AReflectionsDigSpot` | location (0, 300, 50), `SpotId = DigSpike_B`, the same three meshes |

The map uses the project's default game mode; it sets no override.

- [ ] **Step 1: Write two failing tests** in `ReflectionsDigSpotTests.cpp`, inside `FScopedSlotOverride("ReflectionsTest")`:
  - `Reflections.DigSpot.RestoresStageFromSave`: the slot holds `{SpikeA: 2}`. Spawn deferred a spot with `SpotId = SpikeA`, three meshes and `BuriedFindClass = ATargetPoint::StaticClass()`, and a second with `SpotId = SpikeB`. After `BeginPlay`, A is at stage 2 showing mesh 2 with one target point in the world (its find was never taken), and B is at stage 0. The final fix wave adds `RestoredLastStageGivesUntakenFind`, `RestoredTakenFindIsNotGivenAgain`, `MarkFindCollectedSurvivesReload` and `BadSaveLeavesTheSpotUntouched`.
  - `Reflections.DigSpot.DigTwiceThenReloadKeepsStage`: in world 1 a pawn with the dig component digs spot `SpikeA` twice with `TryDig`. Destroy the world. In world 2, a new `SpikeA` spot begins play at stage 2 and a `SpikeB` spot at 0. Delete the slot. In world 3 both begin at 0.
- [ ] **Step 2: Build and run** `test.ps1 -Filter Reflections.DigSpot`. Record RED.
- [ ] **Step 3: Implement** the `BeginPlay` restore. Build and run again; both new tests pass.
- [ ] **Step 4: Write** `Tools/Digging/build_dig_spike_map.py` to the table above, and run it with `editor-python.ps1 -Script "C:\Users\zachc\Documents\Unreal Projects\reflections\.worktrees\digging\Tools\Digging\build_dig_spike_map.py"`. Expected: the script prints `DIG SPIKE MAP SAVED` and `Content/Maps/DigSpike/L_DigSpike.umap` exists.
- [ ] **Step 5: Write the map test** `Reflections.DigSpike.MapIsBuiltAsSpecified`: load the map package and check its persistent level holds exactly two dig spots with ids `DigSpike_A` and `DigSpike_B`, three non-null stage meshes each, one `APlayerStart`, one `ADirectionalLight`, one `ASkyLight`, and a `AStaticMeshActor` labelled `DigSpike_Ground`.
- [ ] **Step 6: Build and run** `test.ps1 -Filter Reflections`. Expected: every test passes (25).
- [ ] **Step 7: Commit** the code, the script and the map (the map goes through Git LFS; `git add` handles it).

**Gate 1:** every `Reflections.*` test passes. The `G` key and the look of the map are checked by hand in the real editor after the branch is merged.

---

### Task 2.1: Ground grid and dig stamps

**Files:**
- Create: `Source/reflections/Digging/ReflectionsDigTypes.h`, `Source/reflections/Digging/ReflectionsDigGrid.h`, `Source/reflections/Digging/ReflectionsDigGrid.cpp`
- Test: `Source/reflections/Digging/Tests/ReflectionsDigGridTests.cpp`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces, in `ReflectionsDigTypes.h`:
  - `namespace ReflectionsDig`: `inline constexpr float CellSizeCm = 50.0f; inline constexpr int32 ChunkCells = 32; inline constexpr int32 DensityPerCell = 64; inline constexpr int8 DensityMax = 127; inline constexpr int32 SampleBorder = 2; inline constexpr uint8 MaterialTopsoil = 0; inline constexpr uint8 MaterialBedrock = 255;`
  - `UENUM(BlueprintType) enum class EReflectionsDigMode : uint8 { Remove, Add };`
  - `struct FReflectionsDigStamp { FVector Center = FVector::ZeroVector; float RadiusCm = 100.0f; EReflectionsDigMode Mode = EReflectionsDigMode::Remove; uint8 Material = ReflectionsDig::MaterialTopsoil; };`
  - `struct FReflectionsDigChunkSamples`: a copy of one chunk's cells plus a border of `SampleBorder` cells on every side. `static constexpr int32 Side = 36;` `FIntVector Chunk;` `FVector3f LocalOriginCm;` (position of local cell (0,0,0) relative to the grid origin) `TArray<int8> Density; TArray<uint8> Material;` (each `Side`^3) and `int8 DensityAt(int32 X, int32 Y, int32 Z) const; uint8 MaterialAt(int32 X, int32 Y, int32 Z) const;` taking local coordinates from -2 to 33.
- Produces, in `ReflectionsDigGrid.h`: `class REFLECTIONS_API FReflectionsDigGrid` with
  - `FReflectionsDigGrid(FIntVector SizeInChunks, FVector OriginCm, float GroundHeightCm);`
  - `FIntVector GetSizeInChunks() const; FIntVector GetSizeInCells() const; FVector GetOriginCm() const; float GetGroundHeightCm() const;`
  - `FVector CellToWorld(FIntVector Cell) const;`
  - `int8 GetDensity(FIntVector Cell) const;` positive is solid
  - `uint8 GetMaterial(FIntVector Cell) const;`
  - `void ApplyStamp(const FReflectionsDigStamp& Stamp, TArray<FIntVector>& OutDirtyChunks);`
  - `void CopyChunkSamples(FIntVector Chunk, FReflectionsDigChunkSamples& Out) const;`

**Rules (exact).**
- A cell is a sample point. Cell (x, y, z) is at `OriginCm + (x, y, z) * 50`. The grid has `SizeInChunks * 32` cells per axis.
- `Quantise(d)` is `clamp(round(d / 50 * 64), -127, 127)`, where d is a signed distance in cm.
- Initial density of a cell is `Quantise(GroundHeightCm - CellWorldZ)`. Initial material is topsoil.
- Bedrock cells are those with z = 0, x = 0, x = max, y = 0 or y = max: the floor and the four side walls. Their material is 255. **No stamp ever changes a bedrock cell.**
- Outside the grid, `GetDensity` returns the initial-density formula for that position and `GetMaterial` returns 255.
- Remove: for every non-bedrock cell in the grid, `new = min(old, Quantise(Dist(cell, Center) - RadiusCm))`.
- Add: for every non-bedrock cell in the grid, `new = max(old, Quantise(RadiusCm - Dist(cell, Center)))`. A cell that goes from not solid to solid takes `Stamp.Material`.
- A stamp with a radius of 0 or less, or a centre that is not finite, changes nothing.
- `OutDirtyChunks` receives, once each, every chunk of the grid that has at least one changed cell inside its own cell range grown by `SampleBorder` cells on every side. A stamp that changes nothing appends nothing.
- `CopyChunkSamples` fills local coordinates -2 to 33 on each axis using the same answers as `GetDensity` and `GetMaterial`, inside and outside the grid.
- Storage is one byte of density and one byte of material per cell, held per chunk. The grid is used from the game thread only; worker threads only ever see `FReflectionsDigChunkSamples` copies.

- [ ] **Step 1: Write nine failing tests** on a 3 x 3 x 2 chunk grid with origin (0, 0, 0) and ground height 2800:
  - `Reflections.Digging.Grid.InitialGroundIsFlat`: cells more than 25 cm below 2800 are solid, cells more than 25 cm above are not, and a cell at exactly 2800 has density 0.
  - `Reflections.Digging.Grid.RemoveClearsInsideRadius`: Remove at (2400, 2400, 2400), radius 200. Cells within 150 cm of the centre have density below 0. Cells farther than 300 cm are unchanged.
  - `Reflections.Digging.Grid.AddRestoresSolid`: after that Remove, Add at the same place with radius 200 and material 7. Cells within 150 cm are solid with material 7. Cells farther than 300 cm still have material 0.
  - `Reflections.Digging.Grid.StampOnChunkCornerDirtiesEightChunks`: Remove at (1600, 1600, 1600), radius 100. `OutDirtyChunks` is exactly the eight chunks with every coordinate 0 or 1, with no repeats.
  - `Reflections.Digging.Grid.StampOutsideBoundsIsNoOp`: Remove at (-5000, -5000, -5000), radius 100. `OutDirtyChunks` is empty and `CopyChunkSamples` of every chunk is byte-identical before and after.
  - `Reflections.Digging.Grid.StampHalfOutsideIsClipped`: Remove at (0, 2400, 2400), radius 200. Cell (2, 48, 48) has density below 0. Cells with x = 0 keep their density and material 255. `GetDensity` of cell (-1, 48, 48) still equals the initial formula.
  - `Reflections.Digging.Grid.BedrockCannotBeRemoved`: Remove at (2400, 2400, 0), radius 300. Every cell with z = 0 within the radius still has density 127 and material 255. Cell (48, 48, 2) has density below 0.
  - `Reflections.Digging.Grid.SideWallsAreBedrock`: every cell on the floor and the four side faces has material 255; cell (48, 48, 30) has material 0; an Add of material 7 touching a wall leaves the wall cells at 255.
  - `Reflections.Digging.Grid.CopyChunkSamplesMatchesGetters`: for chunks (1, 1, 1) and (0, 0, 0), every one of the 36^3 entries equals `GetDensity` and `GetMaterial` of the matching global cell.
- [ ] **Step 2: Build and run** `test.ps1 -Filter Reflections.Digging.Grid`. Record RED.
- [ ] **Step 3: Implement** the types and the grid.
- [ ] **Step 4: Build and run** `test.ps1 -Filter Reflections.Digging.Grid`. Expected: 9 ran, 9 passed.
- [ ] **Step 5: Commit** the four files.

---

### Task 2.2: Mesher

**Files:**
- Create: `Source/reflections/Digging/ReflectionsDigMesher.h`, `Source/reflections/Digging/ReflectionsDigMesher.cpp`
- Modify: `Source/reflections/reflections.Build.cs`: add `"GeometryCore"` to `PublicDependencyModuleNames`
- Test: `Source/reflections/Digging/Tests/ReflectionsDigMesherTests.cpp`

**Interfaces:**
- Consumes: `FReflectionsDigGrid::CopyChunkSamples`, `FReflectionsDigChunkSamples`, the `ReflectionsDig` constants (task 2.1).
- Produces:
  - `struct FReflectionsDigMeshData { TArray<FVector3f> Positions; TArray<FVector3f> Normals; TArray<int32> Triangles; TArray<uint8> Materials; void Reset(); bool IsEmpty() const; };` `Positions`, `Normals` and `Materials` have one entry per vertex; `Triangles` has three indices per triangle.
  - `namespace ReflectionsDigMesher`:
    - `REFLECTIONS_API void BuildFromSamples(const FReflectionsDigChunkSamples& Samples, FReflectionsDigMeshData& Out);` pure and safe to call from any thread
    - `REFLECTIONS_API void BuildChunk(const FReflectionsDigGrid& Grid, FIntVector Chunk, FReflectionsDigMeshData& Out);` copies the samples, then calls `BuildFromSamples`
    - `REFLECTIONS_API bool SplitsAlongOwnCubeDiagonal(const FVector3f& P00, const FVector3f& P10, const FVector3f& P11, const FVector3f& P01, const FVector3f& AirDirection);` the one place the quad diagonal is decided, exposed so a test can pin it

**Rules (exact).** Naive surface nets.
- A cube (i, j, k) has its corners at local cells i..i+1, j..j+1, k..k+1. A corner is solid when its density is above 0.
- A cube with both solid and non-solid corners gets one vertex: the mean of the crossings on its sign-changing edges. **The surface is the 0.5 density level, not 0**, so a crossing never lands exactly on a cell: on an edge from a solid corner (density `d0`, at least 1) to a non-solid corner (density `d1`, at most 0) the crossing is at `t = (d0 - 0.5) / (d0 - d1)` from the solid corner. `t` is always strictly between 0 and 1, every vertex lies strictly inside its own cube, and no two cubes share a vertex position. (With the 0 level, a cell of density exactly 0 collapsed up to four vertices onto one point and produced zero-area triangles.)
- Positions are in cm relative to the grid origin (`Samples.LocalOriginCm` plus the local position).
- A chunk owns the lattice edges that start at local cells 0 to 31 on every axis and run one cell along +X, +Y or +Z. For each owned edge whose ends differ in solidity it emits one quad (two triangles) joining the four cubes around that edge. So it needs vertices for cubes -1 to 31, and every quad in the grid is emitted by exactly one chunk.
- Winding: for every triangle (A, B, C), `UE::Geometry::VectorUtil::Normal(A, B, C)` points from solid toward air.
- Diagonal: each quad is split along the diagonal that makes both of its triangles face air, judged by the sign of each triangle normal's component along the edge's direction from solid to air. If both diagonals qualify, use the shorter one; on an exact tie, the diagonal through the edge's own cube. The quad's four vertices lie strictly inside four different cubes around the edge, so at least one diagonal always qualifies. (A fixed diagonal folds a triangle over when one vertex sits close to the edge.)
- Normals: the central-difference density gradient at each of the cube's eight corners, trilinearly interpolated at the vertex position, negated and normalised. This is why the border is two cells. If that gradient has near-zero length, the normal is the normalised sum, over the cube's sign-changing edges, of the unit direction from the solid corner to the non-solid corner; if that sum vanishes too, +Z. Every case uses only the cube's own samples, so two chunks give the same cube the same normal.
- Materials: the material of the cube's solid corner with the highest density; ties go to the lowest corner index.
- `Out` is reset first. A chunk with no surface gives an empty `Out`.
- No triangle has zero area. The tests assert, on every mesh they build, that each triangle's area is above 0.01 cm² and that its `VectorUtil::Normal` agrees in direction with the stored normals of its three vertices.

- [ ] **Step 1: Write the failing tests** (eight after review) (grid 3 x 3 x 2 chunks, origin (0, 0, 0), ground height 2800 unless stated):
  - `Reflections.Digging.Mesher.UniformChunkIsEmpty`: chunk (1, 1, 0), all solid, gives no triangles; a sample block filled with -127 gives none.
  - `Reflections.Digging.Mesher.FlatGroundIsFlat`: chunk (1, 1, 1). Every vertex Z is within 1 cm of 2800; every normal is within 1 degree of +Z; every triangle's `VectorUtil::Normal` is within 1 degree of +Z; there are exactly 2048 triangles.
  - `Reflections.Digging.Mesher.NeighboursShareBorderVertices`: Remove at (1600, 2400, 2600), radius 200, then mesh chunks (0, 1, 1) and (1, 1, 1). Pair vertices by cube (a cube has at most one vertex; a vertex's cube is the floor of its position divided by 50). At least 8 cubes with X index 31 have a vertex in both chunks, and in every such pair the positions agree within 0.01 cm and the normals within 0.1 degree. (A border cube used only by edges the first chunk owns has no twin, and that is correct.)
  - `Reflections.Digging.Mesher.QuadsAreNotDuplicatedAcrossChunks`: for the same two meshes, no triangle (as a set of three positions, within 0.01 cm) appears in both.
  - `Reflections.Digging.Mesher.CellCentredDigsMakeNoDegenerateTriangles` (added when the 0-level bug was found): Remove stamps of radius 100 centred exactly on cells, underground, inside chunk (1, 1, 1) and across its border into (0, 1, 1); both meshes hold no triangle under the area threshold.
  - `Reflections.Digging.Mesher.DenseDigFieldsKeepEveryTriangleFacingAir` (added in review): radius-100 Remove stamps on 150, 200 and 250 cm lattices, with centres on cells and 17 cm off cells, buried (ground height 6400) and at the surface (ground height 2800). For each of the twelve fields, mesh chunks (1, 1, 1) and (0, 1, 1): every triangle passes the area and facing checks, every normal is unit length, and vertices paired by cube across the border agree.
  - `Reflections.Digging.Mesher.FoldedQuadTakesTheOtherDiagonal` (added in review): crafted quads fed to `SplitsAlongOwnCubeDiagonal`: one folded on each diagonal, one where both qualify and the other diagonal is shorter, and a square (exact tie). The chosen split always has both triangles facing air, and for the folded cases the rejected split has a triangle facing away.
  - `Reflections.Digging.Mesher.BuriedSphereIsClosed`: on a grid with ground height 6400 (all solid), Remove at (2400, 2400, 2400), radius 200, then mesh chunk (1, 1, 1). There is at least one triangle, every edge is used by exactly two triangles, and every vertex normal points toward the sphere centre.
- [ ] **Step 2: Build and run** `test.ps1 -Filter Reflections.Digging.Mesher`. Record RED.
- [ ] **Step 3: Implement** the mesher.
- [ ] **Step 4: Build and run** `test.ps1 -Filter Reflections.Digging`. Expected: 19 ran, 19 passed (9 grid tests, 2 grid tests added by the task 2.1 review, 8 mesher tests).
- [ ] **Step 5: Commit** the listed files.

---

### Task 2.3: Terrain actor, worker tasks and the commit budget

**Files:**
- Create: `Source/reflections/Digging/ReflectionsDigCommitQueue.h` and `.cpp`
- Create: `Source/reflections/Digging/ReflectionsDigPieces.h` and `.cpp` (pure piece building, added in review), with `Source/reflections/Digging/Tests/ReflectionsDigPiecesTests.cpp`
- Create: `Source/reflections/Digging/ReflectionsDigTerrain.h` and `.cpp`
- Create: `Source/reflections/Digging/ReflectionsDigSubsystem.h` and `.cpp`
- Modify: `Source/reflections/reflections.Build.cs`: add `"GeometryFramework"` to `PublicDependencyModuleNames`
- Test: `Source/reflections/Digging/Tests/ReflectionsDigQueueTests.cpp`, `Source/reflections/Digging/Tests/ReflectionsDigTerrainTests.cpp`

**Interfaces:**
- Consumes: `FReflectionsDigGrid` (2.1); `ReflectionsDigMesher::BuildFromSamples`, `FReflectionsDigMeshData` (2.2); `FReflectionsDigTestWorld` (1.2).
- Produces:
  - `namespace ReflectionsDigPieces` (pure, no `UObject`, safe on workers): `struct FReflectionsDigChunkResult { TArray<UE::Geometry::FDynamicMesh3> Pieces; int32 SourceVertexCount = 0; int32 SourceTriangleCount = 0; int32 DroppedTriangles = 0; };` and `REFLECTIONS_API void Build(const FReflectionsDigMeshData& Mesh, FReflectionsDigChunkResult& Out);` which applies the Pieces rule below and builds each piece as an `FDynamicMesh3` with its per-vertex normals.
  - `class REFLECTIONS_API FReflectionsDigCommitQueue`: `void Push(FIntVector Chunk, FReflectionsDigChunkResult&& Result);` (any thread; a second push for a queued chunk replaces its result and keeps its place in line), `int32 PopUpTo(int32 Max, TFunctionRef<bool(FIntVector)> CanCommit, TFunctionRef<void(FIntVector, FReflectionsDigChunkResult&&)> Commit);` (game thread; oldest-queued chunk first; a chunk for which `CanCommit` is false is skipped and keeps its place in line; both callbacks run outside the queue lock; returns how many it committed), `int32 Num() const;`
  - `UCLASS() class REFLECTIONS_API AReflectionsDigTerrain : public AActor` with `UPROPERTY(EditAnywhere, Category = "Digging") FIntVector SizeInChunks = FIntVector(3, 3, 2);`, `float GroundHeightCm = 0.0f;` (world Z of the ground surface), `float MeshRadiusCm = 2400.0f;`, `TObjectPtr<UMaterialInterface> GroundMaterial;` (all `EditAnywhere`), and `void CommitChunk(FIntVector Chunk, FReflectionsDigMeshData&& Mesh);` (builds the pieces, then commits them) `void CommitChunkPieces(FIntVector Chunk, FReflectionsDigChunkResult&& Result); void ReleaseChunk(FIntVector Chunk); UDynamicMeshComponent* FindChunkComponent(FIntVector Chunk) const;` (the chunk's first piece) `int32 GetChunkPieceCount(FIntVector Chunk) const; FReflectionsDigGrid* GetGrid() const; int32 GetLargestCollisionVertexCount() const;` Also add `inline constexpr int32 MaxPieceVertices = 12000;` to `namespace ReflectionsDig` in `ReflectionsDigTypes.h`.
  - `UCLASS() class REFLECTIONS_API UReflectionsDigSubsystem : public UTickableWorldSubsystem` with `bool Dig(FVector Center, float RadiusCm, EReflectionsDigMode Mode);`, `void RegisterTerrain(AReflectionsDigTerrain* Terrain); void UnregisterTerrain(AReflectionsDigTerrain* Terrain);`, `void SetFocusOverride(TOptional<FVector> Focus);`, `bool IsIdle() const;`, `int32 GetTasksInFlight() const;`, `int32 GetQueuedCommits() const;`, `int32 GetCommitsLastTick() const;`
  - Console variable `reflections.Dig.MaxCommitsPerFrame`, default 2.

**Rules (exact).**
- **Placement.** The actor must be unrotated and unscaled. Grid origin = (ActorLocation.X + 25, ActorLocation.Y + 25, GroundHeightCm - SizeInChunks.Z * 1600 + 400): the actor's X and Y are the patch's minimum corner, and the ground surface sits 400 cm below the top of the grid. The 25 cm (half a cell) is there because cells are sample points and the mesher puts its vertices at cube centres: with the origin on the corner the meshed ground ran from 25 cm before the patch to 25 cm short of its far edge (found by the rendered seam traces in task 2.6). With the half-cell shift the meshed ground spans exactly the patch. Chunk components sit at the grid origin in world space.
- **Registration.** The terrain builds its grid and registers with the subsystem in `BeginPlay`, and unregisters in `EndPlay`. The spike supports one terrain per world.
- **`Dig`** is the only way anything digs. It returns false when no terrain is registered or the stamp changed nothing. `Add` fills with topsoil. It applies the stamp to the grid at once and marks the returned chunks dirty.
- **Streaming, each tick.** The focus is the override if set, otherwise the first local player's pawn location, otherwise none. With no focus every chunk is wanted. With a focus a chunk is wanted when the distance from the focus to the chunk's box is `MeshRadiusCm` or less. An unwanted chunk's component is released. A wanted chunk with no mesh state is marked dirty.
- **Meshing.** For each dirty, wanted chunk with no task in flight: copy its samples on the game thread (all copies first, then all launches, so tasks really overlap; `CopyChunkSamples` must stay cheap, see the carry-over below), then run `BuildFromSamples` and `ReflectionsDigPieces::Build` on a worker with `UE::Tasks::Launch`; the worker pushes the built pieces to the commit queue. (Building the pieces on the game thread cost 15 to 17 ms for a busy chunk.) **At most one task is in flight per chunk.** A chunk dirtied while its task is in flight is meshed once more when that task has returned. Workers touch only the copied samples and the queue, never a `UObject`.
- **Committing.** Each tick, `PopUpTo(MaxCommitsPerFrame)` calls `CommitChunkPieces`. A result for a chunk that is no longer wanted is dropped. A chunk that is not wanted and still has components is released, whatever led to that state.
- **`CommitChunk`.** An empty mesh retires the chunk's pieces (see Collision swap). Otherwise the chunk's `UDynamicMeshComponent` is created or reused and given the mesh (positions, per-vertex normals, triangles) and `GroundMaterial`. **Pieces:** the mesher's worst case for one chunk is about 36,000 vertices, and UE 5.9 has a collision bug above 16,384 vertices (UE-380849), so a mesh with more than `MaxPieceVertices` vertices is split into horizontal slabs of equal height: the fewest slabs for which every slab holds at most `MaxPieceVertices` vertices. A triangle goes to the slab that holds its centroid, a slab gets its own copy of the vertices it uses, and each non-empty slab is its own component. The limit applies to each built piece: building can duplicate a few vertices at non-manifold edges, so a mesh just under the limit may still split. `GetLargestCollisionVertexCount()` counts every piece that still collides, retiring ones included. A triangle that cannot be added to a piece is counted in `DroppedTriangles` and reported with one warning per commit. Collision: `CTF_UseComplexAsSimple`, `bUseAsyncCooking = true`, `bDeferCollisionUpdates = true`, query and physics enabled, blocking every channel including `ECC_Visibility`. The component can affect navigation. **The chunk's previous collision must stay in place until the new cook has finished.** Read `Engine/Plugins/Runtime/GeometryFramework/Source/GeometryFramework/Private/Components/DynamicMeshComponent.cpp` (or wherever 5.9 keeps it) to see how deferred and async collision interact, and say in the report which calls give that guarantee.
- **One cook at a time per chunk (added in review).** A chunk is not committed again while any piece of its current set is still cooking: the commit loop skips it, its queued result keeps its place in line and may be replaced by a newer one. Every cook therefore finishes, so collision always moves forward under a held dig, and the engine never aborts a cook in flight. A failed cook does not block later commits.
- **Collision swap (exact, added in review).** Each chunk has a current set of pieces and at most one retiring set. The retiring set is hidden but keeps colliding.
  - A commit that reuses the chunk's single component relies on the engine: with deferred, async collision the body already in the scene stays until `FinishPhysicsAsyncCook` swaps the new one in.
  - A commit that replaces the set: if every piece of the current set has collision of its own (it is the newest collision that really exists), the retiring set is destroyed and the current set becomes the retiring set; otherwise the current set is destroyed and the retiring set stays. Decide this at commit time from the real state of each piece, not from the order of calls in `Tick`. With one cook at a time per chunk the second case arises only after a failed cook or a direct `CommitChunk` call.
  - A retiring set whose replacement is not empty is destroyed as soon as every piece of the replacement has finished cooking successfully. If a cook fails, the retiring set stays and a warning is logged. This check runs at the start of each tick, before the commits, and again after the launches; the reuse path also runs it for its own chunk before it sets a new mesh. (Checked only after the commits, a held dig on a one-piece chunk started a new cook every tick before the check ran, and the retiring set stayed for the whole hold as an invisible lid.)
  - A retiring set whose replacement is empty (the chunk became all solid or all air) is destroyed only when the whole terrain is quiet: no wanted chunk dirty, no task in flight, no queued commit, no cook pending anywhere. A neighbouring chunk may still be showing the old hole into this chunk. (The dirty-chunk condition matters because the swap check also runs at the start of a tick, before that tick has launched the re-mesh of a chunk the last dig touched.)
- **Safety floor.** The terrain actor owns one blocking `UBoxComponent` under the whole patch, 100 cm thick, with its top 30 cm below the grid origin Z. It catches anything the chunk collision ever misses, so nothing leaves the world. Tests treat a body or a trace reaching it as a failure of the terrain: it lies below the grid floor.
- **Ground material (added from task 2.6).** The pieces never draw with the engine's default world-grid material: on this mesh (per-vertex normals, no texture coordinates, no tangents) a lit view along a tunnel came out pure black for the whole frame. When `GroundMaterial` is null the terrain uses the plain engine material `/Engine/BasicShapes/BasicShapeMaterial`, resolved once at `BeginPlay` and set on every piece when it is created; if that asset cannot be loaded it logs one warning. The test map sets `GroundMaterial` to the same asset explicitly.
- **`IsIdle`** is true when no task is in flight, the queue is empty, no wanted chunk is dirty and no chunk is waiting on a collision cook.
- **Shutdown.** `Deinitialize` and `UnregisterTerrain` are safe with tasks in flight.

- [ ] **Step 1: Write three failing queue tests** (after review they distinguish results by `SourceTriangleCount`), and three piece tests: `Reflections.Digging.Pieces.SmallMeshIsOnePiece` (the flat chunk mesh gives one piece with 1,089 vertices and 2,048 triangles and unit normals), `Reflections.Digging.Pieces.BusyMeshSplitsUnderTheLimit` (a mesh above 12,000 vertices gives at least two pieces, each with at most 12,000 vertices; the triangles of the pieces sum to the source count and `DroppedTriangles` is 0), `Reflections.Digging.Pieces.SlabsAreTheFewestThatFit` (one slab fewer would leave a piece above the limit):
  - `Reflections.Digging.Queue.KeepsOnlyNewestPerChunk`: five pushes for one chunk, with 1 to 5 triangles; `Num()` is 1 and the one popped mesh has 5 triangles.
  - `Reflections.Digging.Queue.PopRespectsBudget`: six chunks queued; `PopUpTo(2)` returns 2, commits the first two pushed, and `Num()` is 4.
  - `Reflections.Digging.Queue.ReplacingKeepsPlaceInLine`: push A, push B, push A again; the pop order is A (the newer mesh), then B.
  - `Reflections.Digging.Queue.SkippedChunkKeepsItsPlace` (added in review): push A, B, C; with `CanCommit` false for A, `PopUpTo(2)` commits B then C and returns 2; A is still queued and comes first on the next call.
- [ ] **Step 2: Write the failing terrain tests** (sixteen after review), each in an `FReflectionsDigTestWorld` with one terrain at (0, 0, 0), `GroundHeightCm = 0`, default size, waiting for `IsIdle()` through the helper's new `bool TickUntil(TFunctionRef<bool()> IsDone, double TimeoutSeconds = 10.0, float DeltaSeconds = 1.0f / 60.0f)` (ticks the world, pumps game-thread tasks, sleeps about a millisecond; false on timeout) and asserting its result:
  - `Reflections.Digging.Terrain.MeshesAllChunksWithNoFocus`: the nine chunks with Z = 1 have components with triangles; the nine with Z = 0 have none.
  - `Reflections.Digging.Terrain.DigChangesCollision`: a downward visibility trace at (2400, 2400) hits within 5 cm of Z = 0. `Dig((2400, 2400, 0), 100, Remove)` returns true. After idle the same trace hits below Z = -50.
  - `Reflections.Digging.Terrain.DigOutsideTerrainReturnsFalse`: `Dig((-9000, 0, 0), 100, Remove)` returns false; with no terrain in the world `Dig` returns false.
  - `Reflections.Digging.Terrain.CommitBudgetIsRespected`: with the console variable at 1, a dig at the chunk corner (1600, 1600, -400) is followed tick by tick; `GetCommitsLastTick()` never exceeds 1.
  - `Reflections.Digging.Terrain.FarChunksAreReleasedAndRestored`: with the focus at the centre, dig a pit at (400, 400, 0) and record the trace depth. Move the focus to (4400, 4400, 0): after idle, chunk (0, 0, 1) has no component. Move the focus back: after idle the trace depth is within 1 cm of the recorded one.
  - `Reflections.Digging.Terrain.HeldDigStaysBounded`: on each of 120 ticks call `Dig` at the eight-chunk corner (1600, 1600, -1200), alternating Remove and Add so every call changes the grid. `GetTasksInFlight()` and `GetQueuedCommits()` never exceed 8; tasks in flight reached at least 2 on some tick; the commits summed over the 120 ticks exceed 8; after the last dig the subsystem is idle within 5 seconds. (The first wording dug one point with Remove only, which changes nothing after the first call and passed against an empty stub.)
  - `Reflections.Digging.Terrain.SplitChunkCollisionFollowsEachCook` (review, Important 1): on a chunk that is split into pieces, fill one cavity and wait for idle; a downward trace into it hits the top of the fill. Then dig elsewhere in the same chunk on each of 30 ticks: on every tick that trace still hits the top of the fill, never the old cavity floor.
  - `Reflections.Digging.Terrain.FillingAShaftNeverOpensAGapBelow` (review, Important 2): dig a shaft at (2400, 2400) deep enough that its floor lies in the lower chunk (below Z = -1200), wait for idle, then fill it from the bottom up, one stamp per tick. On every tick a downward trace from the shaft mouth hits a terrain piece, never nothing and never the safety floor.
  - `Reflections.Digging.Terrain.ChunkWaitsForItsCookBeforeTheNextCommit` (review): while a chunk has a cook pending, a newer result for it stays queued and `GetChunkPieceCount` and the current pieces do not change; once the cook has finished, the next tick commits it. Under a 120-tick held dig at one moving point, the collision under that point changes at least 10 times during the hold (it is not frozen).
  - `Reflections.Digging.Terrain.RetiredSetGoesDuringAHeldDig` (re-review): riddle chunk (1, 1, 0) until it is split, fill it back until it is one piece again, then hold a moving Remove inside it for 120 ticks. During the hold a downward trace into the newly dug space reaches below the old surface, and by the end of the hold the chunk has no retiring pieces left.
  - `Reflections.Digging.Terrain.DirectCommitWhileCookingKeepsTheRetiringFloor` (re-review): on a split chunk with a retiring set, call `CommitChunk` directly while the replacement set is still cooking; on that tick a trace into the cavity hits the retiring floor.
  - `Reflections.Digging.Terrain.SurfaceSpansExactlyThePatch` (added from task 2.6): with the terrain at (0, 0, 0), downward traces 5 cm inside each of the four patch edges and at the four corners hit a chunk piece within 5 cm of Z = 0; traces 5 cm outside each edge hit no chunk piece.
  - `Reflections.Digging.Terrain.PiecesNeverUseTheDefaultMaterial` (added from task 2.6): with `GroundMaterial` null every piece's material is the plain engine material and not the engine default; with `GroundMaterial` set every piece uses that one, including pieces created by a later dig.
  - `Reflections.Digging.Terrain.SafetyFloorLiesBelowTheGrid`: a downward trace started inside the solid interior of chunk (1, 1, 0), where there is no mesh, hits the safety floor within 1 cm of 30 cm below the grid origin Z.
  - `Reflections.Digging.Terrain.ChunkLeftAgainAfterAStaleResultIsReleased`: with a focus near chunk (0, 0, 1), dig there and at once move the focus far away, back, and far away again while results are still arriving; after idle with the focus far away, chunk (0, 0, 1) has no component.
  - `Reflections.Digging.Terrain.WorldTornDownWithTasksInFlight`: dig at the eight-chunk corner and destroy the test world at once, without waiting. No crash, no error, and the stale-world check of the helper stays clean.
  - `Reflections.Digging.Terrain.OldCollisionStaysWhileNewOneCooks`: after idle, dig at one point on every tick for 60 ticks; on every one of those ticks a downward visibility trace at that point, from above the ground to the grid floor, hits something.
  - `Reflections.Digging.Terrain.BusyChunkIsSplitUnderTheCollisionLimit`: riddle the buried chunk (1, 1, 0) with radius-100 digs on a 200 cm lattice until `ReflectionsDigMesher::BuildChunk` for it reports more than 12,000 vertices (assert that premise). After idle, `GetChunkPieceCount((1, 1, 0))` is at least 2, `GetLargestCollisionVertexCount()` is at most 12,000, and a downward trace started inside one of the cavities hits that cavity's floor.
- [ ] **Step 3: Build and run** `test.ps1 -Filter Reflections.Digging`. Record RED.
- [ ] **Carry-over to task 2.1's grid (added in review):** `FReflectionsDigGrid::CopyChunkSamples` copied 46,656 cells one getter call at a time, about 0.5 ms per chunk on the game thread, so a dig touching eight chunks cost about 4 ms before any meshing. Copy whole rows from chunk storage instead (the chunk's own cells and its neighbours' border cells), and use the formula only for cells outside the grid. Results stay byte-identical (`CopyChunkSamplesMatchesGetters` already pins that). Add `Reflections.Digging.Grid.CopyChunkSamplesIsFast`: 200 copies of an interior chunk take less than 20 ms in total.
- [ ] **Step 4: Implement** the queue, the terrain actor and the subsystem.
- [ ] **Step 5: Build and run** `test.ps1 -Filter Reflections`. Expected: every test passes.
- [ ] **Step 6: Commit** the listed files.

---

### Task 2.4: The hero digs the patch

**Files:**
- Modify: `Source/reflections/Digging/ReflectionsDigComponent.h` and `.cpp`
- Modify: `Source/reflections/Digging/Tests/ReflectionsDigComponentTests.cpp`
- Modify: `Tools/Digging/build_dig_spike_map.py`, then rebuild `Content/Maps/DigSpike/L_DigSpike.umap`
- Modify: `Source/reflections/Digging/Tests/ReflectionsDigSpikeMapTests.cpp`
- Test: `Source/reflections/Digging/Tests/ReflectionsDigGameTests.cpp` (game-context tests)

**Interfaces:**
- Consumes: `UReflectionsDigSubsystem::Dig`, `IsIdle`, `SetFocusOverride`; `AReflectionsDigTerrain` (2.3).
- Produces: `UFUNCTION(BlueprintCallable, Category = "Digging") bool UReflectionsDigComponent::TryFill();` and the game-context test file later tasks add to.

**Component rules.**
- `TryDig`: when the hit actor is an `AReflectionsDigTerrain`, return `Dig(Hit.ImpactPoint, 100, Remove)`. Dig spots behave as before.
- `TryFill`: the same trace; on a terrain return `Dig(Hit.ImpactPoint, 100, Add)`; otherwise false.
- A second action `IA_Fill` on `EKeys::H` calls `TryFill`, built and bound exactly like `IA_Dig`.

**Map changes (exact).**
- `DigSpike_Ground` becomes location (-2000, 0, -50), scale (60, 100, 1): it now ends at X = 1000.
- Add `DigSpike_Terrain`, an `AReflectionsDigTerrain` at (1000, -2400, 0) with `GroundHeightCm = 0` and default size, so the patch covers X 1000 to 5800 and Y -2400 to 2400, flush against the cube ground. Its `GroundMaterial` is `/Engine/BasicShapes/BasicShapeMaterial` (added from task 2.6; the map test pins it).
- `DigSpike_Start` moves to (400, 0, 100).
- Add four movable point lights `DigSpike_CaveLight1` to `4` at (2800, -600, 250), (2800, 600, 250), (4000, -600, 250) and (4000, 600, 250), intensity 5000 (unitless), attenuation radius 1500.

**Game-context tests.** These run in the real map in a `-game` process, so the game mode, world subsystems and physics are live. Each test spawns its own plain `ACharacter`, has the first player controller possess it, and calls `UReflectionsDigComponent::EnsureOnPawn`. They use latent commands and wait on `IsIdle()`, never on fixed sleeps. The sparse worktree has no hero Blueprint, so the game mode's own pawn is whatever the engine falls back to; the tests do not depend on it.

- [ ] **Step 1: Prove the harness.** Add one trivial test `Reflections.DigSpike.HarnessRunsInGame` flagged for the client context that passes when `GWorld` is a game world whose map name ends in `L_DigSpike`, and (added in review) when 60 consecutive frames take between 0.8 and 1.5 seconds, which proves the frame cap is on. Build, rebuild the map, and run `test.ps1 -Game -Map /Game/Maps/DigSpike/L_DigSpike -Filter Reflections.DigSpike`. If no test runs in a `-game` process in UE 5.9, stop and report NEEDS_CONTEXT with the log lines that show why.
- [ ] **Step 2: Write three failing editor-context tests** in `ReflectionsDigComponentTests.cpp`, in a test world with a terrain at (0, 0, 0):
  - `Reflections.DigInput.DigsTerrainInReach`: a pawn 150 cm above the ground at (2400, 2400), looking straight down; `TryDig` returns true and after idle the downward trace hits lower than before.
  - `Reflections.DigInput.FillRestoresTerrain`: after three `TryDig` calls, repeated `TryFill` calls (at most ten) bring the trace back to within 60 cm of Z = 0. Before each call the pawn is placed 150 cm above the current floor under it, as a falling player would be; a pawn fixed above the original ground is out of reach after the first dig.
  - `Reflections.DigInput.SafetyFloorIsNotTerrain` (added in review): a pawn inside the solid interior of the lower chunk, 100 cm above the safety floor and looking straight down, gets false from both `TryDig` and `TryFill`, and every chunk's samples are byte-identical afterwards.
- [ ] **Step 3: Write four failing game-context tests** in `ReflectionsDigGameTests.cpp`:
  - `Reflections.DigSpike.PitTunnelAndFill`: the character stands at (3400, 0). Dig a pit at least 300 cm deep under it with repeated `Dig` calls; the character ends at least 250 cm lower and above the grid floor. From the pit bottom dig a tunnel 500 cm along +X; a capsule sweep of the character's size along the tunnel axis is clear. Teleport the character out, fill the pit with `Add` stamps from the bottom up; a downward trace at (3400, 0) then hits within 60 cm of Z = 0.
  - `Reflections.DigSpike.DigDownToBedrock`: dig under the character until its Z stops changing for 2 seconds. It rests within 60 cm of the bedrock top plus its capsule half-height, and its Z was never below the grid floor on any frame.
  - `Reflections.DigSpike.FloorStaysWhileCollisionRecooks`: for 300 frames (5 seconds at the capped frame rate), dig under the character's feet every frame. On every frame a downward visibility trace from the character hits something above the grid floor. The character never ends below the grid floor.
  - `Reflections.DigSpike.PitSurvivesUnloadAndReturn`: dig a pit at (1400, -2000) and record the trace depth. Teleport the character to (5400, 2000); wait until the pit's chunk has no component. Teleport back and wait for idle: the trace depth is within 5 cm of the recorded one.
- [ ] **Step 4: Build and run** both test commands. Record RED.
- [ ] **Step 5: Implement** the component changes and the map changes; rebuild the map; extend `Reflections.DigSpike.MapIsBuiltAsSpecified` to check the terrain actor, the moved ground and the four lights.
- [ ] **Step 6: Run** `test.ps1 -Filter Reflections` and `test.ps1 -Game -Map /Game/Maps/DigSpike/L_DigSpike -Filter Reflections.DigSpike`. Expected: every test passes in both.
- [ ] **Step 7: Commit** the listed files and the rebuilt map.

---

### Task 2.5: Navmesh

**Files:**
- Modify: `Source/reflections/Digging/ReflectionsDigTerrain.cpp` (and `.h` if needed)
- Modify: `Tools/Digging/build_dig_spike_map.py`, then rebuild the map
- Create: `Source/reflections/Digging/Tests/ReflectionsDigGameTestHarness.h` (added in review): the game-test harness helpers moved out of `ReflectionsDigGameTests.cpp` unchanged, so task 2.6's measurement tests can use them
- Modify: `Source/reflections/Digging/Tests/ReflectionsDigSpikeMapTests.cpp`, `Source/reflections/Digging/Tests/ReflectionsDigGameTests.cpp`

**Interfaces:**
- Consumes: everything from 2.3 and 2.4.
- Produces: `double AReflectionsDigTerrain::GetLastNavUpdateSeconds() const;` (world time of the last navigation update the terrain asked for), used by task 2.6.

**Rules.**
- When a chunk piece's collision cook finishes, the terrain calls `FNavigationSystem::UpdateComponentData` for that piece. A dynamic mesh component does not tell navigation by itself. A piece that retires stops affecting navigation at once (it is old collision), and navigation is told; a piece that is destroyed leaves navigation through the engine's normal unregister path.
- If a new piece's cook fails and the retiring set is therefore kept as the chunk's only collision, that retiring set affects navigation again until it is destroyed or replaced. Otherwise the navmesh would show a hole over ground that still collides, for as long as nobody digs there again.
- The map gets a `NavMeshBoundsVolume` labelled `DigSpike_NavBounds` covering the whole patch and its full depth with a 200 cm margin, and its `RecastNavMesh` actor has Runtime Generation set to Dynamic **on the actor in this map**. Do not change project navigation settings in `Config/`.

- [ ] **Step 1: Write two failing game-context tests**, and after review two headless ones, `Reflections.Digging.Terrain.RetiringPiecesLeaveNavigationAtOnce` (during the swap window every retiring piece reports that it cannot affect navigation) and `Reflections.Digging.Terrain.FailedCookGivesTheRetiringSetItsNavigationBack` (with a cook forced to fail, the kept retiring pieces can affect navigation again):
  - `Reflections.DigSpike.NavmeshFollowsNewPit`: before digging, a navigation projection at (2000, 1600, 0) succeeds. Starting at (1800, 1600), dig a ramp down to 300 cm deep (stamps of radius 150 stepping down along +X so the slope is walkable); this site is clear of every other game test's digs. Within 1 second of the last dig's collision being ready, a projection onto the ramp's lowest point succeeds. Log the measured time as `DIGSPIKE NAV SECONDS=<value>`.
  - `Reflections.DigSpike.AiWalksIntoPit`: at its own site, starting at (2200, -400), dig a ramp of the same shape along -Y; a plain `ACharacter` with an `AAIController` is told to move to that ramp's lowest point and arrives within 100 cm of it inside 10 seconds. (Tests run in name order and digs persist, so this test cannot share the other test's ramp or its start point.)
- [ ] **Step 2: Build and run** the game-context command. Record RED.
- [ ] **Step 3: Implement** the navigation update, the map changes and the map test additions (bounds volume present; the map's navmesh actor is Dynamic). Rebuild the map.
- [ ] **Step 4: Run** both test commands. Expected: every test passes in both.
- [ ] **Step 5: Commit** the listed files and the rebuilt map.

---

### Task 2.6: Measure and report

**Files:**
- Create: `Source/reflections/Digging/Tests/ReflectionsDigPerfTests.cpp` (game-context tests under `Reflections.SpikePerf`)
- Modify: `Source/reflections/Digging/ReflectionsDigTerrain.h` and `.cpp` only to add two counters for navigation cost (see below)
- Modify: `Source/reflections/reflections.Build.cs` only if the game-thread timer lives in a module not yet listed
- Create: `ArtDirection/Digging/SpikeResults.md` and screenshots under `ArtDirection/Digging/SpikeShots/`

**Interfaces:**
- Consumes: everything above, and the game-test harness in `Tests/ReflectionsDigGameTestHarness.h`.
- Produces: numbers only, plus `int32 AReflectionsDigTerrain::GetNavUpdateCount() const` and `double AReflectionsDigTerrain::GetNavUpdateSeconds() const` (how many navigation updates the terrain has asked for, and the game-thread seconds spent inside those calls).

These run with the real renderer, off screen: `test.ps1 -Game -Render -Map /Game/Maps/DigSpike/L_DigSpike -Filter Reflections.SpikePerf -TimeoutSec 2400`. The prefix is `Reflections.SpikePerf`, not `Reflections.DigSpike...`, so the ordinary game-context command does not pick them up. They are measurements, not gates: each test logs lines that start with `DIGSPIKE` at Display level and passes if it completed. The pass marks are applied in `SpikeResults.md`, not in code. Game-thread time per frame is read from the engine's own game-thread timer (`GGameThreadTime`); the wrapper caps the run at 60 frames a second, so frame time itself says nothing.

- [ ] **Step 1: Prove the renderer is on.** Write `Reflections.SpikePerf.RendererIsOn`: it passes when the process is not using the null RHI and a game viewport exists, and logs `DIGSPIKE RENDER rhi=<name> raytracing=<0 or 1> lumen_hwrt=<0 or 1> resolution=<w>x<h>`. Run the command above. If the process cannot start a renderer off screen on this machine, stop and report NEEDS_CONTEXT with the log lines.
- [ ] **Step 2: Write the measurement tests**, each at its own site on the patch, clear of the other game tests' digs:
  - `Reflections.SpikePerf.DigCost`: 300 idle frames, then 30 seconds of a dig under the character every 0.1 s. Log `DIGSPIKE DIG idle_mean_ms=... idle_max_ms=... dig_max_ms=... dig_p99_ms=... dig_mean_ms=... digs=... nav_updates=... nav_ms_total=...`.
  - `Reflections.SpikePerf.StreamingCost`: move the character corner to corner over 20 seconds so chunks unload and reload. Log `DIGSPIKE STREAM idle_max_ms=... max_ms=... p99_ms=... chunks_released=... chunks_restored=...`.
  - `Reflections.SpikePerf.CollisionSize`: after 200 digs at seeded random points inside the patch, log `DIGSPIKE COLLISION largest_vertices=... pieces_max_per_chunk=...`.
  - `Reflections.SpikePerf.Seams`: 500 downward traces along the chunk borders and along the join with the cube ground at X = 1000. Log `DIGSPIKE SEAMS traces=500 misses=...`.
  - `Reflections.SpikePerf.CaveShots`: dig a 500 cm tunnel, put `DigSpike_CaveLight1` inside it, and save four screenshots under `ArtDirection/Digging/SpikeShots/`: the tunnel and the pit, each with `r.Lumen.HardwareRayTracing` 1 and 0. Log for each shot whether hardware ray tracing was really active.
  - `Reflections.SpikePerf.ShadowCost`: dig beside the sun-lit pit edge for 10 seconds. Log `DIGSPIKE SHADOW idle_max_ms=... max_ms=... mean_ms=...`.
- [ ] **Step 3: Run** the command three times and collect every `DIGSPIKE` line from each log.
- [ ] **Step 3b (added in review): attribute the cost.** A worst frame alone cannot be blamed on digging: frames with a garbage collection, and frames slowed by the other editor on this machine, are just as slow. `DigCost` and `StreamingCost` tag every frame of their windows with what happened in it (chunk commits, chunk releases and restores, a garbage collection) and log, as milliseconds above the idle median of the same run: for frames with a commit and no collection, the mean, 99th percentile and maximum; the same for frames with a release or a restore; the maximum for frames with a collection; and the maximum for frames with none of these (the background noise). Also log how many collections happened in the dig window against the same length of idle. Run the ordinary game tests once with the renderer on (`test.ps1 -Game -Render -Map /Game/Maps/DigSpike/L_DigSpike -Filter Reflections.DigSpike`) and record `DIGSPIKE NAV SECONDS` from it.
- [ ] **Step 4: Write** `ArtDirection/Digging/SpikeResults.md`: the plan doc's results table (game-thread cost of digging, streaming, collision size per chunk, seams, navmesh, cave lighting, shadows, packaged build) with the measured numbers from all three runs, the pass mark beside each, and how each was measured; the headless numbers from the earlier tasks, labelled as headless; what could not be measured from this worktree (the packaged build, and anything that needs the game's real content or the real hero) and why; and the plugin check (Voxel Plugin 2 listed UE 5.6 and 5.7 only when checked on 2026-11-21; nothing was bought or installed). Leave the last section, "Verdict", with the single line `Verdict: to be written by the controller after review.`
- [ ] **Step 5: Commit** the test file, the two counters, the results file and the screenshots.

- [ ] **Step 3c (added in review): measure the whole window, and the heavy cases.** The first review showed that tagging only the frame of a chunk commit leaves out most of what a dig costs: in this process (the editor binary run with `-game`) the renderer's data for a changed piece is rebuilt on the game thread one frame after the commit, and the collision cook finishing, the navigation update, the `Dig()` call and the copy-and-launch all fall in other frames. So:
  - The headline figures for digging and streaming are whole-window: every frame of the window, as milliseconds above the idle median of the same run (mean, median, 99th percentile, maximum), with the raw maximum always shown beside them. Also log the cost per dig: (window mean minus idle mean) times frames, divided by digs.
  - Frames are tagged as dig-related when any of these happened in them or in the frame before: a `Dig()` call, a chunk commit, a collision cook finishing, a navigation update, a chunk released or restored. Only frames with none of those and no garbage collection count as background, and their maximum is logged as the machine's noise level.
  - `Reflections.SpikePerf.CornerDigCost`: 10 seconds of digging every 0.1 s at a place where eight chunks meet, whole-window figures as above.
  - `Reflections.SpikePerf.BusyChunkCost`: riddle one chunk until its mesh is above 12,000 vertices (so it is split into pieces), then dig inside it every 0.1 s for 10 seconds; whole-window figures, the piece count and the largest collision vertex count.
  - `Reflections.SpikePerf.NavAfterDig`: dig a walkable ramp and log, for the last dig, the seconds from the `Dig()` call to the first successful navigation projection onto the new floor (`DIGSPIKE NAV FROM_DIG_SECONDS=...`), the seconds from collision ready (as before), and the worst game-thread frame above the idle median while navigation rebuilt.
  - `Reflections.SpikePerf.CaveShots` also saves `tunnel_fixed_exposure_hwrt_on/off.png` with automatic exposure off and one fixed exposure for both, so the pair shows real brightness.
  - The results file says in plain words: that the process was the editor program run as a game and not a packaged game; that game-thread time leaves out time spent waiting for other threads; for each pass-mark row whether the mark is met on the 99th percentile and on the worst frame, leading with any run that does not meet it; and nothing is called background noise unless it comes from frames with no dig-related event.

### Task 2.7: Navigation never builds a piece's collision on the main thread

Added after a profiler capture. It is a defect fix, not the tuning round the plan doc keeps for the owner.

**What the capture showed.** `Reflections.SpikePerf.BusyChunkCost` was run once with CPU tracing (`-trace=cpu,frame,bookmark -statnamedevents`, log `test-101716.log`) and the trace was read with Unreal Insights. In the frame after every chunk update, the navigation tick (`Nav Tick Time`) took 46 to 68 ms. Inside it, `STAT_Navigation_ProcessPendingOctreeUpdates` called `UBodySetup::CreatePhysicsMeshes` three times, once per new piece, and each call was a full collision build on the game thread (`FChaosDerivedDataCooker::Build`, 12 to 21 ms each). 101 navigation ticks held exactly three such builds each and total 4.74 s; the unexplained cost in `SpikeResults.md` was 4.7 to 4.8 s per 100 digs.

**The engine path** (UE 5.9 source): a navigation element captures the component's `GetBodySetup()` when the component registers or is updated (`FNavigationElement::InitializeFromInterface`, `NavigationElement.cpp`). When the navmesh generator exports the element (`ExportObject`, `RecastNavMeshGenerator.cpp`), it calls `ExportRigidBodySetup`, whose first line is `BodySetup.CreatePhysicsMeshes()`, unless the element's custom export says the default export is not required. `UDynamicMeshComponent::InternalOnMeshUpdated` clears the current body setup's built data when deferred collision updates are on. A new piece registers navigation-relevant while empty and then receives its mesh, so at the next navigation tick the generator builds that body on the spot, while the background build of the same data is still running.

**Files:**
- Modify: `Source/reflections/Digging/ReflectionsDigPieces.h` and `.cpp`
- Modify: `Source/reflections/Digging/ReflectionsDigTerrain.h` and `.cpp`
- Modify tests: `Tests/ReflectionsDigPiecesTests.cpp`, `Tests/ReflectionsDigTerrainTests.cpp`, `Tests/ReflectionsDigGameTests.cpp`, `Tests/ReflectionsDigPerfTests.cpp`

**Interfaces:**
- Consumes: `FReflectionsDigChunkResult`, `ReflectionsDigPieces::Build`, `UReflectionsDigChunkComponent`, `AReflectionsDigTerrain::UpdatePieceNavigation`.
- Produces:
  - `struct FReflectionsDigNavGeometry { TArray<FVector> Vertices; TArray<int32> Indices; };` (vertices in the piece's local space, three indices per triangle) and `TArray<FReflectionsDigNavGeometry> NavGeometry` in `FReflectionsDigChunkResult`, parallel to `Pieces`, built on the worker by `ReflectionsDigPieces::Build` from the same triangles as each piece.
  - `void UReflectionsDigChunkComponent::SetNavGeometry(FReflectionsDigNavGeometry&& InGeometry)`, called by the commit together with `SetMesh`.
  - `virtual bool UReflectionsDigChunkComponent::DoCustomNavigableGeometryExport(FNavigableGeometryExport& GeomExport) const override`: exports the stored arrays with `ExportCustomMesh` and the component's transform, and returns `false`.
  - `int32 AReflectionsDigTerrain::GetGameThreadCookCount() const` (read-only detector, see rule 3).

**Rules:**
1. Navigation never reads a piece's body setup. Pieces are created with `SetCustomNavigableGeometry(EHasCustomNavigableGeometry::Yes)` and export their own triangles; returning `false` from the export tells the generator that the default body-setup export is not required. The export must be safe whichever geometry gathering mode the project uses: check `GetGeometryGatheringMode` in the engine and force gathering on the game thread for pieces if the default could run it elsewhere.
2. A brand-new piece does not count for navigation until its first successful collision build is in. The existing order stays: navigation is told about a piece when its new collision arrives; a retiring piece leaves navigation at once; a retiring set kept after a failed build gets its navigation back. The piece carries its own "should count for navigation" state, so these rules do not depend on what `CanEverAffectNavigation` happens to be while a piece waits for its first build.
3. `GetGameThreadCookCount()` counts every time a background collision build finishes and finds that the body setup it is about to replace was built by someone else in the meantime: it reports its physics meshes as created and holds at least one triangle mesh, although this piece's mesh changed after a background build last produced that body, or no background build ever produced it. Checked before the engine's `FinishPhysicsAsyncCook` runs. It must stay 0.

- [ ] **Step 1: Write the failing tests.**
  - `Reflections.DigSpike.NavigationNeverBuildsCollision` (game context, the spike map's real navmesh): riddle one chunk until its mesh is above 12,000 vertices, dig inside it ten times 0.1 s apart, wait until the terrain is idle; `GetGameThreadCookCount()` is 0, and a navigation projection onto the last dug floor succeeds within 1 s. Before the fix the count is above 0: show it.
  - `Reflections.Digging.Pieces.NavGeometryMatchesEachPiece`: for every piece of a split chunk, the index count is three times the piece's triangle count, every index is valid, and the bounds of the navigation vertices equal the bounds of the piece's mesh.
  - `Reflections.Digging.Terrain.PieceExportsItsOwnNavigationGeometry`: with a recording `FNavigableGeometryExport` written in the test, a committed piece's export returns `false`, calls `ExportCustomMesh` once with three indices per triangle, and never calls `ExportRigidBodySetup`.
  - `Reflections.Digging.Terrain.NewPieceWaitsForCollisionBeforeNavigation`: between the commit that creates a piece and the finish of its first build, `IsNavigationRelevant()` is false; after the finish it is true; a retiring piece is false.
- [ ] **Step 2: Run them**; the game-context test and the two terrain tests fail (or do not compile) for the stated reasons.
- [ ] **Step 3: Implement** rules 1 to 3. Add `game_thread_cooks=<n>` to every whole-window `DIGSPIKE` line of the measurement tests (the count over that window).
- [ ] **Step 4: Run** the build, the editor-context suite and the game-context suite; all pass with clean output. Run the render command once and report the busy-chunk, corner, open-ground and streaming whole-window lines beside the same lines of `test-091739.log`. Restore the screenshots (`git checkout -- ArtDirection/Digging/SpikeShots/`). Do not edit `SpikeResults.md`.
- [ ] **Step 5: Commit.**

### Task 2.8: Measure again and rewrite the numbers

**Files:**
- Create: `Tools/Digging/summarize_spike_log.py`
- Modify: `ArtDirection/Digging/SpikeResults.md`

- [ ] **Step 1: Write** `Tools/Digging/summarize_spike_log.py <log> [<log> ...]` (Python 3, standard library only): it reads the `DIGSPIKE` lines of each log and prints, one column per log, every figure the results file shows: each whole-window row (average, middle frame, 99 in 100, worst frame raw and above idle, worst dig-related frame, cost per dig, frames, `game_thread_cooks`), the split of the heavy cases, the noise level, navmesh, collision size, seams, shadows, graphics card, the run length and the screenshot brightness. Check it first against the three old logs (`test-090807`, `test-091247`, `test-091739`): its output must reproduce the numbers now in `SpikeResults.md`; list any figure it cannot reproduce.
- [ ] **Step 2: Run** the render command three times (`test.ps1 -Game -Render -Map /Game/Maps/DigSpike/L_DigSpike -Filter Reflections.SpikePerf -TimeoutSec 2400`), 10 of 10 passing each time, and restore the screenshots after each run.
- [ ] **Step 3: Rewrite the numbers** in `SpikeResults.md` from the three new logs with the script: every table, every figure in a sentence, the log names, the run lengths, "Read this first", and each "Met / Not met" result. Keep the old busy-chunk, corner and streaming figures in one short table headed "Before the navigation fix" that names the three old logs. Leave the section "Where the cost of a heavy dig goes" with its new split table only; the controller writes its explanation and the Verdict. State nothing about a cause.
- [ ] **Step 4: Commit** the script and the results file.

**Gate 2:** every measured row meets the plan doc's pass mark and the user accepts the cave lighting.
