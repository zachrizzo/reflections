#pragma once

#include "CoreMinimal.h"
#include "Hero/ReflectionsHeroCharacter.h"

enum class EReflectionsSpellDelivery : uint8 { Heal, Jump, Projectile, Area, Ward };
enum class EReflectionsSpellElement : uint8 { Life, Air, Water, Fire, Ice, Lightning, Earth, Arcane };

struct FReflectionsSpellSpec
{
    const TCHAR* Name;
    EHeroSpell AnimationFamily;
    EReflectionsSpellElement Element;
    EReflectionsSpellDelivery Delivery;
    float Power;
    float Radius;
    float Speed;
    float Range;
    float Impulse;
    float ManaCost;
    float Cooldown;
};

/** Shared, ordered spell definitions; enum values are deliberately stable for existing assets. */
namespace ReflectionsSpellCatalog
{
    // This is the player's hotbar. Keep the underlying catalog for scripted and crafted spells.
    inline constexpr EHeroSpell PlayerSpells[] = {
        EHeroSpell::Levitation, EHeroSpell::Firestorm, EHeroSpell::Healing, EHeroSpell::Freeze
    };
    constexpr int32 PlayerSpellCount = UE_ARRAY_COUNT(PlayerSpells);
    constexpr float FreezeDuration = 10.0f;
    int32 FindPlayerSpellSlot(EHeroSpell Spell);
    constexpr int32 Count = static_cast<int32>(EHeroSpell::MAX);
    const FReflectionsSpellSpec& Get(EHeroSpell Spell);
    bool IsValid(EHeroSpell Spell);
    /** Signature colour for an element, used by the reticle, ground preview and VFX. */
    FLinearColor ElementColor(EReflectionsSpellElement Element);
}
