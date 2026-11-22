#pragma once

#include "CoreMinimal.h"
#include "Components/DynamicMeshComponent.h"
#include "Digging/ReflectionsDigGrid.h"
#include "GameFramework/Actor.h"
#include "ReflectionsDigTerrain.generated.h"

class UBodySetup;
class UMaterialInterface;
struct FReflectionsDigMeshData;

/**
 * The mesh component of one chunk piece. It knows whether its newest async collision cook is still running:
 * the engine keeps that queue protected, so this subclass watches RebuildPhysicsData and FinishPhysicsAsyncCook.
 */
UCLASS(Transient)
class REFLECTIONS_API UReflectionsDigChunkComponent : public UDynamicMeshComponent
{
    GENERATED_BODY()

public:
    /** Replaces the mesh and starts its collision cook. The current collision stays until the cook has finished. */
    void SetMeshAndCook(UE::Geometry::FDynamicMesh3&& NewMesh);

    /** True from the start of a collision cook until the newest one has finished. */
    bool IsCollisionCookPending() const;

protected:
    virtual void RebuildPhysicsData() override;
    virtual void FinishPhysicsAsyncCook(bool bSuccess, UBodySetup* FinishedBodySetup) override;

private:
    /** The body setup of the newest cook still running, or null. */
    UPROPERTY(Transient)
    TObjectPtr<UBodySetup> PendingCook;
};

/** The mesh components of one chunk. */
USTRUCT()
struct FReflectionsDigTerrainChunk
{
    GENERATED_BODY()

    /** The chunk's current pieces, lowest slab first. */
    UPROPERTY(Transient)
    TArray<TObjectPtr<UReflectionsDigChunkComponent>> Pieces;

    /** The pieces they replaced: hidden, still colliding until every current piece has finished its cook. */
    UPROPERTY(Transient)
    TArray<TObjectPtr<UReflectionsDigChunkComponent>> Retiring;
};

/**
 * A diggable patch of ground. It owns the grid and one or more mesh components per chunk; the dig subsystem
 * decides what is meshed and when. The actor must be unrotated and unscaled: its X and Y are the patch's
 * minimum corner and the ground surface lies 400 cm below the top of the grid. One terrain per world.
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

    /**
     * Shows a chunk's new mesh (positions relative to the grid origin). An empty mesh releases the chunk.
     * A mesh over ReflectionsDig::MaxPieceVertices vertices is split into horizontal slabs, one component each.
     * The chunk's previous collision stays until the new collision has finished cooking.
     */
    void CommitChunk(FIntVector Chunk, FReflectionsDigMeshData&& Mesh);

    /** Destroys the chunk's components at once. */
    void ReleaseChunk(FIntVector Chunk);

    /** The chunk's first (lowest) current piece, or null. */
    UDynamicMeshComponent* FindChunkComponent(FIntVector Chunk) const;

    int32 GetChunkPieceCount(FIntVector Chunk) const;

    /** Null before BeginPlay and after EndPlay. */
    FReflectionsDigGrid* GetGrid() const;

    /** The largest vertex count among the current pieces of every chunk; 0 with none. */
    int32 GetLargestCollisionVertexCount() const;

    /** Destroys each chunk's retiring pieces once all of its current pieces have finished their collision cook. */
    void FinishCollisionSwaps();

    /** True while any piece's collision cook runs or any chunk still has retiring pieces. */
    bool IsWaitingOnCollision() const;

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    UReflectionsDigChunkComponent* CreatePieceComponent();

    TUniquePtr<FReflectionsDigGrid> Grid;

    /** Rebuilt from the grid at run time, never saved. */
    UPROPERTY(Transient)
    TMap<FIntVector, FReflectionsDigTerrainChunk> Chunks;
};
