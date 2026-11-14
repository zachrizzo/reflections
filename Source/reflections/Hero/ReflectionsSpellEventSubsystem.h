#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Hero/ReflectionsHeroCharacter.h"
#include "ReflectionsSpellEventSubsystem.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_FourParams(FReflectionsSpellEvent, EHeroSpell, Spell, FVector, Location, AActor*, Caster, float, Intensity);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_FiveParams(FReflectionsDirectionalSpellVisual, EHeroSpell, Spell, FVector, Location, FVector, Direction, AActor*, Caster, float, Intensity);
USTRUCT(BlueprintType)
struct FReflectionsSpellHitData
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly) EHeroSpell Spell = EHeroSpell::Fire;
    UPROPERTY(BlueprintReadOnly) FVector Location = FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly) FVector Impulse = FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly) FVector ImpactNormal = FVector::UpVector;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<AActor> Caster = nullptr;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<AActor> Target = nullptr;
    UPROPERTY(BlueprintReadOnly) FName Bone = NAME_None;
    UPROPERTY(BlueprintReadOnly) TEnumAsByte<EPhysicalSurface> Surface = SurfaceType_Default;
};
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FReflectionsSpellHitEvent, const FReflectionsSpellHitData&, Hit);

/** World-level event that nearby NPCs can use to react to spell impacts. */
UCLASS()
class REFLECTIONS_API UReflectionsSpellEventSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()
public:
    UPROPERTY(BlueprintAssignable, Category="Spells")
    FReflectionsSpellEvent OnSpellEvent;
    /** Non-hostile cast visuals, kept separate from danger/reputation events. */
    UPROPERTY(BlueprintAssignable, Category="Spells")
    FReflectionsSpellEvent OnSupportSpellVisual;
    /** Carries aim direction for visual effects; does not drive AI reactions. */
    UPROPERTY(BlueprintAssignable, Category="Spells")
    FReflectionsDirectionalSpellVisual OnDirectionalSpellVisual;
    UPROPERTY(BlueprintAssignable, Category="Spells")
    FReflectionsSpellHitEvent OnSpellHit;
    /** Visual-only burst where a spell lands. Direction carries the surface normal, Intensity the visual scale. */
    UPROPERTY(BlueprintAssignable, Category="Spells")
    FReflectionsDirectionalSpellVisual OnSpellImpactVisual;
    /** Visual-only flash at the casting hand. Direction is the aim direction, Intensity the visual scale. */
    UPROPERTY(BlueprintAssignable, Category="Spells")
    FReflectionsDirectionalSpellVisual OnSpellReleaseVisual;

    void BroadcastSpell(EHeroSpell Spell, FVector Location, AActor* Caster, float Intensity)
    {
        OnSpellEvent.Broadcast(Spell, Location, Caster, FMath::Max(0.0f, Intensity));
    }
};
