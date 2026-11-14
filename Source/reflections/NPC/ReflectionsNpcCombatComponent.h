#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ReflectionsNpcCombatComponent.generated.h"

class ACharacter;
class AController;
class UAnimInstance;
class UDamageType;
class USkeletalMeshComponent;

UENUM(BlueprintType)
enum class EReflectionsNpcCombatState : uint8
{
    Idle,
    Chasing,
    Windup,
    Recovering,
    Dead
};

/** Combat for explicitly tagged enemies; ordinary crowd reactions stay separate. */
UCLASS(ClassGroup=(NPC), BlueprintType, meta=(BlueprintSpawnableComponent))
class REFLECTIONS_API UReflectionsNpcCombatComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UReflectionsNpcCombatComponent();

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC|Combat", meta=(ClampMin="0", Units="cm"))
    float AwarenessRadius = 1200.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC|Combat", meta=(ClampMin="0", Units="cm"))
    float AttackRange = 165.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC|Combat", meta=(ClampMin="0"))
    float AttackDamage = 12.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC|Combat", meta=(ClampMin="0"))
    float AttackCooldown = 1.0f;

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

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* TickFunction) override;

private:
    UFUNCTION()
    void OnOwnerDamaged(AActor* DamagedActor, float Damage, const UDamageType* DamageType,
        AController* Instigator, AActor* DamageCauser);
    bool CanTarget(AActor* Candidate) const;
    bool HasLineOfSight(AActor* Candidate) const;
    void FollowTarget(ACharacter* Driver, AActor* Candidate, float DeltaTime);
    void StartAttack(ACharacter* Driver);
    void EndAttack(bool bRestoreAnimation);

    UPROPERTY(Transient) TObjectPtr<USkeletalMeshComponent> Body;
    UPROPERTY(Transient) TSubclassOf<UAnimInstance> SavedAnimationClass;
    UPROPERTY(Transient) TObjectPtr<class UAnimSequence> AttackAnimation;
    TArray<FVector> PathPoints;
    int32 PathIndex = 0;
    float PathTimer = 0.0f;
    float AttackTime = 0.0f;
    float ImpactTime = 0.0f;
    float RecoveryTime = 0.0f;
    bool bImpactApplied = false;
};
