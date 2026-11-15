#pragma once

#include "GameFramework/GameModeBase.h"
#include "ReflectionsSampleGameMode.generated.h"

UCLASS()
class REFLECTIONS_API AReflectionsSampleGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	virtual void InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage) override;
};
