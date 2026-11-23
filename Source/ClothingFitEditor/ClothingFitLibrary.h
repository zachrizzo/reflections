#pragma once

#include "Kismet/BlueprintFunctionLibrary.h"
#include "ClothingFitLibrary.generated.h"

class USkinnedMeshComponent;
class USkeletalMeshComponent;
class UChaosClothComponent;

/** Editor-only inspection of the fitted, bone-deformed LOD 0 surface. */
UCLASS()
class UClothingFitLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, Category="Clothing Fit")
    static bool WritePosedSurface(USkinnedMeshComponent* Component, const FString& Filename);

    UFUNCTION(BlueprintCallable, Category="Clothing Fit")
    static void RefreshSamplePose(USkeletalMeshComponent* Body);

    UFUNCTION(BlueprintCallable, Category="Clothing Fit")
    static bool WriteSimulatedSurface(USkinnedMeshComponent* Component, const FString& Filename);

    UFUNCTION(BlueprintPure, Category="Clothing Fit")
    static int32 GetDynamicClothParticleCount(USkinnedMeshComponent* Component);

    UFUNCTION(BlueprintCallable, Category="Clothing Fit")
    static AActor* SpawnBenchActor(AActor* WorldContext, FVector Location, FRotator Rotation);

    /** Build a fitted outfit with a skinned body collider from the wearer's actual mesh. */
    UFUNCTION(BlueprintCallable, Category="Clothing Fit")
    static int32 FitTriangleCollider(UChaosClothComponent* Cloth, USkeletalMeshComponent* Body);

    /** Read LOD 0 using the simulation state and the same proxy mapping as the renderer. */
    UFUNCTION(BlueprintCallable, Category="Clothing Fit")
    static bool WriteClothFrame(UChaosClothComponent* Cloth, const FString& Filename);
};
