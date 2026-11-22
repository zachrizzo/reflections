#pragma once

#include "CoreMinimal.h"
#include "Digging/ReflectionsDigTypes.h"

class FReflectionsDigGrid;

/**
 * The triangle mesh of one chunk's ground surface. Positions, Normals and Materials have one entry
 * per vertex; Triangles has three vertex indices per triangle. Positions are in cm relative to the
 * grid origin. For every triangle (A, B, C), UE::Geometry::VectorUtil::Normal(A, B, C) and the
 * vertex normals point from solid toward air.
 */
struct REFLECTIONS_API FReflectionsDigMeshData
{
    TArray<FVector3f> Positions;
    TArray<FVector3f> Normals;
    TArray<int32> Triangles;
    TArray<uint8> Materials;

    /** Empties every array and keeps the allocations for the next build. */
    void Reset();
    bool IsEmpty() const;
};

/** Naive surface nets over the ground grid, one chunk at a time. */
namespace ReflectionsDigMesher
{
    /**
     * Meshes one chunk's sample copy. Pure (no statics, no UObjects): safe to call from any thread.
     * The chunk emits the quads of the lattice edges that start at local cells 0 to 31, so every
     * quad of the grid comes from exactly one chunk. Out is reset first.
     */
    REFLECTIONS_API void BuildFromSamples(const FReflectionsDigChunkSamples& Samples, FReflectionsDigMeshData& Out);

    /** Copies the chunk's samples from the grid, then calls BuildFromSamples. Game thread (it reads the grid). */
    REFLECTIONS_API void BuildChunk(const FReflectionsDigGrid& Grid, FIntVector Chunk, FReflectionsDigMeshData& Out);
}
