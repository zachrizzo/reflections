#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Quests/ReflectionsQuestTypes.h"
#include "Quests/ReflectionsQuestSubsystem.h"
#include "Hero/ReflectionsHeroCharacter.h"
#include "NPC/ReflectionsNpcArchetype.h"
#include "ReflectionsQuestWorldSubsystem.generated.h"

class APawn;
class APlayerController;
class AReflectionsQuestItem;
class SReflectionsQuestHud;
class SReflectionsQuestJournal;
class SReflectionsQuestTalk;
class SWidget;
class UInputComponent;
struct FReflectionsSpellHitData;

/** Where the tracked objective is, for the HUD pointer. */
struct FReflectionsQuestTarget
{
    bool bValid = false;
    FVector Location = FVector::ZeroVector;
    float Radius = 0.0f;
    /** The target is on another side of the city: no pointer, the tracker says where instead. */
    bool bOtherSide = false;
    EReflectionsWorld Side = EReflectionsWorld::Red;
    FText Label;
};

/** One line of the tracker. */
struct FReflectionsTrackerLine
{
    FText Text;
    bool bDone = false;
    bool bOptional = false;
};

/** A button on the talk card. */
struct FReflectionsTalkOption
{
    FText Label;
    /** Quest action (accept:q, turn_in:q, choose:q.c, give_hint:q) or "goodbye". */
    FString Action;
    bool bPrimary = false;
};

/** A person or item with quest business, for the over-head marks. */
struct FReflectionsQuestMark
{
    TWeakObjectPtr<AActor> Actor;
    /** '!' offer, '?' turn in, '*' talk / deliver / choice. */
    TCHAR Glyph = TEXT('!');
    bool bPrompt = false;
};

/**
 * Per-map side of the quests: listens to the game (spell hits, NPC deaths, world jumps, shards, pages, keys, the
 * finale, victory), tracks positional objectives, spawns quest givers and quest items that the map lacks, and draws
 * the UI: tracked objective (top right, under the Tarnish meter), the on-screen pointer, over-head marks on quest
 * people, banners, the journal (L; Journal in the pause menu) and the talk card (E near a person; D-pad Down via
 * the voice hook).
 */
UCLASS()
class REFLECTIONS_API UReflectionsQuestWorldSubsystem : public UTickableWorldSubsystem
{
    GENERATED_BODY()

public:
    static UReflectionsQuestWorldSubsystem* Get(const UObject* WorldContext);

    virtual void OnWorldBeginPlay(UWorld& InWorld) override;
    virtual void Deinitialize() override;
    virtual void Tick(float DeltaTime) override;
    virtual TStatId GetStatId() const override;
    virtual bool IsTickableWhenPaused() const override { return true; }

protected:
    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

public:
    // ---- Screens ---------------------------------------------------------------------------------------------

    UFUNCTION(BlueprintCallable, Category = "Quests") void OpenJournal();
    UFUNCTION(BlueprintCallable, Category = "Quests") void CloseJournal();
    UFUNCTION(BlueprintPure, Category = "Quests") bool IsJournalOpen() const { return bJournalOpen; }

    /** Opens the talk card with a person. bOnlyIfBusiness: only when they have quest business (voice hook). */
    UFUNCTION(BlueprintCallable, Category = "Quests")
    bool OpenTalk(AActor* Npc, bool bOnlyIfBusiness);
    /** A choice with nobody to ask (narration): opens the card on its own. */
    bool OpenChoice(FName QuestId);
    UFUNCTION(BlueprintCallable, Category = "Quests") void CloseTalk();
    UFUNCTION(BlueprintPure, Category = "Quests") bool IsTalkOpen() const { return bTalkOpen; }

    // Talk card state, read and driven by SReflectionsQuestTalk.
    FText GetTalkSpeaker() const;
    FText GetTalkSpeakerTitle() const;
    FText GetTalkLine() const;
    bool IsTalkOnLastLine() const { return TalkLines.IsEmpty() || TalkLineIndex >= TalkLines.Num() - 1; }
    const TArray<FReflectionsTalkOption>& GetTalkOptions() const { return TalkOptions; }
    /** Next line; false when there are no more. */
    UFUNCTION(BlueprintCallable, Category = "Quests")
    bool AdvanceTalk();
    UFUNCTION(BlueprintCallable, Category = "Quests")
    void ChooseTalkOption(int32 Index);
    int32 GetTalkRevision() const { return TalkRevision; }

    // ---- HUD reads -------------------------------------------------------------------------------------------

    bool ShouldShowHud() const;
    FText GetTrackedTitle() const { return TrackedTitle; }
    const TArray<FReflectionsTrackerLine>& GetTrackerLines() const { return TrackerLines; }
    const FReflectionsQuestTarget& GetTrackedTarget() const { return TrackedTarget; }
    const TArray<FReflectionsQuestMark>& GetMarks() const { return Marks; }
    AActor* GetPromptTarget() const { return PromptTarget.Get(); }
    FText GetPromptText() const;
    bool IsUsingGamepad() const;
    /** The banner on screen now (kicker, title, detail) and its fade 0..1. */
    bool GetBanner(FText& OutKicker, FText& OutTitle, FText& OutDetail, FLinearColor& OutColor, float& OutAlpha) const;
    /** Narration subtitle (speaker: line) and fade. */
    bool GetSubtitle(FText& OutSpeaker, FText& OutLine, float& OutAlpha) const;
    APlayerController* GetController() const { return Controller.Get(); }
    APawn* GetHero() const;
    float GetClock() const { return Clock; }
    int32 GetRevision() const { return Revision; }

    // ---- People and places -----------------------------------------------------------------------------------

    /** The actor playing a person (tag Person_<Id>, or their own archetype). */
    UFUNCTION(BlueprintCallable, Category = "Quests")
    AActor* FindPersonActor(FName PersonId) const;

    /** Where an objective points (person, marker, nearest item or enemy, the villain's arena). */
    bool ResolveObjectiveTarget(const FReflectionsQuestDef& Def, const FReflectionsQuestObjective& Objective, FReflectionsQuestTarget& Out);

    /** Text for tests: what each widget shows. */
    UFUNCTION(BlueprintCallable, Category = "Quests|Debug")
    FString DescribeUi() const;

    /** Debug: synthesizes a key press on the open quest screen (Up, Down, Enter, Escape, Gamepad_FaceButton_Bottom...). */
    UFUNCTION(BlueprintCallable, Category = "Quests|Debug")
    bool SimulateKey(const FString& KeyName);

private:
    void EnsureController();
    void BuildWidgets();
    void RemoveWidgets();
    void BindInput(APlayerController* PC);
    void OnJournalPressed();
    void OnTalkPressed();
    void EnterMenuMode(TSharedPtr<SWidget> Focus);
    void EnterGameMode();
    void BindGame();
    void UnbindGame();

    void EvaluateObjectives(float DeltaTime);
    void EnsurePeople();
    AActor* SpawnPerson(FName PersonId);
    void EnsureItems(const FReflectionsQuestObjective& Objective);
    void SpawnFor(FName QuestId, const FReflectionsQuestObjective& Objective);
    int32 QueryEventCount(FName Key, FName Arg) const;
    void UpdateTracker();
    void UpdateMarks();
    void UpdatePrompt();
    bool HasBusiness(AActor* Npc, TCHAR& OutGlyph) const;
    void RefreshTalkOptions();
    void PushTalkLine(FName Speaker, const FText& Text, FName LineId = NAME_None);
    /** Says lines: into the talk card when it is open, else as subtitles with their voice cues. */
    void PlayLines(const TArray<FReflectionsQuestLine>& Lines);
    /** Plays SCue_VO_<Id> from the speaker (2D when absent). Returns its length, or 0. */
    float PlayVoiceCue(FName LineId, FName Speaker);
    UObject* CutsceneSystem() const;
    bool IsCutscenePlaying() const;
    /** Starts a step's cutscene; false if there is no cutscene system or it refused. */
    bool PlayCutscene(FName Name);
    void EvaluateCutsceneSteps();
    void EvaluateAfterLines();
    void PlayStepCue(FName QuestId, FName StepId);
    void PlaySound(const TCHAR* Cue);
    bool IsHeroNear(const FVector& Location, float Radius, bool bSameSideOnly = true) const;
    EReflectionsWorld SideOf(const FVector& Location) const;
    EReflectionsWorld HeroSide() const;
    bool IsWorldJumpActive() const;
    FName SideName(EReflectionsWorld World) const;
    AActor* FindSpellTarget(FName Target) const;

    UFUNCTION() void HandleQuestEvent(FName QuestId, FName StepId, FName ObjectiveId, EReflectionsQuestEventType Type);
    UFUNCTION() void HandleQuestsChanged();
    UFUNCTION() void HandleSpellHit(const FReflectionsSpellHitData& Hit);
    UFUNCTION() void HandleNpcDied(AActor* Npc, AActor* Killer);
    /** npc-unify's OnPlayerCrime(Victim, Crime, Witness, Location, Heat), bound by name. Fires once per witness. */
    UFUNCTION() void HandlePlayerCrime(AActor* Victim, FName Crime, AActor* Witness, FVector Location, float Heat);
    /** Crimes already counted (victim + crime + rounded place), so the per-witness repeats don't stack. */
    TMap<FString, double> CountedCrimes;
    TSet<FString> CrimeWitnesses;
    UFUNCTION() void HandleWorldChanged(EReflectionsWorld From, EReflectionsWorld To);
    UFUNCTION() void HandleCoinsChanged(EReflectionsWorld World, int32 Count);
    UFUNCTION() void HandlePagesChanged(int32 Pages, int32 PagesForBook);
    UFUNCTION() void HandleKeyAdded(FName KeyId);
    UFUNCTION() void HandleBookComplete();
    UFUNCTION() void HandleVictory();
    UFUNCTION() void HandleNpcInfection(AActor* Npc, EReflectionsNpcInfection State, AActor* Source);
    UFUNCTION() void HandleSpellEvent(EHeroSpell Spell, FVector Location, AActor* Caster, float Intensity);
    UFUNCTION() void HandleDoorOpened();
    void CountSpellAt(EHeroSpell Spell, const FVector& Location, AActor* HitActor, bool bFromCast);

    TSharedPtr<SReflectionsQuestHud> Hud;
    TSharedPtr<SReflectionsQuestJournal> Journal;
    TSharedPtr<SReflectionsQuestTalk> Talk;
    TWeakObjectPtr<APlayerController> Controller;
    TWeakObjectPtr<class ULocalPlayer> WidgetPlayer;
    UPROPERTY(Transient) TObjectPtr<UInputComponent> Input;
    UPROPERTY(Transient) TMap<FName, TObjectPtr<class USoundBase>> Sounds;

    bool bBegunPlay = false;
    bool bBound = false;
    bool bJournalOpen = false;
    bool bTalkOpen = false;
    bool bPausedByUs = false;
    bool bHadCheckpoint = false;
    bool bFinaleSeen = false;
    bool bInputBoundToPadTalk = false;
    bool bQuestsStarted = false;
    float Clock = 0.0f;
    float EvalAccumulator = 0.0f;
    float PeopleCheckAt = 3.0f;
    int32 Revision = 0;

    // Tracker
    FText TrackedTitle;
    TArray<FReflectionsTrackerLine> TrackerLines;
    FReflectionsQuestTarget TrackedTarget;
    TArray<FReflectionsQuestMark> Marks;
    TWeakObjectPtr<AActor> PromptTarget;

    // Banners and subtitles
    TArray<UReflectionsQuestSubsystem::FBanner> BannerQueue;
    UReflectionsQuestSubsystem::FBanner Banner;
    float BannerStarted = -100.0f;
    float BannerDuration = 4.0f;
    struct FSubtitle { FText Speaker; FText Line; float Seconds = 4.0f; FName Id; FName SpeakerId; float Delay = 0.0f; };
    TArray<FSubtitle> SubtitleQueue;
    FSubtitle Subtitle;
    float SubtitleStarted = -100.0f;
    float SubtitleEnded = -100.0f;
    int32 CuedTalkIndex = -1;
    int32 CuedTalkRevision = -1;
    UPROPERTY(Transient) TObjectPtr<class UAudioComponent> VoiceAudio;
    TMap<FName, float> StepStartedAt;
    TMap<FName, float> ProximityTalk;
    TMap<FName, double> SpellCooldown;
    TSet<TWeakObjectPtr<AActor>> KnownTarnished;
    bool bDoorsBound = false;

    // Talk card
    TWeakObjectPtr<AActor> TalkNpc;
    FName TalkPerson;
    FName TalkChoiceQuest;
    TArray<FReflectionsQuestLine> TalkLines;
    int32 TalkLineIndex = 0;
    TArray<FReflectionsTalkOption> TalkOptions;
    int32 TalkRevision = 0;
    bool bTalkEnding = false;

    // Spawned helpers
    TMap<FName, TWeakObjectPtr<AActor>> SpawnedPeople;
    TArray<TWeakObjectPtr<AReflectionsQuestItem>> SpawnedItems;
    TMap<EReflectionsWorld, int32> LastCoins;
    TSet<FName> KnownPages;
    TMap<FName, EReflectionsWorld> PageSides;
};
