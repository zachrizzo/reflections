#include "SpellCrafting/ReflectionsCraftedSpellSubsystem.h"

#include "SpellCrafting/ReflectionsCraftedSpell.h"
#include "SpellCrafting/ReflectionsSpellCraftingComponent.h"
#include "SpellCrafting/ReflectionsSpellCraftingLibrary.h"
#include "Hero/ReflectionsSampleSpellDriver.h"
#include "Hero/ReflectionsSpellAim.h"
#include "Hero/ReflectionsSpellCombat.h"
#include "Hero/ReflectionsSpellEventSubsystem.h"
#include "Interfaces/CombatDamageable.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "NPC/ReflectionsNpcSubsystem.h"

#include "Components/PrimitiveComponent.h"
#include "Engine/OverlapResult.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "NiagaraComponent.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraSystem.h"
#include "PhysicalMaterials/PhysicalMaterial.h"
#include "Components/AudioComponent.h"
#include "Sound/SoundBase.h"

#include <concepts>

namespace
{
    /** A fire burst this wide (cm) or wider is a blast (Explosion); smaller fire hits set the target alight (Burn). */
    constexpr float BlastReactionRadius = 150.0f;

    /** What a crafted hit does to a body: the element's reaction, agreed with spell-combat for catalog spells. */
    EReflectionsSpellReaction CraftedReaction(const FCraftedSpellResolved& Spell, bool bBlast)
    {
        switch (Spell.Recipe.Element)
        {
        case ECraftedSpellElement::Fire: return bBlast ? EReflectionsSpellReaction::Explosion : EReflectionsSpellReaction::Burn;
        case ECraftedSpellElement::Lightning: return EReflectionsSpellReaction::Electrify;
        case ECraftedSpellElement::Water: return EReflectionsSpellReaction::Push;
        case ECraftedSpellElement::Earth: return EReflectionsSpellReaction::Knockdown;
        case ECraftedSpellElement::Air: return EReflectionsSpellReaction::Lift;
        case ECraftedSpellElement::Ice: return EReflectionsSpellReaction::Freeze;
        case ECraftedSpellElement::Life: return EReflectionsSpellReaction::Push;
        default: return EReflectionsSpellReaction::Hit;
        }
    }

    /** Reactions that last, so repeated quiet hits (beams, pools, rain) keep them going. */
    bool NeedsUpkeep(EReflectionsSpellReaction Reaction)
    {
        return Reaction == EReflectionsSpellReaction::Electrify || Reaction == EReflectionsSpellReaction::Burn
            || Reaction == EReflectionsSpellReaction::Freeze || Reaction == EReflectionsSpellReaction::Pull
            || Reaction == EReflectionsSpellReaction::Lift;
    }

    /** Seconds the reaction lasts: the shock latch, the burn, the slow. */
    float ReactionSeconds(const FCraftedSpellResolved& Spell, EReflectionsSpellReaction Reaction, float Scale)
    {
        switch (Reaction)
        {
        case EReflectionsSpellReaction::Electrify: return FMath::Clamp(0.8f + 0.3f * Spell.Recipe.Power, 1.0f, 2.0f);
        case EReflectionsSpellReaction::Burn: return Spell.StatusSeconds > 0.0f ? Spell.StatusSeconds : 2.5f;
        case EReflectionsSpellReaction::Freeze: return (Spell.StatusSeconds > 0.0f ? Spell.StatusSeconds : 2.5f) * FMath::Clamp(Scale, 0.5f, 1.5f);
        default: return 0.0f;
        }
    }

    /**
     * Allegiance comes from the NPC subsystem, the one answer shared with catalog spells and aim assist: it reads each
     * NPC's archetype, so a civilian the villain infects turns hostile without tag edits. Detected at compile time so
     * a change on that side drops crafting back to the Friendly tag instead of breaking the build.
     */
    template <typename T>
    concept CNpcAllegiance = requires(const T* Npcs, const AActor* Actor) {
        { T::Get(Actor) };
        { Npcs->IsAllyOf(Actor, Actor) } -> std::convertible_to<bool>;
        { Npcs->CanBeHarmedBy(Actor, Actor) } -> std::convertible_to<bool>;
    };

    /** True with the NPC subsystem's answer in bOutAlly, or false when there is no subsystem (bOutAlly untouched). */
    template <typename T = UReflectionsNpcSubsystem>
    bool NpcIsAlly(const AActor* Target, const AActor* Caster, bool& bOutAlly)
    {
        if constexpr (CNpcAllegiance<T>)
        {
            if (const T* Npcs = T::Get(Target))
            {
                bOutAlly = Npcs->IsAllyOf(Target, Caster);
                return true;
            }
        }
        return false;
    }

    /** NPC crowd bodies are moved by a hidden locomotion character; pulls launch that one. */
    template <typename T>
    concept CNpcMover = requires(const T* Npcs, const AActor* Actor) {
        { Npcs->FindNpc(Actor)->GetMovementCharacter() } -> std::convertible_to<ACharacter*>;
    };

    template <typename T = UReflectionsNpcSubsystem>
    ACharacter* MovementCharacter(AActor* Target)
    {
        if (ACharacter* Character = Cast<ACharacter>(Target)) return Character;
        if constexpr (CNpcMover<T>)
        {
            if (const T* Npcs = T::Get(Target))
                if (const auto* Npc = Npcs->FindNpc(Target)) return Npc->GetMovementCharacter();
        }
        return nullptr;
    }

    template <typename T = UReflectionsNpcSubsystem>
    bool NpcCanHarm(const AActor* Target, const AActor* Caster, bool& bOutHarm)
    {
        if constexpr (CNpcAllegiance<T>)
        {
            if (const T* Npcs = T::Get(Target))
            {
                bOutHarm = Npcs->CanBeHarmedBy(Target, Caster);
                return true;
            }
        }
        return false;
    }

    const TCHAR* CraftedFolder = TEXT("/Game/SpellCrafting/VFX/");
    const TCHAR* CoreFolder = TEXT("/Game/Characters/Hero/SpellVFX/Systems/");

    UNiagaraSystem* LoadSystemAt(const TCHAR* Folder, const TCHAR* Name)
    {
        return LoadObject<UNiagaraSystem>(nullptr, *FString::Printf(TEXT("%s%s.%s"), Folder, Name, Name), nullptr, LOAD_NoWarn | LOAD_Quiet);
    }

    /** Cast and impact cue names for an element; Air and Life borrow the closest cues the audio set has. */
    void ElementCues(ECraftedSpellElement Element, const TCHAR*& OutCast, const TCHAR*& OutImpact)
    {
        switch (Element)
        {
        case ECraftedSpellElement::Fire: OutCast = TEXT("SCue_Fire_Cast"); OutImpact = TEXT("SCue_Fire_Impact"); break;
        case ECraftedSpellElement::Ice: OutCast = TEXT("SCue_Ice_Cast"); OutImpact = TEXT("SCue_Ice_Impact"); break;
        case ECraftedSpellElement::Lightning: OutCast = TEXT("SCue_Lightning_Cast"); OutImpact = TEXT("SCue_Lightning_Impact"); break;
        case ECraftedSpellElement::Water: OutCast = TEXT("SCue_Water_Cast"); OutImpact = TEXT("SCue_Water_Impact"); break;
        case ECraftedSpellElement::Earth: OutCast = TEXT("SCue_Earth_Cast"); OutImpact = TEXT("SCue_Earth_Impact"); break;
        case ECraftedSpellElement::Air: OutCast = TEXT("SCue_Levitation_Start"); OutImpact = TEXT("SCue_Water_Impact"); break;
        case ECraftedSpellElement::Life: OutCast = TEXT("SCue_Heal_Shimmer"); OutImpact = TEXT("SCue_Heal_Shimmer"); break;
        default: OutCast = TEXT("SCue_Arcane_Cast"); OutImpact = TEXT("SCue_Arcane_Impact"); break;
        }
    }

    bool IsAlive(const AActor* Actor)
    {
        if (const UReflectionsHealthComponent* Health = Actor->FindComponentByClass<UReflectionsHealthComponent>())
        {
            return Health->Health > 0.0f;
        }
        return true;
    }

    bool IsAttachedTo(const AActor* Actor, const AActor* Root)
    {
        for (const AActor* Parent = Actor ? Actor->GetAttachParentActor() : nullptr; Parent; Parent = Parent->GetAttachParentActor())
        {
            if (Parent == Root) return true;
        }
        return false;
    }

    void OverlapActors(const UWorld* World, const FVector& Location, float Radius, const AActor* Caster, TArray<AActor*>& Out)
    {
        if (!World || Radius <= 0.0f) return;
        TArray<FOverlapResult> Hits;
        FCollisionObjectQueryParams Types;
        Types.AddObjectTypesToQuery(ECC_Pawn);
        Types.AddObjectTypesToQuery(ECC_WorldDynamic);
        Types.AddObjectTypesToQuery(ECC_PhysicsBody);
        FCollisionQueryParams Query(SCENE_QUERY_STAT(CraftedSpellOverlap), false, Caster);
        World->OverlapMultiByObjectType(Hits, Location, FQuat::Identity, Types, FCollisionShape::MakeSphere(Radius), Query);
        for (const FOverlapResult& Hit : Hits)
        {
            AActor* Actor = Hit.GetActor();
            if (Actor && !Out.Contains(Actor)) Out.Add(Actor);
        }
    }
}

bool UReflectionsCraftedSpellSubsystem::DoesSupportWorldType(EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UReflectionsCraftedSpellSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
    Super::OnWorldBeginPlay(InWorld);
    bool bFallback = false;
    SystemFor(ECraftedFx::Body, bFallback);
}

TStatId UReflectionsCraftedSpellSubsystem::GetStatId() const
{
    RETURN_QUICK_DECLARE_CYCLE_STAT(UReflectionsCraftedSpellSubsystem, STATGROUP_Tickables);
}

UReflectionsCraftedSpellSubsystem* UReflectionsCraftedSpellSubsystem::Get(const UObject* WorldContext)
{
    const UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
    return World ? World->GetSubsystem<UReflectionsCraftedSpellSubsystem>() : nullptr;
}

void UReflectionsCraftedSpellSubsystem::EnsureCraftingComponents()
{
    UWorld* World = GetWorld();
    if (!World || World->GetNetMode() == NM_DedicatedServer) return;
    for (FConstPlayerControllerIterator It = World->GetPlayerControllerIterator(); It; ++It)
    {
        APlayerController* PC = It->Get();
        APawn* Pawn = PC && PC->IsLocalController() ? PC->GetPawn() : nullptr;
        if (!Pawn || !Pawn->FindComponentByClass<UReflectionsSampleSpellDriver>() || Pawn->FindComponentByClass<UReflectionsSpellCraftingComponent>())
        {
            continue;
        }
        UReflectionsSpellCraftingComponent* Crafting = NewObject<UReflectionsSpellCraftingComponent>(Pawn, TEXT("SpellCrafting"));
        Crafting->RegisterComponent();
    }
}

void UReflectionsCraftedSpellSubsystem::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    AttachClock -= DeltaTime;
    if (AttachClock <= 0.0f)
    {
        AttachClock = 0.5f;
        EnsureCraftingComponents();
        if (ReactionSent.Num() > 64)
        {
            const double Now = GetWorld()->GetTimeSeconds();
            for (auto It = ReactionSent.CreateIterator(); It; ++It)
            {
                if (!It.Key().IsValid() || Now - It.Value() > 3.0) It.RemoveCurrent();
            }
        }
    }

    for (int32 i = Burns.Num() - 1; i >= 0; --i)
    {
        FBurn& Burn = Burns[i];
        AActor* Target = Burn.Target.Get();
        Burn.Remaining -= DeltaTime;
        Burn.Clock += DeltaTime;
        if (!IsValid(Target) || Burn.Remaining <= 0.0f || !IsAlive(Target))
        {
            Burns.RemoveAtSwap(i);
            continue;
        }
        if (Burn.Clock >= 0.5f)
        {
            Burn.Clock -= 0.5f;
            const float Damage = Burn.Dps * 0.5f;
            AActor* Caster = Burn.Caster.Get();
            if (ICombatDamageable* Damageable = Cast<ICombatDamageable>(Target))
            {
                Damageable->ApplyDamage(Damage, Caster, Target->GetActorLocation(), FVector::ZeroVector);
            }
            else
            {
                const APawn* Pawn = Cast<APawn>(Caster);
                UGameplayStatics::ApplyDamage(Target, Damage, Pawn ? Pawn->GetController() : nullptr, Caster, UDamageType::StaticClass());
            }
        }
    }

    for (int32 i = Slows.Num() - 1; i >= 0; --i)
    {
        FSlow& Slow = Slows[i];
        AActor* Target = Slow.Target.Get();
        Slow.Remaining -= DeltaTime;
        if (!IsValid(Target))
        {
            Slows.RemoveAtSwap(i);
            continue;
        }
        if (Slow.Remaining <= 0.0f)
        {
            Target->CustomTimeDilation = 1.0f;
            Slows.RemoveAtSwap(i);
            continue;
        }
        // Ease back to full speed over the last half second so a slow never snaps off.
        Target->CustomTimeDilation = FMath::Lerp(1.0f, Slow.Factor, FMath::Clamp(Slow.Remaining / 0.5f, 0.0f, 1.0f));
    }

    for (int32 i = Arcs.Num() - 1; i >= 0; --i)
    {
        Arcs[i].Remaining -= DeltaTime;
        if (Arcs[i].Remaining <= 0.0f || !Arcs[i].Fx.IsValid())
        {
            if (UNiagaraComponent* Fx = Arcs[i].Fx.Get()) Fx->Deactivate();
            Arcs.RemoveAtSwap(i);
        }
    }
}

bool UReflectionsCraftedSpellSubsystem::IsEnemy(const AActor* Actor, const AActor* Caster)
{
    if (!IsValid(Actor) || Actor == Caster || Actor->IsHidden() || IsAttachedTo(Actor, Caster)) return false;
    // Friendly civilians are harmable, as they are for the catalog spells; IsHostile keeps spells from seeking them.
    if (Actor->ActorHasTag(TEXT("Player"))) return false;
    if (Actor->IsA<AReflectionsCraftedSpell>()) return false;
    bool bHarm = true;
    if (NpcCanHarm(Actor, Caster, bHarm) && !bHarm) return false;
    return IsAlive(Actor);
}

bool UReflectionsCraftedSpellSubsystem::IsHostile(const AActor* Actor, const AActor* Caster)
{
    if (!IsEnemy(Actor, Caster)) return false;
    bool bAlly = false;
    if (NpcIsAlly(Actor, Caster, bAlly)) return !bAlly;
    return !Actor->ActorHasTag(TEXT("Friendly"));
}

bool UReflectionsCraftedSpellSubsystem::IsAlly(const AActor* Actor, const AActor* Caster)
{
    if (!IsValid(Actor) || !IsAlive(Actor)) return false;
    if (Actor == Caster) return true;
    bool bAlly = false;
    if (NpcIsAlly(Actor, Caster, bAlly)) return bAlly;
    return Actor->ActorHasTag(TEXT("Friendly"));
}

void UReflectionsCraftedSpellSubsystem::FindEnemies(const FVector& Location, float Radius, const AActor* Caster, TArray<AActor*>& Out,
    bool bHostileOnly) const
{
    TArray<AActor*> All;
    OverlapActors(GetWorld(), Location, Radius, Caster, All);
    for (AActor* Actor : All)
    {
        if (!(bHostileOnly ? IsHostile(Actor, Caster) : IsEnemy(Actor, Caster))) continue;
        // Static set dressing that only happens to be WorldDynamic is ignored unless it can take a hit or move.
        const UPrimitiveComponent* Root = Cast<UPrimitiveComponent>(Actor->GetRootComponent());
        const bool bCanReact = Actor->IsA<APawn>() || Actor->Implements<UCombatDamageable>()
            || Actor->FindComponentByClass<UReflectionsHealthComponent>() || (Root && Root->IsSimulatingPhysics());
        if (bCanReact) Out.Add(Actor);
    }
}

void UReflectionsCraftedSpellSubsystem::FindAllies(const FVector& Location, float Radius, const AActor* Caster, TArray<AActor*>& Out) const
{
    TArray<AActor*> All;
    OverlapActors(GetWorld(), Location, Radius, nullptr, All);
    for (AActor* Actor : All)
    {
        if (IsAlly(Actor, Caster) && Actor->IsA<APawn>()) Out.AddUnique(Actor);
    }
}

AActor* UReflectionsCraftedSpellSubsystem::NearestEnemy(const FVector& Location, float Range, const AActor* Caster,
    const TSet<TWeakObjectPtr<AActor>>* Exclude, const FVector* Direction, float ConeCos) const
{
    TArray<AActor*> Candidates;
    FindEnemies(Location, Range, Caster, Candidates, true);
    AActor* Best = nullptr;
    float BestScore = TNumericLimits<float>::Max();
    for (AActor* Actor : Candidates)
    {
        if (!Actor->IsA<APawn>() && !Actor->FindComponentByClass<UReflectionsHealthComponent>()) continue;
        if (Exclude && Exclude->Contains(Actor)) continue;
        const FVector To = Actor->GetActorLocation() - Location;
        if (Direction && ConeCos > -1.0f && FVector::DotProduct(To.GetSafeNormal(), *Direction) < ConeCos) continue;
        const float Score = To.SizeSquared();
        if (Score < BestScore)
        {
            BestScore = Score;
            Best = Actor;
        }
    }
    return Best;
}

float UReflectionsCraftedSpellSubsystem::HealActor(AActor* Target, float Amount, AActor* Healer)
{
    if (!IsValid(Target) || Amount <= 0.0f) return 0.0f;
    if (UReflectionsHealthComponent* Health = Target->FindComponentByClass<UReflectionsHealthComponent>())
    {
        return Health->Heal(Amount, Healer);
    }
    if (ICombatDamageable* Damageable = Cast<ICombatDamageable>(Target))
    {
        Damageable->ApplyHealing(Amount, Healer);
        return Amount;
    }
    return 0.0f;
}

float UReflectionsCraftedSpellSubsystem::ApplyHit(const FCraftedSpellResolved& Spell, AActor* Target, AActor* Caster, float Scale,
    const FVector& Origin, const FHitResult* DirectHit, bool bQuiet, float BlastRadius)
{
    if (!IsValid(Target) || Scale <= 0.0f) return 0.0f;
    // A healing spell never hurts a friend; its ally pass (FindAllies at each call site) does the healing, once.
    if (Spell.Heal > 0.0f && IsAlly(Target, Caster)) return 0.0f;
    if (!IsEnemy(Target, Caster)) return 0.0f;

    FVector Direction = (Target->GetActorLocation() - Origin).GetSafeNormal2D();
    if (Direction.IsNearlyZero()) Direction = (Target->GetActorLocation() - (Caster ? Caster->GetActorLocation() : Origin)).GetSafeNormal2D();
    if (Direction.IsNearlyZero()) Direction = FVector::ForwardVector;
    UPrimitiveComponent* Primitive = DirectHit ? DirectHit->GetComponent() : Cast<UPrimitiveComponent>(Target->GetRootComponent());
    const FVector Point = DirectHit ? FVector(DirectHit->ImpactPoint) : Target->GetActorLocation();
    const FHitResult Hit = DirectHit ? *DirectHit : FHitResult(Target, Primitive, Point, -Direction);
    const float Damage = Spell.Damage * Scale;
    const float Push = Spell.Impulse * FMath::Sqrt(Scale);
    const FVector Impulse = Direction * Push + FVector(0.0f, 0.0f, Push * 0.15f + Spell.Lift * Scale);

    if (Damage > 0.0f)
    {
        if (ICombatDamageable* Damageable = Cast<ICombatDamageable>(Target))
        {
            Damageable->ApplyDamage(Damage, Caster, Point, Impulse);
        }
        else
        {
            const APawn* Pawn = Cast<APawn>(Caster);
            UGameplayStatics::ApplyPointDamage(Target, Damage, Direction, Hit, Pawn ? Pawn->GetController() : nullptr, Caster, UDamageType::StaticClass());
        }
    }
    if (Push > 1.0f || Spell.Lift > 0.0f)
    {
        if (ACharacter* Character = Cast<ACharacter>(Target))
        {
            Character->LaunchCharacter(Impulse, true, Spell.Lift > 0.0f);
        }
        else if (Primitive && Primitive->IsSimulatingPhysics(Hit.BoneName))
        {
            Primitive->AddImpulseAtLocation(Impulse * Primitive->GetMass() * 0.5f, Point, Hit.BoneName);
        }
    }
    if (Spell.BurnDps > 0.0f) AddBurn(Target, Caster, Spell.BurnDps * Scale, Spell.StatusSeconds);
    if (Spell.SlowFactor < 1.0f) AddSlow(Target, Spell.SlowFactor, Spell.StatusSeconds * FMath::Clamp(Scale, 0.5f, 1.5f));

    // The body's reaction (NPCs pick the animation): a fire burst explodes, a fire bolt burns, lightning electrifies...
    const EReflectionsSpellReaction Reaction = CraftedReaction(Spell, !bQuiet && BlastRadius >= BlastReactionRadius);
    // 1 is a full-power hit at point blank (power-3 fire orb ~0.64, water wave ~1, lightning bolt ~0.34).
    float Magnitude = FMath::Clamp(0.5f * Damage / 28.0f + 0.5f * Push / 800.0f, 0.05f, 1.0f);
    if (BlastRadius > 0.0f)
    {
        Magnitude *= 1.0f - 0.6f * FMath::Clamp(FVector::Dist(Target->GetActorLocation(), Origin) / BlastRadius, 0.0f, 1.0f);
    }
    if (Spell.Recipe.Element == ECraftedSpellElement::Life) Magnitude = FMath::Min(Magnitude * 0.5f, 0.35f);
    bool bRepeat = false;
    const bool bSend = !bQuiet || (NeedsUpkeep(Reaction) && TakeReactionSlot(Target, true, bRepeat));
    if (!bQuiet) TakeReactionSlot(Target, false, bRepeat);

    UReflectionsSpellEventSubsystem* Events = bSend ? GetWorld()->GetSubsystem<UReflectionsSpellEventSubsystem>() : nullptr;
    if (Events)
    {
        // Listeners (hit marker, hit-stop, ragdoll, NPC reactions, reputation) treat this like any other spell hit.
        FReflectionsSpellHitData Data;
        Data.Spell = UReflectionsSpellCraftingLibrary::EventProxy(Spell.Recipe.Element);
        Data.Caster = Caster;
        Data.Target = Target;
        Data.Location = Point;
        Data.Impulse = Impulse;
        Data.ImpactNormal = Hit.ImpactNormal;
        Data.Bone = Hit.BoneName;
        Data.Surface = UPhysicalMaterial::DetermineSurfaceType(Hit.PhysMaterial.Get());
        Data.Reaction = Reaction;
        Data.Magnitude = Magnitude;
        Data.Duration = ReactionSeconds(Spell, Reaction, Scale);
        Data.Origin = Reaction == EReflectionsSpellReaction::Explosion ? Origin : Point;
        Data.bRepeat = bRepeat;
        Events->OnSpellHit.Broadcast(Data);
    }
    if ((!Events || bRepeat) && Caster)
    {
        // Quiet hits still show the hit marker (repeat reaction ticks skip the event's own marker).
        if (UReflectionsSpellAimComponent* Aim = Caster->FindComponentByClass<UReflectionsSpellAimComponent>())
        {
            Aim->NotifyHit(!IsAlive(Target));
        }
    }
    return Damage;
}

void UReflectionsCraftedSpellSubsystem::AddBurn(AActor* Target, AActor* Caster, float Dps, float Seconds)
{
    if (!IsValid(Target) || Dps <= 0.0f || Seconds <= 0.0f) return;
    for (FBurn& Burn : Burns)
    {
        if (Burn.Target == Target)
        {
            Burn.Dps = FMath::Max(Burn.Dps, Dps);
            Burn.Remaining = FMath::Max(Burn.Remaining, Seconds);
            return;
        }
    }
    FBurn Burn;
    Burn.Target = Target;
    Burn.Caster = Caster;
    Burn.Dps = Dps;
    Burn.Remaining = Seconds;
    Burns.Add(Burn);
}

void UReflectionsCraftedSpellSubsystem::AddSlow(AActor* Target, float Factor, float Seconds)
{
    if (!IsValid(Target) || Factor >= 1.0f || Seconds <= 0.0f || Target->IsA<APlayerController>()) return;
    // The local player is never slowed by their own spells.
    if (const APawn* Pawn = Cast<APawn>(Target)) if (Pawn->IsPlayerControlled()) return;
    for (FSlow& Slow : Slows)
    {
        if (Slow.Target == Target)
        {
            Slow.Factor = FMath::Min(Slow.Factor, Factor);
            Slow.Remaining = FMath::Max(Slow.Remaining, Seconds);
            return;
        }
    }
    FSlow Slow;
    Slow.Target = Target;
    Slow.Factor = FMath::Clamp(Factor, 0.02f, 1.0f);
    Slow.Remaining = Seconds;
    Slows.Add(Slow);
    Target->CustomTimeDilation = Slow.Factor;
}

void UReflectionsCraftedSpellSubsystem::Pull(AActor* Target, const FVector& Center, float Strength, float Radius, bool bLift, float DeltaTime,
    const FCraftedSpellResolved* Spell, AActor* Caster)
{
    if (!IsValid(Target) || Strength <= 0.0f || Radius <= 0.0f) return;
    const FVector To = Center - Target->GetActorLocation();
    const float Distance = To.Size2D();
    if (Distance > Radius) return;
    const float Falloff = 0.35f + 0.65f * (1.0f - Distance / Radius);
    bool bRepeat = false;
    if (Spell && TakeReactionSlot(Target, true, bRepeat))
    {
        // Being dragged (or lifted, for Updraft) is a reaction of its own; resent every 0.5 s while it lasts.
        if (UReflectionsSpellEventSubsystem* Events = GetWorld()->GetSubsystem<UReflectionsSpellEventSubsystem>())
        {
            FReflectionsSpellHitData Data;
            Data.Spell = UReflectionsSpellCraftingLibrary::EventProxy(Spell->Recipe.Element);
            Data.Caster = Caster;
            Data.Target = Target;
            Data.Location = Target->GetActorLocation();
            Data.Impulse = bLift ? FVector(0.0f, 0.0f, FMath::Lerp(380.0f, 720.0f, Falloff)) : To.GetSafeNormal2D() * Strength * Falloff;
            Data.ImpactNormal = -To.GetSafeNormal();
            Data.Reaction = bLift ? EReflectionsSpellReaction::Lift : EReflectionsSpellReaction::Pull;
            Data.Magnitude = FMath::Clamp(Strength * Falloff / 900.0f, 0.1f, 1.0f);
            Data.Duration = 0.6f;
            Data.Origin = Center;
            Data.bRepeat = bRepeat;
            Events->OnSpellHit.Broadcast(Data);
        }
    }
    if (ACharacter* Character = MovementCharacter(Target))
    {
        // Re-launch at most ten times a second: enough to drag a crowd without fighting the movement solver every frame.
        const double Now = GetWorld()->GetTimeSeconds();
        double& Last = LastPull.FindOrAdd(Target);
        if (Now - Last < 0.1) return;
        Last = Now;
        FVector Velocity = Distance > 70.0f ? To.GetSafeNormal2D() * Strength * Falloff : FVector::ZeroVector;
        Velocity.Z = bLift ? FMath::Lerp(380.0f, 720.0f, Falloff) : 90.0f;
        if (bLift) Velocity *= FVector(0.35f, 0.35f, 1.0f);
        Character->LaunchCharacter(Velocity, true, true);
    }
    else if (UPrimitiveComponent* Primitive = Cast<UPrimitiveComponent>(Target->GetRootComponent()))
    {
        if (Primitive->IsSimulatingPhysics())
        {
            const FVector Direction = bLift ? FVector::UpVector : To.GetSafeNormal();
            Primitive->AddForce(Direction * Strength * Falloff * 4.0f, NAME_None, true);
        }
    }
}

bool UReflectionsCraftedSpellSubsystem::TakeReactionSlot(AActor* Target, bool bQuiet, bool& bOutRepeat)
{
    const double Now = GetWorld()->GetTimeSeconds();
    double& Last = ReactionSent.FindOrAdd(Target, -1000.0);
    if (!bQuiet)
    {
        bOutRepeat = false;
        Last = Now;
        return true;
    }
    if (Now - Last < 0.5) return false;
    bOutRepeat = Now - Last < 1.5;
    Last = Now;
    return true;
}

UNiagaraSystem* UReflectionsCraftedSpellSubsystem::SystemFor(ECraftedFx Kind, bool& bFallback)
{
    if (!bLoadedSystems)
    {
        bLoadedSystems = true;
        BodySystem = LoadSystemAt(CraftedFolder, TEXT("NS_Crafted_Body"));
        BurstSystem = LoadSystemAt(CraftedFolder, TEXT("NS_Crafted_Burst"));
        ArcSystem = LoadSystemAt(CraftedFolder, TEXT("NS_Crafted_Arc"));
        FieldSystem = LoadSystemAt(CraftedFolder, TEXT("NS_Crafted_Field"));
        UE_CLOG(!BodySystem || !BurstSystem || !ArcSystem || !FieldSystem, LogTemp, Warning,
            TEXT("Spell crafting: some systems under %s are missing (run Tools/SpellCrafting/build_crafted_niagara.py); using the spell core's systems."),
            CraftedFolder);
        if (!BodySystem) BodySystem = LoadSystemAt(CoreFolder, TEXT("NS_Spell_Projectile"));
        if (!BurstSystem) BurstSystem = LoadSystemAt(CoreFolder, TEXT("NS_Spell_Impact"));
        if (!FieldSystem) FieldSystem = LoadSystemAt(CoreFolder, TEXT("NS_Spell_Heal"));
    }
    bFallback = false;
    switch (Kind)
    {
    case ECraftedFx::Body: return BodySystem;
    case ECraftedFx::Burst: return BurstSystem;
    case ECraftedFx::Arc: return ArcSystem;
    case ECraftedFx::Field: return FieldSystem;
    default: return nullptr;
    }
}

void UReflectionsCraftedSpellSubsystem::ApplyLook(UNiagaraComponent* C, const FCraftedSpellLook& Look, float Scale)
{
    if (!C) return;
    C->SetVariableLinearColor(TEXT("User.ColorA"), Look.ColorA);
    C->SetVariableLinearColor(TEXT("User.ColorB"), Look.ColorB);
    C->SetVariableLinearColor(TEXT("User.ColorC"), Look.ColorC);
    C->SetVariableFloat(TEXT("User.Shape"), Look.Shape);
    C->SetVariableFloat(TEXT("User.Density"), Look.Density);
    C->SetVariableFloat(TEXT("User.Size"), Look.Size);
    C->SetVariableFloat(TEXT("User.Swirl"), Look.Swirl);
    C->SetVariableFloat(TEXT("User.Jitter"), Look.Jitter);
    C->SetVariableFloat(TEXT("User.Turbulence"), Look.Turbulence);
    C->SetVariableFloat(TEXT("User.Pulse"), Look.Pulse);
    C->SetVariableFloat(TEXT("User.Spikes"), Look.Spikes);
    C->SetVariableFloat(TEXT("User.Glow"), Look.Glow);
    C->SetVariableFloat(TEXT("User.Gravity"), Look.Gravity);
    C->SetVariableFloat(TEXT("User.Scale"), Scale);
    C->SetVariableFloat(TEXT("User.Intensity"), 1.0f);
    // The spell core's systems, used as a fallback, read these.
    C->SetVariableLinearColor(TEXT("User.Color"), Look.ColorA);
    C->SetVariableLinearColor(TEXT("User.Color2"), Look.ColorB);
    C->SetVariableFloat(TEXT("User.CoreSize"), Look.Size);
    C->SetVariableFloat(TEXT("User.SparkRate"), 60.0f * Look.Density);
    C->SetVariableFloat(TEXT("User.TrailWidth"), Look.Size * 0.6f);
}

UNiagaraComponent* UReflectionsCraftedSpellSubsystem::SpawnFx(ECraftedFx Kind, const FCraftedSpellLook& Look, const FVector& Location,
    const FRotator& Rotation, USceneComponent* AttachTo, float Scale)
{
    UWorld* World = GetWorld();
    if (!World || World->GetNetMode() == NM_DedicatedServer) return nullptr;
    bool bFallback = false;
    UNiagaraSystem* System = SystemFor(Kind, bFallback);
    if (!System) return nullptr;
    UNiagaraComponent* Component = AttachTo
        ? UNiagaraFunctionLibrary::SpawnSystemAttached(System, AttachTo, NAME_None, FVector::ZeroVector, FRotator::ZeroRotator,
            EAttachLocation::KeepRelativeOffset, true, false, ENCPoolMethod::None, true)
        : UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, System, Location, Rotation, FVector(1.0f), true, false, ENCPoolMethod::AutoRelease, true);
    if (!Component) return nullptr;
    ApplyLook(Component, Look, Scale);
    Component->Activate(true);
    return Component;
}

void UReflectionsCraftedSpellSubsystem::SpawnArc(const FCraftedSpellLook& Look, const FVector& Start, const FVector& End, float Seconds)
{
    // Fields carry their radius in Size; an arc only wants a thickness.
    FCraftedSpellLook ArcLook = Look;
    ArcLook.Size = FMath::Clamp(ArcLook.Size, 8.0f, 36.0f);
    UNiagaraComponent* Arc = SpawnFx(ECraftedFx::Arc, ArcLook, Start, (End - Start).Rotation(), nullptr, 1.0f);
    if (!Arc) return;
    Arc->SetVariablePosition(TEXT("User.Start"), Start);
    Arc->SetVariablePosition(TEXT("User.End"), End);
    Arc->SetVariableFloat(TEXT("User.Length"), FVector::Dist(Start, End));
    FArc Entry;
    Entry.Fx = Arc;
    Entry.Remaining = Seconds;
    Arcs.Add(Entry);
}

void UReflectionsCraftedSpellSubsystem::Shake(const FVector& Location, float Strength) const
{
    const UWorld* World = GetWorld();
    APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
    const APawn* Pawn = PC ? PC->GetPawn() : nullptr;
    if (!Pawn) return;
    const float Distance = FVector::Dist(Pawn->GetActorLocation(), Location);
    const float Falloff = 1.0f - FMath::Clamp((Distance - 300.0f) / 2200.0f, 0.0f, 1.0f);
    if (Falloff <= 0.0f) return;
    if (UReflectionsSpellCameraModifier* Modifier = UReflectionsSpellCameraModifier::Get(PC))
    {
        Modifier->AddTrauma(FMath::Clamp(Strength * Falloff, 0.0f, 0.6f));
    }
}

USoundBase* UReflectionsCraftedSpellSubsystem::Cue(const TCHAR* Name)
{
    const FName Key(Name);
    if (const TObjectPtr<USoundBase>* Found = Cues.Find(Key)) return *Found;
    USoundBase* Sound = LoadObject<USoundBase>(nullptr, *FString::Printf(TEXT("/Game/Audio/Jam/Cues/%s.%s"), Name, Name), nullptr, LOAD_NoWarn | LOAD_Quiet);
    Cues.Add(Key, Sound);
    return Sound;
}

void UReflectionsCraftedSpellSubsystem::PlayCastCue(const FCraftedSpellResolved& Spell, const FVector& Location)
{
    const TCHAR* CastName = nullptr;
    const TCHAR* ImpactName = nullptr;
    ElementCues(Spell.Recipe.Element, CastName, ImpactName);
    if (USoundBase* Sound = Cue(CastName))
    {
        const float Pitch = FMath::Clamp(1.18f - 0.07f * Spell.Recipe.Power - (Spell.IsField() ? 0.08f : 0.0f), 0.75f, 1.25f);
        UGameplayStatics::PlaySoundAtLocation(this, Sound, Location, 0.9f, Pitch);
    }
}

void UReflectionsCraftedSpellSubsystem::PlayImpactCue(const FCraftedSpellResolved& Spell, const FVector& Location, float Size, bool bMinor)
{
    const UWorld* World = GetWorld();
    if (!World) return;
    const double Now = World->GetTimeSeconds();
    if (Now - LastImpactCue > 1.0) { LastImpactCue = Now; ImpactCuesThisSecond = 0; }
    // At most ten impacts a second, and minor ones (rain drops, pool ticks) only when it is quiet.
    if (ImpactCuesThisSecond >= (bMinor ? 4 : 10)) return;
    ++ImpactCuesThisSecond;
    const TCHAR* CastName = nullptr;
    const TCHAR* ImpactName = nullptr;
    ElementCues(Spell.Recipe.Element, CastName, ImpactName);
    if (USoundBase* Sound = Cue(ImpactName))
    {
        const float Pitch = FMath::Clamp(1.35f - Size / 600.0f, 0.7f, 1.4f);
        UGameplayStatics::PlaySoundAtLocation(this, Sound, Location, bMinor ? 0.45f : FMath::Clamp(0.6f + Size / 500.0f, 0.6f, 1.2f), Pitch);
    }
}

UAudioComponent* UReflectionsCraftedSpellSubsystem::AttachLoopCue(USceneComponent* AttachTo, const FCraftedSpellResolved& Spell)
{
    USoundBase* Sound = Cue(Spell.Recipe.Element == ECraftedSpellElement::Life ? TEXT("SCue_Shield_Loop") : TEXT("SCue_Projectile_Loop"));
    if (!Sound || !AttachTo) return nullptr;
    return UGameplayStatics::SpawnSoundAttached(Sound, AttachTo, NAME_None, FVector::ZeroVector, EAttachLocation::KeepRelativeOffset, true, 0.6f,
        FMath::Clamp(1.2f - 0.08f * Spell.Recipe.Power, 0.75f, 1.2f));
}

void UReflectionsCraftedSpellSubsystem::PlayUiCue(const TCHAR* Name)
{
    if (USoundBase* Sound = Cue(Name)) UGameplayStatics::PlaySound2D(this, Sound, 0.6f);
}
