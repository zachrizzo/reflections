#include "NPC/ReflectionsNpcArchetype.h"
#include "Materials/MaterialInterface.h"

#include "Animation/AnimSequence.h"
#include "Engine/StaticMesh.h"
#include "Misc/PackageName.h"

bool UReflectionsNpcArchetype::EvaluateStimulus(const FReflectionsNpcReactionProfile& Profile,
    const FReflectionsNpcStimulus& Stimulus, const FVector& NpcLocation, float InstigatorReputation,
    float& InOutFear, float& InOutAggression, EReflectionsNpcReaction& OutReaction)
{
    if (Profile.NoiseResponse == EReflectionsNpcNoiseResponse::Ignore) return false;
    const float Radius = Stimulus.Radius > 0.0f ? Stimulus.Radius : Profile.AwarenessRadius;
    const float Distance = FVector::Dist(NpcLocation, Stimulus.Location);
    if (Distance > Radius) return false;
    const float Strength = FMath::Clamp((1.0f - Distance / FMath::Max(1.0f, Radius)) * Stimulus.Intensity / 20.0f, 0.0f, 1.0f);
    if (Strength < 0.04f) return false;

    float FearScale = 1.0f;
    switch (Stimulus.Kind)
    {
    case EReflectionsNpcStimulusKind::Death: FearScale = 1.5f; break;
    case EReflectionsNpcStimulusKind::Infection: FearScale = 1.25f; break;
    case EReflectionsNpcStimulusKind::Alarm: FearScale = 0.0f; break;
    default: break;
    }
    InOutFear = FMath::Clamp(InOutFear + Strength * Profile.FearPerNoise * FearScale, 0.0f, 1.0f);

    const bool bDisliked = Profile.bTurnsOnDisliked && InstigatorReputation <= Profile.HostileBelowReputation;
    if (Profile.NoiseResponse == EReflectionsNpcNoiseResponse::Attack || bDisliked)
    {
        InOutAggression = FMath::Clamp(InOutAggression + Strength * Profile.AggressionPerNoise, 0.0f, 1.0f);
        OutReaction = Profile.bCanAttack ? EReflectionsNpcReaction::Attacking : EReflectionsNpcReaction::Defending;
    }
    else if (Profile.NoiseResponse == EReflectionsNpcNoiseResponse::Investigate)
        OutReaction = EReflectionsNpcReaction::Investigating;
    else if (InOutFear > Profile.FleeFearThreshold)
        OutReaction = EReflectionsNpcReaction::Fleeing;
    else
        OutReaction = EReflectionsNpcReaction::Alert;
    return true;
}

EReflectionsNpcReaction UReflectionsNpcArchetype::EvaluateHit(const FReflectionsNpcReactionProfile& Profile,
    float& InOutFear, float& InOutAggression)
{
    InOutFear = FMath::Clamp(InOutFear + Profile.FearPerHit, 0.0f, 1.0f);
    InOutAggression = FMath::Clamp(InOutAggression + Profile.AggressionPerHit, 0.0f, 1.0f);
    const bool bFights = Profile.bFightsBack && Profile.bCanAttack && InOutAggression >= Profile.AttackAggressionThreshold;
    return bFights ? EReflectionsNpcReaction::Attacking : EReflectionsNpcReaction::Fleeing;
}

FVector UReflectionsNpcArchetype::FleeDestination(const FReflectionsNpcReactionProfile& Profile,
    const FVector& NpcLocation, const FVector& ThreatLocation, const FVector& FallbackDirection, uint32 Seed)
{
    FVector Away = (NpcLocation - ThreatLocation).GetSafeNormal2D();
    if (Away.IsNearlyZero()) Away = FallbackDirection.GetSafeNormal2D();
    if (Away.IsNearlyZero()) Away = FVector::ForwardVector;
    const float Variation = static_cast<float>(Seed % 61) - 30.0f;
    return NpcLocation + Away.RotateAngleAxis(Variation, FVector::UpVector) * Profile.FleeDistance;
}

const TArray<FName>& UReflectionsNpcArchetype::BuiltInIds()
{
    static const TArray<FName> Ids = {
        TEXT("Civilian"), TEXT("Timid"), TEXT("Brave"), TEXT("Guard"),
        TEXT("Enemy"), TEXT("Hostile"), TEXT("Soldier"), TEXT("SoldierCaster"), TEXT("Infected"), TEXT("VillainHost"),
        TEXT("AlliedSoldier"), TEXT("AlliedSoldierCaster") };
    return Ids;
}

UReflectionsNpcArchetype* UReflectionsNpcArchetype::MakeBuiltIn(UObject* Outer, FName Id)
{
    if (!BuiltInIds().Contains(Id)) return nullptr;
    UReflectionsNpcArchetype* Archetype = NewObject<UReflectionsNpcArchetype>(Outer,
        MakeUniqueObjectName(Outer, StaticClass(), FName(*FString::Printf(TEXT("NpcBuiltIn_%s"), *Id.ToString()))), RF_Transient);
    Archetype->ApplyBuiltIn(Id);
    return Archetype;
}

void UReflectionsNpcArchetype::ResetToBuiltIn()
{
    if (ApplyBuiltIn(ArchetypeId)) MarkPackageDirty();
    else UE_LOG(LogTemp, Warning, TEXT("'%s' is not a built-in NPC type; nothing was reset."), *ArchetypeId.ToString());
}

bool UReflectionsNpcArchetype::ApplyBuiltIn(FName Id)
{
    if (!BuiltInIds().Contains(Id)) return false;
    UReflectionsNpcArchetype* A = this;
    const UReflectionsNpcArchetype* Defaults = GetDefault<UReflectionsNpcArchetype>();
    A->ArchetypeId = Id;
    A->Disposition = Defaults->Disposition;
    A->Reaction = Defaults->Reaction;
    A->Combat = Defaults->Combat;
    A->MaxHealth = Defaults->MaxHealth;
    A->bRagdollOnLethalHit = Defaults->bRagdollOnLethalHit;
    A->bPhysicalHitReaction = Defaults->bPhysicalHitReaction;
    A->bAddHitProxy = Defaults->bAddHitProxy;
    A->GrantedTags = Defaults->GrantedTags;
    A->HomeWorld = Defaults->HomeWorld;
    A->CoinReward = Defaults->CoinReward;
    A->ReputationOnPlayerHit = Defaults->ReputationOnPlayerHit;
    A->ReputationOnPlayerKill = Defaults->ReputationOnPlayerKill;
    A->ReputationPerHealedPoint = Defaults->ReputationPerHealedPoint;
    A->MaxReputationPerHeal = Defaults->MaxReputationPerHeal;
    A->bCountsOnInfectionMeter = Defaults->bCountsOnInfectionMeter;
    A->VoiceCharacter = Defaults->VoiceCharacter;
    A->BarkOnFear = Defaults->BarkOnFear;
    A->BarkOnAlert = Defaults->BarkOnAlert;
    A->BarkOnAttack = Defaults->BarkOnAttack;
    A->Looks = Defaults->Looks;
    A->HiddenLookParts = Defaults->HiddenLookParts;
    A->bCuredOnDeath = Defaults->bCuredOnDeath;
    // The team's melee set, /Game/Combat/Melee/AS_Melee_<Move>_<Body>: every move exists once per body skeleton
    // in use, and the motor plays the one that fits. Those trained to fight get the full set of strikes, the
    // tarnished two wild swings. The blow lands at 47 % of these clips.
    A->Combat.AttackAnimations.Reset();
    const auto AddMelee = [A](const TArray<const TCHAR*>& Moves)
    {
        static const TCHAR* Bodies[] = { TEXT("IvenRook"), TEXT("BridgeGuard"), TEXT("CoinClerk") };
        for (const TCHAR* Move : Moves)
            for (const TCHAR* Body : Bodies)
            {
                const FString Name = FString::Printf(TEXT("AS_Melee_%s_%s"), Move, Body);
                const FString Package = FString::Printf(TEXT("/Game/Combat/Melee/%s"), *Name);
                if (FPackageName::DoesPackageExist(Package))
                    A->Combat.AttackAnimations.Add(TSoftObjectPtr<UAnimSequence>(FSoftObjectPath(FString::Printf(TEXT("%s.%s"), *Package, *Name))));
            }
        if (A->Combat.AttackAnimations.Num() > 0) A->Combat.ImpactFraction = 0.47f;
    };
    if (Id == TEXT("Guard") || Id == TEXT("Enemy") || Id == TEXT("Hostile") || Id == TEXT("Soldier"))
        AddMelee({ TEXT("Sword_Slash_LR"), TEXT("Sword_Slash_RL"), TEXT("Sword_Stab"), TEXT("Sword_Overhead") });
    else if (Id == TEXT("Infected") || Id == TEXT("VillainHost"))
        AddMelee({ TEXT("Sword_Slash_RL"), TEXT("Sword_Overhead") });
    // The same moves made for the hidden walker's skeleton (AS_Melee_<Move>_Walker): the route that leaves the
    // visible body's animation alone. Listed only when the assets are in the project.
    A->Combat.WalkerAttackAnimations.Reset();
    const auto WalkerClip = [](const TCHAR* Move)
    {
        const FString Name = FString::Printf(TEXT("AS_Melee_%s_Walker"), Move);
        const FString Package = FString::Printf(TEXT("/Game/Combat/Melee/%s"), *Name);
        return FPackageName::DoesPackageExist(Package)
            ? TSoftObjectPtr<UAnimSequence>(FSoftObjectPath(FString::Printf(TEXT("%s.%s"), *Package, *Name))) : TSoftObjectPtr<UAnimSequence>();
    };
    const auto AddWalker = [A, &WalkerClip](const TArray<const TCHAR*>& Moves)
    {
        for (const TCHAR* Move : Moves)
        {
            const TSoftObjectPtr<UAnimSequence> Clip = WalkerClip(Move);
            if (!Clip.IsNull()) A->Combat.WalkerAttackAnimations.Add(Clip);
        }
    };
    const auto Prop = [](const TCHAR* Package, const TCHAR* Name)
    {
        return FPackageName::DoesPackageExist(Package)
            ? TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(FString::Printf(TEXT("%s.%s"), Package, Name))) : TSoftObjectPtr<UStaticMesh>();
    };
    if (Id == TEXT("Guard") || Id == TEXT("Enemy") || Id == TEXT("Hostile") || Id == TEXT("Soldier") || Id == TEXT("AlliedSoldier"))
    {
        // Trained fighters carry a sword and have the full set of strikes.
        AddWalker({ TEXT("Sword_Slash_LR"), TEXT("Sword_Slash_RL"), TEXT("Sword_Stab"), TEXT("Sword_Overhead") });
        A->Combat.WeaponProp = Prop(TEXT("/Game/LanthorneAssets/Frostside/Props/SM_Frostside_MirrorSword"), TEXT("SM_Frostside_MirrorSword"));
    }
    else if (Id == TEXT("SoldierCaster") || Id == TEXT("AlliedSoldierCaster"))
        // Casters are soldiers too: the same sword (they cast from the sword hand), no wand.
        A->Combat.WeaponProp = Prop(TEXT("/Game/LanthorneAssets/Frostside/Props/SM_Frostside_MirrorSword"), TEXT("SM_Frostside_MirrorSword"));
    const bool bGuardLike = Id == TEXT("Guard") || Id == TEXT("AlliedSoldier") || Id == TEXT("AlliedSoldierCaster");
    const bool bEnemyFighter = Id == TEXT("Soldier") || Id == TEXT("SoldierCaster") || Id == TEXT("Enemy") || Id == TEXT("Hostile");
    if (bGuardLike || bEnemyFighter)
    {
        if (FPackageName::DoesPackageExist(TEXT("/Game/NPC/Anim/AS_Npc_ArmedHold_Add_Walker")))
            A->Combat.WalkerArmedHold = TSoftObjectPtr<UAnimSequence>(FSoftObjectPath(TEXT("/Game/NPC/Anim/AS_Npc_ArmedHold_Add_Walker.AS_Npc_ArmedHold_Add_Walker")));
        // Sword and shield held at the ready: listed only when the clips are in the project.
        A->Combat.WalkerGuardIdle = WalkerClip(TEXT("Shield_Guard_Idle"));
        A->Combat.WalkerMarchHold = WalkerClip(TEXT("Shield_March_Hold"));
    }
    if (Id == TEXT("Infected") || Id == TEXT("VillainHost"))
    {
        // The tarnished are dark sorcerers: from 8 to 20 m with a clear line they stop and throw the Tarnish's
        // magic at the player, a bolt or now and then a slow wisp that follows; up close they claw, and they still
        // run townspeople down to turn them.
        AddWalker({ TEXT("Sword_Slash_RL"), TEXT("Sword_Overhead") });
        A->Combat.bCastsAtPlayer = true;
        A->Combat.RangedSpells = { EHeroSpell::ArcaneBolt };
        A->Combat.RangedHomingChance = 0.35f;
        A->Combat.RangedDamageScale = 0.6f;
        A->Combat.RangedMinRange = 800.0f;
        A->Combat.RangedMaxRange = 2000.0f;
        A->Combat.RangedCooldown = FVector2D(2.5, 4.0);
        A->Combat.RangedWindup = 0.9f;
        A->Combat.WalkerCastAnimation = WalkerClip(TEXT("Wand_Flick"));
    }
    // Blood is opt-in (the spell VFX reads the Flesh tag): those who fight the player bleed, bystanders do not.
    if (Id == TEXT("Enemy") || Id == TEXT("Hostile") || Id == TEXT("Soldier") || Id == TEXT("SoldierCaster") ||
        Id == TEXT("Infected") || Id == TEXT("VillainHost"))
        A->GrantedTags.AddUnique(FName(TEXT("Flesh")));
    // Health is counted in the player's spells (Fire Bolt 14, Fireball 20): a fireball kills a townsperson and a
    // bolt nearly does; a guard takes three bolts, a soldier four, the dedicated opponent five. Nobody is a sponge.

    if (Id == TEXT("Civilian") || Id == TEXT("Timid") || Id == TEXT("Brave"))
    {
        A->BarkOnFear = TEXT("Civilian_Fear");
    }
    else if (Id == TEXT("Guard") || Id == TEXT("AlliedSoldier") || Id == TEXT("AlliedSoldierCaster"))
    {
        A->VoiceCharacter = Id == TEXT("Guard") ? TEXT("Guard") : TEXT("Soldier");
        A->BarkOnAlert = TEXT("Guard_Alert");
        A->BarkOnAttack = TEXT("Guard_Attack");
    }
    else if (Id == TEXT("Infected") || Id == TEXT("VillainHost"))
    {
        A->VoiceCharacter = TEXT("Tarnished");
        A->BarkOnAttack = TEXT("Tarnished_Mutter");
    }
    else
    {
        A->VoiceCharacter = TEXT("Soldier");
    }


    if (Id == TEXT("Civilian"))
    {
        A->Disposition = EReflectionsNpcDisposition::Civilian;
        A->MaxHealth = 20.0f;
    }
    else if (Id == TEXT("Timid"))
    {
        A->Disposition = EReflectionsNpcDisposition::Timid;
        A->MaxHealth = 20.0f;
        A->Reaction.FearPerNoise = 0.9f;
    }
    else if (Id == TEXT("Brave"))
    {
        A->Disposition = EReflectionsNpcDisposition::Brave;
        A->MaxHealth = 28.0f;
        A->Reaction.NoiseResponse = EReflectionsNpcNoiseResponse::Investigate;
        A->Reaction.bFightsBack = true;
        A->Reaction.bCanAttack = true;
    }
    else if (Id == TEXT("Guard"))
    {
        A->Disposition = EReflectionsNpcDisposition::Guard;
        A->MaxHealth = 42.0f;
        A->Reaction.NoiseResponse = EReflectionsNpcNoiseResponse::Investigate;
        A->Reaction.bFightsBack = true;
        A->Reaction.bCanAttack = true;
        A->Reaction.bTurnsOnDisliked = true;
        A->Combat.bUseMeleeMotor = true;
    }
    else if (Id == TEXT("AlliedSoldier"))
    {
        // Giltside's own soldiers: on the player's side. They stand their post (or march, where the squad layer
        // steers them), go for any of the tarnished they see, fight back when struck, and like the guards they
        // turn on a player who has made himself wanted. The tarnished hunt them as they hunt the townspeople.
        A->Disposition = EReflectionsNpcDisposition::Guard;
        A->MaxHealth = 56.0f;
        A->HomeWorld = EReflectionsNpcHomeWorld::Red;
        A->GrantedTags.AddUnique(FName(TEXT("NPC_AlliedSoldier")));
        A->Reaction.AwarenessRadius = 1800.0f;
        A->Reaction.bRoamsWhenCalm = false;
        A->Reaction.NoiseResponse = EReflectionsNpcNoiseResponse::Investigate;
        A->Reaction.bFightsBack = true;
        A->Reaction.bCanAttack = true;
        A->Reaction.bTurnsOnDisliked = true;
        A->Reaction.ReactionSeconds = 7.0f;
        A->Combat.bUseMeleeMotor = true;
        A->Combat.bFightsTarnished = true;
        A->Combat.SightRadius = 1800.0f;
        A->Combat.AttackRange = 170.0f;
        A->Combat.AttackDamage = 10.0f;
        A->Combat.AttackCooldown = 1.3f;
        A->Combat.ChaseInput = 0.8f;
    }
    else if (Id == TEXT("AlliedSoldierCaster"))
    {
        // Giltside's wand-bearers: on the player's side like the allied soldier, but they do not close in. They
        // keep their distance, flinch away from a hit, and cast when their squad has them cast (the squad layer
        // reads the Ranged block, as it does for the enemy's casters).
        A->Disposition = EReflectionsNpcDisposition::Guard;
        A->MaxHealth = 42.0f;
        A->HomeWorld = EReflectionsNpcHomeWorld::Red;
        A->GrantedTags.AddUnique(FName(TEXT("NPC_AlliedSoldier")));
        A->Reaction.AwarenessRadius = 1800.0f;
        A->Reaction.bRoamsWhenCalm = false;
        A->Reaction.NoiseResponse = EReflectionsNpcNoiseResponse::Ignore;
        A->Reaction.FearPerNoise = 0.0f;
        A->Reaction.bFightsBack = false;
        A->Reaction.bCanAttack = false;
        A->Reaction.FleeBelowHealthFraction = 0.25f;
        A->Reaction.ReactionSeconds = 2.5f;
        A->Reaction.FleeDistance = 550.0f;
        A->Reaction.ReactionSpeed = 260.0f;
        A->Combat.bHuntPlayerOnSight = false;
        A->Combat.bUseMeleeMotor = false;
        A->Combat.SightRadius = 2200.0f;
        A->Combat.bRangedCaster = true;
        A->Combat.RangedSpells = { EHeroSpell::Fire, EHeroSpell::IceShard, EHeroSpell::ArcaneBolt };
        A->Combat.RangedCastAnimation = TSoftObjectPtr<UAnimSequence>(FSoftObjectPath(
            TEXT("/Game/Characters/Hero/Animation/CombatCasts/AS_Hero_CombatBoltRight.AS_Hero_CombatBoltRight")));
    }
    else if (Id == TEXT("Enemy") || Id == TEXT("Hostile"))
    {
        // Enemy: the tagged combat opponent, hunts on sight with the full melee motor.
        // Hostile: attacks only once provoked, with the simple poke.
        const bool bHunter = Id == TEXT("Enemy");
        A->Disposition = EReflectionsNpcDisposition::Enemy;
        A->Reaction.NoiseResponse = EReflectionsNpcNoiseResponse::Attack;
        A->Reaction.bFightsBack = true;
        A->Reaction.bCanAttack = true;
        A->Reaction.bRoamsWhenCalm = !bHunter;
        A->Combat.bHuntPlayerOnSight = bHunter;
        A->Combat.bUseMeleeMotor = bHunter;
        A->CoinReward = EReflectionsNpcCoinReward::Purse;
        A->ReputationOnPlayerHit = 0.0f;
        A->MaxHealth = bHunter ? 70.0f : 42.0f;
    }
    else if (Id == TEXT("Soldier") || Id == TEXT("SoldierCaster"))
    {
        // Enemy soldiers that march in squads (Source/reflections/Squads steers them and orders them to fight).
        // Alone they stand their ground: no roaming, no charging at noise; a hit makes a melee soldier fight back
        // and a caster flinch away, and a badly hurt one runs.
        const bool bCaster = Id == TEXT("SoldierCaster");
        A->Disposition = EReflectionsNpcDisposition::Enemy;
        A->MaxHealth = bCaster ? 42.0f : 56.0f;
        A->GrantedTags.AddUnique(FName(TEXT("NPC_Soldier")));
        A->CoinReward = EReflectionsNpcCoinReward::Pickup;
        A->ReputationOnPlayerHit = 0.0f;
        A->Reaction.AwarenessRadius = 1800.0f;
        A->Reaction.bRoamsWhenCalm = false;
        A->Reaction.NoiseResponse = EReflectionsNpcNoiseResponse::Ignore;
        A->Reaction.FearPerNoise = 0.0f;
        A->Reaction.bFightsBack = !bCaster;
        A->Reaction.bCanAttack = !bCaster;
        A->Reaction.FleeBelowHealthFraction = 0.25f;
        A->Reaction.ReactionSeconds = bCaster ? 2.5f : 7.0f;
        A->Reaction.FleeDistance = bCaster ? 550.0f : 900.0f;
        A->Reaction.ReactionSpeed = 260.0f;
        A->Combat.bHuntPlayerOnSight = false;
        A->Combat.bUseMeleeMotor = !bCaster;
        A->Combat.SightRadius = 2200.0f;
        A->Combat.AttackRange = 170.0f;
        A->Combat.AttackDamage = 8.0f;
        A->Combat.AttackCooldown = 1.4f;
        A->Combat.SimpleAttackDamage = 8.0f;
        A->Combat.ChaseInput = 0.75f;
        A->Combat.bRangedCaster = bCaster;
        if (bCaster)
        {
            A->Combat.RangedSpells = { EHeroSpell::Fire, EHeroSpell::IceShard, EHeroSpell::ArcaneBolt };
            A->Combat.RangedCastAnimation = TSoftObjectPtr<UAnimSequence>(FSoftObjectPath(
                TEXT("/Game/Characters/Hero/Animation/CombatCasts/AS_Hero_CombatBoltRight.AS_Hero_CombatBoltRight")));
        }
    }
    else if (Id == TEXT("Infected"))
    {
        A->Disposition = EReflectionsNpcDisposition::Infected;
        A->MaxHealth = 28.0f;
        A->Reaction.NoiseResponse = EReflectionsNpcNoiseResponse::Attack;
        A->Reaction.bFightsBack = true;
        A->Reaction.bCanAttack = true;
        A->Reaction.bRoamsWhenCalm = true;
        A->Combat.bHuntPlayerOnSight = true;
        A->Combat.bHuntsNpcs = true;
        A->Combat.bConvertsNpcs = true;
        A->Combat.bUseMeleeMotor = true;
        // 15 m: far enough to start casting from range (with 9 m they only ever noticed the player up close).
        A->Combat.SightRadius = 1500.0f;
        A->Combat.AttackDamage = 8.0f;
        A->Combat.AttackCooldown = 1.4f;
        A->Combat.ChaseInput = 0.5f;
        A->ReputationOnPlayerHit = 0.0f;
        A->bCountsOnInfectionMeter = true;
    }
    else if (Id == TEXT("VillainHost"))
    {
        A->Disposition = EReflectionsNpcDisposition::VillainHost;
        A->MaxHealth = 70.0f;
        A->Reaction.NoiseResponse = EReflectionsNpcNoiseResponse::Attack;
        A->Reaction.bFightsBack = true;
        A->Reaction.bCanAttack = true;
        A->Reaction.bRoamsWhenCalm = false;
        A->Combat.bHuntPlayerOnSight = true;
        A->Combat.bHuntsNpcs = true;
        A->Combat.bConvertsNpcs = true;
        A->Combat.bUseMeleeMotor = true;
        A->Combat.SightRadius = 1600.0f;
        A->Combat.AttackDamage = 16.0f;
        A->Combat.ChaseInput = 0.85f;
        A->ReputationOnPlayerHit = 0.0f;
        A->bCountsOnInfectionMeter = true;
        // A host the player kills falls like any body (the villain session asked for this); when he burns a
        // host out, that session sets BurnedOut first and the body dies as its own type.
    }
    return true;
}
