#include "Digging/ReflectionsDigSpot.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/CollisionProfile.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Save/ReflectionsSaveGame.h"

AReflectionsDigSpot::AReflectionsDigSpot()
{
    PrimaryActorTick.bCanEverTick = false;

    MeshComponent = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
    MeshComponent->SetCollisionProfileName(UCollisionProfile::BlockAll_ProfileName);
    // The mesh is swapped at runtime, which a Static component refuses.
    MeshComponent->SetMobility(EComponentMobility::Movable);
    RootComponent = MeshComponent;
}

bool AReflectionsDigSpot::DigOnce()
{
    if (StageMeshes.IsEmpty() || Stage >= GetLastStage())
    {
        return false;
    }

    ++Stage;
    ShowStage();

    if (Stage == GetLastStage() && !bFindSpawned && BuriedFindClass != nullptr)
    {
        bFindSpawned = true;
        FActorSpawnParameters Params;
        Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        // Location and rotation only: a scaled ground patch must not scale what it uncovers.
        GetWorld()->SpawnActor<AActor>(BuriedFindClass, GetActorLocation(), GetActorRotation(), Params);
    }
    return true;
}

int32 AReflectionsDigSpot::GetStage() const
{
    return Stage;
}

void AReflectionsDigSpot::SetStage(int32 NewStage)
{
    Stage = FMath::Clamp(NewStage, 0, GetLastStage());
    if (Stage == GetLastStage())
    {
        // A spot set to fully dug has already given its find, whatever is called on it later.
        bFindSpawned = true;
    }
    ShowStage();
}

UStaticMeshComponent* AReflectionsDigSpot::GetMeshComponent() const
{
    return MeshComponent;
}

void AReflectionsDigSpot::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);
    ShowStage();
}

void AReflectionsDigSpot::BeginPlay()
{
    Super::BeginPlay();

    // Restore how far this spot was dug. Reading never writes; any other outcome leaves the stage as it is.
    if (SpotId != NAME_None)
    {
        UReflectionsSaveGame* Data = nullptr;
        if (ReflectionsSave::Read(ReflectionsSave::ActiveSlot(), Data) == EReflectionsLoadResult::Loaded && Data != nullptr)
        {
            if (const uint8* SavedStage = Data->DigSpotStages.Find(SpotId))
            {
                SetStage(*SavedStage);
                return;
            }
        }
    }
    ShowStage();
}

int32 AReflectionsDigSpot::GetLastStage() const
{
    return FMath::Max(0, StageMeshes.Num() - 1);
}

void AReflectionsDigSpot::ShowStage()
{
    MeshComponent->SetStaticMesh(StageMeshes.IsValidIndex(Stage) ? StageMeshes[Stage].Get() : nullptr);
}
