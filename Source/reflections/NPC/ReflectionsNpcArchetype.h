#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "Engine/DataTable.h"
#include "Hero/ReflectionsHeroCharacter.h"
#include "ReflectionsNpcArchetype.generated.h"

class UAnimSequence;
class UStaticMesh;

UENUM(BlueprintType)
enum class EReflectionsNpcDisposition : uint8 { Timid, Civilian, Brave, Guard, Enemy, Infected, VillainHost };

UENUM(BlueprintType)
enum class EReflectionsNpcReaction : uint8 { Calm, Alert, Fleeing, Investigating, Defending, Attacking, Incapacitated };

/** What happened in the world. Spells arrive as SpellNoise; anything else is reported by gameplay code. */
UENUM(BlueprintType)
enum class EReflectionsNpcStimulusKind : uint8
{
    /** Loud magic nearby (an area spell, a projectile impact). */
    SpellNoise,
    /** Non-magical danger: a brawl, a weapon strike. Treated like SpellNoise. */
    Violence,
    /** Somebody died here. Frightens more than the noise that caused it. */
    Death,
    /** Somebody was taken by the villain here. */
    Infection,
    /** A call for help: frightens nobody, brings the brave and the guards. */
    Alarm,
};

/** What loud magic (or any other stimulus) makes this kind of NPC do. */
UENUM(BlueprintType)
enum class EReflectionsNpcNoiseResponse : uint8 { FleeWhenAfraid, Investigate, Attack, Ignore };

UENUM(BlueprintType)
enum class EReflectionsNpcInfection : uint8
{
    None,
    /** One of his: counted on the infection meter, attacks the player. */
    Infected,
    /** He is inside this body. */
    VillainHost,
    /** Spent. Behaves as it did before, never counted again. */
    BurnedOut,
};

UENUM(BlueprintType)
enum class EReflectionsNpcHomeWorld : uint8 { FromSpawnLocation, Gray, Red, White };

UENUM(BlueprintType)
enum class EReflectionsNpcCoinReward : uint8
{
    None,
    /** Straight into the player's purse (UReflectionsWorldLibrary::AwardCoin). */
    Purse,
    /** A coin to walk over where the NPC fell (UReflectionsWorldLibrary::DropCoin). */
    Pickup,
};

UENUM(BlueprintType)
enum class EReflectionsNpcSex : uint8 { Unknown, Female, Male };

/** Who an NPC sounds like. Stable for the NPC's life, so its barks and its dialogue voice always match. */
USTRUCT(BlueprintType)
struct REFLECTIONS_API FReflectionsNpcVoiceProfile
{
    GENERATED_BODY()

    /** From the NPC's look (or the actor tag NPC_Voice_F / NPC_Voice_M). */
    UPROPERTY(BlueprintReadOnly, Category="NPC|Voice") EReflectionsNpcSex Sex = EReflectionsNpcSex::Unknown;
    /** 0..2: which of the three voices of that sex. Nearby NPCs of one sex get different slots while there are free ones. */
    UPROPERTY(BlueprintReadOnly, Category="NPC|Voice") int32 Slot = 0;
    /** How it talks, from the archetype it behaves as now: Civilian, Guard, Soldier or Tarnished. */
    UPROPERTY(BlueprintReadOnly, Category="NPC|Voice") FName Character = NAME_None;
    UPROPERTY(BlueprintReadOnly, Category="NPC|Voice") FName ArchetypeId = NAME_None;
    /** F1..F3 or M1..M3: the suffix of audio's cues, SCue_VO_<Group>_<CueSuffix>. */
    UPROPERTY(BlueprintReadOnly, Category="NPC|Voice") FString CueSuffix;
    /** This NPC's voice in audio's roster table (V001...), None while the project has no roster. */
    UPROPERTY(BlueprintReadOnly, Category="NPC|Voice") FName VoiceId = NAME_None;
    /** The roster's id of the designed voice, for live and cached replies; empty without a roster voice. */
    UPROPERTY(BlueprintReadOnly, Category="NPC|Voice") FString GeminiVoice;
};

/**
 * One voice of audio's roster, the DataTable /Game/Audio/Jam/Voice/DT_NpcVoiceRoster. The row name is the
 * VoiceId (V001...). Audio owns the table and its contents; the NPC system only reads it to give each NPC a voice.
 */
USTRUCT(BlueprintType)
struct REFLECTIONS_API FReflectionsNpcVoiceRow : public FTableRowBase
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Voice") EReflectionsNpcSex Sex = EReflectionsNpcSex::Unknown;
    /** The side the voice was designed for: Pewterside, Giltside or Frostside. None: any side. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Voice") FName Side = NAME_None;
    /** Which kinds of NPC it suits (an archetype's VoiceCharacter: Civilian, Guard, Soldier, Tarnished). Empty: any. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Voice") TArray<FName> Characters;
    /** Rough age in years, for whoever directs the delivery; 0 when unknown. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Voice") int32 Age = 0;
    /** How the voice was designed, in a sentence. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Voice") FString Description;
    /** The designed voice's id at the speech service, for live and cached replies. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Voice") FString GeminiVoice;
    /** Off: nobody is given this voice (a bad take can be dropped without renumbering). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Voice") bool bEnabled = true;
};

/** One thing NPCs can notice. Intensity uses the spell-event scale: 20 is full strength at zero distance. */
USTRUCT(BlueprintType)
struct REFLECTIONS_API FReflectionsNpcStimulus
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC") EReflectionsNpcStimulusKind Kind = EReflectionsNpcStimulusKind::SpellNoise;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC") FVector Location = FVector::ZeroVector;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC") float Intensity = 20.0f;
    /** 0 uses each NPC's own awareness radius. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC", meta=(Units="cm")) float Radius = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC") TWeakObjectPtr<AActor> Instigator;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC") EHeroSpell Spell = EHeroSpell::Fire;
    /** World time the subsystem received it. */
    UPROPERTY(BlueprintReadOnly, Category="NPC") double WorldTime = 0.0;
};

/** How an NPC type feels and decides. Plain data: copy it anywhere (a Mass shared fragment, for example). */
USTRUCT(BlueprintType)
struct REFLECTIONS_API FReflectionsNpcReactionProfile
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Senses", meta=(ClampMin="1", Units="cm"))
    float AwarenessRadius = 1400.0f;

    /** Fear added by a full-strength stimulus. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Fear", meta=(ClampMin="0"))
    float FearPerNoise = 0.45f;
    /** Above this fear the NPC runs (when NoiseResponse is FleeWhenAfraid); below it, it only looks up. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Fear", meta=(ClampMin="0", ClampMax="1"))
    float FleeFearThreshold = 0.18f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Fear", meta=(ClampMin="0"))
    float FearPerHit = 0.6f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Aggression", meta=(ClampMin="0"))
    float AggressionPerNoise = 0.6f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Aggression", meta=(ClampMin="0"))
    float AggressionPerHit = 0.7f;
    /** A hit turns into an attack once aggression reaches this (and bFightsBack and bCanAttack are set). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Aggression", meta=(ClampMin="0", ClampMax="1"))
    float AttackAggressionThreshold = 0.5f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Behaviour")
    EReflectionsNpcNoiseResponse NoiseResponse = EReflectionsNpcNoiseResponse::FleeWhenAfraid;
    /** Hit: fight (true) or run (false). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Behaviour")
    bool bFightsBack = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Behaviour")
    bool bCanAttack = false;
    /** Attacks whoever causes a stimulus once their reputation is at or below HostileBelowReputation (guards). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Behaviour")
    bool bTurnsOnDisliked = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Behaviour", meta=(EditCondition="bTurnsOnDisliked"))
    float HostileBelowReputation = -25.0f;
    /** A hit that leaves it at or below this share of its health makes it run, whatever else it would do. 0: never. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Behaviour", meta=(ClampMin="0", ClampMax="1"))
    float FleeBelowHealthFraction = 0.0f;
    /** Walks a small loop near its start while calm (needs a walking body). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Behaviour")
    bool bRoamsWhenCalm = true;

    /** How long one reaction lasts before the NPC calms down. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Timing", meta=(ClampMin="0.1", Units="s"))
    float ReactionSeconds = 7.0f;
    /** How long it only looks up (Alert) before going back to what it was doing. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Timing", meta=(ClampMin="0.1", Units="s"))
    float AlertSeconds = 2.5f;
    /** Fear and aggression lost each time a reaction ends. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Timing", meta=(ClampMin="0"))
    float FearDecay = 0.3f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Timing", meta=(ClampMin="0"))
    float AggressionDecay = 0.2f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Movement", meta=(ClampMin="0", Units="cm/s"))
    float ReactionSpeed = 210.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Movement", meta=(ClampMin="0", Units="cm/s"))
    float CalmSpeed = 140.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Movement", meta=(ClampMin="0", Units="cm"))
    float FleeDistance = 700.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Movement", meta=(ClampMin="0", Units="cm"))
    float InvestigateStopDistance = 250.0f;
};

/** How an NPC type fights. The melee values are the tuning of the original enemy combat component. */
USTRUCT(BlueprintType)
struct REFLECTIONS_API FReflectionsNpcCombatProfile
{
    GENERATED_BODY()

    /** Attacks the player as soon as it can see them inside SightRadius, without being provoked. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat")
    bool bHuntPlayerOnSight = false;
    /**
     * Hunts NPCs too, not only the player: the nearest living NPC that is not against the player and that it can
     * see inside SightRadius (the tarnished go for the townspeople). Needs bHuntPlayerOnSight.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat")
    bool bHuntsNpcs = false;
    /**
     * On reaching an NPC it hunts, it first asks the villain system to convert it (a paired sequence both NPCs are
     * held for) and only attacks normally if that is refused. The player is never converted.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat", meta=(EditCondition="bHuntsNpcs"))
    bool bConvertsNpcs = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat", meta=(EditCondition="bConvertsNpcs", ClampMin="0", Units="cm"))
    float ConversionRange = 250.0f;
    /**
     * A defender of the town: goes for the tarnished it can see inside SightRadius, and for nobody else unprovoked
     * (never the player on sight; it does not need bHuntPlayerOnSight). Only for those not against the player.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat")
    bool bFightsTarnished = false;

    /** Path-following chase, windup clip, strike, recover. Off (or no walking body): the simple poke below. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat")
    bool bUseMeleeMotor = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Melee", meta=(ClampMin="0", Units="cm"))
    float SightRadius = 1200.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Melee", meta=(ClampMin="0", Units="cm"))
    float AttackRange = 165.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Melee", meta=(ClampMin="0"))
    float AttackDamage = 12.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Melee", meta=(ClampMin="0", Units="s"))
    float AttackCooldown = 1.0f;
    /** Movement input while chasing (1 = the body's full speed). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Melee", meta=(ClampMin="0", ClampMax="1"))
    float ChaseInput = 0.7f;
    /** Stagger after being hit during a windup. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Melee", meta=(ClampMin="0", Units="s"))
    float InterruptRecovery = 0.65f;
    /** Where in the strike clip the blow lands. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Melee", meta=(ClampMin="0", ClampMax="1"))
    float ImpactFraction = 0.45f;
    /** Strike clip, played on the mesh named Body when its skeleton matches. None: a timed strike with no clip. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Melee")
    TSoftObjectPtr<UAnimSequence> AttackAnimation;
    /**
     * Strike clips for any body. Each strike plays one whose skeleton is the NPC body's, picked at random (the
     * team's melee set has every move once per body skeleton). None fits: AttackAnimation, else a timed strike.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Melee")
    TArray<TSoftObjectPtr<UAnimSequence>> AttackAnimations;
    /**
     * Strike clips made for the hidden walker's skeleton. A strike plays one at random as a montage on the walker
     * and the visible body follows it: nothing about the body's own animation changes (the safe way to show a swing).
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Melee")
    TArray<TSoftObjectPtr<UAnimSequence>> WalkerAttackAnimations;
    /** A prop held in the right hand (a sword, a wand). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Melee")
    TSoftObjectPtr<UStaticMesh> WeaponProp;

    /**
     * Fights at range with spells instead of closing in. The NPC then never walks up to its target; whoever
     * directs it (a squad, a set piece) performs the casts and reads the values below, so they stay in one place.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ranged")
    bool bRangedCaster = false;
    /** Catalog spells it may cast. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ranged", meta=(EditCondition="bRangedCaster"))
    TArray<EHeroSpell> RangedSpells;
    /** Its spells do this share of the catalog damage. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ranged", meta=(EditCondition="bRangedCaster", ClampMin="0"))
    float RangedDamageScale = 0.6f;
    /** Backs away inside the first value, closes in beyond the second. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ranged", meta=(EditCondition="bRangedCaster", Units="cm"))
    float RangedMinRange = 500.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ranged", meta=(EditCondition="bRangedCaster", Units="cm"))
    float RangedMaxRange = 1400.0f;
    /** Seconds between casts: a random value between X and Y. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ranged", meta=(EditCondition="bRangedCaster"))
    FVector2D RangedCooldown = FVector2D(3.0, 5.0);
    /** Telegraph before the spell leaves the hand. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ranged", meta=(EditCondition="bRangedCaster", ClampMin="0", Units="s"))
    float RangedWindup = 0.7f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ranged", meta=(EditCondition="bRangedCaster"))
    TSoftObjectPtr<UAnimSequence> RangedCastAnimation;

    /**
     * Casts its RangedSpells itself at a player it is fighting. Between half of RangedMinRange and RangedMaxRange,
     * with a clear line, it stops, the spell glows in front of it for RangedWindup, then flies (damage scaled by
     * RangedDamageScale, the next cast after RangedCooldown). Nearer than that the melee motor takes over; NPC
     * targets are still closed in on. The tarnished are set up this way.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ranged")
    bool bCastsAtPlayer = false;
    /** Share of those casts that are a slow wisp following the target instead of a straight bolt. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ranged", meta=(ClampMin="0", ClampMax="1"))
    float RangedHomingChance = 0.0f;
    /** Cast gesture made for the hidden walker's skeleton (a montage on the walker; the body follows). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ranged")
    TSoftObjectPtr<UAnimSequence> WalkerCastAnimation;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Simple attack", meta=(ClampMin="0", Units="cm"))
    float SimpleAttackRange = 150.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Simple attack", meta=(ClampMin="0"))
    float SimpleAttackDamage = 8.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Simple attack", meta=(ClampMin="0", Units="s"))
    float SimpleAttackCooldown = 1.5f;
};

/**
 * One kind of NPC: everything about how it reacts to spells and world events. Create one in
 * /Game/NPC/Archetypes, give it an ArchetypeId, and tag an actor NPC_Reactive + NPC_Type_<ArchetypeId>
 * (or set it on a UReflectionsNpcReactionComponent). An asset whose id matches a built-in type
 * (Civilian, Timid, Brave, Guard, Enemy, Hostile, Soldier, SoldierCaster, Infected, VillainHost) replaces that built-in.
 */
UCLASS(BlueprintType)
class REFLECTIONS_API UReflectionsNpcArchetype : public UDataAsset
{
    GENERATED_BODY()

public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="NPC")
    FName ArchetypeId = NAME_None;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="NPC")
    EReflectionsNpcDisposition Disposition = EReflectionsNpcDisposition::Civilian;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="NPC", meta=(ShowOnlyInnerProperties))
    FReflectionsNpcReactionProfile Reaction;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="NPC", meta=(ShowOnlyInnerProperties))
    FReflectionsNpcCombatProfile Combat;

    /** Used when the system adds the health component; an existing UReflectionsHealthComponent is left alone. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Body", meta=(ClampMin="1"))
    float MaxHealth = 100.0f;

    /** Full ragdoll when a hit kills it. Without a physics asset on the body it tips over instead. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Body")
    bool bRagdollOnLethalHit = true;

    /**
     * Briefly blends a physics-driven upper body into the pose on a nonlethal hit. Off by default: on the crowd
     * MetaHuman bodies the partial simulation leaves the body without a readable pose afterwards (the NPC then
     * slides in its reference pose). Every hit still leans the NPC away, shoves it and flashes.
     */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Body")
    bool bPhysicalHitReaction = false;

    /** Adds the capsule spells can hit when the actor is not a Character and has no Pawn-type collision. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Body")
    bool bAddHitProxy = true;

    /** Actor tags the system adds at enrolment (for example Friendly, Flesh). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Body")
    TArray<FName> GrantedTags;

    /** How this type talks: Civilian, Guard, Soldier or Tarnished. Audio and dialogue pick lines by it. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Voice")
    FName VoiceCharacter = TEXT("Civilian");

    /**
     * Bark groups (audio's cue is /Game/Audio/Jam/Voice/Cues/SCue_VO_<Group>_<F1..M3>): said when it starts to
     * run, when it looks up or goes to look, and when it turns to fight. None: silent.
     */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Voice")
    FName BarkOnFear = NAME_None;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Voice")
    FName BarkOnAlert = NAME_None;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Voice")
    FName BarkOnAttack = NAME_None;

    /**
     * The team MetaHuman looks UReflectionsNpcSubsystem::SpawnNpc picks from for this type. Empty: any team look.
     * Only actor Blueprints of the crowd MetaHumans belong here, never a mannequin.
     */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Body")
    TArray<TSoftClassPtr<AActor>> Looks;

    /** Which London this NPC belongs to: decides the coin it is worth. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="World")
    EReflectionsNpcHomeWorld HomeWorld = EReflectionsNpcHomeWorld::FromSpawnLocation;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="World")
    EReflectionsNpcCoinReward CoinReward = EReflectionsNpcCoinReward::None;

    /** Reputation change when the player's spell hits it, kills it, and per point of health the player heals. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Reputation")
    float ReputationOnPlayerHit = -8.0f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Reputation")
    float ReputationOnPlayerKill = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Reputation")
    float ReputationPerHealedPoint = 0.1f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Reputation")
    float MaxReputationPerHeal = 5.0f;

    /** While an NPC behaves as this archetype it is counted on game flow's infection meter. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Infection")
    bool bCountsOnInfectionMeter = false;
    /** Killing it takes it off the meter. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Infection")
    bool bCuredOnDeath = true;

    /**
     * The one decision every NPC makes about a stimulus, actor or Mass entity. Pure: touches nothing but its
     * arguments. Returns false when the stimulus is out of range, too weak or ignored (nothing is changed).
     */
    static bool EvaluateStimulus(const FReflectionsNpcReactionProfile& Profile, const FReflectionsNpcStimulus& Stimulus,
        const FVector& NpcLocation, float InstigatorReputation, float& InOutFear, float& InOutAggression,
        EReflectionsNpcReaction& OutReaction);

    /** The decision about being hit: adds fear and aggression, returns Attacking or Fleeing. */
    static EReflectionsNpcReaction EvaluateHit(const FReflectionsNpcReactionProfile& Profile, float& InOutFear,
        float& InOutAggression);

    /** Dispositions that are against the player from the start: Enemy, Infected, VillainHost. */
    static bool IsHostileDisposition(EReflectionsNpcDisposition InDisposition)
    {
        return InDisposition == EReflectionsNpcDisposition::Enemy || InDisposition == EReflectionsNpcDisposition::Infected ||
            InDisposition == EReflectionsNpcDisposition::VillainHost;
    }

    /** Where a frightened NPC runs: away from the threat, fanned out by Seed so a crowd does not run in a line. */
    static FVector FleeDestination(const FReflectionsNpcReactionProfile& Profile, const FVector& NpcLocation,
        const FVector& ThreatLocation, const FVector& FallbackDirection, uint32 Seed);

    /** The built-in types, with the numbers the game shipped with before archetypes existed. Null for other ids. */
    static UReflectionsNpcArchetype* MakeBuiltIn(UObject* Outer, FName Id);
    static const TArray<FName>& BuiltInIds();

    /** Overwrites every value with the built-in type named Id. False (and no change) for an unknown id. */
    bool ApplyBuiltIn(FName Id);

    /** Editor button: reset this asset to the built-in type named by its ArchetypeId, as a starting point. */
    UFUNCTION(BlueprintCallable, CallInEditor, Category="NPC")
    void ResetToBuiltIn();
};
