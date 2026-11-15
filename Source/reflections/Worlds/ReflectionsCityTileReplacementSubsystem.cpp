#include "Worlds/ReflectionsCityTileReplacementSubsystem.h"

#include "Components/StaticMeshComponent.h"
#include "Containers/ArrayView.h"
#include "Engine/Level.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"
#include "PhysicsEngine/BodyInstance.h"
#include "Stats/Stats.h"
#include "Templates/UnrealTemplate.h"
#include "UObject/Package.h"
#include "Worlds/ReflectionsCityTileReplacement.h"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsCityTileReplacement, Log, All);

namespace
{
    TAutoConsoleVariable<int32> CVarCityTileReplacementEnable(
        TEXT("GrayLondon.TileReplacement.Enable"),
        0,
        TEXT("Set to 1 before starting Gray London to enable the whole-building replacement pilot. ")
        TEXT("Read when the world begins play. Defaults to 0."),
        ECVF_Default);

    bool IsGrayLondon(const UWorld& World)
    {
        return World.PersistentLevel && UWorld::RemovePIEPrefix(World.PersistentLevel->GetOutermost()->GetName()) ==
            TEXT("/Game/GrayLondon/Maps/GrayLondon_Geodata");
    }

    bool MatchesSource(const AReflectionsCityTileReplacement& Replacement, const AStaticMeshActor& Source)
    {
        const UStaticMeshComponent* Component = Source.GetStaticMeshComponent();
        if (!IsValid(&Source) || !Source.IsActorInitialized() || Source.IsActorBeingDestroyed() ||
            Source.GetWorld() != Replacement.GetWorld() || !IsValid(Component) || !Component->IsRegistered() ||
            Component->IsBeingDestroyed() || Component->GetStaticMesh() != Replacement.SourceTileMesh.Get() ||
            !UReflectionsCityTileReplacementSubsystem::TransformsMatch(
                Component->GetComponentTransform(), Replacement.SourceTileWorldTransform))
        {
            return false;
        }
        TInlineComponentArray<UPrimitiveComponent*> Components;
        Source.GetComponents(Components);
        return Components.Num() == 1 && Components[0] == Component;
    }

    AStaticMeshActor* ResolveSource(const AReflectionsCityTileReplacement& Replacement,
        TConstArrayView<AStaticMeshActor*> Candidates)
    {
        AStaticMeshActor* Result = nullptr;
        for (AStaticMeshActor* Source : Candidates)
        {
            if (MatchesSource(Replacement, *Source))
            {
                if (Result)
                {
                    return nullptr;
                }
                Result = Source;
            }
        }
        return Result;
    }

    bool HasMatchingCollision(const UStaticMeshComponent& Component, const UStaticMeshComponent& Source)
    {
        const FBodyInstance* Body = Component.GetBodyInstance(NAME_None, false);
        const FBodyInstance* SourceBody = Source.GetBodyInstance(NAME_None, false);
        return Body && SourceBody && Body->GetCollisionEnabled(false) == SourceBody->GetCollisionEnabled(false) &&
            Component.GetCollisionObjectType() == Source.GetCollisionObjectType() &&
            Component.GetCollisionResponseToChannels() == Source.GetCollisionResponseToChannels() &&
            Component.CanEverAffectNavigation() == Source.CanEverAffectNavigation();
    }

    bool HasPhysicsBody(const UStaticMeshComponent& Component)
    {
        const FBodyInstance* Body = Component.GetBodyInstance(NAME_None, false);
        return Component.IsPhysicsStateCreated() && Body && Body->IsValidBodyInstance();
    }

    bool HasPreparedCollisions(const TArray<UStaticMeshComponent*>& Components, const UStaticMeshComponent& Source)
    {
        return !Components.ContainsByPredicate([&](const UStaticMeshComponent* Component)
        {
            return !HasPhysicsBody(*Component) || !HasMatchingCollision(*Component, Source);
        });
    }
}

UReflectionsCityTileReplacementSubsystem::EClaim UReflectionsCityTileReplacementSubsystem::EvaluateClaim(
    int32 ClaimCount, bool bAlreadyActive)
{
    if (ClaimCount != 1)
    {
        return EClaim::Retry;
    }
    return bAlreadyActive ? EClaim::KeepActive : EClaim::Activate;
}

bool UReflectionsCityTileReplacementSubsystem::TransformsMatch(const FTransform& First, const FTransform& Second)
{
    return !First.ContainsNaN() && !Second.ContainsNaN() &&
        First.GetLocation().Equals(Second.GetLocation(), 0.05) &&
        First.GetRotation().Equals(Second.GetRotation(), 0.00001) &&
        First.GetScale3D().Equals(Second.GetScale3D(), 0.00001);
}

bool UReflectionsCityTileReplacementSubsystem::DoesSupportWorldType(EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UReflectionsCityTileReplacementSubsystem::OnWorldBeginPlay(UWorld& World)
{
    Super::OnWorldBeginPlay(World);
    if (CVarCityTileReplacementEnable.GetValueOnGameThread() != 1 || !IsGrayLondon(World))
    {
        return;
    }
    bRunning = true;
    LevelAddedHandle = FWorldDelegates::LevelAddedToWorld.AddUObject(this, &ThisClass::HandleLevelAdded);
    PreLevelRemovedHandle = FWorldDelegates::PreLevelRemovedFromWorld.AddUObject(this, &ThisClass::HandlePreLevelRemoved);
    ActorSpawnedHandle = World.AddOnActorSpawnedHandler(
        FOnActorSpawned::FDelegate::CreateUObject(this, &ThisClass::HandleActorSpawned));
    Refresh();
}

void UReflectionsCityTileReplacementSubsystem::OnWorldEndPlay(UWorld& World)
{
    Stop();
    Super::OnWorldEndPlay(World);
}

void UReflectionsCityTileReplacementSubsystem::Deinitialize()
{
    Stop();
    Super::Deinitialize();
}

bool UReflectionsCityTileReplacementSubsystem::IsTickable() const
{
    return bRunning && Super::IsTickable();
}

TStatId UReflectionsCityTileReplacementSubsystem::GetStatId() const
{
    RETURN_QUICK_DECLARE_CYCLE_STAT(UReflectionsCityTileReplacementSubsystem, STATGROUP_Tickables);
}

void UReflectionsCityTileReplacementSubsystem::RequestRefresh()
{
    bNeedsRefresh = bRunning;
}

void UReflectionsCityTileReplacementSubsystem::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    RetryDelay -= DeltaSeconds;
    RestoreWhere([&](AReflectionsCityTileReplacement* Replacement, const FOriginalState& Original)
    {
        AStaticMeshActor* Source = Original.Actor.Get();
        TArray<UStaticMeshComponent*> Components;
        const bool bInvalid = !IsValid(Replacement) || !IsValid(Source) ||
            !CollectReadyPair(*Replacement, *Source, Components) ||
            !Source->IsHidden() || Source->GetActorEnableCollision() ||
            Replacement->IsHidden() != !Original.bReplacementRenders ||
            Replacement->GetActorEnableCollision() != Original.bReplacementCollides ||
            (Original.bReplacementCollides && !HasPreparedCollisions(Components, *Source->GetStaticMeshComponent()));
        if (bInvalid)
        {
            RequestRefresh();
        }
        return bInvalid;
    });
    if (bNeedsRefresh || (bUnpaired && RetryDelay <= 0))
    {
        Refresh();
    }
}

void UReflectionsCityTileReplacementSubsystem::HandleLevelAdded(ULevel* Level, UWorld* World)
{
    if (bRunning && World == GetWorld())
    {
        DepartingLevels.Remove(Level);
        Refresh();
    }
}

void UReflectionsCityTileReplacementSubsystem::HandlePreLevelRemoved(ULevel* Level, UWorld* World)
{
    if (!bRunning || World != GetWorld())
    {
        return;
    }
    if (Level)
    {
        DepartingLevels.Add(Level);
    }
    RestoreWhere([&](AReflectionsCityTileReplacement* Replacement, const FOriginalState& Original)
    {
        const AStaticMeshActor* Source = Original.Actor.Get();
        return !Level || !Replacement || !Source || Replacement->GetLevel() == Level || Source->GetLevel() == Level;
    });
    RequestRefresh();
}

void UReflectionsCityTileReplacementSubsystem::HandleActorSpawned(AActor* Actor)
{
    if (Actor->IsA<AStaticMeshActor>() || Actor->IsA<AReflectionsCityTileReplacement>())
    {
        // The spawn delegate can run before a deferred-spawn actor has its components.
        RequestRefresh();
    }
}

void UReflectionsCityTileReplacementSubsystem::HandleActorEndPlay(AActor* Actor, EEndPlayReason::Type Reason)
{
    RestoreWhere([&](AReflectionsCityTileReplacement* Replacement, const FOriginalState& Original)
    {
        return Replacement == Actor || Original.Actor.Get() == Actor;
    });
    RequestRefresh();
}

bool UReflectionsCityTileReplacementSubsystem::IsLoadedLevel(ULevel* Level) const
{
    return Level && Level->bIsVisible && !DepartingLevels.Contains(Level);
}

bool UReflectionsCityTileReplacementSubsystem::CollectReadyPair(AReflectionsCityTileReplacement& Replacement,
    AStaticMeshActor& Source, TArray<UStaticMeshComponent*>& Components) const
{
    return bRunning && IsValid(&Replacement) && IsValid(&Source) &&
        IsLoadedLevel(Replacement.GetLevel()) && IsLoadedLevel(Source.GetLevel()) &&
        MatchesSource(Replacement, Source) && Replacement.CollectReadyComponents(Components);
}

void UReflectionsCityTileReplacementSubsystem::Refresh()
{
    if (!bRunning || bRefreshing)
    {
        RequestRefresh();
        return;
    }
    TGuardValue<bool> Refreshing(bRefreshing, true);
    bNeedsRefresh = false;
    bUnpaired = false;
    RetryDelay = 0.25f;
    for (auto It = DepartingLevels.CreateIterator(); It; ++It)
    {
        if (!It->IsValid())
        {
            It.RemoveCurrent();
        }
    }

    TArray<AReflectionsCityTileReplacement*> Ready;
    TMap<const UStaticMesh*, TArray<AStaticMeshActor*>> Sources;
    for (TActorIterator<AReflectionsCityTileReplacement> It(GetWorld()); It; ++It)
    {
        AReflectionsCityTileReplacement* Replacement = *It;
        TArray<UStaticMeshComponent*> Components;
        if (!IsLoadedLevel(Replacement->GetLevel()))
        {
            continue;
        }
        if (Replacement->CollectReadyComponents(Components))
        {
            Sources.FindOrAdd(Replacement->SourceTileMesh.Get());
            Ready.Add(Replacement);
            continue;
        }
        bUnpaired = true;
    }

    if (!Sources.IsEmpty())
    {
        for (TActorIterator<AStaticMeshActor> It(GetWorld()); It; ++It)
        {
            AStaticMeshActor* Source = *It;
            const UStaticMeshComponent* Component = Source->GetStaticMeshComponent();
            if (Component && IsLoadedLevel(Source->GetLevel()))
            {
                if (TArray<AStaticMeshActor*>* Candidates = Sources.Find(Component->GetStaticMesh()))
                {
                    Candidates->Add(Source);
                }
            }
        }
    }
    TMap<AReflectionsCityTileReplacement*, AStaticMeshActor*> Desired;
    TMap<AStaticMeshActor*, int32> ClaimCounts;
    for (AReflectionsCityTileReplacement* Replacement : Ready)
    {
        if (AStaticMeshActor* Source = ResolveSource(*Replacement, Sources.FindChecked(Replacement->SourceTileMesh.Get())))
        {
            Desired.Add(Replacement, Source);
            ++ClaimCounts.FindOrAdd(Source);
        }
        else
        {
            bUnpaired = true;
        }
    }
    RestoreWhere([&](AReflectionsCityTileReplacement* Replacement, const FOriginalState& Original)
    {
        AStaticMeshActor* Source = Desired.FindRef(Replacement);
        return !Source || Source != Original.Actor.Get() || ClaimCounts.FindRef(Source) != 1;
    });
    for (const auto& Pair : Desired)
    {
        const EClaim Claim = EvaluateClaim(ClaimCounts.FindRef(Pair.Value), Active.Contains(Pair.Key));
        if (Claim == EClaim::Retry || (Claim == EClaim::Activate &&
            (!IsValid(Pair.Key) || !IsValid(Pair.Value) || !Activate(*Pair.Key, *Pair.Value))))
        {
            bUnpaired = true;
        }
    }
}

bool UReflectionsCityTileReplacementSubsystem::Activate(AReflectionsCityTileReplacement& Replacement, AStaticMeshActor& Source)
{
    TArray<UStaticMeshComponent*> Components;
    if (!CollectReadyPair(Replacement, Source, Components))
    {
        return false;
    }
    UStaticMeshComponent& SourceComponent = *Source.GetStaticMeshComponent();
    FOriginalState Original;
    Original.Actor = &Source;
    Original.bHidden = Source.IsHidden();
    Original.bCollisionEnabled = Source.GetActorEnableCollision();
    Original.bReplacementRenders = !Original.bHidden && SourceComponent.GetVisibleFlag() && !SourceComponent.bHiddenInGame;
    Original.bReplacementCollides =
        Original.bCollisionEnabled && SourceComponent.GetCollisionEnabled() != ECollisionEnabled::NoCollision;
    const bool bCollide = Original.bReplacementCollides;
    if (bCollide && Components.ContainsByPredicate(
        [&](const UStaticMeshComponent* Component) { return !HasMatchingCollision(*Component, SourceComponent); }))
    {
        return false;
    }

    // A hidden staged actor can lack physics bodies even after its components have registered.
    // Create and verify every body before removing the original collider.
    Replacement.SetReplacementActive(false, bCollide);
    if (!CollectReadyPair(Replacement, Source, Components))
    {
        Replacement.SetReplacementActive(false, false);
        return false;
    }
    if (bCollide)
    {
        for (UStaticMeshComponent* Component : Components)
        {
            if (IsValid(Component) && !HasPhysicsBody(*Component))
            {
                Component->RecreatePhysicsState();
            }
        }
    }
    const auto IsStagedPairReady = [&]()
    {
        return CollectReadyPair(Replacement, Source, Components) &&
            (!bCollide || HasPreparedCollisions(Components, *Source.GetStaticMeshComponent()));
    };
    if (!IsStagedPairReady())
    {
        Replacement.SetReplacementActive(false, false);
        return false;
    }

    Source.SetActorHiddenInGame(true);
    Source.SetActorEnableCollision(false);
    if (!Source.IsHidden() || Source.GetActorEnableCollision() || !IsStagedPairReady())
    {
        Restore(&Replacement, Original);
        return false;
    }
    Replacement.SetReplacementActive(Original.bReplacementRenders, bCollide);
    Active.Add(&Replacement, Original);
    Replacement.OnEndPlay.AddUniqueDynamic(this, &ThisClass::HandleActorEndPlay);
    Source.OnEndPlay.AddUniqueDynamic(this, &ThisClass::HandleActorEndPlay);
    UE_LOG(LogReflectionsCityTileReplacement, Log, TEXT("Activated %s for %s (%d whole buildings; collision %s)."),
        *Replacement.GetName(), *Source.GetName(), Replacement.RequiredBuildings.Num(), bCollide ? TEXT("on") : TEXT("off"));
    return true;
}

void UReflectionsCityTileReplacementSubsystem::Restore(
    AReflectionsCityTileReplacement* Replacement, const FOriginalState& Original)
{
    if (IsValid(Replacement))
    {
        Replacement->OnEndPlay.RemoveDynamic(this, &ThisClass::HandleActorEndPlay);
    }
    if (AStaticMeshActor* Source = Original.Actor.Get())
    {
        Source->OnEndPlay.RemoveDynamic(this, &ThisClass::HandleActorEndPlay);
        if (!Source->IsActorBeingDestroyed())
        {
            Source->SetActorHiddenInGame(Original.bHidden);
            Source->SetActorEnableCollision(Original.bCollisionEnabled);
        }
    }
    if (IsValid(Replacement))
    {
        Replacement->SetReplacementActive(false, false);
    }
}

void UReflectionsCityTileReplacementSubsystem::RestoreWhere(
    TFunctionRef<bool(AReflectionsCityTileReplacement*, const FOriginalState&)> Predicate)
{
    TArray<TPair<TWeakObjectPtr<AReflectionsCityTileReplacement>, FOriginalState>> Removed;
    for (auto It = Active.CreateIterator(); It; ++It)
    {
        if (Predicate(It.Key().Get(), It.Value()))
        {
            Removed.Emplace(It.Key(), It.Value());
            It.RemoveCurrent();
        }
    }
    for (const auto& Pair : Removed)
    {
        Restore(Pair.Key.Get(), Pair.Value);
    }
}

void UReflectionsCityTileReplacementSubsystem::Stop()
{
    if (!bRunning)
    {
        return;
    }
    bRunning = false;
    FWorldDelegates::LevelAddedToWorld.Remove(LevelAddedHandle);
    FWorldDelegates::PreLevelRemovedFromWorld.Remove(PreLevelRemovedHandle);
    if (UWorld* World = GetWorld())
    {
        World->RemoveOnActorSpawnedHandler(ActorSpawnedHandle);
    }
    RestoreWhere([](const AReflectionsCityTileReplacement*, const FOriginalState&) { return true; });
    DepartingLevels.Reset();
}
