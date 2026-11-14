#include "NPC/ReflectionsNpcCombatComponent.h"

#include "Animation/AnimInstance.h"
#include "Animation/AnimSequence.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Hero/ReflectionsSpellCombat.h"
#include "Kismet/GameplayStatics.h"
#include "NavigationPath.h"
#include "NavigationSystem.h"
#include "NPC/ReflectionsNpcReactionComponent.h"

UReflectionsNpcCombatComponent::UReflectionsNpcCombatComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.TickGroup = TG_PrePhysics;
}

void UReflectionsNpcCombatComponent::BeginPlay()
{
    Super::BeginPlay();
    TInlineComponentArray<USkeletalMeshComponent*> Meshes(GetOwner());
    for (USkeletalMeshComponent* Mesh : Meshes)
    {
        if (Mesh && Mesh->GetFName() == TEXT("Body"))
        {
            Body = Mesh;
            break;
        }
    }
    AttackAnimation = LoadObject<UAnimSequence>(nullptr,
        TEXT("/Game/Characters/CrowdMotion/Combat/AS_GuardPunch.AS_GuardPunch"));
    GetOwner()->OnTakeAnyDamage.AddUniqueDynamic(this, &UReflectionsNpcCombatComponent::OnOwnerDamaged);
    if (!AttackAnimation)
        UE_LOG(LogTemp, Warning, TEXT("Combat enemy %s cannot attack: guard animation is missing"), *GetOwner()->GetName());
}

void UReflectionsNpcCombatComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    if (AActor* Actor = GetOwner())
        Actor->OnTakeAnyDamage.RemoveDynamic(this, &UReflectionsNpcCombatComponent::OnOwnerDamaged);
    EndAttack(false);
    Super::EndPlay(Reason);
}

void UReflectionsNpcCombatComponent::OnOwnerDamaged(AActor* DamagedActor, float Damage,
    const UDamageType* DamageType, AController* Instigator, AActor* DamageCauser)
{
    if (Damage <= 0.0f || CombatState != EReflectionsNpcCombatState::Windup) return;
    const UReflectionsHealthComponent* Health = GetOwner()->FindComponentByClass<UReflectionsHealthComponent>();
    EndAttack(!Health || Health->Health > 0.0f);
    ++InterruptedAttacks;
    RecoveryTime = 0.65f;
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
    if (!Candidate || !GetWorld()) return false;
    const FVector Start = GetOwner()->GetActorLocation() + FVector(0.0, 0.0, 95.0);
    const FVector End = Candidate->GetActorLocation();
    FCollisionQueryParams Params(SCENE_QUERY_STAT(NpcCombatSight), false, GetOwner());
    if (const UReflectionsNpcReactionComponent* Reaction = GetOwner()->FindComponentByClass<UReflectionsNpcReactionComponent>())
        if (const ACharacter* Driver = Reaction->GetLocomotionDriver()) Params.AddIgnoredActor(Driver);
    FHitResult Hit;
    return !GetWorld()->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, Params) ||
        Hit.GetActor() == Candidate || (Hit.GetActor() && Hit.GetActor()->IsAttachedTo(Candidate));
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
    if (!Direction.IsNearlyZero()) Driver->AddMovementInput(Direction, 0.7f, true);
}

void UReflectionsNpcCombatComponent::StartAttack(ACharacter* Driver)
{
    if (!Body || !AttackAnimation || !Driver) return;
    SavedAnimationClass = Body->GetAnimClass();
    if (!SavedAnimationClass) return;
    Driver->GetCharacterMovement()->StopMovementImmediately();
    Body->PlayAnimation(AttackAnimation, false);
    AttackTime = 0.0f;
    ImpactTime = FMath::Clamp(AttackAnimation->GetPlayLength() * 0.45f, 0.2f, 0.8f);
    bImpactApplied = false;
    ++AttacksStarted;
    CombatState = EReflectionsNpcCombatState::Windup;
}

void UReflectionsNpcCombatComponent::EndAttack(bool bRestoreAnimation)
{
    if (bRestoreAnimation && Body && SavedAnimationClass)
        Body->SetAnimInstanceClass(SavedAnimationClass);
    SavedAnimationClass = nullptr;
}

void UReflectionsNpcCombatComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* TickFunction)
{
    Super::TickComponent(DeltaTime, TickType, TickFunction);
    UReflectionsNpcReactionComponent* Reaction = GetOwner()->FindComponentByClass<UReflectionsNpcReactionComponent>();
    UReflectionsHealthComponent* OwnHealth = GetOwner()->FindComponentByClass<UReflectionsHealthComponent>();
    ACharacter* Driver = Reaction ? Reaction->GetLocomotionDriver() : nullptr;
    if ((OwnHealth && OwnHealth->Health <= 0.0f) || (Reaction && Reaction->Reaction == EReflectionsNpcReaction::Incapacitated))
    {
        EndAttack(false);
        Target = nullptr;
        CombatState = EReflectionsNpcCombatState::Dead;
        return;
    }
    if (!Driver || !GetWorld()) return;

    AActor* Player = UGameplayStatics::GetPlayerPawn(GetWorld(), 0);
    if (!CanTarget(Player) || FVector::DistSquared2D(GetOwner()->GetActorLocation(), Player->GetActorLocation()) > FMath::Square(AwarenessRadius))
    {
        if (CombatState == EReflectionsNpcCombatState::Windup) EndAttack(true);
        Target = nullptr;
        CombatState = EReflectionsNpcCombatState::Idle;
        Driver->GetCharacterMovement()->StopMovementImmediately();
        return;
    }
    if (Target != Player)
    {
        Target = nullptr;
        if (!HasLineOfSight(Player))
        {
            CombatState = EReflectionsNpcCombatState::Idle;
            Driver->GetCharacterMovement()->StopMovementImmediately();
            return;
        }
    }
    Target = Player;

    if (CombatState == EReflectionsNpcCombatState::Windup)
    {
        AttackTime += DeltaTime;
        if (!bImpactApplied && AttackTime >= ImpactTime)
        {
            bImpactApplied = true;
            const FVector Delta = Player->GetActorLocation() - GetOwner()->GetActorLocation();
            if (Delta.Size2D() <= AttackRange && FMath::Abs(Delta.Z) < 160.0f && HasLineOfSight(Player) && CanTarget(Player))
            {
                UGameplayStatics::ApplyDamage(Player, AttackDamage, Driver->GetController(), GetOwner(), UDamageType::StaticClass());
                ++SuccessfulHits;
            }
        }
        if (AttackTime >= AttackAnimation->GetPlayLength())
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
            const FVector Away = (Driver->GetActorLocation() - Player->GetActorLocation()).GetSafeNormal2D();
            Driver->AddMovementInput(Away, 0.3f, true);
        }
        if (RecoveryTime > 0.0f) return;
    }

    const FVector Delta = Player->GetActorLocation() - GetOwner()->GetActorLocation();
    if (Delta.Size2D() <= AttackRange && FMath::Abs(Delta.Z) < 160.0f && HasLineOfSight(Player))
        StartAttack(Driver);
    else
    {
        CombatState = EReflectionsNpcCombatState::Chasing;
        FollowTarget(Driver, Player, DeltaTime);
    }
}
