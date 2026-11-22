#pragma once

#include "CoreMinimal.h"
#include "Components/DynamicMeshComponent.h"
#include "Digging/ReflectionsDigGrid.h"
#include "Digging/ReflectionsDigPieces.h"
#include "GameFramework/Actor.h"
#include "ReflectionsDigTerrain.generated.h"

class UBodySetup;
class UBoxComponent;
class UMaterialInterface;
struct FReflectionsDigMeshData;

/** The terrain's log. Its Verbose lines time each commit and swap (tests raise it to read them). */
DECLARE_LOG_CATEGORY_EXTERN(LogReflectionsDigTerrain, Log, All);

/**
 * The mesh component of one chunk piece. It knows whether its newest async collision cook is still running and how
 * its cooks ended: the engine keeps that queue protected, so this subclass watches RebuildPhysicsData and
 * FinishPhysicsAsyncCook.
 */
UCLASS(Transient)
class REFLECTIONS_API UReflectionsDigChunkComponent : public UDynamicMeshComponent
{
    GENERATED_BODY()

public:
    /** True from the start of a collision cook until the newest one has finished. */
    bool IsCollisionCookPending() const;

    /** True once a cook has succeeded: the component has collision of its own (perhaps older than its mesh). */
    bool HasCollision() const;

    /** True when the newest finished cook failed (the engine kept the previous body). */
    bool DidLastCookFail() const;

protected:
    virtual void RebuildPhysicsData() override;
    virtual void FinishPhysicsAsyncCook(bool bSuccess, UBodySetup* FinishedBodySetup) override;

private:
    /** The body setup of the newest cook still running, or null. */
    UPROPERTY(Transient)
    TObjectPtr<UBodySetup> PendingCook;

    bool bHasCollision = false;
    bool bLastCookFailed = false;
};

/** The mesh components of one chunk. */
USTRUCT()
struct FReflectionsDigTerrainChunk
{
    GENERATED_BODY()

    /** The chunk's current pieces, lowest slab first. Empty after the chunk's mesh became empty. */
    UPROPERTY(Transient)
    TArray<TObjectPtr<UReflectionsDigChunkComponent>> Pieces;

    /** The newest set that really collided before the current one: hidden, still colliding until the swap. */
    UPROPERTY(Transient)
    TArray<TObjectPtr<UReflectionsDigChunkComponent>> Retiring;

    /** A failed cook kept the retiring set; it has been reported. */
    bool bCookFailureReported = false;
};

/**
 * A diggable patch of ground. It owns the grid, one or more mesh components per chunk and a safety floor under the
 * grid; the dig subsystem decides what is meshed and when. The actor must be unrotated and unscaled: its X and Y are
 * the patch's minimum corner and the ground surface lies 400 cm below the top of the grid. One terrain per world.
 */
UCLASS()
class REFLECTIONS_API AReflectionsDigTerrain : public AActor
{
    GENERATED_BODY()

public:
    AReflectionsDigTerrain();

    UPROPERTY(EditAnywhere, Category = "Digging")
    FIntVector SizeInChunks = FIntVector(3, 3, 2);

    /** World Z of the ground surface. */
    UPROPERTY(EditAnywhere, Category = "Digging")
    float GroundHeightCm = 0.0f;

    /** With a focus, chunks whose box is farther than this from it are not meshed. */
    UPROPERTY(EditAnywhere, Category = "Digging")
    float MeshRadiusCm = 2400.0f;

    UPROPERTY(EditAnywhere, Category = "Digging")
    TObjectPtr<UMaterialInterface> GroundMaterial;

    /** Builds the mesh's pieces on the game thread, then commits them. For tests and tools; the subsystem builds on workers. */
    void CommitChunk(FIntVector Chunk, FReflectionsDigMeshData&& Mesh);

    /**
     * Shows a chunk's new pieces (positions relative to the grid origin). No pieces retires the chunk's set.
     * The chunk's previous collision stays until the new collision has finished cooking (see the collision swap
     * in the class's .cpp).
     */
    void CommitChunkPieces(FIntVector Chunk, FReflectionsDigChunkResult&& Result);

    /** Destroys the chunk's components at once, retiring ones included. */
    void ReleaseChunk(FIntVector Chunk);

    /** The chunk's first (lowest) current piece, or null. */
    UDynamicMeshComponent* FindChunkComponent(FIntVector Chunk) const;

    int32 GetChunkPieceCount(FIntVector Chunk) const;

    /** The chunk's retiring pieces: hidden, still colliding until their swap. */
    int32 GetRetiringPieceCount(FIntVector Chunk) const;

    /** Null before BeginPlay and after EndPlay. */
    FReflectionsDigGrid* GetGrid() const;

    /** The largest vertex count among every piece that still collides, retiring ones included; 0 with none. */
    int32 GetLargestCollisionVertexCount() const;

    /**
     * Destroys retiring sets whose time has come: one replaced by pieces once every piece has cooked successfully,
     * one replaced by nothing only when bTerrainQuiet (no task in flight, no queued commit, no cook pending anywhere).
     */
    void FinishCollisionSwaps(bool bTerrainQuiet);

    /** True while any of the chunk's current pieces has a collision cook running (the subsystem then holds its next commit). */
    bool IsChunkCooking(FIntVector Chunk) const;

    /** True while any piece, current or retiring, has a collision cook running. */
    bool HasCookPending() const;

    /** True while any cook runs or any retiring set still waits for its swap (a set kept by a failed cook does not wait). */
    bool IsWaitingOnCollision() const;

    /** The blocking box under the whole patch, its top 30 cm below the grid floor. */
    UBoxComponent* GetSafetyFloor() const;

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    UReflectionsDigChunkComponent* CreatePieceComponent();
    /** Moves the current set out of the way of a new one, keeping the newest set that really collides. */
    void RetireCurrentSet(FReflectionsDigTerrainChunk& State, double& InOutDestroySeconds);

    UPROPERTY(VisibleAnywhere, Category = "Digging")
    TObjectPtr<UBoxComponent> SafetyFloor;

    TUniquePtr<FReflectionsDigGrid> Grid;

    /** Rebuilt from the grid at run time, never saved. */
    UPROPERTY(Transient)
    TMap<FIntVector, FReflectionsDigTerrainChunk> Chunks;
};
