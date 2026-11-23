#include "Digging/ReflectionsDigTerrain.h"

#include "CoreMinimal.h"
#include "AI/NavigationSystemHelpers.h"
#include "Async/TaskGraphInterfaces.h"
#include "Components/BoxComponent.h"
#include "Components/DynamicMeshComponent.h"
#include "Digging/ReflectionsDigGrid.h"
#include "Digging/ReflectionsDigMesher.h"
#include "Digging/ReflectionsDigPieces.h"
#include "Digging/ReflectionsDigSubsystem.h"
#include "Digging/ReflectionsDigTypes.h"
#include "Digging/Tests/ReflectionsDigTestTraces.h"
#include "Digging/Tests/ReflectionsDigTestWorld.h"
#include "DynamicMesh/DynamicMesh3.h"
#include "Engine/HitResult.h"
#include "Engine/World.h"
#include "Materials/Material.h"
#include "Materials/MaterialInterface.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformProcess.h"
#include "HAL/PlatformTime.h"
#include "Misc/AutomationTest.h"
#include "Misc/OutputDevice.h"
#include "Misc/OutputDeviceRedirector.h"
#include "PhysicsEngine/BodySetup.h"

#include <atomic>

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
    constexpr EAutomationTestFlags DigTerrainTestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter;
    constexpr double IdleTimeoutSeconds = 10.0;
    /** Above the top of the grid (Z 350 for a terrain at Z 0 with the ground at 0). */
    constexpr double TraceStartZ = 1000.0;
    /** The grid origin's Z for a terrain with the ground at 0 and two chunks of height: 0 - 2 * 1600 + 400. */
    constexpr double GridFloorZ = -2800.0;
    /** The grid origin sits half a cell inside the terrain's corner in X and Y, so the meshed ground spans exactly the patch. */
    constexpr double HalfCellCm = 25.0;
    /** A cavity of the riddled chunk (1, 1, 0): a lattice centre. */
    const FVector CavityCentre(2525.0, 2525.0, -1900.0);
    /**
     * Where the cavity test traces: 50 cm off the cavity's centre in X and Y, so the trace meets the cavity's own
     * floor (at about 70.7 cm below the centre) instead of the point where it touches the cavity under it.
     */
    const FVector CavityTraceStart = CavityCentre + FVector(50.0, 50.0, 0.0);
    constexpr double CavityFloorBelowCentreCm = 70.7;
    /**
     * A point of the riddled chunk (1, 1, 0) on the border between its blocks 3 (high X and Y, low Z) and 7 (high X, Y
     * and Z), in a lattice column of cavities but away from CavityCentre's: a stamp here changes those two blocks only,
     * so its commit replaces two pieces (the replace path). The cavity traces above run in block 7.
     */
    const FVector TwoBlockPoint(2925.0, 2925.0, -2000.0);
    /** A cavity centre well inside block 7 of the riddled chunk: a stamp here changes that block only (the reuse path). */
    const FVector InsideBlock7(2925.0, 2925.0, -1500.0);
    constexpr int32 HighBlock = 7;

    /** Position of a chunk's local cell (0, 0, 0) relative to the grid origin, as FReflectionsDigChunkSamples::LocalOriginCm. */
    FVector3f ChunkOrigin(const FIntVector& Chunk)
    {
        return FVector3f(Chunk * ReflectionsDig::ChunkCells) * ReflectionsDig::CellSizeCm;
    }

    /** A radius-100 stamp straight into the terrain's grid: the subsystem does not see it, so it re-meshes nothing. */
    void StampGrid(AReflectionsDigTerrain& Terrain, const FVector& Center, EReflectionsDigMode Mode)
    {
        FReflectionsDigStamp Stamp;
        Stamp.Center = Center;
        Stamp.RadiusCm = 100.0f;
        Stamp.Mode = Mode;
        TArray<FIntVector> Dirty;
        Terrain.GetGrid()->ApplyStamp(Stamp, Dirty);
    }

    /** Meshes a chunk from the terrain's grid and commits it straight to the terrain. */
    void CommitFromGrid(AReflectionsDigTerrain& Terrain, FIntVector Chunk)
    {
        FReflectionsDigMeshData Mesh;
        ReflectionsDigMesher::BuildChunk(*Terrain.GetGrid(), Chunk, Mesh);
        Terrain.CommitChunk(Chunk, MoveTemp(Mesh));
    }

    /** The chunk's eight slots, by block. */
    TStaticArray<UDynamicMeshComponent*, ReflectionsDig::BlocksPerChunk> GetSlots(const AReflectionsDigTerrain& Terrain, FIntVector Chunk)
    {
        TStaticArray<UDynamicMeshComponent*, ReflectionsDig::BlocksPerChunk> Slots(InPlace, nullptr);
        for (int32 Block = 0; Block < ReflectionsDig::BlocksPerChunk; ++Block)
        {
            Slots[Block] = Terrain.GetChunkBlockPiece(Chunk, Block);
        }
        return Slots;
    }

    /** How many of the terrain's hidden (retiring) pieces have bounds that hold Point. */
    int32 GetHiddenPiecesAround(const AReflectionsDigTerrain& Terrain, const FVector& Point)
    {
        TArray<UReflectionsDigChunkComponent*> Pieces;
        Terrain.GetComponents(Pieces);
        return Pieces.FilterByPredicate([&Point](const UReflectionsDigChunkComponent* Piece)
        {
            return !Piece->IsVisible() && Piece->Bounds.GetBox().IsInside(Point);
        }).Num();
    }

    struct FTerrainScene
    {
        AReflectionsDigTerrain* Terrain = nullptr;
        UReflectionsDigSubsystem* Dig = nullptr;
    };

    bool WaitForIdle(FAutomationTestBase& Test, FReflectionsDigTestWorld& TestWorld, const FTerrainScene& Scene, const FString& Label,
        double TimeoutSeconds = IdleTimeoutSeconds)
    {
        UReflectionsDigSubsystem* Dig = Scene.Dig;
        return Test.TestTrue(Label, TestWorld.TickUntil([Dig]() { return Dig->IsIdle(); }, TimeoutSeconds));
    }

    /** A terrain at (0, 0, 0) with the defaults (ground at Z 0, 3 x 3 x 2 chunks), ticked until idle. */
    bool MakeTerrainScene(FAutomationTestBase& Test, FReflectionsDigTestWorld& TestWorld, FTerrainScene& Out,
        TOptional<FVector> Focus = TOptional<FVector>())
    {
        if (!Test.TestNotNull(TEXT("Test world"), TestWorld.World))
        {
            return false;
        }
        Out.Dig = TestWorld.World->GetSubsystem<UReflectionsDigSubsystem>();
        if (!Test.TestNotNull(TEXT("Dig subsystem"), Out.Dig))
        {
            return false;
        }
        Out.Dig->SetFocusOverride(Focus);
        Out.Terrain = TestWorld.Spawn<AReflectionsDigTerrain>(FVector::ZeroVector);
        if (!Test.TestNotNull(TEXT("Terrain"), Out.Terrain))
        {
            return false;
        }
        return WaitForIdle(Test, TestWorld, Out, TEXT("Idle after the terrain begins play"));
    }

    /** Where every downward trace ends: well under the grid floor and under the safety floor below it. */
    constexpr double TraceEndZ = GridFloorZ - 300.0;

    /** The first hit of a downward visibility trace at (X, Y) from StartZ to TraceEndZ, whatever it hit. */
    TOptional<FHitResult> TraceDown(UWorld* World, double X, double Y, double StartZ = TraceStartZ)
    {
        return FReflectionsDigTestTraces::TraceDown(World, X, Y, StartZ, TraceEndZ);
    }

    /**
     * Z of the first hit of a downward visibility trace at (X, Y) from StartZ, only when that hit is a chunk
     * piece of the terrain. Nothing, or anything else (such as the safety floor under the grid), gives no value.
     */
    TOptional<double> TraceDownZ(UWorld* World, double X, double Y, double StartZ = TraceStartZ)
    {
        return FReflectionsDigTestTraces::TraceDownToChunkZ(World, X, Y, StartZ, TraceEndZ);
    }

    /** One plain world tick: commits and cooks started in it have not had a chance to finish. */
    void TickWithoutPumping(FReflectionsDigTestWorld& TestWorld)
    {
        TestWorld.Tick();
    }

    /** Lets finished worker tasks and collision cooks land: the game thread's queued tasks run, then a short sleep. */
    void PumpGameThread()
    {
        FTaskGraphInterface::Get().ProcessThreadUntilIdle(ENamedThreads::GameThread);
        FPlatformProcess::Sleep(0.001f);
    }

    /** Riddles chunk (1, 1, 0) with radius-100 Remove digs on a 200 cm lattice of cells filling the chunk. */
    int32 RiddleBuriedChunk(UReflectionsDigSubsystem& Dig)
    {
        int32 Changed = 0;
        for (double Z = -2700.0; Z <= -1300.0; Z += 200.0)
        {
            for (double Y = 1725.0; Y <= 3125.0; Y += 200.0)
            {
                for (double X = 1725.0; X <= 3125.0; X += 200.0)
                {
                    Changed += Dig.Dig(FVector(X, Y, Z), 100.0f, EReflectionsDigMode::Remove) ? 1 : 0;
                }
            }
        }
        return Changed;
    }

    /** Sets reflections.Dig.MaxCommitsPerFrame for one scope and restores the old value on every exit path. */
    struct FScopedMaxCommitsPerFrame
    {
        IConsoleVariable* Variable = nullptr;
        int32 OldValue = 0;

        explicit FScopedMaxCommitsPerFrame(int32 Value)
            : Variable(IConsoleManager::Get().FindConsoleVariable(TEXT("reflections.Dig.MaxCommitsPerFrame")))
        {
            if (Variable != nullptr)
            {
                OldValue = Variable->GetInt();
                Variable->Set(Value, ECVF_SetByCode);
            }
        }

        ~FScopedMaxCommitsPerFrame()
        {
            if (Variable != nullptr)
            {
                Variable->Set(OldValue, ECVF_SetByCode);
            }
        }

        FScopedMaxCommitsPerFrame(const FScopedMaxCommitsPerFrame&) = delete;
        FScopedMaxCommitsPerFrame& operator=(const FScopedMaxCommitsPerFrame&) = delete;
    };

    /**
     * Meshes a chunk and builds its pieces (as a worker would), then commits the pieces straight to the terrain and
     * logs the game-thread time of the commit, with the terrain's own breakdown (headless, no renderer).
     */
    void TimeCommit(AReflectionsDigTerrain& Terrain, FIntVector Chunk, const TCHAR* Label)
    {
        FReflectionsDigMeshData Mesh;
        ReflectionsDigMesher::BuildChunk(*Terrain.GetGrid(), Chunk, Mesh);
        FReflectionsDigChunkResult Result;
        ReflectionsDigPieces::Build(Mesh, ChunkOrigin(Chunk), Result);
        const int32 Vertices = Result.SourceVertexCount;
        const int32 Triangles = Result.SourceTriangleCount;

        const ELogVerbosity::Type OldVerbosity = LogReflectionsDigTerrain.GetVerbosity();
        LogReflectionsDigTerrain.SetVerbosity(ELogVerbosity::Verbose);
        const double Start = FPlatformTime::Seconds();
        Terrain.CommitChunkPieces(Chunk, MoveTemp(Result));
        const double Milliseconds = (FPlatformTime::Seconds() - Start) * 1000.0;
        LogReflectionsDigTerrain.SetVerbosity(OldVerbosity);
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE headless CommitChunkPieces %s: %d vertices, %d triangles, %d pieces, %.2f ms"),
            Label, Vertices, Triangles, Terrain.GetChunkPieceCount(Chunk), Milliseconds);
    }

    /** Waits for idle with the terrain's Verbose log on, so its swap timings are logged too. */
    bool WaitForIdleLoggingSwaps(FAutomationTestBase& Test, FReflectionsDigTestWorld& TestWorld, const FTerrainScene& Scene, const FString& Label)
    {
        const ELogVerbosity::Type OldVerbosity = LogReflectionsDigTerrain.GetVerbosity();
        LogReflectionsDigTerrain.SetVerbosity(ELogVerbosity::Verbose);
        const bool bIdle = WaitForIdle(Test, TestWorld, Scene, Label);
        LogReflectionsDigTerrain.SetVerbosity(OldVerbosity);
        return bIdle;
    }
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainMeshesAllChunksWithNoFocusTest, "Reflections.Digging.Terrain.MeshesAllChunksWithNoFocus", DigTerrainTestFlags)
bool FReflectionsDigTerrainMeshesAllChunksWithNoFocusTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    FTerrainScene Scene;
    if (!MakeTerrainScene(*this, TestWorld, Scene))
    {
        return true;
    }
    for (int32 Y = 0; Y < 3; ++Y)
    {
        for (int32 X = 0; X < 3; ++X)
        {
            const FIntVector Top(X, Y, 1);
            const FIntVector Buried(X, Y, 0);
            UDynamicMeshComponent* TopComponent = Scene.Terrain->FindChunkComponent(Top);
            if (TestNotNull(FString::Printf(TEXT("Chunk %s has a component"), *Top.ToString()), TopComponent))
            {
                TestTrue(FString::Printf(TEXT("Chunk %s has triangles"), *Top.ToString()), TopComponent->GetMesh()->TriangleCount() > 0);
                TestEqual(FString::Printf(TEXT("Chunk %s's component sits at the grid origin"), *Top.ToString()),
                    TopComponent->GetComponentLocation(), FVector(HalfCellCm, HalfCellCm, GridFloorZ));
                TestTrue(FString::Printf(TEXT("Chunk %s's component belongs to the terrain"), *Top.ToString()),
                    TopComponent->GetOwner() == Scene.Terrain);
            }
            TestNull(FString::Printf(TEXT("Chunk %s has no component"), *Buried.ToString()), Scene.Terrain->FindChunkComponent(Buried));
            TestEqual(FString::Printf(TEXT("Chunk %s has no pieces"), *Buried.ToString()), Scene.Terrain->GetChunkPieceCount(Buried), 0);
        }
    }

    // Informal headless timings: copying one chunk's samples, and one flat-chunk commit (it reuses the component).
    {
        FReflectionsDigChunkSamples Samples;
        const double Start = FPlatformTime::Seconds();
        Scene.Terrain->GetGrid()->CopyChunkSamples(FIntVector(1, 1, 1), Samples);
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE headless CopyChunkSamples: %.2f ms"), (FPlatformTime::Seconds() - Start) * 1000.0);
    }
    TimeCommit(*Scene.Terrain, FIntVector(1, 1, 1), TEXT("flat chunk"));
    WaitForIdleLoggingSwaps(*this, TestWorld, Scene, TEXT("Idle after the timed commit"));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainSurfaceSpansExactlyThePatchTest, "Reflections.Digging.Terrain.SurfaceSpansExactlyThePatch", DigTerrainTestFlags)
bool FReflectionsDigTerrainSurfaceSpansExactlyThePatchTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    FTerrainScene Scene;
    if (!MakeTerrainScene(*this, TestWorld, Scene))
    {
        return true;
    }
    // The terrain at (0, 0, 0) with 3 x 3 chunks: the patch is X 0..4800, Y 0..4800, its ground at Z 0.
    constexpr double Far = 4800.0;
    constexpr double Mid = 2400.0;
    constexpr double In = 5.0;
    const FVector2D Inside[] = {
        { In, Mid }, { Far - In, Mid }, { Mid, In }, { Mid, Far - In },
        { In, In }, { Far - In, In }, { In, Far - In }, { Far - In, Far - In },
    };
    for (const FVector2D& At : Inside)
    {
        const TOptional<double> Z = TraceDownZ(TestWorld.World, At.X, At.Y);
        TestTrue(FString::Printf(TEXT("5 cm inside the patch at (%.0f, %.0f) a trace hits a chunk piece within 5 cm of Z 0 (at %s)"), At.X, At.Y,
            Z.IsSet() ? *FString::SanitizeFloat(*Z) : TEXT("no chunk piece")), Z.IsSet() && FMath::Abs(*Z) <= 5.0);
    }
    const FVector2D Outside[] = { { -In, Mid }, { Far + In, Mid }, { Mid, -In }, { Mid, Far + In } };
    for (const FVector2D& At : Outside)
    {
        const TOptional<double> Z = TraceDownZ(TestWorld.World, At.X, At.Y);
        TestFalse(FString::Printf(TEXT("5 cm outside the patch at (%.0f, %.0f) a trace hits no chunk piece (hit at %s)"), At.X, At.Y,
            Z.IsSet() ? *FString::SanitizeFloat(*Z) : TEXT("none")), Z.IsSet());
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainPiecesNeverUseTheDefaultMaterialTest, "Reflections.Digging.Terrain.PiecesNeverUseTheDefaultMaterial", DigTerrainTestFlags)
bool FReflectionsDigTerrainPiecesNeverUseTheDefaultMaterialTest::RunTest(const FString& Parameters)
{
    const UMaterialInterface* EngineDefault = UMaterial::GetDefaultMaterial(MD_Surface);
    const UMaterialInterface* Plain = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
    UMaterialInterface* Chosen = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial_Inst.BasicShapeMaterial_Inst"));
    if (!TestNotNull(TEXT("The plain engine material loads"), Plain) || !TestNotNull(TEXT("The chosen test material loads"), Chosen))
    {
        return true;
    }
    auto TestEveryPiece = [this](const AReflectionsDigTerrain& Terrain, const UMaterialInterface* Expected, const UMaterialInterface* Default, const TCHAR* When)
    {
        TArray<UReflectionsDigChunkComponent*> Pieces;
        Terrain.GetComponents(Pieces);
        TestTrue(FString::Printf(TEXT("%s: the terrain has pieces"), When), Pieces.Num() > 0);
        for (const UReflectionsDigChunkComponent* Piece : Pieces)
        {
            const UMaterialInterface* Material = Piece->GetMaterial(0);
            TestTrue(FString::Printf(TEXT("%s: piece %s draws with %s (has %s)"), When, *Piece->GetName(), *GetNameSafe(Expected), *GetNameSafe(Material)),
                Material == Expected);
            TestTrue(FString::Printf(TEXT("%s: piece %s does not draw with the engine default material"), When, *Piece->GetName()),
                Material != nullptr && Material != Default);
        }
    };

    // GroundMaterial null: the plain engine material, and GroundMaterial itself stays null.
    {
        FReflectionsDigTestWorld TestWorld;
        FTerrainScene Scene;
        if (!MakeTerrainScene(*this, TestWorld, Scene))
        {
            return true;
        }
        TestNull(TEXT("GroundMaterial is not overwritten"), Scene.Terrain->GroundMaterial.Get());
        TestEveryPiece(*Scene.Terrain, Plain, EngineDefault, TEXT("GroundMaterial null"));
    }

    // GroundMaterial set: that material, also on pieces a later dig creates (the riddled buried chunk had none).
    {
        FReflectionsDigTestWorld TestWorld;
        if (!TestNotNull(TEXT("Test world"), TestWorld.World))
        {
            return true;
        }
        FTerrainScene Scene;
        Scene.Dig = TestWorld.World->GetSubsystem<UReflectionsDigSubsystem>();
        AReflectionsDigTerrain* Terrain = TestWorld.SpawnDeferred<AReflectionsDigTerrain>(FVector::ZeroVector);
        if (!TestNotNull(TEXT("Dig subsystem"), Scene.Dig) || !TestNotNull(TEXT("Terrain"), Terrain))
        {
            return true;
        }
        Terrain->GroundMaterial = Chosen;
        Scene.Terrain = TestWorld.FinishSpawning(Terrain);
        if (!TestNotNull(TEXT("Terrain begins play"), Scene.Terrain) || !WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the terrain begins play")))
        {
            return true;
        }
        TestEveryPiece(*Scene.Terrain, Chosen, EngineDefault, TEXT("GroundMaterial set"));
        const FIntVector Busy(1, 1, 0);
        TestEqual(TEXT("Premise: the buried chunk has no pieces before the dig"), Scene.Terrain->GetChunkPieceCount(Busy), 0);
        RiddleBuriedChunk(*Scene.Dig);
        if (WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after riddling the buried chunk")))
        {
            TestTrue(TEXT("Premise: the dig created pieces in the buried chunk"), Scene.Terrain->GetChunkPieceCount(Busy) > 0);
            TestEveryPiece(*Scene.Terrain, Chosen, EngineDefault, TEXT("After a later dig"));
        }
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainDigChangesCollisionTest,"Reflections.Digging.Terrain.DigChangesCollision", DigTerrainTestFlags)
bool FReflectionsDigTerrainDigChangesCollisionTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    FTerrainScene Scene;
    if (!MakeTerrainScene(*this, TestWorld, Scene))
    {
        return true;
    }
    const TOptional<double> Before = TraceDownZ(TestWorld.World, 2400.0, 2400.0);
    if (TestTrue(TEXT("The trace hits the ground before the dig"), Before.IsSet()))
    {
        TestTrue(FString::Printf(TEXT("The ground is within 5 cm of Z 0 (hit at %.2f)"), *Before), FMath::Abs(*Before) <= 5.0);
    }

    TestTrue(TEXT("Dig returns true"), Scene.Dig->Dig(FVector(2400.0, 2400.0, 0.0), 100.0f, EReflectionsDigMode::Remove));
    if (WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the dig")))
    {
        const TOptional<double> After = TraceDownZ(TestWorld.World, 2400.0, 2400.0);
        if (TestTrue(TEXT("The trace hits the pit"), After.IsSet()))
        {
            TestTrue(FString::Printf(TEXT("The pit floor is below Z -50 (hit at %.2f)"), *After), *After < -50.0);
        }
    }

    // Informal headless timing of a commit for a chunk with one 3 m pit.
    for (double Z = 0.0; Z >= -300.0; Z -= 50.0)
    {
        Scene.Dig->Dig(FVector(2400.0, 2400.0, Z), 100.0f, EReflectionsDigMode::Remove);
    }
    if (WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after digging the 3 m pit")))
    {
        TimeCommit(*Scene.Terrain, FIntVector(1, 1, 1), TEXT("chunk with a 3 m pit"));
        WaitForIdleLoggingSwaps(*this, TestWorld, Scene, TEXT("Idle after the timed commit"));
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainDigOutsideTerrainReturnsFalseTest, "Reflections.Digging.Terrain.DigOutsideTerrainReturnsFalse", DigTerrainTestFlags)
bool FReflectionsDigTerrainDigOutsideTerrainReturnsFalseTest::RunTest(const FString& Parameters)
{
    {
        FReflectionsDigTestWorld TestWorld;
        FTerrainScene Scene;
        if (MakeTerrainScene(*this, TestWorld, Scene))
        {
            TestFalse(TEXT("A dig outside the terrain returns false"), Scene.Dig->Dig(FVector(-9000.0, 0.0, 0.0), 100.0f, EReflectionsDigMode::Remove));
            TestTrue(TEXT("Nothing is dirty after the dig outside"), Scene.Dig->IsIdle());

            // Destroy the terrain while its mesh tasks are in flight; afterwards nothing digs.
            TestTrue(TEXT("A dig inside returns true"), Scene.Dig->Dig(FVector(2400.0, 2400.0, 0.0), 100.0f, EReflectionsDigMode::Remove));
            TickWithoutPumping(TestWorld);
            Scene.Terrain->Destroy();
            WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the terrain is destroyed"));
            TestFalse(TEXT("Dig after the terrain is destroyed returns false"), Scene.Dig->Dig(FVector(2400.0, 2400.0, 0.0), 100.0f, EReflectionsDigMode::Remove));
        }
    }
    {
        FReflectionsDigTestWorld EmptyWorld;
        if (TestNotNull(TEXT("World without a terrain"), EmptyWorld.World))
        {
            UReflectionsDigSubsystem* Dig = EmptyWorld.World->GetSubsystem<UReflectionsDigSubsystem>();
            if (TestNotNull(TEXT("Dig subsystem"), Dig))
            {
                TestFalse(TEXT("Dig with no terrain returns false"), Dig->Dig(FVector(2400.0, 2400.0, 0.0), 100.0f, EReflectionsDigMode::Remove));
            }
        }
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainCommitBudgetIsRespectedTest, "Reflections.Digging.Terrain.CommitBudgetIsRespected", DigTerrainTestFlags)
bool FReflectionsDigTerrainCommitBudgetIsRespectedTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    FTerrainScene Scene;
    if (!MakeTerrainScene(*this, TestWorld, Scene))
    {
        return true;
    }
    const FScopedMaxCommitsPerFrame Budget(1);
    if (!TestNotNull(TEXT("reflections.Dig.MaxCommitsPerFrame exists"), Budget.Variable)
        || !TestEqual(TEXT("reflections.Dig.MaxCommitsPerFrame took the value 1"), Budget.Variable->GetInt(), 1))
    {
        return true;
    }

    // The corner of four top chunks: all four are re-meshed.
    TestTrue(TEXT("Dig returns true"), Scene.Dig->Dig(FVector(1625.0, 1625.0, -400.0), 100.0f, EReflectionsDigMode::Remove));
    int32 MostCommits = 0;
    int32 TotalCommits = 0;
    UReflectionsDigSubsystem* Dig = Scene.Dig;
    const bool bIdle = TestWorld.TickUntil([Dig, &MostCommits, &TotalCommits]()
    {
        MostCommits = FMath::Max(MostCommits, Dig->GetCommitsLastTick());
        TotalCommits += Dig->GetCommitsLastTick();
        return Dig->IsIdle();
    }, IdleTimeoutSeconds);
    TestTrue(TEXT("Idle after the dig"), bIdle);
    TestTrue(FString::Printf(TEXT("No tick commits more than 1 chunk (most: %d)"), MostCommits), MostCommits <= 1);
    TestTrue(FString::Printf(TEXT("The four dug chunks were committed (total commits: %d)"), TotalCommits), TotalCommits >= 4);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainFarChunksAreReleasedAndRestoredTest, "Reflections.Digging.Terrain.FarChunksAreReleasedAndRestored", DigTerrainTestFlags)
bool FReflectionsDigTerrainFarChunksAreReleasedAndRestoredTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    FTerrainScene Scene;
    const FVector Centre(2400.0, 2400.0, 0.0);
    if (!MakeTerrainScene(*this, TestWorld, Scene, Centre))
    {
        return true;
    }
    TestTrue(TEXT("Dig returns true"), Scene.Dig->Dig(FVector(400.0, 400.0, 0.0), 100.0f, EReflectionsDigMode::Remove));
    if (!WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the dig")))
    {
        return true;
    }
    const TOptional<double> Recorded = TraceDownZ(TestWorld.World, 400.0, 400.0);
    if (!TestTrue(TEXT("The trace hits the pit"), Recorded.IsSet()))
    {
        return true;
    }
    TestTrue(FString::Printf(TEXT("The pit is dug (hit at %.2f)"), *Recorded), *Recorded < -50.0);

    Scene.Dig->SetFocusOverride(FVector(4400.0, 4400.0, 0.0));
    if (WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the focus moves away")))
    {
        TestNull(TEXT("Chunk (0, 0, 1) has no component"), Scene.Terrain->FindChunkComponent(FIntVector(0, 0, 1)));
        TestNotNull(TEXT("Chunk (2, 2, 1) near the focus still has its component"), Scene.Terrain->FindChunkComponent(FIntVector(2, 2, 1)));
    }

    Scene.Dig->SetFocusOverride(Centre);
    if (WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the focus comes back")))
    {
        const TOptional<double> Restored = TraceDownZ(TestWorld.World, 400.0, 400.0);
        if (TestTrue(TEXT("The trace hits the restored pit"), Restored.IsSet()))
        {
            TestTrue(FString::Printf(TEXT("The pit depth is within 1 cm of the recorded one (%.2f, recorded %.2f)"), *Restored, *Recorded),
                FMath::Abs(*Restored - *Recorded) <= 1.0);
        }
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainHeldDigStaysBoundedTest, "Reflections.Digging.Terrain.HeldDigStaysBounded", DigTerrainTestFlags)
bool FReflectionsDigTerrainHeldDigStaysBoundedTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    FTerrainScene Scene;
    if (!MakeTerrainScene(*this, TestWorld, Scene))
    {
        return true;
    }
    // The corner shared by eight chunks, so every dig there dirties all eight. Remove and Add alternate, so every
    // call changes the grid and the held dig keeps all eight chunks busy.
    const FVector Point(1625.0, 1625.0, -1200.0);
    int32 MostTasks = 0;
    int32 MostQueued = 0;
    int32 TotalCommits = 0;
    int32 DigsThatChanged = 0;
    for (int32 Frame = 0; Frame < 120; ++Frame)
    {
        const EReflectionsDigMode Mode = Frame % 2 == 0 ? EReflectionsDigMode::Remove : EReflectionsDigMode::Add;
        DigsThatChanged += Scene.Dig->Dig(Point, 100.0f, Mode) ? 1 : 0;
        MostTasks = FMath::Max(MostTasks, Scene.Dig->GetTasksInFlight());
        MostQueued = FMath::Max(MostQueued, Scene.Dig->GetQueuedCommits());
        TickWithoutPumping(TestWorld);
        TotalCommits += Scene.Dig->GetCommitsLastTick();
        MostTasks = FMath::Max(MostTasks, Scene.Dig->GetTasksInFlight());
        MostQueued = FMath::Max(MostQueued, Scene.Dig->GetQueuedCommits());
        PumpGameThread();
    }
    TestEqual(TEXT("Every dig changed the grid"), DigsThatChanged, 120);
    TestTrue(FString::Printf(TEXT("At most 8 tasks in flight (most: %d)"), MostTasks), MostTasks <= 8);
    TestTrue(FString::Printf(TEXT("At most 8 queued commits (most: %d)"), MostQueued), MostQueued <= 8);
    TestTrue(FString::Printf(TEXT("Tasks in flight reached at least 2 (most: %d)"), MostTasks), MostTasks >= 2);
    TestTrue(FString::Printf(TEXT("More than 8 commits over the 120 ticks (%d)"), TotalCommits), TotalCommits > 8);
    WaitForIdle(*this, TestWorld, Scene, TEXT("Idle within 5 seconds of the last dig"), 5.0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainSplitChunkCollisionFollowsEachCookTest, "Reflections.Digging.Terrain.SplitChunkCollisionFollowsEachCook", DigTerrainTestFlags)
bool FReflectionsDigTerrainSplitChunkCollisionFollowsEachCookTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    FTerrainScene Scene;
    if (!MakeTerrainScene(*this, TestWorld, Scene))
    {
        return true;
    }
    const FIntVector Busy(1, 1, 0);
    RiddleBuriedChunk(*Scene.Dig);
    if (!WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after riddling the chunk")))
    {
        return true;
    }
    TestEqual(TEXT("The riddled chunk fills all eight blocks"), Scene.Terrain->GetChunkPieceCount(Busy), ReflectionsDig::BlocksPerChunk);

    // The fill is a radius-100 Add centred on the cavity's lowest point, so it fills the cavity's lower half. The
    // trace runs 30 cm off the centre in X and Y: the fill's top is there about 9 cm under the cavity centre, the
    // old cavity floor about 91 cm under it. Both are in block 7.
    const FVector FillCentre = CavityCentre - FVector(0.0, 0.0, 100.0);
    const FVector TraceStart = CavityCentre + FVector(30.0, 30.0, 50.0);
    const double FillTopAboveZ = CavityCentre.Z - 45.0;
    // The later changes are in blocks 3 and 7: each commit replaces the piece the trace hits, with another one.
    const FVector Elsewhere = TwoBlockPoint;
    UWorld* World = TestWorld.World;
    auto HitsFillTop = [World, TraceStart, FillTopAboveZ](double& OutZ)
    {
        const TOptional<double> Z = TraceDownZ(World, TraceStart.X, TraceStart.Y, TraceStart.Z);
        OutZ = Z.Get(TraceEndZ);
        return Z.IsSet() && *Z > FillTopAboveZ;
    };

    // Part 1, decided at commit time: commit the fill straight to the terrain, let its cook finish without ticking
    // the world (so no swap runs in between), then commit another change to the same block. The cooked fill pieces
    // are the newest real collision, so they must survive that commit; destroying them would bring the old cavity
    // floor back.
    {
        TestTrue(TEXT("The fill changes the grid"), Scene.Dig->Dig(FillCentre, 100.0f, EReflectionsDigMode::Add));
        FReflectionsDigMeshData Filled;
        ReflectionsDigMesher::BuildChunk(*Scene.Terrain->GetGrid(), Busy, Filled);
        Scene.Terrain->CommitChunk(Busy, MoveTemp(Filled));
        double HitZ = 0.0;
        const double Deadline = FPlatformTime::Seconds() + 5.0;
        // Every piece of the fill set must finish its cook, not only the one under the trace.
        bool bFillCooked = !Scene.Terrain->IsChunkCooking(Busy) && HitsFillTop(HitZ);
        while (!bFillCooked && FPlatformTime::Seconds() < Deadline)
        {
            PumpGameThread();
            bFillCooked = !Scene.Terrain->IsChunkCooking(Busy) && HitsFillTop(HitZ);
        }
        if (TestTrue(FString::Printf(TEXT("Every piece of the fill set cooks without a world tick (last hit %.2f)"), HitZ), bFillCooked))
        {
            TestTrue(TEXT("The second change changes the grid"), Scene.Dig->Dig(Elsewhere, 100.0f, EReflectionsDigMode::Add));
            FReflectionsDigMeshData Next;
            ReflectionsDigMesher::BuildChunk(*Scene.Terrain->GetGrid(), Busy, Next);
            Scene.Terrain->CommitChunk(Busy, MoveTemp(Next));
            const bool bStillFill = HitsFillTop(HitZ);
            TestTrue(FString::Printf(TEXT("Right after the next commit the trace still hits the fill (hit %.2f)"), HitZ), bStillFill);
        }
    }

    // Part 2, the held dig: after idle the trace hits the fill; then dig beside it, in its block and the one below, on
    // each of 30 ticks.
    if (!WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the fill")))
    {
        return true;
    }
    double HitZ = 0.0;
    const bool bFillAfterIdle = HitsFillTop(HitZ);
    TestTrue(FString::Printf(TEXT("After idle the trace hits the top of the fill (hit %.2f)"), HitZ), bFillAfterIdle);
    int32 Misses = 0;
    double LastMissZ = 0.0;
    for (int32 Frame = 0; Frame < 30; ++Frame)
    {
        const EReflectionsDigMode Mode = Frame % 2 == 0 ? EReflectionsDigMode::Remove : EReflectionsDigMode::Add;
        TestTrue(FString::Printf(TEXT("Dig on tick %d changes the grid"), Frame), Scene.Dig->Dig(Elsewhere, 100.0f, Mode));
        TickWithoutPumping(TestWorld);
        if (!HitsFillTop(HitZ))
        {
            ++Misses;
            LastMissZ = HitZ;
        }
        PumpGameThread();
        if (!HitsFillTop(HitZ))
        {
            ++Misses;
            LastMissZ = HitZ;
        }
    }
    TestEqual(FString::Printf(TEXT("Traces that missed the top of the fill (last miss at %.2f)"), LastMissZ), Misses, 0);
    WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the held dig"));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainFillingAShaftNeverOpensAGapBelowTest, "Reflections.Digging.Terrain.FillingAShaftNeverOpensAGapBelow", DigTerrainTestFlags)
bool FReflectionsDigTerrainFillingAShaftNeverOpensAGapBelowTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    FTerrainScene Scene;
    if (!MakeTerrainScene(*this, TestWorld, Scene))
    {
        return true;
    }
    // A shaft of radius-100 digs every 50 cm from the ground down to Z -1500: its floor is in the lower chunk.
    const double X = 2400.0;
    const double Y = 2400.0;
    for (double Z = 0.0; Z >= -1500.0; Z -= 50.0)
    {
        Scene.Dig->Dig(FVector(X, Y, Z), 100.0f, EReflectionsDigMode::Remove);
    }
    if (!WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after digging the shaft")))
    {
        return true;
    }
    const TOptional<double> Floor = TraceDownZ(TestWorld.World, X, Y);
    if (!TestTrue(TEXT("The trace hits the shaft floor"), Floor.IsSet()))
    {
        return true;
    }
    TestTrue(FString::Printf(TEXT("Premise: the shaft floor is in the lower chunk (%.2f)"), *Floor), *Floor < -1200.0);

    // Fill it from the bottom up, one stamp per tick; trace from the mouth right after each tick and again after
    // the game thread has run its finished cooks. Only a chunk piece counts as a hit.
    int32 Misses = 0;
    int32 Stamps = 0;
    for (double Z = -1500.0; Z <= 0.0; Z += 50.0)
    {
        Stamps += Scene.Dig->Dig(FVector(X, Y, Z), 100.0f, EReflectionsDigMode::Add) ? 1 : 0;
        TickWithoutPumping(TestWorld);
        Misses += TraceDownZ(TestWorld.World, X, Y).IsSet() ? 0 : 1;
        PumpGameThread();
        Misses += TraceDownZ(TestWorld.World, X, Y).IsSet() ? 0 : 1;
    }
    TestEqual(TEXT("Every fill stamp changed the grid"), Stamps, 31);
    TestEqual(TEXT("Traces from the shaft mouth that hit no terrain piece"), Misses, 0);
    if (!WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the fill")))
    {
        return true;
    }
    const TOptional<double> Top = TraceDownZ(TestWorld.World, X, Y);
    if (TestTrue(TEXT("After the fill the trace hits the terrain"), Top.IsSet()))
    {
        TestTrue(FString::Printf(TEXT("The filled shaft is level with the ground or above it (%.2f)"), *Top), *Top > -60.0);
    }

    // The order above depends on the workers, so also force the case it aims at: dig the shaft again, fill all of
    // it without ticking, and commit only the lower chunk (now all solid, so its mesh is empty) straight to the
    // terrain. The upper chunk still shows its old shaft, open into the lower chunk.
    for (double Z = 0.0; Z >= -1500.0; Z -= 50.0)
    {
        Scene.Dig->Dig(FVector(X, Y, Z), 100.0f, EReflectionsDigMode::Remove);
    }
    if (!WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after digging the shaft again")))
    {
        return true;
    }
    // Radius 150 rather than 100: a cell exactly 100 cm from a dig centre has density 0 (air) after the dig and a
    // radius-100 fill leaves it at 0, a one-cell bubble; the wider fill makes every cell of the shaft solid.
    for (double Z = -1500.0; Z <= 0.0; Z += 50.0)
    {
        Scene.Dig->Dig(FVector(X, Y, Z), 150.0f, EReflectionsDigMode::Add);
    }
    const FIntVector Lower(1, 1, 0);
    FReflectionsDigMeshData LowerMesh;
    ReflectionsDigMesher::BuildChunk(*Scene.Terrain->GetGrid(), Lower, LowerMesh);
    TestTrue(TEXT("Premise: the filled lower chunk has no surface"), LowerMesh.IsEmpty());
    Scene.Terrain->CommitChunk(Lower, MoveTemp(LowerMesh));
    TestTrue(TEXT("Right after the lower chunk empties, the trace from the mouth still hits a terrain piece"),
        TraceDownZ(TestWorld.World, X, Y).IsSet());
    int32 LaterMisses = 0;
    UReflectionsDigSubsystem* Dig = Scene.Dig;
    UWorld* World = TestWorld.World;
    const bool bIdle = TestWorld.TickUntil([Dig, World, X, Y, &LaterMisses]()
    {
        LaterMisses += TraceDownZ(World, X, Y).IsSet() ? 0 : 1;
        return Dig->IsIdle();
    }, IdleTimeoutSeconds);
    TestTrue(TEXT("Idle after the forced fill"), bIdle);
    TestEqual(TEXT("Traces after the forced fill that hit no terrain piece"), LaterMisses, 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainChunkLeftAgainAfterAStaleResultIsReleasedTest, "Reflections.Digging.Terrain.ChunkLeftAgainAfterAStaleResultIsReleased", DigTerrainTestFlags)
bool FReflectionsDigTerrainChunkLeftAgainAfterAStaleResultIsReleasedTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    FTerrainScene Scene;
    const FVector Near(400.0, 400.0, 0.0);
    const FVector Far(4400.0, 4400.0, 0.0);
    const FIntVector Chunk(0, 0, 1);
    if (!MakeTerrainScene(*this, TestWorld, Scene, Near))
    {
        return true;
    }
    // Dig, then leave, come back and leave again while the chunk's result is still on its way.
    TestTrue(TEXT("Dig returns true"), Scene.Dig->Dig(Near, 100.0f, EReflectionsDigMode::Remove));
    TickWithoutPumping(TestWorld);
    Scene.Dig->SetFocusOverride(Far);
    TickWithoutPumping(TestWorld);
    Scene.Dig->SetFocusOverride(Near);
    TickWithoutPumping(TestWorld);
    PumpGameThread();
    TickWithoutPumping(TestWorld);
    Scene.Dig->SetFocusOverride(Far);
    if (WaitForIdle(*this, TestWorld, Scene, TEXT("Idle with the focus far away")))
    {
        TestNull(TEXT("Chunk (0, 0, 1) has no component"), Scene.Terrain->FindChunkComponent(Chunk));
    }

    // The timing above depends on the workers, so also force the state it aims at: a result committed for the chunk
    // while it is not wanted and no mesh is being asked for (what a stale result landing then does).
    FReflectionsDigMeshData Stale;
    ReflectionsDigMesher::BuildChunk(*Scene.Terrain->GetGrid(), Chunk, Stale);
    Scene.Terrain->CommitChunk(Chunk, MoveTemp(Stale));
    TestNotNull(TEXT("The stale commit made a component"), Scene.Terrain->FindChunkComponent(Chunk));
    if (WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the stale commit")))
    {
        TestNull(TEXT("Chunk (0, 0, 1) has no component after the stale commit"), Scene.Terrain->FindChunkComponent(Chunk));
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainWorldTornDownWithTasksInFlightTest, "Reflections.Digging.Terrain.WorldTornDownWithTasksInFlight", DigTerrainTestFlags)
bool FReflectionsDigTerrainWorldTornDownWithTasksInFlightTest::RunTest(const FString& Parameters)
{
    {
        FReflectionsDigTestWorld TestWorld;
        FTerrainScene Scene;
        if (!MakeTerrainScene(*this, TestWorld, Scene))
        {
            return true;
        }
        TestTrue(TEXT("Dig at the eight-chunk corner returns true"), Scene.Dig->Dig(FVector(1625.0, 1625.0, -1200.0), 100.0f, EReflectionsDigMode::Remove));
        // The subsystem's tick here copies and launches all eight chunks; time it (headless, informal).
        const double Start = FPlatformTime::Seconds();
        Scene.Dig->Tick(1.0f / 60.0f);
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE headless subsystem tick that copies and launches 8 chunks: %.2f ms"),
            (FPlatformTime::Seconds() - Start) * 1000.0);
        const int32 InFlight = Scene.Dig->GetTasksInFlight();
        TestTrue(FString::Printf(TEXT("Tasks are in flight when the world goes (%d)"), InFlight), InFlight > 0);
        // The world is destroyed here, without waiting; its destructor checks that nothing still holds the world.
    }
    // Let anything left over run on the game thread now that the world is gone.
    PumpGameThread();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainBusyChunkIsSplitUnderTheCollisionLimitTest, "Reflections.Digging.Terrain.BusyChunkIsSplitUnderTheCollisionLimit", DigTerrainTestFlags)
bool FReflectionsDigTerrainBusyChunkIsSplitUnderTheCollisionLimitTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    FTerrainScene Scene;
    if (!MakeTerrainScene(*this, TestWorld, Scene))
    {
        return true;
    }
    const FIntVector Busy(1, 1, 0);
    TestTrue(TEXT("The lattice digs change the grid"), RiddleBuriedChunk(*Scene.Dig) > 0);
    FReflectionsDigMeshData Premise;
    ReflectionsDigMesher::BuildChunk(*Scene.Terrain->GetGrid(), Busy, Premise);
    if (!TestTrue(FString::Printf(TEXT("Premise: the riddled chunk meshes to more than 12,000 vertices (%d)"), Premise.Positions.Num()),
        Premise.Positions.Num() > ReflectionsDig::MaxPieceVertices))
    {
        return true;
    }
    if (!WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after riddling the chunk")))
    {
        return true;
    }
    const int32 Pieces = Scene.Terrain->GetChunkPieceCount(Busy);
    const int32 Largest = Scene.Terrain->GetLargestCollisionVertexCount();
    TestEqual(TEXT("The busy chunk has one piece in each of its eight blocks"), Pieces, ReflectionsDig::BlocksPerChunk);
    TestTrue(FString::Printf(TEXT("No piece holds more than 12,000 vertices (largest: %d)"), Largest), Largest <= ReflectionsDig::MaxPieceVertices);
    UE_LOG(LogTemp, Display, TEXT("DIGSPIKE busy chunk: %d vertices in %d pieces, largest piece %d vertices"), Premise.Positions.Num(), Pieces, Largest);

    const TOptional<double> Floor = TraceDownZ(TestWorld.World, CavityTraceStart.X, CavityTraceStart.Y, CavityTraceStart.Z);
    if (TestTrue(TEXT("A trace inside a cavity hits something"), Floor.IsSet()))
    {
        const double Expected = CavityCentre.Z - CavityFloorBelowCentreCm;
        TestTrue(FString::Printf(TEXT("It hits the cavity's floor near Z %.1f (hit at %.2f)"), Expected, *Floor), FMath::Abs(*Floor - Expected) <= 25.0);
    }

    // Informal headless timing of one busy-chunk commit (a new set of pieces).
    TimeCommit(*Scene.Terrain, Busy, TEXT("busy chunk"));
    WaitForIdleLoggingSwaps(*this, TestWorld, Scene, TEXT("Idle after the timed commit"));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainOldCollisionStaysWhileNewOneCooksTest, "Reflections.Digging.Terrain.OldCollisionStaysWhileNewOneCooks", DigTerrainTestFlags)
bool FReflectionsDigTerrainOldCollisionStaysWhileNewOneCooksTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    FTerrainScene Scene;
    if (!MakeTerrainScene(*this, TestWorld, Scene))
    {
        return true;
    }

    // One block's piece: dig and fill at one point in the middle of a block on alternate ticks, so every tick changes
    // the grid there and each commit changes that block only (the reuse path). Each tick is traced twice: straight
    // after the world tick (a commit made in it is still cooking), and after the game thread's queued tasks have run
    // (cooks that finished have swapped their body in).
    {
        const FIntVector Chunk(1, 1, 1);
        const FVector Point(2025.0, 2025.0, 0.0);
        int32 Misses = 0;
        int32 TracesWhileCooking = 0;
        TSet<const UBodySetup*> BodiesSeen;
        for (int32 Frame = 0; Frame < 60; ++Frame)
        {
            const EReflectionsDigMode Mode = Frame % 2 == 0 ? EReflectionsDigMode::Remove : EReflectionsDigMode::Add;
            TestTrue(FString::Printf(TEXT("Dig on tick %d changes the grid"), Frame), Scene.Dig->Dig(Point, 100.0f, Mode));
            TickWithoutPumping(TestWorld);
            const UReflectionsDigChunkComponent* Component = Cast<UReflectionsDigChunkComponent>(Scene.Terrain->FindChunkComponent(Chunk));
            if (Component != nullptr && Component->IsCollisionCookPending())
            {
                ++TracesWhileCooking;
            }
            Misses += TraceDownZ(TestWorld.World, Point.X, Point.Y).IsSet() ? 0 : 1;

            PumpGameThread();
            Misses += TraceDownZ(TestWorld.World, Point.X, Point.Y).IsSet() ? 0 : 1;
            Component = Cast<UReflectionsDigChunkComponent>(Scene.Terrain->FindChunkComponent(Chunk));
            if (Component != nullptr)
            {
                BodiesSeen.Add(Component->GetBodySetup());
            }
        }
        TestEqual(TEXT("One-piece chunk: traces that hit nothing"), Misses, 0);
        TestTrue(FString::Printf(TEXT("Some traces ran while a new collision was cooking (%d)"), TracesWhileCooking), TracesWhileCooking > 0);
        TestTrue(FString::Printf(TEXT("Cooks finished and swapped the body in (%d bodies seen)"), BodiesSeen.Num()), BodiesSeen.Num() >= 2);
        WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the one-piece digs"));
    }

    // Two blocks' pieces: each commit replaces the pieces of blocks 3 and 7 with new ones. Dig and fill on their
    // border on alternate ticks and trace a cavity's floor in block 7, away from the digs.
    {
        const FIntVector Busy(1, 1, 0);
        RiddleBuriedChunk(*Scene.Dig);
        if (!WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after riddling the chunk")))
        {
            return true;
        }
        TestEqual(TEXT("The riddled chunk fills all eight blocks"), Scene.Terrain->GetChunkPieceCount(Busy), ReflectionsDig::BlocksPerChunk);

        const FVector OtherCavity = TwoBlockPoint;
        const double Expected = CavityCentre.Z - CavityFloorBelowCentreCm;
        int32 Misses = 0;
        TSet<const UDynamicMeshComponent*> FirstPiecesSeen;
        for (int32 Frame = 0; Frame < 30; ++Frame)
        {
            const EReflectionsDigMode Mode = Frame % 2 == 0 ? EReflectionsDigMode::Add : EReflectionsDigMode::Remove;
            TestTrue(FString::Printf(TEXT("Cavity dig on tick %d changes the grid"), Frame), Scene.Dig->Dig(OtherCavity, 100.0f, Mode));
            TickWithoutPumping(TestWorld);
            for (int32 Trace = 0; Trace < 2; ++Trace)
            {
                const TOptional<double> Floor = TraceDownZ(TestWorld.World, CavityTraceStart.X, CavityTraceStart.Y, CavityTraceStart.Z);
                Misses += Floor.IsSet() && FMath::Abs(*Floor - Expected) <= 25.0 ? 0 : 1;
                if (Trace == 0)
                {
                    PumpGameThread();
                }
            }
            FirstPiecesSeen.Add(Scene.Terrain->GetChunkBlockPiece(Busy, HighBlock));
        }
        TestEqual(TEXT("Two-block commits: traces that missed the cavity floor"), Misses, 0);
        TestTrue(FString::Printf(TEXT("Block 7's piece was replaced (%d pieces seen)"), FirstPiecesSeen.Num()), FirstPiecesSeen.Num() >= 2);
        WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the two-block digs"));
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainSafetyFloorLiesBelowTheGridTest, "Reflections.Digging.Terrain.SafetyFloorLiesBelowTheGrid", DigTerrainTestFlags)
bool FReflectionsDigTerrainSafetyFloorLiesBelowTheGridTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    FTerrainScene Scene;
    if (!MakeTerrainScene(*this, TestWorld, Scene))
    {
        return true;
    }
    // Inside the solid interior of chunk (1, 1, 0) there is no mesh, so the trace falls to the safety floor.
    const TOptional<FHitResult> Hit = TraceDown(TestWorld.World, 2400.0, 2400.0, -2000.0);
    if (TestTrue(TEXT("The trace hits something"), Hit.IsSet()))
    {
        TestTrue(TEXT("It hits the terrain's safety floor"), Hit->GetComponent() != nullptr && Hit->GetComponent() == Scene.Terrain->GetSafetyFloor());
        const double Expected = GridFloorZ - 30.0;
        TestTrue(FString::Printf(TEXT("The safety floor's top is within 1 cm of Z %.1f (hit at %.2f)"), Expected, Hit->ImpactPoint.Z),
            FMath::Abs(Hit->ImpactPoint.Z - Expected) <= 1.0);
    }
    // It is 100 cm thick and spans the whole patch: traces inside solid ground at the four corners of the patch
    // hit it at the same height.
    UBoxComponent* Floor = Scene.Terrain->GetSafetyFloor();
    if (TestNotNull(TEXT("Safety floor"), Floor))
    {
        TestTrue(FString::Printf(TEXT("The safety floor is 100 cm thick (%.2f)"), Floor->GetScaledBoxExtent().Z * 2.0),
            FMath::IsNearlyEqual(Floor->GetScaledBoxExtent().Z * 2.0, 100.0, 0.01));
        for (const FVector2D& Corner : { FVector2D(5.0, 5.0), FVector2D(4795.0, 5.0), FVector2D(5.0, 4795.0), FVector2D(4795.0, 4795.0) })
        {
            const TOptional<FHitResult> CornerHit = TraceDown(TestWorld.World, Corner.X, Corner.Y, -2000.0);
            const bool bHitsFloor = CornerHit.IsSet() && CornerHit->GetComponent() == Floor;
            TestTrue(FString::Printf(TEXT("A trace at the patch corner (%.0f, %.0f) hits the safety floor"), Corner.X, Corner.Y), bHitsFloor);
            if (bHitsFloor)
            {
                TestTrue(FString::Printf(TEXT("At (%.0f, %.0f) its top is at Z %.1f (hit at %.2f)"), Corner.X, Corner.Y, GridFloorZ - 30.0, CornerHit->ImpactPoint.Z),
                    FMath::Abs(CornerHit->ImpactPoint.Z - (GridFloorZ - 30.0)) <= 1.0);
            }
        }
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainChunkWaitsForItsCookBeforeTheNextCommitTest, "Reflections.Digging.Terrain.ChunkWaitsForItsCookBeforeTheNextCommit", DigTerrainTestFlags)
bool FReflectionsDigTerrainChunkWaitsForItsCookBeforeTheNextCommitTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    FTerrainScene Scene;
    if (!MakeTerrainScene(*this, TestWorld, Scene))
    {
        return true;
    }
    // The subsystem is ticked directly here, without a world tick and without running the game thread's queued
    // tasks, so a cook it starts cannot finish until the test pumps the game thread. Both digs touch chunk
    // (1, 1, 1) only.
    const FIntVector Chunk(1, 1, 1);
    const FVector Point(2400.0, 2400.0, 0.0);
    constexpr float DeltaSeconds = 1.0f / 60.0f;
    UReflectionsDigSubsystem* Dig = Scene.Dig;
    auto PieceCooking = [&Scene, Chunk]()
    {
        const UReflectionsDigChunkComponent* Piece = Cast<UReflectionsDigChunkComponent>(Scene.Terrain->FindChunkComponent(Chunk));
        return Piece != nullptr && Piece->IsCollisionCookPending();
    };
    auto WaitWithoutPumping = [](TFunctionRef<bool()> IsDone)
    {
        const double Deadline = FPlatformTime::Seconds() + 5.0;
        while (!IsDone())
        {
            if (FPlatformTime::Seconds() > Deadline)
            {
                return false;
            }
            FPlatformProcess::Sleep(0.001f);
        }
        return true;
    };

    // 1. A first dig is meshed and committed: its cook starts.
    TestTrue(TEXT("The first dig changes the grid"), Dig->Dig(Point, 100.0f, EReflectionsDigMode::Remove));
    const bool bFirstCommitted = WaitWithoutPumping([Dig, DeltaSeconds, &PieceCooking]()
    {
        Dig->Tick(DeltaSeconds);
        return PieceCooking();
    });
    if (!TestTrue(TEXT("The first result is committed and its cook is pending"), bFirstCommitted))
    {
        return true;
    }

    // 2. A newer result arrives while that cook is pending.
    TestTrue(TEXT("The second dig changes the grid"), Dig->Dig(Point - FVector(0.0, 0.0, 50.0), 100.0f, EReflectionsDigMode::Remove));
    Dig->Tick(DeltaSeconds);
    if (!TestTrue(TEXT("The second result is built"), WaitWithoutPumping([Dig]() { return Dig->GetTasksInFlight() == 0; })))
    {
        return true;
    }
    TestEqual(TEXT("The second result is queued"), Dig->GetQueuedCommits(), 1);
    TestTrue(TEXT("The first cook is still pending"), PieceCooking());
    const int32 PiecesBefore = Scene.Terrain->GetChunkPieceCount(Chunk);
    const UDynamicMeshComponent* FirstBefore = Scene.Terrain->FindChunkComponent(Chunk);
    const int32 VerticesBefore = FirstBefore != nullptr ? FirstBefore->GetMesh()->VertexCount() : -1;
    for (int32 Frame = 0; Frame < 3; ++Frame)
    {
        Dig->Tick(DeltaSeconds);
        TestEqual(FString::Printf(TEXT("Tick %d while cooking commits nothing"), Frame), Dig->GetCommitsLastTick(), 0);
        TestEqual(FString::Printf(TEXT("Tick %d while cooking keeps the result queued"), Frame), Dig->GetQueuedCommits(), 1);
        TestEqual(FString::Printf(TEXT("Tick %d while cooking keeps the piece count"), Frame), Scene.Terrain->GetChunkPieceCount(Chunk), PiecesBefore);
        const UDynamicMeshComponent* First = Scene.Terrain->FindChunkComponent(Chunk);
        TestTrue(FString::Printf(TEXT("Tick %d while cooking keeps the current piece"), Frame), First == FirstBefore);
        TestEqual(FString::Printf(TEXT("Tick %d while cooking keeps the piece's mesh"), Frame),
            First != nullptr ? First->GetMesh()->VertexCount() : -1, VerticesBefore);
        FPlatformProcess::Sleep(0.001f);
    }

    // 3. Once the cook has finished, the next tick commits the waiting result.
    const bool bCooked = WaitWithoutPumping([&PieceCooking]()
    {
        FTaskGraphInterface::Get().ProcessThreadUntilIdle(ENamedThreads::GameThread);
        return !PieceCooking();
    });
    if (TestTrue(TEXT("The first cook finishes once the game thread runs"), bCooked))
    {
        Dig->Tick(DeltaSeconds);
        TestEqual(TEXT("The next tick commits the waiting result"), Dig->GetCommitsLastTick(), 1);
        TestEqual(TEXT("Nothing is left queued"), Dig->GetQueuedCommits(), 0);
        TestTrue(TEXT("The committed result's cook has started"), PieceCooking());
    }
    if (!WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the two digs")))
    {
        return true;
    }

    // 4. A held dig at a point that moves down 10 cm a tick: the collision under it keeps moving.
    int32 Changes = 0;
    TOptional<double> LastZ = TraceDownZ(TestWorld.World, Point.X, Point.Y);
    for (int32 Frame = 0; Frame < 120; ++Frame)
    {
        Dig->Dig(Point - FVector(0.0, 0.0, 100.0 + 10.0 * Frame), 100.0f, EReflectionsDigMode::Remove);
        TickWithoutPumping(TestWorld);
        PumpGameThread();
        const TOptional<double> Z = TraceDownZ(TestWorld.World, Point.X, Point.Y);
        if (Z.IsSet() && (!LastZ.IsSet() || FMath::Abs(*Z - *LastZ) > 1.0))
        {
            ++Changes;
        }
        LastZ = Z;
    }
    TestTrue(FString::Printf(TEXT("The collision under the held dig changed at least 10 times (%d)"), Changes), Changes >= 10);
    WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the held dig"));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainRetiredSetGoesDuringAHeldDigTest, "Reflections.Digging.Terrain.RetiredSetGoesDuringAHeldDig", DigTerrainTestFlags)
bool FReflectionsDigTerrainRetiredSetGoesDuringAHeldDigTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    FTerrainScene Scene;
    if (!MakeTerrainScene(*this, TestWorld, Scene))
    {
        return true;
    }
    const FIntVector Busy(1, 1, 0);
    RiddleBuriedChunk(*Scene.Dig);
    if (!WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after riddling the chunk")))
    {
        return true;
    }
    TestEqual(TEXT("The riddled chunk fills all eight blocks"), Scene.Terrain->GetChunkPieceCount(Busy), ReflectionsDig::BlocksPerChunk);

    // Fill it back with radius-150 Adds on every lattice row but the lowest, so its upper blocks are solid again.
    for (double Z = -2500.0; Z <= -1300.0; Z += 200.0)
    {
        for (double Y = 1725.0; Y <= 3125.0; Y += 200.0)
        {
            for (double X = 1725.0; X <= 3125.0; X += 200.0)
            {
                Scene.Dig->Dig(FVector(X, Y, Z), 150.0f, EReflectionsDigMode::Add);
            }
        }
    }

    // Hold a Remove that moves down 10 cm a tick through the filled space of block 7 (X and Y 2425..3225, Z
    // -2000..-1200), starting at once (no idle in between, so the riddled pieces are still retiring when the
    // one-block commits begin): after the first commit each commit changes block 7 only and takes the reuse path.
    // The trace starts inside the new pit, 50 cm off its axis; the old cavity there had its floor at about Z -1371.
    const FVector PitAxis(2725.0, 2725.0, -1300.0);
    const FVector TraceStart = PitAxis + FVector(50.0, 50.0, 0.0);
    const double OldSurfaceZ = PitAxis.Z - CavityFloorBelowCentreCm;
    double DeepestZ = 0.0;
    bool bSawReuse = false;
    const UDynamicMeshComponent* LastPiece = nullptr;
    int32 LastChanged = Scene.Terrain->GetPiecesChangedCount();
    for (int32 Frame = 0; Frame < 50; ++Frame)
    {
        Scene.Dig->Dig(PitAxis - FVector(0.0, 0.0, 10.0 * Frame), 100.0f, EReflectionsDigMode::Remove);
        TickWithoutPumping(TestWorld);
        PumpGameThread();
        const UDynamicMeshComponent* Piece = Scene.Terrain->GetChunkBlockPiece(Busy, HighBlock);
        const int32 Changed = Scene.Terrain->GetPiecesChangedCount();
        bSawReuse |= Piece != nullptr && Piece == LastPiece && Changed > LastChanged;
        LastPiece = Piece;
        LastChanged = Changed;
        const TOptional<double> Z = TraceDownZ(TestWorld.World, TraceStart.X, TraceStart.Y, TraceStart.Z);
        if (Z.IsSet())
        {
            DeepestZ = FMath::Min(DeepestZ, *Z);
        }
    }
    TestTrue(TEXT("Block 7's piece took the reuse path during the hold"), bSawReuse);
    TestTrue(FString::Printf(TEXT("A trace into the new pit reached well below the old surface at %.1f (deepest %.2f)"), OldSurfaceZ, DeepestZ),
        DeepestZ < OldSurfaceZ - 200.0);
    // The emptied blocks' retiring pieces wait for a quiet terrain; none of them is block 7's, around the pit.
    const FVector InPit = PitAxis - FVector(0.0, 0.0, 200.0);
    const int32 RetiringAtPit = GetHiddenPiecesAround(*Scene.Terrain, InPit);
    TestEqual(TEXT("No retiring piece is left around the pit by the end of the hold"), RetiringAtPit, 0);
    WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the held dig"));
    TestEqual(TEXT("No retiring pieces are left once the terrain is idle"), Scene.Terrain->GetRetiringPieceCount(Busy), 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainDirectCommitWhileCookingKeepsTheRetiringFloorTest, "Reflections.Digging.Terrain.DirectCommitWhileCookingKeepsTheRetiringFloor", DigTerrainTestFlags)
bool FReflectionsDigTerrainDirectCommitWhileCookingKeepsTheRetiringFloorTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    FTerrainScene Scene;
    if (!MakeTerrainScene(*this, TestWorld, Scene))
    {
        return true;
    }
    const FIntVector Busy(1, 1, 0);
    RiddleBuriedChunk(*Scene.Dig);
    if (!WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after riddling the chunk")))
    {
        return true;
    }
    TestEqual(TEXT("The riddled chunk fills all eight blocks"), Scene.Terrain->GetChunkPieceCount(Busy), ReflectionsDig::BlocksPerChunk);
    const double FloorZ = CavityCentre.Z - CavityFloorBelowCentreCm;
    // Blocks 3 and 7: the cavity traced below is in block 7.
    const FVector Elsewhere = TwoBlockPoint;

    // A first direct commit retires the cooked pieces of the two blocks; a second one, while their replacements are
    // still cooking, must destroy those replacements and keep the retiring pieces. Nothing is pumped in between, so
    // no cook finishes.
    TestTrue(TEXT("The first change changes the grid"), Scene.Dig->Dig(Elsewhere, 100.0f, EReflectionsDigMode::Add));
    FReflectionsDigMeshData First;
    ReflectionsDigMesher::BuildChunk(*Scene.Terrain->GetGrid(), Busy, First);
    Scene.Terrain->CommitChunk(Busy, MoveTemp(First));
    TestTrue(TEXT("The first replacement is cooking"), Scene.Terrain->IsChunkCooking(Busy));
    TestEqual(TEXT("The two blocks' cooked pieces are retiring"), Scene.Terrain->GetRetiringPieceCount(Busy), 2);

    TestTrue(TEXT("The second change changes the grid"), Scene.Dig->Dig(Elsewhere, 100.0f, EReflectionsDigMode::Remove));
    FReflectionsDigMeshData Second;
    ReflectionsDigMesher::BuildChunk(*Scene.Terrain->GetGrid(), Busy, Second);
    Scene.Terrain->CommitChunk(Busy, MoveTemp(Second));
    TestTrue(TEXT("The second replacement is cooking"), Scene.Terrain->IsChunkCooking(Busy));

    const TOptional<double> Floor = TraceDownZ(TestWorld.World, CavityTraceStart.X, CavityTraceStart.Y, CavityTraceStart.Z);
    if (TestTrue(TEXT("On that tick a trace into the cavity hits a terrain piece"), Floor.IsSet()))
    {
        TestTrue(FString::Printf(TEXT("It hits the retiring set's cavity floor near Z %.1f (hit at %.2f)"), FloorZ, *Floor), FMath::Abs(*Floor - FloorZ) <= 25.0);
    }
    WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the direct commits"));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainReusePathClearsAFinishedRetiringSetTest, "Reflections.Digging.Terrain.ReusePathClearsAFinishedRetiringSet", DigTerrainTestFlags)
bool FReflectionsDigTerrainReusePathClearsAFinishedRetiringSetTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    FTerrainScene Scene;
    if (!MakeTerrainScene(*this, TestWorld, Scene))
    {
        return true;
    }
    const FIntVector Busy(1, 1, 0);
    RiddleBuriedChunk(*Scene.Dig);
    if (!WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after riddling the chunk")))
    {
        return true;
    }
    TestEqual(TEXT("The riddled chunk fills all eight blocks"), Scene.Terrain->GetChunkPieceCount(Busy), ReflectionsDig::BlocksPerChunk);

    // Change blocks 3 and 7 and commit that directly: their pieces retire behind two new ones.
    TestTrue(TEXT("The two-block change changes the grid"), Scene.Dig->Dig(TwoBlockPoint, 100.0f, EReflectionsDigMode::Add));
    CommitFromGrid(*Scene.Terrain, Busy);
    const int32 RetiringBefore = Scene.Terrain->GetRetiringPieceCount(Busy);
    TestEqual(TEXT("Premise: the two blocks' pieces are retiring"), RetiringBefore, 2);
    const UDynamicMeshComponent* Block7Piece = Scene.Terrain->GetChunkBlockPiece(Busy, HighBlock);

    // Let the new pieces' cooks finish without ticking the world, so no swap check runs.
    const double Deadline = FPlatformTime::Seconds() + IdleTimeoutSeconds;
    while (Scene.Terrain->IsChunkCooking(Busy) && FPlatformTime::Seconds() < Deadline)
    {
        PumpGameThread();
    }
    if (!TestFalse(TEXT("The new pieces' cooks finish while the game thread is pumped"), Scene.Terrain->IsChunkCooking(Busy)))
    {
        return true;
    }
    TestEqual(TEXT("Premise: with no tick the two pieces are still retiring"), Scene.Terrain->GetRetiringPieceCount(Busy), RetiringBefore);

    // A direct commit that changes block 7 only takes the reuse path, which must finish the swap that is due first.
    TestTrue(TEXT("The one-block change changes the grid"), Scene.Dig->Dig(InsideBlock7, 100.0f, EReflectionsDigMode::Add));
    CommitFromGrid(*Scene.Terrain, Busy);
    TestTrue(TEXT("Premise: block 7 kept its piece (the reuse path)"), Block7Piece != nullptr && Scene.Terrain->GetChunkBlockPiece(Busy, HighBlock) == Block7Piece);
    TestTrue(TEXT("Premise: block 7's piece is cooking its new mesh"), Scene.Terrain->IsChunkCooking(Busy));
    TestEqual(TEXT("The chunk still fills all eight blocks"), Scene.Terrain->GetChunkPieceCount(Busy), ReflectionsDig::BlocksPerChunk);
    TestEqual(TEXT("The reuse commit destroyed the finished retiring pieces"), Scene.Terrain->GetRetiringPieceCount(Busy), 0);
    WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the reuse commit"));
    return true;
}

namespace
{
    /** The terrain's retiring pieces, every chunk's: they are the hidden ones. */
    TArray<UReflectionsDigChunkComponent*> GetHiddenPieces(const AReflectionsDigTerrain& Terrain)
    {
        TArray<UReflectionsDigChunkComponent*> Pieces;
        Terrain.GetComponents(Pieces);
        Pieces.RemoveAll([](const UReflectionsDigChunkComponent* Piece) { return Piece->IsVisible(); });
        return Pieces;
    }

    /**
     * Riddles chunk (1, 1, 0), then changes its blocks 3 and 7 straight in the grid (the subsystem does not see it)
     * and commits the chunk's mesh directly, so the two blocks' pieces retire behind new pieces that are still
     * cooking. OutCreated gets the new pieces. Returns false (reported) when a premise fails.
     */
    bool RetireTheRiddledChunk(FAutomationTestBase& Test, FReflectionsDigTestWorld& TestWorld, const FTerrainScene& Scene, FIntVector Busy,
        TArray<UReflectionsDigChunkComponent*>* OutCreated = nullptr)
    {
        RiddleBuriedChunk(*Scene.Dig);
        if (!WaitForIdle(Test, TestWorld, Scene, TEXT("Idle after riddling the chunk")))
        {
            return false;
        }
        Test.TestEqual(TEXT("The riddled chunk fills all eight blocks"), Scene.Terrain->GetChunkPieceCount(Busy), ReflectionsDig::BlocksPerChunk);
        Test.TestEqual(TEXT("Premise: no piece is hidden before the commit"), GetHiddenPieces(*Scene.Terrain).Num(), 0);
        const TStaticArray<UDynamicMeshComponent*, ReflectionsDig::BlocksPerChunk> Before = GetSlots(*Scene.Terrain, Busy);
        StampGrid(*Scene.Terrain, TwoBlockPoint, EReflectionsDigMode::Add);
        CommitFromGrid(*Scene.Terrain, Busy);
        const TStaticArray<UDynamicMeshComponent*, ReflectionsDig::BlocksPerChunk> After = GetSlots(*Scene.Terrain, Busy);
        int32 Created = 0;
        for (int32 Block = 0; Block < ReflectionsDig::BlocksPerChunk; ++Block)
        {
            if (After[Block] != nullptr && After[Block] != Before[Block])
            {
                ++Created;
                if (OutCreated != nullptr)
                {
                    OutCreated->Add(Cast<UReflectionsDigChunkComponent>(After[Block]));
                }
            }
        }
        return Test.TestTrue(TEXT("Premise: the new pieces are cooking"), Scene.Terrain->IsChunkCooking(Busy))
            && Test.TestEqual(TEXT("Premise: the commit created two pieces"), Created, 2)
            && Test.TestEqual(TEXT("Premise: the two blocks' old pieces are retiring"), Scene.Terrain->GetRetiringPieceCount(Busy), 2);
    }

    /**
     * Lets the chunk's cooks finish by running the game thread's tasks without ticking the world, as happens between
     * two ticks: no swap check runs. Returns false (reported) when they do not finish in time.
     */
    bool FinishCooksWithoutATick(FAutomationTestBase& Test, const FTerrainScene& Scene, FIntVector Chunk)
    {
        const double Deadline = FPlatformTime::Seconds() + IdleTimeoutSeconds;
        while (Scene.Terrain->IsChunkCooking(Chunk) && FPlatformTime::Seconds() < Deadline)
        {
            PumpGameThread();
        }
        return Test.TestFalse(TEXT("The new set's cooks finish while the game thread is pumped, with no tick"), Scene.Terrain->IsChunkCooking(Chunk));
    }

    /** Counts the log lines that contain a text, as they are logged, for one scope. */
    struct FScopedLogCounter : public FOutputDevice
    {
        explicit FScopedLogCounter(const TCHAR* InText)
            : Text(InText)
        {
            GLog->AddOutputDevice(this);
        }

        virtual ~FScopedLogCounter() override
        {
            GLog->RemoveOutputDevice(this);
        }

        virtual void Serialize(const TCHAR* Message, ELogVerbosity::Type Verbosity, const FName& Category) override
        {
            if (FCString::Strstr(Message, *Text) != nullptr)
            {
                ++Count;
            }
        }

        /** Unbuffered: called on the logging thread at once, so a count read right after a call is current. */
        virtual bool CanBeUsedOnMultipleThreads() const override
        {
            return true;
        }

        FString Text;
        std::atomic<int32> Count{ 0 };
    };
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainRetiringPiecesLeaveNavigationAtOnceTest, "Reflections.Digging.Terrain.RetiringPiecesLeaveNavigationAtOnce", DigTerrainTestFlags)
bool FReflectionsDigTerrainRetiringPiecesLeaveNavigationAtOnceTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    FTerrainScene Scene;
    if (!MakeTerrainScene(*this, TestWorld, Scene))
    {
        return true;
    }
    const FIntVector Busy(1, 1, 0);
    if (!RetireTheRiddledChunk(*this, TestWorld, Scene, Busy))
    {
        return true;
    }
    // The swap window: the replacement is cooking, the old set still collides but is old collision.
    const TArray<UReflectionsDigChunkComponent*> Retiring = GetHiddenPieces(*Scene.Terrain);
    TestEqual(TEXT("The hidden pieces are the retiring set"), Retiring.Num(), Scene.Terrain->GetRetiringPieceCount(Busy));
    for (const UReflectionsDigChunkComponent* Piece : Retiring)
    {
        TestFalse(FString::Printf(TEXT("Retiring piece %s cannot affect navigation"), *Piece->GetName()), Piece->CanEverAffectNavigation());
    }
    // A successful cook that lands between ticks leaves a swap due: the terrain is not idle until the swap check
    // has destroyed the retiring set.
    if (!FinishCooksWithoutATick(*this, Scene, Busy))
    {
        return true;
    }
    TestFalse(TEXT("Before any tick, a due swap keeps the terrain from idle"), Scene.Dig->IsIdle());
    if (WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the commit")))
    {
        TestEqual(TEXT("The retiring set is gone once the new set has cooked"), Scene.Terrain->GetRetiringPieceCount(Busy), 0);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainFailedCookGivesTheRetiringSetItsNavigationBackTest, "Reflections.Digging.Terrain.FailedCookGivesTheRetiringSetItsNavigationBack", DigTerrainTestFlags)
bool FReflectionsDigTerrainFailedCookGivesTheRetiringSetItsNavigationBackTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    FTerrainScene Scene;
    if (!MakeTerrainScene(*this, TestWorld, Scene))
    {
        return true;
    }
    const FIntVector Busy(1, 1, 0);
    TArray<UReflectionsDigChunkComponent*> Created;
    if (!RetireTheRiddledChunk(*this, TestWorld, Scene, Busy, &Created))
    {
        return true;
    }
    // Every new piece fails its cook, so the retiring pieces stay those blocks' only collision.
    const TCHAR* FailureWarning = TEXT("a collision cook failed or a piece has no collision");
    AddExpectedMessagePlain(FailureWarning, ELogVerbosity::Warning, EAutomationExpectedMessageFlags::Contains, 1);
    FScopedLogCounter Warnings(FailureWarning);
    TArray<UReflectionsDigChunkComponent*> All;
    Scene.Terrain->GetComponents(All);
    int32 Failing = 0;
    for (UReflectionsDigChunkComponent* Piece : All)
    {
        if (Piece->IsCollisionCookPending())
        {
            Piece->FailNextCookForTest();
            ++Failing;
        }
    }
    TestEqual(TEXT("Premise: every cooking piece is one the commit created"), Failing, Created.Num());
    const int32 RetiringBefore = Scene.Terrain->GetRetiringPieceCount(Busy);

    // The cooks fail between ticks. Until the next swap check has handled the failure, something is still to happen.
    if (!FinishCooksWithoutATick(*this, Scene, Busy))
    {
        return true;
    }
    TestFalse(TEXT("Before any tick, an unhandled failed cook keeps the terrain from idle"), Scene.Dig->IsIdle());
    TestEqual(TEXT("Before any tick, no failure warning yet"), Warnings.Count.load(), 0);

    // Everything below holds at the first moment the terrain is idle.
    if (!WaitForIdle(*this, TestWorld, Scene, TEXT("The terrain reaches idle after the failed cooks")))
    {
        return true;
    }
    TestEqual(TEXT("At the first idle the failure warning has been logged once"), Warnings.Count.load(), 1);
    TestEqual(TEXT("The retiring set is kept"), Scene.Terrain->GetRetiringPieceCount(Busy), RetiringBefore);
    const TOptional<FHitResult> Hit = TraceDown(TestWorld.World, CavityTraceStart.X, CavityTraceStart.Y, CavityTraceStart.Z);
    const UReflectionsDigChunkComponent* HitPiece = Hit.IsSet() ? Cast<UReflectionsDigChunkComponent>(Hit->GetComponent()) : nullptr;
    const double FloorZ = CavityCentre.Z - CavityFloorBelowCentreCm;
    if (TestTrue(TEXT("A trace into the cavity hits a terrain piece"), HitPiece != nullptr))
    {
        TestFalse(TEXT("It hits the kept retiring set (a hidden piece)"), HitPiece->IsVisible());
        TestTrue(FString::Printf(TEXT("It hits the cavity floor near Z %.1f (hit at %.2f)"), FloorZ, Hit->ImpactPoint.Z),
            FMath::Abs(Hit->ImpactPoint.Z - FloorZ) <= 25.0);
    }
    const TArray<UReflectionsDigChunkComponent*> Kept = GetHiddenPieces(*Scene.Terrain);
    TestEqual(TEXT("The hidden pieces are the kept retiring set"), Kept.Num(), RetiringBefore);
    for (const UReflectionsDigChunkComponent* Piece : Kept)
    {
        TestTrue(FString::Printf(TEXT("At the first idle, kept retiring piece %s can affect navigation again"), *Piece->GetName()), Piece->CanEverAffectNavigation());
    }
    return true;
}

namespace
{
    /** Marks every piece whose cook is running to fail it; returns how many. */
    int32 FailEveryPendingCook(const AReflectionsDigTerrain& Terrain)
    {
        TArray<UReflectionsDigChunkComponent*> All;
        Terrain.GetComponents(All);
        int32 Failing = 0;
        for (UReflectionsDigChunkComponent* Piece : All)
        {
            if (Piece->IsCollisionCookPending())
            {
                Piece->FailNextCookForTest();
                ++Failing;
            }
        }
        return Failing;
    }

    /**
     * Checks that every retiring piece of the chunk has navigation back (Expected true) or has left it again (false).
     * Returns false (reported) when the chunk has no retiring pieces.
     */
    bool TestRetiringNavigation(FAutomationTestBase& Test, const AReflectionsDigTerrain& Terrain, const FString& When, bool bExpected)
    {
        const TArray<UReflectionsDigChunkComponent*> Retiring = GetHiddenPieces(Terrain);
        if (!Test.TestTrue(FString::Printf(TEXT("%s: the chunk has retiring pieces"), *When), Retiring.Num() > 0))
        {
            return false;
        }
        for (const UReflectionsDigChunkComponent* Piece : Retiring)
        {
            Test.TestEqual(FString::Printf(TEXT("%s: retiring piece %s can affect navigation"), *When, *Piece->GetName()),
                Piece->CanEverAffectNavigation(), bExpected);
        }
        return true;
    }
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainKeptRetiringSetLeavesNavigationAtTheNextCommitTest, "Reflections.Digging.Terrain.KeptRetiringSetLeavesNavigationAtTheNextCommit", DigTerrainTestFlags)
bool FReflectionsDigTerrainKeptRetiringSetLeavesNavigationAtTheNextCommitTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    FTerrainScene Scene;
    if (!MakeTerrainScene(*this, TestWorld, Scene))
    {
        return true;
    }
    const FIntVector Busy(1, 1, 0);
    // Two failed cooks below, one warning each.
    AddExpectedMessagePlain(TEXT("a collision cook failed or a piece has no collision"), ELogVerbosity::Warning, EAutomationExpectedMessageFlags::Contains, 2);

    // Part 1, the replace path (RetireCurrentSet): kept pieces of blocks 3 and 7 behind new ones that never got
    // collision. The next commit of the same mesh changes no hash, but the two blocks never collided with it, so it
    // replaces their pieces again.
    if (!RetireTheRiddledChunk(*this, TestWorld, Scene, Busy))
    {
        return true;
    }
    TestEqual(TEXT("Premise: every cooking piece is one of the two the commit created"), FailEveryPendingCook(*Scene.Terrain), 2);
    if (!WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the two pieces' failed cooks"))
        || !TestRetiringNavigation(*this, *Scene.Terrain, TEXT("Part 1, at the first idle"), true))
    {
        return true;
    }
    const int32 KeptPair = Scene.Terrain->GetRetiringPieceCount(Busy);
    const TStaticArray<UDynamicMeshComponent*, ReflectionsDig::BlocksPerChunk> FailedSlots = GetSlots(*Scene.Terrain, Busy);
    CommitFromGrid(*Scene.Terrain, Busy);
    TestTrue(TEXT("Premise: part 1's commit replaces block 3's and block 7's pieces"),
        Scene.Terrain->GetChunkBlockPiece(Busy, 3) != FailedSlots[3] && Scene.Terrain->GetChunkBlockPiece(Busy, HighBlock) != FailedSlots[HighBlock]);
    TestTrue(TEXT("Premise: part 1's new pieces are cooking"), Scene.Terrain->IsChunkCooking(Busy));
    TestEqual(TEXT("Premise: part 1 keeps the same retiring pieces"), Scene.Terrain->GetRetiringPieceCount(Busy), KeptPair);
    TestRetiringNavigation(*this, *Scene.Terrain, TEXT("Part 1, while the next pieces cook"), false);
    if (!WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after part 1's commit")))
    {
        return true;
    }
    TestEqual(TEXT("Part 1's retiring pieces are gone once the new pieces have cooked"), Scene.Terrain->GetRetiringPieceCount(Busy), 0);

    // Part 2, the reuse path (one block changes, with a piece before and after): a kept pair behind block 7's piece,
    // which never got collision. Blocks 3 and 7 change again; only block 7's new piece fails its cook.
    StampGrid(*Scene.Terrain, TwoBlockPoint, EReflectionsDigMode::Remove);
    CommitFromGrid(*Scene.Terrain, Busy);
    TestEqual(TEXT("Premise: part 2's first commit retires blocks 3 and 7"), Scene.Terrain->GetRetiringPieceCount(Busy), 2);
    UReflectionsDigChunkComponent* Reused = Cast<UReflectionsDigChunkComponent>(Scene.Terrain->GetChunkBlockPiece(Busy, HighBlock));
    if (!TestTrue(TEXT("Premise: block 7's new piece is cooking"), Reused != nullptr && Reused->IsCollisionCookPending()))
    {
        return true;
    }
    Reused->FailNextCookForTest();
    if (!WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after block 7's failed cook"))
        || !TestRetiringNavigation(*this, *Scene.Terrain, TEXT("Part 2, at the first idle"), true))
    {
        return true;
    }
    const int32 KeptForReuse = Scene.Terrain->GetRetiringPieceCount(Busy);
    TestEqual(TEXT("Premise: the failed cook keeps both retiring pieces"), KeptForReuse, 2);
    CommitFromGrid(*Scene.Terrain, Busy);
    TestTrue(TEXT("Premise: part 2's commit reuses block 7's piece"), Scene.Terrain->GetChunkBlockPiece(Busy, HighBlock) == Reused);
    TestTrue(TEXT("Premise: the reused piece is cooking"), Scene.Terrain->IsChunkCooking(Busy) && Reused->IsCollisionCookPending());
    TestEqual(TEXT("Premise: part 2 keeps the same retiring pieces"), Scene.Terrain->GetRetiringPieceCount(Busy), KeptForReuse);
    TestRetiringNavigation(*this, *Scene.Terrain, TEXT("Part 2, while the reused piece cooks"), false);
    if (WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after part 2's commit")))
    {
        TestEqual(TEXT("Part 2's retiring pieces are gone once the reused piece has cooked"), Scene.Terrain->GetRetiringPieceCount(Busy), 0);
    }
    return true;
}

namespace
{
    /** Records what a navigation geometry export is asked to do; it exports nothing. */
    struct FRecordingGeometryExport : public FNavigableGeometryExport
    {
        int32 CustomMeshCalls = 0;
        int32 CustomMeshVertices = 0;
        int32 CustomMeshIndices = 0;
        int32 RigidBodyCalls = 0;
        int32 OtherCalls = 0;

        virtual void ExportChaosTriMesh(const Chaos::FTriangleMeshImplicitObject* const TriMesh, const FTransform& LocalToWorld) override { ++OtherCalls; }
        virtual void ExportChaosConvexMesh(const FKConvexElem* const Convex, const FTransform& LocalToWorld) override { ++OtherCalls; }
        virtual void ExportChaosHeightField(const Chaos::FHeightField* const Heightfield, const FTransform& LocalToWorld) override { ++OtherCalls; }
        virtual void ExportChaosHeightFieldSlice(const FNavHeightfieldSamples& PrefetchedHeightfieldSamples, const int32 NumRows, const int32 NumCols,
            const FTransform& LocalToWorld, const FBox& SliceBox) override { ++OtherCalls; }
        virtual void ExportRigidBodySetup(UBodySetup& BodySetup, const FTransform& LocalToWorld) override { ++RigidBodyCalls; }
        virtual void ExportCustomMesh(const FVector* VertexBuffer, int32 NumVerts, const int32* IndexBuffer, int32 NumIndices, const FTransform& LocalToWorld) override
        {
            ++CustomMeshCalls;
            CustomMeshVertices += NumVerts;
            CustomMeshIndices += NumIndices;
        }
        virtual void AddNavModifiers(const FCompositeNavModifier& Modifiers) override {}
        virtual void SetNavDataPerInstanceTransformDelegate(const FNavDataPerInstanceTransformDelegate& InDelegate) override {}
    };
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainPieceExportsItsOwnNavigationGeometryTest, "Reflections.Digging.Terrain.PieceExportsItsOwnNavigationGeometry", DigTerrainTestFlags)
bool FReflectionsDigTerrainPieceExportsItsOwnNavigationGeometryTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    FTerrainScene Scene;
    if (!MakeTerrainScene(*this, TestWorld, Scene))
    {
        return true;
    }
    // A chunk committed directly, with its collision in.
    const FIntVector Chunk(1, 1, 1);
    FReflectionsDigMeshData Mesh;
    ReflectionsDigMesher::BuildChunk(*Scene.Terrain->GetGrid(), Chunk, Mesh);
    Scene.Terrain->CommitChunk(Chunk, MoveTemp(Mesh));
    if (!WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the commit")))
    {
        return true;
    }
    const UReflectionsDigChunkComponent* Piece = Cast<UReflectionsDigChunkComponent>(Scene.Terrain->FindChunkComponent(Chunk));
    if (!TestNotNull(TEXT("The chunk has a piece"), Piece) || !TestNotNull(TEXT("The piece has a mesh"), Piece->GetMesh()))
    {
        return true;
    }
    FRecordingGeometryExport Export;
    const bool bDefaultExportRequired = Piece->DoCustomNavigableGeometryExport(Export);
    TestFalse(TEXT("The export says the default (body setup) export is not required"), bDefaultExportRequired);
    TestEqual(TEXT("ExportCustomMesh is called once"), Export.CustomMeshCalls, 1);
    TestEqual(TEXT("It is given three indices per triangle of the piece"), Export.CustomMeshIndices, 3 * Piece->GetMesh()->TriangleCount());
    TestEqual(TEXT("It is given the piece's vertices"), Export.CustomMeshVertices, Piece->GetMesh()->VertexCount());
    TestEqual(TEXT("ExportRigidBodySetup is never called"), Export.RigidBodyCalls, 0);
    TestEqual(TEXT("Nothing else is exported"), Export.OtherCalls, 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainNewPieceWaitsForCollisionBeforeNavigationTest, "Reflections.Digging.Terrain.NewPieceWaitsForCollisionBeforeNavigation", DigTerrainTestFlags)
bool FReflectionsDigTerrainNewPieceWaitsForCollisionBeforeNavigationTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    FTerrainScene Scene;
    if (!MakeTerrainScene(*this, TestWorld, Scene))
    {
        return true;
    }
    const FIntVector Busy(1, 1, 0);
    // The commit inside creates two new pieces, still cooking, in front of the pieces that cooked before them.
    TArray<UReflectionsDigChunkComponent*> Created;
    if (!RetireTheRiddledChunk(*this, TestWorld, Scene, Busy, &Created))
    {
        return true;
    }
    const TArray<UReflectionsDigChunkComponent*> Retiring = GetHiddenPieces(*Scene.Terrain);
    TestTrue(TEXT("Premise: the chunk has retiring pieces"), Retiring.Num() > 0);
    for (const UReflectionsDigChunkComponent* Piece : Created)
    {
        if (TestNotNull(TEXT("A created piece"), Piece))
        {
            TestTrue(FString::Printf(TEXT("Premise: created piece %s is cooking its first collision"), *Piece->GetName()), Piece->IsCollisionCookPending());
            TestFalse(FString::Printf(TEXT("Before its first cook finishes, created piece %s is not navigation relevant"), *Piece->GetName()),
                Piece->IsNavigationRelevant());
        }
    }
    for (const UReflectionsDigChunkComponent* Piece : Retiring)
    {
        TestFalse(FString::Printf(TEXT("Retiring piece %s is not navigation relevant"), *Piece->GetName()), Piece->IsNavigationRelevant());
    }
    if (!FinishCooksWithoutATick(*this, Scene, Busy))
    {
        return true;
    }
    for (const UReflectionsDigChunkComponent* Piece : Created)
    {
        if (Piece != nullptr)
        {
            TestTrue(FString::Printf(TEXT("Premise: created piece %s has collision"), *Piece->GetName()), Piece->HasCollision());
            TestTrue(FString::Printf(TEXT("Once its first cook has finished, created piece %s is navigation relevant"), *Piece->GetName()),
                Piece->IsNavigationRelevant());
        }
    }
    for (const UReflectionsDigChunkComponent* Piece : Retiring)
    {
        TestFalse(FString::Printf(TEXT("After the cooks, retiring piece %s is still not navigation relevant"), *Piece->GetName()), Piece->IsNavigationRelevant());
    }
    WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the commit"));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainUnchangedBlocksAreNotTouchedTest, "Reflections.Digging.Terrain.UnchangedBlocksAreNotTouched", DigTerrainTestFlags)
bool FReflectionsDigTerrainUnchangedBlocksAreNotTouchedTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    FTerrainScene Scene;
    if (!MakeTerrainScene(*this, TestWorld, Scene))
    {
        return true;
    }
    const FIntVector Busy(1, 1, 0);
    RiddleBuriedChunk(*Scene.Dig);
    if (!WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after riddling the chunk")))
    {
        return true;
    }
    const TStaticArray<UDynamicMeshComponent*, ReflectionsDig::BlocksPerChunk> Before = GetSlots(*Scene.Terrain, Busy);
    TArray<const UBodySetup*> BodiesBefore;
    for (int32 Block = 0; Block < ReflectionsDig::BlocksPerChunk; ++Block)
    {
        if (!TestNotNull(FString::Printf(TEXT("Premise: the riddled chunk has a piece in block %d"), Block), Before[Block]))
        {
            return true;
        }
        BodiesBefore.Add(Before[Block]->GetBodySetup());
    }
    const int32 CooksBefore = Scene.Terrain->GetCookCompletionCount();
    const int32 KeptBefore = Scene.Terrain->GetPiecesKeptCount();
    const int32 ChangedBefore = Scene.Terrain->GetPiecesChangedCount();

    // One dig in the middle of block 0 (X and Y 1625..2425, Z -2800..-2000), between the cavities and 400 cm from
    // every border of the block, so no other block's triangles and no other chunk change.
    constexpr int32 DugBlock = 0;
    TestTrue(TEXT("The dig changes the grid"), Scene.Dig->Dig(FVector(2025.0, 2025.0, -2400.0), 100.0f, EReflectionsDigMode::Remove));
    if (!WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the dig")))
    {
        return true;
    }
    TestEqual(TEXT("One slot was given a new mesh"), Scene.Terrain->GetPiecesChangedCount() - ChangedBefore, 1);
    TestNotNull(TEXT("The dug block still has a piece"), Scene.Terrain->GetChunkBlockPiece(Busy, DugBlock));
    for (int32 Block = 0; Block < ReflectionsDig::BlocksPerChunk; ++Block)
    {
        if (Block == DugBlock)
        {
            continue;
        }
        UDynamicMeshComponent* Piece = Scene.Terrain->GetChunkBlockPiece(Busy, Block);
        TestTrue(FString::Printf(TEXT("Block %d holds the same component"), Block), Piece == Before[Block]);
        TestTrue(FString::Printf(TEXT("Block %d keeps the same body"), Block), Piece != nullptr && Piece->GetBodySetup() == BodiesBefore[Block]);
    }
    TestEqual(TEXT("The other seven filled slots were kept"), Scene.Terrain->GetPiecesKeptCount() - KeptBefore, ReflectionsDig::BlocksPerChunk - 1);
    TestEqual(TEXT("Exactly one collision cook finished"), Scene.Terrain->GetCookCompletionCount() - CooksBefore, 1);
    TestEqual(TEXT("Nothing is retiring"), Scene.Terrain->GetRetiringPieceCount(Busy), 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainBorderOnlyChangeDoesNoWorkTest, "Reflections.Digging.Terrain.BorderOnlyChangeDoesNoWork", DigTerrainTestFlags)
bool FReflectionsDigTerrainBorderOnlyChangeDoesNoWorkTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    FTerrainScene Scene;
    if (!MakeTerrainScene(*this, TestWorld, Scene))
    {
        return true;
    }
    // A dig deep in the buried chunk (1, 1, 0), 200 cm under its top face: its hole (Z -1500..-1300) stays inside
    // that chunk, but the cells it softens reach within two cells of the face, so the chunk above, (1, 1, 1), is
    // dirtied and re-meshed. Its ground is 1200 cm higher, so its mesh comes out the same.
    const FIntVector Buried(1, 1, 0);
    const FIntVector Above(1, 1, 1);
    const TStaticArray<UDynamicMeshComponent*, ReflectionsDig::BlocksPerChunk> Before = GetSlots(*Scene.Terrain, Above);
    TArray<const UBodySetup*> BodiesBefore;
    int32 Filled = 0;
    for (const UDynamicMeshComponent* Piece : Before)
    {
        Filled += Piece != nullptr ? 1 : 0;
        BodiesBefore.Add(Piece != nullptr ? Piece->GetBodySetup() : nullptr);
    }
    TestEqual(TEXT("Premise: the chunk above fills its four upper blocks"), Filled, 4);
    TestEqual(TEXT("Premise: the buried chunk has no pieces"), Scene.Terrain->GetChunkPieceCount(Buried), 0);
    const int32 CooksBefore = Scene.Terrain->GetCookCompletionCount();
    const int32 KeptBefore = Scene.Terrain->GetPiecesKeptCount();
    const int32 ChangedBefore = Scene.Terrain->GetPiecesChangedCount();

    TestTrue(TEXT("The dig changes the grid"), Scene.Dig->Dig(FVector(2025.0, 2025.0, -1400.0), 100.0f, EReflectionsDigMode::Remove));
    int32 Commits = 0;
    UReflectionsDigSubsystem* Dig = Scene.Dig;
    const bool bIdle = TestWorld.TickUntil([Dig, &Commits]()
    {
        Commits += Dig->GetCommitsLastTick();
        return Dig->IsIdle();
    }, IdleTimeoutSeconds);
    if (!TestTrue(TEXT("Idle after the dig"), bIdle))
    {
        return true;
    }
    TestEqual(TEXT("Premise: both chunks were meshed and committed"), Commits, 2);
    TestEqual(TEXT("The buried chunk gained one piece"), Scene.Terrain->GetChunkPieceCount(Buried), 1);
    TestEqual(TEXT("Only the buried chunk's new piece was given a mesh"), Scene.Terrain->GetPiecesChangedCount() - ChangedBefore, 1);
    TestEqual(TEXT("The chunk above kept its four pieces"), Scene.Terrain->GetPiecesKeptCount() - KeptBefore, Filled);
    for (int32 Block = 0; Block < ReflectionsDig::BlocksPerChunk; ++Block)
    {
        UDynamicMeshComponent* Piece = Scene.Terrain->GetChunkBlockPiece(Above, Block);
        TestTrue(FString::Printf(TEXT("Above, block %d holds the same component"), Block), Piece == Before[Block]);
        TestTrue(FString::Printf(TEXT("Above, block %d keeps the same body"), Block), (Piece != nullptr ? Piece->GetBodySetup() : nullptr) == BodiesBefore[Block]);
    }
    TestEqual(TEXT("Only the buried chunk's new piece cooked collision"), Scene.Terrain->GetCookCompletionCount() - CooksBefore, 1);
    TestFalse(TEXT("The chunk above is not cooking"), Scene.Terrain->IsChunkCooking(Above));
    TestTrue(TEXT("The terrain is idle"), Scene.Dig->IsIdle());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainNewBlockCollidesBeforeItsNeighbourOpensTest, "Reflections.Digging.Terrain.NewBlockCollidesBeforeItsNeighbourOpens", DigTerrainTestFlags)
bool FReflectionsDigTerrainNewBlockCollidesBeforeItsNeighbourOpensTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    FTerrainScene Scene;
    if (!MakeTerrainScene(*this, TestWorld, Scene))
    {
        return true;
    }
    // A shaft in the middle of block column (low X, low Y) of chunk (1, 1, 1), from the ground down to a floor at
    // about Z -700: the floor lies in block 0 (Z -1200..-400), which had no piece; the ground was block 4's.
    const FIntVector Chunk(1, 1, 1);
    constexpr double X = 2025.0;
    constexpr double Y = 2025.0;
    constexpr int32 FloorBlock = 0;
    constexpr int32 GroundBlock = 4;
    TestNull(TEXT("Premise: block 0 has no piece"), Scene.Terrain->GetChunkBlockPiece(Chunk, FloorBlock));
    UDynamicMeshComponent* OldGround = Scene.Terrain->GetChunkBlockPiece(Chunk, GroundBlock);
    if (!TestNotNull(TEXT("Premise: block 4 has the ground's piece"), OldGround))
    {
        return true;
    }
    for (double Z = 0.0; Z >= -600.0; Z -= 50.0)
    {
        StampGrid(*Scene.Terrain, FVector(X, Y, Z), EReflectionsDigMode::Remove);
    }
    CommitFromGrid(*Scene.Terrain, Chunk);
    const UReflectionsDigChunkComponent* NewFloor = Cast<UReflectionsDigChunkComponent>(Scene.Terrain->GetChunkBlockPiece(Chunk, FloorBlock));
    if (!TestNotNull(TEXT("The commit gives block 0 a piece"), NewFloor) || !TestFalse(TEXT("Premise: it has no collision yet"), NewFloor->HasCollision()))
    {
        return true;
    }
    TestTrue(TEXT("Block 4 shows a new piece"), Scene.Terrain->GetChunkBlockPiece(Chunk, GroundBlock) != OldGround);
    TestFalse(TEXT("Block 4's old piece is hidden"), OldGround->IsVisible());

    // Until block 0's piece has collision, a trace down the shaft must still meet the old ground (block 4's old
    // piece, hidden but colliding); the world ticks, so the swap check runs in between.
    int32 Checks = 0;
    int32 Misses = 0;
    FString LastMiss;
    const double Deadline = FPlatformTime::Seconds() + IdleTimeoutSeconds;
    while (!NewFloor->HasCollision() && FPlatformTime::Seconds() < Deadline)
    {
        const TOptional<FHitResult> Hit = TraceDown(TestWorld.World, X, Y);
        ++Checks;
        if (!Hit.IsSet() || Hit->GetComponent() != OldGround || FMath::Abs(Hit->ImpactPoint.Z) > 5.0)
        {
            ++Misses;
            LastMiss = Hit.IsSet() ? FString::Printf(TEXT("%s at %.2f"), *GetNameSafe(Hit->GetComponent()), Hit->ImpactPoint.Z) : TEXT("nothing");
        }
        TickWithoutPumping(TestWorld);
        PumpGameThread();
    }
    TestTrue(FString::Printf(TEXT("Block 0's piece got collision (%d checks before)"), Checks), NewFloor->HasCollision());
    TestTrue(TEXT("Premise: at least one trace ran before block 0 had collision"), Checks > 0);
    TestEqual(FString::Printf(TEXT("Traces that did not meet the old ground before block 0 had collision (last: %s)"), *LastMiss), Misses, 0);

    if (WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the commit")))
    {
        const TOptional<double> Floor = TraceDownZ(TestWorld.World, X, Y);
        TestTrue(FString::Printf(TEXT("After idle the trace meets the shaft floor below Z -600 (at %s)"),
            Floor.IsSet() ? *FString::SanitizeFloat(*Floor) : TEXT("no terrain hit")), Floor.IsSet() && *Floor < -600.0);
        TestEqual(TEXT("No retiring piece is left"), Scene.Terrain->GetRetiringPieceCount(Chunk), 0);
    }
    return true;
}

#endif
