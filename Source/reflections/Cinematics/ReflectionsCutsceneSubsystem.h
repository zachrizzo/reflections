#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Camera/CameraTypes.h"
#include "Components/SkeletalMeshComponent.h"
#include "ReflectionsCutsceneSubsystem.generated.h"

class AActor;
class ACameraActor;
class ALevelSequenceActor;
class APawn;
class APlayerController;
class UAudioComponent;
class UReflectionsCutsceneAsset;
class SReflectionsCutsceneOverlay;
class SWidget;
class FReflectionsCutsceneInput;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FReflectionsCutsceneStarted, FName, Cutscene);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FReflectionsCutsceneFinished, FName, Cutscene, bool, bSkipped);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FReflectionsCutsceneCueEvent, FName, Cutscene, FName, Cue);

/**
 * Plays the game's cutscenes. A cutscene is a UReflectionsCutsceneAsset at /Game/Cinematics/Data/DA_Cutscene_<Name>:
 * a Level Sequence for cameras plus the cast, body takes, lines and cards. At play time it
 *  - finds the anchor (CutsceneAnchor_<Name> marker, else the hero's feet and facing) and plays the sequence with that
 *    transform as its origin, so it works on any map;
 *  - binds the live hero and named NPCs to the sequence's tagged bindings (stand-ins spawn only when nobody is found);
 *  - shows letterbox bars, subtitles, title cards and a hold-to-skip prompt (Space / Enter / gamepad A);
 *  - takes game input away, hides the other HUD layers, makes the hero invulnerable, and on the way out blends the
 *    camera back behind the hero and restores input and HUD exactly as it found them;
 *  - fires OnCutsceneStarted / OnCutsceneCue / OnCutsceneFinished for quests, game flow and the villain.
 *
 * Other code calls it by name (no header needed): world subsystem /Script/reflections.ReflectionsCutsceneSubsystem,
 * UFUNCTIONs PlayCutscene(FName), PlayNewGameIntro(), IsCutscenePlaying(), SkipCutscene(), HasPlayed(FName).
 */
UCLASS()
class REFLECTIONS_API UReflectionsCutsceneSubsystem : public UTickableWorldSubsystem
{
    GENERATED_BODY()

public:
    static UReflectionsCutsceneSubsystem* Get(const UObject* WorldContext);
    /** True while any cutscene plays in WorldContext's world. */
    static bool IsAnyCutscenePlaying(const UObject* WorldContext);

    virtual void Deinitialize() override;
    virtual void Tick(float DeltaTime) override;
    virtual TStatId GetStatId() const override;
    virtual bool IsTickableWhenPaused() const override { return true; }
    virtual ETickableTickType GetTickableTickType() const override;

protected:
    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

public:
    /** Plays /Game/Cinematics/Data/DA_Cutscene_<Name>. False if it doesn't exist or another cutscene is playing. */
    UFUNCTION(BlueprintCallable, Category = "Cutscene")
    bool PlayCutscene(FName Name);

    /** Plays an asset directly (tests, editor tools). */
    bool PlayCutsceneAsset(UReflectionsCutsceneAsset* Asset, FName Name);

    /** Game flow calls this when a fresh run starts. Plays "Intro"; in PIE only with Cutscene.IntroInPIE 1. */
    UFUNCTION(BlueprintCallable, Category = "Cutscene")
    bool PlayNewGameIntro();

    /** Ends the cutscene now (with the skip fade). */
    UFUNCTION(BlueprintCallable, Category = "Cutscene")
    void SkipCutscene();

    UFUNCTION(BlueprintPure, Category = "Cutscene")
    bool IsCutscenePlaying() const { return bActive; }

    UFUNCTION(BlueprintPure, Category = "Cutscene")
    FName GetCurrentCutscene() const { return bActive ? CurrentName : NAME_None; }

    /** Seconds into the current cutscene. */
    UFUNCTION(BlueprintPure, Category = "Cutscene")
    float GetCutsceneTime() const { return Elapsed; }

    /** Played (to the end or skipped) in this play session. */
    UFUNCTION(BlueprintPure, Category = "Cutscene")
    bool HasPlayed(FName Name) const { return Played.Contains(Name); }

    /** The origin the current cutscene plays relative to. */
    UFUNCTION(BlueprintPure, Category = "Cutscene")
    FTransform GetAnchorTransform() const { return Anchor; }

    /** The actor playing a role in the current cutscene (live or stand-in), or null. */
    UFUNCTION(BlueprintPure, Category = "Cutscene")
    AActor* GetCastActor(FName Role) const;

    UPROPERTY(BlueprintAssignable, Category = "Cutscene")
    FReflectionsCutsceneStarted OnCutsceneStarted;

    UPROPERTY(BlueprintAssignable, Category = "Cutscene")
    FReflectionsCutsceneFinished OnCutsceneFinished;

    UPROPERTY(BlueprintAssignable, Category = "Cutscene")
    FReflectionsCutsceneCueEvent OnCutsceneCue;

    /** Resolves the anchor for a name the way PlayCutscene does (for tools and the README checks). */
    bool FindAnchor(FName AnchorName, FTransform& OutAnchor, AActor*& OutMarker) const;

    // ---- Read by the overlay every frame ----------------------------------------------------------------
    float GetLetterboxAlpha() const { return LetterboxAlpha; }
    float GetLetterboxAspect() const;
    float GetBlackAlpha() const;
    float GetSkipProgress() const { return SkipHeld; }
    float GetSkipPromptAlpha() const;
    bool IsUsingGamepad() const;
    FText GetSubtitleSpeaker() const { return SubtitleSpeaker; }
    FText GetSubtitleText() const { return SubtitleText; }
    float GetSubtitleAlpha() const;
    /** The card showing now: false if none. */
    bool GetCard(int32& OutStyle, FText& OutText, FText& OutSubText, float& OutAlpha) const;

    // Input (from the Slate input processor).
    void NotifySkipKey(bool bDown, bool bGamepad);
    void NotifyAnyInput(bool bGamepad);

private:
    struct FCastEntry
    {
        FName Role;
        TWeakObjectPtr<AActor> Actor;
        bool bStandIn = false;
        bool bKeep = false;
        bool bFoundByTag = false;
        bool bAddedHoldTag = false;
        bool bRestoreTransform = false;
        bool bWasHidden = false;
        bool bHidden = false;
        FTransform OriginalTransform;
        TWeakObjectPtr<UObject> SteeredComponent;
    };

    struct FPlayingTake
    {
        TWeakObjectPtr<class UAnimInstance> AnimInstance;
        TWeakObjectPtr<class UAnimMontage> Montage;
        TWeakObjectPtr<class USkeletalMeshComponent> SingleNodeMesh;
        EAnimationMode::Type PreviousMode = EAnimationMode::AnimationBlueprint;
        TWeakObjectPtr<UClass> PreviousClass;
    };

    APlayerController* GetController() const;
    APawn* GetHero() const;
    bool ResolveAnchor(const UReflectionsCutsceneAsset* Asset, FName Name);
    void SpawnCast();
    AActor* FindRoleActor(const struct FReflectionsCutsceneCastMember& Member) const;
    void StartSequence();
    void BeginControlTakeover();
    void EndControlTakeover();
    void ShowOverlay();
    void RemoveOverlay();
    void HideOtherLayers(bool bHide);
    void TickTimeline(float Previous, float Now);
    void StartPerformance(const struct FReflectionsCutscenePerformance& Take);
    void StartLine(const struct FReflectionsCutsceneLine& Line);
    void NotifyQuests(FName Name);
    bool IsLineAllowed(const struct FReflectionsCutsceneLine& Line) const;
    void StartConversion(const struct FReflectionsCutsceneCue& Cue);
    AActor* FindNearestNpc(const struct FReflectionsCutsceneCastMember& Member) const;

    /** Conversion hold: at HoldAtTime the sequence pauses for HoldExtraSeconds of real time. */
    float HoldAtTime = -1.0f;
    float HoldExtraSeconds = 0.0f;
    float HoldEndReal = -1.0f;
    bool bHolding = false;
    /** Gray / Red / White: the side the hero was on when the cutscene started (variant lines and cards). */
    FName CurrentSide;
    void Cleanup(bool bBlendCamera);
    float GetTotalLength() const;
    bool IsMenuBlocking(bool& bGameOver) const;

    UPROPERTY(Transient) TObjectPtr<UReflectionsCutsceneAsset> Current;
    UPROPERTY(Transient) TObjectPtr<ALevelSequenceActor> SequenceActor;
    UPROPERTY(Transient) TObjectPtr<UAudioComponent> VoiceAudio;
    UPROPERTY(Transient) TObjectPtr<UAudioComponent> MusicAudio;
    UPROPERTY(Transient) TObjectPtr<ACameraActor> HandOffCamera;
    /** Assets loaded for the current cutscene (kept referenced while it plays). */
    UPROPERTY(Transient) TArray<TObjectPtr<UObject>> Loaded;

    FName CurrentName;
    bool bActive = false;
    bool bEnding = false;
    bool bSkipped = false;
    float Elapsed = 0.0f;
    float EndFadeClock = -1.0f;
    float RealClock = 0.0f;
    float LetterboxAlpha = 0.0f;
    float SkipHeld = 0.0f;
    bool bSkipDown = false;
    float SkipPromptShownAt = -100.0f;
    bool bGamepad = false;
    float HandOffBlendLeft = -1.0f;
    float LastFrameFade = 0.0f;

    FTransform Anchor = FTransform::Identity;
    TWeakObjectPtr<AActor> AnchorMarker;
    TArray<FCastEntry> CastEntries;
    TArray<FPlayingTake> Takes;
    TSet<FName> Played;

    FText SubtitleSpeaker;
    FText SubtitleText;
    float SubtitleStart = -100.0f;
    float SubtitleEnd = -100.0f;

    // Saved control state.
    TWeakObjectPtr<APlayerController> TakenController;
    TWeakObjectPtr<APawn> TakenHero;
    bool bSavedIgnoreViewportInput = false;
    bool bSavedCanBeDamaged = true;
    bool bTookControl = false;
    /** Deinitialize: restore everything, notify nobody (the world is going away). */
    bool bSilentTeardown = false;
    TWeakObjectPtr<UActorComponent> PausedDriver;
    FMinimalViewInfo LastView;
    bool bHaveLastView = false;

    TSharedPtr<SReflectionsCutsceneOverlay> Overlay;
    TSharedPtr<SWidget> OverlayRoot;
    TWeakObjectPtr<class ULocalPlayer> OverlayPlayer;
    struct FHiddenLayer
    {
        TWeakPtr<SWidget> Widget;
        float Opacity = 1.0f;
    };
    TArray<FHiddenLayer> HiddenLayers;
    bool bLayersHidden = false;

    TSharedPtr<FReflectionsCutsceneInput> InputProcessor;
};
