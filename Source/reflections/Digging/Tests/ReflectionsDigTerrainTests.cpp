#include "Digging/ReflectionsDigTerrain.h"

#include "CoreMinimal.h"
#include "Async/TaskGraphInterfaces.h"
#include "Components/DynamicMeshComponent.h"
#include "Digging/ReflectionsDigGrid.h"
#include "Digging/ReflectionsDigMesher.h"
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

    /** Z of the first hit of a downward visibility trace at (X, Y) from StartZ to just under the grid floor. */
    TOptional<double> TraceDownZ(UWorld* World, double X, double Y, double StartZ = TraceStartZ)
    {
        FHitResult Hit;
        if (World->LineTraceSingleByChannel(Hit, FVector(X, Y, StartZ), FVector(X, Y, GridFloorZ - 10.0), ECC_Visibility))
        {
            return Hit.ImpactPoint.Z;
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

    /** Commits Mesh straight to the terrain and logs how long the game thread spent (headless, no renderer). */
    void TimeCommit(AReflectionsDigTerrain& Terrain, FIntVector Chunk, FReflectionsDigMeshData&& Mesh, const TCHAR* Label)
    {
        const int32 Vertices = Mesh.Positions.Num();
        const int32 Triangles = Mesh.Triangles.Num() / 3;
        const double Start = FPlatformTime::Seconds();
        Terrain.CommitChunk(Chunk, MoveTemp(Mesh));
        const double Milliseconds = (FPlatformTime::Seconds() - Start) * 1000.0;
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE headless CommitChunk %s: %d vertices, %d triangles, %d pieces, %.2f ms"),
            Label, Vertices, Triangles, Terrain.GetChunkPieceCount(Chunk), Milliseconds);
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

    // Informal headless timing of one flat-chunk commit (it reuses the chunk's component).
    FReflectionsDigMeshData Flat;
    ReflectionsDigMesher::BuildChunk(*Scene.Terrain->GetGrid(), FIntVector(1, 1, 1), Flat);
    TimeCommit(*Scene.Terrain, FIntVector(1, 1, 1), MoveTemp(Flat), TEXT("flat chunk"));
    WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the timed commit"));
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
    if (!TestNotNull(TEXT("reflections.Dig.MaxCommitsPerFrame exists"), Budget.Variable))
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
    // The corner shared by eight chunks, so every dig there dirties all eight.
    const FVector Point(1600.0, 1600.0, -1200.0);
    int32 MostTasks = 0;
    int32 MostQueued = 0;
    for (int32 Frame = 0; Frame < 120; ++Frame)
    {
        Scene.Dig->Dig(Point, 100.0f, EReflectionsDigMode::Remove);
        MostTasks = FMath::Max(MostTasks, Scene.Dig->GetTasksInFlight());
        MostQueued = FMath::Max(MostQueued, Scene.Dig->GetQueuedCommits());
        TestWorld.TickUntil([]() { return true; });
        MostTasks = FMath::Max(MostTasks, Scene.Dig->GetTasksInFlight());
        MostQueued = FMath::Max(MostQueued, Scene.Dig->GetQueuedCommits());
    }
    TestTrue(FString::Printf(TEXT("At most 8 tasks in flight (most: %d)"), MostTasks), MostTasks <= 8);
    TestTrue(FString::Printf(TEXT("At most 8 queued commits (most: %d)"), MostQueued), MostQueued <= 8);
    WaitForIdle(*this, TestWorld, Scene, TEXT("Idle within 5 seconds of the last dig"), 5.0);
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
    TimeCommit(*Scene.Terrain, Busy, MoveTemp(Premise), TEXT("busy chunk"));
    WaitForIdle(*this, TestWorld, Scene, TEXT("Idle after the timed commit"));
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

#endif
