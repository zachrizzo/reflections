#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Pawn.h"
#include "ReflectionsVillainBoss.generated.h"

class UAudioComponent;
class UCapsuleComponent;
class UInstancedStaticMeshComponent;
class UMaterialInstanceDynamic;
class UNiagaraComponent;
class UProjectileMovementComponent;
class UReflectionsVillainLookComponent;
class USphereComponent;
class UStaticMeshComponent;

UENUM(BlueprintType)
enum class EReflectionsVillainBossState : uint8
{
    /** Hidden in the tower until the player comes close. */
    Dormant,
    Manifesting,
    Fighting,
    Dying,
    Dead,
};

UENUM(BlueprintType)
enum class EReflectionsVillainAttack : uint8
{
    None,
    /** Shadow orbs gather over his head, then fly at the player one by one: strafe. */
    Volley,
    /** Violet circles fill on the ground under and around the player, then the dark erupts: step out. */
    Grasp,
    /** He rises and slams; a ring of black spikes sweeps outward along the ground: jump it. */
    Wave,
};

/**
 * His true form, in Frostside's tower (White). Barely hurt by ordinary spells; the Final Spell
 * (UReflectionsFinalSpellDamageType) does full damage. Three telegraphed attacks, a faster second phase
 * under half health, and a dissolve on death that hands victory to game flow.
 */
UCLASS()
class REFLECTIONS_API AReflectionsVillainBoss : public APawn
{
    GENERATED_BODY()

public:
    AReflectionsVillainBoss();

    static FText DisplayName();

    void InitArena(const FVector& GroundCenter, float Radius);

    UFUNCTION(BlueprintPure, Category = "Villain") float GetHealth() const { return Health; }
    UFUNCTION(BlueprintPure, Category = "Villain") float GetMaxHealth() const { return MaxHealth; }
    UFUNCTION(BlueprintPure, Category = "Villain") EReflectionsVillainBossState GetBossState() const { return State; }
    UFUNCTION(BlueprintPure, Category = "Villain") bool IsSecondPhase() const { return bPhaseTwo; }
    FString DescribeState() const;

    /** Starts the fight now (skips waiting for the player to come close). */
    void Manifest();

    virtual float TakeDamage(float DamageAmount, struct FDamageEvent const& DamageEvent, AController* EventInstigator, AActor* DamageCauser) override;

    /** Attack helpers report the player's position here. */
    APawn* GetPlayer() const;
    float GetGroundZ() const { return ArenaCenter.Z; }

protected:
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;

private:
    void TickManifest(float DeltaSeconds);
    void TickFight(float DeltaSeconds);
    void TickDying(float DeltaSeconds);
    void Hover(float DeltaSeconds, float ExtraHeight);
    void FacePlayer(float DeltaSeconds);
    void ChooseAttack();
    void StartAttack(EReflectionsVillainAttack Attack);
    void TickAttack(float DeltaSeconds);
    void EndAttack();
    void Blink();
    void FireOrb(int32 Index);
    void ClearCharge();
    void SpawnHazards();
    void SpawnWave();
    void Die();
    void UpdateHud(bool bVisible);
    float TelegraphTime(float Base) const;

    UPROPERTY(VisibleAnywhere) TObjectPtr<UCapsuleComponent> Capsule;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UReflectionsVillainLookComponent> Look;
    UPROPERTY(Transient) TArray<TObjectPtr<UNiagaraComponent>> ChargeOrbs;
    UPROPERTY(Transient) TObjectPtr<UNiagaraComponent> Column;
    UPROPERTY(Transient) TObjectPtr<UAudioComponent> Music;
    UPROPERTY(Transient) TArray<TWeakObjectPtr<AActor>> Spawned;

    EReflectionsVillainBossState State = EReflectionsVillainBossState::Dormant;
    EReflectionsVillainAttack Attack = EReflectionsVillainAttack::None;
    EReflectionsVillainAttack LastAttack = EReflectionsVillainAttack::None;
    FVector ArenaCenter = FVector::ZeroVector;
    FVector Station = FVector::ZeroVector;
    float ArenaRadius = 1400.0f;
    float MaxHealth = 1000.0f;
    float Health = 1000.0f;
    float StateClock = 0.0f;
    float AttackClock = 0.0f;
    float Telegraph = 1.0f;
    float NextAttack = 0.0f;
    float NextTaunt = 0.0f;
    float NextBurst = 0.0f;
    float HoverClock = 0.0f;
    float Rise = 0.0f;
    float LastResistMessage = -100.0f;
    float LastHurtVoice = -100.0f;
    float PhaseTwoAt = -1.0f;
    int32 StoryLines = 0;
    bool bFirstFinalHit = false;
    bool bDeathLine = false;
    int32 OrbCount = 0;
    int32 OrbsFired = 0;
    int32 WavesFired = 0;
    bool bPhaseTwo = false;
    bool bHazardsSpawned = false;
    bool bBlinkFirst = false;
};

/** One of his shadow orbs. Flies straight; hurts the player on contact. */
UCLASS()
class REFLECTIONS_API AReflectionsVillainOrb : public AActor
{
    GENERATED_BODY()

public:
    AReflectionsVillainOrb();
    void Fire(const FVector& Direction, float Speed, float InDamage, AActor* InBoss);

protected:
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;

private:
    UFUNCTION() void HandleHit(UPrimitiveComponent* HitComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp, FVector NormalImpulse, const FHitResult& Hit);
    void Explode(AActor* Victim);

    UPROPERTY(VisibleAnywhere) TObjectPtr<USphereComponent> Collision;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UProjectileMovementComponent> Movement;
    UPROPERTY(Transient) TObjectPtr<UNiagaraComponent> Visual;
    TWeakObjectPtr<AActor> Boss;
    float Damage = 10.0f;
    bool bDone = false;
};

/** A violet circle on the ground that fills, then erupts. Also the wave's warning ring. */
UCLASS()
class REFLECTIONS_API AReflectionsVillainHazard : public AActor
{
    GENERATED_BODY()

public:
    AReflectionsVillainHazard();
    /** Delay 0 or less: only a warning ring that fades after FadeAfter seconds. */
    void Setup(float InRadius, float InDelay, float InDamage, AActor* InBoss, float FadeAfter = 0.0f);

protected:
    virtual void Tick(float DeltaSeconds) override;

private:
    void Erupt();

    UPROPERTY(VisibleAnywhere) TObjectPtr<USceneComponent> Root;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> Disc;
    UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> Material;
    TWeakObjectPtr<AActor> Boss;
    float Radius = 240.0f;
    float Delay = 1.5f;
    float Damage = 18.0f;
    float Life = 0.0f;
    float Clock = 0.0f;
    bool bErupted = false;
    bool bWarningOnly = false;
};

/** An expanding ring of black spikes along the ground. Jump over it or be far away. */
UCLASS()
class REFLECTIONS_API AReflectionsVillainWave : public AActor
{
    GENERATED_BODY()

public:
    AReflectionsVillainWave();
    void Setup(float InSpeed, float InMaxRadius, float InDamage, AActor* InBoss);

protected:
    virtual void Tick(float DeltaSeconds) override;

private:
    UPROPERTY(VisibleAnywhere) TObjectPtr<USceneComponent> Root;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UInstancedStaticMeshComponent> Spikes;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> Band;
    UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> BandMaterial;
    TWeakObjectPtr<AActor> Boss;
    TArray<float> Phases;
    float Radius = 120.0f;
    float Speed = 750.0f;
    float MaxRadius = 2200.0f;
    float Damage = 14.0f;
    float Clock = 0.0f;
    bool bHit = false;
};
