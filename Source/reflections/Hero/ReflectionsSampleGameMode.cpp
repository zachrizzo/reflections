#include "Hero/ReflectionsSampleGameMode.h"

#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/PlayerStart.h"
#include "GameFramework/PlayerController.h"
#include "UObject/SoftObjectPath.h"

void AReflectionsSampleGameMode::InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage)
{
	Super::InitGame(MapName, Options, ErrorMessage);
	// The clean copies retain sample locomotion while avoiding legacy combat Blueprint dependencies.
	const FSoftClassPath CharacterPath(TEXT("/Game/Characters/Hero/Sample/BP_HeroSampleCleanTest.BP_HeroSampleCleanTest_C"));
	if (UClass* Character = CharacterPath.TryLoadClass<ACharacter>())
	{
		DefaultPawnClass = Character;
	}

	const FSoftClassPath ControllerPath(TEXT("/Game/Characters/Hero/Sample/BP_SampleControllerClean.BP_SampleControllerClean_C"));
	if (UClass* Controller = ControllerPath.TryLoadClass<APlayerController>())
	{
		PlayerControllerClass = Controller;
	}
}

AActor* AReflectionsSampleGameMode::ChoosePlayerStart_Implementation(AController* Player)
{
	if (UWorld* World = GetWorld())
	{
		const FName LanthorneTag(TEXT("Lanthorne"));
		for (TActorIterator<APlayerStart> It(World); It; ++It)
		{
			if (It->PlayerStartTag == LanthorneTag)
			{
				return *It;
			}
		}
	}
	return Super::ChoosePlayerStart_Implementation(Player);
}
