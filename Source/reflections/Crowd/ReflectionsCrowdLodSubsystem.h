#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Hero/ReflectionsSpellEventSubsystem.h"
#include "NPC/ReflectionsNpcArchetype.h"
#include "ReflectionsCrowdLodSubsystem.generated.h"

class ACharacter;
class USkeletalMeshComponent;

UENUM(BlueprintType)
enum class EReflectionsCrowdLodTier : uint8
{
    /** Every frame: near the camera, reacting to a spell, hit, or simulating physics. */
    Full,
    /** On screen, beyond Crowd.Lod.NearDistance. */
    Mid,
    /** On screen, beyond Crowd.Lod.FarDistance. */
    Far,
    /** Not rendered recently (behind the camera or occluded). */
    Hidden
};

/**
 * Animation update-rate LOD for crowd walkers: actors tagged NPC_SampleLocomotion and the hidden
 * locomotion pawn each one is attached to. Far and off-screen walkers evaluate motion matching and their
 * MetaHuman body/face less often. Any walker near a spell, hit by one, simulating physics (hit reaction or
 * ragdoll) or near the camera goes back to every-frame animation at once.
 *
 * It only changes skeletal-mesh tick intervals. Movement, reactions, health, damage and ragdoll stay in the
 * unified NPC system (NPC/), and movement (CharacterMovement) is never throttled. Wake-ups come from that
 * system too: UReflectionsNpcSubsystem's stimulus feed, NPC reactions and NPC spell hits.
 * Tuning: Crowd.Lod.* console variables. Inspect: Crowd.LodDump.
 */
UCLASS(BlueprintType)
class REFLECTIONS_API UReflectionsCrowdLodSubsystem : public UTickableWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;
    virtual void OnWorldBeginPlay(UWorld& InWorld) override;
    virtual void Deinitialize() override;
    virtual void Tick(float DeltaTime) override;
    virtual TStatId GetStatId() const override;

    /** Every walker within Radius of Location animates every frame for Crowd.Lod.WakeSeconds. */
    UFUNCTION(BlueprintCallable, Category="Crowd|LOD")
    void WakeNear(FVector Location, float Radius);

    /** One line per walker: label, tier, distance to the camera, seconds left awake. */
    UFUNCTION(BlueprintCallable, Category="Crowd|LOD")
    FString Describe() const;

    UFUNCTION(BlueprintPure, Category="Crowd|LOD")
    int32 CountInTier(EReflectionsCrowdLodTier Tier) const;

    UFUNCTION(BlueprintPure, Category="Crowd|LOD")
    int32 NumWalkers() const { return Walkers.Num(); }

    UFUNCTION(BlueprintPure, Category="Crowd|LOD")
    EReflectionsCrowdLodTier GetTier(const AActor* Walker) const;

private:
    struct FWalker
    {
        TWeakObjectPtr<AActor> Actor;
        TWeakObjectPtr<ACharacter> Driver;
        TWeakObjectPtr<USkeletalMeshComponent> Body;
        TArray<TWeakObjectPtr<USkeletalMeshComponent>> Meshes;
        TArray<float> OriginalIntervals;
        double AwakeUntil = 0.0;
        float LastDistance = 0.0f;
        EReflectionsCrowdLodTier Tier = EReflectionsCrowdLodTier::Full;
        /** When its body went ragdoll (dead: root body simulating, driver capsule off); -1 while it is not. */
        double RagdollSince = -1.0;
        double NextCorpseCheck = 0.0;
        int32 CorpseLifts = 0;
    };

    /** Corpse regrounding (Crowd.Lod.RegroundCorpses): lifts a fresh ragdoll that lies under a road or floor sheet. */
    void TickCorpse(FWalker& Walker, double Time);

    void Rescan();
    void UpdateTiers();
    void ApplyTier(FWalker& Walker, EReflectionsCrowdLodTier Tier, bool bForce = false);
    void CollectMeshes(FWalker& Walker) const;
    void RestoreAll();
    double Now() const;

    void WakeActor(const AActor* Actor);
    void HandleStimulus(const FReflectionsNpcStimulus& Stimulus);
    UFUNCTION() void HandleNpcReaction(AActor* Npc, EReflectionsNpcReaction Reaction, AActor* Cause, FVector Location);
    UFUNCTION() void HandleNpcSpellHit(AActor* Npc, const FReflectionsSpellHitData& Hit);

    TArray<FWalker> Walkers;
    FDelegateHandle StimulusHandle;
    double NextUpdate = 0.0;
    double NextRescan = 0.0;
    bool bWasEnabled = true;
};
