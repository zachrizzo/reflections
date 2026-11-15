#pragma once

#include "CoreMinimal.h"
#include "Engine/DataTable.h"
#include "GameFramework/Actor.h"
#include "ReflectionsCrowdLookRow.generated.h"

/**
 * Which full NPC actor a city-crowd pedestrian becomes when it is promoted, so it keeps its face, outfit and tint.
 * One row per MetaHuman Instance used by the crowd. The table is maintained with the crowd looks
 * (default path /Game/Crowd/City/DT_CrowdLookMap, CVar Crowd.Mass.LookTable).
 */
USTRUCT(BlueprintType)
struct REFLECTIONS_API FReflectionsCrowdLookRow : public FTableRowBase
{
    GENERATED_BODY()

    /** A MetaHuman Instance from the crowd entity config's visualization (CharacterInstances). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Crowd")
    TSoftObjectPtr<UObject> CrowdInstance;

    /** The full-quality look actor of the same person (spawned through UReflectionsNpcSubsystem::SpawnNpc). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Crowd")
    TSoftClassPtr<AActor> ActorClass;
};
