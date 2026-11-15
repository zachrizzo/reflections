#include "Squads/ReflectionsSquadNpcBridge.h"
#include "Squads/ReflectionsSquad.h"

#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/DamageType.h"
#include "Hero/ReflectionsSpellCombat.h"
#include "Kismet/GameplayStatics.h"
#include "NPC/ReflectionsNpcArchetype.h"
#include "NPC/ReflectionsNpcCombatComponent.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "NPC/ReflectionsNpcSubsystem.h"

// Soldiers are enrolled in the one NPC system (UReflectionsNpcSubsystem) with a "Soldier" / "SoldierCaster"
// archetype built here from the built-in Enemy type. The NPC system owns their life; the squad only steers them
// while they are in formation (or keeping casting range) and tells the melee motor whom to fight.
//
// The steering/engage hooks on the NPC component are detected at compile time, so this file builds whether or
// not the NPC session has added them yet; without them the soldier archetype simply never roams or hunts by itself.

namespace
{
    const FName SoldierTag(TEXT("NPC_Soldier"));

    template <typename T>
    void CallSetSteered(T* Npc, bool bSteered)
    {
        if constexpr (requires(T* N) { N->SetExternallySteered(true); })
        {
            Npc->SetExternallySteered(bSteered);
        }
        else if constexpr (requires(T* N) { N->SetExternalControl(true); })
        {
            Npc->SetExternalControl(bSteered);
        }
        else if constexpr (requires(T* N) { N->SetSquadControlled(true); })
        {
            Npc->SetSquadControlled(bSteered);
        }
    }

    template <typename T>
    bool CallEngage(T* Npc, AActor* Target)
    {
        if constexpr (requires(T* N, AActor* A) { N->Engage(A); })
        {
            Npc->Engage(Target);
            return true;
        }
        else if constexpr (requires(T* N, AActor* A) { N->EngageTarget(A); })
        {
            Npc->EngageTarget(Target);
            return true;
        }
        else
        {
            return false;
        }
    }

    template <typename T>
    ACharacter* CallMover(const T* Npc)
    {
        if constexpr (requires(const T* N) { N->GetMovementCharacter(); })
        {
            return Npc->GetMovementCharacter();
        }
        else
        {
            return Npc->GetLocomotionDriver();
        }
    }

    UReflectionsNpcReactionComponent* FindNpc(AActor* Soldier)
    {
        return Soldier ? Soldier->FindComponentByClass<UReflectionsNpcReactionComponent>() : nullptr;
    }

    UReflectionsHealthComponent* FindHealth(AActor* Soldier)
    {
        return Soldier ? Soldier->FindComponentByClass<UReflectionsHealthComponent>() : nullptr;
    }

    UReflectionsNpcArchetype* MakeSoldierArchetype(UObject* Outer, const ReflectionsSquadNpc::FSoldierSpec& Spec)
    {
        const bool bCaster = Spec.Role == EReflectionsSquadRole::Caster;
        UReflectionsNpcArchetype* Archetype = UReflectionsNpcArchetype::MakeBuiltIn(Outer, TEXT("Enemy"));
        if (!Archetype)
        {
            Archetype = NewObject<UReflectionsNpcArchetype>(Outer, NAME_None, RF_Transient);
        }
        Archetype->ArchetypeId = bCaster ? FName(TEXT("SoldierCaster")) : FName(TEXT("Soldier"));
        Archetype->Disposition = EReflectionsNpcDisposition::Enemy;
        if (Spec.MaxHealth > 0.0f)
        {
            Archetype->MaxHealth = Spec.MaxHealth;
        }
        Archetype->bRagdollOnLethalHit = true;
        // The partial-physics hit flinch empties the bone buffers of these crowd MetaHuman bodies (two editor crashes
        // on 2026-11-14); the NPC system's lean-away flinch replaces it.
        Archetype->bPhysicalHitReaction = false;
        Archetype->bAddHitProxy = true;
        Archetype->GrantedTags.AddUnique(TEXT("Flesh"));
        Archetype->GrantedTags.AddUnique(SoldierTag);
        Archetype->HomeWorld = EReflectionsNpcHomeWorld::FromSpawnLocation;
        Archetype->CoinReward = EReflectionsNpcCoinReward::Pickup;
        // Enemy raiders: hurting or killing them costs the player no standing.
        Archetype->ReputationOnPlayerHit = 0.0f;
        Archetype->ReputationOnPlayerKill = 0.0f;

        FReflectionsNpcReactionProfile& Reaction = Archetype->Reaction;
        Reaction.AwarenessRadius = 1800.0f;
        // The squad decides when to move and what noise means; the NPC never wanders or charges off by itself.
        Reaction.bRoamsWhenCalm = false;
        Reaction.NoiseResponse = EReflectionsNpcNoiseResponse::Ignore;
        Reaction.bTurnsOnDisliked = false;
        Reaction.FearPerNoise = 0.0f;
        // Melee soldiers fight back when hit; casters flinch away for a moment and then return to the squad.
        Reaction.bFightsBack = !bCaster;
        Reaction.bCanAttack = !bCaster;
        Reaction.ReactionSeconds = bCaster ? 2.5f : 7.0f;
        Reaction.FleeDistance = bCaster ? 550.0f : 900.0f;
        Reaction.ReactionSpeed = 260.0f;

        FReflectionsNpcCombatProfile& Combat = Archetype->Combat;
        Combat.bHuntPlayerOnSight = false;
        Combat.bUseMeleeMotor = !bCaster;
        Combat.SightRadius = 2200.0f;
        Combat.AttackRange = 170.0f;
        Combat.AttackCooldown = 1.4f;
        if (Spec.MeleeDamage > 0.0f)
        {
            Combat.AttackDamage = Spec.MeleeDamage;
            Combat.SimpleAttackDamage = Spec.MeleeDamage;
        }
        Combat.ChaseInput = 0.75f;
        return Archetype;
    }
}

void ReflectionsSquadNpc::Enrol(AActor* Soldier, const FSoldierSpec& Spec)
{
    if (!IsValid(Soldier))
    {
        return;
    }
    // Per-actor options of the NPC system: walk with the sample locomotion driver, ragdoll on a lethal hit.
    Soldier->Tags.AddUnique(TEXT("NPC_SampleLocomotion"));
    Soldier->Tags.AddUnique(TEXT("NPC_Ragdoll"));
    Soldier->Tags.AddUnique(TEXT("NPC_HitProxy"));
    Soldier->Tags.AddUnique(SoldierTag);
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(Soldier);
    if (!Npcs)
    {
        UE_LOG(LogTemp, Warning, TEXT("Squads: no NPC subsystem; %s is not an NPC"), *Soldier->GetName());
        return;
    }
    // The NPC system's own Soldier / SoldierCaster types (data assets in /Game/NPC/Archetypes when saved) keep the
    // soldier numbers in one place. A private copy is made only when this squad overrides health or melee damage.
    const bool bCaster = Spec.Role == EReflectionsSquadRole::Caster;
    UReflectionsNpcArchetype* Archetype = nullptr;
    if (Spec.bAllied)
    {
        // Gilt guards: allied types; the plain Guard type until the NPC system has them.
        Archetype = Npcs->FindArchetype(bCaster ? FName(TEXT("AlliedSoldierCaster")) : FName(TEXT("AlliedSoldier")));
        if (!Archetype && bCaster)
        {
            Archetype = Npcs->FindArchetype(TEXT("AlliedSoldier"));
        }
        if (!Archetype)
        {
            Archetype = Npcs->FindArchetype(TEXT("Guard"));
        }
    }
    else
    {
        Archetype = Npcs->FindArchetype(bCaster ? FName(TEXT("SoldierCaster")) : FName(TEXT("Soldier")));
    }
    if (!Archetype)
    {
        Archetype = MakeSoldierArchetype(Npcs, Spec);
    }
    else if (Spec.MaxHealth > 0.0f || (!bCaster && Spec.MeleeDamage > 0.0f))
    {
        Archetype = DuplicateObject<UReflectionsNpcArchetype>(Archetype, Npcs);
        if (Spec.MaxHealth > 0.0f)
        {
            Archetype->MaxHealth = Spec.MaxHealth;
        }
        if (!bCaster && Spec.MeleeDamage > 0.0f)
        {
            Archetype->Combat.AttackDamage = Spec.MeleeDamage;
            Archetype->Combat.SimpleAttackDamage = Spec.MeleeDamage;
        }
        Archetype->bPhysicalHitReaction = false;
    }
    UReflectionsNpcReactionComponent* Npc = Npcs->EnrollActor(Soldier, Archetype);
    if (!Npc)
    {
        UE_LOG(LogTemp, Warning, TEXT("Squads: NPC system refused %s"), *Soldier->GetName());
        return;
    }
    Npc->bUseSampleLocomotion = true;
    Npc->bEnableRagdollOnDeath = true;
    Npc->bEnablePhysicalHitReaction = false;
    CallSetSteered(Npc, true);
}

ACharacter* ReflectionsSquadNpc::GetDriver(AActor* Soldier)
{
    if (ACharacter* Character = Cast<ACharacter>(Soldier))
    {
        return Character;
    }
    const UReflectionsNpcReactionComponent* Npc = FindNpc(Soldier);
    return Npc ? CallMover(Npc) : nullptr;
}

USkeletalMeshComponent* ReflectionsSquadNpc::GetBody(AActor* Soldier)
{
    if (!Soldier)
    {
        return nullptr;
    }
    TInlineComponentArray<USkeletalMeshComponent*> Meshes(Soldier);
    for (USkeletalMeshComponent* Mesh : Meshes)
    {
        if (Mesh && Mesh->GetFName() == TEXT("Body"))
        {
            return Mesh;
        }
    }
    return Meshes.Num() > 0 ? Meshes[0] : nullptr;
}

bool ReflectionsSquadNpc::IsAlive(AActor* Soldier)
{
    if (!IsValid(Soldier))
    {
        return false;
    }
    if (const UReflectionsNpcReactionComponent* Npc = FindNpc(Soldier))
    {
        if (Npc->Reaction == EReflectionsNpcReaction::Incapacitated)
        {
            return false;
        }
    }
    const UReflectionsHealthComponent* Health = FindHealth(Soldier);
    return !Health || Health->Health > 0.0f;
}

float ReflectionsSquadNpc::GetHealth(AActor* Soldier)
{
    const UReflectionsHealthComponent* Health = FindHealth(Soldier);
    return Health ? Health->Health : 0.0f;
}

bool ReflectionsSquadNpc::WantsToFlee(AActor* Soldier)
{
    const UReflectionsNpcReactionComponent* Npc = FindNpc(Soldier);
    return Npc && Npc->Reaction == EReflectionsNpcReaction::Fleeing;
}

bool ReflectionsSquadNpc::IsAggravated(AActor* Soldier)
{
    const UReflectionsNpcReactionComponent* Npc = FindNpc(Soldier);
    return Npc && (Npc->Reaction == EReflectionsNpcReaction::Attacking || Npc->Reaction == EReflectionsNpcReaction::Defending ||
        Npc->Reaction == EReflectionsNpcReaction::Investigating);
}

void ReflectionsSquadNpc::SetMeleeTarget(AActor* Soldier, AActor* Target)
{
    UReflectionsNpcReactionComponent* Npc = FindNpc(Soldier);
    if (!Npc)
    {
        return;
    }
    if (!CallEngage(Npc, Target))
    {
        // No engage hook: provoke the NPC toward the target (archetypes are shared, so never edit them here).
        if (Target)
        {
            FReflectionsNpcStimulus Provoke;
            Provoke.Kind = EReflectionsNpcStimulusKind::Violence;
            Provoke.Location = Soldier->GetActorLocation();
            Provoke.Intensity = 20.0f;
            Provoke.Instigator = Target;
            Npc->ReceiveStimulus(Provoke, 0.0f);
        }
    }
    // A fighting melee soldier is moved by the NPC system's motor, not by the squad.
    CallSetSteered(Npc, Target == nullptr);
    if (!Target)
    {
        if (ACharacter* Driver = GetDriver(Soldier))
        {
            Driver->GetCharacterMovement()->StopMovementImmediately();
        }
    }
}

void ReflectionsSquadNpc::SetSteered(AActor* Soldier, bool bSteered)
{
    if (UReflectionsNpcReactionComponent* Npc = FindNpc(Soldier))
    {
        CallSetSteered(Npc, bSteered);
    }
}

void ReflectionsSquadNpc::Release(AActor* Soldier)
{
    SetSteered(Soldier, false);
}

void ReflectionsSquadNpc::Kill(AActor* Soldier, AActor* Instigator)
{
    if (const UReflectionsHealthComponent* Health = FindHealth(Soldier))
    {
        UGameplayStatics::ApplyDamage(Soldier, Health->Health + Health->Shield + 1.0f, nullptr, Instigator, UDamageType::StaticClass());
    }
}

bool ReflectionsSquadNpc::GetCasterTuning(const UObject* WorldContext, FCasterTuning& Out, FName ArchetypeId)
{
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(WorldContext);
    const UReflectionsNpcArchetype* Caster = Npcs ? Npcs->FindArchetype(ArchetypeId) : nullptr;
    if ((!Caster || !Caster->Combat.bRangedCaster) && Npcs)
    {
        Caster = Npcs->FindArchetype(TEXT("SoldierCaster"));
    }
    if (!Caster || !Caster->Combat.bRangedCaster)
    {
        Out.bValid = false;
        return false;
    }
    const FReflectionsNpcCombatProfile& Combat = Caster->Combat;
    Out.bValid = true;
    Out.Spells = Combat.RangedSpells;
    Out.DamageScale = Combat.RangedDamageScale;
    Out.MinRange = Combat.RangedMinRange;
    Out.MaxRange = Combat.RangedMaxRange;
    Out.Cooldown = Combat.RangedCooldown;
    Out.Windup = Combat.RangedWindup;
    Out.CastAnimation = Combat.RangedCastAnimation;
    return true;
}

namespace
{
    template <typename T>
    bool ArchetypeHasWeapon(const T* Archetype)
    {
        if constexpr (requires(const T* A) { A->Combat.WeaponProp.IsNull(); })
        {
            return Archetype && !Archetype->Combat.WeaponProp.IsNull();
        }
        else
        {
            return false;
        }
    }
}

namespace
{
    template <typename T>
    FDelegateHandle BindCrimesOn(T* Npcs, TFunction<void(AActor*, const FVector&)> Fn)
    {
        if constexpr (requires(T* N) { N->OnCrime.AddLambda([](AActor*, AActor*, const FVector&, float) {}); })
        {
            return Npcs->OnCrime.AddLambda([Fn = MoveTemp(Fn)](AActor* Offender, AActor*, const FVector& Location, float)
            {
                Fn(Offender, Location);
            });
        }
        else
        {
            return FDelegateHandle();
        }
    }

    template <typename T>
    void UnbindCrimesOn(T* Npcs, FDelegateHandle Handle)
    {
        if constexpr (requires(T* N, FDelegateHandle H) { N->OnCrime.Remove(H); })
        {
            Npcs->OnCrime.Remove(Handle);
        }
    }
}

FDelegateHandle ReflectionsSquadNpc::BindCrimes(const UObject* WorldContext, TFunction<void(AActor*, const FVector&)> Fn)
{
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(WorldContext);
    return Npcs ? BindCrimesOn(Npcs, MoveTemp(Fn)) : FDelegateHandle();
}

void ReflectionsSquadNpc::UnbindCrimes(const UObject* WorldContext, FDelegateHandle Handle)
{
    UReflectionsNpcSubsystem* Npcs = Handle.IsValid() ? UReflectionsNpcSubsystem::Get(WorldContext) : nullptr;
    if (Npcs)
    {
        UnbindCrimesOn(Npcs, Handle);
    }
}

bool ReflectionsSquadNpc::NpcCarriesWeapon(AActor* Soldier)
{
    const UReflectionsNpcReactionComponent* Npc = Soldier ? Soldier->FindComponentByClass<UReflectionsNpcReactionComponent>() : nullptr;
    if (!Npc)
    {
        return false;
    }
    const UReflectionsNpcArchetype* Archetype = Npc->GetActiveArchetype();
    return ArchetypeHasWeapon(Archetype ? Archetype : Npc->Archetype.Get());
}

namespace
{
    template <typename T>
    bool LooksAt(T* Npcs, FName Id, const FVector& Location, TArray<TSoftClassPtr<AActor>>& Out)
    {
        if constexpr (requires(T* N, FName I, FVector L) { N->GetLooksAt(I, L); })
        {
            for (const TSoftClassPtr<AActor>& Look : Npcs->GetLooksAt(Id, Location))
            {
                if (!Look.IsNull())
                {
                    Out.Add(Look);
                }
            }
            return Out.Num() > 0;
        }
        else
        {
            return false;
        }
    }
}

bool ReflectionsSquadNpc::GetSideLooks(const UObject* WorldContext, FName ArchetypeId, const FVector& Location, const FString& Side,
    TArray<TSoftClassPtr<AActor>>& Out)
{
    Out.Reset();
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(WorldContext);
    if (Npcs && LooksAt(Npcs, ArchetypeId, Location, Out))
    {
        return true;
    }
    GetArchetypeLooks(WorldContext, ArchetypeId, Out);
    if (!Side.IsEmpty())
    {
        const FString Token = Side.StartsWith(TEXT("Gilt")) ? TEXT("Gilt") : Side.StartsWith(TEXT("Frost")) ? TEXT("Frost") : TEXT("Pew");
        Out.RemoveAll([&Token](const TSoftClassPtr<AActor>& Look) { return !Look.ToSoftObjectPath().GetAssetName().Contains(Token); });
    }
    return Out.Num() > 0;
}

bool ReflectionsSquadNpc::GetArchetypeLooks(const UObject* WorldContext, bool bCaster, TArray<TSoftClassPtr<AActor>>& Out)
{
    return GetArchetypeLooks(WorldContext, bCaster ? FName(TEXT("SoldierCaster")) : FName(TEXT("Soldier")), Out);
}

namespace
{
    template <typename T>
    void BindCrimeOn(T* Npcs, AReflectionsSquad* Squad, bool bBind)
    {
        // OnPlayerCrime(Victim, Crime, Witness, Location, Heat): bound only when it exists with that signature.
        if constexpr (requires(T* N, AReflectionsSquad* S) { N->OnPlayerCrime.__Internal_AddUniqueDynamic(S, &AReflectionsSquad::HandlePlayerCrime, FName()); })
        {
            if (bBind)
            {
                Npcs->OnPlayerCrime.AddUniqueDynamic(Squad, &AReflectionsSquad::HandlePlayerCrime);
            }
            else
            {
                Npcs->OnPlayerCrime.RemoveDynamic(Squad, &AReflectionsSquad::HandlePlayerCrime);
            }
        }
    }
}

void ReflectionsSquadNpc::BindNpcEvents(AReflectionsSquad* Squad, bool bBind)
{
    UReflectionsNpcSubsystem* Npcs = Squad ? UReflectionsNpcSubsystem::Get(Squad) : nullptr;
    if (!Npcs)
    {
        return;
    }
    if (bBind)
    {
        Npcs->OnNpcSpellHit.AddUniqueDynamic(Squad, &AReflectionsSquad::HandleNpcSpellHit);
        Npcs->OnNpcDied.AddUniqueDynamic(Squad, &AReflectionsSquad::HandleNpcDied);
    }
    else
    {
        Npcs->OnNpcSpellHit.RemoveDynamic(Squad, &AReflectionsSquad::HandleNpcSpellHit);
        Npcs->OnNpcDied.RemoveDynamic(Squad, &AReflectionsSquad::HandleNpcDied);
    }
    BindCrimeOn(Npcs, Squad, bBind);
}

bool ReflectionsSquadNpc::PlayOnWalker(AActor* Soldier, UAnimSequenceBase* Clip, float Rate)
{
    UReflectionsNpcReactionComponent* Npc = Soldier && Clip ? Soldier->FindComponentByClass<UReflectionsNpcReactionComponent>() : nullptr;
    return Npc && Npc->PlayOnWalker(Clip, Rate);
}

bool ReflectionsSquadNpc::PlayBark(AActor* Speaker, FName Group)
{
    UReflectionsNpcSubsystem* Npcs = Speaker ? UReflectionsNpcSubsystem::Get(Speaker) : nullptr;
    if (!Npcs || !Npcs->FindVoiceCue(Speaker, Group))
    {
        return false;
    }
    Npcs->PlayBark(Speaker, Group);
    return true;
}

bool ReflectionsSquadNpc::IsTarnished(const AActor* Actor)
{
    const UReflectionsNpcReactionComponent* Npc = Actor ? Actor->FindComponentByClass<UReflectionsNpcReactionComponent>() : nullptr;
    const UReflectionsNpcArchetype* Archetype = Npc ? Npc->GetActiveArchetype() : nullptr;
    return Archetype && (Archetype->Disposition == EReflectionsNpcDisposition::Infected ||
        Archetype->Disposition == EReflectionsNpcDisposition::VillainHost);
}

TArray<AActor*> ReflectionsSquadNpc::GetNpcActors(const UObject* WorldContext)
{
    const UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(WorldContext);
    return Npcs ? Npcs->GetNpcActors() : TArray<AActor*>();
}

bool ReflectionsSquadNpc::GetArchetypeLooks(const UObject* WorldContext, FName ArchetypeId, TArray<TSoftClassPtr<AActor>>& Out)
{
    Out.Reset();
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(WorldContext);
    const UReflectionsNpcArchetype* Archetype = Npcs ? Npcs->FindArchetype(ArchetypeId) : nullptr;
    if (Archetype)
    {
        for (const TSoftClassPtr<AActor>& Look : Archetype->Looks)
        {
            if (!Look.IsNull())
            {
                Out.Add(Look);
            }
        }
    }
    return Out.Num() > 0;
}

FString ReflectionsSquadNpc::GetVoiceSuffix(AActor* Soldier)
{
    const UReflectionsNpcSubsystem* Npcs = Soldier ? UReflectionsNpcSubsystem::Get(Soldier) : nullptr;
    return Npcs ? Npcs->GetVoiceProfile(Soldier).CueSuffix : FString();
}
