#pragma once

#include "CoreMinimal.h"
#include "GameFramework/SaveGame.h"
#include "GameFlow/ReflectionsGameFlowTypes.h"
#include "ReflectionsGameFlowSave.generated.h"

/** The single save slot: the last checkpoint plus which tips the player has already seen. */
UCLASS()
class REFLECTIONS_API UReflectionsGameFlowSave : public USaveGame
{
    GENERATED_BODY()

public:
    static constexpr int32 CurrentVersion = 1;

    /** 0 by default and set on every write: a value equal to the class default would not be serialized at all. */
    UPROPERTY() int32 Version = 0;
    UPROPERTY() FReflectionsCheckpoint Checkpoint;
    UPROPERTY() int32 SeenTips = 0;
};
