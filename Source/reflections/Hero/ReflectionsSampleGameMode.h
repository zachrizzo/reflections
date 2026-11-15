#pragma once

#include "GameFramework/GameModeBase.h"
#include "ReflectionsSampleGameMode.generated.h"

UCLASS()
class REFLECTIONS_API AReflectionsSampleGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	virtual void InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage) override;

	/** Gray London has two PlayerStarts: one at the map origin (in the dark) and the Lanthorne start at Great Tower St
	 *  (PlayerStartTag "Lanthorne"). The hero starts at the first Lanthorne one; without it, the default choice. */
	virtual AActor* ChoosePlayerStart_Implementation(AController* Player) override;
};
