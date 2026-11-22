#pragma once

#include "CoreMinimal.h"
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

/** A chunk mesh built into the pieces the terrain shows, one mesh component each. Built on a worker. */
struct FReflectionsDigChunkResult
{
    /** Lowest slab first. Empty when the chunk has no surface. */
    TArray<UE::Geometry::FDynamicMesh3> Pieces;
    /** Parallel to Pieces: each piece's own triangles for navigation, built from the same triangles. */
    TArray<FReflectionsDigNavGeometry> NavGeometry;
    int32 SourceVertexCount = 0;
    int32 SourceTriangleCount = 0;
    /** Source triangles no piece could take (FDynamicMesh3 refused them even with their own vertex copies). */
    int32 DroppedTriangles = 0;
};

/** Turns a chunk mesh into pieces under the collision limit. Pure (no statics, no UObjects): safe on any thread. */
namespace ReflectionsDigPieces
{
    /**
     * One piece when the mesh has at most ReflectionsDig::MaxPieceVertices vertices; otherwise the fewest
     * equal-height horizontal slabs (over the mesh's Z extent) for which every built piece holds at most
     * MaxPieceVertices vertices. A triangle goes to the slab that holds its centroid, each piece has its own copy
     * of the vertices it uses with the mesher's per-vertex normals in its primary normal overlay, and an empty
     * slab makes no piece. The limit is checked on the built pieces: a triangle on an edge that already has two
     * gets its own vertex copies, so a piece can hold a few more vertices than its slab. Out is reset first.
     * Each piece's navigation geometry (Out.NavGeometry) is built from the piece's own vertices and triangles.
     */
    REFLECTIONS_API void Build(const FReflectionsDigMeshData& Mesh, FReflectionsDigChunkResult& Out);

    /** The pieces (and their navigation geometry) of exactly NumSlabs slabs (at least 1), with no limit check. Build uses it; tests pin Build with it. */
    REFLECTIONS_API void BuildWithSlabs(const FReflectionsDigMeshData& Mesh, int32 NumSlabs, FReflectionsDigChunkResult& Out);
}
