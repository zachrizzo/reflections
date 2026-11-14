#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "SpellCrafting/ReflectionsSpellCraftingTypes.h"
#include "ReflectionsCraftedSpellSubsystem.generated.h"

class UNiagaraComponent;
class UNiagaraSystem;
class USceneComponent;

/** Which crafted Niagara system to use. */
enum class ECraftedFx : uint8 { Body, Burst, Arc, Field };

/**
 * World-level services for crafted spells:
 *  - gives the local spell-casting pawn a crafting component (no Blueprint edits needed),
 *  - runs element status effects (burn, slow, stun) that outlive the spell that applied them,
 *  - shared targeting and hit application,
 *  - spawns the crafted Niagara systems and feeds them the recipe's procedural look.
 */
UCLASS()
class REFLECTIONS_API UReflectionsCraftedSpellSubsystem : public UTickableWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual bool DoesSupportWorldType(EWorldType::Type WorldType) const override;
    virtual void OnWorldBeginPlay(UWorld& InWorld) override;
    virtual void Tick(float DeltaTime) override;
    virtual TStatId GetStatId() const override;

    static UReflectionsCraftedSpellSubsystem* Get(const UObject* WorldContext);

    // ---- targeting
    /** Something a crafted spell should hurt: not the caster, not attached to it, not tagged Friendly. */
    static bool IsEnemy(const AActor* Actor, const AActor* Caster);
    static bool IsAlly(const AActor* Actor, const AActor* Caster);
    /** Enemies whose collision overlaps a sphere. Pawns first; physics props included. */
    void FindEnemies(const FVector& Location, float Radius, const AActor* Caster, TArray<AActor*>& Out) const;
    void FindAllies(const FVector& Location, float Radius, const AActor* Caster, TArray<AActor*>& Out) const;
    /** Nearest enemy pawn within Range, optionally inside a cone around Direction, skipping Exclude. */
    AActor* NearestEnemy(const FVector& Location, float Range, const AActor* Caster, const TSet<TWeakObjectPtr<AActor>>* Exclude = nullptr,
        const FVector* Direction = nullptr, float ConeCos = -1.0f) const;

    // ---- hits
    /** Damage (or healing, for Life on allies), knockback, element status and the shared spell-hit event. Returns damage dealt. */
    /** Quiet hits (rain drops, pools, auras) skip the shared hit event, so they do not trigger hit-stop on every tick. */
    float ApplyHit(const FCraftedSpellResolved& Spell, AActor* Target, AActor* Caster, float Scale, const FVector& Origin, const FHitResult* DirectHit = nullptr,
        bool bQuiet = false);
    float HealActor(AActor* Target, float Amount, AActor* Healer);
    void AddBurn(AActor* Target, AActor* Caster, float Dps, float Seconds);
    void AddSlow(AActor* Target, float Factor, float Seconds);
    /** Moves Target toward Center (or up, for Updraft). Call every frame while a pull is active. */
    void Pull(AActor* Target, const FVector& Center, float Strength, float Radius, bool bLift, float DeltaTime);

    // ---- visuals
    UNiagaraComponent* SpawnFx(ECraftedFx Kind, const FCraftedSpellLook& Look, const FVector& Location, const FRotator& Rotation,
        USceneComponent* AttachTo = nullptr, float Scale = 1.0f);
    void SpawnArc(const FCraftedSpellLook& Look, const FVector& Start, const FVector& End, float Seconds = 0.25f);
    static void ApplyLook(UNiagaraComponent* Component, const FCraftedSpellLook& Look, float Scale);
    /** Camera feedback when a blast lands near the local player. */
    void Shake(const FVector& Location, float Strength) const;

    // ---- audio (/Game/Audio/Jam/Cues, from the audio session)
    /** The element's cast cue at the hand. Bigger spells play lower. */
    void PlayCastCue(const FCraftedSpellResolved& Spell, const FVector& Location);
    /** The element's impact cue; throttled so rain and pools don't flood the mixer. */
    void PlayImpactCue(const FCraftedSpellResolved& Spell, const FVector& Location, float Size, bool bMinor);
    /** Looping hum for slow flying spells; the caller stops it. */
    class UAudioComponent* AttachLoopCue(USceneComponent* AttachTo, const FCraftedSpellResolved& Spell);
    void PlayUiCue(const TCHAR* Name);

private:
    void EnsureCraftingComponents();
    class USoundBase* Cue(const TCHAR* Name);
    UNiagaraSystem* SystemFor(ECraftedFx Kind, bool& bFallback);

    struct FBurn { TWeakObjectPtr<AActor> Target; TWeakObjectPtr<AActor> Caster; float Dps = 0; float Remaining = 0; float Clock = 0; };
    struct FSlow { TWeakObjectPtr<AActor> Target; float Factor = 1; float Remaining = 0; };
    TArray<FBurn> Burns;
    TArray<FSlow> Slows;
    TMap<TWeakObjectPtr<AActor>, double> LastPull;
    struct FArc { TWeakObjectPtr<UNiagaraComponent> Fx; float Remaining = 0; };
    TArray<FArc> Arcs;

    UPROPERTY(Transient) TObjectPtr<UNiagaraSystem> BodySystem;
    UPROPERTY(Transient) TObjectPtr<UNiagaraSystem> BurstSystem;
    UPROPERTY(Transient) TObjectPtr<UNiagaraSystem> ArcSystem;
    UPROPERTY(Transient) TObjectPtr<UNiagaraSystem> FieldSystem;
    bool bLoadedSystems = false;
    UPROPERTY(Transient) TMap<FName, TObjectPtr<class USoundBase>> Cues;
    double LastImpactCue = 0.0;
    int32 ImpactCuesThisSecond = 0;
    float AttachClock = 0.0f;
};
