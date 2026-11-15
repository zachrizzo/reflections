#include "Crowd/ReflectionsCrowdRingSubsystem.h"
#include "Crowd/ReflectionsCrowdStrollSubsystem.h"
#include "NPC/ReflectionsNpcArchetype.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "NPC/ReflectionsNpcSubsystem.h"

#include "Animation/AnimInstance.h"
#include "Animation/AnimMontage.h"
#include "Animation/AnimSequence.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Character.h"
#include "Engine/AssetManager.h"
#include "Engine/StreamableManager.h"
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
    TAutoConsoleVariable<FString> CVarRingMaps(TEXT("Crowd.Ring.Maps"), TEXT("GrayLondon_Geodata"),
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
    TAutoConsoleVariable<int32> CVarRingLaneFree(TEXT("Crowd.Ring.LaneFree"), 1,
        TEXT("Without ZoneGraph lanes, place walkers on open street floor near the hero (they stroll round their spawn point). 0: no lanes, no walkers."));
    TAutoConsoleVariable<float> CVarRingRefillDelay(TEXT("Crowd.Ring.RefillDelay"), 12.0f,
        TEXT("After violence within 60 m of the hero, no new walkers for this long (s): the street stays empty, then refills."));
    TAutoConsoleVariable<float> CVarRingFledRetire(TEXT("Crowd.Ring.FledRetireDistance"), 2000.0f,
        TEXT("A fleeing walker farther than this (cm) and unseen for 1 s is retired at once (it ran off the street)."));
    TAutoConsoleVariable<float> CVarRingCarryChance(TEXT("Crowd.Ring.CarryChance"), 0.3f,
        TEXT("Share of new walkers that carry a basket or crate (needs Crowd.Ring.CarryProp and an additive carry clip)."));
    TAutoConsoleVariable<FString> CVarRingCarryProp(TEXT("Crowd.Ring.CarryProp"),
        TEXT("/Game/LanthorneAssets/Pewterside/Props/SM_Pewterside_CanalCrate.SM_Pewterside_CanalCrate"),
        TEXT("Static mesh carried by carriers (object path; scaled to about 45 cm across). Empty: nobody carries."));
    TAutoConsoleVariable<FString> CVarRingCarryClip(TEXT("Crowd.Ring.CarryClip"), TEXT("/Game/Combat/Melee/AS_Street_Carry_Hold_Walker.AS_Street_Carry_Hold_Walker"),
        TEXT("Additive upper-body hold for the walker skeleton, looped over the walk while carrying."));
    TAutoConsoleVariable<int32> CVarRingPrewarm(TEXT("Crowd.Ring.PrewarmPerCheck"), 4,
        TEXT("Walkers spawned per 0.5 s check during the initial fill (at map start, behind the intro), instead of one."));

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
    if (!bActiveMap) return;
    UE_LOG(LogReflectionsCrowdRing, Log, TEXT("Ring crowd: active on %s."), *InWorld.GetMapName());
    if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this))
    {
        StimulusHandle = Npcs->OnStimulus().AddUObject(this, &UReflectionsCrowdRingSubsystem::HandleStimulus);
    }
    // SpawnNpc loads a look synchronously the first time it is worn; load them all in the background now instead.
    if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this))
    {
        if (const UReflectionsNpcArchetype* Archetype = Npcs->FindArchetype(FName(*CVarRingArchetype.GetValueOnGameThread())))
        {
            TArray<FSoftObjectPath> Looks;
            for (const TSoftClassPtr<AActor>& Look : Archetype->Looks)
                if (!Look.IsNull() && !Look.Get()) Looks.AddUnique(Look.ToSoftObjectPath());
            if (!Looks.IsEmpty()) LookPreload = UAssetManager::GetStreamableManager().RequestAsyncLoad(Looks);
        }
    }
}

void UReflectionsCrowdRingSubsystem::Deinitialize()
{
    // The world is ending and takes the walkers with it.
    if (UWorld* World = GetWorld())
    {
        UReflectionsNpcSubsystem* Npcs = World->GetSubsystem<UReflectionsNpcSubsystem>();
        if (IsValid(Npcs) && StimulusHandle.IsValid()) Npcs->OnStimulus().Remove(StimulusHandle);
    }
    StimulusHandle.Reset();
    Walkers.Reset();
    if (LookPreload.IsValid()) LookPreload->CancelHandle();
    LookPreload.Reset();
    Super::Deinitialize();
}

TArray<AActor*> UReflectionsCrowdRingSubsystem::GetWalkers() const
{
    TArray<AActor*> Actors;
    for (const FRingWalker& Walker : Walkers)
        if (AActor* Actor = Walker.Actor.Get()) Actors.Add(Actor);
    return Actors;
}

void UReflectionsCrowdRingSubsystem::HandleStimulus(const FReflectionsNpcStimulus& Stimulus)
{
    // Everything that frightens a street except a call for help (the villain taking someone counts too).
    if (Stimulus.Kind == EReflectionsNpcStimulusKind::Alarm) return;
    if (const UWorld* World = GetWorld())
    {
        LastViolenceTime = World->GetTimeSeconds();
        LastViolenceLocation = Stimulus.Location;
    }
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

bool UReflectionsCrowdRingSubsystem::FindFloorPoint(const FVector& Hero, float HeroFeetZ, float AheadYaw, bool bAllowSeen, FVector& OutLocation, float& OutYaw) const
{
    UWorld* World = GetWorld();
    const float MinDistance = CVarRingMinDistance.GetValueOnGameThread();
    const float Farthest = FMath::Max(MinDistance + 100.0f, CVarRingRecycleDistance.GetValueOnGameThread() * 0.9f);
    const float MaxDistance = FMath::Clamp(CVarRingMaxDistance.GetValueOnGameThread(), MinDistance + 100.0f, Farthest);
    FCollisionQueryParams Params(SCENE_QUERY_STAT(CrowdRingFloor), false);
    if (const APawn* HeroPawn = UGameplayStatics::GetPlayerPawn(this, 0)) Params.AddIgnoredActor(HeroPawn);
    FCollisionObjectQueryParams Solid(ECC_WorldStatic);
    Solid.AddObjectTypesToQuery(ECC_WorldDynamic);
    const FCollisionShape Body = FCollisionShape::MakeCapsule(40.0f, 88.0f);
    for (int32 Try = 0; Try < 16; ++Try)
    {
        const float Yaw = AheadYaw + FMath::FRandRange(-100.0f, 100.0f);
        const FVector Probe = Hero + FRotator(0.0f, Yaw, 0.0f).Vector() * FMath::FRandRange(MinDistance, MaxDistance);
        // Street floor at about the hero's level (not a roof, not a cellar).
        FHitResult Floor;
        if (!World->LineTraceSingleByObjectType(Floor, FVector(Probe.X, Probe.Y, HeroFeetZ + 250.0f), FVector(Probe.X, Probe.Y, HeroFeetZ - 400.0f), Solid, Params)) continue;
        if (Floor.ImpactNormal.Z < 0.8f || FMath::Abs(Floor.ImpactPoint.Z - HeroFeetZ) > 400.0f) continue;
        // Outdoors: from high above, the first thing hit is this same floor (no roof or upper storey over it).
        FHitResult Sky;
        if (World->LineTraceSingleByObjectType(Sky, FVector(Probe.X, Probe.Y, Floor.ImpactPoint.Z + 3000.0f), Floor.ImpactPoint + FVector(0.0, 0.0, 5.0), Solid, Params)) continue;
        // Room for a person standing there.
        if (World->OverlapAnyTestByObjectType(Floor.ImpactPoint + FVector(0.0, 0.0, 92.0), FQuat::Identity, Solid, Body, Params)) continue;
        const FVector Spot = Floor.ImpactPoint;
        const bool bCrowded = Walkers.ContainsByPredicate([&Spot](const FRingWalker& Walker)
        {
            const AActor* Actor = Walker.Actor.Get();
            return Actor && FVector::Dist2D(Actor->GetActorLocation(), Spot) < 300.0;
        });
        if (bCrowded) continue;
        if (!bAllowSeen && IsSeen(Spot)) continue;
        OutLocation = Spot + FVector(0.0, 0.0, 2.0);
        OutYaw = FMath::FRandRange(-180.0f, 180.0f);
        return true;
    }
    return false;
}

bool UReflectionsCrowdRingSubsystem::FindSpawnPoint(const FVector& Hero, float AheadYaw, bool bAllowSeen, FVector& OutLocation, float& OutYaw) const
{
    const UZoneGraphSubsystem* ZoneGraph = UWorld::GetSubsystem<UZoneGraphSubsystem>(GetWorld());
    if (!ZoneGraph) return false;
    const float MinDistance = CVarRingMinDistance.GetValueOnGameThread();
    // Never place a walker where it would be recycled at once (beyond the recycle distance, unseen).
    const float Farthest = FMath::Max(MinDistance + 100.0f, CVarRingRecycleDistance.GetValueOnGameThread() * 0.9f);
    const float MaxDistance = FMath::Clamp(CVarRingMaxDistance.GetValueOnGameThread(), MinDistance + 100.0f, Farthest);
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
        if (FromHero < MinDistance * 0.7f || FromHero > FMath::Min(MaxDistance * 1.3f, Farthest)) continue;
        const bool bCrowded = Walkers.ContainsByPredicate([&Lane](const FRingWalker& Walker)
        {
            const AActor* Actor = Walker.Actor.Get();
            return Actor && FVector::Dist2D(Actor->GetActorLocation(), Lane.Position) < 300.0;
        });
        if (bCrowded) continue;
        if (!bAllowSeen && IsSeen(Lane.Position)) continue;
        // Lane points are at pavement height (city ground + 3 cm). Where a lane cuts a road corner, the road sheet
        // is 18 cm higher and one-sided: spawning at the lane's height would put the walker under it. Stand on the
        // top floor found from 25 cm above the lane (high enough for a road, below a bench seat).
        FVector Feet = Lane.Position;
        FHitResult Floor;
        FCollisionQueryParams FloorParams(SCENE_QUERY_STAT(CrowdRingLaneFloor), true);
        if (GetWorld()->LineTraceSingleByObjectType(Floor, Lane.Position + FVector(0.0, 0.0, 25.0), Lane.Position - FVector(0.0, 0.0, 60.0),
            FCollisionObjectQueryParams(ECC_WorldStatic), FloorParams) && Floor.ImpactNormal.Z > 0.7f)
        {
            Feet.Z = Floor.ImpactPoint.Z;
        }
        OutLocation = Feet + FVector(0.0, 0.0, 2.0);
        OutYaw = Lane.Direction.Rotation().Yaw;
        return true;
    }
    return false;
}

void UReflectionsCrowdRingSubsystem::SpawnWalker(const FVector& Hero, float HeroFeetZ, float AheadYaw, bool bAllowSeen, bool bLanes)
{
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    FVector Location = FVector::ZeroVector;
    float Yaw = 0.0f;
    // A map with street routes (MedievalLondon): spawn on a route, where walkers keep clear of houses and stalls.
    bool bOnRoute = false;
    if (UReflectionsCrowdStrollSubsystem* Stroll = GetWorld()->GetSubsystem<UReflectionsCrowdStrollSubsystem>())
    {
        const float MinDistance = CVarRingMinDistance.GetValueOnGameThread();
        const float Farthest = FMath::Max(MinDistance + 100.0f, CVarRingRecycleDistance.GetValueOnGameThread() * 0.9f);
        const float MaxDistance = FMath::Clamp(CVarRingMaxDistance.GetValueOnGameThread(), MinDistance + 100.0f, Farthest);
        bOnRoute = Stroll->FindRouteSpawn(Hero, MinDistance, MaxDistance, [this, bAllowSeen](const FVector& Point)
        {
            const bool bCrowded = Walkers.ContainsByPredicate([&Point](const FRingWalker& Walker)
            {
                const AActor* Actor = Walker.Actor.Get();
                return Actor && FVector::Dist2D(Actor->GetActorLocation(), Point) < 300.0;
            });
            return !bCrowded && (bAllowSeen || !IsSeen(Point));
        }, Location, Yaw);
        if (bOnRoute) Location.Z += 2.0f;
    }
    // Lanes may cover only part of the city: where no lane point fits, open street floor will do.
    const bool bFound = bOnRoute || (bLanes && FindSpawnPoint(Hero, AheadYaw, bAllowSeen, Location, Yaw))
        || (CVarRingLaneFree.GetValueOnGameThread() != 0 && FindFloorPoint(Hero, HeroFeetZ, AheadYaw, bAllowSeen, Location, Yaw));
    if (!Npcs || !bFound)
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
    // Passers-by are an endless supply next to the hero: the Tarnish takes only named or placed people (orchestrator, train #13).
    Npc->Tags.AddUnique(TEXT("NoVillain"));
    FRingWalker& Walker = Walkers.Add_GetRef({ Npc, -1.0 });
    ++SpawnedTotal;
    // Some carry goods; only when there is a prop and the hold clip is additive (a full-body clip would stop the legs).
    if (!CVarRingCarryProp.GetValueOnGameThread().IsEmpty() && FMath::FRand() < CVarRingCarryChance.GetValueOnGameThread())
    {
        const UAnimSequence* Hold = LoadObject<UAnimSequence>(nullptr, *CVarRingCarryClip.GetValueOnGameThread());
        if (Hold && Hold->IsValidAdditive())
        {
            Walker.bCarrier = true;
            Npc->Tags.AddUnique(TEXT("Crowd_Carry"));
        }
    }
}

void UReflectionsCrowdRingSubsystem::TickCarrier(FRingWalker& Walker)
{
    AActor* Actor = Walker.Actor.Get();
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    UReflectionsNpcReactionComponent* Brain = Actor && Npcs ? Npcs->FindNpc(Actor) : nullptr;
    ACharacter* Driver = Brain ? Brain->GetLocomotionDriver() : nullptr;
    UAnimInstance* Anim = Driver && Driver->GetMesh() ? Driver->GetMesh()->GetAnimInstance() : nullptr;
    if (!Anim) return;
    // Calm and walking: hold the goods. Frightened (or in a scene): let go of the pose and hide the goods.
    const bool bCalm = Brain->Reaction == EReflectionsNpcReaction::Calm && !Brain->IsIncapacitated() && !Npcs->IsNpcInScene(Actor);
    UAnimMontage* Playing = Walker.CarryMontage.Get();
    const bool bHolding = Playing && Anim->Montage_IsPlaying(Playing);
    if (bCalm && !bHolding)
    {
        if (UAnimSequenceBase* Hold = LoadObject<UAnimSequenceBase>(nullptr, *CVarRingCarryClip.GetValueOnGameThread()))
            Walker.CarryMontage = Anim->PlaySlotAnimationAsDynamicMontage(Hold, TEXT("DefaultSlot"), 0.3f, 0.3f, 1.0f, 100000);
    }
    else if (!bCalm && bHolding)
    {
        Anim->Montage_Stop(0.2f, Playing);
    }
    UStaticMeshComponent* Prop = Walker.CarryProp.Get();
    if (!Prop && bCalm)
    {
        if (UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *CVarRingCarryProp.GetValueOnGameThread()))
        {
            Prop = NewObject<UStaticMeshComponent>(Actor, TEXT("CrowdCarryProp"));
            Prop->SetStaticMesh(Mesh);
            Prop->SetCollisionEnabled(ECollisionEnabled::NoCollision);
            Prop->SetCastShadow(true);
            // Held in front at waist height (the looks face their own +Y), scaled to about 45 cm across.
            const float Size = FMath::Max(1.0f, Mesh->GetBounds().BoxExtent.GetMax() * 2.0f);
            Prop->SetRelativeScale3D(FVector(45.0f / Size));
            Prop->SetupAttachment(Actor->GetRootComponent());
            Prop->SetRelativeLocation(FVector(0.0, 32.0, 98.0));
            Prop->RegisterComponent();
            Walker.CarryProp = Prop;
        }
    }
    if (Prop) Prop->SetVisibility(bCalm);
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
    const bool bLanes = ZoneGraph && !ZoneGraph->GetRegisteredZoneGraphData().IsEmpty();
    if (!bLanes)
    {
        const bool bLaneFree = CVarRingLaneFree.GetValueOnGameThread() != 0;
        if (!bWarnedNoLanes)
        {
            UE_LOG(LogReflectionsCrowdRing, Warning, TEXT("Ring crowd: %s has no ZoneGraph lanes; %s."), *World->GetMapName(),
                bLaneFree ? TEXT("walkers are placed on open street floor near the hero") : TEXT("no walkers (Crowd.Ring.LaneFree 0)"));
            bWarnedNoLanes = true;
        }
        if (!bLaneFree) return;
    }
    const FVector Hero = HeroPawn->GetActorLocation();
    float HeroFeetZ = Hero.Z;
    if (const ACharacter* HeroCharacter = Cast<ACharacter>(HeroPawn))
        if (const UCapsuleComponent* Capsule = HeroCharacter->GetCapsuleComponent()) HeroFeetZ -= Capsule->GetScaledCapsuleHalfHeight();
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
        if (!bWarnedClaimed && Actor->ActorHasTag(TEXT("NPC_NoStroll")) && !Actor->ActorHasTag(TEXT("Crowd_Spot")))
        {
            bWarnedClaimed = true;
            UE_LOG(LogReflectionsCrowdRing, Warning, TEXT("Ring crowd: %s was tagged NPC_NoStroll by another system; stroll will not walk it."), *Actor->GetName());
        }
        // Calm (or dead) walkers go once far and unseen; a still-frightened one only when twice as far.
        const double Distance = FVector::Dist2D(Actor->GetActorLocation(), Hero);
        // Someone who fled out of sight has left the street: retire them now, so the street visibly empties.
        if (Brain && Brain->Reaction == EReflectionsNpcReaction::Fleeing && Distance > CVarRingFledRetire.GetValueOnGameThread()
            && !Actor->WasRecentlyRendered(1.0f))
        {
            Actor->Destroy();
            Walkers.RemoveAtSwap(Index);
            ++RetiredFled;
            continue;
        }
        const bool bBusy = Brain && !Brain->IsIncapacitated() && Brain->Reaction != EReflectionsNpcReaction::Calm;
        const bool bGone = !Actor->WasRecentlyRendered(1.0f) && Distance > RecycleDistance && (!bBusy || Distance > RecycleDistance * 2.0f);
        if (Walker.bCarrier && Brain) TickCarrier(Walker);
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
    else if (Walkers.Num() < Want && Now - LastViolenceTime < CVarRingRefillDelay.GetValueOnGameThread()
        && FVector::Dist2D(LastViolenceLocation, Hero) < 6000.0)
    {
        // A lull after violence near the hero: the street stays empty for now.
    }
    else if (Walkers.Num() < Want)
    {
        // The initial fill happens at map start, behind the intro fade: several at once so the street is full when the
        // player gets control. Later replacements come one at a time, out of sight.
        const bool bInitialFill = SpawnedTotal < Want;
        const int32 Batch = bInitialFill ? FMath::Clamp(CVarRingPrewarm.GetValueOnGameThread(), 1, 12) : 1;
        for (int32 Spawn = 0; Spawn < Batch && Walkers.Num() < Want; ++Spawn)
        {
            SpawnWalker(Hero, HeroFeetZ, AheadYaw, bInitialFill, bLanes);
        }
    }
}

FString UReflectionsCrowdRingSubsystem::Describe() const
{
    const APawn* HeroPawn = UGameplayStatics::GetPlayerPawn(this, 0);
    FString Text = FString::Printf(TEXT("Ring crowd: map %d, %d walkers (want %d), spawned %d, recycled %d, fled and retired %d, released to the villain %d, failed spawns %d"),
        bActiveMap, Walkers.Num(), CVarRingCount.GetValueOnGameThread(), SpawnedTotal, RecycledTotal, RetiredFled, ReleasedTotal, FailedSpawns);
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
