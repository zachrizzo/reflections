#pragma once

#include "CoreMinimal.h"
#include "UObject/Object.h"
#include "SpellCrafting/ReflectionsSpellCraftingTypes.h"
#include "ReflectionsSpellRecipeRelay.generated.h"

class IWebSocket;

/**
 * Development-only client for Tools/SpellCrafting/recipe_relay.py: sends one sentence to a loopback relay that
 * holds the OpenAI key in its own process and returns a recipe. The game never sees a key. Compiled out of
 * Shipping builds; when the relay is not running (or in any packaged build) the caller falls back to the
 * offline keyword parser, so "describe your spell" never needs the network.
 */
UCLASS()
class REFLECTIONS_API UReflectionsSpellRecipeRelay : public UObject
{
    GENERATED_BODY()

public:
    using FDone = TFunction<void(bool bOk, const FCraftedSpellRecipe& Recipe, const FString& Message)>;

    /** True when this build may use the relay and its local token is configured. */
    static bool IsConfigured();

    /** Sends Text; Done runs on the game thread exactly once. */
    void Request(const FString& Text, FDone Done);

    virtual void BeginDestroy() override;

private:
    void Finish(bool bOk, const FCraftedSpellRecipe& Recipe, const FString& Message);
    TSharedPtr<IWebSocket> Socket;
    FDone Pending;
    double StartedAt = 0.0;
};
