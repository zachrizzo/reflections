#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Hero/ReflectionsSpellEventSubsystem.h"
#include "ReflectionsSpellVfxSubsystem.generated.h"

class UNiagaraComponent;
class UNiagaraSystem;
class UMaterialInterface;
class UDecalComponent;
class USceneComponent;
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

    /** Tarnish (enemy) magic hit, or with bMuzzle the small flash at the caster's hand: black-violet smoke, sickly
     *  silver sparks, a violet shock ring and a dark stain on the ground. Scale is about 1 for a bolt, 4 for a burst. */
    void SpawnTarnishImpact(const FVector& Location, const FVector& Normal, AActor* Caster, float Scale, bool bMuzzle);
    /** The wind-up gather at a tarnished caster's hand. The caller ramps User.Scale and destroys it. */
    UNiagaraComponent* SpawnTarnishTelegraph(USceneComponent* Parent, FName Socket);
    /** Ground warning circle for a tarnish burst. The caller ramps the "Strength" parameter (0-1) and destroys it. */
    UDecalComponent* SpawnTarnishWarning(const FVector& Center, float Radius);

private:
    void OnActorSpawned(AActor* Actor);
    void AttachProjectileVisual(TWeakObjectPtr<AReflectionsSpellProjectile> Projectile);
    void SpawnImpact(EHeroSpell Spell, const FVector& Location, const FVector& Normal, float Scale, bool bMuzzle);
    void AttachTarnishVisual(AReflectionsSpellProjectile* Projectile);
    /** Traces for the surface under Location and lays a M_Spell_GroundMark decal of the given Kind on it. Fading marks
     *  join the capped GroundMarks list; a non-fading one (a warning) belongs to the caller. */
    UDecalComponent* PlaceGroundMark(float Kind, float Strength, const FLinearColor& Color, const FVector& Location,
        const FVector& Normal, float Radius, bool bFade);
    /** Spawns every spell system once, far out of view, at map start so first casts do not compile PSOs mid-fight. */
    void WarmUpSpellEffects(UWorld& InWorld);
    /** Per-element scorch / frost / wet / burn / dirt / rune mark under an impact; fades out over ~5 s. */
    void SpawnGroundMark(EHeroSpell Spell, const FVector& Location, const FVector& Normal, float Scale);
    void ShakeNear(const FVector& Location, float Strength);
    /** Freezes time for Seconds of real time (strong hits: 50-80 ms); rate-limited so area spells don't stack it. */
    void HitStop(float Seconds = 0.06f);

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
    /** Tarnish bolt / wisp in flight and wind-up gather (NS_Tarnish_Bolt) and its burst (NS_Tarnish_Burst). Without
     *  them the shared projectile and impact systems stand in, tinted violet and silver. */
    UPROPERTY(Transient) TObjectPtr<UNiagaraSystem> TarnishSystem;
    UPROPERTY(Transient) TObjectPtr<UNiagaraSystem> TarnishBurstSystem;
    UPROPERTY(Transient) TObjectPtr<class USoundBase> ExplosionCue;
    /** Crackle on a body hit by an Electrify reaction (NS_Spell_Shock) and its optional loop (SCue_Shock_Loop). */
    UPROPERTY(Transient) TObjectPtr<UNiagaraSystem> ShockSystem;
    UPROPERTY(Transient) TObjectPtr<class USoundBase> ShockLoopCue;
    struct FBodyShock
    {
        TWeakObjectPtr<UNiagaraComponent> Crackle;
        TWeakObjectPtr<class UAudioComponent> Loop;
        double EndTime = 0.0;
        /** Body-effect kind for afflictions: 0 burn, 1 frost, 2 wet. */
        int32 Kind = -1;
    };
    /** Lingering burn / frost / wet effect on a body (NS_Spell_BodyFx), one per body; a new element replaces it. */
    TMap<TWeakObjectPtr<AActor>, FBodyShock> Afflictions;
    UPROPERTY(Transient) TObjectPtr<UNiagaraSystem> BodyFxSystem;
    /** Optional body-hit sound layer (audio session): light, heavy, and per-element sweeteners indexed by element. */
    UPROPERTY(Transient) TObjectPtr<class USoundBase> BodyHitCue;
    UPROPERTY(Transient) TObjectPtr<class USoundBase> BodyHitHeavyCue;
    UPROPERTY(Transient) TArray<TObjectPtr<class USoundBase>> BodyElementCues;
    double LastHitShake = -1.0;
    void AfflictBody(AActor* Target, int32 Kind, float Duration, float Magnitude, float MaxDuration = 5.0f);
    /** Spawns System on a body's pelvis (or its middle), as a world-up capsule sized to the body. */
    UNiagaraComponent* AttachToBody(UNiagaraSystem* System, AActor* Target, USceneComponent*& OutParent, FName& OutSocket);
    /** Bodies crackling now, by target; a new Electrify hit on the same body extends it. */
    TMap<TWeakObjectPtr<AActor>, FBodyShock> Shocks;
    FTimerHandle ShockTimer;
    void ElectrifyBody(AActor* Target, float Duration, float Magnitude);
    void TickShocks();
    UPROPERTY(Transient) TObjectPtr<UNiagaraSystem> BloodImpact;
    UPROPERTY(Transient) TObjectPtr<UMaterialInterface> BloodSpatter;
    UPROPERTY(Transient) TObjectPtr<UMaterialInterface> GroundMarkMaterial;
    /** Live ground marks, oldest first; capped so rapid fire never piles decals up. */
    TArray<TWeakObjectPtr<UDecalComponent>> GroundMarks;
    FTimerHandle WarmUpTimer;

    TMap<TWeakObjectPtr<AActor>, TWeakObjectPtr<UNiagaraComponent>> ProjectileTrails;
    FDelegateHandle SpawnHandle;
    FTimerHandle HitStopTimer;
    double LastHitStop = -1.0;
};
