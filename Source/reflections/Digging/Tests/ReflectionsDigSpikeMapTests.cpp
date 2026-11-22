#include "Digging/ReflectionsDigSpot.h"

#include "CoreMinimal.h"
#include "Components/BrushComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Digging/ReflectionsDigTerrain.h"
#include "Engine/DirectionalLight.h"
#include "Engine/Level.h"
#include "Engine/PointLight.h"
#include "Engine/SkyLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/PlayerStart.h"
#include "GameFramework/WorldSettings.h"
#include "Misc/AutomationTest.h"
#include "Misc/PackageName.h"
#include "NavigationData.h"
#include "NavMesh/NavMeshBoundsVolume.h"
#include "NavMesh/RecastNavMesh.h"
#include "UObject/Package.h"
#include "UObject/UObjectGlobals.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

namespace
{
    const TCHAR* DigSpikeMapPackage = TEXT("/Game/Maps/DigSpike/L_DigSpike");

    const TCHAR* StageMeshPaths[] = {
        TEXT("/Engine/BasicShapes/Cube.Cube"),
        TEXT("/Engine/BasicShapes/Cone.Cone"),
        TEXT("/Engine/BasicShapes/Cylinder.Cylinder"),
    };

    struct FCaveLightSpec
    {
        const TCHAR* Label;
        FVector Location;
    };

    const FCaveLightSpec CaveLights[] = {
        {TEXT("DigSpike_CaveLight1"), FVector(2800.0, -600.0, 250.0)},
        {TEXT("DigSpike_CaveLight2"), FVector(2800.0, 600.0, 250.0)},
        {TEXT("DigSpike_CaveLight3"), FVector(4000.0, -600.0, 250.0)},
        {TEXT("DigSpike_CaveLight4"), FVector(4000.0, 600.0, 250.0)},
    };

    /**
     * The whole table: ground, terrain, sun, sky, sky light, the cave lights, player start, two dig spots, the navmesh
     * bounds and the navmesh.
     */
    constexpr int32 ExpectedActorCount = 8 + static_cast<int32>(UE_ARRAY_COUNT(CaveLights)) + 2;

    /** The level's one actor of class T labelled Label, or null (reported) when there is none or more than one. */
    template <typename T>
    T* FindByLabel(FAutomationTestBase& Test, const ULevel& Level, const TCHAR* Label)
    {
        TArray<T*> Found;
        for (AActor* Actor : Level.Actors)
        {
            if (T* Typed = Cast<T>(Actor); Typed != nullptr && Actor->GetActorLabel() == Label)
            {
                Found.Add(Typed);
            }
        }
        if (!Test.TestEqual(FString::Printf(TEXT("Actors of class %s labelled %s"), *T::StaticClass()->GetName(), Label), Found.Num(), 1))
        {
            return nullptr;
        }
        return Found[0];
    }

    void TestLocation(FAutomationTestBase& Test, const AActor& Actor, const FVector& Expected)
    {
        Test.TestTrue(FString::Printf(TEXT("%s location %s is %s"), *Actor.GetActorLabel(), *Actor.GetActorLocation().ToString(), *Expected.ToString()),
            Actor.GetActorLocation().Equals(Expected, 0.01));
    }

    void TestUnrotatedUnscaled(FAutomationTestBase& Test, const AActor& Actor)
    {
        Test.TestTrue(FString::Printf(TEXT("%s is unrotated"), *Actor.GetActorLabel()), Actor.GetActorRotation().Equals(FRotator::ZeroRotator, 0.01));
        Test.TestTrue(FString::Printf(TEXT("%s is unscaled"), *Actor.GetActorLabel()), Actor.GetActorScale3D().Equals(FVector::OneVector, 0.0001));
    }

    void TestMovable(FAutomationTestBase& Test, const AActor& Actor, const USceneComponent* Component)
    {
        if (Test.TestNotNull(FString::Printf(TEXT("%s component"), *Actor.GetActorLabel()), Component))
        {
            Test.TestTrue(FString::Printf(TEXT("%s is movable"), *Actor.GetActorLabel()), Component->Mobility == EComponentMobility::Movable);
        }
    }

    void TestSpot(FAutomationTestBase& Test, const ULevel& Level, const TCHAR* Label, FName Id, const FVector& Location)
    {
        const AReflectionsDigSpot* Spot = FindByLabel<AReflectionsDigSpot>(Test, Level, Label);
        if (Spot == nullptr)
        {
            return;
        }
        Test.TestTrue(FString::Printf(TEXT("%s spot id %s is %s"), Label, *Spot->SpotId.ToString(), *Id.ToString()), Spot->SpotId == Id);
        TestLocation(Test, *Spot, Location);
        TestUnrotatedUnscaled(Test, *Spot);
        if (Test.TestEqual(FString::Printf(TEXT("%s stage meshes"), Label), Spot->StageMeshes.Num(), static_cast<int32>(UE_ARRAY_COUNT(StageMeshPaths))))
        {
            for (int32 Index = 0; Index < Spot->StageMeshes.Num(); ++Index)
            {
                const UStaticMesh* Mesh = Spot->StageMeshes[Index];
                Test.TestEqual(FString::Printf(TEXT("%s stage mesh %d"), Label, Index), Mesh != nullptr ? Mesh->GetPathName() : FString(TEXT("null")),
                    FString(StageMeshPaths[Index]));
            }
        }
    }
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
    const ULevel& Level = *World->PersistentLevel;
    TestNull(TEXT("The map is not a World Partition map"), World->GetWorldPartition());
    TestFalse(TEXT("The level keeps its actors in its own file"), Level.IsUsingExternalActors());
    if (const AWorldSettings* Settings = World->GetWorldSettings(); TestNotNull(TEXT("World settings"), Settings))
    {
        TestNull(TEXT("The level sets no game mode override"), Settings->DefaultGameMode.Get());
    }

    // Every actor the map file holds, but the world settings and the default brush, is one of the table below, so an
    // actor of any other class, or a second one of these, fails the total. Transient actors the editor spawns into a
    // loaded level (its default physics volume, a debug-draw actor) are not in the file and are not counted.
    TArray<FString> Counted;
    for (const AActor* Actor : Level.Actors)
    {
        if (Actor != nullptr && !Actor->HasAnyFlags(RF_Transient) && Actor != Level.GetWorldSettings(/*bChecked=*/ false)
            && Actor != Level.GetDefaultBrush())
        {
            Counted.Add(FString::Printf(TEXT("%s %s"), *Actor->GetClass()->GetName(), *Actor->GetActorLabel()));
        }
    }
    TestEqual(FString::Printf(TEXT("Saved actors besides the world settings and the default brush (%s)"), *FString::Join(Counted, TEXT(", "))),
        Counted.Num(), ExpectedActorCount);

    int32 Spots = 0;
    int32 Terrains = 0;
    int32 PlayerStarts = 0;
    int32 Suns = 0;
    int32 SkyLights = 0;
    int32 SkyAtmospheres = 0;
    int32 PointLights = 0;
    int32 StaticMeshActors = 0;
    int32 NavBoundsVolumes = 0;
    int32 NavigationDatas = 0;
    for (const AActor* Actor : Level.Actors)
    {
        if (Actor == nullptr || Actor->HasAnyFlags(RF_Transient))
        {
            continue;
        }
        NavBoundsVolumes += Actor->IsA<ANavMeshBoundsVolume>() ? 1 : 0;
        NavigationDatas += Actor->IsA<ANavigationData>() ? 1 : 0;
        Spots += Actor->IsA<AReflectionsDigSpot>() ? 1 : 0;
        Terrains += Actor->IsA<AReflectionsDigTerrain>() ? 1 : 0;
        PlayerStarts += Actor->IsA<APlayerStart>() ? 1 : 0;
        Suns += Actor->IsA<ADirectionalLight>() ? 1 : 0;
        SkyLights += Actor->IsA<ASkyLight>() ? 1 : 0;
        SkyAtmospheres += Actor->IsA<ASkyAtmosphere>() ? 1 : 0;
        PointLights += Actor->IsA<APointLight>() ? 1 : 0;
        StaticMeshActors += Actor->IsA<AStaticMeshActor>() ? 1 : 0;
    }
    TestEqual(TEXT("Dig spots"), Spots, 2);
    TestEqual(TEXT("Dig terrains"), Terrains, 1);
    TestEqual(TEXT("Player starts"), PlayerStarts, 1);
    TestEqual(TEXT("Directional lights"), Suns, 1);
    TestEqual(TEXT("Sky lights"), SkyLights, 1);
    TestEqual(TEXT("Sky atmospheres"), SkyAtmospheres, 1);
    TestEqual(TEXT("Point lights"), PointLights, static_cast<int32>(UE_ARRAY_COUNT(CaveLights)));
    TestEqual(TEXT("Static mesh actors"), StaticMeshActors, 1);
    TestEqual(TEXT("Navmesh bounds volumes"), NavBoundsVolumes, 1);
    TestEqual(TEXT("Navigation data actors"), NavigationDatas, 1);

    // The bounds cover the whole patch (X 1000 to 5800, Y -2400 to 2400, Z -2800 to 400) with a 200 cm margin.
    if (const ANavMeshBoundsVolume* Bounds = FindByLabel<ANavMeshBoundsVolume>(*this, Level, TEXT("DigSpike_NavBounds")))
    {
        const FBox Expected(FVector(800.0, -2600.0, -3000.0), FVector(6000.0, 2600.0, 600.0));
        // The level is loaded, not registered in a world, so the brush's bounds are computed from its saved shape.
        const UBrushComponent* Brush = Bounds->GetBrushComponent();
        const FBox Actual = Brush != nullptr
            ? Brush->CalcBounds(FTransform(Brush->GetRelativeRotation(), Brush->GetRelativeLocation(), Brush->GetRelativeScale3D())).GetBox()
            : FBox(ForceInit);
        TestTrue(FString::Printf(TEXT("DigSpike_NavBounds covers %s (it covers %s)"), *Expected.ToString(), *Actual.ToString()),
            Actual.IsValid && Actual.Min.Equals(Expected.Min, 0.5) && Actual.Max.Equals(Expected.Max, 0.5));
        TestTrue(TEXT("DigSpike_NavBounds is unrotated"), Bounds->GetActorRotation().Equals(FRotator::ZeroRotator, 0.01));
    }

    // The navmesh rebuilds itself at run time; the project's navigation settings stay untouched.
    if (const ARecastNavMesh* NavMesh = FindByLabel<ARecastNavMesh>(*this, Level, TEXT("DigSpike_NavMesh")))
    {
        TestTrue(TEXT("DigSpike_NavMesh is exactly an ARecastNavMesh"), NavMesh->GetClass() == ARecastNavMesh::StaticClass());
        TestTrue(FString::Printf(TEXT("DigSpike_NavMesh runtime generation is Dynamic (%s)"), *UEnum::GetValueAsString(NavMesh->GetRuntimeGenerationMode())),
            NavMesh->GetRuntimeGenerationMode() == ERuntimeGenerationType::Dynamic);
    }

    // The ground ends at X = 1000, flush against the patch.
    if (const AStaticMeshActor* Ground = FindByLabel<AStaticMeshActor>(*this, Level, TEXT("DigSpike_Ground")))
    {
        TestLocation(*this, *Ground, FVector(-2000.0, 0.0, -50.0));
        TestTrue(TEXT("DigSpike_Ground scale is (60, 100, 1)"), Ground->GetActorScale3D().Equals(FVector(60.0, 100.0, 1.0), 0.0001));
        TestTrue(TEXT("DigSpike_Ground is unrotated"), Ground->GetActorRotation().Equals(FRotator::ZeroRotator, 0.01));
        const UStaticMesh* Mesh = Ground->GetStaticMeshComponent()->GetStaticMesh();
        TestEqual(TEXT("DigSpike_Ground mesh"), Mesh != nullptr ? Mesh->GetPathName() : FString(TEXT("null")), FString(StageMeshPaths[0]));
    }

    if (const AReflectionsDigTerrain* Terrain = FindByLabel<AReflectionsDigTerrain>(*this, Level, TEXT("DigSpike_Terrain")))
    {
        TestTrue(TEXT("DigSpike_Terrain is exactly an AReflectionsDigTerrain"), Terrain->GetClass() == AReflectionsDigTerrain::StaticClass());
        TestLocation(*this, *Terrain, FVector(1000.0, -2400.0, 0.0));
        TestUnrotatedUnscaled(*this, *Terrain);
        TestEqual(TEXT("DigSpike_Terrain GroundHeightCm"), Terrain->GroundHeightCm, 0.0f);
        TestTrue(FString::Printf(TEXT("DigSpike_Terrain size %s is the default (3, 3, 2)"), *Terrain->SizeInChunks.ToString()),
            Terrain->SizeInChunks == FIntVector(3, 3, 2) && Terrain->SizeInChunks == GetDefault<AReflectionsDigTerrain>()->SizeInChunks);
    }

    if (const ADirectionalLight* Sun = FindByLabel<ADirectionalLight>(*this, Level, TEXT("DigSpike_Sun")))
    {
        TestLocation(*this, *Sun, FVector::ZeroVector);
        TestTrue(FString::Printf(TEXT("DigSpike_Sun rotation %s is pitch -45, yaw 30"), *Sun->GetActorRotation().ToString()),
            Sun->GetActorRotation().Equals(FRotator(-45.0, 30.0, 0.0), 0.01));
        TestMovable(*this, *Sun, Sun->GetRootComponent());
    }

    if (const ASkyAtmosphere* Sky = FindByLabel<ASkyAtmosphere>(*this, Level, TEXT("DigSpike_Sky")))
    {
        TestLocation(*this, *Sky, FVector::ZeroVector);
        TestUnrotatedUnscaled(*this, *Sky);
    }

    if (const ASkyLight* SkyLight = FindByLabel<ASkyLight>(*this, Level, TEXT("DigSpike_SkyLight")))
    {
        TestLocation(*this, *SkyLight, FVector::ZeroVector);
        TestUnrotatedUnscaled(*this, *SkyLight);
        const USkyLightComponent* Component = SkyLight->GetLightComponent();
        TestMovable(*this, *SkyLight, Component);
        if (Component != nullptr)
        {
            TestTrue(TEXT("DigSpike_SkyLight captures in real time"), Component->bRealTimeCapture);
        }
    }

    for (const FCaveLightSpec& Spec : CaveLights)
    {
        const APointLight* Light = FindByLabel<APointLight>(*this, Level, Spec.Label);
        if (Light == nullptr)
        {
            continue;
        }
        TestLocation(*this, *Light, Spec.Location);
        const UPointLightComponent* Component = Light->PointLightComponent;
        TestMovable(*this, *Light, Component);
        if (Component != nullptr)
        {
            TestTrue(FString::Printf(TEXT("%s intensity is unitless"), Spec.Label), Component->IntensityUnits == ELightUnits::Unitless);
            TestEqual(FString::Printf(TEXT("%s intensity"), Spec.Label), Component->Intensity, 5000.0f);
            TestEqual(FString::Printf(TEXT("%s attenuation radius"), Spec.Label), Component->AttenuationRadius, 1500.0f);
        }
    }

    if (const APlayerStart* Start = FindByLabel<APlayerStart>(*this, Level, TEXT("DigSpike_Start")))
    {
        TestLocation(*this, *Start, FVector(400.0, 0.0, 100.0));
        TestTrue(TEXT("DigSpike_Start faces +X"), Start->GetActorRotation().Equals(FRotator::ZeroRotator, 0.01));
    }

    TestSpot(*this, Level, TEXT("DigSpike_SpotA"), FName(TEXT("DigSpike_A")), FVector(0.0, -300.0, 50.0));
    TestSpot(*this, Level, TEXT("DigSpike_SpotB"), FName(TEXT("DigSpike_B")), FVector(0.0, 300.0, 50.0));
    return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR
