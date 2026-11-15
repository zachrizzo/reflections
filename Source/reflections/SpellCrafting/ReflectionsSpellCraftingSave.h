#pragma once

#include "CoreMinimal.h"
#include "GameFramework/SaveGame.h"
#include "SpellCrafting/ReflectionsSpellCraftingTypes.h"
#include "ReflectionsSpellCraftingSave.generated.h"

/** Crafted spell slots. Only recipes are stored; everything else is re-derived on load. */
UCLASS()
class REFLECTIONS_API UReflectionsSpellCraftingSave : public USaveGame
{
    GENERATED_BODY()

public:
    static const TCHAR* SlotName() { return TEXT("SpellCrafting"); }
    static constexpr int32 CurrentVersion = 1;

    UPROPERTY(SaveGame)
    int32 Version = CurrentVersion;

    UPROPERTY(SaveGame)
    TArray<FCraftedSpellRecipe> Slots;

    /** -1 when the catalog spells were selected last. */
    UPROPERTY(SaveGame)
    int32 ActiveSlot = -1;
};
