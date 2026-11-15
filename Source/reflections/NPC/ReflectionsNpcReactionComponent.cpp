#include "NPC/ReflectionsNpcReactionComponent.h"
#include "NPC/ReflectionsNpcCombatComponent.h"
#include "NPC/ReflectionsNpcSubsystem.h"
#include "Hero/ReflectionsSpellCombat.h"
#include "Hero/ReflectionsSpellCatalog.h"
#include "Animation/AnimInstance.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/AudioComponent.h"
#include "Sound/SoundBase.h"
#include "Misc/PackageName.h"
#include "Components/StaticMeshComponent.h"
#include "Animation/AnimSequence.h"
#include "Engine/StaticMesh.h"
#include "NiagaraComponent.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraSystem.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "UObject/UnrealType.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/DamageType.h"
#include "Kismet/GameplayStatics.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicsEngine/PhysicsAsset.h"
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

    /** A physics asset that can carry the whole body: some imported ones only have arms and a head. */
    bool CanRagdoll(const USkeletalMeshComponent* Mesh)
    {
        const UPhysicsAsset* Asset = Mesh ? Mesh->GetPhysicsAsset() : nullptr;
        return Asset && (Asset->FindBodyIndex(TEXT("pelvis")) != INDEX_NONE || Asset->SkeletalBodySetups.Num() >= 8);
    }

}

namespace
{
    /**
     * True when the body's component-space bone transforms are all there. Some engine calls index that array
     * with no bounds check (GetClosestPointOnPhysicsAsset asserted and took the editor down), and it can be
     * empty on a registered mesh, so nothing below touches bones or starts physics without asking first.
     */
    bool HasPose(const USkeletalMeshComponent* Mesh)
    {
        const USkeletalMesh* Asset = Mesh ? Mesh->GetSkeletalMeshAsset() : nullptr;
        if (!Asset || !Mesh->IsRegistered()) return false;
        if (Mesh->LeaderPoseComponent.IsValid()) return true;
        // The read buffer and the one animation writes into: either can be the one that lost its contents.
        const int32 Bones = Asset->GetRefSkeleton().GetNum();
        return Mesh->GetComponentSpaceTransforms().Num() >= Bones && Mesh->GetEditableComponentSpaceTransforms().Num() >= Bones;
    }
}

void UReflectionsNpcReactionComponent::RepairBodyPose()
{
    USkeletalMeshComponent* Body = WatchedBody.Get();
    if (!Body)
    {
        Body = FindNpcBody(GetOwner());
        WatchedBody = Body;
    }
    // Followers have no buffers of their own; a simulating body is left to physics; a task in flight means the
    // buffers are swapped on purpose.
    if (!Body || !Body->IsRegistered() || !Body->GetSkeletalMeshAsset() || Body->LeaderPoseComponent.IsValid() ||
        Body->IsAnySimulatingPhysics() || Body->IsRunningParallelEvaluation() || HasPose(Body)) return;
    const UWorld* World = GetWorld();
    const float Now = World ? World->GetTimeSeconds() : 0.0f;
    if (Now < NextPoseRepairTime || PoseRepairs >= 20) return;
    NextPoseRepairTime = Now + 0.25f;
    ++PoseRepairs;
    UE_LOG(LogTemp, Warning, TEXT("NPC %s: body bone buffers were incomplete (read %d, write %d of %d); re-registering the body (repair %d)."),
        *GetNameSafe(GetOwner()), Body->GetComponentSpaceTransforms().Num(), Body->GetEditableComponentSpaceTransforms().Num(),
        Body->GetSkeletalMeshAsset()->GetRefSkeleton().GetNum(), PoseRepairs);
    Body->ReregisterComponent();
}

const FName UReflectionsNpcReactionComponent::HitProxyTag(TEXT("NpcHitProxy"));

bool UReflectionsNpcReactionComponent::BodyPoseReady(const USkeletalMeshComponent* Body)
{
    if (HasPose(Body)) return true;
    if (Body && !bLoggedEmptyPose)
    {
        bLoggedEmptyPose = true;
        const USkeletalMesh* Asset = Body->GetSkeletalMeshAsset();
        UE_LOG(LogTemp, Warning, TEXT("NPC %s: body pose not ready (bones %d of %d, registered %d, tick %d every %.3fs, anim %s, leader %d); bone work skipped."),
            *GetNameSafe(GetOwner()), Body->GetNumComponentSpaceTransforms(), Asset ? Asset->GetRefSkeleton().GetNum() : -1,
            Body->IsRegistered() ? 1 : 0, Body->IsComponentTickEnabled() ? 1 : 0, Body->GetComponentTickInterval(),
            *GetNameSafe(Body->GetAnimInstance() ? Body->GetAnimInstance()->GetClass() : nullptr), Body->LeaderPoseComponent.IsValid() ? 1 : 0);
    }
    return false;
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

ACharacter* UReflectionsNpcReactionComponent::GetMovementCharacter() const
{
    if (ACharacter* Driver = LocomotionDriver.Get()) return Driver;
    return Cast<ACharacter>(GetOwner());
}

USkeletalMeshComponent* UReflectionsNpcReactionComponent::GetBodyMesh() const
{
    return FindNpcBody(GetOwner());
}

UReflectionsNpcArchetype* UReflectionsNpcReactionComponent::GetActiveArchetype() const
{
    return ActiveArchetype ? ActiveArchetype.Get() : Archetype.Get();
}

FVector UReflectionsNpcReactionComponent::GetAimPoint() const
{
    AActor* Owner = GetOwner();
    if (!Owner) return FVector::ZeroVector;
    if (const USkeletalMeshComponent* Body = FindNpcBody(Owner); HasPose(Body))
    {
        const FName ChestBones[] = { TEXT("spine_04"), TEXT("spine_03"), TEXT("spine_02") };
        for (const FName Bone : ChestBones)
            if (Body->GetBoneIndex(Bone) != INDEX_NONE) return Body->GetBoneLocation(Bone);
    }
    TInlineComponentArray<UCapsuleComponent*> Capsules(Owner);
    for (const UCapsuleComponent* Capsule : Capsules)
        if (Capsule && Capsule->ComponentHasTag(HitProxyTag)) return Capsule->GetComponentLocation();
    FVector Origin, Extent;
    Owner->GetActorBounds(true, Origin, Extent);
    return Origin;
}

void UReflectionsNpcReactionComponent::StartHitFlash(const FReflectionsSpellHitData& Hit)
{
    AActor* Owner = GetOwner();
    if (!Owner || !Owner->GetRootComponent() || !ReflectionsSpellCatalog::IsValid(Hit.Spell)) return;
    // A short flash in the spell's colour on the body where it was struck.
    if (!HitFlash)
    {
        HitFlash = NewObject<UPointLightComponent>(Owner);
        HitFlash->SetMobility(EComponentMobility::Movable);
        HitFlash->SetupAttachment(Owner->GetRootComponent());
        HitFlash->SetCastShadows(false);
        HitFlash->SetAttenuationRadius(260.0f);
        HitFlash->SetIntensityUnits(ELightUnits::Unitless);
        HitFlash->RegisterComponent();
    }
    const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(Hit.Spell);
    // Bystanders get a lighter flash than those who fight the player.
    HitFlashPeak = (Spec.Radius >= 180.0f ? 9000.0f : 6000.0f) * (UReflectionsNpcArchetype::IsHostileDisposition(Disposition) ? 1.0f : 0.5f);
    HitFlashRemaining = 0.22f;
    HitFlash->SetLightColor(ReflectionsSpellCatalog::ElementColor(Spec.Element));
    HitFlash->SetIntensity(HitFlashPeak);
    HitFlash->SetWorldLocation(Hit.Location + FVector(0.0, 0.0, 10.0));
    HitFlash->SetVisibility(true);
}

void UReflectionsNpcReactionComponent::StartFlinch(const FReflectionsSpellHitData& Hit)
{
    // Only walkers carried by a locomotion pawn: their rotation relative to that pawn is otherwise constant, so
    // the lean can be put on and taken back exactly. Characters are launched by the spell instead.
    AActor* Owner = GetOwner();
    USceneComponent* Root = Owner ? Owner->GetRootComponent() : nullptr;
    if (!Root || !LocomotionDriver.IsValid() || !Root->GetAttachParent()) return;
    FVector Away(Hit.Impulse.X, Hit.Impulse.Y, 0.0f);
    if (Away.IsNearlyZero() && IsValid(Hit.Caster)) Away = (Owner->GetActorLocation() - Hit.Caster->GetActorLocation()).GetSafeNormal2D();
    if (!Away.Normalize()) return;
    if (!bFlinching) FlinchRestRotation = Root->GetRelativeRotation().Quaternion();
    bFlinching = true;
    const bool bBlast = ReflectionsSpellCatalog::IsValid(Hit.Spell) && ReflectionsSpellCatalog::Get(Hit.Spell).Radius >= 180.0f;
    FlinchDuration = bBlast ? 0.55f : 0.4f;
    FlinchRemaining = FlinchDuration;
    FlinchAngle = bBlast ? 16.0f : 10.0f;
    // Tipping the head away from the impact is a turn about the horizontal axis square to it.
    FlinchAxis = FVector::CrossProduct(FVector::UpVector, Away);
}

void UReflectionsNpcReactionComponent::EndFlinch()
{
    if (!bFlinching) return;
    bFlinching = false;
    FlinchRemaining = 0.0f;
    AActor* Owner = GetOwner();
    USceneComponent* Root = Owner ? Owner->GetRootComponent() : nullptr;
    if (Root && Root->GetAttachParent()) Root->SetRelativeRotation(FlinchRestRotation);
}

bool UReflectionsNpcReactionComponent::ConsumeFreshDeath()
{
    const bool bWasFresh = bFreshDeath;
    bFreshDeath = false;
    return bWasFresh;
}

bool UReflectionsNpcReactionComponent::IsAttackable(const AActor* Candidate)
{
    const APawn* Pawn = Cast<APawn>(Candidate);
    if (!IsValid(Pawn) || !Pawn->IsPlayerControlled()) return false;
    const UReflectionsHealthComponent* Health = Pawn->FindComponentByClass<UReflectionsHealthComponent>();
    return !Health || Health->Health > 0.0f;
}

bool UReflectionsNpcReactionComponent::MayAttack(const AActor* Candidate) const
{
    return IsAttackable(Candidate) || (Candidate && EngagedTarget == Candidate) || IsPrey(Candidate);
}

bool UReflectionsNpcReactionComponent::IsPrey(const AActor* Candidate) const
{
    const UReflectionsNpcArchetype* Active = GetActiveArchetype();
    if (!Active || !IsValid(Candidate) || Candidate == GetOwner()) return false;
    const bool bDefender = Active->Combat.bFightsTarnished && !UReflectionsNpcArchetype::IsHostileDisposition(Disposition);
    if (!bDefender && !Active->Combat.bHuntsNpcs) return false;
    const UReflectionsNpcReactionComponent* Other = Candidate->FindComponentByClass<UReflectionsNpcReactionComponent>();
    // Nobody goes for one that is down or held by a set piece.
    if (!Other || Other->IsIncapacitated() || Other->IsScripted()) return false;
    // A defender of the town goes for the tarnished and for nobody else. The villain's own host is left to the
    // player (that fight is the villain session's).
    if (bDefender) return Other->Disposition == EReflectionsNpcDisposition::Infected;
    // A hunter leaves its own kind alone (anything already against the player).
    if (UReflectionsNpcArchetype::IsHostileDisposition(Other->Disposition)) return false;
    if (Active->Combat.bConvertsNpcs)
    {
        // Those who turn people leave alone whoever cannot be turned: already used up, or marked out of the
        // Tarnish's reach. The villain's conversion refuses the same ones; chasing them would only end in a
        // beating. Friendly townspeople are fair game (the villain takes them too).
        if (Other->Infection != EReflectionsNpcInfection::None) return false;
        static const FName OutOfReach[] = { TEXT("NoVillain"), TEXT("Villain_BurnedOut") };
        for (const FName& Tag : OutOfReach)
            if (Candidate->ActorHasTag(Tag)) return false;
    }
    return true;
}

AActor* UReflectionsNpcReactionComponent::FindNpcPrey(const AActor* Keep) const
{
    const UReflectionsNpcArchetype* Active = GetActiveArchetype();
    AActor* Owner = GetOwner();
    if (!Active || !Owner || !Subsystem.IsValid()) return nullptr;
    const FVector Here = Owner->GetActorLocation();
    const float Reach = FMath::Square(Active->Combat.SightRadius);
    AActor* Best = nullptr;
    float BestDistance = Reach;
    for (AActor* Candidate : Subsystem->GetNpcActors())
    {
        if (!IsPrey(Candidate)) continue;
        const float Distance = FVector::DistSquared2D(Here, Candidate->GetActorLocation());
        // The one it is already after is kept without a fresh sight check; a new one must be seen.
        if (Distance >= BestDistance || (Candidate != Keep && !HasLineOfSight(Owner, Candidate, LocomotionDriver.Get()))) continue;
        Best = Candidate;
        BestDistance = Distance;
    }
    return Best;
}

void UReflectionsNpcReactionComponent::BeginScriptedHold(float Seconds)
{
    if (IsIncapacitated() || Seconds <= 0.0f) return;
    ScriptedHoldRemaining = FMath::Max(ScriptedHoldRemaining, Seconds);
    KnockbackVelocity = FVector::ZeroVector;
    EndFlinch();
    if (Motor) Motor->SetCombatTarget(nullptr);
    if (ACharacter* Mover = GetMovementCharacter()) Mover->GetCharacterMovement()->StopMovementImmediately();
}

void UReflectionsNpcReactionComponent::EndScriptedHold()
{
    ScriptedHoldRemaining = 0.0f;
}

static TAutoConsoleVariable<int32> CVarNpcElementReactions(TEXT("Npc.ElementReactions"), 0,
    TEXT("1: a spell's hit does to a living NPC what the spell says (thrown by a blast, shoved, lifted, pulled, shocked until it drops, frozen, set alight). 0 (default until tested): the plain flinch."));

namespace
{
    // A clip made for the hidden walker's skeleton, by name, when the project has it (/Game/Combat/Melee/<Name>).
    UAnimSequence* WalkerClipNamed(const TCHAR* Name)
    {
        static TMap<FName, TWeakObjectPtr<UAnimSequence>> Known;
        static TSet<FName> Missing;
        const FName Key(Name);
        if (const TWeakObjectPtr<UAnimSequence>* Found = Known.Find(Key))
            if (Found->IsValid()) return Found->Get();
        if (Missing.Contains(Key)) return nullptr;
        const FString Package = FString::Printf(TEXT("/Game/Combat/Melee/%s"), Name);
        UAnimSequence* Clip = FPackageName::DoesPackageExist(Package)
            ? LoadObject<UAnimSequence>(nullptr, *FString::Printf(TEXT("%s.%s"), *Package, Name)) : nullptr;
        if (Clip) Known.Add(Key, Clip);
        else Missing.Add(Key);
        return Clip;
    }
}

bool UReflectionsNpcReactionComponent::PlayOnWalker(UAnimSequenceBase* Clip, float PlayRate, int32 Loops)
{
    const ACharacter* Driver = LocomotionDriver.Get();
    USkeletalMeshComponent* Mesh = Driver ? Driver->GetMesh() : nullptr;
    UAnimInstance* Anim = Mesh ? Mesh->GetAnimInstance() : nullptr;
    if (!Clip || !Anim || !Mesh->GetSkeletalMeshAsset() || Clip->GetSkeleton() != Mesh->GetSkeletalMeshAsset()->GetSkeleton()) return false;
    return Anim->PlaySlotAnimationAsDynamicMontage(Clip, TEXT("DefaultSlot"), 0.1f, 0.15f, FMath::Max(0.1f, PlayRate), FMath::Max(1, Loops)) != nullptr;
}

void UReflectionsNpcReactionComponent::ForgivePlayer()
{
    AActor* Owner = GetOwner();
    if (!Owner || IsIncapacitated() || UReflectionsNpcArchetype::IsHostileDisposition(Disposition)) return;
    ProvokedRemaining = 0.0f;
    Hostility = 0.0f;
    if (Reaction == EReflectionsNpcReaction::Attacking && IsAttackable(Focus.Get()))
        SetReaction(EReflectionsNpcReaction::Calm, nullptr, Owner->GetActorLocation());
}

void UReflectionsNpcReactionComponent::TickHeat()
{
    // The armed and lawful (guards, allied soldiers) go for a player whose heat is up, when they can see them.
    const UReflectionsNpcArchetype* Active = GetActiveArchetype();
    AActor* Owner = GetOwner();
    if (!Owner || !Active || !Subsystem.IsValid() || UReflectionsNpcArchetype::IsHostileDisposition(Disposition) || !Active->Reaction.bCanAttack ||
        !(Active->Reaction.bTurnsOnDisliked || Active->Combat.bUseMeleeMotor) || bExternallySteered) return;
    if (Subsystem->GetPlayerHeat() < 0.5f) return;
    // Busy with a quarry of its own (one of the tarnished): that comes first.
    if (bHunting && IsPrey(Focus.Get())) return;
    APawn* Player = UGameplayStatics::GetPlayerPawn(this, 0);
    if (!IsAttackable(Player) ||
        FVector::DistSquared2D(Owner->GetActorLocation(), Player->GetActorLocation()) > FMath::Square(Active->Reaction.AwarenessRadius) ||
        !HasLineOfSight(Owner, Player, LocomotionDriver.Get())) return;
    Subsystem->NoteHeatSeen();
    if (Reaction == EReflectionsNpcReaction::Attacking && Focus == Player)
    {
        ReactionTimeRemaining = FMath::Max(ReactionTimeRemaining, 2.0f);
        return;
    }
    ProvokedRemaining = FMath::Max(ProvokedRemaining, Active->Reaction.ReactionSeconds);
    SetReaction(EReflectionsNpcReaction::Attacking, Player, Player->GetActorLocation());
    Subsystem->PlayReaction(Owner, Active->VoiceCharacter == TEXT("Soldier") ? FName(TEXT("Heat_Alarm")) : FName(TEXT("Heat_Halt")));
}

bool UReflectionsNpcReactionComponent::Throw(const FVector& Velocity, bool bFirst)
{
    AActor* Owner = GetOwner();
    ACharacter* Mover = GetMovementCharacter();
    if (!Owner || !Mover || Velocity.IsNearlyZero()) return false;
    // The spell has already launched an NPC that is a character itself; the hidden walker of a dressed body it has
    // not. Either way it is the capsule that flies and the body rides it: the body is never simulated for this.
    if (Mover != Owner) Mover->LaunchCharacter(Velocity, true, true);
    KnockbackVelocity = FVector::ZeroVector;
    if (bFirst)
    {
        UAnimSequence* Stagger = WalkerClipNamed(TEXT("AS_React_Stagger_Walker"));
        if (!Stagger) Stagger = WalkerClipNamed(TEXT("AS_Melee_Sword_HitReact_Walker"));
        if (Stagger) PlayOnWalker(Stagger);
        if (Subsystem.IsValid())
            if (USoundBase* Thud = Subsystem->FindJamCue(TEXT("Cues/SCue_Body_Knockback")))
                UGameplayStatics::PlaySoundAtLocation(this, Thud, Owner->GetActorLocation() + FVector(0.0, 0.0, 60.0));
    }
    return true;
}

void UReflectionsNpcReactionComponent::StartShock(const FReflectionsSpellHitData& Hit, bool bFirst)
{
    AActor* Owner = GetOwner();
    if (!Owner || !Subsystem.IsValid()) return;
    // Shocked: it stands convulsing while the current runs through it and keeps hurting it. A hit while it is
    // already convulsing only keeps it going. How it ends is decided when the current stops (see the tick).
    ShockHit = Hit;
    ShockRemaining = FMath::Max(ShockRemaining, FMath::Clamp(Hit.Duration > 0.0f ? Hit.Duration : 1.5f, 1.0f, 2.0f));
    if (bShocked) return;
    bShocked = true;
    ShockDamageLeft = 6.0f;
    ShockTickIn = 0.5f;
    ShockFlashIn = 0.0f;
    if (ACharacter* Mover = GetMovementCharacter()) Mover->GetCharacterMovement()->StopMovementImmediately();
    if (UAnimSequence* Convulse = WalkerClipNamed(TEXT("AS_Shock_Convulse_Walker")))
        PlayOnWalker(Convulse, 1.0f, FMath::Max(1, FMath::CeilToInt(ShockRemaining / FMath::Max(0.2f, Convulse->GetPlayLength()))));
    if (!ShockLoop && Owner->GetRootComponent())
        if (USoundBase* Loop = Subsystem->FindJamCue(TEXT("Cues/SCue_Shock_Loop")))
            ShockLoop = UGameplayStatics::SpawnSoundAttached(Loop, Owner->GetRootComponent(), NAME_None, FVector(0.0, 0.0, 100.0), EAttachLocation::KeepRelativeOffset, true);
    if (bFirst) Subsystem->PlayReaction(Owner, TEXT("React_Shocked"));
}

void UReflectionsNpcReactionComponent::EndShock(bool bFell)
{
    const bool bWasShocked = bShocked;
    bShocked = false;
    ShockRemaining = 0.0f;
    ShockDamageLeft = 0.0f;
    if (ShockLoop) ShockLoop->Stop();
    ShockLoop = nullptr;
    AActor* Owner = GetOwner();
    if (bWasShocked && bFell && Owner && Subsystem.IsValid())
        if (USoundBase* Collapse = Subsystem->FindJamCue(TEXT("Cues/SCue_Shock_Collapse")))
            UGameplayStatics::PlaySoundAtLocation(this, Collapse, Owner->GetActorLocation() + FVector(0.0, 0.0, 80.0));
}

void UReflectionsNpcReactionComponent::TwitchRagdoll()
{
    USkeletalMeshComponent* Body = FindNpcBody(GetOwner());
    if (!Body || !Body->IsSimulatingPhysics()) return;
    // A small jolt through one limb of the ragdoll that is already lying there: the same kind of push a hit on a
    // body gives, only weaker. Nothing is started and nothing is re-initialised.
    static const FName Limbs[] = { TEXT("hand_l"), TEXT("hand_r"), TEXT("foot_l"), TEXT("foot_r"), TEXT("spine_03"), TEXT("head") };
    const FName Bone = Limbs[FMath::RandHelper(UE_ARRAY_COUNT(Limbs))];
    if (Body->GetBoneIndex(Bone) == INDEX_NONE) return;
    Body->WakeAllRigidBodies();
    Body->AddImpulse((FMath::VRand() + FVector(0.0, 0.0, 0.6)).GetSafeNormal() * FMath::FRandRange(90.0f, 170.0f), Bone, true);
}

void UReflectionsNpcReactionComponent::StartBurning(float Seconds, bool bFirst)
{
    AActor* Owner = GetOwner();
    if (!Owner || !Subsystem.IsValid()) return;
    const bool bAlready = BurningRemaining > 0.0f;
    BurningRemaining = FMath::Max(BurningRemaining, Seconds);
    if (bAlready) return;
    NextBurnBarkIn = FMath::FRandRange(1.5f, 2.5f);
    if (!BurnLoop && Owner->GetRootComponent())
        if (USoundBase* Loop = Subsystem->FindJamCue(TEXT("Cues/SCue_Burning_Loop")))
            BurnLoop = UGameplayStatics::SpawnSoundAttached(Loop, Owner->GetRootComponent(), NAME_None, FVector(0.0, 0.0, 100.0), EAttachLocation::KeepRelativeOffset, true);
    if (bFirst) Subsystem->PlayReaction(Owner, TEXT("React_Burning"));
}

void UReflectionsNpcReactionComponent::EndBurning()
{
    BurningRemaining = 0.0f;
    if (BurnLoop) BurnLoop->Stop();
    BurnLoop = nullptr;
}

void UReflectionsNpcReactionComponent::StartFreeze(float Seconds)
{
    // Frozen: held where it stands with its motion all but stopped. The walker's own clock is slowed, so its
    // movement and its animation (which the visible body follows) both hold; nothing about the body is changed.
    FrozenRemaining = FMath::Max(FrozenRemaining, Seconds);
    if (ACharacter* Mover = GetMovementCharacter())
    {
        Mover->GetCharacterMovement()->StopMovementImmediately();
        if (Mover != GetOwner()) Mover->CustomTimeDilation = 0.05f;
    }
}

void UReflectionsNpcReactionComponent::EndFreeze()
{
    FrozenRemaining = 0.0f;
    if (ACharacter* Mover = GetMovementCharacter())
        if (Mover != GetOwner()) Mover->CustomTimeDilation = 1.0f;
}

bool UReflectionsNpcReactionComponent::ReactToSpell(const FReflectionsSpellHitData& Hit)
{
    AActor* Owner = GetOwner();
    const UReflectionsNpcArchetype* Active = GetActiveArchetype();
    if (CVarNpcElementReactions.GetValueOnGameThread() == 0 || !Owner || !Active || !Subsystem.IsValid()) return false;
    const FVector Here = Owner->GetActorLocation();
    // Which way: along the velocity the hit gives the body, flattened; away from the blast's centre when it has none.
    FVector Along(Hit.Impulse.X, Hit.Impulse.Y, 0.0);
    if (Along.SizeSquared() < 1.0) Along = FVector(Here.X - Hit.Origin.X, Here.Y - Hit.Origin.Y, 0.0);
    Along = Along.GetSafeNormal();
    if (Along.IsNearlyZero()) Along = -Owner->GetActorForwardVector().GetSafeNormal2D();
    // How hard: the spell's own measure, 1 a full-power hit at point blank.
    const float Strength = FMath::Clamp(Hit.Magnitude, 0.1f, 1.0f);
    // A repeat tick of a lasting spell keeps the reaction going without saying or staggering again.
    const bool bFirst = !Hit.bRepeat;
    const auto Say = [this, Owner, bFirst](const TCHAR* Group)
    {
        if (bFirst) Subsystem->PlayReaction(Owner, FName(Group));
    };
    const auto Up = [](float Speed) { return FVector(0.0, 0.0, Speed); };
    switch (Hit.Reaction)
    {
    case EReflectionsSpellReaction::Explosion:
    {
        // Thrown off its feet, harder the nearer the blast. A blast of fire leaves it burning as well.
        const bool bThrown = Throw(Along * FMath::Lerp(450.0f, 1000.0f, Strength) + Up(FMath::Lerp(220.0f, 480.0f, Strength)), bFirst);
        if (ReflectionsSpellCatalog::IsValid(Hit.Spell) && ReflectionsSpellCatalog::Get(Hit.Spell).Element == EReflectionsSpellElement::Fire)
            StartBurning(3.5f, bFirst);
        else Say(TEXT("React_Knocked"));
        return bThrown;
    }
    case EReflectionsSpellReaction::Push:
    {
        const bool bThrown = Throw(Along * FMath::Lerp(500.0f, 950.0f, Strength) + Up(170.0f), bFirst);
        Say(TEXT("React_Knocked"));
        return bThrown;
    }
    case EReflectionsSpellReaction::Knockdown:
    {
        const bool bThrown = Throw(Along * FMath::Lerp(300.0f, 600.0f, Strength) + Up(280.0f), bFirst);
        Say(TEXT("React_Knocked"));
        return bThrown;
    }
    case EReflectionsSpellReaction::Lift:
    {
        const bool bThrown = Throw(Along * FMath::Lerp(150.0f, 400.0f, Strength) + Up(FMath::Lerp(480.0f, 760.0f, Strength)), bFirst);
        Say(TEXT("React_Knocked"));
        return bThrown;
    }
    case EReflectionsSpellReaction::Pull:
    {
        // Drawn toward the centre; the spell sends this again about twice a second while it lasts.
        const FVector Toward = FVector(Hit.Origin.X - Here.X, Hit.Origin.Y - Here.Y, 0.0).GetSafeNormal();
        const bool bThrown = !Toward.IsNearlyZero() && Throw(Toward * FMath::Lerp(300.0f, 600.0f, Strength) + Up(120.0f), bFirst);
        Say(TEXT("React_Knocked"));
        return bThrown;
    }
    case EReflectionsSpellReaction::Electrify:
        StartShock(Hit, bFirst);
        return false;
    case EReflectionsSpellReaction::Freeze:
        StartFreeze(FMath::Clamp(Hit.Duration > 0.0f ? Hit.Duration : 2.0f, 1.0f, 3.0f));
        Say(TEXT("React_Hurt"));
        return false;
    case EReflectionsSpellReaction::Burn:
        StartBurning(FMath::Clamp(Hit.Duration + 1.0f, 2.5f, 5.0f), bFirst);
        return false;
    default:
        Say(TEXT("React_Hurt"));
        return false;
    }
}

void UReflectionsNpcReactionComponent::RefreshWeaponProp()
{
    AActor* Owner = GetOwner();
    const UReflectionsNpcArchetype* Active = GetActiveArchetype();
    UStaticMesh* Mesh = Active ? Active->Combat.WeaponProp.LoadSynchronous() : nullptr;
    USkeletalMeshComponent* Body = Owner ? FindNpcBody(Owner) : nullptr;
    if (!Mesh || !Body || Body->GetBoneIndex(TEXT("hand_r")) == INDEX_NONE)
    {
        if (WeaponProp) WeaponProp->DestroyComponent();
        WeaponProp = nullptr;
        return;
    }
    if (!WeaponProp)
    {
        WeaponProp = NewObject<UStaticMeshComponent>(Owner, NAME_None, RF_Transient);
        WeaponProp->SetMobility(EComponentMobility::Movable);
        WeaponProp->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        WeaponProp->SetGenerateOverlapEvents(false);
        WeaponProp->SetCanEverAffectNavigation(false);
        WeaponProp->ComponentTags.Add(TEXT("NpcRuntime"));
        WeaponProp->RegisterComponent();
        // The grip the melee set was made for: a weapon_r socket where the skeleton has one, else the same
        // offset on the hand bone (the crafting session's numbers, +X along the blade).
        const bool bSocket = Body->DoesSocketExist(TEXT("weapon_r"));
        WeaponProp->AttachToComponent(Body, FAttachmentTransformRules::SnapToTargetNotIncludingScale, bSocket ? FName(TEXT("weapon_r")) : FName(TEXT("hand_r")));
        if (!bSocket) WeaponProp->SetRelativeLocationAndRotation(FVector(-3.8, -0.1, 0.1), FRotator(73.2, -142.3, 0.0));
    }
    WeaponProp->SetStaticMesh(Mesh);
}

void UReflectionsNpcReactionComponent::FaceTowards(const AActor* Target, float DeltaTime)
{
    AActor* Owner = GetOwner();
    if (!Owner || !Target) return;
    const FVector Direction = (Target->GetActorLocation() - Owner->GetActorLocation()).GetSafeNormal2D();
    if (Direction.IsNearlyZero()) return;
    // A walking NPC is turned through its walker (the body is attached to it); anything else turns itself.
    AActor* Turner = LocomotionDriver.IsValid() ? static_cast<AActor*>(LocomotionDriver.Get()) : Owner;
    Turner->SetActorRotation(FMath::RInterpTo(Turner->GetActorRotation(), FRotator(0.0, Direction.Rotation().Yaw, 0.0), DeltaTime, 8.0f));
}

namespace
{
    // spell-combat's tarnish magic (UReflectionsTarnishCasterComponent) is called by name, so neither side's build
    // depends on the other's header. Its spells: 0 bolt, 1 slow homing wisp, 2 burst around the caster.
    struct FTarnishStartCast
    {
        uint8 Spell = 0;
        AActor* Target = nullptr;
        bool ReturnValue = false;
    };
    struct FTarnishSpellFloat
    {
        uint8 Spell = 0;
        float ReturnValue = 0.0f;
    };

    UFunction* TarnishFunction(UObject* Caster, const TCHAR* Name, int32 NumParms, int32 MaxSize)
    {
        UFunction* Function = Caster ? Caster->FindFunction(Name) : nullptr;
        return Function && Function->NumParms == NumParms && Function->ParmsSize <= MaxSize ? Function : nullptr;
    }

    bool StartTarnishCast(UObject* Caster, uint8 Spell, AActor* Target)
    {
        UFunction* Function = TarnishFunction(Caster, TEXT("StartCast"), 3, sizeof(FTarnishStartCast));
        if (!Function || !CastField<FBoolProperty>(Function->GetReturnProperty())) return false;
        FTarnishStartCast Params;
        Params.Spell = Spell;
        Params.Target = Target;
        Caster->ProcessEvent(Function, &Params);
        return Params.ReturnValue;
    }

    float TarnishWindup(UObject* Caster, uint8 Spell, float Fallback)
    {
        UFunction* Function = TarnishFunction(Caster, TEXT("GetWindup"), 2, sizeof(FTarnishSpellFloat));
        if (!Function || !CastField<FFloatProperty>(Function->GetReturnProperty())) return Fallback;
        FTarnishSpellFloat Params;
        Params.Spell = Spell;
        Caster->ProcessEvent(Function, &Params);
        return Params.ReturnValue > 0.05f ? Params.ReturnValue : Fallback;
    }
}

UActorComponent* UReflectionsNpcReactionComponent::FindOrAddTarnishCaster()
{
    if (TarnishCaster) return TarnishCaster;
    AActor* Owner = GetOwner();
    UClass* CasterClass = FindObject<UClass>(nullptr, TEXT("/Script/reflections.ReflectionsTarnishCasterComponent"));
    if (!Owner || !CasterClass || !CasterClass->IsChildOf(UActorComponent::StaticClass()) || CasterClass->HasAnyClassFlags(CLASS_Abstract)) return nullptr;
    TarnishCaster = Owner->FindComponentByClass(CasterClass);
    if (!TarnishCaster)
    {
        TarnishCaster = NewObject<UActorComponent>(Owner, CasterClass, NAME_None, RF_Transient);
        TarnishCaster->ComponentTags.Add(TEXT("NpcRuntime"));
        TarnishCaster->RegisterComponent();
    }
    return TarnishCaster;
}

void UReflectionsNpcReactionComponent::CancelTarnishCast()
{
    if (!bCastByTarnishCaster) return;
    bCastByTarnishCaster = false;
    if (UFunction* Cancel = TarnishFunction(TarnishCaster, TEXT("CancelCast"), 0, 0)) TarnishCaster->ProcessEvent(Cancel, nullptr);
}

void UReflectionsNpcReactionComponent::EndCastTelegraph()
{
    if (CastLight) CastLight->DestroyComponent();
    if (CastGlow) CastGlow->DestroyComponent();
    CastLight = nullptr;
    CastGlow = nullptr;
}

bool UReflectionsNpcReactionComponent::TickSpellcasting(float DeltaTime)
{
    const UReflectionsNpcArchetype* Active = GetActiveArchetype();
    AActor* Owner = GetOwner();
    AActor* Target = Focus.Get();
    CastCooldownRemaining = FMath::Max(0.0f, CastCooldownRemaining - DeltaTime);
    const bool bMay = Owner && Active && Active->Combat.bCastsAtPlayer && Active->Combat.RangedSpells.Num() > 0 &&
        Active->Reaction.bCanAttack && Reaction == EReflectionsNpcReaction::Attacking && !bExternallySteered && IsAttackable(Target);
    if (!bMay)
    {
        CastWindupRemaining = 0.0f;
        EndCastTelegraph();
        CancelTarnishCast();
        return false;
    }
    ACharacter* Mover = GetMovementCharacter();
    if (CastWindupRemaining > 0.0f)
    {
        // Committed: it stands, keeps facing its target while the glow builds, then lets go. The telegraph is
        // the player's cue to move.
        if (Mover) Mover->GetCharacterMovement()->StopMovementImmediately();
        FaceTowards(Target, DeltaTime);
        CastWindupRemaining -= DeltaTime;
        const float Alpha = 1.0f - FMath::Clamp(CastWindupRemaining / FMath::Max(0.05f, CastWindupLength), 0.0f, 1.0f);
        if (CastLight) CastLight->SetIntensity(FMath::Lerp(400.0f, 9000.0f, Alpha * Alpha));
        if (CastGlow) CastGlow->SetVariableFloat(TEXT("User.Scale"), FMath::Lerp(0.15f, 0.6f, Alpha));
        if (CastWindupRemaining <= 0.0f)
        {
            // The tarnish caster lets go by itself at the end of its own wind-up; the fallback is released here.
            if (!bCastByTarnishCaster) ReleaseSpell(Target);
            bCastByTarnishCaster = false;
            EndCastTelegraph();
            CastCooldownRemaining = FMath::FRandRange(Active->Combat.RangedCooldown.X, FMath::Max(Active->Combat.RangedCooldown.X, Active->Combat.RangedCooldown.Y));
        }
        return true;
    }
    // In range with a clear line it stops here. Nearer than half the near range the melee motor takes over;
    // farther than the far range, or with something in the way, it keeps closing in.
    const float Distance = FVector::Dist2D(Owner->GetActorLocation(), Target->GetActorLocation());
    UActorComponent* Caster = FindOrAddTarnishCaster();
    // Right on top of the player: the Tarnish's burst, when that magic is in the build and the cooldown is up.
    // Without it the melee motor claws instead.
    const bool bBurst = Caster && Distance <= 300.0f && CastCooldownRemaining <= 0.0f;
    if (!bBurst && (Distance > Active->Combat.RangedMaxRange || Distance < Active->Combat.RangedMinRange * 0.5f ||
        !HasLineOfSight(Owner, Target, LocomotionDriver.Get()))) return false;
    if (Mover) Mover->GetCharacterMovement()->StopMovementImmediately();
    FaceTowards(Target, DeltaTime);
    if (CastCooldownRemaining > 0.0f) return true;

    // Begin a cast: pick the spell, start the glow in front of the chest, mutter.
    PendingSpell = Active->Combat.RangedSpells[FMath::RandHelper(Active->Combat.RangedSpells.Num())];
    bPendingHoming = FMath::FRand() < Active->Combat.RangedHomingChance;
    CastWindupLength = FMath::Max(0.2f, Active->Combat.RangedWindup);
    CastWindupRemaining = CastWindupLength;
    // The Tarnish's own magic first (spell-combat's caster: its wind-up effects, projectile and damage). It
    // lets go by itself; this NPC only stands and faces for as long as that wind-up takes.
    const uint8 TarnishSpell = bBurst ? 2 : bPendingHoming ? 1 : 0;
    if (Caster && StartTarnishCast(Caster, TarnishSpell, Target))
    {
        bCastByTarnishCaster = true;
        CastWindupLength = TarnishWindup(Caster, TarnishSpell, CastWindupLength) + 0.1f;
        CastWindupRemaining = CastWindupLength;
        EndCastTelegraph();
        if (UAnimSequence* Gesture = Active->Combat.WalkerCastAnimation.LoadSynchronous())
            PlayOnWalker(Gesture, FMath::Clamp(Gesture->GetPlayLength() * 0.5f / CastWindupLength, 0.5f, 2.0f));
        if (Subsystem.IsValid() && !Active->BarkOnAttack.IsNone()) Subsystem->PlayBark(Owner, Active->BarkOnAttack);
        return true;
    }
    if (bBurst && Distance < Active->Combat.RangedMinRange * 0.5f)
    {
        // No burst to be had after all: back to the claws.
        CastWindupRemaining = 0.0f;
        return false;
    }
    const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(PendingSpell);
    // The Tarnish's magic is the spell's own colour, darkened.
    FLinearColor Color = ReflectionsSpellCatalog::ElementColor(Spec.Element) * 0.6f;
    Color.A = 1.0f;
    USceneComponent* Root = Owner->GetRootComponent();
    // In the body's own space: the crowd looks face along their +Y and ride on the walker.
    const FVector Offset = LocomotionDriver.IsValid() ? FVector(0.0, 45.0, 125.0) : FVector(45.0, 0.0, 125.0);
    EndCastTelegraph();
    if (Root)
    {
        CastLight = NewObject<UPointLightComponent>(Owner, NAME_None, RF_Transient);
        CastLight->SetMobility(EComponentMobility::Movable);
        CastLight->SetCastShadows(false);
        CastLight->SetLightColor(Color);
        CastLight->SetIntensity(400.0f);
        CastLight->SetAttenuationRadius(420.0f);
        CastLight->RegisterComponent();
        CastLight->AttachToComponent(Root, FAttachmentTransformRules::KeepRelativeTransform);
        CastLight->SetRelativeLocation(Offset);
        static TWeakObjectPtr<UNiagaraSystem> GlowSystem;
        if (!GlowSystem.IsValid())
            GlowSystem = LoadObject<UNiagaraSystem>(nullptr, TEXT("/Game/Characters/Hero/SpellVFX/Systems/NS_Spell_Projectile.NS_Spell_Projectile"));
        if (GlowSystem.IsValid())
        {
            CastGlow = UNiagaraFunctionLibrary::SpawnSystemAttached(GlowSystem.Get(), Root, NAME_None, Offset, FRotator::ZeroRotator,
                EAttachLocation::KeepRelativeOffset, false, true, ENCPoolMethod::None, true);
            if (CastGlow)
            {
                CastGlow->SetVariableLinearColor(TEXT("User.Color"), Color);
                CastGlow->SetVariableLinearColor(TEXT("User.Color2"), Color * 0.5f);
                CastGlow->SetVariableFloat(TEXT("User.Scale"), 0.15f);
                CastGlow->SetVariableFloat(TEXT("User.CoreSize"), 18.0f);
            }
        }
    }
    // The gesture, when the project has one for the walker's skeleton, timed to end with the windup.
    if (UAnimSequence* Gesture = Active->Combat.WalkerCastAnimation.LoadSynchronous())
        PlayOnWalker(Gesture, FMath::Clamp(Gesture->GetPlayLength() * 0.5f / CastWindupLength, 0.5f, 2.0f));
    if (Subsystem.IsValid() && !Active->BarkOnAttack.IsNone()) Subsystem->PlayBark(Owner, Active->BarkOnAttack);
    return true;
}

void UReflectionsNpcReactionComponent::ReleaseSpell(AActor* Target)
{
    // The same projectile the player's and the squads' spells use, so damage, impact effects, sound and the
    // spell events all come from the one spell path.
    AActor* Owner = GetOwner();
    UWorld* World = GetWorld();
    const UReflectionsNpcArchetype* Active = GetActiveArchetype();
    if (!Owner || !World || !Active || !IsValid(Target)) return;
    const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(PendingSpell);
    const FVector Forward = (Target->GetActorLocation() - Owner->GetActorLocation()).GetSafeNormal2D();
    // Chest height, a step in front. A walking NPC's origin is at its feet; anything else's is its middle.
    const FVector Origin = Owner->GetActorLocation() + FVector(0.0, 0.0, LocomotionDriver.IsValid() ? 125.0 : 35.0) + Forward * 55.0;
    // A wisp is slow and follows; a bolt is fast, led a little by where the target is going, and not perfectly true.
    const float Speed = FMath::Max(100.0f, Spec.Speed) * (bPendingHoming ? 0.45f : 1.0f);
    FVector Aim = Target->GetActorLocation() + FVector(0.0, 0.0, 25.0);
    if (!bPendingHoming)
    {
        const FVector Velocity = Target->GetVelocity();
        Aim += FVector(Velocity.X, Velocity.Y, 0.0) * (FVector::Dist(Aim, Origin) / Speed) * 0.5f;
        Aim += FMath::VRand() * FMath::FRandRange(0.0f, 40.0f);
    }
    FVector Direction = (Aim - Origin).GetSafeNormal();
    if (Direction.IsNearlyZero()) Direction = Forward;
    const FTransform Launch(Direction.Rotation(), Origin);
    AReflectionsSpellProjectile* Projectile = World->SpawnActorDeferred<AReflectionsSpellProjectile>(
        AReflectionsSpellProjectile::StaticClass(), Launch, Owner, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
    if (Projectile)
    {
        Projectile->Initialize(PendingSpell, Spec.Power * Active->Combat.RangedDamageScale, Speed,
            FMath::Max(Spec.Range, Active->Combat.RangedMaxRange + 400.0f), nullptr, nullptr);
        Projectile->FinishSpawning(Launch);
        if (bPendingHoming) Projectile->SetHomingTarget(Target);
        if (UPrimitiveComponent* Collision = Cast<UPrimitiveComponent>(Projectile->GetRootComponent()))
        {
            // It must not go off on the caster itself.
            Collision->IgnoreActorWhenMoving(Owner, true);
            if (ACharacter* Driver = LocomotionDriver.Get()) Collision->IgnoreActorWhenMoving(Driver, true);
        }
    }
    if (UReflectionsSpellEventSubsystem* Events = World->GetSubsystem<UReflectionsSpellEventSubsystem>())
        Events->OnSpellReleaseVisual.Broadcast(PendingSpell, Origin, Direction, Owner, 0.35f + Spec.Radius / 600.0f);
}

void UReflectionsNpcReactionComponent::TickRemark(float DeltaTime)
{
    // A calm townsperson says a line of its own when the player comes within a few steps: looked at twice a
    // second, each NPC at most once a minute or so, and the subsystem lets only one remark play at a time.
    RemarkCheckIn -= DeltaTime;
    if (RemarkCheckIn > 0.0f) return;
    RemarkCheckIn = 0.5f;
    const UWorld* World = GetWorld();
    const AActor* Owner = GetOwner();
    if (!World || !Owner || !Subsystem.IsValid() || bRemarksMuted || Infection != EReflectionsNpcInfection::None ||
        UReflectionsNpcArchetype::IsHostileDisposition(Disposition)) return;
    const float Now = World->GetTimeSeconds();
    // Nobody greets the player the instant the map starts.
    if (NextRemarkTime <= 0.0f) NextRemarkTime = Now + FMath::FRandRange(4.0f, 20.0f);
    if (Now < NextRemarkTime) return;
    const APawn* Player = UGameplayStatics::GetPlayerPawn(this, 0);
    if (!IsAttackable(Player) || FVector::DistSquared2D(Owner->GetActorLocation(), Player->GetActorLocation()) > FMath::Square(450.0f)) return;
    if (Subsystem->TryPlayRemark(this)) NextRemarkTime = Now + FMath::FRandRange(60.0f, 90.0f);
}

void UReflectionsNpcReactionComponent::SetVoiceOverride(FName InVoiceId)
{
    if (InVoiceId.IsNone())
    {
        ClearVoiceOverride();
        return;
    }
    if (!bVoiceOverridden)
    {
        OwnVoiceId = VoiceId;
        OwnGeminiVoice = GeminiVoice;
        bVoiceOverridden = true;
    }
    VoiceId = InVoiceId;
    FReflectionsNpcVoiceRow Row;
    GeminiVoice = Subsystem.IsValid() && Subsystem->FindVoiceRow(InVoiceId, Row) ? Row.GeminiVoice : FString();
}

void UReflectionsNpcReactionComponent::ClearVoiceOverride()
{
    if (!bVoiceOverridden) return;
    bVoiceOverridden = false;
    VoiceId = OwnVoiceId;
    GeminiVoice = OwnGeminiVoice;
}

void UReflectionsNpcReactionComponent::Engage(AActor* Target)
{
    if (Target == GetOwner()) Target = nullptr;
    const bool bHadOrder = EngagedTarget.IsValid();
    EngagedTarget = Target;
    if (IsIncapacitated() || !HasBegunPlay()) return;
    if (Target) SetReaction(EReflectionsNpcReaction::Attacking, Target, Target->GetActorLocation());
    else if (bHadOrder && Reaction == EReflectionsNpcReaction::Attacking)
        SetReaction(EReflectionsNpcReaction::Calm, nullptr, GetOwner()->GetActorLocation());
}

void UReflectionsNpcReactionComponent::SetExternallySteered(bool bSteered)
{
    bExternallySteered = bSteered;
    if (bSteered && Motor) Motor->SetCombatTarget(nullptr);
}

bool UReflectionsNpcReactionComponent::UpdateEngagement()
{
    AActor* Ordered = EngagedTarget.Get();
    if (!Ordered) return false;
    const UReflectionsHealthComponent* Health = Ordered->FindComponentByClass<UReflectionsHealthComponent>();
    if (Health && Health->Health <= 0.0f)
    {
        // The ordered target is down: the order is done.
        EngagedTarget.Reset();
        if (Reaction == EReflectionsNpcReaction::Attacking && Focus == Ordered)
            SetReaction(EReflectionsNpcReaction::Calm, nullptr, GetOwner()->GetActorLocation());
        return false;
    }
    // Driven off for a moment (a hit that made it run) is allowed; otherwise it stays on the ordered target.
    if (Reaction == EReflectionsNpcReaction::Fleeing) return true;
    if (Reaction != EReflectionsNpcReaction::Attacking || !Focus.IsValid())
        SetReaction(EReflectionsNpcReaction::Attacking, Ordered, Ordered->GetActorLocation());
    // Provoked by someone else (it was hit): that reaction runs its time, then it returns to the ordered target.
    else if (Focus == Ordered) ReactionTimeRemaining = FMath::Max(ReactionTimeRemaining, 1.0f);
    return true;
}

// Both default on; they exist so the performance session can measure with and without (read when an NPC gets its walker).
static TAutoConsoleVariable<int32> CVarNpcWalkerFoley(TEXT("Npc.WalkerFoley"), 0,
    TEXT("1: the hidden walker pawns of NPCs play the animation sample's foley sounds (footsteps). 0 (default): silent."));
static TAutoConsoleVariable<int32> CVarNpcLeanFollowers(TEXT("Npc.LeanFollowerParts"), 1,
    TEXT("1 (default): an NPC's outfit and face parts that follow the body's pose take the body's bounds and raise no overlap events. 0: as authored."));

bool UReflectionsNpcReactionComponent::HasLineOfSight(const AActor* From, const AActor* To, const AActor* ExtraIgnored)
{
    const UWorld* World = From ? From->GetWorld() : nullptr;
    if (!World || !To) return false;
    // Eye height to the target, against the static world only: other NPCs (their hit capsules block the
    // Visibility channel) and knee-high props must not hide the target, or the back rank of a group never moves.
    const FVector Start = From->GetActorLocation() + FVector(0.0, 0.0, 150.0);
    // To the target's chest. A pawn's origin is the middle of its capsule already; an NPC actor's origin is at
    // its feet, on the floor, where the floor itself would end the trace and hide it (seen on train #6: hunters
    // ignored townspeople standing next to them and the melee motor would not walk towards them).
    FVector End = To->GetActorLocation();
    if (!To->IsA<APawn>()) End.Z += 110.0;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(NpcSight), false, From);
    if (ExtraIgnored) Params.AddIgnoredActor(ExtraIgnored);
    Params.AddIgnoredActor(To);
    FHitResult Hit;
    return !World->LineTraceSingleByObjectType(Hit, Start, End, FCollisionObjectQueryParams(ECC_WorldStatic), Params);
}

void UReflectionsNpcReactionComponent::BeginPlay()
{
    Super::BeginPlay();
    AActor* Owner = GetOwner();
    Subsystem = UReflectionsNpcSubsystem::Get(this);
    if (!Archetype && Subsystem.IsValid()) Archetype = Subsystem->ResolveArchetype(Owner);
    bEnableRagdollOnDeath |= Owner->ActorHasTag(TEXT("NPC_Ragdoll"));
    bUseSampleLocomotion |= Owner->ActorHasTag(TEXT("NPC_SampleLocomotion"));
    HomeLocation = Owner->GetActorLocation();
    RefreshActiveArchetype();
    if (UReflectionsHealthComponent* Health = Owner->FindComponentByClass<UReflectionsHealthComponent>())
    {
        LastKnownHealth = Health->Health > 0.0f ? Health->Health : Health->MaxHealth;
        Health->OnDeath.AddUniqueDynamic(this, &UReflectionsNpcReactionComponent::OnOwnerDied);
        Health->OnHealthChanged.AddUniqueDynamic(this, &UReflectionsNpcReactionComponent::OnHealthChanged);
    }
    if (Subsystem.IsValid()) Subsystem->RegisterNpc(this);
    ConfigureMotor();
}

void UReflectionsNpcReactionComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    if (HitMesh.IsValid()) EndPhysicalHit();
    EndFlinch();
    if (Reason == EEndPlayReason::Destroyed)
        if (ACharacter* Driver = LocomotionDriver.Get()) Driver->Destroy();
    if (AActor* Owner = GetOwner())
        if (UReflectionsHealthComponent* Health = Owner->FindComponentByClass<UReflectionsHealthComponent>())
        {
            Health->OnDeath.RemoveDynamic(this, &UReflectionsNpcReactionComponent::OnOwnerDied);
            Health->OnHealthChanged.RemoveDynamic(this, &UReflectionsNpcReactionComponent::OnHealthChanged);
        }
    if (Subsystem.IsValid()) Subsystem->UnregisterNpc(this);
    Super::EndPlay(Reason);
}

// ---- Archetype and infection -------------------------------------------------------------------------------

void UReflectionsNpcReactionComponent::RefreshActiveArchetype()
{
    const bool bTaken = Infection == EReflectionsNpcInfection::Infected || Infection == EReflectionsNpcInfection::VillainHost;
    ActiveArchetype = bTaken && TakenArchetype ? TakenArchetype.Get() : Archetype.Get();
    if (ActiveArchetype) Disposition = ActiveArchetype->Disposition;
}

void UReflectionsNpcReactionComponent::SetArchetype(UReflectionsNpcArchetype* NewArchetype)
{
    if (!NewArchetype || NewArchetype == Archetype) return;
    Archetype = NewArchetype;
    RefreshActiveArchetype();
    if (HasBegunPlay()) ConfigureMotor();
}

bool UReflectionsNpcReactionComponent::ApplyInfection(EReflectionsNpcInfection NewState, UReflectionsNpcArchetype* InTakenArchetype)
{
    if (NewState == Infection) return false;
    const auto IsTaken = [](EReflectionsNpcInfection State)
    {
        return State == EReflectionsNpcInfection::Infected || State == EReflectionsNpcInfection::VillainHost;
    };
    const bool bWasTaken = IsTaken(Infection);
    const bool bTaken = IsTaken(NewState);
    Infection = NewState;
    TakenArchetype = bTaken ? InTakenArchetype : nullptr;
    if (AActor* Owner = GetOwner())
    {
        // One of his is no longer an ally: aim assist may pick it and ally heals skip it.
        if (bTaken && !bWasTaken)
        {
            bHadFriendlyTag = Owner->ActorHasTag(TEXT("Friendly"));
            Owner->Tags.Remove(FName(TEXT("Friendly")));
        }
        else if (!bTaken && bWasTaken && bHadFriendlyTag) Owner->Tags.AddUnique(FName(TEXT("Friendly")));
        // What the taken archetype grants (blood, for one) lasts only while it is taken.
        for (const FName& Tag : TakenTagsAdded) Owner->Tags.Remove(Tag);
        TakenTagsAdded.Reset();
        if (bTaken && TakenArchetype)
            for (const FName& Tag : TakenArchetype->GrantedTags)
                if (!Owner->Tags.Contains(Tag))
                {
                    Owner->Tags.Add(Tag);
                    TakenTagsAdded.Add(Tag);
                }
    }
    RefreshActiveArchetype();
    Fear = 0.0f; Hostility = 0.0f; bHunting = false; ProvokedRemaining = 0.0f;
    if (HasBegunPlay())
    {
        if (!IsIncapacitated()) SetReaction(EReflectionsNpcReaction::Calm, nullptr, GetOwner()->GetActorLocation());
        ConfigureMotor();
    }
    return true;
}

void UReflectionsNpcReactionComponent::ConfigureMotor()
{
    AActor* Owner = GetOwner();
    const UReflectionsNpcArchetype* Active = GetActiveArchetype();
    if (!Owner || !Active) return;
    const bool bNeedsMotor = Active->Combat.bUseMeleeMotor && Active->Reaction.bCanAttack;
    if (!Motor) Motor = Owner->FindComponentByClass<UReflectionsNpcCombatComponent>();
    if (!Motor && bNeedsMotor)
    {
        const FName MotorName(TEXT("RuntimeNpcCombat"));
        Motor = NewObject<UReflectionsNpcCombatComponent>(Owner, StaticFindObjectFast(nullptr, Owner, MotorName)
            ? MakeUniqueObjectName(Owner, UReflectionsNpcCombatComponent::StaticClass(), MotorName) : MotorName);
        Motor->ComponentTags.Add(TEXT("NpcRuntime"));
        Motor->RegisterComponent();
    }
    RefreshWeaponProp();
    if (!Motor) return;
    Motor->Configure(Active->Combat, this);
    Motor->AddTickPrerequisiteComponent(this);
    if (!bNeedsMotor) Motor->SetCombatTarget(nullptr);
}

// ---- Reactions ---------------------------------------------------------------------------------------------

void UReflectionsNpcReactionComponent::SetReaction(EReflectionsNpcReaction Next, AActor* Cause, FVector EventLocation)
{
    if (Reaction == EReflectionsNpcReaction::Incapacitated) return;
    const UReflectionsNpcArchetype* Active = GetActiveArchetype();
    const FReflectionsNpcReactionProfile DefaultProfile;
    const FReflectionsNpcReactionProfile& Profile = Active ? Active->Reaction : DefaultProfile;
    Focus = Cause; ThreatLocation = EventLocation;
    ReactionTimeRemaining = Next == EReflectionsNpcReaction::Alert ? Profile.AlertSeconds : Profile.ReactionSeconds;
    if (Reaction != Next)
    {
        Reaction = Next;
        OnReactionChanged.Broadcast(Reaction, Cause, EventLocation);
        if (Subsystem.IsValid()) Subsystem->NotifyReaction(this, Reaction, Cause, EventLocation);
    }
    if (Next == EReflectionsNpcReaction::Fleeing)
        SafeDestination = UReflectionsNpcArchetype::FleeDestination(Profile, GetOwner()->GetActorLocation(), EventLocation,
            -GetOwner()->GetActorForwardVector(), GetTypeHash(GetOwner()->GetFName()));
}

void UReflectionsNpcReactionComponent::ReceiveStimulus(const FReflectionsNpcStimulus& Stimulus, float InstigatorReputation)
{
    AActor* Owner = GetOwner();
    const UReflectionsNpcArchetype* Active = GetActiveArchetype();
    AActor* Instigator = Stimulus.Instigator.Get();
    if (!IsValid(Owner) || !Active || Instigator == Owner || IsIncapacitated() || IsScripted()) return;
    // Someone turning is no news to those already against the player: they keep hunting instead of going to look.
    if (Stimulus.Kind == EReflectionsNpcStimulusKind::Infection && UReflectionsNpcArchetype::IsHostileDisposition(Disposition)) return;

    EReflectionsNpcReaction Next = EReflectionsNpcReaction::Alert;
    if (!UReflectionsNpcArchetype::EvaluateStimulus(Active->Reaction, Stimulus, Owner->GetActorLocation(),
            InstigatorReputation, Fear, Hostility, Next)) return;
    // Already fighting someone: noise does not pull it off its target.
    if (Reaction == EReflectionsNpcReaction::Attacking && Focus.IsValid() && Next != EReflectionsNpcReaction::Attacking)
        return;
    const bool bFight = Next == EReflectionsNpcReaction::Attacking || Next == EReflectionsNpcReaction::Defending;
    // Nobody it could fight caused this: go and look instead.
    if (bFight && !MayAttack(Instigator)) Next = EReflectionsNpcReaction::Investigating;
    else if (bFight) ProvokedRemaining = Active->Reaction.ReactionSeconds;
    SetReaction(Next, Instigator, Stimulus.Location);
}

void UReflectionsNpcReactionComponent::ReceiveSpellHit(const FReflectionsSpellHitData& Hit)
{
    AActor* Owner = GetOwner();
    const UReflectionsNpcArchetype* Active = GetActiveArchetype();
    if (!IsValid(Owner) || !Active) return;
    if (IsIncapacitated())
    {
        // The hit that killed it (health is spent before the hit event) or a later hit on the body.
        StartHitFlash(Hit);
        KickRagdoll(Hit);
        // Lightning on a body that is down (the bolt that killed it included): it twitches where it lies.
        if (Hit.Reaction == EReflectionsSpellReaction::Electrify && CVarNpcElementReactions.GetValueOnGameThread() != 0)
        {
            ShockHit = Hit;
            CorpseShockRemaining = FMath::Max(CorpseShockRemaining, 1.2f);
            ShockFlashIn = 0.0f;
        }
        return;
    }
    StartHitFlash(Hit);
    // Held by a set piece: it is hurt (the damage has landed) but does not move or change its mind.
    if (IsScripted()) return;
    StartPhysicalHit(Hit);
    StartFlinch(Hit);
    // The spell says what the body does (thrown, shocked, set alight...). Thrown that way, nothing pushes it twice.
    if (!ReactToSpell(Hit) && !Cast<ACharacter>(Owner))
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
            : HorizontalImpulse.GetSafeNormal() * FMath::Clamp(HorizontalImpulse.Size() * 2.5f, 300.0f, 900.0f);
    }
    EReflectionsNpcReaction Next = UReflectionsNpcArchetype::EvaluateHit(Active->Reaction, Fear, Hostility);
    if (Next == EReflectionsNpcReaction::Attacking && !MayAttack(Hit.Caster)) Next = EReflectionsNpcReaction::Fleeing;
    // On fire: those who do not fight back run, whatever they would have done.
    if (BurningRemaining > 0.0f && !Active->Reaction.bFightsBack) Next = EReflectionsNpcReaction::Fleeing;
    if (Active->Reaction.FleeBelowHealthFraction > 0.0f)
        if (const UReflectionsHealthComponent* Health = Owner->FindComponentByClass<UReflectionsHealthComponent>())
            if (Health->Health <= Health->MaxHealth * Active->Reaction.FleeBelowHealthFraction) Next = EReflectionsNpcReaction::Fleeing;
    if (Next == EReflectionsNpcReaction::Attacking) ProvokedRemaining = Active->Reaction.ReactionSeconds;
    SetReaction(Next, Hit.Caster, Hit.Location);
}

// ---- Hit physics and death ---------------------------------------------------------------------------------

bool UReflectionsNpcReactionComponent::StartPhysicalHit(const FReflectionsSpellHitData& Hit)
{
    // Refused for now, whatever the archetype or the actor asks: on the crowd bodies this partial simulation
    // loses the body's bone buffers, which twice took the editor down (11:53 and 12:16 on 2026-11-14). The code
    // below stays for when it is proven safe on a body type; flip this flag then.
    static bool bPartialPhysicsFlinchIsSafe = false;
    if (!bPartialPhysicsFlinchIsSafe) return false;
    const UReflectionsNpcArchetype* Active = GetActiveArchetype();
    if (!bEnablePhysicalHitReaction || (Active && !Active->bPhysicalHitReaction)) return false;
    USkeletalMeshComponent* Mesh = FindNpcBody(GetOwner());
    if (!Mesh || !Mesh->GetPhysicsAsset() || Mesh->IsSimulatingPhysics() || !BodyPoseReady(Mesh)) return false;
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

bool UReflectionsNpcReactionComponent::StartRagdoll()
{
    USkeletalMeshComponent* Mesh = FindNpcBody(GetOwner());
    if (!CanRagdoll(Mesh) || !BodyPoseReady(Mesh)) return false;
    // A physics body that rests on the world, lets pawns walk through and no longer stops aim traces.
    Mesh->SetCollisionObjectType(ECC_PhysicsBody);
    Mesh->SetCollisionResponseToAllChannels(ECR_Block);
    Mesh->SetCollisionResponseToChannel(ECC_Pawn, ECR_Ignore);
    Mesh->SetCollisionResponseToChannel(ECC_Vehicle, ECR_Ignore);
    Mesh->SetCollisionResponseToChannel(ECC_Visibility, ECR_Ignore);
    Mesh->SetCollisionResponseToChannel(ECC_Camera, ECR_Ignore);
    Mesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    Mesh->SetSimulatePhysics(true);
    Mesh->WakeAllRigidBodies();
    return Mesh->IsSimulatingPhysics();
}

void UReflectionsNpcReactionComponent::KickRagdoll(const FReflectionsSpellHitData& Hit)
{
    AActor* Owner = GetOwner();
    USkeletalMeshComponent* Body = FindNpcBody(Owner);
    if (!Body || !Body->IsSimulatingPhysics() || !ReflectionsSpellCatalog::IsValid(Hit.Spell)) return;

    const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(Hit.Spell);
    const bool bBlast = Spec.Radius >= 180.0f;
    FVector Direction = Hit.Impulse.GetSafeNormal();
    if (Direction.IsNearlyZero()) Direction = -Hit.ImpactNormal.GetSafeNormal();
    if (Direction.IsNearlyZero() && IsValid(Hit.Caster))
        Direction = (Owner->GetActorLocation() - Hit.Caster->GetActorLocation()).GetSafeNormal();
    if (Direction.IsNearlyZero()) Direction = Owner->GetActorForwardVector();

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
    // GetClosestPointOnPhysicsAsset indexes the component-space bone array directly (no bounds check) unless
    // a leader pose drives the mesh. That array can be empty on a live body; it asserted in Array.h and
    // crashed the editor on a lethal spell hit. Without a full pose there is nothing to aim the kick at.
    if (!BodyPoseReady(Body)) return;
    if (Bone.IsNone() || !Body->GetBodyInstance(Bone))
        if (Body->GetClosestPointOnPhysicsAsset(Hit.Location, Closest, false)) Bone = Closest.BoneName;
    if (Bone.IsNone() || !Body->GetBodyInstance(Bone) || !Body->IsSimulatingPhysics(Bone))
    {
        // Query-only target capsules usually do not report a skeletal bone.
        // Some MetaHuman physics assets also omit torso and pelvis bodies.
        const FName Candidates[] = { TEXT("upperarm_l"), TEXT("upperarm_r"), TEXT("lowerarm_l"), TEXT("lowerarm_r"), TEXT("head") };
        Bone = NAME_None;
        float ClosestDistance = TNumericLimits<float>::Max();
        for (const FName Candidate : Candidates)
        {
            if (!Body->GetBodyInstance(Candidate) || !Body->IsSimulatingPhysics(Candidate)) continue;
            const float Distance = FVector::DistSquared(Body->GetBoneLocation(Candidate), Hit.Location);
            if (Distance < ClosestDistance) { ClosestDistance = Distance; Bone = Candidate; }
        }
    }
    if (Bone.IsNone()) return;
    FBodyInstance* Instance = Body->GetBodyInstance(Bone);
    if (!Instance || !Body->IsSimulatingPhysics(Bone)) return;

    const FVector Point = Body->GetBoneLocation(Bone) + (Hit.Location - Body->GetBoneLocation(Bone)).GetClampedToMaxSize(30.0f);
    const float Speed = FMath::Clamp(Hit.Impulse.Size() * 1.5f, 100.0f, 600.0f);
    Body->AddImpulseAtLocation(Direction * Speed * FMath::Max(1.0f, Instance->GetBodyMass()), Point, Bone);
}

void UReflectionsNpcReactionComponent::OnOwnerDied(AActor* Source)
{
    if (IsIncapacitated()) return;
    AActor* Owner = GetOwner();
    const UReflectionsNpcArchetype* Active = GetActiveArchetype();
    if (HitMesh.IsValid()) EndPhysicalHit();
    EndFlinch();
    KnockbackVelocity = FVector::ZeroVector;
    SetReaction(EReflectionsNpcReaction::Incapacitated, Source, Owner->GetActorLocation());
    bFreshDeath = true;
    bHunting = false;
    CastWindupRemaining = 0.0f;
    EndCastTelegraph();
    CancelTarnishCast();
    // Whatever it was going through ends here: the loops stop, the walker's clock runs again, and it has a last
    // sound of its own. One that dies while the current runs through it goes on twitching on the ground.
    if (bShocked)
    {
        CorpseShockRemaining = 0.9f;
        ShockFlashIn = 0.0f;
    }
    EndShock(true);
    EndBurning();
    EndFreeze();
    if (Subsystem.IsValid() && CVarNpcElementReactions.GetValueOnGameThread() != 0) Subsystem->PlayReaction(Owner, TEXT("React_Death"));
    ScriptedHoldRemaining = 0.0f;
    EngagedTarget.Reset();
    if (Motor) Motor->SetCombatTarget(nullptr);
    if (ACharacter* Mover = GetMovementCharacter())
    {
        Mover->GetCharacterMovement()->StopMovementImmediately();
        Mover->GetCharacterMovement()->DisableMovement();
        Mover->GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    }
    // Aim assist skips hidden pawns; the locomotion pawn has nothing left to drive.
    if (ACharacter* Driver = LocomotionDriver.Get()) Driver->SetActorHiddenInGame(true);
    // The capsule stands where the NPC died while the body falls elsewhere: stop it catching spells.
    TInlineComponentArray<UCapsuleComponent*> Capsules(Owner);
    for (UCapsuleComponent* Capsule : Capsules)
        if (Capsule && Capsule->ComponentHasTag(HitProxyTag)) Capsule->SetCollisionEnabled(ECollisionEnabled::NoCollision);

    const bool bWantsRagdoll = bEnableRagdollOnDeath || (Active && Active->bRagdollOnLethalHit);
    if (!bWantsRagdoll || !StartRagdoll())
    {
        // No usable physics body: freeze the pose and tip over so the death still reads.
        if (USkeletalMeshComponent* Body = FindNpcBody(Owner)) Body->bPauseAnims = true;
        ToppleStart = Owner->GetActorRotation();
        ToppleRemaining = 0.6f;
    }
    if (Subsystem.IsValid()) Subsystem->NotifyDied(this, Source);
}

void UReflectionsNpcReactionComponent::OnHealthChanged(float Health, float MaxHealth, AActor* Source)
{
    const float Healed = Health - LastKnownHealth;
    LastKnownHealth = Health;
    if (Healed > 0.0f && Subsystem.IsValid()) Subsystem->NotifyHealed(this, Source, Healed);
}

// ---- Movement ----------------------------------------------------------------------------------------------

void UReflectionsNpcReactionComponent::InitializeLocomotion()
{
    bTriedLocomotion = true;
    AActor* Actor = GetOwner();
    if (!bUseSampleLocomotion) return;
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

    // The walker is the hero's sample pawn with nobody looking through it. Its gameplay camera starts itself and
    // would run a camera system of its own every frame (about 0.4 ms of game thread per NPC, measured by the
    // performance session), so everything camera-like on it is switched off. By class name: the camera plugin's
    // headers are not a dependency of this module.
    TInlineComponentArray<UActorComponent*> DriverComponents(Driver);
    for (UActorComponent* Component : DriverComponents)
    {
        if (!Component) continue;
        const FString ClassName = Component->GetClass()->GetName();
        if (ClassName.Contains(TEXT("Camera")) || ClassName.Contains(TEXT("SpringArm")))
        {
            Component->Deactivate();
            Component->SetComponentTickEnabled(false);
        }
        // The same pawn brings the animation sample's foley: its walk clips fire a notify that asks this
        // component for a sound and plays it (footsteps from an invisible body, in sample audio the jam does not
        // ship, at a cost the performance session measured). The component stays, because without it the notify
        // falls back to its own default sound bank; it is handed an empty bank instead, so every lookup finds
        // nothing. By name: these are Blueprint classes of the sample.
        else if (ClassName == TEXT("AC_FoleyEvents_C") && CVarNpcWalkerFoley.GetValueOnGameThread() == 0)
        {
            if (const FObjectPropertyBase* Bank = FindFProperty<FObjectPropertyBase>(Component->GetClass(), TEXT("FoleyEventBank")))
            {
                const UObject* Current = Bank->GetObjectPropertyValue_InContainer(Component);
                UClass* BankClass = Current ? Current->GetClass() : Bank->PropertyClass.Get();
                if (BankClass && !BankClass->HasAnyClassFlags(CLASS_Abstract))
                    Bank->SetObjectPropertyValue_InContainer(Component, NewObject<UObject>(Component, BankClass, NAME_None, RF_Transient));
            }
        }
    }

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
    // A frightened walker must not run off the edge of the floor.
    Movement->bCanWalkOffLedges = false;
    Driver->bUseControllerRotationYaw = false;
    Movement->AddTickPrerequisiteComponent(this);

    Actor->AttachToComponent(Driver->GetMesh(), FAttachmentTransformRules::KeepWorldTransform);
    Body->AddTickPrerequisiteComponent(Driver->GetMesh());
    Body->ComponentTags.AddUnique(TEXT("CrowdSample"));
    Body->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    Body->SetAnimInstanceClass(AnimClass);
    // Every step of the walker moves the whole MetaHuman attached to it. The parts that only copy the body's
    // pose (outfit pieces, the face) need no bounds of their own and never take part in overlaps: they take the
    // body's bounds and stop raising overlap events. Only parts attached directly to the mesh they follow; the
    // body, the hit capsule and the walker keep everything, since spells, pickups and triggers use them.
    if (CVarNpcLeanFollowers.GetValueOnGameThread() != 0)
    {
        TInlineComponentArray<USkeletalMeshComponent*> Parts(Actor);
        for (USkeletalMeshComponent* Part : Parts)
        {
            USkinnedMeshComponent* Leader = Part ? Part->LeaderPoseComponent.Get() : nullptr;
            if (!Leader || Part == Body || Part->GetAttachParent() != Leader) continue;
            Part->SetGenerateOverlapEvents(false);
            Part->bUseAttachParentBound = true;
            Part->UpdateBounds();
            Part->MarkRenderTransformDirty();
        }
    }
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
    const UReflectionsNpcArchetype* Active = GetActiveArchetype();
    const float ReactionSpeed = Active ? Active->Reaction.ReactionSpeed : 210.0f;
    const float CalmSpeed = Active ? Active->Reaction.CalmSpeed : 140.0f;
    const FVector Here = Actor->GetActorLocation();
    FVector Direction = (Target - Here).GetSafeNormal2D();
    if (Direction.IsNearlyZero()) return;
    if (ACharacter* Driver = LocomotionDriver.Get())
    {
        // The sample sets max speed in its own pre-movement update. Supply
        // analog input through CMC so pose search sees the actual trajectory.
        const float DesiredSpeed = Reaction == EReflectionsNpcReaction::Calm ? CalmSpeed : ReactionSpeed;
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

void UReflectionsNpcReactionComponent::UpdateHunt()
{
    const UReflectionsNpcArchetype* Active = GetActiveArchetype();
    // The town's defenders hunt as well, but only the tarnished: never the player on sight. Not while the squad
    // layer steers them (it picks their fights).
    const bool bDefender = Active && Active->Combat.bFightsTarnished && !bExternallySteered &&
        !UReflectionsNpcArchetype::IsHostileDisposition(Disposition);
    if (!Active || (!Active->Combat.bHuntPlayerOnSight && !bDefender) || !Active->Reaction.bCanAttack)
    {
        bHunting = false;
        return;
    }
    AActor* Owner = GetOwner();
    APawn* Player = UGameplayStatics::GetPlayerPawn(this, 0);
    // Sight is needed to pick the player up, not to keep after them.
    const bool bSeesPlayer = Active->Combat.bHuntPlayerOnSight && IsAttackable(Player) &&
        FVector::DistSquared2D(Owner->GetActorLocation(), Player->GetActorLocation()) <= FMath::Square(Active->Combat.SightRadius) &&
        ((bHunting && Focus == Player) || HasLineOfSight(Owner, Player, LocomotionDriver.Get()));
    AActor* Quarry = bSeesPlayer ? Player : nullptr;
    if (Active->Combat.bHuntsNpcs || bDefender)
    {
        // Those who hunt the townspeople go for whoever is nearer, the player or an NPC. The list is walked a
        // few times a second, not every frame; in between it stays on what it had.
        AActor* Current = bHunting && IsPrey(Focus.Get()) ? Focus.Get() : nullptr;
        const UWorld* World = GetWorld();
        const float Now = World ? World->GetTimeSeconds() : 0.0f;
        AActor* Prey = Current;
        if (Now >= NextPreyScanTime || !Current)
        {
            NextPreyScanTime = Now + 0.4f;
            Prey = FindNpcPrey(Current);
        }
        if (Prey && (!Quarry || FVector::DistSquared2D(Owner->GetActorLocation(), Prey->GetActorLocation()) <
                FVector::DistSquared2D(Owner->GetActorLocation(), Quarry->GetActorLocation())))
            Quarry = Prey;
    }
    if (Quarry)
    {
        bHunting = true;
        if (Reaction != EReflectionsNpcReaction::Attacking || Focus != Quarry)
            SetReaction(EReflectionsNpcReaction::Attacking, Quarry, Quarry->GetActorLocation());
        else
        {
            ThreatLocation = Quarry->GetActorLocation();
            ReactionTimeRemaining = FMath::Max(ReactionTimeRemaining, 1.0f);
        }
    }
    else if (bHunting)
    {
        // Lost them: stand down at once unless it was provoked and is still angry.
        bHunting = false;
        if (ProvokedRemaining <= 0.0f && Reaction == EReflectionsNpcReaction::Attacking)
            SetReaction(EReflectionsNpcReaction::Calm, nullptr, Owner->GetActorLocation());
    }
}

void UReflectionsNpcReactionComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* TickFunction)
{
    Super::TickComponent(DeltaTime, TickType, TickFunction);
    AActor* Owner = GetOwner();
    const UReflectionsNpcArchetype* Active = GetActiveArchetype();
    if (!Owner || !Active) return;
    if (!IsIncapacitated()) RepairBodyPose();
    if (!bTriedLocomotion && !IsIncapacitated()) InitializeLocomotion();
    if (HitMesh.IsValid())
    {
        HitPhysicsRemaining -= DeltaTime;
        if (HitPhysicsRemaining <= 0.0f) EndPhysicalHit();
        else if (HitPhysicsRemaining < HitPhysicsDuration * 0.5f)
            HitMesh->SetAllBodiesBelowPhysicsBlendWeight(HitPhysicsRoot, HitPhysicsPeakWeight * HitPhysicsRemaining / (HitPhysicsDuration * 0.5f), false, true);
    }
    if (!KnockbackVelocity.IsNearlyZero() && !IsIncapacitated())
    {
        FHitResult Hit;
        AActor* MovingActor = LocomotionDriver.IsValid() ? static_cast<AActor*>(LocomotionDriver.Get()) : Owner;
        MovingActor->AddActorWorldOffset(KnockbackVelocity * DeltaTime, true, &Hit);
        KnockbackVelocity *= FMath::Exp(-6.0f * DeltaTime);
        if (KnockbackVelocity.SizeSquared() < 25.0f) KnockbackVelocity = FVector::ZeroVector;
    }
    if (bFlinching)
    {
        FlinchRemaining -= DeltaTime;
        USceneComponent* Root = Owner->GetRootComponent();
        USceneComponent* Parent = Root ? Root->GetAttachParent() : nullptr;
        if (FlinchRemaining <= 0.0f || !Parent) EndFlinch();
        else
        {
            // Out fast, back slowly: a quarter of the time leaning, the rest recovering.
            const float Phase = 1.0f - FlinchRemaining / FlinchDuration;
            const float Lean = Phase < 0.25f ? Phase / 0.25f : 1.0f - (Phase - 0.25f) / 0.75f;
            const FVector LocalAxis = Parent->GetComponentTransform().InverseTransformVectorNoScale(FlinchAxis).GetSafeNormal();
            if (!LocalAxis.IsNearlyZero())
                Root->SetRelativeRotation(FQuat(LocalAxis, FMath::DegreesToRadians(FlinchAngle * FMath::InterpEaseOut(0.0f, 1.0f, Lean, 2.0f))) * FlinchRestRotation);
        }
    }
    if (HitFlash && HitFlashRemaining > 0.0f)
    {
        HitFlashRemaining = FMath::Max(0.0f, HitFlashRemaining - DeltaTime);
        HitFlash->SetIntensity(HitFlashPeak * HitFlashRemaining / 0.22f);
        if (HitFlashRemaining <= 0.0f) HitFlash->SetVisibility(false);
    }
    if (IsIncapacitated())
    {
        if (CorpseShockRemaining > 0.0f)
        {
            // Dropped by lightning: the body on the ground keeps twitching and flickering for a moment.
            CorpseShockRemaining -= DeltaTime;
            ShockFlashIn -= DeltaTime;
            if (ShockFlashIn <= 0.0f)
            {
                ShockFlashIn = 0.14f;
                StartHitFlash(ShockHit);
                TwitchRagdoll();
            }
        }
        if (ToppleRemaining > 0.0f)
        {
            ToppleRemaining = FMath::Max(0.0f, ToppleRemaining - DeltaTime);
            const float Alpha = FMath::InterpEaseIn(0.0f, 1.0f, 1.0f - ToppleRemaining / 0.6f, 2.0f);
            Owner->SetActorRotation(FRotator(ToppleStart.Pitch, ToppleStart.Yaw, ToppleStart.Roll + 86.0f * Alpha));
        }
        return;
    }

    if (BurningRemaining > 0.0f)
    {
        // Burning: it keeps crying out until it is over (it is already running if it is the running kind).
        BurningRemaining -= DeltaTime;
        NextBurnBarkIn -= DeltaTime;
        if (BurningRemaining <= 0.0f) EndBurning();
        else if (NextBurnBarkIn <= 0.0f && Subsystem.IsValid())
        {
            NextBurnBarkIn = FMath::FRandRange(1.5f, 2.5f);
            Subsystem->PlayReaction(Owner, TEXT("React_Burning"));
        }
    }
    if (bShocked || FrozenRemaining > 0.0f)
    {
        // Shocked or frozen: no thinking, no moving, no fighting until it is over.
        if (ACharacter* Mover = GetMovementCharacter()) Mover->GetCharacterMovement()->StopMovementImmediately();
        if (Motor) Motor->SetCombatTarget(nullptr);
        CastWindupRemaining = 0.0f;
        EndCastTelegraph();
        CancelTarnishCast();
        if (FrozenRemaining > 0.0f)
        {
            FrozenRemaining -= DeltaTime;
            if (FrozenRemaining <= 0.0f) EndFreeze();
        }
        if (bShocked)
        {
            // It flickers and the current keeps hurting it. If that kills it, the ordinary death takes over
            // from inside ApplyDamage (the body drops into its ragdoll).
            AActor* Caster = ShockHit.Caster;
            const APawn* CasterPawn = Cast<APawn>(Caster);
            AController* By = CasterPawn ? CasterPawn->GetController() : nullptr;
            ShockRemaining -= DeltaTime;
            ShockFlashIn -= DeltaTime;
            if (ShockFlashIn <= 0.0f)
            {
                ShockFlashIn = 0.18f;
                StartHitFlash(ShockHit);
            }
            ShockTickIn -= DeltaTime;
            if (ShockTickIn <= 0.0f && ShockDamageLeft > 0.0f)
            {
                ShockTickIn = 0.5f;
                const float Damage = FMath::Min(3.0f, ShockDamageLeft);
                ShockDamageLeft -= Damage;
                UGameplayStatics::ApplyDamage(Owner, Damage, By, Caster, UDamageType::StaticClass());
                if (IsIncapacitated()) return;
            }
            if (ShockRemaining <= 0.0f)
            {
                // The current stops. Those who were never fighters, and anyone it has left under half, do not
                // get up: they drop where they stand. The rest come round.
                const UReflectionsHealthComponent* Health = Owner->FindComponentByClass<UReflectionsHealthComponent>();
                const bool bDrops = Health && Health->Health > 0.0f &&
                    (!Active->Reaction.bCanAttack || Health->Health <= Health->MaxHealth * 0.5f);
                // Dropping is dying: the ordinary death ends the shock (with its sound) and lets the body fall.
                if (bDrops) UGameplayStatics::ApplyDamage(Owner, Health->Health + Health->Shield + 1.0f, By, Caster, UDamageType::StaticClass());
                if (IsIncapacitated()) return;
                EndShock(false);
            }
        }
        return;
    }
    if (ScriptedHoldRemaining > 0.0f)
    {
        // A set piece has this NPC: no thinking, no moving, no fighting until it lets go or the time runs out.
        ScriptedHoldRemaining = FMath::Max(0.0f, ScriptedHoldRemaining - DeltaTime);
        CastWindupRemaining = 0.0f;
        EndCastTelegraph();
        CancelTarnishCast();
        if (Motor) Motor->SetCombatTarget(nullptr);
        return;
    }
    ProvokedRemaining = FMath::Max(0.0f, ProvokedRemaining - DeltaTime);
    AttackCooldown = FMath::Max(0.0f, AttackCooldown - DeltaTime);
    HeatCheckIn -= DeltaTime;
    if (HeatCheckIn <= 0.0f)
    {
        HeatCheckIn = 0.5f;
        TickHeat();
    }
    if (!UpdateEngagement()) UpdateHunt();

    // Reached an NPC it converts: hand both over to the villain's sequence; refused, it just attacks.
    if (Active->Combat.bConvertsNpcs && Reaction == EReflectionsNpcReaction::Attacking && Subsystem.IsValid() && IsPrey(Focus.Get()))
    {
        const UWorld* World = GetWorld();
        const float Now = World ? World->GetTimeSeconds() : 0.0f;
        if (Now >= ConversionRetryTime &&
            FVector::DistSquared2D(Owner->GetActorLocation(), Focus->GetActorLocation()) <= FMath::Square(Active->Combat.ConversionRange))
        {
            ConversionRetryTime = Now + 2.0f;
            if (Subsystem->TryBeginConversion(this, Focus.Get())) return;
        }
    }

    // Those who cast at the player stop at range and throw spells; while they do, nothing else moves the body.
    const bool bCasting = TickSpellcasting(DeltaTime);

    // The melee motor (chase, windup, strike, recover) takes over the body while there is someone to fight.
    AActor* MotorTarget = nullptr;
    if (!bCasting && Motor && !bExternallySteered && Active->Combat.bUseMeleeMotor && Active->Reaction.bCanAttack && Motor->IsUsable() &&
        Reaction == EReflectionsNpcReaction::Attacking)
        MotorTarget = Focus.Get();
    if (Motor) Motor->SetCombatTarget(MotorTarget);

    if (Reaction == EReflectionsNpcReaction::Calm)
    {
        if (Active->Reaction.bRoamsWhenCalm && !bExternallySteered) TickAmbientMovement(DeltaTime);
        TickRemark(DeltaTime);
        return;
    }
    ReactionTimeRemaining -= DeltaTime;
    if (ReactionTimeRemaining <= 0.0f)
    {
        Fear = FMath::Max(0.0f, Fear - Active->Reaction.FearDecay);
        Hostility = FMath::Max(0.0f, Hostility - Active->Reaction.AggressionDecay);
        SetReaction(EReflectionsNpcReaction::Calm, nullptr, Owner->GetActorLocation());
        return;
    }
    // Whoever steers the body decides where it goes, except that a frightened NPC always runs by itself.
    if (bExternallySteered && Reaction != EReflectionsNpcReaction::Fleeing) return;
    if (Reaction == EReflectionsNpcReaction::Fleeing) TryMove(SafeDestination, DeltaTime);
    else if (Reaction == EReflectionsNpcReaction::Investigating &&
        FVector::Dist2D(Owner->GetActorLocation(), ThreatLocation) > Active->Reaction.InvestigateStopDistance) TryMove(ThreatLocation, DeltaTime);
    else if (Reaction == EReflectionsNpcReaction::Attacking && Focus.IsValid() && !MotorTarget && !bCasting)
    {
        const float Distance = FVector::Dist2D(Owner->GetActorLocation(), Focus->GetActorLocation());
        if (Active->Combat.bRangedCaster)
        {
            // A caster keeps its distance; the casts themselves come from whoever directs it.
            if (Distance < Active->Combat.RangedMinRange)
                TryMove(Owner->GetActorLocation() + (Owner->GetActorLocation() - Focus->GetActorLocation()).GetSafeNormal2D() * 300.0, DeltaTime);
            else if (Distance > Active->Combat.RangedMaxRange) TryMove(Focus->GetActorLocation(), DeltaTime);
        }
        // The simple attack: walk up and strike on a timer.
        else if (Distance > Active->Combat.SimpleAttackRange) TryMove(Focus->GetActorLocation(), DeltaTime);
        else if (AttackCooldown <= 0.0f && Active->Reaction.bCanAttack)
        {
            UGameplayStatics::ApplyDamage(Focus.Get(), Active->Combat.SimpleAttackDamage, nullptr, Owner, UDamageType::StaticClass());
            AttackCooldown = Active->Combat.SimpleAttackCooldown;
        }
    }
}
