#include "Crowd/ReflectionsCrowdStrollSubsystem.h"
#include "NPC/ReflectionsNpcArchetype.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "NPC/ReflectionsNpcSubsystem.h"

#include "Components/CapsuleComponent.h"
#include "DrawDebugHelpers.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "HAL/IConsoleManager.h"
#include "UObject/UnrealType.h"
#include "ZoneGraphSubsystem.h"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsCrowdStroll, Log, All);
DECLARE_CYCLE_STAT(TEXT("Crowd stroll"), STAT_ReflectionsCrowdStroll, STATGROUP_Game);

namespace
{
    TAutoConsoleVariable<int32> CVarStrollEnable(TEXT("Crowd.Stroll.Enable"), 1,
        TEXT("Calm walkers stroll like city pedestrians (walk gait, goals on open floor, idles). 0 gives every body back to the NPC system."));
    TAutoConsoleVariable<float> CVarStrollMinSpeed(TEXT("Crowd.Stroll.MinSpeed"), 120.0f, TEXT("Slowest stroll speed (cm/s)."));
    TAutoConsoleVariable<float> CVarStrollMaxSpeed(TEXT("Crowd.Stroll.MaxSpeed"), 160.0f, TEXT("Fastest stroll speed (cm/s)."));
    TAutoConsoleVariable<float> CVarStrollMinRadius(TEXT("Crowd.Stroll.MinRadius"), 400.0f, TEXT("Nearest stroll goal from home (cm)."));
    TAutoConsoleVariable<float> CVarStrollMaxRadius(TEXT("Crowd.Stroll.MaxRadius"), 1400.0f, TEXT("Farthest stroll goal from home (cm)."));
    TAutoConsoleVariable<int32> CVarStrollDebug(TEXT("Crowd.Stroll.Debug"), 0, TEXT("Draw each strolling walker's goal."));

    TAutoConsoleVariable<float> CVarStrollLaneLegMin(TEXT("Crowd.Stroll.LaneLegMin"), 1000.0f, TEXT("Shortest walk along a sidewalk lane before an idle (cm)."));
    TAutoConsoleVariable<float> CVarStrollLaneLegMax(TEXT("Crowd.Stroll.LaneLegMax"), 3000.0f, TEXT("Longest walk along a sidewalk lane before an idle (cm)."));

    const FName SoldierTag(TEXT("NPC_Soldier"));
    const FName NoStrollTag(TEXT("NPC_NoStroll"));
    const FName LaneWalkerTag(TEXT("Crowd_LaneWalker"));
    constexpr double RefreshPeriod = 1.0;
    constexpr float ArriveRadius = 70.0f;
    /** A lane walker steers at a point this far ahead of it on the lane, so it follows the curve of a corner. */
    constexpr float CarrotDistance = 220.0f;

    /**
     * The sample character keeps its locomotion wishes in a Blueprint struct (CharacterInputState). Walk on means
     * the Walk gait (about 200 cm/s top speed) instead of the default Run; strafing and sprinting stay off for NPCs.
     */
    bool SetSampleWalkGait(ACharacter* Driver, bool bWalk)
    {
        if (!Driver) return false;
        FStructProperty* StateProperty = FindFProperty<FStructProperty>(Driver->GetClass(), TEXT("CharacterInputState"));
        if (!StateProperty || !StateProperty->Struct) return false;
        void* State = StateProperty->ContainerPtrToValuePtr<void>(Driver);
        bool bFound = false;
        for (TFieldIterator<FBoolProperty> It(StateProperty->Struct); It; ++It)
        {
            const FString Name = It->GetAuthoredName();
            if (Name.StartsWith(TEXT("WantsToWalk")))
            {
                It->SetPropertyValue_InContainer(State, bWalk);
                bFound = true;
            }
            else if (Name.StartsWith(TEXT("WantsToStrafe")) || Name.StartsWith(TEXT("WantsToSprint")) || Name.StartsWith(TEXT("WantsToAim")))
            {
                It->SetPropertyValue_InContainer(State, false);
            }
        }
        return bFound;
    }

    bool IsStrollCandidate(const AActor* Actor, const UReflectionsNpcReactionComponent* Brain)
    {
        if (!Actor || !Brain || !Brain->GetLocomotionDriver()) return false;
        if (Actor->ActorHasTag(SoldierTag) || Actor->ActorHasTag(NoStrollTag)) return false;
        switch (Brain->Disposition)
        {
        case EReflectionsNpcDisposition::Enemy:
        case EReflectionsNpcDisposition::Infected:
        case EReflectionsNpcDisposition::VillainHost:
            return false;
        default:
            break;
        }
        const UReflectionsNpcArchetype* Archetype = Brain->GetActiveArchetype();
        return Archetype && Archetype->Reaction.bRoamsWhenCalm;
    }

    const TCHAR* PhaseName(int32 Phase)
    {
        return Phase == 2 ? TEXT("walking") : Phase == 1 ? TEXT("idle") : TEXT("released");
    }
}

bool UReflectionsCrowdStrollSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId UReflectionsCrowdStrollSubsystem::GetStatId() const
{
    RETURN_QUICK_DECLARE_CYCLE_STAT(UReflectionsCrowdStrollSubsystem, STATGROUP_Tickables);
}

void UReflectionsCrowdStrollSubsystem::Deinitialize()
{
    Strollers.Reset();
    Super::Deinitialize();
}

float UReflectionsCrowdStrollSubsystem::NextRandom(FStroller& Stroller, float Min, float Max) const
{
    Stroller.Seed = Stroller.Seed * 1664525u + 1013904223u;
    return Min + (Max - Min) * static_cast<float>(Stroller.Seed >> 8) / 16777216.0f;
}

int32 UReflectionsCrowdStrollSubsystem::GetStrollingCount() const
{
    int32 Count = 0;
    for (const FStroller& Stroller : Strollers)
        if (Stroller.Phase != EPhase::Released) ++Count;
    return Count;
}

void UReflectionsCrowdStrollSubsystem::Take(FStroller& Stroller, ACharacter* Driver)
{
    UReflectionsNpcReactionComponent* Brain = Stroller.Brain.Get();
    if (!Brain || !Driver) return;
    Brain->SetExternallySteered(true);
    if (!SetSampleWalkGait(Driver, true))
    {
        UE_LOG(LogReflectionsCrowdStroll, Verbose, TEXT("%s: no CharacterInputState on its driver; speed cap only."), *GetNameSafe(Stroller.Npc.Get()));
    }
    Stroller.Driver = Driver;
    Stroller.Phase = EPhase::Idle;
    Stroller.PhaseTime = 0.0f;
    Stroller.IdleFor = NextRandom(Stroller, 0.3f, 2.0f);
    Stroller.StuckTime = 0.0f;
}

void UReflectionsCrowdStrollSubsystem::Release(FStroller& Stroller)
{
    if (Stroller.Phase == EPhase::Released) return;
    if (UReflectionsNpcReactionComponent* Brain = Stroller.Brain.Get()) Brain->SetExternallySteered(false);
    // Reactions may run (fleeing is allowed to): leave the Walk gait, keep strafing off.
    SetSampleWalkGait(Stroller.Driver.Get(), false);
    Stroller.Phase = EPhase::Released;
    Stroller.PhaseTime = 0.0f;
    // It may run off somewhere: find the nearest lane again when it is calm.
    Stroller.bOnLane = false;
}

void UReflectionsCrowdStrollSubsystem::ReleaseAll()
{
    for (FStroller& Stroller : Strollers) Release(Stroller);
}

void UReflectionsCrowdStrollSubsystem::Refresh()
{
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    if (!Npcs) return;
    TArray<FStroller> Next;
    for (AActor* Actor : Npcs->GetNpcActors())
    {
        UReflectionsNpcReactionComponent* Brain = Npcs->FindNpc(Actor);
        FStroller* Existing = Strollers.FindByPredicate([Actor](const FStroller& S) { return S.Npc.Get() == Actor; });
        if (!IsStrollCandidate(Actor, Brain))
        {
            if (Existing) Release(*Existing);
            continue;
        }
        if (Existing)
        {
            Next.Add(*Existing);
            continue;
        }
        // Someone else (a squad, a cutscene, the villain) already moves this body: leave it alone.
        if (Brain->IsExternallySteered()) continue;
        FStroller& Stroller = Next.AddDefaulted_GetRef();
        Stroller.Npc = Actor;
        Stroller.Brain = Brain;
        Stroller.Home = Brain->GetHomeLocation();
        Stroller.Seed = GetTypeHash(Actor->GetFName()) | 1u;
        Stroller.Speed = NextRandom(Stroller, CVarStrollMinSpeed.GetValueOnGameThread(), CVarStrollMaxSpeed.GetValueOnGameThread());
        Stroller.bLaneWalker = Actor->ActorHasTag(LaneWalkerTag);
    }
    // Anyone who dropped out of the NPC list is let go before being forgotten.
    for (FStroller& Old : Strollers)
    {
        if (!Next.ContainsByPredicate([&Old](const FStroller& S) { return S.Npc == Old.Npc; })) Release(Old);
    }
    Strollers = MoveTemp(Next);
}

bool UReflectionsCrowdStrollSubsystem::PickGoal(FStroller& Stroller, const ACharacter& Driver)
{
    UWorld* World = GetWorld();
    const UCapsuleComponent* Capsule = Driver.GetCapsuleComponent();
    if (!World || !Capsule) return false;
    const float Radius = Capsule->GetScaledCapsuleRadius();
    const float HalfHeight = Capsule->GetScaledCapsuleHalfHeight();
    const FVector From = Driver.GetActorLocation();
    const float FeetZ = From.Z - HalfHeight;
    const float MinRadius = CVarStrollMinRadius.GetValueOnGameThread();
    const float MaxRadius = FMath::Max(MinRadius + 50.0f, CVarStrollMaxRadius.GetValueOnGameThread());

    FCollisionQueryParams Params(SCENE_QUERY_STAT(CrowdStrollGoal), false, &Driver);
    Params.AddIgnoredActor(Stroller.Npc.Get());
    FCollisionObjectQueryParams Solid(ECC_WorldStatic);
    Solid.AddObjectTypesToQuery(ECC_WorldDynamic);
    const FCollisionShape Body = FCollisionShape::MakeCapsule(Radius * 0.9f, HalfHeight * 0.6f);

    for (int32 Try = 0; Try < 10; ++Try)
    {
        const float Angle = FMath::DegreesToRadians(NextRandom(Stroller, 0.0f, 360.0f));
        const float Distance = NextRandom(Stroller, MinRadius, MaxRadius);
        const FVector Candidate = Stroller.Home + FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0.0f) * Distance;
        if (FVector::Dist2D(Candidate, From) < 300.0f) continue;

        // Open floor at about the walker's own height: no climbing onto blocks, no stepping off ledges.
        FHitResult Floor;
        if (!World->LineTraceSingleByObjectType(Floor, FVector(Candidate.X, Candidate.Y, FeetZ + 150.0f),
            FVector(Candidate.X, Candidate.Y, FeetZ - 200.0f), Solid, Params)) continue;
        if (FMath::Abs(Floor.ImpactPoint.Z - FeetZ) > 40.0f || Floor.ImpactNormal.Z < 0.8f) continue;

        // A straight, clear walk: sweep a slightly slimmer body, lifted off the floor, against walls and props.
        const FVector Lift(0.0f, 0.0f, HalfHeight * 0.4f + 5.0f);
        const FVector GoalCentre(Candidate.X, Candidate.Y, Floor.ImpactPoint.Z + HalfHeight + 2.0f);
        FHitResult Blocked;
        if (World->SweepSingleByObjectType(Blocked, From + Lift, GoalCentre + Lift, FQuat::Identity, Solid, Body, Params)) continue;

        Stroller.Goal = GoalCentre;
        ++Stroller.Picks;
        return true;
    }
    return false;
}

bool UReflectionsCrowdStrollSubsystem::StartLaneLeg(FStroller& Stroller, const ACharacter& Driver)
{
    const UZoneGraphSubsystem* ZoneGraph = UWorld::GetSubsystem<UZoneGraphSubsystem>(GetWorld());
    if (!ZoneGraph) return false;
    const FVector Here = Driver.GetActorLocation();
    if (!Stroller.bOnLane || FVector::Dist2D(Stroller.Lane.Position, Here) > 400.0f)
    {
        const FVector Extent(600.0f, 600.0f, 300.0f);
        FZoneGraphLaneLocation Nearest;
        float DistanceSq = 0.0f;
        if (!ZoneGraph->FindNearestLane(FBox(Here - Extent, Here + Extent), FZoneGraphTagFilter(), Nearest, DistanceSq))
        {
            Stroller.bOnLane = false;
            return false;
        }
        Stroller.Lane = Nearest;
        Stroller.bOnLane = true;
    }
    const float LegMin = CVarStrollLaneLegMin.GetValueOnGameThread();
    Stroller.LegLeft = NextRandom(Stroller, LegMin, FMath::Max(LegMin, CVarStrollLaneLegMax.GetValueOnGameThread()));
    Stroller.Goal = Stroller.Lane.Position;
    ++Stroller.Picks;
    return true;
}

bool UReflectionsCrowdStrollSubsystem::AdvanceLane(FStroller& Stroller, float Step)
{
    const UZoneGraphSubsystem* ZoneGraph = UWorld::GetSubsystem<UZoneGraphSubsystem>(GetWorld());
    float Length = 0.0f;
    if (!ZoneGraph || !ZoneGraph->GetLaneLength(Stroller.Lane.LaneHandle, Length)) return false;
    const float Left = Length - Stroller.Lane.DistanceAlongLane;
    FZoneGraphLaneLocation Next;
    if (Step < Left)
    {
        if (!ZoneGraph->AdvanceLaneLocation(Stroller.Lane, Step, Next)) return false;
        Stroller.Lane = Next;
        return true;
    }
    // End of this lane: carry on along a lane that starts here (round the corner of the block).
    TArray<FZoneGraphLinkedLane> Links;
    ZoneGraph->GetLinkedLanes(Stroller.Lane.LaneHandle, EZoneLaneLinkType::Outgoing, EZoneLaneLinkFlags::All, EZoneLaneLinkFlags::None, Links);
    if (Links.IsEmpty())
    {
        // A dead end: turn round onto the lane running the other way.
        ZoneGraph->GetLinkedLanes(Stroller.Lane.LaneHandle, EZoneLaneLinkType::Adjacent, EZoneLaneLinkFlags::OppositeDirection, EZoneLaneLinkFlags::None, Links);
    }
    if (Links.IsEmpty()) return false;
    const int32 Pick = FMath::Clamp(static_cast<int32>(NextRandom(Stroller, 0.0f, static_cast<float>(Links.Num()))), 0, Links.Num() - 1);
    if (!ZoneGraph->CalculateLocationAlongLane(Links[Pick].DestLane, FMath::Max(0.0f, Step - Left), Next)) return false;
    Stroller.Lane = Next;
    return true;
}

void UReflectionsCrowdStrollSubsystem::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    UWorld* World = GetWorld();
    if (!World || !World->HasBegunPlay()) return;
    SCOPE_CYCLE_COUNTER(STAT_ReflectionsCrowdStroll);

    const bool bEnabled = CVarStrollEnable.GetValueOnGameThread() != 0;
    if (!bEnabled)
    {
        if (bWasEnabled) ReleaseAll();
        bWasEnabled = false;
        return;
    }
    bWasEnabled = true;
    if (World->GetTimeSeconds() >= NextRefresh)
    {
        NextRefresh = World->GetTimeSeconds() + RefreshPeriod;
        Refresh();
    }

    const bool bDebug = CVarStrollDebug.GetValueOnGameThread() != 0;
    for (FStroller& Stroller : Strollers)
    {
        UReflectionsNpcReactionComponent* Brain = Stroller.Brain.Get();
        ACharacter* Driver = Brain ? Brain->GetLocomotionDriver() : nullptr;
        if (!Brain || !Driver || Brain->IsIncapacitated() || Brain->Reaction != EReflectionsNpcReaction::Calm)
        {
            // Any reaction belongs to the NPC system, which moves (and may run) on its own.
            Release(Stroller);
            continue;
        }
        if (Stroller.Phase == EPhase::Released)
        {
            // Calm again: keep the bodies that someone else is steering out of it.
            if (Brain->IsExternallySteered()) continue;
            Take(Stroller, Driver);
        }
        Stroller.PhaseTime += DeltaTime;

        if (Stroller.Phase == EPhase::Idle)
        {
            if (Stroller.PhaseTime < Stroller.IdleFor) continue;
            // Lane walkers follow the sidewalk lanes; with none nearby they stroll round home like the others.
            const bool bLaneLeg = Stroller.bLaneWalker && StartLaneLeg(Stroller, *Driver);
            if (!bLaneLeg) Stroller.bOnLane = false;
            if (bLaneLeg || PickGoal(Stroller, *Driver))
            {
                Stroller.Phase = EPhase::Walking;
                Stroller.PhaseTime = 0.0f;
                Stroller.StuckTime = 0.0f;
            }
            else
            {
                Stroller.IdleFor = Stroller.PhaseTime + 1.0f;
            }
            continue;
        }

        const FVector Here = Driver->GetActorLocation();
        const bool bLaneLeg = Stroller.bLaneWalker && Stroller.bOnLane;
        if (bLaneLeg)
        {
            // Keep the lane point a little ahead of the walker until the leg's distance is used up.
            for (int32 Guard = 0; Guard < 8 && Stroller.LegLeft > 0.0f && FVector::Dist2D(Here, Stroller.Lane.Position) < CarrotDistance; ++Guard)
            {
                const float Step = FMath::Min(60.0f, Stroller.LegLeft);
                if (!AdvanceLane(Stroller, Step))
                {
                    Stroller.LegLeft = 0.0f;
                    break;
                }
                Stroller.LegLeft -= Step;
            }
            Stroller.Goal = Stroller.Lane.Position;
        }
        const FVector ToGoal(Stroller.Goal.X - Here.X, Stroller.Goal.Y - Here.Y, 0.0f);
        const float Distance = ToGoal.Size();
        const float LegLimit = bLaneLeg ? 60.0f
            : FVector::Dist2D(Stroller.Home, Stroller.Goal) / FMath::Max(50.0f, Stroller.Speed) * 2.0f + 12.0f;
        const bool bArrived = Distance < ArriveRadius && (!bLaneLeg || Stroller.LegLeft <= 0.0f);
        if (bArrived || Stroller.PhaseTime > LegLimit)
        {
            // Arrived: a short stop most of the time, now and then a longer one.
            Stroller.Phase = EPhase::Idle;
            Stroller.PhaseTime = 0.0f;
            Stroller.IdleFor = NextRandom(Stroller, 0.0f, 1.0f) < 0.15f ? NextRandom(Stroller, 7.0f, 12.0f) : NextRandom(Stroller, 1.5f, 5.0f);
            continue;
        }
        UCharacterMovementComponent* Movement = Driver->GetCharacterMovement();
        if (!Movement) continue;
        if (Distance < 1.0f) continue;
        // Ease in over the last metre so it does not overshoot and turn back (not mid-way along a lane).
        const float Slow = bLaneLeg && Stroller.LegLeft > 0.0f ? 1.0f
            : FMath::GetMappedRangeValueClamped(FVector2f(40.0f, 140.0f), FVector2f(0.55f, 1.0f), Distance);
        const float Scale = FMath::Clamp(Stroller.Speed * Slow / FMath::Max(1.0f, Movement->GetMaxSpeed()), 0.12f, 1.0f);
        Driver->AddMovementInput(ToGoal / Distance, Scale, true);

        // Walked into something the goal sweep missed (another walker, the player): pick again shortly.
        if (Stroller.PhaseTime > 1.0f && Driver->GetVelocity().Size2D() < 25.0f) Stroller.StuckTime += DeltaTime;
        else Stroller.StuckTime = 0.0f;
        if (Stroller.StuckTime > 1.5f)
        {
            Stroller.Phase = EPhase::Idle;
            Stroller.PhaseTime = 0.0f;
            Stroller.IdleFor = 0.6f;
        }
        if (bDebug)
        {
            DrawDebugLine(World, Here, Stroller.Goal, FColor::Green, false, 0.0f, 0, 1.5f);
            DrawDebugSphere(World, Stroller.Goal, 25.0f, 8, FColor::Green, false, 0.0f);
        }
    }
}

FString UReflectionsCrowdStrollSubsystem::Describe() const
{
    FString Out = FString::Printf(TEXT("Crowd stroll: %d strolling of %d candidates, enabled %d"), GetStrollingCount(), Strollers.Num(),
        CVarStrollEnable.GetValueOnGameThread());
    for (const FStroller& Stroller : Strollers)
    {
        const ACharacter* Driver = Stroller.Driver.Get();
        Out += FString::Printf(TEXT("\n  %s: %s%s, %.0f cm/s now (target %.0f), %.0f cm to goal, %d goals"),
            *GetNameSafe(Stroller.Npc.Get()), PhaseName(static_cast<int32>(Stroller.Phase)),
            Stroller.bLaneWalker ? (Stroller.bOnLane ? TEXT(" on lane") : TEXT(" (lane walker, no lane)")) : TEXT(""),
            Driver ? Driver->GetVelocity().Size2D() : 0.0f, Stroller.Speed,
            Driver ? FVector::Dist2D(Driver->GetActorLocation(), Stroller.Goal) : 0.0f, Stroller.Picks);
    }
    return Out;
}
