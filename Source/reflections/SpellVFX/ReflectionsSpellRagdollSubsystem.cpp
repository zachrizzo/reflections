#include "SpellVFX/ReflectionsSpellRagdollSubsystem.h"

#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Hero/ReflectionsSpellCatalog.h"
#include "Hero/ReflectionsSpellCombat.h"
#include "PhysicsEngine/BodyInstance.h"

bool UReflectionsSpellRagdollSubsystem::DoesSupportWorldType(EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UReflectionsSpellRagdollSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
    Super::OnWorldBeginPlay(InWorld);
    if (UReflectionsSpellEventSubsystem* Events = InWorld.GetSubsystem<UReflectionsSpellEventSubsystem>())
    {
        Events->OnSpellHit.AddUniqueDynamic(this, &UReflectionsSpellRagdollSubsystem::OnSpellHit);
    }
}

void UReflectionsSpellRagdollSubsystem::Deinitialize()
{
    if (UWorld* World = GetWorld())
    {
        if (UReflectionsSpellEventSubsystem* Events = World->GetSubsystem<UReflectionsSpellEventSubsystem>())
        {
            Events->OnSpellHit.RemoveDynamic(this, &UReflectionsSpellRagdollSubsystem::OnSpellHit);
        }
    }
    Super::Deinitialize();
}

void UReflectionsSpellRagdollSubsystem::OnSpellHit(const FReflectionsSpellHitData& Hit)
{
    AActor* Target = Hit.Target;
    if (!IsValid(Target) || !Target->ActorHasTag(TEXT("NPC_Ragdoll")) ||
        !ReflectionsSpellCatalog::IsValid(Hit.Spell))
    {
        return;
    }

    const UReflectionsHealthComponent* Health = Target->FindComponentByClass<UReflectionsHealthComponent>();
    if (!Health || Health->Health > 0.0f) return;

    USkeletalMeshComponent* Body = nullptr;
    TInlineComponentArray<USkeletalMeshComponent*> Meshes(Target);
    for (USkeletalMeshComponent* Mesh : Meshes)
    {
        if (Mesh->GetFName() == TEXT("Body") && Mesh->GetPhysicsAsset())
        {
            Body = Mesh;
            break;
        }
    }
    if (!Body || !Body->IsSimulatingPhysics()) return;

    const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(Hit.Spell);
    const bool bBlast = Spec.Radius >= 180.0f;
    FVector Direction = Hit.Impulse.GetSafeNormal();
    if (Direction.IsNearlyZero()) Direction = -Hit.ImpactNormal.GetSafeNormal();
    if (Direction.IsNearlyZero() && IsValid(Hit.Caster))
    {
        Direction = (Target->GetActorLocation() - Hit.Caster->GetActorLocation()).GetSafeNormal();
    }
    if (Direction.IsNearlyZero()) Direction = Target->GetActorForwardVector();

    Body->WakeAllRigidBodies();
    if (bBlast)
    {
        // Apply a shared velocity change to the whole ragdoll so an explosion
        // pushes the character away without separating the constrained limbs.
        const FVector Horizontal = Direction.GetSafeNormal2D();
        const FVector BlastDirection = (Horizontal + FVector(0.0f, 0.0f, 0.35f)).GetSafeNormal();
        const float Speed = FMath::Clamp(Hit.Impulse.Size() * 2.0f, 250.0f, 850.0f);
        Body->AddImpulseToAllBodiesBelow(BlastDirection * Speed, NAME_None, true, true);
        return;
    }

    FClosestPointOnPhysicsAsset Closest;
    FName Bone = Hit.Bone;
    if (Bone.IsNone() || !Body->GetBodyInstance(Bone))
    {
        if (Body->GetClosestPointOnPhysicsAsset(Hit.Location, Closest, false)) Bone = Closest.BoneName;
    }
    if (Bone.IsNone() || !Body->GetBodyInstance(Bone) || !Body->IsSimulatingPhysics(Bone))
    {
        // Query-only target capsules usually do not report a skeletal bone.
        // Some MetaHuman physics assets also omit torso and pelvis bodies.
        constexpr const TCHAR* Candidates[] = {
            TEXT("upperarm_l"), TEXT("upperarm_r"), TEXT("lowerarm_l"),
            TEXT("lowerarm_r"), TEXT("head")
        };
        Bone = NAME_None;
        float ClosestDistance = TNumericLimits<float>::Max();
        for (const TCHAR* Candidate : Candidates)
        {
            const FName CandidateName(Candidate);
            if (!Body->GetBodyInstance(CandidateName) || !Body->IsSimulatingPhysics(CandidateName)) continue;
            const float Distance = FVector::DistSquared(Body->GetBoneLocation(CandidateName), Hit.Location);
            if (Distance < ClosestDistance)
            {
                ClosestDistance = Distance;
                Bone = CandidateName;
            }
        }
    }
    if (Bone.IsNone()) return;
    FBodyInstance* Instance = Body->GetBodyInstance(Bone);
    if (!Instance || !Body->IsSimulatingPhysics(Bone)) return;

    const FVector Point = Body->GetBoneLocation(Bone) +
        (Hit.Location - Body->GetBoneLocation(Bone)).GetClampedToMaxSize(30.0f);
    const float Speed = FMath::Clamp(Hit.Impulse.Size() * 1.5f, 100.0f, 600.0f);
    Body->AddImpulseAtLocation(Direction * Speed * FMath::Max(1.0f, Instance->GetBodyMass()), Point, Bone);
}
