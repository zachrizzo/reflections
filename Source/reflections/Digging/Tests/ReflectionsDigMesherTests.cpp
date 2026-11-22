#include "Digging/ReflectionsDigMesher.h"

#include "CoreMinimal.h"
#include "Digging/ReflectionsDigGrid.h"
#include "Digging/ReflectionsDigTypes.h"
#include "Misc/AutomationTest.h"
#include "VectorUtil.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
    constexpr EAutomationTestFlags DigMesherTestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter;
    constexpr float FlatGroundHeightCm = 2800.0f;
    constexpr float BuriedGroundHeightCm = 6400.0f;

    FReflectionsDigGrid MakeTestGrid(float GroundHeightCm = FlatGroundHeightCm)
    {
        return FReflectionsDigGrid(FIntVector(3, 3, 2), FVector::ZeroVector, GroundHeightCm);
    }

    void Remove(FReflectionsDigGrid& Grid, const FVector& Center, float RadiusCm)
    {
        FReflectionsDigStamp Stamp;
        Stamp.Center = Center;
        Stamp.RadiusCm = RadiusCm;
        Stamp.Mode = EReflectionsDigMode::Remove;
        TArray<FIntVector> Dirty;
        Grid.ApplyStamp(Stamp, Dirty);
    }

    double AngleDegrees(const FVector3f& A, const FVector3f& B)
    {
        const double Dot = FMath::Clamp(static_cast<double>(A.GetSafeNormal() | B.GetSafeNormal()), -1.0, 1.0);
        return FMath::RadiansToDegrees(FMath::Acos(Dot));
    }

    FVector3f TriangleNormal(const FReflectionsDigMeshData& Mesh, int32 Triangle)
    {
        return UE::Geometry::VectorUtil::Normal(
            Mesh.Positions[Mesh.Triangles[3 * Triangle]],
            Mesh.Positions[Mesh.Triangles[3 * Triangle + 1]],
            Mesh.Positions[Mesh.Triangles[3 * Triangle + 2]]);
    }

    /** No triangle may be smaller than this. */
    constexpr float MinTriangleAreaCm2 = 0.01f;

    float TriangleAreaCm2(const FReflectionsDigMeshData& Mesh, int32 Triangle)
    {
        const FVector3f& A = Mesh.Positions[Mesh.Triangles[3 * Triangle]];
        const FVector3f& B = Mesh.Positions[Mesh.Triangles[3 * Triangle + 1]];
        const FVector3f& C = Mesh.Positions[Mesh.Triangles[3 * Triangle + 2]];
        return 0.5f * ((B - A) ^ (C - A)).Size();
    }

    struct FMismatchLog
    {
        int32 Count = 0;
        FString First;

        void Note(const FString& What)
        {
            if (Count++ == 0)
            {
                First = What;
            }
        }

        bool Check(FAutomationTestBase& Test, const FString& Label) const
        {
            return Test.TestEqual(FString::Printf(TEXT("%s mismatches (first: %s)"), *Label, *First), Count, 0);
        }
    };

    /**
     * Rules every mesh obeys: matching array sizes, indices in range, every vertex used, unit normals,
     * every triangle's area above 0.01 cm2, and on every triangle VectorUtil::Normal agrees in direction
     * with each of its three vertex normals.
     */
    bool CheckMeshInvariants(FAutomationTestBase& Test, const FReflectionsDigMeshData& Mesh, const FString& Label)
    {
        const int32 NumVertices = Mesh.Positions.Num();
        if (!Test.TestEqual(Label + TEXT(" normal count"), Mesh.Normals.Num(), NumVertices)
            || !Test.TestEqual(Label + TEXT(" material count"), Mesh.Materials.Num(), NumVertices)
            || !Test.TestEqual(Label + TEXT(" index count is a multiple of 3"), Mesh.Triangles.Num() % 3, 0))
        {
            return false;
        }

        FMismatchLog Indices;
        TArray<bool> Used;
        Used.SetNumZeroed(NumVertices);
        for (int32 Index : Mesh.Triangles)
        {
            if (Index < 0 || Index >= NumVertices)
            {
                Indices.Note(FString::Printf(TEXT("index %d out of range"), Index));
                continue;
            }
            Used[Index] = true;
        }
        if (!Indices.Check(Test, Label + TEXT(" indices")))
        {
            return false;
        }

        FMismatchLog Vertices;
        for (int32 Vertex = 0; Vertex < NumVertices; ++Vertex)
        {
            const FVector3f& Normal = Mesh.Normals[Vertex];
            const float Length = Normal.Size();
            if (!Used[Vertex])
            {
                Vertices.Note(FString::Printf(TEXT("vertex %d is used by no triangle"), Vertex));
            }
            else if (!(FMath::Abs(Length - 1.0f) <= 0.001f))
            {
                Vertices.Note(FString::Printf(TEXT("vertex %d normal length %f"), Vertex, Length));
            }
        }
        Vertices.Check(Test, Label + TEXT(" vertices"));

        FMismatchLog Areas;
        FMismatchLog Winding;
        for (int32 Triangle = 0; Triangle < Mesh.Triangles.Num() / 3; ++Triangle)
        {
            const float Area = TriangleAreaCm2(Mesh, Triangle);
            if (!(Area > MinTriangleAreaCm2))
            {
                Areas.Note(FString::Printf(TEXT("triangle %d area %f cm2"), Triangle, Area));
            }
            const FVector3f Face = TriangleNormal(Mesh, Triangle);
            for (int32 Corner = 0; Corner < 3; ++Corner)
            {
                const int32 Vertex = Mesh.Triangles[3 * Triangle + Corner];
                if (!((Face | Mesh.Normals[Vertex]) > 0.0f))
                {
                    Winding.Note(FString::Printf(TEXT("triangle %d normal (%s) disagrees with vertex %d normal (%s)"),
                        Triangle, *Face.ToString(), Vertex, *Mesh.Normals[Vertex].ToString()));
                }
            }
        }
        Areas.Check(Test, Label + TEXT(" triangle areas"));
        Winding.Check(Test, Label + TEXT(" winding"));
        return true;
    }

    /** The crater the border tests share: Remove at (1600, 2400, 2600), radius 200, meshed in chunks (0, 1, 1) and (1, 1, 1). */
    void BuildBorderCraterMeshes(FReflectionsDigMeshData& OutLeft, FReflectionsDigMeshData& OutRight)
    {
        FReflectionsDigGrid Grid = MakeTestGrid();
        Remove(Grid, FVector(1600.0, 2400.0, 2600.0), 200.0f);
        ReflectionsDigMesher::BuildChunk(Grid, FIntVector(0, 1, 1), OutLeft);
        ReflectionsDigMesher::BuildChunk(Grid, FIntVector(1, 1, 1), OutRight);
    }

    bool PositionsMatch(const FVector3f& A, const FVector3f& B)
    {
        return FVector3f::DistSquared(A, B) <= 0.01f * 0.01f;
    }
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigMesherUniformChunkIsEmptyTest, "Reflections.Digging.Mesher.UniformChunkIsEmpty", DigMesherTestFlags)
bool FReflectionsDigMesherUniformChunkIsEmptyTest::RunTest(const FString& Parameters)
{
    const FReflectionsDigGrid Grid = MakeTestGrid();

    // Fill Out first so the test also shows that a build resets it.
    FReflectionsDigMeshData Mesh;
    ReflectionsDigMesher::BuildChunk(Grid, FIntVector(1, 1, 1), Mesh);
    TestFalse(TEXT("the flat chunk filled the mesh first"), Mesh.IsEmpty());

    ReflectionsDigMesher::BuildChunk(Grid, FIntVector(1, 1, 0), Mesh);
    TestTrue(TEXT("all-solid chunk (1, 1, 0) is empty"), Mesh.IsEmpty());
    TestEqual(TEXT("all-solid chunk triangles"), Mesh.Triangles.Num(), 0);
    TestEqual(TEXT("all-solid chunk vertices"), Mesh.Positions.Num(), 0);
    TestEqual(TEXT("all-solid chunk normals"), Mesh.Normals.Num(), 0);
    TestEqual(TEXT("all-solid chunk materials"), Mesh.Materials.Num(), 0);

    constexpr int32 Side = FReflectionsDigChunkSamples::Side;
    FReflectionsDigChunkSamples Air;
    Air.Density.Init(-ReflectionsDig::DensityMax, Side * Side * Side);
    Air.Material.Init(ReflectionsDig::MaterialTopsoil, Side * Side * Side);
    ReflectionsDigMesher::BuildFromSamples(Air, Mesh);
    TestTrue(TEXT("a block of -127 is empty"), Mesh.IsEmpty());
    TestEqual(TEXT("a block of -127 has no vertices"), Mesh.Positions.Num(), 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigMesherFlatGroundIsFlatTest, "Reflections.Digging.Mesher.FlatGroundIsFlat", DigMesherTestFlags)
bool FReflectionsDigMesherFlatGroundIsFlatTest::RunTest(const FString& Parameters)
{
    const FReflectionsDigGrid Grid = MakeTestGrid();
    FReflectionsDigMeshData Mesh;
    ReflectionsDigMesher::BuildChunk(Grid, FIntVector(1, 1, 1), Mesh);

    TestEqual(TEXT("triangle count"), Mesh.Triangles.Num() / 3, 2048);
    if (!CheckMeshInvariants(*this, Mesh, TEXT("flat chunk")))
    {
        return true;
    }

    const FVector3f Up(0.0f, 0.0f, 1.0f);
    FMismatchLog Vertices;
    for (int32 Vertex = 0; Vertex < Mesh.Positions.Num(); ++Vertex)
    {
        const FVector3f& Position = Mesh.Positions[Vertex];
        if (!(FMath::Abs(Position.Z - FlatGroundHeightCm) <= 1.0f))
        {
            Vertices.Note(FString::Printf(TEXT("vertex %d at %s is off the ground"), Vertex, *Position.ToString()));
        }
        else if (!(AngleDegrees(Mesh.Normals[Vertex], Up) <= 1.0))
        {
            Vertices.Note(FString::Printf(TEXT("vertex %d normal %s is not up"), Vertex, *Mesh.Normals[Vertex].ToString()));
        }
    }
    Vertices.Check(*this, TEXT("flat vertices"));

    FMismatchLog Faces;
    for (int32 Triangle = 0; Triangle < Mesh.Triangles.Num() / 3; ++Triangle)
    {
        const FVector3f Face = TriangleNormal(Mesh, Triangle);
        if (!(AngleDegrees(Face, Up) <= 1.0))
        {
            Faces.Note(FString::Printf(TEXT("triangle %d normal %s is not up"), Triangle, *Face.ToString()));
        }
    }
    Faces.Check(*this, TEXT("flat triangles"));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigMesherNeighboursShareBorderVerticesTest, "Reflections.Digging.Mesher.NeighboursShareBorderVertices", DigMesherTestFlags)
bool FReflectionsDigMesherNeighboursShareBorderVerticesTest::RunTest(const FString& Parameters)
{
    FReflectionsDigMeshData Left;
    FReflectionsDigMeshData Right;
    BuildBorderCraterMeshes(Left, Right);
    if (!CheckMeshInvariants(*this, Left, TEXT("chunk (0, 1, 1)")) || !CheckMeshInvariants(*this, Right, TEXT("chunk (1, 1, 1)")))
    {
        return true;
    }

    const double MaxNormalAngle = 0.1;
    auto CheckTwins = [&](const FReflectionsDigMeshData& From, const FReflectionsDigMeshData& To, const TCHAR* Label)
    {
        FMismatchLog Twins;
        int32 BorderVertices = 0;
        for (int32 Vertex = 0; Vertex < From.Positions.Num(); ++Vertex)
        {
            const FVector3f& Position = From.Positions[Vertex];
            if (Position.X < 1550.0f || Position.X > 1600.0f)
            {
                continue;
            }
            ++BorderVertices;
            int32 Twin = INDEX_NONE;
            for (int32 Other = 0; Other < To.Positions.Num(); ++Other)
            {
                if (PositionsMatch(Position, To.Positions[Other]))
                {
                    Twin = Other;
                    break;
                }
            }
            if (Twin == INDEX_NONE)
            {
                Twins.Note(FString::Printf(TEXT("vertex %d at %s has no twin"), Vertex, *Position.ToString()));
            }
            else if (!(AngleDegrees(From.Normals[Vertex], To.Normals[Twin]) <= MaxNormalAngle))
            {
                Twins.Note(FString::Printf(TEXT("vertex %d at %s: normal %s, twin's %s"),
                    Vertex, *Position.ToString(), *From.Normals[Vertex].ToString(), *To.Normals[Twin].ToString()));
            }
        }
        TestTrue(FString::Printf(TEXT("%s has border vertices"), Label), BorderVertices > 0);
        Twins.Check(*this, Label);
    };
    CheckTwins(Left, Right, TEXT("chunk (0, 1, 1) border vertices"));
    CheckTwins(Right, Left, TEXT("chunk (1, 1, 1) border vertices"));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigMesherQuadsAreNotDuplicatedAcrossChunksTest, "Reflections.Digging.Mesher.QuadsAreNotDuplicatedAcrossChunks", DigMesherTestFlags)
bool FReflectionsDigMesherQuadsAreNotDuplicatedAcrossChunksTest::RunTest(const FString& Parameters)
{
    FReflectionsDigMeshData Left;
    FReflectionsDigMeshData Right;
    BuildBorderCraterMeshes(Left, Right);
    if (!CheckMeshInvariants(*this, Left, TEXT("chunk (0, 1, 1)")) || !CheckMeshInvariants(*this, Right, TEXT("chunk (1, 1, 1)")))
    {
        return true;
    }
    TestTrue(TEXT("chunk (0, 1, 1) has triangles"), !Left.IsEmpty());
    TestTrue(TEXT("chunk (1, 1, 1) has triangles"), !Right.IsEmpty());

    auto Corner = [](const FReflectionsDigMeshData& Mesh, int32 Triangle, int32 Index) -> const FVector3f&
    {
        return Mesh.Positions[Mesh.Triangles[3 * Triangle + Index]];
    };
    // Every corner of triangle A matches some corner of triangle B.
    auto CornersCovered = [&](const FReflectionsDigMeshData& MeshA, int32 TriangleA, const FReflectionsDigMeshData& MeshB, int32 TriangleB)
    {
        for (int32 Index = 0; Index < 3; ++Index)
        {
            const FVector3f& Position = Corner(MeshA, TriangleA, Index);
            if (!PositionsMatch(Position, Corner(MeshB, TriangleB, 0))
                && !PositionsMatch(Position, Corner(MeshB, TriangleB, 1))
                && !PositionsMatch(Position, Corner(MeshB, TriangleB, 2)))
            {
                return false;
            }
        }
        return true;
    };
    // Same set of three positions, within 0.01 cm, in both directions.
    auto SameTriangle = [&](int32 LeftTriangle, int32 RightTriangle)
    {
        return CornersCovered(Left, LeftTriangle, Right, RightTriangle) && CornersCovered(Right, RightTriangle, Left, LeftTriangle);
    };

    FMismatchLog Duplicates;
    for (int32 LeftTriangle = 0; LeftTriangle < Left.Triangles.Num() / 3; ++LeftTriangle)
    {
        for (int32 RightTriangle = 0; RightTriangle < Right.Triangles.Num() / 3; ++RightTriangle)
        {
            if (SameTriangle(LeftTriangle, RightTriangle))
            {
                Duplicates.Note(FString::Printf(TEXT("triangle at %s appears in both chunks"), *Corner(Left, LeftTriangle, 0).ToString()));
            }
        }
    }
    Duplicates.Check(*this, TEXT("triangles in both chunks"));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigMesherBuriedSphereIsClosedTest, "Reflections.Digging.Mesher.BuriedSphereIsClosed", DigMesherTestFlags)
bool FReflectionsDigMesherBuriedSphereIsClosedTest::RunTest(const FString& Parameters)
{
    FReflectionsDigGrid Grid = MakeTestGrid(BuriedGroundHeightCm);
    const FVector3f Center(2400.0f, 2400.0f, 2400.0f);
    Remove(Grid, FVector(Center), 200.0f);
    FReflectionsDigMeshData Mesh;
    ReflectionsDigMesher::BuildChunk(Grid, FIntVector(1, 1, 1), Mesh);

    TestTrue(TEXT("the sphere has triangles"), Mesh.Triangles.Num() >= 3);
    if (!CheckMeshInvariants(*this, Mesh, TEXT("sphere")))
    {
        return true;
    }

    TMap<uint64, int32> EdgeUses;
    for (int32 Triangle = 0; Triangle < Mesh.Triangles.Num() / 3; ++Triangle)
    {
        for (int32 Corner = 0; Corner < 3; ++Corner)
        {
            const uint32 A = static_cast<uint32>(Mesh.Triangles[3 * Triangle + Corner]);
            const uint32 B = static_cast<uint32>(Mesh.Triangles[3 * Triangle + (Corner + 1) % 3]);
            const uint64 Key = (static_cast<uint64>(FMath::Min(A, B)) << 32) | FMath::Max(A, B);
            ++EdgeUses.FindOrAdd(Key);
        }
    }
    FMismatchLog Edges;
    for (const TPair<uint64, int32>& Edge : EdgeUses)
    {
        if (Edge.Value != 2)
        {
            Edges.Note(FString::Printf(TEXT("edge (%u, %u) used by %d triangles"),
                static_cast<uint32>(Edge.Key >> 32), static_cast<uint32>(Edge.Key & 0xffffffffu), Edge.Value));
        }
    }
    Edges.Check(*this, TEXT("sphere edges"));

    FMismatchLog Normals;
    for (int32 Vertex = 0; Vertex < Mesh.Positions.Num(); ++Vertex)
    {
        if (!((Mesh.Normals[Vertex] | (Center - Mesh.Positions[Vertex])) > 0.0f))
        {
            Normals.Note(FString::Printf(TEXT("vertex %d at %s: normal %s points away from the centre"),
                Vertex, *Mesh.Positions[Vertex].ToString(), *Mesh.Normals[Vertex].ToString()));
        }
    }
    Normals.Check(*this, TEXT("sphere normals"));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigMesherCellCentredDigsMakeNoDegenerateTrianglesTest, "Reflections.Digging.Mesher.CellCentredDigsMakeNoDegenerateTriangles", DigMesherTestFlags)
bool FReflectionsDigMesherCellCentredDigsMakeNoDegenerateTrianglesTest::RunTest(const FString& Parameters)
{
    // Radius-100 digs centred exactly on cells leave cells of density exactly 0 two cells from each centre.
    // Under a 0-level surface those cells collapsed up to four vertices onto one point. The block of eight
    // centres, 4 cells apart, sits underground at cells x 30 and 34 (across the chunk border at x = 32),
    // y 46 and 50, z 44 and 48.
    FReflectionsDigGrid Grid = MakeTestGrid();
    TArray<FIntVector> Centres;
    for (int32 Z : { 44, 48 })
    {
        for (int32 Y : { 46, 50 })
        {
            for (int32 X : { 30, 34 })
            {
                Centres.Add(FIntVector(X, Y, Z));
                Remove(Grid, Grid.CellToWorld(FIntVector(X, Y, Z)), 100.0f);
            }
        }
    }

    int32 ZeroCells = 0;
    for (const FIntVector& Centre : Centres)
    {
        for (const FIntVector& Step : { FIntVector(2, 0, 0), FIntVector(-2, 0, 0), FIntVector(0, 2, 0), FIntVector(0, -2, 0), FIntVector(0, 0, 2), FIntVector(0, 0, -2) })
        {
            ZeroCells += Grid.GetDensity(Centre + Step) == 0 ? 1 : 0;
        }
    }
    TestEqual(TEXT("premise: the six cells two steps from each centre have density 0"), ZeroCells, 6 * Centres.Num());

    for (const FIntVector& Chunk : { FIntVector(0, 1, 1), FIntVector(1, 1, 1) })
    {
        const FString Label = FString::Printf(TEXT("chunk (%d, %d, %d)"), Chunk.X, Chunk.Y, Chunk.Z);
        FReflectionsDigMeshData Mesh;
        ReflectionsDigMesher::BuildChunk(Grid, Chunk, Mesh);
        TestFalse(Label + TEXT(" has triangles"), Mesh.IsEmpty());
        CheckMeshInvariants(*this, Mesh, Label);
    }
    return true;
}

#endif
