#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Hero/ReflectionsSpellEventSubsystem.h"
#include "NPC/ReflectionsNpcArchetype.h"
#include "ReflectionsNpcSubsystem.generated.h"

class ULevel;
class USoundBase;
class UReflectionsNpcReactionComponent;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_FourParams(FReflectionsNpcReactionEvent, AActor*, Npc, EReflectionsNpcReaction, Reaction, AActor*, Cause, FVector, Location);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FReflectionsNpcHitEvent, AActor*, Npc, const FReflectionsSpellHitData&, Hit);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FReflectionsNpcDeathEvent, AActor*, Npc, AActor*, Killer);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FReflectionsNpcInfectionEvent, AActor*, Npc, EReflectionsNpcInfection, State, AActor*, Source);
DECLARE_MULTICAST_DELEGATE_OneParam(FReflectionsNpcStimulusNative, const FReflectionsNpcStimulus&);
/** The player hurt or killed someone (or another crime was reported): once per witness, Witness null when nobody saw it. */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_FiveParams(FReflectionsPlayerCrimeEvent, AActor*, Victim, FName, Crime, AActor*, Witness, FVector, Location, float, Heat);

/**
 * The one place where spell hits and world events turn into NPC behaviour.
 *
 * - It is the only NPC-side listener to UReflectionsSpellEventSubsystem (OnSpellEvent, OnSpellHit).
 * - It enrols actors (tag NPC_Reactive, or EnrollActor at any time) by giving them health, the NPC component
 *   and, when needed, a hit capsule; the archetype comes from the actor's tags or from the caller.
 * - It owns the consequences: reputation, the coin an NPC is worth (world jump), infection (game flow).
 * - It keeps a short feed of stimuli for systems whose NPCs are not actors (the Mass crowd bridge).
 *
 * Everything else (the villain, quests, crowd code) calls in here instead of touching NPCs directly.
 */
UCLASS()
class REFLECTIONS_API UReflectionsNpcSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()

public:
    static UReflectionsNpcSubsystem* Get(const UObject* WorldContext);

    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;
    virtual void OnWorldBeginPlay(UWorld& World) override;
    virtual void Deinitialize() override;

    // ---- Archetypes ------------------------------------------------------------------------------------

    /** A data asset from /Game/NPC/Archetypes with this id, else the built-in type, else null. */
    UFUNCTION(BlueprintPure, Category="NPC")
    UReflectionsNpcArchetype* FindArchetype(FName Id);

    /** The archetype an actor's tags ask for (NPC_Type_<Id>, NPC_CombatEnemy, NPC_Guard, ...); Civilian if none. */
    UFUNCTION(BlueprintPure, Category="NPC")
    UReflectionsNpcArchetype* ResolveArchetype(const AActor* Actor);

    // ---- Enrolment -------------------------------------------------------------------------------------

    /**
     * Makes Actor an NPC of this system now: health, the NPC component, a hit capsule if it needs one.
     * Archetype null: taken from the actor's tags. Safe to call twice (the second call can change the archetype).
     */
    UFUNCTION(BlueprintCallable, Category="NPC")
    UReflectionsNpcReactionComponent* EnrollActor(AActor* Actor, UReflectionsNpcArchetype* Archetype = nullptr);

    /** Takes back what EnrollActor added at runtime (for pooled crowd actors). The actor itself is untouched. */
    UFUNCTION(BlueprintCallable, Category="NPC")
    void ReleaseActor(AActor* Actor);

    /** The NPC component for an actor; also resolves an NPC's hidden locomotion pawn to that NPC. */
    UFUNCTION(BlueprintPure, Category="NPC")
    UReflectionsNpcReactionComponent* FindNpc(const AActor* Actor) const;

    /** Every live NPC actor of this system. */
    UFUNCTION(BlueprintPure, Category="NPC")
    TArray<AActor*> GetNpcActors() const;

    void RegisterNpc(UReflectionsNpcReactionComponent* Npc);
    void UnregisterNpc(UReflectionsNpcReactionComponent* Npc);

    // ---- Spawning ---------------------------------------------------------------------------------------

    /**
     * Spawns an NPC of an archetype wearing one of the team's MetaHuman looks and enrols it: the one helper for
     * tests and gameplay (crafting dummies, squads, spell tests), so nobody spawns mannequins. Look null: the next
     * of the archetype's Looks (any team look if it has none). FacingYaw is where the NPC looks.
     */
    UFUNCTION(BlueprintCallable, Category="NPC")
    AActor* SpawnNpc(FName ArchetypeId, FVector Location, float FacingYaw = 0.0f, TSubclassOf<AActor> Look = nullptr);

    /** Every team MetaHuman look SpawnNpc may use. */
    static const TArray<TSoftClassPtr<AActor>>& TeamLooks();

    /**
     * The looks an NPC of this archetype may wear on a side ("Giltside", "Frostside", "Pewterside"): only that
     * side's people. The people in rags belong to Frostside and the people in red to Giltside; they are never
     * mixed. A side with no look for the archetype's role uses its own nearest role (its soldiers for its
     * guards and so on), never another side's. Pewterside, which has no looks of its own yet, borrows Giltside's
     * (logged once). Everyone who spawns or dresses an NPC picks from this list.
     */
    UFUNCTION(BlueprintCallable, Category="NPC")
    TArray<TSoftClassPtr<AActor>> GetLooksForSide(FName ArchetypeId, FName Side);

    /** The same, for the side a place is in (the world-jump side at that location). */
    UFUNCTION(BlueprintCallable, Category="NPC")
    TArray<TSoftClassPtr<AActor>> GetLooksAt(FName ArchetypeId, FVector Location);

    /** "Giltside", "Frostside" or "Pewterside": the side a place is in. */
    UFUNCTION(BlueprintPure, Category="NPC")
    FName GetSideAt(FVector Location) const;

    /**
     * How many living NPCs wear this look right now. SpawnNpc takes the least-worn look of its pool, so that copies
     * of one person only appear once every other look of the pool is in use; anyone who dresses an NPC another
     * way can prefer the lowest count and stay in step.
     */
    UFUNCTION(BlueprintPure, Category="NPC")
    int32 GetLookUseCount(TSoftClassPtr<AActor> Look) const;

    // ---- Voice -------------------------------------------------------------------------------------------

    /**
     * Who this NPC sounds like: sex from its look, a voice slot that never changes for the instance, and the
     * archetype's character. Audio's bark cues and the dialogue voice are both chosen from it.
     */
    UFUNCTION(BlueprintPure, Category="NPC|Voice")
    FReflectionsNpcVoiceProfile GetVoiceProfile(const AActor* Actor) const;

    /** Sex of a look: the actor tag NPC_Voice_F / NPC_Voice_M if present, else the table of team looks. */
    UFUNCTION(BlueprintPure, Category="NPC|Voice")
    static EReflectionsNpcSex GetLookSex(const AActor* Actor);

    /**
     * The cue of a line group (Civilian_Fear, Guard_Alert, Remark, Reply, Talk...) in this NPC's own voice, null
     * if audio has none. Looked for in /Game/Audio/Jam/Voice/Cues, most personal first:
     * <Group>/SCue_VO_<Group>_<VoiceId> (roster voice), SCue_VO_<Group>_<F1..M3> (slot), SCue_VO_<Group>.
     */
    UFUNCTION(BlueprintCallable, Category="NPC|Voice")
    USoundBase* FindVoiceCue(const AActor* Actor, FName Group);

    /** A voice of audio's roster by its id (V001...). False when the project has no roster or no such row. */
    UFUNCTION(BlueprintCallable, Category="NPC|Voice")
    bool FindVoiceRow(FName VoiceId, FReflectionsNpcVoiceRow& OutRow);

    /** Says one line of a group in this NPC's own voice (FindVoiceCue), from its head, at most every 4 s. */
    UFUNCTION(BlueprintCallable, Category="NPC|Voice")
    void PlayBark(AActor* Actor, FName Group);

    // ---- Allegiance (one answer for spells, crafted spells and aim assist) -------------------------------

    /** Against the player right now: an Enemy, Infected or VillainHost NPC, or any NPC currently attacking a player. */
    UFUNCTION(BlueprintPure, Category="NPC")
    bool IsHostileToPlayer(const AActor* Actor) const;

    /** On the same side: heals and wards from Caster should reach Target, and Caster's attacks should avoid it. */
    UFUNCTION(BlueprintPure, Category="NPC")
    bool IsAllyOf(const AActor* Target, const AActor* Caster) const;

    /**
     * Whether Caster's spell should damage Target. The player can hurt anyone (hurting bystanders costs
     * reputation); NPCs do not hurt their own side.
     */
    UFUNCTION(BlueprintPure, Category="NPC")
    bool CanBeHarmedBy(const AActor* Target, const AActor* Caster) const;

    // ---- Events in -------------------------------------------------------------------------------------

    /** Something NPCs can notice happened. Spell noise arrives by itself; call this for everything else. */
    UFUNCTION(BlueprintCallable, Category="NPC")
    void ReportStimulus(const FReflectionsNpcStimulus& Stimulus);

    /** A spell hit an actor. Arrives by itself from OnSpellHit; public for code that hits without that event. */
    UFUNCTION(BlueprintCallable, Category="NPC")
    void ReportSpellHit(const FReflectionsSpellHitData& Hit);

    /** An NPC that never was an actor (a Mass entity) died: coin, reputation and a Death stimulus for witnesses. */
    UFUNCTION(BlueprintCallable, Category="NPC")
    void ReportAnonymousDeath(FVector Location, FName ArchetypeId, AActor* Killer);

    // ---- Infection and possession ----------------------------------------------------------------------

    /**
     * Infects, possesses, burns out or cures an NPC (None cures). Enrols the actor if it is not an NPC yet,
     * swaps its behaviour to the Infected / VillainHost archetype (or back), lifts and restores the Friendly
     * tag, and keeps game flow's infection meter in step. Returns false if the state did not change.
     */
    UFUNCTION(BlueprintCallable, Category="NPC")
    bool SetInfection(AActor* Actor, EReflectionsNpcInfection State, AActor* Source);

    UFUNCTION(BlueprintPure, Category="NPC")
    EReflectionsNpcInfection GetInfection(const AActor* Actor) const;

    /** Hands an NPC to a set piece for at most Seconds (see UReflectionsNpcReactionComponent::BeginScriptedHold). */
    UFUNCTION(BlueprintCallable, Category="NPC")
    void HoldNpc(AActor* Actor, float Seconds);
    UFUNCTION(BlueprintCallable, Category="NPC")
    void ReleaseNpc(AActor* Actor);

    /**
     * Asks the villain system to run its conversion sequence on a hunter and the NPC it reached, and holds both
     * for its length. False (nothing held) when there is no villain system, it refuses, or the victim is no NPC.
     * Called by the NPC component; the villain ends it with SetInfection(Victim, Infected, Attacker).
     */
    bool TryBeginConversion(UReflectionsNpcReactionComponent* Attacker, AActor* Victim);

    /**
     * Plays the NPC's Remark line (FindVoiceCue) from its head if no other remark is playing anywhere and audio
     * has one for its voice. Called by the NPC component when the player walks up to a calm NPC.
     */
    bool TryPlayRemark(UReflectionsNpcReactionComponent* Npc);

    // ---- Events out ------------------------------------------------------------------------------------

    UPROPERTY(BlueprintAssignable, Category="NPC")
    FReflectionsNpcReactionEvent OnNpcReaction;

    /** After the NPC has reacted to a spell hit (lethal or not). */
    UPROPERTY(BlueprintAssignable, Category="NPC")
    FReflectionsNpcHitEvent OnNpcSpellHit;

    UPROPERTY(BlueprintAssignable, Category="NPC")
    FReflectionsNpcDeathEvent OnNpcDied;

    UPROPERTY(BlueprintAssignable, Category="NPC")
    FReflectionsNpcInfectionEvent OnNpcInfection;

    // ---- Heat: what the player's violence costs ----------------------------------------------------------

    /**
     * Fired for every crime of the player: "Assault" (a spell of theirs hurt a non-hostile NPC), "Murder" (it
     * killed one), or whatever ReportPlayerCrime was given. Once per witness; a single broadcast with a null
     * Witness when nobody saw it. Heat is the value after the crime.
     */
    UPROPERTY(BlueprintAssignable, Category="NPC")
    FReflectionsPlayerCrimeEvent OnPlayerCrime;

    /**
     * 0..1: how wanted the player is right now. Rises with every witnessed crime; from 0.5 the armed and lawful
     * (guards and the like) in sight turn on the player; decays once none of them has seen the player for a while.
     */
    UFUNCTION(BlueprintPure, Category="NPC")
    float GetPlayerHeat() const;

    /** A crime of the player that the NPC system did not see for itself ("Theft", "Arson", "Trespass", ...). */
    UFUNCTION(BlueprintCallable, Category="NPC")
    void ReportPlayerCrime(AActor* Victim, FName Crime, FVector Location);

    /** The player's record is wiped: heat to zero at once, and whoever was after them for it stands down. */
    UFUNCTION(BlueprintCallable, Category="NPC")
    void ClearPlayerHeat();

    /** An NPC that is after the player because of heat still sees them: the heat does not cool yet. */
    void NoteHeatSeen();

    /** Says a line group in the NPC's voice at once (a reaction to being hit does not wait for the bark cooldown). */
    UFUNCTION(BlueprintCallable, Category="NPC|Voice")
    void PlayReaction(AActor* Actor, FName Group);

    /** A cue of the jam's audio by its path under /Game/Audio/Jam ("Cues/SCue_Shock_Loop"), or null. */
    USoundBase* FindJamCue(const FString& RelativePath) { return FindBarkCue(RelativePath); }

    /** Every stimulus as it arrives, for non-actor crowds. Game thread. */
    FReflectionsNpcStimulusNative& OnStimulus() { return StimulusEvent; }

    /** Stimuli received in the last StimulusMemorySeconds, oldest first. Game thread. */
    const TArray<FReflectionsNpcStimulus>& GetActiveStimuli();

    /** Reputation of whoever caused something (0 for non-players and when unknown). */
    float GetReputation(AActor* Instigator) const;

    // ---- Called by the NPC component -------------------------------------------------------------------

    void NotifyReaction(UReflectionsNpcReactionComponent* Npc, EReflectionsNpcReaction Reaction, AActor* Cause, const FVector& Location);
    void NotifyDied(UReflectionsNpcReactionComponent* Npc, AActor* Killer);
    void NotifyHealed(UReflectionsNpcReactionComponent* Npc, AActor* Healer, float Amount);

    static constexpr float StimulusMemorySeconds = 1.5f;

private:
    UFUNCTION() void HandleSpellEvent(EHeroSpell Spell, FVector Location, AActor* Caster, float Intensity);
    UFUNCTION() void HandleSpellHit(const FReflectionsSpellHitData& Hit);
    void HandleActorSpawned(AActor* Actor);
    void HandleLevelAdded(ULevel* Level, UWorld* World);
    void EnrollIfTagged(AActor* Actor);
    void LoadArchetypeAssets();
    void PruneStimuli();
    void AssignVoice(UReflectionsNpcReactionComponent* Npc);
    void LoadVoiceRoster();
    UPROPERTY(Transient) TObjectPtr<class UDataTable> VoiceRoster;
    bool bRosterLoaded = false;
    void PlayCueFromHead(UReflectionsNpcReactionComponent* Npc, USoundBase* Cue);
    float RemarkBusyUntil = 0.0f;
    float PlayerHeat = 0.0f;
    float HeatCoolsFrom = 0.0f;
    class USoundBase* FindBarkCue(const FString& Name);
    UPROPERTY(Transient) TMap<FString, TObjectPtr<class USoundBase>> BarkCues;
    int32 NextLookIndex = 0;
    void ReportToInfectionMeter(AActor* Host, bool bInfected) const;
    void RewardCoin(const UReflectionsNpcArchetype& Archetype, const FVector& HomeLocation, const FVector& DeathLocation, AActor* Owner);

    UPROPERTY(Transient) TMap<FName, TObjectPtr<UReflectionsNpcArchetype>> Archetypes;
    TArray<TWeakObjectPtr<UReflectionsNpcReactionComponent>> Npcs;
    TArray<FReflectionsNpcStimulus> ActiveStimuli;
    FReflectionsNpcStimulusNative StimulusEvent;
    FDelegateHandle SpawnedHandle;
    FDelegateHandle LevelAddedHandle;
    bool bAssetsLoaded = false;
};
