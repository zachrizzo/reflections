#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Character.h"
#include "SpellVFX/ReflectionsTarnishMagic.h"
#include "ReflectionsVillainPossession.generated.h"

class UMaterialInstanceDynamic;
class UMaterialInterface;
class UMeshComponent;
class UNiagaraComponent;
class UPointLightComponent;
class UReflectionsHealthComponent;
class UReflectionsTarnishCasterComponent;
class UStaticMeshComponent;

UENUM(BlueprintType)
enum class EReflectionsVillainInfection : uint8
{
    None,
    /** Dark veins and a thin smoke: one of his, counted on the infection meter. */
    Infected,
    /** He is inside: heavy smoke, burning eyes, a violet glow. Burns out after a while. */
    Host,
    /** Spent: scorched grey and never taken again. */
    BurnedOut,
};

/**
 * Put on any NPC pawn at runtime (UReflectionsVillainSubsystem does it) to infect it or make it his host.
 * It only adds visuals (an overlay material on every mesh, eyes on the head bone, Niagara smoke, a light)
 * and timers; it never touches the NPC's own components, AI or Blueprint.
 */
UCLASS(ClassGroup = (Villain), meta = (BlueprintSpawnableComponent))
class REFLECTIONS_API UReflectionsVillainPossessionComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UReflectionsVillainPossessionComponent();

    /** Adds the component if needed and moves it to State (never downgrades a host to infected). */
    static UReflectionsVillainPossessionComponent* Apply(AActor* Target, EReflectionsVillainInfection State, AActor* Source = nullptr);
    static EReflectionsVillainInfection StateOf(const AActor* Target);

    UFUNCTION(BlueprintPure, Category = "Villain")
    EReflectionsVillainInfection GetState() const { return State; }

    UFUNCTION(BlueprintPure, Category = "Villain")
    bool IsHost() const { return State == EReflectionsVillainInfection::Host; }

    /** Seconds in the current state. */
    UFUNCTION(BlueprintPure, Category = "Villain")
    float GetStateAge() const { return Age; }

    void SetState(EReflectionsVillainInfection NewState, AActor* Source = nullptr);
    /** Drives him out: back to None (an infected NPC is cured). */
    void Cleanse();
    /** Host time is up (or he was forced out): scorch and optionally kill the body. */
    void BurnOut(bool bKill);
    /** Makes the host's remaining time short (he was hit and wants out). */
    void ShortenHost(float SecondsLeft);
    /** Host seconds left before he burns out of this body (0 when not a host). */
    float GetHostTimeLeft() const { return State == EReflectionsVillainInfection::Host ? FMath::Max(0.0f, Lifetime - Age) : 0.0f; }
    /** A loaded save: this host has SecondsLeft before it burns out. */
    void RestoreHostTime(float SecondsLeft) { if (State == EReflectionsVillainInfection::Host) { Lifetime = Age + FMath::Max(1.0f, SecondsLeft); } }
    /** The body died (a soldier, the player, a fall): drop the look and leave his count. The NPC system already
     *  reported the cure to the meter (bCuredOnDeath), so this never calls SetInfection. */
    void HandleOwnerDied();

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

private:
    void ApplyLook();
    void ClearLook(bool bRestoreOverlays);
    void AddEyes(float Brightness);
    /** Black eyes: MetaHuman eye materials (iris and sclera to black), else black beads on the head bone. */
    void SetBlackEyes(bool bBlack);
    void SetOverlay(UMaterialInterface* Material, float Intensity);
    void TryRift();
    /** Burning eyes: glowing violet-white glints on the MetaHuman eye bones (FACIAL_L/R_Eye), else on the head. */
    void AddBurningEyes(float Brightness);
    void EnsureLight();
    /** Dark-sorcerer read at range: the cast pulse (spell-combat's Tarnish caster) and how fast the body moves. */
    void TickSorcerer(float DeltaTime);
    void BindCaster();
    void SetEyeGlow(float Glow);
    UFUNCTION() void HandleTarnishWindup(EReflectionsTarnishSpell Spell, float Seconds);
    UFUNCTION() void HandleTarnishReleased(EReflectionsTarnishSpell Spell, float Seconds);

    UPROPERTY(Transient) TArray<TObjectPtr<UMeshComponent>> Meshes;
    UPROPERTY(Transient) TArray<TObjectPtr<UMaterialInterface>> SavedOverlays;
    UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> Overlay;
    UPROPERTY(Transient) TObjectPtr<UNiagaraComponent> Smoke;
    UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> Eyes;
    UPROPERTY(Transient) TArray<TObjectPtr<UMaterialInstanceDynamic>> EyeMaterials;
    UPROPERTY(Transient) TObjectPtr<UPointLightComponent> Light;
    UPROPERTY(Transient) TArray<TObjectPtr<UMeshComponent>> EyeMeshes;
    UPROPERTY(Transient) TArray<TObjectPtr<UMaterialInterface>> EyeOriginals;
    TArray<int32> EyeSlots;

    EReflectionsVillainInfection State = EReflectionsVillainInfection::None;
    float Age = 0.0f;
    float Lifetime = 0.0f;
    float NextSpread = 0.0f;
    float Clock = 0.0f;
    bool bRiftChecked = false;
    bool bTaunted = false;
    bool bBlackEyes = false;
    bool bSavedOverlays = false;
    bool bDead = false;
    TWeakObjectPtr<UReflectionsTarnishCasterComponent> BoundCaster;
    float NextCasterCheck = 0.0f;
    float WindupStart = -1.0f;
    float WindupLength = 0.0f;
    float CastFlash = 0.0f;
    float Pulse = 0.0f;
    float Run = 0.0f;
    float Speed = 0.0f;
    float EyePhase = 0.0f;
    FVector LastLocation = FVector::ZeroVector;
    bool bHasLastLocation = false;
};

/** A streak of his smoke flying from one body to the next (a hop or an infection). */
UCLASS()
class REFLECTIONS_API AReflectionsVillainWisp : public AActor
{
    GENERATED_BODY()

public:
    AReflectionsVillainWisp();

    /** Flies to Target; on arrival gives it State. bHop: this is the villain himself moving. */
    void Launch(AActor* InTarget, EReflectionsVillainInfection InState, bool bInHop);

    bool IsHop() const { return bHop; }
    AActor* GetTarget() const { return Target.Get(); }

protected:
    virtual void Tick(float DeltaSeconds) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;

private:
    FVector TargetPoint() const;

    UPROPERTY(VisibleAnywhere) TObjectPtr<USceneComponent> Root;
    UPROPERTY(Transient) TObjectPtr<UNiagaraComponent> Trail;
    UPROPERTY(Transient) TObjectPtr<UNiagaraComponent> Smoke;
    UPROPERTY(Transient) TObjectPtr<UPointLightComponent> Light;

    TWeakObjectPtr<AActor> Target;
    EReflectionsVillainInfection State = EReflectionsVillainInfection::Infected;
    FVector Start = FVector::ZeroVector;
    float Clock = 0.0f;
    float Duration = 1.0f;
    float ArcHeight = 200.0f;
    bool bHop = false;
    bool bArrived = false;
};

/** A plain wandering NPC for testing possession in maps without NPCs (Villain.SpawnTestHosts). */
UCLASS()
class REFLECTIONS_API AReflectionsVillainTestHost : public ACharacter
{
    GENERATED_BODY()

public:
    AReflectionsVillainTestHost();

protected:
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;

private:
    UFUNCTION() void HandleDeath(AActor* Source);

    UPROPERTY(VisibleAnywhere) TObjectPtr<UReflectionsHealthComponent> Health;

    FVector Home = FVector::ZeroVector;
    FVector Heading = FVector::ForwardVector;
    float NextTurn = 0.0f;
    bool bDead = false;
};
