#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SpellCrafting/ReflectionsSpellCraftingTypes.h"
#include "ReflectionsCraftedSpell.generated.h"

class UNiagaraComponent;
class UReflectionsCraftedSpellSubsystem;

UENUM()
enum class ECraftedSpellMode : uint8
{
    Projectile, // Bolt, Orb, Ray and every shard
    Satellite,  // a projectile circling its caster (Orbit)
    Beam,       // a held ray (Ray + Pulse)
    Mine,       // a projectile that stopped and waits (Proximity)
    Fuse,       // waiting to detonate (Delayed)
    Field,      // Nova, Wave, Rain, Rune, Aura
    Hazard,     // lingering pool (Hazard)
    Spent       // finished; lingers briefly so chains and particles can finish
};

/**
 * One live crafted spell. A single actor class plays every form: it reads the resolved recipe and runs the
 * matching mode. Behaviours are implemented once and shared, which is what lets them combine: a Split payload
 * spawns shards that are themselves crafted spells, a Hazard spawns a pool that is itself a crafted spell, and so on.
 * Collision uses sweeps and overlaps only; the actor has no collision of its own.
 */
UCLASS(NotBlueprintable, NotPlaceable)
class REFLECTIONS_API AReflectionsCraftedSpell : public AActor
{
    GENERATED_BODY()

public:
    AReflectionsCraftedSpell();

    /**
     * Releases a resolved recipe: spawns its actor (or several, for satellites) from Origin toward Target.
     * AimTarget is the aim-assist actor, used as the first homing target.
     */
    static void CastSpell(UWorld* World, const FCraftedSpellResolved& Spell, AActor* Caster, const FVector& Origin, const FVector& Target,
        AActor* AimTarget, float Scale = 1.0f);

    virtual void Tick(float DeltaSeconds) override;

    const FCraftedSpellResolved& GetSpell() const { return Spell; }
    ECraftedSpellMode GetMode() const { return Mode; }

private:
    struct FChainJump
    {
        TWeakObjectPtr<AActor> From;
        FVector FromLocation = FVector::ZeroVector;
        int32 Remaining = 0;
        float Clock = 0.0f;
        float Scale = 1.0f;
        TSet<TWeakObjectPtr<AActor>> Hit;
    };

    static AReflectionsCraftedSpell* SpawnSpell(UWorld* World, const FCraftedSpellResolved& Spell, AActor* Caster, ECraftedSpellMode Mode,
        const FVector& Origin, const FVector& Target, AActor* AimTarget, float Scale, int32 Generation, float Phase = 0.0f);
    void Start(ECraftedSpellMode InMode, const FVector& Origin, const FVector& Target, AActor* AimTarget, float InScale, int32 InGeneration, float Phase);

    void TickProjectile(float DeltaSeconds);
    void TickSatellite(float DeltaSeconds);
    void TickBeam(float DeltaSeconds);
    void TickMine(float DeltaSeconds);
    void TickFuse(float DeltaSeconds);
    void TickField(float DeltaSeconds);
    void TickHazard(float DeltaSeconds);
    void TickPull(float DeltaSeconds);
    void TickChains(float DeltaSeconds);

    void Steer(float DeltaSeconds);
    void HandleHit(const FHitResult& Hit);
    /** The trigger point: becomes a fuse or a mine if the recipe says so, otherwise fires the payload and ends. */
    void Fire(const FVector& Location, const FVector& Normal, AActor* DirectHit, const FHitResult* Hit);
    /** Damage/heal in the payload radius plus the behaviours that spawn things. Returns the enemies it hit. */
    TArray<AActor*> Payload(const FVector& Location, const FVector& Normal, AActor* DirectHit, const FHitResult* Hit, float PayloadScale,
        bool bChain, bool bSplit, bool bHazard);
    /** A field's burst: the payload plus per-pulse behaviours (lance, shards), rate-limited. */
    void FieldBurst(const FVector& Center, float BurstScale);
    void RainDrop();
    void TickWave(float DeltaSeconds);
    void StartChain(AActor* From, const FVector& FromLocation, int32 Jumps, float ChainScale, const TArray<AActor*>& AlreadyHit);
    void SpawnShards(const FVector& Location, const FVector& Normal, int32 Count, bool bRadial);
    void FireLance(const FVector& From);
    void SpawnHazard(const FVector& Location);
    void BecomeMine(const FVector& Location);
    void BecomeFuse(const FVector& Location, AActor* AttachTo);
    void Expire();

    FVector GroundBelow(const FVector& Point, float Up = 200.0f) const;
    FVector CasterFeet() const;
    FVector BeamOrigin() const;
    FCollisionQueryParams QueryParams() const;
    UReflectionsCraftedSpellSubsystem* Services() const;
    void SetFxFloat(FName Name, float Value);

    UPROPERTY(VisibleAnywhere)
    TObjectPtr<USceneComponent> Root;

    UPROPERTY(Transient)
    TObjectPtr<UNiagaraComponent> Fx;

    UPROPERTY(Transient)
    TObjectPtr<class UAudioComponent> Loop;

    FCraftedSpellResolved Spell;
    TWeakObjectPtr<AActor> Caster;
    TWeakObjectPtr<AActor> HomingTarget;
    TWeakObjectPtr<AActor> FuseAttach;
    TSet<TWeakObjectPtr<AActor>> Pierced;
    TMap<TWeakObjectPtr<AActor>, float> RecentHits;
    TArray<FChainJump> Chains;
    ECraftedSpellMode Mode = ECraftedSpellMode::Projectile;

    FVector Velocity = FVector::ZeroVector;
    FVector TargetPoint = FVector::ZeroVector;
    FVector Anchor = FVector::ZeroVector;
    FVector LegStart = FVector::ZeroVector;
    FVector WaveDirection = FVector::ForwardVector;
    FVector FuseOffset = FVector::ZeroVector;
    float Age = 0.0f;
    float Life = 1.0f;
    float Scale = 1.0f;
    float Travelled = 0.0f;
    float PulseClock = 0.0f;
    float FieldClock = 0.0f;
    float ShardClock = 0.0f;
    float HazardClock = 0.0f;
    float HopClock = 0.0f;
    float RetargetClock = 0.0f;
    float StormClock = 0.0f;
    float SanctuaryClock = 0.0f;
    float WaveFront = 0.0f;
    float OrbitAngle = 0.0f;
    float FuseClock = 0.0f;
    float HazardRadius = 0.0f;
    int32 Generation = 0;
    int32 BouncesLeft = 0;
    int32 PiercesLeft = 0;
    int32 HopsLeft = 0;
    bool bFused = false;
    bool bBurstDone = false;
    bool bRay = false;
    TSet<TWeakObjectPtr<AActor>> WaveHit;
};
