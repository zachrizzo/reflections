#include "Digging/ReflectionsDigComponent.h"

#include "CoreMinimal.h"
#include "Digging/ReflectionsDigSpot.h"
#include "Digging/Tests/ReflectionsDigTestWorld.h"
#include "Engine/StaticMesh.h"
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
        const FRotator& PawnRotation, FName SpotId, FDigScene& Out)
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

        // ADefaultPawn rather than APawn: it has a root component, so it can be placed. Eye height 0 puts the
        // view point at the actor location, so the trace runs level at the cube.
        Out.Pawn = TestWorld.Spawn<ADefaultPawn>(PawnLocation, PawnRotation);
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
        TestWorld.Tick();
        return true;
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
    AddExpectedError(TEXT("LogReflectionsSave"), EAutomationExpectedErrorFlags::Contains, 1);

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

#endif // WITH_DEV_AUTOMATION_TESTS
