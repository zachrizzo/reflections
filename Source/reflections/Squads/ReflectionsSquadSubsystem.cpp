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
        TEXT("1 spawns two test squads when Lvl_HeroSampleCrowd begins play (PIE testing only; nothing is saved)."),
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
        TEXT("1: on Lvl_HeroSampleCrowd and Lvl_MockCity, raise one squad patrolling in sight of the player start when no ")
        TEXT("squad already patrols within 40 m of it. 0 = off (set before PIE for tests that need an empty start)."),
        ECVF_Default);

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
    if (CVarSquadAutoTest.GetValueOnGameThread() > 0 && InWorld.GetMapName().Contains(TEXT("Lvl_HeroSampleCrowd")))
    {
        // Wait a moment for the player pawn to spawn.
        FTimerHandle Handle;
        InWorld.GetTimerManager().SetTimer(Handle, FTimerDelegate::CreateWeakLambda(this, [this]() { SpawnTestSquads(2); }), 0.5f, false);
    }
    const FString Map = InWorld.GetMapName();
    if (CVarSquadStartPatrol.GetValueOnGameThread() > 0 && (Map.Contains(TEXT("Lvl_HeroSampleCrowd")) || Map.Contains(TEXT("Lvl_MockCity"))))
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
    // Ground under the start, then a 14 x 8 m loop 8-16 m away that the start can see and that has no wall in it:
    // ahead first, then right, left and behind, shrinking it if it doesn't fit.
    FVector Floor;
    {
        FHitResult Hit;
        FCollisionQueryParams Params(SCENE_QUERY_STAT(SquadStartFloor), false);
        if (!World->LineTraceSingleByObjectType(Hit, Start, Start - FVector(0, 0, 500), FCollisionObjectQueryParams(ECC_WorldStatic), Params))
        {
            return;
        }
        Floor = Hit.ImpactPoint;
    }
    const FVector Eye = Floor + FVector(0, 0, 160);
    const FVector Ahead = FRotator(0.0, Facing.Yaw, 0.0).Vector();
    const FVector Side(-Ahead.Y, Ahead.X, 0.0);
    UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World);
    const bool bNav = Nav && Nav->GetDefaultNavDataInstance(FNavigationSystem::DontCreate) != nullptr;
    for (const FVector& Dir : { Ahead, Side, -Side, -Ahead })
    {
        const FVector Across(-Dir.Y, Dir.X, 0.0);
        for (const double Scale : { 1.0, 0.75, 0.55 })
        {
            const FVector Mid = Floor + Dir * (1200.0 * Scale);
            const FVector Corners[4] = { Mid + Dir * 400.0 * Scale - Across * 700.0 * Scale, Mid + Dir * 400.0 * Scale + Across * 700.0 * Scale,
                Mid - Dir * 400.0 * Scale + Across * 700.0 * Scale, Mid - Dir * 400.0 * Scale - Across * 700.0 * Scale };
            TArray<FVector> Points;
            bool bFits = true;
            for (const FVector& Corner : Corners)
            {
                FVector Ground;
                FNavLocation OnNav;
                if (!GroundAt(World, Corner, Floor.Z, Ground) || !ClearLine(World, Eye, Ground + FVector(0, 0, 120))
                    || (bNav && !Nav->ProjectPointToNavigation(Ground, OnNav, FVector(100.0, 100.0, 250.0))))
                {
                    bFits = false;
                    break;
                }
                Points.Add(Ground);
            }
            for (int32 Index = 0; bFits && Index < Points.Num(); ++Index)
            {
                const FVector Lift(0, 0, 90);
                bFits = ClearLine(World, Points[Index] + Lift, Points[(Index + 1) % Points.Num()] + Lift);
            }
            if (!bFits)
            {
                continue;
            }
            TArray<FVector> Offsets;
            for (const FVector& Point : Points)
            {
                Offsets.Add(Point - Floor);
            }
            // Hostile, but only at close quarters: it marches past in plain view and fights when the player walks up
            // to it or casts at it (a spell within 11 m, or a hit, always starts the fight).
            AReflectionsSquad* Squad = SpawnOne(World, Floor, Offsets, true, EReflectionsSquadFormation::Column, 5, 2,
                { EHeroSpell::Fire, EHeroSpell::IceShard }, 0.0f, TestActors, 700.0f, 300.0f);
            StartPatrol = Squad;
            UE_LOG(LogTemp, Log, TEXT("Squads: start patrol %s on %s, %d m from the player start"), *GetNameSafe(Squad),
                *World->GetMapName(), static_cast<int32>(FVector::Dist2D(Mid, Floor) / 100.0));
            return;
        }
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
    const APawn* Player = UGameplayStatics::GetPlayerPawn(World, 0);
    const FVector Center = Player ? Player->GetActorLocation() : FVector::ZeroVector;
    // Offsets fit Lvl_HeroSampleCrowd's 35 m practice ground (player start at its centre), clear of the jump steps
    // and the crouch beam; GroundPoint pulls any point that misses the floor back toward the player.
    if (Count >= 1)
    {
        // A column of five (3 blades, fire + ice casters) patrolling the edge of the ground.
        SpawnOne(World, Center, { FVector(1400, -1400, 0), FVector(1400, 1350, 0), FVector(-1450, 1350, 0), FVector(-1450, -1400, 0) },
            true, EReflectionsSquadFormation::Column, 5, 2, { EHeroSpell::Fire, EHeroSpell::IceShard }, 0.0f, TestActors);
    }
    if (Count >= 2)
    {
        // A line of five (3 blades, arcane + fire casters) pacing up and down the west side, halting at each end.
        SpawnOne(World, Center, { FVector(-950, -1050, 0), FVector(-950, 950, 0) },
            false, EReflectionsSquadFormation::Line, 5, 2, { EHeroSpell::ArcaneBolt, EHeroSpell::Fire }, 2.0f, TestActors);
    }
    for (int32 Extra = 2; Extra < Count; ++Extra)
    {
        const float Side = Extra % 2 == 0 ? -1.0f : 1.0f;
        SpawnOne(World, Center, { FVector(300, Side * 900, 0), FVector(1100, Side * 900, 0), FVector(1100, Side * 1150, 0), FVector(300, Side * 1150, 0) },
            true, EReflectionsSquadFormation::ColumnOfTwos, 6, 2, { EHeroSpell::IceShard, EHeroSpell::ArcaneBolt }, 0.0f, TestActors);
    }
}

void UReflectionsSquadSubsystem::SpawnGiltTestSquad()
{
    UWorld* World = GetWorld();
    if (!World)
    {
        return;
    }
    const APawn* Player = UGameplayStatics::GetPlayerPawn(World, 0);
    const FVector Center = Player ? Player->GetActorLocation() : FVector::ZeroVector;
    // Five Gilt guards (3 blades with shields, 1 caster) pacing the east side of the practice ground.
    SpawnOne(World, Center, { FVector(950, -1050, 0), FVector(950, 950, 0) }, false, EReflectionsSquadFormation::ColumnOfTwos, 5, 1,
        { EHeroSpell::IceShard }, 2.0f, TestActors, -1.0f, -1.0f, static_cast<int32>(EReflectionsSquadFaction::Gilt));
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
