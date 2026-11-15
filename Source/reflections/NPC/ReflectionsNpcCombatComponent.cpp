#include "NPC/ReflectionsNpcCombatComponent.h"

#include "Animation/AnimInstance.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/DamageType.h"
#include "Hero/ReflectionsSpellCombat.h"
#include "Kismet/GameplayStatics.h"
#include "NavigationPath.h"
#include "NavigationSystem.h"
#include "NPC/ReflectionsNpcArchetype.h"
#include "NPC/ReflectionsNpcReactionComponent.h"

UReflectionsNpcCombatComponent::UReflectionsNpcCombatComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.TickGroup = TG_PrePhysics;
}

void UReflectionsNpcCombatComponent::Configure(const FReflectionsNpcCombatProfile& Profile, UReflectionsNpcReactionComponent* InBrain)
{
    Brain = InBrain;
    AwarenessRadius = Profile.SightRadius;
    AttackRange = Profile.AttackRange;
    AttackDamage = Profile.AttackDamage;
    AttackCooldown = Profile.AttackCooldown;
    ChaseInput = Profile.ChaseInput;
    InterruptRecovery = Profile.InterruptRecovery;
    ImpactFraction = Profile.ImpactFraction;
    AttackAnimation = Profile.AttackAnimation.LoadSynchronous();
    AttackAnimations.Reset();
    for (const TSoftObjectPtr<UAnimSequence>& Clip : Profile.AttackAnimations)
        if (UAnimSequence* Loaded = Clip.LoadSynchronous()) AttackAnimations.Add(Loaded);
    WalkerAttackAnimations.Reset();
    for (const TSoftObjectPtr<UAnimSequence>& Clip : Profile.WalkerAttackAnimations)
        if (UAnimSequence* Loaded = Clip.LoadSynchronous()) WalkerAttackAnimations.Add(Loaded);
}

void UReflectionsNpcCombatComponent::SetCombatTarget(AActor* NewTarget)
{
    AssignedTarget = NewTarget;
}

ACharacter* UReflectionsNpcCombatComponent::GetDriver() const
{
    return Brain ? Brain->GetMovementCharacter() : Cast<ACharacter>(GetOwner());
}

bool UReflectionsNpcCombatComponent::IsUsable() const
{
    return GetDriver() != nullptr;
}

void UReflectionsNpcCombatComponent::BeginPlay()
{
    Super::BeginPlay();
    AActor* Owner = GetOwner();
    TInlineComponentArray<USkeletalMeshComponent*> Meshes(Owner);
    for (USkeletalMeshComponent* Mesh : Meshes)
    {
        if (Mesh && Mesh->GetFName() == TEXT("Body"))
        {
            Body = Mesh;
            break;
        }
    }
    if (!Body)
        if (const ACharacter* Character = Cast<ACharacter>(Owner)) Body = Character->GetMesh();
    if (!Brain) Brain = Owner->FindComponentByClass<UReflectionsNpcReactionComponent>();
    Owner->OnTakeAnyDamage.AddUniqueDynamic(this, &UReflectionsNpcCombatComponent::OnOwnerDamaged);
    if (!AttackAnimation)
        UE_LOG(LogTemp, Verbose, TEXT("Combat NPC %s has no strike clip: its attacks are timed without animation"), *Owner->GetName());
}

void UReflectionsNpcCombatComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    if (AActor* Actor = GetOwner())
        Actor->OnTakeAnyDamage.RemoveDynamic(this, &UReflectionsNpcCombatComponent::OnOwnerDamaged);
    EndAttack(Reason == EEndPlayReason::Destroyed && IsValid(GetOwner()) && !GetOwner()->IsActorBeingDestroyed());
    Super::EndPlay(Reason);
}

void UReflectionsNpcCombatComponent::OnOwnerDamaged(AActor* DamagedActor, float Damage,
    const UDamageType* DamageType, AController* Instigator, AActor* DamageCauser)
{
    if (Damage <= 0.0f || CombatState != EReflectionsNpcCombatState::Windup) return;
    const UReflectionsHealthComponent* Health = GetOwner()->FindComponentByClass<UReflectionsHealthComponent>();
    EndAttack(!Health || Health->Health > 0.0f);
    ++InterruptedAttacks;
    RecoveryTime = InterruptRecovery;
    CombatState = EReflectionsNpcCombatState::Recovering;
}

bool UReflectionsNpcCombatComponent::CanTarget(AActor* Candidate) const
{
    if (!IsValid(Candidate) || Candidate == GetOwner()) return false;
    const UReflectionsHealthComponent* Health = Candidate->FindComponentByClass<UReflectionsHealthComponent>();
    return !Health || Health->Health > 0.0f;
}

bool UReflectionsNpcCombatComponent::HasLineOfSight(AActor* Candidate) const
{
    return UReflectionsNpcReactionComponent::HasLineOfSight(GetOwner(), Candidate, Brain ? Brain->GetLocomotionDriver() : nullptr);
}

void UReflectionsNpcCombatComponent::FollowTarget(ACharacter* Driver, AActor* Candidate, float DeltaTime)
{
    if (!Driver || !Candidate) return;
    PathTimer -= DeltaTime;
    if (PathTimer <= 0.0f)
    {
        PathTimer = 0.8f;
        PathPoints.Empty();
        PathIndex = 0;
        if (UNavigationPath* Path = UNavigationSystemV1::FindPathToLocationSynchronously(
                GetWorld(), Driver->GetActorLocation(), Candidate->GetActorLocation(), Driver))
        {
            if (Path->IsValid() && !Path->IsPartial()) PathPoints = Path->PathPoints;
        }
    }
    while (PathIndex < PathPoints.Num() && FVector::DistSquared2D(Driver->GetActorLocation(), PathPoints[PathIndex]) < FMath::Square(75.0))
        ++PathIndex;
    // If a path isn't ready, move only towards a target visible from the current location.
    // Character movement collision then prevents walking through geometry.
    const bool bPathAvailable = PathIndex < PathPoints.Num();
    if (!bPathAvailable && !HasLineOfSight(Candidate)) return;
    const FVector Goal = bPathAvailable ? PathPoints[PathIndex] : Candidate->GetActorLocation();
    const FVector Direction = (Goal - Driver->GetActorLocation()).GetSafeNormal2D();
    if (!Direction.IsNearlyZero()) Driver->AddMovementInput(Direction, ChaseInput, true);
}

void UReflectionsNpcCombatComponent::StartAttack(ACharacter* Driver)
{
    if (!Driver) return;
    // A clip plays on the body when its skeleton is the body's; otherwise the strike is only timed. Among the
    // clips that fit, one at random, so a fighter does not repeat the same swing.
    UAnimSequence* Clip = nullptr;
    // SWITCHED OFF. Playing a clip on the visible body puts it in single-clip mode and re-initialises its
    // animation, and on the crowd MetaHuman bodies that can leave the body with no bone transforms: on train #8
    // three enemies struck with clips playing, were killed, and 0.7 s later the engine asserted on a body with
    // 342 bones and 0 transforms (SkinnedAsset.cpp:471, editor crash 16:16, the same lost pose as the physics
    // flinch). Until a fix is proven in PIE every strike is timed, whatever clips the archetype lists.
    static const bool bStrikeClipsOnTheBodyAreSafe = false;
    const USkeleton* Skeleton = bStrikeClipsOnTheBodyAreSafe && Body && Body->GetAnimClass() && Body->GetSkeletalMeshAsset()
        ? Body->GetSkeletalMeshAsset()->GetSkeleton() : nullptr;
    if (Skeleton)
    {
        TArray<UAnimSequence*, TInlineAllocator<8>> Fitting;
        for (UAnimSequence* Candidate : AttackAnimations)
            if (Candidate && Candidate->GetSkeleton() == Skeleton) Fitting.Add(Candidate);
        if (Fitting.Num() > 0) Clip = Fitting[FMath::RandHelper(Fitting.Num())];
        else if (AttackAnimation && AttackAnimation->GetSkeleton() == Skeleton) Clip = AttackAnimation;
    }
    const bool bPlayClip = Clip != nullptr;
    SavedAnimationClass = bPlayClip ? Body->GetAnimClass() : nullptr;
    // A body that someone already drives with one clip (a squad's march) gets that clip back after the strike;
    // any other body goes back to its animation blueprint.
    SavedSingleNodeAsset = nullptr;
    if (bPlayClip && Body->GetAnimationMode() == EAnimationMode::AnimationSingleNode)
        if (const UAnimSingleNodeInstance* Single = Body->GetSingleNodeInstance())
        {
            SavedSingleNodeAsset = Single->GetAnimationAsset();
            bSavedSingleNodeLooping = Single->IsLooping();
        }
    Driver->GetCharacterMovement()->StopMovementImmediately();
    if (bPlayClip) Body->PlayAnimation(Clip, false);
    // The way strikes are shown: a montage on the hidden walker, which the visible body follows through its
    // retarget blueprint. The body's own animation mode is never touched, so dying mid-swing is an ordinary death.
    UAnimSequence* WalkerStrike = !bPlayClip && Brain && WalkerAttackAnimations.Num() > 0
        ? WalkerAttackAnimations[FMath::RandHelper(WalkerAttackAnimations.Num())].Get() : nullptr;
    if (WalkerStrike && !Brain->PlayOnWalker(WalkerStrike, 1.0f)) WalkerStrike = nullptr;
    AttackTime = 0.0f;
    AttackLength = bPlayClip ? Clip->GetPlayLength() : WalkerStrike ? WalkerStrike->GetPlayLength() : 0.8f;
    ImpactTime = FMath::Clamp(AttackLength * ImpactFraction, 0.2f, 0.8f);
    bImpactApplied = false;
    ++AttacksStarted;
    CombatState = EReflectionsNpcCombatState::Windup;
}

void UReflectionsNpcCombatComponent::EndAttack(bool bRestoreAnimation)
{
    if (bRestoreAnimation && Body)
    {
        if (SavedSingleNodeAsset) Body->PlayAnimation(SavedSingleNodeAsset, bSavedSingleNodeLooping);
        else if (SavedAnimationClass) Body->SetAnimInstanceClass(SavedAnimationClass);
    }
    SavedAnimationClass = nullptr;
    SavedSingleNodeAsset = nullptr;
}

void UReflectionsNpcCombatComponent::StandDown(ACharacter* Driver)
{
    if (CombatState == EReflectionsNpcCombatState::Windup) EndAttack(true);
    if (Target || CombatState != EReflectionsNpcCombatState::Idle)
    {
        Target = nullptr;
        CombatState = EReflectionsNpcCombatState::Idle;
        if (Driver) Driver->GetCharacterMovement()->StopMovementImmediately();
    }
}

void UReflectionsNpcCombatComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* TickFunction)
{
    Super::TickComponent(DeltaTime, TickType, TickFunction);
    UReflectionsHealthComponent* OwnHealth = GetOwner()->FindComponentByClass<UReflectionsHealthComponent>();
    if ((OwnHealth && OwnHealth->Health <= 0.0f) || (Brain && Brain->IsIncapacitated()))
    {
        EndAttack(false);
        Target = nullptr;
        CombatState = EReflectionsNpcCombatState::Dead;
        return;
    }
    ACharacter* Driver = GetDriver();
    if (!Driver || !GetWorld()) return;

    // The NPC component says whom to fight (sight, a hit, a stimulus); none, or a dead one, stands the motor down.
    AActor* Wanted = AssignedTarget.Get();
    if (!CanTarget(Wanted))
    {
        StandDown(Driver);
        return;
    }
    Target = Wanted;

    if (CombatState == EReflectionsNpcCombatState::Windup)
    {
        AttackTime += DeltaTime;
        if (!bImpactApplied && AttackTime >= ImpactTime)
        {
            bImpactApplied = true;
            const FVector Delta = Wanted->GetActorLocation() - GetOwner()->GetActorLocation();
            if (Delta.Size2D() <= AttackRange && FMath::Abs(Delta.Z) < 160.0f && HasLineOfSight(Wanted) && CanTarget(Wanted))
            {
                UGameplayStatics::ApplyDamage(Wanted, AttackDamage, Driver->GetController(), GetOwner(), UDamageType::StaticClass());
                ++SuccessfulHits;
            }
        }
        if (AttackTime >= AttackLength)
        {
            EndAttack(true);
            RecoveryTime = AttackCooldown;
            CombatState = EReflectionsNpcCombatState::Recovering;
        }
        return;
    }
    if (CombatState == EReflectionsNpcCombatState::Recovering)
    {
        RecoveryTime -= DeltaTime;
        if (RecoveryTime > AttackCooldown * 0.5f)
        {
            const FVector Away = (Driver->GetActorLocation() - Wanted->GetActorLocation()).GetSafeNormal2D();
            Driver->AddMovementInput(Away, 0.3f, true);
        }
        if (RecoveryTime > 0.0f) return;
    }

    const FVector Delta = Wanted->GetActorLocation() - GetOwner()->GetActorLocation();
    if (Delta.Size2D() <= AttackRange && FMath::Abs(Delta.Z) < 160.0f && HasLineOfSight(Wanted))
        StartAttack(Driver);
    else
    {
        CombatState = EReflectionsNpcCombatState::Chasing;
        FollowTarget(Driver, Wanted, DeltaTime);
    }
}
