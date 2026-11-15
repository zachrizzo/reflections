#include "SpellCrafting/ReflectionsCraftedSpell.h"

#include "SpellCrafting/ReflectionsCraftedSpellSubsystem.h"
#include "SpellCrafting/ReflectionsSpellCraftingLibrary.h"
#include "Hero/ReflectionsSpellAim.h"
#include "Hero/ReflectionsSpellEventSubsystem.h"

#include "Components/CapsuleComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/Pawn.h"
#include "NiagaraComponent.h"
#include "Components/AudioComponent.h"

namespace
{
    using EForm = ECraftedSpellForm;
    using EMod = ECraftedSpellModifier;
    using ETrig = ECraftedSpellTrigger;
    using ESyn = ECraftedSpellSynergy;

    FCollisionObjectQueryParams SweepTypes()
    {
        FCollisionObjectQueryParams Types;
        Types.AddObjectTypesToQuery(ECC_WorldStatic);
        Types.AddObjectTypesToQuery(ECC_WorldDynamic);
        Types.AddObjectTypesToQuery(ECC_Pawn);
        Types.AddObjectTypesToQuery(ECC_PhysicsBody);
        return Types;
    }

    /** Shards thrown by Split, and lances fired by Pierce on a field: small bolts that keep only the behaviours that make sense. */
    FCraftedSpellResolved MakeShard(const FCraftedSpellResolved& Parent, int32 ChildGeneration, bool bLance)
    {
        FCraftedSpellResolved S = Parent;
        S.Recipe.Form = bLance ? EForm::Ray : EForm::Bolt;
        S.Recipe.Trigger = ETrig::Impact;
        S.Recipe.Modifiers.Reset();
        const bool bShatter = Parent.Has(ESyn::Shatterstorm) && ChildGeneration < 2;
        if (Parent.HasModifier(EMod::Homing)) S.Recipe.Modifiers.Add(EMod::Homing);
        if (Parent.HasModifier(EMod::Leech)) S.Recipe.Modifiers.Add(EMod::Leech);
        if (bShatter) { S.Recipe.Modifiers.Add(EMod::Bounce); S.Recipe.Modifiers.Add(EMod::Split); }
        if (bLance) S.Recipe.Modifiers.Add(EMod::Pierce);
        const int32 Keep = (1 << static_cast<int32>(ESyn::Swarm)) | (1 << static_cast<int32>(ESyn::Ricochet)) | (bShatter ? 1 << static_cast<int32>(ESyn::Shatterstorm) : 0);
        S.SynergyMask = Parent.SynergyMask & Keep;
        S.Damage = Parent.Damage * (bLance ? 0.6f : 0.4f);
        S.Heal = Parent.Heal * 0.4f;
        S.Radius = 50.0f;
        S.Impulse = Parent.Impulse * 0.4f;
        S.Speed = bLance ? 26000.0f : 1900.0f;
        S.Range = bLance ? 2600.0f : 1300.0f;
        S.Lifetime = S.Range / S.Speed + 0.05f;
        S.CollisionRadius = bLance ? 5.0f : 9.0f;
        S.SplitCount = bShatter ? 2 : 0;
        S.BounceCount = bShatter ? 1 : 0;
        S.PierceCount = bLance ? 3 : 0;
        S.ChainCount = 0;
        S.PullStrength = 0.0f;
        S.FuseTime = 0.0f;
        S.HazardDuration = 0.0f;
        S.OrbitDuration = 0.0f;
        S.EchoCount = 0;
        S.PulseInterval = 0.0f;
        S.ProximityRadius = 0.0f;
        S.BurnDps = Parent.BurnDps * 0.5f;
        S.Look.Size *= Parent.IsField() ? 0.35f : 0.55f;
        S.Look.Size = FMath::Clamp(S.Look.Size, 8.0f, 30.0f);
        S.Look.Density *= 0.6f;
        S.Look.Shape = bLance ? 3.0f : S.Look.Shape;
        return S;
    }

    /** Pools left by Hazard: a ground field that damages (or heals) on a slow tick and never spawns further pools. */
    FCraftedSpellResolved MakeHazard(const FCraftedSpellResolved& Parent)
    {
        FCraftedSpellResolved S = Parent;
        S.Recipe.Modifiers.Reset();
        if (Parent.Has(ESyn::Sinkhole)) S.Recipe.Modifiers.Add(EMod::Gravity);
        if (Parent.HasModifier(EMod::Leech)) S.Recipe.Modifiers.Add(EMod::Leech);
        S.SynergyMask = Parent.SynergyMask & ((1 << static_cast<int32>(ESyn::Sinkhole)) | (1 << static_cast<int32>(ESyn::Bloodbath))
            | (1 << static_cast<int32>(ESyn::Wildfire)) | (1 << static_cast<int32>(ESyn::Permafrost)) | (1 << static_cast<int32>(ESyn::Sanctuary))
            | (1 << static_cast<int32>(ESyn::Updraft)) | (1 << static_cast<int32>(ESyn::Whirlpool)));
        S.Damage = Parent.Damage * 0.22f;
        S.Heal = Parent.Heal * 0.2f;
        S.Impulse = 0.0f;
        S.Lift = 0.0f;
        S.Radius = Parent.HazardRadius;
        S.PullRadius = Parent.HazardRadius * 1.3f;
        S.PullStrength = Parent.Has(ESyn::Sinkhole) ? FMath::Max(Parent.PullStrength * 0.6f, 500.0f) : 0.0f;
        S.SplitCount = S.BounceCount = S.PierceCount = S.ChainCount = S.EchoCount = 0;
        S.HazardDuration = 0.0f;
        S.FuseTime = 0.0f;
        S.Lifetime = Parent.HazardDuration;
        S.Look.Size = Parent.HazardRadius;
        return S;
    }
}

AReflectionsCraftedSpell::AReflectionsCraftedSpell()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickGroup = TG_PrePhysics;
    Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    SetRootComponent(Root);
    SetCanBeDamaged(false);
}

UReflectionsCraftedSpellSubsystem* AReflectionsCraftedSpell::Services() const
{
    return UReflectionsCraftedSpellSubsystem::Get(this);
}

void AReflectionsCraftedSpell::CastSpell(UWorld* World, const FCraftedSpellResolved& Spell, AActor* Caster, const FVector& Origin,
    const FVector& Target, AActor* AimTarget, float Scale)
{
    if (!World) return;
    const ECraftedSpellForm Form = Spell.Recipe.Form;
    if (Spell.IsField())
    {
        SpawnSpell(World, Spell, Caster, ECraftedSpellMode::Field, Origin, Target, AimTarget, Scale, 0);
        return;
    }
    if (Form == EForm::Ray && Spell.Recipe.Trigger == ETrig::Pulse)
    {
        SpawnSpell(World, Spell, Caster, ECraftedSpellMode::Beam, Origin, Target, AimTarget, Scale, 0);
        return;
    }
    if (Spell.HasModifier(EMod::Orbit))
    {
        // Satellites: the split happens up front, as a ring of orbiters.
        const int32 Count = Spell.Has(ESyn::Satellites) ? FMath::Max(2, Spell.SplitCount) : 1;
        FCraftedSpellResolved Orbiter = Spell;
        if (Count > 1)
        {
            Orbiter.Damage *= 0.6f;
            Orbiter.SplitCount = 0;
            Orbiter.Look.Size *= 0.75f;
        }
        for (int32 i = 0; i < Count; ++i)
        {
            SpawnSpell(World, Orbiter, Caster, ECraftedSpellMode::Satellite, Origin, Target, AimTarget, Scale, 0, 2.0f * PI * i / Count);
        }
        return;
    }
    SpawnSpell(World, Spell, Caster, ECraftedSpellMode::Projectile, Origin, Target, AimTarget, Scale, 0);
}

AReflectionsCraftedSpell* AReflectionsCraftedSpell::SpawnSpell(UWorld* World, const FCraftedSpellResolved& Spell, AActor* Caster,
    ECraftedSpellMode Mode, const FVector& Origin, const FVector& Target, AActor* AimTarget, float Scale, int32 Generation, float Phase)
{
    FActorSpawnParameters Params;
    Params.Owner = Caster;
    Params.Instigator = Cast<APawn>(Caster);
    Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    FVector Direction = (Target - Origin).GetSafeNormal();
    if (Direction.IsNearlyZero()) Direction = Caster ? Caster->GetActorForwardVector() : FVector::ForwardVector;
    AReflectionsCraftedSpell* Actor = World->SpawnActor<AReflectionsCraftedSpell>(AReflectionsCraftedSpell::StaticClass(), Origin, Direction.Rotation(), Params);
    if (!Actor) return nullptr;
    Actor->Spell = Spell;
    Actor->Caster = Caster;
    Actor->Start(Mode, Origin, Target, AimTarget, Scale, Generation, Phase);
    // Shards and lances skip their dynamic light: a Shatterstorm can put dozens in the air at once.
    if (Generation > 0 && Mode == ECraftedSpellMode::Projectile) Actor->SetFxFloat(TEXT("User.Light"), 0.0f);
    return Actor;
}

void AReflectionsCraftedSpell::Start(ECraftedSpellMode InMode, const FVector& Origin, const FVector& Target, AActor* AimTarget, float InScale,
    int32 InGeneration, float Phase)
{
    Mode = InMode;
    Scale = InScale;
    Generation = InGeneration;
    TargetPoint = Target;
    LegStart = Origin;
    HomingTarget = AimTarget;
    BouncesLeft = Spell.BounceCount;
    PiercesLeft = Spell.PierceCount;
    Life = FMath::Max(0.1f, Spell.Lifetime);
    OrbitAngle = Phase;
    bRay = Spell.Recipe.Form == EForm::Ray;
    FVector Direction = (Target - Origin).GetSafeNormal();
    if (Direction.IsNearlyZero()) Direction = GetActorForwardVector();
    Velocity = Direction * Spell.Speed;
    UReflectionsCraftedSpellSubsystem* S = Services();
    if (!S) return;

    switch (Mode)
    {
    case ECraftedSpellMode::Projectile:
    case ECraftedSpellMode::Satellite:
        Fx = S->SpawnFx(bRay ? ECraftedFx::Arc : ECraftedFx::Body, Spell.Look, Origin, Direction.Rotation(), bRay ? nullptr : Root, Scale);
        if (Mode == ECraftedSpellMode::Satellite) Life = Spell.OrbitDuration + Spell.Range / FMath::Max(Spell.Speed, 1.0f) + 0.5f;
        if (InGeneration == 0 && (Spell.Recipe.Form == EForm::Orb || Mode == ECraftedSpellMode::Satellite)) Loop = S->AttachLoopCue(Root, Spell);
        break;
    case ECraftedSpellMode::Beam:
        Fx = S->SpawnFx(ECraftedFx::Arc, Spell.Look, Origin, Direction.Rotation(), nullptr, Scale);
        if (Fx) Fx->SetVariableFloat(TEXT("User.Size"), FMath::Clamp(Spell.Look.Size * 1.5f, 10.0f, 36.0f));
        break;
    case ECraftedSpellMode::Field:
    {
        const EForm Form = Spell.Recipe.Form;
        const bool bOnCaster = Form == EForm::Aura || Form == EForm::Wave || Spell.Has(ESyn::Escort);
        Anchor = bOnCaster ? CasterFeet() : GroundBelow(Target);
        WaveDirection = (Target - Origin).GetSafeNormal2D();
        if (WaveDirection.IsNearlyZero()) WaveDirection = Caster.IsValid() ? Caster->GetActorForwardVector() : FVector::ForwardVector;
        SetActorLocationAndRotation(Anchor, WaveDirection.Rotation());
        FieldClock = -(Spell.StartDelay + Spell.FuseTime);
        HopsLeft = Spell.BounceCount;
        if (Form != EForm::Wave)
        {
            Fx = S->SpawnFx(ECraftedFx::Field, Spell.Look, Anchor, FRotator::ZeroRotator, Root, Scale);
            SetFxFloat(TEXT("User.Radius"), Spell.Radius);
            SetFxFloat(TEXT("User.Rain"), Form == EForm::Rain ? 1.0f : 0.0f);
            SetFxFloat(TEXT("User.Height"), Form == EForm::Rain ? 520.0f : 0.0f);
            SetFxFloat(TEXT("User.Pull"), Spell.PullStrength > 0.0f ? (Spell.Has(ESyn::Updraft) ? -1.0f : 1.0f) : 0.0f);
            SetFxFloat(TEXT("User.Ring"), Form == EForm::Rune || Form == EForm::Aura ? 1.0f : 0.4f);
            SetFxFloat(TEXT("User.Intensity"), FieldClock < 0.0f ? 0.35f : 1.0f);
            if (Form == EForm::Rain || Form == EForm::Aura) Loop = S->AttachLoopCue(Root, Spell);
        }
        break;
    }
    case ECraftedSpellMode::Hazard:
        Anchor = GroundBelow(Origin);
        SetActorLocation(Anchor);
        HazardRadius = Spell.Radius;
        Fx = S->SpawnFx(ECraftedFx::Field, Spell.Look, Anchor, FRotator::ZeroRotator, Root, Scale);
        SetFxFloat(TEXT("User.Radius"), HazardRadius);
        SetFxFloat(TEXT("User.Rain"), 0.0f);
        SetFxFloat(TEXT("User.Height"), 0.0f);
        SetFxFloat(TEXT("User.Ring"), 0.15f);
        SetFxFloat(TEXT("User.Pull"), Spell.PullStrength > 0.0f ? 1.0f : 0.0f);
        SetFxFloat(TEXT("User.Density"), Spell.Look.Density * 0.7f);
        break;
    default:
        break;
    }
    if (Fx && bRay)
    {
        Fx->SetVariablePosition(TEXT("User.Start"), Origin);
        Fx->SetVariablePosition(TEXT("User.End"), Origin);
    }
}

void AReflectionsCraftedSpell::SetFxFloat(FName Name, float Value)
{
    if (Fx) Fx->SetVariableFloat(Name, Value);
}

FCollisionQueryParams AReflectionsCraftedSpell::QueryParams() const
{
    FCollisionQueryParams Query(SCENE_QUERY_STAT(CraftedSpellSweep), false, this);
    Query.bReturnPhysicalMaterial = true;
    if (AActor* C = Caster.Get())
    {
        Query.AddIgnoredActor(C);
        TArray<AActor*> Attached;
        C->GetAttachedActors(Attached, true, true);
        Query.AddIgnoredActors(Attached);
    }
    for (const TWeakObjectPtr<AActor>& Actor : Pierced)
    {
        if (Actor.IsValid()) Query.AddIgnoredActor(Actor.Get());
    }
    return Query;
}

FVector AReflectionsCraftedSpell::GroundBelow(const FVector& Point, float Up) const
{
    FHitResult Hit;
    FCollisionQueryParams Query(SCENE_QUERY_STAT(CraftedSpellGround), false, this);
    if (AActor* C = Caster.Get()) Query.AddIgnoredActor(C);
    if (GetWorld()->LineTraceSingleByChannel(Hit, Point + FVector(0, 0, Up), Point - FVector(0, 0, 3000.0f), ECC_Visibility, Query))
    {
        return Hit.ImpactPoint + FVector(0, 0, 2.0f);
    }
    return Point;
}

FVector AReflectionsCraftedSpell::CasterFeet() const
{
    const AActor* C = Caster.Get();
    if (!C) return GetActorLocation();
    float HalfHeight = 90.0f;
    if (const ACharacter* Character = Cast<ACharacter>(C)) HalfHeight = Character->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
    return C->GetActorLocation() - FVector(0, 0, HalfHeight - 2.0f);
}

FVector AReflectionsCraftedSpell::BeamOrigin() const
{
    const AActor* C = Caster.Get();
    if (!C) return GetActorLocation();
    return C->GetActorLocation() + FVector(0, 0, 45.0f) + C->GetActorForwardVector() * 45.0f;
}

void AReflectionsCraftedSpell::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    Age += DeltaSeconds;
    ShardClock -= DeltaSeconds;
    for (auto It = RecentHits.CreateIterator(); It; ++It)
    {
        It.Value() -= DeltaSeconds;
        if (It.Value() <= 0.0f || !It.Key().IsValid()) It.RemoveCurrent();
    }
    TickChains(DeltaSeconds);
    switch (Mode)
    {
    case ECraftedSpellMode::Projectile: TickProjectile(DeltaSeconds); break;
    case ECraftedSpellMode::Satellite: TickSatellite(DeltaSeconds); break;
    case ECraftedSpellMode::Beam: TickBeam(DeltaSeconds); break;
    case ECraftedSpellMode::Mine: TickMine(DeltaSeconds); break;
    case ECraftedSpellMode::Fuse: TickFuse(DeltaSeconds); break;
    case ECraftedSpellMode::Field: TickField(DeltaSeconds); break;
    case ECraftedSpellMode::Hazard: TickHazard(DeltaSeconds); break;
    default: return;
    }
    if (Mode != ECraftedSpellMode::Spent && Spell.PullStrength > 0.0f) TickPull(DeltaSeconds);
}

// ------------------------------------------------------------------------------------------------ projectile
void AReflectionsCraftedSpell::Steer(float DeltaSeconds)
{
    if (Spell.HomingStrength <= 0.0f) return;
    UReflectionsCraftedSpellSubsystem* S = Services();
    RetargetClock -= DeltaSeconds;
    const FVector Location = GetActorLocation();
    const FVector Direction = Velocity.GetSafeNormal();
    if ((!HomingTarget.IsValid() || !UReflectionsCraftedSpellSubsystem::IsHostile(HomingTarget.Get(), Caster.Get())) && RetargetClock <= 0.0f && S)
    {
        RetargetClock = 0.2f;
        HomingTarget = S->NearestEnemy(Location, 2600.0f, Caster.Get(), &Pierced, &Direction, FMath::Cos(FMath::DegreesToRadians(75.0f)));
    }
    if (const AActor* Target = HomingTarget.Get())
    {
        const FVector Desired = (Target->GetActorLocation() + FVector(0, 0, 20.0f) - Location).GetSafeNormal();
        const FVector NewDirection = (Direction + Desired * Spell.HomingStrength * DeltaSeconds).GetSafeNormal();
        Velocity = NewDirection * Velocity.Size();
    }
}

void AReflectionsCraftedSpell::TickProjectile(float DeltaSeconds)
{
    if (Age >= Life)
    {
        // Out of range. Airbursts still go off; plain bolts fizzle with a small puff.
        if (Spell.Recipe.Trigger == ETrig::Airburst || Spell.Recipe.Trigger == ETrig::Proximity) Fire(GetActorLocation(), -Velocity.GetSafeNormal(), nullptr, nullptr);
        else Expire();
        return;
    }
    Steer(DeltaSeconds);
    if (Spell.Recipe.Trigger == ETrig::Pulse && Spell.PulseInterval > 0.0f)
    {
        PulseClock += DeltaSeconds;
        if (PulseClock >= Spell.PulseInterval)
        {
            PulseClock -= Spell.PulseInterval;
            Payload(GetActorLocation(), -Velocity.GetSafeNormal(), nullptr, nullptr, Scale * 0.35f, false, false, false);
        }
    }
    const FVector Location = GetActorLocation();
    const FVector Step = Velocity * DeltaSeconds;
    const ETrig Trigger = Spell.Recipe.Trigger;
    if (Generation == 0 && (Trigger == ETrig::Airburst || Trigger == ETrig::Proximity)
        && FVector::DistSquared(Location, TargetPoint) <= Step.SizeSquared() && Spell.HomingStrength <= 0.0f)
    {
        // Stop exactly on the aim point.
        FHitResult Blocked;
        if (!GetWorld()->SweepSingleByObjectType(Blocked, Location, TargetPoint, FQuat::Identity, SweepTypes(),
            FCollisionShape::MakeSphere(Spell.CollisionRadius), QueryParams()))
        {
            SetActorLocation(TargetPoint);
            if (bRay && Fx) Fx->SetVariablePosition(TEXT("User.End"), TargetPoint);
            if (Trigger == ETrig::Proximity) BecomeMine(TargetPoint);
            else Fire(TargetPoint, -Velocity.GetSafeNormal(), nullptr, nullptr);
            return;
        }
    }
    FHitResult Hit;
    if (GetWorld()->SweepSingleByObjectType(Hit, Location, Location + Step, FQuat::Identity, SweepTypes(),
        FCollisionShape::MakeSphere(Spell.CollisionRadius), QueryParams()))
    {
        HandleHit(Hit);
        return;
    }
    SetActorLocationAndRotation(Location + Step, Velocity.Rotation());
    Travelled += Step.Size();
    if (bRay && Fx) Fx->SetVariablePosition(TEXT("User.End"), Location + Step);
}

void AReflectionsCraftedSpell::HandleHit(const FHitResult& Hit)
{
    UReflectionsCraftedSpellSubsystem* S = Services();
    AActor* Other = Hit.GetActor();
    const bool bEnemy = UReflectionsCraftedSpellSubsystem::IsEnemy(Other, Caster.Get());
    FVector Normal = Hit.ImpactNormal.GetSafeNormal();
    if (Normal.IsNearlyZero()) Normal = -Velocity.GetSafeNormal();
    const FVector Direction = Velocity.GetSafeNormal();
    const FVector HitLocation = Hit.bStartPenetrating ? GetActorLocation() : FVector(Hit.Location);

    if (bEnemy && PiercesLeft > 0 && S)
    {
        const float Dealt = S->ApplyHit(Spell, Other, Caster.Get(), Scale, HitLocation - Direction * 20.0f, &Hit);
        if (Spell.LeechFraction > 0.0f) S->HealActor(Caster.Get(), Dealt * Spell.LeechFraction, Caster.Get());
        if (Spell.Has(ESyn::Conductor)) StartChain(Other, Other->GetActorLocation(), FMath::Max(1, Spell.ChainCount - 1), Scale * 0.7f, {Other});
        S->SpawnFx(ECraftedFx::Burst, Spell.Look, Hit.ImpactPoint, Normal.Rotation(), nullptr, 0.35f);
        Pierced.Add(Other);
        --PiercesLeft;
        SetActorLocation(HitLocation + Direction * 4.0f);
        return;
    }
    if (BouncesLeft > 0)
    {
        if (bEnemy && S)
        {
            const float Dealt = S->ApplyHit(Spell, Other, Caster.Get(), Scale * (Spell.Has(ESyn::Boulder) ? 0.9f : 0.6f), HitLocation - Direction * 20.0f, &Hit);
            if (Spell.LeechFraction > 0.0f) S->HealActor(Caster.Get(), Dealt * Spell.LeechFraction, Caster.Get());
            Pierced.Add(Other);
        }
        if (Spell.Has(ESyn::Shatterstorm) && Generation < 2) SpawnShards(HitLocation, Normal, 2, false);
        Velocity = (Velocity - 2.0f * FVector::DotProduct(Velocity, Normal) * Normal) * (Spell.Has(ESyn::Boulder) ? 0.85f : 1.0f);
        if (S && (bEnemy || Spell.Has(ESyn::Ricochet)))
        {
            // Off an enemy, a bounce ricochets toward the next one nearby; Ricochet (with Homing) also seeks after wall bounces.
            const FVector NewDirection = Velocity.GetSafeNormal();
            TSet<TWeakObjectPtr<AActor>> Exclude = Pierced;
            Exclude.Add(Other);
            AActor* Next = S->NearestEnemy(HitLocation, bEnemy ? 1500.0f : 2600.0f, Caster.Get(), &Exclude, bEnemy ? nullptr : &NewDirection, -0.2f);
            if (Next && bEnemy)
            {
                Velocity = (Next->GetActorLocation() + FVector(0, 0, 30.0f) - HitLocation).GetSafeNormal() * Velocity.Size();
            }
            if (Spell.Has(ESyn::Ricochet)) HomingTarget = Next;
        }
        --BouncesLeft;
        if (S) S->SpawnFx(ECraftedFx::Burst, Spell.Look, Hit.ImpactPoint, Normal.Rotation(), nullptr, 0.3f);
        if (bRay)
        {
            S->SpawnArc(Spell.Look, LegStart, HitLocation, 0.3f);
            LegStart = HitLocation;
            if (Fx) Fx->SetVariablePosition(TEXT("User.Start"), LegStart);
        }
        SetActorLocation(HitLocation + Normal * (Spell.CollisionRadius + 2.0f));
        // Bounced spells forget who they pierced or hit only after leaving them.
        return;
    }
    if (bRay && Fx) Fx->SetVariablePosition(TEXT("User.End"), HitLocation);
    Fire(Hit.ImpactPoint, Normal, bEnemy ? Other : nullptr, &Hit);
}

void AReflectionsCraftedSpell::Fire(const FVector& Location, const FVector& Normal, AActor* DirectHit, const FHitResult* Hit)
{
    if (Spell.FuseTime > 0.0f && !bFused && Mode != ECraftedSpellMode::Field)
    {
        BecomeFuse(Location + Normal * 6.0f, DirectHit);
        return;
    }
    if (Spell.Recipe.Trigger == ETrig::Proximity && Mode == ECraftedSpellMode::Projectile && !DirectHit)
    {
        BecomeMine(Location + Normal * 8.0f);
        return;
    }
    Payload(Location, Normal, DirectHit, Hit, bFused ? Scale * Spell.FuseScale : Scale, true, true, true);
    Expire();
}

TArray<AActor*> AReflectionsCraftedSpell::Payload(const FVector& Location, const FVector& Normal, AActor* DirectHit, const FHitResult* Hit,
    float PayloadScale, bool bChain, bool bSplit, bool bHazard)
{
    TArray<AActor*> Enemies;
    UReflectionsCraftedSpellSubsystem* S = Services();
    if (!S) return Enemies;
    AActor* C = Caster.Get();
    const float Radius = Spell.Radius * FMath::Sqrt(FMath::Clamp(PayloadScale, 0.2f, 3.0f));
    S->FindEnemies(Location, Radius, C, Enemies);
    if (DirectHit && UReflectionsCraftedSpellSubsystem::IsEnemy(DirectHit, C)) Enemies.AddUnique(DirectHit);
    // Rhythmic payloads (auras, pulses, beams) hit quietly so the shared hit-stop does not stutter every tick.
    const bool bQuiet = PayloadScale < 0.5f || Spell.Recipe.Form == EForm::Aura || Spell.Recipe.Form == EForm::Rain
        || (Spell.Recipe.Trigger == ETrig::Pulse && Mode == ECraftedSpellMode::Field);
    float Dealt = 0.0f;
    for (AActor* Enemy : Enemies)
    {
        Dealt += S->ApplyHit(Spell, Enemy, C, PayloadScale, Location - FVector(0, 0, 40.0f), Enemy == DirectHit ? Hit : nullptr, bQuiet, Radius);
    }
    if (Spell.Heal > 0.0f)
    {
        TArray<AActor*> Allies;
        S->FindAllies(Location, Radius + 120.0f, C, Allies);
        for (AActor* Ally : Allies) S->HealActor(Ally, Spell.Heal * PayloadScale, C);
    }
    if (Spell.LeechFraction > 0.0f && Dealt > 0.0f) S->HealActor(C, Dealt * Spell.LeechFraction, C);

    if (bChain && Spell.ChainCount > 0)
    {
        AActor* From = DirectHit ? DirectHit : (Enemies.Num() > 0 ? Enemies[0] : nullptr);
        if (!From) From = S->NearestEnemy(Location, Spell.ChainRange, C);
        if (From) StartChain(From, Location, Spell.ChainCount, PayloadScale * 0.75f, Enemies);
    }
    if (bSplit && Spell.SplitCount > 0 && Generation < 3) SpawnShards(Location, Normal, Spell.SplitCount, Spell.IsField());
    if (bHazard && Spell.HazardDuration > 0.0f) SpawnHazard(Location);

    const float VisualScale = FMath::Clamp(FMath::Max(Radius, 60.0f) / 220.0f, 0.25f, 3.0f);
    if (UNiagaraComponent* Burst = S->SpawnFx(ECraftedFx::Burst, Spell.Look, Location, Normal.Rotation(), nullptr, VisualScale))
    {
        Burst->SetVariableVec3(TEXT("User.Normal"), Normal);
        Burst->SetVariableFloat(TEXT("User.Radius"), Radius);
    }
    S->Shake(Location, 0.08f + Radius / 1600.0f);
    S->PlayImpactCue(Spell, Location, Radius, bQuiet);
    if (UReflectionsSpellEventSubsystem* Events = GetWorld()->GetSubsystem<UReflectionsSpellEventSubsystem>())
    {
        Events->BroadcastSpell(UReflectionsSpellCraftingLibrary::EventProxy(Spell.Recipe.Element), Location, C, Spell.Damage * PayloadScale + Radius * 0.02f);
    }
    return Enemies;
}

// ------------------------------------------------------------------------------------------------ chain, shards, hazard
void AReflectionsCraftedSpell::StartChain(AActor* From, const FVector& FromLocation, int32 Jumps, float ChainScale, const TArray<AActor*>& AlreadyHit)
{
    if (Jumps <= 0 || !From) return;
    FChainJump Jump;
    Jump.From = From;
    Jump.FromLocation = FromLocation;
    Jump.Remaining = Jumps;
    Jump.Scale = ChainScale;
    Jump.Clock = 0.06f;
    Jump.Hit.Add(From);
    for (AActor* Actor : AlreadyHit) Jump.Hit.Add(Actor);
    Chains.Add(MoveTemp(Jump));
}

void AReflectionsCraftedSpell::TickChains(float DeltaSeconds)
{
    UReflectionsCraftedSpellSubsystem* S = Services();
    if (!S) return;
    for (int32 i = Chains.Num() - 1; i >= 0; --i)
    {
        FChainJump& Jump = Chains[i];
        Jump.Clock -= DeltaSeconds;
        if (Jump.Clock > 0.0f) continue;
        Jump.Clock = 0.08f;
        const FVector From = Jump.From.IsValid() ? Jump.From->GetActorLocation() : Jump.FromLocation;
        AActor* Next = S->NearestEnemy(From, Spell.ChainRange, Caster.Get(), &Jump.Hit);
        if (!Next || Jump.Remaining <= 0)
        {
            Chains.RemoveAtSwap(i);
            continue;
        }
        const FVector To = Next->GetActorLocation();
        S->SpawnArc(Spell.Look, From, To, 0.22f);
        const float Dealt = S->ApplyHit(Spell, Next, Caster.Get(), Jump.Scale, From);
        if (Spell.LeechFraction > 0.0f) S->HealActor(Caster.Get(), Dealt * Spell.LeechFraction, Caster.Get());
        S->SpawnFx(ECraftedFx::Burst, Spell.Look, To, FRotator(90, 0, 0), nullptr, 0.3f);
        Jump.Hit.Add(Next);
        Jump.From = Next;
        Jump.FromLocation = To;
        Jump.Scale *= 0.85f;
        --Jump.Remaining;
    }
}

void AReflectionsCraftedSpell::SpawnShards(const FVector& Location, const FVector& Normal, int32 Count, bool bRadial)
{
    UWorld* World = GetWorld();
    UReflectionsCraftedSpellSubsystem* S = Services();
    if (!World || !S || Count <= 0) return;
    const FCraftedSpellResolved Shard = MakeShard(Spell, Generation + 1, false);
    // Swarm: hand each shard its own target.
    TArray<AActor*> Targets;
    if (Spell.Has(ESyn::Swarm))
    {
        S->FindEnemies(Location, 2200.0f, Caster.Get(), Targets, true);
        Targets.RemoveAll([](AActor* A) { return !A->IsA<APawn>(); });
        Targets.Sort([&Location](const AActor& A, const AActor& B) { return FVector::DistSquared(A.GetActorLocation(), Location) < FVector::DistSquared(B.GetActorLocation(), Location); });
    }
    FVector Base = bRadial ? (Caster.IsValid() ? Caster->GetActorForwardVector() : FVector::ForwardVector)
        : (Velocity.IsNearlyZero() ? Normal : (Velocity - 2.0f * FVector::DotProduct(Velocity, Normal) * Normal).GetSafeNormal());
    Base = (Base.GetSafeNormal2D() * 0.9f + FVector(0, 0, 0.12f)).GetSafeNormal();
    if (Base.IsNearlyZero()) Base = FVector::ForwardVector;
    const float Fan = bRadial ? 360.0f : 110.0f;
    const FVector Lift = Normal.Z > 0.5f ? FVector(0, 0, 25.0f) : Normal * 20.0f;
    for (int32 i = 0; i < Count; ++i)
    {
        const float Alpha = bRadial ? float(i) / Count : (Count > 1 ? float(i) / (Count - 1) - 0.5f : 0.0f);
        const FVector Direction = Base.RotateAngleAxis(Alpha * Fan, FVector::UpVector);
        const FVector ShardStart = Location + Lift + Direction * 15.0f;
        AActor* Target = Targets.Num() > 0 ? Targets[i % Targets.Num()] : nullptr;
        SpawnSpell(World, Shard, Caster.Get(), ECraftedSpellMode::Projectile, ShardStart, ShardStart + Direction * 1000.0f, Target, Scale, Generation + 1);
    }
}

void AReflectionsCraftedSpell::FireLance(const FVector& From)
{
    UWorld* World = GetWorld();
    UReflectionsCraftedSpellSubsystem* S = Services();
    if (!World || !S) return;
    AActor* Target = S->NearestEnemy(From, 2400.0f, Caster.Get());
    if (!Target) return;
    const FVector LanceStart = From + FVector(0, 0, 90.0f);
    const FCraftedSpellResolved Lance = MakeShard(Spell, Generation + 1, true);
    SpawnSpell(World, Lance, Caster.Get(), ECraftedSpellMode::Projectile, LanceStart, Target->GetActorLocation(), Target, Scale, Generation + 1);
}

void AReflectionsCraftedSpell::SpawnHazard(const FVector& Location)
{
    if (UWorld* World = GetWorld())
    {
        SpawnSpell(World, MakeHazard(Spell), Caster.Get(), ECraftedSpellMode::Hazard, Location, Location, nullptr, Scale, Generation + 1);
    }
}

// ------------------------------------------------------------------------------------------------ satellite, beam, mine, fuse
void AReflectionsCraftedSpell::TickSatellite(float DeltaSeconds)
{
    AActor* C = Caster.Get();
    UReflectionsCraftedSpellSubsystem* S = Services();
    if (!C || !S || Age >= Life)
    {
        Expire();
        return;
    }
    if (Age >= Spell.OrbitDuration)
    {
        // Launch at whatever is closest; with nothing around, the satellite fades.
        AActor* Target = HomingTarget.IsValid() && UReflectionsCraftedSpellSubsystem::IsHostile(HomingTarget.Get(), C) ? HomingTarget.Get()
            : S->NearestEnemy(C->GetActorLocation(), Spell.Range, C);
        if (!Target)
        {
            Expire();
            return;
        }
        Mode = ECraftedSpellMode::Projectile;
        HomingTarget = Target;
        Velocity = (Target->GetActorLocation() - GetActorLocation()).GetSafeNormal() * FMath::Max(Spell.Speed, 900.0f);
        Spell.HomingStrength = FMath::Max(Spell.HomingStrength, 3.0f);
        Age = 0.0f;
        Life = Spell.Range / Velocity.Size() + 0.2f;
        return;
    }
    const float AngularSpeed = FMath::Clamp(FMath::Max(Spell.Speed, 600.0f) / FMath::Max(Spell.OrbitRadius, 50.0f), 2.2f, 5.0f);
    OrbitAngle += AngularSpeed * DeltaSeconds;
    const float Bob = FMath::Sin(Age * 3.0f + OrbitAngle) * 12.0f;
    const FVector Location = C->GetActorLocation() + FVector(FMath::Cos(OrbitAngle), FMath::Sin(OrbitAngle), 0.0f) * Spell.OrbitRadius + FVector(0, 0, 25.0f + Bob);
    Velocity = (Location - GetActorLocation()) / FMath::Max(DeltaSeconds, 0.001f);
    SetActorLocationAndRotation(Location, Velocity.Rotation());
    TArray<AActor*> Touching;
    S->FindEnemies(Location, Spell.CollisionRadius + 45.0f, C, Touching);
    for (AActor* Enemy : Touching)
    {
        if (RecentHits.Contains(Enemy)) continue;
        RecentHits.Add(Enemy, 0.6f);
        const float Dealt = S->ApplyHit(Spell, Enemy, C, Scale * 0.6f, C->GetActorLocation());
        if (Spell.LeechFraction > 0.0f) S->HealActor(C, Dealt * Spell.LeechFraction, C);
        if (Spell.ChainCount > 0) StartChain(Enemy, Enemy->GetActorLocation(), Spell.ChainCount, Scale * 0.5f, {Enemy});
        S->SpawnFx(ECraftedFx::Burst, Spell.Look, Enemy->GetActorLocation(), Velocity.Rotation(), nullptr, 0.35f);
    }
}

void AReflectionsCraftedSpell::TickBeam(float DeltaSeconds)
{
    UReflectionsCraftedSpellSubsystem* S = Services();
    AActor* C = Caster.Get();
    if (!S || !C || Age >= Life)
    {
        Expire();
        return;
    }
    // Held ray: follows the reticle every frame, applies its payload on the pulse.
    const FVector BeamStart = BeamOrigin();
    FVector Aim = BeamStart + C->GetActorForwardVector() * Spell.Range;
    if (const UReflectionsSpellAimComponent* AimComponent = C->FindComponentByClass<UReflectionsSpellAimComponent>())
    {
        const FVector Point = AimComponent->GetAimPoint();
        if (!Point.IsNearlyZero() && FVector::DotProduct(Point - BeamStart, C->GetActorForwardVector()) > 50.0f) Aim = Point;
    }
    FVector Direction = (Aim - BeamStart).GetSafeNormal();
    if (Spell.HomingStrength > 0.0f)
    {
        if (AActor* Target = S->NearestEnemy(BeamStart, Spell.Range, C, nullptr, &Direction, FMath::Cos(FMath::DegreesToRadians(25.0f))))
        {
            Direction = (Target->GetActorLocation() - BeamStart).GetSafeNormal();
        }
    }
    const FVector End = BeamStart + Direction * Spell.Range;
    TArray<FHitResult> Hits;
    GetWorld()->SweepMultiByObjectType(Hits, BeamStart, End, FQuat::Identity, SweepTypes(), FCollisionShape::MakeSphere(Spell.CollisionRadius * 2.0f), QueryParams());
    FVector Stop = End;
    TArray<AActor*> Struck;
    for (const FHitResult& Hit : Hits)
    {
        AActor* Actor = Hit.GetActor();
        if (UReflectionsCraftedSpellSubsystem::IsEnemy(Actor, C))
        {
            Struck.AddUnique(Actor);
            if (Struck.Num() > Spell.PierceCount) { Stop = Hit.ImpactPoint; break; }
            continue;
        }
        if (Hit.bBlockingHit) { Stop = Hit.ImpactPoint; break; }
    }
    if (Fx)
    {
        Fx->SetVariablePosition(TEXT("User.Start"), BeamStart);
        Fx->SetVariablePosition(TEXT("User.End"), Stop);
        Fx->SetVariableFloat(TEXT("User.Length"), FVector::Dist(BeamStart, Stop));
    }
    SetActorLocation(Stop);
    PulseClock += DeltaSeconds;
    if (PulseClock < Spell.PulseInterval) return;
    PulseClock -= Spell.PulseInterval;
    for (AActor* Actor : Struck)
    {
        const float Dealt = S->ApplyHit(Spell, Actor, C, Scale * 0.45f, BeamStart, nullptr, true);
        if (Spell.LeechFraction > 0.0f) S->HealActor(C, Dealt * Spell.LeechFraction, C);
    }
    Payload(Stop, -Direction, nullptr, nullptr, Scale * 0.35f, Spell.ChainCount > 0 && Struck.Num() > 0, false, false);
    if (Spell.SplitCount > 0 && ShardClock <= 0.0f && Struck.Num() > 0)
    {
        ShardClock = 0.6f;
        SpawnShards(Stop, -Direction, Spell.SplitCount, false);
    }
}

void AReflectionsCraftedSpell::BecomeMine(const FVector& Location)
{
    Mode = ECraftedSpellMode::Mine;
    Velocity = FVector::ZeroVector;
    SetActorLocation(Location);
    Age = 0.0f;
    Life = FMath::Max(8.0f, Spell.Lifetime);
    SetFxFloat(TEXT("User.Intensity"), 0.55f);
    SetFxFloat(TEXT("User.Pulse"), 1.5f);
}

void AReflectionsCraftedSpell::TickMine(float DeltaSeconds)
{
    UReflectionsCraftedSpellSubsystem* S = Services();
    if (!S || Age >= Life)
    {
        if (S) Payload(GetActorLocation(), FVector::UpVector, nullptr, nullptr, Scale * 0.5f, false, false, false);
        Expire();
        return;
    }
    TArray<AActor*> Near;
    S->FindEnemies(GetActorLocation(), FMath::Max(Spell.ProximityRadius, 200.0f), Caster.Get(), Near, true);
    Near.RemoveAll([](AActor* A) { return !A->IsA<APawn>(); });
    if (Near.Num() > 0)
    {
        Mode = ECraftedSpellMode::Projectile;  // So Fire() does not re-arm.
        Fire(GetActorLocation(), FVector::UpVector, nullptr, nullptr);
    }
}

void AReflectionsCraftedSpell::BecomeFuse(const FVector& Location, AActor* AttachTo)
{
    Mode = ECraftedSpellMode::Fuse;
    bFused = true;
    FuseClock = Spell.FuseTime;
    Velocity = FVector::ZeroVector;
    FuseAttach = AttachTo;
    FuseOffset = AttachTo ? Location - AttachTo->GetActorLocation() : FVector::ZeroVector;
    SetActorLocation(Location);
    SetFxFloat(TEXT("User.Pulse"), 6.0f);
}

void AReflectionsCraftedSpell::TickFuse(float DeltaSeconds)
{
    if (AActor* Attached = FuseAttach.Get()) SetActorLocation(Attached->GetActorLocation() + FuseOffset);
    FuseClock -= DeltaSeconds;
    const float Alpha = 1.0f - FMath::Clamp(FuseClock / FMath::Max(Spell.FuseTime, 0.01f), 0.0f, 1.0f);
    SetFxFloat(TEXT("User.Intensity"), 1.0f + Alpha * 1.5f);
    SetFxFloat(TEXT("User.Pulse"), 4.0f + Alpha * 14.0f);
    if (FuseClock <= 0.0f)
    {
        Payload(GetActorLocation(), FVector::UpVector, FuseAttach.Get(), nullptr, Scale * Spell.FuseScale, true, true, true);
        Expire();
    }
}

// ------------------------------------------------------------------------------------------------ pull
void AReflectionsCraftedSpell::TickPull(float DeltaSeconds)
{
    UReflectionsCraftedSpellSubsystem* S = Services();
    if (!S) return;
    const FVector Center = Mode == ECraftedSpellMode::Field || Mode == ECraftedSpellMode::Hazard ? Anchor : GetActorLocation();
    const bool bImploding = Mode == ECraftedSpellMode::Fuse && Spell.Has(ESyn::Implosion);
    const float Radius = Spell.PullRadius * (bImploding ? 1.25f : 1.0f);
    const float Strength = Spell.PullStrength * (bImploding ? 1.5f : 1.0f);
    TArray<AActor*> Caught;
    S->FindEnemies(Center, Radius, Caster.Get(), Caught);
    for (AActor* Enemy : Caught) S->Pull(Enemy, Center, Strength, Radius, Spell.Has(ESyn::Updraft), DeltaSeconds, &Spell, Caster.Get());

    if (!Spell.Has(ESyn::StormEye)) return;
    // Eye of the storm: lightning leaps between everything caught in the pull.
    StormClock -= DeltaSeconds;
    if (StormClock > 0.0f) return;
    StormClock = 0.35f;
    Caught.RemoveAll([](AActor* A) { return !A->IsA<APawn>(); });
    Caught.Sort([&Center](const AActor& A, const AActor& B) { return FVector::DistSquared(A.GetActorLocation(), Center) < FVector::DistSquared(B.GetActorLocation(), Center); });
    FVector From = Center;
    for (int32 i = 0; i < FMath::Min(Caught.Num(), Spell.ChainCount + 1); ++i)
    {
        const FVector To = Caught[i]->GetActorLocation();
        S->SpawnArc(Spell.Look, From, To, 0.2f);
        S->ApplyHit(Spell, Caught[i], Caster.Get(), Scale * 0.18f, From, nullptr, true);
        From = To;
    }
}

// ------------------------------------------------------------------------------------------------ fields
void AReflectionsCraftedSpell::FieldBurst(const FVector& Center, float BurstScale)
{
    Payload(Center, FVector::UpVector, nullptr, nullptr, BurstScale, true, false, false);
    if (ShardClock > 0.0f) return;
    bool bUsed = false;
    if (Spell.SplitCount > 0)
    {
        SpawnShards(Center + FVector(0, 0, 60.0f), FVector::UpVector, Spell.SplitCount, true);
        bUsed = true;
    }
    if (Spell.PierceCount > 0)
    {
        FireLance(Center);
        bUsed = true;
    }
    if (bUsed) ShardClock = 0.5f;
}

void AReflectionsCraftedSpell::RainDrop()
{
    UReflectionsCraftedSpellSubsystem* S = Services();
    if (!S) return;
    FVector Point;
    if (Spell.Recipe.Trigger == ETrig::Proximity)
    {
        TArray<AActor*> Under;
        S->FindEnemies(Anchor, Spell.Radius, Caster.Get(), Under);
        Under.RemoveAll([](AActor* A) { return !A->IsA<APawn>(); });
        if (Under.Num() == 0) return;
        Point = Under[FMath::RandRange(0, Under.Num() - 1)]->GetActorLocation();
    }
    else
    {
        const FVector2D Disc = FMath::RandPointInCircle(Spell.Radius);
        Point = Anchor + FVector(Disc.X, Disc.Y, 0.0f);
    }
    Point = GroundBelow(Point, 400.0f);
    // Each drop is a tiny payload of its own; behaviours ride on every few drops.
    FCraftedSpellResolved Drop = Spell;
    const float DropRadius = 85.0f + 10.0f * Spell.Recipe.Power;
    Drop.Radius = DropRadius;
    Drop.Look.Size *= 0.25f;
    TArray<AActor*> Enemies;
    S->FindEnemies(Point, DropRadius, Caster.Get(), Enemies);
    for (AActor* Enemy : Enemies) S->ApplyHit(Drop, Enemy, Caster.Get(), Scale, Point + FVector(0, 0, 300.0f), nullptr, true);
    if (Drop.Heal > 0.0f)
    {
        // Healing rain: a drop that lands near a friend mends them.
        TArray<AActor*> Allies;
        S->FindAllies(Point + FVector(0, 0, 80.0f), DropRadius * 1.5f, Caster.Get(), Allies);
        for (AActor* Ally : Allies) S->HealActor(Ally, Drop.Heal * Scale, Caster.Get());
    }
    if (UNiagaraComponent* Splash = S->SpawnFx(ECraftedFx::Burst, Drop.Look, Point, FRotator(90, 0, 0), nullptr, 0.22f))
    {
        Splash->SetVariableVec3(TEXT("User.Normal"), FVector::UpVector);
        Splash->SetVariableFloat(TEXT("User.Radius"), DropRadius);
    }
    if (Spell.ChainCount > 0 && Enemies.Num() > 0 && ShardClock <= 0.0f)
    {
        StartChain(Enemies[0], Point, Spell.ChainCount, Scale * 0.6f, Enemies);
    }
    if ((Spell.SplitCount > 0 || Spell.PierceCount > 0) && ShardClock <= 0.0f)
    {
        ShardClock = 0.6f;
        if (Spell.SplitCount > 0) SpawnShards(Point, FVector::UpVector, Spell.SplitCount, true);
        if (Spell.PierceCount > 0) FireLance(Point);
    }
}

void AReflectionsCraftedSpell::TickWave(float DeltaSeconds)
{
    UReflectionsCraftedSpellSubsystem* S = Services();
    if (!S) return;
    const float Previous = WaveFront;
    WaveFront = FMath::Min(WaveFront + Spell.Speed * DeltaSeconds, Spell.Range);
    const float HalfCone = FMath::DegreesToRadians(Spell.ConeDegrees * 0.5f + (Spell.SplitCount > 0 ? 25.0f : 0.0f));
    const float ConeCos = FMath::Cos(HalfCone);
    TArray<AActor*> Candidates;
    S->FindEnemies(Anchor, WaveFront + 60.0f, Caster.Get(), Candidates);
    for (AActor* Enemy : Candidates)
    {
        if (WaveHit.Contains(Enemy)) continue;
        const FVector To = Enemy->GetActorLocation() - Anchor;
        if (FVector::DotProduct(To.GetSafeNormal2D(), WaveDirection) < ConeCos) continue;
        WaveHit.Add(Enemy);
        const float Dealt = S->ApplyHit(Spell, Enemy, Caster.Get(), Scale, Anchor);
        if (Spell.LeechFraction > 0.0f) S->HealActor(Caster.Get(), Dealt * Spell.LeechFraction, Caster.Get());
        if (Spell.ChainCount > 0) StartChain(Enemy, Enemy->GetActorLocation(), Spell.ChainCount, Scale * 0.6f, {Enemy});
    }
    if (Spell.Heal > 0.0f)
    {
        TArray<AActor*> Allies;
        S->FindAllies(Anchor, WaveFront, Caster.Get(), Allies);
        for (AActor* Ally : Allies)
        {
            if (Ally != Caster.Get() && !WaveHit.Contains(Ally)) { WaveHit.Add(Ally); S->HealActor(Ally, Spell.Heal * Scale, Caster.Get()); }
        }
    }
    // A rolling wall of bursts along the front.
    HopClock -= DeltaSeconds;
    if (HopClock <= 0.0f && WaveFront > Previous)
    {
        HopClock = 0.07f;
        const int32 Points = Spell.SplitCount > 0 ? 5 : 3;
        for (int32 i = 0; i < Points; ++i)
        {
            const float Alpha = Points > 1 ? float(i) / (Points - 1) - 0.5f : 0.0f;
            const FVector Direction = WaveDirection.RotateAngleAxis(FMath::RadiansToDegrees(HalfCone) * 1.6f * Alpha, FVector::UpVector);
            const FVector Point = GroundBelow(Anchor + Direction * WaveFront, 150.0f) + FVector(0, 0, 30.0f);
            if (UNiagaraComponent* Burst = S->SpawnFx(ECraftedFx::Burst, Spell.Look, Point, Direction.Rotation(), nullptr, 0.4f * FMath::Sqrt(Scale)))
            {
                Burst->SetVariableVec3(TEXT("User.Normal"), (Direction + FVector(0, 0, 0.6f)).GetSafeNormal());
                Burst->SetVariableFloat(TEXT("User.Radius"), 90.0f);
            }
        }
    }
}

void AReflectionsCraftedSpell::TickField(float DeltaSeconds)
{
    UReflectionsCraftedSpellSubsystem* S = Services();
    AActor* C = Caster.Get();
    if (!S)
    {
        Expire();
        return;
    }
    const EForm Form = Spell.Recipe.Form;
    const ETrig Trigger = Spell.Recipe.Trigger;
    const bool bEscort = Form == EForm::Aura || Spell.Has(ESyn::Escort);

    // Where the field is: on the caster, drifting toward enemies, or hopping between them.
    if (bEscort && C)
    {
        Anchor = Form == EForm::Rain || Form == EForm::Rune ? GroundBelow(CasterFeet() + FVector(0, 0, 60.0f), 100.0f) : CasterFeet();
        if (Form == EForm::Wave && WaveFront <= 0.0f) WaveDirection = C->GetActorForwardVector().GetSafeNormal2D();
    }
    else if (Spell.HomingStrength > 0.0f && Form != EForm::Wave)
    {
        if (AActor* Target = S->NearestEnemy(Anchor, 1600.0f, C))
        {
            const FVector To = (Target->GetActorLocation() - Anchor).GetSafeNormal2D();
            Anchor = GroundBelow(Anchor + To * 260.0f * DeltaSeconds, 120.0f);
        }
    }
    else if (Spell.BounceCount > 0 && (Form == EForm::Rain || Form == EForm::Aura) && HopsLeft > 0)
    {
        HopClock -= DeltaSeconds;
        if (HopClock <= 0.0f && FieldClock > 0.0f)
        {
            HopClock = 1.0f;
            if (AActor* Target = S->NearestEnemy(Anchor, 1400.0f, C))
            {
                Anchor = GroundBelow(FMath::Lerp(Anchor, Target->GetActorLocation(), 0.7f), 200.0f);
                --HopsLeft;
            }
        }
    }
    if (Form != EForm::Wave) SetActorLocation(Anchor);

    FieldClock += DeltaSeconds;
    if (FieldClock < 0.0f)
    {
        // Telegraph a delayed field: dim, quickening pulse.
        SetFxFloat(TEXT("User.Intensity"), 0.35f + 0.65f * (1.0f + FieldClock / FMath::Max(Spell.StartDelay + Spell.FuseTime, 0.01f)));
        SetFxFloat(TEXT("User.Pulse"), 3.0f + 10.0f * (1.0f + FieldClock / FMath::Max(Spell.StartDelay + Spell.FuseTime, 0.01f)));
        return;
    }
    SetFxFloat(TEXT("User.Intensity"), 1.0f);
    const float DelayBonus = Spell.FuseTime > 0.0f ? Spell.FuseScale : 1.0f;
    const float Remaining = Life - FieldClock;

    // Sanctuary: Life fields heal everyone friendly standing in them.
    if (Spell.Heal > 0.0f)
    {
        SanctuaryClock -= DeltaSeconds;
        if (SanctuaryClock <= 0.0f)
        {
            SanctuaryClock = 0.5f;
            TArray<AActor*> Allies;
            S->FindAllies(Anchor + FVector(0, 0, 80.0f), Spell.Radius + 60.0f, C, Allies);
            for (AActor* Ally : Allies) S->HealActor(Ally, Spell.Heal * 0.2f * Scale, C);
        }
    }

    switch (Form)
    {
    case EForm::Nova:
    case EForm::Rune:
    {
        bool bGo = false;
        if (Trigger == ETrig::Pulse)
        {
            PulseClock -= DeltaSeconds;
            if (PulseClock <= 0.0f) { PulseClock = Spell.PulseInterval; bGo = true; }
        }
        else if (!bBurstDone)
        {
            const bool bWaits = Trigger == ETrig::Proximity || (Form == EForm::Rune && Trigger == ETrig::Impact);
            if (bWaits)
            {
                TArray<AActor*> Near;
                S->FindEnemies(Anchor + FVector(0, 0, 60.0f), FMath::Max(Spell.ProximityRadius, Spell.Radius * 0.6f), C, Near, true);
                Near.RemoveAll([](AActor* A) { return !A->IsA<APawn>(); });
                bGo = Near.Num() > 0;
            }
            else
            {
                bGo = true;
            }
        }
        else if (HopsLeft > 0)
        {
            // Bounce: the burst hops to the nearest enemy that it did not just hit.
            HopClock -= DeltaSeconds;
            if (HopClock <= 0.0f)
            {
                AActor* Target = S->NearestEnemy(Anchor, 1300.0f, C, &WaveHit);
                if (!Target) { Expire(); return; }
                Anchor = GroundBelow(Target->GetActorLocation(), 150.0f);
                SetActorLocation(Anchor);
                --HopsLeft;
                bGo = true;
            }
        }
        else if (Trigger != ETrig::Pulse)
        {
            if (FieldClock > 0.4f || Remaining <= 0.0f) { if (Spell.HazardDuration > 0.0f) SpawnHazard(Anchor); Expire(); }
            return;
        }
        if (bGo)
        {
            FieldBurst(Anchor + FVector(0, 0, 40.0f), Scale * (bBurstDone ? 0.8f : DelayBonus));
            TArray<AActor*> Struck;
            S->FindEnemies(Anchor, Spell.Radius, C, Struck);
            for (AActor* A : Struck) WaveHit.Add(A);
            if (!bBurstDone) { bBurstDone = true; FieldClock = 0.0f; }
            HopClock = 0.45f;
        }
        if (Trigger == ETrig::Pulse && Remaining <= 0.0f)
        {
            if (Spell.HazardDuration > 0.0f) SpawnHazard(Anchor);
            Expire();
        }
        if (Remaining <= 0.0f && !bBurstDone) Expire();
        return;
    }
    case EForm::Wave:
    {
        if (WaveFront <= 0.0f && C)
        {
            Anchor = CasterFeet() + FVector(0, 0, 40.0f);
            if (Spell.Has(ESyn::Escort)) WaveDirection = C->GetActorForwardVector().GetSafeNormal2D();
        }
        TickWave(DeltaSeconds);
        if (Trigger == ETrig::Pulse && WaveFront >= Spell.Range && Remaining > 0.0f)
        {
            PulseClock -= DeltaSeconds;
            if (PulseClock <= 0.0f) { PulseClock = Spell.PulseInterval; WaveFront = 0.0f; WaveHit.Reset(); }
        }
        if (WaveFront >= Spell.Range && (Trigger != ETrig::Pulse || Remaining <= 0.0f))
        {
            if (Spell.HazardDuration > 0.0f) SpawnHazard(GroundBelow(Anchor + WaveDirection * Spell.Range * 0.5f));
            if (Spell.SplitCount > 0) SpawnShards(Anchor + WaveDirection * Spell.Range, -WaveDirection, Spell.SplitCount, false);
            Expire();
        }
        return;
    }
    case EForm::Rain:
    {
        PulseClock -= DeltaSeconds;
        while (PulseClock <= 0.0f)
        {
            PulseClock += FMath::Max(Spell.PulseInterval, 0.05f);
            RainDrop();
        }
        break;
    }
    case EForm::Aura:
    {
        PulseClock -= DeltaSeconds;
        if (PulseClock <= 0.0f)
        {
            PulseClock = FMath::Max(Spell.PulseInterval, 0.1f);
            bool bGo = true;
            if (Trigger == ETrig::Proximity)
            {
                TArray<AActor*> Near;
                S->FindEnemies(Anchor, Spell.Radius, C, Near, true);
                bGo = Near.Num() > 0;
            }
            if (bGo) FieldBurst(Anchor + FVector(0, 0, 60.0f), Scale * DelayBonus);
        }
        if (Spell.HazardDuration > 0.0f)
        {
            // An aura with Hazard lays a trail behind you.
            HazardClock -= DeltaSeconds;
            if (HazardClock <= 0.0f)
            {
                HazardClock = 0.8f;
                FCraftedSpellResolved Trail = MakeHazard(Spell);
                Trail.Radius = FMath::Min(Trail.Radius, 160.0f);
                Trail.Look.Size = Trail.Radius;
                Trail.Lifetime = 3.0f;
                SpawnSpell(GetWorld(), Trail, C, ECraftedSpellMode::Hazard, Anchor, Anchor, nullptr, Scale, Generation + 1);
            }
        }
        break;
    }
    default:
        break;
    }
    if (Remaining <= 0.0f)
    {
        if (Spell.HazardDuration > 0.0f && Form != EForm::Aura) SpawnHazard(Anchor);
        Expire();
    }
}

void AReflectionsCraftedSpell::TickHazard(float DeltaSeconds)
{
    UReflectionsCraftedSpellSubsystem* S = Services();
    if (!S || Age >= Life)
    {
        Expire();
        return;
    }
    if (Spell.Has(ESyn::Wildfire))
    {
        // Wildfire: the pool spreads as it burns.
        HazardRadius = FMath::Lerp(Spell.Radius, Spell.Radius * 1.7f, FMath::Clamp(Age / Life, 0.0f, 1.0f));
        SetFxFloat(TEXT("User.Radius"), HazardRadius);
    }
    SetFxFloat(TEXT("User.Intensity"), FMath::Clamp((Life - Age) / 0.8f, 0.0f, 1.0f));
    PulseClock -= DeltaSeconds;
    if (PulseClock > 0.0f) return;
    PulseClock = 0.5f;
    AActor* C = Caster.Get();
    TArray<AActor*> Inside;
    S->FindEnemies(Anchor + FVector(0, 0, 50.0f), HazardRadius, C, Inside);
    float Dealt = 0.0f;
    for (AActor* Enemy : Inside) Dealt += S->ApplyHit(Spell, Enemy, C, Scale, Anchor, nullptr, true);
    if (Spell.LeechFraction > 0.0f && Dealt > 0.0f) S->HealActor(C, Dealt * Spell.LeechFraction * (Spell.Has(ESyn::Bloodbath) ? 1.5f : 1.0f), C);
    if (Spell.Heal > 0.0f)
    {
        TArray<AActor*> Allies;
        S->FindAllies(Anchor + FVector(0, 0, 80.0f), HazardRadius + 40.0f, C, Allies);
        for (AActor* Ally : Allies) S->HealActor(Ally, Spell.Heal * Scale, C);
    }
}

void AReflectionsCraftedSpell::Expire()
{
    if (Mode == ECraftedSpellMode::Spent) return;
    Mode = ECraftedSpellMode::Spent;
    Velocity = FVector::ZeroVector;
    if (Fx)
    {
        Fx->SetVariableFloat(TEXT("User.Intensity"), 0.0f);
        Fx->Deactivate();
    }
    if (Loop) Loop->FadeOut(0.3f, 0.0f);
    // Linger so pending chain jumps and trailing particles can finish.
    SetLifeSpan(Chains.Num() > 0 ? 1.5f : 0.8f);
}
