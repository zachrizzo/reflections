#include "Villain/ReflectionsVillainPossession.h"

#include "Villain/ReflectionsVillainConfig.h"
#include "Villain/ReflectionsVillainFx.h"
#include "Villain/ReflectionsVillainSubsystem.h"

#include "Hero/ReflectionsSpellCombat.h"
#include "NPC/ReflectionsNpcSubsystem.h"
#include "Worlds/ReflectionsWorldJumpSubsystem.h"

#include "AIController.h"
#include "Components/CapsuleComponent.h"
#include "Components/MeshComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "NiagaraComponent.h"

#define LOCTEXT_NAMESPACE "ReflectionsVillain"

namespace
{
    const FName HeadBone(TEXT("head"));
    const FName EyeBones[] = {TEXT("FACIAL_L_Eye"), TEXT("FACIAL_R_Eye")};
    // Eye glow (M_Villain_Eye "Glow"): bright enough to bloom at range against Frostside's white and Pewterside's grey.
    constexpr float InfectedEyeGlow = 2.5f;
    constexpr float HostEyeGlow = 4.0f;

    USkeletalMeshComponent* FindHeadMesh(AActor* Owner)
    {
        // The visible body (an NPC's MetaHuman, not its hidden locomotion mannequin).
        if (USkeletalMeshComponent* Visible = ReflectionsVillainFx::HeadMesh(Owner))
        {
            return Visible;
        }
        if (ACharacter* Character = Cast<ACharacter>(Owner))
        {
            if (USkeletalMeshComponent* Mesh = Character->GetMesh())
            {
                if (Mesh->GetSkinnedAsset() && Mesh->GetBoneIndex(HeadBone) != INDEX_NONE)
                {
                    return Mesh;
                }
            }
        }
        TArray<USkeletalMeshComponent*> Meshes;
        Owner->GetComponents<USkeletalMeshComponent>(Meshes);
        for (USkeletalMeshComponent* Mesh : Meshes)
        {
            if (Mesh && Mesh->GetSkinnedAsset() && Mesh->GetBoneIndex(HeadBone) != INDEX_NONE)
            {
                return Mesh;
            }
        }
        return nullptr;
    }

    FVector BodyCenter(const AActor* Actor)
    {
        FVector Origin, Extent;
        Actor->GetActorBounds(true, Origin, Extent);
        return Extent.IsNearlyZero() ? Actor->GetActorLocation() : Origin;
    }
}

// ============================================================================================ possession

UReflectionsVillainPossessionComponent::UReflectionsVillainPossessionComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.TickInterval = 0.05f;
}

UReflectionsVillainPossessionComponent* UReflectionsVillainPossessionComponent::Apply(AActor* Target, EReflectionsVillainInfection NewState, AActor* Source)
{
    if (!IsValid(Target))
    {
        return nullptr;
    }
    UReflectionsVillainPossessionComponent* Component = Target->FindComponentByClass<UReflectionsVillainPossessionComponent>();
    if (!Component)
    {
        if (NewState == EReflectionsVillainInfection::None)
        {
            return nullptr;
        }
        Component = NewObject<UReflectionsVillainPossessionComponent>(Target, TEXT("VillainPossession"));
        Component->RegisterComponent();
    }
    if (Component->State == EReflectionsVillainInfection::BurnedOut && NewState != EReflectionsVillainInfection::BurnedOut)
    {
        return nullptr;
    }
    if (Component->State == EReflectionsVillainInfection::Host && NewState == EReflectionsVillainInfection::Infected)
    {
        return Component;
    }
    Component->SetState(NewState, Source);
    return Component;
}

EReflectionsVillainInfection UReflectionsVillainPossessionComponent::StateOf(const AActor* Target)
{
    const UReflectionsVillainPossessionComponent* Component = Target ? Target->FindComponentByClass<UReflectionsVillainPossessionComponent>() : nullptr;
    if (Component && Component->State != EReflectionsVillainInfection::None)
    {
        return Component->State;
    }
    // The NPC system is the source of truth for NPCs it tarnished without us.
    if (const UReflectionsNpcSubsystem* Npcs = Target ? UReflectionsNpcSubsystem::Get(Target) : nullptr)
    {
        switch (Npcs->GetInfection(Target))
        {
        case EReflectionsNpcInfection::Infected: return EReflectionsVillainInfection::Infected;
        case EReflectionsNpcInfection::VillainHost: return EReflectionsVillainInfection::Host;
        case EReflectionsNpcInfection::BurnedOut: return EReflectionsVillainInfection::BurnedOut;
        default: break;
        }
    }
    return EReflectionsVillainInfection::None;
}

void UReflectionsVillainPossessionComponent::BeginPlay()
{
    Super::BeginPlay();
}

void UReflectionsVillainPossessionComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    const EReflectionsVillainInfection Old = State;
    // Only a body that really leaves the game frees its slot; map travel and PIE shutdown report nothing.
    const bool bLeavesGame = Reason == EEndPlayReason::Destroyed || Reason == EEndPlayReason::RemovedFromWorld;
    if (bLeavesGame && (Old == EReflectionsVillainInfection::Host || Old == EReflectionsVillainInfection::Infected))
    {
        State = EReflectionsVillainInfection::None;
        if (UReflectionsVillainSubsystem* Villain = UReflectionsVillainSubsystem::Get(GetWorld()))
        {
            Villain->NotifyStateChanged(this, Old, State);
        }
    }
    if (UReflectionsTarnishCasterComponent* Caster = BoundCaster.Get())
    {
        Caster->OnTarnishWindup.RemoveDynamic(this, &UReflectionsVillainPossessionComponent::HandleTarnishWindup);
        Caster->OnTarnishReleased.RemoveDynamic(this, &UReflectionsVillainPossessionComponent::HandleTarnishReleased);
    }
    ClearLook(Reason != EEndPlayReason::Destroyed && Reason != EEndPlayReason::EndPlayInEditor && Reason != EEndPlayReason::Quit);
    Super::EndPlay(Reason);
}

void UReflectionsVillainPossessionComponent::SetState(EReflectionsVillainInfection NewState, AActor* Source)
{
    const EReflectionsVillainInfection Old = State;
    State = NewState;
    Age = 0.0f;
    if (NewState == EReflectionsVillainInfection::Host)
    {
        Lifetime = ReflectionsVillainTuning::HostLifetime() * FMath::FRandRange(0.85f, 1.15f);
        bTaunted = false;
        UReflectionsVillainSubsystem* Director = UReflectionsVillainSubsystem::Get(GetWorld());
        NextSpread = (Director ? Director->InfectIntervalNow() : ReflectionsVillainTuning::InfectInterval()) * 0.45f;
    }
    if (NewState == EReflectionsVillainInfection::Infected)
    {
        bRiftChecked = false;
    }
    ApplyLook();
    // The NPC system owns how a body behaves (its archetype) and reports it to the infection meter.
    if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this))
    {
        static const EReflectionsNpcInfection Map[] = {EReflectionsNpcInfection::None, EReflectionsNpcInfection::Infected,
            EReflectionsNpcInfection::VillainHost, EReflectionsNpcInfection::BurnedOut};
        Npcs->SetInfection(GetOwner(), Map[static_cast<uint8>(NewState)], Source);
    }
    if (Old != NewState)
    {
        if (UReflectionsVillainSubsystem* Villain = UReflectionsVillainSubsystem::Get(GetWorld()))
        {
            Villain->NotifyStateChanged(this, Old, NewState);
        }
    }
}

void UReflectionsVillainPossessionComponent::Cleanse()
{
    if (State != EReflectionsVillainInfection::Infected && State != EReflectionsVillainInfection::Host)
    {
        return;
    }
    if (AActor* Owner = GetOwner())
    {
        ReflectionsVillainFx::Impact(GetWorld(), BodyCenter(Owner), ReflectionsVillainColors::Lilac, ReflectionsVillainColors::FinalWhite,
            0.8f, 1.2f);
    }
    SetState(EReflectionsVillainInfection::None);
}

void UReflectionsVillainPossessionComponent::BurnOut(bool bKill)
{
    AActor* Owner = GetOwner();
    if (!Owner || State == EReflectionsVillainInfection::BurnedOut)
    {
        return;
    }
    const FVector Center = BodyCenter(Owner);
    ReflectionsVillainFx::Impact(GetWorld(), Center, ReflectionsVillainColors::Violet, ReflectionsVillainColors::Lilac, 1.3f, 2.5f);
    SetState(EReflectionsVillainInfection::BurnedOut);
    if (bKill)
    {
        ReflectionsVillainFx::Damage(Owner, 100000.0f, Owner, Center + FVector(0.0f, 0.0f, 50.0f), 0.0f, nullptr);
    }
}

void UReflectionsVillainPossessionComponent::ShortenHost(float SecondsLeft)
{
    if (State == EReflectionsVillainInfection::Host)
    {
        Lifetime = FMath::Min(Lifetime, Age + FMath::Max(0.1f, SecondsLeft));
    }
}

void UReflectionsVillainPossessionComponent::HandleOwnerDied()
{
    if (bDead || (State != EReflectionsVillainInfection::Infected && State != EReflectionsVillainInfection::Host))
    {
        return;
    }
    bDead = true;
    const EReflectionsVillainInfection Old = State;
    State = EReflectionsVillainInfection::None;
    if (AActor* Owner = GetOwner())
    {
        // The tarnish leaves the corpse as a last puff of black smoke.
        ReflectionsVillainFx::Impact(GetWorld(), BodyCenter(Owner), ReflectionsVillainColors::Violet, ReflectionsVillainColors::Lilac, 0.8f, 1.6f);
    }
    ClearLook(true);
    if (UReflectionsVillainSubsystem* Villain = UReflectionsVillainSubsystem::Get(GetWorld()))
    {
        Villain->NotifyStateChanged(this, Old, State);
    }
}

void UReflectionsVillainPossessionComponent::SetEyeGlow(float Glow)
{
    for (UMaterialInstanceDynamic* Material : EyeMaterials)
    {
        if (Material)
        {
            Material->SetScalarParameterValue(TEXT("Glow"), Glow);
        }
    }
}

void UReflectionsVillainPossessionComponent::AddBurningEyes(float Brightness)
{
    if (Eyes.Num() > 0)
    {
        SetEyeGlow(Brightness);
        return;
    }
    AActor* Owner = GetOwner();
    UStaticMesh* EyeMesh = ReflectionsVillainAssets::EyeMesh();
    if (!Owner || !EyeMesh)
    {
        return;
    }
    // The MetaHuman face carries the eye bones; mannequins and test hosts fall back to the head-bone beads.
    USkeletalMeshComponent* Face = nullptr;
    TArray<USkeletalMeshComponent*> Skeletals;
    Owner->GetComponents<USkeletalMeshComponent>(Skeletals);
    for (USkeletalMeshComponent* Mesh : Skeletals)
    {
        if (Mesh && Mesh->IsVisible() && Mesh->GetSkinnedAsset() && Mesh->GetBoneIndex(EyeBones[0]) != INDEX_NONE
            && Mesh->GetBoneIndex(EyeBones[1]) != INDEX_NONE)
        {
            Face = Mesh;
            break;
        }
    }
    if (!Face)
    {
        AddEyes(Brightness);
        return;
    }
    UMaterialInterface* EyeMaterial = ReflectionsVillainAssets::EyeMaterial();
    const FVector Forward = Owner->GetActorForwardVector();
    for (int32 Side = 0; Side < 2; ++Side)
    {
        UStaticMeshComponent* Eye = NewObject<UStaticMeshComponent>(Owner, Side ? TEXT("VillainHostGlintR") : TEXT("VillainHostGlintL"));
        Eye->SetStaticMesh(EyeMesh);
        Eye->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Eye->SetGenerateOverlapEvents(false);
        Eye->SetCanEverAffectNavigation(false);
        Eye->SetCastShadow(false);
        Eye->RegisterComponent();
        Eye->SetWorldScale3D(FVector(0.011f));
        Eye->SetWorldLocationAndRotation(Face->GetSocketLocation(EyeBones[Side]) + Forward * 1.4f, Forward.Rotation());
        Eye->AttachToComponent(Face, FAttachmentTransformRules::KeepWorldTransform, EyeBones[Side]);
        if (EyeMaterial)
        {
            UMaterialInstanceDynamic* Dynamic = UMaterialInstanceDynamic::Create(EyeMaterial, this);
            Dynamic->SetScalarParameterValue(TEXT("Glow"), Brightness);
            Eye->SetMaterial(0, Dynamic);
            EyeMaterials.Add(Dynamic);
        }
        Eyes.Add(Eye);
    }
}

void UReflectionsVillainPossessionComponent::EnsureLight()
{
    AActor* Owner = GetOwner();
    if (Light || !Owner)
    {
        return;
    }
    Light = NewObject<UPointLightComponent>(Owner, TEXT("VillainHostLight"));
    Light->SetupAttachment(Owner->GetRootComponent());
    Light->SetRelativeLocation(FVector(30.0f, 0.0f, 40.0f));
    Light->SetLightColor(ReflectionsVillainColors::Violet);
    Light->SetAttenuationRadius(420.0f);
    Light->SetCastShadows(false);
    Light->SetIntensity(0.0f);
    Light->RegisterComponent();
}

void UReflectionsVillainPossessionComponent::BindCaster()
{
    AActor* Owner = GetOwner();
    UReflectionsTarnishCasterComponent* Caster = Owner ? Owner->FindComponentByClass<UReflectionsTarnishCasterComponent>() : nullptr;
    if (!Caster)
    {
        return;
    }
    Caster->OnTarnishWindup.AddUniqueDynamic(this, &UReflectionsVillainPossessionComponent::HandleTarnishWindup);
    Caster->OnTarnishReleased.AddUniqueDynamic(this, &UReflectionsVillainPossessionComponent::HandleTarnishReleased);
    BoundCaster = Caster;
}

void UReflectionsVillainPossessionComponent::HandleTarnishWindup(EReflectionsTarnishSpell Spell, float Seconds)
{
    // The body gathers with the hand: aura, eyes and a violet glow climb over the whole wind-up.
    WindupStart = Clock;
    WindupLength = FMath::Max(0.1f, Seconds);
}

void UReflectionsVillainPossessionComponent::HandleTarnishReleased(EReflectionsTarnishSpell Spell, float Seconds)
{
    WindupStart = -1.0f;
    CastFlash = 1.0f;
}

void UReflectionsVillainPossessionComponent::TickSorcerer(float DeltaTime)
{
    AActor* Owner = GetOwner();
    if (!Owner)
    {
        return;
    }
    if (!BoundCaster.IsValid() && Clock >= NextCasterCheck)
    {
        NextCasterCheck = Clock + 0.5f;
        BindCaster();
    }
    float Charge = 0.0f;
    if (WindupStart >= 0.0f)
    {
        const float Into = Clock - WindupStart;
        if (Into > WindupLength + 0.5f)
        {
            WindupStart = -1.0f;   // cancelled (stagger, cure): CancelCast broadcasts nothing
        }
        else
        {
            Charge = FMath::Clamp(Into / WindupLength, 0.0f, 1.0f);
        }
    }
    CastFlash = FMath::Max(0.0f, CastFlash - DeltaTime / 0.4f);
    Pulse = FMath::Max(Charge * Charge, CastFlash);
    // MetaHumans are carried by their hidden driver, so measure the motion instead of reading a movement component.
    const FVector Location = Owner->GetActorLocation();
    if (bHasLastLocation && DeltaTime > KINDA_SMALL_NUMBER)
    {
        Speed = FMath::FInterpTo(Speed, FVector::Dist2D(Location, LastLocation) / DeltaTime, DeltaTime, 4.0f);
    }
    LastLocation = Location;
    bHasLastLocation = true;
    Run = FMath::Clamp(Speed / 350.0f, 0.0f, 1.0f);
    if (Pulse > 0.01f)
    {
        EnsureLight();
    }
}

void UReflectionsVillainPossessionComponent::SetOverlay(UMaterialInterface* Material, float Intensity)
{
    if (!Material)
    {
        return;
    }
    if (!Overlay || Overlay->Parent != Material)
    {
        Overlay = UMaterialInstanceDynamic::Create(Material, this);
    }
    Overlay->SetScalarParameterValue(TEXT("Intensity"), Intensity);
    for (UMeshComponent* Mesh : Meshes)
    {
        if (IsValid(Mesh))
        {
            Mesh->SetOverlayMaterial(Overlay);
        }
    }
}

void UReflectionsVillainPossessionComponent::AddEyes(float Brightness)
{
    if (Eyes.Num() > 0)
    {
        for (UMaterialInstanceDynamic* Material : EyeMaterials)
        {
            if (Material)
            {
                Material->SetScalarParameterValue(TEXT("Glow"), Brightness);
            }
        }
        return;
    }
    AActor* Owner = GetOwner();
    USkeletalMeshComponent* Head = Owner ? FindHeadMesh(Owner) : nullptr;
    UStaticMesh* EyeMesh = ReflectionsVillainAssets::EyeMesh();
    UMaterialInterface* EyeMaterial = ReflectionsVillainAssets::EyeMaterial();
    if (!Head || !EyeMesh)
    {
        return;
    }
    const FVector HeadLocation = Head->GetSocketLocation(HeadBone);
    const FVector Forward = Owner->GetActorForwardVector();
    const FVector Right = Owner->GetActorRightVector();
    for (int32 Side = 0; Side < 2; ++Side)
    {
        UStaticMeshComponent* Eye = NewObject<UStaticMeshComponent>(Owner, Side ? TEXT("VillainHostEyeR") : TEXT("VillainHostEyeL"));
        Eye->SetStaticMesh(EyeMesh);
        Eye->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Eye->SetGenerateOverlapEvents(false);
        Eye->SetCanEverAffectNavigation(false);
        Eye->SetCastShadow(false);
        Eye->RegisterComponent();
        Eye->SetWorldScale3D(FVector(0.028f, 0.02f, 0.014f));
        Eye->SetWorldLocationAndRotation(HeadLocation + Forward * 10.0f + FVector(0.0f, 0.0f, 7.0f) + Right * (Side ? 3.3f : -3.3f),
            Forward.Rotation());
        Eye->AttachToComponent(Head, FAttachmentTransformRules::KeepWorldTransform, HeadBone);
        if (EyeMaterial)
        {
            UMaterialInstanceDynamic* Dynamic = UMaterialInstanceDynamic::Create(EyeMaterial, this);
            Dynamic->SetScalarParameterValue(TEXT("Glow"), Brightness);
            Eye->SetMaterial(0, Dynamic);
            EyeMaterials.Add(Dynamic);
        }
        Eyes.Add(Eye);
    }
}

void UReflectionsVillainPossessionComponent::SetBlackEyes(bool bBlack)
{
    AActor* Owner = GetOwner();
    if (!Owner || bBlack == bBlackEyes)
    {
        return;
    }
    bBlackEyes = bBlack;
    if (!bBlack)
    {
        for (int32 Index = 0; Index < EyeMeshes.Num(); ++Index)
        {
            if (IsValid(EyeMeshes[Index]) && EyeOriginals.IsValidIndex(Index))
            {
                EyeMeshes[Index]->SetMaterial(EyeSlots[Index], EyeOriginals[Index]);
            }
        }
        EyeMeshes.Reset();
        EyeOriginals.Reset();
        EyeSlots.Reset();
        return;
    }
    // MetaHuman faces: baked eye materials (Iris/Sclera Color Multiply) and the simplified far-LOD eye (brightness).
    TArray<UMeshComponent*> Found;
    Owner->GetComponents<UMeshComponent>(Found);
    for (UMeshComponent* Mesh : Found)
    {
        if (!Mesh || Mesh->GetName().StartsWith(TEXT("VillainHost")))
        {
            continue;
        }
        for (int32 Slot = 0; Slot < Mesh->GetNumMaterials(); ++Slot)
        {
            UMaterialInterface* Material = Mesh->GetMaterial(Slot);
            const FString Name = Material ? Material->GetName() : FString();
            const bool bEye = (Name.Contains(TEXT("EyeL")) || Name.Contains(TEXT("EyeR")) || Name.Contains(TEXT("MetaHumanEye"))
                || Name.Contains(TEXT("EyeRefractive")) || Name.Contains(TEXT("eyeball")))
                && !Name.Contains(TEXT("lash")) && !Name.Contains(TEXT("Occlusion")) && !Name.Contains(TEXT("Lacrimal")) && !Name.Contains(TEXT("brow"));
            if (!bEye)
            {
                continue;
            }
            UMaterialInstanceDynamic* Black = UMaterialInstanceDynamic::Create(Material, this);
            Black->SetVectorParameterValue(TEXT("Iris Color Multiply"), FLinearColor::Black);
            Black->SetVectorParameterValue(TEXT("Sclera Color Multiply"), FLinearColor(0.01f, 0.01f, 0.012f));
            Black->SetScalarParameterValue(TEXT("IrisBrightness"), 0.0f);
            Black->SetScalarParameterValue(TEXT("IrisBrightnessBoost"), 0.0f);
            Black->SetScalarParameterValue(TEXT("ScleraBrightness"), 0.0f);
            Mesh->SetMaterial(Slot, Black);
            EyeMeshes.Add(Mesh);
            EyeOriginals.Add(Material);
            EyeSlots.Add(Slot);
        }
    }
    if (EyeMeshes.Num() == 0)
    {
        // No eye materials (mannequins): black beads under the brow.
        AddEyes(0.0f);
    }
}

void UReflectionsVillainPossessionComponent::ApplyLook()
{
    AActor* Owner = GetOwner();
    if (!Owner)
    {
        return;
    }
    if (!bSavedOverlays)
    {
        bSavedOverlays = true;
        TArray<UMeshComponent*> Found;
        Owner->GetComponents<UMeshComponent>(Found);
        for (UMeshComponent* Mesh : Found)
        {
            if (Mesh && Mesh->IsVisible() && !Mesh->GetName().StartsWith(TEXT("VillainHost")))
            {
                Meshes.Add(Mesh);
                SavedOverlays.Add(Mesh->GetOverlayMaterial());
            }
        }
    }

    switch (State)
    {
    case EReflectionsVillainInfection::None:
        ClearLook(true);
        break;

    case EReflectionsVillainInfection::Infected:
        if (ReflectionsVillainTuning::VeinOverlay())
        {
            SetOverlay(ReflectionsVillainAssets::InfectedOverlay(), 0.6f);
        }
        if (!Smoke)
        {
            Smoke = ReflectionsVillainFx::Shroud(GetWorld(), Owner->GetRootComponent(), NAME_None, FVector(0.0f, 0.0f, -70.0f), 0.7f, 0.9f);
        }
        ReflectionsVillainFx::SetShroudAmount(Smoke, 0.9f);
        SetBlackEyes(true);
        AddBurningEyes(InfectedEyeGlow);
        EyePhase = FMath::FRandRange(0.0f, 6.0f);
        if (Light)
        {
            Light->SetIntensity(0.0f);
        }
        break;

    case EReflectionsVillainInfection::Host:
        if (ReflectionsVillainTuning::VeinOverlay())
        {
            SetOverlay(ReflectionsVillainAssets::InfectedOverlay(), 1.0f);
        }
        if (!Smoke)
        {
            Smoke = ReflectionsVillainFx::Shroud(GetWorld(), Owner->GetRootComponent(), NAME_None, FVector(0.0f, 0.0f, -70.0f), 0.8f, 1.4f);
        }
        ReflectionsVillainFx::SetShroudAmount(Smoke, 1.4f);
        SetBlackEyes(true);
        AddBurningEyes(HostEyeGlow);
        EnsureLight();
        if (Light)
        {
            Light->SetIntensity(2600.0f);
        }
        break;

    case EReflectionsVillainInfection::BurnedOut:
        ClearLook(false);
        SetOverlay(ReflectionsVillainAssets::BurnedOverlay(), 1.0f);
        break;
    }
}

void UReflectionsVillainPossessionComponent::ClearLook(bool bRestoreOverlays)
{
    SetBlackEyes(false);
    for (UStaticMeshComponent* Eye : Eyes)
    {
        if (IsValid(Eye))
        {
            Eye->DestroyComponent();
        }
    }
    Eyes.Reset();
    EyeMaterials.Reset();
    if (Smoke)
    {
        Smoke->Deactivate();
        Smoke->SetAutoDestroy(true);
        Smoke = nullptr;
    }
    if (Light)
    {
        Light->DestroyComponent();
        Light = nullptr;
    }
    if (bRestoreOverlays)
    {
        for (int32 Index = 0; Index < Meshes.Num(); ++Index)
        {
            if (IsValid(Meshes[Index]))
            {
                Meshes[Index]->SetOverlayMaterial(SavedOverlays.IsValidIndex(Index) ? SavedOverlays[Index].Get() : nullptr);
            }
        }
    }
}

void UReflectionsVillainPossessionComponent::TryRift()
{
    bRiftChecked = true;
    AActor* Owner = GetOwner();
    UReflectionsWorldJumpWorldSubsystem* Jump = UReflectionsWorldJumpWorldSubsystem::Get(this);
    if (!Owner || !Jump || !Jump->IsWorldJumpActive() || FMath::FRand() > ReflectionsVillainTuning::RiftChance())
    {
        return;
    }
    const FVector From = Owner->GetActorLocation();
    const EReflectionsWorld Here = Jump->GetWorldAtLocation(From);
    TArray<EReflectionsWorld> Choices;
    for (EReflectionsWorld World : {EReflectionsWorld::Gray, EReflectionsWorld::Red, EReflectionsWorld::White})
    {
        if (World != Here)
        {
            Choices.Add(World);
        }
    }
    const EReflectionsWorld To = Choices[FMath::RandRange(0, Choices.Num() - 1)];
    FVector Destination;
    if (!Jump->TranslateBetweenWorlds(From, Here, To, Destination))
    {
        return;
    }
    // Land on the ground of the other side, and not inside a wall.
    const float HalfHeight = Owner->GetSimpleCollisionHalfHeight();
    const FVector Ground = ReflectionsVillainFx::Ground(GetWorld(), Destination, Owner, 400.0f, 2000.0f);
    Destination = Ground + FVector(0.0f, 0.0f, HalfHeight + 4.0f);
    ReflectionsVillainFx::Impact(GetWorld(), BodyCenter(Owner), ReflectionsVillainColors::Violet, ReflectionsVillainColors::Lilac, 1.4f, 3.0f);
    ReflectionsVillainFx::Sound(GetWorld(), ReflectionsVillainAssets::HopSound(), From);
    if (Owner->TeleportTo(Destination, Owner->GetActorRotation(), false, false))
    {
        ReflectionsVillainFx::Impact(GetWorld(), Destination, ReflectionsVillainColors::Violet, ReflectionsVillainColors::Lilac, 1.4f, 3.0f);
        if (UReflectionsVillainSubsystem* Villain = UReflectionsVillainSubsystem::Get(GetWorld()))
        {
            Villain->NotifyRift(Owner, Here, To);
        }
    }
}

void UReflectionsVillainPossessionComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
    if (bDead)
    {
        return;
    }
    Age += DeltaTime;
    Clock += DeltaTime;
    if (State == EReflectionsVillainInfection::Infected || State == EReflectionsVillainInfection::Host)
    {
        TickSorcerer(DeltaTime);
    }
    UReflectionsVillainSubsystem* Villain = UReflectionsVillainSubsystem::Get(GetWorld());

    switch (State)
    {
    case EReflectionsVillainInfection::Host:
    {
        // The last seconds before a hop: the body visibly starts to burn (eyes flare, smoke thickens).
        const float Left = Lifetime - Age;
        const float Burn = FMath::Clamp(1.0f - Left / 4.0f, 0.0f, 1.0f);
        const float Flicker = 1.0f + Burn * (0.8f + 0.8f * FMath::Sin(Clock * 31.0f));
        SetEyeGlow((HostEyeGlow + 6.0f * Burn) * Flicker * (1.0f + 3.0f * Pulse));
        if (Overlay)
        {
            Overlay->SetScalarParameterValue(TEXT("Intensity"), 1.0f + Burn);
        }
        ReflectionsVillainFx::SetShroudAmount(Smoke, 1.4f + 1.5f * Burn + 0.7f * Run + 1.2f * Pulse);
        if (Light)
        {
            Light->SetIntensity(2600.0f * Flicker + 3200.0f * Pulse);
        }
        if (Villain && !Villain->IsFinale() && Age >= NextSpread)
        {
            NextSpread += Villain->InfectIntervalNow() * FMath::FRandRange(0.8f, 1.2f);
            Villain->SpreadFrom(GetOwner());
        }
        if (!bTaunted && Age > 6.0f && Lifetime - Age > 4.0f)
        {
            bTaunted = true;
            ReflectionsVillainFx::Voice(GetWorld(), ReflectionsVillainAssets::VoTaunt(), GetOwner());
        }
        if (Age >= Lifetime && Villain)
        {
            Villain->HostExpired(this);
        }
        break;
    }
    case EReflectionsVillainInfection::Infected:
        // A dark sorcerer at range: eyes that smoulder, wisps that stream behind a running body, and a black-violet
        // surge over the whole body while a Tarnish spell gathers in the hand (spell-combat's wind-up), then a flash.
        SetEyeGlow(InfectedEyeGlow * (0.85f + 0.15f * FMath::Sin(Clock * 6.3f + EyePhase)) * (1.0f + 3.0f * Pulse));
        ReflectionsVillainFx::SetShroudAmount(Smoke, 0.9f + 0.7f * Run + 1.6f * Pulse);
        if (Light)
        {
            Light->SetIntensity(3200.0f * Pulse);
        }
        if (!bRiftChecked && Age >= ReflectionsVillainTuning::RiftDelay() && (!Villain || !Villain->IsFinale()))
        {
            TryRift();
        }
        break;
    default:
        break;
    }
}

// ============================================================================================ wisp

AReflectionsVillainWisp::AReflectionsVillainWisp()
{
    PrimaryActorTick.bCanEverTick = true;
    Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    RootComponent = Root;
    SetActorEnableCollision(false);
}

void AReflectionsVillainWisp::Launch(AActor* InTarget, EReflectionsVillainInfection InState, bool bInHop)
{
    Target = InTarget;
    State = InState;
    bHop = bInHop;
    Start = GetActorLocation();
    const float Distance = InTarget ? FVector::Dist(Start, TargetPoint()) : 0.0f;
    Duration = FMath::Clamp(Distance / (bHop ? 1000.0f : 850.0f), 0.7f, 3.5f);
    ArcHeight = FMath::Clamp(Distance * 0.22f, 80.0f, 650.0f);
    UWorld* World = GetWorld();
    Trail = ReflectionsVillainFx::Projectile(World, Root, FVector::ZeroVector, ReflectionsVillainColors::Violet, ReflectionsVillainColors::Lilac,
        bHop ? 1.4f : 0.8f);
    Smoke = ReflectionsVillainFx::Shroud(World, Root, NAME_None, FVector::ZeroVector, bHop ? 0.45f : 0.3f, 0.9f);
    Light = NewObject<UPointLightComponent>(this, TEXT("WispLight"));
    Light->SetupAttachment(Root);
    Light->SetLightColor(ReflectionsVillainColors::Violet);
    Light->SetIntensity(bHop ? 5000.0f : 2500.0f);
    Light->SetAttenuationRadius(bHop ? 600.0f : 380.0f);
    Light->SetCastShadows(false);
    Light->RegisterComponent();
    ReflectionsVillainFx::Sound(World, bHop ? ReflectionsVillainAssets::HopSound() : ReflectionsVillainAssets::VoiceSound(), Start,
        bHop ? 1.0f : 0.6f);
}

FVector AReflectionsVillainWisp::TargetPoint() const
{
    const AActor* Actor = Target.Get();
    return Actor ? BodyCenter(Actor) + FVector(0.0f, 0.0f, 25.0f) : GetActorLocation();
}

void AReflectionsVillainWisp::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (bArrived)
    {
        return;
    }
    UReflectionsVillainSubsystem* Villain = UReflectionsVillainSubsystem::Get(GetWorld());
    AActor* Actor = Target.Get();
    if (!IsValid(Actor) || !ReflectionsVillainFx::IsAlive(Actor))
    {
        bArrived = true;
        ReflectionsVillainFx::Impact(GetWorld(), GetActorLocation(), ReflectionsVillainColors::Violet, ReflectionsVillainColors::Lilac, 0.6f);
        if (Villain)
        {
            Villain->WispFinished(this, false);
        }
        Destroy();
        return;
    }
    Clock += DeltaSeconds;
    const float T = FMath::Clamp(Clock / Duration, 0.0f, 1.0f);
    const float Eased = T * T * (3.0f - 2.0f * T);
    const FVector Point = FMath::Lerp(Start, TargetPoint(), Eased) + FVector(0.0f, 0.0f, FMath::Sin(T * PI) * ArcHeight);
    SetActorLocation(Point);
    if (T < 1.0f)
    {
        return;
    }
    bArrived = true;
    const bool bTaken = UReflectionsVillainPossessionComponent::Apply(Actor, State) != nullptr;
    ReflectionsVillainFx::Impact(GetWorld(), Point, ReflectionsVillainColors::Violet, ReflectionsVillainColors::Lilac, bHop ? 1.2f : 0.7f, 1.5f);
    ReflectionsVillainFx::Sound(GetWorld(), ReflectionsVillainAssets::PossessSound(), Point, bHop ? 1.0f : 0.7f);
    if (Villain)
    {
        Villain->WispFinished(this, bTaken);
    }
    // Let the trail and smoke finish instead of popping out.
    if (Trail)
    {
        Trail->Deactivate();
    }
    if (Smoke)
    {
        Smoke->Deactivate();
    }
    if (Light)
    {
        Light->SetIntensity(0.0f);
    }
    SetLifeSpan(1.5f);
}

void AReflectionsVillainWisp::EndPlay(const EEndPlayReason::Type Reason)
{
    if (!bArrived)
    {
        if (UReflectionsVillainSubsystem* Villain = UReflectionsVillainSubsystem::Get(GetWorld()))
        {
            Villain->WispFinished(this, false);
        }
    }
    Super::EndPlay(Reason);
}

// ============================================================================================ test host

AReflectionsVillainTestHost::AReflectionsVillainTestHost()
{
    PrimaryActorTick.bCanEverTick = true;
    AutoPossessAI = EAutoPossessAI::PlacedInWorldOrSpawned;
    AIControllerClass = AAIController::StaticClass();
    bUseControllerRotationYaw = false;
    GetCharacterMovement()->bOrientRotationToMovement = true;
    GetCharacterMovement()->RotationRate = FRotator(0.0f, 240.0f, 0.0f);
    GetCharacterMovement()->MaxWalkSpeed = 150.0f;
    GetMesh()->SetRelativeLocationAndRotation(FVector(0.0f, 0.0f, -90.0f), FRotator(0.0f, -90.0f, 0.0f));
    Health = CreateDefaultSubobject<UReflectionsHealthComponent>(TEXT("Health"));
    Health->MaxHealth = 60.0f;
    Tags.Add(TEXT("VillainTestHost"));
}

void AReflectionsVillainTestHost::BeginPlay()
{
    Super::BeginPlay();
    if (USkeletalMesh* HostMesh = ReflectionsVillainAssets::TestHostMesh())
    {
        GetMesh()->SetSkeletalMesh(HostMesh);
    }
    if (UClass* AnimClass = ReflectionsVillainAssets::TestHostAnimClass())
    {
        GetMesh()->SetAnimInstanceClass(AnimClass);
    }
    Home = GetActorLocation();
    Heading = FRotator(0.0f, FMath::FRandRange(0.0f, 360.0f), 0.0f).Vector();
    Health->OnDeath.AddDynamic(this, &AReflectionsVillainTestHost::HandleDeath);
}

void AReflectionsVillainTestHost::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (bDead)
    {
        return;
    }
    NextTurn -= DeltaSeconds;
    const FVector ToHome = Home - GetActorLocation();
    if (ToHome.Size2D() > 650.0f)
    {
        Heading = ToHome.GetSafeNormal2D();
        NextTurn = 2.0f;
    }
    else if (NextTurn <= 0.0f)
    {
        NextTurn = FMath::FRandRange(2.0f, 5.0f);
        Heading = FMath::FRand() < 0.25f ? FVector::ZeroVector : FRotator(0.0f, FMath::FRandRange(0.0f, 360.0f), 0.0f).Vector();
    }
    if (!Heading.IsNearlyZero())
    {
        AddMovementInput(Heading, 1.0f);
    }
}

void AReflectionsVillainTestHost::HandleDeath(AActor* Source)
{
    if (bDead)
    {
        return;
    }
    bDead = true;
    GetCharacterMovement()->DisableMovement();
    GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    USkeletalMeshComponent* Body = GetMesh();
    if (Body && Body->GetPhysicsAsset())
    {
        Body->SetCollisionProfileName(TEXT("Ragdoll"));
        Body->SetSimulatePhysics(true);
    }
    SetLifeSpan(25.0f);
}

#undef LOCTEXT_NAMESPACE
