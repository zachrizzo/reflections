#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Subsystems/WorldSubsystem.h"
#include "Hero/ReflectionsSpellEventSubsystem.h"
#include "NPC/ReflectionsNpcArchetype.h"
#include "Lives/ReflectionsLivesTypes.h"
#include "Lives/ReflectionsPeopleBook.h"
#include "ReflectionsLivesSubsystem.generated.h"

class ACharacter;
class APlayerController;
class UCanvas;
class UInputComponent;
class UReflectionsLivesMemory;
class UReflectionsNpcReactionComponent;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FReflectionsLivesHourChanged, int32, Hour);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FReflectionsLifeEvent, FName, PersonId, AActor*, Actor, const FString&, What);

/**
 * Marks an NPC actor as a person of the people book. Added by UReflectionsLivesSubsystem; read-only for others.
 * Find it with Actor->FindComponentByClass, or ask the subsystem (GetPersonId, GetPersonaFacts).
 */
UCLASS(ClassGroup=(Lives), BlueprintType)
class REFLECTIONS_API UReflectionsLifeComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UReflectionsLifeComponent();

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Lives") FName PersonId;
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Lives") FString PersonName;
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Lives") EReflectionsLifeActivity Activity = EReflectionsLifeActivity::Idle;
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Lives") FName Place;
};

/** Runtime state of one life (not reflected; owned by UReflectionsLivesSubsystem). */
enum class EReflectionsLifeMove : uint8 { None, Travel, Mill, Meet, Chat, Inside };

struct FReflectionsLifeRuntime
{
    FReflectionsPerson Person;
    TArray<FReflectionsScheduleStep> Schedule;
    TWeakObjectPtr<AActor> Actor;
    TWeakObjectPtr<UReflectionsNpcReactionComponent> Brain;
    TWeakObjectPtr<UReflectionsLifeComponent> Comp;
    bool bSpawnedByLives = false;
    bool bCrowdAgent = false;
    /** A short-lived passer-by of the crowd's ring (Crowd_Ring): a person, but crowd's stroll owns the body. */
    bool bAmbient = false;
    EReflectionsLifeLod Lod = EReflectionsLifeLod::Virtual;

    int32 StepIndex = INDEX_NONE;
    FName PlaceTag;
    EReflectionsLifeActivity Activity = EReflectionsLifeActivity::Idle;
    FVector PlaceLocation = FVector::ZeroVector;
    float PlaceRadius = 300.0f;
    bool bIndoorStep = false;

    EReflectionsLifeMove Move = EReflectionsLifeMove::None;
    FVector Goal = FVector::ZeroVector;
    TArray<FVector> Path;
    int32 PathIndex = 0;
    float StuckTime = 0.0f;
    int32 Repaths = 0;
    FVector LastPos = FVector::ZeroVector;
    float Idle = 0.0f;
    float Speed = 135.0f;
    bool bSteering = false;
    bool bGaitSet = false;
    bool bInside = false;
    bool bHeld = false;
    /** World time before which the body is not claimed (the crowd stroll releases within its 1 s refresh). */
    float ClaimNotBefore = 0.0f;
    /** The crowd chat director is playing a baked conversation for this pair (leader only). */
    bool bDirectorChat = false;
    /** SetLifePaused: Lives leaves the body alone. */
    bool bPaused = false;
    float NextDirectorCheck = 0.0f;
    /** Story conversations this person has already had (never twice in a run). */
    TSet<FName> PlayedConversations;

    FName ChatWith;
    float ChatRemaining = 0.0f;
    float NextChatLine = 0.0f;
    int32 ChatLines = 0;
    TMap<FName, double> LastChatHours;

    float NextThink = 0.0f;
    double NextGreetTime = 0.0;
    double LastCastNearHours = -100.0;
    double AvoidStepUntilHours = 0.0;
    FString LastReactionText;
    double LastReactionTime = -100.0;
    /** Walking away from the player (world seconds); bShyRun: afraid, at a run. */
    double ShyUntil = 0.0;
    bool bShy = false;
    bool bShyRun = false;
    /** World seconds of the last crime by the player this person took in (one report per crime). */
    double LastCrimeTime = -100.0;
    uint32 Seed = 1;
};

/**
 * Every NPC's own life: who they are (the people book), their day (a compressed game clock and a schedule that
 * walks them between home, work, haunts and friends), the people they know (who they meet, who they mourn) and
 * what they remember of the player.
 *
 * Bodies: a calm NPC with a life is steered by this subsystem through UReflectionsNpcReactionComponent::
 * SetExternallySteered (the crowd's stroll lets it go: NPC_NoStroll). Any other reaction hands the body straight
 * back to the NPC system, which flees, fights and dies as before. Places are quest markers (actors tagged or
 * named Home_<id>, Work_<job>, Haunt_<place>, optional Door_<place>), placed automatically when a map has none.
 *
 * The clock exposes time of day; it does not light the world (the map owner reads GetTimeOfDayHours).
 * Console: Lives.Debug 0|1|2 (or F7), Lives.SetHour <h>, Lives.TimeScale <x>, Lives.Dump, Lives.TestWitness [name].
 */
UCLASS(BlueprintType)
class REFLECTIONS_API UReflectionsLivesSubsystem : public UTickableWorldSubsystem
{
    GENERATED_BODY()

public:
    static UReflectionsLivesSubsystem* Get(const UObject* WorldContext);

    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;
    virtual void OnWorldBeginPlay(UWorld& InWorld) override;
    virtual void Deinitialize() override;
    virtual void Tick(float DeltaTime) override;
    virtual TStatId GetStatId() const override;
    virtual bool IsTickable() const override { return bBegun; }

    // ---- Clock --------------------------------------------------------------------------------------------

    /** 0..24. */
    UFUNCTION(BlueprintPure, Category="Lives|Clock")
    float GetTimeOfDayHours() const;
    /** 0..1 over the day (0 = midnight). */
    UFUNCTION(BlueprintPure, Category="Lives|Clock")
    float GetDayFraction() const { return GetTimeOfDayHours() / 24.0f; }
    UFUNCTION(BlueprintPure, Category="Lives|Clock")
    int32 GetDay() const;
    /** "07:45". */
    UFUNCTION(BlueprintPure, Category="Lives|Clock")
    FString GetClockText() const;
    UFUNCTION(BlueprintCallable, Category="Lives|Clock")
    void SetTimeOfDay(float Hour);
    /** Real minutes per in-game day (from the people book; 24 by default). */
    UFUNCTION(BlueprintPure, Category="Lives|Clock")
    float GetRealMinutesPerDay() const { return Book.RealMinutesPerDay; }

    UPROPERTY(BlueprintAssignable, Category="Lives|Clock")
    FReflectionsLivesHourChanged OnHourChanged;

    // ---- Identity (whitelisted for dialogue) --------------------------------------------------------------

    /** The person an NPC actor (or its hidden locomotion pawn) is; None if it has no life. */
    UFUNCTION(BlueprintPure, Category="Lives")
    FName GetPersonId(const AActor* Actor) const;
    UFUNCTION(BlueprintPure, Category="Lives")
    AActor* FindActorForPerson(FName PersonId) const;
    UFUNCTION(BlueprintPure, Category="Lives")
    FString GetPersonName(FName PersonId) const;
    /** True if the person is in the book or alive in this world. Fills OutPerson (with its secret: not for dialogue). */
    bool FindPerson(FName PersonId, FReflectionsPerson& OutPerson) const;

    /** Facts the dialogue persona may use. bValid false for actors without a life. */
    UFUNCTION(BlueprintPure, Category="Lives")
    FReflectionsPersonaFacts GetPersonaFacts(const AActor* Actor) const;
    /** The same facts as a ready persona block (a few short lines); empty for actors without a life. */
    UFUNCTION(BlueprintPure, Category="Lives")
    FString GetPersonaText(const AActor* Actor) const;
    /** How this person would greet the player now, as a direction for a writer or a live reply (not a line). */
    UFUNCTION(BlueprintPure, Category="Lives")
    FString GetGreetingHint(const AActor* Actor) const;
    /** The bark group a greeting would use now (Greet_Warm, Greet_Cold, Greet_Afraid, Greet_Grieving, Greet_Neutral). */
    UFUNCTION(BlueprintPure, Category="Lives")
    FName GetGreetingGroup(const AActor* Actor) const;

    // ---- Memory of the player -----------------------------------------------------------------------------

    UFUNCTION(BlueprintCallable, Category="Lives|Memory")
    void RememberPlayer(AActor* Actor, EReflectionsPlayerDeed Deed, float Weight = 1.0f);
    UFUNCTION(BlueprintCallable, Category="Lives|Memory")
    void RememberPlayerById(FName PersonId, EReflectionsPlayerDeed Deed, float Weight = 1.0f, const FString& Note = TEXT(""));
    UFUNCTION(BlueprintPure, Category="Lives|Memory")
    FReflectionsPlayerMemory GetPlayerMemory(FName PersonId) const;
    UFUNCTION(BlueprintPure, Category="Lives|Memory")
    EReflectionsLifeMood GetMood(FName PersonId) const;
    /** False when the person is dead, tarnished, grieving, afraid, or thinks badly of the player. */
    UFUNCTION(BlueprintPure, Category="Lives|Memory")
    bool IsQuestAvailable(FName PersonId) const;
    UFUNCTION(BlueprintCallable, Category="Lives|Memory")
    void CompleteQuestFor(FName PersonId);
    /**
     * The player committed a crime (Assault, Murder, Theft, Arson, Trespass...) against Victim (may be null) at Location.
     * Witness: the one person who saw it, or null to let Lives work out who saw it (sight and hearing distance).
     * Lives also listens to the NPC system's OnPlayerCrime, so callers of that need not call this as well.
     */
    UFUNCTION(BlueprintCallable, Category="Lives|Memory")
    void ReportPlayerCrime(FName Crime, AActor* Victim, FVector Location, AActor* Witness);
    /** 0: no strong feeling, 1: afraid of the player, 2: hates the player. Both keep out of the player's way. */
    UFUNCTION(BlueprintPure, Category="Lives|Memory")
    int32 GetPlayerFeeling(FName PersonId) const;

    // ---- Story and set pieces ------------------------------------------------------------------------------

    /** A story flag of side-quests.md (Hal_Home, Drifters_Stay, Bell_Lane_Lit...). Saved with checkpoints. */
    UFUNCTION(BlueprintCallable, Category="Lives|Story")
    void SetStoryFlag(FName Flag, bool bOn = true);
    UFUNCTION(BlueprintPure, Category="Lives|Story")
    bool HasStoryFlag(FName Flag) const;

    /**
     * The person's actor, spawned now at Location if they have none (a team look of their sex, their own voice,
     * tagged Person_<id>). Lives keeps driving their day afterwards and never removes them by itself. Null if the
     * person is unknown, dead or tarnished.
     */
    UFUNCTION(BlueprintCallable, Category="Lives|Story")
    AActor* SpawnPerson(FName PersonId, FVector Location, float FacingYaw = 0.0f);

    /**
     * Lives lets go of this body and leaves it alone until unpaused (cutscenes, set pieces). The actor tag Lives_Hold
     * does the same. HoldNpc / BeginScriptedHold on the NPC system also make Lives let go.
     */
    UFUNCTION(BlueprintCallable, Category="Lives|Story")
    void SetLifePaused(AActor* Actor, bool bPaused);

    // ---- Crowd bridge (Mass pedestrians have persons too) -------------------------------------------------

    /** A stable generated person for a crowd agent key (same key, same person). Tag a promoted actor Lives_Person_<Id>. */
    UFUNCTION(BlueprintCallable, Category="Lives|Crowd")
    FName ClaimPersonForCrowdAgent(int32 AgentKey);
    /** Where the person's schedule wants them now. False if they are inside, dead or unknown. */
    UFUNCTION(BlueprintCallable, Category="Lives|Crowd")
    bool GetPersonGoal(FName PersonId, FVector& OutGoal) const;

    // ---- Places --------------------------------------------------------------------------------------------

    UFUNCTION(BlueprintCallable, Category="Lives|Places")
    bool FindPlace(FName Tag, FReflectionsLifePlace& OutPlace);
    UFUNCTION(BlueprintPure, Category="Lives|Places")
    TArray<FReflectionsLifePlace> GetPlaces() const;

    // ---- Events and debug ---------------------------------------------------------------------------------

    /** Something happened in a person's life ("saw Tom Vell taken by the Tarnish", "met Jo Ash at Haunt_Market"). */
    UPROPERTY(BlueprintAssignable, Category="Lives")
    FReflectionsLifeEvent OnLifeEvent;

    UFUNCTION(BlueprintCallable, Category="Lives|Debug")
    void SetDebugLevel(int32 Level);
    UFUNCTION(BlueprintPure, Category="Lives|Debug")
    int32 GetDebugLevel() const;
    /** One line per life: id, name, activity, place, LOD, mood, opinion, distance to goal. */
    UFUNCTION(BlueprintCallable, Category="Lives|Debug")
    FString Describe() const;
    /** Test: takes (SetInfection Infected) a person someone nearby knows; returns "<witness> saw <victim>" or empty. */
    UFUNCTION(BlueprintCallable, Category="Lives|Debug")
    FString TestWitness(const FString& WitnessName);
    UFUNCTION(BlueprintCallable, Category="Lives|Debug")
    int32 GetLifeCount() const { return Lives.Num(); }
    UFUNCTION(BlueprintCallable, Category="Lives|Debug")
    int32 GetEmbodiedCount() const;

private:
    using FLife = FReflectionsLifeRuntime;
    using EMove = EReflectionsLifeMove;
    enum class EWitnessed : uint8 { Hurt, Killed, Taken, Healed, Saved };

    // Setup
    void BeginLives();
    void BindEvents();
    void EnsureInput();
    void DiscoverPlaces();
    FReflectionsLifePlace& AutoPlace(FName Tag, const FLife* For);
    bool FindStoryMarker(FName Tag, FReflectionsLifePlace& OutPlace);
    FVector GroundPoint(const FVector& Near) const;

    // Population
    void RefreshPopulation();
    FLife* Embody(AActor* Actor, UReflectionsNpcReactionComponent* Brain);
    FLife& AddLife(const FReflectionsPerson& Person);
    void LinkGeneratedFriends(FLife& Life);
    void Disembody(FLife& Life, bool bDestroySpawned);
    void SpawnNamedNearPlayer();
    FLife* FindLife(FName Id) { return Lives.Find(Id); }
    const FLife* FindLife(FName Id) const { return Lives.Find(Id); }
    FLife* FindLifeByActor(const AActor* Actor);
    const FLife* FindLifeByActor(const AActor* Actor) const;
    FString UniqueName(const FReflectionsPerson& Person, int32& Salt) const;

    // Schedule
    void Think(FLife& Life, float Now);
    /** The Tarnish meter's band now (quiet, spreading, rising, brink), None without bands. */
    FName CurrentBand() const;
    int32 CurrentStepIndex(const FLife& Life, float Hour) const;
    FName ResolveWhere(const FLife& Life, const FReflectionsScheduleStep& Step, int32 StepIndex, int32 Depth = 0) const;
    static EReflectionsLifeActivity ActivityFor(FName Do);
    FString NextStepText(const FLife& Life) const;
    bool IsOut(const FLife& Life) const { return !Life.bIndoorStep || Life.Move != EMove::Inside; }

    // Bodies
    bool CanSteer(const FLife& Life) const;
    void Steer(FLife& Life, float DeltaTime);
    void TakeBody(FLife& Life);
    void ReleaseBody(FLife& Life);
    void GoInside(FLife& Life);
    void ComeOut(FLife& Life);
    void SetGoal(FLife& Life, const FVector& Goal, EMove Move);
    void FacePoint(FLife& Life, const FVector& Point, float DeltaTime);
    ACharacter* DriverOf(const FLife& Life) const;

    // Relationships
    FString RelationTo(const FLife& Who, FName Other) const;
    bool Knows(const FLife& Who, FName Other) const { return !RelationTo(Who, Other).IsEmpty(); }
    void TryMeet(FLife& Life, float Now);
    void TickChat(FLife& Life, float DeltaTime);
    void EndChat(FLife& Life);
    bool PlayChatLine(FLife& Speaker, FLife& Listener);
    /** Calls a (const AActor*) -> bool function of the chat director by name; false if there is none. */
    bool CallDirector(const TCHAR* Function, AActor* Actor, bool& bOutResult) const;
    /** Calls a (TArray<AActor*> Speakers, FName) -> bool function of the chat director by name. */
    bool CallDirectorConversation(const TCHAR* Function, const TArray<AActor*>& Speakers, FName Arg) const;
    /** A story-clique conversation of audio's DT_StoryConversations for these two, played through the director. */
    bool TryStoryConversation(FLife& A, FLife& B);
    UPROPERTY(Transient) TObjectPtr<class UDataTable> StoryConversations;
    bool bTriedStoryConversations = false;
    void TryGreet(FLife& Life, double Now, const FVector& PlayerLocation);

    // Witnessing and memory
    UFUNCTION() void HandleNpcHit(AActor* Npc, const FReflectionsSpellHitData& Hit);
    UFUNCTION() void HandleNpcDied(AActor* Npc, AActor* Killer);
    UFUNCTION() void HandleNpcInfection(AActor* Npc, EReflectionsNpcInfection State, AActor* Source);
    UFUNCTION() void HandleSpellEvent(EHeroSpell Spell, FVector Location, AActor* Caster, float Intensity);
    /** Bound by name to the NPC system's OnPlayerCrime (Victim, Crime, Witness, Location, Heat). */
    UFUNCTION() void HandlePlayerCrime(AActor* Victim, FName Crime, AActor* Witness, FVector Location, float Heat);
    void BindCrimeEvent();
    void CrimeSeenBy(FLife& W, FName Crime, const FLife* VictimLife, const FVector& Where, bool bSaw);
    /** Keeps people who fear or hate the player out of their way (near the player only). */
    void TickShy(FLife& Life, double Now, const FVector& PlayerLocation);
    /** Body facts from the look's tags (crowd-looks): Giltside/Frostside/Pewterside, Civilian/Guard/Soldier/Caster. */
    static FName BodySide(const AActor* Body);
    static FName BodyRole(const AActor* Body);
    static bool SameSide(FName A, FName B);
    static bool IsSoldierPerson(const FReflectionsPerson& Person);
    void Witness(AActor* Victim, EWitnessed What, AActor* Instigator, const FVector& Where);
    void ReactTo(FLife& Witness, const FLife* VictimLife, const FString& VictimName, EWitnessed What, bool bPlayerDidIt,
        const FVector& Where, bool bSaw, const FString& Relation);
    void AddEvent(FReflectionsPersonState& State, const FString& Text);
    void SetMood(FName PersonId, EReflectionsLifeMood Mood, float Hours, FName ConcernFor);
    void RefreshMood(FReflectionsPersonState& State) const;
    static bool IsPlayer(const AActor* Actor);
    static FString DeedText(EReflectionsPlayerDeed Deed);
    static FString MoodText(EReflectionsLifeMood Mood);
    static FString ActivityText(EReflectionsLifeActivity Activity);
    FString PlayerMemoryText(const FLife& Life) const;
    void ApplyStoryOverrides(FLife& Life) const;
    AActor* SpawnLife(FLife& Life, const FVector& Location, float FacingYaw);

    // Debug
    /** Builds the F7 view (Slate, on the game viewport) from the lives in sight. */
    void UpdateOverlay();
    void ToggleDebug();

    FReflectionsPeopleBook Book;
    TMap<FName, FLife> Lives;
    TMap<FName, FReflectionsLifePlace> Places;
    TMap<int32, FName> CrowdAgents;
    TSet<FString> UsedNames;
    FVector AutoCenter = FVector::ZeroVector;
    bool bHaveAutoCenter = false;
    TWeakObjectPtr<UReflectionsLivesMemory> Memory;
    double LocalHours = 8.0;
    int32 LastHour = -1;
    float NextPopulation = 0.0f;
    float NextSpawnCheck = 0.0f;
    float NextPlaceScan = 0.0f;
    float BeginDelay = 0.75f;
    bool bBegun = false;
    bool bStarted = false;
    bool bEventsBound = false;
    bool bCrimeBound = false;
    /** The memory generation this world began on (see UReflectionsLivesMemory::Generation). */
    uint32 MemoryGeneration = 0;
    float NextCrimeBindTry = 0.0f;
    UPROPERTY(Transient) TObjectPtr<UInputComponent> DebugInput;
    TSharedPtr<class SReflectionsLivesOverlay> Overlay;
    /** F7 / SetDebugLevel: this world only, starts off every Play (the console variable Lives.Debug is separate). */
    int32 DebugLevel = 0;
};
