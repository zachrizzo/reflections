#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Hero/ReflectionsHeroCharacter.h"
#include "SpellCrafting/ReflectionsSpellCraftingTypes.h"
#include "ReflectionsSpellCraftingLibrary.generated.h"

/**
 * Pure functions over the spell-crafting grammar: validation, derived stats, cost, procedural names and looks,
 * plus an offline keyword parser that turns a sentence into a recipe.
 */
UCLASS()
class REFLECTIONS_API UReflectionsSpellCraftingLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    /** Clamps every field, removes None and duplicate behaviours and keeps at most three. */
    UFUNCTION(BlueprintPure, Category="Spell Crafting")
    static FCraftedSpellRecipe Sanitize(const FCraftedSpellRecipe& Recipe);

    /** Derives stats, cost, synergies, name, description and look. Deterministic. */
    UFUNCTION(BlueprintPure, Category="Spell Crafting")
    static FCraftedSpellResolved Resolve(const FCraftedSpellRecipe& Recipe);

    /** Stable 31-bit hash of the recipe's gameplay fields and look variant. */
    UFUNCTION(BlueprintPure, Category="Spell Crafting")
    static int32 RecipeSeed(const FCraftedSpellRecipe& Recipe);

    UFUNCTION(BlueprintPure, Category="Spell Crafting") static FString FormLabel(ECraftedSpellForm Form);
    UFUNCTION(BlueprintPure, Category="Spell Crafting") static FString ElementLabel(ECraftedSpellElement Element);
    UFUNCTION(BlueprintPure, Category="Spell Crafting") static FString ModifierLabel(ECraftedSpellModifier Modifier);
    UFUNCTION(BlueprintPure, Category="Spell Crafting") static FString TriggerLabel(ECraftedSpellTrigger Trigger);
    UFUNCTION(BlueprintPure, Category="Spell Crafting") static FString SynergyLabel(ECraftedSpellSynergy Synergy);

    /** One-line hints shown in the crafting screen. */
    static FString FormHint(ECraftedSpellForm Form);
    static FString ElementHint(ECraftedSpellElement Element);
    static FString ModifierHint(ECraftedSpellModifier Modifier);
    static FString TriggerHint(ECraftedSpellTrigger Trigger);

    /** Starter recipes: 0 bouncing ice splitter, 1 gravity orb, 2 healing rain that follows you, 3 storm-eye orb. */
    UFUNCTION(BlueprintPure, Category="Spell Crafting")
    static FCraftedSpellRecipe Preset(int32 Index);
    static constexpr int32 NumPresets = 4;

    /**
     * Offline: turns a sentence ("a slow orb of lightning that pulls enemies in and chains") into a recipe by
     * keyword matching. Never touches the network. Returns false when nothing in the text was recognised.
     */
    UFUNCTION(BlueprintCallable, Category="Spell Crafting")
    static bool ParseDescription(const FString& Text, FCraftedSpellRecipe& OutRecipe);

    /** Recipe <-> JSON with enum names as strings, used by the save-free share code and the dev relay. */
    static FString ToJson(const FCraftedSpellRecipe& Recipe);
    static bool FromJson(const FString& Json, FCraftedSpellRecipe& OutRecipe);

    /** Catalog spell used to drive the existing aim preview and target resolution for a form. */
    static EHeroSpell AimProxy(ECraftedSpellForm Form);
    /** Catalog spell reported in spell events (NPC reactions, hit VFX) for an element. */
    static EHeroSpell EventProxy(ECraftedSpellElement Element);

    /** Gesture clip names in the order they are preferred for a form; the first one that exists is used. */
    static void GestureCandidates(ECraftedSpellForm Form, int32 CastCount, TArray<FName>& OutNames);
};
