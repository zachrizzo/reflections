#include "Crowd/ReflectionsCrowdRingSubsystem.h"
#include "NPC/ReflectionsNpcArchetype.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "NPC/ReflectionsNpcSubsystem.h"

#include "Camera/PlayerCameraManager.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"
#include "ZoneGraphSubsystem.h"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsCrowdRing, Log, All);
DECLARE_CYCLE_STAT(TEXT("Crowd ring"), STAT_ReflectionsCrowdRing, STATGROUP_Game);

namespace
{
    TAutoConsoleVariable<int32> CVarRingEnable(TEXT("Crowd.Ring.Enable"), 1,
        TEXT("Civilians kept around the hero on the sidewalk lanes of the ring-crowd maps. 0 removes them."));
    TAutoConsoleVariable<FString> CVarRingMaps(TEXT("Crowd.Ring.Maps"), TEXT("Lvl_MockCity"),
        TEXT("Short names of the maps that get a ring crowd, comma separated (the map needs ZoneGraph sidewalk lanes)."));
    TAutoConsoleVariable<int32> CVarRingCount(TEXT("Crowd.Ring.Count"), 12,
        TEXT("How many ring walkers to keep. Each is a full sample-locomotion character (see Crowd.Lod for the cost)."));
    TAutoConsoleVariable<float> CVarRingMinDistance(TEXT("Crowd.Ring.MinDistance"), 1500.0f,
        TEXT("Nearest a new walker is placed from the hero (cm)."));
    TAutoConsoleVariable<float> CVarRingMaxDistance(TEXT("Crowd.Ring.MaxDistance"), 4500.0f,
        TEXT("Farthest a new walker is placed from the hero (cm)."));
    TAutoConsoleVariable<float> CVarRingRecycleDistance(TEXT("Crowd.Ring.RecycleDistance"), 5500.0f,
        TEXT("A calm walker farther than this from the hero (cm), unseen for Crowd.Ring.RecycleSeconds, is replaced ahead of the hero."));
    TAutoConsoleVariable<float> CVarRingRecycleSeconds(TEXT("Crowd.Ring.RecycleSeconds"), 2.0f,
        TEXT("How long a far walker must stay unseen before it is replaced."));
    TAutoConsoleVariable<FString> CVarRingArchetype(TEXT("Crowd.Ring.Archetype"), TEXT("Civilian"),
        TEXT("NPC archetype the ring walkers are spawned as."));

    const FName RingTag(TEXT("Crowd_Ring"));
    const FName LaneWalkerTag(TEXT("Crowd_LaneWalker"));
    constexpr double CheckPeriod = 0.5;

    bool IsRingMap(const FString& MapName)
    {
        TArray<FString> Maps;
        CVarRingMaps.GetValueOnGameThread().ParseIntoArray(Maps, TEXT(","), true);
        for (FString& Map : Maps)
        {
            if (Map.TrimStartAndEnd().Equals(MapName, ESearchCase::IgnoreCase)) return true;
        }
        return false;
    }
}

bool UReflectionsCrowdRingSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId UReflectionsCrowdRingSubsystem::GetStatId() const
{
    RETURN_QUICK_DECLARE_CYCLE_STAT(UReflectionsCrowdRingSubsystem, STATGROUP_Tickables);
}

void UReflectionsCrowdRingSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
    Super::OnWorldBeginPlay(InWorld);
    bActiveMap = IsRingMap(UWorld::RemovePIEPrefix(InWorld.GetMapName()));
    // The hero and the NPC system settle in first.
    StartAt = InWorld.GetTimeSeconds() + 1.5;
    if (bActiveMap) UE_LOG(LogReflectionsCrowdRing, Log, TEXT("Ring crowd: active on %s."), *InWorld.GetMapName());
}

void UReflectionsCrowdRingSubsystem::Deinitialize()
{
    // The world is ending and takes the walkers with it.
    Walkers.Reset();
    Super::Deinitialize();
}

TArray<AActor*> UReflectionsCrowdRingSubsystem::GetWalkers() const
{
    TArray<AActor*> Actors;
    for (const FRingWalker& Walker : Walkers)
        if (AActor* Actor = Walker.Actor.Get()) Actors.Add(Actor);
    return Actors;
}

void UReflectionsCrowdRingSubsystem::RemoveAll()
{
    for (FRingWalker& Walker : Walkers)
        if (AActor* Actor = Walker.Actor.Get()) Actor->Destroy();
    Walkers.Reset();
}

bool UReflectionsCrowdRingSubsystem::IsSeen(const FVector& Location) const
{
    const APlayerController* Controller = UGameplayStatics::GetPlayerController(this, 0);
    const APlayerCameraManager* Camera = Controller ? Controller->PlayerCameraManager.Get() : nullptr;
    if (!Camera) return false;
    const FVector Eye = Camera->GetCameraLocation();
    const FVector Head = Location + FVector(0.0, 0.0, 120.0);
    const FVector To = Head - Eye;
    const double Distance = To.Size();
    // Far away a pop goes unnoticed; outside the view (with a margin for wide screens) it cannot be seen.
    if (Distance > 6000.0 || Distance < 1.0) return Distance < 1.0;
    if (FVector::DotProduct(To / Distance, Camera->GetCameraRotation().Vector()) < FMath::Cos(FMath::DegreesToRadians(65.0))) return false;
    // In the view cone: seen unless a building is in the way.
    FHitResult Hit;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(CrowdRingSight), false, Controller->GetPawn());
    return !GetWorld()->LineTraceSingleByChannel(Hit, Eye, Head, ECC_Visibility, Params);
}

bool UReflectionsCrowdRingSubsystem::FindSpawnPoint(const FVector& Hero, float AheadYaw, bool bAllowSeen, FVector& OutLocation, float& OutYaw) const
{
    const UZoneGraphSubsystem* ZoneGraph = UWorld::GetSubsystem<UZoneGraphSubsystem>(GetWorld());
    if (!ZoneGraph) return false;
    const float MinDistance = CVarRingMinDistance.GetValueOnGameThread();
    const float MaxDistance = FMath::Max(MinDistance + 100.0f, CVarRingMaxDistance.GetValueOnGameThread());
    const FVector Extent(800.0f, 800.0f, 1000.0f);
    for (int32 Try = 0; Try < 12; ++Try)
    {
        // Mostly ahead of where the hero is going, sometimes to the sides.
        const float Yaw = AheadYaw + FMath::FRandRange(-100.0f, 100.0f);
        const FVector Probe = Hero + FRotator(0.0f, Yaw, 0.0f).Vector() * FMath::FRandRange(MinDistance, MaxDistance);
        FZoneGraphLaneLocation Lane;
        float DistanceSq = 0.0f;
        if (!ZoneGraph->FindNearestLane(FBox(Probe - Extent, Probe + Extent), FZoneGraphTagFilter(), Lane, DistanceSq)) continue;
        const double FromHero = FVector::Dist2D(Lane.Position, Hero);
        if (FromHero < MinDistance * 0.7f || FromHero > MaxDistance * 1.3f) continue;
        const bool bCrowded = Walkers.ContainsByPredicate([&Lane](const FRingWalker& Walker)
        {
            const AActor* Actor = Walker.Actor.Get();
            return Actor && FVector::Dist2D(Actor->GetActorLocation(), Lane.Position) < 300.0;
        });
        if (bCrowded) continue;
        if (!bAllowSeen && IsSeen(Lane.Position)) continue;
        OutLocation = Lane.Position + FVector(0.0, 0.0, 2.0);
        OutYaw = Lane.Direction.Rotation().Yaw;
        return true;
    }
    return false;
}

void UReflectionsCrowdRingSubsystem::SpawnWalker(const FVector& Hero, float AheadYaw, bool bAllowSeen)
{
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    FVector Location;
    float Yaw = 0.0f;
    if (!Npcs || !FindSpawnPoint(Hero, AheadYaw, bAllowSeen, Location, Yaw))
    {
        ++FailedSpawns;
        return;
    }
    AActor* Npc = Npcs->SpawnNpc(FName(*CVarRingArchetype.GetValueOnGameThread()), Location, Yaw, nullptr);
    if (!Npc)
    {
        ++FailedSpawns;
        return;
    }
    // A city civilian walking the sidewalks (stroll's lane mode); Friendly like the placed civilians.
    Npc->Tags.AddUnique(RingTag);
    Npc->Tags.AddUnique(LaneWalkerTag);
    Npc->Tags.AddUnique(TEXT("Friendly"));
    Walkers.Add({ Npc, -1.0 });
    ++SpawnedTotal;
}

void UReflectionsCrowdRingSubsystem::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    UWorld* World = GetWorld();
    if (!bActiveMap || !World || !World->HasBegunPlay()) return;
    const double Now = World->GetTimeSeconds();
    if (Now < StartAt || Now < NextCheck) return;
    NextCheck = Now + CheckPeriod;
    SCOPE_CYCLE_COUNTER(STAT_ReflectionsCrowdRing);

    if (CVarRingEnable.GetValueOnGameThread() == 0)
    {
        if (!Walkers.IsEmpty()) RemoveAll();
        return;
    }
    const APawn* HeroPawn = UGameplayStatics::GetPlayerPawn(this, 0);
    const UZoneGraphSubsystem* ZoneGraph = UWorld::GetSubsystem<UZoneGraphSubsystem>(World);
    if (!HeroPawn) return;
    if (!ZoneGraph || ZoneGraph->GetRegisteredZoneGraphData().IsEmpty())
    {
        if (!bWarnedNoLanes)
        {
            UE_LOG(LogReflectionsCrowdRing, Warning, TEXT("Ring crowd: %s has no ZoneGraph lanes; no walkers."), *World->GetMapName());
            bWarnedNoLanes = true;
        }
        return;
    }
    const FVector Hero = HeroPawn->GetActorLocation();
    const FVector Velocity = HeroPawn->GetVelocity();
    float AheadYaw = HeroPawn->GetControlRotation().Yaw;
    if (Velocity.Size2D() > 100.0) AheadYaw = Velocity.Rotation().Yaw;

    // Replace the calm (or dead) walkers left far behind, once nobody can see them go.
    const UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    const float RecycleDistance = CVarRingRecycleDistance.GetValueOnGameThread();
    const float RecycleSeconds = CVarRingRecycleSeconds.GetValueOnGameThread();
    for (int32 Index = Walkers.Num() - 1; Index >= 0; --Index)
    {
        FRingWalker& Walker = Walkers[Index];
        AActor* Actor = Walker.Actor.Get();
        if (!Actor)
        {
            Walkers.RemoveAtSwap(Index);
            continue;
        }
        const UReflectionsNpcReactionComponent* Brain = Npcs ? Npcs->FindNpc(Actor) : nullptr;
        // Converted by the villain: it is his now (his Tarnish counts it), so it leaves the ring, which gets a fresh civilian.
        if (Brain && (Brain->Disposition == EReflectionsNpcDisposition::Infected || Brain->Disposition == EReflectionsNpcDisposition::VillainHost))
        {
            Actor->Tags.Remove(RingTag);
            Actor->Tags.Remove(LaneWalkerTag);
            Walkers.RemoveAtSwap(Index);
            ++ReleasedTotal;
            continue;
        }
        // Stroll's lane mode owns ring walkers; anyone else claiming one leaves it standing (said once).
        if (!bWarnedClaimed && Actor->ActorHasTag(TEXT("NPC_NoStroll")))
        {
            bWarnedClaimed = true;
            UE_LOG(LogReflectionsCrowdRing, Warning, TEXT("Ring crowd: %s was tagged NPC_NoStroll by another system; stroll will not walk it."), *Actor->GetName());
        }
        // Calm (or dead) walkers go once far and unseen; a still-frightened one only when twice as far.
        const double Distance = FVector::Dist2D(Actor->GetActorLocation(), Hero);
        const bool bBusy = Brain && !Brain->IsIncapacitated() && Brain->Reaction != EReflectionsNpcReaction::Calm;
        const bool bGone = !Actor->WasRecentlyRendered(1.0f) && Distance > RecycleDistance && (!bBusy || Distance > RecycleDistance * 2.0f);
        if (!bGone)
        {
            Walker.FarSince = -1.0;
            continue;
        }
        if (Walker.FarSince < 0.0) Walker.FarSince = Now;
        if (Now - Walker.FarSince < RecycleSeconds) continue;
        Actor->Destroy();
        Walkers.RemoveAtSwap(Index);
        ++RecycledTotal;
    }

    // One new walker per check: the first ones may appear in view (the map just began), later ones out of sight.
    const int32 Want = FMath::Clamp(CVarRingCount.GetValueOnGameThread(), 0, 64);
    if (Walkers.Num() > Want)
    {
        if (AActor* Extra = Walkers.Last().Actor.Get()) Extra->Destroy();
        Walkers.Pop();
    }
    else if (Walkers.Num() < Want)
    {
        SpawnWalker(Hero, AheadYaw, SpawnedTotal < Want);
    }
}

FString UReflectionsCrowdRingSubsystem::Describe() const
{
    const APawn* HeroPawn = UGameplayStatics::GetPlayerPawn(this, 0);
    FString Text = FString::Printf(TEXT("Ring crowd: map %d, %d walkers (want %d), spawned %d, recycled %d, released to the villain %d, failed spawns %d"),
        bActiveMap, Walkers.Num(), CVarRingCount.GetValueOnGameThread(), SpawnedTotal, RecycledTotal, ReleasedTotal, FailedSpawns);
    const UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    for (const FRingWalker& Walker : Walkers)
    {
        if (const AActor* Actor = Walker.Actor.Get())
        {
            const UReflectionsNpcReactionComponent* Brain = Npcs ? Npcs->FindNpc(Actor) : nullptr;
            Text += FString::Printf(TEXT("\n  %s: %.0f m from the hero, reaction %d, disposition %d, steered %d, no-stroll %d"), *Actor->GetName(),
                HeroPawn ? FVector::Dist2D(Actor->GetActorLocation(), HeroPawn->GetActorLocation()) / 100.0 : 0.0,
                Brain ? static_cast<int32>(Brain->Reaction) : -1, Brain ? static_cast<int32>(Brain->Disposition) : -1,
                Brain && Brain->IsExternallySteered(), Actor->ActorHasTag(TEXT("NPC_NoStroll")));
        }
    }
    return Text;
}
