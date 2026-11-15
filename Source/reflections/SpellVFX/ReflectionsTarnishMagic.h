#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ReflectionsTarnishMagic.generated.h"

class UDecalComponent;
class UNiagaraComponent;
class UPointLightComponent;
class USceneComponent;
class USkeletalMeshComponent;

/** The Tarnish's own magic, cast by tarnished NPCs (never by the player). */
UENUM(BlueprintType)
enum class EReflectionsTarnishSpell : uint8
{
    /** Fast black-violet dart with a smoke wake and silver sparks. */
    Bolt UMETA(DisplayName="Tarnish Bolt"),
    /** Slow, swollen orb that homes gently; dodgeable by moving across its path. */
    Wisp UMETA(DisplayName="Tarnish Wisp"),
    /** Short-range dark blast around the caster, warned by a violet ring on the ground. */
    Burst UMETA(DisplayName="Tarnish Burst"),
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FReflectionsTarnishCastEvent, EReflectionsTarnishSpell, Spell, float, Seconds);

/**
 * Enemy magic for tarnished NPCs. Add it to the NPC actor and call StartCast from its AI: it shows a readable
 * wind-up (black-violet gather and a pulsing violet light at the casting hand; a ground ring for Burst), then
 * releases on its own. Hits use the same projectile and area path as squad casters (AReflectionsSpellProjectile and
 * AffectTarget), so the unified NPC system's harm rules apply. Animation and movement stay with the AI: play the
 * gesture from OnTarnishWindup / OnTarnishReleased.
 */
UCLASS(ClassGroup=(Combat), BlueprintType, meta=(BlueprintSpawnableComponent))
class REFLECTIONS_API UReflectionsTarnishCasterComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UReflectionsTarnishCasterComponent();

    // Damage, tuned for a 100 HP player: three bolts take a third of their health.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Tarnish|Damage", meta=(ClampMin="0"))
    float BoltDamage = 11.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Tarnish|Damage", meta=(ClampMin="0"))
    float WispDamage = 9.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Tarnish|Damage", meta=(ClampMin="0"))
    float BurstDamage = 13.0f;

    // Wind-up before each release: long enough to read and react to.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Tarnish|Timing", meta=(ClampMin="0.2", Units="s"))
    float BoltWindup = 0.8f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Tarnish|Timing", meta=(ClampMin="0.2", Units="s"))
    float WispWindup = 1.1f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Tarnish|Timing", meta=(ClampMin="0.2", Units="s"))
    float BurstWindup = 1.0f;
    /** Time after a release before the next cast may start. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Tarnish|Timing", meta=(ClampMin="0", Units="s"))
    float RecoverTime = 0.4f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Tarnish|Flight", meta=(ClampMin="100", Units="cm/s"))
    float BoltSpeed = 1500.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Tarnish|Flight", meta=(ClampMin="100", Units="cm/s"))
    float WispSpeed = 620.0f;
    /** How far a bolt flies before it fizzles. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Tarnish|Flight", meta=(ClampMin="100", Units="cm"))
    float BoltRange = 2600.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Tarnish|Flight", meta=(ClampMin="100", Units="cm"))
    float WispRange = 2300.0f;
    /** Wisp homing acceleration as a multiple of its speed (player spells use 2.2). Lower is easier to dodge. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Tarnish|Flight", meta=(ClampMin="0"))
    float WispHoming = 1.4f;
    /** Bolts lead a moving target by this fraction of its velocity times the flight time. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Tarnish|Flight", meta=(ClampMin="0", ClampMax="1"))
    float AimLead = 0.5f;
    /** Random aim error for bolts. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Tarnish|Flight", meta=(ClampMin="0", Units="cm"))
    float AimSpread = 40.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Tarnish|Burst", meta=(ClampMin="50", Units="cm"))
    float BurstRadius = 340.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Tarnish|Burst", meta=(ClampMin="0"))
    float BurstPush = 420.0f;

    /** Socket on the cast body the magic gathers at and leaves from. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Tarnish")
    FName HandSocket = TEXT("hand_r");

    /** A wind-up started; Seconds is its length (play the cast gesture). */
    UPROPERTY(BlueprintAssignable, Category="Tarnish")
    FReflectionsTarnishCastEvent OnTarnishWindup;
    /** The spell left the hand (Seconds is 0). */
    UPROPERTY(BlueprintAssignable, Category="Tarnish")
    FReflectionsTarnishCastEvent OnTarnishReleased;

    /** Starts the wind-up for Spell at Target; it releases by itself. False while casting or recovering, or without a target. */
    UFUNCTION(BlueprintCallable, Category="Tarnish")
    bool StartCast(EReflectionsTarnishSpell Spell, AActor* Target);

    /** Stops a wind-up without releasing (stagger, death, cure). */
    UFUNCTION(BlueprintCallable, Category="Tarnish")
    void CancelCast();

    /** Releases Spell at Target right now, with no wind-up (for AI that runs its own timing). Returns the projectile
     *  for Bolt and Wisp, the caster for Burst, or null. */
    UFUNCTION(BlueprintCallable, Category="Tarnish")
    AActor* ReleaseNow(EReflectionsTarnishSpell Spell, AActor* Target);

    /** True from StartCast until the recovery after the release ends. */
    UFUNCTION(BlueprintPure, Category="Tarnish")
    bool IsCasting() const { return Phase != EPhase::Ready; }

    UFUNCTION(BlueprintPure, Category="Tarnish")
    EReflectionsTarnishSpell GetCurrentSpell() const { return CurrentSpell; }

    UFUNCTION(BlueprintPure, Category="Tarnish")
    float GetWindup(EReflectionsTarnishSpell Spell) const;

    /** Distance to the target at which Spell is worth casting (Burst: inside its blast). */
    UFUNCTION(BlueprintPure, Category="Tarnish")
    float GetCastRange(EReflectionsTarnishSpell Spell) const;

    /** The mesh that holds HandSocket (the visible body). By default the first skeletal mesh on the owner with it. */
    UFUNCTION(BlueprintCallable, Category="Tarnish")
    void SetCastBody(USkeletalMeshComponent* Body);

    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* TickFunction) override;

protected:
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;

private:
    enum class EPhase : uint8 { Ready, Windup, Recover };

    USceneComponent* FindHand(FName& OutSocket) const;
    FVector HandLocation() const;
    /** Owner plus the hidden pawn that walks for it: never hit by our own magic. */
    TArray<AActor*> OwnActors() const;
    AActor* Release(EReflectionsTarnishSpell Spell, AActor* Target);
    void ClearTelegraph();
    void Finish();

    UPROPERTY(Transient) TObjectPtr<USkeletalMeshComponent> CastBody;
    UPROPERTY(Transient) TObjectPtr<UNiagaraComponent> Telegraph;
    UPROPERTY(Transient) TObjectPtr<UPointLightComponent> TelegraphLight;
    UPROPERTY(Transient) TObjectPtr<UDecalComponent> Warning;
    TWeakObjectPtr<AActor> CastTarget;
    EPhase Phase = EPhase::Ready;
    EReflectionsTarnishSpell CurrentSpell = EReflectionsTarnishSpell::Bolt;
    float PhaseTime = 0.0f;
    float WindupLength = 0.0f;
};
