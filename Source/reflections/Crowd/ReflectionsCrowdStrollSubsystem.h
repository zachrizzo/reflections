#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "ZoneGraphTypes.h"
#include "ReflectionsCrowdStrollSubsystem.generated.h"

class ACharacter;
class UReflectionsNpcReactionComponent;

/**
 * City-pedestrian strolling for actor NPCs that walk with the hidden sample-locomotion pawn
 * (NPC_SampleLocomotion) and whose archetype roams when calm.
 *
 * While such an NPC is calm, this takes over its body through the unified NPC system
 * (UReflectionsNpcReactionComponent::SetExternallySteered): it picks a goal 4-14 m from home on open floor,
 * walks there at 120-160 cm/s in the sample's Walk gait (no strafing, no sprint), idles a few seconds,
 * and picks the next one. The moment the NPC system reports any other reaction (alert, flee, investigate,
 * fight, down) it hands the body straight back, so reactions (and running away) stay in the NPC system;
 * when the NPC is calm again, strolling resumes from where it stands.
 *
 * Ring walkers take longer sidewalk trips, or collision-checked trips towards the map's street activities when
 * no lanes exist. Predictive local steering keeps pedestrians apart. Some calm walkers travel in pairs, separating
 * immediately for a scene or reaction. All of this uses the existing locomotion driver and NPC ownership rules.
 *
 * Tuning: Crowd.Stroll.* console variables. Crowd.Stroll.Enable 0 gives every body back.
 */
UCLASS(BlueprintType)
class REFLECTIONS_API UReflectionsCrowdStrollSubsystem : public UTickableWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;
    virtual void Deinitialize() override;
    virtual void Tick(float DeltaTime) override;
    virtual TStatId GetStatId() const override;

    /** NPCs currently strolling (calm and steered by this subsystem). */
    UFUNCTION(BlueprintPure, Category="Crowd|Stroll")
    int32 GetStrollingCount() const;

    /** One line per walker: state, speed, distance to goal. */
    UFUNCTION(BlueprintCallable, Category="Crowd|Stroll")
    FString Describe() const;

    /** Street routes loaded for this map (the "routes" graph of Content/Crowd/Spots/<map>.json). */
    UFUNCTION(BlueprintPure, Category="Crowd|Stroll")
    int32 GetRouteNodeCount();

    /**
     * Ring spawns on maps with street routes: a point on a route MinDistance..MaxDistance from Near (2D) that Accept
     * approves, and the yaw along the route there. False when the map has no routes or nothing fits.
     */
    bool FindRouteSpawn(const FVector& Near, float MinDistance, float MaxDistance, TFunctionRef<bool(const FVector&)> Accept,
        FVector& OutLocation, float& OutYaw);

private:
    enum class EPhase : uint8 { Released, Idle, Walking };

    struct FStroller
    {
        TWeakObjectPtr<AActor> Npc;
        TWeakObjectPtr<UReflectionsNpcReactionComponent> Brain;
        TWeakObjectPtr<ACharacter> Driver;
        FVector Home = FVector::ZeroVector;
        FVector Goal = FVector::ZeroVector;
        EPhase Phase = EPhase::Released;
        float PhaseTime = 0.0f;
        float IdleFor = 0.0f;
        float Speed = 140.0f;
        float StuckTime = 0.0f;
        uint32 Seed = 0;
        int32 Picks = 0;
        /** Lane walkers: where on the sidewalk lane the walker is heading (a point a little ahead of it). */
        bool bLaneWalker = false;
        bool bOnLane = false;
        FZoneGraphLaneLocation Lane;
        /** Route walkers (maps with a route graph): walking the edge RouteFrom -> RouteTo, RouteAlong cm along it,
            RouteOffset cm to the left of its centre line (keep left, so head-on passes never cross). */
        bool bOnRoute = false;
        int32 RouteFrom = INDEX_NONE;
        int32 RouteTo = INDEX_NONE;
        float RouteAlong = 0.0f;
        float RouteOffset = 35.0f;
        /** Lane distance still to walk in this leg (cm). */
        float LegLeft = 0.0f;
        float LegLength = 0.0f;
        FVector Heading = FVector::ZeroVector;
        FVector Avoidance = FVector::ZeroVector;
        FVector SafeHeading = FVector::ZeroVector;
        float CurrentSpeed = 0.0f;
        float OriginalMinAnalogSpeed = 0.0f;
        bool bSavedMovement = false;
        float ProbeIn = 0.0f;
        int32 DestinationIndex = INDEX_NONE;
        int32 PreviousDestinationIndex = INDEX_NONE;
        TWeakObjectPtr<AActor> Companion;
        bool bPairLeader = false;
        float PairCooldown = 0.0f;
        float PairSeconds = 0.0f;
        float PairSide = 1.0f;
    };

    struct FStreetDestination
    {
        FName Name;
        FVector Location = FVector::ZeroVector;
    };

    struct FPedestrianObstacle
    {
        TWeakObjectPtr<AActor> Actor;
        TWeakObjectPtr<ACharacter> Driver;
        float Radius = 40.0f;
    };

    void Refresh();
    void Take(FStroller& Stroller, ACharacter* Driver);
    void Release(FStroller& Stroller);
    void ReleaseAll();
    bool PickGoal(FStroller& Stroller, const ACharacter& Driver);
    /** Lane walkers: snap to the nearest lane (if not on one) and start a leg along it. */
    bool StartLaneLeg(FStroller& Stroller, const ACharacter& Driver);
    /** Move the lane point Step cm further, onto the next lane at a lane's end. False when the lane ends nowhere. */
    bool AdvanceLane(FStroller& Stroller, float Step);
    /** Route walkers: join the nearest route edge (within 20 m) and start a leg along it. */
    bool StartRouteLeg(FStroller& Stroller, const ACharacter& Driver);
    /** Move Step cm further along the route, choosing the next edge at a junction (mostly straight on). */
    bool AdvanceRoute(FStroller& Stroller, float Step);
    /** Where on the route the walker heads now: the edge point, offset to the left of travel. */
    FVector RoutePoint(const FStroller& Stroller) const;
    float NextRandom(FStroller& Stroller, float Min, float Max) const;
    void LoadDestinations();
    bool CheckStreetGoal(const FStroller& Stroller, const ACharacter& Driver, const FVector& Candidate, FVector& OutGoal) const;
    void RefreshPairs();
    void BreakPair(FStroller& Stroller);
    FStroller* FindCompanion(const FStroller& Stroller);
    bool TickCompanion(FStroller& Stroller, ACharacter& Driver, float DeltaTime);
    void Steer(FStroller& Stroller, ACharacter& Driver, const FVector& Goal, float WantedSpeed, float DeltaTime);

    TArray<FStroller> Strollers;
    TArray<FStreetDestination> Destinations;
    TArray<FPedestrianObstacle> Obstacles;
    /** Street route graph (undirected): node positions and each node's neighbours. */
    TArray<FVector> RouteNodes;
    TArray<TArray<int32>> RouteLinks;
    float RouteBaseOffset = 35.0f;
    bool bDestinationsLoaded = false;
    double NextRefresh = 0.0;
    bool bWasEnabled = true;
};
