#include "Hero/ReflectionsSampleGameMode.h"

#include "Digging/ReflectionsDigComponent.h"
#include "Hero/ReflectionsSwordTest.h"
#include "GameFramework/Character.h"
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

void AReflectionsSampleGameMode::SetPlayerDefaults(APawn* PlayerPawn)
{
	Super::SetPlayerDefaults(PlayerPawn);
	// The live player pawn is a Blueprint this code cannot edit, so the dig component is added at runtime.
	UReflectionsDigComponent::EnsureOnPawn(PlayerPawn);
	// Temporary sword animation test (X draws the sword); Sword.Test 0 skips it. See ArtDirection/VideoToAnim/SwordCombatPatch.md.
	UReflectionsSwordTestComponent::EnsureOnPawn(PlayerPawn);
}
