#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ReflectionsGameFlowLibrary.generated.h"

class AActor;

/**
 * One-line calls for NPC, enemy and villain code. Include "GameFlow/ReflectionsGameFlowLibrary.h".
 *
 *   UReflectionsGameFlowLibrary::ReportInfected(this, Npc);   // +1 to the global count (once per actor)
 *   UReflectionsGameFlowLibrary::ReportCured(this, Npc);      // -1 if it was counted
 *   UReflectionsGameFlowLibrary::ShowVictory(this);           // the villain is beaten
 */
UCLASS()
class REFLECTIONS_API UReflectionsGameFlowLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, Category = "Game Flow", meta = (WorldContext = "WorldContext"))
    static void ReportInfected(const UObject* WorldContext, AActor* Host);

    UFUNCTION(BlueprintCallable, Category = "Game Flow", meta = (WorldContext = "WorldContext"))
    static void ReportCured(const UObject* WorldContext, AActor* Host);

    UFUNCTION(BlueprintPure, Category = "Game Flow", meta = (WorldContext = "WorldContext"))
    static int32 GetInfectionCount(const UObject* WorldContext);

    UFUNCTION(BlueprintPure, Category = "Game Flow", meta = (WorldContext = "WorldContext"))
    static int32 GetInfectionCap(const UObject* WorldContext);

    UFUNCTION(BlueprintCallable, Category = "Game Flow", meta = (WorldContext = "WorldContext"))
    static void ShowVictory(const UObject* WorldContext);

    UFUNCTION(BlueprintCallable, Category = "Game Flow", meta = (WorldContext = "WorldContext"))
    static bool SaveCheckpoint(const UObject* WorldContext, const FString& Reason);

    UFUNCTION(BlueprintPure, Category = "Game Flow", meta = (WorldContext = "WorldContext"))
    static bool IsGameOver(const UObject* WorldContext);
};
