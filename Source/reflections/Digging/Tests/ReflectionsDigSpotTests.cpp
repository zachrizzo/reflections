#include "Digging/ReflectionsDigSpot.h"

#include "CoreMinimal.h"
#include "Components/StaticMeshComponent.h"
#include "Digging/Tests/ReflectionsDigTestWorld.h"
#include "Engine/StaticMesh.h"
#include "Engine/TargetPoint.h"
#include "EngineUtils.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
    constexpr EAutomationTestFlags DigSpotTestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter;

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
    AReflectionsDigSpot* Spot = SpawnSpot(TestWorld, Meshes, ATargetPoint::StaticClass());
    if (!TestNotNull(TEXT("Spot"), Spot))
    {
        return false;
    }

    TestEqual(TEXT("No find before digging"), CountTargetPoints(TestWorld.World), 0);
    Spot->DigOnce();
    TestEqual(TEXT("No find after the first dig"), CountTargetPoints(TestWorld.World), 0);
    Spot->DigOnce();
    TestEqual(TEXT("One find after the second dig"), CountTargetPoints(TestWorld.World), 1);
    Spot->DigOnce();
    TestEqual(TEXT("Still one find after a third dig"), CountTargetPoints(TestWorld.World), 1);

    AReflectionsDigSpot* Restored = SpawnSpot(TestWorld, Meshes, ATargetPoint::StaticClass());
    if (!TestNotNull(TEXT("Second spot"), Restored))
    {
        return false;
    }
    Restored->SetStage(2);
    TestEqual(TEXT("Second spot is at the last stage"), Restored->GetStage(), 2);
    TestEqual(TEXT("SetStage spawns no find"), CountTargetPoints(TestWorld.World), 1);
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

#endif // WITH_DEV_AUTOMATION_TESTS
