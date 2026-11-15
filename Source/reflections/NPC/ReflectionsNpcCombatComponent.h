#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ReflectionsNpcCombatComponent.generated.h"

class ACharacter;
class AController;
class UAnimInstance;
class UAnimSequence;
class UDamageType;
class UReflectionsNpcReactionComponent;
class USkeletalMeshComponent;
struct FReflectionsNpcCombatProfile;

UENUM(BlueprintType)
enum class EReflectionsNpcCombatState : uint8
{
    Idle,
    Chasing,
    Windup,
    Recovering,
    Dead
};

/**
 * The melee motor: path-following chase, windup clip, strike, recover, and being interrupted by a hit.
 *
 * It no longer decides anything. UReflectionsNpcReactionComponent creates it when the archetype asks for it,
 * copies the archetype's combat tuning in (Configure) and tells it whom to fight (SetCombatTarget); who that is
 * comes from the one NPC system (hunt on sight, a hit, a stimulus, an infection).
 */
UCLASS(ClassGroup=(NPC), BlueprintType, meta=(BlueprintSpawnableComponent))
class REFLECTIONS_API UReflectionsNpcCombatComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UReflectionsNpcCombatComponent();

    /** Mirrors the archetype (FReflectionsNpcCombatProfile::SightRadius). Sight itself is the NPC component's job. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC|Combat", meta=(ClampMin="0", Units="cm"))
    float AwarenessRadius = 1200.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC|Combat", meta=(ClampMin="0", Units="cm"))
    float AttackRange = 165.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC|Combat", meta=(ClampMin="0"))
    float AttackDamage = 12.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC|Combat", meta=(ClampMin="0"))
    float AttackCooldown = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC|Combat", meta=(ClampMin="0", ClampMax="1"))
    float ChaseInput = 0.7f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC|Combat", meta=(ClampMin="0", Units="s"))
    float InterruptRecovery = 0.65f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC|Combat", meta=(ClampMin="0", ClampMax="1"))
    float ImpactFraction = 0.45f;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="NPC|Combat")
    EReflectionsNpcCombatState CombatState = EReflectionsNpcCombatState::Idle;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="NPC|Combat")
    TObjectPtr<AActor> Target = nullptr;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="NPC|Combat")
    int32 AttacksStarted = 0;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="NPC|Combat")
    int32 SuccessfulHits = 0;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="NPC|Combat")
    int32 InterruptedAttacks = 0;

    /** Copies an archetype's melee tuning in and loads its strike clip. */
    void Configure(const FReflectionsNpcCombatProfile& Profile, UReflectionsNpcReactionComponent* InBrain);
    /** Whom to fight; null stands the motor down. */
    void SetCombatTarget(AActor* NewTarget);
    /** True when there is a body that can walk (the hidden locomotion pawn, or the owner if it is a Character). */
    bool IsUsable() const;
    bool HasLineOfSight(AActor* Candidate) const;

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* TickFunction) override;

private:
    UFUNCTION()
    void OnOwnerDamaged(AActor* DamagedActor, float Damage, const UDamageType* DamageType,
        AController* Instigator, AActor* DamageCauser);
    bool CanTarget(AActor* Candidate) const;
    bool CanReachTarget(AActor* Candidate, bool bAtImpact) const;
    ACharacter* GetDriver() const;
    void FollowTarget(ACharacter* Driver, AActor* Candidate, float DeltaTime);
    void StartAttack(ACharacter* Driver);
    void EndAttack(bool bRestoreAnimation);
    void StandDown(ACharacter* Driver);

    UPROPERTY(Transient) TObjectPtr<USkeletalMeshComponent> Body;
    UPROPERTY(Transient) TSubclassOf<UAnimInstance> SavedAnimationClass;
    UPROPERTY(Transient) TObjectPtr<UAnimSequence> AttackAnimation;
    UPROPERTY(Transient) TArray<TObjectPtr<UAnimSequence>> AttackAnimations;
    /** Strike clips on the hidden walker's skeleton, played as montages on the walker. */
    UPROPERTY(Transient) TArray<TObjectPtr<UAnimSequence>> WalkerAttackAnimations;
    /** What the body was playing by itself before the strike (a squad's march clip), to give back afterwards. */
    UPROPERTY(Transient) TObjectPtr<class UAnimationAsset> SavedSingleNodeAsset;
    bool bSavedSingleNodeLooping = false;
    UPROPERTY(Transient) TObjectPtr<UReflectionsNpcReactionComponent> Brain;
    TWeakObjectPtr<AActor> AssignedTarget;
    TArray<FVector> PathPoints;
    int32 PathIndex = 0;
    float PathTimer = 0.0f;
    float AttackTime = 0.0f;
    float AttackLength = 0.0f;
    float ImpactTime = 0.0f;
    float RecoveryTime = 0.0f;
    bool bImpactApplied = false;
};
