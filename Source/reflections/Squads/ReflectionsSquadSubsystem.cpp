#include "Squads/ReflectionsSquadSubsystem.h"

#include "Squads/ReflectionsSquad.h"
#include "Squads/ReflectionsSquadRoute.h"

#include "EngineUtils.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerStart.h"
#include "NavigationSystem.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"
#include "TimerManager.h"

namespace
{
    TAutoConsoleVariable<int32> CVarSquadAutoTest(
        TEXT("Squads.AutoTest"), 0,
        TEXT("1 spawns two test squads when a start-patrol map (Squads.StartPatrolMaps) begins play (PIE testing only)."),
        ECVF_Default);

    bool GroundPoint(UWorld* World, const FVector& Center, FVector Candidate, FVector& Out)
    {
        // Pull a route point toward the centre until it lands on walkable ground.
        for (int32 Attempt = 0; Attempt < 6; ++Attempt)
        {
            FHitResult Hit;
            FCollisionQueryParams Params(SCENE_QUERY_STAT(SquadTestGround), false);
            if (World->LineTraceSingleByObjectType(Hit, Candidate + FVector(0, 0, 400), Candidate - FVector(0, 0, 1500),
                    FCollisionObjectQueryParams(ECC_WorldStatic), Params) && Hit.ImpactNormal.Z > 0.7f)
            {
                Out = Hit.ImpactPoint;
                return true;
            }
            Candidate = FMath::Lerp(Candidate, Center, 0.3f);
        }
        return false;
    }

    TAutoConsoleVariable<int32> CVarSquadStartPatrol(
        TEXT("Squads.StartPatrol"), 1,
        TEXT("1: on the maps in Squads.StartPatrolMaps, raise one squad patrolling in sight of the player start when no ")
        TEXT("squad already patrols within 40 m of it. 0 = off (set before PIE for tests that need an empty start)."),
        ECVF_Default);

    TAutoConsoleVariable<FString> CVarSquadStartPatrolMaps(
        TEXT("Squads.StartPatrolMaps"), TEXT("GrayLondon"),
        TEXT("Comma-separated map-name fragments that get the start patrol (and Squads.AutoTest). Default: Gray London."),
        ECVF_Default);

    TAutoConsoleVariable<int32> CVarSquadStartPatrolFaction(
        TEXT("Squads.StartPatrolFaction"), 0,
        TEXT("Faction of the start patrol where the map has no side levels: 0 Frost raiders (hostile when provoked), 1 Gilt guards (allied)."),
        ECVF_Default);

    bool IsStartPatrolMap(const FString& Map)
    {
        TArray<FString> Names;
        CVarSquadStartPatrolMaps.GetValueOnGameThread().ParseIntoArray(Names, TEXT(","), true);
        for (FString& Name : Names)
        {
            Name.TrimStartAndEndInline();
            if (!Name.IsEmpty() && Map.Contains(Name))
            {
                return true;
            }
        }
        return false;
    }

    /** Ground under a point on the same floor as the start (no pulling): walkable and within 1.5 m of its height. */
    bool GroundAt(UWorld* World, const FVector& Point, float FloorZ, FVector& Out)
    {
        FHitResult Hit;
        FCollisionQueryParams Params(SCENE_QUERY_STAT(SquadStartGround), false);
        if (World->LineTraceSingleByObjectType(Hit, FVector(Point.X, Point.Y, FloorZ + 300.0), FVector(Point.X, Point.Y, FloorZ - 300.0),
                FCollisionObjectQueryParams(ECC_WorldStatic), Params) && Hit.ImpactNormal.Z > 0.7f && FMath::Abs(Hit.ImpactPoint.Z - FloorZ) < 150.0)
        {
            Out = Hit.ImpactPoint;
            return true;
        }
        return false;
    }

    bool ClearLine(UWorld* World, const FVector& From, const FVector& To)
    {
        FHitResult Hit;
        FCollisionQueryParams Params(SCENE_QUERY_STAT(SquadStartSight), false);
        return !World->LineTraceSingleByObjectType(Hit, From, To, FCollisionObjectQueryParams(ECC_WorldStatic), Params);
    }

    /**
     * A patrol route near Floor (the ground under the player) that fits a city street as well as open ground: in each
     * direction (ahead, right, left, behind) first a 14 x 8 m loop 8-16 m away (or 3/4 of that), else a straight
     * out-and-back line from 6 m out (20, 14 or 10 m long). Every point on walkable ground at the same level, in view
     * from the start, on the navmesh when there is one, and no wall across any leg. Each direction gives at most one
     * route; Skip picks the next direction's (so several test squads never overlap).
     */
    bool FitRouteNear(UWorld* World, const FVector& Floor, const FVector& Ahead, int32 Skip, TArray<FVector>& OutPoints, bool& bOutLoop)
    {
        const FVector Eye = Floor + FVector(0, 0, 160);
        const FVector Side(-Ahead.Y, Ahead.X, 0.0);
        UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World);
        const bool bNav = Nav && Nav->GetDefaultNavDataInstance(FNavigationSystem::DontCreate) != nullptr;
        const auto Fits = [&](const TArray<FVector>& Wanted, bool bLoop, TArray<FVector>& Points)
        {
            Points.Reset();
            for (const FVector& Want : Wanted)
            {
                FVector Ground;
                FNavLocation OnNav;
                if (!GroundAt(World, Want, Floor.Z, Ground) || !ClearLine(World, Eye, Ground + FVector(0, 0, 120))
                    || (bNav && !Nav->ProjectPointToNavigation(Ground, OnNav, FVector(100.0, 100.0, 250.0))))
                {
                    return false;
                }
                Points.Add(Ground);
            }
            const int32 Legs = bLoop ? Points.Num() : Points.Num() - 1;
            for (int32 Index = 0; Index < Legs; ++Index)
            {
                const FVector Lift(0, 0, 90);
                if (!ClearLine(World, Points[Index] + Lift, Points[(Index + 1) % Points.Num()] + Lift))
                {
                    return false;
                }
            }
            return true;
        };
        int32 Found = 0;
        for (const FVector& Dir : { Ahead, Side, -Side, -Ahead })
        {
            const FVector Across(-Dir.Y, Dir.X, 0.0);
            TArray<FVector> Points;
            bool bLoop = false;
            bool bFound = false;
            for (const double Scale : { 1.0, 0.75 })
            {
                const FVector Mid = Floor + Dir * (1200.0 * Scale);
                const TArray<FVector> Corners = { Mid + Dir * 400.0 * Scale - Across * 700.0 * Scale, Mid + Dir * 400.0 * Scale + Across * 700.0 * Scale,
                    Mid - Dir * 400.0 * Scale + Across * 700.0 * Scale, Mid - Dir * 400.0 * Scale - Across * 700.0 * Scale };
                if (Fits(Corners, true, Points))
                {
                    bLoop = true;
                    bFound = true;
                    break;
                }
            }
            for (const double Length : { 2000.0, 1400.0, 1000.0 })
            {
                if (bFound)
                {
                    break;
                }
                const TArray<FVector> Line = { Floor + Dir * 600.0, Floor + Dir * (600.0 + Length) };
                if (Fits(Line, false, Points))
                {
                    bLoop = false;
                    bFound = true;
                }
            }
            if (bFound && Found++ == Skip)
            {
                OutPoints = Points;
                bOutLoop = bLoop;
                return true;
            }
        }
        return false;
    }

    /** Ground under the player and the way it faces, for fitting routes. */
    bool PlayerFloor(UWorld* World, FVector& OutFloor, FVector& OutAhead)
    {
        const APawn* Player = UGameplayStatics::GetPlayerPawn(World, 0);
        FVector Start;
        FRotator Facing;
        if (Player)
        {
            Start = Player->GetActorLocation();
            Facing = Player->GetControlRotation();
        }
        else
        {
            TActorIterator<APlayerStart> It(World);
            if (!It)
            {
                return false;
            }
            Start = It->GetActorLocation();
            Facing = It->GetActorRotation();
        }
        FHitResult Hit;
        FCollisionQueryParams Params(SCENE_QUERY_STAT(SquadPlayerFloor), false);
        if (!World->LineTraceSingleByObjectType(Hit, Start, Start - FVector(0, 0, 500), FCollisionObjectQueryParams(ECC_WorldStatic), Params))
        {
            return false;
        }
        OutFloor = Hit.ImpactPoint;
        OutAhead = FRotator(0.0, Facing.Yaw, 0.0).Vector();
        return true;
    }

    AReflectionsSquad* SpawnOne(UWorld* World, const FVector& Center, const TArray<FVector>& Offsets, bool bLoop,
        EReflectionsSquadFormation Formation, int32 Size, int32 Casters, const TArray<EHeroSpell>& Spells, float Halt,
        TArray<TWeakObjectPtr<AActor>>& Spawned, float SightRadius = -1.0f, float AlertRadius = -1.0f, int32 FactionOverride = -1)
    {
        TArray<FVector> Points;
        for (const FVector& Offset : Offsets)
        {
            FVector Ground;
            if (GroundPoint(World, Center, Center + Offset, Ground))
            {
                Points.Add(Ground);
            }
        }
        if (Points.Num() < 2)
        {
            UE_LOG(LogTemp, Warning, TEXT("Squads: no ground for a test route around %s"), *Center.ToString());
            return nullptr;
        }
        FActorSpawnParameters Params;
        Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        AReflectionsSquadRoute* Route = World->SpawnActor<AReflectionsSquadRoute>(Points[0], FRotator::ZeroRotator, Params);
        if (!Route)
        {
            return nullptr;
        }
        Route->SetPoints(Points, bLoop);
        Route->HaltSeconds = Halt;
        Spawned.Add(Route);

        const FTransform Transform(FRotator::ZeroRotator, Points[0]);
        AReflectionsSquad* Squad = World->SpawnActorDeferred<AReflectionsSquad>(AReflectionsSquad::StaticClass(), Transform,
            nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
        if (!Squad)
        {
            return nullptr;
        }
        Squad->Route = Route;
        Squad->Formation = Formation;
        Squad->SquadSize = Size;
        Squad->CasterCount = Casters;
        Squad->CasterSpells = Spells;
        if (SightRadius >= 0.0f)
        {
            Squad->SightRadius = SightRadius;
        }
        if (AlertRadius >= 0.0f)
        {
            Squad->AlertRadius = AlertRadius;
        }
        if (FactionOverride >= 0)
        {
            Squad->Faction = static_cast<EReflectionsSquadFaction>(FactionOverride);
            Squad->bFactionFromSide = false;
        }
        Squad->FinishSpawning(Transform);
        Spawned.Add(Squad);
        return Squad;
    }

#if !UE_BUILD_SHIPPING
    UReflectionsSquadSubsystem* SquadsFor(UWorld* World)
    {
        return World ? World->GetSubsystem<UReflectionsSquadSubsystem>() : nullptr;
    }

    template <typename TFunc>
    void ForEachSquad(UWorld* World, TFunc&& Func)
    {
        if (!World)
        {
            return;
        }
        for (TActorIterator<AReflectionsSquad> It(World); It; ++It)
        {
            Func(**It);
        }
    }

    FAutoConsoleCommandWithWorldAndArgs SpawnTestCommand(TEXT("Squads.SpawnTest"),
        TEXT("Spawn test enemy squads around the player: Squads.SpawnTest [count=2]"),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsSquadSubsystem* Squads = SquadsFor(World))
            {
                Squads->SpawnTestSquads(Args.Num() > 0 ? FCString::Atoi(*Args[0]) : 2);
            }
        }));

    FAutoConsoleCommandWithWorldAndArgs SpawnGiltCommand(TEXT("Squads.SpawnGilt"),
        TEXT("Spawn an allied Gilt test squad (swords and shields) pacing beside the player."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
        {
            if (UReflectionsSquadSubsystem* Squads = SquadsFor(World))
            {
                Squads->SpawnGiltTestSquad();
            }
        }));

    FAutoConsoleCommandWithWorldAndArgs ClearCommand(TEXT("Squads.Clear"), TEXT("Remove test squads."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
        {
            if (UReflectionsSquadSubsystem* Squads = SquadsFor(World))
            {
                Squads->ClearTestSquads();
            }
        }));

    FAutoConsoleCommandWithWorldAndArgs EngageCommand(TEXT("Squads.Engage"),
        TEXT("Every squad breaks formation and fights the player: Squads.Engage [squad index]"),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            int32 Index = 0;
            const int32 Only = Args.Num() > 0 ? FCString::Atoi(*Args[0]) : -1;
            ForEachSquad(World, [&](AReflectionsSquad& Squad)
            {
                if (Only < 0 || Only == Index)
                {
                    Squad.Engage(UGameplayStatics::GetPlayerPawn(World, 0));
                }
                ++Index;
            });
        }));

    FAutoConsoleCommandWithWorldAndArgs ReformCommand(TEXT("Squads.Reform"), TEXT("Every squad stands down and reforms."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
        {
            ForEachSquad(World, [](AReflectionsSquad& Squad) { Squad.Reform(); });
        }));

    FAutoConsoleCommandWithWorldAndArgs CastCommand(TEXT("Squads.Cast"), TEXT("The first ready caster of each squad casts now."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
        {
            ForEachSquad(World, [](AReflectionsSquad& Squad) { Squad.DebugForceCast(); });
        }));

    FAutoConsoleCommandWithWorldAndArgs KillCommand(TEXT("Squads.KillAll"), TEXT("Kill every soldier through the normal damage path."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
        {
            ForEachSquad(World, [](AReflectionsSquad& Squad) { Squad.DebugKillAll(); });
        }));

    FAutoConsoleCommandWithWorldAndArgs DumpCommand(TEXT("Squads.Dump"), TEXT("Log every squad's state and members."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
        {
            ForEachSquad(World, [](AReflectionsSquad& Squad)
            {
                UE_LOG(LogTemp, Display, TEXT("Squad %s %s alive %d anchor %s"), *Squad.GetName(),
                    *UEnum::GetValueAsString(Squad.State), Squad.GetAliveCount(), *Squad.GetAnchorLocation().ToString());
                for (const FReflectionsSquadMember& Member : Squad.Members)
                {
                    UE_LOG(LogTemp, Display, TEXT("  %s %s %s cast=%s released=%d"), *GetNameSafe(Member.Actor),
                        *UEnum::GetValueAsString(Member.Role), *UEnum::GetValueAsString(Member.State),
                        *UEnum::GetValueAsString(Member.CastPhase), Member.CastsReleased);
                }
            });
        }));
#endif
}

bool UReflectionsSquadSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UReflectionsSquadSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
    Super::OnWorldBeginPlay(InWorld);
    if (CVarSquadAutoTest.GetValueOnGameThread() > 0 && IsStartPatrolMap(InWorld.GetMapName()))
    {
        // Wait a moment for the player pawn to spawn.
        FTimerHandle Handle;
        InWorld.GetTimerManager().SetTimer(Handle, FTimerDelegate::CreateWeakLambda(this, [this]() { SpawnTestSquads(2); }), 0.5f, false);
    }
    const FString Map = InWorld.GetMapName();
    if (CVarSquadStartPatrol.GetValueOnGameThread() > 0 && IsStartPatrolMap(Map))
    {
        // After the placed squads in the streamed side levels have begun play, so they count as "already near".
        FTimerHandle Handle;
        InWorld.GetTimerManager().SetTimer(Handle, FTimerDelegate::CreateWeakLambda(this, [this]() { SpawnStartPatrol(); }), 1.5f, false);
    }
}

void UReflectionsSquadSubsystem::SpawnStartPatrol()
{
    UWorld* World = GetWorld();
    if (!World || StartPatrol.IsValid())
    {
        return;
    }
    FVector Start;
    FRotator Facing;
    if (const APawn* Player = UGameplayStatics::GetPlayerPawn(World, 0))
    {
        Start = Player->GetActorLocation();
        Facing = Player->GetControlRotation();
    }
    else
    {
        TActorIterator<APlayerStart> It(World);
        if (!It)
        {
            return;
        }
        Start = It->GetActorLocation();
        Facing = It->GetActorRotation();
    }
    // A squad that already patrols (or stands) within 40 m of the start is enough.
    constexpr double Near = 4000.0;
    for (TActorIterator<AReflectionsSquad> It(World); It; ++It)
    {
        const AReflectionsSquad& Squad = **It;
        if (Squad.GetAliveCount() > 0 && FVector::Dist2D(Squad.GetAnchorLocation(), Start) < Near)
        {
            return;
        }
        if (const AReflectionsSquadRoute* Route = Squad.Route)
        {
            const int32 Count = Route->GetNumPoints();
            for (int32 Index = 0; Index < Count; ++Index)
            {
                if (Index == Count - 1 && !Route->bLoop)
                {
                    break;
                }
                const FVector A = Route->GetPoint(Index);
                const FVector B = Route->GetPoint(Index + 1);
                const FVector Closest = FMath::ClosestPointOnSegment(FVector(Start.X, Start.Y, 0.0), FVector(A.X, A.Y, 0.0), FVector(B.X, B.Y, 0.0));
                if (FVector::Dist2D(Closest, Start) < Near)
                {
                    return;
                }
            }
        }
    }
    // A route near the start that fits the street (FitRouteNear), in plain view of the player start.
    FVector Floor;
    FVector Ahead;
    TArray<FVector> Points;
    bool bLoop = false;
    if (PlayerFloor(World, Floor, Ahead) && FitRouteNear(World, Floor, Ahead, 0, Points, bLoop))
    {
        TArray<FVector> Offsets;
        FVector Middle = FVector::ZeroVector;
        for (const FVector& Point : Points)
        {
            Offsets.Add(Point - Floor);
            Middle += Point / Points.Num();
        }
        // A showcase: it marches past in plain view and never attacks an idle player (no sight of the player).
        // Hitting a soldier, a spell near a Frost squad, or a crime near it starts the fight. An allied Gilt squad
        // still watches for the tarnished (its sight is for them only).
        AReflectionsSquad* Squad = SpawnOne(World, Floor, Offsets, bLoop, EReflectionsSquadFormation::Column, 5, 2,
            { EHeroSpell::Fire, EHeroSpell::IceShard }, bLoop ? 0.0f : 2.0f, TestActors, 0.0f, 0.0f,
            CVarSquadStartPatrolFaction.GetValueOnGameThread() > 0 ? static_cast<int32>(EReflectionsSquadFaction::Gilt) : -1);
        StartPatrol = Squad;
        UE_LOG(LogTemp, Log, TEXT("Squads: start patrol %s on %s, %s, %d m from the player start"), *GetNameSafe(Squad),
            *World->GetMapName(), bLoop ? TEXT("loop") : TEXT("out and back"), static_cast<int32>(FVector::Dist2D(Middle, Floor) / 100.0));
        return;
    }
    UE_LOG(LogTemp, Warning, TEXT("Squads: no clear ground for a start patrol near %s"), *Start.ToString());
}

void UReflectionsSquadSubsystem::SpawnTestSquads(int32 Count)
{
    UWorld* World = GetWorld();
    if (!World)
    {
        return;
    }
    // Routes fitted around the player (any map): one per direction, so the squads never overlap.
    FVector Floor;
    FVector Ahead;
    if (!PlayerFloor(World, Floor, Ahead))
    {
        return;
    }
    const int32 Taken = StartPatrol.IsValid() ? 1 : 0;
    for (int32 Index = 0; Index < Count; ++Index)
    {
        TArray<FVector> Points;
        bool bLoop = false;
        if (!FitRouteNear(World, Floor, Ahead, Index + Taken, Points, bLoop))
        {
            UE_LOG(LogTemp, Warning, TEXT("Squads: room for only %d test squads here"), Index);
            break;
        }
        TArray<FVector> Offsets;
        for (const FVector& Point : Points)
        {
            Offsets.Add(Point - Floor);
        }
        const TArray<EHeroSpell> Spells = Index == 0 ? TArray<EHeroSpell>{ EHeroSpell::Fire, EHeroSpell::IceShard }
            : Index == 1 ? TArray<EHeroSpell>{ EHeroSpell::ArcaneBolt, EHeroSpell::Fire } : TArray<EHeroSpell>{ EHeroSpell::IceShard, EHeroSpell::ArcaneBolt };
        SpawnOne(World, Floor, Offsets, bLoop, Index == 0 ? EReflectionsSquadFormation::Column : EReflectionsSquadFormation::ColumnOfTwos,
            5, 2, Spells, bLoop ? 0.0f : 2.0f, TestActors);
    }
}

void UReflectionsSquadSubsystem::SpawnGiltTestSquad()
{
    UWorld* World = GetWorld();
    if (!World)
    {
        return;
    }
    // Five Gilt guards (3 blades, 1 caster) on the next free route around the player.
    FVector Floor;
    FVector Ahead;
    TArray<FVector> Points;
    bool bLoop = false;
    int32 Squads = 0;
    for (TActorIterator<AReflectionsSquad> It(World); It; ++It)
    {
        ++Squads;
    }
    if (!PlayerFloor(World, Floor, Ahead) || !FitRouteNear(World, Floor, Ahead, FMath::Min(Squads, 3), Points, bLoop))
    {
        UE_LOG(LogTemp, Warning, TEXT("Squads: no room for a Gilt test squad here"));
        return;
    }
    TArray<FVector> Offsets;
    for (const FVector& Point : Points)
    {
        Offsets.Add(Point - Floor);
    }
    SpawnOne(World, Floor, Offsets, bLoop, EReflectionsSquadFormation::ColumnOfTwos, 5, 1, { EHeroSpell::IceShard },
        bLoop ? 0.0f : 2.0f, TestActors, -1.0f, -1.0f, static_cast<int32>(EReflectionsSquadFaction::Gilt));
}

void UReflectionsSquadSubsystem::ClearTestSquads()
{
    for (const TWeakObjectPtr<AActor>& Actor : TestActors)
    {
        if (Actor.IsValid())
        {
            Actor->Destroy();
        }
    }
    TestActors.Reset();
}

void UReflectionsSquadSubsystem::RaiseAlarm(AActor* Offender, FVector Location, float Radius)
{
    UWorld* World = GetWorld();
    if (!World || !IsValid(Offender))
    {
        return;
    }
    for (TActorIterator<AReflectionsSquad> It(World); It; ++It)
    {
        if (It->HasMemberWithin(Location, Radius))
        {
            It->Engage(Offender);
        }
    }
}

TArray<AReflectionsSquad*> UReflectionsSquadSubsystem::GetSquads() const
{
    TArray<AReflectionsSquad*> Result;
    if (UWorld* World = GetWorld())
    {
        for (TActorIterator<AReflectionsSquad> It(World); It; ++It)
        {
            Result.Add(*It);
        }
    }
    return Result;
}
