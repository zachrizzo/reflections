#include "Digging/ReflectionsDigPieces.h"

#include "CoreMinimal.h"
#include "Digging/ReflectionsDigGrid.h"
#include "Digging/ReflectionsDigMesher.h"
#include "Digging/ReflectionsDigTypes.h"
#include "DynamicMesh/DynamicMesh3.h"
#include "DynamicMesh/DynamicMeshAttributeSet.h"
#include "Misc/AutomationTest.h"
#include "Tasks/Task.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
    constexpr EAutomationTestFlags DigPiecesTestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter;

    /** The default terrain's grid: 3 x 3 x 2 chunks, origin at Z -2800, ground at Z 0. */
    FReflectionsDigGrid MakeTerrainGrid()
    {
        return FReflectionsDigGrid(FIntVector(3, 3, 2), FVector(0.0, 0.0, -2800.0), 0.0f);
    }

    const FIntVector BusyChunk(1, 1, 0);
    const FIntVector FlatChunk(1, 1, 1);

    void Stamp(FReflectionsDigGrid& Grid, const FVector& Center, EReflectionsDigMode Mode)
    {
        FReflectionsDigStamp Stamp;
        Stamp.Center = Center;
        Stamp.RadiusCm = 100.0f;
        Stamp.Mode = Mode;
        TArray<FIntVector> Dirty;
        Grid.ApplyStamp(Stamp, Dirty);
    }

    /** Riddles chunk (1, 1, 0) with radius-100 digs on a 200 cm lattice of cells: about 29,000 vertices. */
    void RiddleBusyChunk(FReflectionsDigGrid& Grid)
    {
        for (double Z = -2700.0; Z <= -1300.0; Z += 200.0)
        {
            for (double Y = 1700.0; Y <= 3100.0; Y += 200.0)
            {
                for (double X = 1700.0; X <= 3100.0; X += 200.0)
                {
                    Stamp(Grid, FVector(X, Y, Z), EReflectionsDigMode::Remove);
                }
            }
        }
    }

    FReflectionsDigMeshData MakeBusyMesh()
    {
        FReflectionsDigGrid Grid = MakeTerrainGrid();
        RiddleBusyChunk(Grid);
        FReflectionsDigMeshData Mesh;
        ReflectionsDigMesher::BuildChunk(Grid, BusyChunk, Mesh);
        return Mesh;
    }

    /** Position of a chunk's local cell (0, 0, 0) relative to the grid origin, as FReflectionsDigChunkSamples::LocalOriginCm. */
    FVector3f ChunkOrigin(const FIntVector& Chunk)
    {
        return FVector3f(Chunk * ReflectionsDig::ChunkCells) * ReflectionsDig::CellSizeCm;
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

    int32 PieceTriangles(const FReflectionsDigChunkResult& Result)
    {
        int32 Triangles = 0;
        for (const UE::Geometry::FDynamicMesh3& Piece : Result.Pieces)
        {
            Triangles += Piece.TriangleCount();
        }
        return Triangles;
    }

    FString DescribeHashes(const FReflectionsDigChunkResult& Result)
    {
        FString Text;
        for (int32 Block = 0; Block < ReflectionsDig::BlocksPerChunk; ++Block)
        {
            Text += FString::Printf(TEXT("%s%d:%016llx"), Block > 0 ? TEXT(" ") : TEXT(""), Block, static_cast<unsigned long long>(Result.PieceHash[Block]));
        }
        return Text;
    }
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigPiecesFlatChunkPiecesCarryUnitNormalsTest, "Reflections.Digging.Pieces.FlatChunkPiecesCarryUnitNormals", DigPiecesTestFlags)
bool FReflectionsDigPiecesFlatChunkPiecesCarryUnitNormalsTest::RunTest(const FString& Parameters)
{
    const FReflectionsDigGrid Grid = MakeTerrainGrid();
    FReflectionsDigMeshData Flat;
    ReflectionsDigMesher::BuildChunk(Grid, FlatChunk, Flat);
    FReflectionsDigChunkResult Result;
    ReflectionsDigPieces::Build(Flat, ChunkOrigin(FlatChunk), Result);

    TestEqual(TEXT("Source vertices"), Result.SourceVertexCount, 1089);
    TestEqual(TEXT("Source triangles"), Result.SourceTriangleCount, 2048);
    TestEqual(TEXT("Dropped triangles"), Result.DroppedTriangles, 0);
    TestEqual(TEXT("Pieces"), Result.NumPieces(), 4);
    TestEqual(TEXT("The pieces' triangles sum to the source count"), PieceTriangles(Result), 2048);
    for (int32 Block = 0; Block < ReflectionsDig::BlocksPerChunk; ++Block)
    {
        const UE::Geometry::FDynamicMesh3& Piece = Result.Pieces[Block];
        if (Piece.TriangleCount() == 0)
        {
            continue;
        }
        const UE::Geometry::FDynamicMeshNormalOverlay* Normals = Piece.HasAttributes() ? Piece.Attributes()->PrimaryNormals() : nullptr;
        if (!TestNotNull(FString::Printf(TEXT("Block %d: primary normal overlay"), Block), Normals))
        {
            continue;
        }
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
        TestEqual(FString::Printf(TEXT("Block %d: triangles with no normals"), Block), Unset, 0);
        TestEqual(FString::Printf(TEXT("Block %d: normals that are not unit length"), Block), NotUnit, 0);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigPiecesBusyMeshBlocksStayUnderTheLimitTest, "Reflections.Digging.Pieces.BusyMeshBlocksStayUnderTheLimit", DigPiecesTestFlags)
bool FReflectionsDigPiecesBusyMeshBlocksStayUnderTheLimitTest::RunTest(const FString& Parameters)
{
    const FReflectionsDigMeshData Busy = MakeBusyMesh();
    if (!TestTrue(FString::Printf(TEXT("Premise: the busy mesh has more than 12,000 vertices (%d)"), Busy.Positions.Num()),
        Busy.Positions.Num() > ReflectionsDig::MaxPieceVertices))
    {
        return true;
    }
    FReflectionsDigChunkResult Result;
    ReflectionsDigPieces::Build(Busy, ChunkOrigin(BusyChunk), Result);
    TestEqual(TEXT("The riddled chunk fills all eight blocks"), Result.NumPieces(), ReflectionsDig::BlocksPerChunk);
    TestTrue(FString::Printf(TEXT("Every piece holds at most 12,000 vertices (largest %d)"), LargestPiece(Result)),
        LargestPiece(Result) <= ReflectionsDig::MaxPieceVertices);
    TestEqual(TEXT("The pieces' triangles sum to the source count"), PieceTriangles(Result), Result.SourceTriangleCount);
    TestEqual(TEXT("Source triangle count"), Result.SourceTriangleCount, Busy.Triangles.Num() / 3);
    TestEqual(TEXT("Dropped triangles"), Result.DroppedTriangles, 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigPiecesTrianglesGoToTheBlockOfTheirCentroidTest, "Reflections.Digging.Pieces.TrianglesGoToTheBlockOfTheirCentroid", DigPiecesTestFlags)
bool FReflectionsDigPiecesTrianglesGoToTheBlockOfTheirCentroidTest::RunTest(const FString& Parameters)
{
    // The riddled chunk: every triangle of block B's piece has its centroid on B's side of each inner border (the
    // border itself belongs to the high block), and inside the chunk's meshed span (half a cell below its origin to
    // its far face), along each axis.
    {
        const FReflectionsDigMeshData Busy = MakeBusyMesh();
        FReflectionsDigChunkResult Result;
        const FVector3f Origin = ChunkOrigin(BusyChunk);
        ReflectionsDigPieces::Build(Busy, Origin, Result);
        const FVector3f Border = Origin + FVector3f(ReflectionsDig::BlockCells * ReflectionsDig::CellSizeCm);
        const FVector3f SpanMin = Origin - FVector3f(ReflectionsDig::CellSizeCm);
        const FVector3f SpanMax = Origin + FVector3f(ReflectionsDig::ChunkSizeCm);
        int32 Outside = 0;
        FString FirstOutside;
        for (int32 Block = 0; Block < ReflectionsDig::BlocksPerChunk; ++Block)
        {
            const UE::Geometry::FDynamicMesh3& Piece = Result.Pieces[Block];
            for (const int32 Triangle : Piece.TriangleIndicesItr())
            {
                const UE::Geometry::FIndex3i Corners = Piece.GetTriangle(Triangle);
                const FVector3f Centroid = (FVector3f(Piece.GetVertex(Corners.A)) + FVector3f(Piece.GetVertex(Corners.B)) + FVector3f(Piece.GetVertex(Corners.C))) / 3.0f;
                bool bInside = true;
                for (int32 Axis = 0; Axis < 3; ++Axis)
                {
                    const bool bHigh = ((Block >> Axis) & 1) != 0;
                    const float Value = Centroid[Axis];
                    bInside &= bHigh ? (Value >= Border[Axis] && Value <= SpanMax[Axis]) : (Value < Border[Axis] && Value >= SpanMin[Axis]);
                }
                if (!bInside)
                {
                    if (Outside == 0)
                    {
                        FirstOutside = FString::Printf(TEXT("block %d triangle %d centroid %s"), Block, Triangle, *Centroid.ToString());
                    }
                    ++Outside;
                }
            }
        }
        TestEqual(FString::Printf(TEXT("Riddled chunk: triangles outside their block (first: %s)"), *FirstOutside), Outside, 0);
        TestEqual(TEXT("Riddled chunk: the pieces' triangles sum to the source count"), PieceTriangles(Result), Result.SourceTriangleCount);
        TestEqual(TEXT("Riddled chunk: dropped triangles"), Result.DroppedTriangles, 0);
    }

    // An untouched flat chunk: its surface runs through the four upper blocks only.
    {
        const FReflectionsDigGrid Grid = MakeTerrainGrid();
        FReflectionsDigMeshData Flat;
        ReflectionsDigMesher::BuildChunk(Grid, FlatChunk, Flat);
        FReflectionsDigChunkResult Result;
        ReflectionsDigPieces::Build(Flat, ChunkOrigin(FlatChunk), Result);
        TestEqual(TEXT("Flat chunk: four pieces"), Result.NumPieces(), 4);
        for (int32 Block = 0; Block < ReflectionsDig::BlocksPerChunk; ++Block)
        {
            const bool bUpper = Block >= 4;
            TestEqual(FString::Printf(TEXT("Flat chunk: block %d %s"), Block, bUpper ? TEXT("has a piece") : TEXT("is empty")),
                Result.Pieces[Block].TriangleCount() > 0, bUpper);
            TestEqual(FString::Printf(TEXT("Flat chunk: block %d's hash is 0 exactly when it is empty"), Block),
                Result.PieceHash[Block] == 0, Result.Pieces[Block].TriangleCount() == 0);
        }
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigPiecesHashFollowsTheMeshOnlyTest, "Reflections.Digging.Pieces.HashFollowsTheMeshOnly", DigPiecesTestFlags)
bool FReflectionsDigPiecesHashFollowsTheMeshOnlyTest::RunTest(const FString& Parameters)
{
    FReflectionsDigGrid Grid = MakeTerrainGrid();
    RiddleBusyChunk(Grid);
    FReflectionsDigMeshData Before;
    ReflectionsDigMesher::BuildChunk(Grid, BusyChunk, Before);
    const FVector3f Origin = ChunkOrigin(BusyChunk);

    FReflectionsDigChunkResult First;
    FReflectionsDigChunkResult Second;
    ReflectionsDigPieces::Build(Before, Origin, First);
    ReflectionsDigPieces::Build(Before, Origin, Second);
    // The same input on a worker thread, as the subsystem builds it.
    FReflectionsDigChunkResult OnWorker;
    UE::Tasks::Launch(TEXT("ReflectionsDigPiecesHashTest"), [&Before, &Origin, &OnWorker]()
    {
        ReflectionsDigPieces::Build(Before, Origin, OnWorker);
    }).Wait();
    for (int32 Block = 0; Block < ReflectionsDig::BlocksPerChunk; ++Block)
    {
        TestTrue(FString::Printf(TEXT("Block %d: a piece of the riddled chunk has a hash"), Block), First.PieceHash[Block] != 0);
        TestEqual(FString::Printf(TEXT("Block %d: building twice gives the same hash"), Block), Second.PieceHash[Block], First.PieceHash[Block]);
        TestEqual(FString::Printf(TEXT("Block %d: building on a worker gives the same hash"), Block), OnWorker.PieceHash[Block], First.PieceHash[Block]);
    }

    // One more dig in the middle of block 0 (X 1600..2400, Y 1600..2400, Z -2800..-2000), between the cavities.
    Stamp(Grid, FVector(2000.0, 2000.0, -2400.0), EReflectionsDigMode::Remove);
    FReflectionsDigMeshData After;
    ReflectionsDigMesher::BuildChunk(Grid, BusyChunk, After);
    FReflectionsDigChunkResult Dug;
    ReflectionsDigPieces::Build(After, Origin, Dug);
    TestTrue(FString::Printf(TEXT("Premise: the dig changed the mesh (%d vertices, before %d)"), After.Positions.Num(), Before.Positions.Num()),
        After.Positions.Num() != Before.Positions.Num() || After.Triangles != Before.Triangles);
    TestNotEqual(TEXT("Block 0's hash changes with its mesh"), Dug.PieceHash[0], First.PieceHash[0]);
    for (int32 Block = 1; Block < ReflectionsDig::BlocksPerChunk; ++Block)
    {
        TestEqual(FString::Printf(TEXT("Block %d, whose triangles the dig did not touch, keeps its hash"), Block), Dug.PieceHash[Block], First.PieceHash[Block]);
    }
    AddInfo(FString::Printf(TEXT("Hashes before: %s"), *DescribeHashes(First)));
    AddInfo(FString::Printf(TEXT("Hashes after:  %s"), *DescribeHashes(Dug)));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigPiecesWorstBlockStaysUnderTheLimitTest, "Reflections.Digging.Pieces.WorstBlockStaysUnderTheLimit", DigPiecesTestFlags)
bool FReflectionsDigPiecesWorstBlockStaysUnderTheLimitTest::RunTest(const FString& Parameters)
{
    // Cells alternate solid and air along every axis: every cube has a vertex and every edge a quad, the most
    // vertices the mesher can make for one chunk.
    FReflectionsDigChunkSamples Samples;
    Samples.Chunk = BusyChunk;
    Samples.LocalOriginCm = ChunkOrigin(BusyChunk);
    constexpr int32 Side = FReflectionsDigChunkSamples::Side;
    Samples.Density.SetNumZeroed(Side * Side * Side);
    Samples.Material.SetNumZeroed(Side * Side * Side);
    constexpr int32 Low = -ReflectionsDig::SampleBorder;
    constexpr int32 High = ReflectionsDig::ChunkCells - 1 + ReflectionsDig::SampleBorder;
    for (int32 Z = Low; Z <= High; ++Z)
    {
        for (int32 Y = Low; Y <= High; ++Y)
        {
            for (int32 X = Low; X <= High; ++X)
            {
                Samples.Density[FReflectionsDigChunkSamples::IndexOf(X, Y, Z)] = ((X + Y + Z + 3 * ReflectionsDig::SampleBorder) % 2 == 0) ? 64 : -64;
            }
        }
    }
    FReflectionsDigMeshData Worst;
    ReflectionsDigMesher::BuildFromSamples(Samples, Worst);
    constexpr int32 Cubes = (ReflectionsDig::ChunkCells + 1) * (ReflectionsDig::ChunkCells + 1) * (ReflectionsDig::ChunkCells + 1);
    TestTrue(FString::Printf(TEXT("Premise: nearly every one of the %d cubes has a vertex (%d)"), Cubes, Worst.Positions.Num()),
        Worst.Positions.Num() >= Cubes - 1);

    FReflectionsDigChunkResult Result;
    ReflectionsDigPieces::Build(Worst, Samples.LocalOriginCm, Result);
    TestEqual(TEXT("The worst chunk fills all eight blocks"), Result.NumPieces(), ReflectionsDig::BlocksPerChunk);
    FString Counts;
    for (int32 Block = 0; Block < ReflectionsDig::BlocksPerChunk; ++Block)
    {
        const int32 Vertices = Result.Pieces[Block].VertexCount();
        Counts += FString::Printf(TEXT("%s%d"), Block > 0 ? TEXT(", ") : TEXT(""), Vertices);
        TestTrue(FString::Printf(TEXT("Block %d holds at most %d vertices (%d)"), Block, ReflectionsDig::MaxPieceVertices, Vertices),
            Vertices <= ReflectionsDig::MaxPieceVertices);
    }
    TestEqual(TEXT("The pieces' triangles sum to the source count"), PieceTriangles(Result), Result.SourceTriangleCount);
    TestEqual(TEXT("Dropped triangles"), Result.DroppedTriangles, 0);
    UE_LOG(LogTemp, Display, TEXT("DIGSPIKE headless worst chunk: %d vertices, %d triangles; piece vertices by block: %s"),
        Worst.Positions.Num(), Result.SourceTriangleCount, *Counts);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigPiecesNavGeometryMatchesEachPieceTest, "Reflections.Digging.Pieces.NavGeometryMatchesEachPiece", DigPiecesTestFlags)
bool FReflectionsDigPiecesNavGeometryMatchesEachPieceTest::RunTest(const FString& Parameters)
{
    const FReflectionsDigMeshData Busy = MakeBusyMesh();
    FReflectionsDigChunkResult Result;
    ReflectionsDigPieces::Build(Busy, ChunkOrigin(BusyChunk), Result);
    if (!TestTrue(FString::Printf(TEXT("Premise: the busy mesh fills more than one block (%d pieces)"), Result.NumPieces()), Result.NumPieces() >= 2))
    {
        return true;
    }
    for (int32 Index = 0; Index < ReflectionsDig::BlocksPerChunk; ++Index)
    {
        const UE::Geometry::FDynamicMesh3& Piece = Result.Pieces[Index];
        const FReflectionsDigNavGeometry& Nav = Result.NavGeometry[Index];
        TestEqual(FString::Printf(TEXT("Piece %d: three indices per triangle"), Index), Nav.Indices.Num(), 3 * Piece.TriangleCount());
        if (Piece.TriangleCount() == 0)
        {
            TestEqual(FString::Printf(TEXT("Empty block %d: no navigation vertices"), Index), Nav.Vertices.Num(), 0);
            continue;
        }
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
