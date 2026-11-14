#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Hero/ReflectionsSpellEventSubsystem.h"
#include "ReflectionsNpcReactionComponent.generated.h"

class ACharacter;

UENUM(BlueprintType)
enum class EReflectionsNpcDisposition : uint8 { Timid, Civilian, Brave, Guard, Hostile };
UENUM(BlueprintType)
enum class EReflectionsNpcReaction : uint8 { Calm, Alert, Fleeing, Investigating, Defending, Attacking, Incapacitated };
DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FReflectionsNpcReactionChanged, EReflectionsNpcReaction, Reaction, AActor*, Cause, FVector, Location);

/** A lightweight, opt-in NPC brain that listens to nearby magic and direct hits. */
UCLASS(ClassGroup=(NPC), BlueprintType, meta=(BlueprintSpawnableComponent))
class REFLECTIONS_API UReflectionsNpcReactionComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UReflectionsNpcReactionComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC")
    EReflectionsNpcDisposition Disposition = EReflectionsNpcDisposition::Civilian;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC", meta=(ClampMin="1", Units="cm"))
    float AwarenessRadius = 1400.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC", meta=(ClampMin="0", Units="cm/s"))
    float ReactionSpeed = 210.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC")
    bool bCanAttack = true;
    /** Only enable after giving the NPC body a suitable physics asset and collision. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC|Physics")
    bool bEnableRagdollOnDeath = false;
    /** Briefly blend a physics-driven body response into the standing pose on nonlethal hits. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="NPC|Physics")
    bool bEnablePhysicalHitReaction = true;
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="NPC")
    EReflectionsNpcReaction Reaction = EReflectionsNpcReaction::Calm;
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="NPC")
    float Fear = 0.0f;
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="NPC")
    float Hostility = 0.0f;
    UPROPERTY(BlueprintAssignable, Category="NPC")
    FReflectionsNpcReactionChanged OnReactionChanged;
    UFUNCTION(BlueprintPure, Category="NPC")
    AActor* GetFocusActor() const { return Focus.Get(); }
    UFUNCTION(BlueprintPure, Category="NPC")
    ACharacter* GetLocomotionDriver() const;
protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* TickFunction) override;
private:
    UFUNCTION() void OnNearbySpell(EHeroSpell Spell, FVector Location, AActor* Caster, float Intensity);
    UFUNCTION() void OnSpellHit(const FReflectionsSpellHitData& Hit);
    UFUNCTION() void OnOwnerDied(AActor* Source);
    UFUNCTION() void OnHealthChanged(float Health, float MaxHealth, AActor* Source);
    void SetReaction(EReflectionsNpcReaction Next, AActor* Cause, FVector EventLocation);
    void TryMove(const FVector& Target, float DeltaTime);
    void InitializeLocomotion();
    void TickAmbientMovement(float DeltaTime);
    bool StartPhysicalHit(const FReflectionsSpellHitData& Hit);
    void EndPhysicalHit();
    TWeakObjectPtr<AActor> Focus;
    TWeakObjectPtr<ACharacter> LocomotionDriver;
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
    float AttackCooldown = 0.0f;
    float LastKnownHealth = 0.0f;
    TWeakObjectPtr<class USkeletalMeshComponent> HitMesh;
    FName HitPhysicsRoot = NAME_None;
    float HitPhysicsRemaining = 0.0f;
    float HitPhysicsDuration = 0.0f;
    float HitPhysicsPeakWeight = 0.0f;
    TEnumAsByte<ECollisionEnabled::Type> OriginalMeshCollision = ECollisionEnabled::NoCollision;
};
