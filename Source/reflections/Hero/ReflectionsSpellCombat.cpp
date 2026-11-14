#include "Hero/ReflectionsSpellCombat.h"
#include "Hero/ReflectionsSpellCatalog.h"
#include "Hero/ReflectionsSpellEventSubsystem.h"

#include "Components/SphereComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/OverlapResult.h"
#include "GameFramework/ProjectileMovementComponent.h"
#include "GameFramework/Character.h"
#include "Interfaces/CombatDamageable.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "PhysicalMaterials/PhysicalMaterial.h"
#include "UObject/ConstructorHelpers.h"
#include "TimerManager.h"
#include "Sound/SoundBase.h"

namespace
{
    void AffectTarget(AActor* Target, AActor* Caster, EHeroSpell Spell, float Damage, float Push, const FVector& Origin, const FHitResult* DirectHit = nullptr)
    {
        if (!Target || Target == Caster) return;
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
        if (Push > 0.0f)
        {
            if (ACharacter* Character = Cast<ACharacter>(Target)) Character->LaunchCharacter(Direction * Push + FVector(0,0,Push * .15f), true, true);
            else if (Primitive && Primitive->IsSimulatingPhysics(Hit.BoneName))
                Primitive->AddImpulseAtLocation(Direction * Push, Point, Hit.BoneName);
        }
        if (UWorld* World = Target->GetWorld())
            if (UReflectionsSpellEventSubsystem* Events = World->GetSubsystem<UReflectionsSpellEventSubsystem>())
            {
                FReflectionsSpellHitData Data;
                Data.Spell = Spell; Data.Caster = Caster; Data.Target = Target; Data.Location = Point;
                Data.Impulse = Direction * Push; Data.ImpactNormal = Hit.ImpactNormal; Data.Bone = Hit.BoneName;
                Data.Surface = UPhysicalMaterial::DetermineSurfaceType(Hit.PhysMaterial.Get());
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
        for (const FOverlapResult& Hit : Hits) if (AActor* Actor = Hit.GetActor()) if (Actor != Caster) Targets.Add(Actor);
        return Targets;
    }
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

void AReflectionsSpellProjectile::InitializeCatalog(EHeroSpell InSpell, UStaticMesh* InMesh, UMaterialInterface* InMaterial)
{
    const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(InSpell);
    BlastRadius = Spec.Radius;
    HitImpulse = Spec.Impulse;
    Initialize(InSpell, Spec.Power, Spec.Speed, Spec.Range, InMesh, InMaterial);
}

void AReflectionsSpellProjectile::SetHomingTarget(AActor* Target)
{
    if (!Target || !Target->GetRootComponent())
    {
        return;
    }
    Movement->bIsHomingProjectile = true;
    Movement->HomingTargetComponent = Target->GetRootComponent();
    // Proportional to speed so fast bolts still bend a little, slow orbs a lot.
    Movement->HomingAccelerationMagnitude = Movement->InitialSpeed * 2.2f;
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
    if (BlastRadius > 0.0f)
    {
        TSet<AActor*> Targets = OverlapTargets(GetWorld(), Hit.ImpactPoint, BlastRadius, Caster);
        if (OtherActor && OtherActor != Caster) Targets.Add(OtherActor);
        for (AActor* Target : Targets) AffectTarget(Target, Caster, Spell, Damage, HitImpulse, Hit.ImpactPoint, Target == OtherActor ? &Hit : nullptr);
    }
    else if (OtherActor) AffectTarget(OtherActor, Caster, Spell, Damage, HitImpulse, Hit.ImpactPoint - GetActorForwardVector() * 10.0f, &Hit);
    if (UWorld* World = GetWorld())
    {
        if (UReflectionsSpellEventSubsystem* Events = World->GetSubsystem<UReflectionsSpellEventSubsystem>())
        {
            FVector Normal = Hit.ImpactNormal.GetSafeNormal();
            if (Normal.IsNearlyZero()) Normal = -GetActorForwardVector();
            Events->OnSpellImpactVisual.Broadcast(Spell, Hit.ImpactPoint, Normal, Caster, 0.8f + BlastRadius / 250.0f);
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
                AffectTarget(Victim, Caster, Spell, Spec.Power, Spec.Impulse, bCone ? CasterLocation : Center - FVector(0.0f, 0.0f, 60.0f));
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
        Projectile->InitializeCatalog(Spell, bWaterStyle ? WaterMesh.Get() : FireMesh.Get(), bWaterStyle ? WaterMaterial.Get() : FireMaterial.Get());
        Projectile->FinishSpawning(Launch);
        Projectile->SetHomingTarget(AimTarget);
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
