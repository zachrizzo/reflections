#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Subsystems/WorldSubsystem.h"
#include "ReflectionsCityTileReplacementSubsystem.generated.h"

class AReflectionsCityTileReplacement;
class AStaticMeshActor;
class ULevel;
class UStaticMeshComponent;

/** Pairs loaded World Partition actors in Gray London without patching the shared map actor. */
UCLASS()
class REFLECTIONS_API UReflectionsCityTileReplacementSubsystem : public UTickableWorldSubsystem
{
    GENERATED_BODY()

public:
    enum class EClaim : uint8
    {
        Retry,
        Activate,
        KeepActive
    };

    void RequestRefresh();
    static bool TransformsMatch(const FTransform& First, const FTransform& Second);
    static EClaim EvaluateClaim(int32 ClaimCount, bool bAlreadyActive);

    virtual void OnWorldBeginPlay(UWorld& World) override;
    virtual void OnWorldEndPlay(UWorld& World) override;
    virtual void Deinitialize() override;
    virtual bool IsTickable() const override;
    virtual void Tick(float DeltaSeconds) override;
    virtual TStatId GetStatId() const override;

protected:
    virtual bool DoesSupportWorldType(EWorldType::Type WorldType) const override;

private:
    struct FOriginalState
    {
        TWeakObjectPtr<AStaticMeshActor> Actor;
        bool bHidden = false;
        bool bCollisionEnabled = false;
        bool bReplacementRenders = false;
        bool bReplacementCollides = false;
    };

    void HandleLevelAdded(ULevel* Level, UWorld* World);
    void HandlePreLevelRemoved(ULevel* Level, UWorld* World);
    void HandleActorSpawned(AActor* Actor);

    UFUNCTION()
    void HandleActorEndPlay(AActor* Actor, EEndPlayReason::Type Reason);

    void Refresh();
    bool IsLoadedLevel(ULevel* Level) const;
    bool CollectReadyPair(AReflectionsCityTileReplacement& Replacement, AStaticMeshActor& Source,
        TArray<UStaticMeshComponent*>& Components) const;
    bool Activate(AReflectionsCityTileReplacement& Replacement, AStaticMeshActor& Source);
    void Restore(AReflectionsCityTileReplacement* Replacement, const FOriginalState& Original);
    void RestoreWhere(TFunctionRef<bool(AReflectionsCityTileReplacement*, const FOriginalState&)> Predicate);
    void Stop();

    TMap<TWeakObjectPtr<AReflectionsCityTileReplacement>, FOriginalState> Active;
    TSet<TWeakObjectPtr<ULevel>> DepartingLevels;
    FDelegateHandle LevelAddedHandle;
    FDelegateHandle PreLevelRemovedHandle;
    FDelegateHandle ActorSpawnedHandle;
    float RetryDelay = 0;
    bool bRunning = false;
    bool bNeedsRefresh = false;
    bool bUnpaired = false;
    bool bRefreshing = false;
};
