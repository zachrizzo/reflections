#include "SpellCrafting/ReflectionsSpellCraftingLibrary.h"

#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Policies/CondensedJsonPrintPolicy.h"

namespace
{
    using EForm = ECraftedSpellForm;
    using EElem = ECraftedSpellElement;
    using EMod = ECraftedSpellModifier;
    using ETrig = ECraftedSpellTrigger;
    using ESyn = ECraftedSpellSynergy;

    template <typename TEnum>
    int32 Count() { return static_cast<int32>(TEnum::MAX); }

    /** Small deterministic generator (SplitMix-style) so looks and names never depend on FMath::Rand. */
    struct FSeeded
    {
        uint32 State;
        explicit FSeeded(uint32 Seed) : State(Seed ? Seed : 0x9E3779B9u) {}
        uint32 Next()
        {
            State += 0x9E3779B9u;
            uint32 Z = State;
            Z = (Z ^ (Z >> 16)) * 0x85EBCA6Bu;
            Z = (Z ^ (Z >> 13)) * 0xC2B2AE35u;
            return Z ^ (Z >> 16);
        }
        float Unit() { return (Next() & 0xFFFFFF) / float(0x1000000); }
        float Range(float A, float B) { return FMath::Lerp(A, B, Unit()); }
        int32 Pick(int32 N) { return N > 0 ? int32(Next() % uint32(N)) : 0; }
    };

    struct FFormBase
    {
        float Damage, Radius, Speed, Range, Lifetime, Cost, Cooldown, Impulse, Collision, Cone, Pulse;
    };

    const FFormBase& BaseFor(EForm Form)
    {
        static const FFormBase Bases[] = {
            /* Bolt */ {14.0f, 70.0f, 2300.0f, 2600.0f, 0.0f, 9.0f, 0.25f, 120.0f, 12.0f, 0.0f, 0.0f},
            /* Orb  */ {22.0f, 260.0f, 620.0f, 2200.0f, 0.0f, 16.0f, 1.2f, 300.0f, 30.0f, 0.0f, 0.0f},
            /* Ray  */ {15.0f, 50.0f, 26000.0f, 3400.0f, 0.0f, 12.0f, 0.5f, 80.0f, 6.0f, 0.0f, 0.0f},
            /* Nova */ {20.0f, 340.0f, 0.0f, 1800.0f, 0.6f, 17.0f, 2.0f, 650.0f, 0.0f, 0.0f, 0.0f},
            /* Wave */ {13.0f, 950.0f, 1500.0f, 950.0f, 0.7f, 15.0f, 1.6f, 900.0f, 0.0f, 70.0f, 0.0f},
            /* Rain */ {5.0f, 380.0f, 0.0f, 1800.0f, 4.0f, 24.0f, 5.0f, 60.0f, 0.0f, 0.0f, 0.14f},
            /* Rune */ {30.0f, 300.0f, 0.0f, 1800.0f, 14.0f, 15.0f, 2.5f, 700.0f, 0.0f, 0.0f, 0.0f},
            /* Aura */ {6.0f, 330.0f, 0.0f, 0.0f, 5.0f, 22.0f, 5.0f, 200.0f, 0.0f, 0.0f, 0.5f},
        };
        static_assert(UE_ARRAY_COUNT(Bases) == static_cast<int32>(EForm::MAX), "Every form needs base stats");
        return Bases[FMath::Clamp(static_cast<int32>(Form), 0, Count<EForm>() - 1)];
    }

    float ModifierCost(EMod Mod)
    {
        switch (Mod)
        {
        case EMod::Split: return 1.35f;
        case EMod::Bounce: return 1.2f;
        case EMod::Pierce: return 1.2f;
        case EMod::Chain: return 1.35f;
        case EMod::Gravity: return 1.4f;
        case EMod::Delayed: return 1.1f;
        case EMod::Hazard: return 1.3f;
        case EMod::Leech: return 1.25f;
        case EMod::Homing: return 1.15f;
        case EMod::Orbit: return 1.25f;
        case EMod::Echo: return 1.6f;
        default: return 1.0f;
        }
    }

    bool IsFieldForm(EForm Form)
    {
        return Form == EForm::Nova || Form == EForm::Wave || Form == EForm::Rain || Form == EForm::Rune || Form == EForm::Aura;
    }

    /** Pulsing is the natural rhythm of rain and auras; on other forms it is an upgrade with a price. */
    bool PulseIsNative(EForm Form) { return Form == EForm::Rain || Form == EForm::Aura; }

    // ---------------------------------------------------------------------------------------------- words
    const TCHAR* ElementWords[][4] = {
        {TEXT("Ember"), TEXT("Cinder"), TEXT("Blazing"), TEXT("Pyre")},
        {TEXT("Frost"), TEXT("Rime"), TEXT("Glacial"), TEXT("Hoarfrost")},
        {TEXT("Storm"), TEXT("Volt"), TEXT("Thunder"), TEXT("Galvanic")},
        {TEXT("Tidal"), TEXT("Brine"), TEXT("Torrent"), TEXT("Mist")},
        {TEXT("Stone"), TEXT("Granite"), TEXT("Quake"), TEXT("Iron")},
        {TEXT("Gale"), TEXT("Zephyr"), TEXT("Squall"), TEXT("Tempest")},
        {TEXT("Arcane"), TEXT("Astral"), TEXT("Void"), TEXT("Runic")},
        {TEXT("Verdant"), TEXT("Blessed"), TEXT("Dawn"), TEXT("Mending")},
    };
    const TCHAR* FormWords[][3] = {
        {TEXT("Bolt"), TEXT("Dart"), TEXT("Shard")},
        {TEXT("Orb"), TEXT("Sphere"), TEXT("Moon")},
        {TEXT("Ray"), TEXT("Beam"), TEXT("Lance")},
        {TEXT("Nova"), TEXT("Burst"), TEXT("Bloom")},
        {TEXT("Wave"), TEXT("Surge"), TEXT("Crescent")},
        {TEXT("Rain"), TEXT("Downpour"), TEXT("Deluge")},
        {TEXT("Rune"), TEXT("Sigil"), TEXT("Glyph")},
        {TEXT("Aura"), TEXT("Mantle"), TEXT("Halo")},
    };
    const TCHAR* ModifierAdjectives[][3] = {
        {TEXT(""), TEXT(""), TEXT("")},
        {TEXT("Splintering"), TEXT("Forking"), TEXT("Scattering")},
        {TEXT("Ricocheting"), TEXT("Skipping"), TEXT("Rebounding")},
        {TEXT("Piercing"), TEXT("Lancing"), TEXT("Boring")},
        {TEXT("Chaining"), TEXT("Leaping"), TEXT("Arcing")},
        {TEXT("Gravitic"), TEXT("Devouring"), TEXT("Abyssal")},
        {TEXT("Fused"), TEXT("Brooding"), TEXT("Patient")},
        {TEXT("Lingering"), TEXT("Festering"), TEXT("Pooling")},
        {TEXT("Vampiric"), TEXT("Thirsting"), TEXT("Leeching")},
        {TEXT("Seeking"), TEXT("Hunting"), TEXT("Faithful")},
        {TEXT("Orbiting"), TEXT("Circling"), TEXT("Loyal")},
        {TEXT("Echoing"), TEXT("Twin"), TEXT("Resounding")},
    };
    const TCHAR* ModifierNouns[][2] = {
        {TEXT(""), TEXT("")},
        {TEXT("Shards"), TEXT("Many")},
        {TEXT("Ricochets"), TEXT("Rebounds")},
        {TEXT("Piercing"), TEXT("the Needle")},
        {TEXT("Chains"), TEXT("the Leap")},
        {TEXT("the Abyss"), TEXT("Gravity")},
        {TEXT("Reckoning"), TEXT("the Fuse")},
        {TEXT("Ruin"), TEXT("the Mire")},
        {TEXT("Thirst"), TEXT("the Leech")},
        {TEXT("the Hunt"), TEXT("Pursuit")},
        {TEXT("Orbits"), TEXT("the Moon")},
        {TEXT("Echoes"), TEXT("Twins")},
    };

    /** Synergies with a name strong enough to replace the form noun. */
    const TCHAR* SynergyTitle(ESyn Synergy)
    {
        switch (Synergy)
        {
        case ESyn::StormEye: return TEXT("Eye of the Storm");
        case ESyn::Shatterstorm: return TEXT("Shatterstorm");
        case ESyn::Swarm: return TEXT("Swarm");
        case ESyn::Implosion: return TEXT("Implosion");
        case ESyn::Sinkhole: return TEXT("Sinkhole");
        case ESyn::Conductor: return TEXT("Conductor");
        case ESyn::Satellites: return TEXT("Satellites");
        case ESyn::Cascade: return TEXT("Cascade");
        case ESyn::Whirlpool: return TEXT("Maelstrom");
        case ESyn::Updraft: return TEXT("Cyclone");
        case ESyn::Boulder: return TEXT("Boulder");
        case ESyn::Wildfire: return TEXT("Wildfire");
        case ESyn::Permafrost: return TEXT("Permafrost");
        default: return nullptr;
        }
    }

    FString Capitalised(FString S)
    {
        if (!S.IsEmpty()) S[0] = FChar::ToUpper(S[0]);
        return S;
    }

    FString Num0(float V) { return FString::Printf(TEXT("%d"), FMath::RoundToInt(V)); }
    FString Num1(float V) { return FString::Printf(TEXT("%.1f"), V); }

    // ---------------------------------------------------------------------------------------------- look
    float ElementHue(EElem Element)
    {
        switch (Element)
        {
        case EElem::Fire: return 0.035f;
        case EElem::Ice: return 0.54f;
        case EElem::Lightning: return 0.64f;
        case EElem::Water: return 0.585f;
        case EElem::Earth: return 0.085f;
        case EElem::Air: return 0.46f;
        case EElem::Arcane: return 0.79f;
        case EElem::Life: return 0.27f;
        default: return 0.0f;
        }
    }

    FLinearColor Hsv(float H, float S, float V)
    {
        H = FMath::Frac(H);
        return FLinearColor(H * 360.0f, FMath::Clamp(S, 0.0f, 1.0f), FMath::Max(V, 0.0f)).HSVToLinearRGB();
    }

    FCraftedSpellLook BuildLook(const FCraftedSpellResolved& R, int32 Seed)
    {
        const FCraftedSpellRecipe& Rec = R.Recipe;
        FSeeded Rng(uint32(Seed) * 2654435761u + 17u);
        FCraftedSpellLook L;
        L.Seed = Seed;
        // Colour ramp: stay in the element's family, but every recipe and variant lands somewhere new.
        const float Variant = FMath::Frac(Rec.LookVariant * 0.61803398875f) * (Rec.LookVariant ? 1.0f : 0.0f);
        const float Hue = ElementHue(Rec.Element) + Rng.Range(-0.05f, 0.05f) + (Variant - 0.5f) * (Rec.LookVariant ? 0.22f : 0.0f);
        const float Accent = (Rng.Unit() < 0.5f ? -1.0f : 1.0f) * Rng.Range(0.04f, 0.2f);
        const bool bPale = Rec.Element == EElem::Ice || Rec.Element == EElem::Air || Rec.Element == EElem::Lightning;
        L.ColorA = Hsv(Hue, Rng.Range(bPale ? 0.55f : 0.75f, 0.98f), 1.0f);
        L.ColorB = Hsv(Hue + Accent, Rng.Range(0.12f, 0.45f), 1.0f);
        L.ColorC = Hsv(Hue - Accent * 1.6f, Rng.Range(0.6f, 1.0f), Rng.Range(0.18f, 0.45f));
        if (Rec.Element == EElem::Life)
        {
            // Healing reads as warm gold over green.
            L.ColorB = Hsv(0.12f + Rng.Range(-0.02f, 0.03f), 0.45f, 1.0f);
        }

        // Shape: behaviours pull toward a silhouette, the seed picks between near candidates.
        TArray<float, TInlineAllocator<6>> Shapes;
        if (R.HasModifier(EMod::Orbit)) Shapes.Add(1.0f);
        if (R.HasModifier(EMod::Homing)) Shapes.Add(2.0f);
        if (R.HasModifier(EMod::Split) || R.HasModifier(EMod::Pierce)) Shapes.Add(3.0f);
        if (R.HasModifier(EMod::Bounce) || Rec.Element == EElem::Ice || Rec.Element == EElem::Earth) Shapes.Add(4.0f);
        if (R.HasModifier(EMod::Gravity) || R.HasModifier(EMod::Echo)) Shapes.Add(5.0f);
        if (Shapes.Num() == 0) Shapes.Add(float(Rng.Pick(6)));
        L.Shape = Shapes[Rng.Pick(Shapes.Num())] + (Rng.Unit() < 0.3f ? Rng.Range(-0.35f, 0.35f) : 0.0f);
        L.Shape = FMath::Clamp(L.Shape, 0.0f, 5.0f);
        L.Spikes = float(3 + Rng.Pick(5));

        const float PowerScale = 0.8f + 0.1f * (Rec.Power - 1);
        L.Density = Rng.Range(0.55f, 1.6f) * PowerScale;
        switch (Rec.Form)
        {
        case EForm::Orb: L.Size = Rng.Range(46.0f, 70.0f); break;
        case EForm::Ray: L.Size = Rng.Range(10.0f, 18.0f); break;
        case EForm::Bolt: L.Size = Rng.Range(20.0f, 34.0f); break;
        default: L.Size = FMath::Max(R.Radius, 80.0f); break;
        }
        L.Size *= PowerScale;

        L.Swirl = Rng.Range(0.0f, 2.5f);
        if (R.HasModifier(EMod::Gravity)) L.Swirl = Rng.Range(5.0f, 8.0f) * (R.Has(ESyn::Updraft) ? -1.0f : 1.0f);
        if (R.HasModifier(EMod::Orbit)) L.Swirl = FMath::Max(L.Swirl, Rng.Range(3.0f, 5.0f));
        L.Jitter = Rec.Element == EElem::Lightning || R.HasModifier(EMod::Chain) ? Rng.Range(6.0f, 14.0f) : Rng.Range(0.0f, 2.0f);
        L.Turbulence = Rec.Element == EElem::Fire || Rec.Element == EElem::Air ? Rng.Range(280.0f, 520.0f) : Rng.Range(40.0f, 220.0f);
        L.Pulse = Rec.Trigger == ETrig::Pulse && R.PulseInterval > 0.0f ? 1.0f / R.PulseInterval
            : R.HasModifier(EMod::Delayed) ? Rng.Range(3.0f, 6.0f) : Rng.Range(0.0f, 1.5f);
        L.Glow = Rng.Range(0.8f, 1.35f) * (Rec.Element == EElem::Lightning ? 1.4f : 1.0f);
        switch (Rec.Element)
        {
        case EElem::Fire: L.Gravity = -Rng.Range(120.0f, 260.0f); break;
        case EElem::Water: case EElem::Earth: L.Gravity = Rng.Range(500.0f, 1000.0f); break;
        case EElem::Ice: L.Gravity = Rng.Range(150.0f, 350.0f); break;
        case EElem::Life: L.Gravity = -Rng.Range(30.0f, 90.0f); break;
        default: L.Gravity = Rng.Range(-60.0f, 60.0f); break;
        }
        return L;
    }

    // ---------------------------------------------------------------------------------------------- json
    template <typename TEnum>
    FString EnumName(TEnum Value)
    {
        const UEnum* Enum = StaticEnum<TEnum>();
        return Enum ? Enum->GetNameStringByValue(static_cast<int64>(Value)) : FString();
    }

    template <typename TEnum>
    bool EnumFromName(const FString& Name, TEnum& Out)
    {
        const UEnum* Enum = StaticEnum<TEnum>();
        if (!Enum) return false;
        for (int32 i = 0; i < Enum->NumEnums() - 1; ++i)
        {
            if (Enum->GetNameStringByIndex(i).Equals(Name, ESearchCase::IgnoreCase))
            {
                Out = static_cast<TEnum>(Enum->GetValueByIndex(i));
                return true;
            }
        }
        return false;
    }
}

FCraftedSpellRecipe UReflectionsSpellCraftingLibrary::Sanitize(const FCraftedSpellRecipe& In)
{
    FCraftedSpellRecipe Out = In;
    Out.Form = static_cast<EForm>(FMath::Clamp(static_cast<int32>(In.Form), 0, Count<EForm>() - 1));
    Out.Element = static_cast<EElem>(FMath::Clamp(static_cast<int32>(In.Element), 0, Count<EElem>() - 1));
    Out.Trigger = static_cast<ETrig>(FMath::Clamp(static_cast<int32>(In.Trigger), 0, Count<ETrig>() - 1));
    Out.Power = FMath::Clamp(In.Power, 1, 5);
    Out.LookVariant = FMath::Clamp(In.LookVariant, 0, 999);
    Out.CustomName = In.CustomName.Left(40).TrimStartAndEnd();
    Out.Modifiers.Reset();
    for (EMod Mod : In.Modifiers)
    {
        const int32 Index = static_cast<int32>(Mod);
        if (Index <= 0 || Index >= Count<EMod>() || Out.Modifiers.Contains(Mod)) continue;
        Out.Modifiers.Add(Mod);
        if (Out.Modifiers.Num() == 3) break;
    }
    return Out;
}

int32 UReflectionsSpellCraftingLibrary::RecipeSeed(const FCraftedSpellRecipe& InRecipe)
{
    const FCraftedSpellRecipe R = Sanitize(InRecipe);
    // FNV-1a over the fields that define the spell. CustomName is deliberately excluded.
    uint32 Hash = 2166136261u;
    auto Mix = [&Hash](uint32 V) { for (int32 i = 0; i < 4; ++i) { Hash ^= (V >> (i * 8)) & 0xFF; Hash *= 16777619u; } };
    Mix(static_cast<uint32>(R.Form) + 1);
    Mix(static_cast<uint32>(R.Element) + 11);
    for (EMod Mod : R.Modifiers) Mix(static_cast<uint32>(Mod) + 101);
    Mix(static_cast<uint32>(R.Trigger) + 1001);
    Mix(static_cast<uint32>(R.Power) + 10001);
    Mix(static_cast<uint32>(R.LookVariant) + 100001);
    return static_cast<int32>(Hash & 0x7FFFFFFF);
}

FCraftedSpellResolved UReflectionsSpellCraftingLibrary::Resolve(const FCraftedSpellRecipe& InRecipe)
{
    FCraftedSpellResolved R;
    R.Recipe = Sanitize(InRecipe);
    const FCraftedSpellRecipe& Rec = R.Recipe;
    const FFormBase& Base = BaseFor(Rec.Form);
    const int32 P = Rec.Power;
    const bool bField = IsFieldForm(Rec.Form);
    const bool bProjectile = !bField;
    auto Has = [&Rec](EMod Mod) { return Rec.HasModifier(Mod); };

    // ---- synergies first: several of them change the numbers below.
    auto Add = [&R](ESyn Synergy) { R.SynergyMask |= 1 << static_cast<int32>(Synergy); };
    if (Has(EMod::Gravity) && Has(EMod::Chain)) Add(ESyn::StormEye);
    if (Has(EMod::Split) && Has(EMod::Bounce)) Add(ESyn::Shatterstorm);
    if (Has(EMod::Split) && Has(EMod::Homing)) Add(ESyn::Swarm);
    if (Has(EMod::Gravity) && Has(EMod::Delayed)) Add(ESyn::Implosion);
    if (Has(EMod::Gravity) && Has(EMod::Hazard)) Add(ESyn::Sinkhole);
    if (Has(EMod::Pierce) && Has(EMod::Chain)) Add(ESyn::Conductor);
    if (Has(EMod::Orbit) && Has(EMod::Split) && bProjectile) Add(ESyn::Satellites);
    if (Has(EMod::Orbit) && bField) Add(ESyn::Escort);
    if (Has(EMod::Leech) && Has(EMod::Hazard)) Add(ESyn::Bloodbath);
    if (Has(EMod::Homing) && Has(EMod::Bounce)) Add(ESyn::Ricochet);
    if (Has(EMod::Echo) && Has(EMod::Delayed)) Add(ESyn::Cascade);
    if (Rec.Element == EElem::Lightning && Has(EMod::Chain)) Add(ESyn::ArcAffinity);
    if (Rec.Element == EElem::Ice && Has(EMod::Hazard)) Add(ESyn::Permafrost);
    if (Rec.Element == EElem::Fire && Has(EMod::Hazard)) Add(ESyn::Wildfire);
    if (Rec.Element == EElem::Water && Has(EMod::Gravity)) Add(ESyn::Whirlpool);
    if (Rec.Element == EElem::Air && Has(EMod::Gravity)) Add(ESyn::Updraft);
    if (Rec.Element == EElem::Earth && Has(EMod::Bounce)) Add(ESyn::Boulder);
    if (Rec.Element == EElem::Life && (Has(EMod::Hazard) || bField)) Add(ESyn::Sanctuary);

    // ---- form and power.
    const float DamageScale = 0.6f + 0.35f * (P - 1);
    const float SizeScale = 0.8f + 0.125f * (P - 1);
    const float CostScale = 0.5f + 0.4f * (P - 1) + 0.05f * FMath::Square(float(P - 1));
    R.Damage = Base.Damage * DamageScale;
    R.Radius = Base.Radius * SizeScale;
    R.Speed = Base.Speed;
    R.Range = Base.Range;
    R.Lifetime = Base.Lifetime;
    R.Impulse = Base.Impulse;
    R.CollisionRadius = Base.Collision * SizeScale;
    R.ConeDegrees = Base.Cone;
    R.PulseInterval = Base.Pulse;

    // ---- element.
    switch (Rec.Element)
    {
    case EElem::Fire: R.BurnDps = R.Damage * 0.35f; R.StatusSeconds = 3.0f; break;
    case EElem::Ice: R.Damage *= 0.85f; R.SlowFactor = 0.45f; R.StatusSeconds = 2.5f; break;
    case EElem::Lightning: R.Damage *= 0.9f; R.SlowFactor = 0.05f; R.StatusSeconds = 0.35f; R.Speed *= 1.25f; break;
    case EElem::Water: R.Damage *= 0.75f; R.Impulse *= 2.6f; break;
    case EElem::Earth: R.Damage *= 1.3f; R.Impulse *= 1.8f; R.Speed *= 0.8f; break;
    case EElem::Air: R.Damage *= 0.6f; R.Impulse *= 2.2f; R.Lift = 650.0f; R.Speed *= 1.2f; break;
    case EElem::Arcane: R.Damage *= 1.1f; break;
    case EElem::Life: R.Heal = R.Damage * 1.3f; R.Damage *= 0.35f; R.Impulse *= 0.3f; break;
    default: break;
    }

    // ---- trigger.
    float TriggerCost = 1.0f;
    switch (Rec.Trigger)
    {
    case ETrig::Airburst:
        R.Radius = FMath::Max(R.Radius, 120.0f) * 1.25f;
        R.Damage *= 0.9f;
        if (bField) R.StartDelay = 0.6f;
        break;
    case ETrig::Proximity:
        R.ProximityRadius = FMath::Max(260.0f, R.Radius * 0.8f);
        if (bProjectile || Rec.Form == EForm::Nova) R.Lifetime = 10.0f;
        TriggerCost = 1.1f;
        break;
    case ETrig::Pulse:
        if (!PulseIsNative(Rec.Form)) TriggerCost = 1.25f;
        switch (Rec.Form)
        {
        case EForm::Bolt: case EForm::Orb: R.PulseInterval = 0.3f; break;
        case EForm::Ray: R.PulseInterval = 0.2f; R.Lifetime = 1.4f; break;
        case EForm::Nova: R.PulseInterval = 0.45f; R.Lifetime = 1.4f; break;
        case EForm::Wave: R.PulseInterval = 0.35f; R.Lifetime = 0.75f; break;
        case EForm::Rune: R.PulseInterval = 0.8f; break;
        case EForm::Rain: R.PulseInterval = 0.1f; break;
        case EForm::Aura: R.PulseInterval = 0.35f; break;
        default: break;
        }
        break;
    default: break;
    }

    if (bProjectile)
    {
        R.Lifetime = FMath::Max(R.Lifetime, R.Range / FMath::Max(R.Speed, 1.0f) + 0.05f);
    }

    // ---- behaviours.
    float ModCost = 1.0f;
    for (EMod Mod : Rec.Modifiers) ModCost *= ModifierCost(Mod);
    if (Has(EMod::Split)) R.SplitCount = 3 + (P >= 4 ? 1 : 0);
    if (Has(EMod::Bounce)) R.BounceCount = 2 + (P >= 3 ? 1 : 0);
    if (Has(EMod::Pierce)) R.PierceCount = 2 + (P >= 3 ? 1 : 0);
    if (Has(EMod::Chain))
    {
        R.ChainCount = 2 + (P >= 3 ? 1 : 0) + (R.Has(ESyn::ArcAffinity) ? 2 : 0);
        R.ChainRange = 650.0f;
    }
    if (Has(EMod::Gravity))
    {
        R.PullRadius = FMath::Max(R.Radius * 1.8f, 480.0f);
        R.PullStrength = 900.0f * (R.Has(ESyn::Whirlpool) ? 1.7f : 1.0f) * (0.85f + 0.075f * P);
        if (Rec.Form == EForm::Orb) R.Speed *= 0.65f;  // A gravity orb should be slow enough to drag a crowd.
        if (bProjectile) R.Lifetime = FMath::Max(R.Lifetime, R.Range / FMath::Max(R.Speed, 1.0f) + 0.05f);
    }
    if (Has(EMod::Delayed))
    {
        R.FuseTime = 1.2f;
        R.FuseScale = R.Has(ESyn::Implosion) ? 1.9f : 1.6f;
    }
    if (Has(EMod::Hazard))
    {
        R.HazardDuration = 5.0f;
        R.HazardRadius = FMath::Max(R.Radius, 180.0f) * 1.1f;
    }
    if (Has(EMod::Leech)) R.LeechFraction = 0.35f;
    if (Has(EMod::Homing)) R.HomingStrength = Rec.Element == EElem::Arcane ? 6.5f : 4.0f;
    if (Has(EMod::Orbit))
    {
        R.OrbitRadius = 170.0f + R.CollisionRadius;
        R.OrbitDuration = 6.0f;
        if (bField) R.Lifetime *= 1.3f;
    }
    if (Has(EMod::Echo))
    {
        R.EchoCount = R.Has(ESyn::Cascade) ? 2 : 1;
        R.EchoDelay = R.Has(ESyn::Cascade) ? 0.6f : 0.45f;
    }
    if (R.Has(ESyn::Boulder)) { R.Impulse *= 1.5f; R.Speed *= 0.8f; R.CollisionRadius *= 1.6f; }
    if (R.Has(ESyn::Permafrost)) { R.SlowFactor = 0.12f; R.StatusSeconds = 3.0f; }

    // ---- cost, cooldown.
    const int32 Synergies = FMath::CountBits64(static_cast<uint64>(R.SynergyMask));
    const float Resonance = FMath::Pow(1.08f, float(Synergies));
    R.ManaCost = FMath::Clamp(FMath::RoundToFloat(Base.Cost * CostScale * ModCost * TriggerCost * Resonance), 4.0f, 95.0f);
    R.Cooldown = Base.Cooldown * (0.75f + 0.1f * P) + 0.25f * Rec.Modifiers.Num();

    // ---- name.
    const int32 Seed = RecipeSeed(Rec);
    FSeeded Words(uint32(Seed) ^ 0xA5A5A5A5u);
    const int32 E = static_cast<int32>(Rec.Element);
    const int32 F = static_cast<int32>(Rec.Form);
    FString ElementWord = ElementWords[E][Words.Pick(4)];
    FString FormWord = FormWords[F][Words.Pick(3)];
    if (Rec.Element == EElem::Ice && Rec.Form == EForm::Bolt && Words.Unit() < 0.5f) FormWord = TEXT("Splinter");
    const TCHAR* Title = nullptr;
    for (int32 S = 0; S < static_cast<int32>(ESyn::MAX) && !Title; ++S)
    {
        if (R.Has(static_cast<ESyn>(S))) Title = SynergyTitle(static_cast<ESyn>(S));
    }
    TArray<EMod> Remaining = Rec.Modifiers;
    FString Name;
    if (Title)
    {
        // A named synergy replaces the noun and consumes the behaviours that made it.
        Name = FString::Printf(TEXT("%s %s"), *ElementWord, Title);
        if (R.Has(ESyn::StormEye)) { Remaining.Remove(EMod::Gravity); Remaining.Remove(EMod::Chain); }
        if (R.Has(ESyn::Shatterstorm)) { Remaining.Remove(EMod::Split); Remaining.Remove(EMod::Bounce); }
        if (R.Has(ESyn::Swarm)) { Remaining.Remove(EMod::Split); Remaining.Remove(EMod::Homing); }
        if (R.Has(ESyn::Implosion)) { Remaining.Remove(EMod::Gravity); Remaining.Remove(EMod::Delayed); }
        if (R.Has(ESyn::Sinkhole)) { Remaining.Remove(EMod::Gravity); Remaining.Remove(EMod::Hazard); }
        if (R.Has(ESyn::Conductor)) { Remaining.Remove(EMod::Pierce); Remaining.Remove(EMod::Chain); }
        if (R.Has(ESyn::Satellites)) { Remaining.Remove(EMod::Orbit); Remaining.Remove(EMod::Split); }
        if (R.Has(ESyn::Cascade)) { Remaining.Remove(EMod::Echo); Remaining.Remove(EMod::Delayed); }
        if (R.Has(ESyn::Whirlpool) || R.Has(ESyn::Updraft)) Remaining.Remove(EMod::Gravity);
        if (R.Has(ESyn::Boulder)) Remaining.Remove(EMod::Bounce);
        if (R.Has(ESyn::Wildfire) || R.Has(ESyn::Permafrost)) Remaining.Remove(EMod::Hazard);
        if (Remaining.Num() > 0)
        {
            Name = FString::Printf(TEXT("%s %s"), ModifierAdjectives[static_cast<int32>(Remaining[0])][Words.Pick(3)], *Name);
            Remaining.RemoveAt(0);
        }
    }
    else if (Remaining.Num() > 0)
    {
        Name = FString::Printf(TEXT("%s %s %s"), ModifierAdjectives[static_cast<int32>(Remaining[0])][Words.Pick(3)], *ElementWord, *FormWord);
        Remaining.RemoveAt(0);
    }
    else
    {
        Name = FString::Printf(TEXT("%s %s"), *ElementWord, *FormWord);
    }
    if (Remaining.Num() == 1)
    {
        Name += FString::Printf(TEXT(" of %s"), ModifierNouns[static_cast<int32>(Remaining[0])][Words.Pick(2)]);
    }
    else if (Remaining.Num() >= 2)
    {
        Name += FString::Printf(TEXT(" of %s and %s"), ModifierNouns[static_cast<int32>(Remaining[0])][0], ModifierNouns[static_cast<int32>(Remaining[1])][0]);
    }
    if (P == 1) Name = TEXT("Lesser ") + Name;
    if (P == 5) Name = TEXT("Grand ") + Name;
    R.Name = Rec.CustomName.IsEmpty() ? Name : Rec.CustomName;

    // ---- description.
    TArray<FString> Lines;
    static const TCHAR* FormLines[] = {
        TEXT("A fast bolt"), TEXT("A slow, heavy orb"), TEXT("A searing ray"), TEXT("A nova that erupts where you aim"),
        TEXT("A wave that rolls out in front of you"), TEXT("A cloud that rains down on an area"), TEXT("A rune laid on the ground"),
        TEXT("An aura that surrounds you")};
    static const TCHAR* ElementLines[] = {
        TEXT("of fire that sets targets burning"), TEXT("of frost that slows what it touches"), TEXT("of lightning that stuns"),
        TEXT("of water that hurls targets back"), TEXT("of stone that hits like a hammer"), TEXT("of wind that throws targets into the air"),
        TEXT("of raw arcane force"), TEXT("of life that heals you and your allies")};
    Lines.Add(FString::Printf(TEXT("%s %s."), FormLines[F], ElementLines[E]));
    switch (Rec.Trigger)
    {
    case ETrig::Airburst: Lines.Add(bField ? TEXT("Erupts after a short fuse.") : TEXT("Bursts at the aim point, even in mid-air.")); break;
    case ETrig::Proximity: Lines.Add(TEXT("Arms and waits until an enemy comes close.")); break;
    case ETrig::Pulse: if (!PulseIsNative(Rec.Form)) Lines.Add(FString::Printf(TEXT("Pulses every %s s while it lives."), *Num1(R.PulseInterval))); break;
    default: break;
    }
    for (EMod Mod : Rec.Modifiers)
    {
        switch (Mod)
        {
        case EMod::Split: Lines.Add(FString::Printf(TEXT("Throws %d shards when it fires."), R.SplitCount)); break;
        case EMod::Bounce: Lines.Add(bField ? FString::Printf(TEXT("Hops to the nearest enemy up to %d times."), R.BounceCount)
            : FString::Printf(TEXT("Ricochets up to %d times."), R.BounceCount)); break;
        case EMod::Pierce: Lines.Add(bField ? TEXT("Fires a piercing lance at the nearest enemy each pulse.")
            : FString::Printf(TEXT("Passes through up to %d enemies."), R.PierceCount)); break;
        case EMod::Chain: Lines.Add(FString::Printf(TEXT("Arcs to %d more enemies."), R.ChainCount)); break;
        case EMod::Gravity: Lines.Add(R.Has(ESyn::Updraft) ? TEXT("Lifts nearby enemies off their feet.") : TEXT("Drags nearby enemies toward it.")); break;
        case EMod::Delayed: Lines.Add(FString::Printf(TEXT("Waits %s s, then detonates %d%% harder."), *Num1(R.FuseTime), FMath::RoundToInt((R.FuseScale - 1.0f) * 100.0f))); break;
        case EMod::Hazard: Lines.Add(FString::Printf(TEXT("Leaves a pool that lasts %s s."), *Num0(R.HazardDuration))); break;
        case EMod::Leech: Lines.Add(FString::Printf(TEXT("Heals you for %d%% of the damage dealt."), FMath::RoundToInt(R.LeechFraction * 100.0f))); break;
        case EMod::Homing: Lines.Add(bField ? TEXT("Drifts toward the nearest enemy.") : TEXT("Seeks the nearest enemy.")); break;
        case EMod::Orbit: Lines.Add(bField ? TEXT("Follows you.") : FString::Printf(TEXT("Circles you for %s s, then launches at an enemy."), *Num0(R.OrbitDuration))); break;
        case EMod::Echo: Lines.Add(R.EchoCount > 1 ? TEXT("Recasts itself twice, weaker each time.") : TEXT("Recasts itself once, weaker.")); break;
        default: break;
        }
    }
    if (R.Heal > 0.0f) Lines.Add(FString::Printf(TEXT("Heals %s, deals %s."), *Num0(R.Heal), *Num0(R.Damage)));
    else Lines.Add(FString::Printf(TEXT("Deals %s damage."), *Num0(R.Damage)));
    R.Description = FString::Join(Lines, TEXT(" "));

    for (int32 S = 0; S < static_cast<int32>(ESyn::MAX); ++S)
    {
        if (R.Has(static_cast<ESyn>(S))) R.SynergyNotes.Add(SynergyLabel(static_cast<ESyn>(S)));
    }

    R.Look = BuildLook(R, Seed);
    return R;
}

FString UReflectionsSpellCraftingLibrary::FormLabel(ECraftedSpellForm Form)
{
    static const TCHAR* Labels[] = {TEXT("Bolt"), TEXT("Orb"), TEXT("Ray"), TEXT("Nova"), TEXT("Wave"), TEXT("Rain"), TEXT("Rune"), TEXT("Aura")};
    return Labels[FMath::Clamp(static_cast<int32>(Form), 0, Count<EForm>() - 1)];
}

FString UReflectionsSpellCraftingLibrary::ElementLabel(ECraftedSpellElement Element)
{
    static const TCHAR* Labels[] = {TEXT("Fire"), TEXT("Ice"), TEXT("Lightning"), TEXT("Water"), TEXT("Earth"), TEXT("Air"), TEXT("Arcane"), TEXT("Life")};
    return Labels[FMath::Clamp(static_cast<int32>(Element), 0, Count<EElem>() - 1)];
}

FString UReflectionsSpellCraftingLibrary::ModifierLabel(ECraftedSpellModifier Modifier)
{
    static const TCHAR* Labels[] = {TEXT("None"), TEXT("Split"), TEXT("Bounce"), TEXT("Pierce"), TEXT("Chain"), TEXT("Gravity Pull"),
        TEXT("Delayed Detonation"), TEXT("Leaves Hazard"), TEXT("Heal on Hit"), TEXT("Homing"), TEXT("Orbiting"), TEXT("Echo")};
    return Labels[FMath::Clamp(static_cast<int32>(Modifier), 0, Count<EMod>() - 1)];
}

FString UReflectionsSpellCraftingLibrary::TriggerLabel(ECraftedSpellTrigger Trigger)
{
    static const TCHAR* Labels[] = {TEXT("On Impact"), TEXT("Airburst"), TEXT("Proximity"), TEXT("Pulse")};
    return Labels[FMath::Clamp(static_cast<int32>(Trigger), 0, Count<ETrig>() - 1)];
}

FString UReflectionsSpellCraftingLibrary::SynergyLabel(ECraftedSpellSynergy Synergy)
{
    switch (Synergy)
    {
    case ESyn::StormEye: return TEXT("Eye of the Storm: arcs leap between everything caught in the pull");
    case ESyn::Shatterstorm: return TEXT("Shatterstorm: splits again on every bounce");
    case ESyn::Swarm: return TEXT("Swarm: each shard hunts a different enemy");
    case ESyn::Implosion: return TEXT("Implosion: pulls enemies in during the fuse, then detonates harder");
    case ESyn::Sinkhole: return TEXT("Sinkhole: the pool keeps pulling enemies in");
    case ESyn::Conductor: return TEXT("Conductor: every enemy pierced also chains");
    case ESyn::Satellites: return TEXT("Satellites: several shards orbit you at once");
    case ESyn::Escort: return TEXT("Escort: the field travels with you");
    case ESyn::Bloodbath: return TEXT("Bloodbath: the pool feeds you as it burns");
    case ESyn::Ricochet: return TEXT("Ricochet: re-targets after every bounce");
    case ESyn::Cascade: return TEXT("Cascade: echoes detonate in a staggered rhythm");
    case ESyn::ArcAffinity: return TEXT("Arc Affinity: lightning chains two extra times");
    case ESyn::Permafrost: return TEXT("Permafrost: the pool nearly freezes enemies");
    case ESyn::Wildfire: return TEXT("Wildfire: the pool spreads as it burns");
    case ESyn::Whirlpool: return TEXT("Maelstrom: water pulls far harder");
    case ESyn::Updraft: return TEXT("Cyclone: wind lifts enemies instead of pulling them");
    case ESyn::Boulder: return TEXT("Boulder: earth bounces heavy and slow");
    case ESyn::Sanctuary: return TEXT("Sanctuary: allies standing in it are healed");
    default: return FString();
    }
}

FString UReflectionsSpellCraftingLibrary::FormHint(ECraftedSpellForm Form)
{
    switch (Form)
    {
    case EForm::Bolt: return TEXT("Fast, cheap projectile.");
    case EForm::Orb: return TEXT("Slow, heavy projectile with a big blast.");
    case EForm::Ray: return TEXT("Near-instant beam along the reticle.");
    case EForm::Nova: return TEXT("Erupts on the ground where you aim.");
    case EForm::Wave: return TEXT("Cone that rolls out in front of you.");
    case EForm::Rain: return TEXT("Cloud that strikes an area over time.");
    case EForm::Rune: return TEXT("Trap that waits on the ground.");
    case EForm::Aura: return TEXT("Field around you for a few seconds.");
    default: return FString();
    }
}

FString UReflectionsSpellCraftingLibrary::ElementHint(ECraftedSpellElement Element)
{
    switch (Element)
    {
    case EElem::Fire: return TEXT("Burns over time.");
    case EElem::Ice: return TEXT("Slows targets.");
    case EElem::Lightning: return TEXT("Stuns briefly, faster, chains further.");
    case EElem::Water: return TEXT("Heavy knockback.");
    case EElem::Earth: return TEXT("Heavy damage, slower.");
    case EElem::Air: return TEXT("Throws targets up and away.");
    case EElem::Arcane: return TEXT("Pure damage, tracks well.");
    case EElem::Life: return TEXT("Heals you and allies; weak against enemies.");
    default: return FString();
    }
}

FString UReflectionsSpellCraftingLibrary::ModifierHint(ECraftedSpellModifier Modifier)
{
    switch (Modifier)
    {
    case EMod::None: return TEXT("No behaviour in this slot.");
    case EMod::Split: return TEXT("Throws shards when the payload fires.");
    case EMod::Bounce: return TEXT("Projectiles ricochet; fields hop toward enemies.");
    case EMod::Pierce: return TEXT("Projectiles pass through; fields fire a piercing lance.");
    case EMod::Chain: return TEXT("Arcs to nearby enemies.");
    case EMod::Gravity: return TEXT("Pulls enemies toward the spell.");
    case EMod::Delayed: return TEXT("Waits, then detonates harder.");
    case EMod::Hazard: return TEXT("Leaves a lingering pool.");
    case EMod::Leech: return TEXT("Heals you for part of the damage.");
    case EMod::Homing: return TEXT("Projectiles seek; fields drift toward enemies.");
    case EMod::Orbit: return TEXT("Projectiles circle you; fields follow you.");
    case EMod::Echo: return TEXT("Recasts itself, weaker.");
    default: return FString();
    }
}

FString UReflectionsSpellCraftingLibrary::TriggerHint(ECraftedSpellTrigger Trigger)
{
    switch (Trigger)
    {
    case ETrig::Impact: return TEXT("Fires on contact.");
    case ETrig::Airburst: return TEXT("Fires at the aim point or after a fuse.");
    case ETrig::Proximity: return TEXT("Waits for an enemy to come close.");
    case ETrig::Pulse: return TEXT("Fires repeatedly while it lives.");
    default: return FString();
    }
}

FCraftedSpellRecipe UReflectionsSpellCraftingLibrary::Preset(int32 Index)
{
    FCraftedSpellRecipe R;
    switch (((Index % NumPresets) + NumPresets) % NumPresets)
    {
    case 0: // Bouncing ice splitter.
        R.Form = EForm::Bolt; R.Element = EElem::Ice; R.Modifiers = {EMod::Bounce, EMod::Split}; R.Trigger = ETrig::Impact; R.Power = 2;
        break;
    case 1: // Slow orb that pulls enemies in.
        R.Form = EForm::Orb; R.Element = EElem::Arcane; R.Modifiers = {EMod::Gravity, EMod::Delayed}; R.Trigger = ETrig::Impact; R.Power = 3;
        break;
    case 2: // Healing rain that follows you.
        R.Form = EForm::Rain; R.Element = EElem::Life; R.Modifiers = {EMod::Orbit}; R.Trigger = ETrig::Pulse; R.Power = 2;
        break;
    default: // Storm eye: a lightning orb that pulls and chains.
        R.Form = EForm::Orb; R.Element = EElem::Lightning; R.Modifiers = {EMod::Gravity, EMod::Chain}; R.Trigger = ETrig::Pulse; R.Power = 3;
        break;
    }
    return R;
}

bool UReflectionsSpellCraftingLibrary::ParseDescription(const FString& Text, FCraftedSpellRecipe& Out)
{
    // Words match at the start of a word only ("nice" is not ice, "chair" is not air); punctuation becomes spaces.
    FString T = TEXT(" ") + Text.ToLower() + TEXT(" ");
    for (TCHAR& C : T) if (!FChar::IsAlnum(C)) C = TEXT(' ');
    int32 Hits = 0;
    auto Any = [&T](const TArray<const TCHAR*>& Words)
    {
        for (const TCHAR* W : Words) if (T.Contains(FString(TEXT(" ")) + W)) return true;
        return false;
    };
    FCraftedSpellRecipe R;
    R.Modifiers.Reset();
    R.Power = 2;

    struct FFormWords { EForm Form; TArray<const TCHAR*> Words; };
    const FFormWords Forms[] = {
        {EForm::Rain, {TEXT("rain"), TEXT("downpour"), TEXT("storm cloud"), TEXT("cloud"), TEXT("hail"), TEXT("meteor")}},
        {EForm::Aura, {TEXT("aura"), TEXT("around me"), TEXT("around you"), TEXT("mantle"), TEXT("halo"), TEXT("cloak")}},
        {EForm::Rune, {TEXT("rune"), TEXT("trap"), TEXT("mine"), TEXT("sigil"), TEXT("glyph")}},
        {EForm::Wave, {TEXT("wave"), TEXT("cone"), TEXT("sweep"), TEXT("surge"), TEXT("breath")}},
        {EForm::Nova, {TEXT("nova"), TEXT("explosion"), TEXT("burst"), TEXT("eruption"), TEXT("shockwave")}},
        {EForm::Ray, {TEXT("ray"), TEXT("beam"), TEXT("laser"), TEXT("lance")}},
        {EForm::Orb, {TEXT("orb"), TEXT("sphere"), TEXT("ball"), TEXT("globe"), TEXT("moon")}},
        {EForm::Bolt, {TEXT("bolt"), TEXT("dart"), TEXT("arrow"), TEXT("shard"), TEXT("missile"), TEXT("splitter"), TEXT("spike")}},
    };
    for (const FFormWords& F : Forms) if (Any(F.Words)) { R.Form = F.Form; ++Hits; break; }

    struct FElemWords { EElem Element; TArray<const TCHAR*> Words; };
    const FElemWords Elements[] = {
        {EElem::Life, {TEXT("heal"), TEXT("life"), TEXT("restor"), TEXT("mend"), TEXT("holy"), TEXT("bless")}},
        {EElem::Lightning, {TEXT("lightning"), TEXT("thunder"), TEXT("electric"), TEXT("shock"), TEXT("spark"), TEXT("volt")}},
        {EElem::Ice, {TEXT("ice"), TEXT("frost"), TEXT("freez"), TEXT("cold"), TEXT("snow"), TEXT("glacial")}},
        {EElem::Fire, {TEXT("fire"), TEXT("flame"), TEXT("burn"), TEXT("ember"), TEXT("lava"), TEXT("magma"), TEXT("inferno")}},
        {EElem::Water, {TEXT("water"), TEXT("tide"), TEXT("tidal"), TEXT("wave of water"), TEXT("ocean"), TEXT("bubble")}},
        {EElem::Earth, {TEXT("earth"), TEXT("stone"), TEXT("rock"), TEXT("boulder"), TEXT("quake"), TEXT("mud")}},
        {EElem::Air, {TEXT("wind"), TEXT("air"), TEXT("gust"), TEXT("tornado"), TEXT("cyclone"), TEXT("gale")}},
        {EElem::Arcane, {TEXT("arcane"), TEXT("void"), TEXT("magic"), TEXT("astral"), TEXT("shadow"), TEXT("star")}},
    };
    for (const FElemWords& E : Elements) if (Any(E.Words)) { R.Element = E.Element; ++Hits; break; }

    struct FModWords { EMod Mod; TArray<const TCHAR*> Words; };
    const FModWords Mods[] = {
        {EMod::Gravity, {TEXT("pull"), TEXT("gravity"), TEXT("vortex"), TEXT("black hole"), TEXT("suck"), TEXT("drag")}},
        {EMod::Bounce, {TEXT("bounc"), TEXT("ricochet"), TEXT("rebound"), TEXT("skip")}},
        {EMod::Split, {TEXT("split"), TEXT("shatter"), TEXT("fork"), TEXT("scatter"), TEXT("cluster"), TEXT("fragment")}},
        {EMod::Chain, {TEXT("chain"), TEXT("jump"), TEXT("arc to"), TEXT("leap")}},
        {EMod::Pierce, {TEXT("pierc"), TEXT("through"), TEXT("penetrat"), TEXT("drill")}},
        {EMod::Delayed, {TEXT("delay"), TEXT("timer"), TEXT("fuse"), TEXT("after a"), TEXT("detonat"), TEXT("sticky")}},
        {EMod::Hazard, {TEXT("pool"), TEXT("puddle"), TEXT("lingering"), TEXT("leaves"), TEXT("patch"), TEXT("burning ground")}},
        {EMod::Leech, {TEXT("leech"), TEXT("drain"), TEXT("vampir"), TEXT("steal"), TEXT("lifesteal"), TEXT("on hit")}},
        {EMod::Homing, {TEXT("hom"), TEXT("seek"), TEXT("track"), TEXT("hunt"), TEXT("guided")}},
        {EMod::Orbit, {TEXT("orbit"), TEXT("circl"), TEXT("follow"), TEXT("around me"), TEXT("around you"), TEXT("guard")}},
        {EMod::Echo, {TEXT("echo"), TEXT("twice"), TEXT("repeat"), TEXT("double"), TEXT("again")}},
    };
    for (const FModWords& M : Mods)
    {
        if (R.Modifiers.Num() < 3 && Any(M.Words)) { R.Modifiers.Add(M.Mod); ++Hits; }
    }
    // "Leaves" alone is too common to count as a hazard when the form already explains it.
    if (R.Form == EForm::Rune) R.Modifiers.Remove(EMod::Hazard);

    if (Any({TEXT("mine"), TEXT("when close"), TEXT("proxim"), TEXT("wait"), TEXT("trap")})) { R.Trigger = ETrig::Proximity; ++Hits; }
    else if (Any({TEXT("pulse"), TEXT("repeated"), TEXT("keeps"), TEXT("over time"), TEXT("every")}) || R.Form == EForm::Rain || R.Form == EForm::Aura)
    {
        R.Trigger = ETrig::Pulse;
    }
    else if (Any({TEXT("airburst"), TEXT("mid air"), TEXT("midair"), TEXT("in the air"), TEXT("explode at")})) { R.Trigger = ETrig::Airburst; ++Hits; }

    if (Any({TEXT("tiny"), TEXT("weak"), TEXT("small"), TEXT("quick"), TEXT("cheap")})) R.Power = 1;
    if (Any({TEXT("big"), TEXT("strong"), TEXT("large"), TEXT("powerful"), TEXT("heavy")})) R.Power = 3;
    if (Any({TEXT("huge"), TEXT("massive"), TEXT("devastating"), TEXT("ultimate"), TEXT("enormous")})) R.Power = 4;
    if (Any({TEXT("slow"), TEXT("lumbering")}) && R.Form == EForm::Bolt) R.Form = EForm::Orb;

    if (Hits == 0) return false;
    if (R.Modifiers.Num() == 0) R.Modifiers.Add(R.Element == EElem::Life ? EMod::Orbit : EMod::Split);
    Out = Sanitize(R);
    return true;
}

FString UReflectionsSpellCraftingLibrary::ToJson(const FCraftedSpellRecipe& InRecipe)
{
    const FCraftedSpellRecipe R = Sanitize(InRecipe);
    TSharedRef<FJsonObject> Object = MakeShared<FJsonObject>();
    Object->SetStringField(TEXT("form"), EnumName(R.Form));
    Object->SetStringField(TEXT("element"), EnumName(R.Element));
    TArray<TSharedPtr<FJsonValue>> Mods;
    for (EMod Mod : R.Modifiers) Mods.Add(MakeShared<FJsonValueString>(EnumName(Mod)));
    Object->SetArrayField(TEXT("modifiers"), Mods);
    Object->SetStringField(TEXT("trigger"), EnumName(R.Trigger));
    Object->SetNumberField(TEXT("power"), R.Power);
    Object->SetNumberField(TEXT("look"), R.LookVariant);
    if (!R.CustomName.IsEmpty()) Object->SetStringField(TEXT("name"), R.CustomName);
    FString Out;
    const TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> Writer = TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Out);
    FJsonSerializer::Serialize(Object, Writer);
    return Out;
}

bool UReflectionsSpellCraftingLibrary::FromJson(const FString& Json, FCraftedSpellRecipe& Out)
{
    TSharedPtr<FJsonObject> Object;
    if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json), Object) || !Object.IsValid()) return false;
    FCraftedSpellRecipe R;
    FString S;
    if (!Object->TryGetStringField(TEXT("form"), S) || !EnumFromName(S, R.Form)) return false;
    if (!Object->TryGetStringField(TEXT("element"), S) || !EnumFromName(S, R.Element)) return false;
    if (Object->TryGetStringField(TEXT("trigger"), S)) EnumFromName(S, R.Trigger);
    const TArray<TSharedPtr<FJsonValue>>* Mods = nullptr;
    if (Object->TryGetArrayField(TEXT("modifiers"), Mods))
    {
        for (const TSharedPtr<FJsonValue>& Value : *Mods)
        {
            EMod Mod;
            if (Value.IsValid() && EnumFromName(Value->AsString(), Mod)) R.Modifiers.Add(Mod);
        }
    }
    double Number = 0.0;
    if (Object->TryGetNumberField(TEXT("power"), Number)) R.Power = FMath::RoundToInt(Number);
    if (Object->TryGetNumberField(TEXT("look"), Number)) R.LookVariant = FMath::RoundToInt(Number);
    Object->TryGetStringField(TEXT("name"), R.CustomName);
    Out = Sanitize(R);
    return true;
}

EHeroSpell UReflectionsSpellCraftingLibrary::AimProxy(ECraftedSpellForm Form)
{
    switch (Form)
    {
    case EForm::Bolt: case EForm::Ray: return EHeroSpell::LightningBolt;  // Projectile, no radius: hit marker.
    case EForm::Orb: return EHeroSpell::Firestorm;                        // Projectile with radius: blast marker.
    case EForm::Wave: return EHeroSpell::TidalSurge;                      // Cone.
    case EForm::Rain: case EForm::Nova: return EHeroSpell::FrostNova;     // Ground area.
    case EForm::Rune: return EHeroSpell::EarthShock;                      // Ground area, smaller.
    case EForm::Aura: return EHeroSpell::HealingPulse;                    // Self.
    default: return EHeroSpell::ArcaneBolt;
    }
}

EHeroSpell UReflectionsSpellCraftingLibrary::EventProxy(ECraftedSpellElement Element)
{
    switch (Element)
    {
    case EElem::Fire: return EHeroSpell::Fire;
    case EElem::Ice: return EHeroSpell::IceShard;
    case EElem::Lightning: return EHeroSpell::LightningBolt;
    case EElem::Water: return EHeroSpell::Water;
    case EElem::Earth: return EHeroSpell::StoneShard;
    case EElem::Air: return EHeroSpell::ForcePush;
    case EElem::Life: return EHeroSpell::Healing;
    default: return EHeroSpell::ArcaneBolt;
    }
}

void UReflectionsSpellCraftingLibrary::GestureCandidates(ECraftedSpellForm Form, int32 CastCount, TArray<FName>& Out)
{
    // Crafting gestures (generated for this system) first, then the shared combat casts as fallbacks.
    const bool bOdd = (CastCount & 1) != 0;
    switch (Form)
    {
    case EForm::Bolt: Out = {bOdd ? FName("BoltLeft") : FName("BoltRight"), FName("BoltRight")}; break;
    case EForm::Orb: Out = {FName("Conjure"), FName("HeavyPush")}; break;
    case EForm::Ray: Out = {FName("Lance"), FName("BoltRight")}; break;
    case EForm::Nova: Out = {FName("Slam")}; break;
    case EForm::Wave: Out = {FName("Sweep")}; break;
    case EForm::Rain: Out = {FName("SkyCall"), FName("HealRaise")}; break;
    case EForm::Rune: Out = {FName("GroundPlant"), FName("Slam")}; break;
    case EForm::Aura: Out = {FName("Spiral"), FName("HealRaise")}; break;
    default: Out = {FName("BoltRight")}; break;
    }
}
