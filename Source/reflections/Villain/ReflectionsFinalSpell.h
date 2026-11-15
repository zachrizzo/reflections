#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "GameFramework/Actor.h"
#include "ReflectionsFinalSpell.generated.h"

class UEnhancedInputComponent;
class UInputAction;
class UInputMappingContext;
class UNiagaraComponent;
class UPointLightComponent;
class UProjectileMovementComponent;
class UReflectionsSampleSpellDriver;
class USphereComponent;

/**
 * The book's spell. Added to the hero at runtime when the book is complete. F (keyboard) or X / Square
 * (gamepad) casts it through the spell driver's CastExternal (normal windup, animation, mana and cooldown);
 * without a driver it fires straight from the camera. The bolt homes on his true form.
 */
UCLASS(ClassGroup = (Villain), meta = (BlueprintSpawnableComponent))
class REFLECTIONS_API UReflectionsFinalSpellComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UReflectionsFinalSpellComponent();

    /** Cast now (same as the button). True if a cast started. */
    UFUNCTION(BlueprintCallable, Category = "Villain")
    bool CastFinalSpell();

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

private:
    void BindInput();
    void OnCastPressed();
    void Release(const FVector& Origin, const FVector& Target, AActor* AimTarget);

    UPROPERTY(Transient) TObjectPtr<UInputMappingContext> Context;
    UPROPERTY(Transient) TObjectPtr<UInputAction> Action;
    UPROPERTY(Transient) TObjectPtr<UEnhancedInputComponent> Input;
    TWeakObjectPtr<UReflectionsSampleSpellDriver> Driver;
    double CooldownUntil = 0.0;
    float HudClock = 0.0f;
};

/** The Final Spell bolt: gold-white, fast, homing on his true form. */
UCLASS()
class REFLECTIONS_API AReflectionsFinalSpellProjectile : public AActor
{
    GENERATED_BODY()

public:
    AReflectionsFinalSpellProjectile();
    void Fire(const FVector& Direction, AActor* HomingTarget);

protected:
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;

private:
    UFUNCTION() void HandleHit(UPrimitiveComponent* HitComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp, FVector NormalImpulse, const FHitResult& Hit);
    void Explode(AActor* Victim, const FVector& Point);

    UPROPERTY(VisibleAnywhere) TObjectPtr<USphereComponent> Collision;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UProjectileMovementComponent> Movement;
    UPROPERTY(Transient) TObjectPtr<UNiagaraComponent> Visual;
    UPROPERTY(Transient) TObjectPtr<UPointLightComponent> Light;
    TWeakObjectPtr<AActor> Homing;
    bool bDone = false;
};
