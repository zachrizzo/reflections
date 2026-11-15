#include "Hero/ReflectionsSpellCombat.h"
#include "Hero/ReflectionsSpellCatalog.h"
#include "Hero/ReflectionsSpellEventSubsystem.h"

#include "Components/CapsuleComponent.h"
#include "Components/SphereComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/OverlapResult.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"
#include "GameFramework/DamageType.h"
#include "GameFramework/ProjectileMovementComponent.h"
#include "GameFramework/Character.h"
#include "Interfaces/CombatDamageable.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "NPC/ReflectionsNpcSubsystem.h"
#include "SpellVFX/ReflectionsSpellVfxSubsystem.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "PhysicalMaterials/PhysicalMaterial.h"
#include "UObject/ConstructorHelpers.h"
#include "TimerManager.h"
#include "Sound/SoundBase.h"

static TAutoConsoleVariable<int32> CVarSpellLogHits(TEXT("Spell.LogHits"), 0,
    TEXT("1: log every spell projectile hit and every target a spell skips (actor, component, damage). Debug only."));

namespace
{
    /** The reaction a hit asks of the body (FReflectionsSpellHitData::Reaction and friends). */
    struct FSpellReaction
    {
        EReflectionsSpellReaction Type = EReflectionsSpellReaction::Hit;
        float Magnitude = 0.0f;
        float Duration = 0.0f;
    };

    /** Element-driven default: fire burns (or blasts), lightning electrifies, water pushes, earth knocks down. */
    FSpellReaction ReactionFor(EHeroSpell Spell, float Damage, float Push)
    {
        FSpellReaction R;
        R.Magnitude = FMath::Clamp(Push / 1400.0f + Damage / 50.0f, 0.1f, 1.0f);
        if (!ReflectionsSpellCatalog::IsValid(Spell)) return R;
        const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(Spell);
        switch (Spec.Element)
        {
        case EReflectionsSpellElement::Fire:
            if (Spec.Radius > 0.0f) R.Type = EReflectionsSpellReaction::Explosion;
            else { R.Type = EReflectionsSpellReaction::Burn; R.Duration = 2.5f; }
            break;
        case EReflectionsSpellElement::Lightning:
            R.Type = EReflectionsSpellReaction::Electrify;
            R.Duration = Spec.Radius > 0.0f ? 1.0f : 1.5f;
            R.Magnitude = FMath::Max(R.Magnitude, 0.6f);
            break;
        case EReflectionsSpellElement::Water: R.Type = EReflectionsSpellReaction::Push; break;
        case EReflectionsSpellElement::Ice: R.Type = EReflectionsSpellReaction::Freeze; R.Duration = 2.5f; break;
        case EReflectionsSpellElement::Earth: R.Type = EReflectionsSpellReaction::Knockdown; break;
        case EReflectionsSpellElement::Air: R.Type = EReflectionsSpellReaction::Lift; break;
        case EReflectionsSpellElement::Arcane:
            if (Spell == EHeroSpell::ForcePush) R.Type = EReflectionsSpellReaction::Push;
            break;
        default: break;
        }
        return R;
    }

    void AffectTarget(AActor* Target, AActor* Caster, EHeroSpell Spell, float Damage, float Push, const FVector& Origin,
        const FHitResult* DirectHit = nullptr, const FSpellReaction* Reaction = nullptr)
    {
        if (!Target || Target == Caster) return;
        // NPC casters (enemy soldiers) spare their own side; the player's spells can still hit anyone.
        const UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(Target);
        // A hit on an NPC's hidden walker or hit proxy is a hit on the NPC; the NPC system moves NPC bodies itself.
        bool bNpc = false;
        if (Npcs)
        {
            if (const UReflectionsNpcReactionComponent* Npc = Npcs->FindNpc(Target))
            {
                Target = Npc->GetOwner();
                bNpc = true;
                if (!Target || Target == Caster) return;
            }
        }
        if (Npcs && !Npcs->CanBeHarmedBy(Target, Caster))
        {
            UE_CLOG(CVarSpellLogHits.GetValueOnGameThread() != 0, LogTemp, Display, TEXT("Spell: %s spared %s (ally of the caster)"),
                *GetNameSafe(Caster), *GetNameSafe(Target));
            return;
        }
        const FSpellReaction React = Reaction ? *Reaction : ReactionFor(Spell, Damage, Push);
        const bool bBlast = React.Type == EReflectionsSpellReaction::Explosion;
        const FVector Direction = (Target->GetActorLocation() - Origin).GetSafeNormal();
        UPrimitiveComponent* Primitive = DirectHit ? DirectHit->GetComponent() : Cast<UPrimitiveComponent>(Target->GetRootComponent());
        const FVector Point = DirectHit ? FVector(DirectHit->ImpactPoint) : Target->GetActorLocation();
        const FHitResult Hit = DirectHit ? *DirectHit : FHitResult(Target, Primitive, Point, -Direction);
        if (Damage > 0.0f)
        {
            if (ICombatDamageable* Damageable = Cast<ICombatDamageable>(Target))
                Damageable->ApplyDamage(Damage, Caster, Point, Direction * Push);
            else
            {
                const APawn* Pawn = Cast<APawn>(Caster);
                UGameplayStatics::ApplyPointDamage(Target, Damage, Direction, Hit, Pawn ? Pawn->GetController() : nullptr, Caster, UDamageType::StaticClass());
            }
        }
        // The player is shoved, not thrown: enemy bolts would otherwise knock them around on every hit.
        if (const APawn* TargetPawn = Cast<APawn>(Target); TargetPawn && TargetPawn->IsPlayerControlled()) Push *= 0.3f;
        // Blasts throw bodies up as well as away.
        const FVector Velocity = Direction * Push + FVector(0.0f, 0.0f, Push * (bBlast ? 0.4f : 0.15f));
        if (Push > 0.0f)
        {
            if (ACharacter* Character = Cast<ACharacter>(Target); Character && !bNpc) Character->LaunchCharacter(Velocity, true, true);
            else if (Primitive && Primitive->IsSimulatingPhysics(Hit.BoneName) && !(Npcs && Npcs->FindNpc(Target)))
            {
                // Loose props: a velocity kick, so a crate flies as far as a bottle. NPC bodies react on their own side.
                Primitive->AddImpulseAtLocation(Velocity * Primitive->GetMass(), Point, Hit.BoneName);
            }
        }
        if (UWorld* World = Target->GetWorld())
            if (UReflectionsSpellEventSubsystem* Events = World->GetSubsystem<UReflectionsSpellEventSubsystem>())
            {
                FReflectionsSpellHitData Data;
                Data.Spell = Spell; Data.Caster = Caster; Data.Target = Target; Data.Location = Point;
                Data.Impulse = Velocity; Data.ImpactNormal = Hit.ImpactNormal; Data.Bone = Hit.BoneName;
                Data.Surface = UPhysicalMaterial::DetermineSurfaceType(Hit.PhysMaterial.Get());
                Data.Reaction = React.Type; Data.Magnitude = React.Magnitude; Data.Duration = React.Duration;
                Data.Origin = bBlast || React.Type == EReflectionsSpellReaction::Pull ? Origin : Point;
                Events->OnSpellHit.Broadcast(Data);
            }
    }

    TSet<AActor*> OverlapTargets(UWorld* World, const FVector& Location, float Radius, AActor* Caster)
    {
        TSet<AActor*> Targets;
        if (!World || Radius <= 0) return Targets;
        TArray<FOverlapResult> Hits;
        FCollisionObjectQueryParams Types;
        Types.AddObjectTypesToQuery(ECC_Pawn); Types.AddObjectTypesToQuery(ECC_WorldDynamic); Types.AddObjectTypesToQuery(ECC_PhysicsBody);
        FCollisionQueryParams Query(SCENE_QUERY_STAT(SpellArea), false, Caster);
        World->OverlapMultiByObjectType(Hits, Location, FQuat::Identity, Types, FCollisionShape::MakeSphere(Radius), Query);
        const UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(World);
        for (const FOverlapResult& Hit : Hits)
        {
            AActor* Actor = Hit.GetActor();
            // An NPC and its hidden walker or hit proxy count once, as the NPC.
            if (Npcs && Actor)
            {
                if (const UReflectionsNpcReactionComponent* Npc = Npcs->FindNpc(Actor)) Actor = Npc->GetOwner();
            }
            if (Actor && Actor != Caster) Targets.Add(Actor);
        }
        return Targets;
    }

    /** A real explosion: damage and knock-back fall off from the centre (1 to 0.35), loose physics objects are thrown
     *  radially, and every body gets an Explosion reaction with Origin = Center. DirectActor (what the projectile
     *  struck) always takes the full blast. */
    void ExplodeSpellAt(UWorld* World, AActor* Caster, EHeroSpell Spell, const FVector& Center, float Radius, float Damage, float Speed,
        const TArray<AActor*>& Ignore, AActor* DirectActor = nullptr, const FHitResult* DirectHit = nullptr)
    {
        if (!World || Radius <= 0.0f) return;
        TArray<FOverlapResult> Hits;
        FCollisionObjectQueryParams Types;
        Types.AddObjectTypesToQuery(ECC_Pawn); Types.AddObjectTypesToQuery(ECC_WorldDynamic); Types.AddObjectTypesToQuery(ECC_PhysicsBody);
        FCollisionQueryParams Query(SCENE_QUERY_STAT(SpellExplosion), false, Caster);
        World->OverlapMultiByObjectType(Hits, Center, FQuat::Identity, Types, FCollisionShape::MakeSphere(Radius), Query);
        const UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(World);
        if (Npcs && DirectActor)
        {
            if (const UReflectionsNpcReactionComponent* Npc = Npcs->FindNpc(DirectActor)) DirectActor = Npc->GetOwner();
        }
        TSet<AActor*> Done;
        TSet<UPrimitiveComponent*> Thrown;
        auto Blast = [&](AActor* Target, const FHitResult* Direct)
        {
            const float Alpha = Direct ? 0.0f : FMath::Clamp(FVector::Dist(Target->GetActorLocation(), Center) / Radius, 0.0f, 1.0f);
            FSpellReaction React;
            React.Type = EReflectionsSpellReaction::Explosion;
            React.Magnitude = FMath::Lerp(1.0f, 0.35f, Alpha);
            AffectTarget(Target, Caster, Spell, Damage * React.Magnitude, Speed * React.Magnitude, Center, Direct, &React);
        };
        for (const FOverlapResult& Hit : Hits)
        {
            AActor* Target = Hit.GetActor();
            if (!Target || Target == Caster || Ignore.Contains(Target)) continue;
            UPrimitiveComponent* Part = Hit.GetComponent();
            if (Part && Part->IsSimulatingPhysics() && !Thrown.Contains(Part) && !(Npcs && Npcs->FindNpc(Target)))
            {
                Thrown.Add(Part);
                Part->AddRadialImpulse(Center, Radius, Speed, ERadialImpulseFalloff::RIF_Linear, true);
            }
            if (Npcs)
            {
                if (const UReflectionsNpcReactionComponent* Npc = Npcs->FindNpc(Target)) Target = Npc->GetOwner();
            }
            if (!Target || Target == Caster || Ignore.Contains(Target) || Done.Contains(Target) || Target == DirectActor) continue;
            Done.Add(Target);
            Blast(Target, nullptr);
        }
        if (DirectActor && DirectActor != Caster && !Ignore.Contains(DirectActor)) Blast(DirectActor, DirectHit);
    }
}

void ReflectionsSpellCombat::ApplyArea(UWorld* World, AActor* Caster, EHeroSpell Spell, const FVector& Center, float Radius,
    float Damage, float Push, const TArray<AActor*>& Ignore)
{
    ExplodeSpellAt(World, Caster, Spell, Center, Radius, Damage, Push, Ignore);
}

UReflectionsHealthComponent::UReflectionsHealthComponent()
{
    PrimaryComponentTick.bCanEverTick = false;
}

void UReflectionsHealthComponent::BeginPlay()
{
    Super::BeginPlay();
    Health = FMath::Max(1.0f, MaxHealth);
    GetOwner()->OnTakeAnyDamage.AddDynamic(this, &UReflectionsHealthComponent::ReceiveDamage);
}

void UReflectionsHealthComponent::ReceiveDamage(AActor* DamagedActor, float Damage,
    const UDamageType* DamageType, AController* Instigator, AActor* DamageCauser)
{
    if (Damage <= 0.0f || Health <= 0.0f)
    {
        return;
    }
    const float Absorbed = FMath::Min(Shield, Damage);
    Shield -= Absorbed;
    if (Absorbed > 0.0f)
    {
        // Jam SoundCue owned by the audio session; referenced only.
        if (USoundBase* Block = LoadObject<USoundBase>(nullptr, TEXT("/Game/Audio/Jam/Cues/SCue_Shield_Block.SCue_Shield_Block")))
        {
            UGameplayStatics::PlaySoundAtLocation(this, Block, GetOwner()->GetActorLocation());
        }
    }
    Health = FMath::Max(0.0f, Health - (Damage - Absorbed));
    OnHealthChanged.Broadcast(Health, MaxHealth, DamageCauser);
    if (Health <= 0.0f)
    {
        OnDeath.Broadcast(DamageCauser);
    }
}

void UReflectionsHealthComponent::GrantShield(float Amount)
{
    if (Health > 0.0f && Amount > 0.0f)
    {
        Shield = FMath::Min(MaxHealth, Shield + Amount);
        if (UWorld* World = GetWorld()) World->GetTimerManager().SetTimer(ShieldTimer, this, &UReflectionsHealthComponent::ExpireShield, 8.0f, false);
        OnHealthChanged.Broadcast(Health, MaxHealth, nullptr);
    }
}
void UReflectionsHealthComponent::ExpireShield()
{
    Shield = 0.0f;
    OnHealthChanged.Broadcast(Health, MaxHealth, nullptr);
}

void UReflectionsHealthComponent::ResetHealth()
{
    if (UWorld* World = GetWorld()) World->GetTimerManager().ClearTimer(ShieldTimer);
    Shield = 0.0f;
    Health = FMath::Max(1.0f, MaxHealth);
    OnHealthChanged.Broadcast(Health, MaxHealth, nullptr);
}

float UReflectionsHealthComponent::Heal(float Amount, AActor* Healer)
{
    if (Amount <= 0.0f || Health <= 0.0f)
    {
        return 0.0f;
    }
    const float Previous = Health;
    Health = FMath::Min(MaxHealth, Health + Amount);
    if (Health > Previous)
    {
        OnHealthChanged.Broadcast(Health, MaxHealth, Healer);
    }
    return Health - Previous;
}

AReflectionsSpellProjectile::AReflectionsSpellProjectile()
{
    PrimaryActorTick.bCanEverTick = false;
    Collision = CreateDefaultSubobject<USphereComponent>(TEXT("Collision"));
    SetRootComponent(Collision);
    Collision->InitSphereRadius(14.0f);
    Collision->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    Collision->SetCollisionObjectType(ECC_WorldDynamic);
    Collision->SetCollisionResponseToAllChannels(ECR_Ignore);
    Collision->SetCollisionResponseToChannel(ECC_WorldStatic, ECR_Block);
    Collision->SetCollisionResponseToChannel(ECC_WorldDynamic, ECR_Block);
    Collision->SetCollisionResponseToChannel(ECC_Pawn, ECR_Block);
    Collision->bReturnMaterialOnMove = true;
    Collision->OnComponentHit.AddDynamic(this, &AReflectionsSpellProjectile::OnProjectileHit);
    Visual = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Visual"));
    Visual->SetupAttachment(Collision);
    Visual->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Visual->SetCastShadow(false);
    Movement = CreateDefaultSubobject<UProjectileMovementComponent>(TEXT("Movement"));
    Movement->UpdatedComponent = Collision;
    Movement->ProjectileGravityScale = 0.0f;
    // Initialize supplies a world-space velocity; do not rotate it a second time on activation.
    Movement->bInitialVelocityInLocalSpace = false;
    Movement->bRotationFollowsVelocity = true;
    Movement->bShouldBounce = false;
}

void AReflectionsSpellProjectile::Initialize(EHeroSpell InSpell, float InDamage, float InSpeed,
    float InRange, UStaticMesh* InMesh, UMaterialInterface* InMaterial)
{
    Spell = InSpell;
    Damage = FMath::Max(0.0f, InDamage);
    const float Speed = FMath::Max(1.0f, InSpeed);
    Movement->InitialSpeed = Speed;
    Movement->MaxSpeed = Speed;
    Movement->Velocity = GetActorForwardVector() * Speed;
    SetLifeSpan(FMath::Max(0.01f, InRange / Speed));
    if (InMesh)
    {
        Visual->SetStaticMesh(InMesh);
        Visual->SetMaterial(0, InMaterial);
    }
}

void AReflectionsSpellProjectile::InitializeCatalog(EHeroSpell InSpell, UStaticMesh* InMesh, UMaterialInterface* InMaterial, float DamageScale)
{
    const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(InSpell);
    BlastRadius = Spec.Radius;
    HitImpulse = Spec.Impulse;
    Initialize(InSpell, Spec.Power * FMath::Max(0.0f, DamageScale), Spec.Speed, Spec.Range, InMesh, InMaterial);
    // A Lightning Bolt that strikes a body arcs on to up to two more nearby.
    ChainsLeft = InSpell == EHeroSpell::LightningBolt ? 2 : 0;
}

void AReflectionsSpellProjectile::ChainLightning(AActor* From, const FVector& Point)
{
    UWorld* World = GetWorld();
    AActor* Caster = GetOwner();
    if (!World || ChainsLeft <= 0 || !IsValid(From)) return;
    const UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(World);
    auto Body = [Npcs](AActor* Actor) -> AActor*
    {
        if (!Npcs || !Actor) return Actor;
        const UReflectionsNpcReactionComponent* Npc = Npcs->FindNpc(Actor);
        return Npc ? Npc->GetOwner() : Actor;
    };
    AActor* Struck = Body(From);
    TArray<TPair<float, AActor*>> Next;
    for (AActor* Candidate : OverlapTargets(World, Point, 750.0f, Caster))
    {
        AActor* Target = Body(Candidate);
        if (!IsValid(Target) || Target == Struck || Target == Caster || Next.ContainsByPredicate([Target](const TPair<float, AActor*>& P) { return P.Value == Target; })) continue;
        const UReflectionsHealthComponent* Health = Target->FindComponentByClass<UReflectionsHealthComponent>();
        const bool bLiving = (Health && Health->Health > 0.0f) || (!Health && (Target->IsA<APawn>() || (Npcs && Npcs->FindNpc(Target))));
        if (!bLiving || (Npcs && !Npcs->CanBeHarmedBy(Target, Caster))) continue;
        Next.Add(TPair<float, AActor*>(FVector::DistSquared(Point, Target->GetActorLocation()), Target));
    }
    Next.Sort([](const TPair<float, AActor*>& A, const TPair<float, AActor*>& B) { return A.Key < B.Key; });
    for (int32 Index = 0; Index < FMath::Min(Next.Num(), 2); ++Index)
    {
        AActor* Target = Next[Index].Value;
        FVector Aim = Target->GetActorLocation();
        if (const UReflectionsNpcReactionComponent* Npc = Npcs ? Npcs->FindNpc(Target) : nullptr) Aim = Npc->GetAimPoint();
        const FVector Start = Point + (Aim - Point).GetSafeNormal() * 40.0f;
        const FTransform Launch((Aim - Start).Rotation(), Start);
        AReflectionsSpellProjectile* Arc = World->SpawnActorDeferred<AReflectionsSpellProjectile>(StaticClass(), Launch, Caster,
            GetInstigator(), ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
        if (!Arc) continue;
        // Faster and weaker than the bolt; the hop itself does not chain again.
        Arc->Initialize(Spell, Damage * 0.6f, 3600.0f, 900.0f, nullptr, nullptr);
        Arc->FinishSpawning(Launch);
        Arc->Collision->IgnoreActorWhenMoving(From, true);
        if (Struck != From) Arc->Collision->IgnoreActorWhenMoving(Struck, true);
        Arc->SetHomingTarget(Target, 8.0f);
    }
    ChainsLeft = 0;
}

void AReflectionsSpellProjectile::SetHomingTarget(AActor* Target, float Strength)
{
    if (!Target || !Target->GetRootComponent())
    {
        return;
    }
    Movement->bIsHomingProjectile = true;
    // Characters home on their root capsule. Actor-only NPCs (the crowd MetaHumans) have their root at the feet or
    // on a hidden driver; curve into their hit capsule so the bolt meets the visible body.
    USceneComponent* Aim = Target->GetRootComponent();
    if (!Target->IsA<ACharacter>())
    {
        if (UCapsuleComponent* Capsule = Target->FindComponentByClass<UCapsuleComponent>()) Aim = Capsule;
    }
    Movement->HomingTargetComponent = Aim;
    // Proportional to speed so fast bolts still bend a little, slow orbs a lot.
    Movement->HomingAccelerationMagnitude = Movement->InitialSpeed * FMath::Max(0.0f, Strength);
}

bool AReflectionsSpellProjectile::ResolvePointBlank(const FVector& From)
{
    UWorld* World = GetWorld();
    if (!World || bImpacted) return false;
    const FVector Muzzle = GetActorLocation();
    FCollisionQueryParams Query(SCENE_QUERY_STAT(SpellPointBlank), false, this);
    if (AActor* Caster = GetOwner())
    {
        Query.AddIgnoredActor(Caster);
        TArray<AActor*> Attached;
        Caster->GetAttachedActors(Attached, true, true);
        Query.AddIgnoredActors(Attached);
    }
    // Everything the projectile itself ignores (a caster's hidden pawn, squad mates) stays ignored.
    Query.AddIgnoredActors(Collision->GetMoveIgnoreActors());
    FHitResult Hit;
    if (!World->SweepSingleByChannel(Hit, From, Muzzle, FQuat::Identity, Collision->GetCollisionObjectType(),
        FCollisionShape::MakeSphere(Collision->GetScaledSphereRadius()), Query, FCollisionResponseParams(Collision->GetCollisionResponseToChannels())))
    {
        return false;
    }
    if (Hit.bStartPenetrating)
    {
        Hit.ImpactPoint = From;
        Hit.Location = From;
    }
    SetActorLocation(Hit.Location);
    OnProjectileHit(Collision, Hit.GetActor(), Hit.GetComponent(), FVector::ZeroVector, Hit);
    return true;
}

void AReflectionsSpellProjectile::HideFallbackVisual()
{
    Visual->SetVisibility(false);
}

void AReflectionsSpellProjectile::BeginPlay()
{
    Super::BeginPlay();
    if (AActor* Caster = GetOwner())
    {
        Collision->IgnoreActorWhenMoving(Caster, true);
        TArray<AActor*> Attached;
        Caster->GetAttachedActors(Attached, true, true);
        for (AActor* Child : Attached)
        {
            Collision->IgnoreActorWhenMoving(Child, true);
        }
    }
    // Spells pass through each other. Otherwise chain-lightning hops spawned at the same point struck each other at
    // once (seen in PIE, 14 Nov), and rapid bolts or crossing enemy bolts cancelled out.
    for (TActorIterator<AReflectionsSpellProjectile> It(GetWorld()); It; ++It)
    {
        if (*It == this || !It->Collision) continue;
        Collision->IgnoreActorWhenMoving(*It, true);
        It->Collision->IgnoreActorWhenMoving(this, true);
    }
}

void AReflectionsSpellProjectile::OnProjectileHit(UPrimitiveComponent* HitComponent, AActor* OtherActor,
    UPrimitiveComponent* OtherComponent, FVector NormalImpulse, const FHitResult& Hit)
{
    if (bImpacted || OtherActor == GetOwner())
    {
        return;
    }
    bImpacted = true;
    AActor* Caster = GetOwner();
    UE_CLOG(CVarSpellLogHits.GetValueOnGameThread() != 0, LogTemp, Display,
        TEXT("Spell hit: %s from %s struck %s (%s) at %s, damage %.1f, blast %.0f%s"), *GetNameSafe(this), *GetNameSafe(Caster),
        *GetNameSafe(OtherActor), *GetNameSafe(OtherComponent), *Hit.ImpactPoint.ToCompactString(), Damage, BlastRadius,
        Hit.bStartPenetrating ? TEXT(" (started inside)") : TEXT(""));
    const bool bExplosion = BlastRadius > 0.0f && Look == EReflectionsSpellLook::Catalog && ReflectionsSpellCatalog::IsValid(Spell)
        && ReflectionsSpellCatalog::Get(Spell).Element == EReflectionsSpellElement::Fire;
    if (bExplosion)
    {
        // Fireball: a real explosion (falloff damage, bodies knocked back, props thrown), wider than the catalog radius.
        ExplodeSpellAt(GetWorld(), Caster, Spell, Hit.ImpactPoint, FMath::Max(BlastRadius, 320.0f), Damage, 1100.0f, TArray<AActor*>(), OtherActor, &Hit);
    }
    else if (BlastRadius > 0.0f)
    {
        TSet<AActor*> Targets = OverlapTargets(GetWorld(), Hit.ImpactPoint, BlastRadius, Caster);
        if (OtherActor && OtherActor != Caster) Targets.Add(OtherActor);
        for (AActor* Target : Targets) AffectTarget(Target, Caster, Spell, Damage, HitImpulse, Hit.ImpactPoint, Target == OtherActor ? &Hit : nullptr);
    }
    else if (OtherActor) AffectTarget(OtherActor, Caster, Spell, Damage, HitImpulse, Hit.ImpactPoint - GetActorForwardVector() * 10.0f, &Hit);
    if (ChainsLeft > 0 && OtherActor)
    {
        ChainLightning(OtherActor, Hit.ImpactPoint);
    }
    if (UWorld* World = GetWorld())
    {
        FVector Normal = Hit.ImpactNormal.GetSafeNormal();
        if (Normal.IsNearlyZero()) Normal = -GetActorForwardVector();
        if (Look != EReflectionsSpellLook::Catalog)
        {
            // Tarnish bolts and wisps burst into their own black-violet smoke, silver sparks and stain.
            if (UReflectionsSpellVfxSubsystem* Vfx = World->GetSubsystem<UReflectionsSpellVfxSubsystem>())
            {
                Vfx->SpawnTarnishImpact(Hit.ImpactPoint, Normal, Caster, Look == EReflectionsSpellLook::TarnishWisp ? 1.15f : 0.9f, false);
            }
        }
        else if (UReflectionsSpellEventSubsystem* Events = World->GetSubsystem<UReflectionsSpellEventSubsystem>())
        {
            Events->OnSpellImpactVisual.Broadcast(Spell, Hit.ImpactPoint, Normal, Caster, bExplosion ? 2.1f : 0.8f + BlastRadius / 250.0f);
        }
    }
    if (Caster)
    {
        if (UReflectionsSpellCombatComponent* Combat = Caster->FindComponentByClass<UReflectionsSpellCombatComponent>())
        {
            Combat->NotifyImpact(Spell, OtherActor, Hit.ImpactPoint);
        }
    }
    Destroy();
}

UReflectionsSpellCombatComponent::UReflectionsSpellCombatComponent()
{
    PrimaryComponentTick.bCanEverTick = false;
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Fire(
        TEXT("/Game/Characters/WhiteLondon/IvenRook/MetaHuman/Animation/ElementalSpells/FX/SM_Iven_FlameTongues.SM_Iven_FlameTongues"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> FireTint(
        TEXT("/Game/Characters/WhiteLondon/IvenRook/MetaHuman/Animation/ElementalSpells/FX/M_Iven_FireOrange.M_Iven_FireOrange"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Water(
        TEXT("/Game/Characters/WhiteLondon/IvenRook/MetaHuman/Animation/ElementalSpells/FX/SM_Iven_WaterCrescent.SM_Iven_WaterCrescent"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> WaterTint(
        TEXT("/Game/Characters/WhiteLondon/IvenRook/MetaHuman/Animation/ElementalSpells/FX/M_Iven_WaterCyan.M_Iven_WaterCyan"));
    FireMesh = Fire.Object;
    FireMaterial = FireTint.Object;
    WaterMesh = Water.Object;
    WaterMaterial = WaterTint.Object;
}

void UReflectionsSpellCombatComponent::BeginPlay()
{
    Super::BeginPlay();
    if (AReflectionsHeroCharacter* Hero = Cast<AReflectionsHeroCharacter>(GetOwner()))
    {
        Hero->OnHeroSpellReleased.AddUniqueDynamic(this, &UReflectionsSpellCombatComponent::ReleaseSpell);
    }
}

void UReflectionsSpellCombatComponent::ReleaseSpell(EHeroSpell Spell, FTransform Origin)
{
    AActor* Caster = GetOwner();
    if (!Caster || !ReflectionsSpellCatalog::IsValid(Spell))
    {
        return;
    }
    const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(Spell);
    // Unaimed callers (the older hero pawn) keep their previous behaviour: forward projectiles, caster-centred areas.
    const FVector Target = Spec.Delivery == EReflectionsSpellDelivery::Projectile
        ? Origin.GetLocation() + Origin.GetRotation().GetForwardVector() * FMath::Max(Spec.Range, 100.0f)
        : Spell == EHeroSpell::TidalSurge || Spell == EHeroSpell::ForcePush
            ? Caster->GetActorLocation() + Origin.GetRotation().GetForwardVector() * FMath::Max(Spec.Radius, 100.0f)
            : Caster->GetActorLocation();
    ReleaseSpellAt(Spell, Origin, Target, nullptr);
}

void UReflectionsSpellCombatComponent::ReleaseSpellAt(EHeroSpell Spell, FTransform Origin, FVector Target, AActor* AimTarget)
{
    AActor* Caster = GetOwner();
    UWorld* World = GetWorld();
    if (!Caster || !World || !ReflectionsSpellCatalog::IsValid(Spell))
    {
        return;
    }
    const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(Spell);
    UReflectionsSpellEventSubsystem* Events = World->GetSubsystem<UReflectionsSpellEventSubsystem>();
    if (Spec.Delivery == EReflectionsSpellDelivery::Heal)
    {
        if (UReflectionsHealthComponent* Health = Caster->FindComponentByClass<UReflectionsHealthComponent>())
        {
            Health->Heal(Spec.Power, Caster);
        }
        else if (ICombatDamageable* Damageable = Cast<ICombatDamageable>(Caster))
        {
            Damageable->ApplyHealing(Spec.Power, Caster);
        }
        if (Spec.Radius > 0.0f)
            for (AActor* Ally : OverlapTargets(World, Caster->GetActorLocation(), Spec.Radius, Caster))
                if (Ally->ActorHasTag(TEXT("Friendly")))
                    if (UReflectionsHealthComponent* Health = Ally->FindComponentByClass<UReflectionsHealthComponent>()) Health->Heal(Spec.Power, Caster);
        if (Events) Events->OnSupportSpellVisual.Broadcast(Spell, Caster->GetActorLocation(), Caster, Spec.Power);
        return;
    }
    if (Spec.Delivery == EReflectionsSpellDelivery::Ward)
    {
        if (UReflectionsHealthComponent* Health = Caster->FindComponentByClass<UReflectionsHealthComponent>()) Health->GrantShield(Spec.Power);
        if (Events) Events->OnSupportSpellVisual.Broadcast(Spell, Caster->GetActorLocation(), Caster, Spec.Power);
        return;
    }
    if (Spec.Delivery == EReflectionsSpellDelivery::Hover)
    {
        if (Events) Events->OnSupportSpellVisual.Broadcast(Spell, Caster->GetActorLocation(), Caster, 1.0f);
        return;
    }
    if (Spec.Delivery == EReflectionsSpellDelivery::Area)
    {
        const bool bCone = Spell == EHeroSpell::TidalSurge || Spell == EHeroSpell::ForcePush;
        const FVector CasterLocation = Caster->GetActorLocation();
        FVector Forward = (Target - CasterLocation).GetSafeNormal2D();
        if (Forward.IsNearlyZero()) Forward = Caster->GetActorForwardVector();
        // Cones push out from the caster; radial spells erupt where the player aimed.
        const FVector Center = bCone ? CasterLocation : Target + FVector(0.0f, 0.0f, 40.0f);
        if (Events)
        {
            Events->BroadcastSpell(Spell, Center, Caster, Spec.Power + Spec.Impulse * .02f);
            Events->OnDirectionalSpellVisual.Broadcast(Spell, CasterLocation, Forward, Caster, Spec.Power);
            Events->OnSpellReleaseVisual.Broadcast(Spell, Origin.GetLocation(), Forward, Caster, 0.45f);
            if (!bCone)
            {
                Events->OnSpellImpactVisual.Broadcast(Spell, Target, FVector::UpVector, Caster, Spec.Radius / 200.0f);
            }
        }
        for (AActor* Victim : OverlapTargets(World, Center, Spec.Radius, Caster))
        {
            const FVector Offset = Victim->GetActorLocation() - CasterLocation;
            if (!bCone || FVector::DotProduct(Offset.GetSafeNormal2D(), Forward) > .35f)
                AffectTarget(Victim, Caster, Spell, Spec.Power * FMath::Max(0.0f, DamageScale), Spec.Impulse,
                    bCone ? CasterLocation : Center - FVector(0.0f, 0.0f, 60.0f));
        }
        return;
    }
    if (Spec.Delivery != EReflectionsSpellDelivery::Projectile)
    {
        return;
    }

    FVector Direction = (Target - Origin.GetLocation()).GetSafeNormal();
    if (Direction.IsNearlyZero()) Direction = Origin.GetRotation().GetForwardVector();
    const FTransform Launch(Direction.Rotation(), Origin.GetLocation());
    if (Events)
    {
        Events->OnSpellReleaseVisual.Broadcast(Spell, Origin.GetLocation(), Direction, Caster, 0.35f + Spec.Radius / 600.0f);
    }
    AReflectionsSpellProjectile* Projectile = World->SpawnActorDeferred<AReflectionsSpellProjectile>(
        AReflectionsSpellProjectile::StaticClass(), Launch, Caster, Cast<APawn>(Caster),
        ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
    if (Projectile)
    {
        const bool bWaterStyle = Spec.Element == EReflectionsSpellElement::Water || Spec.Element == EReflectionsSpellElement::Ice;
        Projectile->InitializeCatalog(Spell, bWaterStyle ? WaterMesh.Get() : FireMesh.Get(), bWaterStyle ? WaterMaterial.Get() : FireMaterial.Get(),
            DamageScale);
        Projectile->FinishSpawning(Launch);
        // A target in melee range may already be past the hand: strike it now.
        if (!Projectile->ResolvePointBlank(Caster ? Caster->GetActorLocation() : Origin.GetLocation()))
        {
            Projectile->SetHomingTarget(AimTarget);
        }
    }
}

void UReflectionsSpellCombatComponent::NotifyImpact(EHeroSpell Spell, AActor* Target, const FVector& Location)
{
    OnSpellImpact.Broadcast(Spell, Target, Location);
    if (UWorld* World = GetWorld())
        if (UReflectionsSpellEventSubsystem* Events = World->GetSubsystem<UReflectionsSpellEventSubsystem>())
        {
            const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(Spell);
            Events->BroadcastSpell(Spell, Location, GetOwner(), Spec.Power + Spec.Radius * .02f);
        }
}

AReflectionsSpellTarget::AReflectionsSpellTarget()
{
    TargetMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("TargetMesh"));
    SetRootComponent(TargetMesh);
    TargetMesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    TargetMesh->SetCollisionObjectType(ECC_WorldDynamic);
    TargetMesh->SetCollisionResponseToAllChannels(ECR_Block);
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (Cube.Succeeded())
    {
        TargetMesh->SetStaticMesh(Cube.Object);
    }
    Health = CreateDefaultSubobject<UReflectionsHealthComponent>(TEXT("Health"));
    Health->MaxHealth = 3.0f;
}
