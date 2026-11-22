#include "Digging/ReflectionsDigTerrain.h"

#include "CoreMinimal.h"
#include "Async/TaskGraphInterfaces.h"
#include "Components/BoxComponent.h"
#include "Components/DynamicMeshComponent.h"
#include "Digging/ReflectionsDigGrid.h"
#include "Digging/ReflectionsDigMesher.h"
#include "Digging/ReflectionsDigPieces.h"
#include "Digging/ReflectionsDigSubsystem.h"
#include "Digging/ReflectionsDigTypes.h"
#include "Digging/Tests/ReflectionsDigTestWorld.h"
#include "DynamicMesh/DynamicMesh3.h"
#include "Engine/HitResult.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformProcess.h"
#include "HAL/PlatformTime.h"
#include "Misc/AutomationTest.h"
#include "PhysicsEngine/BodySetup.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
    constexpr EAutomationTestFlags DigTerrainTestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter;
    constexpr double IdleTimeoutSeconds = 10.0;
    /** Above the top of the grid (Z 350 for a terrain at Z 0 with the ground at 0). */
    constexpr double TraceStartZ = 1000.0;
    /** The grid origin's Z for a terrain with the ground at 0 and two chunks of height: 0 - 2 * 1600 + 400. */
    constexpr double GridFloorZ = -2800.0;
    /** A cavity of the riddled chunk (1, 1, 0): a lattice centre. */
    const FVector CavityCentre(2500.0, 2500.0, -1900.0);
    /**
     * Where the cavity test traces: 50 cm off the cavity's centre in X and Y, so the trace meets the cavity's own
     * floor (at about 70.7 cm below the centre) instead of the point where it touches the cavity under it.
     */
    const FVector CavityTraceStart = CavityCentre + FVector(50.0, 50.0, 0.0);
    constexpr double CavityFloorBelowCentreCm = 70.7;

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
        FHitResult Hit;
        if (World->LineTraceSingleByChannel(Hit, FVector(X, Y, StartZ), FVector(X, Y, TraceEndZ), ECC_Visibility))
        {
            return Hit;
        }
        return TOptional<FHitResult>();
    }

    /**
     * Z of the first hit of a downward visibility trace at (X, Y) from StartZ, only when that hit is a chunk
     * piece of the terrain. Nothing, or anything else (such as the safety floor under the grid), gives no value.
     */
    TOptional<double> TraceDownZ(UWorld* World, double X, double Y, double StartZ = TraceStartZ)
    {
        const TOptional<FHitResult> Hit = TraceDown(World, X, Y, StartZ);
        if (Hit.IsSet() && Cast<UReflectionsDigChunkComponent>(Hit->GetComponent()) != nullptr)
        {
            return Hit->ImpactPoint.Z;
        }
        return TOptional<double>();
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
            for (double Y = 1700.0; Y <= 3100.0; Y += 200.0)
            {
                for (double X = 1700.0; X <= 3100.0; X += 200.0)
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
        ReflectionsDigPieces::Build(Mesh, Result);
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
                    TopComponent->GetComponentLocation(), FVector(0.0, 0.0, GridFloorZ));
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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigTerrainDigChangesCollisionTest, "Reflections.Digging.Terrain.DigChangesCollision", DigTerrainTestFlags)
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
    TestTrue(TEXT("Dig returns true"), Scene.Dig->Dig(FVector(1600.0, 1600.0, -400.0), 100.0f, EReflectionsDigMode::Remove));
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
    const FVector Point(1600.0, 1600.0, -1200.0);
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
    TestTrue(TEXT("The riddled chunk is split"), Scene.Terrain->GetChunkPieceCount(Busy) >= 2);

    // The fill is a radius-100 Add centred on the cavity's lowest point, so it fills the cavity's lower half. The
    // trace runs 30 cm off the centre in X and Y: the fill's top is there about 9 cm under the cavity centre, the
    // old cavity floor about 91 cm under it.
    const FVector FillCentre = CavityCentre - FVector(0.0, 0.0, 100.0);
    const FVector TraceStart = CavityCentre + FVector(30.0, 30.0, 50.0);
    const double FillTopAboveZ = CavityCentre.Z - 45.0;
    const FVector Elsewhere(2100.0, 2100.0, -2300.0);
    UWorld* World = TestWorld.World;
    auto HitsFillTop = [World, TraceStart, FillTopAboveZ](double& OutZ)
    {
        const TOptional<double> Z = TraceDownZ(World, TraceStart.X, TraceStart.Y, TraceStart.Z);
        OutZ = Z.Get(TraceEndZ);
        return Z.IsSet() && *Z > FillTopAboveZ;
    };

    // Part 1, decided at commit time: commit the fill straight to the terrain, let its cook finish without ticking
    // the world (so no swap runs in between), then commit another change. The cooked fill set is the newest real
    // collision, so it must survive that commit; destroying it would bring the old cavity floor back.
    {
        TestTrue(TEXT("The fill changes the grid"), Scene.Dig->Dig(FillCentre, 100.0f, EReflectionsDigMode::Add));
        FReflectionsDigMeshData Filled;
        ReflectionsDigMesher::BuildChunk(*Scene.Terrain->GetGrid(), Busy, Filled);
        Scene.Terrain->CommitChunk(Busy, MoveTemp(Filled));
        double HitZ = 0.0;
        const double Deadline = FPlatformTime::Seconds() + 5.0;
        bool bFillCooked = HitsFillTop(HitZ);
        while (!bFillCooked && FPlatformTime::Seconds() < Deadline)
        {
            PumpGameThread();
            bFillCooked = HitsFillTop(HitZ);
        }
        if (TestTrue(FString::Printf(TEXT("The fill's collision cooks without a world tick (last hit %.2f)"), HitZ), bFillCooked))
        {
            TestTrue(TEXT("The second change changes the grid"), Scene.Dig->Dig(Elsewhere, 100.0f, EReflectionsDigMode::Add));
            FReflectionsDigMeshData Next;
            ReflectionsDigMesher::BuildChunk(*Scene.Terrain->GetGrid(), Busy, Next);
            Scene.Terrain->CommitChunk(Busy, MoveTemp(Next));
            const bool bStillFill = HitsFillTop(HitZ);
            TestTrue(FString::Printf(TEXT("Right after the next commit the trace still hits the fill (hit %.2f)"), HitZ), bStillFill);
        }
    }

    // Part 2, the held dig: after idle the trace hits the fill; then dig elsewhere in the chunk on each of 30 ticks.
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
        TestTrue(TEXT("Dig at the eight-chunk corner returns true"), Scene.Dig->Dig(FVector(1600.0, 1600.0, -1200.0), 100.0f, EReflectionsDigMode::Remove));
        TickWithoutPumping(TestWorld);
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
    TestTrue(FString::Printf(TEXT("The busy chunk has at least 2 pieces (%d)"), Pieces), Pieces >= 2);
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

    // One-piece chunk: dig and fill at one point on alternate ticks, so every tick changes the grid there.
    // Each tick is traced twice: straight after the world tick (a commit made in it is still cooking), and
    // after the game thread's queued tasks have run (cooks that finished have swapped their body in).
    {
        const FIntVector Chunk(1, 1, 1);
        const FVector Point(2400.0, 2400.0, 0.0);
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

    // Split chunk: each commit replaces the chunk's whole set of pieces. Dig and fill one cavity on alternate
    // ticks and trace another cavity's floor in the same chunk.
    {
        const FIntVector Busy(1, 1, 0);
        RiddleBuriedChunk(*Scene.Dig);
        if (!WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after riddling the chunk")))
        {
            return true;
        }
        TestTrue(TEXT("The riddled chunk is split"), Scene.Terrain->GetChunkPieceCount(Busy) >= 2);

        const FVector OtherCavity(2100.0, 2100.0, -2300.0);
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
            FirstPiecesSeen.Add(Scene.Terrain->FindChunkComponent(Busy));
        }
        TestEqual(TEXT("Split chunk: traces that missed the cavity floor"), Misses, 0);
        TestTrue(FString::Printf(TEXT("The chunk's pieces were replaced (%d first pieces seen)"), FirstPiecesSeen.Num()), FirstPiecesSeen.Num() >= 2);
        WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the split-chunk digs"));
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
    // It spans the whole patch: a trace at a corner of the patch hits it too.
    const TOptional<FHitResult> Corner = TraceDown(TestWorld.World, 25.0, 4775.0, -2000.0);
    TestTrue(TEXT("The safety floor covers the patch's corner"), Corner.IsSet() && Corner->GetComponent() == Scene.Terrain->GetSafetyFloor());
    return true;
}

#endif
