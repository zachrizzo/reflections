#include "Digging/ReflectionsDigSpot.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/CollisionProfile.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"

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
        GetWorld()->SpawnActor<AActor>(BuriedFindClass, GetActorTransform(), Params);
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
