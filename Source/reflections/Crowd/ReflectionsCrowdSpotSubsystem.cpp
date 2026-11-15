#include "Crowd/ReflectionsCrowdSpotSubsystem.h"
#include "Crowd/ReflectionsCrowdChatSubsystem.h"
#include "NPC/ReflectionsNpcArchetype.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "NPC/ReflectionsNpcSubsystem.h"

#include "Animation/AnimSequenceBase.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/CapsuleComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/OverlapResult.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/UnrealType.h"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsCrowdSpots, Log, All);
DECLARE_CYCLE_STAT(TEXT("Crowd spots"), STAT_ReflectionsCrowdSpots, STATGROUP_Game);

namespace
{
    TAutoConsoleVariable<int32> CVarSpotsEnable(TEXT("Crowd.Spots.Enable"), 1,
        TEXT("Street scenes: civilians chat, look in windows, sell, sit on benches, lean and smoke. 0 frees everyone."));
    TAutoConsoleVariable<float> CVarSpotsActivate(TEXT("Crowd.Spots.ActivateDistance"), 6000.0f,
        TEXT("Spots within this distance of the hero (cm) are in use."));
    TAutoConsoleVariable<float> CVarSpotsDeactivate(TEXT("Crowd.Spots.DeactivateDistance"), 8000.0f,
        TEXT("Spots beyond this distance let their people go (pinned occupants are removed once unseen)."));
    TAutoConsoleVariable<float> CVarSpotsClaimRadius(TEXT("Crowd.Spots.ClaimRadius"), 1500.0f,
        TEXT("A passing ring walker this close (cm) to a free claimable slot may stop there."));
    TAutoConsoleVariable<float> CVarSpotsClaimChance(TEXT("Crowd.Spots.ClaimChance"), 0.5f,
        TEXT("Chance per check (4 per second) that an eligible walker takes a free slot."));
    TAutoConsoleVariable<int32> CVarSpotsMaxPinned(TEXT("Crowd.Spots.MaxPinned"), 6,
        TEXT("Most pinned occupants alive at once (each is a full character, on top of the ring)."));
    TAutoConsoleVariable<FString> CVarSpotsArchetype(TEXT("Crowd.Spots.Archetype"), TEXT("Civilian"),
        TEXT("NPC archetype pinned occupants are spawned as."));
    TAutoConsoleVariable<float> CVarSpotsSeatForward(TEXT("Crowd.Spots.SeatForward"), 12.0f,
        TEXT("A seated person's root sits this far (cm) in front of the bench's middle (tune if they float or sink into the back)."));

    const FName RingTag(TEXT("Crowd_Ring"));
    const FName NoStrollTag(TEXT("NPC_NoStroll"));
    const FName SpotTag(TEXT("Crowd_Spot"));
    const FName CarryTag(TEXT("Crowd_Carry"));
    constexpr double TickPeriod = 0.25;
    constexpr float ArriveRadius = 35.0f;

    // Clips on the walker skeleton (SK_UEFN_Mannequin): Game Animation Sample idles and bench set; Kimodo street loops.
    const TCHAR* RelaxedIdleLoop = TEXT("/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Relaxed_Stand_Idle_Loop.M_Relaxed_Stand_Idle_Loop");
    const TCHAR* BenchIdleLoop = TEXT("/Game/Characters/UEFN_Mannequin/Animations/Interactions/Bench/M_interaction_bench_idle_loop.M_interaction_bench_idle_loop");
    const TCHAR* BenchStandUp = TEXT("/Game/Characters/UEFN_Mannequin/Animations/Interactions/Bench/M_interaction_bench_out_to_stand.M_interaction_bench_out_to_stand");
    const TCHAR* LeanLoop = TEXT("/Game/Combat/Melee/AS_Street_Wall_Lean_Walker.AS_Street_Wall_Lean_Walker");
    const TCHAR* SmokeLoop = TEXT("/Game/Combat/Melee/AS_Street_Pipe_Smoke_Walker.AS_Street_Pipe_Smoke_Walker");
    const TCHAR* ChatGesture = TEXT("/Game/Combat/Melee/AS_Street_Chat_Gesture_Walker.AS_Street_Chat_Gesture_Walker");
    const TCHAR* VendorCall = TEXT("/Game/Combat/Melee/AS_Street_Vendor_Call_Walker.AS_Street_Vendor_Call_Walker");
    const TCHAR* IdleBreaks[] = {
        TEXT("/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Relaxed_Stand_Idle_Break_v01.M_Relaxed_Stand_Idle_Break_v01"),
        TEXT("/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Relaxed_Stand_Idle_Break_v02.M_Relaxed_Stand_Idle_Break_v02"),
        TEXT("/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Relaxed_Stand_Idle_Break_v03.M_Relaxed_Stand_Idle_Break_v03"),
        TEXT("/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Relaxed_Stand_Idle_Break_v04.M_Relaxed_Stand_Idle_Break_v04"),
        TEXT("/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Relaxed_Stand_Idle_Break_v05.M_Relaxed_Stand_Idle_Break_v05"),
        TEXT("/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Relaxed_Stand_Idle_Break_v06.M_Relaxed_Stand_Idle_Break_v06"),
        TEXT("/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Relaxed_Stand_Idle_Break_v07.M_Relaxed_Stand_Idle_Break_v07"),
        TEXT("/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Relaxed_Stand_Idle_Break_v08.M_Relaxed_Stand_Idle_Break_v08"),
    };

    UAnimSequenceBase* Clip(const TCHAR* Path) { return LoadObject<UAnimSequenceBase>(nullptr, Path); }

    /** Walk gait on the sample character (same switch the stroll uses). */
    void SetWalkGait(ACharacter* Driver, bool bWalk)
    {
        if (!Driver) return;
        FStructProperty* StateProperty = FindFProperty<FStructProperty>(Driver->GetClass(), TEXT("CharacterInputState"));
        if (!StateProperty || !StateProperty->Struct) return;
        void* State = StateProperty->ContainerPtrToValuePtr<void>(Driver);
        for (TFieldIterator<FBoolProperty> It(StateProperty->Struct); It; ++It)
        {
            const FString Name = It->GetAuthoredName();
            if (Name.StartsWith(TEXT("WantsToWalk"))) It->SetPropertyValue_InContainer(State, bWalk);
            else if (Name.StartsWith(TEXT("WantsToStrafe")) || Name.StartsWith(TEXT("WantsToSprint")) || Name.StartsWith(TEXT("WantsToAim")))
                It->SetPropertyValue_InContainer(State, false);
        }
    }

    bool IsUsable(const UReflectionsNpcReactionComponent* Brain)
    {
        return Brain && !Brain->IsIncapacitated() && Brain->Reaction == EReflectionsNpcReaction::Calm
            && Brain->Disposition != EReflectionsNpcDisposition::Infected && Brain->Disposition != EReflectionsNpcDisposition::VillainHost;
    }
}

bool UReflectionsCrowdSpotSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId UReflectionsCrowdSpotSubsystem::GetStatId() const
{
    RETURN_QUICK_DECLARE_CYCLE_STAT(UReflectionsCrowdSpotSubsystem, STATGROUP_Tickables);
}

void UReflectionsCrowdSpotSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
    Super::OnWorldBeginPlay(InWorld);
    LoadSpots(UWorld::RemovePIEPrefix(InWorld.GetMapName()));
    if (!Spots.IsEmpty())
        if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this))
            Npcs->OnNpcSceneEnded.AddUniqueDynamic(this, &UReflectionsCrowdSpotSubsystem::HandleSceneEnded);
}

void UReflectionsCrowdSpotSubsystem::Deinitialize()
{
    if (UWorld* World = GetWorld())
    {
        UReflectionsNpcSubsystem* Npcs = World->GetSubsystem<UReflectionsNpcSubsystem>();
        if (IsValid(Npcs)) Npcs->OnNpcSceneEnded.RemoveDynamic(this, &UReflectionsCrowdSpotSubsystem::HandleSceneEnded);
    }
    // The world ends and takes its people with it.
    Spots.Reset();
    Super::Deinitialize();
}

void UReflectionsCrowdSpotSubsystem::LoadSpots(const FString& MapName)
{
    const FString Path = FPaths::ProjectContentDir() / TEXT("Crowd/Spots") / (MapName + TEXT(".json"));
    FString Text;
    if (!FFileHelper::LoadFileToString(Text, *Path)) return; // no scenes on this map
    TSharedPtr<FJsonObject> Root;
    if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid())
    {
        UE_LOG(LogReflectionsCrowdSpots, Warning, TEXT("Crowd spots: %s is not valid JSON."), *Path);
        return;
    }
    const TArray<TSharedPtr<FJsonValue>>* List = nullptr;
    if (!Root->TryGetArrayField(TEXT("spots"), List)) return;
    for (const TSharedPtr<FJsonValue>& Value : *List)
    {
        const TSharedPtr<FJsonObject> Object = Value.IsValid() ? Value->AsObject() : nullptr;
        if (!Object.IsValid()) continue;
        FSpot Spot;
        Spot.Name = FName(*Object->GetStringField(TEXT("name")));
        FString Kind = TEXT("chat"), Place = TEXT("street");
        Object->TryGetStringField(TEXT("kind"), Kind);
        Object->TryGetStringField(TEXT("place"), Place);
        Spot.Kind = Kind.Equals(TEXT("window"), ESearchCase::IgnoreCase) ? EKind::Window
            : Kind.Equals(TEXT("vendor"), ESearchCase::IgnoreCase) ? EKind::Vendor
            : Kind.Equals(TEXT("bench"), ESearchCase::IgnoreCase) ? EKind::Bench
            : Kind.Equals(TEXT("lean"), ESearchCase::IgnoreCase) ? EKind::Lean
            : Kind.Equals(TEXT("smoke"), ESearchCase::IgnoreCase) ? EKind::Smoke : EKind::Chat;
        Spot.Place = FName(*Place);
        Object->TryGetBoolField(TEXT("pinned"), Spot.bPinned);
        double X = 0.0, Y = 0.0, Z = 0.0, Yaw = 0.0, Slots = Spot.Kind == EKind::Chat ? 3.0 : 1.0;
        Object->TryGetNumberField(TEXT("x"), X);
        Object->TryGetNumberField(TEXT("y"), Y);
        Object->TryGetNumberField(TEXT("z"), Z);
        Object->TryGetNumberField(TEXT("yaw"), Yaw);
        Object->TryGetNumberField(TEXT("slots"), Slots);
        double SearchM = 0.0;
        if (Object->TryGetNumberField(TEXT("search_m"), SearchM)) Spot.Search = static_cast<float>(FMath::Clamp(SearchM, 0.5, 40.0) * 100.0);
        Spot.Location = FVector(X, Y, Z);
        Spot.Yaw = static_cast<float>(Yaw);
        const int32 MaxSlots = Spot.Kind == EKind::Chat ? 4 : (Spot.Kind == EKind::Window || Spot.Kind == EKind::Bench) ? 2 : 1;
        Spot.SlotCount = FMath::Clamp(static_cast<int32>(Slots), 1, MaxSlots);
        Spots.Add(Spot);
    }
    UE_LOG(LogReflectionsCrowdSpots, Log, TEXT("Crowd spots: %d street scenes from %s."), Spots.Num(), *Path);
}

bool UReflectionsCrowdSpotSubsystem::FindStreetFloor(const FVector& Near, float SearchRadius, FVector& OutFloor) const
{
    // The street is the lowest outdoor floor round the point (roofs are higher), sampled on a small grid.
    UWorld* World = GetWorld();
    FCollisionQueryParams Params(SCENE_QUERY_STAT(CrowdSpotFloor), false);
    FCollisionObjectQueryParams Solid(ECC_WorldStatic);
    Solid.AddObjectTypesToQuery(ECC_WorldDynamic);
    bool bFound = false;
    for (int32 Ring = 0; Ring <= 3; ++Ring)
    {
        const float Step = SearchRadius * Ring / 3.0f;
        for (int32 Index = 0; Index < (Ring == 0 ? 1 : 8); ++Index)
        {
            const float Angle = Index * PI / 4.0f;
            const FVector At = Near + FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0.0f) * Step;
            FHitResult Hit;
            if (!World->LineTraceSingleByObjectType(Hit, FVector(At.X, At.Y, Near.Z + 15000.0f), FVector(At.X, At.Y, Near.Z - 5000.0f), Solid, Params)) continue;
            if (Hit.ImpactNormal.Z < 0.8f || !HasRoom(Hit.ImpactPoint)) continue;
            if (!bFound || Hit.ImpactPoint.Z < OutFloor.Z - 50.0f)
            {
                OutFloor = Hit.ImpactPoint;
                bFound = true;
            }
        }
        if (bFound && Ring == 0) return true;
    }
    return bFound;
}

bool UReflectionsCrowdSpotSubsystem::HasRoom(const FVector& Floor) const
{
    FCollisionQueryParams Params(SCENE_QUERY_STAT(CrowdSpotRoom), false);
    FCollisionObjectQueryParams Solid(ECC_WorldStatic);
    Solid.AddObjectTypesToQuery(ECC_WorldDynamic);
    return !GetWorld()->OverlapAnyTestByObjectType(Floor + FVector(0.0, 0.0, 92.0), FQuat::Identity, Solid,
        FCollisionShape::MakeCapsule(38.0f, 88.0f), Params);
}

bool UReflectionsCrowdSpotSubsystem::FindBenchSeats(FSpot& Spot) const
{
    // A bench of the map near the spot: any static mesh (or instance) whose mesh is named like a bench.
    UWorld* World = GetWorld();
    TArray<FOverlapResult> Overlaps;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(CrowdSpotBench), false);
    FCollisionObjectQueryParams Solid(ECC_WorldStatic);
    Solid.AddObjectTypesToQuery(ECC_WorldDynamic);
    World->OverlapMultiByObjectType(Overlaps, Spot.Location, FQuat::Identity, Solid,
        FCollisionShape::MakeSphere(Spot.Search > 0.0f ? Spot.Search : 1500.0f), Params);
    const UStaticMeshComponent* Best = nullptr;
    FTransform BestTransform;
    double BestDistance = TNumericLimits<double>::Max();
    for (const FOverlapResult& Overlap : Overlaps)
    {
        const UStaticMeshComponent* Mesh = Cast<UStaticMeshComponent>(Overlap.GetComponent());
        const UStaticMesh* Asset = Mesh ? Mesh->GetStaticMesh() : nullptr;
        if (!Asset || !Asset->GetName().Contains(TEXT("bench"), ESearchCase::IgnoreCase)) continue;
        FTransform Transform = Mesh->GetComponentTransform();
        if (const UInstancedStaticMeshComponent* Instances = Cast<UInstancedStaticMeshComponent>(Mesh))
        {
            if (!Instances->GetInstanceTransform(Overlap.ItemIndex, Transform, true)) continue;
        }
        const double Distance = FVector::Dist2D(Transform.GetLocation(), Spot.Location);
        if (Distance < BestDistance)
        {
            Best = Mesh;
            BestTransform = Transform;
            BestDistance = Distance;
        }
    }
    if (!Best) return false;
    const FBox Local = Best->GetStaticMesh()->GetBoundingBox();
    const FVector Extent = Local.GetExtent() * BestTransform.GetScale3D().GetAbs();
    const FVector Centre = BestTransform.TransformPosition(Local.GetCenter());
    // The bench runs along its longer horizontal axis; people face across the shorter one, away from the backrest
    // (the side whose top is higher).
    const bool bAlongX = Extent.X >= Extent.Y;
    const FVector Along = BestTransform.GetUnitAxis(bAlongX ? EAxis::X : EAxis::Y).GetSafeNormal2D();
    const FVector Across = BestTransform.GetUnitAxis(bAlongX ? EAxis::Y : EAxis::X).GetSafeNormal2D();
    const float Depth = bAlongX ? Extent.Y : Extent.X;
    const float Length = bAlongX ? Extent.X : Extent.Y;
    const float Top = Centre.Z + Extent.Z + 50.0f;
    auto TopAt = [&](const FVector& At)
    {
        FHitResult Hit;
        return World->LineTraceSingleByObjectType(Hit, FVector(At.X, At.Y, Top), FVector(At.X, At.Y, Centre.Z - Extent.Z - 20.0f), Solid, Params)
            ? Hit.ImpactPoint.Z : Centre.Z;
    };
    const double FrontTop = TopAt(Centre + Across * Depth * 0.7f);
    const double BackTop = TopAt(Centre - Across * Depth * 0.7f);
    const FVector Facing = FrontTop >= BackTop ? -Across : Across; // away from the higher (back) side
    const float Floor = Centre.Z - Extent.Z;
    const float Yaw = Facing.Rotation().Yaw;
    Spot.Slots.Reset();
    const int32 Seats = Length > 60.0f ? Spot.SlotCount : 1;
    for (int32 Index = 0; Index < Seats; ++Index)
    {
        FSlot Slot;
        const float Offset = Seats > 1 ? (Index == 0 ? -1.0f : 1.0f) * Length * 0.45f : 0.0f;
        const FVector Seat = Centre + Along * Offset + Facing * CVarSpotsSeatForward.GetValueOnGameThread();
        Slot.Position = FVector(Seat.X, Seat.Y, Floor);
        Slot.Yaw = Yaw;
        Slot.Approach = Slot.Position + Facing * (Depth + 55.0f);
        FVector ApproachFloor;
        if (FindStreetFloor(Slot.Approach, 40.0f, ApproachFloor)) Slot.Approach = ApproachFloor;
        Spot.Slots.Add(Slot);
    }
    Spot.Location = Centre;
    return !Spot.Slots.IsEmpty();
}

bool UReflectionsCrowdSpotSubsystem::FindLeanPlace(const FVector& Floor, float Reach, FVector& OutRoot, float& OutYaw) const
{
    // The nearest wall round the point at shoulder height; stand 40 cm off it, wall on the left.
    UWorld* World = GetWorld();
    FCollisionQueryParams Params(SCENE_QUERY_STAT(CrowdSpotWall), false);
    FCollisionObjectQueryParams Solid(ECC_WorldStatic);
    const FVector Shoulder = Floor + FVector(0.0, 0.0, 130.0);
    bool bFound = false;
    double BestDistance = TNumericLimits<double>::Max();
    for (int32 Index = 0; Index < 16; ++Index)
    {
        const FVector Dir = FRotator(0.0f, Index * 22.5f, 0.0f).Vector();
        FHitResult Hit;
        if (!World->LineTraceSingleByObjectType(Hit, Shoulder, Shoulder + Dir * Reach, Solid, Params)) continue;
        if (FMath::Abs(Hit.ImpactNormal.Z) > 0.3f || Hit.Distance >= BestDistance) continue;
        const FVector Normal = Hit.ImpactNormal.GetSafeNormal2D();
        const FVector Root = FVector(Hit.ImpactPoint.X, Hit.ImpactPoint.Y, Floor.Z) + Normal * 40.0f;
        if (!HasRoom(Root)) continue;
        BestDistance = Hit.Distance;
        OutRoot = Root;
        // Right vector of yaw t is (-sin t, cos t): with the wall on the left, right points away from it (= normal).
        OutYaw = FMath::RadiansToDegrees(FMath::Atan2(-Normal.X, Normal.Y));
        bFound = true;
    }
    return bFound;
}

bool UReflectionsCrowdSpotSubsystem::CheckSpot(FSpot& Spot) const
{
    Spot.bChecked = true;
    if (Spot.Kind == EKind::Bench) return FindBenchSeats(Spot);
    // Positions come from map coordinates, not from the map itself: look up to 8 m round them for open street floor.
    FVector Centre;
    if (!FindStreetFloor(Spot.Location, Spot.Kind != EKind::Lean && Spot.Search > 0.0f ? Spot.Search : 800.0f, Centre)) return false;
    Spot.Location = Centre;
    Spot.Slots.Reset();
    if (Spot.Kind == EKind::Lean)
    {
        FSlot Slot;
        if (!FindLeanPlace(Centre, Spot.Search > 0.0f ? Spot.Search : 250.0f, Slot.Position, Slot.Yaw)) return false;
        Slot.Approach = Slot.Position;
        Spot.Slots.Add(Slot);
        return true;
    }
    const FRotator Facing(0.0f, Spot.Yaw, 0.0f);
    for (int32 Index = 0; Index < Spot.SlotCount; ++Index)
    {
        FSlot Slot;
        if (Spot.Kind == EKind::Chat)
        {
            // A small ring, everyone facing the middle.
            const float Angle = Spot.Yaw + 360.0f * Index / Spot.SlotCount;
            const FVector Out = FRotator(0.0f, Angle, 0.0f).Vector();
            Slot.Position = Centre + Out * 85.0f;
            Slot.Yaw = (-Out).Rotation().Yaw;
        }
        else
        {
            // Side by side, facing the window or the street.
            const float Offset = (Index - (Spot.SlotCount - 1) * 0.5f) * 90.0f;
            Slot.Position = Centre + FRotationMatrix(Facing).GetUnitAxis(EAxis::Y) * Offset;
            Slot.Yaw = Spot.Yaw;
        }
        FVector SlotFloor;
        if (!FindStreetFloor(Slot.Position, 60.0f, SlotFloor) || FMath::Abs(SlotFloor.Z - Centre.Z) > 60.0f) continue;
        Slot.Position = SlotFloor;
        Slot.Approach = SlotFloor;
        Spot.Slots.Add(Slot);
    }
    return Spot.Kind == EKind::Chat ? Spot.Slots.Num() >= 2 : Spot.Slots.Num() >= 1;
}

bool UReflectionsCrowdSpotSubsystem::IsSeen(const FVector& Location) const
{
    const APlayerController* Controller = UGameplayStatics::GetPlayerController(this, 0);
    const APlayerCameraManager* Camera = Controller ? Controller->PlayerCameraManager.Get() : nullptr;
    if (!Camera) return false;
    const FVector Eye = Camera->GetCameraLocation();
    const FVector Head = Location + FVector(0.0, 0.0, 120.0);
    const FVector To = Head - Eye;
    const double Distance = To.Size();
    if (Distance > 6000.0) return false;
    if (Distance < 1.0) return true;
    if (FVector::DotProduct(To / Distance, Camera->GetCameraRotation().Vector()) < FMath::Cos(FMath::DegreesToRadians(65.0))) return false;
    FHitResult Hit;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(CrowdSpotSight), false, Controller->GetPawn());
    return !GetWorld()->LineTraceSingleByChannel(Hit, Eye, Head, ECC_Visibility, Params);
}

bool UReflectionsCrowdSpotSubsystem::IsClaimed(const AActor* Actor) const
{
    for (const FSpot& Spot : Spots)
        for (const FSlot& Slot : Spot.Slots)
            if (Slot.Occupant.Get() == Actor) return true;
    return false;
}

int32 UReflectionsCrowdSpotSubsystem::GetOccupiedCount() const
{
    int32 Count = 0;
    for (const FSpot& Spot : Spots)
        for (const FSlot& Slot : Spot.Slots)
            if (Slot.Phase == EPhase::Holding && Slot.Occupant.IsValid()) ++Count;
    return Count;
}

void UReflectionsCrowdSpotSubsystem::RestoreCollision(FSlot& Slot) const
{
    if (!Slot.bCollisionOff) return;
    Slot.bCollisionOff = false;
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    const UReflectionsNpcReactionComponent* Brain = Slot.Occupant.IsValid() && Npcs ? Npcs->FindNpc(Slot.Occupant.Get()) : nullptr;
    if (ACharacter* Driver = Brain ? Brain->GetLocomotionDriver() : nullptr)
        if (UCapsuleComponent* Capsule = Driver->GetCapsuleComponent()) Capsule->SetCollisionEnabled(Slot.PreviousCollision);
}

void UReflectionsCrowdSpotSubsystem::FinishRelease(FSlot& Slot, double Now, bool bDestroySpawned)
{
    if (Slot.Phase == EPhase::Free) return;
    RestoreCollision(Slot);
    // Free the slot first: ending the scene below fires OnNpcSceneEnded, which must find nothing left to release.
    const FSlot Was = Slot;
    Slot = FSlot();
    Slot.Position = Was.Position;
    Slot.Approach = Was.Approach;
    Slot.Yaw = Was.Yaw;
    Slot.FreeAfter = Now + FMath::FRandRange(4.0f, 12.0f);

    AActor* Actor = Was.Occupant.Get();
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    UReflectionsNpcReactionComponent* Brain = Actor && Npcs ? Npcs->FindNpc(Actor) : nullptr;
    if (Brain && Npcs->IsNpcInScene(Actor)) Npcs->EndNpcScene(Actor, 0.25f);
    if (Brain && Was.bSteered && Brain->IsExternallySteered()) Brain->SetExternallySteered(false);
    if (Actor)
    {
        if (Was.bSpawned && bDestroySpawned)
        {
            Actor->Destroy();
        }
        else
        {
            if (Was.bAddedNoStroll) Actor->Tags.Remove(NoStrollTag);
            Actor->Tags.Remove(SpotTag);
        }
    }
    if (Was.bSpawned) PinnedAlive = FMath::Max(0, PinnedAlive - 1);
}

void UReflectionsCrowdSpotSubsystem::Release(FSpot& Spot, FSlot& Slot, double Now, bool bDestroySpawned, bool bGently)
{
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    AActor* Actor = Slot.Occupant.Get();
    // A seated person stands up first (the scene ends with the stand-up); the rest of the release follows.
    if (bGently && Actor && Npcs && Slot.Phase == EPhase::Holding && Spot.Kind == EKind::Bench && Npcs->IsNpcInScene(Actor)
        && Npcs->PlayNpcSceneClip(Actor, Clip(BenchStandUp), 0.2f, 0.25f, true))
    {
        Slot.Phase = EPhase::Leaving;
        Slot.PhaseSince = Now;
        return;
    }
    FinishRelease(Slot, Now, bDestroySpawned);
}

void UReflectionsCrowdSpotSubsystem::HandleSceneEnded(AActor* Npc, bool bDisturbed)
{
    // The NPC broke off its scene (a fright, a hit, death, a taking): free the slot now and give the body back.
    const double Now = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
    for (FSpot& Spot : Spots)
        for (FSlot& Slot : Spot.Slots)
            if (Slot.Occupant.Get() == Npc && Slot.Phase != EPhase::Free && (bDisturbed || Slot.Phase == EPhase::Leaving))
                FinishRelease(Slot, Now, !bDisturbed);
}

void UReflectionsCrowdSpotSubsystem::TryClaim(FSpot& Spot, FSlot& Slot, double Now)
{
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    if (!Npcs || FMath::FRand() > CVarSpotsClaimChance.GetValueOnGameThread()) return;
    const float Radius = CVarSpotsClaimRadius.GetValueOnGameThread();
    AActor* Best = nullptr;
    double BestDistance = Radius;
    for (AActor* Actor : Npcs->GetNpcActors())
    {
        if (!Actor || !Actor->ActorHasTag(RingTag) || Actor->ActorHasTag(NoStrollTag) || Actor->ActorHasTag(CarryTag) || IsClaimed(Actor)) continue;
        const double Distance = FVector::Dist2D(Actor->GetActorLocation(), Slot.Approach);
        if (Distance >= BestDistance || !IsUsable(Npcs->FindNpc(Actor)) || Npcs->IsNpcInScene(Actor)) continue;
        Best = Actor;
        BestDistance = Distance;
    }
    if (!Best) return;
    // Ask the stroll to let go (it does on its next refresh), then take the body.
    Best->Tags.AddUnique(NoStrollTag);
    Best->Tags.AddUnique(SpotTag);
    Slot.Occupant = Best;
    Slot.bAddedNoStroll = true;
    Slot.Phase = EPhase::Claiming;
    Slot.PhaseSince = Now;
}

void UReflectionsCrowdSpotSubsystem::TrySpawnPinned(FSpot& Spot, FSlot& Slot, double Now)
{
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    if (!Npcs || PinnedAlive >= CVarSpotsMaxPinned.GetValueOnGameThread() || IsSeen(Slot.Position)) return;
    AActor* Npc = Npcs->SpawnNpc(FName(*CVarSpotsArchetype.GetValueOnGameThread()), Slot.Approach + FVector(0.0, 0.0, 2.0), Slot.Yaw, nullptr);
    if (!Npc) return;
    // Stays at its spot: not a stroller, not a ring walker, not the villain's.
    Npc->Tags.AddUnique(NoStrollTag);
    Npc->Tags.AddUnique(SpotTag);
    Npc->Tags.AddUnique(TEXT("Friendly"));
    Npc->Tags.AddUnique(TEXT("NoVillain"));
    Slot.Occupant = Npc;
    Slot.bSpawned = true;
    Slot.Phase = EPhase::Claiming;
    Slot.PhaseSince = Now;
    ++PinnedAlive;
}

void UReflectionsCrowdSpotSubsystem::Settle(FSpot& Spot, FSlot& Slot, ACharacter* Driver, double Now)
{
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    AActor* Actor = Slot.Occupant.Get();
    UCapsuleComponent* Capsule = Driver->GetCapsuleComponent();
    const float HalfHeight = Capsule ? Capsule->GetScaledCapsuleHalfHeight() : 90.0f;
    const bool bPinned = Spot.Kind == EKind::Bench || Spot.Kind == EKind::Lean || Spot.Kind == EKind::Smoke;
    // Seated and leaning people go exactly onto their place; a seated one's capsule stops colliding with the bench.
    if (Spot.Kind == EKind::Bench && Capsule)
    {
        Slot.PreviousCollision = Capsule->GetCollisionEnabled();
        Capsule->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Slot.bCollisionOff = true;
    }
    if (bPinned)
    {
        Driver->SetActorLocationAndRotation(Slot.Position + FVector(0.0, 0.0, HalfHeight + 2.0), FRotator(0.0f, Slot.Yaw, 0.0f),
            false, nullptr, ETeleportType::TeleportPhysics);
    }
    else
    {
        Driver->SetActorRotation(FRotator(0.0f, Slot.Yaw, 0.0f));
    }
    const TCHAR* LoopPath = Spot.Kind == EKind::Bench ? BenchIdleLoop : Spot.Kind == EKind::Lean ? LeanLoop
        : Spot.Kind == EKind::Smoke ? SmokeLoop : RelaxedIdleLoop;
    if (!Npcs || !Npcs->BeginNpcScene(Actor, Clip(LoopPath), bPinned, Spot.Kind == EKind::Bench ? 0.6f : 0.35f))
    {
        FinishRelease(Slot, Now, true);
        return;
    }
    Slot.Phase = EPhase::Holding;
    Slot.PhaseSince = Now;
    Slot.LeaveAt = Slot.bSpawned ? 0.0 : Now + (Spot.Kind == EKind::Bench ? FMath::FRandRange(35.0f, 70.0f) : FMath::FRandRange(20.0f, 45.0f));
    Slot.NextBreakAt = Now + FMath::FRandRange(2.0f, 7.0f);
}

void UReflectionsCrowdSpotSubsystem::TickSlot(FSpot& Spot, FSlot& Slot, double Now)
{
    if (Slot.Phase == EPhase::Free) return;
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    AActor* Actor = Slot.Occupant.Get();
    UReflectionsNpcReactionComponent* Brain = Actor && Npcs ? Npcs->FindNpc(Actor) : nullptr;
    if (Slot.Phase == EPhase::Leaving)
    {
        // Standing up; the scene ends with the clip (HandleSceneEnded), or give up after 4 s.
        if (!Actor || !Npcs || !Npcs->IsNpcInScene(Actor) || Now - Slot.PhaseSince > 4.0) FinishRelease(Slot, Now, true);
        return;
    }
    // Any reaction, death, conversion or removal ends the scene at once: the NPC system has the body.
    if (!IsUsable(Brain))
    {
        FinishRelease(Slot, Now, false);
        return;
    }
    ACharacter* Driver = Brain->GetLocomotionDriver();
    if (Slot.Phase == EPhase::Claiming)
    {
        // Wait for the walker (the stroll lets go within a second; a fresh occupant needs its walker first).
        if (!Driver || Brain->IsExternallySteered())
        {
            if (Now - Slot.PhaseSince > 4.0) FinishRelease(Slot, Now, true);
            return;
        }
        Brain->SetExternallySteered(true);
        Slot.bSteered = true;
        SetWalkGait(Driver, true);
        Slot.Phase = EPhase::Approaching;
        Slot.PhaseSince = Now;
        return;
    }
    if (!Driver)
    {
        FinishRelease(Slot, Now, true);
        return;
    }
    if (Slot.Phase == EPhase::Approaching)
    {
        const FVector Here = Driver->GetActorLocation();
        const FVector To(Slot.Approach.X - Here.X, Slot.Approach.Y - Here.Y, 0.0f);
        const float Distance = To.Size();
        if (Distance < ArriveRadius)
        {
            Settle(Spot, Slot, Driver, Now);
            return;
        }
        if (Now - Slot.PhaseSince > 15.0)
        {
            FinishRelease(Slot, Now, true);
            return;
        }
        if (UCharacterMovementComponent* Movement = Driver->GetCharacterMovement())
        {
            const float Scale = FMath::Clamp(140.0f * FMath::GetMappedRangeValueClamped(FVector2f(30.0f, 120.0f), FVector2f(0.4f, 1.0f), Distance)
                / FMath::Max(1.0f, Movement->GetMaxSpeed()), 0.1f, 1.0f);
            Driver->AddMovementInput(To / Distance, Scale, true);
        }
        return;
    }
    // Holding: a gesture or an idle break now and then; claimed people move on after a while.
    if (Now >= Slot.NextBreakAt && Npcs)
    {
        const TCHAR* Path = nullptr;
        if (Spot.Kind == EKind::Chat) Path = FMath::FRand() < 0.6f ? ChatGesture : IdleBreaks[FMath::RandRange(0, UE_ARRAY_COUNT(IdleBreaks) - 1)];
        else if (Spot.Kind == EKind::Vendor) Path = FMath::FRand() < 0.6f ? VendorCall : IdleBreaks[FMath::RandRange(0, UE_ARRAY_COUNT(IdleBreaks) - 1)];
        else if (Spot.Kind == EKind::Window) Path = IdleBreaks[FMath::RandRange(0, UE_ARRAY_COUNT(IdleBreaks) - 1)];
        if (Path) Npcs->PlayNpcSceneClip(Actor, Clip(Path), 0.25f, 0.25f, false);
        Slot.NextBreakAt = Now + (Spot.Kind == EKind::Window ? FMath::FRandRange(7.0f, 16.0f) : FMath::FRandRange(4.5f, 9.0f));
    }
    if (!Slot.bSpawned && Slot.LeaveAt > 0.0 && Now >= Slot.LeaveAt) Release(Spot, Slot, Now, false, true);
}

void UReflectionsCrowdSpotSubsystem::TickSpot(FSpot& Spot, const FVector& Hero, double Now)
{
    const double Distance = FVector::Dist2D(Spot.Location, Hero);
    const float Activate = CVarSpotsActivate.GetValueOnGameThread();
    const float Deactivate = FMath::Max(Activate + 500.0f, CVarSpotsDeactivate.GetValueOnGameThread());
    if (!Spot.bActive && Distance < Activate)
    {
        if (!Spot.bChecked)
        {
            Spot.bValid = CheckSpot(Spot);
            if (!Spot.bValid) UE_LOG(LogReflectionsCrowdSpots, Warning, TEXT("Crowd spots: %s found no %s near it; skipped."), *Spot.Name.ToString(),
                Spot.Kind == EKind::Bench ? TEXT("bench") : Spot.Kind == EKind::Lean ? TEXT("wall") : TEXT("clear street floor"));
        }
        Spot.bActive = Spot.bValid;
    }
    if (!Spot.bActive) return;
    if (Distance > Deactivate)
    {
        // Far behind the hero: claimed walkers go back to strolling; pinned ones leave once nobody sees them.
        bool bAnyLeft = false;
        for (FSlot& Slot : Spot.Slots)
        {
            if (Slot.Phase == EPhase::Free) continue;
            if (Slot.bSpawned && Slot.Occupant.IsValid() && IsSeen(Slot.Occupant->GetActorLocation())) { bAnyLeft = true; continue; }
            FinishRelease(Slot, Now, true);
        }
        Spot.bActive = bAnyLeft;
        return;
    }
    for (FSlot& Slot : Spot.Slots)
    {
        TickSlot(Spot, Slot, Now);
        if (Slot.Phase == EPhase::Free && Now >= Slot.FreeAfter)
        {
            if (Spot.bPinned) TrySpawnPinned(Spot, Slot, Now);
            else TryClaim(Spot, Slot, Now);
        }
    }
    // A chat ring with two or more people talks (the chat director picks a conversation for the place).
    if (Spot.Kind == EKind::Chat && Now >= Spot.NextChatAt)
    {
        TArray<AActor*> Here;
        for (const FSlot& Slot : Spot.Slots)
            if (Slot.Phase == EPhase::Holding)
                if (AActor* Actor = Slot.Occupant.Get()) Here.Add(Actor);
        if (Here.Num() >= 2)
        {
            UReflectionsCrowdChatSubsystem* Chat = GetWorld()->GetSubsystem<UReflectionsCrowdChatSubsystem>();
            const bool bTalking = Chat && Chat->IsInConversation(Here[0]);
            if (Chat && !bTalking) Chat->PlayConversationBetween(Here, Spot.Place);
            Spot.NextChatAt = Now + (bTalking ? 2.0 : 8.0);
        }
    }
}

void UReflectionsCrowdSpotSubsystem::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    UWorld* World = GetWorld();
    if (!World || !World->HasBegunPlay() || Spots.IsEmpty()) return;
    const double Now = World->GetTimeSeconds();
    if (Now < NextTick) return;
    NextTick = Now + TickPeriod;
    SCOPE_CYCLE_COUNTER(STAT_ReflectionsCrowdSpots);

    if (CVarSpotsEnable.GetValueOnGameThread() == 0)
    {
        for (FSpot& Spot : Spots)
        {
            for (FSlot& Slot : Spot.Slots)
                if (Slot.Phase != EPhase::Free) FinishRelease(Slot, Now, true);
            Spot.bActive = false;
        }
        return;
    }
    const APawn* Hero = UGameplayStatics::GetPlayerPawn(this, 0);
    if (!Hero) return;
    const FVector HeroLocation = Hero->GetActorLocation();
    for (FSpot& Spot : Spots) TickSpot(Spot, HeroLocation, Now);
}

FString UReflectionsCrowdSpotSubsystem::Describe() const
{
    static const TCHAR* Kinds[] = { TEXT("chat"), TEXT("window"), TEXT("vendor"), TEXT("bench"), TEXT("lean"), TEXT("smoke") };
    static const TCHAR* Phases[] = { TEXT("free"), TEXT("claiming"), TEXT("approaching"), TEXT("holding"), TEXT("leaving") };
    FString Text = FString::Printf(TEXT("Crowd spots: %d loaded, %d people at spots, %d pinned alive, enabled %d"),
        Spots.Num(), GetOccupiedCount(), PinnedAlive, CVarSpotsEnable.GetValueOnGameThread());
    for (const FSpot& Spot : Spots)
    {
        Text += FString::Printf(TEXT("\n  %s (%s%s): %s"), *Spot.Name.ToString(), Kinds[static_cast<int32>(Spot.Kind)],
            Spot.bPinned ? TEXT(", pinned") : TEXT(""), !Spot.bChecked ? TEXT("not checked yet") : !Spot.bValid ? TEXT("skipped")
            : Spot.bActive ? TEXT("active") : TEXT("idle"));
        for (const FSlot& Slot : Spot.Slots)
        {
            Text += FString::Printf(TEXT(" [%s%s%s]"), Phases[static_cast<int32>(Slot.Phase)], Slot.Occupant.IsValid() ? TEXT(" ") : TEXT(""),
                Slot.Occupant.IsValid() ? *Slot.Occupant->GetName() : TEXT(""));
        }
    }
    return Text;
}
