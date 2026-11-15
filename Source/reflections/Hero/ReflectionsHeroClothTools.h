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

	/**
	 * Same cloth build as BuildCoatTailSimulation, with a painted profile for long coats.
	 * Depth runs 0 at the highest cloth vertex to 1 at the hem. Particles above PinnedDepth are pinned;
	 * below it max distance rises continuously as MaxDistanceAtHem * t^GradientExponent, so there is no
	 * hard pinned/free edge. BackstopRadius > 0 adds a non-legacy backstop letting each particle move at most
	 * BackstopDistance inward from its skinned position; 0 removes any backstop maps.
	 */
	UFUNCTION(BlueprintCallable, Category = "Hero|Wardrobe", meta = (DevelopmentOnly))
	static bool BuildCoatClothProfile(USkeletalMesh* CoatMesh, UPhysicsAsset* CollisionAsset, float PinnedDepth,
		float MaxDistanceAtHem, float GradientExponent, float BackstopDistance, float BackstopRadius);

	UFUNCTION(BlueprintPure, Category = "Hero|Wardrobe", meta = (DevelopmentOnly))
	static FString InspectCoatTailSimulation(USkeletalMeshComponent* TailComponent);
};
