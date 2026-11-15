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
    /**
     * Something a crafted spell can hurt, like the catalog spells: anything alive except the caster, what is attached
     * to it and the Player. Civilians tagged Friendly are harmable (and healable, see IsAlly).
     */
    static bool IsEnemy(const AActor* Actor, const AActor* Caster);
    /** Harmable and not Friendly: what spells seek out on their own (homing, ricochets, chains, swarms, triggers). */
    static bool IsHostile(const AActor* Actor, const AActor* Caster);
    static bool IsAlly(const AActor* Actor, const AActor* Caster);
    /** Harmable actors whose collision overlaps a sphere (only hostile ones with bHostileOnly). Physics props included. */
    void FindEnemies(const FVector& Location, float Radius, const AActor* Caster, TArray<AActor*>& Out, bool bHostileOnly = false) const;
    void FindAllies(const FVector& Location, float Radius, const AActor* Caster, TArray<AActor*>& Out) const;
    /** Nearest hostile pawn within Range, optionally inside a cone around Direction, skipping Exclude. Never a civilian. */
    AActor* NearestEnemy(const FVector& Location, float Range, const AActor* Caster, const TSet<TWeakObjectPtr<AActor>>* Exclude = nullptr,
        const FVector* Direction = nullptr, float ConeCos = -1.0f) const;

    // ---- hits
    /**
     * Damage (or healing, for Life on allies), knockback, element status and the shared spell-hit event with its
     * reaction (element -> Explosion / Burn / Electrify / Push / Knockdown / Lift / Freeze / Hit). Returns damage dealt.
     * Quiet hits (rain drops, pools, auras, beams) skip the shared hit event, so they do not trigger hit-stop on every
     * tick, except that an ongoing reaction (electrify, burn, freeze, lift) is kept alive at most every 0.5 s per target
     * with bRepeat set. BlastRadius > 0 marks a burst payload around Origin: the reaction falls off with distance, and a
     * fire burst of 150 cm or more is an Explosion instead of a Burn.
     */
    float ApplyHit(const FCraftedSpellResolved& Spell, AActor* Target, AActor* Caster, float Scale, const FVector& Origin, const FHitResult* DirectHit = nullptr,
        bool bQuiet = false, float BlastRadius = 0.0f);
    float HealActor(AActor* Target, float Amount, AActor* Healer);
    void AddBurn(AActor* Target, AActor* Caster, float Dps, float Seconds);
    void AddSlow(AActor* Target, float Factor, float Seconds);
    /** Moves Target toward Center (or up, for Updraft). Call every frame while a pull is active. With Spell, it also
     *  sends the Pull (or Lift) reaction about every 0.5 s per target, so NPCs play being dragged. */
    void Pull(AActor* Target, const FVector& Center, float Strength, float Radius, bool bLift, float DeltaTime,
        const FCraftedSpellResolved* Spell = nullptr, AActor* Caster = nullptr);

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
    /** When each target last got a reaction from a crafted spell: the 0.5 s upkeep limit and the bRepeat flag. */
    TMap<TWeakObjectPtr<AActor>, double> ReactionSent;
    /** May a reaction go to Target now? Loud hits always may (bOutRepeat false); quiet upkeep at most every 0.5 s,
     *  repeating when the target had one within the last 1.5 s. Records the send. */
    bool TakeReactionSlot(AActor* Target, bool bQuiet, bool& bOutRepeat);
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
