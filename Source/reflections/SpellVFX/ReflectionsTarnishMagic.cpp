#include "SpellVFX/ReflectionsTarnishMagic.h"
#include "SpellVFX/ReflectionsSpellVfxSubsystem.h"
#include "Hero/ReflectionsSpellCombat.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "Components/DecalComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "NiagaraComponent.h"

namespace
{
    // The gameplay spell tarnish magic reports in hit events and the HUD; its visuals and impact are its own.
    constexpr EHeroSpell TarnishGameplaySpell = EHeroSpell::ArcaneBolt;
    const FLinearColor TarnishLightColor(0.42f, 0.06f, 0.85f);

    FVector TarnishAimPoint(const AActor* Target)
    {
        if (const UReflectionsNpcReactionComponent* Npc = Target->FindComponentByClass<UReflectionsNpcReactionComponent>())
        {
            return Npc->GetAimPoint();
        }
        if (Target->IsA<APawn>())
        {
            return Target->GetActorLocation() + FVector(0.0f, 0.0f, 25.0f);
        }
        FVector Origin, Extent;
        Target->GetActorBounds(true, Origin, Extent);
        return Origin;
    }

    FVector TarnishFlat(const FVector& V) { return FVector(V.X, V.Y, 0.0f); }

    /** True when the mesh's hand socket can be read safely: it exists and the pose that drives it (the leader pose's,
     *  if it follows one) has bones evaluated. Some crowd bodies briefly have empty bone buffers. */
    bool HasPosedSocket(const USkeletalMeshComponent* Mesh, FName Socket)
    {
        if (!Mesh || !Mesh->IsRegistered() || !Mesh->DoesSocketExist(Socket)) return false;
        const USkinnedMeshComponent* Pose = Mesh->LeaderPoseComponent.IsValid() ? Mesh->LeaderPoseComponent.Get() : Mesh;
        return Pose && Pose->GetNumComponentSpaceTransforms() > 0;
    }
}

UReflectionsTarnishCasterComponent::UReflectionsTarnishCasterComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.bStartWithTickEnabled = false;
}

float UReflectionsTarnishCasterComponent::GetWindup(EReflectionsTarnishSpell Spell) const
{
    switch (Spell)
    {
    case EReflectionsTarnishSpell::Wisp: return WispWindup;
    case EReflectionsTarnishSpell::Burst: return BurstWindup;
    default: return BoltWindup;
    }
}

float UReflectionsTarnishCasterComponent::GetCastRange(EReflectionsTarnishSpell Spell) const
{
    switch (Spell)
    {
    case EReflectionsTarnishSpell::Wisp: return WispRange * 0.85f;
    case EReflectionsTarnishSpell::Burst: return BurstRadius * 0.85f;
    default: return BoltRange * 0.85f;
    }
}

void UReflectionsTarnishCasterComponent::SetCastBody(USkeletalMeshComponent* Body)
{
    CastBody = Body;
}

USceneComponent* UReflectionsTarnishCasterComponent::FindHand(FName& OutSocket) const
{
    OutSocket = NAME_None;
    AActor* Owner = GetOwner();
    if (!Owner) return nullptr;
    if (HasPosedSocket(CastBody, HandSocket))
    {
        OutSocket = HandSocket;
        return CastBody;
    }
    // The visible body first; a hidden locomotion mesh only if nothing visible has the socket.
    TArray<USkeletalMeshComponent*> Meshes;
    Owner->GetComponents(Meshes);
    USkeletalMeshComponent* Hidden = nullptr;
    for (USkeletalMeshComponent* Mesh : Meshes)
    {
        if (!HasPosedSocket(Mesh, HandSocket)) continue;
        if (Mesh->IsVisible() && !Mesh->bHiddenInGame)
        {
            OutSocket = HandSocket;
            return Mesh;
        }
        if (!Hidden) Hidden = Mesh;
    }
    if (Hidden)
    {
        OutSocket = HandSocket;
        return Hidden;
    }
    return Owner->GetRootComponent();
}

FVector UReflectionsTarnishCasterComponent::HandLocation() const
{
    FName Socket;
    USceneComponent* Hand = FindHand(Socket);
    if (Hand && !Socket.IsNone())
    {
        return Hand->GetSocketLocation(Socket);
    }
    const AActor* Owner = GetOwner();
    return Owner ? TarnishAimPoint(Owner) + FVector(0.0f, 0.0f, 20.0f) : FVector::ZeroVector;
}

TArray<AActor*> UReflectionsTarnishCasterComponent::OwnActors() const
{
    TArray<AActor*> Own;
    if (AActor* Owner = GetOwner())
    {
        Own.Add(Owner);
        if (const UReflectionsNpcReactionComponent* Npc = Owner->FindComponentByClass<UReflectionsNpcReactionComponent>())
        {
            if (ACharacter* Driver = Npc->GetMovementCharacter())
            {
                Own.AddUnique(Driver);
            }
        }
    }
    return Own;
}

bool UReflectionsTarnishCasterComponent::StartCast(EReflectionsTarnishSpell Spell, AActor* Target)
{
    UWorld* World = GetWorld();
    AActor* Owner = GetOwner();
    if (!World || !Owner || !IsValid(Target) || Phase != EPhase::Ready)
    {
        return false;
    }
    CurrentSpell = Spell;
    CastTarget = Target;
    Phase = EPhase::Windup;
    PhaseTime = 0.0f;
    WindupLength = FMath::Max(0.2f, GetWindup(Spell));

    FName Socket;
    USceneComponent* Hand = FindHand(Socket);
    if (UReflectionsSpellVfxSubsystem* Vfx = World->GetSubsystem<UReflectionsSpellVfxSubsystem>())
    {
        Telegraph = Vfx->SpawnTarnishTelegraph(Hand, Socket);
        if (Spell == EReflectionsTarnishSpell::Burst)
        {
            Warning = Vfx->SpawnTarnishWarning(Owner->GetActorLocation(), BurstRadius);
        }
    }
    if (Hand)
    {
        UPointLightComponent* Light = NewObject<UPointLightComponent>(Owner, NAME_None, RF_Transient);
        Light->SetMobility(EComponentMobility::Movable);
        Light->SetCastShadows(false);
        Light->SetLightColor(TarnishLightColor);
        Light->SetIntensity(300.0f);
        Light->SetAttenuationRadius(380.0f);
        Light->RegisterComponent();
        Light->AttachToComponent(Hand, FAttachmentTransformRules::SnapToTargetNotIncludingScale, Socket);
        TelegraphLight = Light;
    }
    SetComponentTickEnabled(true);
    OnTarnishWindup.Broadcast(Spell, WindupLength);
    return true;
}

void UReflectionsTarnishCasterComponent::CancelCast()
{
    if (Phase == EPhase::Ready) return;
    Finish();
}

AActor* UReflectionsTarnishCasterComponent::ReleaseNow(EReflectionsTarnishSpell Spell, AActor* Target)
{
    return Release(Spell, Target);
}

void UReflectionsTarnishCasterComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* TickFunction)
{
    Super::TickComponent(DeltaTime, TickType, TickFunction);
    AActor* Owner = GetOwner();
    if (Phase == EPhase::Ready || !Owner)
    {
        SetComponentTickEnabled(false);
        return;
    }
    // A caster that dies mid-cast never finishes the spell.
    if (const UReflectionsHealthComponent* Health = Owner->FindComponentByClass<UReflectionsHealthComponent>())
    {
        if (Health->Health <= 0.0f)
        {
            Finish();
            return;
        }
    }
    PhaseTime += DeltaTime;
    if (Phase == EPhase::Windup)
    {
        AActor* Target = CastTarget.Get();
        if (!IsValid(Target))
        {
            Finish();
            return;
        }
        const float Alpha = FMath::Clamp(PhaseTime / WindupLength, 0.0f, 1.0f);
        if (Telegraph)
        {
            Telegraph->SetVariableFloat(TEXT("User.Scale"), FMath::Lerp(0.25f, CurrentSpell == EReflectionsTarnishSpell::Wisp ? 1.0f : 0.7f, Alpha));
        }
        if (TelegraphLight)
        {
            // Swells and throbs faster as the release nears: the cue to move.
            const float Throb = 0.75f + 0.25f * FMath::Sin(PhaseTime * FMath::Lerp(9.0f, 30.0f, Alpha));
            TelegraphLight->SetIntensity(FMath::Lerp(300.0f, 7000.0f, Alpha * Alpha) * Throb);
        }
        if (Warning)
        {
            if (UMaterialInstanceDynamic* Material = Cast<UMaterialInstanceDynamic>(Warning->GetDecalMaterial()))
            {
                Material->SetScalarParameterValue(TEXT("Strength"), FMath::Lerp(0.15f, 1.0f, Alpha));
            }
        }
        if (PhaseTime >= WindupLength)
        {
            ClearTelegraph();
            Release(CurrentSpell, Target);
            OnTarnishReleased.Broadcast(CurrentSpell, 0.0f);
            Phase = EPhase::Recover;
            PhaseTime = 0.0f;
        }
        return;
    }
    if (PhaseTime >= RecoverTime)
    {
        Finish();
    }
}

AActor* UReflectionsTarnishCasterComponent::Release(EReflectionsTarnishSpell Spell, AActor* Target)
{
    UWorld* World = GetWorld();
    AActor* Owner = GetOwner();
    if (!World || !Owner || !IsValid(Target))
    {
        return nullptr;
    }
    UReflectionsSpellVfxSubsystem* Vfx = World->GetSubsystem<UReflectionsSpellVfxSubsystem>();
    const TArray<AActor*> Own = OwnActors();

    if (Spell == EReflectionsTarnishSpell::Burst)
    {
        const FVector Center = Owner->GetActorLocation();
        ReflectionsSpellCombat::ApplyArea(World, Owner, TarnishGameplaySpell, Center, BurstRadius, BurstDamage, BurstPush, Own);
        if (Vfx)
        {
            Vfx->SpawnTarnishImpact(Center, FVector::UpVector, Owner, BurstRadius / 85.0f, false);
        }
        return Owner;
    }

    const bool bWisp = Spell == EReflectionsTarnishSpell::Wisp;
    const float Speed = FMath::Max(100.0f, bWisp ? WispSpeed : BoltSpeed);
    const FVector Hand = HandLocation();
    FVector Aim = TarnishAimPoint(Target);
    if (!bWisp)
    {
        const float Flight = FVector::Dist(Aim, Hand) / Speed;
        Aim += TarnishFlat(Target->GetVelocity()) * Flight * AimLead;
        Aim += FMath::VRand() * FMath::FRandRange(0.0f, AimSpread);
    }
    FVector Direction = (Aim - Hand).GetSafeNormal();
    if (Direction.IsNearlyZero())
    {
        Direction = Owner->GetActorForwardVector();
    }
    const FVector Muzzle = Hand + Direction * 30.0f;
    const FTransform Launch(Direction.Rotation(), Muzzle);
    AReflectionsSpellProjectile* Projectile = World->SpawnActorDeferred<AReflectionsSpellProjectile>(
        AReflectionsSpellProjectile::StaticClass(), Launch, Owner, Cast<APawn>(Owner), ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
    if (!Projectile)
    {
        return nullptr;
    }
    Projectile->Initialize(TarnishGameplaySpell, bWisp ? WispDamage : BoltDamage, Speed, bWisp ? WispRange : BoltRange, nullptr, nullptr);
    Projectile->SetLook(bWisp ? EReflectionsSpellLook::TarnishWisp : EReflectionsSpellLook::TarnishBolt);
    Projectile->FinishSpawning(Launch);
    if (UPrimitiveComponent* Collision = Cast<UPrimitiveComponent>(Projectile->GetRootComponent()))
    {
        for (AActor* Mine : Own)
        {
            Collision->IgnoreActorWhenMoving(Mine, true);
        }
    }
    if (bWisp)
    {
        Projectile->SetHomingTarget(Target, WispHoming);
    }
    if (Vfx)
    {
        Vfx->SpawnTarnishImpact(Muzzle, Direction, Owner, 0.4f, true);
    }
    return Projectile;
}

void UReflectionsTarnishCasterComponent::ClearTelegraph()
{
    if (Telegraph)
    {
        Telegraph->DestroyComponent();
        Telegraph = nullptr;
    }
    if (TelegraphLight)
    {
        TelegraphLight->DestroyComponent();
        TelegraphLight = nullptr;
    }
    if (Warning)
    {
        Warning->DestroyComponent();
        Warning = nullptr;
    }
}

void UReflectionsTarnishCasterComponent::Finish()
{
    ClearTelegraph();
    Phase = EPhase::Ready;
    PhaseTime = 0.0f;
    CastTarget = nullptr;
    SetComponentTickEnabled(false);
}

void UReflectionsTarnishCasterComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    ClearTelegraph();
    Super::EndPlay(Reason);
}
