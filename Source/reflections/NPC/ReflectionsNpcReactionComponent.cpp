#include "NPC/ReflectionsNpcReactionComponent.h"
#include "NPC/ReflectionsReputationSubsystem.h"
#include "Hero/ReflectionsSpellCombat.h"
#include "Hero/ReflectionsSpellCatalog.h"
#include "Animation/AnimInstance.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/CapsuleComponent.h"
#include "Engine/SkeletalMesh.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "PhysicsEngine/BodyInstance.h"
#include "UObject/SoftObjectPath.h"

namespace
{
    USkeletalMeshComponent* FindNpcBody(AActor* Actor)
    {
        if (!Actor) return nullptr;
        TInlineComponentArray<USkeletalMeshComponent*> Meshes(Actor);
        for (USkeletalMeshComponent* Mesh : Meshes)
            if (Mesh && Mesh->GetFName() == TEXT("Body")) return Mesh;
        for (USkeletalMeshComponent* Mesh : Meshes)
            if (Mesh && Mesh->GetPhysicsAsset()) return Mesh;
        return nullptr;
    }
}

UReflectionsNpcReactionComponent::UReflectionsNpcReactionComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.TickGroup = TG_PrePhysics;
}

ACharacter* UReflectionsNpcReactionComponent::GetLocomotionDriver() const
{
    return LocomotionDriver.Get();
}
void UReflectionsNpcReactionComponent::BeginPlay()
{
    Super::BeginPlay();
    if (UReflectionsSpellEventSubsystem* Events = GetWorld()->GetSubsystem<UReflectionsSpellEventSubsystem>())
    {
        Events->OnSpellEvent.AddUniqueDynamic(this, &UReflectionsNpcReactionComponent::OnNearbySpell);
        Events->OnSpellHit.AddUniqueDynamic(this, &UReflectionsNpcReactionComponent::OnSpellHit);
    }
    if (UReflectionsHealthComponent* Health = GetOwner()->FindComponentByClass<UReflectionsHealthComponent>())
    {
        LastKnownHealth = Health->Health > 0.0f ? Health->Health : Health->MaxHealth;
        Health->OnDeath.AddUniqueDynamic(this, &UReflectionsNpcReactionComponent::OnOwnerDied);
        Health->OnHealthChanged.AddUniqueDynamic(this, &UReflectionsNpcReactionComponent::OnHealthChanged);
    }
}
void UReflectionsNpcReactionComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    if (Reason == EEndPlayReason::Destroyed)
        if (ACharacter* Driver = LocomotionDriver.Get()) Driver->Destroy();
    if (UWorld* World = GetWorld())
        if (UReflectionsSpellEventSubsystem* Events = World->GetSubsystem<UReflectionsSpellEventSubsystem>())
        {
            Events->OnSpellEvent.RemoveDynamic(this, &UReflectionsNpcReactionComponent::OnNearbySpell);
            Events->OnSpellHit.RemoveDynamic(this, &UReflectionsNpcReactionComponent::OnSpellHit);
        }
    Super::EndPlay(Reason);
}
void UReflectionsNpcReactionComponent::SetReaction(EReflectionsNpcReaction Next, AActor* Cause, FVector EventLocation)
{
    if (Reaction == EReflectionsNpcReaction::Incapacitated) return;
    Focus = Cause; ThreatLocation = EventLocation; ReactionTimeRemaining = 7.0f;
    if (Reaction != Next) { Reaction = Next; OnReactionChanged.Broadcast(Reaction, Cause, EventLocation); }
    if (Next == EReflectionsNpcReaction::Fleeing)
    {
        FVector Away = (GetOwner()->GetActorLocation() - EventLocation).GetSafeNormal2D();
        if (Away.IsNearlyZero()) Away = -GetOwner()->GetActorForwardVector();
        const float Variation = static_cast<float>(GetTypeHash(GetOwner()->GetFName()) % 61) - 30.0f;
        SafeDestination = GetOwner()->GetActorLocation() + Away.RotateAngleAxis(Variation, FVector::UpVector) * 700.0f;
    }
}
void UReflectionsNpcReactionComponent::OnNearbySpell(EHeroSpell Spell, FVector Location, AActor* Caster, float Intensity)
{
    if (!IsValid(GetOwner()) || !IsValid(Caster) || Caster == GetOwner() || Reaction == EReflectionsNpcReaction::Incapacitated) return;
    const float Distance = FVector::Dist(GetOwner()->GetActorLocation(), Location);
    if (Distance > AwarenessRadius) return;
    const float Strength = FMath::Clamp((1.0f - Distance / FMath::Max(1.0f, AwarenessRadius)) * Intensity / 20.0f, 0.0f, 1.0f);
    if (Strength < .04f) return;
    Fear = FMath::Clamp(Fear + Strength * (Disposition == EReflectionsNpcDisposition::Timid ? .9f : .45f), 0.0f, 1.0f);
    const UReflectionsReputationSubsystem* Reputation = GetWorld()->GetSubsystem<UReflectionsReputationSubsystem>();
    const float PlayerReputation = Reputation ? Reputation->GetReputation(Caster) : 0.0f;
    if (Disposition == EReflectionsNpcDisposition::Hostile || (Disposition == EReflectionsNpcDisposition::Guard && PlayerReputation <= -25.0f))
    {
        Hostility = FMath::Clamp(Hostility + Strength * .6f, 0.0f, 1.0f);
        SetReaction(bCanAttack ? EReflectionsNpcReaction::Attacking : EReflectionsNpcReaction::Defending, Caster, Location);
    }
    else if (Disposition == EReflectionsNpcDisposition::Guard || Disposition == EReflectionsNpcDisposition::Brave)
        SetReaction(EReflectionsNpcReaction::Investigating, Caster, Location);
    else if (Fear > .18f)
        SetReaction(EReflectionsNpcReaction::Fleeing, Caster, Location);
    else
        SetReaction(EReflectionsNpcReaction::Alert, Caster, Location);
}
void UReflectionsNpcReactionComponent::OnSpellHit(const FReflectionsSpellHitData& Hit)
{
    if (Hit.Target != GetOwner()) return;
    if (Reaction == EReflectionsNpcReaction::Incapacitated)
    {
        if (USkeletalMeshComponent* Mesh = FindNpcBody(GetOwner()))
            if (Mesh->IsSimulatingPhysics(Hit.Bone)) Mesh->AddImpulseAtLocation(Hit.Impulse, Hit.Location, Hit.Bone);
        return;
    }
    StartPhysicalHit(Hit);
    if (!Cast<ACharacter>(GetOwner()))
    {
        const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(Hit.Spell);
        const bool bBlast = Spec.Radius >= 180.0f;
        // The actor-only assemblies have no CharacterMovement capsule: keep their
        // root moving while the skeletal bodies react, and sweep against the world.
        // Proxy impact points are often chest-high while actor origins are at
        // their feet; applying that raw vector would drive the actor into the floor.
        const FVector HorizontalImpulse(Hit.Impulse.X, Hit.Impulse.Y, 0.0f);
        KnockbackVelocity = bBlast && !HorizontalImpulse.IsNearlyZero()
            ? HorizontalImpulse.GetSafeNormal() * FMath::Clamp(HorizontalImpulse.Size() * 2.5f, 400.0f, 1100.0f)
            : HorizontalImpulse.GetClampedToMaxSize(900.0f);
    }
    Fear = FMath::Clamp(Fear + .6f, 0.0f, 1.0f);
    Hostility = FMath::Clamp(Hostility + .7f, 0.0f, 1.0f);
    const bool Fighter = Disposition == EReflectionsNpcDisposition::Guard || Disposition == EReflectionsNpcDisposition::Hostile || Disposition == EReflectionsNpcDisposition::Brave;
    SetReaction(Fighter && bCanAttack ? EReflectionsNpcReaction::Attacking : EReflectionsNpcReaction::Fleeing, Hit.Caster, Hit.Location);
}

bool UReflectionsNpcReactionComponent::StartPhysicalHit(const FReflectionsSpellHitData& Hit)
{
    if (!bEnablePhysicalHitReaction) return false;
    USkeletalMeshComponent* Mesh = FindNpcBody(GetOwner());
    if (!Mesh || !Mesh->GetPhysicsAsset() || Mesh->IsSimulatingPhysics()) return false;
    if (HitMesh.IsValid()) EndPhysicalHit();

    const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(Hit.Spell);
    const bool bBlast = Spec.Radius >= 180.0f;
    // Keep the actor's root and legs animated during nonlethal hits. Some
    // MetaHuman assets have no torso body but do have upper-arm physics bodies.
    // Enabling collision first creates instances for normally no-collision meshes.
    OriginalMeshCollision = Mesh->GetCollisionEnabled();
    Mesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    FName Bone = Hit.Bone;
    const FName Candidates[] = { TEXT("upperarm_l"), TEXT("upperarm_r"), TEXT("lowerarm_l"), TEXT("lowerarm_r"), TEXT("head") };
    bool bSafeHitBone = false;
    for (const FName Candidate : Candidates) bSafeHitBone |= Bone == Candidate;
    if (!bSafeHitBone || !Mesh->GetBodyInstance(Bone))
    {
        Bone = NAME_None;
        float NearestDistance = TNumericLimits<float>::Max();
        for (const FName Candidate : Candidates)
            if (Mesh->GetBodyInstance(Candidate))
            {
                const float Distance = FVector::DistSquared(Mesh->GetBoneLocation(Candidate), Hit.Location);
                if (Distance < NearestDistance) { NearestDistance = Distance; Bone = Candidate; }
            }
    }
    if (Bone.IsNone()) { Mesh->SetCollisionEnabled(OriginalMeshCollision); return false; }
    FBodyInstance* Body = Mesh->GetBodyInstance(Bone);
    if (!Body) { Mesh->SetCollisionEnabled(OriginalMeshCollision); return false; }

    HitMesh = Mesh;
    HitPhysicsRoot = Bone;
    HitPhysicsDuration = bBlast ? 1.0f : 0.65f;
    HitPhysicsRemaining = HitPhysicsDuration;
    HitPhysicsPeakWeight = bBlast ? 0.8f : 0.55f;
    Mesh->SetAllBodiesBelowSimulatePhysics(HitPhysicsRoot, true, true);
    Mesh->SetAllBodiesBelowPhysicsBlendWeight(HitPhysicsRoot, HitPhysicsPeakWeight, false, true);
    if (!Mesh->IsSimulatingPhysics(Bone)) { EndPhysicalHit(); return false; }
    FVector Direction = bBlast ? FVector(Hit.Impulse.X, Hit.Impulse.Y, 0.0f).GetSafeNormal() : Hit.Impulse.GetSafeNormal();
    if (Direction.IsNearlyZero()) Direction = -Hit.ImpactNormal.GetSafeNormal();
    if (Direction.IsNearlyZero()) Direction = GetOwner()->GetActorForwardVector();
    if (bBlast) Direction = (Direction + FVector(0, 0, 0.25f)).GetSafeNormal();
    const float Speed = FMath::Clamp(Hit.Impulse.Size() * (bBlast ? 2.5f : 1.5f), bBlast ? 300.0f : 100.0f, 1000.0f);
    const FVector BonePosition = Mesh->GetBoneLocation(Bone);
    const FVector Point = BonePosition + (Hit.Location - BonePosition).GetClampedToMaxSize(30.0f);
    Mesh->AddImpulseAtLocation(Direction * Speed * FMath::Max(1.0f, Body->GetBodyMass()), Point, Bone);
    return true;
}

void UReflectionsNpcReactionComponent::EndPhysicalHit()
{
    if (USkeletalMeshComponent* Mesh = HitMesh.Get())
    {
        Mesh->SetAllBodiesBelowPhysicsBlendWeight(HitPhysicsRoot, 0.0f, false, true);
        Mesh->SetAllBodiesBelowSimulatePhysics(HitPhysicsRoot, false, true);
        Mesh->SetCollisionEnabled(OriginalMeshCollision);
    }
    HitMesh.Reset(); HitPhysicsRoot = NAME_None; HitPhysicsRemaining = 0.0f;
}
void UReflectionsNpcReactionComponent::OnOwnerDied(AActor* Source)
{
    if (HitMesh.IsValid()) EndPhysicalHit();
    SetReaction(EReflectionsNpcReaction::Incapacitated, Source, GetOwner()->GetActorLocation());
    if (ACharacter* Driver = LocomotionDriver.Get())
    {
        Driver->GetCharacterMovement()->StopMovementImmediately();
        Driver->GetCharacterMovement()->DisableMovement();
        Driver->GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    }
    if (!bEnableRagdollOnDeath) return;
    if (USkeletalMeshComponent* Mesh = FindNpcBody(GetOwner()))
        if (Mesh->GetPhysicsAsset()) { Mesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics); Mesh->SetSimulatePhysics(true); }
}
void UReflectionsNpcReactionComponent::OnHealthChanged(float Health, float MaxHealth, AActor* Source)
{
    const float Healed = Health - LastKnownHealth;
    LastKnownHealth = Health;
    const APawn* Pawn = Cast<APawn>(Source);
    if (Healed > 0.0f && Pawn && Pawn->IsPlayerControlled())
        if (UReflectionsReputationSubsystem* Reputation = GetWorld()->GetSubsystem<UReflectionsReputationSubsystem>())
            Reputation->AdjustReputation(Source, FMath::Min(5.0f, Healed * .1f));
}

void UReflectionsNpcReactionComponent::InitializeLocomotion()
{
    bTriedLocomotion = true;
    AActor* Actor = GetOwner();
    if (!Actor->ActorHasTag(TEXT("NPC_SampleLocomotion"))) return;
    USkeletalMeshComponent* Body = FindNpcBody(Actor);
    if (!Body || !Body->GetSkeletalMeshAsset() || !Actor->GetRootComponent()) return;

    const FString MeshName = Body->GetSkeletalMeshAsset()->GetName();
    FString Identity = MeshName;
    if (!Identity.RemoveFromStart(TEXT("SKM_MHC_")) || !Identity.RemoveFromEnd(TEXT("_BodyMesh"))) return;
    const FString AnimName = TEXT("ABP_Crowd_") + Identity;
    const FSoftClassPath AnimPath(FString::Printf(TEXT("/Game/Characters/CrowdMotion/%s.%s_C"), *AnimName, *AnimName));
    UClass* AnimClass = AnimPath.TryLoadClass<UAnimInstance>();
    const FSoftClassPath DriverPath(TEXT("/Game/Characters/Hero/Sample/BP_SampleCMCClean2.BP_SampleCMCClean2_C"));
    UClass* DriverClass = DriverPath.TryLoadClass<ACharacter>();
    if (!AnimClass || !DriverClass)
    {
        UE_LOG(LogTemp, Warning, TEXT("Sample locomotion assets missing for %s"), *Actor->GetName());
        return;
    }

    const ACharacter* Defaults = DriverClass->GetDefaultObject<ACharacter>();
    const float HalfHeight = Defaults->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
    RoamOrigin = Actor->GetActorLocation();
    const FRotator DriverFacing(0.0, Actor->GetActorRotation().Yaw + 90.0, 0.0);
    const FVector SpawnLocation = RoamOrigin + FVector(0.0, 0.0, HalfHeight + 1.0);
    FActorSpawnParameters Params;
    Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    ACharacter* Driver = GetWorld()->SpawnActor<ACharacter>(DriverClass, SpawnLocation, DriverFacing, Params);
    if (!Driver) return;

    // The existing MetaHuman retains health, hit queries, voice and skeletal physics.
    // The hidden pawn only drives movement and the sample pose, and ignores spell traces.
    Driver->SetCanBeDamaged(false);
    UCapsuleComponent* Capsule = Driver->GetCapsuleComponent();
    // The spell overlap and projectile paths query Pawn, WorldDynamic and
    // PhysicsBody; the visible actor's proxy remains the spell target.
    Capsule->SetCollisionObjectType(ECC_Vehicle);
    Capsule->SetCollisionResponseToAllChannels(ECR_Ignore);
    Capsule->SetCollisionResponseToChannel(ECC_WorldStatic, ECR_Block);
    Capsule->SetCollisionResponseToChannel(ECC_Pawn, ECR_Block);
    Capsule->IgnoreActorWhenMoving(Actor, true);
    Driver->GetMesh()->SetVisibility(false);
    Driver->GetMesh()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Driver->GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    Driver->GetMesh()->SetForcedLOD(1);
    if (!Driver->GetController()) Driver->SpawnDefaultController();
    UCharacterMovementComponent* Movement = Driver->GetCharacterMovement();
    Movement->bOrientRotationToMovement = true;
    Movement->bUseControllerDesiredRotation = false;
    Driver->bUseControllerRotationYaw = false;
    Movement->AddTickPrerequisiteComponent(this);

    Actor->AttachToComponent(Driver->GetMesh(), FAttachmentTransformRules::KeepWorldTransform);
    Body->AddTickPrerequisiteComponent(Driver->GetMesh());
    Body->ComponentTags.AddUnique(TEXT("CrowdSample"));
    Body->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    Body->SetAnimInstanceClass(AnimClass);
    LocomotionDriver = Driver;
    RoamPause = 0.2f + FMath::Fmod(FMath::Abs(RoamOrigin.Y), 170.0f) / 180.0f;
}

void UReflectionsNpcReactionComponent::TickAmbientMovement(float DeltaTime)
{
    if (!LocomotionDriver.IsValid()) return;
    if (RoamPause > 0.0f)
    {
        RoamPause -= DeltaTime;
        return;
    }

    RoamLegTime -= DeltaTime;
    if (RoamLegTime <= 0.0f || FVector::DistSquared2D(GetOwner()->GetActorLocation(), RoamTarget) < FMath::Square(45.0))
    {
        ++RoamLeg;
        constexpr float RouteRadius = 200.0f;
        const float Angle = RoamLeg * 120.0f + RoamOrigin.X * 0.24f + RoamOrigin.Y * 0.09f;
        RoamTarget = RoamOrigin + FVector::ForwardVector.RotateAngleAxis(Angle, FVector::UpVector) * RouteRadius;
        RoamLegTime = 4.5f;
        RoamPause = RoamLeg > 1 ? 0.35f : 0.0f;
        if (RoamPause > 0.0f) return;
    }
    TryMove(RoamTarget, DeltaTime);
}

void UReflectionsNpcReactionComponent::TryMove(const FVector& Target, float DeltaTime)
{
    AActor* Actor = GetOwner();
    const FVector Here = Actor->GetActorLocation();
    FVector Direction = (Target - Here).GetSafeNormal2D();
    if (Direction.IsNearlyZero()) return;
    if (ACharacter* Driver = LocomotionDriver.Get())
    {
        // The sample sets max speed in its own pre-movement update. Supply
        // analog input through CMC so pose search sees the actual trajectory.
        const float DesiredSpeed = Reaction == EReflectionsNpcReaction::Calm ? 140.0f : ReactionSpeed;
        const float SampleSpeed = Driver->GetCharacterMovement()->GetMaxSpeed();
        Driver->AddMovementInput(Direction, FMath::Clamp(DesiredSpeed / FMath::Max(1.0f, SampleSpeed), 0.0f, 1.0f), true);
    }
    else if (ACharacter* Character = Cast<ACharacter>(Actor)) Character->AddMovementInput(Direction, 1.0f);
    else
    {
        const float Step = FMath::Min(ReactionSpeed * DeltaTime, FVector::Dist2D(Here, Target));
        FHitResult Hit;
        Actor->AddActorWorldOffset(Direction * Step, true, &Hit);
        Actor->SetActorRotation(FMath::RInterpTo(Actor->GetActorRotation(), Direction.Rotation(), DeltaTime, 5.0f));
    }
}
void UReflectionsNpcReactionComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* TickFunction)
{
    Super::TickComponent(DeltaTime, TickType, TickFunction);
    if (!bTriedLocomotion && Reaction != EReflectionsNpcReaction::Incapacitated) InitializeLocomotion();
    if (HitMesh.IsValid())
    {
        HitPhysicsRemaining -= DeltaTime;
        if (HitPhysicsRemaining <= 0.0f) EndPhysicalHit();
        else if (HitPhysicsRemaining < HitPhysicsDuration * 0.5f)
            HitMesh->SetAllBodiesBelowPhysicsBlendWeight(HitPhysicsRoot, HitPhysicsPeakWeight * HitPhysicsRemaining / (HitPhysicsDuration * 0.5f), false, true);
    }
    if (!KnockbackVelocity.IsNearlyZero() && Reaction != EReflectionsNpcReaction::Incapacitated)
    {
        FHitResult Hit;
        AActor* MovingActor = LocomotionDriver.IsValid() ? static_cast<AActor*>(LocomotionDriver.Get()) : GetOwner();
        MovingActor->AddActorWorldOffset(KnockbackVelocity * DeltaTime, true, &Hit);
        KnockbackVelocity *= FMath::Exp(-6.0f * DeltaTime);
        if (KnockbackVelocity.SizeSquared() < 25.0f) KnockbackVelocity = FVector::ZeroVector;
    }
    if (Reaction == EReflectionsNpcReaction::Incapacitated) return;
    // Dedicated combat opponents have their own path-following and attack state.
    // Keep the reaction component's physics and death handling active above.
    if (GetOwner()->ActorHasTag(TEXT("NPC_CombatEnemy"))) return;
    if (Reaction == EReflectionsNpcReaction::Calm)
    {
        TickAmbientMovement(DeltaTime);
        return;
    }
    ReactionTimeRemaining -= DeltaTime; AttackCooldown = FMath::Max(0.0f, AttackCooldown - DeltaTime);
    if (ReactionTimeRemaining <= 0.0f)
    {
        Fear = FMath::Max(0.0f, Fear - .3f); Hostility = FMath::Max(0.0f, Hostility - .2f);
        SetReaction(EReflectionsNpcReaction::Calm, nullptr, GetOwner()->GetActorLocation()); return;
    }
    if (Reaction == EReflectionsNpcReaction::Fleeing) TryMove(SafeDestination, DeltaTime);
    else if (Reaction == EReflectionsNpcReaction::Investigating && FVector::Dist2D(GetOwner()->GetActorLocation(), ThreatLocation) > 250.0f) TryMove(ThreatLocation, DeltaTime);
    else if (Reaction == EReflectionsNpcReaction::Attacking && Focus.IsValid())
    {
        const float Distance = FVector::Dist2D(GetOwner()->GetActorLocation(), Focus->GetActorLocation());
        if (Distance > 150.0f) TryMove(Focus->GetActorLocation(), DeltaTime);
        else if (AttackCooldown <= 0.0f && bCanAttack)
        {
            UGameplayStatics::ApplyDamage(Focus.Get(), 8.0f, nullptr, GetOwner(), UDamageType::StaticClass());
            AttackCooldown = 1.5f;
        }
    }
}
