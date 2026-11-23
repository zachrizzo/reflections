#pragma once

#include "CoreMinimal.h"
#include "Containers/StaticArray.h"
#include "Digging/ReflectionsDigTypes.h"
#include "DynamicMesh/DynamicMesh3.h"

struct FReflectionsDigMeshData;

/**
 * The triangles one piece gives navigation, so navigation never has to read (and build) the piece's collision: its
 * vertices in the piece's local space and three indices per triangle into them.
 */
struct FReflectionsDigNavGeometry
{
    TArray<FVector> Vertices;
    TArray<int32> Indices;
};

/**
 * A chunk mesh built into the pieces the terrain shows, one slot per block (ReflectionsDig::BlocksPerChunk, block
 * index X + 2 * Y + 4 * Z, each 0 for the chunk's low half on that axis and 1 for the high half). Built on a worker.
 */
struct FReflectionsDigChunkResult
{
    /** Each block's piece; a block with no triangles has an empty mesh. */
    TStaticArray<UE::Geometry::FDynamicMesh3, ReflectionsDig::BlocksPerChunk> Pieces;
    /** Each piece's own triangles for navigation, built from the same triangles. */
    TStaticArray<FReflectionsDigNavGeometry, ReflectionsDig::BlocksPerChunk> NavGeometry;
    /** Each piece's hash (its positions, normals and triangles); 0 for a block with no triangles. */
    TStaticArray<uint64, ReflectionsDig::BlocksPerChunk> PieceHash{ InPlace, uint64(0) };
    int32 SourceVertexCount = 0;
    int32 SourceTriangleCount = 0;
    /** Source triangles no piece could take (FDynamicMesh3 refused them even with their own vertex copies). */
    int32 DroppedTriangles = 0;

    /** How many slots hold a piece. */
    REFLECTIONS_API int32 NumPieces() const;
};

/** Turns a chunk mesh into one piece per block. Pure (no statics, no UObjects): safe on any thread. */
namespace ReflectionsDigPieces
{
    /**
     * A triangle goes to the block that holds its centroid: the border between two blocks lies BlockCells cells past
     * ChunkLocalOriginCm (the chunk's local cell (0, 0, 0) relative to the grid origin, as in FReflectionsDigChunkSamples)
     * on each axis, and a centroid exactly on it goes to the high block. Each piece has its own copy of the vertices it
     * uses, with the mesher's per-vertex normals in its primary normal overlay; a block with no triangles makes no
     * piece. A triangle on an edge that already has two goes onto a second copy of its vertices (and, if that is full
     * too, onto copies of its own). PieceHash covers each piece's positions, normals and triangles in the mesher's
     * order, so the same input gives the same hash on any thread. Pieces are never split: a piece above
     * ReflectionsDig::MaxPieceVertices is logged as a warning. Out is reset first.
     */
    REFLECTIONS_API void Build(const FReflectionsDigMeshData& Mesh, const FVector3f& ChunkLocalOriginCm, FReflectionsDigChunkResult& Out);
}
