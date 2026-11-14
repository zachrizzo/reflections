#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "GameFramework/Actor.h"
#include "Hero/ReflectionsHeroCharacter.h"
#include "ReflectionsSpellCombat.generated.h"

class UMaterialInterface;
class UProjectileMovementComponent;
class USphereComponent;
class UStaticMesh;
class UStaticMeshComponent;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FReflectionsHealthChanged, float, Health, float, MaxHealth, AActor*, Source);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FReflectionsDeath, AActor*, Source);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FReflectionsSpellImpact, EHeroSpell, Spell, AActor*, Target, FVector, Location);

/** A small reusable health pool for actors that do not already implement combat health. */
UCLASS(ClassGroup=(Combat), BlueprintType, meta=(BlueprintSpawnableComponent))
class REFLECTIONS_API UReflectionsHealthComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UReflectionsHealthComponent();

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Health", meta=(ClampMin="1"))
    float MaxHealth = 100.0f;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Health")
    float Health = 0.0f;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Health")
    float Shield = 0.0f;

    UPROPERTY(BlueprintAssignable, Category="Health")
    FReflectionsHealthChanged OnHealthChanged;

    UPROPERTY(BlueprintAssignable, Category="Health")
    FReflectionsDeath OnDeath;

    UFUNCTION(BlueprintCallable, Category="Health")
    float Heal(float Amount, AActor* Healer);

    UFUNCTION(BlueprintCallable, Category="Health")
    void GrantShield(float Amount);

    /** Restore this actor for a new life and clear any temporary shield. */
    UFUNCTION(BlueprintCallable, Category="Health")
    void ResetHealth();

protected:
    virtual void BeginPlay() override;

private:
    void ExpireShield();
    FTimerHandle ShieldTimer;
    UFUNCTION()
    void ReceiveDamage(AActor* DamagedActor, float Damage, const UDamageType* DamageType,
        AController* Instigator, AActor* DamageCauser);
};

/** A single-hit, collision-tested spell projectile. */
UCLASS()
class REFLECTIONS_API AReflectionsSpellProjectile : public AActor
{
    GENERATED_BODY()

public:
    AReflectionsSpellProjectile();
    UFUNCTION(BlueprintPure, Category="Spells")
    EHeroSpell GetSpell() const { return Spell; }
    void Initialize(EHeroSpell InSpell, float InDamage, float InSpeed, float InRange,
        UStaticMesh* InMesh, UMaterialInterface* InMaterial);
    void InitializeCatalog(EHeroSpell InSpell, UStaticMesh* InMesh, UMaterialInterface* InMaterial);
    /** Gently curves toward an aim-assist target; strong enough to forgive, not to guarantee. */
    void SetHomingTarget(AActor* Target);
    /** Hides the static-mesh stand-in once a particle visual is attached. */
    void HideFallbackVisual();

protected:
    virtual void BeginPlay() override;

private:
    UFUNCTION()
    void OnProjectileHit(UPrimitiveComponent* HitComponent, AActor* OtherActor,
        UPrimitiveComponent* OtherComponent, FVector NormalImpulse, const FHitResult& Hit);

    UPROPERTY(VisibleAnywhere)
    TObjectPtr<USphereComponent> Collision;

    UPROPERTY(VisibleAnywhere)
    TObjectPtr<UStaticMeshComponent> Visual;

    UPROPERTY(VisibleAnywhere)
    TObjectPtr<UProjectileMovementComponent> Movement;

    EHeroSpell Spell = EHeroSpell::Fire;
    float Damage = 1.0f;
    float BlastRadius = 0.0f;
    float HitImpulse = 0.0f;
    bool bImpacted = false;
};

/** Spell effects that can be called by any player character at the animation release frame. */
UCLASS(ClassGroup=(Combat), BlueprintType, meta=(BlueprintSpawnableComponent))
class REFLECTIONS_API UReflectionsSpellCombatComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UReflectionsSpellCombatComponent();

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Spells", meta=(ClampMin="0"))
    float HealingAmount = 35.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Spells", meta=(ClampMin="0"))
    float FireDamage = 1.5f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Spells", meta=(ClampMin="0"))
    float WaterDamage = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Spells", meta=(ClampMin="1", Units="cm/s"))
    float ProjectileSpeed = 1100.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Spells", meta=(ClampMin="1", Units="cm"))
    float ProjectileRange = 1800.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Spells|Visual")
    TObjectPtr<UStaticMesh> FireMesh;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Spells|Visual")
    TObjectPtr<UMaterialInterface> FireMaterial;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Spells|Visual")
    TObjectPtr<UStaticMesh> WaterMesh;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Spells|Visual")
    TObjectPtr<UMaterialInterface> WaterMaterial;

    UPROPERTY(BlueprintAssignable, Category="Spells")
    FReflectionsSpellImpact OnSpellImpact;

    /** Called at a spell's release frame. The transform supplies its muzzle and facing. */
    UFUNCTION(BlueprintCallable, Category="Spells")
    void ReleaseSpell(EHeroSpell Spell, FTransform Origin);

    /**
     * Aimed release: projectiles fly from Origin toward Target (curving toward AimTarget if set),
     * radial area spells land centred on Target, cones fire from the caster toward Target.
     */
    UFUNCTION(BlueprintCallable, Category="Spells")
    void ReleaseSpellAt(EHeroSpell Spell, FTransform Origin, FVector Target, AActor* AimTarget);

    void NotifyImpact(EHeroSpell Spell, AActor* Target, const FVector& Location);

protected:
    virtual void BeginPlay() override;
};

/** Reusable practice target with health and a visible collision shape. */
UCLASS(Blueprintable)
class REFLECTIONS_API AReflectionsSpellTarget : public AActor
{
    GENERATED_BODY()

public:
    AReflectionsSpellTarget();

private:
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Target", meta=(AllowPrivateAccess="true"))
    TObjectPtr<UStaticMeshComponent> TargetMesh;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Target", meta=(AllowPrivateAccess="true"))
    TObjectPtr<UReflectionsHealthComponent> Health;
};
