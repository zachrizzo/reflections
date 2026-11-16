#include "Hero/ReflectionsSpellCatalog.h"

namespace
{
    using D = EReflectionsSpellDelivery;
    using E = EReflectionsSpellElement;
    using A = EHeroSpell;
    const FReflectionsSpellSpec Specs[] = {
        {TEXT("Healing"), A::Healing, E::Life, D::Heal, 35, 0, 0, 0, 0, 35, 120},
        {TEXT("Magic Jump"), A::Levitation, E::Air, D::Jump, 0, 0, 0, 0, 0, 25, 6},
        {TEXT("Water Bolt"), A::Water, E::Water, D::Projectile, 10, 0, 1250, 2200, 450, 12, 4},
        {TEXT("Fire Bolt"), A::Fire, E::Fire, D::Projectile, 14, 0, 1500, 2400, 380, 15, 4},
        {TEXT("Flame Burst"), A::Fire, E::Fire, D::Area, 16, 260, 0, 0, 120, 27, 6},
        {TEXT("Fireball"), A::Fire, E::Fire, D::Projectile, 20, 220, 850, 1800, 100, 35, 12},
        {TEXT("Ice Shard"), A::Water, E::Ice, D::Projectile, 18, 0, 1800, 2600, 320, 18, 4},
        {TEXT("Frost Nova"), A::Water, E::Ice, D::Area, 12, 360, 0, 0, 140, 30, 7},
        {TEXT("Tidal Surge"), A::Water, E::Water, D::Area, 10, 410, 0, 0, 900, 36, 8},
        {TEXT("Water Orb"), A::Water, E::Water, D::Projectile, 12, 180, 800, 1800, 650, 24, 5},
        {TEXT("Lightning Burst"), A::Fire, E::Lightning, D::Projectile, 11, 340, 2100, 2500, 200, 30, 6},
        {TEXT("Lightning Bolt"), A::Fire, E::Lightning, D::Projectile, 21, 0, 2800, 3200, 260, 24, 5},
        {TEXT("Thunder Wave"), A::Fire, E::Lightning, D::Area, 13, 320, 0, 0, 750, 33, 7},
        {TEXT("Stone Shard"), A::Fire, E::Earth, D::Projectile, 24, 0, 1150, 2000, 650, 27, 5},
        {TEXT("Earth Shock"), A::Fire, E::Earth, D::Area, 19, 250, 0, 0, 500, 33, 7},
        {TEXT("Force Push"), A::Water, E::Arcane, D::Area, 2, 430, 0, 0, 1400, 27, 6},
        {TEXT("Arcane Bolt"), A::Fire, E::Arcane, D::Projectile, 15, 100, 1650, 2500, 340, 18, 4},
        {TEXT("Greater Heal"), A::Healing, E::Life, D::Heal, 70, 0, 0, 0, 0, 53, 10},
        {TEXT("Healing Pulse"), A::Healing, E::Life, D::Heal, 25, 400, 0, 0, 0, 38, 8},
        {TEXT("Arcane Shield"), A::Levitation, E::Arcane, D::Ward, 40, 0, 0, 0, 0, 38, 10},
        {TEXT("Freeze"), A::Water, E::Ice, D::Projectile, 0, 0, 1800, 2600, 0, 22, 10},
    };
    static_assert(UE_ARRAY_COUNT(Specs) == ReflectionsSpellCatalog::Count, "Every spell needs a specification");
}

int32 ReflectionsSpellCatalog::FindPlayerSpellSlot(EHeroSpell Spell)
{
    for (int32 Slot = 0; Slot < PlayerSpellCount; ++Slot)
    {
        if (PlayerSpells[Slot] == Spell) return Slot;
    }
    return INDEX_NONE;
}

bool ReflectionsSpellCatalog::IsValid(EHeroSpell Spell)
{
    return static_cast<uint8>(Spell) < static_cast<uint8>(EHeroSpell::MAX);
}
const FReflectionsSpellSpec& ReflectionsSpellCatalog::Get(EHeroSpell Spell)
{
    return Specs[IsValid(Spell) ? static_cast<uint8>(Spell) : 0];
}

FLinearColor ReflectionsSpellCatalog::ElementColor(EReflectionsSpellElement Element)
{
    switch (Element)
    {
    case EReflectionsSpellElement::Life: return FLinearColor(0.55f, 1.0f, 0.45f);
    case EReflectionsSpellElement::Air: return FLinearColor(0.75f, 0.9f, 1.0f);
    case EReflectionsSpellElement::Water: return FLinearColor(0.15f, 0.5f, 1.0f);
    case EReflectionsSpellElement::Fire: return FLinearColor(1.0f, 0.35f, 0.06f);
    case EReflectionsSpellElement::Ice: return FLinearColor(0.5f, 0.85f, 1.0f);
    case EReflectionsSpellElement::Lightning: return FLinearColor(0.55f, 0.6f, 1.0f);
    case EReflectionsSpellElement::Earth: return FLinearColor(0.9f, 0.6f, 0.28f);
    case EReflectionsSpellElement::Arcane: return FLinearColor(0.75f, 0.3f, 1.0f);
    default: return FLinearColor::White;
    }
}
