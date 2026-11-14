#pragma once

#include "CoreMinimal.h"
#include "reflectionsGameMode.h"
#include "ReflectionsHeroGameMode.generated.h"

/** Game mode for the isolated hero gameplay test map. */
UCLASS()
class AReflectionsHeroGameMode : public AreflectionsGameMode
{
    GENERATED_BODY()

public:
    AReflectionsHeroGameMode();
    virtual UClass* GetDefaultPawnClassForController_Implementation(AController* InController) override;
};
