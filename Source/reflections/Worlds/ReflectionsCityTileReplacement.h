#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ReflectionsCityTileReplacement.generated.h"

class UStaticMesh;
class UStaticMeshComponent;

USTRUCT(BlueprintType)
struct REFLECTIONS_API FReflectionsCityBuildingPart
{
    GENERATED_BODY()

    /** Tag on the owned Static Mesh Component that represents this complete building. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "City Replacement")
    FName ComponentTag;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "City Replacement")
    TObjectPtr<UStaticMesh> Mesh;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "City Replacement")
    FTransform RelativeTransform = FTransform::Identity;
};

/** Owns the filtered tile and all replacement building components as a single streaming unit. */
UCLASS(Blueprintable)
class REFLECTIONS_API AReflectionsCityTileReplacement : public AActor
{
    GENERATED_BODY()

public:
    AReflectionsCityTileReplacement();

    /** Assign the section-preserving filtered tile mesh on this component before cooking. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "City Replacement")
    TObjectPtr<UStaticMeshComponent> FilteredTile;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "City Replacement")
    TObjectPtr<UStaticMesh> SourceTileMesh;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "City Replacement")
    FTransform SourceTileWorldTransform = FTransform::Identity;

    /** Every building must have its own authored static mesh component and exact local transform. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "City Replacement")
    TArray<FReflectionsCityBuildingPart> RequiredBuildings;

    bool CollectReadyComponents(TArray<UStaticMeshComponent*>& Components) const;
    void SetReplacementActive(bool bRender, bool bCollide);

protected:
    virtual void PreRegisterAllComponents() override;
    virtual void BeginPlay() override;
};
