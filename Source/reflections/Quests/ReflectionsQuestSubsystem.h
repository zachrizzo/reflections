#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "GameFlow/ReflectionsGameFlowTypes.h"
#include "Quests/ReflectionsQuestTypes.h"
#include "ReflectionsQuestSubsystem.generated.h"

class UReflectionsGameFlowSubsystem;

class AActor;
class APawn;
class UReflectionsQuestPack;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_FourParams(FReflectionsQuestEvent, FName, QuestId, FName, StepId, FName, ObjectiveId, EReflectionsQuestEventType, Type);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FReflectionsQuestUnlock, FName, Unlock, FName, QuestId);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FReflectionsQuestGameEvent, FName, Key, FName, Arg, int32, Count);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FReflectionsQuestStandingChanged, FName, Person, float, Value);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FReflectionsQuestsChanged);

/** A line to show in a talk card or say through the voice relay. */
USTRUCT(BlueprintType)
struct FReflectionsQuestLine
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly, Category = "Quest") FName Speaker;
    UPROPERTY(BlueprintReadOnly, Category = "Quest") FText Text;
    /** Line id (voice cue SCue_VO_<Id>), if any. */
    UPROPERTY(BlueprintReadOnly, Category = "Quest") FName Id;
    UPROPERTY(BlueprintReadOnly, Category = "Quest") float Delay = 0.0f;
};

/**
 * Quests for the whole play session (state survives map loads): the main story and data-driven side quests, their
 * steps and objectives, rewards, the hero's quest items, standing with people, unlock flags, the tracked quest, and
 * the checkpoint save (slot Reflections_Quests, written with every game-flow checkpoint).
 *
 * Other systems:
 *   - Listen: OnQuestEvent (quest, step, objective, type), OnUnlock, OnGameEvent, OnQuestsChanged.
 *   - Report: NotifyEvent(Key, Arg) for anything a quest may wait on (CutsceneDone, a door, a crafted spell).
 *   - Ask: GetStatus, HasUnlock, GetStanding, GetItemCount.
 *   - Talk: GetQuestActions(Npc) / ExecuteQuestAction(...) / GetQuestContext(Npc) for the voice relay, the same
 *     rules the talk card uses. All are UFUNCTIONs, callable by name.
 * The per-map side (objective tracking, UI, input, spawning givers and items) is UReflectionsQuestWorldSubsystem.
 */
UCLASS(Config = Game)
class REFLECTIONS_API UReflectionsQuestSubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()

public:
    static UReflectionsQuestSubsystem* Get(const UObject* WorldContext);

    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;

    // ---- Content ---------------------------------------------------------------------------------------------

    /** Quest packs loaded on start, after the built-in quests (a pack quest replaces a built-in one with the same id). */
    UPROPERTY(Config, EditAnywhere, Category = "Quests")
    TArray<FSoftObjectPath> Packs;

    /** Reloads built-ins and packs (state of quests that still exist is kept). */
    UFUNCTION(BlueprintCallable, Category = "Quests")
    void ReloadContent();

    /** Adds or replaces quests and people from JSON text (Quest.LoadJson; tools). */
    bool AddContentFromJson(const FString& QuestJson, const FString& PeopleJson, FString& OutReport);

    const FReflectionsQuestDef* FindQuest(FName QuestId) const;
    const FReflectionsQuestPerson* FindPerson(FName PersonId) const;
    const TArray<FReflectionsQuestDef>& GetQuests() const { return Quests; }
    const TArray<FReflectionsQuestPerson>& GetPeople() const { return People; }
    const TMap<FName, FName>& GetMarkerAliases() const { return MarkerAliases; }

    /** A quest item's display name (the quest file's items list, else the id spaced out). */
    UFUNCTION(BlueprintPure, Category = "Quests")
    FText GetItemName(FName Item) const;

    /** The item's data (name, mesh), or null. */
    const FReflectionsQuestItemDef* FindItem(FName Item) const;

    /** Display name of a person (people book, else the id spaced out). */
    UFUNCTION(BlueprintPure, Category = "Quests")
    FText GetPersonName(FName PersonId) const;

    /** Test quests are hidden unless Quest.ShowTestQuests 1, or no real side quests are loaded. */
    bool IsQuestVisible(const FReflectionsQuestDef& Def) const;

    // ---- State -----------------------------------------------------------------------------------------------

    UFUNCTION(BlueprintPure, Category = "Quests")
    EReflectionsQuestStatus GetStatus(FName QuestId) const;

    const FReflectionsQuestState* FindState(FName QuestId) const;

    UFUNCTION(BlueprintCallable, Category = "Quests")
    bool GetQuestState(FName QuestId, FReflectionsQuestState& OutState) const;

    /** The step being worked on, or null. */
    const FReflectionsQuestStep* GetCurrentStep(FName QuestId) const;

    /** Starts a quest (from a giver's offer, or directly from script). */
    UFUNCTION(BlueprintCallable, Category = "Quests")
    bool AcceptQuest(FName QuestId);

    /** Not now: the giver keeps offering it later. */
    UFUNCTION(BlueprintCallable, Category = "Quests")
    bool DeclineQuest(FName QuestId);

    /** Hands a finished quest back to its giver and gives the reward. */
    UFUNCTION(BlueprintCallable, Category = "Quests")
    bool TurnInQuest(FName QuestId);

    UFUNCTION(BlueprintCallable, Category = "Quests")
    bool FailQuest(FName QuestId);

    /** Picks an option of the current step's choice. */
    UFUNCTION(BlueprintCallable, Category = "Quests")
    bool MakeChoice(FName QuestId, FName ChoiceId);

    /** Script / debug: marks one objective of the current step done. */
    UFUNCTION(BlueprintCallable, Category = "Quests")
    bool CompleteObjective(FName QuestId, FName ObjectiveId);

    /** Script / debug: finishes the current step. */
    UFUNCTION(BlueprintCallable, Category = "Quests")
    bool CompleteStep(FName QuestId);

    /** Ends the current step and goes to NextStep ("End" finishes the quest). For branches such as ifKilledNext. */
    UFUNCTION(BlueprintCallable, Category = "Quests")
    bool CompleteStepTo(FName QuestId, FName NextStep);

    /**
     * Something happened that a quest may wait on (Event objectives with Target = Key and, if set, Spell = Arg).
     * Exactly two FName parameters, so other systems can call it by name (cutscenes: CutsceneDone, <Name>).
     * Built-in keys: see ArtDirection/Quests/README.md.
     */
    UFUNCTION(BlueprintCallable, Category = "Quests")
    void NotifyEvent(FName Key, FName Arg);

    /** NotifyEvent counted Count times. */
    UFUNCTION(BlueprintCallable, Category = "Quests")
    void NotifyEventCount(FName Key, FName Arg, int32 Count);

    /** NotifyEvent where it happened: Event objectives with a Marker and a Radius only count it inside. */
    void NotifyEventAt(FName Key, FName Arg, const FVector& Location, int32 Count = 1);

    // ---- Tracking --------------------------------------------------------------------------------------------

    UFUNCTION(BlueprintPure, Category = "Quests")
    FName GetTrackedQuest() const { return Tracked; }

    UFUNCTION(BlueprintCallable, Category = "Quests")
    void SetTrackedQuest(FName QuestId);

    /** Quests in journal order: main first, then active side quests, ready to turn in, completed, failed. */
    UFUNCTION(BlueprintCallable, Category = "Quests")
    TArray<FName> GetJournalQuests() const;

    // ---- Items, standing, unlocks ---------------------------------------------------------------------------

    UFUNCTION(BlueprintCallable, Category = "Quests|Items") void GiveItem(FName Item, int32 Count = 1);
    UFUNCTION(BlueprintCallable, Category = "Quests|Items") bool TakeItem(FName Item, int32 Count = 1);
    UFUNCTION(BlueprintPure, Category = "Quests|Items") int32 GetItemCount(FName Item) const;

    /** Standing with one person, -100..100 (quest rewards; others may add their own). */
    UFUNCTION(BlueprintPure, Category = "Quests|Standing") float GetStanding(FName Person) const;
    UFUNCTION(BlueprintCallable, Category = "Quests|Standing") void AdjustStanding(FName Person, float Delta);

    UFUNCTION(BlueprintPure, Category = "Quests|Unlocks") bool HasUnlock(FName Unlock) const { return Unlocks.Contains(Unlock); }
    UFUNCTION(BlueprintCallable, Category = "Quests|Unlocks") void AddUnlock(FName Unlock, FName SourceQuest);

    // ---- Talking (talk card and voice relay share these rules) -----------------------------------------------

    /** People-book id of an actor: tag Person_<Id>, else the NPC's archetype id if a person has that id. */
    UFUNCTION(BlueprintPure, Category = "Quests|Talk")
    static FName GetPersonId(const AActor* Actor);

    /**
     * What this person can do about quests right now: offer_quest:<q>, accept:<q>, decline:<q>, turn_in:<q>,
     * give_hint:<q>, choose:<q>.<choice>, deliver:<q> (hand over a quest item), talk:<q> (a talk-to objective).
     */
    UFUNCTION(BlueprintCallable, Category = "Quests|Talk")
    TArray<FString> GetQuestActions(AActor* Npc) const;

    /**
     * Performs one of GetQuestActions (checked again against the state now). OutSay is the line the person should
     * say (hint text, a reply), empty when the action has none. False with OutReason when it is not possible.
     */
    UFUNCTION(BlueprintCallable, Category = "Quests|Talk")
    bool ExecuteQuestAction(AActor* Npc, const FString& Action, FString& OutReason, FString& OutSay);

    /** Persona facts for the relay: JSON with this person's quests (status, pitch, current objective, hints left). */
    UFUNCTION(BlueprintCallable, Category = "Quests|Talk")
    FString GetQuestContext(AActor* Npc) const;

    /** Lines for a talk card with this person for an action (offer lines for offer_quest, reminder for the rest). */
    TArray<FReflectionsQuestLine> GetLinesFor(AActor* Npc, const FString& Action) const;

    /** Called whenever the hero has spoken with a person (talk card, voice conversation). Counts talk objectives. */
    UFUNCTION(BlueprintCallable, Category = "Quests|Talk")
    void NotifyTalkedTo(AActor* Npc);

    /**
     * Voice hook: the talk key was pressed at this NPC. Opens the quest talk card and returns true if the person
     * has quest business (offer, turn-in, delivery, choice); false leaves the press to live voice.
     */
    UFUNCTION(BlueprintCallable, Category = "Quests|Talk")
    bool HandleTalkPressed(AActor* Npc);

    // ---- Consequences (people die; the hero gets a reputation) --------------------------------------------

    /**
     * A person died (the world subsystem calls this from npc-unify's OnNpcDied; anyone may call it by name).
     * Side quests that still need them fail with a journal note. A quest whose giver died but needs nothing
     * else from them goes on and finishes itself, with no one to return to. The main quest skips the beats that
     * needed them. Dead people are never spawned or offered quests through again.
     */
    UFUNCTION(BlueprintCallable, Category = "Quests|Consequences")
    void NotifyPersonDied(FName PersonId, bool bByHero);

    UFUNCTION(BlueprintPure, Category = "Quests|Consequences")
    bool IsPersonDead(FName PersonId) const { return DeadPeople.Contains(PersonId); }

    /** npc-unify's player heat, normalised to 0..1 (0 while that system has none). Read by name. */
    UFUNCTION(BlueprintPure, Category = "Quests|Consequences")
    float GetPlayerHeat() const;

    /**
     * True when this person won't offer the hero quests right now because of the heat (Quest.HeatRefuse, eased
     * by standing with them). OutLine is what they say instead.
     */
    bool IsWaryOfHero(FName PersonId, FText* OutLine = nullptr, const AActor* Npc = nullptr) const;

    /**
     * A crime against a person: their standing drops by Severity x 20 (Severity 0..1). The world subsystem calls
     * it from npc-unify's OnPlayerCrime (bound by name): the victim takes the full drop, a witness who is a person
     * a quarter of it.
     */
    UFUNCTION(BlueprintCallable, Category = "Quests|Consequences")
    void NotifyCrimeAgainst(FName PersonId, float Severity);

    /** npc-unify's crime names as 0..1 (Murder 1, Assault 0.5, Theft 0.35, anything else 0.2). */
    static float CrimeSeverity(FName Crime);

    /** Opens the journal (game flow's pause menu can call this by name). */
    UFUNCTION(BlueprintCallable, Category = "Quests")
    void OpenJournal();

    /** True while the journal is on screen (game flow's pause menu hides itself meanwhile). */
    UFUNCTION(BlueprintPure, Category = "Quests")
    bool IsJournalOpen() const;

    // ---- Events ----------------------------------------------------------------------------------------------

    UPROPERTY(BlueprintAssignable, Category = "Quests") FReflectionsQuestEvent OnQuestEvent;
    UPROPERTY(BlueprintAssignable, Category = "Quests") FReflectionsQuestUnlock OnUnlock;
    UPROPERTY(BlueprintAssignable, Category = "Quests") FReflectionsQuestGameEvent OnGameEvent;
    UPROPERTY(BlueprintAssignable, Category = "Quests") FReflectionsQuestStandingChanged OnStandingChanged;
    /** Anything in the quest state changed (journal and HUD refresh). */
    UPROPERTY(BlueprintAssignable, Category = "Quests") FReflectionsQuestsChanged OnQuestsChanged;

    // ---- Used by the world subsystem -------------------------------------------------------------------------

    /** Turns quest line defs into talk lines (default speaker filled in). */
    static TArray<FReflectionsQuestLine> ToLines(const TArray<FReflectionsQuestLineDef>& Defs, FName DefaultSpeaker);
    /** The after lines of a finished quest have been said. */
    void MarkAfterSaid(FName QuestId);
    /** Optional lines for a person from the active steps' Talk lists. */
    TArray<FReflectionsQuestLine> GetStepTalkLines(FName Person) const;
    /** The lives system's per-person gate (fear, hate, grief) for new quest offers, called by name. */
    bool IsOfferAllowedByLives(FName Person) const;

    /** Re-checks requirements: quests whose requirements are met become Available (auto-start ones start). */
    UFUNCTION(BlueprintCallable, Category = "Quests")
    void RefreshAvailability();
    /** Adds Delta to an objective of a quest's current step (clamped). */
    void AdvanceObjective(FName QuestId, FName ObjectiveId, int32 Delta);
    /** Sets an objective's progress (stateful objectives such as items held). */
    void SetObjectiveProgress(FName QuestId, FName ObjectiveId, int32 Progress);
    /** Protect: adds held time; completes at Seconds. */
    void AddHeldTime(FName QuestId, FName ObjectiveId, float Seconds);
    void MarkObjectiveSpawned(FName QuestId, FName ObjectiveId);
    FReflectionsObjectiveState* FindObjectiveState(FName QuestId, FName ObjectiveId);
    /** Progress text for an objective ("Find the ledger  1/3"). */
    FText FormatObjective(const FReflectionsQuestObjective& Objective, const FReflectionsObjectiveState* State) const;
    /** The next hint for the current step's first unfinished objective (and counts it). */
    FText TakeHint(FName QuestId);
    /** What a reward gives, in one line ("+2 mirror shards, +25 mana, Maren +15"). */
    FText DescribeReward(const FReflectionsQuestReward& Reward) const;

    /** A banner message the HUD shows once (quest started, objective done, reward). */
    struct FBanner { FText Kicker; FText Title; FText Detail; FLinearColor Color; };
    TArray<FBanner> PendingBanners;
    void PushBanner(const FText& Kicker, const FText& Title, const FText& Detail, const FLinearColor& Color);

    // ---- Save ------------------------------------------------------------------------------------------------

    UFUNCTION() void HandleCheckpointSaved(const FReflectionsCheckpoint& Checkpoint);
    /** World jump's OnProgressRestored: a checkpoint was applied; roll the quests back to it. */
    UFUNCTION() void HandleProgressRestored();
    /** Forget everything (new game). */
    void ResetAll();
    FReflectionsQuestSnapshot Capture() const;
    void Apply(const FReflectionsQuestSnapshot& Snapshot);
    static FString SlotName() { return TEXT("Reflections_Quests"); }

    UFUNCTION(BlueprintCallable, Category = "Quests|Debug")
    FString DescribeStatus() const;

    /** Set when an unlock may have made quests available; the world subsystem re-checks on its next tick. */
    bool bAvailabilityDirty = false;

private:
    /** Every known quest gets its state entry up front, so the state map never grows mid-update (references stay valid). */
    void EnsureStates();
    void LoadBuiltIns();
    void LoadPacks();
    void MergeQuest(const FReflectionsQuestDef& Def);
    void MergePerson(const FReflectionsQuestPerson& Person);
    FReflectionsQuestState& StateFor(FName QuestId);
    bool RequirementsMet(const FReflectionsQuestDef& Def) const;
    void StartStep(const FReflectionsQuestDef& Def, FReflectionsQuestState& State, int32 StepIndex);
    void CheckStepComplete(const FReflectionsQuestDef& Def, FReflectionsQuestState& State);
    void FinishStep(const FReflectionsQuestDef& Def, FReflectionsQuestState& State, FName ForcedNext);
    void FinishQuest(const FReflectionsQuestDef& Def, FReflectionsQuestState& State);
    void GiveReward(const FReflectionsQuestReward& Reward, FName QuestId);
    void Broadcast(FName QuestId, FName StepId, FName ObjectiveId, EReflectionsQuestEventType Type);
    void Changed();
    void AutoTrack();
    void ReadCheckpointSnapshot(const UReflectionsGameFlowSubsystem* Flow);
    /** Whether a quest still needs this person: an unfinished objective now or later, a choice, failIfDies. */
    bool StillNeeds(const FReflectionsQuestDef& Def, const FReflectionsQuestState& State, FName Person) const;
    /** Marks the current step's objectives that only this (dead) person could fulfil as done (main quest). */
    bool SkipObjectivesFor(const FReflectionsQuestDef& Def, FReflectionsQuestState& State, FName Person);
    TSet<FName> DeadPeople;

    TArray<FReflectionsQuestDef> Quests;
    TArray<FReflectionsQuestPerson> People;
    TArray<FReflectionsQuestItemDef> ItemDefs;
    TMap<FName, FName> MarkerAliases;
    UPROPERTY(Transient) TArray<TObjectPtr<UReflectionsQuestPack>> LoadedPacks;

    TMap<FName, FReflectionsQuestState> States;
    TMap<FName, int32> Items;
    TMap<FName, float> Standing;
    TSet<FName> Unlocks;
    FName Tracked;

    /** Taken with the last checkpoint; applied when that checkpoint is restored. */
    FReflectionsQuestSnapshot CheckpointSnapshot;
    bool bApplying = false;
    int32 ChangeDepth = 0;
};
