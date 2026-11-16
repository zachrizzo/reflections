#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "GameFlow/ReflectionsGameFlowTypes.h"
#include "Tasks/Task.h"
#include "ReflectionsGameFlowSubsystem.generated.h"

class AActor;
class UReflectionsGameFlowSave;
class UReflectionsGameFlowWorldSubsystem;
class FReflectionsFlowInputTracker;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FReflectionsInfectionChanged, int32, Count, int32, Cap);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FReflectionsGameFlowEvent);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FReflectionsCheckpointSaved, const FReflectionsCheckpoint&, Checkpoint);

/** What the next map load should do once the player's pawn is in. */
enum class EReflectionsFlowStart : uint8
{
    /** First map of the session: the title screen (packaged / -game), or straight into play in PIE. */
    Launch,
    Title,
    /** Put the hero back at the saved checkpoint. */
    Restore,
    /** Fresh run, no title. */
    Play,
    /** Nothing special (for example a world-jump map change). */
    None,
};

/**
 * The game loop for the whole play session: global infection count and the lose condition, victory, the
 * checkpoint save slot, and the title / restart / quit flow. Survives map loads. The per-map side (widgets,
 * pause key, tips) lives in UReflectionsGameFlowWorldSubsystem.
 *
 * NPC, enemy and villain code, from C++:
 *   if (auto* Flow = UReflectionsGameFlowSubsystem::Get(this)) Flow->ReportInfected(Npc);
 * or the one-liners in UReflectionsGameFlowLibrary, or by name: FindFunction("ReportInfected") + ProcessEvent
 * on the game instance subsystem of class /Script/reflections.ReflectionsGameFlowSubsystem.
 */
UCLASS(Config = Game)
class REFLECTIONS_API UReflectionsGameFlowSubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()

public:
    static UReflectionsGameFlowSubsystem* Get(const UObject* WorldContext);

    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;

    // ---- Infection -------------------------------------------------------------------------------------

    /**
     * A host became infected. The count is "currently infected": a host already counted is ignored, so calling
     * twice is safe. Null Host adds one anonymous infection. Reaching the cap shows the lose screen.
     */
    UFUNCTION(BlueprintCallable, Category = "Game Flow|Infection")
    void ReportInfected(AActor* Host);

    /** A host was cured or freed: -1 if it was counted. Null Host removes one anonymous infection. Never below 0. */
    UFUNCTION(BlueprintCallable, Category = "Game Flow|Infection")
    void ReportCured(AActor* Host);

    UFUNCTION(BlueprintPure, Category = "Game Flow|Infection")
    int32 GetInfectionCount() const;

    UFUNCTION(BlueprintPure, Category = "Game Flow|Infection")
    int32 GetInfectionCap() const;

    /** Count / cap, 0..1. */
    UFUNCTION(BlueprintPure, Category = "Game Flow|Infection")
    float GetInfectionFraction() const;

    UFUNCTION(BlueprintPure, Category = "Game Flow|Infection")
    bool IsInfected(const AActor* Host) const;

    /** Change the cap for this run (a level can set its own). Values below 1 restore the default. */
    UFUNCTION(BlueprintCallable, Category = "Game Flow|Infection")
    void SetInfectionCap(int32 Cap);

    /** Clears every infection (restarts do this; NPCs reset with the map). */
    UFUNCTION(BlueprintCallable, Category = "Game Flow|Infection")
    void ResetInfection();

    /**
     * After a restore: the meter shows the saved count at once, as placeholders. Each host the villain re-tarnishes
     * (ReportInfected of a new host) takes a placeholder's place, so the count neither drops to 0 nor doubles.
     */
    void RestoreInfectionPlaceholders(int32 Count);

    /** Fires on every change of the count or the cap. */
    UPROPERTY(BlueprintAssignable, Category = "Game Flow|Infection")
    FReflectionsInfectionChanged OnInfectionChanged;

    /** Default cap when nothing set one; DefaultGame.ini [/Script/reflections.ReflectionsGameFlowSubsystem] can override. */
    UPROPERTY(Config, EditAnywhere, Category = "Game Flow|Infection")
    int32 DefaultInfectionCap = 20;

    /**
     * The map Start / New Game plays. Empty: play in the map already loaded (the title is an overlay on whatever
     * GameDefaultMap opens). One line in DefaultGame.ini swaps it, e.g.
     *   [/Script/reflections.ReflectionsGameFlowSubsystem]
     *   NewGameMap=/Game/MockCity/Lvl_MockCity.Lvl_MockCity
     * The map must also be in the packaging map list (MapsToCook): a config path is invisible to the cooker.
     * Console override for testing: GameFlow.NewGameMap /Game/MockCity/Lvl_MockCity
     */
    UPROPERTY(Config, EditAnywhere, Category = "Game Flow", meta = (AllowedClasses = "/Script/Engine.World"))
    FSoftObjectPath NewGameMap;

    /** NewGameMap (or the console override) as a long package name; empty when unset. */
    FString GetNewGameMapPackage() const;

    // ---- Win / lose ------------------------------------------------------------------------------------

    /** The villain is beaten: pauses the game and shows the victory screen with the credits. */
    UFUNCTION(BlueprintCallable, Category = "Game Flow")
    void ShowVictory();

    /** Shows the lose screen now (the infection cap calls this). */
    UFUNCTION(BlueprintCallable, Category = "Game Flow")
    void ShowLose();

    /** True after a loss or a victory, until the next restart. */
    UFUNCTION(BlueprintPure, Category = "Game Flow")
    bool IsGameOver() const { return bLost || bWon; }

    UFUNCTION(BlueprintPure, Category = "Game Flow")
    bool IsVictory() const { return bWon; }

    UPROPERTY(BlueprintAssignable, Category = "Game Flow")
    FReflectionsGameFlowEvent OnGameLost;

    UPROPERTY(BlueprintAssignable, Category = "Game Flow")
    FReflectionsGameFlowEvent OnVictory;

    // ---- Checkpoints -----------------------------------------------------------------------------------

    /** Saves the hero's state now (world jumps and page pickups call this automatically). */
    UFUNCTION(BlueprintCallable, Category = "Game Flow|Checkpoint")
    bool SaveCheckpoint(const FString& Reason);

    UFUNCTION(BlueprintPure, Category = "Game Flow|Checkpoint")
    bool HasCheckpoint() const { return Checkpoint.bValid; }

    UFUNCTION(BlueprintPure, Category = "Game Flow|Checkpoint")
    const FReflectionsCheckpoint& GetCheckpoint() const { return Checkpoint; }

    /** Forgets the checkpoint and deletes the save slot (tips seen are kept). */
    UFUNCTION(BlueprintCallable, Category = "Game Flow|Checkpoint")
    void ClearCheckpoint();

    UPROPERTY(BlueprintAssignable, Category = "Game Flow|Checkpoint")
    FReflectionsCheckpointSaved OnCheckpointSaved;

    void SetCheckpoint(const FReflectionsCheckpoint& InCheckpoint);

    /**
     * Fires after the hero has been put back at a restored checkpoint or save (after RestoreProgress), on the map
     * reload of Load, Continue, Try again and Restart. Not on a death respawn (the world keeps going there).
     * Systems with their own state restore it here from GetSaveData.
     */
    UPROPERTY(BlueprintAssignable, Category = "Game Flow|Checkpoint")
    FReflectionsCheckpointSaved OnCheckpointRestored;

    // ---- Save slots ------------------------------------------------------------------------------------
    // Slots (ReflectionsSaveSlots): 0 autosave (= the checkpoint), 1 quick save, 2-4 manual slots 1-3.
    // A manual or quick save is also a checkpoint: OnCheckpointSaved fires, so every system stores its state.

    /** Saves the game now into the quick slot (1) or a manual slot (2-4). False when it can't (no hero, defeated, game over). */
    UFUNCTION(BlueprintCallable, Category = "Game Flow|Save")
    bool SaveToSlot(int32 Slot);

    /** Queues disk I/O and reports its result on the game thread. */
    bool SaveToSlotAsync(int32 Slot, TFunction<void(bool)> OnSaved);

    /** Loads a slot: the saved state becomes the checkpoint, and its map reloads with everything put back. */
    UFUNCTION(BlueprintCallable, Category = "Game Flow|Save")
    bool LoadFromSlot(int32 Slot);

    UFUNCTION(BlueprintCallable, Category = "Game Flow|Save")
    bool QuickSave();

    UFUNCTION(BlueprintCallable, Category = "Game Flow|Save")
    bool QuickLoad();

    /** Time, side, pages and Tarnish of a slot (bUsed false when it is empty). */
    UFUNCTION(BlueprintCallable, Category = "Game Flow|Save")
    FReflectionsSaveSlotInfo GetSaveSlotInfo(int32 Slot) const;

    /** The used slot with the newest save time, or -1. bExcludeAutosave: quick and manual slots only. */
    UFUNCTION(BlueprintCallable, Category = "Game Flow|Save")
    int32 GetNewestSaveSlot(bool bExcludeAutosave = false) const;

    UFUNCTION(BlueprintPure, Category = "Game Flow|Save")
    bool HasAnySave() const { return GetNewestSaveSlot() != INDEX_NONE; }

    /** "Autosave", "Quick save", "Slot 1".. */
    static FText GetSlotDisplayName(int32 Slot);
    static FString SaveSlotFileName(int32 Slot);

    /**
     * Another system's own state, stored with the current checkpoint and every save made from it. Call it from your
     * OnCheckpointSaved handler (it fires on autosaves, manual saves and quick saves). Any byte format; for a
     * USaveGame object, UGameplayStatics::SaveGameToMemory / LoadGameFromMemory.
     */
    UFUNCTION(BlueprintCallable, Category = "Game Flow|Save")
    void SetSaveData(FName System, const TArray<uint8>& Data);

    /** The state a system stored with the checkpoint being restored (read it in OnCheckpointRestored). */
    UFUNCTION(BlueprintCallable, Category = "Game Flow|Save")
    bool GetSaveData(FName System, TArray<uint8>& Data) const;

    /** The next restore came from loading a slot: health and mana come back too. Read by the world subsystem. */
    bool bRestoreVitals = false;

    /** A map change is under way (set by OpenMap, cleared when the next map begins play): no checkpoint saves. */
    bool bTravelPending = false;

    // ---- Flow ------------------------------------------------------------------------------------------

    /** Reloads the checkpoint's map and puts the hero back at the checkpoint (fresh start if there is none). */
    UFUNCTION(BlueprintCallable, Category = "Game Flow")
    void RestartFromCheckpoint();

    /** Reloads the map and shows the title screen. */
    UFUNCTION(BlueprintCallable, Category = "Game Flow")
    void ReturnToTitle();

    /** Clears progress, infection and the save, and plays from the map's start. */
    UFUNCTION(BlueprintCallable, Category = "Game Flow")
    void StartNewGame();

    /** From the title: resume the saved checkpoint (loads its map if it is another one). */
    UFUNCTION(BlueprintCallable, Category = "Game Flow")
    void ContinueFromCheckpoint();

    UFUNCTION(BlueprintCallable, Category = "Game Flow")
    void QuitGame();

    /** The menu being shown in the current map. */
    UFUNCTION(BlueprintPure, Category = "Game Flow")
    EReflectionsFlowScreen GetScreen() const;

    /**
     * True only while the player is actually playing: play has begun in this map (title dismissed, restore done),
     * no game-flow menu is open, and the game is not lost or won. False on the first frames of a map load before
     * that, which GetScreen() == None alone does not rule out. (Cutscenes are the cutscene subsystem's to report.)
     */
    UFUNCTION(BlueprintPure, Category = "Game Flow")
    bool IsRunLive() const;

    EReflectionsFlowStart ConsumeStartAction();
    void ClearGameOver() { bLost = false; bWon = false; }

    /**
     * True while a menu holds UI-only input. FInputModeUIOnly sets IgnoreInput on the game viewport client, which
     * outlives map loads, so a map opened from a menu must hand input back to the game when play starts.
     */
    bool bMenuInputActive = false;

    /** The narrated intro (theme line) plays once per session. */
    bool bIntroPlayed = false;

    /** The next map load is a New Game (fresh run: the intro cutscene may play), not a restart. */
    bool bPendingFreshRun = false;

    /** A new map started: forget hosts destroyed with the previous map (they can never be cured now). */
    void PruneStaleHosts();

    // ---- Tips ------------------------------------------------------------------------------------------

    bool HasSeenTip(EReflectionsTip Tip) const { return (SeenTips & (1 << static_cast<int32>(Tip))) != 0; }
    void MarkTipSeen(EReflectionsTip Tip);
    void ResetTips();

    // ---- Input device ----------------------------------------------------------------------------------

    /** True while the most recent input came from a gamepad (prompts switch between key and button names). */
    UFUNCTION(BlueprintPure, Category = "Game Flow")
    bool IsUsingGamepad() const;

    static FString SlotName() { return TEXT("Reflections_Checkpoint"); }

    // ---- Test hooks (read by the PIE test scripts) ------------------------------------------------------

    /** Labels of the buttons on the open menu, top to bottom. */
    UFUNCTION(BlueprintCallable, Category = "Game Flow|Debug")
    TArray<FString> GetMenuButtonLabels() const;

    /** Index into GetMenuButtonLabels of the button with focus, or -1. */
    UFUNCTION(BlueprintCallable, Category = "Game Flow|Debug")
    int32 GetMenuFocusedIndex() const;

    /** Name of the tip on screen, or empty. */
    UFUNCTION(BlueprintCallable, Category = "Game Flow|Debug")
    FString GetActiveTipName() const;

private:
    UReflectionsGameFlowWorldSubsystem* GetWorldFlow() const;
    void BroadcastInfection();
    void CheckInfectionCap();
    bool CaptureCheckpoint(const FString& Reason);
    void RecordCheckpoint(const FReflectionsCheckpoint& InCheckpoint);
    bool SaveSlot(int32 Slot, bool bWait, TFunction<void(bool)> OnSaved);
    bool WriteSave(int32 Slot = INDEX_NONE, bool bWait = false, TFunction<void(bool)> OnSaved = {});
    void ResumeSavedCheckpoint();
    void OpenMap(const FString& MapPath);
    FString CurrentMapPath() const;

    mutable TMap<int32, FReflectionsSaveSlotInfo> SlotCache;
    UE::Tasks::TTask<bool> SaveWriteTask;
    /** Reusable content held only during a same-map reload, while the old actors are destroyed. */
    UPROPERTY(Transient) TSet<TObjectPtr<UObject>> TravelAssets;
    bool bBroadcastingCheckpoint = false;

    /** Hosts currently infected; a destroyed host stays counted until ReportCured. */
    TSet<TWeakObjectPtr<AActor>> InfectedHosts;
    int32 AnonymousInfected = 0;
    /** Part of AnonymousInfected that stands in for saved hosts not re-reported yet. */
    int32 RestoredPlaceholders = 0;
    int32 CapOverride = 0;
    bool bLost = false;
    bool bWon = false;
    bool bLosePending = false;

    UPROPERTY(Transient) FReflectionsCheckpoint Checkpoint;
    int32 SeenTips = 0;
    EReflectionsFlowStart PendingStart = EReflectionsFlowStart::Launch;

    TSharedPtr<FReflectionsFlowInputTracker> InputTracker;
};
