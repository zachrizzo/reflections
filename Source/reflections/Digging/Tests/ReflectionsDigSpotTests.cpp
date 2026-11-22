#include "Digging/ReflectionsDigSpot.h"

#include "CoreMinimal.h"
#include "Components/StaticMeshComponent.h"
#include "Digging/ReflectionsDigComponent.h"
#include "Digging/Tests/ReflectionsDigTestWorld.h"
#include "Engine/StaticMesh.h"
#include "Engine/TargetPoint.h"
#include "EngineUtils.h"
#include "GameFramework/DefaultPawn.h"
#include "Kismet/GameplayStatics.h"
#include "Math/RandomStream.h"
#include "Misc/AutomationTest.h"
#include "Misc/OutputDevice.h"
#include "Misc/OutputDeviceRedirector.h"
#include "Save/ReflectionsSaveGame.h"

#include <atomic>

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
    constexpr EAutomationTestFlags DigSpotTestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter;
    const FString TestSlot = TEXT("ReflectionsTest");
    const FName SpikeA(TEXT("SpikeA"));
    const FName SpikeB(TEXT("SpikeB"));

    void DeleteTestSlot()
    {
        if (UGameplayStatics::DoesSaveGameExist(TestSlot, 0))
        {
            UGameplayStatics::DeleteGameInSlot(TestSlot, 0);
        }
    }

    TArray<UStaticMesh*> LoadStageMeshes()
    {
        return {
            LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")),
            LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cone.Cone")),
            LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cylinder.Cylinder")),
        };
    }

    /** Spawns a spot holding the three stage meshes, with an optional buried find. */
    AReflectionsDigSpot* SpawnSpot(FReflectionsDigTestWorld& TestWorld, const TArray<UStaticMesh*>& Meshes,
        TSubclassOf<AActor> FindClass = nullptr)
    {
        AReflectionsDigSpot* Spot = TestWorld.SpawnDeferred<AReflectionsDigSpot>();
        if (Spot == nullptr)
        {
            return nullptr;
        }
        Spot->StageMeshes.Append(Meshes);
        Spot->BuriedFindClass = FindClass;
        return TestWorld.FinishSpawning(Spot);
    }

    /** Spawns a spot with an id and the three stage meshes at Location; it begins play (and restores) at once. */
    AReflectionsDigSpot* SpawnSpotWithId(FReflectionsDigTestWorld& TestWorld, const TArray<UStaticMesh*>& Meshes,
        FName SpotId, const FVector& Location = FVector::ZeroVector, TSubclassOf<AActor> FindClass = nullptr)
    {
        AReflectionsDigSpot* Spot = TestWorld.SpawnDeferred<AReflectionsDigSpot>(Location);
        if (Spot == nullptr)
        {
            return nullptr;
        }
        Spot->StageMeshes.Append(Meshes);
        Spot->SpotId = SpotId;
        Spot->BuriedFindClass = FindClass;
        return TestWorld.FinishSpawning(Spot);
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

    /** Writes the test slot with SpikeA at Stage and, if bCollected, SpikeA's find taken. */
    bool WriteSpikeA(uint8 Stage, bool bCollected)
    {
        UReflectionsSaveGame* Data = NewObject<UReflectionsSaveGame>();
        Data->DigSpotStages.Add(SpikeA, Stage);
        if (bCollected)
        {
            Data->DigSpotFindsCollected.Add(SpikeA);
        }
        return ReflectionsSave::Write(*Data, TestSlot);
    }

    /** Counts, while alive, every log line of a category whose name contains "Reflections". */
    struct FReflectionsLogCounter : public FOutputDevice
    {
        std::atomic<int32> Lines{ 0 };

        FReflectionsLogCounter()
        {
            GLog->AddOutputDevice(this);
        }

        virtual ~FReflectionsLogCounter() override
        {
            GLog->RemoveOutputDevice(this);
        }

        virtual void Serialize(const TCHAR* Message, ELogVerbosity::Type Verbosity, const FName& Category) override
        {
            if (Category.ToString().Contains(TEXT("Reflections")))
            {
                ++Lines;
            }
        }

        virtual bool CanBeUsedOnMultipleThreads() const override
        {
            return true;
        }
    };

    int32 CountTargetPoints(UWorld* World)
    {
        int32 Count = 0;
        for (TActorIterator<ATargetPoint> It(World); It; ++It)
        {
            ++Count;
        }
        return Count;
    }
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigSpotAdvancesOneStagePerDigTest, "Reflections.DigSpot.AdvancesOneStagePerDig", DigSpotTestFlags)
bool FReflectionsDigSpotAdvancesOneStagePerDigTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    if (!TestNotNull(TEXT("Test world"), TestWorld.World))
    {
        return false;
    }
    const TArray<UStaticMesh*> Meshes = LoadStageMeshes();
    if (!TestFalse(TEXT("A stage mesh failed to load"), Meshes.Contains(nullptr)))
    {
        return false;
    }
    AReflectionsDigSpot* Spot = SpawnSpot(TestWorld, Meshes);
    if (!TestNotNull(TEXT("Spot"), Spot))
    {
        return false;
    }

    // The test world must run BeginPlay on spawned actors and advance when ticked.
    TestTrue(TEXT("Spot has begun play"), Spot->HasActorBegunPlay());
    TestWorld.Tick(2);
    TestTrue(TEXT("Ticking advances world time"), TestWorld.World->GetTimeSeconds() > 0.0);

    TestEqual(TEXT("Starts at stage 0"), Spot->GetStage(), 0);
    TestTrue(TEXT("Starts showing mesh 0"), Spot->GetMeshComponent()->GetStaticMesh() == Meshes[0]);

    TestTrue(TEXT("First dig succeeds"), Spot->DigOnce());
    TestEqual(TEXT("Stage after first dig"), Spot->GetStage(), 1);
    TestTrue(TEXT("Mesh after first dig"), Spot->GetMeshComponent()->GetStaticMesh() == Meshes[1]);

    TestTrue(TEXT("Second dig succeeds"), Spot->DigOnce());
    TestEqual(TEXT("Stage after second dig"), Spot->GetStage(), 2);
    TestTrue(TEXT("Mesh after second dig"), Spot->GetMeshComponent()->GetStaticMesh() == Meshes[2]);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigSpotStopsAtLastStageTest, "Reflections.DigSpot.StopsAtLastStage", DigSpotTestFlags)
bool FReflectionsDigSpotStopsAtLastStageTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    if (!TestNotNull(TEXT("Test world"), TestWorld.World))
    {
        return false;
    }
    const TArray<UStaticMesh*> Meshes = LoadStageMeshes();
    if (!TestFalse(TEXT("A stage mesh failed to load"), Meshes.Contains(nullptr)))
    {
        return false;
    }
    AReflectionsDigSpot* Spot = SpawnSpot(TestWorld, Meshes);
    if (!TestNotNull(TEXT("Spot"), Spot))
    {
        return false;
    }

    Spot->DigOnce();
    Spot->DigOnce();
    TestFalse(TEXT("Third dig is refused"), Spot->DigOnce());
    TestEqual(TEXT("Stage stays at the last"), Spot->GetStage(), 2);
    TestTrue(TEXT("Mesh stays the last"), Spot->GetMeshComponent()->GetStaticMesh() == Meshes[2]);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigSpotSetStageClampsTest, "Reflections.DigSpot.SetStageClamps", DigSpotTestFlags)
bool FReflectionsDigSpotSetStageClampsTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    if (!TestNotNull(TEXT("Test world"), TestWorld.World))
    {
        return false;
    }
    const TArray<UStaticMesh*> Meshes = LoadStageMeshes();
    if (!TestFalse(TEXT("A stage mesh failed to load"), Meshes.Contains(nullptr)))
    {
        return false;
    }
    AReflectionsDigSpot* Spot = SpawnSpot(TestWorld, Meshes);
    if (!TestNotNull(TEXT("Spot"), Spot))
    {
        return false;
    }

    Spot->SetStage(9);
    TestEqual(TEXT("SetStage(9) clamps to the last stage"), Spot->GetStage(), 2);
    TestTrue(TEXT("SetStage(9) shows the last mesh"), Spot->GetMeshComponent()->GetStaticMesh() == Meshes[2]);

    Spot->SetStage(-1);
    TestEqual(TEXT("SetStage(-1) clamps to 0"), Spot->GetStage(), 0);
    TestTrue(TEXT("SetStage(-1) shows mesh 0"), Spot->GetMeshComponent()->GetStaticMesh() == Meshes[0]);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigSpotSpawnsBuriedFindOnceTest, "Reflections.DigSpot.SpawnsBuriedFindOnce", DigSpotTestFlags)
bool FReflectionsDigSpotSpawnsBuriedFindOnceTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    if (!TestNotNull(TEXT("Test world"), TestWorld.World))
    {
        return false;
    }
    const TArray<UStaticMesh*> Meshes = LoadStageMeshes();
    if (!TestFalse(TEXT("A stage mesh failed to load"), Meshes.Contains(nullptr)))
    {
        return false;
    }
    // A scaled patch away from the origin: the find must take the spot's location but not its scale.
    const FVector SpotLocation(300.0, -200.0, 50.0);
    AReflectionsDigSpot* Spot = TestWorld.SpawnDeferred<AReflectionsDigSpot>(SpotLocation);
    if (!TestNotNull(TEXT("Spot"), Spot))
    {
        return false;
    }
    Spot->StageMeshes.Append(Meshes);
    Spot->BuriedFindClass = ATargetPoint::StaticClass();
    TestWorld.FinishSpawning(Spot);
    Spot->SetActorScale3D(FVector(2.0, 2.0, 1.0));
    TestEqual(TEXT("Spot is scaled"), Spot->GetActorScale3D(), FVector(2.0, 2.0, 1.0));

    TestEqual(TEXT("No find before digging"), CountTargetPoints(TestWorld.World), 0);
    Spot->DigOnce();
    TestEqual(TEXT("No find after the first dig"), CountTargetPoints(TestWorld.World), 0);
    Spot->DigOnce();
    TestEqual(TEXT("One find after the second dig"), CountTargetPoints(TestWorld.World), 1);
    Spot->DigOnce();
    TestEqual(TEXT("Still one find after a third dig"), CountTargetPoints(TestWorld.World), 1);

    TActorIterator<ATargetPoint> Find(TestWorld.World);
    if (TestTrue(TEXT("The find exists"), static_cast<bool>(Find)))
    {
        TestEqual(TEXT("Find is at the spot's location"), Find->GetActorLocation(), Spot->GetActorLocation());
        TestEqual(TEXT("Find has unit scale"), Find->GetActorScale3D(), FVector::OneVector);
        TestTrue(TEXT("The find's owner is its spot"), Find->GetOwner() == Spot);
        TestTrue(TEXT("The find is in its spot's level"), Find->GetLevel() == Spot->GetLevel());
    }

    AReflectionsDigSpot* Restored = SpawnSpot(TestWorld, Meshes, ATargetPoint::StaticClass());
    if (!TestNotNull(TEXT("Second spot"), Restored))
    {
        return false;
    }
    Restored->SetStage(2);
    TestEqual(TEXT("Second spot is at the last stage"), Restored->GetStage(), 2);
    TestEqual(TEXT("SetStage spawns no find"), CountTargetPoints(TestWorld.World), 1);

    // Restored as fully dug, then set back: digging to the end again must not give the find.
    AReflectionsDigSpot* Rewound = SpawnSpot(TestWorld, Meshes, ATargetPoint::StaticClass());
    if (!TestNotNull(TEXT("Third spot"), Rewound))
    {
        return false;
    }
    Rewound->SetStage(2);
    Rewound->SetStage(1);
    TestTrue(TEXT("Third spot digs from stage 1"), Rewound->DigOnce());
    TestEqual(TEXT("Third spot is at the last stage"), Rewound->GetStage(), 2);
    TestEqual(TEXT("A spot restored as fully dug never gives its find"), CountTargetPoints(TestWorld.World), 1);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigSpotNoMeshesMeansNothingToDigTest, "Reflections.DigSpot.NoMeshesMeansNothingToDig", DigSpotTestFlags)
bool FReflectionsDigSpotNoMeshesMeansNothingToDigTest::RunTest(const FString& Parameters)
{
    FReflectionsDigTestWorld TestWorld;
    if (!TestNotNull(TEXT("Test world"), TestWorld.World))
    {
        return false;
    }
    AReflectionsDigSpot* Spot = SpawnSpot(TestWorld, {}, ATargetPoint::StaticClass());
    if (!TestNotNull(TEXT("Spot"), Spot))
    {
        return false;
    }

    TestFalse(TEXT("DigOnce with no meshes is refused"), Spot->DigOnce());
    TestEqual(TEXT("Stage stays 0"), Spot->GetStage(), 0);
    TestEqual(TEXT("No find spawned"), CountTargetPoints(TestWorld.World), 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigSpotRestoresStageFromSaveTest, "Reflections.DigSpot.RestoresStageFromSave", DigSpotTestFlags)
bool FReflectionsDigSpotRestoresStageFromSaveTest::RunTest(const FString& Parameters)
{
    ReflectionsSave::FScopedSlotOverride Override(TestSlot);
    DeleteTestSlot();
    {
        UReflectionsSaveGame* Data = NewObject<UReflectionsSaveGame>();
        Data->DigSpotStages.Add(SpikeA, 2);
        TestTrue(TEXT("Write the slot"), ReflectionsSave::Write(*Data, TestSlot));

        FReflectionsDigTestWorld TestWorld;
        const TArray<UStaticMesh*> Meshes = LoadStageMeshes();
        if (TestNotNull(TEXT("Test world"), TestWorld.World) && TestFalse(TEXT("A stage mesh failed to load"), Meshes.Contains(nullptr)))
        {
            AReflectionsDigSpot* A = SpawnSpotWithId(TestWorld, Meshes, SpikeA, FVector::ZeroVector, ATargetPoint::StaticClass());
            AReflectionsDigSpot* B = SpawnSpotWithId(TestWorld, Meshes, SpikeB, FVector(0.0, 300.0, 0.0));
            if (TestNotNull(TEXT("Spot A"), A) && TestNotNull(TEXT("Spot B"), B))
            {
                TestTrue(TEXT("A has begun play"), A->HasActorBegunPlay());
                TestEqual(TEXT("A is restored to stage 2"), A->GetStage(), 2);
                TestTrue(TEXT("A shows mesh 2"), A->GetMeshComponent()->GetStaticMesh() == Meshes[2]);
                TestEqual(TEXT("Restored at the last stage with its find not taken, A gives the find once"), CountTargetPoints(TestWorld.World), 1);
                TestEqual(TEXT("B has no entry and stays at stage 0"), B->GetStage(), 0);
                TestTrue(TEXT("B shows mesh 0"), B->GetMeshComponent()->GetStaticMesh() == Meshes[0]);
            }
        }
    }
    DeleteTestSlot();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigSpotDigTwiceThenReloadKeepsStageTest, "Reflections.DigSpot.DigTwiceThenReloadKeepsStage", DigSpotTestFlags)
bool FReflectionsDigSpotDigTwiceThenReloadKeepsStageTest::RunTest(const FString& Parameters)
{
    ReflectionsSave::FScopedSlotOverride Override(TestSlot);
    DeleteTestSlot();
    const TArray<UStaticMesh*> Meshes = LoadStageMeshes();
    if (!TestFalse(TEXT("A stage mesh failed to load"), Meshes.Contains(nullptr)))
    {
        return false;
    }
    {
        // World 1: a pawn 150 cm behind spot A, eye level with it, digs it twice.
        FReflectionsDigTestWorld TestWorld;
        if (TestNotNull(TEXT("World 1"), TestWorld.World))
        {
            AReflectionsDigSpot* A = SpawnSpotWithId(TestWorld, Meshes, SpikeA);
            ADefaultPawn* Pawn = TestWorld.Spawn<ADefaultPawn>(FVector(-150.0, 0.0, 0.0));
            if (TestNotNull(TEXT("World 1 spot A"), A) && TestNotNull(TEXT("Pawn"), Pawn))
            {
                Pawn->BaseEyeHeight = 0.0f;
                UReflectionsDigComponent* Dig = UReflectionsDigComponent::EnsureOnPawn(Pawn);
                if (TestNotNull(TEXT("Dig component"), Dig))
                {
                    TestWorld.Tick();
                    TestTrue(TEXT("First dig"), Dig->TryDig());
                    TestWorld.Tick();
                    TestTrue(TEXT("Second dig"), Dig->TryDig());
                    TestEqual(TEXT("World 1 spot A stage"), A->GetStage(), 2);
                }
            }
        }
    }
    {
        // World 2: fresh spots restore from the save.
        FReflectionsDigTestWorld TestWorld;
        if (TestNotNull(TEXT("World 2"), TestWorld.World))
        {
            AReflectionsDigSpot* A = SpawnSpotWithId(TestWorld, Meshes, SpikeA);
            AReflectionsDigSpot* B = SpawnSpotWithId(TestWorld, Meshes, SpikeB, FVector(0.0, 300.0, 0.0));
            if (TestNotNull(TEXT("World 2 spot A"), A) && TestNotNull(TEXT("World 2 spot B"), B))
            {
                TestEqual(TEXT("World 2 spot A begins at stage 2"), A->GetStage(), 2);
                TestEqual(TEXT("World 2 spot B begins at stage 0"), B->GetStage(), 0);
            }
        }
    }
    DeleteTestSlot();
    {
        // World 3: with no save both begin untouched.
        FReflectionsDigTestWorld TestWorld;
        if (TestNotNull(TEXT("World 3"), TestWorld.World))
        {
            AReflectionsDigSpot* A = SpawnSpotWithId(TestWorld, Meshes, SpikeA);
            AReflectionsDigSpot* B = SpawnSpotWithId(TestWorld, Meshes, SpikeB, FVector(0.0, 300.0, 0.0));
            if (TestNotNull(TEXT("World 3 spot A"), A) && TestNotNull(TEXT("World 3 spot B"), B))
            {
                TestEqual(TEXT("World 3 spot A begins at stage 0"), A->GetStage(), 0);
                TestEqual(TEXT("World 3 spot B begins at stage 0"), B->GetStage(), 0);
            }
        }
    }
    DeleteTestSlot();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigSpotRestoredLastStageGivesUntakenFindTest, "Reflections.DigSpot.RestoredLastStageGivesUntakenFind", DigSpotTestFlags)
bool FReflectionsDigSpotRestoredLastStageGivesUntakenFindTest::RunTest(const FString& Parameters)
{
    ReflectionsSave::FScopedSlotOverride Override(TestSlot);
    DeleteTestSlot();
    {
        TestTrue(TEXT("Write the slot"), WriteSpikeA(2, /*bCollected=*/ false));
        FReflectionsDigTestWorld TestWorld;
        const TArray<UStaticMesh*> Meshes = LoadStageMeshes();
        if (TestNotNull(TEXT("Test world"), TestWorld.World) && TestFalse(TEXT("A stage mesh failed to load"), Meshes.Contains(nullptr)))
        {
            const FVector Location(300.0, -200.0, 50.0);
            AReflectionsDigSpot* A = SpawnSpotWithId(TestWorld, Meshes, SpikeA, Location, ATargetPoint::StaticClass());
            if (TestNotNull(TEXT("Spot A"), A))
            {
                TestEqual(TEXT("A is restored to its last stage"), A->GetStage(), 2);
                TestEqual(TEXT("Exactly one find is uncovered"), CountTargetPoints(TestWorld.World), 1);
                TActorIterator<ATargetPoint> Find(TestWorld.World);
                if (TestTrue(TEXT("The find exists"), static_cast<bool>(Find)))
                {
                    TestEqual(TEXT("The find is at the spot's location"), Find->GetActorLocation(), Location);
                    TestEqual(TEXT("The find has unit scale"), Find->GetActorScale3D(), FVector::OneVector);
                    TestTrue(TEXT("The find's owner is its spot"), Find->GetOwner() == A);
                    TestTrue(TEXT("The find is in its spot's level"), Find->GetLevel() == A->GetLevel());
                }
                TestFalse(TEXT("A restored spot at its last stage digs no further"), A->DigOnce());
                A->SetStage(2);
                TestEqual(TEXT("Digging and SetStage after the restore give no second find"), CountTargetPoints(TestWorld.World), 1);
            }
        }
    }
    DeleteTestSlot();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigSpotRestoredTakenFindIsNotGivenAgainTest, "Reflections.DigSpot.RestoredTakenFindIsNotGivenAgain", DigSpotTestFlags)
bool FReflectionsDigSpotRestoredTakenFindIsNotGivenAgainTest::RunTest(const FString& Parameters)
{
    ReflectionsSave::FScopedSlotOverride Override(TestSlot);
    DeleteTestSlot();
    {
        TestTrue(TEXT("Write the slot"), WriteSpikeA(2, /*bCollected=*/ true));
        FReflectionsDigTestWorld TestWorld;
        const TArray<UStaticMesh*> Meshes = LoadStageMeshes();
        if (TestNotNull(TEXT("Test world"), TestWorld.World) && TestFalse(TEXT("A stage mesh failed to load"), Meshes.Contains(nullptr)))
        {
            AReflectionsDigSpot* A = SpawnSpotWithId(TestWorld, Meshes, SpikeA, FVector::ZeroVector, ATargetPoint::StaticClass());
            if (TestNotNull(TEXT("Spot A"), A))
            {
                TestEqual(TEXT("A is restored to its last stage"), A->GetStage(), 2);
                TestEqual(TEXT("A taken find is not uncovered again"), CountTargetPoints(TestWorld.World), 0);
            }
        }
    }
    DeleteTestSlot();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigSpotMarkFindCollectedSurvivesReloadTest, "Reflections.DigSpot.MarkFindCollectedSurvivesReload", DigSpotTestFlags)
bool FReflectionsDigSpotMarkFindCollectedSurvivesReloadTest::RunTest(const FString& Parameters)
{
    ReflectionsSave::FScopedSlotOverride Override(TestSlot);
    DeleteTestSlot();
    const TArray<UStaticMesh*> Meshes = LoadStageMeshes();
    if (!TestFalse(TEXT("A stage mesh failed to load"), Meshes.Contains(nullptr)))
    {
        return false;
    }
    TestTrue(TEXT("Write the slot"), WriteSpikeA(2, /*bCollected=*/ false));
    {
        // World 1: the find is uncovered and the player takes it.
        FReflectionsDigTestWorld TestWorld;
        if (TestNotNull(TEXT("World 1"), TestWorld.World))
        {
            AReflectionsDigSpot* A = SpawnSpotWithId(TestWorld, Meshes, SpikeA, FVector::ZeroVector, ATargetPoint::StaticClass());
            if (TestNotNull(TEXT("World 1 spot A"), A))
            {
                TestEqual(TEXT("World 1 uncovers the find"), CountTargetPoints(TestWorld.World), 1);
                A->MarkFindCollected();
            }
        }
    }
    UReflectionsSaveGame* Loaded = nullptr;
    TestEqual(TEXT("Read result"), ReflectionsSave::Read(TestSlot, Loaded), EReflectionsLoadResult::Loaded);
    if (TestNotNull(TEXT("Loaded data"), Loaded))
    {
        TestTrue(TEXT("The save records A's find as taken"), Loaded->DigSpotFindsCollected.Contains(SpikeA));
        const uint8* Stage = Loaded->DigSpotStages.Find(SpikeA);
        TestTrue(TEXT("The save keeps A's stage"), Stage != nullptr && *Stage == 2);
    }
    {
        // World 2: the restored spot gives nothing.
        FReflectionsDigTestWorld TestWorld;
        if (TestNotNull(TEXT("World 2"), TestWorld.World))
        {
            AReflectionsDigSpot* A = SpawnSpotWithId(TestWorld, Meshes, SpikeA, FVector::ZeroVector, ATargetPoint::StaticClass());
            if (TestNotNull(TEXT("World 2 spot A"), A))
            {
                TestEqual(TEXT("World 2 spot A begins at its last stage"), A->GetStage(), 2);
                TestEqual(TEXT("World 2 uncovers no find"), CountTargetPoints(TestWorld.World), 0);
            }
        }
    }
    DeleteTestSlot();
    {
        // A spot without an id records nothing.
        FReflectionsDigTestWorld TestWorld;
        if (TestNotNull(TEXT("World 3"), TestWorld.World))
        {
            AReflectionsDigSpot* NoId = SpawnSpot(TestWorld, Meshes, ATargetPoint::StaticClass());
            if (TestNotNull(TEXT("Spot without an id"), NoId))
            {
                NoId->MarkFindCollected();
                TestFalse(TEXT("MarkFindCollected on a spot without an id writes no save"), UGameplayStatics::DoesSaveGameExist(TestSlot, 0));
            }
        }
    }
    DeleteTestSlot();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigSpotBadSaveLeavesTheSpotUntouchedTest, "Reflections.DigSpot.BadSaveLeavesTheSpotUntouched", DigSpotTestFlags)
bool FReflectionsDigSpotBadSaveLeavesTheSpotUntouchedTest::RunTest(const FString& Parameters)
{
    ReflectionsSave::FScopedSlotOverride Override(TestSlot);
    DeleteTestSlot();
    const TArray<UStaticMesh*> Meshes = LoadStageMeshes();
    if (!TestFalse(TEXT("A stage mesh failed to load"), Meshes.Contains(nullptr)))
    {
        return false;
    }
    TArray<TArray<uint8>> BadFiles;
    BadFiles.Add(RandomBytes());
    {
        // A well-formed file from a newer version: its header says 2, and it would put spot A at its last stage.
        UReflectionsSaveGame* Newer = NewObject<UReflectionsSaveGame>();
        Newer->SaveVersion = 2;
        Newer->DigSpotStages.Add(SpikeA, 2);
        TestTrue(TEXT("Write a version 2 file"), ReflectionsSave::Write(*Newer, TestSlot));
        BadFiles.Add(LoadRaw());
    }
    const TCHAR* const Kinds[] = { TEXT("random bytes"), TEXT("a version 2 file") };
    for (int32 Index = 0; Index < BadFiles.Num(); ++Index)
    {
        const FString Kind = Kinds[Index];
        DeleteTestSlot();
        TestTrue(FString::Printf(TEXT("Store %s"), *Kind), UGameplayStatics::SaveDataToSlot(BadFiles[Index], TestSlot, 0));
        FReflectionsDigTestWorld TestWorld;
        if (TestNotNull(FString::Printf(TEXT("Test world (%s)"), *Kind), TestWorld.World))
        {
            int32 Logged = 0;
            AReflectionsDigSpot* A = nullptr;
            {
                FReflectionsLogCounter Counter;
                A = SpawnSpotWithId(TestWorld, Meshes, SpikeA, FVector::ZeroVector, ATargetPoint::StaticClass());
                Logged = Counter.Lines;
            }
            if (TestNotNull(FString::Printf(TEXT("Spot A (%s)"), *Kind), A))
            {
                TestTrue(FString::Printf(TEXT("Spot A has begun play (%s)"), *Kind), A->HasActorBegunPlay());
                TestEqual(FString::Printf(TEXT("Spot A begins at stage 0 (%s)"), *Kind), A->GetStage(), 0);
                TestTrue(FString::Printf(TEXT("Spot A shows mesh 0 (%s)"), *Kind), A->GetMeshComponent()->GetStaticMesh() == Meshes[0]);
                TestEqual(FString::Printf(TEXT("No find (%s)"), *Kind), CountTargetPoints(TestWorld.World), 0);
            }
            TestEqual(FString::Printf(TEXT("Beginning play logs nothing (%s)"), *Kind), Logged, 0);
            TestTrue(FString::Printf(TEXT("The slot's bytes are unchanged (%s)"), *Kind), LoadRaw() == BadFiles[Index]);
        }
    }
    DeleteTestSlot();
    return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
