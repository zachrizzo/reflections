#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Hero/ReflectionsHeroCharacter.h"
#include "ReflectionsSpellEventSubsystem.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_FourParams(FReflectionsSpellEvent, EHeroSpell, Spell, FVector, Location, AActor*, Caster, float, Intensity);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_FiveParams(FReflectionsDirectionalSpellVisual, EHeroSpell, Spell, FVector, Location, FVector, Direction, AActor*, Caster, float, Intensity);
/** How a body reacts to a spell hit. Every spell sets it (built-in, crafted, enemy); NPCs choose the animation. */
UENUM(BlueprintType)
enum class EReflectionsSpellReaction : uint8
{
    /** Plain hit: flinch along Impulse. */
    Hit,
    /** Blast from Origin (fireball): thrown away from it; ragdoll when Magnitude is high. */
    Explosion,
    /** Electric shock: convulse for Duration, then collapse. */
    Electrify,
    /** Shoved along Impulse (water wave, force push). */
    Push,
    /** Heavy impact (earth): knocked off the feet. */
    Knockdown,
    /** Thrown upward and away (air, updraft, levitation). */
    Lift,
    /** Drawn toward Origin (gravity well, whirlpool); resent about every 0.5 s while it lasts. */
    Pull,
    /** Slowed or frozen for Duration (ice). */
    Freeze,
    /** Set alight for Duration (fire bolts). */
    Burn,
};

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
    // Reaction stimulus (14 Nov). Impulse above is the velocity the hit gives the body (cm/s, direction x speed);
    // the element is ReflectionsSpellCatalog::Get(Spell).Element (crafted spells send their element's proxy spell).
    /** What the body should do. */
    UPROPERTY(BlueprintReadOnly) EReflectionsSpellReaction Reaction = EReflectionsSpellReaction::Hit;
    /** Strength, 0-1: 1 is a full-power hit at point blank (knockdown or ragdoll); explosions fall off with distance. */
    UPROPERTY(BlueprintReadOnly) float Magnitude = 0.0f;
    /** Seconds an Electrify, Freeze, Burn or Pull lasts (0 for instant reactions). */
    UPROPERTY(BlueprintReadOnly) float Duration = 0.0f;
    /** Blast or pull centre for Explosion and Pull; equals Location for other reactions. */
    UPROPERTY(BlueprintReadOnly) FVector Origin = FVector::ZeroVector;
    /** A repeat tick of an ongoing effect (beam, lingering field, pull): keep the reaction going, but skip one-shot
     *  feedback such as hit-stop, hit markers and blood. */
    UPROPERTY(BlueprintReadOnly) bool bRepeat = false;
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
