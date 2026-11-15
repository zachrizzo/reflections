#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ReflectionsCrowdLaneLibrary.generated.h"

/**
 * Read-only checks of a world's ZoneGraph lanes, callable from editor Python (the lane generator in Tools/Crowd/
 * uses them to verify its build) and from tests. They work in editor and game worlds.
 */
UCLASS()
class REFLECTIONS_API UReflectionsCrowdLaneLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    /** Lanes with at least one point within Radius (cm, 2D) of Center, over every registered ZoneGraph data. */
    UFUNCTION(BlueprintCallable, Category="Crowd|Lanes", meta=(WorldContext="WorldContext"))
    static int32 CountLanesNear(const UObject* WorldContext, FVector Center, float Radius);

    /** "N data, N lanes, N points, total length" for the world, or why there are none. */
    UFUNCTION(BlueprintCallable, Category="Crowd|Lanes", meta=(WorldContext="WorldContext"))
    static FString DescribeLanes(const UObject* WorldContext);
};
