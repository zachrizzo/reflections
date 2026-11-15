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
 * Walkers tagged Crowd_LaneWalker (the ring crowd) walk the ZoneGraph sidewalk lanes instead: a leg of 10-30 m
 * along the nearest lane, following it round corners onto the next lane, then an idle. Without lanes nearby they
 * stroll around home like the others.
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
        /** Lane distance still to walk in this leg (cm). */
        float LegLeft = 0.0f;
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
    float NextRandom(FStroller& Stroller, float Min, float Max) const;

    TArray<FStroller> Strollers;
    double NextRefresh = 0.0;
    bool bWasEnabled = true;
};
