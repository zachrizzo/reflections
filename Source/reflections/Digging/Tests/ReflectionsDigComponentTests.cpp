#include "Digging/ReflectionsDigComponent.h"

#include "CoreMinimal.h"
#include "Digging/ReflectionsDigSpot.h"
#include "Digging/ReflectionsDigSubsystem.h"
#include "Digging/ReflectionsDigTerrain.h"
#include "Digging/Tests/ReflectionsDigTestTraces.h"
#include "Digging/Tests/ReflectionsDigTestWorld.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "GameFramework/DefaultPawn.h"
#include "Kismet/GameplayStatics.h"
#include "Math/RandomStream.h"
#include "Misc/AutomationTest.h"
#include "Save/ReflectionsSaveGame.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
    const FString TestSlot = TEXT("ReflectionsTest");
    const FName TestSpotId(TEXT("DigInputTestSpot"));
    constexpr EAutomationTestFlags DigInputTestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter;

    void DeleteTestSlot()
    {
        if (UGameplayStatics::DoesSaveGameExist(TestSlot, 0))
        {
            UGameplayStatics::DeleteGameInSlot(TestSlot, 0);
        }
    }

    TArray<uint8> LoadRaw()
    {
        TArray<uint8> Bytes;
        UGameplayStatics::LoadDataFromSlot(Bytes, TestSlot, 0);
        return Bytes;
    }

    TArray<uint8> RandomBytes()
    {
        FRandomStream Stream(1234);
        TArray<uint8> Bytes;
        Bytes.SetNumUninitialized(256);
        for (uint8& Byte : Bytes)
        {
            Byte = static_cast<uint8>(Stream.RandRange(0, 255));
        }
        return Bytes;
    }

    TArray<UStaticMesh*> LoadStageMeshes()
    {
        return {
            LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")),
            LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cone.Cone")),
            LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cylinder.Cylinder")),
        };
    }

    /** A dig spot at the origin (its stage-0 mesh is the 100 cm cube) and a pawn carrying the dig component. */
    struct FDigScene
    {
        AReflectionsDigSpot* Spot = nullptr;
        ADefaultPawn* Pawn = nullptr;
        UReflectionsDigComponent* Dig = nullptr;
    };

    /** Builds the scene; returns false (after reporting why) if any part is missing. */
    bool MakeScene(FAutomationTestBase& Test, FReflectionsDigTestWorld& TestWorld, const FVector& PawnLocation,
        const FRotator& PawnRotation, FName SpotId, FDigScene& Out, float EyeHeight = 0.0f)
    {
        if (!Test.TestNotNull(TEXT("Test world"), TestWorld.World))
        {
            return false;
        }
        const TArray<UStaticMesh*> Meshes = LoadStageMeshes();
        if (!Test.TestFalse(TEXT("A stage mesh failed to load"), Meshes.Contains(nullptr)))
        {
            return false;
        }
        Out.Spot = TestWorld.SpawnDeferred<AReflectionsDigSpot>();
        if (!Test.TestNotNull(TEXT("Spot"), Out.Spot))
        {
            return false;
        }
        Out.Spot->StageMeshes.Append(Meshes);
        Out.Spot->SpotId = SpotId;
        TestWorld.FinishSpawning(Out.Spot);

        // ADefaultPawn rather than APawn: it has a root component, so it can be placed. Eye height 0 (the default
        // here) puts the view point at the actor location, so the trace runs level at the cube.
        Out.Pawn = TestWorld.Spawn<ADefaultPawn>(PawnLocation, PawnRotation);
        if (!Test.TestNotNull(TEXT("Pawn"), Out.Pawn))
        {
            return false;
        }
        Out.Pawn->BaseEyeHeight = EyeHeight;
        Out.Dig = UReflectionsDigComponent::EnsureOnPawn(Out.Pawn);
        if (!Test.TestNotNull(TEXT("Dig component"), Out.Dig))
        {
            return false;
        }
        TestWorld.Tick();
        return true;
    }

    /** Where the terrain tests' pawn hovers: 150 cm above the ground (Z 0) of a terrain at the origin. */
    const FVector TerrainPawnLocation(2400.0, 2400.0, 150.0);
    constexpr double TerrainIdleTimeoutSeconds = 10.0;

    /** A terrain at the origin (ground at Z 0, default size, no focus so every chunk is meshed) and a pawn looking straight down at it. */
    struct FTerrainDigScene
    {
        UReflectionsDigSubsystem* Subsystem = nullptr;
        ADefaultPawn* Pawn = nullptr;
        UReflectionsDigComponent* Dig = nullptr;
    };

    bool WaitForTerrainIdle(FAutomationTestBase& Test, FReflectionsDigTestWorld& TestWorld, const FTerrainDigScene& Scene, const FString& Label)
    {
        UReflectionsDigSubsystem* Subsystem = Scene.Subsystem;
        return Test.TestTrue(Label, TestWorld.TickUntil([Subsystem]() { return Subsystem->IsIdle(); }, TerrainIdleTimeoutSeconds));
    }

    /** Builds the scene and waits until the terrain is meshed; returns false (after reporting why) if any part is missing. */
    bool MakeTerrainScene(FAutomationTestBase& Test, FReflectionsDigTestWorld& TestWorld, FTerrainDigScene& Out)
    {
        if (!Test.TestNotNull(TEXT("Test world"), TestWorld.World))
        {
            return false;
        }
        Out.Subsystem = TestWorld.World->GetSubsystem<UReflectionsDigSubsystem>();
        if (!Test.TestNotNull(TEXT("Dig subsystem"), Out.Subsystem)
            || !Test.TestNotNull(TEXT("Terrain"), TestWorld.Spawn<AReflectionsDigTerrain>(FVector::ZeroVector)))
        {
            return false;
        }
        // Eye height 0: the view point is the actor location, and pitch -90 looks straight down.
        Out.Pawn = TestWorld.Spawn<ADefaultPawn>(TerrainPawnLocation, FRotator(-90.0, 0.0, 0.0));
        if (!Test.TestNotNull(TEXT("Pawn"), Out.Pawn))
        {
            return false;
        }
        Out.Pawn->BaseEyeHeight = 0.0f;
        Out.Dig = UReflectionsDigComponent::EnsureOnPawn(Out.Pawn);
        if (!Test.TestNotNull(TEXT("Dig component"), Out.Dig))
        {
            return false;
        }
        return WaitForTerrainIdle(Test, TestWorld, Out, TEXT("Idle after the terrain begins play"));
    }

    /** Z of the ground under the pawn, from a downward trace that counts only a chunk piece of the terrain. */
    TOptional<double> TraceGroundUnderPawn(const FReflectionsDigTestWorld& TestWorld, const FTerrainDigScene& Scene)
    {
        return FReflectionsDigTestTraces::TraceDownToChunkZ(TestWorld.World, TerrainPawnLocation.X, TerrainPawnLocation.Y,
            1000.0, -3100.0, Scene.Pawn);
    }
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigInputDigsSpotInReachTest, "Reflections.DigInput.DigsSpotInReach", DigInputTestFlags)
bool FReflectionsDigInputDigsSpotInReachTest::RunTest(const FString& Parameters)
{
    ReflectionsSave::FScopedSlotOverride Override(TestSlot);
    DeleteTestSlot();
    {
        FReflectionsDigTestWorld TestWorld;
        FDigScene Scene;
        if (MakeScene(*this, TestWorld, FVector(-150.0, 0.0, 0.0), FRotator::ZeroRotator, TestSpotId, Scene))
        {
            TestTrue(TEXT("TryDig succeeds"), Scene.Dig->TryDig());
            TestEqual(TEXT("Spot stage"), Scene.Spot->GetStage(), 1);

            UReflectionsSaveGame* Loaded = nullptr;
            TestEqual(TEXT("Read result"), ReflectionsSave::Read(TestSlot, Loaded), EReflectionsLoadResult::Loaded);
            if (TestNotNull(TEXT("Loaded data"), Loaded))
            {
                const uint8* Stage = Loaded->DigSpotStages.Find(TestSpotId);
                if (TestNotNull(TEXT("Saved entry for the spot"), Stage))
                {
                    TestEqual(TEXT("Saved stage"), static_cast<int32>(*Stage), 1);
                }
            }
        }
    }
    DeleteTestSlot();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigInputIgnoresSpotOutOfReachTest, "Reflections.DigInput.IgnoresSpotOutOfReach", DigInputTestFlags)
bool FReflectionsDigInputIgnoresSpotOutOfReachTest::RunTest(const FString& Parameters)
{
    ReflectionsSave::FScopedSlotOverride Override(TestSlot);
    DeleteTestSlot();
    {
        FReflectionsDigTestWorld TestWorld;
        FDigScene Scene;
        if (MakeScene(*this, TestWorld, FVector(-400.0, 0.0, 0.0), FRotator::ZeroRotator, TestSpotId, Scene))
        {
            TestFalse(TEXT("TryDig fails"), Scene.Dig->TryDig());
            TestEqual(TEXT("Spot stage"), Scene.Spot->GetStage(), 0);
            TestFalse(TEXT("No save file"), UGameplayStatics::DoesSaveGameExist(TestSlot, 0));
        }
    }
    DeleteTestSlot();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigInputNothingHitReturnsFalseTest, "Reflections.DigInput.NothingHitReturnsFalse", DigInputTestFlags)
bool FReflectionsDigInputNothingHitReturnsFalseTest::RunTest(const FString& Parameters)
{
    ReflectionsSave::FScopedSlotOverride Override(TestSlot);
    DeleteTestSlot();
    {
        FReflectionsDigTestWorld TestWorld;
        FDigScene Scene;
        if (MakeScene(*this, TestWorld, FVector(-150.0, 0.0, 0.0), FRotator(0.0, 180.0, 0.0), TestSpotId, Scene))
        {
            TestFalse(TEXT("TryDig facing away fails"), Scene.Dig->TryDig());
            TestEqual(TEXT("Spot stage"), Scene.Spot->GetStage(), 0);
        }
    }
    DeleteTestSlot();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigInputSpotWithoutIdDigsButIsNotSavedTest, "Reflections.DigInput.SpotWithoutIdDigsButIsNotSaved", DigInputTestFlags)
bool FReflectionsDigInputSpotWithoutIdDigsButIsNotSavedTest::RunTest(const FString& Parameters)
{
    ReflectionsSave::FScopedSlotOverride Override(TestSlot);
    DeleteTestSlot();
    {
        FReflectionsDigTestWorld TestWorld;
        FDigScene Scene;
        if (MakeScene(*this, TestWorld, FVector(-150.0, 0.0, 0.0), FRotator::ZeroRotator, NAME_None, Scene))
        {
            TestTrue(TEXT("TryDig succeeds"), Scene.Dig->TryDig());
            TestEqual(TEXT("Spot stage"), Scene.Spot->GetStage(), 1);
            TestFalse(TEXT("No save file"), UGameplayStatics::DoesSaveGameExist(TestSlot, 0));
        }
    }
    DeleteTestSlot();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigInputEnsureOnPawnAddsExactlyOneTest, "Reflections.DigInput.EnsureOnPawnAddsExactlyOne", DigInputTestFlags)
bool FReflectionsDigInputEnsureOnPawnAddsExactlyOneTest::RunTest(const FString& Parameters)
{
    ReflectionsSave::FScopedSlotOverride Override(TestSlot);
    DeleteTestSlot();
    {
        FReflectionsDigTestWorld TestWorld;
        if (TestNotNull(TEXT("Test world"), TestWorld.World))
        {
            ADefaultPawn* Pawn = TestWorld.Spawn<ADefaultPawn>(FVector(-150.0, 0.0, 0.0));
            if (TestNotNull(TEXT("Pawn"), Pawn))
            {
                UReflectionsDigComponent* First = UReflectionsDigComponent::EnsureOnPawn(Pawn);
                UReflectionsDigComponent* Second = UReflectionsDigComponent::EnsureOnPawn(Pawn);
                TestNotNull(TEXT("First call returns a component"), First);
                TestTrue(TEXT("Second call returns the same component"), First == Second);

                TArray<UReflectionsDigComponent*> Found;
                Pawn->GetComponents(Found);
                TestEqual(TEXT("Pawn has one dig component"), Found.Num(), 1);
                if (First != nullptr)
                {
                    TestTrue(TEXT("Component is registered"), First->IsRegistered());
                }
            }
            TestNull(TEXT("Null pawn gives null"), UReflectionsDigComponent::EnsureOnPawn(nullptr));
        }
    }
    DeleteTestSlot();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigInputBadSaveDoesNotBlockDiggingTest, "Reflections.DigInput.BadSaveDoesNotBlockDigging", DigInputTestFlags)
bool FReflectionsDigInputBadSaveDoesNotBlockDiggingTest::RunTest(const FString& Parameters)
{
    // The refused save update logs exactly one LogReflectionsSave warning.
    AddExpectedError(TEXT("not updating it"), EAutomationExpectedErrorFlags::Contains, 1);

    ReflectionsSave::FScopedSlotOverride Override(TestSlot);
    DeleteTestSlot();
    {
        const TArray<uint8> Bad = RandomBytes();
        TestTrue(TEXT("Store random bytes"), UGameplayStatics::SaveDataToSlot(Bad, TestSlot, 0));

        FReflectionsDigTestWorld TestWorld;
        FDigScene Scene;
        if (MakeScene(*this, TestWorld, FVector(-150.0, 0.0, 0.0), FRotator::ZeroRotator, TestSpotId, Scene))
        {
            TestTrue(TEXT("TryDig succeeds"), Scene.Dig->TryDig());
            TestEqual(TEXT("Spot stage"), Scene.Spot->GetStage(), 1);
        }
        TestTrue(TEXT("Bytes unchanged"), LoadRaw() == Bad);
    }
    DeleteTestSlot();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigInputReachIsMeasuredFromThePawnTest, "Reflections.DigInput.ReachIsMeasuredFromThePawn", DigInputTestFlags)
bool FReflectionsDigInputReachIsMeasuredFromThePawnTest::RunTest(const FString& Parameters)
{
    ReflectionsSave::FScopedSlotOverride Override(TestSlot);
    DeleteTestSlot();
    {
        // The eye is level with the cube in both cases; only the pawn's distance from the hit differs.
        FReflectionsDigTestWorld TestWorld;
        FDigScene Scene;
        if (MakeScene(*this, TestWorld, FVector(-150.0, 0.0, -300.0), FRotator::ZeroRotator, TestSpotId, Scene, 300.0f))
        {
            TestFalse(TEXT("Cube face about 316 cm from the pawn is out of reach"), Scene.Dig->TryDig());
            TestEqual(TEXT("Spot stage after the far dig"), Scene.Spot->GetStage(), 0);
        }
    }
    DeleteTestSlot();
    {
        FReflectionsDigTestWorld TestWorld;
        FDigScene Scene;
        if (MakeScene(*this, TestWorld, FVector(-150.0, 0.0, -100.0), FRotator::ZeroRotator, TestSpotId, Scene, 100.0f))
        {
            TestTrue(TEXT("Cube face about 141 cm from the pawn is in reach"), Scene.Dig->TryDig());
            TestEqual(TEXT("Spot stage after the near dig"), Scene.Spot->GetStage(), 1);
        }
    }
    DeleteTestSlot();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigInputTraceStartsLevelWithThePawnTest, "Reflections.DigInput.TraceStartsLevelWithThePawn", DigInputTestFlags)
bool FReflectionsDigInputTraceStartsLevelWithThePawnTest::RunTest(const FString& Parameters)
{
    ReflectionsSave::FScopedSlotOverride Override(TestSlot);
    DeleteTestSlot();
    {
        FReflectionsDigTestWorld TestWorld;
        TestNotNull(TEXT("Test world"), TestWorld.World);

        FVector Start;
        FVector End;
        UReflectionsDigComponent::ComputeReachTrace(FVector(-565.0, 0.0, 100.0), FVector::ForwardVector,
            FVector(-150.0, 0.0, 0.0), 250.0f, Start, End);
        TestEqual(TEXT("Camera behind: start is level with the pawn"), Start, FVector(-150.0, 0.0, 100.0));
        TestEqual(TEXT("Camera behind: end is reach past the start"), End, FVector(100.0, 0.0, 100.0));

        UReflectionsDigComponent::ComputeReachTrace(FVector(50.0, 0.0, 0.0), FVector::ForwardVector,
            FVector(-150.0, 0.0, 0.0), 250.0f, Start, End);
        TestEqual(TEXT("View ahead of the pawn: start is the view location"), Start, FVector(50.0, 0.0, 0.0));
        TestEqual(TEXT("View ahead of the pawn: end is reach past the start"), End, FVector(300.0, 0.0, 0.0));
    }
    DeleteTestSlot();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigInputIgnoresActorsAttachedToThePawnTest, "Reflections.DigInput.IgnoresActorsAttachedToThePawn", DigInputTestFlags)
bool FReflectionsDigInputIgnoresActorsAttachedToThePawnTest::RunTest(const FString& Parameters)
{
    ReflectionsSave::FScopedSlotOverride Override(TestSlot);
    DeleteTestSlot();
    {
        FReflectionsDigTestWorld TestWorld;
        FDigScene Scene;
        if (MakeScene(*this, TestWorld, FVector(-150.0, 0.0, 0.0), FRotator::ZeroRotator, TestSpotId, Scene))
        {
            // A 20 cm blocking cube carried 60 cm in front of the pawn: it spans x -100..-80, across the dig ray.
            AStaticMeshActor* Carried = TestWorld.SpawnDeferred<AStaticMeshActor>(FVector(-90.0, 0.0, 0.0));
            if (TestNotNull(TEXT("Carried cube"), Carried))
            {
                UStaticMeshComponent* Mesh = Carried->GetStaticMeshComponent();
                Mesh->SetMobility(EComponentMobility::Movable);
                Mesh->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")));
                Mesh->SetCollisionProfileName(TEXT("BlockAll"));
                Carried->SetActorScale3D(FVector(0.2));
                TestWorld.FinishSpawning(Carried);
                Carried->AttachToActor(Scene.Pawn, FAttachmentTransformRules::KeepWorldTransform);
                TestTrue(TEXT("Cube is attached to the pawn"), Carried->GetAttachParentActor() == Scene.Pawn);
                TestWorld.Tick();

                // Without the attached-actor ignore the dig ray would stop on the cube.
                FHitResult Blocker;
                const FCollisionQueryParams PawnOnly(SCENE_QUERY_STAT(DigInputTest), false, Scene.Pawn);
                TestWorld.World->LineTraceSingleByChannel(Blocker, FVector(-150.0, 0.0, 0.0), FVector(100.0, 0.0, 0.0),
                    ECC_Visibility, PawnOnly);
                TestTrue(TEXT("The cube blocks a ray that ignores only the pawn"), Blocker.GetActor() == Carried);

                TestTrue(TEXT("TryDig reaches past the carried cube"), Scene.Dig->TryDig());
                TestEqual(TEXT("Spot stage"), Scene.Spot->GetStage(), 1);
            }
        }
    }
    DeleteTestSlot();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigInputDigsTerrainInReachTest, "Reflections.DigInput.DigsTerrainInReach", DigInputTestFlags)
bool FReflectionsDigInputDigsTerrainInReachTest::RunTest(const FString& Parameters)
{
    ReflectionsSave::FScopedSlotOverride Override(TestSlot);
    DeleteTestSlot();
    {
        FReflectionsDigTestWorld TestWorld;
        FTerrainDigScene Scene;
        if (MakeTerrainScene(*this, TestWorld, Scene))
        {
            const TOptional<double> Before = TraceGroundUnderPawn(TestWorld, Scene);
            if (TestTrue(TEXT("The trace hits the terrain before the dig"), Before.IsSet()))
            {
                TestTrue(TEXT("TryDig succeeds"), Scene.Dig->TryDig());
                WaitForTerrainIdle(*this, TestWorld, Scene, TEXT("Idle after the dig"));
                const TOptional<double> After = TraceGroundUnderPawn(TestWorld, Scene);
                if (TestTrue(TEXT("The trace hits the terrain after the dig"), After.IsSet()))
                {
                    TestTrue(FString::Printf(TEXT("The ground is at least 50 cm lower (%.1f before, %.1f after)"), *Before, *After),
                        *After < *Before - 50.0);
                }
            }
        }
    }
    DeleteTestSlot();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigInputFillRestoresTerrainTest, "Reflections.DigInput.FillRestoresTerrain", DigInputTestFlags)
bool FReflectionsDigInputFillRestoresTerrainTest::RunTest(const FString& Parameters)
{
    ReflectionsSave::FScopedSlotOverride Override(TestSlot);
    DeleteTestSlot();
    {
        FReflectionsDigTestWorld TestWorld;
        FTerrainDigScene Scene;
        if (MakeTerrainScene(*this, TestWorld, Scene))
        {
            // The pawn keeps 150 cm above the ground under it, as a player standing in the pit would: a pit floor
            // more than 100 cm down would otherwise be out of reach of a pawn hovering over the original ground.
            auto StandOnGround = [&TestWorld, &Scene](const TOptional<double>& Ground)
            {
                if (Ground.IsSet())
                {
                    Scene.Pawn->SetActorLocation(FVector(TerrainPawnLocation.X, TerrainPawnLocation.Y, *Ground + 150.0));
                }
            };
            TOptional<double> Ground = TraceGroundUnderPawn(TestWorld, Scene);
            for (int32 Dig = 0; Dig < 3; ++Dig)
            {
                StandOnGround(Ground);
                TestTrue(FString::Printf(TEXT("TryDig %d succeeds"), Dig + 1), Scene.Dig->TryDig());
                WaitForTerrainIdle(*this, TestWorld, Scene, TEXT("Idle after a dig"));
                Ground = TraceGroundUnderPawn(TestWorld, Scene);
            }
            if (TestTrue(TEXT("The trace hits the terrain after the digs"), Ground.IsSet()))
            {
                TestTrue(FString::Printf(TEXT("The digs leave a pit at least 250 cm deep (ground at %.1f)"), *Ground), *Ground < -250.0);
            }

            int32 Fills = 0;
            int32 SuccessfulFills = 0;
            while (Fills < 10 && !(Ground.IsSet() && FMath::Abs(*Ground) <= 60.0))
            {
                StandOnGround(Ground);
                SuccessfulFills += Scene.Dig->TryFill() ? 1 : 0;
                ++Fills;
                WaitForTerrainIdle(*this, TestWorld, Scene, TEXT("Idle after a fill"));
                Ground = TraceGroundUnderPawn(TestWorld, Scene);
            }
            TestTrue(FString::Printf(TEXT("TryFill succeeds (%d of %d calls)"), SuccessfulFills, Fills), SuccessfulFills > 0);
            TestTrue(FString::Printf(TEXT("After %d fills the ground is within 60 cm of Z 0 (at %s)"), Fills,
                Ground.IsSet() ? *FString::SanitizeFloat(*Ground) : TEXT("no terrain hit")),
                Ground.IsSet() && FMath::Abs(*Ground) <= 60.0);
        }
    }
    DeleteTestSlot();
    return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
