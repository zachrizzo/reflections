#include "Digging/ReflectionsDigPieces.h"

#include "CoreMinimal.h"
#include "Digging/ReflectionsDigMesher.h"
#include "Digging/ReflectionsDigTypes.h"
#include "DynamicMesh/DynamicMesh3.h"
#include "DynamicMesh/DynamicMeshAttributeSet.h"
#include "Hash/CityHash.h"
#include "IndexTypes.h"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsDigPieces, Log, All);

using UE::Geometry::FDynamicMesh3;
using UE::Geometry::FIndex3i;

namespace
{
    /** The block that holds a centroid: the high half on an axis from the border on (a centroid on it is the high block's). */
    int32 BlockOf(const FVector3f& Centroid, const FVector3f& Border)
    {
        return (Centroid.X >= Border.X ? 1 : 0) + (Centroid.Y >= Border.Y ? 2 : 0) + (Centroid.Z >= Border.Z ? 4 : 0);
    }

    /** What a piece's hash covers, gathered in the order the piece is built (the mesher's order). */
    struct FPieceHashInput
    {
        TArray<FVector3f> Positions;
        TArray<FVector3f> Normals;
        TArray<FIndex3i> Triangles;

        /** CityHash64 of the bytes, the same on every thread and run; 0 only for no triangles. */
        uint64 Hash() const
        {
            if (Triangles.IsEmpty())
            {
                return 0;
            }
            uint64 Hash = CityHash64(Positions.GetData(), Positions.Num() * sizeof(FVector3f));
            Hash = CityHash64WithSeed(Normals.GetData(), Normals.Num() * sizeof(FVector3f), Hash);
            Hash = CityHash64WithSeed(Triangles.GetData(), Triangles.Num() * sizeof(FIndex3i), Hash);
            return Hash != 0 ? Hash : 1;
        }
    };

    /**
     * One piece's dynamic mesh: its own copy of the vertices the triangles use, with the mesher's per-vertex normals in
     * the primary normal overlay (one element per vertex, which the scene proxy renders with). FDynamicMesh3 refuses a
     * triangle on an edge that already has two; such a triangle goes onto a second copy of its vertices, shared by
     * every such triangle of the piece, and only if that copy refuses it too onto vertex copies of its own. Returns how
     * many triangles could not be added even so; OutHash is the piece's hash.
     */
    int32 BuildPieceMesh(const FReflectionsDigMeshData& Mesh, const TArray<int32>& Triangles, FDynamicMesh3& Piece, uint64& OutHash)
    {
        Piece = FDynamicMesh3();
        Piece.EnableAttributes();
        UE::Geometry::FDynamicMeshNormalOverlay* Normals = Piece.Attributes()->PrimaryNormals();
        FPieceHashInput HashInput;
        HashInput.Triangles.Reserve(Triangles.Num());
        TArray<int32> VertexOf[2];
        VertexOf[0].Init(INDEX_NONE, Mesh.Positions.Num());

        // Vertex and normal element IDs stay equal: each vertex appends exactly one element.
        auto AppendVertex = [&Piece, Normals, &Mesh, &HashInput](int32 Source)
        {
            const int32 Vertex = Piece.AppendVertex(FVector3d(Mesh.Positions[Source]));
            Normals->AppendElement(Mesh.Normals[Source]);
            HashInput.Positions.Add(Mesh.Positions[Source]);
            HashInput.Normals.Add(Mesh.Normals[Source]);
            return Vertex;
        };

        // The triangle on one copy of the vertices. An edge between two vertices the copy already has that holds two
        // triangles is checked first, so no vertex is added for a triangle that cannot go in.
        auto TryCopy = [&Piece, &AppendVertex](TArray<int32>& Copy, const int32 (&Sources)[3], FIndex3i& OutCorners)
        {
            for (int32 Edge = 0; Edge < 3; ++Edge)
            {
                const int32 A = Copy[Sources[Edge]];
                const int32 B = Copy[Sources[(Edge + 1) % 3]];
                if (A != INDEX_NONE && B != INDEX_NONE)
                {
                    const int32 EdgeID = Piece.FindEdge(A, B);
                    if (EdgeID != FDynamicMesh3::InvalidID && !Piece.IsBoundaryEdge(EdgeID))
                    {
                        return FDynamicMesh3::NonManifoldID;
                    }
                }
            }
            for (int32 Corner = 0; Corner < 3; ++Corner)
            {
                int32& Vertex = Copy[Sources[Corner]];
                if (Vertex == INDEX_NONE)
                {
                    Vertex = AppendVertex(Sources[Corner]);
                }
                OutCorners[Corner] = Vertex;
            }
            return Piece.AppendTriangle(OutCorners);
        };

        int32 Dropped = 0;
        for (const int32 Triangle : Triangles)
        {
            const int32 Sources[3] = { Mesh.Triangles[3 * Triangle], Mesh.Triangles[3 * Triangle + 1], Mesh.Triangles[3 * Triangle + 2] };
            FIndex3i Corners;
            int32 NewTriangle = TryCopy(VertexOf[0], Sources, Corners);
            if (NewTriangle == FDynamicMesh3::NonManifoldID)
            {
                if (VertexOf[1].IsEmpty())
                {
                    VertexOf[1].Init(INDEX_NONE, Mesh.Positions.Num());
                }
                NewTriangle = TryCopy(VertexOf[1], Sources, Corners);
            }
            if (NewTriangle == FDynamicMesh3::NonManifoldID)
            {
                for (int32 Corner = 0; Corner < 3; ++Corner)
                {
                    Corners[Corner] = AppendVertex(Sources[Corner]);
                }
                NewTriangle = Piece.AppendTriangle(Corners);
            }
            if (NewTriangle >= 0)
            {
                Normals->SetTriangle(NewTriangle, Corners);
                HashInput.Triangles.Add(Corners);
            }
            else
            {
                ++Dropped;
            }
        }
        OutHash = HashInput.Hash();
        return Dropped;
    }

    /** A piece's own vertices (in its local space) and three indices per triangle, for navigation. */
    void BuildNavGeometry(const FDynamicMesh3& Piece, FReflectionsDigNavGeometry& Out)
    {
        Out.Vertices.Reset(Piece.VertexCount());
        Out.Indices.Reset(3 * Piece.TriangleCount());
        // BuildPieceMesh only appends, so the IDs are compact already; the remap keeps this right if that changes.
        TArray<int32> IndexOfVertex;
        IndexOfVertex.Init(INDEX_NONE, Piece.MaxVertexID());
        for (const int32 Vertex : Piece.VertexIndicesItr())
        {
            IndexOfVertex[Vertex] = Out.Vertices.Add(Piece.GetVertex(Vertex));
        }
        for (const int32 Triangle : Piece.TriangleIndicesItr())
        {
            const FIndex3i Corners = Piece.GetTriangle(Triangle);
            Out.Indices.Add(IndexOfVertex[Corners.A]);
            Out.Indices.Add(IndexOfVertex[Corners.B]);
            Out.Indices.Add(IndexOfVertex[Corners.C]);
        }
    }
}

int32 FReflectionsDigChunkResult::NumPieces() const
{
    int32 Count = 0;
    for (const FDynamicMesh3& Piece : Pieces)
    {
        Count += Piece.TriangleCount() > 0 ? 1 : 0;
    }
    return Count;
}

namespace ReflectionsDigPieces
{
    void Build(const FReflectionsDigMeshData& Mesh, const FVector3f& ChunkLocalOriginCm, FReflectionsDigChunkResult& Out)
    {
        Out = FReflectionsDigChunkResult();
        Out.SourceVertexCount = Mesh.Positions.Num();
        Out.SourceTriangleCount = Mesh.Triangles.Num() / 3;
        if (Out.SourceTriangleCount == 0)
        {
            return;
        }
        const FVector3f Border = ChunkLocalOriginCm + FVector3f(ReflectionsDig::BlockCells * ReflectionsDig::CellSizeCm);
        TStaticArray<TArray<int32>, ReflectionsDig::BlocksPerChunk> BlockTriangles;
        for (int32 Triangle = 0; Triangle < Out.SourceTriangleCount; ++Triangle)
        {
            const FVector3f Centroid = (Mesh.Positions[Mesh.Triangles[3 * Triangle]] + Mesh.Positions[Mesh.Triangles[3 * Triangle + 1]]
                + Mesh.Positions[Mesh.Triangles[3 * Triangle + 2]]) / 3.0f;
            BlockTriangles[BlockOf(Centroid, Border)].Add(Triangle);
        }
        for (int32 Block = 0; Block < ReflectionsDig::BlocksPerChunk; ++Block)
        {
            if (BlockTriangles[Block].IsEmpty())
            {
                continue;
            }
            Out.DroppedTriangles += BuildPieceMesh(Mesh, BlockTriangles[Block], Out.Pieces[Block], Out.PieceHash[Block]);
            BuildNavGeometry(Out.Pieces[Block], Out.NavGeometry[Block]);
            if (Out.Pieces[Block].VertexCount() > ReflectionsDig::MaxPieceVertices)
            {
                // Not split: no chunk the mesher can make gives a block this many (WorstBlockStaysUnderTheLimit).
                UE_LOG(LogReflectionsDigPieces, Warning, TEXT("Block %d of a chunk mesh of %d vertices holds %d vertices, above the %d a piece may hold"),
                    Block, Mesh.Positions.Num(), Out.Pieces[Block].VertexCount(), ReflectionsDig::MaxPieceVertices);
            }
        }
    }
}
