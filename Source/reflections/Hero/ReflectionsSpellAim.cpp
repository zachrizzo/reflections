#include "Hero/ReflectionsSpellAim.h"
#include "Hero/ReflectionsSpellCatalog.h"
#include "Hero/ReflectionsSpellCombat.h"

#include "Camera/PlayerCameraManager.h"
#include "Components/CapsuleComponent.h"
#include "Components/DecalComponent.h"
#include "EngineUtils.h"
#include "EnhancedPlayerInput.h"
#include "GameFramework/Character.h"
#include "GameFramework/PlayerController.h"
#include "InputAction.h"
#include "Interfaces/CombatDamageable.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "NPC/ReflectionsNpcSubsystem.h"

namespace
{
    const TCHAR* AimActionPath = TEXT("/Game/Input/IA_Aim.IA_Aim");
    const TCHAR* PreviewMaterialPath = TEXT("/Game/Characters/Hero/SpellVFX/Materials/M_Spell_AimDecal.M_Spell_AimDecal");

    bool IsCone(EHeroSpell Spell)
    {
        return Spell == EHeroSpell::TidalSurge || Spell == EHeroSpell::ForcePush;
    }

    /** Chest-height point on a likely target, or its bounds centre. */
    FVector TargetPoint(const AActor* Actor)
    {
        if (const ACharacter* Character = Cast<ACharacter>(Actor))
        {
            const float HalfHeight = Character->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
            return Character->GetActorLocation() + FVector(0.0f, 0.0f, HalfHeight * 0.35f);
        }
        FVector Origin, Extent;
        Actor->GetActorBounds(true, Origin, Extent);
        return Origin;
    }

    /** The NPC an actor belongs to: itself, or the NPC a hidden locomotion pawn drives. */
    AActor* ResolveNpc(const UReflectionsNpcSubsystem* Npcs, AActor* Actor)
    {
        if (Npcs && Actor)
        {
            if (const UReflectionsNpcReactionComponent* Npc = Npcs->FindNpc(Actor)) return Npc->GetOwner();
        }
        return Actor;
    }

    bool IsAssistCandidate(const AActor* Actor, const AActor* Owner)
    {
        // Friendly actors stay candidates, but only inside FriendlyConeDegrees (see Consider). The walkers' hidden
        // locomotion pawns are filtered in Consider (they resolve to another NPC); the NPC_SampleLocomotion tag
        // is on the visible walker, so it must not be filtered here.
        if (!IsValid(Actor) || Actor == Owner || Actor->IsHidden())
        {
            return false;
        }
        if (const UReflectionsHealthComponent* Health = Actor->FindComponentByClass<UReflectionsHealthComponent>())
        {
            return Health->Health > 0.0f;
        }
        return Actor->IsA<APawn>() || Actor->Implements<UCombatDamageable>();
    }
}

// --------------------------------------------------------------------------------------------- camera

UReflectionsSpellCameraModifier* UReflectionsSpellCameraModifier::Get(const APlayerController* Controller)
{
    if (!Controller || !Controller->PlayerCameraManager)
    {
        return nullptr;
    }
    return Cast<UReflectionsSpellCameraModifier>(
        Controller->PlayerCameraManager->FindCameraModifierByClass(UReflectionsSpellCameraModifier::StaticClass()));
}

bool UReflectionsSpellCameraModifier::ModifyCamera(float DeltaTime, FMinimalViewInfo& InOutPOV)
{
    Clock += DeltaTime;
    Kick = FMath::FInterpTo(Kick, 0.0f, DeltaTime, 9.0f);
    Trauma = FMath::Max(0.0f, Trauma - DeltaTime * 1.5f);

    const float Zoom = FMath::SmoothStep(0.0f, 1.0f, AimAlpha);
    InOutPOV.FOV = FMath::Clamp(InOutPOV.FOV - AimZoomDegrees * Zoom + Kick * 2.5f, 25.0f, 120.0f);
    InOutPOV.Rotation.Pitch += Kick * 0.7f;

    // Squared trauma keeps small hits subtle and big blasts punchy.
    const float Shake = Trauma * Trauma;
    if (Shake > KINDA_SMALL_NUMBER)
    {
        // Low-ish frequency and amplitude: high-frequency jitter reads as motion blur, not impact.
        InOutPOV.Rotation.Pitch += Shake * 1.5f * FMath::PerlinNoise1D(Clock * 14.0f);
        InOutPOV.Rotation.Yaw += Shake * 1.5f * FMath::PerlinNoise1D(Clock * 14.0f + 71.3f);
        InOutPOV.Rotation.Roll += Shake * 1.0f * FMath::PerlinNoise1D(Clock * 11.0f + 13.1f);
        InOutPOV.Location += InOutPOV.Rotation.RotateVector(FVector(0.0f,
            FMath::PerlinNoise1D(Clock * 19.0f + 5.0f), FMath::PerlinNoise1D(Clock * 19.0f + 31.0f))) * Shake * 4.0f;
    }
    return false;
}

// --------------------------------------------------------------------------------------------- aim

UReflectionsSpellAimComponent::UReflectionsSpellAimComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.TickGroup = TG_PostPhysics;
}

void UReflectionsSpellAimComponent::BeginPlay()
{
    Super::BeginPlay();
    AimAction = LoadObject<UInputAction>(nullptr, AimActionPath);

    Preview = NewObject<UDecalComponent>(GetOwner(), TEXT("SpellAimPreview"));
    Preview->SetUsingAbsoluteLocation(true);
    Preview->SetUsingAbsoluteRotation(true);
    Preview->SetUsingAbsoluteScale(true);
    Preview->SetFadeScreenSize(0.0f);
    Preview->SortOrder = 10;
    if (UMaterialInterface* Material = LoadObject<UMaterialInterface>(nullptr, PreviewMaterialPath))
    {
        PreviewMaterial = UMaterialInstanceDynamic::Create(Material, this);
        Preview->SetDecalMaterial(PreviewMaterial);
    }
    Preview->RegisterComponent();
    Preview->SetVisibility(false);
}

void UReflectionsSpellAimComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    if (Preview)
    {
        Preview->DestroyComponent();
        Preview = nullptr;
    }
    Super::EndPlay(Reason);
}

APlayerController* UReflectionsSpellAimComponent::GetLocalController() const
{
    const APawn* Pawn = Cast<APawn>(GetOwner());
    return Pawn && Pawn->IsLocallyControlled() ? Cast<APlayerController>(Pawn->GetController()) : nullptr;
}

bool UReflectionsSpellAimComponent::ReadAimInput(APlayerController* Controller) const
{
    if (!Controller)
    {
        return false;
    }
    if (const UEnhancedPlayerInput* Input = Cast<UEnhancedPlayerInput>(Controller->PlayerInput))
    {
        if (AimAction && Input->GetActionValue(AimAction).Get<bool>())
        {
            return true;
        }
    }
    return Controller->IsInputKeyDown(EKeys::RightMouseButton) || Controller->IsInputKeyDown(EKeys::Gamepad_LeftTrigger);
}

void UReflectionsSpellAimComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
    APlayerController* Controller = GetLocalController();
    if (!Controller)
    {
        return;
    }
    if (!CameraModifier && Controller->PlayerCameraManager)
    {
        CameraModifier = Cast<UReflectionsSpellCameraModifier>(
            Controller->PlayerCameraManager->AddNewCameraModifier(UReflectionsSpellCameraModifier::StaticClass()));
    }

    bAiming = ReadAimInput(Controller);
    AimAlpha = FMath::FInterpTo(AimAlpha, bAiming ? 1.0f : 0.0f, DeltaTime, bAiming ? 10.0f : 8.0f);
    CastSpread = FMath::Max(0.0f, CastSpread - DeltaTime * 3.5f);
    HitMarker = FMath::Max(0.0f, HitMarker - DeltaTime * 3.0f);
    if (CameraModifier)
    {
        CameraModifier->AimAlpha = AimAlpha;
    }
    ElementColor = ReflectionsSpellCatalog::ElementColor(ReflectionsSpellCatalog::Get(SelectedSpell).Element);

    UpdateAimTrace(Controller, DeltaTime);
    UpdatePreview();
}

void UReflectionsSpellAimComponent::UpdateAimTrace(APlayerController* Controller, float DeltaTime)
{
    FRotator ViewRotation;
    Controller->GetPlayerViewPoint(ViewLocation, ViewRotation);
    ViewDirection = ViewRotation.Vector();
    AActor* Owner = GetOwner();
    UWorld* World = GetWorld();

    FCollisionQueryParams Params(SCENE_QUERY_STAT(SpellAimTrace), false, Owner);
    TArray<AActor*> Attached;
    Owner->GetAttachedActors(Attached, true, true);
    Params.AddIgnoredActors(Attached);

    // Start the ray level with the character so walls behind the over-the-shoulder camera are ignored.
    const float Forward = FMath::Max(0.0f, FVector::DotProduct(Owner->GetActorLocation() - ViewLocation, ViewDirection));
    const FVector Start = ViewLocation + ViewDirection * Forward;
    const FVector End = ViewLocation + ViewDirection * MaxAimDistance;
    FHitResult Hit;
    bAimHit = World->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, Params);
    AimPoint = bAimHit ? FVector(Hit.ImpactPoint) : End;
    AimNormal = bAimHit ? FVector(Hit.ImpactNormal) : -ViewDirection;

    // Light assist: the closest valid enemy inside a small cone around the reticle wins.
    AssistTarget.Reset();
    const float Cone = FMath::DegreesToRadians(AssistConeDegrees * (bAiming ? 1.0f : 0.6f) * (bGamepad ? 1.7f : 1.0f));
    const float EnemyCos = FMath::Cos(Cone);
    const float FriendlyCos = FMath::Cos(FMath::DegreesToRadians(FMath::Min(FriendlyConeDegrees, AssistConeDegrees)));
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(World);
    float BestScore = -1.0f;
    AActor* Best = nullptr;
    bool bBestFriendly = false;
    FVector BestPoint = FVector::ZeroVector;
    auto Consider = [&](AActor* Actor)
    {
        if (!IsAssistCandidate(Actor, Owner))
        {
            return;
        }
        // A pawn that drives another NPC (the walkers' hidden GASP pawns) is never the target; the NPC is.
        if (ResolveNpc(Npcs, Actor) != Actor)
        {
            return;
        }
        const bool bFriendly = Actor->ActorHasTag(TEXT("Friendly"));
        const float CosCone = bFriendly ? FriendlyCos : EnemyCos;
        // NPCs of the unified system know their chest (spine bone or hit capsule); others use capsule or bounds.
        FVector Point = TargetPoint(Actor);
        if (const UReflectionsNpcReactionComponent* Npc = Npcs ? Npcs->FindNpc(Actor) : nullptr) Point = Npc->GetAimPoint();
        const FVector ToTarget = Point - ViewLocation;
        const float Distance = ToTarget.Size();
        if (Distance > MaxAimDistance || Distance < 50.0f)
        {
            return;
        }
        const float Cos = FVector::DotProduct(ToTarget / Distance, ViewDirection);
        if (Cos < CosCone)
        {
            return;
        }
        // Prefer centred and near; a quarter of the score comes from distance.
        const float Score = (Cos - CosCone) / (1.0f - CosCone + KINDA_SMALL_NUMBER) * 0.75f + (1.0f - Distance / MaxAimDistance) * 0.25f;
        if (Score <= BestScore)
        {
            return;
        }
        FHitResult Block;
        if (World->LineTraceSingleByChannel(Block, Start, Point, ECC_Visibility, Params) && Block.GetActor() != Actor)
        {
            return;
        }
        BestScore = Score;
        Best = Actor;
        bBestFriendly = bFriendly;
        BestPoint = Point;
    };
    for (TActorIterator<APawn> It(World); It; ++It)
    {
        Consider(*It);
    }
    for (TActorIterator<AReflectionsSpellTarget> It(World); It; ++It)
    {
        Consider(*It);
    }
    // Actor-only NPCs (crowd MetaHumans, infected, hosts) from the unified NPC system.
    if (Npcs)
    {
        for (AActor* Npc : Npcs->GetNpcActors())
        {
            if (!Npc || Npc->IsA<APawn>()) continue;  // Pawns were considered above.
            Consider(Npc);
        }
    }
    // Reticle directly on a target (or its hit proxy / driver pawn): that is the player's pick, Friendly or not.
    // It locks for homing; a civilian still never pulls the camera.
    if (bAimHit && Hit.GetActor())
    {
        AActor* Direct = ResolveNpc(Npcs, Hit.GetActor());
        if (Direct && IsAssistCandidate(Direct, Owner))
        {
            Best = Direct;
            bBestFriendly = Direct->ActorHasTag(TEXT("Friendly"));
            BestPoint = Hit.ImpactPoint;
        }
    }
    if (Best)
    {
        AssistTarget = Best;
        AimPoint = BestPoint;
        AimNormal = (ViewLocation - BestPoint).GetSafeNormal();
        bAimHit = true;
        if (bAiming && AssistTurnRate > 0.0f && !bBestFriendly)
        {
            const FRotator Current = Controller->GetControlRotation();
            FRotator Desired = (BestPoint - ViewLocation).Rotation();
            Desired.Roll = Current.Roll;
            Controller->SetControlRotation(FMath::RInterpConstantTo(Current, Desired, DeltaTime, AssistTurnRate * (bGamepad ? 4.0f : 1.0f)));
        }
    }
}

FVector UReflectionsSpellAimComponent::GroundBelow(const FVector& Point) const
{
    FHitResult Ground;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(SpellAimGround), false, GetOwner());
    if (GetWorld()->LineTraceSingleByChannel(Ground, Point + FVector(0.0f, 0.0f, 150.0f), Point - FVector(0.0f, 0.0f, 2000.0f),
        ECC_Visibility, Params))
    {
        return Ground.ImpactPoint;
    }
    return Point;
}

FVector UReflectionsSpellAimComponent::ClampToRange(const FVector& Point, float Range) const
{
    const FVector From = GetOwner()->GetActorLocation();
    const FVector Offset = Point - From;
    return Offset.Size2D() > Range ? From + Offset.GetSafeNormal2D() * Range + FVector(0.0f, 0.0f, Offset.Z) : Point;
}

EReflectionsAimPreview UReflectionsSpellAimComponent::PreviewFor(EHeroSpell Spell, float& OutRadius) const
{
    const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(Spell);
    OutRadius = Spec.Radius;
    switch (Spec.Delivery)
    {
    case EReflectionsSpellDelivery::Projectile:
        if (Spec.Radius > 0.0f)
        {
            return EReflectionsAimPreview::Blast;
        }
        OutRadius = 32.0f;
        return EReflectionsAimPreview::HitMarker;
    case EReflectionsSpellDelivery::Area:
        return IsCone(Spell) ? EReflectionsAimPreview::Cone : EReflectionsAimPreview::GroundArea;
    case EReflectionsSpellDelivery::Heal:
        OutRadius = Spec.Radius > 0.0f ? Spec.Radius : 110.0f;
        return EReflectionsAimPreview::Self;
    case EReflectionsSpellDelivery::Ward:
        OutRadius = 120.0f;
        return EReflectionsAimPreview::Self;
    default:
        return EReflectionsAimPreview::None;
    }
}

FVector UReflectionsSpellAimComponent::ResolveTarget(EHeroSpell Spell, const FVector& Origin, AActor*& OutTarget) const
{
    OutTarget = nullptr;
    float Radius = 0.0f;
    const AActor* Owner = GetOwner();
    switch (PreviewFor(Spell, Radius))
    {
    case EReflectionsAimPreview::HitMarker:
    case EReflectionsAimPreview::Blast:
    {
        OutTarget = AssistTarget.Get();
        // Never shoot back toward the camera when the reticle sits on something behind the hand.
        if (FVector::DotProduct(AimPoint - Origin, ViewDirection) < 50.0f)
        {
            return Origin + ViewDirection * ReflectionsSpellCatalog::Get(Spell).Range;
        }
        return AimPoint;
    }
    case EReflectionsAimPreview::GroundArea:
        OutTarget = AssistTarget.Get();
        return GroundBelow(ClampToRange(AimPoint, MaxAreaCastDistance));
    case EReflectionsAimPreview::Cone:
        return Owner->GetActorLocation() + ViewDirection.GetSafeNormal2D() * FMath::Max(Radius, 100.0f);
    default:
        return Owner->GetActorLocation();
    }
}

void UReflectionsSpellAimComponent::UpdatePreview()
{
    if (!Preview)
    {
        return;
    }
    float Radius = 0.0f;
    const EReflectionsAimPreview Kind = PreviewFor(SelectedSpell, Radius);
    const bool bShow = AimAlpha > 0.05f && Kind != EReflectionsAimPreview::None
        && (bAimHit || Kind == EReflectionsAimPreview::Cone || Kind == EReflectionsAimPreview::Self || Kind == EReflectionsAimPreview::GroundArea);
    Preview->SetVisibility(bShow);
    if (!bShow)
    {
        return;
    }
    const AActor* Owner = GetOwner();
    FVector Location = AimPoint;
    FRotator Rotation(-90.0f, 0.0f, 0.0f);
    switch (Kind)
    {
    case EReflectionsAimPreview::HitMarker:
    case EReflectionsAimPreview::Blast:
        Rotation = (-AimNormal).Rotation();
        break;
    case EReflectionsAimPreview::GroundArea:
        Location = GroundBelow(ClampToRange(AimPoint, MaxAreaCastDistance));
        break;
    case EReflectionsAimPreview::Cone:
        Location = GroundBelow(Owner->GetActorLocation() + ViewDirection.GetSafeNormal2D() * Radius * 0.55f);
        Radius *= 0.6f;
        break;
    default:
        Location = GroundBelow(Owner->GetActorLocation());
        break;
    }
    Preview->SetWorldLocationAndRotation(Location, Rotation);
    const float Size = FMath::Max(Radius, 20.0f) * FMath::Lerp(0.6f, 1.0f, AimAlpha);
    Preview->DecalSize = FVector(140.0f, Size, Size);
    Preview->MarkRenderStateDirty();
    if (PreviewMaterial)
    {
        const FLinearColor Locked(1.0f, 0.25f, 0.15f, 1.0f);
        PreviewMaterial->SetVectorParameterValue(TEXT("Color"), AssistTarget.IsValid() && Kind == EReflectionsAimPreview::HitMarker
            ? Locked * 1.4f : ElementColor * 1.2f);
    }
}

void UReflectionsSpellAimComponent::NotifyCast()
{
    CastSpread = 1.0f;
    if (CameraModifier)
    {
        CameraModifier->AddKick(bAiming ? 0.45f : 0.7f);
    }
}

void UReflectionsSpellAimComponent::NotifyHit(bool bKilled)
{
    HitMarker = 1.0f;
    bKillMarker = bKilled;
}
