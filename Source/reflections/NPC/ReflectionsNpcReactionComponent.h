#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Hero/ReflectionsSpellEventSubsystem.h"
#include "NPC/ReflectionsNpcArchetype.h"
#include "ReflectionsNpcReactionComponent.generated.h"

class ACharacter;
class UReflectionsNpcCombatComponent;
class UReflectionsNpcSubsystem;
class USkeletalMeshComponent;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FReflectionsNpcReactionChanged, EReflectionsNpcReaction, Reaction, AActor*, Cause, FVector, Location);

/**
 * The one NPC component. It carries the NPC's archetype and its live state (reaction, fear, aggression,
 * infection) and does the body work: moving, hit physics, the lethal ragdoll, and the melee motor.
 *
 * It listens to nothing itself: UReflectionsNpcSubsystem hands it stimuli and hits. Add it through
 * UReflectionsNpcSubsystem::EnrollActor (or the NPC_Reactive tag), or place it on a Blueprint and set Archetype.
 */
UCLASS(ClassGroup=(NPC), BlueprintType, meta=(BlueprintSpawnableComponent))
class REFLECTIONS_API UReflectionsNpcReactionComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UReflectionsNpcReactionComponent();

    /** What kind of NPC this is. None: taken from the owner's tags when play begins. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="NPC")
    TObjectPtr<UReflectionsNpcArchetype> Archetype;

    /** Per-actor: ragdoll on a lethal hit even when the archetype says no (tag NPC_Ragdoll). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC|Physics")
    bool bEnableRagdollOnDeath = false;
    /** Per-actor: allow the brief physics-driven upper body on nonlethal hits (the archetype must allow it too). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC|Physics")
    bool bEnablePhysicalHitReaction = true;
    /** Per-actor: walk with a hidden sample-locomotion pawn (tag NPC_SampleLocomotion). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC")
    bool bUseSampleLocomotion = false;

    /** Disposition of the archetype it is behaving as right now (changes while infected). */
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="NPC")
    EReflectionsNpcDisposition Disposition = EReflectionsNpcDisposition::Civilian;
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="NPC")
    EReflectionsNpcReaction Reaction = EReflectionsNpcReaction::Calm;
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="NPC")
    float Fear = 0.0f;
    /** Aggression, 0..1. */
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="NPC")
    float Hostility = 0.0f;
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="NPC")
    EReflectionsNpcInfection Infection = EReflectionsNpcInfection::None;
    /** True while game flow's infection meter counts this NPC (kept by the subsystem). */
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="NPC")
    bool bOnInfectionMeter = false;

    /** Voice, set once when the NPC joins the system (UReflectionsNpcSubsystem::GetVoiceProfile reads these). */
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="NPC|Voice")
    EReflectionsNpcSex VoiceSex = EReflectionsNpcSex::Unknown;
    /** 0..2 within its sex. */
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="NPC|Voice")
    int32 VoiceSlotIndex = INDEX_NONE;
    /** F1..F3 or M1..M3: sex and slot in one name (the suffix of audio's cues; also what dialogue reads). */
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="NPC|Voice")
    FName VoiceSlot = NAME_None;
    /** Its voice in audio's roster table (V001...); None while the project has no roster, then VoiceSlot is all. */
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="NPC|Voice")
    FName VoiceId = NAME_None;
    /** The roster's id of the designed voice (for live and cached replies); empty without a roster voice. */
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="NPC|Voice")
    FString GeminiVoice;
    float NextBarkTime = 0.0f;
    /** When the player's last assault on this NPC was reported as a crime (the NPC subsystem keeps it). */
    float LastAssaultTime = -100.0f;
    /** Its own roster voice, kept while SetVoiceOverride has given it another. */
    FName OwnVoiceId = NAME_None;
    FString OwnGeminiVoice;
    bool bVoiceOverridden = false;

    UPROPERTY(BlueprintAssignable, Category="NPC")
    FReflectionsNpcReactionChanged OnReactionChanged;

    UFUNCTION(BlueprintPure, Category="NPC")
    AActor* GetFocusActor() const { return Focus.Get(); }
    UFUNCTION(BlueprintPure, Category="NPC")
    ACharacter* GetLocomotionDriver() const;
    /** The archetype it behaves as right now: Infected or VillainHost while taken, else Archetype. */
    UFUNCTION(BlueprintPure, Category="NPC")
    UReflectionsNpcArchetype* GetActiveArchetype() const;
    UFUNCTION(BlueprintPure, Category="NPC")
    EReflectionsNpcInfection GetInfection() const { return Infection; }
    UFUNCTION(BlueprintPure, Category="NPC")
    bool IsIncapacitated() const { return Reaction == EReflectionsNpcReaction::Incapacitated; }
    /** The character that walks for this NPC: the hidden locomotion pawn, or the owner if it is a Character. */
    ACharacter* GetMovementCharacter() const;
    USkeletalMeshComponent* GetBodyMesh() const;
    const FVector& GetHomeLocation() const { return HomeLocation; }
    /** Where to aim a spell at this NPC: its chest, or the middle of its hit capsule or bounds. */
    UFUNCTION(BlueprintPure, Category="NPC")
    FVector GetAimPoint() const;
    /** True once, right after the hit that killed it has been processed. */
    bool ConsumeFreshDeath();

    // ---- Orders from other gameplay systems (squads, set pieces) ---------------------------------------

    /**
     * Fight Target: any living actor, not only the player. It stays on that target until told otherwise, the
     * target dies, or it is driven off. Null calls it off.
     */
    UFUNCTION(BlueprintCallable, Category="NPC")
    void Engage(AActor* Target);
    UFUNCTION(BlueprintPure, Category="NPC")
    AActor* GetEngagedTarget() const { return EngagedTarget.Get(); }

    /**
     * Something else is moving this NPC's body (a squad formation, a cutscene): it stops roaming, fleeing,
     * approaching and chasing by itself. It still feels, takes hits, dies and reports its reaction.
     */
    UFUNCTION(BlueprintCallable, Category="NPC")
    void SetExternallySteered(bool bSteered);
    UFUNCTION(BlueprintPure, Category="NPC")
    bool IsExternallySteered() const { return bExternallySteered; }

    /**
     * A set piece owns this NPC for a while (the villain's conversion tackle): it does not move, fight, flee or
     * change reaction, whatever it hears or is hit by. Damage still applies and death ends the hold, as does the
     * timeout. Seconds is the longest the hold may last.
     */
    /**
     * Casts this NPC as a fixed roster voice (V001...) for as long as a scene needs it: VoiceId and GeminiVoice
     * change, so barks, remarks and replies come out in that voice. None, or ClearVoiceOverride, gives it its own
     * voice back. The sex and the F1..M3 slot stay the NPC's own.
     */
    UFUNCTION(BlueprintCallable, Category="NPC|Voice")
    void SetVoiceOverride(FName InVoiceId);
    UFUNCTION(BlueprintCallable, Category="NPC|Voice")
    void ClearVoiceOverride();
    UFUNCTION(BlueprintPure, Category="NPC|Voice")
    bool HasVoiceOverride() const { return bVoiceOverridden; }

    /**
     * Stops this NPC making passing remarks to the player while something else has it talking (a street
     * conversation, a dialogue, a cutscene). Barks from fear or anger are not affected.
     */
    UFUNCTION(BlueprintCallable, Category="NPC|Voice")
    void SetRemarksMuted(bool bMuted) { bRemarksMuted = bMuted; }
    UFUNCTION(BlueprintPure, Category="NPC|Voice")
    bool AreRemarksMuted() const { return bRemarksMuted; }

    UFUNCTION(BlueprintCallable, Category="NPC")
    void BeginScriptedHold(float Seconds);
    UFUNCTION(BlueprintCallable, Category="NPC")
    void EndScriptedHold();
    UFUNCTION(BlueprintPure, Category="NPC")
    bool IsScripted() const { return ScriptedHoldRemaining > 0.0f; }

    /** The player's record was wiped: one that was after them for it (not an enemy) stands down. */
    void ForgivePlayer();

    /** Turns it toward a point at its turning pace: the walker turns, the body follows. */
    void FacePoint(const FVector& Point, float DeltaTime);

    /**
     * Plays a clip made for the hidden walker's skeleton as a montage on the walker (slot DefaultSlot); the visible
     * body follows it. False when this NPC has no walker, or the clip is for another skeleton. Nothing about the
     * visible body's animation is changed.
     */
    bool PlayOnWalker(class UAnimSequenceBase* Clip, float PlayRate = 1.0f, int32 Loops = 1);

    // ---- Driven by UReflectionsNpcSubsystem ------------------------------------------------------------

    void SetArchetype(UReflectionsNpcArchetype* NewArchetype);
    void ReceiveStimulus(const FReflectionsNpcStimulus& Stimulus, float InstigatorReputation);
    void ReceiveSpellHit(const FReflectionsSpellHitData& Hit);
    /** Returns false if the state is unchanged. TakenArchetype is used for Infected and VillainHost. */
    bool ApplyInfection(EReflectionsNpcInfection NewState, UReflectionsNpcArchetype* TakenArchetype);

    /** Component tag on the capsule spells hit (UReflectionsNpcSubsystem adds it to actors with no collision). */
    static const FName HitProxyTag;

    /** Sight test shared by the NPC and its melee motor: eye height to the target, ignoring both and Extra. */
    static bool HasLineOfSight(const AActor* From, const AActor* To, const AActor* ExtraIgnored);
    /** Something this NPC may attack: a living, player-controlled pawn. */
    static bool IsAttackable(const AActor* Candidate);

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* TickFunction) override;
private:
    UFUNCTION() void OnOwnerDied(AActor* Source);
    UFUNCTION() void OnHealthChanged(float Health, float MaxHealth, AActor* Source);
    void SetReaction(EReflectionsNpcReaction Next, AActor* Cause, FVector EventLocation);
    void RefreshActiveArchetype();
    void ConfigureMotor();
    void UpdateHunt();
    /** The NPC this hunter should go for now, or null: nearest living, visible NPC that is not against the player. */
    AActor* FindNpcPrey(const AActor* Keep) const;
    /** An NPC this hunter may attack or convert. */
    bool IsPrey(const AActor* Candidate) const;
    float ScriptedHoldRemaining = 0.0f;
    float NextPreyScanTime = 0.0f;
    float ConversionRetryTime = 0.0f;
    void TickRemark(float DeltaTime);
    /** Casting at a player from range (archetype Combat.bCastsAtPlayer). True while it stands its ground to cast. */
    bool TickSpellcasting(float DeltaTime);
    void ReleaseSpell(AActor* Target);
    void EndCastTelegraph();
    void FaceTowards(const AActor* Target, float DeltaTime);
    void RefreshWeaponProp();
    /** The shield on the left forearm, and the parts of the look this archetype goes without. */
    void RefreshShieldProp();
    void HideLookParts();
    /** spell-combat's tarnish caster on this actor, added on first use; null when that code is not in the build. */
    UActorComponent* FindOrAddTarnishCaster();
    void CancelTarnishCast();
    UPROPERTY(Transient) TObjectPtr<UActorComponent> TarnishCaster;
    bool bCastByTarnishCaster = false;

    /** Heat: the armed and lawful turn on a player who has just hurt someone. */
    void TickHeat();
    float HeatCheckIn = 0.0f;
    /**
     * What a spell's hit does to a living NPC beyond the damage. The spell says which (Hit.Reaction): thrown by a
     * blast, shoved, knocked down, lifted, pulled, shocked, frozen, set alight. True when it was thrown, so that
     * nothing else pushes it as well.
     */
    bool ReactToSpell(const FReflectionsSpellHitData& Hit);
    /** Throws it: the walker's capsule is launched and staggers. The visible body is never simulated for this. */
    bool Throw(const FVector& Velocity, bool bFirst);
    void StartShock(const FReflectionsSpellHitData& Hit, bool bFirst);
    void EndShock(bool bFell);
    void StartBurning(float Seconds, bool bFirst);
    void EndBurning();
    void StartFreeze(float Seconds);
    void EndFreeze();
    /** A body dropped by lightning keeps twitching for a moment: small kicks to the ragdoll that is already there. */
    void TwitchRagdoll();
    float CorpseShockRemaining = 0.0f;
    bool bShocked = false;
    float ShockRemaining = 0.0f;
    float ShockDamageLeft = 0.0f;
    float ShockTickIn = 0.0f;
    float ShockFlashIn = 0.0f;
    UPROPERTY(Transient) FReflectionsSpellHitData ShockHit;
    float BurningRemaining = 0.0f;
    float NextBurnBarkIn = 0.0f;
    float FrozenRemaining = 0.0f;
    UPROPERTY(Transient) TObjectPtr<class UAudioComponent> ShockLoop;
    UPROPERTY(Transient) TObjectPtr<class UAudioComponent> BurnLoop;
    float CastWindupRemaining = 0.0f;
    float CastWindupLength = 0.0f;
    float CastCooldownRemaining = 0.0f;
    EHeroSpell PendingSpell = EHeroSpell::ArcaneBolt;
    bool bPendingHoming = false;
    bool bLastCastWasWisp = false;

    /** A body that has only just been spawned stays unseen until its walker has a pose that is not its reference pose. */
    void TickReveal(float DeltaTime);
    bool bHiddenUntilPosed = false;

    /**
     * A hit that lands with physics: the hidden walker's upper body simulates for a moment, blended over its
     * animation and fading out. The visible body is never simulated; it copies the walker's pose after physics.
     */
    bool StartWalkerJolt(const FVector& Direction, float Strength);
    void EndWalkerJolt();
    bool bWalkerJolting = false;
    float WalkerJoltRemaining = 0.0f;
    float WalkerJoltDuration = 0.0f;
    float WalkerJoltPeak = 0.0f;
    TEnumAsByte<ETickingGroup> BodyTickGroupBefore = TG_PrePhysics;
    TEnumAsByte<ECollisionEnabled::Type> WalkerCollisionBefore = ECollisionEnabled::NoCollision;

    /**
     * Knocked off its feet: the hidden walker falls as a ragdoll (the visible body is attached to it and copies
     * it), lies a moment, then gets up with a clip while the physics fades out.
     */
    enum class EWalkerDown : uint8 { None, Down, Rising };
    bool StartWalkerKnockdown(const FVector& Velocity);
    void TickWalkerKnockdown(float DeltaTime);
    void BeginWalkerGetUp();
    void EndWalkerKnockdown(bool bLeaveWhereItLies = false);
    /** Puts the walker's mesh back on its capsule. Only once its bodies no longer simulate: the engine refuses otherwise. */
    void ReattachWalkerMesh();
    EWalkerDown WalkerDown = EWalkerDown::None;
    float WalkerDownTime = 0.0f;
    float WalkerStillTime = 0.0f;
    float WalkerRiseRemaining = 0.0f;
    float WalkerRiseBlend = 0.0f;
    FTransform WalkerMeshRelative;
    TEnumAsByte<ECollisionEnabled::Type> WalkerCapsuleCollisionBefore = ECollisionEnabled::QueryAndPhysics;

    /** Armed NPCs hold sword and shield at the ready: a looping hold on the walker that yields to every other montage. */
    void TickStance(float DeltaTime);
    UPROPERTY(Transient) TObjectPtr<class UAnimMontage> StanceMontage;
    float StanceStillFor = 0.0f;
    float StanceCheckIn = 0.0f;
    bool bStanceIsMarch = false;
    float RevealTimeout = 0.0f;
    float RevealElapsed = 0.0f;
    int32 RevealGoodFrames = 0;
    UPROPERTY(Transient) TObjectPtr<class UPointLightComponent> CastLight;
    UPROPERTY(Transient) TObjectPtr<class UNiagaraComponent> CastGlow;
    UPROPERTY(Transient) TObjectPtr<class UStaticMeshComponent> WeaponProp;
    UPROPERTY(Transient) TObjectPtr<class UStaticMeshComponent> ShieldProp;
    bool bRemarksMuted = false;
    float RemarkCheckIn = 0.0f;
    float NextRemarkTime = 0.0f;
    /** Keeps an ordered fight going. Returns true while there is an ordered target. */
    bool UpdateEngagement();
    /** Whether this NPC may turn on Candidate: the player, or the target it was ordered to fight. */
    bool MayAttack(const AActor* Candidate) const;
    void TryMove(const FVector& Target, float DeltaTime);
    void InitializeLocomotion();
    void TickAmbientMovement(float DeltaTime);
    bool StartPhysicalHit(const FReflectionsSpellHitData& Hit);
    void EndPhysicalHit();
    bool StartRagdoll();
    void StartHitFlash(const FReflectionsSpellHitData& Hit);
    /** False (and one log line per body) when the body's bone transforms cannot be read safely right now. */
    bool BodyPoseReady(const USkeletalMeshComponent* Body);
    /**
     * Runs before the body animates each frame: a living body whose bone buffers have lost their contents is
     * re-registered so the engine never evaluates animation into an empty array (that asserts and takes the
     * editor or the game down).
     */
    void RepairBodyPose();
    TWeakObjectPtr<USkeletalMeshComponent> WatchedBody;
    float NextPoseRepairTime = 0.0f;
    int32 PoseRepairs = 0;
    void KickRagdoll(const FReflectionsSpellHitData& Hit);

    UPROPERTY(Transient) TObjectPtr<UReflectionsNpcArchetype> ActiveArchetype;
    UPROPERTY(Transient) TObjectPtr<UReflectionsNpcArchetype> TakenArchetype;
    UPROPERTY(Transient) TObjectPtr<UReflectionsNpcCombatComponent> Motor;
    TWeakObjectPtr<UReflectionsNpcSubsystem> Subsystem;
    TWeakObjectPtr<AActor> Focus;
    TWeakObjectPtr<AActor> EngagedTarget;
    bool bExternallySteered = false;
    TWeakObjectPtr<ACharacter> LocomotionDriver;
    FVector HomeLocation = FVector::ZeroVector;
    FVector RoamOrigin = FVector::ZeroVector;
    FVector RoamTarget = FVector::ZeroVector;
    float RoamLegTime = 0.0f;
    float RoamPause = 0.0f;
    int32 RoamLeg = 0;
    bool bTriedLocomotion = false;
    FVector ThreatLocation = FVector::ZeroVector;
    FVector SafeDestination = FVector::ZeroVector;
    FVector KnockbackVelocity = FVector::ZeroVector;
    float ReactionTimeRemaining = 0.0f;
    /** While above zero the NPC keeps after whoever provoked it, even out of sight. */
    float ProvokedRemaining = 0.0f;
    float AttackCooldown = 0.0f;
    float LastKnownHealth = 0.0f;
    bool bHunting = false;
    bool bFreshDeath = false;
    bool bHadFriendlyTag = false;
    bool bLoggedEmptyPose = false;
    /** Actor tags the Infected / VillainHost archetype granted, to take back when it is cured. */
    TArray<FName> TakenTagsAdded;
    TWeakObjectPtr<USkeletalMeshComponent> HitMesh;
    FName HitPhysicsRoot = NAME_None;
    float HitPhysicsRemaining = 0.0f;
    float HitPhysicsDuration = 0.0f;
    float HitPhysicsPeakWeight = 0.0f;
    TEnumAsByte<ECollisionEnabled::Type> OriginalMeshCollision = ECollisionEnabled::NoCollision;
    UPROPERTY(Transient) TObjectPtr<class UPointLightComponent> HitFlash;
    float HitFlashRemaining = 0.0f;
    float HitFlashPeak = 0.0f;
    /** The lean away from a hit: applied to the walker's rotation under its locomotion pawn, then taken back. */
    void StartFlinch(const FReflectionsSpellHitData& Hit);
    void EndFlinch();
    float FlinchRemaining = 0.0f;
    float FlinchDuration = 0.0f;
    float FlinchAngle = 0.0f;
    FVector FlinchAxis = FVector::RightVector;
    FQuat FlinchRestRotation = FQuat::Identity;
    bool bFlinching = false;
    /** Tip-over for bodies that cannot ragdoll. */
    float ToppleRemaining = 0.0f;
    FRotator ToppleStart = FRotator::ZeroRotator;
};
