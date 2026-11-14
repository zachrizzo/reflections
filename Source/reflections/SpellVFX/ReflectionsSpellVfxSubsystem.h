#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Hero/ReflectionsSpellEventSubsystem.h"
#include "ReflectionsSpellVfxSubsystem.generated.h"

class UNiagaraComponent;
class UNiagaraSystem;
class UMaterialInterface;
class AReflectionsSpellProjectile;

/**
 * Visual-only spell feedback. No collision or gameplay rules are changed here.
 *
 * Three parametric Niagara systems (projectile, impact, heal) plus a ward are driven per element by
 * User.* parameters, so each element gets its own look from one shared, tunable set of assets.
 * Also owns impact camera shake and a short hit-stop when the local player lands a direct hit.
 */
UCLASS()
class REFLECTIONS_API UReflectionsSpellVfxSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()
public:
    virtual bool DoesSupportWorldType(EWorldType::Type WorldType) const override;
    virtual void OnWorldBeginPlay(UWorld& InWorld) override;
    virtual void Deinitialize() override;

private:
    void OnActorSpawned(AActor* Actor);
    void AttachProjectileVisual(TWeakObjectPtr<AReflectionsSpellProjectile> Projectile);
    void SpawnImpact(EHeroSpell Spell, const FVector& Location, const FVector& Normal, float Scale, bool bMuzzle);
    void ShakeNear(const FVector& Location, float Strength);
    void HitStop();

    UFUNCTION() void OnProjectileDestroyed(AActor* Projectile);
    UFUNCTION() void OnSpellHit(const FReflectionsSpellHitData& Hit);
    UFUNCTION() void OnSupportVisual(EHeroSpell Spell, FVector Location, AActor* Caster, float Intensity);
    UFUNCTION() void OnDirectionalVisual(EHeroSpell Spell, FVector Location, FVector Direction, AActor* Caster, float Intensity);
    UFUNCTION() void OnImpactVisual(EHeroSpell Spell, FVector Location, FVector Normal, AActor* Caster, float Scale);
    UFUNCTION() void OnReleaseVisual(EHeroSpell Spell, FVector Location, FVector Direction, AActor* Caster, float Scale);

    UPROPERTY(Transient) TObjectPtr<UNiagaraSystem> ProjectileSystem;
    UPROPERTY(Transient) TObjectPtr<UNiagaraSystem> ImpactSystem;
    UPROPERTY(Transient) TObjectPtr<UNiagaraSystem> HealSystem;
    UPROPERTY(Transient) TObjectPtr<UNiagaraSystem> WardSystem;
    UPROPERTY(Transient) TObjectPtr<UNiagaraSystem> BloodImpact;
    UPROPERTY(Transient) TObjectPtr<UMaterialInterface> BloodSpatter;

    TMap<TWeakObjectPtr<AActor>, TWeakObjectPtr<UNiagaraComponent>> ProjectileTrails;
    FDelegateHandle SpawnHandle;
    FTimerHandle HitStopTimer;
    double LastHitStop = -1.0;
};
