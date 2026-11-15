#pragma once

#include "CoreMinimal.h"
#include "ReflectionsSpellCraftingTypes.generated.h"

/**
 * Spell-crafting grammar: Form x Element x 1-3 Behaviours x Trigger x Look, plus a Power tier.
 *
 * A recipe is the only thing a player authors and the only thing saved. Everything else (stats, cost,
 * name, description, synergies and the procedural look) is derived from it deterministically, so the
 * same recipe always produces the same spell on every machine.
 */

/** How the spell is delivered. Each form has its own cast gesture and aim preview. */
UENUM(BlueprintType)
enum class ECraftedSpellForm : uint8
{
    Bolt,   // fast projectile
    Orb,    // slow, heavy projectile
    Ray,    // near-instant beam
    Nova,   // burst at the aim point
    Wave,   // cone travelling out from the caster
    Rain,   // cloud that drops strikes over an area
    Rune,   // trap placed on the ground
    Aura,   // field around the caster
    MAX UMETA(Hidden)
};

/** What the spell does to what it touches, and its colour family. */
UENUM(BlueprintType)
enum class ECraftedSpellElement : uint8
{
    Fire,       // burns over time
    Ice,        // slows
    Lightning,  // stuns, +1 chain jump
    Water,      // heavy knockback
    Earth,      // heavy damage and stagger
    Air,        // throws targets up and away
    Arcane,     // pure damage, tracks well
    Life,       // heals you and allies, weak against enemies
    MAX UMETA(Hidden)
};

/** Behaviours change how the form moves or what its payload spawns. Up to three per spell. */
UENUM(BlueprintType)
enum class ECraftedSpellModifier : uint8
{
    None,
    Split,      // throws shards when the payload fires
    Bounce,     // projectiles ricochet; fields hop toward enemies
    Pierce,     // projectiles pass through; fields fire a piercing lance each pulse
    Chain,      // payload arcs to nearby enemies
    Gravity,    // pulls enemies toward the spell while it exists
    Delayed,    // payload waits, then detonates harder
    Hazard,     // leaves a lingering pool
    Leech,      // heals the caster for part of the damage dealt
    Homing,     // projectiles seek; fields drift toward enemies
    Orbit,      // projectiles circle you; fields follow you
    Echo,       // the spell recasts itself once, weaker
    MAX UMETA(Hidden)
};

/** When the payload fires. */
UENUM(BlueprintType)
enum class ECraftedSpellTrigger : uint8
{
    Impact,     // on contact
    Airburst,   // at the aim point, even in mid-air, or after a short fuse
    Proximity,  // arms and waits for an enemy to come close
    Pulse,      // fires repeatedly while the spell lives
    MAX UMETA(Hidden)
};

/** Combinations that behave as something new rather than the sum of their parts. */
UENUM(BlueprintType)
enum class ECraftedSpellSynergy : uint8
{
    StormEye,       // Gravity + Chain: arcs leap between everything caught in the pull
    Shatterstorm,   // Split + Bounce: splits again on every bounce
    Swarm,          // Split + Homing: each shard hunts a different enemy
    Implosion,      // Gravity + Delayed: pulls during the fuse, then detonates harder
    Sinkhole,       // Gravity + Hazard: the pool keeps pulling
    Conductor,      // Pierce + Chain: every enemy pierced also chains
    Satellites,     // Orbit + Split: several orbiting satellites
    Escort,         // Orbit on a field: the field travels with you
    Bloodbath,      // Leech + Hazard: the pool feeds you too
    Ricochet,       // Homing + Bounce: re-targets after every bounce
    Cascade,        // Echo + Delayed: echoes detonate in a staggered rhythm
    ArcAffinity,    // Lightning + Chain: two more jumps
    Permafrost,     // Ice + Hazard: the pool nearly freezes enemies
    Wildfire,       // Fire + Hazard: the pool spreads as it burns
    Whirlpool,      // Water + Gravity: much stronger pull
    Updraft,        // Air + Gravity: lifts enemies instead of pulling
    Boulder,        // Earth + Bounce: heavier, slower, hits harder each bounce
    Sanctuary,      // Life + Hazard or Life on a field: heals allies standing in it
    MAX UMETA(Hidden)
};

/** The authored recipe. This is all that is saved; everything else is derived from it. */
USTRUCT(BlueprintType)
struct REFLECTIONS_API FCraftedSpellRecipe
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Spell Crafting")
    ECraftedSpellForm Form = ECraftedSpellForm::Bolt;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Spell Crafting")
    ECraftedSpellElement Element = ECraftedSpellElement::Arcane;

    /** One to three behaviours, in order. None entries are ignored; duplicates are collapsed. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Spell Crafting")
    TArray<ECraftedSpellModifier> Modifiers;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Spell Crafting")
    ECraftedSpellTrigger Trigger = ECraftedSpellTrigger::Impact;

    /** 1 to 5. Raises damage, size and mana cost. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Spell Crafting", meta=(ClampMin="1", ClampMax="5"))
    int32 Power = 2;

    /** Re-rolls the procedural look without changing what the spell does. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Spell Crafting")
    int32 LookVariant = 0;

    /** Optional player-chosen name. Empty uses the generated name. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Spell Crafting")
    FString CustomName;

    bool HasModifier(ECraftedSpellModifier Modifier) const { return Modifiers.Contains(Modifier); }
};

/** Procedural look, fed to the crafted Niagara systems' User.* parameters. Seeded from the recipe. */
USTRUCT(BlueprintType)
struct REFLECTIONS_API FCraftedSpellLook
{
    GENERATED_BODY()

    /** Colour ramp: main, highlight, shadow/tail. */
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") FLinearColor ColorA = FLinearColor::White;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") FLinearColor ColorB = FLinearColor::White;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") FLinearColor ColorC = FLinearColor::Black;
    /** 0 sphere, 1 ring, 2 helix, 3 star, 4 shards, 5 spiral. Fractions blend neighbours. */
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float Shape = 0.0f;
    /** Particle density multiplier. */
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float Density = 1.0f;
    /** Visual size of the body in cm. */
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float Size = 30.0f;
    /** Motion: orbit speed of the shell, positional jitter, curl-noise strength and pulse frequency. */
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float Swirl = 0.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float Jitter = 0.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float Turbulence = 100.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float Pulse = 0.0f;
    /** Star points for shape 3. */
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float Spikes = 5.0f;
    /** Emissive multiplier. */
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float Glow = 1.0f;
    /** Particles fall (+) or rise (-) after they leave the body. */
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float Gravity = 0.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") int32 Seed = 0;
};

/** Everything derived from a recipe: numbers, name, description and look. */
USTRUCT(BlueprintType)
struct REFLECTIONS_API FCraftedSpellResolved
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") FCraftedSpellRecipe Recipe;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") FString Name;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") FString Description;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") TArray<FString> SynergyNotes;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") FCraftedSpellLook Look;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") int32 SynergyMask = 0;

    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float ManaCost = 10.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float Cooldown = 0.5f;

    // Payload.
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float Damage = 10.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float Heal = 0.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float Radius = 0.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float Impulse = 100.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float Lift = 0.0f;

    // Delivery.
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float Speed = 0.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float Range = 2000.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float Lifetime = 3.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float CollisionRadius = 14.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float ConeDegrees = 0.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float PulseInterval = 0.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float ProximityRadius = 0.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float StartDelay = 0.0f;

    // Behaviours.
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") int32 SplitCount = 0;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") int32 BounceCount = 0;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") int32 PierceCount = 0;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") int32 ChainCount = 0;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float ChainRange = 0.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float PullStrength = 0.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float PullRadius = 0.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float FuseTime = 0.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float FuseScale = 1.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float HazardDuration = 0.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float HazardRadius = 0.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float LeechFraction = 0.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float HomingStrength = 0.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float OrbitRadius = 0.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float OrbitDuration = 0.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") int32 EchoCount = 0;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float EchoDelay = 0.45f;

    // Element status.
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float BurnDps = 0.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float SlowFactor = 1.0f;
    UPROPERTY(BlueprintReadOnly, Category="Spell Crafting") float StatusSeconds = 0.0f;

    bool Has(ECraftedSpellSynergy Synergy) const { return (SynergyMask & (1 << static_cast<int32>(Synergy))) != 0; }
    bool HasModifier(ECraftedSpellModifier Modifier) const { return Recipe.HasModifier(Modifier); }
    bool IsField() const
    {
        return Recipe.Form == ECraftedSpellForm::Nova || Recipe.Form == ECraftedSpellForm::Wave || Recipe.Form == ECraftedSpellForm::Rain
            || Recipe.Form == ECraftedSpellForm::Rune || Recipe.Form == ECraftedSpellForm::Aura;
    }
};
