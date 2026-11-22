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

    /**
     * The mesher's quad diagonal choice, exposed so tests can pin it. P00 is the vertex of the edge's own
     * cube, and P00, P10, P11, P01 go counter-clockwise around AirDirection (the unit direction along the
     * edge from solid to air). The split along P00-P11 emits triangles (P00, P11, P10) and (P00, P01, P11);
     * the split along P10-P01 emits (P00, P01, P10) and (P10, P01, P11). Returns true for P00-P11 when both
     * of its triangles face air (VectorUtil::Normal has a positive component along AirDirection) and the
     * other split's do not, or both qualify and P00-P11 is not longer; false for P10-P01 otherwise.
     */
    REFLECTIONS_API bool SplitsAlongOwnCubeDiagonal(const FVector3f& P00, const FVector3f& P10, const FVector3f& P11, const FVector3f& P01, const FVector3f& AirDirection);
}
