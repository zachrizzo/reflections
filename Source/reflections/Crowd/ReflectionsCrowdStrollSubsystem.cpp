#include "Crowd/ReflectionsCrowdStrollSubsystem.h"
#include "NPC/ReflectionsNpcArchetype.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "NPC/ReflectionsNpcSubsystem.h"

#include "Components/CapsuleComponent.h"
#include "Dom/JsonObject.h"
#include "DrawDebugHelpers.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
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

    TAutoConsoleVariable<float> CVarStrollLaneLegMin(TEXT("Crowd.Stroll.LaneLegMin"), 2500.0f, TEXT("Shortest walk along a sidewalk lane before an idle (cm)."));
    TAutoConsoleVariable<float> CVarStrollLaneLegMax(TEXT("Crowd.Stroll.LaneLegMax"), 6500.0f, TEXT("Longest walk along a sidewalk lane before an idle (cm)."));
    TAutoConsoleVariable<int32> CVarStrollDestinations(TEXT("Crowd.Stroll.Destinations"), 1, TEXT("Ring walkers take checked trips towards the map's street activities, including without ZoneGraph lanes."));
    TAutoConsoleVariable<int32> CVarStrollAvoidance(TEXT("Crowd.Stroll.Avoidance"), 1, TEXT("Predict nearby pedestrians and steer round them before their bodies overlap."));
    TAutoConsoleVariable<float> CVarStrollPersonalSpace(TEXT("Crowd.Stroll.PersonalSpace"), 25.0f, TEXT("Extra clearance between pedestrian capsules (cm)."));
    TAutoConsoleVariable<float> CVarStrollPairs(TEXT("Crowd.Stroll.PairShare"), 0.35f, TEXT("Target share of ring walkers travelling in pairs, 0 disables. Scenes and danger break pairs immediately."));

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
    ReleaseAll();
    Strollers.Reset();
    Obstacles.Reset();
    Destinations.Reset();
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
    Stroller.CurrentSpeed = Driver->GetVelocity().Size2D();
    Stroller.Heading = Driver->GetVelocity().GetSafeNormal2D();
    if (Stroller.Heading.IsNearlyZero()) Stroller.Heading = Driver->GetActorForwardVector().GetSafeNormal2D();
    Stroller.Avoidance = FVector::ZeroVector;
    Stroller.ProbeIn = 0.0f;
    if (UCharacterMovementComponent* Movement = Driver->GetCharacterMovement())
    {
        Stroller.OriginalMinAnalogSpeed = Movement->MinAnalogWalkSpeed;
        Stroller.bSavedMovement = true;
        // The sample's minimum analog speed otherwise turns gentle braking inputs back into a full walk.
        Movement->MinAnalogWalkSpeed = 0.0f;
    }
}

void UReflectionsCrowdStrollSubsystem::Release(FStroller& Stroller)
{
    BreakPair(Stroller);
    if (Stroller.Phase == EPhase::Released) return;
    if (Stroller.bSavedMovement)
    {
        if (ACharacter* Driver = Stroller.Driver.Get())
            if (UCharacterMovementComponent* Movement = Driver->GetCharacterMovement()) Movement->MinAnalogWalkSpeed = Stroller.OriginalMinAnalogSpeed;
        Stroller.bSavedMovement = false;
    }
    if (UReflectionsNpcReactionComponent* Brain = Stroller.Brain.Get()) Brain->SetExternallySteered(false);
    // Reactions may run (fleeing is allowed to): leave the Walk gait, keep strafing off.
    SetSampleWalkGait(Stroller.Driver.Get(), false);
    Stroller.Phase = EPhase::Released;
    Stroller.PhaseTime = 0.0f;
    // It may run off somewhere: find the nearest lane (or route) again when it is calm.
    Stroller.bOnLane = false;
    Stroller.bOnRoute = false;
    Stroller.CurrentSpeed = 0.0f;
    Stroller.Avoidance = FVector::ZeroVector;
}

void UReflectionsCrowdStrollSubsystem::ReleaseAll()
{
    for (FStroller& Stroller : Strollers) Release(Stroller);
}

void UReflectionsCrowdStrollSubsystem::Refresh()
{
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    if (!Npcs) return;
    if (!bDestinationsLoaded) LoadDestinations();
    Obstacles.Reset();
    TArray<FStroller> Next;
    for (AActor* Actor : Npcs->GetNpcActors())
    {
        UReflectionsNpcReactionComponent* Brain = Npcs->FindNpc(Actor);
        if (Brain && !Brain->IsIncapacitated())
        {
            if (ACharacter* Driver = Brain->GetMovementCharacter())
            {
                const UCapsuleComponent* Capsule = Driver->GetCapsuleComponent();
                Obstacles.Add({Actor, Driver, Capsule ? Capsule->GetScaledCapsuleRadius() : 40.0f});
            }
        }
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
    if (ACharacter* Player = Cast<ACharacter>(UGameplayStatics::GetPlayerPawn(this, 0)))
    {
        const UCapsuleComponent* Capsule = Player->GetCapsuleComponent();
        Obstacles.Add({Player, Player, Capsule ? Capsule->GetScaledCapsuleRadius() : 40.0f});
    }
    // Anyone who dropped out of the NPC list is let go before being forgotten.
    for (FStroller& Old : Strollers)
    {
        if (!Next.ContainsByPredicate([&Old](const FStroller& S) { return S.Npc == Old.Npc; })) Release(Old);
    }
    Strollers = MoveTemp(Next);
    RefreshPairs();
}

void UReflectionsCrowdStrollSubsystem::LoadDestinations()
{
    bDestinationsLoaded = true;
    FString Text;
    const FString Map = UWorld::RemovePIEPrefix(GetWorld()->GetMapName());
    TSharedPtr<FJsonObject> Root;
    const FString Path = FPaths::ProjectContentDir() / TEXT("Crowd/Spots") / (Map + TEXT(".json"));
    if (!FFileHelper::LoadFileToString(Text, *Path) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root) return;
    // Street routes (generated from the map's layout, e.g. Tools/Crowd/build_medieval_crowd.py):
    // {"routes": {"nodes": [[x, y, z], ...], "edges": [[a, b], ...], "offset_cm": 35}}
    const TSharedPtr<FJsonObject>* Routes = nullptr;
    if (Root->TryGetObjectField(TEXT("routes"), Routes) && Routes && *Routes)
    {
        const TArray<TSharedPtr<FJsonValue>>* Nodes = nullptr;
        const TArray<TSharedPtr<FJsonValue>>* Edges = nullptr;
        if ((*Routes)->TryGetArrayField(TEXT("nodes"), Nodes) && (*Routes)->TryGetArrayField(TEXT("edges"), Edges))
        {
            for (const TSharedPtr<FJsonValue>& Value : *Nodes)
            {
                const TArray<TSharedPtr<FJsonValue>>* XYZ = nullptr;
                if (!Value->TryGetArray(XYZ) || XYZ->Num() < 3) { RouteNodes.Reset(); break; }
                RouteNodes.Add(FVector((*XYZ)[0]->AsNumber(), (*XYZ)[1]->AsNumber(), (*XYZ)[2]->AsNumber()));
            }
            RouteLinks.SetNum(RouteNodes.Num());
            for (const TSharedPtr<FJsonValue>& Value : *Edges)
            {
                const TArray<TSharedPtr<FJsonValue>>* Pair = nullptr;
                if (!Value->TryGetArray(Pair) || Pair->Num() < 2) continue;
                const int32 A = static_cast<int32>((*Pair)[0]->AsNumber());
                const int32 B = static_cast<int32>((*Pair)[1]->AsNumber());
                if (A == B || !RouteNodes.IsValidIndex(A) || !RouteNodes.IsValidIndex(B)) continue;
                RouteLinks[A].AddUnique(B);
                RouteLinks[B].AddUnique(A);
            }
            double Offset = 35.0;
            if ((*Routes)->TryGetNumberField(TEXT("offset_cm"), Offset)) RouteBaseOffset = FMath::Clamp(static_cast<float>(Offset), 0.0f, 120.0f);
            UE_LOG(LogReflectionsCrowdStroll, Log, TEXT("Crowd stroll: %d route nodes on %s."), RouteNodes.Num(), *Map);
        }
    }
    const TArray<TSharedPtr<FJsonValue>>* Spots = nullptr;
    if (!Root->TryGetArrayField(TEXT("spots"), Spots)) return;
    for (const TSharedPtr<FJsonValue>& Value : *Spots)
    {
        const TSharedPtr<FJsonObject>* Spot = nullptr;
        if (!Value->TryGetObject(Spot) || !Spot || !*Spot) continue;
        double X, Y, Z;
        FString Name;
        if (!(*Spot)->TryGetNumberField(TEXT("x"), X) || !(*Spot)->TryGetNumberField(TEXT("y"), Y)
            || !(*Spot)->TryGetNumberField(TEXT("z"), Z) || !(*Spot)->TryGetStringField(TEXT("name"), Name)) continue;
        Destinations.Add({FName(*Name), FVector(X, Y, Z)});
    }
}

bool UReflectionsCrowdStrollSubsystem::CheckStreetGoal(const FStroller& Stroller, const ACharacter& Driver,
    const FVector& Candidate, FVector& OutGoal) const
{
    const UCapsuleComponent* Capsule = Driver.GetCapsuleComponent();
    UWorld* World = GetWorld();
    if (!World || !Capsule) return false;
    const float HalfHeight = Capsule->GetScaledCapsuleHalfHeight();
    const float Radius = Capsule->GetScaledCapsuleRadius();
    FVector Previous = Driver.GetActorLocation();
    const FVector Start = Previous;
    float FeetZ = Start.Z - HalfHeight;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(CrowdStreetRoute), false, &Driver);
    Params.AddIgnoredActor(Stroller.Npc.Get());
    FCollisionObjectQueryParams Solid(ECC_WorldStatic);
    Solid.AddObjectTypesToQuery(ECC_WorldDynamic);
    const FCollisionShape Body = FCollisionShape::MakeCapsule(Radius * 0.95f, HalfHeight * 0.65f);
    const int32 Steps = FMath::Clamp(FMath::CeilToInt(FVector::Dist2D(Start, Candidate) / 250.0), 1, 32);
    for (int32 Step = 1; Step <= Steps; ++Step)
    {
        const FVector Point = FMath::Lerp(Start, Candidate, static_cast<double>(Step) / Steps);
        FHitResult Floor;
        if (!World->LineTraceSingleByObjectType(Floor, FVector(Point.X, Point.Y, FeetZ + 100.0f),
            FVector(Point.X, Point.Y, FeetZ - 120.0f), Solid, Params)
            || Floor.ImpactNormal.Z < 0.8f || FMath::Abs(Floor.ImpactPoint.Z - FeetZ) > 45.0f) return false;
        const FVector Next(Point.X, Point.Y, Floor.ImpactPoint.Z + HalfHeight + 2.0f);
        FHitResult Block;
        if (World->SweepSingleByObjectType(Block, Previous, Next, FQuat::Identity, Solid, Body, Params)) return false;
        Previous = Next;
        FeetZ = Floor.ImpactPoint.Z;
    }
    OutGoal = Previous;
    return true;
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
    const float MinRadius = Stroller.bLaneWalker ? 1000.0f : CVarStrollMinRadius.GetValueOnGameThread();
    const float MaxRadius = Stroller.bLaneWalker ? 2600.0f : FMath::Max(MinRadius + 50.0f, CVarStrollMaxRadius.GetValueOnGameThread());
    if (Stroller.DestinationIndex != INDEX_NONE) Stroller.PreviousDestinationIndex = Stroller.DestinationIndex;
    Stroller.DestinationIndex = INDEX_NONE;

    if (Stroller.bLaneWalker && CVarStrollDestinations.GetValueOnGameThread() != 0 && !Destinations.IsEmpty())
    {
        // Visit a distinct nearby activity. Each trip is checked all the way, including floor between endpoints;
        // there is no navigation mesh in Gray London, so a wall or a canal must never be treated as a valid route.
        const int32 Start = FMath::Clamp(static_cast<int32>(NextRandom(Stroller, 0.0f, Destinations.Num())), 0, Destinations.Num() - 1);
        int32 Checks = 0;
        for (int32 Offset = 0; Offset < Destinations.Num() && Checks < 6; ++Offset)
        {
            const int32 Index = (Start + Offset) % Destinations.Num();
            if (Index == Stroller.PreviousDestinationIndex) continue;
            const FVector Target = Destinations[Index].Location;
            const float Distance = FVector::Dist2D(From, Target);
            if (Distance < 600.0f || Distance > 5500.0f) continue;
            ++Checks;
            // Stop beside the activity, leaving the exact reserved seat/shop slot to the scene system.
            const FVector Approach = Target + (From - Target).GetSafeNormal2D() * 180.0f;
            if (!CheckStreetGoal(Stroller, Driver, Approach, Stroller.Goal)) continue;
            Stroller.DestinationIndex = Index;
            ++Stroller.Picks;
            return true;
        }
    }

    FCollisionQueryParams Params(SCENE_QUERY_STAT(CrowdStrollGoal), false, &Driver);
    Params.AddIgnoredActor(Stroller.Npc.Get());
    FCollisionObjectQueryParams Solid(ECC_WorldStatic);
    Solid.AddObjectTypesToQuery(ECC_WorldDynamic);
    const FCollisionShape Body = FCollisionShape::MakeCapsule(Radius * 0.9f, HalfHeight * 0.6f);

    for (int32 Try = 0; Try < 10; ++Try)
    {
        const float Heading = FMath::RadiansToDegrees(FMath::Atan2(Stroller.Heading.Y, Stroller.Heading.X));
        const float Angle = FMath::DegreesToRadians(Stroller.bLaneWalker
            ? Heading + NextRandom(Stroller, Try < 5 ? -65.0f : -160.0f, Try < 5 ? 65.0f : 160.0f)
            : NextRandom(Stroller, 0.0f, 360.0f));
        const float Distance = NextRandom(Stroller, MinRadius, MaxRadius);
        const FVector Candidate = (Stroller.bLaneWalker ? From : Stroller.Home) + FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0.0f) * Distance;
        if (FVector::Dist2D(Candidate, From) < 300.0f) continue;

        if (Stroller.bLaneWalker)
        {
            if (!CheckStreetGoal(Stroller, Driver, Candidate, Stroller.Goal)) continue;
            ++Stroller.Picks;
            return true;
        }

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
        // Wide enough that a walker who ran off (a fright) heads back to the sidewalk once calm.
        const FVector Extent(2000.0f, 2000.0f, 300.0f);
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
    Stroller.LegLength = Stroller.LegLeft;
    if (CVarStrollDestinations.GetValueOnGameThread() != 0 && !Destinations.IsEmpty())
    {
        const int32 Start = FMath::RandHelper(Destinations.Num());
        for (int32 Offset = 0; Offset < Destinations.Num(); ++Offset)
        {
            const int32 Index = (Start + Offset) % Destinations.Num();
            const float Distance = FVector::Dist2D(Here, Destinations[Index].Location);
            if (Index == Stroller.DestinationIndex || Distance < 1200.0f || Distance > 7500.0f) continue;
            Stroller.DestinationIndex = Index;
            break;
        }
    }
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
    int32 Pick = FMath::Clamp(static_cast<int32>(NextRandom(Stroller, 0.0f, static_cast<float>(Links.Num()))), 0, Links.Num() - 1);
    if (CVarStrollDestinations.GetValueOnGameThread() != 0 && Destinations.IsValidIndex(Stroller.DestinationIndex))
    {
        const FVector Towards = (Destinations[Stroller.DestinationIndex].Location - Stroller.Lane.Position).GetSafeNormal2D();
        double BestScore = -2.0;
        for (int32 Index = 0; Index < Links.Num(); ++Index)
        {
            FZoneGraphLaneLocation Probe;
            float LinkedLength = 0.0f;
            if (!ZoneGraph->GetLaneLength(Links[Index].DestLane, LinkedLength)
                || !ZoneGraph->CalculateLocationAlongLane(Links[Index].DestLane, FMath::Min(300.0f, LinkedLength), Probe)) continue;
            const double Score = FVector::DotProduct((Probe.Position - Stroller.Lane.Position).GetSafeNormal2D(), Towards);
            if (Score > BestScore) { BestScore = Score; Pick = Index; }
        }
    }
    if (!ZoneGraph->CalculateLocationAlongLane(Links[Pick].DestLane, FMath::Max(0.0f, Step - Left), Next)) return false;
    Stroller.Lane = Next;
    return true;
}

int32 UReflectionsCrowdStrollSubsystem::GetRouteNodeCount()
{
    if (!bDestinationsLoaded) LoadDestinations();
    return RouteNodes.Num();
}

FVector UReflectionsCrowdStrollSubsystem::RoutePoint(const FStroller& Stroller) const
{
    if (!RouteNodes.IsValidIndex(Stroller.RouteFrom) || !RouteNodes.IsValidIndex(Stroller.RouteTo)) return Stroller.Goal;
    const FVector A = RouteNodes[Stroller.RouteFrom];
    const FVector B = RouteNodes[Stroller.RouteTo];
    const float Length = FMath::Max(1.0, FVector::Dist2D(A, B));
    const FVector Direction = (B - A).GetSafeNormal2D();
    const FVector Left(Direction.Y, -Direction.X, 0.0);
    return FMath::Lerp(A, B, static_cast<double>(FMath::Clamp(Stroller.RouteAlong / Length, 0.0f, 1.0f))) + Left * Stroller.RouteOffset;
}

bool UReflectionsCrowdStrollSubsystem::StartRouteLeg(FStroller& Stroller, const ACharacter& Driver)
{
    if (RouteNodes.Num() < 2) return false;
    const FVector Here = Driver.GetActorLocation();
    if (!Stroller.bOnRoute || FVector::Dist2D(RoutePoint(Stroller), Here) > 400.0f)
    {
        // The nearest point on any edge within 20 m (wide enough to find the way back after a fright).
        double Best = FMath::Square(2000.0);
        int32 BestA = INDEX_NONE, BestB = INDEX_NONE;
        double BestT = 0.0;
        for (int32 A = 0; A < RouteNodes.Num(); ++A)
        {
            for (const int32 B : RouteLinks[A])
            {
                if (B < A) continue;
                const FVector P = RouteNodes[A], Q = RouteNodes[B];
                const FVector Segment(Q.X - P.X, Q.Y - P.Y, 0.0);
                const double LengthSq = Segment.SizeSquared();
                const double T = LengthSq > 1.0 ? FMath::Clamp(FVector::DotProduct(FVector(Here.X - P.X, Here.Y - P.Y, 0.0), Segment) / LengthSq, 0.0, 1.0) : 0.0;
                const double DistanceSq = FVector::DistSquared2D(Here, P + Segment * T);
                if (DistanceSq < Best) { Best = DistanceSq; BestA = A; BestB = B; BestT = T; }
            }
        }
        if (BestA == INDEX_NONE)
        {
            Stroller.bOnRoute = false;
            return false;
        }
        // Walk the way it faces (a fresh walker: its spawn yaw), else either way.
        const FVector Along = (RouteNodes[BestB] - RouteNodes[BestA]).GetSafeNormal2D();
        const bool bForward = Stroller.Heading.IsNearlyZero() ? NextRandom(Stroller, 0.0f, 1.0f) < 0.5f
            : FVector::DotProduct(Along, Stroller.Heading) >= 0.0;
        const float Length = FVector::Dist2D(RouteNodes[BestA], RouteNodes[BestB]);
        Stroller.RouteFrom = bForward ? BestA : BestB;
        Stroller.RouteTo = bForward ? BestB : BestA;
        Stroller.RouteAlong = static_cast<float>(bForward ? BestT : 1.0 - BestT) * Length;
        Stroller.RouteOffset = RouteBaseOffset * NextRandom(Stroller, 0.7f, 1.3f);
        Stroller.bOnRoute = true;
    }
    const float LegMin = CVarStrollLaneLegMin.GetValueOnGameThread();
    Stroller.LegLeft = NextRandom(Stroller, LegMin, FMath::Max(LegMin, CVarStrollLaneLegMax.GetValueOnGameThread()));
    Stroller.LegLength = Stroller.LegLeft;
    if (CVarStrollDestinations.GetValueOnGameThread() != 0 && !Destinations.IsEmpty())
    {
        const int32 Start = FMath::RandHelper(Destinations.Num());
        for (int32 Offset = 0; Offset < Destinations.Num(); ++Offset)
        {
            const int32 Index = (Start + Offset) % Destinations.Num();
            const float Distance = FVector::Dist2D(Here, Destinations[Index].Location);
            if (Index == Stroller.DestinationIndex || Distance < 1200.0f || Distance > 7500.0f) continue;
            Stroller.DestinationIndex = Index;
            break;
        }
    }
    Stroller.Goal = RoutePoint(Stroller);
    ++Stroller.Picks;
    return true;
}

bool UReflectionsCrowdStrollSubsystem::AdvanceRoute(FStroller& Stroller, float Step)
{
    if (!RouteNodes.IsValidIndex(Stroller.RouteFrom) || !RouteNodes.IsValidIndex(Stroller.RouteTo)) return false;
    Stroller.RouteAlong += Step;
    for (int32 Guard = 0; Guard < 8; ++Guard)
    {
        const float Length = FVector::Dist2D(RouteNodes[Stroller.RouteFrom], RouteNodes[Stroller.RouteTo]);
        if (Stroller.RouteAlong < Length) return true;
        Stroller.RouteAlong -= Length;
        // At a node: carry on, mostly straight; at a dead end, turn round.
        const TArray<int32>& Links = RouteLinks[Stroller.RouteTo];
        const FVector In = (RouteNodes[Stroller.RouteTo] - RouteNodes[Stroller.RouteFrom]).GetSafeNormal2D();
        int32 Pick = INDEX_NONE;
        double BestScore = -3.0;
        const bool bWander = NextRandom(Stroller, 0.0f, 1.0f) < 0.3f;
        const FVector Towards = Destinations.IsValidIndex(Stroller.DestinationIndex)
            ? (Destinations[Stroller.DestinationIndex].Location - RouteNodes[Stroller.RouteTo]).GetSafeNormal2D() : FVector::ZeroVector;
        for (const int32 Candidate : Links)
        {
            if (Candidate == Stroller.RouteFrom && Links.Num() > 1) continue;
            const FVector Out = (RouteNodes[Candidate] - RouteNodes[Stroller.RouteTo]).GetSafeNormal2D();
            // Straight on, a turn now and then (bWander), and a pull towards the trip's street activity.
            const double Score = (bWander ? NextRandom(Stroller, -1.0f, 1.0f) : FVector::DotProduct(In, Out))
                + 0.6 * FVector::DotProduct(Towards, Out);
            if (Score > BestScore) { BestScore = Score; Pick = Candidate; }
        }
        if (Pick == INDEX_NONE) return false;
        Stroller.RouteFrom = Stroller.RouteTo;
        Stroller.RouteTo = Pick;
    }
    return true;
}

bool UReflectionsCrowdStrollSubsystem::FindRouteSpawn(const FVector& Near, float MinDistance, float MaxDistance,
    TFunctionRef<bool(const FVector&)> Accept, FVector& OutLocation, float& OutYaw)
{
    if (!bDestinationsLoaded) LoadDestinations();
    if (RouteNodes.Num() < 2) return false;
    // Edges with a point in the ring round Near; then random points on them.
    TArray<TPair<int32, int32>, TInlineAllocator<256>> Candidates;
    for (int32 A = 0; A < RouteNodes.Num(); ++A)
    {
        const float DistanceA = FVector::Dist2D(RouteNodes[A], Near);
        for (const int32 B : RouteLinks[A])
        {
            if (B < A) continue;
            const float DistanceB = FVector::Dist2D(RouteNodes[B], Near);
            if (FMath::Max(DistanceA, DistanceB) >= MinDistance && FMath::Min(DistanceA, DistanceB) <= MaxDistance) Candidates.Add({A, B});
        }
    }
    for (int32 Try = 0; Try < 24 && Candidates.Num() > 0; ++Try)
    {
        const TPair<int32, int32>& Edge = Candidates[FMath::RandHelper(Candidates.Num())];
        const FVector P = FMath::Lerp(RouteNodes[Edge.Key], RouteNodes[Edge.Value], static_cast<double>(FMath::FRand()));
        const float Distance = FVector::Dist2D(P, Near);
        if (Distance < MinDistance || Distance > MaxDistance || !Accept(P)) continue;
        const FVector Along = (RouteNodes[Edge.Value] - RouteNodes[Edge.Key]).GetSafeNormal2D() * (FMath::RandBool() ? 1.0f : -1.0f);
        const FVector Left(Along.Y, -Along.X, 0.0);
        OutLocation = P + Left * RouteBaseOffset;
        OutYaw = Along.Rotation().Yaw;
        return true;
    }
    return false;
}

UReflectionsCrowdStrollSubsystem::FStroller* UReflectionsCrowdStrollSubsystem::FindCompanion(const FStroller& Stroller)
{
    const AActor* Companion = Stroller.Companion.Get();
    return Companion ? Strollers.FindByPredicate([Companion](const FStroller& Other) { return Other.Npc.Get() == Companion; }) : nullptr;
}

void UReflectionsCrowdStrollSubsystem::BreakPair(FStroller& Stroller)
{
    if (FStroller* Other = FindCompanion(Stroller))
    {
        if (AActor* Actor = Other->Npc.Get()) Actor->Tags.Remove(TEXT("Crowd_Pair"));
        Other->Companion.Reset();
        Other->PairCooldown = 15.0f;
        if (!Other->bPairLeader && Other->Phase != EPhase::Released)
        {
            Other->Phase = EPhase::Idle;
            Other->PhaseTime = 0.0f;
            Other->IdleFor = 0.4f;
        }
    }
    Stroller.Companion.Reset();
    if (AActor* Actor = Stroller.Npc.Get()) Actor->Tags.Remove(TEXT("Crowd_Pair"));
    if (!Stroller.bPairLeader && Stroller.Phase == EPhase::Walking)
    {
        Stroller.Phase = EPhase::Idle;
        Stroller.PhaseTime = 0.0f;
        Stroller.IdleFor = 0.4f;
    }
    Stroller.PairCooldown = 15.0f;
}

void UReflectionsCrowdStrollSubsystem::RefreshPairs()
{
    const float Share = FMath::Clamp(CVarStrollPairs.GetValueOnGameThread(), 0.0f, 1.0f);
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    const auto Available = [](const FStroller& Walker)
    {
        const AActor* Actor = Walker.Npc.Get();
        const UReflectionsNpcReactionComponent* Brain = Walker.Brain.Get();
        return Actor && Brain && Walker.Driver.IsValid() && Walker.bLaneWalker && Walker.Phase == EPhase::Walking
            && !Brain->IsIncapacitated() && Brain->Reaction == EReflectionsNpcReaction::Calm
            && !Actor->ActorHasTag(NoStrollTag) && !Actor->ActorHasTag(TEXT("Crowd_Carry"));
    };
    int32 RingWalkers = 0;
    int32 PairedWalkers = 0;
    for (FStroller& Walker : Strollers)
    {
        if (Walker.bLaneWalker) ++RingWalkers;
        if (!Walker.Companion.IsValid()) continue;
        FStroller* Other = FindCompanion(Walker);
        if (Share <= 0.0f || !Other || !Available(Walker) || !Available(*Other)) BreakPair(Walker);
        else ++PairedWalkers;
    }
    const int32 Target = FMath::FloorToInt(RingWalkers * Share) / 2 * 2;
    for (FStroller& Leader : Strollers)
    {
        if (PairedWalkers + 2 > Target) break;
        if (!Available(Leader) || Leader.Companion.IsValid() || Leader.PairCooldown > 0.0f) continue;
        ACharacter* LeaderDriver = Leader.Driver.Get();
        const FVector Here = LeaderDriver->GetActorLocation();
        FStroller* Best = nullptr;
        float BestDistance = 350.0f;
        for (FStroller& Candidate : Strollers)
        {
            if (&Candidate == &Leader || !Available(Candidate) || Candidate.Companion.IsValid() || Candidate.PairCooldown > 0.0f) continue;
            ACharacter* Driver = Candidate.Driver.Get();
            const FVector There = Driver->GetActorLocation();
            const float Distance = FVector::Dist2D(Here, There);
            if (Distance >= BestDistance || FMath::Abs(Here.Z - There.Z) > 60.0f) continue;
            if (FVector::DotProduct(Leader.Heading, Candidate.Heading) < 0.4f) continue;
            if (Npcs && Npcs->GetSideAt(Here) != Npcs->GetSideAt(There)) continue;
            FVector Checked;
            if (!CheckStreetGoal(Candidate, *Driver, Here, Checked)) continue;
            Best = &Candidate;
            BestDistance = Distance;
        }
        if (!Best) continue;
        Leader.Companion = Best->Npc;
        Best->Companion = Leader.Npc;
        Leader.Npc->Tags.AddUnique(TEXT("Crowd_Pair"));
        Best->Npc->Tags.AddUnique(TEXT("Crowd_Pair"));
        Leader.bPairLeader = true;
        Best->bPairLeader = false;
        Leader.PairSeconds = NextRandom(Leader, 35.0f, 75.0f);
        const FVector Right(-Leader.Heading.Y, Leader.Heading.X, 0.0);
        Best->PairSide = FVector::DotProduct(Best->Driver->GetActorLocation() - Here, Right) < 0.0 ? -1.0f : 1.0f;
        PairedWalkers += 2;
    }
}

bool UReflectionsCrowdStrollSubsystem::TickCompanion(FStroller& Stroller, ACharacter& Driver, float DeltaTime)
{
    if (!Stroller.Companion.IsValid()) return false;
    FStroller* Other = FindCompanion(Stroller);
    const AActor* Actor = Other ? Other->Npc.Get() : nullptr;
    const UReflectionsNpcReactionComponent* Brain = Other ? Other->Brain.Get() : nullptr;
    if (!Other || !Actor || !Brain || !Other->Driver.IsValid() || Actor->ActorHasTag(NoStrollTag)
        || Brain->IsIncapacitated() || Brain->Reaction != EReflectionsNpcReaction::Calm
        || Other->Phase == EPhase::Released || FVector::Dist2D(Driver.GetActorLocation(), Other->Driver->GetActorLocation()) > 650.0f)
    {
        BreakPair(Stroller);
        return false;
    }
    if (Stroller.bPairLeader)
    {
        Stroller.PairSeconds -= DeltaTime;
        if (Stroller.PairSeconds <= 0.0f) BreakPair(Stroller);
        return false;
    }
    const ACharacter* Leader = Other->Driver.Get();
    FVector Heading = Leader->GetVelocity().GetSafeNormal2D();
    if (Heading.IsNearlyZero()) Heading = Other->Heading;
    const FVector Right(-Heading.Y, Heading.X, 0.0);
    Stroller.Goal = Leader->GetActorLocation() + Right * (Stroller.PairSide * 135.0f) - Heading * 35.0f;
    const float Distance = FVector::Dist2D(Driver.GetActorLocation(), Stroller.Goal);
    const float Along = FVector::DotProduct(Stroller.Goal - Driver.GetActorLocation(), Heading);
    const float Speed = Other->Speed * FMath::Clamp(1.0f + Along / 400.0f, 0.65f, 1.2f);
    Steer(Stroller, Driver, Stroller.Goal, Distance < 35.0f ? 0.0f : Speed, DeltaTime);
    Stroller.StuckTime = Distance > 150.0f && Driver.GetVelocity().Size2D() < 25.0f ? Stroller.StuckTime + DeltaTime : 0.0f;
    if (Stroller.StuckTime > 2.5f)
    {
        BreakPair(Stroller);
        return false;
    }
    return true;
}

void UReflectionsCrowdStrollSubsystem::Steer(FStroller& Stroller, ACharacter& Driver, const FVector& Goal,
    float WantedSpeed, float DeltaTime)
{
    UCharacterMovementComponent* Movement = Driver.GetCharacterMovement();
    const UCapsuleComponent* Capsule = Driver.GetCapsuleComponent();
    if (!Movement || !Capsule) return;
    Movement->MinAnalogWalkSpeed = 0.0f;
    const FVector Here = Driver.GetActorLocation();
    const FVector Forward = (Goal - Here).GetSafeNormal2D();
    if (Forward.IsNearlyZero()) return;
    const FVector Right(-Forward.Y, Forward.X, 0.0);
    FVector Avoidance = FVector::ZeroVector;
    FVector Separation = FVector::ZeroVector;
    float SpeedScale = 1.0f;
    if (CVarStrollAvoidance.GetValueOnGameThread() != 0)
    {
        const FVector Velocity = Driver.GetVelocity();
        for (const FPedestrianObstacle& Obstacle : Obstacles)
        {
            const ACharacter* Other = Obstacle.Driver.Get();
            if (!Other || Other == &Driver || !Obstacle.Actor.IsValid()) continue;
            const FVector Offset = Other->GetActorLocation() - Here;
            if (FMath::Abs(Offset.Z) > 100.0f || Offset.SizeSquared2D() > FMath::Square(450.0f)) continue;
            const float Along = FVector::DotProduct(Offset, Forward);
            const FVector RelativeVelocity = FVector(Other->GetVelocity().X - Velocity.X, Other->GetVelocity().Y - Velocity.Y, 0.0);
            const float Time = RelativeVelocity.SizeSquared2D() > 1.0
                ? FMath::Clamp(static_cast<float>(-FVector::DotProduct(Offset, RelativeVelocity) / RelativeVelocity.SizeSquared2D()), 0.0f, 1.5f) : 0.0f;
            const FVector Closest = FVector(Offset.X, Offset.Y, 0.0) + RelativeVelocity * Time;
            const float Clearance = Capsule->GetScaledCapsuleRadius() + Obstacle.Radius
                + FMath::Clamp(CVarStrollPersonalSpace.GetValueOnGameThread(), 0.0f, 100.0f);
            const float Distance = Offset.Size2D();
            if (Distance < Clearance)
            {
                FVector Away = -FVector(Offset.X, Offset.Y, 0.0).GetSafeNormal2D();
                if (Away.IsNearlyZero()) Away = Right * (Driver.GetUniqueID() < Other->GetUniqueID() ? -1.0f : 1.0f);
                Separation += Away * (1.0f - Distance / Clearance);
            }
            if (Along < -Clearance || (Closest.Size2D() > Clearance * 1.35f && Distance > Clearance * 1.2f)) continue;
            // Both directions keep to their own left during a head-on pass, avoiding side-to-side indecision.
            const bool bHeadOn = FVector::DotProduct(Other->GetVelocity().GetSafeNormal2D(), Forward) < -0.25;
            const float Side = bHeadOn ? -1.0f : (FVector::DotProduct(Offset, Right) > 0.0 ? -1.0f : 1.0f);
            const float Urgency = FMath::Clamp(1.0f - static_cast<float>(Closest.Size2D()) / (Clearance * 1.35f), 0.0f, 1.0f);
            // A companion normally occupies its reserved side position; only separate it on actual overlap.
            const bool bCompanion = Obstacle.Actor == Stroller.Companion;
            if (!bCompanion || Distance < Clearance)
                Avoidance += Right * Side * (0.35f + Urgency) * (bCompanion ? 0.35f : 1.0f);
            if (!bCompanion && Along > 0.0f && Distance < Clearance * 2.0f)
                SpeedScale = FMath::Min(SpeedScale, FMath::Clamp((Distance - Clearance * 0.7f) / Clearance, 0.2f, 1.0f));
        }
    }
    Stroller.Avoidance = FMath::VInterpTo(Stroller.Avoidance, Avoidance.GetClampedToMaxSize(1.25), DeltaTime, 5.0f);
    FVector Direction = (Forward + Stroller.Avoidance + Separation.GetClampedToMaxSize(1.0) * 3.0f).GetSafeNormal2D();
    Stroller.ProbeIn -= DeltaTime;
    if (Stroller.ProbeIn <= 0.0f)
    {
        Stroller.ProbeIn = 0.18f;
        Stroller.SafeHeading = FVector::ZeroVector;
        const float ProbeDistance = FMath::Min(static_cast<float>(FVector::Dist2D(Here, Goal)), 110.0f);
        // Check the steered path too: avoiding a person must not send someone into a wall or off an edge.
        const float Turns[] = {0.0f, -35.0f, 35.0f, -70.0f, 70.0f};
        for (const float Turn : Turns)
        {
            const FVector Candidate = Direction.RotateAngleAxis(Turn, FVector::UpVector);
            FVector Checked;
            if (!CheckStreetGoal(Stroller, Driver, Here + Candidate * ProbeDistance, Checked)) continue;
            Stroller.SafeHeading = Candidate;
            break;
        }
    }
    if (Stroller.SafeHeading.IsNearlyZero()) WantedSpeed = 0.0f;
    else Direction = Stroller.SafeHeading;
    Stroller.Heading = FMath::VInterpTo(Stroller.Heading, Direction, DeltaTime, 7.0f).GetSafeNormal2D();
    Stroller.CurrentSpeed = FMath::FInterpTo(Stroller.CurrentSpeed, WantedSpeed * SpeedScale, DeltaTime, 4.0f);
    if (Stroller.CurrentSpeed > 3.0f && !Stroller.SafeHeading.IsNearlyZero())
        Driver.AddMovementInput(Stroller.Heading, FMath::Clamp(Stroller.CurrentSpeed / FMath::Max(1.0f, Movement->GetMaxSpeed()), 0.0f, 1.0f), true);
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
    int32 GoalsPlanned = 0;
    for (FStroller& Stroller : Strollers)
    {
        UReflectionsNpcReactionComponent* Brain = Stroller.Brain.Get();
        ACharacter* Driver = Brain ? Brain->GetLocomotionDriver() : nullptr;
        Stroller.PairCooldown = FMath::Max(0.0f, Stroller.PairCooldown - DeltaTime);
        if (!Brain || !Driver || !Stroller.Npc.IsValid() || Stroller.Npc->ActorHasTag(NoStrollTag)
            || Brain->IsIncapacitated() || Brain->Reaction != EReflectionsNpcReaction::Calm)
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
        if (TickCompanion(Stroller, *Driver, DeltaTime)) continue;

        if (Stroller.Phase == EPhase::Idle)
        {
            if (Stroller.PhaseTime < Stroller.IdleFor || GoalsPlanned >= 2) continue;
            ++GoalsPlanned;
            // Follow the map's street routes or sidewalk lanes when present, otherwise use checked street
            // destinations and continuous trips.
            const bool bRouteLeg = Stroller.bLaneWalker && StartRouteLeg(Stroller, *Driver);
            if (!bRouteLeg) Stroller.bOnRoute = false;
            const bool bLaneLeg = bRouteLeg || (Stroller.bLaneWalker && StartLaneLeg(Stroller, *Driver));
            if (!bLaneLeg || bRouteLeg) Stroller.bOnLane = false;
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
        const bool bRouteLeg = Stroller.bLaneWalker && Stroller.bOnRoute;
        const bool bLaneLeg = bRouteLeg || (Stroller.bLaneWalker && Stroller.bOnLane);
        if (bRouteLeg)
        {
            // Keep the route point a little ahead of the walker until the leg's distance is used up.
            for (int32 Guard = 0; Guard < 8 && Stroller.LegLeft > 0.0f && FVector::Dist2D(Here, RoutePoint(Stroller)) < CarrotDistance; ++Guard)
            {
                const float Step = FMath::Min(60.0f, Stroller.LegLeft);
                if (!AdvanceRoute(Stroller, Step))
                {
                    Stroller.LegLeft = 0.0f;
                    break;
                }
                Stroller.LegLeft -= Step;
            }
            Stroller.Goal = RoutePoint(Stroller);
        }
        else if (bLaneLeg)
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
        const float LegLimit = bLaneLeg ? Stroller.LegLength / FMath::Max(50.0f, Stroller.Speed) * 2.0f + 15.0f
            : (Stroller.bLaneWalker ? 110.0f : FVector::Dist2D(Stroller.Home, Stroller.Goal) / FMath::Max(50.0f, Stroller.Speed) * 2.0f + 12.0f);
        const bool bArrived = Distance < ArriveRadius && (!bLaneLeg || Stroller.LegLeft <= 0.0f);
        if (bArrived || Stroller.PhaseTime > LegLimit)
        {
            // Arrived: a short stop most of the time, now and then a longer one.
            Stroller.Phase = EPhase::Idle;
            Stroller.PhaseTime = 0.0f;
            Stroller.IdleFor = Stroller.bLaneWalker ? NextRandom(Stroller, 0.4f, 2.0f)
                : (NextRandom(Stroller, 0.0f, 1.0f) < 0.15f ? NextRandom(Stroller, 7.0f, 12.0f) : NextRandom(Stroller, 1.5f, 5.0f));
            Stroller.CurrentSpeed = 0.0f;
            continue;
        }
        if (Distance < 1.0f) continue;
        // Ease in over the last metre so it does not overshoot and turn back (not mid-way along a lane).
        const float Slow = bLaneLeg && Stroller.LegLeft > 0.0f ? 1.0f
            : FMath::GetMappedRangeValueClamped(FVector2f(40.0f, 140.0f), FVector2f(0.55f, 1.0f), Distance);
        float Speed = Stroller.Speed * Slow;
        if (Stroller.bPairLeader)
        {
            const FStroller* Companion = FindCompanion(Stroller);
            if (Companion && Companion->Driver.IsValid()
                && FVector::Dist2D(Here, Companion->Driver->GetActorLocation()) > 220.0f) Speed *= 0.7f;
        }
        Steer(Stroller, *Driver, Stroller.Goal, Speed, DeltaTime);

        // Walked into something the goal sweep missed (another walker, the player): pick again shortly.
        if (Stroller.PhaseTime > 1.0f && Driver->GetVelocity().Size2D() < 25.0f) Stroller.StuckTime += DeltaTime;
        else Stroller.StuckTime = 0.0f;
        if (Stroller.StuckTime > 2.5f)
        {
            BreakPair(Stroller);
            Stroller.Phase = EPhase::Idle;
            Stroller.PhaseTime = 0.0f;
            Stroller.IdleFor = 0.6f;
            Stroller.bOnLane = false;
            Stroller.bOnRoute = false;
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
    int32 Pairs = 0;
    for (const FStroller& Stroller : Strollers)
        if (Stroller.Companion.IsValid() && Stroller.bPairLeader) ++Pairs;
    int32 OnRoute = 0;
    for (const FStroller& Stroller : Strollers)
        if (Stroller.bOnRoute && Stroller.Phase != EPhase::Released) ++OnRoute;
    FString Out = FString::Printf(TEXT("Crowd stroll: %d strolling of %d candidates, enabled %d, %d pairs, %d street destinations, %d route nodes (%d walkers on a route)"),
        GetStrollingCount(), Strollers.Num(), CVarStrollEnable.GetValueOnGameThread(), Pairs, Destinations.Num(), RouteNodes.Num(), OnRoute);
    for (const FStroller& Stroller : Strollers)
    {
        const ACharacter* Driver = Stroller.Driver.Get();
        Out += FString::Printf(TEXT("\n  %s: %s%s, %.0f cm/s now (target %.0f), %.0f cm to goal, %d goals, destination %s, companion %s%s"),
            *GetNameSafe(Stroller.Npc.Get()), PhaseName(static_cast<int32>(Stroller.Phase)),
            Stroller.bLaneWalker ? (Stroller.bOnRoute ? TEXT(" on route") : Stroller.bOnLane ? TEXT(" on lane") : TEXT(" (lane walker, no lane)")) : TEXT(""),
            Driver ? Driver->GetVelocity().Size2D() : 0.0f, Stroller.Speed,
            Driver ? FVector::Dist2D(Driver->GetActorLocation(), Stroller.Goal) : 0.0f, Stroller.Picks,
            Destinations.IsValidIndex(Stroller.DestinationIndex) ? *Destinations[Stroller.DestinationIndex].Name.ToString() : TEXT("street"),
            *GetNameSafe(Stroller.Companion.Get()), Stroller.Companion.IsValid() ? (Stroller.bPairLeader ? TEXT(" (leader)") : TEXT(" (alongside)")) : TEXT(""));
    }
    return Out;
}
