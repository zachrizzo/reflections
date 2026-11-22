#include "Digging/ReflectionsDigGrid.h"

#include "CoreMinimal.h"
#include "Digging/ReflectionsDigTypes.h"
#include "HAL/PlatformTime.h"
#include "Misc/AutomationTest.h"

#include <limits>

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
    constexpr EAutomationTestFlags DigGridTestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter;
    constexpr float TestGroundHeightCm = 2800.0f;

    FReflectionsDigGrid MakeTestGrid()
    {
        return FReflectionsDigGrid(FIntVector(3, 3, 2), FVector::ZeroVector, TestGroundHeightCm);
    }

    /** The brief's initial density, written out independently of the grid: clamp(round(d / 50 * 64), -127, 127). */
    int8 ExpectedInitialDensity(int32 CellZ)
    {
        const double DistanceCm = TestGroundHeightCm - static_cast<double>(CellZ) * 50.0;
        const double Rounded = FMath::RoundHalfFromZero(DistanceCm / 50.0 * 64.0);
        return static_cast<int8>(FMath::Clamp(Rounded, -127.0, 127.0));
    }

    FReflectionsDigStamp MakeStamp(const FVector& Center, float RadiusCm, EReflectionsDigMode Mode, uint8 Material = ReflectionsDig::MaterialTopsoil)
    {
        FReflectionsDigStamp Stamp;
        Stamp.Center = Center;
        Stamp.RadiusCm = RadiusCm;
        Stamp.Mode = Mode;
        Stamp.Material = Material;
        return Stamp;
    }

    /** Calls Visit(Cell, DistanceCm) for every grid cell within LimitCm of Center (or farther than LimitCm, with bFarther). */
    template <typename FunctorType>
    void ForEachCellByDistance(const FReflectionsDigGrid& Grid, const FVector& Center, double LimitCm, bool bFarther, FunctorType&& Visit)
    {
        const FIntVector Size = Grid.GetSizeInCells();
        for (int32 Z = 0; Z < Size.Z; ++Z)
        {
            for (int32 Y = 0; Y < Size.Y; ++Y)
            {
                for (int32 X = 0; X < Size.X; ++X)
                {
                    const FIntVector Cell(X, Y, Z);
                    const double Distance = FVector::Dist(Grid.CellToWorld(Cell), Center);
                    if (bFarther ? Distance > LimitCm : Distance <= LimitCm)
                    {
                        Visit(Cell, Distance);
                    }
                }
            }
        }
    }

    struct FMismatchLog
    {
        int32 Count = 0;
        FString First;

        void Note(const FIntVector& Cell, const TCHAR* What, int32 Got)
        {
            if (Count++ == 0)
            {
                First = FString::Printf(TEXT("cell (%d, %d, %d): %s, got %d"), Cell.X, Cell.Y, Cell.Z, What, Got);
            }
        }

        bool Check(FAutomationTestBase& Test, const TCHAR* Label) const
        {
            return Test.TestEqual(FString::Printf(TEXT("%s mismatches (first: %s)"), Label, *First), Count, 0);
        }
    };

    struct FGridSnapshot
    {
        TArray<int8> Density;
        TArray<uint8> Material;
    };

    FGridSnapshot SnapshotAllChunks(const FReflectionsDigGrid& Grid)
    {
        FGridSnapshot Snapshot;
        const FIntVector Chunks = Grid.GetSizeInChunks();
        for (int32 Z = 0; Z < Chunks.Z; ++Z)
        {
            for (int32 Y = 0; Y < Chunks.Y; ++Y)
            {
                for (int32 X = 0; X < Chunks.X; ++X)
                {
                    FReflectionsDigChunkSamples Samples;
                    Grid.CopyChunkSamples(FIntVector(X, Y, Z), Samples);
                    Snapshot.Density.Append(Samples.Density);
                    Snapshot.Material.Append(Samples.Material);
                }
            }
        }
        return Snapshot;
    }
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigGridInitialGroundIsFlatTest, "Reflections.Digging.Grid.InitialGroundIsFlat", DigGridTestFlags)
bool FReflectionsDigGridInitialGroundIsFlatTest::RunTest(const FString& Parameters)
{
    const FReflectionsDigGrid Grid = MakeTestGrid();
    TestEqual(TEXT("size in cells"), Grid.GetSizeInCells(), FIntVector(96, 96, 64));

    FMismatchLog Mismatches;
    const FIntVector Size = Grid.GetSizeInCells();
    for (int32 Z = 0; Z < Size.Z; ++Z)
    {
        for (int32 Y = 0; Y < Size.Y; ++Y)
        {
            for (int32 X = 0; X < Size.X; ++X)
            {
                const FIntVector Cell(X, Y, Z);
                const double CellZ = Grid.CellToWorld(Cell).Z;
                const int8 Density = Grid.GetDensity(Cell);
                if (CellZ < TestGroundHeightCm - 25.0 && Density <= 0)
                {
                    Mismatches.Note(Cell, TEXT("below ground but not solid"), Density);
                }
                else if (CellZ > TestGroundHeightCm + 25.0 && Density > 0)
                {
                    Mismatches.Note(Cell, TEXT("above ground but solid"), Density);
                }
                else if (CellZ == TestGroundHeightCm && Density != 0)
                {
                    Mismatches.Note(Cell, TEXT("at ground height but density not 0"), Density);
                }
            }
        }
    }
    Mismatches.Check(*this, TEXT("flat ground"));
    TestEqual(TEXT("cell at 2800 cm has density 0"), static_cast<int32>(Grid.GetDensity(FIntVector(48, 48, 56))), 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigGridRemoveClearsInsideRadiusTest, "Reflections.Digging.Grid.RemoveClearsInsideRadius", DigGridTestFlags)
bool FReflectionsDigGridRemoveClearsInsideRadiusTest::RunTest(const FString& Parameters)
{
    FReflectionsDigGrid Grid = MakeTestGrid();
    const FVector Center(2400.0, 2400.0, 2400.0);
    TArray<FIntVector> Dirty;
    Grid.ApplyStamp(MakeStamp(Center, 200.0f, EReflectionsDigMode::Remove), Dirty);
    TestTrue(TEXT("the stamp dirtied chunks"), Dirty.Num() > 0);

    FMismatchLog Inside;
    int32 InsideCount = 0;
    ForEachCellByDistance(Grid, Center, 150.0, false, [&](const FIntVector& Cell, double)
    {
        ++InsideCount;
        const int8 Density = Grid.GetDensity(Cell);
        if (Density >= 0)
        {
            Inside.Note(Cell, TEXT("within 150 cm but density not below 0"), Density);
        }
    });
    TestTrue(TEXT("cells within 150 cm exist"), InsideCount > 0);
    Inside.Check(*this, TEXT("inside radius"));

    FMismatchLog Outside;
    ForEachCellByDistance(Grid, Center, 300.0, true, [&](const FIntVector& Cell, double)
    {
        const int8 Density = Grid.GetDensity(Cell);
        if (Density != ExpectedInitialDensity(Cell.Z))
        {
            Outside.Note(Cell, TEXT("farther than 300 cm but changed"), Density);
        }
    });
    Outside.Check(*this, TEXT("outside radius"));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigGridAddRestoresSolidTest, "Reflections.Digging.Grid.AddRestoresSolid", DigGridTestFlags)
bool FReflectionsDigGridAddRestoresSolidTest::RunTest(const FString& Parameters)
{
    FReflectionsDigGrid Grid = MakeTestGrid();
    const FVector Center(2400.0, 2400.0, 2400.0);
    TArray<FIntVector> Dirty;
    Grid.ApplyStamp(MakeStamp(Center, 200.0f, EReflectionsDigMode::Remove), Dirty);
    Dirty.Reset();
    Grid.ApplyStamp(MakeStamp(Center, 200.0f, EReflectionsDigMode::Add, 7), Dirty);
    TestTrue(TEXT("the Add dirtied chunks"), Dirty.Num() > 0);

    FMismatchLog Inside;
    ForEachCellByDistance(Grid, Center, 150.0, false, [&](const FIntVector& Cell, double)
    {
        const int8 Density = Grid.GetDensity(Cell);
        const uint8 Material = Grid.GetMaterial(Cell);
        if (Density <= 0)
        {
            Inside.Note(Cell, TEXT("within 150 cm but not solid"), Density);
        }
        else if (Material != 7)
        {
            Inside.Note(Cell, TEXT("within 150 cm but material not 7"), Material);
        }
    });
    Inside.Check(*this, TEXT("inside radius"));

    FMismatchLog Outside;
    ForEachCellByDistance(Grid, Center, 300.0, true, [&](const FIntVector& Cell, double)
    {
        const FIntVector Size = Grid.GetSizeInCells();
        const bool bBedrock = Cell.Z == 0 || Cell.X == 0 || Cell.Y == 0 || Cell.X == Size.X - 1 || Cell.Y == Size.Y - 1;
        const uint8 Material = Grid.GetMaterial(Cell);
        if (!bBedrock && Material != ReflectionsDig::MaterialTopsoil)
        {
            Outside.Note(Cell, TEXT("farther than 300 cm but material not 0"), Material);
        }
    });
    Outside.Check(*this, TEXT("outside radius"));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigGridStampOnChunkCornerDirtiesEightChunksTest, "Reflections.Digging.Grid.StampOnChunkCornerDirtiesEightChunks", DigGridTestFlags)
bool FReflectionsDigGridStampOnChunkCornerDirtiesEightChunksTest::RunTest(const FString& Parameters)
{
    FReflectionsDigGrid Grid = MakeTestGrid();
    TArray<FIntVector> Dirty;
    Grid.ApplyStamp(MakeStamp(FVector(1600.0, 1600.0, 1600.0), 100.0f, EReflectionsDigMode::Remove), Dirty);

    TestEqual(TEXT("dirty chunk count"), Dirty.Num(), 8);
    TSet<FIntVector> Unique(Dirty);
    TestEqual(TEXT("no repeated chunks"), Unique.Num(), Dirty.Num());
    for (int32 Z = 0; Z <= 1; ++Z)
    {
        for (int32 Y = 0; Y <= 1; ++Y)
        {
            for (int32 X = 0; X <= 1; ++X)
            {
                const FIntVector Chunk(X, Y, Z);
                TestTrue(FString::Printf(TEXT("chunk (%d, %d, %d) is dirty"), X, Y, Z), Unique.Contains(Chunk));
            }
        }
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigGridStampOutsideBoundsIsNoOpTest, "Reflections.Digging.Grid.StampOutsideBoundsIsNoOp", DigGridTestFlags)
bool FReflectionsDigGridStampOutsideBoundsIsNoOpTest::RunTest(const FString& Parameters)
{
    FReflectionsDigGrid Grid = MakeTestGrid();
    const FGridSnapshot Before = SnapshotAllChunks(Grid);
    TArray<FIntVector> Dirty;
    Grid.ApplyStamp(MakeStamp(FVector(-5000.0, -5000.0, -5000.0), 100.0f, EReflectionsDigMode::Remove), Dirty);
    const FGridSnapshot After = SnapshotAllChunks(Grid);

    TestEqual(TEXT("no dirty chunks"), Dirty.Num(), 0);
    TestTrue(TEXT("a snapshot was taken"), Before.Density.Num() > 0);
    TestTrue(TEXT("density bytes unchanged"), Before.Density == After.Density);
    TestTrue(TEXT("material bytes unchanged"), Before.Material == After.Material);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigGridStampHalfOutsideIsClippedTest, "Reflections.Digging.Grid.StampHalfOutsideIsClipped", DigGridTestFlags)
bool FReflectionsDigGridStampHalfOutsideIsClippedTest::RunTest(const FString& Parameters)
{
    FReflectionsDigGrid Grid = MakeTestGrid();
    TArray<FIntVector> Dirty;
    Grid.ApplyStamp(MakeStamp(FVector(0.0, 2400.0, 2400.0), 200.0f, EReflectionsDigMode::Remove), Dirty);

    TestTrue(TEXT("cell (2, 48, 48) density below 0"), Grid.GetDensity(FIntVector(2, 48, 48)) < 0);

    FMismatchLog Wall;
    const FIntVector Size = Grid.GetSizeInCells();
    for (int32 Z = 0; Z < Size.Z; ++Z)
    {
        for (int32 Y = 0; Y < Size.Y; ++Y)
        {
            const FIntVector Cell(0, Y, Z);
            const int8 Density = Grid.GetDensity(Cell);
            const uint8 Material = Grid.GetMaterial(Cell);
            if (Density != ExpectedInitialDensity(Z))
            {
                Wall.Note(Cell, TEXT("wall density changed"), Density);
            }
            else if (Material != ReflectionsDig::MaterialBedrock)
            {
                Wall.Note(Cell, TEXT("wall material not 255"), Material);
            }
        }
    }
    Wall.Check(*this, TEXT("x = 0 wall"));

    TestEqual(TEXT("cell (-1, 48, 48) keeps the initial density"),
        static_cast<int32>(Grid.GetDensity(FIntVector(-1, 48, 48))), static_cast<int32>(ExpectedInitialDensity(48)));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigGridBedrockCannotBeRemovedTest, "Reflections.Digging.Grid.BedrockCannotBeRemoved", DigGridTestFlags)
bool FReflectionsDigGridBedrockCannotBeRemovedTest::RunTest(const FString& Parameters)
{
    FReflectionsDigGrid Grid = MakeTestGrid();
    const FVector Center(2400.0, 2400.0, 0.0);
    TArray<FIntVector> Dirty;
    Grid.ApplyStamp(MakeStamp(Center, 300.0f, EReflectionsDigMode::Remove), Dirty);

    FMismatchLog Floor;
    int32 FloorCount = 0;
    ForEachCellByDistance(Grid, Center, 300.0, false, [&](const FIntVector& Cell, double)
    {
        if (Cell.Z != 0)
        {
            return;
        }
        ++FloorCount;
        const int8 Density = Grid.GetDensity(Cell);
        const uint8 Material = Grid.GetMaterial(Cell);
        if (Density != 127)
        {
            Floor.Note(Cell, TEXT("floor density not 127"), Density);
        }
        else if (Material != ReflectionsDig::MaterialBedrock)
        {
            Floor.Note(Cell, TEXT("floor material not 255"), Material);
        }
    });
    TestTrue(TEXT("floor cells within the radius exist"), FloorCount > 0);
    Floor.Check(*this, TEXT("floor"));
    TestTrue(TEXT("cell (48, 48, 2) density below 0"), Grid.GetDensity(FIntVector(48, 48, 2)) < 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigGridSideWallsAreBedrockTest, "Reflections.Digging.Grid.SideWallsAreBedrock", DigGridTestFlags)
bool FReflectionsDigGridSideWallsAreBedrockTest::RunTest(const FString& Parameters)
{
    FReflectionsDigGrid Grid = MakeTestGrid();
    const FIntVector Size = Grid.GetSizeInCells();

    auto CheckBedrockFaces = [&](const TCHAR* Label)
    {
        FMismatchLog Faces;
        for (int32 Z = 0; Z < Size.Z; ++Z)
        {
            for (int32 Y = 0; Y < Size.Y; ++Y)
            {
                for (int32 X = 0; X < Size.X; ++X)
                {
                    const bool bFace = Z == 0 || X == 0 || Y == 0 || X == Size.X - 1 || Y == Size.Y - 1;
                    const FIntVector Cell(X, Y, Z);
                    if (bFace && Grid.GetMaterial(Cell) != ReflectionsDig::MaterialBedrock)
                    {
                        Faces.Note(Cell, TEXT("face material not 255"), Grid.GetMaterial(Cell));
                    }
                }
            }
        }
        Faces.Check(*this, Label);
    };

    CheckBedrockFaces(TEXT("bedrock faces"));
    TestEqual(TEXT("cell (48, 48, 30) is topsoil"), static_cast<int32>(Grid.GetMaterial(FIntVector(48, 48, 30))), 0);

    // An Add above the ground that reaches into the x = 0 wall.
    TArray<FIntVector> Dirty;
    Grid.ApplyStamp(MakeStamp(FVector(50.0, 2400.0, 3000.0), 200.0f, EReflectionsDigMode::Add, 7), Dirty);
    TestEqual(TEXT("the Add filled the cell beside the wall with material 7"), static_cast<int32>(Grid.GetMaterial(FIntVector(1, 48, 60))), 7);
    TestEqual(TEXT("the wall cell next to it keeps its density"),
        static_cast<int32>(Grid.GetDensity(FIntVector(0, 48, 60))), static_cast<int32>(ExpectedInitialDensity(60)));
    CheckBedrockFaces(TEXT("bedrock faces after Add"));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigGridCopyChunkSamplesMatchesGettersTest, "Reflections.Digging.Grid.CopyChunkSamplesMatchesGetters", DigGridTestFlags)
bool FReflectionsDigGridCopyChunkSamplesMatchesGettersTest::RunTest(const FString& Parameters)
{
    FReflectionsDigGrid Grid = MakeTestGrid();
    // Dig across the corner of chunk (0, 0, 0) and (1, 1, 1) so the copies hold changed cells too.
    TArray<FIntVector> Dirty;
    Grid.ApplyStamp(MakeStamp(FVector(1600.0, 1600.0, 1600.0), 300.0f, EReflectionsDigMode::Remove), Dirty);

    constexpr int32 Side = FReflectionsDigChunkSamples::Side;
    for (const FIntVector& Chunk : { FIntVector(1, 1, 1), FIntVector(0, 0, 0) })
    {
        FReflectionsDigChunkSamples Samples;
        Grid.CopyChunkSamples(Chunk, Samples);
        const FString Label = FString::Printf(TEXT("chunk (%d, %d, %d)"), Chunk.X, Chunk.Y, Chunk.Z);
        TestEqual(Label + TEXT(" chunk"), Samples.Chunk, Chunk);
        TestEqual(Label + TEXT(" local origin"), Samples.LocalOriginCm, FVector3f(Chunk * ReflectionsDig::ChunkCells) * ReflectionsDig::CellSizeCm);
        if (!TestEqual(Label + TEXT(" density size"), Samples.Density.Num(), Side * Side * Side)
            || !TestEqual(Label + TEXT(" material size"), Samples.Material.Num(), Side * Side * Side))
        {
            continue;
        }

        FMismatchLog Mismatches;
        const FIntVector Base = Chunk * ReflectionsDig::ChunkCells;
        for (int32 Z = -ReflectionsDig::SampleBorder; Z < ReflectionsDig::ChunkCells + ReflectionsDig::SampleBorder; ++Z)
        {
            for (int32 Y = -ReflectionsDig::SampleBorder; Y < ReflectionsDig::ChunkCells + ReflectionsDig::SampleBorder; ++Y)
            {
                for (int32 X = -ReflectionsDig::SampleBorder; X < ReflectionsDig::ChunkCells + ReflectionsDig::SampleBorder; ++X)
                {
                    const FIntVector Cell = Base + FIntVector(X, Y, Z);
                    if (Samples.DensityAt(X, Y, Z) != Grid.GetDensity(Cell))
                    {
                        Mismatches.Note(Cell, TEXT("density differs from GetDensity"), Samples.DensityAt(X, Y, Z));
                    }
                    else if (Samples.MaterialAt(X, Y, Z) != Grid.GetMaterial(Cell))
                    {
                        Mismatches.Note(Cell, TEXT("material differs from GetMaterial"), Samples.MaterialAt(X, Y, Z));
                    }
                }
            }
        }
        Mismatches.Check(*this, *Label);

        // Pin the raw array order: X varies fastest, then Y, then Z.
        TestEqual(Label + TEXT(" Density[0] is local (-2, -2, -2)"), static_cast<int32>(Samples.Density[0]), static_cast<int32>(Grid.GetDensity(Base + FIntVector(-2, -2, -2))));
        TestEqual(Label + TEXT(" Density[1] is local (-1, -2, -2)"), static_cast<int32>(Samples.Density[1]), static_cast<int32>(Grid.GetDensity(Base + FIntVector(-1, -2, -2))));
        TestEqual(Label + TEXT(" Density[36] is local (-2, -1, -2)"), static_cast<int32>(Samples.Density[Side]), static_cast<int32>(Grid.GetDensity(Base + FIntVector(-2, -1, -2))));
        TestEqual(Label + TEXT(" Density[36 * 36] is local (-2, -2, -1)"), static_cast<int32>(Samples.Density[Side * Side]), static_cast<int32>(Grid.GetDensity(Base + FIntVector(-2, -2, -1))));
    }

    // The digs above leave the first border cells of those chunks equal to their neighbours (clamped or untouched),
    // so pin the order again where a second dig makes local (-2, -2, -2) and its three +1 neighbours all differ.
    // Chunk (2, 1, 1) has local (-2, -2, -2) at cell (62, 30, 30); the stamp sits at cell (61, 28, 27).
    Grid.ApplyStamp(MakeStamp(FVector(3050.0, 1400.0, 1350.0), 200.0f, EReflectionsDigMode::Remove), Dirty);
    const FIntVector Chunk(2, 1, 1);
    const FIntVector Base = Chunk * ReflectionsDig::ChunkCells;
    FReflectionsDigChunkSamples Samples;
    Grid.CopyChunkSamples(Chunk, Samples);
    const int32 Origin = Grid.GetDensity(Base + FIntVector(-2, -2, -2));
    const int32 PlusX = Grid.GetDensity(Base + FIntVector(-1, -2, -2));
    const int32 PlusY = Grid.GetDensity(Base + FIntVector(-2, -1, -2));
    const int32 PlusZ = Grid.GetDensity(Base + FIntVector(-2, -2, -1));
    TestTrue(TEXT("premise: the four first border cells of chunk (2, 1, 1) all differ"),
        Origin != PlusX && Origin != PlusY && Origin != PlusZ && PlusX != PlusY && PlusX != PlusZ && PlusY != PlusZ);
    TestEqual(TEXT("chunk (2, 1, 1) Density[0] is local (-2, -2, -2)"), static_cast<int32>(Samples.Density[0]), Origin);
    TestEqual(TEXT("chunk (2, 1, 1) Density[1] is local (-1, -2, -2)"), static_cast<int32>(Samples.Density[1]), PlusX);
    TestEqual(TEXT("chunk (2, 1, 1) Density[36] is local (-2, -1, -2)"), static_cast<int32>(Samples.Density[Side]), PlusY);
    TestEqual(TEXT("chunk (2, 1, 1) Density[36 * 36] is local (-2, -2, -1)"), static_cast<int32>(Samples.Density[Side * Side]), PlusZ);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigGridDegenerateStampsAreNoOpsTest, "Reflections.Digging.Grid.DegenerateStampsAreNoOps", DigGridTestFlags)
bool FReflectionsDigGridDegenerateStampsAreNoOpsTest::RunTest(const FString& Parameters)
{
    const FVector Center(2400.0, 2400.0, 2400.0);
    const float Infinity = std::numeric_limits<float>::infinity();
    const float NaN = std::numeric_limits<float>::quiet_NaN();
    struct FCase
    {
        const TCHAR* Label;
        FVector Center;
        float RadiusCm;
    };
    const FCase Cases[] = {
        { TEXT("radius 0"), Center, 0.0f },
        { TEXT("radius -100"), Center, -100.0f },
        { TEXT("infinite radius"), Center, Infinity },
        { TEXT("NaN radius"), Center, NaN },
        { TEXT("centre with a NaN component"), FVector(2400.0, static_cast<double>(NaN), 2400.0), 100.0f },
    };

    for (const FCase& Case : Cases)
    {
        FReflectionsDigGrid Grid = MakeTestGrid();
        const FGridSnapshot Before = SnapshotAllChunks(Grid);
        TArray<FIntVector> Dirty;
        Grid.ApplyStamp(MakeStamp(Case.Center, Case.RadiusCm, EReflectionsDigMode::Remove), Dirty);
        const FGridSnapshot After = SnapshotAllChunks(Grid);

        TestEqual(FString::Printf(TEXT("%s: no dirty chunks"), Case.Label), Dirty.Num(), 0);
        TestTrue(FString::Printf(TEXT("%s: density bytes unchanged"), Case.Label), Before.Density == After.Density);
        TestTrue(FString::Printf(TEXT("%s: material bytes unchanged"), Case.Label), Before.Material == After.Material);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigGridDirtyChunksIncludeBorderNeighboursTest, "Reflections.Digging.Grid.DirtyChunksIncludeBorderNeighbours", DigGridTestFlags)
bool FReflectionsDigGridDirtyChunksIncludeBorderNeighboursTest::RunTest(const FString& Parameters)
{
    // Returns the cells whose density differs from the initial ground.
    auto ChangedCells = [](const FReflectionsDigGrid& Grid)
    {
        TArray<FIntVector> Changed;
        const FIntVector Size = Grid.GetSizeInCells();
        for (int32 Z = 0; Z < Size.Z; ++Z)
        {
            for (int32 Y = 0; Y < Size.Y; ++Y)
            {
                for (int32 X = 0; X < Size.X; ++X)
                {
                    const FIntVector Cell(X, Y, Z);
                    if (Grid.GetDensity(Cell) != ExpectedInitialDensity(Z))
                    {
                        Changed.Add(Cell);
                    }
                }
            }
        }
        return Changed;
    };
    // True when Changed is exactly the 3 x 3 x 3 block around Middle.
    auto IsBlockAround = [](const TArray<FIntVector>& Changed, const FIntVector& Middle)
    {
        if (Changed.Num() != 27)
        {
            return false;
        }
        for (const FIntVector& Cell : Changed)
        {
            const FIntVector Offset = Cell - Middle;
            if (FMath::Abs(Offset.X) > 1 || FMath::Abs(Offset.Y) > 1 || FMath::Abs(Offset.Z) > 1)
            {
                return false;
            }
        }
        return true;
    };

    {
        // Cell (29, 16, 16): the changed cells reach x = 30, which chunk (1, 0, 0) sees through its border.
        FReflectionsDigGrid Grid = MakeTestGrid();
        TArray<FIntVector> Dirty;
        Grid.ApplyStamp(MakeStamp(FVector(1450.0, 800.0, 800.0), 1.0f, EReflectionsDigMode::Remove), Dirty);
        const TArray<FIntVector> Changed = ChangedCells(Grid);
        TestTrue(TEXT("premise: the changed cells are the block x 28 to 30, y and z 15 to 17"), IsBlockAround(Changed, FIntVector(29, 16, 16)));

        const TSet<FIntVector> Unique(Dirty);
        TestEqual(TEXT("border stamp: dirty chunk count"), Dirty.Num(), 2);
        TestEqual(TEXT("border stamp: no repeated chunks"), Unique.Num(), Dirty.Num());
        TestTrue(TEXT("border stamp: chunk (0, 0, 0) is dirty"), Unique.Contains(FIntVector(0, 0, 0)));
        TestTrue(TEXT("border stamp: chunk (1, 0, 0) is dirty"), Unique.Contains(FIntVector(1, 0, 0)));
    }
    {
        // Cell (16, 16, 16): the changed cells stay more than two cells from every other chunk.
        FReflectionsDigGrid Grid = MakeTestGrid();
        TArray<FIntVector> Dirty;
        Grid.ApplyStamp(MakeStamp(FVector(800.0, 800.0, 800.0), 1.0f, EReflectionsDigMode::Remove), Dirty);
        TestTrue(TEXT("premise: the changed cells are the block x, y and z 15 to 17"), IsBlockAround(ChangedCells(Grid), FIntVector(16, 16, 16)));
        TestEqual(TEXT("middle stamp: dirty chunk count"), Dirty.Num(), 1);
        TestTrue(TEXT("middle stamp: chunk (0, 0, 0) is dirty"), Dirty.Contains(FIntVector(0, 0, 0)));
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigGridCopyChunkSamplesIsFastTest, "Reflections.Digging.Grid.CopyChunkSamplesIsFast", DigGridTestFlags)
bool FReflectionsDigGridCopyChunkSamplesIsFastTest::RunTest(const FString& Parameters)
{
    // Three chunks on every axis, so chunk (1, 1, 1) is interior: every border cell comes from a neighbour chunk.
    const FReflectionsDigGrid Grid(FIntVector(3, 3, 3), FVector::ZeroVector, TestGroundHeightCm);
    const FIntVector Chunk(1, 1, 1);
    FReflectionsDigChunkSamples Samples;
    Grid.CopyChunkSamples(Chunk, Samples);

    constexpr int32 Copies = 200;
    const double Start = FPlatformTime::Seconds();
    for (int32 Copy = 0; Copy < Copies; ++Copy)
    {
        Grid.CopyChunkSamples(Chunk, Samples);
    }
    const double TotalMs = (FPlatformTime::Seconds() - Start) * 1000.0;
    UE_LOG(LogTemp, Display, TEXT("DIGSPIKE headless CopyChunkSamples: %d copies in %.2f ms, %.4f ms per copy"), Copies, TotalMs, TotalMs / Copies);
    TestTrue(FString::Printf(TEXT("%d copies of an interior chunk take under 20 ms (%.2f ms)"), Copies, TotalMs), TotalMs < 20.0);
    return true;
}

#endif
