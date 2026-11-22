#include "Digging/ReflectionsDigPieces.h"

#include "CoreMinimal.h"
#include "Digging/ReflectionsDigGrid.h"
#include "Digging/ReflectionsDigMesher.h"
#include "Digging/ReflectionsDigTypes.h"
#include "DynamicMesh/DynamicMesh3.h"
#include "DynamicMesh/DynamicMeshAttributeSet.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
    constexpr EAutomationTestFlags DigPiecesTestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter;

    /** The default terrain's grid: 3 x 3 x 2 chunks, origin at Z -2800, ground at Z 0. */
    FReflectionsDigGrid MakeTerrainGrid()
    {
        return FReflectionsDigGrid(FIntVector(3, 3, 2), FVector(0.0, 0.0, -2800.0), 0.0f);
    }

    /** Chunk (1, 1, 0) riddled with radius-100 digs on a 200 cm lattice of cells: about 29,000 vertices. */
    FReflectionsDigMeshData MakeBusyMesh()
    {
        FReflectionsDigGrid Grid = MakeTerrainGrid();
        for (double Z = -2700.0; Z <= -1300.0; Z += 200.0)
        {
            for (double Y = 1700.0; Y <= 3100.0; Y += 200.0)
            {
                for (double X = 1700.0; X <= 3100.0; X += 200.0)
                {
                    FReflectionsDigStamp Stamp;
                    Stamp.Center = FVector(X, Y, Z);
                    Stamp.RadiusCm = 100.0f;
                    Stamp.Mode = EReflectionsDigMode::Remove;
                    TArray<FIntVector> Dirty;
                    Grid.ApplyStamp(Stamp, Dirty);
                }
            }
        }
        FReflectionsDigMeshData Mesh;
        ReflectionsDigMesher::BuildChunk(Grid, FIntVector(1, 1, 0), Mesh);
        return Mesh;
    }

    int32 LargestPiece(const FReflectionsDigChunkResult& Result)
    {
        int32 Largest = 0;
        for (const UE::Geometry::FDynamicMesh3& Piece : Result.Pieces)
        {
            Largest = FMath::Max(Largest, Piece.VertexCount());
        }
        return Largest;
    }

    TArray<int32> PieceVertexCounts(const FReflectionsDigChunkResult& Result)
    {
        TArray<int32> Counts;
        for (const UE::Geometry::FDynamicMesh3& Piece : Result.Pieces)
        {
            Counts.Add(Piece.VertexCount());
        }
        return Counts;
    }
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigPiecesSmallMeshIsOnePieceTest, "Reflections.Digging.Pieces.SmallMeshIsOnePiece", DigPiecesTestFlags)
bool FReflectionsDigPiecesSmallMeshIsOnePieceTest::RunTest(const FString& Parameters)
{
    const FReflectionsDigGrid Grid = MakeTerrainGrid();
    FReflectionsDigMeshData Flat;
    ReflectionsDigMesher::BuildChunk(Grid, FIntVector(1, 1, 1), Flat);
    FReflectionsDigChunkResult Result;
    ReflectionsDigPieces::Build(Flat, Result);

    TestEqual(TEXT("Source vertices"), Result.SourceVertexCount, 1089);
    TestEqual(TEXT("Source triangles"), Result.SourceTriangleCount, 2048);
    TestEqual(TEXT("Dropped triangles"), Result.DroppedTriangles, 0);
    if (!TestEqual(TEXT("Pieces"), Result.Pieces.Num(), 1))
    {
        return true;
    }
    const UE::Geometry::FDynamicMesh3& Piece = Result.Pieces[0];
    TestEqual(TEXT("Piece vertices"), Piece.VertexCount(), 1089);
    TestEqual(TEXT("Piece triangles"), Piece.TriangleCount(), 2048);

    const UE::Geometry::FDynamicMeshNormalOverlay* Normals = Piece.HasAttributes() ? Piece.Attributes()->PrimaryNormals() : nullptr;
    if (TestNotNull(TEXT("Primary normal overlay"), Normals))
    {
        int32 NotUnit = 0;
        int32 Unset = 0;
        for (const int32 Triangle : Piece.TriangleIndicesItr())
        {
            if (!Normals->IsSetTriangle(Triangle))
            {
                ++Unset;
                continue;
            }
            const UE::Geometry::FIndex3i Elements = Normals->GetTriangle(Triangle);
            for (int32 Corner = 0; Corner < 3; ++Corner)
            {
                const FVector3f Normal = Normals->GetElement(Elements[Corner]);
                NotUnit += FMath::Abs(Normal.Size() - 1.0f) <= 1.0e-3f ? 0 : 1;
            }
        }
        TestEqual(TEXT("Triangles with no normals"), Unset, 0);
        TestEqual(TEXT("Normals that are not unit length"), NotUnit, 0);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigPiecesBusyMeshSplitsUnderTheLimitTest, "Reflections.Digging.Pieces.BusyMeshSplitsUnderTheLimit", DigPiecesTestFlags)
bool FReflectionsDigPiecesBusyMeshSplitsUnderTheLimitTest::RunTest(const FString& Parameters)
{
    const FReflectionsDigMeshData Busy = MakeBusyMesh();
    if (!TestTrue(FString::Printf(TEXT("Premise: the busy mesh has more than 12,000 vertices (%d)"), Busy.Positions.Num()),
        Busy.Positions.Num() > ReflectionsDig::MaxPieceVertices))
    {
        return true;
    }
    FReflectionsDigChunkResult Result;
    ReflectionsDigPieces::Build(Busy, Result);
    TestTrue(FString::Printf(TEXT("At least two pieces (%d)"), Result.Pieces.Num()), Result.Pieces.Num() >= 2);
    TestTrue(FString::Printf(TEXT("Every piece holds at most 12,000 vertices (largest %d)"), LargestPiece(Result)),
        LargestPiece(Result) <= ReflectionsDig::MaxPieceVertices);
    int32 Triangles = 0;
    for (const UE::Geometry::FDynamicMesh3& Piece : Result.Pieces)
    {
        Triangles += Piece.TriangleCount();
    }
    TestEqual(TEXT("The pieces' triangles sum to the source count"), Triangles, Result.SourceTriangleCount);
    TestEqual(TEXT("Source triangle count"), Result.SourceTriangleCount, Busy.Triangles.Num() / 3);
    TestEqual(TEXT("Dropped triangles"), Result.DroppedTriangles, 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigPiecesSlabsAreTheFewestThatFitTest, "Reflections.Digging.Pieces.SlabsAreTheFewestThatFit", DigPiecesTestFlags)
bool FReflectionsDigPiecesSlabsAreTheFewestThatFitTest::RunTest(const FString& Parameters)
{
    const FReflectionsDigMeshData Busy = MakeBusyMesh();
    FReflectionsDigChunkResult Chosen;
    ReflectionsDigPieces::Build(Busy, Chosen);
    const TArray<int32> ChosenCounts = PieceVertexCounts(Chosen);

    // Find the slab count Build used: the one whose built pieces match Build's exactly.
    int32 UsedSlabs = 0;
    for (int32 NumSlabs = 1; NumSlabs <= 64 && UsedSlabs == 0; ++NumSlabs)
    {
        FReflectionsDigChunkResult Candidate;
        ReflectionsDigPieces::BuildWithSlabs(Busy, NumSlabs, Candidate);
        if (PieceVertexCounts(Candidate) == ChosenCounts)
        {
            UsedSlabs = NumSlabs;
        }
    }
    if (!TestTrue(FString::Printf(TEXT("Build's pieces are those of a whole number of slabs (%d) above 1"), UsedSlabs), UsedSlabs >= 2))
    {
        return true;
    }
    // The limit applies to each built piece, so the check builds the pieces of one slab fewer.
    FReflectionsDigChunkResult Fewer;
    ReflectionsDigPieces::BuildWithSlabs(Busy, UsedSlabs - 1, Fewer);
    TestTrue(FString::Printf(TEXT("With %d slabs a piece is above the limit (largest %d)"), UsedSlabs - 1, LargestPiece(Fewer)),
        LargestPiece(Fewer) > ReflectionsDig::MaxPieceVertices);
    TestTrue(FString::Printf(TEXT("With %d slabs every piece fits (largest %d)"), UsedSlabs, LargestPiece(Chosen)),
        LargestPiece(Chosen) <= ReflectionsDig::MaxPieceVertices);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigPiecesNavGeometryMatchesEachPieceTest, "Reflections.Digging.Pieces.NavGeometryMatchesEachPiece", DigPiecesTestFlags)
bool FReflectionsDigPiecesNavGeometryMatchesEachPieceTest::RunTest(const FString& Parameters)
{
    const FReflectionsDigMeshData Busy = MakeBusyMesh();
    FReflectionsDigChunkResult Result;
    ReflectionsDigPieces::Build(Busy, Result);
    if (!TestTrue(FString::Printf(TEXT("Premise: the busy mesh is split (%d pieces)"), Result.Pieces.Num()), Result.Pieces.Num() >= 2)
        || !TestEqual(TEXT("One navigation geometry per piece"), Result.NavGeometry.Num(), Result.Pieces.Num()))
    {
        return true;
    }
    for (int32 Index = 0; Index < Result.Pieces.Num(); ++Index)
    {
        const UE::Geometry::FDynamicMesh3& Piece = Result.Pieces[Index];
        const FReflectionsDigNavGeometry& Nav = Result.NavGeometry[Index];
        TestEqual(FString::Printf(TEXT("Piece %d: three indices per triangle"), Index), Nav.Indices.Num(), 3 * Piece.TriangleCount());
        const int32 Invalid = Nav.Indices.FilterByPredicate([&Nav](int32 Vertex) { return !Nav.Vertices.IsValidIndex(Vertex); }).Num();
        TestEqual(FString::Printf(TEXT("Piece %d: indices outside the %d vertices"), Index, Nav.Vertices.Num()), Invalid, 0);
        const UE::Geometry::FAxisAlignedBox3d MeshBounds = Piece.GetBounds();
        const FBox NavBounds(Nav.Vertices);
        TestTrue(FString::Printf(TEXT("Piece %d: the navigation bounds %s equal the mesh bounds %s"), Index, *NavBounds.ToString(),
            *FBox(MeshBounds.Min, MeshBounds.Max).ToString()),
            NavBounds.IsValid && NavBounds.Min.Equals(MeshBounds.Min, 1.0e-3) && NavBounds.Max.Equals(MeshBounds.Max, 1.0e-3));
    }
    return true;
}

#endif
