#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "GameFlow/ReflectionsGameFlowSettings.h"
#include "GameFlow/ReflectionsGameFlowTypes.h"
#include "ReflectionsGameFlowWorldSubsystem.generated.h"

class APawn;
class APlayerController;
class AReflectionsWorldPickup;
class SReflectionsFlowHud;
class SReflectionsFlowMenu;
class SWidget;
class UInputComponent;
class USoundBase;

/** What a menu button does. */
enum class EReflectionsFlowAction : uint8
{
    Start,
    Continue,
    NewGame,
    Controls,
    Credits,
    QuitGame,
    Resume,
    Restart,
    QuitToTitle,
    ConfirmYes,
    Back,
    TryAgain,
    /** Straight to the title (no confirm), from the lose and victory screens. */
    ReturnToTitle,
    /** Pause > Journal: the quest session's journal (pause steps aside until it closes). */
    Journal,
    /** Title / pause > Settings, and the Settings screen's buttons. */
    Settings,
    SettingsApply,
    SettingsDefaults,
    SettingsKeep,
    SettingsRevert,
    /** Pause > Save Game / Load Game, and the slot buttons on those screens. */
    SaveGame,
    LoadGame,
    SaveSlot1,
    SaveSlot2,
    SaveSlot3,
    LoadAutosave,
    LoadQuick,
    LoadSlot1,
    LoadSlot2,
    LoadSlot3,
    /** F5 / hold Start / Pause > X, and F9 / Pause or death screen > Y. */
    QuickSave,
    QuickLoad,
    /** Death screen: get up at the last checkpoint (the driver's respawn), or load the newest manual / quick save. */
    Respawn,
    LoadLatest,
};

/**
 * Per-map side of the game flow: the HUD layer (infection meter, tips, toasts) and the menus (title, pause,
 * controls, credits, lose, victory), the pause key, the one-time tutorial tips, checkpoint capture on world jumps
 * and page pickups, and putting the hero back at the checkpoint after a restart or a respawn.
 * Everything is Slate built in code, layered above the spell and world-jump HUDs; no widget assets.
 */
UCLASS()
class REFLECTIONS_API UReflectionsGameFlowWorldSubsystem : public UTickableWorldSubsystem
{
    GENERATED_BODY()

public:
    static UReflectionsGameFlowWorldSubsystem* Get(const UObject* WorldContext);

    virtual void OnWorldBeginPlay(UWorld& InWorld) override;
    virtual void Deinitialize() override;
    virtual void Tick(float DeltaTime) override;
    virtual TStatId GetStatId() const override;
    virtual bool IsTickableWhenPaused() const override { return true; }

protected:
    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

public:
    // ---- Screens ---------------------------------------------------------------------------------------

    EReflectionsFlowScreen GetScreen() const { return Screen; }
    bool IsMenuOpen() const { return Screen != EReflectionsFlowScreen::None; }
    void ShowTitle();
    void OpenPause();
    void ShowLose();
    void ShowVictory();
    /** Opens a sub-screen (Controls, Credits) on top of the current one; Back returns. */
    void PushScreen(EReflectionsFlowScreen NewScreen);
    void HandleAction(EReflectionsFlowAction Action);
    /** Closes every menu and returns control to the game. */
    void ResumeGame();

    /** The action a Confirm screen will run, and its wording. */
    EReflectionsFlowAction GetConfirmAction() const { return ConfirmAction; }

    // ---- Saves -----------------------------------------------------------------------------------------

    /** Playing, hero up, no cutscene, not game over: the game can be saved now (from play or the pause menu). */
    bool CanSaveNow() const;
    /** F5, hold Start, Pause > X: quick save, with a toast or a status line. */
    void RequestQuickSave();
    /** F9, Pause / death screen > Y: loads the quick save straight away, or says there is none. */
    void RequestQuickLoad();
    /** The slot (ReflectionsSaveSlots) a Confirm screen will overwrite or load. */
    int32 GetPendingSlot() const { return PendingSlot; }
    /** One line under the slots ("Saved to Slot 2", "That slot is empty"). */
    FText GetSaveStatus() const { return SaveStatus; }
    bool IsHeroDefeated() const;

    // ---- HUD -------------------------------------------------------------------------------------------

    /** Short line under the infection meter ("Checkpoint saved"). */
    void ShowToast(const FText& Text, float Seconds = 2.5f);
    /** Shows a tutorial tip now (and marks it seen). */
    void ShowTip(EReflectionsTip Tip);
    FText GetTipText(EReflectionsTip Tip) const;
    FText GetTipTitle(EReflectionsTip Tip) const;

    // Read by the Slate widgets every frame.
    float GetHudClock() const { return Clock; }
    bool HasActiveTip() const { return ActiveTip != EReflectionsTip::Count; }
    EReflectionsTip GetActiveTip() const { return ActiveTip; }
    float GetTipAlpha() const;
    FText GetToastText() const { return ToastText; }
    float GetToastAlpha() const;
    float GetInfectionPulse() const;
    bool IsUsingGamepad() const;
    /** The HUD hides while the spell-crafting screen is up. */
    bool IsCraftingOpen() const { return bCraftingOpen; }
    bool IsPlaying() const { return bPlaying; }

    // ---- Checkpoints -----------------------------------------------------------------------------------

    /** Builds a checkpoint from the hero's current state. False if there is no pawn. */
    bool CaptureCheckpoint(const FString& Reason, FReflectionsCheckpoint& Out) const;
    /** Puts the hero (and the world-jump progress) back at a checkpoint in this map. */
    bool ApplyCheckpoint(const FReflectionsCheckpoint& Checkpoint);
    /** Called by the game-instance subsystem after every checkpoint save (toast + respawn point). */
    void NotifyCheckpointSaved();

    /** True until play has started in this map (the title can start a run in place). */
    bool IsMapFresh() const { return !bPlaying; }
    /**
     * Closes the menus and starts (or resumes) normal play: tips, checkpoints, pause key. bFreshRun (Start / New
     * Game, not a restore) also asks the cutscene subsystem for the new-game intro.
     */
    void BeginPlaying(bool bFreshRun = false);

    /** The cutscene subsystem (/Script/reflections.ReflectionsCutsceneSubsystem, called by name), or null. */
    UObject* GetCutsceneSubsystem() const;
    /** While a cutscene plays: no pause key, no tips (their clock waits), no checkpoint toast. */
    bool IsCutscenePlaying() const;

    /** The quest session's game-instance subsystem (/Script/reflections.ReflectionsQuestSubsystem, by name), or null. */
    UObject* GetQuestSubsystem() const;
    /** True when the quest subsystem offers OpenJournal() and IsJournalOpen(): the pause menu shows "Journal". */
    bool HasJournal() const;

    // ---- Settings screen ----------------------------------------------------------------------------------

    const FReflectionsVideoDraft& GetSettingsDraft() const { return SettingsDraft; }
    /** Left / right (or a click) on a Settings row. The preset previews live; everything else waits for Apply. */
    void StepSetting(int32 Row, int32 Delta);
    /** Seconds left on the keep-or-revert screen. */
    float GetSettingsConfirmSecondsLeft() const { return FMath::Max(0.0f, SettingsConfirmUntil - Clock); }

    /** Plays /Game/Audio/Jam/Cues/SCue_<CueName> as a UI sound (it plays while the game is paused). */
    void PlayUiSound(const TCHAR* CueName);

    /**
     * Plays /Game/Audio/Jam/Voice/Cues/SCue_VO_Narrator_<Line> (one narrator line at a time; a new line stops the
     * previous one). Silently skipped while the cue does not exist.
     */
    void PlayNarrator(const TCHAR* Line);
    bool IsNarratorSpeaking() const;

    APlayerController* GetLocalController() const { return Controller.Get(); }
    TSharedPtr<SReflectionsFlowMenu> GetMenuWidget() const { return Menu; }

    /** Debug: synthesize one key press through Slate (keyboard or gamepad key name). */
    static bool SimulateKey(const FString& KeyName);

private:
    void EnsureController();
    void BuildWidgets();
    void RemoveWidgets();
    void BindPauseInput(APlayerController* PC);
    void OnPausePressed();
    void OnPadStartPressed();
    void OnPadStartReleased();
    void OnQuickSaveKey();
    void OnQuickLoadKey();
    void ShowDeath();
    void SaveSlotAction(int32 Slot);
    void DoSave(int32 Slot);
    void LoadSlotAction(int32 Slot);
    void RefreshSaveScreen();
    void RestoreVitals(const FReflectionsCheckpoint& Checkpoint);
    void ApplyScreen(EReflectionsFlowScreen NewScreen);
    void EnterMenuMode();
    void EnterGameMode();
    void HandleStartAction();
    void ScheduleCheckpoint(const FString& Reason, int32 Frames = 2);
    void TickTips(float DeltaTime);
    void TickRespawn();
    void TickPendingCheckpoint();
    void TrackPickups();
    void PushRespawnPoint();
    bool CanOpenPause() const;
    UObject* FindPawnComponent(const TCHAR* ClassName) const;

    UFUNCTION() void HandleWorldChanged(EReflectionsWorld From, EReflectionsWorld To);
    UFUNCTION() void HandlePagesChanged(int32 Pages, int32 PagesForBook);
    UFUNCTION() void HandleInfectionChanged(int32 Count, int32 Cap);
    UFUNCTION() void HandlePickedUp(APawn* Collector);

    TSharedPtr<SReflectionsFlowHud> Hud;
    TSharedPtr<SReflectionsFlowMenu> Menu;
    TSharedPtr<SWidget> HudRoot;
    TSharedPtr<SWidget> MenuRoot;

    TWeakObjectPtr<APlayerController> Controller;
    TWeakObjectPtr<APawn> Pawn;
    TWeakObjectPtr<class ULocalPlayer> WidgetPlayer;
    UPROPERTY(Transient) TObjectPtr<UInputComponent> PauseInput;
    /** Loaded UI cues by name (kept referenced so they stay resident). */
    UPROPERTY(Transient) TMap<FName, TObjectPtr<USoundBase>> UiSounds;
    /** The narrator line playing now (2D, UI sound so it plays over menus). */
    UPROPERTY(Transient) TObjectPtr<class UAudioComponent> Narrator;
    /** Pause > Journal is open: the pause menu is hidden until the journal closes. */
    bool bJournalFromPause = false;
    float JournalOpenedAt = -100.0f;

    /** The Settings screen's working copy, and the settings it opened with (Back restores the preset preview). */
    FReflectionsVideoDraft SettingsDraft;
    FReflectionsVideoDraft SettingsOriginal;
    float SettingsConfirmUntil = -1.0f;

    /** A narrator line queued to play at a real-time clock value (the intro, the victory line after the sting). */
    FName QueuedNarratorLine;
    float QueuedNarratorAt = -1.0f;

    EReflectionsFlowScreen Screen = EReflectionsFlowScreen::None;
    TArray<EReflectionsFlowScreen> ScreenStack;
    EReflectionsFlowAction ConfirmAction = EReflectionsFlowAction::Restart;

    // Start / restore
    bool bBegunPlay = false;
    bool bStartHandled = false;
    bool bPlaying = false;
    bool bRestorePending = false;
    bool bPausedByMenu = false;
    bool bBoundProgress = false;
    float Clock = 0.0f;
    float PlayClock = 0.0f;

    // Checkpoint triggers are deferred a frame so the hero has landed.
    FString PendingCheckpointReason;
    int32 PendingCheckpointFrames = -1;
    bool bApplyingCheckpoint = false;
    /** Real-time clock value until which OnWorldChanged does not autosave (the side confirmation after a restore). */
    float SuppressAutosaveUntil = -1.0f;
    struct FWatchedPickup
    {
        TWeakObjectPtr<AReflectionsWorldPickup> Actor;
        FString Name;
        FName PageId;
    };
    TArray<FWatchedPickup> WatchedPickups;
    TArray<FString> CollectedPickups;
    TArray<FName> CollectedPageIds;
    float PickupScanClock = -100.0f;
    float CoinScanClock = -100.0f;
    bool bPickupEventPending = false;
    bool bCoinNearby = false;
    bool bCanCrossWorlds = false;
    bool bCraftingOpen = false;

    // Respawn and the death screen
    bool bWasDefeated = false;
    bool bDeathShown = false;
    float DefeatedAt = -1.0f;

    // Saves
    int32 PendingSlot = -1;
    FText SaveStatus;
    bool bSlotSavePending = false;
    /** Gamepad Start: a short press pauses on release, a hold (0.8 s) quick-saves. */
    double StartHeldSince = -1.0;
    bool bStartHoldConsumed = false;

    // Tips
    EReflectionsTip ActiveTip = EReflectionsTip::Count;
    float TipStarted = -100.0f;
    float TipDuration = 7.0f;
    float LastTipEnded = -100.0f;
    float AimTipShownAt = -1.0f;
    float CastTipShownAt = -1.0f;
    TArray<EReflectionsTip> TipQueue;

    // Toast / infection pulse
    FText ToastText;
    float ToastStarted = -100.0f;
    float ToastDuration = 2.5f;
    float InfectionChangedAt = -100.0f;
};
