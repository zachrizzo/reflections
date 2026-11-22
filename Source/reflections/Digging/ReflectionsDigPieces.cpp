#include "Digging/ReflectionsDigPieces.h"

#include "CoreMinimal.h"
#include "Digging/ReflectionsDigMesher.h"
#include "Digging/ReflectionsDigTypes.h"
#include "DynamicMesh/DynamicMesh3.h"
#include "DynamicMesh/DynamicMeshAttributeSet.h"
#include "IndexTypes.h"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsDigPieces, Log, All);

using UE::Geometry::FDynamicMesh3;
using UE::Geometry::FIndex3i;

namespace
{
    /**
     * More slabs than any chunk needs: a slab one cube layer thick holds at most about 3 * 34 * 34 vertices,
     * far under the limit, and 64 slabs are thinner than that. Reaching it would mean a broken mesh.
     */
    constexpr int32 MaxSlabs = 64;

    void ZExtent(const FReflectionsDigMeshData& Mesh, float& OutMinZ, float& OutMaxZ)
    {
        OutMinZ = TNumericLimits<float>::Max();
        OutMaxZ = TNumericLimits<float>::Lowest();
        for (const FVector3f& Position : Mesh.Positions)
        {
            OutMinZ = FMath::Min(OutMinZ, Position.Z);
            OutMaxZ = FMath::Max(OutMaxZ, Position.Z);
        }
    }

    /** For each of NumSlabs equal-height slabs between MinZ and MaxZ, the triangles whose centroid it holds. */
    TArray<TArray<int32>> AssignTrianglesToSlabs(const FReflectionsDigMeshData& Mesh, int32 NumSlabs)
    {
        float MinZ = 0.0f;
        float MaxZ = 0.0f;
        ZExtent(Mesh, MinZ, MaxZ);
        TArray<TArray<int32>> Slabs;
        Slabs.SetNum(NumSlabs);
        const int32 NumTriangles = Mesh.Triangles.Num() / 3;
        const float SlabHeight = (MaxZ - MinZ) / static_cast<float>(NumSlabs);
        for (int32 Triangle = 0; Triangle < NumTriangles; ++Triangle)
        {
            int32 Slab = 0;
            if (SlabHeight > 0.0f)
            {
                const float CentroidZ = (Mesh.Positions[Mesh.Triangles[3 * Triangle]].Z
                    + Mesh.Positions[Mesh.Triangles[3 * Triangle + 1]].Z
                    + Mesh.Positions[Mesh.Triangles[3 * Triangle + 2]].Z) / 3.0f;
                Slab = FMath::Clamp(FMath::FloorToInt32((CentroidZ - MinZ) / SlabHeight), 0, NumSlabs - 1);
            }
            Slabs[Slab].Add(Triangle);
        }
        return Slabs;
    }

    /** The most vertices any slab uses (each slab counts every vertex its triangles touch once). */
    int32 LargestSlabVertexCount(const FReflectionsDigMeshData& Mesh, const TArray<TArray<int32>>& Slabs)
    {
        TArray<int32> LastSlabOfVertex;
        LastSlabOfVertex.Init(INDEX_NONE, Mesh.Positions.Num());
        int32 Largest = 0;
        for (int32 Slab = 0; Slab < Slabs.Num(); ++Slab)
        {
            int32 Count = 0;
            for (const int32 Triangle : Slabs[Slab])
            {
                for (int32 Corner = 0; Corner < 3; ++Corner)
                {
                    int32& Last = LastSlabOfVertex[Mesh.Triangles[3 * Triangle + Corner]];
                    if (Last != Slab)
                    {
                        Last = Slab;
                        ++Count;
                    }
                }
            }
            Largest = FMath::Max(Largest, Count);
        }
        return Largest;
    }

    /**
     * One piece's dynamic mesh: its own copy of the vertices the triangles use, with the mesher's per-vertex
     * normals in the primary normal overlay (one element per vertex, which the scene proxy renders with).
     * FDynamicMesh3 refuses a triangle on an edge that already has two; such a triangle gets its own vertex copies.
     * Returns how many triangles could not be added even so.
     */
    int32 BuildPieceMesh(const FReflectionsDigMeshData& Mesh, const TArray<int32>& Triangles, FDynamicMesh3& Piece)
    {
        Piece = FDynamicMesh3();
        Piece.EnableAttributes();
        UE::Geometry::FDynamicMeshNormalOverlay* Normals = Piece.Attributes()->PrimaryNormals();
        TArray<int32> PieceVertexOf;
        PieceVertexOf.Init(INDEX_NONE, Mesh.Positions.Num());

        // Vertex and normal element IDs stay equal: each vertex appends exactly one element.
        auto AppendVertex = [&Piece, Normals, &Mesh](int32 Source)
        {
            const int32 Vertex = Piece.AppendVertex(FVector3d(Mesh.Positions[Source]));
            Normals->AppendElement(Mesh.Normals[Source]);
            return Vertex;
        };

        int32 Dropped = 0;
        for (const int32 Triangle : Triangles)
        {
            FIndex3i Corners;
            for (int32 Corner = 0; Corner < 3; ++Corner)
            {
                const int32 Source = Mesh.Triangles[3 * Triangle + Corner];
                int32& Vertex = PieceVertexOf[Source];
                if (Vertex == INDEX_NONE)
                {
                    Vertex = AppendVertex(Source);
                }
                Corners[Corner] = Vertex;
            }
            int32 NewTriangle = Piece.AppendTriangle(Corners);
            if (NewTriangle == FDynamicMesh3::NonManifoldID)
            {
                for (int32 Corner = 0; Corner < 3; ++Corner)
                {
                    Corners[Corner] = AppendVertex(Mesh.Triangles[3 * Triangle + Corner]);
                }
                NewTriangle = Piece.AppendTriangle(Corners);
            }
            if (NewTriangle >= 0)
            {
                Normals->SetTriangle(NewTriangle, Corners);
            }
            else
            {
                ++Dropped;
            }
        }
        return Dropped;
    }

    int32 LargestPieceVertexCount(const FReflectionsDigChunkResult& Result)
    {
        int32 Largest = 0;
        for (const FDynamicMesh3& Piece : Result.Pieces)
        {
            Largest = FMath::Max(Largest, Piece.VertexCount());
        }
        return Largest;
    }
}

namespace ReflectionsDigPieces
{
    void BuildWithSlabs(const FReflectionsDigMeshData& Mesh, int32 NumSlabs, FReflectionsDigChunkResult& Out)
    {
        Out = FReflectionsDigChunkResult();
        Out.SourceVertexCount = Mesh.Positions.Num();
        Out.SourceTriangleCount = Mesh.Triangles.Num() / 3;
        if (Out.SourceTriangleCount == 0)
        {
            return;
        }
        const TArray<TArray<int32>> Slabs = AssignTrianglesToSlabs(Mesh, FMath::Max(1, NumSlabs));
        for (const TArray<int32>& Slab : Slabs)
        {
            if (!Slab.IsEmpty())
            {
                Out.DroppedTriangles += BuildPieceMesh(Mesh, Slab, Out.Pieces.AddDefaulted_GetRef());
            }
        }
    }

    void Build(const FReflectionsDigMeshData& Mesh, FReflectionsDigChunkResult& Out)
    {
        for (int32 NumSlabs = 1; NumSlabs <= MaxSlabs; ++NumSlabs)
        {
            const bool bLastTry = NumSlabs == MaxSlabs;
            // A slab's own vertex count is a lower bound of its built piece's, so a slab already over the limit
            // rules this slab count out without building anything.
            if (!bLastTry && LargestSlabVertexCount(Mesh, AssignTrianglesToSlabs(Mesh, NumSlabs)) > ReflectionsDig::MaxPieceVertices)
            {
                continue;
            }
            BuildWithSlabs(Mesh, NumSlabs, Out);
            if (LargestPieceVertexCount(Out) <= ReflectionsDig::MaxPieceVertices)
            {
                return;
            }
        }
        UE_LOG(LogReflectionsDigPieces, Warning, TEXT("A chunk mesh of %d vertices does not fit %d slabs of %d vertices"),
            Mesh.Positions.Num(), MaxSlabs, ReflectionsDig::MaxPieceVertices);
    }
}
