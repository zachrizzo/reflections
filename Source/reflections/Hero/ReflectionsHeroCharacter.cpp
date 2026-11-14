#include "ReflectionsHeroCharacter.h"
#include "ReflectionsHeroAnimInstance.h"

#include "Animation/AnimInstance.h"
#include "Animation/AnimMontage.h"
#include "Animation/AnimSequenceBase.h"
#include "Components/CapsuleComponent.h"
#include "Components/ChildActorComponent.h"
#include "Components/InputComponent.h"
#include "Components/MeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "InputAction.h"
#include "InputCoreTypes.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
    const FName BodyComponentName(TEXT("Body"));

    float GetLevitationHeight(float MontagePosition)
    {
        // Match the cinematic's lift, hover and landing at frames 15, 46, 81 and 112 at 30 fps.
        const float Rise = FMath::SmoothStep(15.0f / 30.0f, 46.0f / 30.0f, MontagePosition);
        const float Fall = FMath::SmoothStep(81.0f / 30.0f, 112.0f / 30.0f, MontagePosition);
        return 65.0f * (Rise - Fall);
    }

    UInputAction* FindInputAction(const TCHAR* AssetPath)
    {
        ConstructorHelpers::FObjectFinder<UInputAction> Finder(AssetPath);
        return Finder.Object;
    }
}

AReflectionsHeroCharacter::AReflectionsHeroCharacter()
{
    PrimaryActorTick.bCanEverTick = true;

    JumpAction = FindInputAction(TEXT("/Game/Input/Actions/IA_Jump.IA_Jump"));
    MoveAction = FindInputAction(TEXT("/Game/Input/Actions/IA_Move.IA_Move"));
    LookAction = FindInputAction(TEXT("/Game/Input/Actions/IA_Look.IA_Look"));
    MouseLookAction = FindInputAction(TEXT("/Game/Input/Actions/IA_MouseLook.IA_MouseLook"));

    HeroVisual = CreateDefaultSubobject<UChildActorComponent>(TEXT("HeroVisual"));
    HeroVisual->SetupAttachment(GetCapsuleComponent());
    HeroVisual->SetRelativeLocationAndRotation(
        FVector(0.0, 0.0, -GetCapsuleComponent()->GetUnscaledCapsuleHalfHeight()),
        FRotator(0.0, -90.0, 0.0));
    BodyAnimationClass = UReflectionsHeroAnimInstance::StaticClass();
    GetMesh()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    GetMesh()->SetVisibility(false);

    UCharacterMovementComponent* Movement = GetCharacterMovement();
    Movement->MaxWalkSpeed = JogSpeed;
    Movement->MaxWalkSpeedCrouched = 140.0f;
    Movement->GetNavAgentPropertiesRef().bCanCrouch = true;
    GetCameraBoom()->TargetArmLength = 415.0f;

    SpellPreview = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("SpellPreview"));
    SpellPreview->SetupAttachment(RootComponent);
    SpellPreview->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    SpellPreview->SetVisibility(false);
    SpellPreview->SetCastShadow(false);
    SpellPreview->SetAbsolute(true, true, true);
}

void AReflectionsHeroCharacter::BeginPlay()
{
    Super::BeginPlay();

    HeroVisual->SetMobility(EComponentMobility::Movable);
    HeroVisual->SetAbsolute(false, false, false);
    UpdateVisualHeight(0.0f);
    if (AActor* Visual = HeroVisual->GetChildActor())
    {
        TInlineComponentArray<USkeletalMeshComponent*> Meshes(Visual);
        for (USkeletalMeshComponent* Component : Meshes)
        {
            if (Component->GetFName() == BodyComponentName)
            {
                AnimatedBody = Component;
                AnimatedBody->SetAnimInstanceClass(BodyAnimationClass);
                AnimatedBody->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
                break;
            }
        }
    }

    if (!AnimatedBody)
    {
        UE_LOG(LogTemp, Warning, TEXT("'%s' requires a Hero Visual child actor with a Body skeletal mesh component."), *GetName());
    }
    SetCoatVariant(CoatVariantIndex);
    RefreshSpeed();
}

void AReflectionsHeroCharacter::UpdateVisualHeight(float Lift)
{
    // Crouching changes both the capsule center and height. The outfit follows its base.
    const UCapsuleComponent* Capsule = GetCapsuleComponent();
    FVector RelativeLocation = HeroVisual->GetRelativeLocation();
    const float TargetHeight = Lift - Capsule->GetUnscaledCapsuleHalfHeight();
    if (!FMath::IsNearlyEqual(RelativeLocation.Z, TargetHeight))
    {
        RelativeLocation.Z = TargetHeight;
        HeroVisual->SetRelativeLocation(RelativeLocation);
    }
}

void AReflectionsHeroCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
    Super::SetupPlayerInputComponent(PlayerInputComponent);

    PlayerInputComponent->BindKey(EKeys::LeftShift, IE_Pressed, this, &AReflectionsHeroCharacter::StartSprint);
    PlayerInputComponent->BindKey(EKeys::LeftShift, IE_Released, this, &AReflectionsHeroCharacter::StopSprint);
    PlayerInputComponent->BindKey(EKeys::LeftAlt, IE_Pressed, this, &AReflectionsHeroCharacter::StartWalk);
    PlayerInputComponent->BindKey(EKeys::LeftAlt, IE_Released, this, &AReflectionsHeroCharacter::StopWalk);
    PlayerInputComponent->BindKey(EKeys::LeftControl, IE_Pressed, this, &AReflectionsHeroCharacter::StartCrouch);
    PlayerInputComponent->BindKey(EKeys::LeftControl, IE_Released, this, &AReflectionsHeroCharacter::StopCrouch);
    PlayerInputComponent->BindKey(EKeys::V, IE_Pressed, this, &AReflectionsHeroCharacter::CycleCoat);
    PlayerInputComponent->BindKey(EKeys::One, IE_Pressed, this, &AReflectionsHeroCharacter::Heal);
    PlayerInputComponent->BindKey(EKeys::Two, IE_Pressed, this, &AReflectionsHeroCharacter::Levitate);
    PlayerInputComponent->BindKey(EKeys::Three, IE_Pressed, this, &AReflectionsHeroCharacter::CastWater);
    PlayerInputComponent->BindKey(EKeys::Four, IE_Pressed, this, &AReflectionsHeroCharacter::CastFire);
}

bool AReflectionsHeroCharacter::SetCoatVariant(int32 Index)
{
    AActor* Visual = HeroVisual->GetChildActor();
    if (!Visual || !CoatVariants.IsValidIndex(Index))
    {
        return false;
    }

    bool bApplied = false;
    const FHeroCoatVariant& Variant = CoatVariants[Index];
    TInlineComponentArray<UMeshComponent*> Meshes(Visual);
    for (UMeshComponent* Component : Meshes)
    {
        if (Component->GetFName() == TEXT("HeroCoat") && Component->GetNumMaterials() > 0 && Variant.Outer)
        {
            Component->SetMaterial(0, Variant.Outer);
            if (Component->GetNumMaterials() > 3 && Variant.Lining)
            {
                Component->SetMaterial(3, Variant.Lining);
            }
            if (Component->GetNumMaterials() > 4 && Variant.Piping)
            {
                Component->SetMaterial(4, Variant.Piping);
            }
            bApplied = true;
        }
        else if (Component->GetFName() == TEXT("HeroTails") && Component->GetNumMaterials() > 0 && Variant.Tails)
        {
            Component->SetMaterial(0, Variant.Tails);
            bApplied = true;
        }
    }
    if (bApplied)
    {
        CoatVariantIndex = Index;
    }
    return bApplied;
}

void AReflectionsHeroCharacter::CycleCoat()
{
    if (CoatVariants.Num() > 1)
    {
        SetCoatVariant((CoatVariantIndex + 1) % CoatVariants.Num());
    }
}

void AReflectionsHeroCharacter::DoMove(float Right, float Forward)
{
    if (!IsCastingHeroSpell())
    {
        Super::DoMove(Right, Forward);
    }
}

bool AReflectionsHeroCharacter::CanJumpInternal_Implementation() const
{
    return !IsCastingHeroSpell() && Super::CanJumpInternal_Implementation();
}

void AReflectionsHeroCharacter::StartSprint()
{
    bSprintHeld = true;
    RefreshSpeed();
}

void AReflectionsHeroCharacter::StopSprint()
{
    bSprintHeld = false;
    RefreshSpeed();
}

void AReflectionsHeroCharacter::StartWalk()
{
    bWalkHeld = true;
    RefreshSpeed();
}

void AReflectionsHeroCharacter::StopWalk()
{
    bWalkHeld = false;
    RefreshSpeed();
}

void AReflectionsHeroCharacter::StartCrouch()
{
    if (!IsCastingHeroSpell())
    {
        Crouch();
    }
}

void AReflectionsHeroCharacter::StopCrouch()
{
    UnCrouch();
}

void AReflectionsHeroCharacter::RefreshSpeed()
{
    GetCharacterMovement()->MaxWalkSpeed = bWalkHeld ? WalkSpeed : bSprintHeld ? SprintSpeed : JogSpeed;
}

void AReflectionsHeroCharacter::Heal() { CastHeroSpell(EHeroSpell::Healing); }
void AReflectionsHeroCharacter::Levitate() { CastHeroSpell(EHeroSpell::Levitation); }
void AReflectionsHeroCharacter::CastWater() { CastHeroSpell(EHeroSpell::Water); }
void AReflectionsHeroCharacter::CastFire() { CastHeroSpell(EHeroSpell::Fire); }

bool AReflectionsHeroCharacter::CastHeroSpell(EHeroSpell Spell)
{
    const FHeroSpellDefinition* Selection = Spells.Find(Spell);
    UAnimInstance* Instance = AnimatedBody ? AnimatedBody->GetAnimInstance() : nullptr;
    UCharacterMovementComponent* Movement = GetCharacterMovement();
    if (!Selection || !Selection->Animation || !Instance || IsCastingHeroSpell()
        || !Movement->IsMovingOnGround() || bIsCrouched)
    {
        return false;
    }

    ActiveCast = Instance->PlaySlotAnimationAsDynamicMontage(
        Selection->Animation, UReflectionsHeroAnimInstance::SpellSlot, 0.16f, 0.22f);
    if (!ActiveCast)
    {
        return false;
    }

    ActiveSpell = Spell;
    bCastReleased = false;
    Movement->StopMovementImmediately();
    ConsumeMovementInputVector();

    FOnMontageEnded Ended;
    Ended.BindUObject(this, &AReflectionsHeroCharacter::FinishHeroSpell);
    Instance->Montage_SetEndDelegate(Ended, ActiveCast);
    return true;
}

void AReflectionsHeroCharacter::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);

    const UAnimInstance* Instance = AnimatedBody ? AnimatedBody->GetAnimInstance() : nullptr;
    const bool bHasActiveMontage = ActiveCast && Instance;
    const float Position = bHasActiveMontage ? Instance->Montage_GetPosition(ActiveCast) : 0.0f;
    const bool bIsLevitating = bHasActiveMontage && ActiveSpell == EHeroSpell::Levitation;
    const float Lift = bIsLevitating ? GetLevitationHeight(Position) : 0.0f;
    UpdateVisualHeight(Lift);

    if (bHasActiveMontage && !bCastReleased)
    {
        const FHeroSpellDefinition* Selection = Spells.Find(ActiveSpell);
        if (Selection && Position >= Selection->ReleaseTime)
        {
            bCastReleased = true;
            ReleaseHeroSpell(*Selection);
        }
    }
    if (bIsLevitating && SpellPreview->IsVisible())
    {
        SpellPreview->SetWorldLocation(HeroVisual->GetComponentLocation() + GetActorUpVector() * 7.0f);
    }
    MoveSpellPreview(DeltaSeconds);
}

void AReflectionsHeroCharacter::ReleaseHeroSpell(const FHeroSpellDefinition& Spell)
{
    const bool bProjectile = ActiveSpell == EHeroSpell::Water || ActiveSpell == EHeroSpell::Fire;
    const FName HandBone = ActiveSpell == EHeroSpell::Water ? TEXT("hand_l") : TEXT("hand_r");
    const FVector Location = bProjectile ? AnimatedBody->GetSocketLocation(HandBone) : GetActorLocation();
    const FTransform Origin(GetActorRotation(), Location);
    if (Spell.PreviewMesh)
    {
        SpellPreview->SetStaticMesh(Spell.PreviewMesh);
        SpellPreview->SetMaterial(0, Spell.PreviewMaterial);
        SpellPreview->SetWorldTransform(Origin);
        SpellPreview->SetVisibility(true);
        PreviewTime = ActiveSpell == EHeroSpell::Levitation
            ? FMath::Max(0.0f, 112.0f / 30.0f - Spell.ReleaseTime)
            : bProjectile ? 0.32f : 0.70f;
    }
    OnHeroSpellReleased.Broadcast(ActiveSpell, Origin);
}

void AReflectionsHeroCharacter::FinishHeroSpell(UAnimMontage* Montage, bool bInterrupted)
{
    if (ActiveCast == Montage)
    {
        ActiveCast = nullptr;
        if (ActiveSpell == EHeroSpell::Levitation)
        {
            UpdateVisualHeight(0.0f);
            PreviewTime = 0.0f;
            SpellPreview->SetVisibility(false);
        }
    }
}

void AReflectionsHeroCharacter::MoveSpellPreview(float DeltaSeconds)
{
    if (PreviewTime <= 0.0f)
    {
        return;
    }
    PreviewTime -= DeltaSeconds;
    const bool bProjectile = ActiveSpell == EHeroSpell::Water || ActiveSpell == EHeroSpell::Fire;
    if (bProjectile)
    {
        SpellPreview->AddWorldOffset(SpellPreview->GetForwardVector() * 760.0f * DeltaSeconds);
    }
    else
    {
        SpellPreview->AddLocalRotation(FRotator(0.0f, 120.0f * DeltaSeconds, 0.0f));
    }
    if (PreviewTime <= 0.0f)
    {
        SpellPreview->SetVisibility(false);
    }
}
