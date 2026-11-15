#include "Worlds/ReflectionsCityTileReplacement.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Worlds/ReflectionsCityTileReplacementSubsystem.h"

AReflectionsCityTileReplacement::AReflectionsCityTileReplacement()
{
    PrimaryActorTick.bCanEverTick = false;
    bReplicates = false;
    bNetLoadOnClient = true;
    FilteredTile = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("FilteredTile"));
    FilteredTile->SetMobility(EComponentMobility::Static);
    SetRootComponent(FilteredTile);
    SetActorHiddenInGame(true);
    SetActorEnableCollision(false);
}

void AReflectionsCityTileReplacement::PreRegisterAllComponents()
{
    if (const UWorld* World = GetWorld(); World && World->IsGameWorld())
    {
        SetReplacementActive(false, false);
    }
    Super::PreRegisterAllComponents();
}

void AReflectionsCityTileReplacement::BeginPlay()
{
    Super::BeginPlay();
    if (UReflectionsCityTileReplacementSubsystem* Subsystem = GetWorld()->GetSubsystem<UReflectionsCityTileReplacementSubsystem>())
    {
        Subsystem->RequestRefresh();
    }
}

bool AReflectionsCityTileReplacement::CollectReadyComponents(TArray<UStaticMeshComponent*>& Components) const
{
    Components.Reset();
    if (!IsActorInitialized() || IsActorBeingDestroyed() || !IsValid(SourceTileMesh.Get()) || !IsValid(FilteredTile.Get()) ||
        FilteredTile->GetStaticMesh() == SourceTileMesh.Get() || RequiredBuildings.IsEmpty() ||
        !UReflectionsCityTileReplacementSubsystem::TransformsMatch(
            FilteredTile->GetComponentTransform(), SourceTileWorldTransform))
    {
        return false;
    }

    TInlineComponentArray<UPrimitiveComponent*> Primitives;
    GetComponents(Primitives);
    if (Primitives.Num() != RequiredBuildings.Num() + 1 || !Primitives.Contains(FilteredTile.Get()))
    {
        return false;
    }
    for (UPrimitiveComponent* Primitive : Primitives)
    {
        UStaticMeshComponent* Component = Cast<UStaticMeshComponent>(Primitive);
        UStaticMesh* Mesh = Component ? Component->GetStaticMesh() : nullptr;
        if (!IsValid(Component) || !IsValid(Mesh) || !Component->IsRegistered() || Component->IsBeingDestroyed() ||
            Component->GetMobility() != EComponentMobility::Static ||
            !Component->GetVisibleFlag() || Component->bHiddenInGame ||
            (GetNetMode() != NM_DedicatedServer && (!Mesh->GetRenderData() || Mesh->GetNumLODs() == 0)))
        {
            Components.Reset();
            return false;
        }
        Components.Add(Component);
    }

    TSet<const UStaticMeshComponent*> Matched;
    for (const FReflectionsCityBuildingPart& Part : RequiredBuildings)
    {
        if (!IsValid(Part.Mesh.Get()) || Part.Mesh == SourceTileMesh || Part.Mesh.Get() == FilteredTile->GetStaticMesh() ||
            Part.ComponentTag.IsNone())
        {
            return false;
        }
        const UStaticMeshComponent* Match = nullptr;
        for (const UStaticMeshComponent* Component : Components)
        {
            if (Component == FilteredTile.Get() || !Component->ComponentHasTag(Part.ComponentTag))
            {
                continue;
            }
            if (Match || Matched.Contains(Component) || Component->GetStaticMesh() != Part.Mesh.Get() ||
                !UReflectionsCityTileReplacementSubsystem::TransformsMatch(
                    Component->GetComponentTransform(), Part.RelativeTransform * GetActorTransform()))
            {
                return false;
            }
            Match = Component;
        }
        if (!Match)
        {
            return false;
        }
        Matched.Add(Match);
    }
    return true;
}

void AReflectionsCityTileReplacement::SetReplacementActive(bool bRender, bool bCollide)
{
    SetActorHiddenInGame(!bRender);
    SetActorEnableCollision(bCollide);
}
