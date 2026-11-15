#include "Villain/ReflectionsVillainLook.h"

#include "Villain/ReflectionsVillainConfig.h"
#include "Villain/ReflectionsVillainFx.h"

#include "Animation/AnimSequenceBase.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "NiagaraComponent.h"

namespace
{
    const FName HeadBone(TEXT("head"));
    const FName PelvisBone(TEXT("pelvis"));
    const FName ChestBone(TEXT("spine_05"));

    UMaterialInterface* FallbackBlack()
    {
        return LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"), nullptr,
            LOAD_NoWarn | LOAD_Quiet);
    }
}

UReflectionsVillainLookComponent::UReflectionsVillainLookComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.TickInterval = 0.0f;
}

void UReflectionsVillainLookComponent::BeginPlay()
{
    Super::BeginPlay();
    Build();
}

void UReflectionsVillainLookComponent::OnUnregister()
{
    if (ShroudFx)
    {
        ShroudFx->DestroyComponent();
        ShroudFx = nullptr;
    }
    Super::OnUnregister();
}

UStaticMeshComponent* UReflectionsVillainLookComponent::MakeStatic(FName Name, UStaticMesh* Mesh, UMaterialInterface* Material)
{
    if (!Mesh)
    {
        return nullptr;
    }
    UStaticMeshComponent* Part = NewObject<UStaticMeshComponent>(GetOwner(), Name);
    Part->SetupAttachment(this);
    Part->SetStaticMesh(Mesh);
    Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Part->SetGenerateOverlapEvents(false);
    Part->SetCanEverAffectNavigation(false);
    Part->bReceivesDecals = false;
    Part->RegisterComponent();
    if (Material)
    {
        UMaterialInstanceDynamic* Dynamic = UMaterialInstanceDynamic::Create(Material, this);
        for (int32 Index = 0; Index < FMath::Max(1, Part->GetNumMaterials()); ++Index)
        {
            Part->SetMaterial(Index, Dynamic);
        }
        Dynamics.Add(Dynamic);
    }
    return Part;
}

void UReflectionsVillainLookComponent::Build()
{
    if (bBuilt || !GetOwner())
    {
        return;
    }
    bBuilt = true;
    const float S = BodyScale;

    // ---- Body: the mannequin in black, rim-lit so the silhouette reads at any distance.
    Body = NewObject<USkeletalMeshComponent>(GetOwner(), TEXT("VillainBody"));
    Body->SetupAttachment(this);
    Body->SetSkeletalMesh(ReflectionsVillainAssets::BodyMesh());
    Body->SetRelativeRotation(FRotator(0.0f, -90.0f, 0.0f));
    Body->SetRelativeScale3D(FVector(S));
    Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Body->SetGenerateOverlapEvents(false);
    Body->SetCanEverAffectNavigation(false);
    Body->bReceivesDecals = false;
    Body->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    Body->SetAnimationMode(EAnimationMode::AnimationSingleNode);
    Body->RegisterComponent();
    {
        UMaterialInterface* Material = ReflectionsVillainAssets::BodyMaterial();
        const bool bFallback = !Material;
        if (bFallback)
        {
            Material = FallbackBlack();
        }
        if (Material)
        {
            UMaterialInstanceDynamic* Dynamic = UMaterialInstanceDynamic::Create(Material, this);
            if (bFallback)
            {
                Dynamic->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.005f, 0.004f, 0.008f));
            }
            for (int32 Index = 0; Index < Body->GetNumMaterials(); ++Index)
            {
                Body->SetMaterial(Index, Dynamic);
            }
            Dynamics.Add(Dynamic);
        }
    }
    PlayAnimation(ReflectionsVillainAssets::HoverAnim(), true, 0.6f);

    // ---- Shroud: a loose robe from the chest past the feet. Its material ripples the cloth (WPO).
    UMaterialInterface* ClothMaterial = ReflectionsVillainAssets::ShroudMaterial();
    if (UStaticMesh* Robe = ReflectionsVillainAssets::ShroudMesh())
    {
        ShroudMesh = MakeStatic(TEXT("VillainShroud"), Robe, ClothMaterial);
        ShroudMesh->SetRelativeScale3D(FVector(S));
    }
    else if (UStaticMesh* Cone = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cone.Cone"), nullptr, LOAD_NoWarn | LOAD_Quiet))
    {
        ShroudMesh = MakeStatic(TEXT("VillainShroud"), Cone, ClothMaterial ? ClothMaterial : ReflectionsVillainAssets::BodyMaterial());
        ShroudMesh->SetRelativeLocation(FVector(0.0f, 0.0f, 72.0f * S));
        ShroudMesh->SetRelativeScale3D(FVector(0.8f, 0.8f, 1.45f) * S);
    }
    if (UStaticMesh* HoodMesh = ReflectionsVillainAssets::HoodMesh())
    {
        Hood = MakeStatic(TEXT("VillainHood"), HoodMesh, ClothMaterial);
        if (Hood)
        {
            Hood->SetRelativeScale3D(FVector(S));
        }
    }

    // ---- A dim violet light so he lights the smoke around him.
    Light = NewObject<UPointLightComponent>(GetOwner(), TEXT("VillainLight"));
    Light->SetupAttachment(this);
    Light->SetRelativeLocation(FVector(40.0f, 0.0f, 150.0f * S));
    Light->SetLightColor(ReflectionsVillainColors::Violet);
    Light->SetIntensity(1800.0f);
    Light->SetAttenuationRadius(520.0f * S);
    Light->SetCastShadows(false);
    Light->RegisterComponent();

    ShroudFx = ReflectionsVillainFx::Shroud(GetWorld(), this, NAME_None, FVector(0.0f, 0.0f, 20.0f * S), S, ShroudAmount);
    if (bTrueForm)
    {
        BuildTrueForm();
    }
    ApplyGlow();
}

void UReflectionsVillainLookComponent::BuildTrueForm()
{
    const float S = BodyScale;
    // A slow halo of tarnished mirror shards: they catch the sky and the sun, so it reads in daylight and at range.
    if (UStaticMesh* ShardMesh = ReflectionsVillainAssets::ShardMesh())
    {
        Shards = NewObject<UInstancedStaticMeshComponent>(GetOwner(), TEXT("VillainShards"));
        Shards->SetupAttachment(this);
        Shards->SetStaticMesh(ShardMesh);
        Shards->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Shards->SetGenerateOverlapEvents(false);
        Shards->SetCanEverAffectNavigation(false);
        Shards->SetCastShadow(false);
        Shards->RegisterComponent();
        if (UMaterialInterface* Mirror = ReflectionsVillainAssets::MirrorMaterial())
        {
            UMaterialInstanceDynamic* Dynamic = UMaterialInstanceDynamic::Create(Mirror, this);
            Shards->SetMaterial(0, Dynamic);
            Dynamics.Add(Dynamic);
        }
        constexpr int32 Count = 16;
        for (int32 Index = 0; Index < Count; ++Index)
        {
            ShardOrbits.Add(FVector4f(Index * 2.0f * PI / Count + FMath::FRandRange(-0.2f, 0.2f), FMath::FRandRange(70.0f, 130.0f) * S,
                FMath::FRandRange(70.0f, 225.0f) * S, FMath::FRandRange(0.6f, 1.8f) * (FMath::RandBool() ? 1.0f : -1.0f)));
            Shards->AddInstance(FTransform::Identity);
        }
    }
    // The heart: a burning core in the chest. The bright point says where the Final Spell should land.
    Heart = MakeStatic(TEXT("VillainHeart"), ReflectionsVillainAssets::EyeMesh(), nullptr);
    if (Heart)
    {
        Heart->SetCastShadow(false);
        Heart->SetRelativeScale3D(FVector(0.24f, 0.24f, 0.29f) * S);
        if (UMaterialInterface* HeartMaterial = ReflectionsVillainAssets::HeartMaterial())
        {
            HeartGlow = UMaterialInstanceDynamic::Create(HeartMaterial, this);
            Heart->SetMaterial(0, HeartGlow);
        }
    }
    HeartLight = NewObject<UPointLightComponent>(GetOwner(), TEXT("VillainHeartLight"));
    HeartLight->SetupAttachment(this);
    HeartLight->SetLightColor(ReflectionsVillainColors::Lilac);
    HeartLight->SetIntensity(6000.0f);
    HeartLight->SetAttenuationRadius(380.0f * S);
    HeartLight->SetCastShadows(false);
    HeartLight->RegisterComponent();
}

void UReflectionsVillainLookComponent::TickTrueForm(float DeltaTime)
{
    if (Shards && ShardOrbits.Num() == Shards->GetInstanceCount())
    {
        TArray<FTransform> Transforms;
        Transforms.Reserve(ShardOrbits.Num());
        for (const FVector4f& Orbit : ShardOrbits)
        {
            const float Angle = Orbit.X + Clock * 0.35f;
            const FVector Position(FMath::Cos(Angle) * Orbit.Y, FMath::Sin(Angle) * Orbit.Y, Orbit.Z + FMath::Sin(Clock * 1.3f + Orbit.X * 3.0f) * 9.0f);
            // Each shard faces outward and turns slowly on its long axis, so its mirror face flashes now and then.
            const FRotator Facing(FMath::Sin(Clock * 0.7f + Orbit.X) * 25.0f, FMath::RadiansToDegrees(Angle) + Clock * 40.0f * Orbit.W,
                FMath::Cos(Clock * 0.9f + Orbit.X) * 20.0f);
            Transforms.Add(FTransform(Facing, Position, FVector(2.0f + 0.8f * FMath::Frac(Orbit.X * 7.13f))));
        }
        Shards->BatchUpdateInstancesTransforms(0, Transforms, false, true, true);
    }
    const float Pulse = 0.75f + 0.25f * FMath::Sin(Clock * 3.4f) + 0.15f * FMath::Sin(Clock * 11.0f);
    const FVector HeartWorld = GetHeartLocation();
    if (Heart)
    {
        Heart->SetWorldLocation(HeartWorld);
    }
    if (HeartGlow)
    {
        HeartGlow->SetScalarParameterValue(TEXT("Glow"), Glow * Pulse);
        HeartGlow->SetScalarParameterValue(TEXT("Flash"), FlashAmount);
    }
    if (HeartLight)
    {
        HeartLight->SetWorldLocation(HeartWorld + GetForwardVector() * 30.0f * BodyScale);
        HeartLight->SetIntensity((5000.0f + 14000.0f * FlashAmount) * Glow * Pulse);
    }
}

void UReflectionsVillainLookComponent::AttachToBones()
{
    bBonesAttached = true;
    if (!Body)
    {
        return;
    }
    // The robe and hood are modelled in his space (feet at the origin, facing +X). Placed there first, they are
    // then carried by the hips and head so they lean and turn with the attacks.
    const FTransform Space = GetComponentTransform();
    const float S = BodyScale;
    if (ShroudMesh && Body->GetBoneIndex(PelvisBone) != INDEX_NONE)
    {
        ShroudMesh->SetWorldTransform(ShroudMesh->GetRelativeTransform() * Space);
        ShroudMesh->AttachToComponent(Body, FAttachmentTransformRules::KeepWorldTransform, PelvisBone);
    }
    if (Body->GetBoneIndex(HeadBone) == INDEX_NONE)
    {
        return;
    }
    if (Hood)
    {
        Hood->SetWorldTransform(Hood->GetRelativeTransform() * Space);
        Hood->AttachToComponent(Body, FAttachmentTransformRules::KeepWorldTransform, HeadBone);
    }
    const FVector Head = Body->GetSocketLocation(HeadBone);
    const FVector Forward = GetForwardVector();
    const FVector Right = GetRightVector();
    const FVector Up = GetUpVector();
    for (int32 Side = 0; Side < 2; ++Side)
    {
        UStaticMeshComponent* Eye = MakeStatic(Side ? TEXT("VillainEyeR") : TEXT("VillainEyeL"), ReflectionsVillainAssets::EyeMesh(),
            ReflectionsVillainAssets::EyeMaterial());
        if (!Eye)
        {
            continue;
        }
        Eye->SetCastShadow(false);
        Eye->SetWorldScale3D(FVector(0.032f, 0.022f, 0.016f) * S * GetComponentScale().X);
        Eye->SetWorldLocation(Head + (Forward * 11.0f + Up * 4.0f + Right * (Side ? 3.6f : -3.6f)) * S * GetComponentScale().X);
        Eye->SetWorldRotation(Forward.Rotation());
        Eye->AttachToComponent(Body, FAttachmentTransformRules::KeepWorldTransform, HeadBone);
        Eyes.Add(Eye);
    }
    ApplyGlow();
}

void UReflectionsVillainLookComponent::PlayAnimation(UAnimSequenceBase* Animation, bool bLoop, float PlayRate)
{
    if (Body && Animation)
    {
        Body->PlayAnimation(Animation, bLoop);
        Body->SetPlayRate(PlayRate);
    }
}

void UReflectionsVillainLookComponent::SetGlow(float InGlow)
{
    Glow = FMath::Max(0.0f, InGlow);
    ApplyGlow();
}

void UReflectionsVillainLookComponent::Flash(float Strength)
{
    FlashAmount = FMath::Max(FlashAmount, Strength);
}

void UReflectionsVillainLookComponent::SetShroudAmount(float Amount)
{
    ShroudAmount = Amount;
    ReflectionsVillainFx::SetShroudAmount(ShroudFx, Amount);
}

void UReflectionsVillainLookComponent::SetLookVisible(bool bShow)
{
    SetVisibility(bShow, true);
    if (ShroudFx)
    {
        if (bShow)
        {
            ShroudFx->Activate(false);
        }
        else
        {
            ShroudFx->Deactivate();
        }
    }
}

void UReflectionsVillainLookComponent::ApplyGlow()
{
    const float Flicker = 0.85f + 0.15f * FMath::Sin(Clock * 7.3f) * FMath::Sin(Clock * 2.1f + 1.3f);
    for (UMaterialInstanceDynamic* Dynamic : Dynamics)
    {
        if (Dynamic)
        {
            Dynamic->SetScalarParameterValue(TEXT("Glow"), Glow * Flicker);
            Dynamic->SetScalarParameterValue(TEXT("Flash"), FlashAmount);
        }
    }
    if (Light)
    {
        Light->SetIntensity((1400.0f + 9000.0f * FlashAmount) * FMath::Max(0.2f, Glow) * Flicker);
        Light->SetLightColor(FMath::Lerp(ReflectionsVillainColors::Violet, ReflectionsVillainColors::FinalWhite, FMath::Clamp(FlashAmount, 0.0f, 1.0f)));
    }
}

void UReflectionsVillainLookComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
    Clock += DeltaTime;
    // Two frames in, the body has evaluated its animation: bones are where they will really be.
    if (bBuilt && !bBonesAttached && Clock > 0.05f)
    {
        AttachToBones();
    }
    if (bTrueForm)
    {
        TickTrueForm(DeltaTime);
    }
    FlashAmount = FMath::FInterpTo(FlashAmount, 0.0f, DeltaTime, 6.0f);
    ApplyGlow();
}

FVector UReflectionsVillainLookComponent::GetHandLocation(bool bRight) const
{
    const FName Bone = bRight ? FName(TEXT("hand_r")) : FName(TEXT("hand_l"));
    if (Body && Body->GetBoneIndex(Bone) != INDEX_NONE)
    {
        return Body->GetSocketLocation(Bone);
    }
    return GetComponentLocation() + GetUpVector() * 130.0f * BodyScale + GetRightVector() * (bRight ? 30.0f : -30.0f);
}

FVector UReflectionsVillainLookComponent::GetHeadLocation() const
{
    if (Body && Body->GetBoneIndex(HeadBone) != INDEX_NONE)
    {
        return Body->GetSocketLocation(HeadBone);
    }
    return GetComponentLocation() + GetUpVector() * 165.0f * BodyScale;
}

FVector UReflectionsVillainLookComponent::GetHeartLocation() const
{
    // In front of the breastbone, so it shows through the robe's open front.
    return GetChestLocation() + GetForwardVector() * 16.0f * BodyScale - GetUpVector() * 6.0f * BodyScale;
}

FVector UReflectionsVillainLookComponent::GetChestLocation() const
{
    if (Body && Body->GetBoneIndex(ChestBone) != INDEX_NONE)
    {
        return Body->GetSocketLocation(ChestBone);
    }
    return GetComponentLocation() + GetUpVector() * 130.0f * BodyScale;
}
