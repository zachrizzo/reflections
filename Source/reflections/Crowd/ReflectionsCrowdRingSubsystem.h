#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "ReflectionsCrowdRingSubsystem.generated.h"

/**
 * The ring crowd: a fixed number of civilians kept around the hero on the ZoneGraph sidewalk lanes of a city map
 * (Crowd.Ring.Maps, default GrayLondon_Geodata), so the streets look lived in at a fixed cost.
 *
 * - Walkers are spawned through the unified NPC system (UReflectionsNpcSubsystem::SpawnNpc with the Civilian
 *   archetype), so they wear the finished civilian looks and react, flee, die and talk like every NPC.
 * - They are tagged Crowd_LaneWalker: the stroll subsystem walks them along the sidewalk lanes.
 * - A calm walker that is far from the hero and has not been seen for a moment is removed, and a new one is
 *   spawned on a lane ahead of the hero, out of sight (one per half second). After a world jump the crowd moves
 *   to the new side the same way.
 * - Crowd.Lod keeps the far ones cheap.
 *
 * Tuning: Crowd.Ring.* console variables. Crowd.Ring.Enable 0 removes them all.
 */
UCLASS(BlueprintType)
class REFLECTIONS_API UReflectionsCrowdRingSubsystem : public UTickableWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;
    virtual void OnWorldBeginPlay(UWorld& InWorld) override;
    virtual void Deinitialize() override;
    virtual void Tick(float DeltaTime) override;
    virtual TStatId GetStatId() const override;

    /** Ring walkers alive now. */
    UFUNCTION(BlueprintPure, Category="Crowd|Ring")
    int32 GetWalkerCount() const { return Walkers.Num(); }

    UFUNCTION(BlueprintCallable, Category="Crowd|Ring")
    TArray<AActor*> GetWalkers() const;

    /** Counts and each walker's distance from the hero (tests). */
    UFUNCTION(BlueprintCallable, Category="Crowd|Ring")
    FString Describe() const;

private:
    struct FRingWalker
    {
        TWeakObjectPtr<AActor> Actor;
        /** When it was first found far away and unseen (-1: not now). */
        double FarSince = -1.0;
        /** Carriers walk with a basket or crate held in front (an additive hold over the walk, and a prop). */
        bool bCarrier = false;
        TWeakObjectPtr<class UAnimMontage> CarryMontage;
        TWeakObjectPtr<class UStaticMeshComponent> CarryProp;
    };

    void TickCarrier(FRingWalker& Walker);

    /** A lane point (ZoneGraph sidewalk lanes). */
    bool FindSpawnPoint(const FVector& Hero, float AheadYaw, bool bAllowSeen, FVector& OutLocation, float& OutYaw) const;
    /** Without lanes: open street floor near the hero's level, outdoors, with room to stand. */
    bool FindFloorPoint(const FVector& Hero, float HeroFeetZ, float AheadYaw, bool bAllowSeen, FVector& OutLocation, float& OutYaw) const;
    bool IsSeen(const FVector& Location) const;
    void SpawnWalker(const FVector& Hero, float HeroFeetZ, float AheadYaw, bool bAllowSeen, bool bLanes);
    void RemoveAll();
    /** Violence (and loud magic, deaths) near the hero: the street empties, and refills only after a lull. */
    void HandleStimulus(const struct FReflectionsNpcStimulus& Stimulus);

    FDelegateHandle StimulusHandle;
    double LastViolenceTime = -1.0e9;
    FVector LastViolenceLocation = FVector::ZeroVector;
    int32 RetiredFled = 0;

    TArray<FRingWalker> Walkers;
    /** The archetype's looks, loaded in the background at the start so a spawn never waits on a synchronous load. */
    TSharedPtr<struct FStreamableHandle> LookPreload;
    double NextCheck = 0.0;
    double StartAt = 0.0;
    bool bActiveMap = false;
    bool bWarnedNoLanes = false;
    bool bWarnedClaimed = false;
    int32 SpawnedTotal = 0;
    int32 RecycledTotal = 0;
    /** Walkers the villain converted: they stay his, the ring replaces them. */
    int32 ReleasedTotal = 0;
    int32 FailedSpawns = 0;
};
