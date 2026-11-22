#pragma once

#include "Kismet/BlueprintFunctionLibrary.h"
#include "ClothingFitLibrary.generated.h"

class USkinnedMeshComponent;
class USkeletalMeshComponent;

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
};
