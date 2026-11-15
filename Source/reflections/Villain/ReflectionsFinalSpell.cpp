#include "Villain/ReflectionsFinalSpell.h"

#include "Villain/ReflectionsVillainBoss.h"
#include "Villain/ReflectionsVillainConfig.h"
#include "Villain/ReflectionsVillainFx.h"
#include "Villain/ReflectionsVillainHud.h"
#include "Villain/ReflectionsVillainPossession.h"
#include "Villain/ReflectionsVillainSubsystem.h"
#include "Villain/ReflectionsVillainText.h"

#include "SpellCrafting/ReflectionsSpellCraftingComponent.h"

#include "Hero/ReflectionsSampleSpellDriver.h"

#include "Components/PointLightComponent.h"
#include "Components/SphereComponent.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/ProjectileMovementComponent.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "NiagaraComponent.h"

#define LOCTEXT_NAMESPACE "ReflectionsVillain"

namespace
{
    double LastFinalCast = -100.0;
}

// ============================================================================================ component

UReflectionsFinalSpellComponent::UReflectionsFinalSpellComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.TickInterval = 0.1f;
}

void UReflectionsFinalSpellComponent::BeginPlay()
{
    Super::BeginPlay();
    if (AActor* Owner = GetOwner())
    {
        Driver = Owner->FindComponentByClass<UReflectionsSampleSpellDriver>();
    }
    LastFinalCast = -100.0;
    BindInput();
}

void UReflectionsFinalSpellComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    APawn* Pawn = Cast<APawn>(GetOwner());
    APlayerController* PC = Pawn ? Cast<APlayerController>(Pawn->GetController()) : nullptr;
    if (PC)
    {
        if (Input)
        {
            PC->PopInputComponent(Input);
        }
        if (ULocalPlayer* Player = PC->GetLocalPlayer())
        {
            if (UEnhancedInputLocalPlayerSubsystem* Subsystem = Player->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>())
            {
                if (Context)
                {
                    Subsystem->RemoveMappingContext(Context);
                }
            }
        }
    }
    if (UReflectionsVillainSubsystem* Villain = UReflectionsVillainSubsystem::Get(GetWorld()))
    {
        if (UReflectionsVillainHudWidget* Hud = Villain->GetOrCreateHud())
        {
            Hud->SetFinalSpell(false, FText::GetEmpty(), false);
        }
    }
    Super::EndPlay(Reason);
}

void UReflectionsFinalSpellComponent::BindInput()
{
    APawn* Pawn = Cast<APawn>(GetOwner());
    APlayerController* PC = Pawn && Pawn->IsLocallyControlled() ? Cast<APlayerController>(Pawn->GetController()) : nullptr;
    if (!PC || Input)
    {
        return;
    }
    ULocalPlayer* Player = PC->GetLocalPlayer();
    UEnhancedInputLocalPlayerSubsystem* Subsystem = Player ? Player->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>() : nullptr;
    if (!Subsystem)
    {
        return;
    }
    // Built at runtime, like the spell driver's context, so it needs no assets. Priority 3 sits above spells (1) and world jump (2).
    Context = NewObject<UInputMappingContext>(this, TEXT("IMC_FinalSpell"));
    Action = NewObject<UInputAction>(this, TEXT("IA_FinalSpell"));
    Action->ValueType = EInputActionValueType::Boolean;
    Action->bConsumeInput = true;
    Context->MapKey(Action, EKeys::F);
    Context->MapKey(Action, EKeys::Gamepad_FaceButton_Left);
    Input = NewObject<UEnhancedInputComponent>(PC, TEXT("FinalSpellInput"));
    Input->RegisterComponent();
    Input->BindAction(Action, ETriggerEvent::Started, this, &UReflectionsFinalSpellComponent::OnCastPressed);
    PC->PushInputComponent(Input);
    Subsystem->AddMappingContext(Context, 3);
}

void UReflectionsFinalSpellComponent::OnCastPressed()
{
    // F and X belong to the crafting screen while it is open.
    if (const AActor* Owner = GetOwner())
    {
        if (const UReflectionsSpellCraftingComponent* Crafting = Owner->FindComponentByClass<UReflectionsSpellCraftingComponent>())
        {
            if (Crafting->IsCraftingScreenOpen())
            {
                return;
            }
        }
    }
    CastFinalSpell();
}

bool UReflectionsFinalSpellComponent::CastFinalSpell()
{
    UWorld* World = GetWorld();
    APawn* Pawn = Cast<APawn>(GetOwner());
    if (!World || !Pawn)
    {
        return false;
    }
    if (UReflectionsSampleSpellDriver* SpellDriver = Driver.Get())
    {
        FReflectionsExternalCast Cast;
        Cast.AimProxy = EHeroSpell::ArcaneBolt;
        Cast.ManaCost = ReflectionsVillainTuning::FinalSpellManaCost();
        Cast.Cooldown = ReflectionsVillainTuning::FinalSpellCooldown();
        TWeakObjectPtr<UReflectionsFinalSpellComponent> Weak(this);
        Cast.OnRelease = [Weak](const FTransform& Origin, const FVector& Target, AActor* AimTarget)
        {
            if (UReflectionsFinalSpellComponent* Self = Weak.Get())
            {
                Self->Release(Origin.GetLocation(), Target, AimTarget);
            }
        };
        if (SpellDriver->CastExternal(Cast))
        {
            LastFinalCast = World->GetTimeSeconds();
            ReflectionsVillainFx::Sound(World, ReflectionsVillainAssets::FinalSpellSound(), Pawn->GetActorLocation(), 0.7f, 1.1f);
            return true;
        }
        return false;
    }
    // No spell driver on this pawn: fire straight from the view.
    if (World->GetTimeSeconds() < CooldownUntil)
    {
        return false;
    }
    CooldownUntil = World->GetTimeSeconds() + ReflectionsVillainTuning::FinalSpellCooldown();
    LastFinalCast = World->GetTimeSeconds();
    FVector ViewLocation;
    FRotator ViewRotation;
    Pawn->GetActorEyesViewPoint(ViewLocation, ViewRotation);
    if (const AController* Controller = Pawn->GetController())
    {
        ViewRotation = Controller->GetControlRotation();
    }
    const FVector Origin = Pawn->GetActorLocation() + FVector(0.0f, 0.0f, 50.0f) + ViewRotation.Vector() * 70.0f;
    Release(Origin, Origin + ViewRotation.Vector() * 5000.0f, nullptr);
    ReflectionsVillainFx::Sound(World, ReflectionsVillainAssets::FinalSpellSound(), Origin, 0.7f, 1.1f);
    return true;
}

void UReflectionsFinalSpellComponent::Release(const FVector& Origin, const FVector& Target, AActor* AimTarget)
{
    UWorld* World = GetWorld();
    APawn* Pawn = Cast<APawn>(GetOwner());
    if (!World || !Pawn)
    {
        return;
    }
    FVector Direction = (Target - Origin).GetSafeNormal();
    if (Direction.IsNearlyZero())
    {
        Direction = Pawn->GetActorForwardVector();
    }
    // Home on his true form when he is roughly where the player aims; also on infected people the player aims at.
    AActor* Homing = nullptr;
    UReflectionsVillainSubsystem* Villain = UReflectionsVillainSubsystem::Get(World);
    AReflectionsVillainBoss* Boss = Villain ? Villain->GetBoss() : nullptr;
    if (Boss && Boss->GetBossState() == EReflectionsVillainBossState::Fighting)
    {
        const FVector ToBoss = Boss->GetActorLocation() - Origin;
        if (AimTarget == Boss || (FVector::DotProduct(ToBoss.GetSafeNormal(), Direction) > FMath::Cos(FMath::DegreesToRadians(35.0f))
            && ToBoss.Size() < 7000.0f))
        {
            Homing = Boss;
        }
    }
    if (!Homing && AimTarget && UReflectionsVillainPossessionComponent::StateOf(AimTarget) != EReflectionsVillainInfection::None)
    {
        Homing = AimTarget;
    }
    FActorSpawnParameters Params;
    Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    Params.Instigator = Pawn;
    Params.Owner = Pawn;
    if (AReflectionsFinalSpellProjectile* Bolt = World->SpawnActor<AReflectionsFinalSpellProjectile>(AReflectionsFinalSpellProjectile::StaticClass(),
        Origin, Direction.Rotation(), Params))
    {
        Bolt->Fire(Direction, Homing);
    }
    ReflectionsVillainFx::Impact(World, Origin, ReflectionsVillainColors::FinalGold, ReflectionsVillainColors::FinalWhite, 0.45f, 0.0f, Direction);
}

void UReflectionsFinalSpellComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
    if (!Input)
    {
        BindInput();
    }
    UWorld* World = GetWorld();
    UReflectionsVillainSubsystem* Villain = UReflectionsVillainSubsystem::Get(World);
    UReflectionsVillainHudWidget* Hud = Villain ? Villain->GetOrCreateHud() : nullptr;
    if (!Hud || !World)
    {
        return;
    }
    const UReflectionsSampleSpellDriver* SpellDriver = Driver.Get();
    const float Cooldown = ReflectionsVillainTuning::FinalSpellCooldown();
    const float Left = static_cast<float>(LastFinalCast + Cooldown - World->GetTimeSeconds());
    const float Cost = ReflectionsVillainTuning::FinalSpellManaCost();
    FText Status;
    bool bReady = false;
    if (Left > 0.0f)
    {
        Status = ReflectionsVillainText::Recharging(Left);
    }
    else if (SpellDriver && SpellDriver->GetMana() < Cost)
    {
        Status = ReflectionsVillainText::NeedMana(FMath::RoundToInt(Cost));
    }
    else
    {
        Status = ReflectionsVillainText::Ready();
        bReady = true;
    }
    Hud->SetFinalSpell(true, ReflectionsVillainText::FinalPrompt(SpellDriver && SpellDriver->IsUsingGamepad(), Status), bReady);
}

// ============================================================================================ projectile

AReflectionsFinalSpellProjectile::AReflectionsFinalSpellProjectile()
{
    PrimaryActorTick.bCanEverTick = true;
    InitialLifeSpan = 4.0f;
    Collision = CreateDefaultSubobject<USphereComponent>(TEXT("Collision"));
    RootComponent = Collision;
    Collision->InitSphereRadius(22.0f);
    Collision->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    Collision->SetCollisionObjectType(ECC_WorldDynamic);
    Collision->SetCollisionResponseToAllChannels(ECR_Ignore);
    Collision->SetCollisionResponseToChannel(ECC_WorldStatic, ECR_Block);
    Collision->SetCollisionResponseToChannel(ECC_WorldDynamic, ECR_Block);
    Collision->SetCollisionResponseToChannel(ECC_Pawn, ECR_Block);
    Collision->SetCanEverAffectNavigation(false);
    Collision->OnComponentHit.AddDynamic(this, &AReflectionsFinalSpellProjectile::HandleHit);
    Movement = CreateDefaultSubobject<UProjectileMovementComponent>(TEXT("Movement"));
    Movement->UpdatedComponent = Collision;
    Movement->ProjectileGravityScale = 0.0f;
    Movement->InitialSpeed = 0.0f;
    Movement->MaxSpeed = 3400.0f;
    Movement->bInitialVelocityInLocalSpace = false;
    Movement->bRotationFollowsVelocity = true;
    Movement->bShouldBounce = false;
}

void AReflectionsFinalSpellProjectile::BeginPlay()
{
    Super::BeginPlay();
    if (APawn* Caster = GetInstigator())
    {
        Collision->IgnoreActorWhenMoving(Caster, true);
        TArray<AActor*> Attached;
        Caster->GetAttachedActors(Attached, true, true);
        for (AActor* Actor : Attached)
        {
            Collision->IgnoreActorWhenMoving(Actor, true);
        }
    }
    Visual = ReflectionsVillainFx::Projectile(GetWorld(), Collision, FVector::ZeroVector, ReflectionsVillainColors::FinalGold,
        ReflectionsVillainColors::FinalWhite, 1.7f);
    Light = NewObject<UPointLightComponent>(this, TEXT("FinalLight"));
    Light->SetupAttachment(Collision);
    Light->SetLightColor(ReflectionsVillainColors::FinalGold);
    Light->SetIntensity(9000.0f);
    Light->SetAttenuationRadius(650.0f);
    Light->SetCastShadows(false);
    Light->RegisterComponent();
}

void AReflectionsFinalSpellProjectile::Fire(const FVector& Direction, AActor* HomingTarget)
{
    Movement->Velocity = Direction.GetSafeNormal() * 2800.0f;
    Homing = HomingTarget;
    if (HomingTarget && HomingTarget->GetRootComponent())
    {
        Movement->bIsHomingProjectile = true;
        Movement->HomingTargetComponent = HomingTarget->GetRootComponent();
        Movement->HomingAccelerationMagnitude = 14000.0f;
    }
}

void AReflectionsFinalSpellProjectile::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (bDone)
    {
        return;
    }
    if (AActor* Target = Homing.Get())
    {
        if (FVector::Dist(Target->GetActorLocation(), GetActorLocation()) < 150.0f)
        {
            Explode(Target, GetActorLocation());
        }
    }
}

void AReflectionsFinalSpellProjectile::HandleHit(UPrimitiveComponent* HitComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp,
    FVector NormalImpulse, const FHitResult& Hit)
{
    if (!bDone)
    {
        Explode(OtherActor, Hit.ImpactPoint);
    }
}

void AReflectionsFinalSpellProjectile::Explode(AActor* Victim, const FVector& Point)
{
    bDone = true;
    UWorld* World = GetWorld();
    AActor* Caster = GetInstigator();
    if (AReflectionsVillainBoss* Boss = Cast<AReflectionsVillainBoss>(Victim))
    {
        ReflectionsVillainFx::Damage(Boss, ReflectionsVillainTuning::FinalSpellDamage(), Caster ? Caster : this,
            Point - Movement->Velocity.GetSafeNormal() * 100.0f, 0.0f, UReflectionsFinalSpellDamageType::StaticClass());
    }
    else if (UReflectionsVillainPossessionComponent* Possession = Victim ? Victim->FindComponentByClass<UReflectionsVillainPossessionComponent>() : nullptr)
    {
        // The book's light burns the shadow out of a body without harming it.
        Possession->Cleanse();
    }
    ReflectionsVillainFx::Impact(World, Point, ReflectionsVillainColors::FinalGold, ReflectionsVillainColors::FinalWhite, 2.2f, 0.3f);
    Movement->StopMovementImmediately();
    Collision->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    if (Visual)
    {
        Visual->Deactivate();
    }
    if (Light)
    {
        Light->SetIntensity(0.0f);
    }
    SetLifeSpan(1.0f);
}

#undef LOCTEXT_NAMESPACE
