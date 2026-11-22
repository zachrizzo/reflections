#include "Digging/ReflectionsDigSpot.h"

#include "CoreMinimal.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/Level.h"
#include "Engine/SkyLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "GameFramework/PlayerStart.h"
#include "Misc/AutomationTest.h"
#include "Misc/PackageName.h"
#include "UObject/Package.h"
#include "UObject/UObjectGlobals.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

namespace
{
    const TCHAR* DigSpikeMapPackage = TEXT("/Game/Maps/DigSpike/L_DigSpike");
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigSpikeMapIsBuiltAsSpecifiedTest, "Reflections.DigSpike.MapIsBuiltAsSpecified",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FReflectionsDigSpikeMapIsBuiltAsSpecifiedTest::RunTest(const FString& Parameters)
{
    // Load the package and read its persistent level; the map is not opened as the editor's level.
    if (!TestTrue(TEXT("The map package exists (run Tools/Digging/build_dig_spike_map.py)"),
        FPackageName::DoesPackageExist(DigSpikeMapPackage)))
    {
        return false;
    }
    UPackage* Package = LoadPackage(nullptr, DigSpikeMapPackage, LOAD_None);
    UWorld* World = Package != nullptr ? UWorld::FindWorldInPackage(Package) : nullptr;
    if (!TestNotNull(TEXT("World in the map package"), World) || !TestNotNull(TEXT("Persistent level"), World->PersistentLevel.Get()))
    {
        return false;
    }
    TestNull(TEXT("The map is not a World Partition map"), World->GetWorldPartition());
    TestFalse(TEXT("The level keeps its actors in its own file"), World->PersistentLevel->IsUsingExternalActors());

    TArray<AReflectionsDigSpot*> Spots;
    int32 PlayerStarts = 0;
    int32 Suns = 0;
    int32 SkyLights = 0;
    int32 SkyAtmospheres = 0;
    int32 Grounds = 0;
    for (AActor* Actor : World->PersistentLevel->Actors)
    {
        if (Actor == nullptr)
        {
            continue;
        }
        if (AReflectionsDigSpot* Spot = Cast<AReflectionsDigSpot>(Actor))
        {
            Spots.Add(Spot);
        }
        PlayerStarts += Actor->IsA<APlayerStart>() ? 1 : 0;
        Suns += Actor->IsA<ADirectionalLight>() ? 1 : 0;
        SkyLights += Actor->IsA<ASkyLight>() ? 1 : 0;
        SkyAtmospheres += Actor->IsA<ASkyAtmosphere>() ? 1 : 0;
        Grounds += (Actor->IsA<AStaticMeshActor>() && Actor->GetActorLabel() == TEXT("DigSpike_Ground")) ? 1 : 0;
    }

    if (TestEqual(TEXT("Dig spots"), Spots.Num(), 2))
    {
        TArray<FName> Ids;
        for (const AReflectionsDigSpot* Spot : Spots)
        {
            Ids.Add(Spot->SpotId);
            TestEqual(FString::Printf(TEXT("%s stage meshes"), *Spot->SpotId.ToString()), Spot->StageMeshes.Num(), 3);
            TestFalse(FString::Printf(TEXT("%s has a null stage mesh"), *Spot->SpotId.ToString()), Spot->StageMeshes.Contains(nullptr));
        }
        TestTrue(TEXT("A spot has id DigSpike_A"), Ids.Contains(FName(TEXT("DigSpike_A"))));
        TestTrue(TEXT("A spot has id DigSpike_B"), Ids.Contains(FName(TEXT("DigSpike_B"))));
    }
    TestEqual(TEXT("Player starts"), PlayerStarts, 1);
    TestEqual(TEXT("Directional lights"), Suns, 1);
    TestEqual(TEXT("Sky lights"), SkyLights, 1);
    TestEqual(TEXT("Sky atmospheres"), SkyAtmospheres, 1);
    TestEqual(TEXT("Static mesh actors labelled DigSpike_Ground"), Grounds, 1);
    return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR
