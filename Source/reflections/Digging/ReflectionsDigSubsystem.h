#pragma once

#include "CoreMinimal.h"
#include "Digging/ReflectionsDigTypes.h"
#include "Subsystems/WorldSubsystem.h"
#include "Tasks/Task.h"
#include "ReflectionsDigSubsystem.generated.h"

class AReflectionsDigTerrain;
class FReflectionsDigCommitQueue;
struct FHitResult;

/** Fired when HasTerrain()'s answer changes. */
DECLARE_MULTICAST_DELEGATE(FReflectionsDigTerrainRegisteredChanged);

/**
 * Runs the dig flow of the world's terrain: Dig stamps the grid at once and marks chunks dirty; each tick
 * streams chunks around the focus, commits up to reflections.Dig.MaxCommitsPerFrame finished chunks and
 * launches one worker task per dirty wanted chunk (at most one in flight per chunk) that meshes the chunk and
 * builds its pieces. Workers get a copy of the chunk's samples and a shared pointer to the commit queue, nothing else.
 */
UCLASS()
class REFLECTIONS_API UReflectionsDigSubsystem : public UTickableWorldSubsystem
{
    GENERATED_BODY()

public:
    /**
     * The only way anything digs. Remove digs a sphere away; Add fills it with topsoil. Returns false when no
     * terrain is registered or the stamp changed nothing.
     */
    bool Dig(FVector Center, float RadiusCm, EReflectionsDigMode Mode);

    /**
     * Digs (Remove) or fills (Add) a ReflectionsDig::StampRadiusCm sphere at the hit's impact point. Returns false when
     * no terrain is registered, when the hit is not a chunk piece of the registered terrain (its safety floor is not
     * ground) or when the stamp changed nothing.
     */
    bool TryStampAtHit(const FHitResult& Hit, EReflectionsDigMode Mode);

    /** True while a terrain is registered and has its grid. */
    bool HasTerrain() const;

    /** Fired when HasTerrain()'s answer changes: a terrain became the registered one, or its state was dropped. */
    FReflectionsDigTerrainRegisteredChanged OnTerrainRegisteredChanged;

    /** Called by the terrain in BeginPlay. A second terrain while one is registered is ignored with a warning. */
    void RegisterTerrain(AReflectionsDigTerrain* Terrain);

    /** Called by the terrain in EndPlay. Tasks still running finish into a queue nobody reads. */
    void UnregisterTerrain(AReflectionsDigTerrain* Terrain);

    /** Overrides the focus (normally the first local player's pawn); unset to go back to the pawn. */
    void SetFocusOverride(TOptional<FVector> Focus);

    /**
     * No task in flight, no queued commit, no wanted chunk dirty, and the terrain not waiting on collision: no cook
     * running and no retiring set still due for the swap check (one kept by a failed cook waits only until that check
     * has handled the failure).
     */
    bool IsIdle() const;

    int32 GetTasksInFlight() const;
    int32 GetQueuedCommits() const;
    /** Chunks committed in the last tick (results dropped for unwanted chunks do not count). */
    int32 GetCommitsLastTick() const;

    virtual void Deinitialize() override;
    virtual void Tick(float DeltaTime) override;
    virtual TStatId GetStatId() const override;

protected:
    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
    struct FChunkFlow
    {
        /** The grid changed (or the chunk came into range) since its last mesh task started. */
        bool bDirty = true;
        /** A mesh task was started since the chunk was last released. */
        bool bMeshRequested = false;
        /** Within the mesh radius of the focus at the last tick. */
        bool bWanted = true;
        /** The chunk's newest mesh task. */
        UE::Tasks::FTask Task;
    };

    TOptional<FVector> FindFocus() const;
    void UpdateStreaming(AReflectionsDigTerrain& Terrain);
    void CommitFinishedMeshes(AReflectionsDigTerrain& Terrain);
    void LaunchMeshTasks(AReflectionsDigTerrain& Terrain);
    /** Forgets the terrain; tasks still running move to DetachedTasks. */
    void DropTerrainState();
    /** Fires OnTerrainRegisteredChanged if HasTerrain()'s answer differs from the one last announced. */
    void AnnounceTerrainChange();

    /** HasTerrain()'s answer when OnTerrainRegisteredChanged last fired (false before the first). */
    bool bAnnouncedTerrain = false;
    TWeakObjectPtr<AReflectionsDigTerrain> RegisteredTerrain;
    TSharedPtr<FReflectionsDigCommitQueue, ESPMode::ThreadSafe> Queue;
    TMap<FIntVector, FChunkFlow> ChunkFlows;
    /** Tasks of a terrain that has gone; waited for in Deinitialize. */
    TArray<UE::Tasks::FTask> DetachedTasks;
    TOptional<FVector> FocusOverride;
    int32 CommitsLastTick = 0;
};
