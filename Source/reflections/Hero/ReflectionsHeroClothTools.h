#pragma once

#include "Kismet/BlueprintFunctionLibrary.h"
#include "ReflectionsHeroClothTools.generated.h"

class UPhysicsAsset;
class USkeletalMesh;
class USkeletalMeshComponent;

UCLASS()
class UReflectionsHeroClothTools : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "Hero|Wardrobe", meta = (DevelopmentOnly))
	static bool BuildCoatTailSimulation(USkeletalMesh* TailMesh, UPhysicsAsset* CollisionAsset);

	UFUNCTION(BlueprintPure, Category = "Hero|Wardrobe", meta = (DevelopmentOnly))
	static FString InspectCoatTailSimulation(USkeletalMeshComponent* TailComponent);
};
