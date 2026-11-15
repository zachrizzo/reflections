#pragma once

#include "CoreMinimal.h"
#include "GameFramework/SaveGame.h"
#include "Quests/ReflectionsQuestTypes.h"
#include "ReflectionsQuestSave.generated.h"

/** Slot Reflections_Quests: the quest state taken with the last game-flow checkpoint. */
UCLASS()
class REFLECTIONS_API UReflectionsQuestSave : public USaveGame
{
    GENERATED_BODY()

public:
    static constexpr int32 CurrentVersion = 1;

    UPROPERTY() int32 Version = CurrentVersion;
    UPROPERTY() FReflectionsQuestSnapshot Snapshot;
};
