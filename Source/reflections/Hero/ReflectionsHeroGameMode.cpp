#include "ReflectionsHeroGameMode.h"

#include "ReflectionsHeroCharacter.h"
#include "GameFramework/PlayerController.h"
#include "UObject/ConstructorHelpers.h"

AReflectionsHeroGameMode::AReflectionsHeroGameMode()
{
    DefaultPawnClass = AReflectionsHeroCharacter::StaticClass();
    static ConstructorHelpers::FClassFinder<APlayerController> Controller(
        TEXT("/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController"));
    if (Controller.Succeeded())
    {
        PlayerControllerClass = Controller.Class;
    }
}

UClass* AReflectionsHeroGameMode::GetDefaultPawnClassForController_Implementation(AController* InController)
{
    UClass* ConfiguredClass = Super::GetDefaultPawnClassForController_Implementation(InController);
    if (ConfiguredClass != AReflectionsHeroCharacter::StaticClass())
    {
        return ConfiguredClass;
    }

    static const FSoftClassPath HeroPlayer(TEXT("/Game/Characters/Hero/Gameplay/BP_HeroPlayer.BP_HeroPlayer_C"));
    if (UClass* HeroClass = HeroPlayer.TryLoadClass<AReflectionsHeroCharacter>())
    {
        return HeroClass;
    }
    return ConfiguredClass;
}
